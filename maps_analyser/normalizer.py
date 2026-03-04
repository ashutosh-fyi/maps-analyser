"""Parse raw Places API responses into clean records, assign categories, deduplicate."""

import logging

from config.settings import get_type_to_category

logger = logging.getLogger(__name__)


def normalize_place(raw: dict) -> dict | None:
    """Convert a raw Places API place dict into a clean record."""
    place_id = raw.get("id")
    if not place_id:
        return None

    location = raw.get("location", {})
    display_name = raw.get("displayName", {})

    return {
        "place_id": place_id,
        "name": display_name.get("text", ""),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "address": raw.get("formattedAddress", ""),
        "types": raw.get("types", []),
        "primary_type": raw.get("primaryType", ""),
    }


def assign_category(record: dict, type_map: dict) -> str:
    """Determine internal category from place types. Checks primary_type first, then all types."""
    if record["primary_type"] in type_map:
        return type_map[record["primary_type"]]

    for t in record["types"]:
        if t in type_map:
            return type_map[t]

    return "other"


def normalize_and_dedup(raw_places: list[dict], region_key: str) -> list[dict]:
    """Full normalization pipeline: parse, categorize, dedup."""
    type_map = get_type_to_category()
    seen = set()
    records = []

    for raw in raw_places:
        record = normalize_place(raw)
        if record is None:
            continue
        if record["place_id"] in seen:
            continue
        seen.add(record["place_id"])

        record["category"] = assign_category(record, type_map)
        record["region"] = region_key
        record["types_str"] = ",".join(record["types"])
        records.append(record)

    logger.info("Normalized %d → %d unique places for %s", len(raw_places), len(records), region_key)
    return records
