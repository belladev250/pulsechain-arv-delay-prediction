"""Simulated shortage reports and delay causes used for demonstrations (clearly labelled Demo data)."""
import random
from datetime import datetime, timedelta

from config import DELAY_REASONS, DEMO_SITES, SLOW_COUNTRIES
from database import get_db
from services.risk_model import risk_model


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
    late = risk_model.shipments[risk_model.shipments["actual_late"] == 1] if risk_model.shipments is not None else None
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
