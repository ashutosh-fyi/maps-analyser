"""Visualization: matplotlib charts + folium heatmaps and cluster maps."""

import logging

import folium
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from folium.plugins import HeatMap

from config.settings import CHARTS_DIR, MAPS_DIR, get_categories, get_regions

logger = logging.getLogger(__name__)

CLUSTER_COLORS = [
    "red", "blue", "green", "purple", "orange", "darkred",
    "darkblue", "darkgreen", "cadetblue", "pink",
]


def category_bar_chart(distribution: pd.DataFrame, region_key: str, title: str | None = None) -> str:
    """Horizontal bar chart of category distribution. Returns filepath."""
    if distribution.empty:
        logger.warning("Empty distribution, skipping bar chart")
        return ""

    fig, ax = plt.subplots(figsize=(10, max(6, len(distribution) * 0.5)))
    bars = ax.barh(distribution["display_name"], distribution["count"], color="#4285F4")
    ax.set_xlabel("Number of Stores")
    ax.set_title(title or f"Store Distribution — {region_key.replace('_', ' ').title()}")
    ax.invert_yaxis()

    for bar, pct in zip(bars, distribution["percentage"]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{pct}%", va="center", fontsize=9)

    plt.tight_layout()
    path = CHARTS_DIR / f"{region_key}_categories.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved bar chart to %s", path)
    return str(path)


def density_heatmap(places: list[dict], region_key: str) -> str:
    """Folium HeatMap of store locations. Returns filepath."""
    if not places:
        return ""

    regions = get_regions()
    bbox = regions.get(region_key, {}).get("bbox", {})
    center_lat = (bbox.get("south", 13.0) + bbox.get("north", 13.05)) / 2
    center_lon = (bbox.get("west", 80.2) + bbox.get("east", 80.25)) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles="OpenStreetMap")
    heat_data = [[p["latitude"], p["longitude"]] for p in places if p.get("latitude") and p.get("longitude")]
    HeatMap(heat_data, radius=15, blur=10, max_zoom=17).add_to(m)

    path = MAPS_DIR / f"{region_key}_heatmap.html"
    m.save(str(path))
    logger.info("Saved heatmap to %s", path)
    return str(path)


def cluster_map(places: list[dict], cluster_result: dict, region_key: str) -> str:
    """Folium map with colored markers per DBSCAN cluster. Returns filepath."""
    if not places or not cluster_result.get("labels"):
        return ""

    labels = cluster_result["labels"]
    regions = get_regions()
    bbox = regions.get(region_key, {}).get("bbox", {})
    center_lat = (bbox.get("south", 13.0) + bbox.get("north", 13.05)) / 2
    center_lon = (bbox.get("west", 80.2) + bbox.get("east", 80.25)) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles="OpenStreetMap")

    for place, label in zip(places, labels):
        if label == -1:
            color = "gray"
        else:
            color = CLUSTER_COLORS[label % len(CLUSTER_COLORS)]

        folium.CircleMarker(
            location=[place["latitude"], place["longitude"]],
            radius=5,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=f"{place['name']}<br>{place['category']}",
        ).add_to(m)

    # Mark cluster centers
    for cluster in cluster_result.get("clusters", []):
        folium.Marker(
            location=[cluster["center_lat"], cluster["center_lon"]],
            popup=f"Cluster {cluster['cluster_id']}: {cluster['size']} stores",
            icon=folium.Icon(color="black", icon="star"),
        ).add_to(m)

    path = MAPS_DIR / f"{region_key}_clusters.html"
    m.save(str(path))
    logger.info("Saved cluster map to %s", path)
    return str(path)


def category_comparison_chart(comparison_df: pd.DataFrame) -> str:
    """Grouped bar chart comparing categories across regions. Returns filepath."""
    if comparison_df.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, max(6, len(comparison_df) * 0.6)))
    comparison_df.plot(kind="barh", ax=ax)
    ax.set_xlabel("Number of Stores")
    ax.set_title("Category Distribution Comparison")
    ax.invert_yaxis()
    ax.legend(title="Region", loc="lower right")
    plt.tight_layout()

    path = CHARTS_DIR / "category_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved comparison chart to %s", path)
    return str(path)


def summary_dashboard(distribution: pd.DataFrame, density: dict, cluster_result: dict, region_key: str) -> str:
    """4-panel matplotlib summary figure. Returns filepath."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f"Store Analysis Dashboard — {region_key.replace('_', ' ').title()}", fontsize=16, fontweight="bold")

    # Panel 1: Category bar chart
    ax1 = axes[0, 0]
    if not distribution.empty:
        ax1.barh(distribution["display_name"], distribution["count"], color="#4285F4")
        ax1.set_xlabel("Count")
        ax1.set_title("Category Distribution")
        ax1.invert_yaxis()

    # Panel 2: Top categories pie chart
    ax2 = axes[0, 1]
    if not distribution.empty:
        top = distribution.head(6).copy()
        others = distribution.iloc[6:]["count"].sum()
        if others > 0:
            top = pd.concat([top, pd.DataFrame([{"display_name": "Others", "count": others}])], ignore_index=True)
        ax2.pie(top["count"], labels=top["display_name"], autopct="%1.1f%%", startangle=90)
        ax2.set_title("Category Share")

    # Panel 3: Density info
    ax3 = axes[1, 0]
    ax3.axis("off")
    if density:
        info_text = (
            f"Region: {density['region']}\n"
            f"Total Places: {density['total_places']}\n"
            f"Area: {density['area_sq_km']} km²\n"
            f"Density: {density['overall_density_per_km2']} stores/km²"
        )
        ax3.text(0.5, 0.5, info_text, transform=ax3.transAxes, fontsize=14,
                 verticalalignment="center", horizontalalignment="center",
                 fontfamily="monospace", bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
        ax3.set_title("Spatial Density")

    # Panel 4: Cluster summary
    ax4 = axes[1, 1]
    ax4.axis("off")
    if cluster_result and cluster_result.get("clusters"):
        rows = [["Cluster", "Size", "Top Category"]]
        for c in cluster_result["clusters"][:8]:
            top_cat = max(c["categories"], key=c["categories"].get) if c["categories"] else "—"
            rows.append([f"#{c['cluster_id']}", str(c["size"]), top_cat.replace("_", " ").title()])

        table = ax4.table(cellText=rows[1:], colLabels=rows[0], loc="center", cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)
        ax4.set_title(f"DBSCAN Clusters ({cluster_result['n_clusters']} found, {cluster_result['n_noise']} noise)")
    else:
        ax4.text(0.5, 0.5, "No clusters found", transform=ax4.transAxes,
                 fontsize=14, ha="center", va="center")
        ax4.set_title("DBSCAN Clusters")

    plt.tight_layout()
    path = CHARTS_DIR / f"{region_key}_dashboard.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved dashboard to %s", path)
    return str(path)
