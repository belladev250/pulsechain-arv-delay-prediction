"""Shared FastAPI dependencies: who is signed in, role checks and input checks."""
from typing import Optional

from fastapi import Depends, Header, HTTPException

import auth
from config import BASE
from database import get_db
from services.risk_model import risk_model

SECRET = auth.load_secret(BASE)
LIMITER = auth.LoginLimiter()

PUBLIC_FIELDS = "id, name, email, role, country, district, approved, is_demo, created_at"


def current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in")
    uid = auth.read_token(authorization[7:].strip(), SECRET)
    if uid is None:
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    # Read the user from the database on every request so a deactivated or changed account
    # loses access immediately, instead of trusting the token until it expires.
    conn = get_db()
    row = conn.execute("SELECT " + PUBLIC_FIELDS + " FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    if row is None or not row["approved"]:
        raise HTTPException(status_code=401, detail="Account not active")
    return dict(row)


def admin_only(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def manager_only(user=Depends(current_user)):
    if user["role"] not in ("admin", "country"):
        raise HTTPException(status_code=403, detail="Not allowed for your role")
    return user


def require_country(user, country):
    if not auth.in_scope(user, country):
        raise HTTPException(status_code=403, detail="This data belongs to another country")


def shipment_country(shipment_id):
    df = risk_model.scored_shipments()
    if df is None:
        raise HTTPException(status_code=404, detail="upcoming_shipments.csv not found in app/data")
    match = df[df["shipment_id"] == shipment_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return match.iloc[0]["Country"]


def check_choice(value, allowed, label):
    if value not in allowed:
        raise HTTPException(status_code=422, detail=f"{label} must be one of: {', '.join(allowed)}")
