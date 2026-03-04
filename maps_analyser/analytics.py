"""Analytics: category distribution, spatial density, DBSCAN clustering, comparisons."""

import logging
import math

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from config.settings import DBSCAN_EPS_M, DBSCAN_MIN_SAMPLES, GRID_STEP_M, get_regions, get_categories
from maps_analyser.region import calculate_area_sq_km, generate_grid_tiles

logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6_371_000


def category_distribution(places: list[dict]) -> pd.DataFrame:
    """Count and percentage per category."""
    if not places:
        return pd.DataFrame(columns=["category", "count", "percentage"])

    df = pd.DataFrame(places)
    counts = df["category"].value_counts().reset_index()
    counts.columns = ["category", "count"]
    counts["percentage"] = (counts["count"] / counts["count"].sum() * 100).round(1)

    # Add display names
    categories = get_categories()
    counts["display_name"] = counts["category"].map(
        lambda c: categories.get(c, {}).get("display_name", c.replace("_", " ").title())
    )
    return counts


def spatial_density(places: list[dict], region_key: str) -> dict:
    """Compute stores per sq km and per-tile density."""
    regions = get_regions()
    if region_key not in regions:
        return {}

    bbox = regions[region_key]["bbox"]
    area = calculate_area_sq_km(bbox)
    total = len(places)
    overall_density = total / area if area > 0 else 0

    # Per-tile density
    tiles = generate_grid_tiles(bbox, GRID_STEP_M)
    tile_area_km2 = (GRID_STEP_M / 1000) ** 2

    tile_densities = []
    for tile in tiles:
        count = sum(
            1 for p in places
            if abs(p["latitude"] - tile["lat"]) < GRID_STEP_M / EARTH_RADIUS_M * (180 / math.pi) / 2
            and abs(p["longitude"] - tile["lon"]) < GRID_STEP_M / (EARTH_RADIUS_M * math.cos(math.radians(tile["lat"]))) * (180 / math.pi) / 2
        )
        tile_densities.append({
            "lat": tile["lat"],
            "lon": tile["lon"],
            "count": count,
            "density_per_km2": count / tile_area_km2 if tile_area_km2 > 0 else 0,
        })

    return {
        "region": region_key,
        "total_places": total,
        "area_sq_km": round(area, 2),
        "overall_density_per_km2": round(overall_density, 1),
        "tile_densities": tile_densities,
    }


def dbscan_clusters(places: list[dict], eps_m: float = DBSCAN_EPS_M, min_samples: int = DBSCAN_MIN_SAMPLES) -> dict:
    """Run DBSCAN with haversine metric on place locations."""
    if len(places) < min_samples:
        return {"n_clusters": 0, "n_noise": len(places), "clusters": [], "labels": []}

    coords = np.array([[p["latitude"], p["longitude"]] for p in places])
    coords_rad = np.radians(coords)

    eps_rad = eps_m / EARTH_RADIUS_M

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, algorithm="ball_tree", metric="haversine")
    labels = db.fit_predict(coords_rad)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(labels == -1))

    clusters = []
    for cluster_id in range(n_clusters):
        mask = labels == cluster_id
        cluster_coords = coords[mask]
        cluster_places = [p for p, m in zip(places, mask) if m]

        # Category breakdown within cluster
        cat_counts = {}
        for p in cluster_places:
            cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1

        clusters.append({
            "cluster_id": cluster_id,
            "size": int(mask.sum()),
            "center_lat": float(cluster_coords[:, 0].mean()),
            "center_lon": float(cluster_coords[:, 1].mean()),
            "categories": cat_counts,
        })

    clusters.sort(key=lambda c: c["size"], reverse=True)

    return {
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "clusters": clusters,
        "labels": labels.tolist(),
    }


def category_comparison(places_by_region: dict[str, list[dict]]) -> pd.DataFrame:
    """Compare category distributions across regions."""
    all_rows = []
    for region_key, places in places_by_region.items():
        dist = category_distribution(places)
        dist["region"] = region_key
        all_rows.append(dist)

    if not all_rows:
        return pd.DataFrame()

    combined = pd.concat(all_rows, ignore_index=True)
    return combined.pivot_table(
        index="display_name",
        columns="region",
        values="count",
        fill_value=0,
    ).astype(int)
