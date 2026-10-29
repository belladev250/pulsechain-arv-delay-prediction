"""Ranked held-out shipments, explanations and logged delay causes."""
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from config import DELAY_REASONS
from database import get_db
from dependencies import check_choice, current_user, require_country, shipment_country
from schemas import DelayReasonIn
from services.explanations import plain_reason
from services.risk_model import risk_model


router = APIRouter()


@router.get("/api/shipments")
def list_shipments(country: Optional[str] = None, limit: int = 40, user=Depends(current_user)):
    df = risk_model.scored_shipments()
    if df is None:
        raise HTTPException(status_code=404, detail="upcoming_shipments.csv not found in app/data")
    if user["role"] != "admin":
        df = df[df["Country"] == user["country"]]
    elif country:
        df = df[df["Country"] == country]
    df = df.sort_values(["risk_score", "probability_late"], ascending=False).head(limit)
    rows = []
    for _, r in df.iterrows():
        rows.append({"id": int(r["shipment_id"]), "vendor": r["vendor"], "country": r["Country"],
                     "shipment_mode": None if pd.isna(r["Shipment Mode"]) else r["Shipment Mode"],
                     "product_group": r["Product Group"], "scheduled_date": r["scheduled_date"],
                     "probability_late": round(float(r["probability_late"]), 4), "risk_band": r["risk_band"],
                     "actual_late": int(r["actual_late"])})
    return {"total": int(len(df)), "shown": len(rows), "shipments": rows}


@router.get("/api/shipments/{shipment_id}/explain")
def explain_shipment(shipment_id: int, user=Depends(current_user)):
    require_country(user, shipment_country(shipment_id))
    df = risk_model.scored_shipments()
    if df is None:
        raise HTTPException(status_code=404, detail="upcoming_shipments.csv not found in app/data")
    match = df[df["shipment_id"] == shipment_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="Shipment not found")
    row = match.iloc[[0]]
    if risk_model.loaded:
        reasons = risk_model.explain(row[risk_model.feature_cols])
    else:
        r = row.iloc[0]
        reasons = [
            {"feature": "vendor past late rate", "impact": 0, "direction": "raises risk",
             "plain": plain_reason("vendor_past_late_rate", r, "raises risk")},
            {"feature": "country recent late rate", "impact": 0, "direction": "raises risk",
             "plain": plain_reason("country_recent_late_rate", r, "raises risk")},
        ]
    return {"id": shipment_id, "vendor": row.iloc[0]["vendor"], "country": row.iloc[0]["Country"],
            "probability_late": round(float(row.iloc[0]["probability_late"]), 4),
            "risk_band": row.iloc[0]["risk_band"], "actual_late": int(row.iloc[0]["actual_late"]),
            "reasons": reasons}


@router.get("/api/delay-reasons/options")
def delay_reason_options(user=Depends(current_user)):
    return DELAY_REASONS


@router.post("/api/shipments/{shipment_id}/delay-reasons", status_code=201)
def add_delay_reason(shipment_id: int, body: DelayReasonIn, user=Depends(current_user)):
    require_country(user, shipment_country(shipment_id))
    df = risk_model.scored_shipments()
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


@router.get("/api/shipments/{shipment_id}/delay-reasons")
def list_delay_reasons(shipment_id: int, user=Depends(current_user)):
    require_country(user, shipment_country(shipment_id))
    conn = get_db()
    rows = [dict(x) for x in conn.execute(
        "SELECT id, reason, note, logged_at, is_demo FROM delay_reasons WHERE shipment_id = ? ORDER BY id DESC",
        (shipment_id,)).fetchall()]
    conn.close()
    return rows
