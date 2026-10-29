"""Single and batch risk prediction, plus system and model information."""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from config import OPTIONS, STATS
from dependencies import check_choice, current_user, require_country
from schemas import BatchIn, ShipmentIn
from services.risk_model import heuristic_probability, risk_model


router = APIRouter()


@router.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": risk_model.loaded, "calibrated": bool(risk_model.loaded and risk_model.calibration)}


@router.get("/api/options")
def options(user=Depends(current_user)):
    if user["role"] == "admin":
        return OPTIONS
    return {**OPTIONS, "countries": [user["country"]]}


@router.post("/api/predict")
def predict(shipment: ShipmentIn, user=Depends(current_user)):
    check_choice(shipment.country, OPTIONS["countries"], "Country")
    require_country(user, shipment.country)
    if shipment.quantity <= 0 or shipment.value < 0:
        raise HTTPException(status_code=422, detail="Quantity must be positive and value cannot be negative")
    row = risk_model.build_row(shipment)
    if risk_model.loaded:
        raw = float(risk_model.predict_proba(row)[:, 1][0])
        source = risk_model.final_model_name
        reasons = risk_model.explain(row)
    else:
        hist = risk_model.history_for(shipment)
        v, c = hist["vendor_past_late_rate"], hist["country_past_late_rate"]
        raw = float(heuristic_probability(v, c, shipment.shipment_mode))
        source = "Heuristic (model file not found in app/models)"
        reasons = [
            {"feature": "vendor past late rate", "impact": round(float(v), 4), "direction": "raises risk"},
            {"feature": "country past late rate", "impact": round(float(c), 4), "direction": "raises risk"},
        ]
    prob = risk_model.calibrate(raw) if risk_model.loaded else raw
    return {"probability_late": round(prob, 4), "risk_score": round(raw, 4), "risk_band": risk_model.band_for(raw),
            "calibrated": bool(risk_model.loaded and risk_model.calibration), "source": source, "reasons": reasons,
            "vendor_history": risk_model.history_for(shipment), "country_history": STATS["countries"].get(shipment.country)}


@router.post("/api/predict/batch")
def predict_batch(batch: BatchIn, user=Depends(current_user)):
    if len(batch.shipments) == 0:
        raise HTTPException(status_code=400, detail="No shipments provided")
    for item in batch.shipments:
        require_country(user, item.country)
    if len(batch.shipments) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 shipments per request")
    rows = pd.concat([risk_model.build_row(s) for s in batch.shipments], ignore_index=True)
    if risk_model.loaded:
        probs = risk_model.predict_proba(rows)[:, 1]
    else:
        probs = []
        for s in batch.shipments:
            hist = risk_model.history_for(s)
            probs.append(heuristic_probability(hist["vendor_past_late_rate"], hist["country_past_late_rate"], s.shipment_mode))
    results = []
    for i, (s, p) in enumerate(zip(batch.shipments, probs)):
        shown = risk_model.calibrate(float(p)) if risk_model.loaded else float(p)
        results.append({"row": i + 1, "vendor": s.vendor, "country": s.country,
                        "shipment_mode": s.shipment_mode, "probability_late": round(shown, 4),
                        "risk_band": risk_model.band_for(float(p))})
    return {"count": len(results), "high": sum(1 for r in results if r["risk_band"] == "high"),
            "source": risk_model.final_model_name if risk_model.loaded else "Heuristic", "results": results}


@router.get("/api/model-info")
def model_info(user=Depends(current_user)):
    info = {**risk_model.load_metrics(), "model_loaded": risk_model.loaded, "thresholds": risk_model.threshold_info,
            "calibrated": bool(risk_model.loaded and risk_model.calibration),
            "feature_set": risk_model.feature_config.get("feature_set") if risk_model.feature_config else "original (13 features)",
            "final_model": risk_model.final_model_name}
    scored = risk_model.scored_shipments()
    if scored is not None:
        late = int(scored["actual_late"].sum())
        info["test_set"] = {**info["test_set"], "shipments": int(len(scored)), "late": late,
                            "late_share": round(late / len(scored), 3)}
    return info
