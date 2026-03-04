# Chennai Store Distribution Analyzer

> **Work in progress**

## Hypothesis

Chennai neighborhoods are disproportionately saturated with restaurants and food outlets, followed by clothing and shopping stores, far outweighing other commercial categories. This tool was built to test that assumption with real data from Google Maps.

Early results across 5 neighborhoods (6,500+ places) show Food & Dining leading, but the gap to other categories like Health and Clothing is narrower than expected — more analysis to come.

**[Live Demo](https://ashutosh-fyi.github.io/maps-analyser/)**

## Neighborhoods

| Region | Places |
|---|---|
| Anna Nagar | 2,238 |
| T. Nagar | 1,896 |
| Adyar | 1,125 |
| Guduvanchery | 1,055 |
| Urapakkam | 228 |

## Features

- **Fetch** commercial places via Google Places API (New) with type-group splitting for better coverage
- **Categorize** into 10 categories: Food & Dining, Health, Clothing, Automotive, Education, Beauty, Grocery, Finance, Home & Hardware, Electronics
- **Analyze** with category distributions, spatial density (stores/km²), and DBSCAN clustering (haversine metric)
- **Visualize** with interactive Leaflet heatmaps, cluster maps, and bar charts
- **Compare** category distributions across neighborhoods
- **Export** data to CSV

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # Add your Google Maps API key

# CLI
python -m maps_analyser fetch t_nagar
python -m maps_analyser analyze t_nagar
python -m maps_analyser visualize t_nagar
python -m maps_analyser compare t_nagar anna_nagar adyar
python -m maps_analyser export t_nagar
python -m maps_analyser stats

# Web UI (local)
python web_ui.py        # http://localhost:5001
```

## Tech Stack

Python 3.11+, Google Places API (New), SQLite, pandas, scikit-learn, matplotlib, folium, Leaflet.js
