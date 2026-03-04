# Project: Chennai Store Distribution Analyzer

Python CLI + web tool that fetches commercial establishments from Google Maps Places API (New) for Chennai neighborhoods, categorizes them, and produces distribution analytics with interactive visualizations.

**Status**: Work in progress. Hypothesis: restaurants/food outlets and clothing stores disproportionately dominate Chennai neighborhoods.

## Code Style

- Python 3.11+, type hints where useful
- No class hierarchies unless needed — prefer functions and simple data classes
- Imports: stdlib first, then third-party, then local (`config.settings`, `maps_analyser.*`)
- YAML for configuration, not Python dicts
- Keep modules focused: one responsibility per file

## Commands

```bash
# Install
pip install -r requirements.txt

# CLI (all commands via python -m)
python -m maps_analyser fetch t_nagar         # Fetch from Google Maps API → SQLite
python -m maps_analyser fetch --all           # All neighborhoods
python -m maps_analyser analyze t_nagar       # Category stats, density, clusters
python -m maps_analyser visualize t_nagar     # Charts + maps
python -m maps_analyser compare t_nagar anna_nagar adyar
python -m maps_analyser export t_nagar        # CSV export
python -m maps_analyser estimate t_nagar      # Dry run: API call count + cost
python -m maps_analyser stats                 # DB summary

# Web UI (local Flask)
python web_ui.py                              # http://localhost:5001

# Static site (GitHub Pages)
python build_static.py                        # Builds docs/index.html
```

## Architecture

```
config/
  settings.py          # Loads .env + YAML, defines constants (paths, API URL, DBSCAN params)
  regions.yaml         # Neighborhood bounding boxes (lat/lon)
  categories.yaml      # Google Places type → internal category mapping

maps_analyser/
  __main__.py          # Entry point: python -m maps_analyser
  cli.py               # argparse with subcommands
  pipeline.py          # Orchestrates fetch → normalize → store → analyze → visualize
  region.py            # Bounding box → grid tiles (haversine-aware)
  fetcher.py           # PlacesFetcher: API client with rate limiting, retry, type-group splitting
  normalizer.py        # Raw API response → clean records, dedup by place_id, category assignment
  storage.py           # SQLite CRUD (upsert, query, CSV export)
  analytics.py         # Category distribution, spatial density, DBSCAN clustering
  visualizer.py        # matplotlib charts + folium heatmaps/cluster maps

web_ui.py              # Flask web UI (local dev)
build_static.py        # Generates static docs/index.html with embedded data + Leaflet.js
```

## Key Design Decisions

- **Tiling**: 500m search radius, 750m grid step. Overlap avoids truncation in dense areas.
- **Type-group splitting**: ~10 API calls per tile (one per category group) to overcome the 20-result-per-call cap. Each category gets its own budget.
- **Field mask**: Only Pro SKU fields (`id, displayName, location, types, formattedAddress, primaryType`). No Enterprise fields.
- **Deduplication**: By `place_id` in normalizer + `INSERT OR REPLACE` in SQLite.
- **DBSCAN**: Haversine metric, `eps=400m`, `min_samples=5`, `ball_tree` algorithm.
- **Lazy API session**: `PlacesFetcher.session` is a property — only created when making actual API calls. `estimate` command works without an API key.

## Important Notes

- **API key** lives in `.env` (gitignored). Never commit it.
- **Rate limiting**: 200ms delay between calls + exponential backoff on 429. 403 = bad API key, stop immediately.
- **20-result warning**: If a call returns exactly 20 results, it's likely truncated. Logged as warning.
- Region keys use snake_case (`t_nagar`, `anna_nagar`). Display names are in `regions.yaml`.
- Adding a new neighborhood: add its bounding box to `config/regions.yaml`, then `fetch` it.
- After fetching new data, run `python build_static.py` to regenerate the GitHub Pages site.
- SQLite DB is at `data/stores.db`. Delete it to start fresh.

## Neighborhoods

Currently configured: `t_nagar`, `anna_nagar`, `adyar`, `guduvanchery`, `urapakkam`

## External Dependencies

- **Google Places API (New)**: `POST https://places.googleapis.com/v1/places:searchNearby`
- **Leaflet.js + leaflet-heat**: Used in static site (CDN, no local install)
- Python: requests, python-dotenv, pyyaml, pandas, numpy, scikit-learn, matplotlib, folium, flask
