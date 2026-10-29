"""RiskModel: one object that owns the trained pipeline, calibration, risk bands and scored shipments."""
from datetime import datetime

import numpy as np
import pandas as pd

from config import METRICS, MODEL_PATH, MODELS_DIR, SHIPMENTS_PATH, STATS, load_json
from schemas import ShipmentIn
from services.explanations import clean_name, plain_reason

DEFAULT_FEATURES = ["planned_lead_time_days", "weight_kg", "freight_cost_usd", "Line Item Quantity",
                    "Line Item Value", "vendor_past_late_rate", "country_past_late_rate",
                    "vendor_shipment_count_so_far", "Country", "Shipment Mode", "Vendor INCO Term",
                    "Fulfill Via", "Product Group"]


def heuristic_probability(vendor_rate, country_rate, mode):
    """Fallback score used only when the trained model file is missing."""
    return min(0.95, 0.5 * vendor_rate + 0.3 * country_rate + (0.1 if mode == "Truck" else 0))


class RiskModel:
    def __init__(self):
        self.feature_config = load_json(MODELS_DIR / "feature_config.json")
        self.snapshot = load_json(MODELS_DIR / "history_snapshot.json")
        self.threshold_file = load_json(MODELS_DIR / "thresholds.json")
        self.calibration = load_json(MODELS_DIR / "calibration.json")
        if self.feature_config:
            self.feature_cols = self.feature_config["numeric"] + self.feature_config["categorical"]
        else:
            self.feature_cols = list(DEFAULT_FEATURES)
        self.shipments = pd.read_csv(SHIPMENTS_PATH) if SHIPMENTS_PATH.exists() else None
        self.final_model_name = (self.feature_config or {}).get("final_model", "LightGBM (tuned)")
        self.model = self._load_model()
        self._explainer = None
        self._scored = None
        self.high_threshold = 0.5
        self.medium_threshold = 0.3
        self.threshold_info = {"medium": 0.3, "high": 0.5, "data_driven": False}
        self._use_threshold_file()
        try:
            self.scored_shipments()
        except Exception as exc:
            print("Could not score shipments at startup:", exc)

    @property
    def loaded(self) -> bool:
        return self.model is not None

    @staticmethod
    def _load_model():
        try:
            import joblib
            if MODEL_PATH.exists():
                return joblib.load(MODEL_PATH)
        except Exception as exc:
            print("Model could not be loaded:", exc)
        return None

    def predict_proba(self, frame):
        return self.model.predict_proba(frame)

    # ----- features
    def history_for(self, s: ShipmentIn) -> dict:
        # Look up the vendor's and country's late rates from the saved snapshot of the
        # training period. An unknown vendor or country falls back to the global rate.
        overall = STATS["overall_late_rate"]
        snap = self.snapshot
        if snap:
            g_rate = snap["global_late_rate"]
            v = snap["vendors"].get(s.vendor)
            c = snap["countries"].get(s.country)
            pair = snap["pairs"].get(f"{s.vendor}|{s.country}")
            v_past = v["past_late_rate"] if v else g_rate
            c_past = c["past_late_rate"] if c else g_rate
            return {
                "vendor_past_late_rate": v_past,
                "vendor_recent_late_rate": v["recent_late_rate"] if v else g_rate,
                "country_past_late_rate": c_past,
                "country_recent_late_rate": c["recent_late_rate"] if c else g_rate,
                "global_recent_late_rate": snap["global_recent_late_rate"],
                "vendor_country_late_rate": pair["late_rate"] if pair else v_past,
                "vendor_shipment_count_so_far": v["count"] if v else 0,
                "vendor_country_count": pair["count"] if pair else 0,
            }
        v = STATS["vendors"].get(s.vendor)
        c = STATS["countries"].get(s.country)
        return {
            "vendor_past_late_rate": v["late_rate"] if v else overall,
            "country_past_late_rate": c["late_rate"] if c else overall,
            "vendor_shipment_count_so_far": v["count"] if v else 0,
        }

    def build_row(self, s: ShipmentIn) -> pd.DataFrame:
        lead = s.planned_lead_time_days if s.planned_lead_time_days is not None else np.nan
        weight = s.weight_kg if s.weight_kg is not None else np.nan
        freight = s.freight_cost_usd if s.freight_cost_usd is not None else np.nan
        values = {
            "planned_lead_time_days": lead,
            "weight_kg": weight,
            "freight_cost_usd": freight,
            "Line Item Quantity": s.quantity,
            "Line Item Value": s.value,
            "has_lead_time": 0 if pd.isna(lead) else 1,
            "value_per_unit": s.value / s.quantity if s.quantity else np.nan,
            "freight_per_kg": freight / weight if (not pd.isna(freight) and not pd.isna(weight) and weight) else np.nan,
            "scheduled_month": datetime.utcnow().month,
            "Country": s.country,
            "Shipment Mode": np.nan if s.shipment_mode in ("Unknown", "", None) else s.shipment_mode,
            "Vendor INCO Term": s.inco_term,
            "Fulfill Via": s.fulfill_via,
            "Product Group": s.product_group,
        }
        values.update(self.history_for(s))
        return pd.DataFrame([{col: values.get(col, np.nan) for col in self.feature_cols}])

    # ----- explanation
    def explain(self, row: pd.DataFrame):
        try:
            pre = self.model.named_steps["pre"]
            clf = self.model.named_steps["clf"]
            X = np.asarray(pre.transform(row))
            names = pre.get_feature_names_out()
            if hasattr(clf, "coef_"):
                sv = X[0] * clf.coef_[0]
            else:
                import shap
                if self._explainer is None:
                    self._explainer = shap.TreeExplainer(clf)
                values = self._explainer.shap_values(X)
                values = values[1] if isinstance(values, list) else values
                values = np.array(values)
                if values.ndim == 3:
                    values = values[:, :, 1]
                sv = values[0]
            top = np.argsort(-np.abs(sv))[:4]
            out = []
            for i in top:
                direction = "raises risk" if sv[i] > 0 else "lowers risk"
                out.append({"feature": clean_name(str(names[i])), "impact": round(float(sv[i]), 4),
                            "direction": direction, "plain": plain_reason(str(names[i]), row.iloc[0], direction)})
            return out
        except Exception as exc:
            print("Explanation unavailable:", exc)
            return []

    # ----- calibration and risk bands
    def calibrate(self, prob: float) -> float:
        # The raw score is not a true probability. The isotonic curve saved from training maps it
        # to one. The result is kept between 2% and 50% because only 82 late shipments were
        # available to test, so higher values would look more certain than they are.
        if self.calibration:
            value = float(np.interp(prob, self.calibration["x"], self.calibration["y"]))
            return min(max(value, 0.02), 0.50)
        return float(prob)

    def band_for(self, prob: float) -> str:
        return "high" if prob >= self.high_threshold else "medium" if prob >= self.medium_threshold else "low"

    def _use_threshold_file(self):
        tf = self.threshold_file
        if tf and tf.get("mode") == "percentile":
            self.medium_threshold = float(tf["medium"])
            self.high_threshold = float(tf["high"])
            self.threshold_info = {"medium": round(self.medium_threshold, 3), "high": round(self.high_threshold, 3),
                                   "data_driven": True, "from_validation": True,
                                   "rule": "Bands are relative: High is the top 15% of validation scores and Medium the next 25%. "
                                           "Percentile bands keep the number of alerts manageable even when the overall late rate shifts between periods."}

    def _compute_thresholds(self, df):
        # Percentile bands (top 15% = high, next 25% = medium) keep the number of alerts
        # manageable even if the overall late rate changes between periods.
        if self.threshold_file and self.threshold_file.get("mode") == "percentile":
            return
        scores = df["probability_late"]
        medium = float(np.percentile(scores, 60))
        high = max(float(np.percentile(scores, 85)), medium)
        self.medium_threshold, self.high_threshold = medium, high
        self.threshold_info = {"medium": round(medium, 3), "high": round(high, 3), "data_driven": True, "from_validation": False,
                               "rule": "Bands are relative to recent shipments: High is the top 15% of risk scores and Medium the next 25%. "
                                       "No labels are used, and percentile bands keep the number of alerts manageable even when the overall late rate shifts between periods."}

    # ----- scoring of the held-out shipments
    def scored_shipments(self):
        if self._scored is not None or self.shipments is None:
            return self._scored
        df = self.shipments.copy()
        if self.loaded:
            df["risk_score"] = self.predict_proba(df[self.feature_cols])[:, 1]
            df["probability_late"] = df["risk_score"].apply(self.calibrate)
            self._compute_thresholds(df.assign(probability_late=df["risk_score"]))
        else:
            country_col = "country_past_late_rate" if "country_past_late_rate" in df else "country_recent_late_rate"
            df["probability_late"] = [heuristic_probability(v, c, m) for v, c, m in
                                      zip(df["vendor_past_late_rate"], df[country_col], df["Shipment Mode"])]
            df["risk_score"] = df["probability_late"]
        df["risk_band"] = df["risk_score"].apply(self.band_for)
        self._scored = df
        return self._scored

    def load_metrics(self):
        csv_path = MODELS_DIR / "initial_metrics.csv"
        if csv_path.exists():
            try:
                table = pd.read_csv(csv_path)
                models = [{"name": r["Model"], "precision": float(r["Precision"]), "recall": float(r["Recall"]),
                           "f1": float(r["F1"]), "f2": float(r["F2 (recall-weighted)"]), "roc_auc": float(r["ROC-AUC"]),
                           "pr_auc": float(r["PR-AUC"]) if "PR-AUC" in table.columns else None,
                           "flagged_share": float(r["Flagged share"]) if "Flagged share" in table.columns else None,
                           "top20_precision": float(r["Top-20% precision"]) if "Top-20% precision" in table.columns else None,
                           "top20_recall": float(r["Top-20% recall"]) if "Top-20% recall" in table.columns else None,
                           "lift20": float(r["Lift@20%"]) if "Lift@20%" in table.columns else None}
                          for _, r in table.iterrows()]
                return {**METRICS, "models": models, "from_notebook": True}
            except Exception as exc:
                print("Could not read initial_metrics.csv:", exc)
        return {**METRICS, "from_notebook": False}


risk_model = RiskModel()
