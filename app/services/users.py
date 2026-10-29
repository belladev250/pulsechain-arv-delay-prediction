"""User accounts: creation and first-start bootstrap."""
from datetime import datetime

import auth
from config import DEMO_PASSWORD
from database import get_db


def create_user(conn, name, email, password, role, country, district, approved, is_demo=0):
    pw_hash, salt = auth.hash_password(password)
    conn.execute(
        "INSERT INTO users (name, email, password_hash, salt, role, country, district, approved, is_demo, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, email.strip().lower(), pw_hash, salt, role, country, district, approved, is_demo,
         datetime.utcnow().isoformat(timespec="seconds")))


def bootstrap_users():
    """On first start create an administrator, plus demo accounts so the role scoping can be shown."""
    import os
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        admin_email = os.environ.get("PULSECHAIN_ADMIN_EMAIL", "admin@pulsechain.local")
        admin_pw = os.environ.get("PULSECHAIN_ADMIN_PASSWORD", "Admin#2026")
        create_user(conn, "Administrator", admin_email, admin_pw, "admin", None, None, 1)
        if os.environ.get("PULSECHAIN_DEMO_USERS", "1") == "1":
            create_user(conn, "Rwanda country manager", "rwanda.manager@pulsechain.local", DEMO_PASSWORD, "country", "Rwanda", None, 1, 1)
            create_user(conn, "Gasabo district officer", "gasabo@pulsechain.local", DEMO_PASSWORD, "district", "Rwanda", "Gasabo", 1, 1)
            create_user(conn, "Kampala district officer", "kampala@pulsechain.local", DEMO_PASSWORD, "district", "Uganda", "Kampala", 1, 1)
        conn.commit()
        print("First start: created administrator", admin_email, "(change the password for real use).")
    conn.close()
