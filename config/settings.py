import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
MAPS_DIR = OUTPUT_DIR / "maps"

# Ensure runtime dirs exist
for d in (DATA_DIR, CHARTS_DIR, MAPS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Load .env
load_dotenv(PROJECT_ROOT / ".env")

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# API constants
PLACES_API_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = "places.id,places.displayName,places.location,places.types,places.formattedAddress,places.primaryType"
SEARCH_RADIUS_M = 500
GRID_STEP_M = 750
REQUEST_TIMEOUT_S = 5
MAX_RETRIES = 3
RATE_LIMIT_DELAY_S = 0.2  # 5 req/s baseline

# DBSCAN defaults
DBSCAN_EPS_M = 400
DBSCAN_MIN_SAMPLES = 5

# SQLite
DB_PATH = DATA_DIR / "stores.db"


def load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename) as f:
        return yaml.safe_load(f)


def get_regions() -> dict:
    return load_yaml("regions.yaml")["neighborhoods"]


def get_categories() -> dict:
    return load_yaml("categories.yaml")["type_groups"]


def get_type_to_category() -> dict:
    """Build reverse lookup: Google type string → internal category key."""
    categories = get_categories()
    mapping = {}
    for cat_key, cat_info in categories.items():
        for t in cat_info["types"]:
            mapping[t] = cat_key
    return mapping


def get_type_groups() -> list[list[str]]:
    """Return list of type lists for type-group splitting."""
    categories = get_categories()
    return [cat_info["types"] for cat_info in categories.values()]
