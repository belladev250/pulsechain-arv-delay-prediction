"""Authentication helpers using only the Python standard library.

- Passwords: PBKDF2-HMAC-SHA256 with a random salt (never stored in plain text).
- Tokens: signed (HMAC-SHA256) and time-limited, so they cannot be edited by the user.
- Scope: which rows of data a user is allowed to see.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

ITERATIONS = 200_000
TOKEN_HOURS = 12
ROLES = ("admin", "country", "district")
MIN_PASSWORD = 8


def hash_password(password: str, salt: str = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, expected_hash: str, salt: str) -> bool:
    actual, _ = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


def load_secret(base: Path) -> bytes:
    env = os.environ.get("PULSECHAIN_SECRET")
    if env:
        return env.encode()
    path = base / ".secret"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip().encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(user_id: int, secret: bytes, hours: float = TOKEN_HOURS) -> str:
    payload = _b64(json.dumps({"uid": user_id, "exp": int(time.time() + hours * 3600)}).encode())
    signature = _b64(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
    return payload + "." + signature


def read_token(token: str, secret: bytes):
    """Return the user id, or None if the token is invalid, edited or expired."""
    try:
        payload, signature = token.split(".")
        expected = _b64(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_unb64(payload))
        if data["exp"] < time.time():
            return None
        return int(data["uid"])
    except Exception:
        return None


def in_scope(user: dict, country: str, district: str = None) -> bool:
    """Can this user see data for this country (and district)?"""
    role = user["role"]
    if role == "admin":
        return True
    if (country or "").strip().lower() != (user["country"] or "").strip().lower():
        return False
    if role == "country":
        return True
    if district is None:
        return True
    return (district or "").strip().lower() == (user["district"] or "").strip().lower()


def scope_sql(user: dict):
    """SQL WHERE fragment and parameters restricting the reports table to the user's scope."""
    if user["role"] == "admin":
        return "1=1", []
    if user["role"] == "country":
        return "LOWER(country) = LOWER(?)", [user["country"]]
    return "LOWER(country) = LOWER(?) AND LOWER(district) = LOWER(?)", [user["country"], user["district"]]


class LoginLimiter:
    """Locks an email for a minute after 5 failed attempts (slows password guessing)."""

    def __init__(self, attempts=5, window=60):
        self.attempts, self.window, self.failures = attempts, window, {}

    def blocked(self, key: str) -> bool:
        now = time.time()
        recent = [t for t in self.failures.get(key, []) if now - t < self.window]
        self.failures[key] = recent
        return len(recent) >= self.attempts

    def fail(self, key: str):
        self.failures.setdefault(key, []).append(time.time())

    def reset(self, key: str):
        self.failures.pop(key, None)
