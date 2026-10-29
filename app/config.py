"""Paths, reference data and constants shared by every module."""
import json
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "pulsechain.db"
MODELS_DIR = BASE / "models"
MODEL_PATH = MODELS_DIR / "model_pipeline.joblib"
if not MODEL_PATH.exists():
    MODEL_PATH = MODELS_DIR / "lgbm_pipeline.joblib"
SHIPMENTS_PATH = BASE / "data" / "upcoming_shipments.csv"
DIST = BASE.parent / "frontend" / "dist"


def load_json(path):
    """Read a JSON file; return None if it is missing or unreadable."""
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception as exc:
        print("Could not read", path.name, exc)
        return None


OPTIONS = json.loads((BASE / "data" / "options.json").read_text())
STATS = json.loads((BASE / "data" / "stats.json").read_text())
METRICS = json.loads((BASE / "data" / "metrics.json").read_text())

DELAY_REASONS = [
    "Customs clearance delay",
    "Supplier stock-out or production delay",
    "Transport or freight problem",
    "Documentation or paperwork error",
    "Funding or payment delay",
    "Weather, security or access problem",
    "Other",
]

DEMO_PASSWORD = "Demo#2026"

DEMO_SITES = [
    ("Kigali Central Pharmacy", "Gasabo", "Rwanda", 3), ("Nyagatare Health Centre", "Nyagatare", "Rwanda", 2),
    ("Huye Referral Hospital", "Huye", "Rwanda", 2), ("Kampala Health Centre IV", "Kampala", "Uganda", 4),
    ("Gulu Regional Store", "Gulu", "Uganda", 3), ("Mbarara Clinic", "Mbarara", "Uganda", 2),
    ("Dodoma Regional Store", "Dodoma", "Tanzania", 3), ("Arusha Health Centre", "Arusha", "Tanzania", 2),
    ("Bujumbura Clinic", "Mukaza", "Burundi", 6), ("Gitega Hospital", "Gitega", "Burundi", 4),
    ("Juba Teaching Hospital", "Juba", "South Sudan", 5), ("Addis Ababa Depot", "Addis Ababa", "Ethiopia", 1),
    ("Nairobi County Store", "Nairobi", "Kenya", 1),
]
SLOW_COUNTRIES = {"Burundi": 1.8, "South Sudan": 1.5}
