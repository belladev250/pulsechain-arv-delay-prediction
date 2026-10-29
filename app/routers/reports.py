"""Shortage reports: create, list, restock and delete (always scoped to the user)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import auth
from config import OPTIONS
from database import get_db
from dependencies import check_choice, current_user
from schemas import ReportIn
from services.reports import my_reports


router = APIRouter()


@router.post("/api/reports", status_code=201)
def create_report(r: ReportIn, user=Depends(current_user)):
    # The server sets the location from the account, so a user cannot file a report
    # for a district or country that is not theirs by editing the request.
    if user["role"] == "district":
        r.country, r.district = user["country"], user["district"]
    elif user["role"] == "country":
        r.country = user["country"]
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


@router.get("/api/reports")
def list_reports(user=Depends(current_user)):
    conn = get_db()
    rows = my_reports(conn, user)
    conn.close()
    return rows


@router.delete("/api/reports/{report_id}")
def delete_report(report_id: int, user=Depends(current_user)):
    conn = get_db()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None or not auth.in_scope(user, row["country"], row["district"]):
        conn.close()
        raise HTTPException(status_code=404, detail="Report not found")
    conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()
    return {"deleted": report_id}


@router.patch("/api/reports/{report_id}/restock")
def restock(report_id: int, user=Depends(current_user)):
    conn = get_db()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None or not auth.in_scope(user, row["country"], row["district"]):
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
