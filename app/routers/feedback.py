"""Usability survey (System Usability Scale)."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from dependencies import admin_only, current_user
from schemas import FeedbackIn


router = APIRouter()


@router.post("/api/feedback", status_code=201)
def submit_feedback(body: FeedbackIn, user=Depends(current_user)):
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


@router.get("/api/feedback/summary")
def feedback_summary(user=Depends(admin_only)):
    conn = get_db()
    rows = [dict(x) for x in conn.execute("SELECT * FROM feedback ORDER BY id DESC").fetchall()]
    conn.close()
    if not rows:
        return {"responses": 0, "mean_sus": None, "comments": [], "scores": []}
    scores = [r["sus_score"] for r in rows]
    return {"responses": len(rows), "mean_sus": round(sum(scores) / len(scores), 1),
            "min": min(scores), "max": max(scores),
            "comments": [r["comment"] for r in rows if r["comment"]][:8], "scores": scores[::-1]}
