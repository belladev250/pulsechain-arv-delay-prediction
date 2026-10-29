"""SQLite connection and schema."""
import sqlite3

from config import DB_PATH


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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delay_reasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            note TEXT,
            logged_at TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            answers TEXT NOT NULL,
            sus_score REAL NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL,
            country TEXT,
            district TEXT,
            approved INTEGER NOT NULL DEFAULT 0,
            is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
