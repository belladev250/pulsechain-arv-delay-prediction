"""Registration, sign-in and user management."""

from fastapi import APIRouter, Depends, HTTPException

import auth
from config import OPTIONS
from database import get_db
from dependencies import (LIMITER, SECRET, check_choice, current_user, manager_only)
from schemas import LoginIn, RegisterIn, UserUpdateIn
from services.users import create_user
from dependencies import PUBLIC_FIELDS


router = APIRouter()


@router.get("/api/auth/countries")
def public_countries():
    return {"countries": OPTIONS["countries"]}


@router.post("/api/auth/register", status_code=201)
def register(body: RegisterIn):
    name, email = body.name.strip(), body.email.strip().lower()
    district = body.district.strip()
    if len(name) < 2 or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Enter your name and a valid email address")
    if len(body.password) < auth.MIN_PASSWORD:
        raise HTTPException(status_code=422, detail=f"Password must be at least {auth.MIN_PASSWORD} characters")
    check_choice(body.country, OPTIONS["countries"], "Country")
    if not (2 <= len(district) <= 100):
        raise HTTPException(status_code=422, detail="District must be 2 to 100 characters")
    conn = get_db()
    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    create_user(conn, name, email, body.password, "district", body.country, district, 0)
    conn.commit()
    conn.close()
    return {"status": "pending", "message": "Account created. A manager must approve it before you can sign in."}


@router.post("/api/auth/login")
def login(body: LoginIn):
    email = body.email.strip().lower()
    if LIMITER.blocked(email):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a minute.")
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if row is None or not auth.verify_password(body.password, row["password_hash"], row["salt"]):
        LIMITER.fail(email)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not row["approved"]:
        raise HTTPException(status_code=403, detail="Your account is waiting for approval by a manager")
    LIMITER.reset(email)
    user = {k: row[k] for k in ("id", "name", "email", "role", "country", "district")}
    return {"token": auth.make_token(row["id"], SECRET), "user": user}


@router.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user


@router.get("/api/users")
def list_users(user=Depends(manager_only)):
    conn = get_db()
    if user["role"] == "admin":
        rows = conn.execute("SELECT " + PUBLIC_FIELDS + " FROM users ORDER BY approved, id DESC").fetchall()
    else:
        rows = conn.execute("SELECT " + PUBLIC_FIELDS + " FROM users WHERE role = 'district' AND LOWER(country) = LOWER(?) "
                            "ORDER BY approved, id DESC", (user["country"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.patch("/api/users/{user_id}")
def update_user(user_id: int, body: UserUpdateIn, user=Depends(manager_only)):
    conn = get_db()
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if target is None:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    if target["id"] == user["id"]:
        conn.close()
        raise HTTPException(status_code=400, detail="You cannot change your own account")
    if user["role"] == "country":
        if target["role"] != "district" or (target["country"] or "").lower() != user["country"].lower():
            conn.close()
            raise HTTPException(status_code=403, detail="You can only manage district officers in your country")
        if body.role is not None or body.country is not None or body.district is not None:
            conn.close()
            raise HTTPException(status_code=403, detail="Only an administrator can change roles or locations")
    updates, params = [], []
    if body.approved is not None:
        updates.append("approved = ?"); params.append(1 if body.approved else 0)
    if body.role is not None:
        if body.role not in auth.ROLES:
            conn.close()
            raise HTTPException(status_code=422, detail="Unknown role")
        updates.append("role = ?"); params.append(body.role)
    if body.country is not None:
        check_choice(body.country, OPTIONS["countries"], "Country")
        updates.append("country = ?"); params.append(body.country)
    if body.district is not None:
        updates.append("district = ?"); params.append(body.district.strip())
    if updates:
        conn.execute("UPDATE users SET " + ", ".join(updates) + " WHERE id = ?", params + [user_id])
        conn.commit()
    row = conn.execute("SELECT " + PUBLIC_FIELDS + " FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row)
