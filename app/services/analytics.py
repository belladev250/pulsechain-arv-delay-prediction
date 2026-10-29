"""Dashboard and analytics summaries, always computed from the user's own scope."""
from collections import Counter
from datetime import datetime, timedelta

import numpy as np

from config import OPTIONS, STATS
from database import get_db
from services.reports import my_reports
from services.risk_model import risk_model


def build_dashboard(user):
    conn = get_db()
    rows = my_reports(conn, user)
    conn.close()
    open_n = sum(1 for r in rows if r["status"] == "shortage")
    done = [r["restock_days"] for r in rows if r["restock_days"] is not None]
    groups = {}
    for r in rows:
        key = (r["district"], r["country"])
        g = groups.setdefault(key, {"district": r["district"], "country": r["country"], "open": 0, "restocked": 0})
        g["open" if r["status"] == "shortage" else "restocked"] += 1
    overall = STATS["overall_late_rate"]
    scored = risk_model.scored_shipments()
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
        # Flag a district as high attention only when it has at least 2 open shortages AND its
        # country's predicted risk is 15% or more above the overall level.
        g["attention"] = "high" if g["open"] >= 2 and elevated else "medium" if g["open"] > 0 else "ok"
        districts.append(g)
    districts.sort(key=lambda d: (-d["open"], -(d["predicted_risk"] or d["country_late_rate"])))
    return {"total_reports": len(rows), "open_shortages": open_n,
            "restocked": len(rows) - open_n,
            "avg_restock_days": round(sum(done) / len(done), 2) if done else None,
            "districts": districts, "overall_late_rate": round(overall, 4),
            "overall_predicted_risk": round(overall_pred, 4) if overall_pred is not None else None}


def build_analytics(user):
    conn = get_db()
    rows = sorted(my_reports(conn, user), key=lambda r: r["reported_at"], reverse=True)
    conn.close()

    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    opened = Counter(r["reported_at"][:10] for r in rows)
    closed = Counter(r["restocked_at"][:10] for r in rows if r["restocked_at"])
    timeline = [{"date": d.strftime("%d %b"), "reported": opened.get(d.isoformat(), 0),
                 "restocked": closed.get(d.isoformat(), 0)} for d in days]

    by_country = []
    visible_countries = OPTIONS["countries"] if user["role"] == "admin" else [user["country"]]
    for country in visible_countries:
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
    scored = risk_model.scored_shipments()
    if scored is not None and user["role"] != "admin":
        scored = scored[scored["Country"] == user["country"]]
    if scored is not None and len(scored) > 0:
        upper = max(0.3, float(np.ceil(scored["probability_late"].max() * 10) / 10))
        counts, edges = np.histogram(scored["probability_late"], bins=np.linspace(0, upper, 11))
        risk_distribution = [{"range": f"{edges[i] * 100:.0f}%", "shipments": int(c)}
                             for i, c in enumerate(counts)]
        for band, label in [("low", "Low risk"), ("medium", "Medium risk"), ("high", "High risk")]:
            sub = scored[scored["risk_band"] == band]
            band_validation.append({"band": label, "shipments": int(len(sub)),
                                    "late_rate": round(float(sub["actual_late"].mean()) * 100, 1) if len(sub) else 0})

    conn = get_db()
    reason_sql = "SELECT reason, COUNT(*) AS n, SUM(is_demo) AS demo FROM delay_reasons "
    reason_params = []
    if user["role"] != "admin" and scored is not None:
        ids = [int(i) for i in scored["shipment_id"].tolist()]
        reason_sql += "WHERE shipment_id IN (" + ",".join("?" * len(ids)) + ") " if ids else "WHERE 0 "
        reason_params = ids
    reason_rows = conn.execute(reason_sql + "GROUP BY reason ORDER BY n DESC", reason_params).fetchall()
    conn.close()
    delay_reasons = [{"reason": r["reason"], "count": r["n"]} for r in reason_rows]
    demo_reasons = sum(int(r["demo"] or 0) for r in reason_rows)

    return {"delay_reasons": delay_reasons, "demo_delay_reasons": demo_reasons,
            "timeline": timeline, "by_country": by_country, "status": status,
            "risk_distribution": risk_distribution, "band_validation": band_validation,
            "baseline_late_rate": round(float(scored["actual_late"].mean()) * 100, 1) if scored is not None and len(scored) else None,
            "demo_reports": demo_reports, "total_reports": len(rows),
            "recent": rows[:6], "generated_at": datetime.utcnow().isoformat(timespec="seconds")}
