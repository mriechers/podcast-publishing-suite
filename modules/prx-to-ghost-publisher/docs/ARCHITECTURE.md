# PRX-to-Ghost Publisher Architecture

## Overview

A Python-based automation tool that fetches TTBOOK episodes from the PRX/Dovetail RSS feed and publishes them as posts to a Ghost CMS instance.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   PRX/Dovetail  │────▶│   Publisher      │────▶│   Ghost CMS     │
│   RSS Feed      │     │   (Python)       │     │   Admin API     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  State Tracker   │
                        │  (SQLite/JSON)   │
                        └──────────────────┘
```

## Data Flow

### 1. Fetch Phase
- Retrieve RSS feed from `https://feeds.ttbook.org/ttbook`
- Parse XML using Python's `xml.etree.ElementTree` or `feedparser`
- Extract episode metadata (see Field Mapping below)

### 2. Transform Phase
- Convert RSS item fields to Ghost post structure
- Generate HTML content with embedded audio player
- Map categories to Ghost tags
- Download episode artwork, upload to Ghost, and generate OG images

### 3. Publish Phase
- Authenticate with Ghost Admin API (JWT)
- Check state tracker for already-published episodes
- Create new posts via `POST /ghost/api/admin/posts/`
- Update state tracker with published GUIDs

### 4. State Tracking
- Track published episodes by GUID to prevent duplicates
- Store Ghost post IDs for potential updates
- Log publish timestamps for auditing

---

## Field Mapping: PRX RSS → Ghost Post

| PRX RSS Element | Ghost Post Field | Notes |
|-----------------|------------------|-------|
| `<title>` | `title` | Episode title |
| `<guid>` | Custom field / slug source | e.g., `prx_120_f49f790d-...` |
| `<pubDate>` | `published_at` | Parse RFC 2822 date |
| `<link>` | `canonical_url` | ttbook.org episode page |
| `<content:encoded>` | `html` (partial) | Rich HTML description |
| `<itunes:image href>` | `feature_image` | Downloaded, uploaded to Ghost (falls back to PRX URL) |
| *(generated)* | `og_image` | 1200x630 OG image composited from artwork + background |
| *(generated)* | `twitter_image` | Same as `og_image` |
| `<itunes:subtitle>` | `custom_excerpt` | Short description |
| `<itunes:duration>` | Embedded in HTML | e.g., "52:02" |
| `<enclosure url>` | Embedded audio player | Audio file URL |
| `<category>` elements | `tags` | Map to Ghost tags |
| `<itunes:episodeType>` | `tags` | "full", "trailer", "bonus" |

### Generated Content Structure

```html
<!-- Ghost Post HTML -->
<div class="episode-player">
  <audio controls preload="metadata">
    <source src="{enclosure_url}" type="audio/mpeg">
  </audio>
  <p class="episode-duration">Duration: {itunes:duration}</p>
</div>

<div class="episode-content">
  {content:encoded}
</div>

<div class="episode-meta">
  <p><a href="{link}">Listen on TTBOOK.org</a></p>
</div>
```

---

## Ghost API Integration

### Authentication

Using JWT token authentication (not the JS client - pure Python):

```python
import jwt
from datetime import datetime, timezone

def generate_ghost_token(api_key: str) -> str:
    """Generate JWT for Ghost Admin API."""
    key_id, secret = api_key.split(':')

    iat = int(datetime.now(timezone.utc).timestamp())

    header = {'alg': 'HS256', 'typ': 'JWT', 'kid': key_id}
    payload = {
        'iat': iat,
        'exp': iat + 5 * 60,  # 5 minutes
        'aud': '/admin/'
    }

    token = jwt.encode(
        payload,
        bytes.fromhex(secret),
        algorithm='HS256',
        headers=header
    )
    return token
```

### Creating Posts

```python
POST /ghost/api/admin/posts/
Headers:
  Authorization: Ghost {jwt_token}
  Content-Type: application/json
  Accept-Version: v5.0

Body:
{
  "posts": [{
    "title": "Episode Title",
    "html": "<div>...</div>",
    "status": "published",  # or "draft" for review
    "published_at": "2025-09-13T11:00:00.000Z",
    "feature_image": "https://f.prxu.org/.../image.png",
    "custom_excerpt": "Short description...",
    "canonical_url": "https://www.ttbook.org/show/episode-slug",
    "tags": [
      {"name": "TTBOOK"},
      {"name": "Philosophy"},
      {"name": "Category Name"}
    ]
  }]
}
```

---

## Configuration

### Environment Variables

```bash
# .env (not committed)
GHOST_URL=http://192.168.5.156:2368
GHOST_ADMIN_API_KEY=abc123:def456...
PRX_FEED_URL=https://feeds.ttbook.org/ttbook

# Optional
PUBLISH_STATUS=draft  # "draft" or "published"
DRY_RUN=false
```

### Config File

```json
// config.json
{
  "feed_url": "https://feeds.ttbook.org/ttbook",
  "ghost": {
    "url": "http://192.168.5.156:2368",
    "api_version": "v5.0"
  },
  "defaults": {
    "status": "draft",
    "author": "Wisconsin Public Radio",
    "primary_tag": "TTBOOK"
  },
  "state_file": "data/published_episodes.json"
}
```

---

## State Tracking

### SQLite Schema (Recommended)

```sql
CREATE TABLE published_episodes (
    guid TEXT PRIMARY KEY,           -- PRX GUID
    ghost_post_id TEXT,              -- Ghost post UUID
    title TEXT,
    published_at TIMESTAMP,
    ghost_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'published'  -- 'published', 'draft', 'failed'
);

CREATE INDEX idx_published_at ON published_episodes(published_at);
```

### JSON Alternative (Simpler)

```json
// data/published_episodes.json
{
  "prx_120_f49f790d-b51d-4fab-8201-53f67d7f09b2": {
    "ghost_post_id": "6789abc...",
    "title": "Giving Up",
    "published_at": "2025-09-13T11:00:00Z",
    "synced_at": "2025-09-14T10:30:00Z"
  }
}
```

---

## Project Structure

```
prx-to-ghost-publisher/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── feed_parser.py       # RSS feed fetching/parsing
│   ├── ghost_client.py      # Ghost Admin API client
│   ├── content_builder.py   # HTML generation for posts
│   ├── og_image.py          # OG image download + generation
│   ├── state_tracker.py     # Duplicate prevention
│   └── config.py            # Configuration management
├── data/
│   └── published_episodes.db  # State tracking (SQLite)
├── tests/
│   ├── test_feed_parser.py
│   ├── test_ghost_client.py
│   └── fixtures/
│       └── sample_feed.xml
├── scripts/
│   └── (existing scripts...)
├── knowledge/
│   └── ghost/               # Ghost API docs (existing)
├── images/
│   └── og-left-logo.png       # OG image background with Wonder Cabinet branding (1200x630)
├── sample-data/
│   └── prx-sample-feed.xml  # Test data (existing)
├── .env.example
├── config.json
├── pyproject.toml           # Dependencies
└── README.md
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "prx-to-ghost-publisher"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "pyjwt>=2.8.0",      # JWT token generation
    "requests>=2.31.0",  # HTTP client
    "feedparser>=6.0.0", # RSS parsing (optional, can use stdlib)
    "python-dotenv>=1.0.0",  # Environment config
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-vcr>=1.0.0",  # Record/replay HTTP for tests
]
```

---

## CLI Usage

```bash
# Sync new episodes (default: create as drafts)
python -m src.main sync

# Sync and publish immediately
python -m src.main sync --status published

# Dry run (fetch + transform, no publish)
python -m src.main sync --dry-run

# Sync specific episode by GUID
python -m src.main sync --guid "prx_120_f49f790d-..."

# List tracked episodes
python -m src.main list

# Force re-sync an episode (update existing post)
python -m src.main resync --guid "prx_120_f49f790d-..."
```

---

## Development Workflow

### Phase 1: Core Infrastructure
1. Set up project structure with `pyproject.toml`
2. Implement `feed_parser.py` using sample XML
3. Implement `ghost_client.py` with JWT auth
4. Create basic state tracker (JSON first, SQLite later)

### Phase 2: Content Pipeline
5. Implement `content_builder.py` for HTML generation
6. Add tag mapping logic
7. Handle featured image URLs

### Phase 3: CLI & Polish
8. Build CLI with argparse
9. Add dry-run mode
10. Add logging and error handling

### Phase 4: Testing
11. Unit tests with sample feed data
12. Integration tests against local Ghost instance
13. VCR fixtures for reproducible API tests

---

## Ghost Dev Instance

**URL:** `http://192.168.5.156:2368`
**Location:** `/Users/markriechers/Developer/ghost-dev/`
**Version:** Ghost 6.10.3
**Database:** SQLite (`content/data/ghost-local.db`)

### Getting Admin API Key

1. Open Ghost Admin: `http://192.168.5.156:2368/ghost`
2. Go to Settings → Integrations
3. Create new Custom Integration: "PRX Publisher"
4. Copy the Admin API Key

---

## Error Handling

| Error | Handling |
|-------|----------|
| Feed fetch fails (403/timeout) | Retry with backoff, log error |
| Episode already published | Skip (check state tracker) |
| Ghost API auth fails | Re-generate JWT, check key validity |
| Ghost API rate limit | Respect `Retry-After` header |
| Image URL unreachable | Log warning, publish without image |
| Malformed episode data | Log + skip, continue with others |

---

## Transcript Integration

### TTBOOK Cache

For Luminous episodes, transcripts are available from TTBOOK.org. A scraper has captured these to:

```
sample-data/ttbook-cache/luminous/
├── {slug}_transcript.txt      # Transcript text
├── {slug}_episode.json        # Episode metadata
└── ...
```

### Transcript File Format

Transcripts use a simple speaker attribution format:

```
- [Steve Paulson] Welcome to Luminous. Today we're talking with...
- [Melissa Etheridge] Thank you for having me.
- [Steve Paulson] Let's start with...
```

### HTML Conversion

The `format_transcript_html()` function converts this to:

```html
<p><strong>Steve Paulson:</strong> Welcome to Luminous. Today we're talking with...</p>
<p><strong>Melissa Etheridge:</strong> Thank you for having me.</p>
<p><strong>Steve Paulson:</strong> Let's start with...</p>
```

### Transcript Lookup

Transcripts are loaded by episode slug:

```python
def load_transcript(slug: str) -> str | None:
    """Load transcript from TTBOOK cache."""
    cache_dir = Path('sample-data/ttbook-cache/luminous')
    transcript_file = cache_dir / f'{slug}_transcript.txt'
    if transcript_file.exists():
        return transcript_file.read_text()
    return None
```

### Available Transcripts

18 Luminous episodes have cached transcripts:
- `luminous-melissa-etheridge-ayahuasca`
- `luminous-reclaiming-the-acid-queen`
- `luminous-finding-god-in-the-waves`
- And 15 more...

### Integration with Content Builder

When generating Ghost post HTML, the content builder:
1. Checks if a transcript exists for the episode slug
2. Converts the transcript to HTML with speaker formatting
3. Appends the transcript section after episode content

---

## Image Pipeline

### Overview

Episode artwork goes through a three-step pipeline during sync:

```
PRX itunes:image URL
        │
        ▼
  download_image()          → temp file on disk
        │
        ├─► upload_image()  → Ghost /images/upload/ → feature_image URL
        │
        ▼
  generate_og_image()       → 1200×630 JPEG (artwork on background)
        │
        └─► upload_image()  → Ghost /images/upload/ → og_image + twitter_image URL
```

### OG Image Generation

Social platforms (Facebook, Twitter/X, LinkedIn) display shared links as 1.91:1 cards (1200×630px). Podcast artwork is always square, so sharing a post with just the square art results in awkward cropping or tiny thumbnails.

`generate_og_image()` composites the square artwork centered on a 1200×630 background canvas:

- **Background**: Uses `images/og-left-logo.png` by default (Wonder Cabinet branding on the left). Falls back to solid black if the file is missing.
- **Artwork sizing**: Resized to fit the 630px canvas height, right-justified so it sits opposite the branding.
- **Output**: JPEG at 85% quality for a good size/quality balance.

### Customizing the Background

Replace `images/og-swirl.png` with any 1200×630 PNG. The image will be used as-is (resized if dimensions differ). Keep the design dark or muted so episode artwork stays the focal point.

You can also pass a custom path per-call:

```python
generate_og_image(artwork_path, output_path, background_path=Path("images/custom-bg.png"))
```

### Ghost Post Fields

| Ghost Field | Source | Notes |
|-------------|--------|-------|
| `feature_image` | Ghost-hosted square artwork | Falls back to PRX URL if upload fails |
| `og_image` | Ghost-hosted 1200×630 composite | Used for Facebook/LinkedIn cards |
| `twitter_image` | Same as `og_image` | Twitter/X card image |
| `data-episode-artwork` | Ghost-hosted square artwork | Used by the theme's audio player |

### Graceful Degradation

Every step in the pipeline is independently wrapped in try/except:

- Image download fails → use original PRX URL for `feature_image`, no `og_image` set
- Square art upload fails → same fallback
- OG generation fails → square art still uploaded, no `og_image`
- OG upload fails → square art still uploaded, no `og_image`
- Dry run → skip image processing entirely, use PRX URLs as-is

Ghost falls back to `feature_image` for social cards when `og_image` is not set, so the post always has *some* image.

---

## Future Enhancements

1. **Scheduled Sync** - Cron job or systemd timer for hourly/daily sync
2. **Webhook Trigger** - Ghost webhook → re-fetch on demand
3. **PRX Transcript Support** - If PRX adds `<podcast:transcript>` to feed, parse directly
4. **Episode Updates** - Detect RSS changes, update existing Ghost posts
5. **Multi-Feed Support** - Config for multiple PRX feeds → different Ghost sites
6. **Transcript Scraping** - Automated TTBOOK.org scraping for new Luminous episodes

---

## References

- [Ghost Admin API Docs](../knowledge/ghost/admin-api.md)
- [PRX Feed Structure Analysis](../knowledge/prx/PRX_FEED_STRUCTURE_ANALYSIS.md)
- [Sample PRX Feed](../sample-data/prx-sample-feed.xml)
