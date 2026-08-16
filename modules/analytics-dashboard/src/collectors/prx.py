"""PRX Dovetail analytics collector.

Collects episode catalog metadata and podcast inventory from the
PRX Dovetail Podcasts API via OAuth2 client credentials flow.

Note: Dovetail provides episode *metadata* (titles, dates, durations)
but NOT download/listen analytics. This collector captures the episode
inventory for cadence analysis and cross-referencing with Ghost posts.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
TOKEN_EXPIRY_BUFFER = 60  # seconds before expiry to refresh


class PRXCollectorError(Exception):
    """Raised when PRX data collection fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class PRXCollector:
    """Collects podcast and episode metadata from PRX Dovetail API.

    Uses OAuth2 client credentials flow for authentication. Token is
    cached and refreshed automatically when it approaches expiry.

    Args:
        client_id: OAuth2 client ID.
        client_secret: OAuth2 client secret.
        podcast_ids: List of Dovetail podcast IDs to collect.
        api_base_url: Dovetail API base URL.
        token_endpoint: OAuth2 token endpoint URL.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        podcast_ids: list[str],
        api_base_url: str = "https://podcasts.dovetail.prx.org/api/v1",
        token_endpoint: str = "https://id.prx.org/token",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.podcast_ids = podcast_ids
        self.api_base_url = api_base_url.rstrip("/")
        self.token_endpoint = token_endpoint

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def _authenticate(self) -> str:
        """Obtain a bearer token via client credentials flow.

        Returns the access_token string and caches it with expiry.
        """
        resp = requests.post(
            self.token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        if not resp.ok:
            raise PRXCollectorError(
                f"Authentication failed: {resp.status_code} {resp.text[:200]}",
                status_code=resp.status_code,
            )
        token_data = resp.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in
        return self._access_token

    def _get_token(self) -> str:
        """Return a valid access token, refreshing if near expiry."""
        if (
            self._access_token is None
            or time.time() >= self._token_expires_at - TOKEN_EXPIRY_BUFFER
        ):
            self._authenticate()
        return self._access_token  # type: ignore[return-value]

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make an authenticated GET request to the Dovetail API with retries.

        Handles 401 by refreshing token and retrying once. Retries on
        429/5xx with exponential backoff (max 3 retries).
        """
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        token_refreshed = False

        for attempt in range(MAX_RETRIES + 1):
            headers = {"Authorization": f"Bearer {self._get_token()}"}

            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            except requests.RequestException as e:
                if attempt == MAX_RETRIES:
                    raise PRXCollectorError(f"Request failed: {e}")
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                continue

            if resp.ok:
                try:
                    return resp.json()
                except requests.exceptions.JSONDecodeError as e:
                    raise PRXCollectorError(
                        f"PRX API returned non-JSON response from {url}: {resp.text[:200]}"
                    ) from e

            if resp.status_code == 401 and not token_refreshed:
                logger.warning("PRX API 401 on %s (attempt %d), refreshing token", url, attempt)
                self._access_token = None
                token_refreshed = True
                continue

            if resp.status_code == 401 and token_refreshed:
                raise PRXCollectorError(
                    f"PRX authentication failed after token refresh on {url}: "
                    "credentials may be invalid",
                    status_code=401,
                )

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"PRX API {resp.status_code}, retry in {delay}s")
                time.sleep(delay)
                continue

            raise PRXCollectorError(
                f"PRX API error: {resp.status_code} {resp.text[:200]}",
                status_code=resp.status_code,
            )

        raise PRXCollectorError(
            f"PRX API {url} failed after {MAX_RETRIES} retries"
        )

    def _paginate(self, endpoint: str, params: dict | None = None) -> list[dict]:
        """Fetch all pages from a HAL+JSON Dovetail endpoint.

        Items are under `_embedded.prx:items`. Pagination uses `page`
        and `per` query params; `total` indicates total item count.
        """
        params = dict(params or {})
        params.setdefault("per", 100)
        page = 1
        all_items: list[dict] = []

        while True:
            params["page"] = page
            data = self._request(endpoint, params)
            items = data.get("_embedded", {}).get("prx:items", [])
            all_items.extend(items)

            total = data.get("total", 0)
            if len(all_items) >= total or not items:
                break
            page += 1

        return all_items

    @staticmethod
    def _simplify_episode(raw: dict[str, Any]) -> dict[str, Any]:
        """Extract the fields we care about from a raw episode record."""
        return {
            "id": raw.get("id"),
            "guid": raw.get("guid"),
            "title": raw.get("title"),
            "publishedAt": raw.get("publishedAt"),
            "releasedAt": raw.get("releasedAt"),
            "episodeType": raw.get("episodeType"),
            "duration": raw.get("duration"),
            "subtitle": raw.get("subtitle"),
            "tags": raw.get("tags", []),
        }

    @staticmethod
    def _simplify_podcast(raw: dict[str, Any]) -> dict[str, Any]:
        """Extract the fields we care about from a raw podcast record."""
        return {
            "id": raw.get("id"),
            "title": raw.get("title"),
            "subtitle": raw.get("subtitle"),
            "episodeCount": raw.get("episodeCount"),
        }

    def collect_episodes(self, podcast_id: str) -> list[dict]:
        """Collect all episodes for a given podcast.

        Args:
            podcast_id: Dovetail podcast ID.

        Returns:
            List of simplified episode dicts.
        """
        endpoint = f"podcasts/{podcast_id}/episodes"
        raw_episodes = self._paginate(endpoint)
        return [self._simplify_episode(ep) for ep in raw_episodes]

    def collect_podcasts(self) -> tuple[list[dict], list[dict]]:
        """Collect metadata for the configured podcast IDs.

        Returns:
            Tuple of (simplified podcast dicts, collection errors).
        """
        podcasts = []
        errors = []
        for podcast_id in self.podcast_ids:
            try:
                raw = self._request(f"podcasts/{podcast_id}")
                podcasts.append(self._simplify_podcast(raw))
            except PRXCollectorError as e:
                logger.error(f"Failed to collect podcast {podcast_id}: {e}")
                errors.append({"podcast_id": podcast_id, "error": str(e)})
        return podcasts, errors

    def collect_all(self) -> dict:
        """Run all collectors and return a combined snapshot.

        Returns:
            Dict with source, collected_at, podcasts, episodes, and
            collection_errors keys. An empty collection_errors list
            indicates a clean run.
        """
        logger.info("Collecting PRX Dovetail data...")

        podcasts, collection_errors = self.collect_podcasts()

        all_episodes: list[dict] = []
        for podcast_id in self.podcast_ids:
            try:
                eps = self.collect_episodes(podcast_id)
                all_episodes.extend(eps)
                logger.info(f"PRX podcast {podcast_id}: {len(eps)} episodes collected")
            except PRXCollectorError as e:
                logger.error(f"Failed to collect episodes for {podcast_id}: {e}")
                collection_errors.append({"podcast_id": podcast_id, "error": str(e)})

        snapshot = {
            "source": "prx",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "podcasts": podcasts,
            "episodes": all_episodes,
            "collection_errors": collection_errors,
        }
        if collection_errors:
            logger.warning(f"PRX: {len(collection_errors)} collection errors occurred")
        logger.info(
            f"PRX: {len(podcasts)} podcasts, {len(all_episodes)} episodes collected"
        )
        return snapshot

    def save_snapshot(self, data_dir: Path) -> Path:
        """Collect all data and save as a dated JSON snapshot.

        Args:
            data_dir: Root directory for snapshots. File saved at
                      data_dir/prx/YYYY-MM-DD.json.

        Returns:
            Path to the saved snapshot file.
        """
        snapshot = self.collect_all()
        prx_dir = data_dir / "prx"
        prx_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = prx_dir / f"{today}.json"
        path.write_text(json.dumps(snapshot, indent=2, default=str))
        logger.info(f"PRX snapshot saved: {path}")
        return path
