"""Orchestrates fetch → normalize → store → analyze → visualize."""

import logging

from config.settings import get_regions
from maps_analyser.fetcher import PlacesFetcher
from maps_analyser.normalizer import normalize_and_dedup
from maps_analyser.storage import upsert_places, get_places, export_csv, get_region_summary, get_category_summary
from maps_analyser.analytics import category_distribution, spatial_density, dbscan_clusters, category_comparison
from maps_analyser.visualizer import (
    category_bar_chart, density_heatmap, cluster_map,
    category_comparison_chart, summary_dashboard,
)

logger = logging.getLogger(__name__)


def run_fetch(region_key: str) -> int:
    """Fetch places from API, normalize, and store. Returns count."""
    fetcher = PlacesFetcher()
    raw = fetcher.fetch_region(region_key)
    records = normalize_and_dedup(raw, region_key)
    upsert_places(records)
    return len(records)


def run_analyze(region_key: str) -> dict:
    """Run analytics on stored places for a region."""
    places = get_places(region=region_key)
    if not places:
        logger.warning("No places found for %s. Run fetch first.", region_key)
        return {}

    dist = category_distribution(places)
    density = spatial_density(places, region_key)
    clusters = dbscan_clusters(places)

    print(f"\n=== Analysis: {region_key.replace('_', ' ').title()} ===")
    print(f"Total places: {len(places)}")
    print(f"Area: {density.get('area_sq_km', '?')} km²")
    print(f"Density: {density.get('overall_density_per_km2', '?')} stores/km²")
    print(f"\nCategory Distribution:")
    for _, row in dist.iterrows():
        print(f"  {row['display_name']:30s} {row['count']:4d}  ({row['percentage']}%)")
    print(f"\nClusters: {clusters['n_clusters']} found, {clusters['n_noise']} noise points")
    for c in clusters.get("clusters", [])[:5]:
        top_cat = max(c["categories"], key=c["categories"].get) if c["categories"] else "—"
        print(f"  Cluster #{c['cluster_id']}: {c['size']} stores, dominant: {top_cat}")

    return {"distribution": dist, "density": density, "clusters": clusters}


def run_visualize(region_key: str) -> list[str]:
    """Generate all visualizations for a region. Returns list of output paths."""
    places = get_places(region=region_key)
    if not places:
        logger.warning("No places found for %s. Run fetch first.", region_key)
        return []

    dist = category_distribution(places)
    density = spatial_density(places, region_key)
    clusters = dbscan_clusters(places)

    paths = [
        category_bar_chart(dist, region_key),
        density_heatmap(places, region_key),
        cluster_map(places, clusters, region_key),
        summary_dashboard(dist, density, clusters, region_key),
    ]
    return [p for p in paths if p]


def run_compare(region_keys: list[str]) -> str:
    """Compare categories across multiple regions."""
    places_by_region = {}
    for key in region_keys:
        places = get_places(region=key)
        if places:
            places_by_region[key] = places
        else:
            logger.warning("No data for %s, skipping in comparison", key)

    if len(places_by_region) < 2:
        logger.warning("Need at least 2 regions with data for comparison")
        return ""

    comp = category_comparison(places_by_region)
    print("\n=== Category Comparison ===")
    print(comp.to_string())
    path = category_comparison_chart(comp)
    return path


def run_estimate(region_key: str) -> None:
    """Print API call estimate for a region."""
    fetcher = PlacesFetcher()
    est = fetcher.estimate_calls(region_key)
    print(f"\n=== Estimate: {est['display_name']} ===")
    print(f"  Tiles: {est['tiles']}")
    print(f"  Type groups: {est['type_groups']}")
    print(f"  Total API calls: {est['total_api_calls']}")
    print(f"  Search radius: {est['radius_m']}m, step: {est['step_m']}m")
    print(f"  Estimated cost: ${est['estimated_cost_usd']:.2f} (after free tier)")


def run_stats() -> None:
    """Print DB summary stats."""
    regions = get_region_summary()
    if not regions:
        print("Database is empty. Run fetch first.")
        return

    total = sum(r["count"] for r in regions)
    print(f"\n=== Database Stats ===")
    print(f"Total places: {total}")
    print(f"\nBy region:")
    for r in regions:
        print(f"  {r['region']:20s} {r['count']:5d}")

    print(f"\nBy category (all regions):")
    cats = get_category_summary()
    for c in cats:
        print(f"  {c['category']:30s} {c['count']:5d}")


def run_export(region_key: str) -> str:
    """Export region data to CSV. Returns filepath."""
    path = export_csv(region_key)
    print(f"Exported to {path}")
    return str(path)


def run_full_pipeline(region_keys: list[str] | None = None) -> None:
    """Run complete pipeline for specified or all regions."""
    if region_keys is None:
        region_keys = list(get_regions().keys())

    for key in region_keys:
        print(f"\n{'='*60}")
        print(f"Processing {key}...")
        print(f"{'='*60}")

        run_estimate(key)
        count = run_fetch(key)
        print(f"Fetched and stored {count} places")

        run_analyze(key)
        paths = run_visualize(key)
        print(f"\nGenerated {len(paths)} visualizations:")
        for p in paths:
            print(f"  {p}")

        run_export(key)

    if len(region_keys) > 1:
        run_compare(region_keys)
