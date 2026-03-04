"""SQLite storage for places data + CSV export."""

import csv
import logging
import sqlite3
from pathlib import Path

from config.settings import DB_PATH, DATA_DIR

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
    place_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    types_str TEXT,
    primary_type TEXT,
    category TEXT,
    region TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_places_region ON places(region);
CREATE INDEX IF NOT EXISTS idx_places_category ON places(category);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
    logger.info("Database initialized at %s", db_path)


def upsert_places(records: list[dict], db_path: Path = DB_PATH) -> int:
    """Insert or replace places. Returns number of rows affected."""
    init_db(db_path)
    sql = """
        INSERT OR REPLACE INTO places
            (place_id, name, latitude, longitude, address, types_str, primary_type, category, region)
        VALUES
            (:place_id, :name, :latitude, :longitude, :address, :types_str, :primary_type, :category, :region)
    """
    with get_connection(db_path) as conn:
        conn.executemany(sql, records)
        count = conn.total_changes
    logger.info("Upserted %d places", len(records))
    return count


def get_places(region: str | None = None, category: str | None = None, db_path: Path = DB_PATH) -> list[dict]:
    """Query places with optional region/category filters."""
    init_db(db_path)
    query = "SELECT * FROM places WHERE 1=1"
    params = []
    if region:
        query += " AND region = ?"
        params.append(region)
    if category:
        query += " AND category = ?"
        params.append(category)

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_region_summary(db_path: Path = DB_PATH) -> list[dict]:
    """Summary stats: count per region."""
    init_db(db_path)
    sql = "SELECT region, COUNT(*) as count FROM places GROUP BY region ORDER BY count DESC"
    with get_connection(db_path) as conn:
        return [dict(row) for row in conn.execute(sql).fetchall()]


def get_category_summary(region: str | None = None, db_path: Path = DB_PATH) -> list[dict]:
    """Category counts, optionally filtered by region."""
    init_db(db_path)
    query = "SELECT category, COUNT(*) as count FROM places"
    params = []
    if region:
        query += " WHERE region = ?"
        params.append(region)
    query += " GROUP BY category ORDER BY count DESC"
    with get_connection(db_path) as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def export_csv(region: str, output_dir: Path | None = None, db_path: Path = DB_PATH) -> Path:
    """Export places for a region to CSV."""
    if output_dir is None:
        output_dir = DATA_DIR / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    places = get_places(region=region, db_path=db_path)
    if not places:
        logger.warning("No places found for region %s", region)
        return output_dir / f"{region}.csv"

    filepath = output_dir / f"{region}.csv"
    fieldnames = ["place_id", "name", "latitude", "longitude", "address", "primary_type", "category", "region", "types_str"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(places)

    logger.info("Exported %d places to %s", len(places), filepath)
    return filepath
