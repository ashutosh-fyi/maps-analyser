"""Build a static site in docs/ for GitHub Pages with all data embedded."""

import json
from pathlib import Path

from config.settings import get_regions, get_categories
from maps_analyser.storage import get_places, get_region_summary, get_category_summary
from maps_analyser.analytics import category_distribution, spatial_density, dbscan_clusters, category_comparison

DOCS = Path(__file__).parent / "docs"
DOCS.mkdir(exist_ok=True)


def build():
    regions = get_regions()
    categories = get_categories()

    # Build per-region data
    region_data = {}
    places_by_region = {}
    for key in regions:
        places = get_places(region=key)
        if not places:
            continue
        places_by_region[key] = places
        dist = category_distribution(places)
        density = spatial_density(places, key)
        clusters = dbscan_clusters(places)

        # Slim down places for the static page (drop fetched_at, types_str)
        slim_places = [
            {
                "name": p["name"],
                "lat": p["latitude"],
                "lon": p["longitude"],
                "category": p["category"],
                "primary_type": p.get("primary_type", ""),
                "address": p.get("address", ""),
            }
            for p in places
        ]

        region_data[key] = {
            "display_name": regions[key]["display_name"],
            "bbox": regions[key]["bbox"],
            "places": slim_places,
            "distribution": dist.to_dict("records") if not dist.empty else [],
            "density": {
                "total_places": density.get("total_places", 0),
                "area_sq_km": density.get("area_sq_km", 0),
                "overall_density_per_km2": density.get("overall_density_per_km2", 0),
            },
            "clusters": {
                "n_clusters": clusters["n_clusters"],
                "n_noise": clusters["n_noise"],
                "clusters": clusters["clusters"],
                "labels": clusters["labels"],
            },
        }

    # Comparison
    comparison = {}
    if len(places_by_region) >= 2:
        comp_df = category_comparison(places_by_region)
        if not comp_df.empty:
            comparison = {
                "regions": list(places_by_region.keys()),
                "table": comp_df.to_dict("index"),
            }

    # Overview
    overview = {
        "regions": get_region_summary(),
        "categories": get_category_summary(),
    }

    site_data = {
        "overview": overview,
        "regions": {k: v["display_name"] for k, v in regions.items()},
        "region_data": region_data,
        "comparison": comparison,
    }

    data_json = json.dumps(site_data, default=str)
    html = build_html(data_json)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"Built static site at {DOCS / 'index.html'}")
    print(f"Total data size: {len(data_json) / 1024:.0f} KB")


def build_html(data_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chennai Store Distribution Analyzer</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }}
  .header {{ background: #1a73e8; color: white; padding: 20px 32px; }}
  .header h1 {{ font-size: 24px; font-weight: 500; }}
  .header p {{ opacity: 0.85; margin-top: 4px; font-size: 14px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }}
  .tab {{ padding: 10px 20px; border: none; background: white; border-radius: 8px; cursor: pointer;
         font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: all 0.2s; }}
  .tab:hover {{ background: #e8f0fe; }}
  .tab.active {{ background: #1a73e8; color: white; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 24px; }}
  .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .card h3 {{ font-size: 16px; color: #555; margin-bottom: 12px; font-weight: 500; }}
  .stat-value {{ font-size: 36px; font-weight: 700; color: #1a73e8; }}
  .stat-label {{ font-size: 13px; color: #888; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #eee; font-size: 14px; }}
  th {{ font-weight: 600; color: #555; background: #fafafa; position: sticky; top: 0; }}
  tr:hover {{ background: #f8f9fa; }}
  .bar-container {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; }}
  .bar-label {{ min-width: 180px; font-size: 13px; text-align: right; }}
  .bar-wrap {{ flex: 1; background: #eee; border-radius: 4px; height: 24px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: #1a73e8; border-radius: 4px; transition: width 0.5s ease;
              display: flex; align-items: center; padding-left: 8px; }}
  .bar-fill span {{ color: white; font-size: 11px; font-weight: 600; white-space: nowrap; }}
  .bar-count {{ min-width: 50px; font-size: 13px; font-weight: 600; }}
  .map-container {{ width: 100%; height: 500px; border-radius: 8px; overflow: hidden; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 20px; font-weight: 600; margin-bottom: 16px; color: #333; }}
  .cluster-chip {{ display: inline-block; padding: 4px 10px; border-radius: 12px;
                   font-size: 12px; font-weight: 600; margin: 2px; color: white; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }}
  .badge-blue {{ background: #e8f0fe; color: #1a73e8; }}
  .empty-state {{ text-align: center; padding: 60px 20px; color: #888; }}
  #content {{ min-height: 400px; }}
  .footer {{ text-align: center; padding: 24px; color: #999; font-size: 13px; }}
  .footer a {{ color: #1a73e8; text-decoration: none; }}
</style>
</head>
<body>
<div class="header">
  <h1>Chennai Store Distribution Analyzer</h1>
  <p>Commercial establishment mapping and clustering for Chennai neighborhoods</p>
</div>
<div class="container">
  <div class="tabs" id="tabs"></div>
  <div id="content"></div>
</div>
<div class="footer">
  Built with Google Maps Places API &middot;
  <a href="https://github.com/ashutosh-fyi/maps-analyser" target="_blank">Source on GitHub</a>
</div>

<script>
const DATA = {data_json};
let currentTab = 'overview';
let activeMaps = [];

function setTab(tab) {{
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  destroyMaps();
  loadContent(tab);
}}

function destroyMaps() {{
  activeMaps.forEach(m => m.remove());
  activeMaps = [];
}}

function buildTabs() {{
  const tabs = document.getElementById('tabs');
  let html = '<button class="tab active" data-tab="overview">Overview</button>';
  for (const [key, name] of Object.entries(DATA.regions)) {{
    html += '<button class="tab" data-tab="' + key + '">' + name + '</button>';
  }}
  html += '<button class="tab" data-tab="compare">Compare</button>';
  tabs.innerHTML = html;
  tabs.querySelectorAll('.tab').forEach(btn => {{
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
  }});
}}

function barChart(items, maxVal) {{
  return items.map(([label, count, pct]) => {{
    const w = maxVal > 0 ? (count / maxVal * 100) : 0;
    return '<div class="bar-container">' +
      '<div class="bar-label">' + label + '</div>' +
      '<div class="bar-wrap"><div class="bar-fill" style="width:' + w + '%"><span>' + pct + '%</span></div></div>' +
      '<div class="bar-count">' + count + '</div></div>';
  }}).join('');
}}

function loadContent(tab) {{
  const el = document.getElementById('content');
  if (tab === 'overview') renderOverview(el);
  else if (tab === 'compare') renderCompare(el);
  else renderRegion(el, tab);
}}

function renderOverview(el) {{
  const ov = DATA.overview;
  if (!ov.regions.length) {{
    el.innerHTML = '<div class="empty-state"><p>No data available.</p></div>';
    return;
  }}
  const total = ov.regions.reduce((s,r) => s + r.count, 0);
  let html = '<div class="grid">' +
    '<div class="card"><div class="stat-value">' + total + '</div><div class="stat-label">Total Places</div></div>' +
    '<div class="card"><div class="stat-value">' + ov.regions.length + '</div><div class="stat-label">Regions Analyzed</div></div>' +
    '<div class="card"><div class="stat-value">' + ov.categories.length + '</div><div class="stat-label">Categories</div></div>' +
  '</div>';

  html += '<div class="grid"><div class="card"><h3>Places by Region</h3><table><tr><th>Region</th><th>Count</th></tr>';
  ov.regions.forEach(r => {{ html += '<tr><td>' + r.region.replace(/_/g,' ') + '</td><td>' + r.count + '</td></tr>'; }});
  html += '</table></div>';

  html += '<div class="card"><h3>Top Categories</h3><table><tr><th>Category</th><th>Count</th></tr>';
  ov.categories.forEach(c => {{ html += '<tr><td>' + c.category.replace(/_/g,' ') + '</td><td>' + c.count + '</td></tr>'; }});
  html += '</table></div></div>';
  el.innerHTML = html;
}}

function renderRegion(el, region) {{
  const rd = DATA.region_data[region];
  if (!rd) {{
    el.innerHTML = '<div class="empty-state"><p>No data for this region.</p></div>';
    return;
  }}
  const dist = rd.distribution;
  const dens = rd.density;
  const clust = rd.clusters;
  const maxCount = dist.length ? dist[0].count : 1;

  let html = '<div class="grid">' +
    '<div class="card"><div class="stat-value">' + dens.total_places + '</div><div class="stat-label">Total Places</div></div>' +
    '<div class="card"><div class="stat-value">' + dens.area_sq_km + '</div><div class="stat-label">Area (km&sup2;)</div></div>' +
    '<div class="card"><div class="stat-value">' + dens.overall_density_per_km2 + '</div><div class="stat-label">Stores / km&sup2;</div></div>' +
    '<div class="card"><div class="stat-value">' + clust.n_clusters + '</div><div class="stat-label">Clusters Found</div></div>' +
  '</div>';

  // Category bars
  html += '<div class="section"><h2>Category Distribution</h2><div class="card">';
  const bars = dist.map(d => [d.display_name, d.count, d.percentage]);
  html += barChart(bars, maxCount);
  html += '</div></div>';

  // Clusters table
  const colors = ['#ea4335','#4285f4','#34a853','#7b1fa2','#ff6d00','#c62828','#1565c0','#2e7d32','#5f7c8a','#e91e63'];
  if (clust.clusters && clust.clusters.length) {{
    html += '<div class="section"><h2>Store Clusters (DBSCAN)</h2><div class="card">';
    html += '<p style="margin-bottom:12px;color:#666">' + clust.n_clusters + ' clusters, ' + clust.n_noise + ' noise points (eps=400m, min_samples=5)</p>';
    html += '<table><tr><th>#</th><th>Size</th><th>Center</th><th>Top Categories</th></tr>';
    clust.clusters.forEach((c, i) => {{
      const cats = Object.entries(c.categories).sort((a,b) => b[1]-a[1]).slice(0,3)
        .map(([k,v]) => '<span class="cluster-chip" style="background:' + colors[i%colors.length] + '">' + k.replace(/_/g,' ') + ' (' + v + ')</span>').join(' ');
      html += '<tr><td>' + c.cluster_id + '</td><td>' + c.size + '</td><td>' + c.center_lat.toFixed(4) + ', ' + c.center_lon.toFixed(4) + '</td><td>' + cats + '</td></tr>';
    }});
    html += '</table></div></div>';
  }}

  // Heatmap
  html += '<div class="section"><h2>Heatmap</h2><div class="card"><div id="heatmap-' + region + '" class="map-container"></div></div></div>';

  // Cluster map
  html += '<div class="section"><h2>Cluster Map</h2><div class="card"><div id="clustermap-' + region + '" class="map-container"></div></div></div>';

  // Places table
  html += '<div class="section"><h2>All Places (' + rd.places.length + ')</h2><div class="card" style="max-height:500px;overflow:auto">';
  html += '<table><tr><th>Name</th><th>Category</th><th>Type</th><th>Address</th></tr>';
  rd.places.forEach(p => {{
    html += '<tr><td>' + p.name + '</td><td><span class="badge badge-blue">' + (p.category||'').replace(/_/g,' ') + '</span></td><td>' + (p.primary_type||'').replace(/_/g,' ') + '</td><td style="font-size:12px;color:#666">' + (p.address||'') + '</td></tr>';
  }});
  html += '</table></div></div>';

  el.innerHTML = html;

  // Render leaflet maps
  setTimeout(() => {{
    const bbox = rd.bbox;
    const cLat = (bbox.south + bbox.north) / 2;
    const cLon = (bbox.west + bbox.east) / 2;

    // Heatmap
    const hm = L.map('heatmap-' + region).setView([cLat, cLon], 14);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(hm);
    const heatData = rd.places.map(p => [p.lat, p.lon, 1]);
    L.heatLayer(heatData, {{ radius: 18, blur: 12, maxZoom: 17 }}).addTo(hm);
    activeMaps.push(hm);

    // Cluster map
    const cm = L.map('clustermap-' + region).setView([cLat, cLon], 14);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(cm);
    const markerColors = ['red','blue','green','purple','orange','darkred','darkblue','darkgreen','cadetblue','pink'];
    rd.places.forEach((p, i) => {{
      const label = clust.labels[i];
      const color = label === -1 ? '#999' : colors[label % colors.length];
      L.circleMarker([p.lat, p.lon], {{
        radius: 5, color: color, fillColor: color, fillOpacity: 0.7, weight: 1
      }}).bindPopup(p.name + '<br>' + (p.category||'').replace(/_/g,' ')).addTo(cm);
    }});
    clust.clusters.forEach(c => {{
      L.marker([c.center_lat, c.center_lon]).bindPopup('Cluster ' + c.cluster_id + ': ' + c.size + ' stores').addTo(cm);
    }});
    activeMaps.push(cm);
  }}, 100);
}}

function renderCompare(el) {{
  const comp = DATA.comparison;
  if (!comp.regions || comp.regions.length < 2) {{
    el.innerHTML = '<div class="empty-state"><p>Need at least 2 regions with data.</p></div>';
    return;
  }}
  let html = '<div class="section"><h2>Category Comparison</h2><div class="card" style="overflow-x:auto">';
  html += '<table><tr><th>Category</th>';
  comp.regions.forEach(r => {{ html += '<th>' + r.replace(/_/g,' ') + '</th>'; }});
  html += '</tr>';
  Object.keys(comp.table).forEach(cat => {{
    html += '<tr><td>' + cat + '</td>';
    comp.regions.forEach(r => {{ html += '<td>' + (comp.table[cat][r] || 0) + '</td>'; }});
    html += '</tr>';
  }});
  html += '</table></div></div>';
  el.innerHTML = html;
}}

buildTabs();
setTab('overview');
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
