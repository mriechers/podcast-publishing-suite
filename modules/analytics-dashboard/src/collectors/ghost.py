"""Ghost CMS analytics collector.

Collects post inventory, member counts, and newsletter data
from the Ghost Admin API into dated JSON snapshots.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import jwt as pyjwt
import requests

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


class GhostCollectorError(Exception):
    """Raised when Ghost data collection fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GhostCollector:
    """Collects analytics data from Ghost Admin API.

    Args:
        api_base_url: Ghost Admin API base URL (e.g., https://x.ghost.io/ghost/api/admin).
        key_id: Ghost Admin API key ID.
        key_secret: Ghost Admin API secret as bytes.
    """

    def __init__(self, api_base_url: str, key_id: str, key_secret: bytes):
        self.api_base_url = api_base_url.rstrip("/")
        self.key_id = key_id
        self.key_secret = key_secret

    def _generate_jwt(self) -> str:
        """Generate a short-lived JWT for Ghost Admin API."""
        iat = int(time.time())
        header = {"alg": "HS256", "typ": "JWT", "kid": self.key_id}
        payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
        return pyjwt.encode(payload, self.key_secret, algorithm="HS256", headers=header)

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make an authenticated GET request to Ghost Admin API with retries."""
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Ghost {self._generate_jwt()}"}

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            except requests.RequestException as e:
                if attempt == MAX_RETRIES:
                    raise GhostCollectorError(f"Request failed: {e}")
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                continue

            if resp.ok:
                try:
                    return resp.json()
                except requests.exceptions.JSONDecodeError as e:
                    raise GhostCollectorError(
                        f"Ghost API returned non-JSON response from {url}: {resp.text[:200]}"
                    ) from e

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"Ghost API {resp.status_code}, retry in {delay}s")
                time.sleep(delay)
                continue

            raise GhostCollectorError(
                f"Ghost API error: {resp.status_code} {resp.text[:200]}",
                status_code=resp.status_code,
            )

        raise GhostCollectorError(
            f"Ghost API {url} failed after {MAX_RETRIES} retries"
        )

    def _paginate(self, endpoint: str, resource_key: str, params: dict | None = None) -> list[dict]:
        """Fetch all pages of a paginated Ghost endpoint."""
        params = dict(params or {})
        params.setdefault("limit", "100")
        page = 1
        all_items = []

        while True:
            params["page"] = str(page)
            data = self._request(endpoint, params)
            items = data.get(resource_key, [])
            all_items.extend(items)

            meta = data.get("meta", {}).get("pagination", {})
            if page >= meta.get("pages", 1):
                break
            page += 1

        return all_items

    def collect_posts(self) -> list[dict]:
        """Collect all posts with key metadata fields."""
        fields = "id,title,slug,status,published_at,created_at,updated_at,custom_excerpt,feature_image"
        return self._paginate("posts/", "posts", {"fields": fields, "include": "tags", "order": "published_at desc"})

    def collect_members_summary(self) -> dict:
        """Collect member count summary (free vs paid breakdown).

        Uses limit=1 requests with status filters to get counts from pagination metadata
        without downloading all member records.
        """
        counts = {}
        for status in ("free", "paid", "comped"):
            data = self._request("members/", {"limit": "1", "filter": f"status:{status}"})
            meta = data.get("meta", {}).get("pagination", {})
            counts[status] = meta.get("total", 0)

        # Also get total
        data = self._request("members/", {"limit": "1"})
        meta = data.get("meta", {}).get("pagination", {})
        counts["total"] = meta.get("total", 0)

        return counts

    def collect_newsletters(self) -> list[dict]:
        """Collect newsletter configuration and subscriber counts."""
        data = self._request("newsletters/")
        return data.get("newsletters", [])

    def collect_member_growth_history(self) -> list[dict[str, Any]]:
        """Build a monthly cumulative-subscriber time series back to launch.

        Paginates the full member list, extracts ONLY the ``created_at``
        timestamps, and discards everything else (names, emails, locations,
        subscription details). The raw member records never leave this
        method — only the aggregated monthly time series is returned.

        Returns:
            A list of ``{"month": "YYYY-MM", "added": N, "cumulative": M}``
            entries from the earliest signup month through the current
            month, in ascending order. Months with zero signups are
            included (with ``added: 0``) so the series is continuous and
            charts cleanly without gap interpolation.
        """
        # Request only created_at to minimize over-the-wire PII. Ghost's
        # `fields` parameter is best-effort — even if it returns more, we
        # discard everything except the timestamp in the next line.
        raw_members = self._paginate(
            "members/",
            "members",
            {"fields": "id,created_at", "order": "created_at asc"},
        )

        timestamps = sorted(
            m["created_at"] for m in raw_members
            if isinstance(m.get("created_at"), str)
        )
        # Defensive: explicitly drop the reference so PII can't leak via
        # accidental later use of raw_members in a future edit.
        del raw_members

        if not timestamps:
            return []

        # ISO 8601 strings like "2026-01-15T12:34:56.000Z" sort
        # lexicographically and slice cleanly to "YYYY-MM".
        by_month: defaultdict[str, int] = defaultdict(int)
        for ts in timestamps:
            by_month[ts[:7]] += 1

        earliest = min(by_month.keys())
        latest = max(by_month.keys())
        current = date.fromisoformat(f"{earliest}-01")
        end = date.fromisoformat(f"{latest}-01")

        history: list[dict[str, Any]] = []
        cumulative = 0
        while current <= end:
            month_key = current.strftime("%Y-%m")
            added = by_month.get(month_key, 0)
            cumulative += added
            history.append({
                "month": month_key,
                "added": added,
                "cumulative": cumulative,
            })
            current = (
                date(current.year + 1, 1, 1)
                if current.month == 12
                else date(current.year, current.month + 1, 1)
            )
        return history

    def collect_all(self) -> dict:
        """Run all Ghost collectors and return combined snapshot."""
        logger.info("Collecting Ghost analytics data...")
        snapshot = {
            "source": "ghost",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "posts": self.collect_posts(),
            "members": self.collect_members_summary(),
            "member_growth_history": self.collect_member_growth_history(),
            "newsletters": self.collect_newsletters(),
        }
        post_count = len(snapshot["posts"])
        member_count = snapshot["members"].get("total", "?")
        history_months = len(snapshot["member_growth_history"])
        logger.info(
            f"Ghost: {post_count} posts, {member_count} members, "
            f"{history_months} months of growth history collected"
        )
        return snapshot

    def save_snapshot(self, data_dir: Path) -> Path:
        """Collect all data and save as dated JSON snapshot.

        Returns the path to the saved file.
        """
        snapshot = self.collect_all()
        ghost_dir = data_dir / "ghost"
        ghost_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = ghost_dir / f"{today}.json"
        path.write_text(json.dumps(snapshot, indent=2, default=str))
        logger.info(f"Ghost snapshot saved: {path}")
        return path
