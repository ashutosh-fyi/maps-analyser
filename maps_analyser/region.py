"""Bounding box → grid tiles using haversine-aware spacing."""

import math


EARTH_RADIUS_M = 6_371_000


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def meters_to_lat_deg(meters: float) -> float:
    """Convert meters to degrees of latitude."""
    return meters / (EARTH_RADIUS_M * math.pi / 180)


def meters_to_lon_deg(meters: float, lat: float) -> float:
    """Convert meters to degrees of longitude at a given latitude."""
    return meters / (EARTH_RADIUS_M * math.cos(math.radians(lat)) * math.pi / 180)


def generate_grid_tiles(bbox: dict, step_m: float = 750) -> list[dict]:
    """
    Generate grid tile centers covering the bounding box.

    Args:
        bbox: dict with keys south, north, west, east (degrees)
        step_m: distance between tile centers in meters

    Returns:
        List of dicts with lat, lon keys for each tile center.
    """
    south, north = bbox["south"], bbox["north"]
    west, east = bbox["west"], bbox["east"]
    mid_lat = (south + north) / 2

    lat_step = meters_to_lat_deg(step_m)
    lon_step = meters_to_lon_deg(step_m, mid_lat)

    tiles = []
    lat = south + lat_step / 2
    while lat < north:
        lon = west + lon_step / 2
        while lon < east:
            tiles.append({"lat": round(lat, 6), "lon": round(lon, 6)})
            lon += lon_step
        lat += lat_step

    return tiles


def calculate_area_sq_km(bbox: dict) -> float:
    """Approximate area of a bounding box in square kilometers."""
    height_m = haversine_distance(bbox["south"], bbox["west"], bbox["north"], bbox["west"])
    width_m = haversine_distance(bbox["south"], bbox["west"], bbox["south"], bbox["east"])
    return (height_m * width_m) / 1_000_000
