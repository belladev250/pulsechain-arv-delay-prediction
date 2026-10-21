import json
import random
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = Path(__file__).parent
DB_PATH = BASE / "pulsechain.db"
MODEL_PATH = BASE / "models" / "model_pipeline.joblib"
if not MODEL_PATH.exists():
    MODEL_PATH = BASE / "models" / "lgbm_pipeline.joblib"
OPTIONS = json.loads((BASE / "data" / "options.json").read_text())
STATS = json.loads((BASE / "data" / "stats.json").read_text())

METRICS = json.loads((BASE / "data" / "metrics.json").read_text())
SHIPMENTS_PATH = BASE / "data" / "upcoming_shipments.csv"


def load_json(path):
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception as exc:
        print("Could not read", path.name, exc)
        return None


FEATURE_CONFIG = load_json(BASE / "models" / "feature_config.json")
SNAPSHOT = load_json(BASE / "models" / "history_snapshot.json")
THRESHOLD_FILE = load_json(BASE / "models" / "thresholds.json")
CALIBRATION = load_json(BASE / "models" / "calibration.json")
if FEATURE_CONFIG:
    FEATURE_COLS = FEATURE_CONFIG["numeric"] + FEATURE_CONFIG["categorical"]
else:
    FEATURE_COLS = ["planned_lead_time_days", "weight_kg", "freight_cost_usd", "Line Item Quantity",
                    "Line Item Value", "vendor_past_late_rate", "country_past_late_rate",
                    "vendor_shipment_count_so_far", "Country", "Shipment Mode", "Vendor INCO Term",
                    "Fulfill Via", "Product Group"]
SHIPMENTS = pd.read_csv(SHIPMENTS_PATH) if SHIPMENTS_PATH.exists() else None
FINAL_MODEL_NAME = (FEATURE_CONFIG or {}).get("final_model", "LightGBM (tuned)")
SCORED = None

MODEL = None
try:
    import joblib
    if MODEL_PATH.exists():
        MODEL = joblib.load(MODEL_PATH)
except Exception as exc:
    print("Model could not be loaded:", exc)

EXPLAINER = None
MODEL_LABEL = "Machine-learning model"

app = FastAPI(title="PulseChain API", version="0.1.0",
              description="Shipment delay-risk prediction and shortage reporting for HIV/ARV supply chains.")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility TEXT NOT NULL,
            district TEXT NOT NULL,
            country TEXT NOT NULL,
            product_group TEXT NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'shortage',
            reported_at TEXT NOT NULL,
            restocked_at TEXT,
            restock_days REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delay_reasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            note TEXT,
            logged_at TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            answers TEXT NOT NULL,
            sus_score REAL NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()

DELAY_REASONS = [
    "Customs clearance delay",
    "Supplier stock-out or production delay",
    "Transport or freight problem",
    "Documentation or paperwork error",
    "Funding or payment delay",
    "Weather, security or access problem",
    "Other",
]


class ShipmentIn(BaseModel):
    vendor: str
    country: str
    shipment_mode: str
    inco_term: str
    fulfill_via: str
    product_group: str
    quantity: float = 1000
    value: float = 10000
    planned_lead_time_days: Optional[float] = None
    weight_kg: Optional[float] = None
    freight_cost_usd: Optional[float] = None


class DelayReasonIn(BaseModel):
    reason: str
    note: Optional[str] = ""


class FeedbackIn(BaseModel):
    answers: List[int]
    comment: Optional[str] = ""


class BatchIn(BaseModel):
    shipments: List[ShipmentIn]


class ReportIn(BaseModel):
    facility: str
    district: str
    country: str
    product_group: str
    note: Optional[str] = ""


def history_for(s: ShipmentIn) -> dict:
    overall = STATS["overall_late_rate"]
    if SNAPSHOT:
        g_rate = SNAPSHOT["global_late_rate"]
        v = SNAPSHOT["vendors"].get(s.vendor)
        c = SNAPSHOT["countries"].get(s.country)
        pair = SNAPSHOT["pairs"].get(f"{s.vendor}|{s.country}")
        v_past = v["past_late_rate"] if v else g_rate
        c_past = c["past_late_rate"] if c else g_rate
        return {
            "vendor_past_late_rate": v_past,
            "vendor_recent_late_rate": v["recent_late_rate"] if v else g_rate,
            "country_past_late_rate": c_past,
            "country_recent_late_rate": c["recent_late_rate"] if c else g_rate,
            "global_recent_late_rate": SNAPSHOT["global_recent_late_rate"],
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


def build_row(s: ShipmentIn) -> pd.DataFrame:
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
    values.update(history_for(s))
    return pd.DataFrame([{col: values.get(col, np.nan) for col in FEATURE_COLS}])


def clean_name(name: str) -> str:
    for prefix in ("num__", "cat__"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.replace("_", " ")


CAT_BASES = ["Country", "Shipment Mode", "Vendor INCO Term", "Fulfill Via", "Product Group"]


def plain_reason(raw: str, row: pd.Series, direction: str) -> str:
    raw = raw.replace("num__", "").replace("cat__", "")
    effect = "raises" if direction == "raises risk" else "lowers"

    def num(key):
        value = row.get(key)
        return None if value is None or pd.isna(value) else float(value)

    if raw == "vendor_past_late_rate":
        return f"This vendor was late on {num(raw) * 100:.0f}% of its past shipments, which {effect} the risk compared with an average shipment."
    if raw == "country_past_late_rate":
        return f"Past shipments to this country were late {num(raw) * 100:.0f}% of the time, which {effect} the risk compared with an average shipment."
    if raw == "vendor_recent_late_rate":
        return f"This vendor was late on {num(raw) * 100:.0f}% of its most recent shipments, which {effect} the risk compared with an average shipment."
    if raw == "country_recent_late_rate":
        return f"Recent shipments to this country were late {num(raw) * 100:.0f}% of the time, which {effect} the risk compared with an average shipment."
    if raw == "global_recent_late_rate":
        return f"Across all vendors, {num(raw) * 100:.0f}% of recent shipments were late, which {effect} the risk compared with an average shipment."
    if raw == "vendor_country_late_rate":
        return f"This vendor was late on {num(raw) * 100:.0f}% of past shipments to this country, which {effect} the risk compared with an average shipment."
    if raw == "vendor_country_count":
        return f"The vendor has {num(raw):,.0f} earlier shipments to this country, which {effect} the risk compared with an average shipment."
    if raw == "has_lead_time":
        return ("A planned lead time was provided, which " + effect + " the risk." if num(raw)
                else "No planned lead time was provided, which " + effect + " the risk.")
    if raw == "value_per_unit":
        value = num(raw)
        return ("Unit value is unknown, which " + effect + " the risk." if value is None
                else f"A unit value of ${value:,.2f} {effect} the risk compared with an average shipment.")
    if raw == "freight_per_kg":
        value = num(raw)
        return ("Freight cost per kg is unknown, which " + effect + " the risk." if value is None
                else f"A freight cost of ${value:,.2f} per kg {effect} the risk compared with an average shipment.")
    if raw == "scheduled_month":
        return f"The delivery month ({num(raw):.0f}) {effect} the risk compared with an average shipment."
    if raw == "vendor_shipment_count_so_far":
        return f"The vendor has {num(raw):,.0f} earlier shipments on record, which {effect} the risk compared with an average shipment."
    if raw == "planned_lead_time_days":
        value = num(raw)
        return ("No planned lead time was provided, which " + effect + " the risk." if value is None
                else f"A planned lead time of {value:.0f} days {effect} the risk compared with an average shipment.")
    if raw == "weight_kg":
        value = num(raw)
        return ("Weight is missing for this shipment, which " + effect + " the risk." if value is None
                else f"A shipment weight of {value:,.0f} kg {effect} the risk compared with an average shipment.")
    if raw == "freight_cost_usd":
        value = num(raw)
        return ("Freight cost is missing for this shipment, which " + effect + " the risk." if value is None
                else f"A freight cost of ${value:,.0f} {effect} the risk compared with an average shipment.")
    if raw == "Line Item Quantity":
        return f"An order size of {num(raw):,.0f} units {effect} the risk compared with an average shipment."
    if raw == "Line Item Value":
        return f"An order value of ${num(raw):,.0f} {effect} the risk compared with an average shipment."
    for base in CAT_BASES:
        if raw.startswith(base + "_"):
            return f"{base}: {raw[len(base) + 1:]} {effect} the risk compared with an average shipment."
    return f"{clean_name(raw)} {effect} the risk compared with an average shipment."


def explain(row: pd.DataFrame):
    global EXPLAINER
    try:
        pre = MODEL.named_steps["pre"]
        clf = MODEL.named_steps["clf"]
        X = np.asarray(pre.transform(row))
        names = pre.get_feature_names_out()
        if hasattr(clf, "coef_"):
            sv = X[0] * clf.coef_[0]
        else:
            import shap
            if EXPLAINER is None:
                EXPLAINER = shap.TreeExplainer(clf)
            values = EXPLAINER.shap_values(X)
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


def heuristic_probability(vendor_rate, country_rate, mode):
    return min(0.95, 0.5 * vendor_rate + 0.3 * country_rate + (0.1 if mode == "Truck" else 0))


HIGH_THRESHOLD = 0.5
MEDIUM_THRESHOLD = 0.3
THRESHOLD_INFO = {"medium": 0.3, "high": 0.5, "data_driven": False}


def use_threshold_file():
    global HIGH_THRESHOLD, MEDIUM_THRESHOLD, THRESHOLD_INFO
    if THRESHOLD_FILE and THRESHOLD_FILE.get("mode") == "percentile":
        MEDIUM_THRESHOLD = float(THRESHOLD_FILE["medium"])
        HIGH_THRESHOLD = float(THRESHOLD_FILE["high"])
        THRESHOLD_INFO = {"medium": round(MEDIUM_THRESHOLD, 3), "high": round(HIGH_THRESHOLD, 3), "data_driven": True,
                          "from_validation": True,
                          "rule": "Bands are relative: High is the top 15% of validation scores and Medium the next 25%. "
                                  "Percentile bands keep the number of alerts manageable even when the overall late rate shifts between periods."}


use_threshold_file()


def calibrated(prob: float) -> float:
    if CALIBRATION:
        value = float(np.interp(prob, CALIBRATION["x"], CALIBRATION["y"]))
        return min(max(value, 0.02), 0.50)
    return float(prob)


def compute_thresholds(df):
    global HIGH_THRESHOLD, MEDIUM_THRESHOLD, THRESHOLD_INFO
    if THRESHOLD_FILE and THRESHOLD_FILE.get("mode") == "percentile":
        return
    scores = df["probability_late"]
    medium = float(np.percentile(scores, 60))
    high = max(float(np.percentile(scores, 85)), medium)
    MEDIUM_THRESHOLD, HIGH_THRESHOLD = medium, high
    THRESHOLD_INFO = {"medium": round(medium, 3), "high": round(high, 3), "data_driven": True, "from_validation": False,
                      "rule": "Bands are relative to recent shipments: High is the top 15% of risk scores and Medium the next 25%. "
                              "No labels are used, and percentile bands keep the number of alerts manageable even when the overall late rate shifts between periods."}


def band_for(prob: float) -> str:
    return "high" if prob >= HIGH_THRESHOLD else "medium" if prob >= MEDIUM_THRESHOLD else "low"


def scored_shipments():
    global SCORED
    if SCORED is not None or SHIPMENTS is None:
        return SCORED
    df = SHIPMENTS.copy()
    if MODEL is not None:
        df["risk_score"] = MODEL.predict_proba(df[FEATURE_COLS])[:, 1]
        df["probability_late"] = df["risk_score"].apply(calibrated)
        compute_thresholds(df.assign(probability_late=df["risk_score"]))
    else:
        df["probability_late"] = [heuristic_probability(v, c, m) for v, c, m in
                                  zip(df["vendor_past_late_rate"], df["country_past_late_rate"], df["Shipment Mode"])]
        df["risk_score"] = df["probability_late"]
    df["risk_band"] = df["risk_score"].apply(band_for)
    SCORED = df
    return SCORED


try:
    scored_shipments()
except Exception as exc:
    print("Could not score shipments at startup:", exc)


def load_metrics():
    csv_path = BASE / "models" / "initial_metrics.csv"
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


def check_choice(value, allowed, label):
    if value not in allowed:
        raise HTTPException(status_code=422, detail=f"{label} must be one of: {', '.join(allowed)}")


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": MODEL is not None, "calibrated": bool(MODEL is not None and CALIBRATION)}


@app.get("/api/options")
def options():
    return OPTIONS


@app.post("/api/predict")
def predict(shipment: ShipmentIn):
    check_choice(shipment.country, OPTIONS["countries"], "Country")
    if shipment.quantity <= 0 or shipment.value < 0:
        raise HTTPException(status_code=422, detail="Quantity must be positive and value cannot be negative")
    row = build_row(shipment)
    if MODEL is not None:
        raw = float(MODEL.predict_proba(row)[:, 1][0])
        source = FINAL_MODEL_NAME
        reasons = explain(row)
    else:
        v = row["vendor_past_late_rate"].iloc[0]
        c = row["country_past_late_rate"].iloc[0]
        raw = float(heuristic_probability(v, c, shipment.shipment_mode))
        source = "Heuristic (model file not found in app/models)"
        reasons = [
            {"feature": "vendor past late rate", "impact": round(float(v), 4), "direction": "raises risk"},
            {"feature": "country past late rate", "impact": round(float(c), 4), "direction": "raises risk"},
        ]
    prob = calibrated(raw) if MODEL is not None else raw
    return {"probability_late": round(prob, 4), "risk_score": round(raw, 4), "risk_band": band_for(raw),
            "calibrated": bool(MODEL is not None and CALIBRATION), "source": source, "reasons": reasons,
            "vendor_history": history_for(shipment), "country_history": STATS["countries"].get(shipment.country)}


@app.post("/api/predict/batch")
def predict_batch(batch: BatchIn):
    if len(batch.shipments) == 0:
        raise HTTPException(status_code=400, detail="No shipments provided")
    if len(batch.shipments) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 shipments per request")
    rows = pd.concat([build_row(s) for s in batch.shipments], ignore_index=True)
    if MODEL is not None:
        probs = MODEL.predict_proba(rows)[:, 1]
    else:
        probs = [heuristic_probability(v, c, m) for v, c, m in
                 zip(rows["vendor_past_late_rate"], rows["country_past_late_rate"], rows["Shipment Mode"])]
    results = []
    for i, (s, p) in enumerate(zip(batch.shipments, probs)):
        shown = calibrated(float(p)) if MODEL is not None else float(p)
        results.append({"row": i + 1, "vendor": s.vendor, "country": s.country,
                        "shipment_mode": s.shipment_mode, "probability_late": round(shown, 4),
                        "risk_band": band_for(float(p))})
    return {"count": len(results), "high": sum(1 for r in results if r["risk_band"] == "high"),
            "source": FINAL_MODEL_NAME if MODEL is not None else "Heuristic", "results": results}


@app.get("/api/shipments")
def list_shipments(country: Optional[str] = None, limit: int = 40):
    df = scored_shipments()
    if df is None:
        raise HTTPException(status_code=404, detail="upcoming_shipments.csv not found in app/data")
    if country:
        df = df[df["Country"] == country]
    df = df.sort_values(["risk_score", "probability_late"], ascending=False).head(limit)
    rows = []
    for _, r in df.iterrows():
        rows.append({"id": int(r["shipment_id"]), "vendor": r["vendor"], "country": r["Country"],
                     "shipment_mode": None if pd.isna(r["Shipment Mode"]) else r["Shipment Mode"],
                     "product_group": r["Product Group"], "scheduled_date": r["scheduled_date"],
                     "probability_late": round(float(r["probability_late"]), 4), "risk_band": r["risk_band"],
                     "actual_late": int(r["actual_late"])})
    return {"total": int(len(scored_shipments())), "shown": len(rows), "shipments": rows}


@app.get("/api/shipments/{shipment_id}/explain")
def explain_shipment(shipment_id: int):
    df = scored_shipments()
    if df is None:
        raise HTTPException(status_code=404, detail="upcoming_shipments.csv not found in app/data")
    match = df[df["shipment_id"] == shipment_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="Shipment not found")
    row = match.iloc[[0]]
    if MODEL is not None:
        reasons = explain(row[FEATURE_COLS])
    else:
        r = row.iloc[0]
        reasons = [
            {"feature": "vendor past late rate", "impact": 0, "direction": "raises risk",
             "plain": plain_reason("vendor_past_late_rate", r, "raises risk")},
            {"feature": "country past late rate", "impact": 0, "direction": "raises risk",
             "plain": plain_reason("country_past_late_rate", r, "raises risk")},
        ]
    return {"id": shipment_id, "vendor": row.iloc[0]["vendor"], "country": row.iloc[0]["Country"],
            "probability_late": round(float(row.iloc[0]["probability_late"]), 4),
            "risk_band": row.iloc[0]["risk_band"], "actual_late": int(row.iloc[0]["actual_late"]),
            "reasons": reasons}


@app.get("/api/delay-reasons/options")
def delay_reason_options():
    return DELAY_REASONS


@app.post("/api/shipments/{shipment_id}/delay-reasons", status_code=201)
def add_delay_reason(shipment_id: int, body: DelayReasonIn):
    df = scored_shipments()
    if df is None or df[df["shipment_id"] == shipment_id].empty:
        raise HTTPException(status_code=404, detail="Shipment not found")
    check_choice(body.reason, DELAY_REASONS, "Reason")
    conn = get_db()
    cur = conn.execute("INSERT INTO delay_reasons (shipment_id, reason, note, logged_at, is_demo) VALUES (?, ?, ?, ?, 0)",
                       (shipment_id, body.reason, (body.note or "").strip()[:300],
                        datetime.utcnow().isoformat(timespec="seconds")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "shipment_id": shipment_id, "reason": body.reason}


@app.get("/api/shipments/{shipment_id}/delay-reasons")
def list_delay_reasons(shipment_id: int):
    conn = get_db()
    rows = [dict(x) for x in conn.execute(
        "SELECT id, reason, note, logged_at, is_demo FROM delay_reasons WHERE shipment_id = ? ORDER BY id DESC",
        (shipment_id,)).fetchall()]
    conn.close()
    return rows


@app.post("/api/feedback", status_code=201)
def submit_feedback(body: FeedbackIn):
    if len(body.answers) != 10 or any(a < 1 or a > 5 for a in body.answers):
        raise HTTPException(status_code=422, detail="Provide 10 answers, each from 1 to 5")
    total = sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(body.answers))
    sus = total * 2.5
    conn = get_db()
    conn.execute("INSERT INTO feedback (answers, sus_score, comment, created_at) VALUES (?, ?, ?, ?)",
                 (json.dumps(body.answers), sus, (body.comment or "").strip()[:500],
                  datetime.utcnow().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"sus_score": sus}


@app.get("/api/feedback/summary")
def feedback_summary():
    conn = get_db()
    rows = [dict(x) for x in conn.execute("SELECT * FROM feedback ORDER BY id DESC").fetchall()]
    conn.close()
    if not rows:
        return {"responses": 0, "mean_sus": None, "comments": [], "scores": []}
    scores = [r["sus_score"] for r in rows]
    return {"responses": len(rows), "mean_sus": round(sum(scores) / len(scores), 1),
            "min": min(scores), "max": max(scores),
            "comments": [r["comment"] for r in rows if r["comment"]][:8], "scores": scores[::-1]}


@app.get("/api/model-info")
def model_info():
    info = {**load_metrics(), "model_loaded": MODEL is not None, "thresholds": THRESHOLD_INFO,
            "calibrated": bool(MODEL is not None and CALIBRATION),
            "feature_set": FEATURE_CONFIG.get("feature_set") if FEATURE_CONFIG else "original (13 features)",
            "final_model": FINAL_MODEL_NAME}
    scored = scored_shipments()
    if scored is not None:
        late = int(scored["actual_late"].sum())
        info["test_set"] = {**info["test_set"], "shipments": int(len(scored)), "late": late,
                            "late_share": round(late / len(scored), 3)}
    return info


@app.post("/api/reports", status_code=201)
def create_report(r: ReportIn):
    r.facility, r.district = (r.facility or "").strip(), (r.district or "").strip()
    if not (2 <= len(r.facility) <= 100) or not (2 <= len(r.district) <= 100):
        raise HTTPException(status_code=422, detail="Facility and district must be 2 to 100 characters")
    check_choice(r.country, OPTIONS["countries"], "Country")
    check_choice(r.product_group, OPTIONS["product_groups"], "Product group")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO reports (facility, district, country, product_group, note, status, reported_at) "
        "VALUES (?, ?, ?, ?, ?, 'shortage', ?)",
        (r.facility, r.district, r.country, r.product_group, r.note, datetime.utcnow().isoformat(timespec="seconds")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "status": "shortage"}


@app.get("/api/reports")
def list_reports():
    conn = get_db()
    rows = [dict(x) for x in conn.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()]
    conn.close()
    return rows


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: int):
    conn = get_db()
    cur = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": report_id}


@app.patch("/api/reports/{report_id}/restock")
def restock(report_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Report not found")
    if row["status"] == "restocked":
        conn.close()
        raise HTTPException(status_code=400, detail="Already restocked")
    now = datetime.utcnow()
    days = (now - datetime.fromisoformat(row["reported_at"])).total_seconds() / 86400
    conn.execute("UPDATE reports SET status='restocked', restocked_at=?, restock_days=? WHERE id=?",
                 (now.isoformat(timespec="seconds"), round(days, 2), report_id))
    conn.commit()
    conn.close()
    return {"id": report_id, "status": "restocked", "restock_days": round(days, 2)}


@app.get("/api/dashboard")
def dashboard():
    conn = get_db()
    rows = [dict(x) for x in conn.execute("SELECT * FROM reports").fetchall()]
    conn.close()
    open_n = sum(1 for r in rows if r["status"] == "shortage")
    done = [r["restock_days"] for r in rows if r["restock_days"] is not None]
    groups = {}
    for r in rows:
        key = (r["district"], r["country"])
        g = groups.setdefault(key, {"district": r["district"], "country": r["country"], "open": 0, "restocked": 0})
        g["open" if r["status"] == "shortage" else "restocked"] += 1
    overall = STATS["overall_late_rate"]
    scored = scored_shipments()
    country_risk = {}
    overall_pred = None
    if scored is not None:
        overall_pred = float(scored["probability_late"].mean())
        for country, g in scored.groupby("Country"):
            country_risk[country] = {"mean": float(g["probability_late"].mean()),
                                     "high": int((g["risk_band"] == "high").sum()), "total": int(len(g))}
    districts = []
    for g in groups.values():
        rate = STATS["countries"].get(g["country"], {}).get("late_rate", overall)
        g["country_late_rate"] = round(rate, 4)
        risk = country_risk.get(g["country"])
        g["predicted_risk"] = round(risk["mean"], 4) if risk else None
        g["high_risk_shipments"] = risk["high"] if risk else 0
        g["shipments_scored"] = risk["total"] if risk else 0
        if risk and overall_pred is not None:
            elevated = risk["mean"] >= overall_pred * 1.15
        else:
            elevated = rate >= overall
        g["attention"] = "high" if g["open"] >= 2 and elevated else "medium" if g["open"] > 0 else "ok"
        districts.append(g)
    districts.sort(key=lambda d: (-d["open"], -(d["predicted_risk"] or d["country_late_rate"])))
    return {"total_reports": len(rows), "open_shortages": open_n,
            "restocked": len(rows) - open_n,
            "avg_restock_days": round(sum(done) / len(done), 2) if done else None,
            "districts": districts, "overall_late_rate": round(overall, 4),
            "overall_predicted_risk": round(overall_pred, 4) if overall_pred is not None else None}


DEMO_SITES = [
    ("Kigali Central Pharmacy", "Gasabo", "Rwanda", 3), ("Nyagatare Health Centre", "Nyagatare", "Rwanda", 2),
    ("Huye Referral Hospital", "Huye", "Rwanda", 2), ("Kampala Health Centre IV", "Kampala", "Uganda", 4),
    ("Gulu Regional Store", "Gulu", "Uganda", 3), ("Mbarara Clinic", "Mbarara", "Uganda", 2),
    ("Dodoma Regional Store", "Dodoma", "Tanzania", 3), ("Arusha Health Centre", "Arusha", "Tanzania", 2),
    ("Bujumbura Clinic", "Mukaza", "Burundi", 6), ("Gitega Hospital", "Gitega", "Burundi", 4),
    ("Juba Teaching Hospital", "Juba", "South Sudan", 5), ("Addis Ababa Depot", "Addis Ababa", "Ethiopia", 1),
    ("Nairobi County Store", "Nairobi", "Kenya", 1),
]
SLOW_COUNTRIES = {"Burundi": 1.8, "South Sudan": 1.5}


@app.post("/api/seed")
def seed_demo_data():
    rng = random.Random(42)
    weights = [site[3] for site in DEMO_SITES]
    now = datetime.utcnow()
    conn = get_db()
    conn.execute("DELETE FROM reports WHERE note = 'Demo data'")
    created = 0
    for _ in range(48):
        facility, district, country, _w = rng.choices(DEMO_SITES, weights=weights, k=1)[0]
        product = "ARV" if rng.random() < 0.7 else "HRDT"
        age_days = rng.uniform(0.2, 13.5)
        reported = now - timedelta(days=age_days)
        status, restocked_at, restock_days = "shortage", None, None
        if rng.random() < 0.5:
            cap = min(6 * SLOW_COUNTRIES.get(country, 1.0), age_days * 0.9)
            days = rng.uniform(0.3, max(0.35, cap))
            status = "restocked"
            restock_days = round(days, 2)
            restocked_at = (reported + timedelta(days=days)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO reports (facility, district, country, product_group, note, status, reported_at, "
            "restocked_at, restock_days) VALUES (?, ?, ?, ?, 'Demo data', ?, ?, ?, ?)",
            (facility, district, country, product, status, reported.isoformat(timespec="seconds"),
             restocked_at, restock_days))
        created += 1
    conn.execute("DELETE FROM delay_reasons WHERE is_demo = 1")
    late = SHIPMENTS[SHIPMENTS["actual_late"] == 1] if SHIPMENTS is not None else None
    if late is not None and len(late) > 0:
        ids = [int(x) for x in late["shipment_id"].tolist()]
        for sid in rng.sample(ids, min(30, len(ids))):
            reason = rng.choices(DELAY_REASONS, weights=[4, 3, 5, 2, 1, 2, 1], k=1)[0]
            conn.execute("INSERT INTO delay_reasons (shipment_id, reason, note, logged_at, is_demo) VALUES (?, ?, 'Demo data', ?, 1)",
                         (sid, reason, (now - timedelta(days=rng.uniform(0, 12))).isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"seeded": created}


SIM_RNG = random.Random()


@app.post("/api/simulate/tick")
def simulate_tick():
    now = datetime.utcnow()
    conn = get_db()
    events = []
    facility, district, country, _w = SIM_RNG.choices(DEMO_SITES, weights=[x[3] for x in DEMO_SITES], k=1)[0]
    product = "ARV" if SIM_RNG.random() < 0.7 else "HRDT"
    conn.execute(
        "INSERT INTO reports (facility, district, country, product_group, note, status, reported_at) "
        "VALUES (?, ?, ?, ?, 'Demo data', 'shortage', ?)",
        (facility, district, country, product, now.isoformat(timespec="seconds")))
    events.append(f"New shortage at {facility} ({country})")
    if SIM_RNG.random() < 0.4:
        open_rows = conn.execute(
            "SELECT id, facility, country FROM reports WHERE note = 'Demo data' AND status = 'shortage'").fetchall()
        if open_rows:
            row = SIM_RNG.choice(open_rows)
            days = round(SIM_RNG.uniform(0.5, 6) * SLOW_COUNTRIES.get(row["country"], 1.0), 2)
            conn.execute("UPDATE reports SET status='restocked', restocked_at=?, restock_days=? WHERE id=?",
                         (now.isoformat(timespec="seconds"), days, row["id"]))
            events.append(f"{row['facility']} restocked")
    conn.commit()
    conn.close()
    return {"events": events}


@app.get("/api/analytics")
def analytics():
    conn = get_db()
    rows = [dict(x) for x in conn.execute("SELECT * FROM reports ORDER BY reported_at DESC").fetchall()]
    conn.close()

    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    opened = Counter(r["reported_at"][:10] for r in rows)
    closed = Counter(r["restocked_at"][:10] for r in rows if r["restocked_at"])
    timeline = [{"date": d.strftime("%d %b"), "reported": opened.get(d.isoformat(), 0),
                 "restocked": closed.get(d.isoformat(), 0)} for d in days]

    by_country = []
    for country in OPTIONS["countries"]:
        mine = [r for r in rows if r["country"] == country]
        done = [r["restock_days"] for r in mine if r["restock_days"] is not None]
        by_country.append({"country": country,
                           "open": sum(1 for r in mine if r["status"] == "shortage"),
                           "restocked": sum(1 for r in mine if r["status"] == "restocked"),
                           "avg_restock_days": round(sum(done) / len(done), 2) if done else None})

    demo_reports = sum(1 for r in rows if r["note"] == "Demo data")
    open_n = sum(1 for r in rows if r["status"] == "shortage")
    status = [{"name": "Open", "value": open_n}, {"name": "Restocked", "value": len(rows) - open_n}]

    risk_distribution, band_validation = [], []
    scored = scored_shipments()
    if scored is not None:
        upper = max(0.3, float(np.ceil(scored["probability_late"].max() * 10) / 10))
        counts, edges = np.histogram(scored["probability_late"], bins=np.linspace(0, upper, 11))
        risk_distribution = [{"range": f"{edges[i] * 100:.0f}%", "shipments": int(c)}
                             for i, c in enumerate(counts)]
        for band, label in [("low", "Low risk"), ("medium", "Medium risk"), ("high", "High risk")]:
            sub = scored[scored["risk_band"] == band]
            band_validation.append({"band": label, "shipments": int(len(sub)),
                                    "late_rate": round(float(sub["actual_late"].mean()) * 100, 1) if len(sub) else 0})

    conn = get_db()
    reason_rows = conn.execute("SELECT reason, COUNT(*) AS n, SUM(is_demo) AS demo FROM delay_reasons "
                               "GROUP BY reason ORDER BY n DESC").fetchall()
    conn.close()
    delay_reasons = [{"reason": r["reason"], "count": r["n"]} for r in reason_rows]
    demo_reasons = sum(int(r["demo"] or 0) for r in reason_rows)

    return {"delay_reasons": delay_reasons, "demo_delay_reasons": demo_reasons,
            "timeline": timeline, "by_country": by_country, "status": status,
            "risk_distribution": risk_distribution, "band_validation": band_validation,
            "baseline_late_rate": round(float(scored["actual_late"].mean()) * 100, 1) if scored is not None else None,
            "demo_reports": demo_reports, "total_reports": len(rows),
            "recent": rows[:6], "generated_at": datetime.utcnow().isoformat(timespec="seconds")}


DIST = BASE.parent / "frontend" / "dist"

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
    INDEX_FILE = DIST / "index.html"
else:
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    INDEX_FILE = BASE / "static" / "index.html"


@app.get("/")
def index():
    return FileResponse(INDEX_FILE)
