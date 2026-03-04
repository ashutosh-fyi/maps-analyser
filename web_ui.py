"""Simple Flask web UI for Maps Analyser."""

import json
import os

from flask import Flask, render_template_string, jsonify, request

from config.settings import get_regions, get_categories, CHARTS_DIR, MAPS_DIR
from maps_analyser.storage import get_places, get_region_summary, get_category_summary
from maps_analyser.analytics import category_distribution, spatial_density, dbscan_clusters, category_comparison
from maps_analyser.fetcher import PlacesFetcher

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chennai Store Distribution Analyzer</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
  .header { background: #1a73e8; color: white; padding: 20px 32px; }
  .header h1 { font-size: 24px; font-weight: 500; }
  .header p { opacity: 0.85; margin-top: 4px; font-size: 14px; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }
  .tab { padding: 10px 20px; border: none; background: white; border-radius: 8px; cursor: pointer;
         font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: all 0.2s; }
  .tab:hover { background: #e8f0fe; }
  .tab.active { background: #1a73e8; color: white; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 24px; }
  .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .card h3 { font-size: 16px; color: #555; margin-bottom: 12px; font-weight: 500; }
  .stat-value { font-size: 36px; font-weight: 700; color: #1a73e8; }
  .stat-label { font-size: 13px; color: #888; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #eee; font-size: 14px; }
  th { font-weight: 600; color: #555; background: #fafafa; }
  tr:hover { background: #f8f9fa; }
  .bar-container { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
  .bar-label { min-width: 180px; font-size: 13px; text-align: right; }
  .bar-wrap { flex: 1; background: #eee; border-radius: 4px; height: 24px; overflow: hidden; }
  .bar-fill { height: 100%; background: #1a73e8; border-radius: 4px; transition: width 0.5s ease; display: flex; align-items: center; padding-left: 8px; }
  .bar-fill span { color: white; font-size: 11px; font-weight: 600; white-space: nowrap; }
  .bar-count { min-width: 50px; font-size: 13px; font-weight: 600; }
  .map-frame { width: 100%; height: 500px; border: none; border-radius: 8px; }
  .section { margin-bottom: 32px; }
  .section h2 { font-size: 20px; font-weight: 600; margin-bottom: 16px; color: #333; }
  .cluster-chip { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin: 2px; color: white; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }
  .badge-blue { background: #e8f0fe; color: #1a73e8; }
  .compare-table th { position: sticky; top: 0; }
  .empty-state { text-align: center; padding: 60px 20px; color: #888; }
  .empty-state p { font-size: 16px; margin-bottom: 8px; }
  .empty-state code { background: #eee; padding: 4px 8px; border-radius: 4px; font-size: 14px; }
  .loading { text-align: center; padding: 40px; color: #888; }
  #content { min-height: 400px; }
</style>
</head>
<body>
<div class="header">
  <h1>Chennai Store Distribution Analyzer</h1>
  <p>Commercial establishment mapping and clustering for Chennai neighborhoods</p>
</div>
<div class="container">
  <div class="tabs" id="tabs"></div>
  <div id="content"><div class="loading">Loading...</div></div>
</div>

<script>
const REGIONS = {{ regions | tojson }};
const CATEGORIES = {{ categories | tojson }};
let currentTab = 'overview';

function setTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  loadContent(tab);
}

function buildTabs() {
  const tabs = document.getElementById('tabs');
  const regions = Object.entries(REGIONS);
  let html = '<button class="tab active" data-tab="overview">Overview</button>';
  for (const [key, info] of regions) {
    html += '<button class="tab" data-tab="' + key + '">' + info.display_name + '</button>';
  }
  html += '<button class="tab" data-tab="compare">Compare</button>';
  tabs.innerHTML = html;
  tabs.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
  });
}

async function api(url) {
  const resp = await fetch(url);
  return resp.json();
}

function barChart(items, maxVal) {
  return items.map(([label, count, pct]) => {
    const w = maxVal > 0 ? (count / maxVal * 100) : 0;
    return `<div class="bar-container">
      <div class="bar-label">${label}</div>
      <div class="bar-wrap"><div class="bar-fill" style="width:${w}%"><span>${pct}%</span></div></div>
      <div class="bar-count">${count}</div>
    </div>`;
  }).join('');
}

async function loadContent(tab) {
  const el = document.getElementById('content');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    if (tab === 'overview') await renderOverview(el);
    else if (tab === 'compare') await renderCompare(el);
    else await renderRegion(el, tab);
  } catch(e) {
    el.innerHTML = `<div class="empty-state"><p>Error: ${e.message}</p></div>`;
  }
}

async function renderOverview(el) {
  const data = await api('/api/overview');
  if (!data.regions.length) {
    el.innerHTML = `<div class="empty-state">
      <p>No data yet. Fetch some neighborhoods first:</p>
      <code>python -m maps_analyser fetch t_nagar</code>
    </div>`;
    return;
  }
  const total = data.regions.reduce((s,r) => s + r.count, 0);
  let html = `<div class="grid">
    <div class="card"><div class="stat-value">${total}</div><div class="stat-label">Total Places</div></div>
    <div class="card"><div class="stat-value">${data.regions.length}</div><div class="stat-label">Regions Fetched</div></div>
    <div class="card"><div class="stat-value">${data.categories.length}</div><div class="stat-label">Categories</div></div>
  </div>`;

  html += '<div class="grid"><div class="card"><h3>Places by Region</h3><table><tr><th>Region</th><th>Count</th></tr>';
  data.regions.forEach(r => { html += `<tr><td>${r.region}</td><td>${r.count}</td></tr>`; });
  html += '</table></div>';

  html += '<div class="card"><h3>Top Categories</h3><table><tr><th>Category</th><th>Count</th></tr>';
  data.categories.slice(0, 10).forEach(c => { html += `<tr><td>${c.category.replace(/_/g,' ')}</td><td>${c.count}</td></tr>`; });
  html += '</table></div></div>';

  // Estimates
  html += '<div class="card"><h3>API Call Estimates</h3><table><tr><th>Region</th><th>Tiles</th><th>API Calls</th><th>Status</th></tr>';
  for (const [key, info] of Object.entries(REGIONS)) {
    const est = await api(`/api/estimate/${key}`);
    const fetched = data.regions.find(r => r.region === key);
    const status = fetched ? `<span class="badge badge-blue">${fetched.count} fetched</span>` : 'Not fetched';
    html += `<tr><td>${info.display_name}</td><td>${est.tiles}</td><td>${est.total_api_calls}</td><td>${status}</td></tr>`;
  }
  html += '</table></div>';
  el.innerHTML = html;
}

async function renderRegion(el, region) {
  const data = await api(`/api/region/${region}`);
  if (!data.places.length) {
    el.innerHTML = `<div class="empty-state">
      <p>No data for this region. Fetch it first:</p>
      <code>python -m maps_analyser fetch ${region}</code>
    </div>`;
    return;
  }

  const dist = data.distribution;
  const dens = data.density;
  const clust = data.clusters;
  const maxCount = dist.length ? dist[0].count : 1;

  let html = `<div class="grid">
    <div class="card"><div class="stat-value">${data.places.length}</div><div class="stat-label">Total Places</div></div>
    <div class="card"><div class="stat-value">${dens.area_sq_km}</div><div class="stat-label">Area (km&sup2;)</div></div>
    <div class="card"><div class="stat-value">${dens.overall_density_per_km2}</div><div class="stat-label">Stores / km&sup2;</div></div>
    <div class="card"><div class="stat-value">${clust.n_clusters}</div><div class="stat-label">Clusters Found</div></div>
  </div>`;

  // Category distribution bar chart
  html += '<div class="section"><h2>Category Distribution</h2><div class="card">';
  const bars = dist.map(d => [d.display_name, d.count, d.percentage]);
  html += barChart(bars, maxCount);
  html += '</div></div>';

  // Clusters
  if (clust.clusters && clust.clusters.length) {
    html += '<div class="section"><h2>Store Clusters (DBSCAN)</h2><div class="card">';
    html += `<p style="margin-bottom:12px;color:#666">${clust.n_clusters} clusters, ${clust.n_noise} noise points (eps=400m, min_samples=5)</p>`;
    html += '<table><tr><th>#</th><th>Size</th><th>Center</th><th>Top Categories</th></tr>';
    const colors = ['#ea4335','#4285f4','#34a853','#7b1fa2','#ff6d00','#c62828','#1565c0','#2e7d32','#5f7c8a','#e91e63'];
    clust.clusters.forEach((c, i) => {
      const cats = Object.entries(c.categories).sort((a,b) => b[1]-a[1]).slice(0,3)
        .map(([k,v]) => `<span class="cluster-chip" style="background:${colors[i%colors.length]}">${k.replace(/_/g,' ')} (${v})</span>`).join(' ');
      html += `<tr><td>${c.cluster_id}</td><td>${c.size}</td><td>${c.center_lat.toFixed(4)}, ${c.center_lon.toFixed(4)}</td><td>${cats}</td></tr>`;
    });
    html += '</table></div></div>';
  }

  // Maps
  html += `<div class="section"><h2>Heatmap</h2>
    <div class="card"><iframe class="map-frame" src="/map/${region}/heatmap"></iframe></div></div>`;
  html += `<div class="section"><h2>Cluster Map</h2>
    <div class="card"><iframe class="map-frame" src="/map/${region}/clusters"></iframe></div></div>`;

  // Place list
  html += '<div class="section"><h2>All Places</h2><div class="card" style="max-height:500px;overflow:auto">';
  html += '<table><tr><th>Name</th><th>Category</th><th>Type</th><th>Address</th></tr>';
  data.places.forEach(p => {
    html += `<tr><td>${p.name}</td><td><span class="badge badge-blue">${(p.category||'').replace(/_/g,' ')}</span></td><td>${(p.primary_type||'').replace(/_/g,' ')}</td><td style="font-size:12px;color:#666">${p.address||''}</td></tr>`;
  });
  html += '</table></div></div>';

  el.innerHTML = html;
}

async function renderCompare(el) {
  const data = await api('/api/compare');
  if (!data.regions || data.regions.length < 2) {
    el.innerHTML = `<div class="empty-state"><p>Need at least 2 regions with data to compare.</p>
      <code>python -m maps_analyser fetch --all</code></div>`;
    return;
  }

  let html = '<div class="section"><h2>Category Comparison</h2><div class="card" style="overflow-x:auto">';
  html += '<table class="compare-table"><tr><th>Category</th>';
  data.regions.forEach(r => { html += `<th>${r}</th>`; });
  html += '</tr>';

  const cats = Object.keys(data.table);
  cats.forEach(cat => {
    html += `<tr><td>${cat}</td>`;
    data.regions.forEach(r => { html += `<td>${data.table[cat][r] || 0}</td>`; });
    html += '</tr>';
  });
  html += '</table></div></div>';
  el.innerHTML = html;
}

buildTabs();
setTab('overview');
</script>
</body>
</html>
"""

@app.route("/")
def index():
    regions = get_regions()
    categories = get_categories()
    return render_template_string(HTML, regions=regions, categories=categories)


@app.route("/api/overview")
def api_overview():
    return jsonify({
        "regions": get_region_summary(),
        "categories": get_category_summary(),
    })


@app.route("/api/estimate/<region_key>")
def api_estimate(region_key):
    fetcher = PlacesFetcher()
    return jsonify(fetcher.estimate_calls(region_key))


@app.route("/api/region/<region_key>")
def api_region(region_key):
    places = get_places(region=region_key)
    dist = category_distribution(places)
    density = spatial_density(places, region_key)
    clusters = dbscan_clusters(places)

    return jsonify({
        "places": places,
        "distribution": dist.to_dict("records") if not dist.empty else [],
        "density": density,
        "clusters": {
            "n_clusters": clusters["n_clusters"],
            "n_noise": clusters["n_noise"],
            "clusters": clusters["clusters"],
        },
    })


@app.route("/api/compare")
def api_compare():
    regions = get_regions()
    places_by_region = {}
    fetched_regions = []
    for key in regions:
        places = get_places(region=key)
        if places:
            places_by_region[key] = places
            fetched_regions.append(key)

    if len(places_by_region) < 2:
        return jsonify({"regions": fetched_regions, "table": {}})

    comp = category_comparison(places_by_region)
    return jsonify({
        "regions": fetched_regions,
        "table": comp.to_dict("index"),
    })


@app.route("/map/<region_key>/heatmap")
def map_heatmap(region_key):
    """Generate and serve a heatmap inline."""
    import folium
    from folium.plugins import HeatMap as FoliumHeatMap
    from config.settings import get_regions as _get_regions

    places = get_places(region=region_key)
    regions = _get_regions()
    bbox = regions.get(region_key, {}).get("bbox", {})
    center_lat = (bbox.get("south", 13.0) + bbox.get("north", 13.05)) / 2
    center_lon = (bbox.get("west", 80.2) + bbox.get("east", 80.25)) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
    heat_data = [[p["latitude"], p["longitude"]] for p in places if p.get("latitude")]
    FoliumHeatMap(heat_data, radius=15, blur=10, max_zoom=17).add_to(m)
    return m._repr_html_()


@app.route("/map/<region_key>/clusters")
def map_clusters(region_key):
    """Generate and serve a cluster map inline."""
    import folium
    from config.settings import get_regions as _get_regions

    places = get_places(region=region_key)
    clusters = dbscan_clusters(places)
    labels = clusters.get("labels", [])
    regions = _get_regions()
    bbox = regions.get(region_key, {}).get("bbox", {})
    center_lat = (bbox.get("south", 13.0) + bbox.get("north", 13.05)) / 2
    center_lon = (bbox.get("west", 80.2) + bbox.get("east", 80.25)) / 2

    colors = ["red", "blue", "green", "purple", "orange", "darkred", "darkblue", "darkgreen", "cadetblue", "pink"]
    m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
    for place, label in zip(places, labels):
        color = "gray" if label == -1 else colors[label % len(colors)]
        folium.CircleMarker(
            location=[place["latitude"], place["longitude"]],
            radius=5, color=color, fill=True, fill_opacity=0.7,
            popup=f"{place['name']}<br>{place.get('category','')}",
        ).add_to(m)
    for c in clusters.get("clusters", []):
        folium.Marker(
            location=[c["center_lat"], c["center_lon"]],
            popup=f"Cluster {c['cluster_id']}: {c['size']} stores",
            icon=folium.Icon(color="black", icon="star"),
        ).add_to(m)
    return m._repr_html_()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
