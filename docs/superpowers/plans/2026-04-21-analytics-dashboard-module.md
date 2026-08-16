# Analytics Dashboard Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an `analytics-dashboard` module within the podcast-publishing-suite that collects data from Ghost and PRX into local JSON snapshots, and a Claude skill (`/wc-analytics`) that refreshes data and answers questions about podcast/newsletter/site performance.

**Architecture:** Collectors pull data from each source API into dated JSON snapshots under `data/<source>/YYYY-MM-DD.json`. A manifest tracks the latest snapshot per source. The `/wc-analytics` skill triggers a refresh, loads the latest snapshots into agent context, and answers natural-language questions. Each collector is a standalone Python module that reads credentials from `.env.prod` and writes to the `data/` directory.

**Tech Stack:** Python 3.11+, requests, PyJWT, python-dotenv. Follows patterns from `prx-to-ghost-publisher` (dataclass configs, retry logic, env-based credential loading).

**Important context for implementers:**
- The PRX Dovetail API (`podcasts.dovetail.prx.org/api/v1`) provides episode *metadata* (title, dates, duration, GUID) but NOT download/listen analytics. The PRX collector captures the episode catalog for cadence analysis.
- Ghost Admin API provides posts (all fields) and members (count, status breakdown) but NOT newsletter open/click rates or site traffic.
- Existing PRX auth code lives at `modules/prx-to-ghost-publisher/src/prx_auth.py` — we'll vendor a lightweight copy rather than importing across submodules.
- Existing Ghost JWT auth pattern lives at `modules/prx-to-ghost-publisher/src/ghost_client.py` — same approach, vendor it.
- Show configs live at `shows/<slug>/config.json` with Ghost and PRX settings per show.

---

### Task 1: Scaffold the module directory and Python project

**Files:**
- Create: `modules/analytics-dashboard/pyproject.toml`
- Create: `modules/analytics-dashboard/README.md`
- Create: `modules/analytics-dashboard/.env.example`
- Create: `modules/analytics-dashboard/.env.prod` (copy credentials from prx-to-ghost-publisher)
- Create: `modules/analytics-dashboard/.gitignore`
- Create: `modules/analytics-dashboard/src/__init__.py`
- Create: `modules/analytics-dashboard/src/config.py`
- Create: `modules/analytics-dashboard/tests/__init__.py`
- Create: `modules/analytics-dashboard/data/.gitkeep`

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p modules/analytics-dashboard/{src,tests,data/ghost,data/prx}
touch modules/analytics-dashboard/src/__init__.py
touch modules/analytics-dashboard/tests/__init__.py
touch modules/analytics-dashboard/data/.gitkeep
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "wc-analytics-dashboard"
version = "0.1.0"
description = "Analytics data collection and reporting for Wonder Cabinet Productions"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}

dependencies = [
    "pyjwt>=2.8.0",
    "requests>=2.31.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
]

[project.scripts]
wc-analytics = "src.cli:main"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create .env.example**

```
# Ghost CMS
GHOST_URL=https://wonder-cabinet.ghost.io
GHOST_ADMIN_API_KEY=key_id:secret

# PRX Dovetail
PRX_CLIENT_ID=your_client_id
PRX_CLIENT_SECRET=your_client_secret
PRX_PODCAST_IDS=120,3329

# Data directory (relative to module root)
DATA_DIR=data
```

- [ ] **Step 4: Create .env.prod by copying credentials**

Copy the Ghost and PRX credentials from `modules/prx-to-ghost-publisher/.env.prod` into `modules/analytics-dashboard/.env.prod`. The file should contain:

```
GHOST_URL=https://wonder-cabinet.ghost.io
GHOST_ADMIN_API_KEY=<copy from prx-to-ghost-publisher .env.prod>
PRX_CLIENT_ID=<copy from prx-to-ghost-publisher .env.prod>
PRX_CLIENT_SECRET=<copy from prx-to-ghost-publisher .env.prod>
PRX_PODCAST_IDS=120,3329
DATA_DIR=data
```

- [ ] **Step 5: Create .gitignore**

```
.env.prod
.env.dev
.venv/
__pycache__/
*.egg-info/
data/ghost/*.json
data/prx/*.json
!data/.gitkeep
```

- [ ] **Step 6: Create src/config.py**

```python
"""Configuration for analytics dashboard."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid."""


@dataclass
class Config:
    """Analytics dashboard configuration."""

    ghost_url: str
    ghost_admin_api_key: str
    prx_client_id: str
    prx_client_secret: str
    prx_podcast_ids: list[str]
    data_dir: Path

    prx_api_base_url: str = "https://podcasts.dovetail.prx.org/api/v1"
    prx_token_endpoint: str = "https://id.prx.org/token"

    @property
    def ghost_api_base_url(self) -> str:
        return f"{self.ghost_url.rstrip('/')}/ghost/api/admin"

    @property
    def ghost_key_id(self) -> str:
        return self.ghost_admin_api_key.split(":")[0]

    @property
    def ghost_key_secret(self) -> bytes:
        return bytes.fromhex(self.ghost_admin_api_key.split(":")[1])


def load_config(env_name: str = "prod") -> Config:
    """Load configuration from .env file.

    Args:
        env_name: Environment name ('dev' or 'prod').

    Returns:
        Validated Config instance.
    """
    project_root = Path(__file__).parent.parent
    env_path = project_root / f".env.{env_name}"

    if not env_path.exists():
        raise ConfigError(f"Environment file not found: {env_path}")

    load_dotenv(env_path, override=True)

    ghost_key = os.getenv("GHOST_ADMIN_API_KEY", "")
    if ":" not in ghost_key:
        raise ConfigError("GHOST_ADMIN_API_KEY must be in format 'key_id:secret'")

    podcast_ids_raw = os.getenv("PRX_PODCAST_IDS", "")
    podcast_ids = [pid.strip() for pid in podcast_ids_raw.split(",") if pid.strip()]

    data_dir = project_root / os.getenv("DATA_DIR", "data")
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        ghost_url=os.getenv("GHOST_URL", ""),
        ghost_admin_api_key=ghost_key,
        prx_client_id=os.getenv("PRX_CLIENT_ID", ""),
        prx_client_secret=os.getenv("PRX_CLIENT_SECRET", ""),
        prx_podcast_ids=podcast_ids,
        data_dir=data_dir,
    )
```

- [ ] **Step 7: Create a minimal README.md**

```markdown
# Analytics Dashboard

Data collection and agentic analysis for Wonder Cabinet Productions.

## Sources

| Source | What it collects | Status |
|--------|-----------------|--------|
| Ghost | Posts, members, newsletters | Active |
| PRX Dovetail | Episode catalog (metadata) | Active |
| Google Analytics | Site traffic | Planned |
| Google Search Console | Search performance | Planned |
| YouTube | Channel metrics | Planned |

## Usage

```bash
# Refresh all data
python -m src.cli refresh

# Refresh a single source
python -m src.cli refresh --source ghost
```

Or use the `/wc-analytics` Claude skill for agentic analysis.
```

- [ ] **Step 8: Commit**

```bash
git add modules/analytics-dashboard/
git commit -m "feat: scaffold analytics-dashboard module

New submodule for collecting and analyzing podcast/newsletter analytics.
Initial structure with config, dependencies, and data directories."
```

---

### Task 2: Ghost collector

**Files:**
- Create: `modules/analytics-dashboard/src/collectors/__init__.py`
- Create: `modules/analytics-dashboard/src/collectors/ghost.py`
- Create: `modules/analytics-dashboard/tests/test_ghost_collector.py`

- [ ] **Step 1: Create the collectors package**

```bash
mkdir -p modules/analytics-dashboard/src/collectors
touch modules/analytics-dashboard/src/collectors/__init__.py
```

- [ ] **Step 2: Write failing test for Ghost JWT generation**

```python
# tests/test_ghost_collector.py
"""Tests for Ghost analytics collector."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.ghost import GhostCollector


@pytest.fixture
def collector():
    """Create a GhostCollector with test credentials."""
    return GhostCollector(
        api_base_url="https://test.ghost.io/ghost/api/admin",
        key_id="abc123",
        key_secret=bytes.fromhex("aa" * 32),
    )


def test_generate_jwt(collector):
    """JWT should contain correct header fields and audience."""
    import jwt as pyjwt

    token = collector._generate_jwt()
    # Decode without verification to inspect claims
    decoded = pyjwt.decode(token, options={"verify_signature": False})
    assert decoded["aud"] == "/admin/"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] - decoded["iat"] == 300
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_ghost_collector.py::test_generate_jwt -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.collectors.ghost'`

- [ ] **Step 4: Implement GhostCollector**

```python
# src/collectors/ghost.py
"""Ghost CMS analytics collector.

Collects post inventory, member counts, and newsletter data
from the Ghost Admin API into dated JSON snapshots.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
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
                return resp.json()

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"Ghost API {resp.status_code}, retry in {delay}s")
                time.sleep(delay)
                continue

            raise GhostCollectorError(
                f"Ghost API error: {resp.status_code} {resp.text[:200]}",
                status_code=resp.status_code,
            )

        raise GhostCollectorError("Max retries exceeded")

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

    def collect_all(self) -> dict:
        """Run all Ghost collectors and return combined snapshot."""
        logger.info("Collecting Ghost analytics data...")
        snapshot = {
            "source": "ghost",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "posts": self.collect_posts(),
            "members": self.collect_members_summary(),
            "newsletters": self.collect_newsletters(),
        }
        post_count = len(snapshot["posts"])
        member_count = snapshot["members"].get("total", "?")
        logger.info(f"Ghost: {post_count} posts, {member_count} members collected")
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
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_ghost_collector.py::test_generate_jwt -v
```

Expected: PASS

- [ ] **Step 6: Add test for collect_posts with mocked HTTP**

Add to `tests/test_ghost_collector.py`:

```python
@patch("src.collectors.ghost.requests.get")
def test_collect_posts(mock_get, collector):
    """collect_posts should paginate and return all posts."""
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "posts": [
                {"id": "1", "title": "Episode 1", "slug": "ep-1", "status": "published"},
                {"id": "2", "title": "Episode 2", "slug": "ep-2", "status": "draft"},
            ],
            "meta": {"pagination": {"page": 1, "pages": 1, "total": 2}},
        }),
    )
    posts = collector.collect_posts()
    assert len(posts) == 2
    assert posts[0]["title"] == "Episode 1"


@patch("src.collectors.ghost.requests.get")
def test_collect_members_summary(mock_get, collector):
    """collect_members_summary should return count breakdown."""
    def side_effect(url, **kwargs):
        params = kwargs.get("params", {})
        filter_val = params.get("filter", "")
        totals = {"status:free": 50, "status:paid": 5, "status:comped": 2}
        total = totals.get(filter_val, 57)
        resp = MagicMock(ok=True)
        resp.json.return_value = {
            "members": [],
            "meta": {"pagination": {"total": total}},
        }
        return resp

    mock_get.side_effect = side_effect
    summary = collector.collect_members_summary()
    assert summary["free"] == 50
    assert summary["paid"] == 5
    assert summary["total"] == 57
```

- [ ] **Step 7: Run all tests**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_ghost_collector.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add modules/analytics-dashboard/src/collectors/ modules/analytics-dashboard/tests/test_ghost_collector.py
git commit -m "feat: add Ghost analytics collector

Collects posts, member counts, and newsletter data from Ghost Admin API
into dated JSON snapshots. Includes pagination, retry logic, and JWT auth."
```

---

### Task 3: PRX Dovetail collector

**Files:**
- Create: `modules/analytics-dashboard/src/collectors/prx.py`
- Create: `modules/analytics-dashboard/tests/test_prx_collector.py`

- [ ] **Step 1: Write failing test for PRX auth token fetch**

```python
# tests/test_prx_collector.py
"""Tests for PRX Dovetail analytics collector."""

from unittest.mock import MagicMock, patch

import pytest

from src.collectors.prx import PRXCollector


@pytest.fixture
def collector():
    """Create a PRXCollector with test credentials."""
    return PRXCollector(
        client_id="test_id",
        client_secret="test_secret",
        podcast_ids=["120", "3329"],
    )


@patch("src.collectors.prx.requests.post")
def test_authenticate(mock_post, collector):
    """Should obtain bearer token via client credentials flow."""
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_abc123",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    token = collector._authenticate()
    assert token == "tok_abc123"
    mock_post.assert_called_once()
    call_data = mock_post.call_args[1].get("data") or mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else mock_post.call_args[1]["data"]
    assert call_data["grant_type"] == "client_credentials"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_prx_collector.py::test_authenticate -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement PRXCollector**

```python
# src/collectors/prx.py
"""PRX Dovetail analytics collector.

Collects episode catalog metadata from the PRX Dovetail Podcasts API
into dated JSON snapshots. Note: download/listen metrics are not
available through this API — this captures the episode inventory
for cadence analysis and cross-referencing with Ghost posts.
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


class PRXCollectorError(Exception):
    """Raised when PRX data collection fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class PRXCollector:
    """Collects episode catalog data from PRX Dovetail API.

    Args:
        client_id: PRX OAuth2 client ID.
        client_secret: PRX OAuth2 client secret.
        podcast_ids: List of PRX podcast IDs to collect.
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
        self._token: str | None = None
        self._token_expires_at: float = 0

    def _authenticate(self) -> str:
        """Obtain bearer token via OAuth2 client credentials flow."""
        resp = requests.post(
            self.token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if not resp.ok:
            raise PRXCollectorError(
                f"PRX auth failed: {resp.status_code}", status_code=resp.status_code
            )
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600) - 60
        return self._token

    def _get_token(self) -> str:
        """Get a valid token, refreshing if needed."""
        if self._token is None or time.time() >= self._token_expires_at:
            self._authenticate()
        return self._token

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make an authenticated GET request to Dovetail API with retries."""
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/json",
        }

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            except requests.RequestException as e:
                if attempt == MAX_RETRIES:
                    raise PRXCollectorError(f"Request failed: {e}")
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                continue

            if resp.ok:
                return resp.json()

            # Refresh token on 401
            if resp.status_code == 401 and attempt < MAX_RETRIES:
                logger.warning("PRX 401, refreshing token")
                self._authenticate()
                headers["Authorization"] = f"Bearer {self._token}"
                continue

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                continue

            raise PRXCollectorError(
                f"Dovetail API error: {resp.status_code}",
                status_code=resp.status_code,
            )

        raise PRXCollectorError("Max retries exceeded")

    def collect_episodes(self, podcast_id: str) -> list[dict]:
        """Fetch all episodes for a podcast.

        Returns simplified episode dicts with key fields.
        """
        all_episodes = []
        page = 1

        while True:
            data = self._request(
                "authorization/episodes",
                params={"page": str(page), "per": "50"},
            )
            items = data.get("_embedded", {}).get("prx:items", [])
            for ep in items:
                all_episodes.append({
                    "id": ep.get("id"),
                    "guid": ep.get("guid"),
                    "title": ep.get("title"),
                    "publishedAt": ep.get("publishedAt"),
                    "releasedAt": ep.get("releasedAt"),
                    "episodeType": ep.get("episodeType"),
                    "duration": ep.get("duration"),
                    "subtitle": ep.get("subtitle"),
                    "tags": ep.get("tags", []),
                })

            # Check for next page
            total = data.get("total", len(all_episodes))
            if len(all_episodes) >= total or not items:
                break
            page += 1

        return all_episodes

    def collect_podcasts(self) -> list[dict]:
        """Fetch podcast metadata for configured podcast IDs."""
        data = self._request("authorization/podcasts")
        podcasts = data.get("_embedded", {}).get("prx:items", [])
        return [
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "subtitle": p.get("subtitle"),
                "episodeCount": p.get("episodeCount"),
            }
            for p in podcasts
        ]

    def collect_all(self) -> dict:
        """Run all PRX collectors and return combined snapshot."""
        logger.info("Collecting PRX Dovetail data...")

        podcasts = self.collect_podcasts()
        episodes = self.collect_episodes(self.podcast_ids[0]) if self.podcast_ids else []

        snapshot = {
            "source": "prx",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "podcasts": podcasts,
            "episodes": episodes,
        }
        logger.info(f"PRX: {len(podcasts)} podcasts, {len(episodes)} episodes collected")
        return snapshot

    def save_snapshot(self, data_dir: Path) -> Path:
        """Collect all data and save as dated JSON snapshot."""
        snapshot = self.collect_all()
        prx_dir = data_dir / "prx"
        prx_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = prx_dir / f"{today}.json"
        path.write_text(json.dumps(snapshot, indent=2, default=str))
        logger.info(f"PRX snapshot saved: {path}")
        return path
```

- [ ] **Step 4: Run tests**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_prx_collector.py -v
```

Expected: PASS

- [ ] **Step 5: Add test for episode collection with mocked HTTP**

Add to `tests/test_prx_collector.py`:

```python
@patch("src.collectors.prx.requests.get")
@patch("src.collectors.prx.requests.post")
def test_collect_episodes(mock_post, mock_get, collector):
    """Should fetch and simplify episode data from Dovetail API."""
    # Auth mock
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_abc",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    # Episodes mock
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "total": 2,
            "_embedded": {
                "prx:items": [
                    {"id": 1, "guid": "g1", "title": "Ep 1", "publishedAt": "2026-04-01", "duration": 1800},
                    {"id": 2, "guid": "g2", "title": "Ep 2", "publishedAt": "2026-04-08", "duration": 2100},
                ],
            },
        }),
    )
    episodes = collector.collect_episodes("120")
    assert len(episodes) == 2
    assert episodes[0]["title"] == "Ep 1"
    assert episodes[1]["duration"] == 2100
```

- [ ] **Step 6: Run all tests**

```bash
cd modules/analytics-dashboard && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add modules/analytics-dashboard/src/collectors/prx.py modules/analytics-dashboard/tests/test_prx_collector.py
git commit -m "feat: add PRX Dovetail episode catalog collector

Fetches podcast metadata and episode catalog from Dovetail API
via OAuth2 client credentials flow. Saves dated JSON snapshots."
```

---

### Task 4: CLI entry point and refresh orchestration

**Files:**
- Create: `modules/analytics-dashboard/src/cli.py`
- Create: `modules/analytics-dashboard/tests/test_cli.py`

- [ ] **Step 1: Write failing test for CLI refresh**

```python
# tests/test_cli.py
"""Tests for analytics CLI."""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from src.cli import refresh


@patch("src.cli.GhostCollector")
@patch("src.cli.PRXCollector")
@patch("src.cli.load_config")
def test_refresh_all(mock_config, mock_prx_cls, mock_ghost_cls, tmp_path):
    """refresh() should invoke both collectors and return snapshot paths."""
    mock_config.return_value = MagicMock(
        ghost_api_base_url="https://test.ghost.io/ghost/api/admin",
        ghost_key_id="abc",
        ghost_key_secret=b"\xaa" * 32,
        prx_client_id="cid",
        prx_client_secret="csec",
        prx_podcast_ids=["120"],
        prx_api_base_url="https://podcasts.dovetail.prx.org/api/v1",
        prx_token_endpoint="https://id.prx.org/token",
        data_dir=tmp_path,
    )
    mock_ghost_cls.return_value.save_snapshot.return_value = tmp_path / "ghost/2026-04-21.json"
    mock_prx_cls.return_value.save_snapshot.return_value = tmp_path / "prx/2026-04-21.json"

    results = refresh()
    assert "ghost" in results
    assert "prx" in results
    mock_ghost_cls.return_value.save_snapshot.assert_called_once()
    mock_prx_cls.return_value.save_snapshot.assert_called_once()


@patch("src.cli.GhostCollector")
@patch("src.cli.load_config")
def test_refresh_single_source(mock_config, mock_ghost_cls, tmp_path):
    """refresh(source='ghost') should only invoke Ghost collector."""
    mock_config.return_value = MagicMock(
        ghost_api_base_url="https://test.ghost.io/ghost/api/admin",
        ghost_key_id="abc",
        ghost_key_secret=b"\xaa" * 32,
        data_dir=tmp_path,
    )
    mock_ghost_cls.return_value.save_snapshot.return_value = tmp_path / "ghost/2026-04-21.json"

    results = refresh(source="ghost")
    assert "ghost" in results
    assert "prx" not in results
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_cli.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement src/cli.py**

```python
"""CLI entry point for analytics dashboard.

Usage:
    python -m src.cli refresh [--source ghost|prx] [--env prod|dev]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config
from .collectors.ghost import GhostCollector
from .collectors.prx import PRXCollector

logger = logging.getLogger(__name__)

VALID_SOURCES = ("ghost", "prx")


def refresh(source: str | None = None, env: str = "prod") -> dict[str, Path]:
    """Refresh analytics data from one or all sources.

    Args:
        source: Specific source to refresh, or None for all.
        env: Environment name for config loading.

    Returns:
        Dict mapping source name to saved snapshot path.
    """
    config = load_config(env)
    results: dict[str, Path] = {}

    if source is None or source == "ghost":
        ghost = GhostCollector(
            api_base_url=config.ghost_api_base_url,
            key_id=config.ghost_key_id,
            key_secret=config.ghost_key_secret,
        )
        results["ghost"] = ghost.save_snapshot(config.data_dir)

    if source is None or source == "prx":
        prx = PRXCollector(
            client_id=config.prx_client_id,
            client_secret=config.prx_client_secret,
            podcast_ids=config.prx_podcast_ids,
            api_base_url=config.prx_api_base_url,
            token_endpoint=config.prx_token_endpoint,
        )
        results["prx"] = prx.save_snapshot(config.data_dir)

    return results


def main():
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Wonder Cabinet Analytics Dashboard")
    sub = parser.add_subparsers(dest="command")

    refresh_cmd = sub.add_parser("refresh", help="Refresh analytics data")
    refresh_cmd.add_argument("--source", choices=VALID_SOURCES, help="Specific source to refresh")
    refresh_cmd.add_argument("--env", default="prod", choices=("dev", "prod"), help="Environment")

    args = parser.parse_args()

    if args.command == "refresh":
        results = refresh(source=args.source, env=args.env)
        for source_name, path in results.items():
            print(f"  {source_name}: {path}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

```bash
cd modules/analytics-dashboard && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/analytics-dashboard/src/cli.py modules/analytics-dashboard/tests/test_cli.py
git commit -m "feat: add CLI entry point with refresh command

Orchestrates Ghost and PRX collectors. Supports refreshing all sources
or a single source via --source flag."
```

---

### Task 5: Snapshot manifest for quick lookups

**Files:**
- Create: `modules/analytics-dashboard/src/manifest.py`
- Create: `modules/analytics-dashboard/tests/test_manifest.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_manifest.py
"""Tests for snapshot manifest."""

import json
from pathlib import Path

import pytest

from src.manifest import get_latest_snapshot, list_snapshots


def test_get_latest_snapshot(tmp_path):
    """Should return the most recent snapshot file for a source."""
    ghost_dir = tmp_path / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "2026-04-19.json").write_text('{"source": "ghost"}')
    (ghost_dir / "2026-04-21.json").write_text('{"source": "ghost"}')
    (ghost_dir / "2026-04-20.json").write_text('{"source": "ghost"}')

    latest = get_latest_snapshot(tmp_path, "ghost")
    assert latest is not None
    assert latest.name == "2026-04-21.json"


def test_get_latest_snapshot_empty(tmp_path):
    """Should return None if no snapshots exist."""
    latest = get_latest_snapshot(tmp_path, "ghost")
    assert latest is None


def test_list_snapshots(tmp_path):
    """Should return sorted list of snapshot dates."""
    ghost_dir = tmp_path / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "2026-04-19.json").write_text("{}")
    (ghost_dir / "2026-04-21.json").write_text("{}")

    snapshots = list_snapshots(tmp_path, "ghost")
    assert snapshots == ["2026-04-19", "2026-04-21"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_manifest.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement manifest.py**

```python
# src/manifest.py
"""Snapshot manifest utilities.

Provides functions to find and list dated JSON snapshots
in the data directory without maintaining a separate index file.
Uses filename sorting (YYYY-MM-DD.json) for ordering.
"""

from __future__ import annotations

import json
from pathlib import Path


def get_latest_snapshot(data_dir: Path, source: str) -> Path | None:
    """Get the path to the most recent snapshot for a source.

    Args:
        data_dir: Root data directory.
        source: Source name (e.g., 'ghost', 'prx').

    Returns:
        Path to latest snapshot file, or None if no snapshots exist.
    """
    source_dir = data_dir / source
    if not source_dir.exists():
        return None

    snapshots = sorted(source_dir.glob("????-??-??.json"))
    return snapshots[-1] if snapshots else None


def list_snapshots(data_dir: Path, source: str) -> list[str]:
    """List all snapshot dates for a source, sorted chronologically.

    Returns:
        List of date strings (YYYY-MM-DD).
    """
    source_dir = data_dir / source
    if not source_dir.exists():
        return []

    return sorted(p.stem for p in source_dir.glob("????-??-??.json"))


def load_latest(data_dir: Path, source: str) -> dict | None:
    """Load and parse the latest snapshot for a source.

    Returns:
        Parsed JSON dict, or None if no snapshots exist.
    """
    path = get_latest_snapshot(data_dir, source)
    if path is None:
        return None
    return json.loads(path.read_text())
```

- [ ] **Step 4: Run tests**

```bash
cd modules/analytics-dashboard && python -m pytest tests/test_manifest.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/analytics-dashboard/src/manifest.py modules/analytics-dashboard/tests/test_manifest.py
git commit -m "feat: add snapshot manifest utilities

File-based snapshot lookup using YYYY-MM-DD.json naming convention.
No separate index needed — sorted glob handles ordering."
```

---

### Task 6: Create the /wc-analytics Claude skill

**Files:**
- Create: `~/.claude/skills/wc-analytics/skill.md`

- [ ] **Step 1: Create the skill file**

```markdown
---
name: wc-analytics
description: Refresh and analyze Wonder Cabinet podcast/newsletter analytics data from Ghost and PRX
args: optional question or analysis request
---

# Wonder Cabinet Analytics

Agentic analytics for Wonder Cabinet Productions — refreshes local data snapshots
from Ghost CMS and PRX Dovetail, then answers questions about podcast, newsletter,
and website performance.

## Data Sources

| Source | What's available | Status |
|--------|-----------------|--------|
| Ghost | Posts (inventory, cadence, status), members (free/paid/comped), newsletters | Active |
| PRX Dovetail | Episode catalog (titles, dates, durations, tags) | Active |
| Google Analytics | Site traffic, page views, audience | Planned |
| Google Search Console | Search impressions, clicks, queries | Planned |
| YouTube | Channel metrics, video performance | Planned |

## Workflow

### Step 1: Refresh data

Run the analytics refresh to pull latest data from all active sources:

```bash
VENV_PYTHON="/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/analytics-dashboard/.venv/bin/python3"

# If venv doesn't exist yet, create it first:
# cd "/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/analytics-dashboard" && python3.11 -m venv .venv && .venv/bin/pip install -e .

cd "/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/analytics-dashboard"
"$VENV_PYTHON" -m src.cli refresh
```

### Step 2: Load the latest snapshots

Read the latest snapshot files to get current data:

```bash
DATA_DIR="/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/analytics-dashboard/data"

# Find latest snapshots
ls -la "$DATA_DIR/ghost/" | tail -3
ls -la "$DATA_DIR/prx/" | tail -3
```

Then use the Read tool to load the most recent JSON files from `data/ghost/` and `data/prx/`.

### Step 3: Analyze and answer

With the snapshot data loaded, answer the user's question. If no specific question was provided (`<args>` is empty), give a general health overview covering:

- **Publishing cadence**: Are episodes and newsletters going out on schedule? (Saturday episodes, Wednesday newsletters per show config)
- **Content inventory**: Total published posts, drafts in the pipeline, most recent publish date
- **Audience**: Member counts (free vs paid), trend if multiple snapshots exist
- **Episode catalog**: Total episodes on PRX, latest release, any gaps in the schedule
- **Cross-reference**: Do all PRX episodes have corresponding Ghost posts?

### Step 4: Recommend

Based on the analysis, offer 2-3 actionable observations. For example:
- "You haven't published a midweek newsletter in 2 weeks"
- "There are 3 draft posts — here's what's queued"
- "Member growth: +12 free subscribers since last snapshot"

## Show Configuration Reference

Show configs live at:
- `podcast-publishing-suite/shows/wonder-cabinet/config.json`
- `podcast-publishing-suite/shows/luminous/config.json`

Schedule slots define expected publishing cadence for each show.

## Credentials

Production credentials: `modules/analytics-dashboard/.env.prod`
(Copied from prx-to-ghost-publisher — same Ghost and PRX accounts)
```

- [ ] **Step 2: Verify the skill is discoverable**

The skill should appear in the available skills list. Test by checking that the file exists and has valid frontmatter.

- [ ] **Step 3: Commit**

```bash
git add ~/.claude/skills/wc-analytics/skill.md
git commit -m "feat: add /wc-analytics Claude skill

Skill that refreshes Ghost + PRX data snapshots and provides
agentic analysis of podcast/newsletter performance."
```

---

### Task 7: Create the venv and run a live smoke test

**Files:** None created — this validates the module end-to-end against production APIs.

- [ ] **Step 1: Create virtual environment**

```bash
cd "/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/analytics-dashboard"
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 2: Run unit tests**

```bash
cd "/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/analytics-dashboard"
.venv/bin/python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Run live refresh against production**

```bash
cd "/Volumes/Mark's SSD/SSD-Dev/wonder-cabinet/podcast-publishing-suite/modules/analytics-dashboard"
.venv/bin/python -m src.cli refresh
```

Expected: Two snapshot files created in `data/ghost/2026-04-21.json` and `data/prx/2026-04-21.json`.

- [ ] **Step 4: Inspect snapshot contents**

Read both snapshot files and verify they contain real data:
- Ghost snapshot should have posts array, members counts, newsletters
- PRX snapshot should have podcasts and episodes arrays

- [ ] **Step 5: Final commit if any adjustments needed**

```bash
git add -A modules/analytics-dashboard/
git commit -m "chore: finalize analytics-dashboard module setup"
```

---

## Scope Notes for Implementers

**What this plan does NOT include (intentionally deferred):**
- Google Analytics collector (needs GA4 API setup)
- Google Search Console collector (needs Search Console API setup)
- YouTube collector (needs YouTube Data API setup)
- Historical trend analysis across multiple snapshots
- Any frontend/dashboard UI
- Automated scheduled collection (cron/GitHub Actions)

These are natural next steps once the Ghost + PRX foundation is proven.
