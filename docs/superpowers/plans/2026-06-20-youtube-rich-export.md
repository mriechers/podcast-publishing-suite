# YouTube Rich Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Python YouTube publish target to `prx-to-ghost-publisher` that uploads a rendered episode MP4 with PRX-sourced metadata, an on-brand 16:9 thumbnail, SRT captions, and the COPPA flag — replacing the thin TypeScript uploader in `audiogram-tools`.

**Architecture:** The render stays TypeScript (Remotion); everything after the MP4 exists moves to Python, co-located with the PRX feed parser and OG-image compositor it reuses. A CLI orchestrator (`youtube_export.py`) loads the episode manifest + show config, resolves the episode in the live PRX feed, composes metadata, generates the thumbnail, then uploads via the YouTube Data API v3 using the existing long-lived OAuth token. Error handling is persist-then-enrich: the video id is written to the manifest immediately after `videos.insert`, and thumbnail/captions/playlist are best-effort enrichment that never roll back the recorded video.

**Tech Stack:** Python 3, `google-api-python-client` + `google-auth`, Pillow, `requests` (existing `feed_parser.py`), pytest + `unittest.mock`.

**Spec:** `planning/2026-06-20-youtube-rich-export-design.md`

## Global Constraints

- **Module:** all new code lives in `modules/prx-to-ghost-publisher/src/`; tests in `modules/prx-to-ghost-publisher/tests/`.
- **Test command:** `cd modules/prx-to-ghost-publisher && python -m pytest tests/ -v`
- **Test discovery:** files `test_*.py`, functions `test_*` (per `pyproject.toml`).
- **Suite root from a module file:** `Path(__file__).resolve().parent.parent.parent.parent` → suite root; shows at `<suite-root>/shows/<slug>/config.json`.
- **OAuth token path:** `modules/audiogram-tools/.youtube-token.json` (Node-format: `access_token`, `refresh_token`, `scope`, `token_type`, `expiry_date` in **milliseconds**). Client id/secret from env `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`. Token URI `https://oauth2.googleapis.com/token`.
- **Thumbnail:** output 1280×720, **must be < 2,097,152 bytes** (`thumbnails.set` hard limit).
- **WC green:** `#10A544` = `(16, 165, 68)`. Branded background asset: `modules/prx-to-ghost-publisher/images/og-left-logo.png`.
- **Default privacy:** `private`. **Category:** `27`. **madeForKids:** always `false`.
- **Caption track:** language `en`, name `English`, from `<episode-dir>/captions.srt`.
- **Commit style:** Conventional Commits; commit at the end of each task.

---

### Task 1: Dependencies + module scaffolding

**Files:**
- Modify: `modules/prx-to-ghost-publisher/pyproject.toml` (dependencies list)
- Create (empty stubs, filled by later tasks): `src/youtube_auth.py`, `src/youtube_thumbnail.py`, `src/youtube_metadata.py`, `src/youtube_client.py`, `src/youtube_export.py`

- [ ] **Step 1: Add Google client libraries to dependencies**

In `pyproject.toml`, add to the `dependencies` array:

```toml
    "google-api-python-client>=2.100.0",
    "google-auth>=2.23.0",
    "google-auth-oauthlib>=1.1.0",
```

- [ ] **Step 2: Install**

Run: `cd modules/prx-to-ghost-publisher && pip install -e .`
Expected: installs the three google packages without error.

- [ ] **Step 3: Verify import**

Run: `cd modules/prx-to-ghost-publisher && python -c "import googleapiclient.discovery, google.oauth2.credentials; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add modules/prx-to-ghost-publisher/pyproject.toml
git commit -m "build(prx-publisher): add google-api-python-client for YouTube target"
```

---

### Task 2: OAuth token adapter (`youtube_auth.py`)

**Files:**
- Create: `src/youtube_auth.py`
- Test: `tests/test_youtube_auth.py`

**Interfaces:**
- Produces: `load_credentials(token_path: Path, client_id: str, client_secret: str) -> google.oauth2.credentials.Credentials`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_auth.py
import json
from pathlib import Path
from src.youtube_auth import load_credentials


def test_load_credentials_maps_node_token(tmp_path):
    token = {
        "access_token": "ya29.abc",
        "refresh_token": "1//refresh",
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl",
        "token_type": "Bearer",
        "expiry_date": 1781978202016,  # ms
    }
    p = tmp_path / ".youtube-token.json"
    p.write_text(json.dumps(token))

    creds = load_credentials(p, client_id="cid", client_secret="secret")

    assert creds.token == "ya29.abc"
    assert creds.refresh_token == "1//refresh"
    assert "youtube.force-ssl" in " ".join(creds.scopes)
    # expiry_date ms -> seconds -> naive UTC datetime
    assert creds.expiry.year == 2026
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_auth.py -v`
Expected: FAIL — `ModuleNotFoundError` / `load_credentials` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/youtube_auth.py
"""Load the Node-minted YouTube OAuth token into google-auth Credentials."""
import json
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials

TOKEN_URI = "https://oauth2.googleapis.com/token"


def load_credentials(token_path: Path, client_id: str, client_secret: str) -> Credentials:
    """Adapt the audiogram-tools .youtube-token.json (Node googleapis format)
    into a google.oauth2 Credentials object capable of auto-refresh."""
    data = json.loads(Path(token_path).read_text())
    scopes = data.get("scope", "").split()
    creds = Credentials(
        token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )
    expiry_ms = data.get("expiry_date")
    if expiry_ms:
        # google-auth compares expiry as a naive UTC datetime
        creds.expiry = datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    return creds
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_auth.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_auth.py tests/test_youtube_auth.py
git commit -m "feat(prx-publisher): YouTube OAuth token adapter"
```

---

### Task 3: 16:9 thumbnail generator (`youtube_thumbnail.py`)

**Files:**
- Create: `src/youtube_thumbnail.py`
- Test: `tests/test_youtube_thumbnail.py`

**Interfaces:**
- Produces: `generate_youtube_thumbnail(square_image_path: Path, output_path: Path, background_path: Path | None = None) -> Path`
- Constants: `YT_WIDTH = 1280`, `YT_HEIGHT = 720`, `YT_THUMB_MAX_BYTES = 2_097_152`, `DEFAULT_BG_PATH`

Approach: build a 1280×720 canvas filled with the branded background's own green (sampled from its top-left pixel so seams are invisible), paste the branded background (logo+wordmark, the existing `og-left-logo.png`) centered vertically, then paste the square art resized to 720px tall and right-justified over it. Save JPEG, stepping quality down until the file is under the 2 MiB cap.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_thumbnail.py
from pathlib import Path
from PIL import Image
from src.youtube_thumbnail import (
    generate_youtube_thumbnail, YT_WIDTH, YT_HEIGHT, YT_THUMB_MAX_BYTES,
)


def _square(tmp_path, color=(200, 50, 50), size=3000) -> Path:
    p = tmp_path / "art.jpg"
    Image.new("RGB", (size, size), color).save(p, "JPEG", quality=95)
    return p


def test_thumbnail_is_1280x720_and_under_cap(tmp_path):
    src = _square(tmp_path)
    out = tmp_path / "thumb.jpg"
    result = generate_youtube_thumbnail(src, out)
    assert result == out
    with Image.open(out) as img:
        assert img.size == (YT_WIDTH, YT_HEIGHT)
    assert out.stat().st_size < YT_THUMB_MAX_BYTES


def test_thumbnail_art_is_right_justified(tmp_path):
    # square art is solid red; the right edge column should be red (art),
    # the left edge column should NOT be red (branded panel/green).
    src = _square(tmp_path, color=(255, 0, 0))
    out = tmp_path / "thumb.jpg"
    generate_youtube_thumbnail(src, out)
    with Image.open(out) as img:
        right = img.getpixel((YT_WIDTH - 2, YT_HEIGHT // 2))
        left = img.getpixel((2, YT_HEIGHT // 2))
    assert right[0] > 180 and right[1] < 80  # red-ish
    assert not (left[0] > 180 and left[1] < 80)  # not red
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_thumbnail.py -v`
Expected: FAIL — module/function undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/youtube_thumbnail.py
"""Generate a 1280x720 on-brand YouTube thumbnail from square episode art.

Reuses the og_image compositing idea (square art right-justified on a branded
green canvas) at YouTube thumbnail dimensions, and guarantees the output stays
under YouTube's 2 MiB thumbnail limit.
"""
from pathlib import Path
from typing import Optional

from PIL import Image

YT_WIDTH = 1280
YT_HEIGHT = 720
YT_THUMB_MAX_BYTES = 2_097_152  # YouTube thumbnails.set hard limit

DEFAULT_BG_PATH = Path(__file__).parent.parent / "images" / "og-left-logo.png"


def generate_youtube_thumbnail(
    square_image_path: Path,
    output_path: Path,
    background_path: Optional[Path] = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path = background_path or DEFAULT_BG_PATH

    if Path(bg_path).is_file():
        branded = Image.open(bg_path).convert("RGB")
        green = branded.getpixel((0, 0))  # sample for an invisible seam
        canvas = Image.new("RGB", (YT_WIDTH, YT_HEIGHT), green)
        canvas.paste(branded, (0, (YT_HEIGHT - branded.size[1]) // 2))
    else:
        canvas = Image.new("RGB", (YT_WIDTH, YT_HEIGHT), (16, 165, 68))  # WC green

    with Image.open(square_image_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        scale = YT_HEIGHT / max(img.size[0], img.size[1])
        new_w = int(img.size[0] * scale)
        new_h = int(img.size[1] * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas.paste(resized, (YT_WIDTH - new_w, (YT_HEIGHT - new_h) // 2))

    quality = 88
    while quality >= 60:
        canvas.save(output_path, "JPEG", quality=quality)
        if output_path.stat().st_size < YT_THUMB_MAX_BYTES:
            break
        quality -= 6
    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_thumbnail.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_thumbnail.py tests/test_youtube_thumbnail.py
git commit -m "feat(prx-publisher): 1280x720 on-brand YouTube thumbnail generator"
```

---

### Task 4: keywords.md / chapters.md parsers (`youtube_metadata.py` — parsing helpers)

**Files:**
- Create: `src/youtube_metadata.py` (parsing helpers only this task)
- Test: `tests/test_youtube_metadata_parse.py`
- Reference fixtures: real files at `shows/wonder-cabinet/episodes/WC_S01_15_D._Graham_Burnett/{keywords.md,chapters.md}`

**Interfaces:**
- Produces: `parse_keywords(path: Path) -> dict` with keys `"primary": list[str]`, `"topic_tags": list[str]`
- Produces: `parse_chapters_youtube(path: Path) -> str` (the "YouTube Description Format" timestamp block, or `""`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_metadata_parse.py
from src.youtube_metadata import parse_keywords, parse_chapters_youtube


def test_parse_keywords(tmp_path):
    p = tmp_path / "keywords.md"
    p.write_text(
        "## Primary Keywords\n- attention economy\n- wonder\n\n"
        "## Topic Tags\nphilosophy, neuroscience, attention\n"
    )
    kw = parse_keywords(p)
    assert kw["primary"] == ["attention economy", "wonder"]
    assert kw["topic_tags"] == ["philosophy", "neuroscience", "attention"]


def test_parse_chapters_youtube(tmp_path):
    p = tmp_path / "chapters.md"
    p.write_text(
        "## Episode Description Timestamps\n00:00 Intro\n\n"
        "## YouTube Description Format\n0:00 Introduction\n3:00 Human Fracking\n\n"
        "## Podcasting 2.0 JSON Chapters\n{...}\n"
    )
    block = parse_chapters_youtube(p)
    assert block == "0:00 Introduction\n3:00 Human Fracking"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_parse.py -v`
Expected: FAIL — functions undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/youtube_metadata.py
"""Compose YouTube metadata from PRX feed + local episode artifacts."""
import re
from pathlib import Path


def _section(text: str, heading: str) -> str:
    """Return the body lines under a `## heading` up to the next `## `."""
    lines = text.splitlines()
    out, capturing = [], False
    for line in lines:
        if line.strip().lower().startswith("## "):
            capturing = line.strip().lower() == f"## {heading.lower()}"
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def parse_keywords(path: Path) -> dict:
    text = Path(path).read_text()
    primary = [
        m.group(1).strip()
        for m in re.finditer(r"^[-*]\s+(.+)$", _section(text, "Primary Keywords"), re.M)
    ]
    topic_raw = _section(text, "Topic Tags")
    topic_tags = [t.strip() for t in topic_raw.replace("\n", ",").split(",") if t.strip()]
    return {"primary": primary, "topic_tags": topic_tags}


def parse_chapters_youtube(path: Path) -> str:
    return _section(Path(path).read_text(), "YouTube Description Format")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_parse.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_metadata.py tests/test_youtube_metadata_parse.py
git commit -m "feat(prx-publisher): keywords.md/chapters.md parsers for YouTube metadata"
```

---

### Task 5: Resolve the episode in the PRX feed (`youtube_metadata.py` — resolver)

**Files:**
- Modify: `src/youtube_metadata.py` (add resolver)
- Test: `tests/test_youtube_metadata_resolve.py`

**Interfaces:**
- Consumes: `feed_parser.parse_feed_file(path) -> list[Episode]`, `feed_parser.get_episodes(feed_url) -> list[Episode]`, `Episode` (fields `title`, `description`, `guid`, `pub_date: datetime`).
- Produces: `resolve_prx_episode(episodes: list[Episode], guest_name: str, published_at: datetime | None = None) -> Episode` (raises `LookupError` if no match).

Match strategy: filter feed episodes whose title contains the guest's last name (case-insensitive); if several, pick the one whose `pub_date` is closest to `published_at`; if none match by name, fall back to closest `pub_date`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_metadata_resolve.py
from datetime import datetime
from src.feed_parser import Episode
from src.youtube_metadata import resolve_prx_episode


def _ep(title, guid, y, mo, d):
    return Episode(
        guid=guid, title=title, description="<p>x</p>", subtitle="",
        pub_date=datetime(y, mo, d), link="", enclosure_url="",
        enclosure_type="audio/mpeg", duration="", image_url="",
    )


def test_resolve_matches_guest_lastname():
    eps = [
        _ep("Carlo Rovelli: The Order of Time", "g1", 2026, 5, 16),
        _ep("Caroline Winterer: Dinosaurs, Deep Time", "g2", 2026, 4, 25),
    ]
    ep = resolve_prx_episode(eps, guest_name="Caroline Winterer",
                             published_at=datetime(2026, 4, 25))
    assert ep.guid == "g2"


def test_resolve_tiebreaks_on_pub_date():
    eps = [
        _ep("Special: Winterer Live 2024", "old", 2024, 1, 1),
        _ep("Caroline Winterer: Deep Time", "new", 2026, 4, 25),
    ]
    ep = resolve_prx_episode(eps, guest_name="Caroline Winterer",
                             published_at=datetime(2026, 4, 25))
    assert ep.guid == "new"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_resolve.py -v`
Expected: FAIL — `resolve_prx_episode` undefined.

- [ ] **Step 3: Write minimal implementation**

Append to `src/youtube_metadata.py`:

```python
from datetime import datetime
from .feed_parser import Episode


def resolve_prx_episode(
    episodes: list[Episode],
    guest_name: str,
    published_at: datetime | None = None,
) -> Episode:
    last = guest_name.strip().split()[-1].lower() if guest_name.strip() else ""
    named = [e for e in episodes if last and last in e.title.lower()]
    pool = named or episodes
    if not pool:
        raise LookupError(f"No PRX episode found for guest '{guest_name}'")
    if published_at is None:
        return pool[0]  # feed is newest-first

    def naive(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    target = naive(published_at)
    return min(pool, key=lambda e: abs((naive(e.pub_date) - target).total_seconds()))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_resolve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_metadata.py tests/test_youtube_metadata_resolve.py
git commit -m "feat(prx-publisher): resolve episode in PRX feed by guest + pub date"
```

---

### Task 6: Compose title + tags (`youtube_metadata.py`)

**Files:**
- Modify: `src/youtube_metadata.py`
- Test: `tests/test_youtube_metadata_compose.py`

**Interfaces:**
- Produces: `compose_title(episode: Episode, override: str | None = None, max_len: int = 100) -> str`
- Produces: `compose_tags(keywords: dict, show_name: str, max_total: int = 500, max_each: int = 30) -> list[str]` (keywords is the dict from `parse_keywords`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_metadata_compose.py
from datetime import datetime
from src.feed_parser import Episode
from src.youtube_metadata import compose_title, compose_tags


def _ep(title):
    return Episode(guid="g", title=title, description="", subtitle="",
                   pub_date=datetime(2026, 5, 23), link="", enclosure_url="",
                   enclosure_type="audio/mpeg", duration="", image_url="")


def test_compose_title_uses_prx_verbatim():
    assert compose_title(_ep("Caroline Winterer: Deep Time")) == "Caroline Winterer: Deep Time"


def test_compose_title_honors_override_and_caps():
    long = "x" * 130
    out = compose_title(_ep("ignored"), override=long)
    assert len(out) <= 100 and out.endswith("…")


def test_compose_tags_dedupes_caps_and_includes_show():
    kw = {"primary": ["Wonder", "wonder"], "topic_tags": ["attention", "x" * 40]}
    tags = compose_tags(kw, show_name="Wonder Cabinet")
    assert "wonder cabinet" in tags
    assert "podcast" in tags
    assert tags.count("wonder") == 1  # case-folded dedupe
    assert all(len(t) <= 30 for t in tags)
    assert len(",".join(tags)) <= 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_compose.py -v`
Expected: FAIL — functions undefined.

- [ ] **Step 3: Write minimal implementation**

Append to `src/youtube_metadata.py`:

```python
def compose_title(episode: Episode, override: str | None = None, max_len: int = 100) -> str:
    title = (override or episode.title or "").strip()
    if len(title) <= max_len:
        return title
    cut = title[: max_len - 1].rsplit(" ", 1)[0]
    return cut + "…"


def compose_tags(keywords: dict, show_name: str, max_total: int = 500, max_each: int = 30) -> list[str]:
    candidates = [show_name, "podcast"]
    candidates += keywords.get("primary", [])
    candidates += keywords.get("topic_tags", [])
    out, seen, total = [], set(), 0
    for raw in candidates:
        tag = re.sub(r"[<>]", "", str(raw)).strip().lower()
        if not tag or len(tag) > max_each or tag in seen:
            continue
        add = len(tag) + (1 if out else 0)
        if total + add > max_total:
            continue
        out.append(tag)
        seen.add(tag)
        total += add
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_compose.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_metadata.py tests/test_youtube_metadata_compose.py
git commit -m "feat(prx-publisher): compose YouTube title + tags"
```

---

### Task 7: Compose description (`youtube_metadata.py`)

**Files:**
- Modify: `src/youtube_metadata.py`
- Test: `tests/test_youtube_metadata_description.py`

**Interfaces:**
- Produces: `compose_description(episode: Episode, *, chapters_block: str, keywords: dict, links: dict, max_len: int = 5000) -> str`
  - `links` is a dict with optional keys `transcript`, `show_notes`, `rss` (each a URL string).
  - Layout: chapters block (if any) → PRX prose as plain text (HTML stripped, CTAs preserved) → links section (only links not already present in the prose) → hashtags (`#WonderCabinet #podcast` + first 3 primary keywords). Hard cap `max_len`.

PRX `description` is HTML; convert to plain text (YouTube has no markup): unwrap tags, decode entities, collapse blank runs. Keep URLs (YouTube auto-links them).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_metadata_description.py
from datetime import datetime
from src.feed_parser import Episode
from src.youtube_metadata import compose_description


def _ep(desc):
    return Episode(guid="g", title="T", description=desc, subtitle="",
                   pub_date=datetime(2026, 5, 23), link="", enclosure_url="",
                   enclosure_type="audio/mpeg", duration="", image_url="")


def test_description_layout_and_dedupe():
    ep = _ep("<p>A great chat. Subscribe at https://wondercabinetproductions.com</p>")
    out = compose_description(
        ep,
        chapters_block="0:00 Intro\n3:00 Topic",
        keywords={"primary": ["wonder", "attention", "time", "extra"], "topic_tags": []},
        links={"transcript": "https://docs.google.com/d/abc",
               "show_notes": "https://wondercabinetproductions.com",  # already in prose
               "rss": "https://publicfeeds.net/f/120/wondercabinet"},
    )
    # chapters first
    assert out.startswith("0:00 Intro\n3:00 Topic")
    # prose plain-text, CTA preserved
    assert "A great chat." in out and "<p>" not in out
    # transcript + rss linked; show_notes NOT duplicated (already in prose)
    assert "https://docs.google.com/d/abc" in out
    assert out.count("https://wondercabinetproductions.com") == 1
    # hashtags: show + podcast + first 3 primary only
    assert "#WonderCabinet" in out and "#podcast" in out
    assert "#extra" not in out


def test_description_caps_at_5000():
    ep = _ep("<p>" + "x" * 6000 + "</p>")
    out = compose_description(ep, chapters_block="", keywords={"primary": [], "topic_tags": []}, links={})
    assert len(out) <= 5000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_description.py -v`
Expected: FAIL — `compose_description` undefined.

- [ ] **Step 3: Write minimal implementation**

Append to `src/youtube_metadata.py` (add `import html` at top):

```python
import html as _html


def _html_to_text(s: str) -> str:
    s = re.sub(r"(?i)<\s*br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</\s*p\s*>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def compose_description(
    episode: Episode,
    *,
    chapters_block: str,
    keywords: dict,
    links: dict,
    max_len: int = 5000,
) -> str:
    prose = _html_to_text(episode.description or "")
    parts: list[str] = []
    if chapters_block.strip():
        parts.append(chapters_block.strip())
    if prose:
        parts.append(prose)

    link_lines = []
    for label, key in (("Transcript", "transcript"), ("Show notes", "show_notes"), ("Podcast feed", "rss")):
        url = links.get(key)
        if url and url not in prose:
            link_lines.append(f"{label}: {url}")
    if link_lines:
        parts.append("\n".join(link_lines))

    tags = ["#WonderCabinet", "#podcast"] + [
        "#" + re.sub(r"\s+", "", k) for k in keywords.get("primary", [])[:3]
    ]
    parts.append(" ".join(tags))

    out = "\n\n".join(parts)
    return out[:max_len]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_metadata_description.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_metadata.py tests/test_youtube_metadata_description.py
git commit -m "feat(prx-publisher): compose YouTube description (chapters-top, CTAs kept, deduped links)"
```

---

### Task 8: YouTube API client — video insert (`youtube_client.py`)

**Files:**
- Create: `src/youtube_client.py`
- Test: `tests/test_youtube_client.py`

**Interfaces:**
- Produces: `class YouTubeClient` with `__init__(self, service)` (inject the discovery service for testability) and `insert_video(self, *, video_path, title, description, tags, category_id, privacy_status, made_for_kids=False) -> str` (returns video id).
- Produces: classmethod `YouTubeClient.from_credentials(credentials) -> "YouTubeClient"` building the real `youtube` v3 service.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_client.py
from unittest.mock import MagicMock
from pathlib import Path
from src.youtube_client import YouTubeClient


def test_insert_video_sets_made_for_kids_false_and_returns_id(tmp_path):
    video = tmp_path / "ep.mp4"
    video.write_bytes(b"\x00\x01")
    service = MagicMock()
    insert = service.videos.return_value.insert
    insert.return_value.next_chunk.side_effect = [(None, {"id": "VID123"})]

    client = YouTubeClient(service)
    vid = client.insert_video(
        video_path=video, title="T", description="D", tags=["a"],
        category_id="27", privacy_status="private",
    )

    assert vid == "VID123"
    body = insert.call_args.kwargs["body"]
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert body["status"]["privacyStatus"] == "private"
    assert body["snippet"]["categoryId"] == "27"
    assert "snippet,status" in insert.call_args.kwargs["part"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_client.py -v`
Expected: FAIL — module/class undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/youtube_client.py
"""Thin wrapper over the YouTube Data API v3 (videos, thumbnails, captions, playlists)."""
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class YouTubeClient:
    def __init__(self, service):
        self.service = service

    @classmethod
    def from_credentials(cls, credentials) -> "YouTubeClient":
        return cls(build("youtube", "v3", credentials=credentials))

    def insert_video(self, *, video_path: Path, title: str, description: str,
                     tags: list[str], category_id: str, privacy_status: str,
                     made_for_kids: bool = False) -> str:
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
        request = self.service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _status, response = request.next_chunk()
        return response["id"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_client.py tests/test_youtube_client.py
git commit -m "feat(prx-publisher): YouTube client video insert (madeForKids:false)"
```

---

### Task 9: YouTube API client — thumbnail, captions, playlist (`youtube_client.py`)

**Files:**
- Modify: `src/youtube_client.py`
- Test: `tests/test_youtube_client_enrich.py`

**Interfaces:**
- Produces (methods on `YouTubeClient`):
  - `set_thumbnail(self, video_id: str, thumbnail_path: Path) -> None`
  - `insert_captions(self, video_id: str, srt_path: Path, language: str = "en", name: str = "English") -> str` (returns caption id)
  - `add_to_playlist(self, video_id: str, playlist_id: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_client_enrich.py
from unittest.mock import MagicMock
from src.youtube_client import YouTubeClient


def test_insert_captions_passes_language_and_returns_id(tmp_path):
    srt = tmp_path / "captions.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
    service = MagicMock()
    service.captions.return_value.insert.return_value.execute.return_value = {"id": "CAP1"}

    cid = YouTubeClient(service).insert_captions("VID", srt, language="en", name="English")

    assert cid == "CAP1"
    body = service.captions.return_value.insert.call_args.kwargs["body"]
    assert body["snippet"]["videoId"] == "VID"
    assert body["snippet"]["language"] == "en"
    assert body["snippet"]["name"] == "English"


def test_add_to_playlist_builds_correct_body():
    service = MagicMock()
    YouTubeClient(service).add_to_playlist("VID", "PL123")
    body = service.playlistItems.return_value.insert.call_args.kwargs["body"]
    assert body["snippet"]["playlistId"] == "PL123"
    assert body["snippet"]["resourceId"]["videoId"] == "VID"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_client_enrich.py -v`
Expected: FAIL — methods undefined.

- [ ] **Step 3: Write minimal implementation**

Add `from googleapiclient.http import MediaFileUpload` is already imported. Append methods to `YouTubeClient`:

```python
    def set_thumbnail(self, video_id: str, thumbnail_path: Path) -> None:
        media = MediaFileUpload(str(thumbnail_path))
        self.service.thumbnails().set(videoId=video_id, media_body=media).execute()

    def insert_captions(self, video_id: str, srt_path: Path,
                        language: str = "en", name: str = "English") -> str:
        media = MediaFileUpload(str(srt_path), mimetype="application/octet-stream")
        body = {"snippet": {"videoId": video_id, "language": language, "name": name}}
        resp = self.service.captions().insert(part="snippet", body=body, media_body=media).execute()
        return resp["id"]

    def add_to_playlist(self, video_id: str, playlist_id: str) -> None:
        body = {"snippet": {"playlistId": playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        self.service.playlistItems().insert(part="snippet", body=body).execute()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_client_enrich.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_client.py tests/test_youtube_client_enrich.py
git commit -m "feat(prx-publisher): YouTube client thumbnail/captions/playlist"
```

---

### Task 10: Manifest persist-then-enrich helpers (`youtube_export.py` — manifest layer)

**Files:**
- Create: `src/youtube_export.py` (manifest helpers this task)
- Test: `tests/test_youtube_export_manifest.py`

**Interfaces:**
- Produces:
  - `load_manifest(episode_dir: Path) -> dict`
  - `save_manifest(episode_dir: Path, manifest: dict) -> None` (pretty JSON + trailing newline)
  - `record_video(manifest: dict, *, video_id: str, url: str, privacy: str, title: str) -> None` (writes `manifest["youtube"]` with `thumbnail="pending"`, `captions="pending"`, `playlist="pending"`)
  - `set_enrich_status(manifest: dict, key: str, status: str) -> None` (key in `{thumbnail,captions,playlist}`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_export_manifest.py
import json
from src.youtube_export import load_manifest, save_manifest, record_video, set_enrich_status


def test_record_video_then_enrich(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"slug": "WC_S01_11", "guestName": "X"}))
    m = load_manifest(tmp_path)
    record_video(m, video_id="VID", url="https://yt/VID", privacy="private", title="T")
    assert m["youtube"]["videoId"] == "VID"
    assert m["youtube"]["thumbnail"] == "pending"
    set_enrich_status(m, "thumbnail", "ok")
    save_manifest(tmp_path, m)
    reloaded = load_manifest(tmp_path)
    assert reloaded["youtube"]["thumbnail"] == "ok"
    assert reloaded["guestName"] == "X"  # preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_export_manifest.py -v`
Expected: FAIL — functions undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/youtube_export.py
"""CLI orchestrator: export a rendered episode to YouTube with rich metadata."""
import json
from pathlib import Path

_ENRICH_KEYS = {"thumbnail", "captions", "playlist"}


def load_manifest(episode_dir: Path) -> dict:
    return json.loads((Path(episode_dir) / "manifest.json").read_text())


def save_manifest(episode_dir: Path, manifest: dict) -> None:
    p = Path(episode_dir) / "manifest.json"
    p.write_text(json.dumps(manifest, indent=2) + "\n")


def record_video(manifest: dict, *, video_id: str, url: str, privacy: str, title: str) -> None:
    yt = manifest.setdefault("youtube", {})
    yt.update({
        "videoId": video_id, "url": url, "privacyStatus": privacy, "title": title,
        "thumbnail": "pending", "captions": "pending", "playlist": "pending",
    })


def set_enrich_status(manifest: dict, key: str, status: str) -> None:
    if key not in _ENRICH_KEYS:
        raise ValueError(f"unknown enrich key: {key}")
    manifest.setdefault("youtube", {})[key] = status
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_export_manifest.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_export.py tests/test_youtube_export_manifest.py
git commit -m "feat(prx-publisher): manifest persist-then-enrich helpers"
```

---

### Task 11: MP4 resolution + dry-run plan (`youtube_export.py`)

**Files:**
- Modify: `src/youtube_export.py`
- Test: `tests/test_youtube_export_mp4.py`

**Interfaces:**
- Produces: `find_episode_mp4(episode_dir: Path, ep_num: int | None) -> Path | None`
  - Priority: `audiogram/*_youtube.mp4` → `audiogram/EP{n}_*.mp4` → `audiogram/E{n}[-_]*.mp4` → any `.mp4` >100 MB not matching `test|smoke|sample`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_export_mp4.py
from src.youtube_export import find_episode_mp4


def test_find_prefers_ep_number(tmp_path):
    ag = tmp_path / "audiogram"; ag.mkdir()
    (ag / "EP11_Caroline-Winterer_2026-04-24.mp4").write_bytes(b"x")
    (ag / "WC_S01_11_Henderson_smoke.mp4").write_bytes(b"x")
    found = find_episode_mp4(tmp_path, 11)
    assert found.name == "EP11_Caroline-Winterer_2026-04-24.mp4"


def test_find_skips_smoke_and_missing(tmp_path):
    ag = tmp_path / "audiogram"; ag.mkdir()
    (ag / "WC_S01_12_Henderson_smoke.mp4").write_bytes(b"x")  # excluded
    assert find_episode_mp4(tmp_path, 12) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_export_mp4.py -v`
Expected: FAIL — `find_episode_mp4` undefined.

- [ ] **Step 3: Write minimal implementation**

Append to `src/youtube_export.py` (add `import re` at top):

```python
def find_episode_mp4(episode_dir: Path, ep_num):
    ag = Path(episode_dir) / "audiogram"
    if not ag.is_dir():
        return None
    mp4s = [p for p in ag.iterdir() if p.suffix.lower() == ".mp4"]
    for p in mp4s:
        if re.search(r"_youtube\.mp4$", p.name, re.I):
            return p
    if ep_num:
        for p in mp4s:
            if re.match(rf"EP{ep_num}[_-]", p.name, re.I):
                return p
        for p in mp4s:
            if re.match(rf"E{ep_num}[_-]", p.name, re.I):
                return p
    for p in mp4s:
        if re.search(r"test|smoke|sample", p.name, re.I):
            continue
        if p.stat().st_size > 100 * 1024 * 1024:
            return p
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_export_mp4.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youtube_export.py tests/test_youtube_export_mp4.py
git commit -m "feat(prx-publisher): episode MP4 resolution (ports TS findEpisodeMp4)"
```

---

### Task 12: Orchestrator wiring + CLI (`youtube_export.py`)

**Files:**
- Modify: `src/youtube_export.py` (add `build_plan`, `run`, `main`)
- Test: `tests/test_youtube_export_run.py`

**Interfaces:**
- Consumes: everything above — `youtube_auth.load_credentials`, `youtube_metadata.*`, `youtube_thumbnail.generate_youtube_thumbnail`, `youtube_client.YouTubeClient`, manifest helpers, `find_episode_mp4`.
- Produces:
  - `build_plan(episode_dir: Path, *, suite_root: Path, feed_episodes: list, privacy: str | None, title_override: str | None) -> dict` — pure assembly returning `{title, description, tags, privacy, category_id, playlist_id, mp4_path, thumbnail_path, captions_path, prx_guid}`. No network/upload.
  - `run(episode_dir, *, client, suite_root, feed_episodes, privacy=None, title_override=None, dry_run=False) -> dict` — builds plan; if not dry_run, uploads + enriches with persist-then-enrich, writing the manifest after `insert_video` and after each enrich step.
  - `main(argv=None) -> int` — argparse (`episode_dir`, `--privacy`, `--title`, `--dry-run`), loads token+config+feed, constructs the client, calls `run`.

Test `build_plan` and `run` with a fake client + local sample feed; do not exercise `main`'s network path in unit tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_youtube_export_run.py
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from src.feed_parser import Episode
from src import youtube_export as yx


def _episode_dir(tmp_path) -> Path:
    d = tmp_path / "WC_S01_11_Caroline_Winterer"; (d / "audiogram").mkdir(parents=True)
    big = b"0" * (101 * 1024 * 1024)
    (d / "audiogram" / "EP11_Caroline-Winterer.mp4").write_bytes(big)
    (d / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
    (d / "keywords.md").write_text("## Primary Keywords\n- wonder\n\n## Topic Tags\nhistory\n")
    (d / "chapters.md").write_text("## YouTube Description Format\n0:00 Intro\n")
    from PIL import Image
    (d / "images").mkdir()
    Image.new("RGB", (1000, 1000), (200, 50, 50)).save(d / "images" / "WC_S01_11.jpg")
    (d / "manifest.json").write_text(json.dumps({
        "slug": "WC_S01_11_Caroline_Winterer", "guestName": "Caroline Winterer",
        "episodeNumber": 11, "ghost": {"publishedAt": "2026-04-25T10:00:08.000Z"},
    }))
    return d


def _feed():
    return [Episode(guid="g2", title="Caroline Winterer: Deep Time",
                    description="<p>Great chat.</p>", subtitle="",
                    pub_date=datetime(2026, 4, 25), link="", enclosure_url="",
                    enclosure_type="audio/mpeg", duration="", image_url="")]


def test_build_plan_assembles_metadata(tmp_path):
    d = _episode_dir(tmp_path)
    plan = yx.build_plan(d, suite_root=tmp_path, feed_episodes=_feed(),
                         privacy="private", title_override=None)
    assert plan["title"] == "Caroline Winterer: Deep Time"
    assert plan["description"].startswith("0:00 Intro")
    assert "Great chat." in plan["description"]
    assert "wonder" in plan["tags"]
    assert plan["mp4_path"].name == "EP11_Caroline-Winterer.mp4"
    assert plan["prx_guid"] == "g2"


def test_run_persists_then_enriches(tmp_path):
    d = _episode_dir(tmp_path)
    client = MagicMock()
    client.insert_video.return_value = "VID123"
    client.insert_captions.return_value = "CAP1"

    result = yx.run(d, client=client, suite_root=tmp_path, feed_episodes=_feed(),
                    privacy="private")

    assert result["youtube"]["videoId"] == "VID123"
    assert result["youtube"]["thumbnail"] == "ok"
    assert result["youtube"]["captions"] == "ok"
    assert result["prx"]["guid"] == "g2"
    # manifest written to disk with the video id
    saved = json.loads((d / "manifest.json").read_text())
    assert saved["youtube"]["videoId"] == "VID123"


def test_run_records_video_even_if_thumbnail_fails(tmp_path):
    d = _episode_dir(tmp_path)
    client = MagicMock()
    client.insert_video.return_value = "VID123"
    client.set_thumbnail.side_effect = RuntimeError("Media too large")

    result = yx.run(d, client=client, suite_root=tmp_path, feed_episodes=_feed(),
                    privacy="private")

    assert result["youtube"]["videoId"] == "VID123"      # recorded despite failure
    assert result["youtube"]["thumbnail"] == "failed"
    saved = json.loads((d / "manifest.json").read_text())
    assert saved["youtube"]["videoId"] == "VID123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/test_youtube_export_run.py -v`
Expected: FAIL — `build_plan` / `run` undefined.

- [ ] **Step 3: Write minimal implementation**

Append to `src/youtube_export.py` (add imports at top: `import argparse`, `import os`, `from datetime import datetime`, and the sibling modules):

```python
from . import youtube_metadata as ytm
from .youtube_thumbnail import generate_youtube_thumbnail
from .youtube_client import YouTubeClient
from .youtube_auth import load_credentials


def _load_show_config(suite_root: Path, slug: str) -> dict:
    p = Path(suite_root) / "shows" / slug / "config.json"
    return json.loads(p.read_text())


def _parse_published_at(manifest: dict):
    raw = (manifest.get("ghost") or {}).get("publishedAt")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def build_plan(episode_dir: Path, *, suite_root: Path, feed_episodes: list,
               privacy: str | None, title_override: str | None) -> dict:
    episode_dir = Path(episode_dir)
    manifest = load_manifest(episode_dir)
    show_slug = manifest.get("show", "wonder-cabinet")
    cfg = _load_show_config(suite_root, show_slug)
    yt_cfg = cfg.get("youtube", {})

    episode = ytm.resolve_prx_episode(
        feed_episodes, guest_name=manifest.get("guestName", ""),
        published_at=_parse_published_at(manifest),
    )
    keywords = ytm.parse_keywords(episode_dir / "keywords.md")
    chapters_block = ytm.parse_chapters_youtube(episode_dir / "chapters.md")

    transcript_id = (manifest.get("google_drive") or {}).get("formatted_transcript_file_id")
    links = {
        "transcript": f"https://docs.google.com/document/d/{transcript_id}/view" if transcript_id else None,
        "show_notes": (manifest.get("ghost") or {}).get("url"),
        "rss": (cfg.get("prx") or {}).get("feedUrl"),
    }

    title = ytm.compose_title(episode, override=title_override)
    description = ytm.compose_description(
        episode, chapters_block=chapters_block, keywords=keywords, links=links)
    tags = ytm.compose_tags(keywords, show_name=cfg.get("name", "Wonder Cabinet"))

    images = sorted((episode_dir / "images").glob("WC_S*.jpg")) or \
        sorted((episode_dir / "images").glob("*.jpg"))
    square = images[0] if images else None
    thumb_path = episode_dir / "audiogram" / "youtube-thumbnail.jpg"
    captions = episode_dir / "captions.srt"

    return {
        "title": title, "description": description, "tags": tags,
        "privacy": privacy or yt_cfg.get("defaultPrivacy", "private"),
        "category_id": yt_cfg.get("categoryId", "27"),
        "playlist_id": yt_cfg.get("playlistId"),
        "mp4_path": find_episode_mp4(episode_dir, manifest.get("episodeNumber")),
        "square_art": square, "thumbnail_path": thumb_path,
        "captions_path": captions if captions.is_file() else None,
        "prx_guid": episode.guid,
    }


def run(episode_dir: Path, *, client, suite_root: Path, feed_episodes: list,
        privacy: str | None = None, title_override: str | None = None,
        dry_run: bool = False) -> dict:
    episode_dir = Path(episode_dir)
    plan = build_plan(episode_dir, suite_root=suite_root, feed_episodes=feed_episodes,
                      privacy=privacy, title_override=title_override)
    manifest = load_manifest(episode_dir)
    manifest.setdefault("prx", {})["guid"] = plan["prx_guid"]

    if dry_run:
        manifest["_plan_preview"] = {k: str(v) for k, v in plan.items()}
        return manifest
    if not plan["mp4_path"]:
        raise FileNotFoundError(f"No rendered MP4 in {episode_dir}/audiogram/")

    # 1. upload + persist immediately
    video_id = client.insert_video(
        video_path=plan["mp4_path"], title=plan["title"], description=plan["description"],
        tags=plan["tags"], category_id=plan["category_id"], privacy_status=plan["privacy"],
        made_for_kids=False)
    url = f"https://www.youtube.com/watch?v={video_id}"
    record_video(manifest, video_id=video_id, url=url, privacy=plan["privacy"], title=plan["title"])
    save_manifest(episode_dir, manifest)

    # 2. best-effort enrichment
    if plan["square_art"]:
        try:
            generate_youtube_thumbnail(plan["square_art"], plan["thumbnail_path"])
            client.set_thumbnail(video_id, plan["thumbnail_path"])
            set_enrich_status(manifest, "thumbnail", "ok")
        except Exception:
            set_enrich_status(manifest, "thumbnail", "failed")
        save_manifest(episode_dir, manifest)

    if plan["captions_path"]:
        try:
            client.insert_captions(video_id, plan["captions_path"])
            set_enrich_status(manifest, "captions", "ok")
        except Exception:
            set_enrich_status(manifest, "captions", "failed")
        save_manifest(episode_dir, manifest)

    if plan["playlist_id"]:
        try:
            client.add_to_playlist(video_id, plan["playlist_id"])
            set_enrich_status(manifest, "playlist", "ok")
        except Exception:
            set_enrich_status(manifest, "playlist", "failed")
        save_manifest(episode_dir, manifest)

    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="youtube-export",
                                     description="Export a rendered episode to YouTube.")
    parser.add_argument("episode_dir")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"])
    parser.add_argument("--title")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    episode_dir = Path(args.episode_dir).resolve()
    suite_root = Path(__file__).resolve().parent.parent.parent.parent
    manifest = load_manifest(episode_dir)
    cfg = _load_show_config(suite_root, manifest.get("show", "wonder-cabinet"))
    feed_url = cfg["prx"]["feedUrl"]

    from .feed_parser import get_episodes
    feed_episodes = get_episodes(feed_url)

    client = None
    if not args.dry_run:
        token_path = suite_root / "modules" / "audiogram-tools" / ".youtube-token.json"
        creds = load_credentials(token_path, os.environ["YOUTUBE_CLIENT_ID"],
                                 os.environ["YOUTUBE_CLIENT_SECRET"])
        client = YouTubeClient.from_credentials(creds)

    result = run(episode_dir, client=client, suite_root=suite_root,
                 feed_episodes=feed_episodes, privacy=args.privacy,
                 title_override=args.title, dry_run=args.dry_run)
    yt = result.get("youtube", {})
    print(json.dumps(yt or result.get("_plan_preview", {}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full suite**

Run: `cd modules/prx-to-ghost-publisher && python -m pytest tests/ -v`
Expected: PASS (all youtube_* tests green; existing tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/youtube_export.py tests/test_youtube_export_run.py
git commit -m "feat(prx-publisher): YouTube export orchestrator (build_plan/run/main, persist-then-enrich)"
```

---

### Task 13: Live dry-run validation + skill wiring + TS retirement

**Files:**
- Modify: the `/wc-youtube-export` skill definition (confirm path: `.claude/commands/wc-youtube-export.md` or `~/.claude/skills/wc-youtube-export/`) — point its export step at `python -m src.youtube_export <episode-dir>`.
- Modify: `shows/wonder-cabinet/config.json` only if `prx.feedUrl` is absent (the resolver needs it; Wonder Cabinet feed = `https://publicfeeds.net/f/120/wondercabinet`).
- Delete (after parity confirmed): `modules/audiogram-tools/src/automation/{youtube-metadata.ts,youtube-upload.ts,wc-export-and-upload.ts,youtube-backfill.ts}`.

- [ ] **Step 1: Live dry-run against a real episode**

Run:
```bash
cd modules/prx-to-ghost-publisher
python -m src.youtube_export ../../shows/wonder-cabinet/episodes/WC_S01_15_D._Graham_Burnett --dry-run
```
Expected: prints an assembled plan — title from PRX, description starting with the chapter block, tag list, resolved MP4 path, `prx_guid`. No upload. Confirm the PRX match is the Burnett episode.

- [ ] **Step 2: Confirm `prx.feedUrl` exists in show config**

Run: `python -c "import json; print(json.load(open('../../shows/wonder-cabinet/config.json')).get('prx',{}).get('feedUrl'))"`
Expected: prints the feed URL. If `None`, add `"feedUrl": "https://publicfeeds.net/f/120/wondercabinet"` under the `prx` block and re-run Step 1.

- [ ] **Step 3: Live enrich the existing EP11 draft (real API, in place)**

EP11 already has `youtube.videoId = idFXdDLbENk` (thumbnail/captions still absent). Verify the new code enriches in place rather than re-uploading: temporarily clear only the enrich markers and run a real (non-dry) export. Because `insert_video` would create a *new* video, instead validate the enrich primitives directly:
```bash
python - <<'PY'
import os
from pathlib import Path
from src.youtube_auth import load_credentials
from src.youtube_client import YouTubeClient
from src.youtube_thumbnail import generate_youtube_thumbnail
root = Path(__file__).resolve().parent
sq = next((root.parent.parent / "shows/wonder-cabinet/episodes/WC_S01_11_Caroline_Winterer/images").glob("WC_S*.jpg"))
thumb = generate_youtube_thumbnail(sq, root / "out-thumb.jpg")
creds = load_credentials(root.parent / "audiogram-tools/.youtube-token.json",
                         os.environ["YOUTUBE_CLIENT_ID"], os.environ["YOUTUBE_CLIENT_SECRET"])
c = YouTubeClient.from_credentials(creds)
c.set_thumbnail("idFXdDLbENk", thumb)
c.insert_captions("idFXdDLbENk", root.parent.parent / "shows/wonder-cabinet/episodes/WC_S01_11_Caroline_Winterer/captions.srt")
print("enriched idFXdDLbENk: thumbnail + captions")
PY
```
Expected: no error; YouTube Studio shows the 16:9 thumbnail + an English caption track on the EP11 draft. (This both validates the API path and finishes the orphaned smoke-test video.)

- [ ] **Step 4: Point the skill at the Python entry point**

Edit the `/wc-youtube-export` skill so its post-render step invokes
`python -m src.youtube_export <episode-dir> --privacy=private` (from the publisher module),
replacing the `npx tsx .../wc-export-and-upload.ts` call. Keep the render step (TS) unchanged.

- [ ] **Step 5: Retire the TypeScript uploader + commit**

```bash
git rm modules/audiogram-tools/src/automation/youtube-metadata.ts \
       modules/audiogram-tools/src/automation/youtube-upload.ts \
       modules/audiogram-tools/src/automation/wc-export-and-upload.ts \
       modules/audiogram-tools/src/automation/youtube-backfill.ts
# (run inside the audiogram-tools submodule; commit there, then bump the pointer)
git add -A
git commit -m "feat: switch /wc-youtube-export to the Python publisher; retire TS uploader"
```
Note: `youtube-auth-only.ts` may stay as the one TS auth helper, or be ported later — out of scope here.

---

## Self-Review

**Spec coverage:**
- PRX-sourced title/description → Tasks 5–7 ✓
- Keep CTAs + chapters on top → Task 7 (chapters first, prose CTAs preserved) ✓
- 1280×720 logo-only thumbnail, <2 MiB → Task 3 ✓
- Captions/transcript via `captions.insert` → Task 9 + wired in Task 12 ✓
- `madeForKids: false` → Task 8 ✓
- Consolidate into Python inside prx-to-ghost-publisher → all tasks ✓
- Persist-then-enrich error handling → Tasks 10 + 12 (`test_run_records_video_even_if_thumbnail_fails`) ✓
- Token portability (Node JSON → google-auth) → Task 2 ✓
- PRX episode matching + cache `prx.guid` → Tasks 5, 12 ✓
- Description de-dup → Task 7 (`test_description_layout_and_dedupe`) ✓
- Skill wiring + TS retirement → Task 13 ✓
- Enrich the orphaned EP11 draft in place → Task 13 Step 3 ✓

**Open item deferred to execution:** confirm the exact `/wc-youtube-export` skill file path (Task 13 Step 4) and whether `prx.feedUrl` is present in the show config (Task 13 Step 2 handles both branches).

**Type consistency:** `YouTubeClient` methods (`insert_video`, `set_thumbnail`, `insert_captions`, `add_to_playlist`) are defined in Tasks 8–9 and consumed with identical signatures in Task 12. `parse_keywords` returns `{"primary","topic_tags"}` (Task 4), consumed as such in Tasks 6–7, 12. `resolve_prx_episode(episodes, guest_name, published_at)` (Task 5) is called with those exact args in Task 12.
