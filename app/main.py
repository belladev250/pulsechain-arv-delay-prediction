import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = Path(__file__).parent
DB_PATH = BASE / "pulsechain.db"
MODEL_PATH = BASE / "models" / "lgbm_pipeline.joblib"
OPTIONS = json.loads((BASE / "data" / "options.json").read_text())
STATS = json.loads((BASE / "data" / "stats.json").read_text())

MODEL = None
try:
    import joblib
    if MODEL_PATH.exists():
        MODEL = joblib.load(MODEL_PATH)
except Exception as exc:
    print("Model could not be loaded:", exc)

EXPLAINER = None

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
    conn.commit()
    conn.close()


init_db()


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


class ReportIn(BaseModel):
    facility: str
    district: str
    country: str
    product_group: str
    note: Optional[str] = ""


def build_row(s: ShipmentIn) -> pd.DataFrame:
    v = STATS["vendors"].get(s.vendor)
    c = STATS["countries"].get(s.country)
    overall = STATS["overall_late_rate"]
    return pd.DataFrame([{
        "planned_lead_time_days": s.planned_lead_time_days if s.planned_lead_time_days is not None else np.nan,
        "weight_kg": s.weight_kg if s.weight_kg is not None else np.nan,
        "freight_cost_usd": s.freight_cost_usd if s.freight_cost_usd is not None else np.nan,
        "Line Item Quantity": s.quantity,
        "Line Item Value": s.value,
        "vendor_past_late_rate": v["late_rate"] if v else overall,
        "country_past_late_rate": c["late_rate"] if c else overall,
        "vendor_shipment_count_so_far": v["count"] if v else 0,
        "Country": s.country,
        "Shipment Mode": s.shipment_mode,
        "Vendor INCO Term": s.inco_term,
        "Fulfill Via": s.fulfill_via,
        "Product Group": s.product_group,
    }])


def clean_name(name: str) -> str:
    for prefix in ("num__", "cat__"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.replace("_", " ")


def explain(row: pd.DataFrame):
    global EXPLAINER
    try:
        import shap
        pre = MODEL.named_steps["pre"]
        clf = MODEL.named_steps["clf"]
        if EXPLAINER is None:
            EXPLAINER = shap.TreeExplainer(clf)
        X = pre.transform(row)
        names = pre.get_feature_names_out()
        sv = EXPLAINER.shap_values(X)
        sv = sv[1] if isinstance(sv, list) else sv
        sv = np.array(sv)
        if sv.ndim == 3:
            sv = sv[:, :, 1]
        sv = sv[0]
        top = np.argsort(-np.abs(sv))[:4]
        return [{"feature": clean_name(str(names[i])), "impact": round(float(sv[i]), 4),
                 "direction": "raises risk" if sv[i] > 0 else "lowers risk"} for i in top]
    except Exception as exc:
        print("SHAP explanation unavailable:", exc)
        return []


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": MODEL is not None}


@app.get("/api/options")
def options():
    return OPTIONS


@app.post("/api/predict")
def predict(shipment: ShipmentIn):
    row = build_row(shipment)
    if MODEL is not None:
        prob = float(MODEL.predict_proba(row)[:, 1][0])
        source = "LightGBM model"
        reasons = explain(row)
    else:
        v = row["vendor_past_late_rate"].iloc[0]
        c = row["country_past_late_rate"].iloc[0]
        prob = float(min(0.95, 0.5 * v + 0.3 * c + (0.1 if shipment.shipment_mode == "Truck" else 0)))
        source = "Heuristic (model file not found in app/models)"
        reasons = [
            {"feature": "vendor past late rate", "impact": round(float(v), 4), "direction": "raises risk"},
            {"feature": "country past late rate", "impact": round(float(c), 4), "direction": "raises risk"},
        ]
    band = "high" if prob >= 0.5 else "medium" if prob >= 0.3 else "low"
    return {"probability_late": round(prob, 4), "risk_band": band, "source": source, "reasons": reasons,
            "vendor_history": STATS["vendors"].get(shipment.vendor),
            "country_history": STATS["countries"].get(shipment.country)}


@app.post("/api/reports", status_code=201)
def create_report(r: ReportIn):
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
    districts = []
    for g in groups.values():
        rate = STATS["countries"].get(g["country"], {}).get("late_rate", overall)
        g["country_late_rate"] = round(rate, 4)
        g["attention"] = "high" if g["open"] > 0 and rate >= overall else "medium" if g["open"] > 0 else "ok"
        districts.append(g)
    districts.sort(key=lambda d: (-d["open"], -d["country_late_rate"]))
    return {"total_reports": len(rows), "open_shortages": open_n,
            "restocked": len(rows) - open_n,
            "avg_restock_days": round(sum(done) / len(done), 2) if done else None,
            "districts": districts, "overall_late_rate": round(overall, 4)}


@app.post("/api/seed")
def seed_demo_data():
    demo = [("Kigali Central Pharmacy", "Gasabo", "Rwanda", "ARV"),
            ("Kampala Health Centre IV", "Kampala", "Uganda", "ARV"),
            ("Dodoma Regional Store", "Dodoma", "Tanzania", "HRDT"),
            ("Bujumbura Clinic", "Mukaza", "Burundi", "ARV"),
            ("Juba Teaching Hospital", "Juba", "South Sudan", "ARV")]
    conn = get_db()
    for fac, dist, ctry, pg in demo:
        conn.execute("INSERT INTO reports (facility, district, country, product_group, note, status, reported_at) "
                     "VALUES (?, ?, ?, ?, 'Demo data', 'shortage', ?)",
                     (fac, dist, ctry, pg, datetime.utcnow().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"seeded": len(demo)}


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
