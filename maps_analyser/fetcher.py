"""Google Places API (New) client with rate limiting, retry, and type-group splitting."""

import logging
import time

import requests

from config.settings import (
    GOOGLE_MAPS_API_KEY,
    PLACES_API_URL,
    FIELD_MASK,
    SEARCH_RADIUS_M,
    GRID_STEP_M,
    REQUEST_TIMEOUT_S,
    MAX_RETRIES,
    RATE_LIMIT_DELAY_S,
    get_type_groups,
    get_regions,
)
from maps_analyser.region import generate_grid_tiles

logger = logging.getLogger(__name__)


class PlacesFetcher:
    def __init__(self, api_key: str = GOOGLE_MAPS_API_KEY):
        self.api_key = api_key
        self.type_groups = get_type_groups()
        self._session = None

    @property
    def session(self) -> requests.Session:
        """Lazy session init — only created when making actual API calls."""
        if self._session is None:
            if not self.api_key:
                raise ValueError("GOOGLE_MAPS_API_KEY not set. Copy .env.example to .env and add your key.")
            self._session = requests.Session()
            self._session.headers.update({
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": FIELD_MASK,
            })
        return self._session

    def search_nearby(self, lat: float, lon: float, radius: float, included_types: list[str]) -> list[dict]:
        """Single searchNearby call. Returns list of raw place dicts."""
        body = {
            "includedTypes": included_types,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": radius,
                }
            },
            "maxResultCount": 20,
        }

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(PLACES_API_URL, json=body, timeout=REQUEST_TIMEOUT_S)

                if resp.status_code == 200:
                    data = resp.json()
                    places = data.get("places", [])
                    if len(places) == 20:
                        logger.warning(
                            "Got 20 results (possible truncation) at (%.4f, %.4f) types=%s",
                            lat, lon, included_types[:3],
                        )
                    return places

                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning("Rate limited (429), waiting %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
                    time.sleep(wait)
                    continue

                if resp.status_code == 403:
                    logger.error("403 Forbidden — check your API key and billing. Response: %s", resp.text)
                    raise PermissionError(f"API returned 403: {resp.text}")

                logger.error("API error %d: %s", resp.status_code, resp.text)
                resp.raise_for_status()

            except requests.exceptions.Timeout:
                logger.warning("Timeout at (%.4f, %.4f), attempt %d/%d", lat, lon, attempt + 1, MAX_RETRIES)
                if attempt == MAX_RETRIES - 1:
                    raise
            except requests.exceptions.ConnectionError:
                logger.warning("Connection error, attempt %d/%d", attempt + 1, MAX_RETRIES)
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)

        return []

    def fetch_tile(self, lat: float, lon: float, radius: float = SEARCH_RADIUS_M) -> list[dict]:
        """Fetch all places in a tile by iterating over type groups."""
        all_places = []
        for type_group in self.type_groups:
            time.sleep(RATE_LIMIT_DELAY_S)
            places = self.search_nearby(lat, lon, radius, type_group)
            all_places.extend(places)
            logger.debug("Tile (%.4f, %.4f) type_group[0]=%s → %d results", lat, lon, type_group[0], len(places))
        return all_places

    def fetch_region(self, region_key: str) -> list[dict]:
        """Fetch all places for a named region."""
        regions = get_regions()
        if region_key not in regions:
            raise ValueError(f"Unknown region: {region_key}. Available: {list(regions.keys())}")

        bbox = regions[region_key]["bbox"]
        tiles = generate_grid_tiles(bbox, GRID_STEP_M)
        display_name = regions[region_key]["display_name"]
        total_calls = len(tiles) * len(self.type_groups)

        logger.info("Fetching %s: %d tiles × %d type groups = %d API calls", display_name, len(tiles), len(self.type_groups), total_calls)

        all_places = []
        for i, tile in enumerate(tiles, 1):
            logger.info("Tile %d/%d (%.4f, %.4f)", i, len(tiles), tile["lat"], tile["lon"])
            places = self.fetch_tile(tile["lat"], tile["lon"])
            all_places.extend(places)

        logger.info("Fetched %d raw results for %s (before dedup)", len(all_places), display_name)
        return all_places

    def estimate_calls(self, region_key: str) -> dict:
        """Dry-run: estimate API calls and cost for a region."""
        regions = get_regions()
        if region_key not in regions:
            raise ValueError(f"Unknown region: {region_key}. Available: {list(regions.keys())}")

        bbox = regions[region_key]["bbox"]
        tiles = generate_grid_tiles(bbox, GRID_STEP_M)
        n_tiles = len(tiles)
        n_groups = len(self.type_groups)
        total_calls = n_tiles * n_groups
        # Pro SKU: $32/1000 after free tier (first 5000/month free)
        cost_usd = max(0, total_calls - 5000) * 0.032

        return {
            "region": region_key,
            "display_name": regions[region_key]["display_name"],
            "tiles": n_tiles,
            "type_groups": n_groups,
            "total_api_calls": total_calls,
            "estimated_cost_usd": cost_usd,
            "radius_m": SEARCH_RADIUS_M,
            "step_m": GRID_STEP_M,
        }
