# Wonder Cabinet Episode Import Process

> **Last Updated**: 2026-02-06
> **Status**: Production-ready with documented enhancements needed

This document captures the complete process for importing Wonder Cabinet episodes from PRX Dovetail to Ghost CMS, including lessons learned and required fixes.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Import Process Steps](#import-process-steps)
4. [Data Flow](#data-flow)
5. [Known Issues & Fixes](#known-issues--fixes)
6. [Ghost Post Structure](#ghost-post-structure)
7. [Automation Enhancements](#automation-enhancements)
8. [Manual Intervention Scenarios](#manual-intervention-scenarios)

---

## Overview

Wonder Cabinet episodes are published via PRX Dovetail and need to be imported to Ghost CMS at `wonder-cabinet.ghost.io` (production) with:

- Ghost-hosted audio (not PRX tracking URLs) to avoid CORS issues
- Waveform peaks JSON for the Wavesurfer audio player
- Proper CSS classes for episode notes styling
- Image alt text and credits from PRX metadata
- Full transcript (from local files or RSS)

### Key Insight: Scheduled vs Published Episodes

| Episode State | `_links.enclosure.href` | `media[]` array |
|---------------|-------------------------|-----------------|
| **Published** | Works (tracking URL) | Works (direct CDN) |
| **Scheduled** | 404 Error | Works (direct CDN) |

**Always use the `media[]` array** for audio downloads to handle both cases.

---

## Prerequisites

### Tools Required

```bash
# Waveform generation
audiowaveform --version  # v1.11.0+ required

# Audio concatenation
ffmpeg -version  # For combining multi-segment episodes

# Python environment
uv --version  # For running the sync script
```

### Environment Configuration

```bash
# .env.prod contains:
GHOST_URL=https://wonder-cabinet.ghost.io
GHOST_ADMIN_API_KEY=<key_id>:<secret>
PRX_CLIENT_ID=<client_id>
PRX_CLIENT_SECRET=<client_secret>
PRX_PODCAST_IDS=120,3329  # Wonder Cabinet, Luminous
```

### Local Files

| Path | Purpose |
|------|---------|
| `transcripts/<episode_number>_<Guest>_formatted.html` | Pre-formatted transcript HTML |
| `data/published_episodes.prod.json` | State tracking (prevents duplicates) |
| `audio/` | Downloaded/concatenated audio files |

---

## Import Process Steps

### Step 1: Check Episode Availability

```bash
# List available episodes from Dovetail API
uv run python3 -m src.main --env prod list --source api
```

### Step 2: Run Sync with Audio Upload

```bash
uv run python3 -m src.main --env prod sync \
    --source api \
    --status draft \
    --upload-audio \
    --guid "prx_120_<episode-uuid>" \
    -y
```

### Step 3: Handle Audio Download Failures

If the sync reports "Download/peaks pipeline failed" with a 404:

1. **Check API for media segments**:
```python
# The media[] array contains direct CDN URLs
media = [
    {"href": "https://f.prxu.org/.../part1.mp3", "fileName": "..."},
    {"href": "https://f.prxu.org/.../midroll.mp3", "fileName": "..."},
    {"href": "https://f.prxu.org/.../part2.mp3", "fileName": "..."},
]
```

2. **Download segments manually**:
```bash
mkdir -p audio/segments && cd audio/segments
curl -L -o "01_part1.mp3" "<segment1_url>"
curl -L -o "02_midroll.mp3" "<segment2_url>"
curl -L -o "03_part2.mp3" "<segment3_url>"
```

3. **Concatenate with ffmpeg**:
```bash
echo "file '01_part1.mp3'" > concat_list.txt
echo "file '02_midroll.mp3'" >> concat_list.txt
echo "file '03_part2.mp3'" >> concat_list.txt
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy ../episode_combined.mp3
```

4. **Generate peaks**:
```bash
audiowaveform -i ../episode_combined.mp3 \
    -o /tmp/peaks/<slug>-peaks.json \
    --output-format json \
    --pixels-per-second 50
```

5. **Upload to Ghost**:
```python
from src.ghost_client import GhostClient
client = GhostClient(base_url=GHOST_URL, api_key=GHOST_ADMIN_API_KEY)

# Upload audio
audio_url = client.upload_media(Path("audio/episode_combined.mp3"))

# Upload peaks
peaks_url = client.upload_file(Path("/tmp/peaks/<slug>-peaks.json"))
```

6. **Update Ghost post** with new URLs (see [Manual Post Updates](#manual-post-updates))

### Step 4: Post-Import Fixes

After initial sync, the following manual fixes may be needed:

| Fix | Reason |
|-----|--------|
| Update `published_at` to import time | Ghost won't save drafts with future dates |
| Add `feature_image_alt` | PRX provides alt text not captured by sync |
| Add `feature_image_caption` | PRX provides image credit |
| Fix episode links CSS class | Links need `wc-episode-notes-content-links` class |

---

## Data Flow

```
PRX Dovetail API
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Episode Data                                                │
│  ├── title, subtitle, description                           │
│  ├── publishedAt (use for JSON-LD, NOT Ghost published_at)  │
│  ├── image.href, image.altText, image.credit                │
│  ├── _links.enclosure (tracking URL - may 404 for scheduled)│
│  └── media[] (direct CDN URLs - always works)               │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Audio Processing                                            │
│  ├── Download segments from media[].href                    │
│  ├── Concatenate: part1 + midroll + part2                   │
│  ├── Generate peaks JSON (audiowaveform, 50 pps)            │
│  └── Upload both to Ghost media/files library               │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Ghost Post                                                  │
│  ├── Audio player HTML card with Ghost-hosted URLs          │
│  ├── Episode description (sanitized, links styled)          │
│  ├── Transcript HTML card                                   │
│  ├── Feature image with alt text and caption                │
│  └── JSON-LD structured data in codeinjection_head          │
└─────────────────────────────────────────────────────────────┘
```

---

## Known Issues & Fixes

### Issue 1: Scheduled Episode Audio 404

**Problem**: `_links.enclosure.href` tracking URL returns 404 for episodes scheduled in the future.

**Root Cause**: Dovetail tracking redirects (Podtrac → mgln.ai → dovetail.prxu.org) aren't active until the episode is publicly released.

**Solution**: Use `media[]` array URLs which point directly to `f.prxu.org` CDN and work regardless of release status.

**Code Location**: `src/waveform_peaks.py:download_and_generate_peaks()`

**Fix Needed**:
```python
# When enclosure URL fails, fall back to media[] segments
if response.status_code == 404:
    # Fetch episode from API to get media[] array
    # Download and concatenate segments
    # Continue with peaks generation
```

---

### Issue 2: Ghost Draft Future Date

**Problem**: Ghost won't save a draft post with `published_at` in the future.

**Root Cause**: Future dates are reserved for `status: scheduled` posts.

**Solution**: Always set `published_at` to import time. Preserve original release date in JSON-LD `datePublished`.

**Code Location**: `src/content_builder.py:build_ghost_post()`

**Fix Needed**:
```python
# Use current time for Ghost published_at
from datetime import datetime, timezone
published_at = datetime.now(timezone.utc).isoformat()

# Original date goes in JSON-LD only
json_ld["datePublished"] = episode.pub_date.isoformat()
```

---

### Issue 3: Missing Image Metadata

**Problem**: PRX provides `altText`, `caption`, and `credit` for episode images, but these aren't captured.

**API Response**:
```json
{
  "image": {
    "href": "https://f.prxu.org/.../image.png",
    "altText": "Description for accessibility",
    "caption": "Optional visible caption",
    "credit": "Photo credit attribution"
  }
}
```

**Ghost Fields**:
- `feature_image_alt` ← `image.altText`
- `feature_image_caption` ← `image.credit` (or combined with caption)

**Code Location**: `src/dovetail_client.py:_parse_api_episode()`

**Fix Needed**:
```python
# Extract image metadata
image_data = data.get("image", {})
image_url = image_data.get("href", "")
image_alt = image_data.get("altText", "")
image_caption = image_data.get("caption", "")
image_credit = image_data.get("credit", "")

# Add to Episode dataclass
```

---

### Issue 4: Episode Links CSS Class ✅ FIXED

**Problem**: Episode resource links in description need `wc-episode-notes-content-links` class for proper styling.

**PRX Description**:
```html
<ul>
<li>Link text: <a href="...">URL</a></li>
</ul>
```

**Required Output**:
```html
<ul class="wc-episode-notes-content-links">
<li><a href="..." target="_blank" rel="noopener noreferrer">Link text</a></li>
</ul>
```

**Code Location**: `src/content_builder.py:format_episode_links()`

**Status**: Implemented and tested. The `format_episode_links()` function:
1. Detects `<ul>` elements containing links
2. Adds `class="wc-episode-notes-content-links"` to the `<ul>` tag
3. Adds `target="_blank" rel="noopener noreferrer"` to all links
4. Extracts descriptive text from PRX format (`Description: <a>URL</a>` → `<a>Description</a>`)
5. Wraps in `<!--kg-card-begin: html-->` markers to prevent Lexical conversion

**Test Coverage**: 7 tests in `tests/test_content_builder.py::TestEpisodeLinksFormatting`

---

## Ghost Post Structure

### Audio Player HTML Card

```html
<div class="wc-audio-player"
     data-audio-url="https://wondercabinetproductions.com/content/media/2026/02/episode.mp3"
     data-episode-artwork="https://wondercabinetproductions.com/content/images/..."
     data-episode-date="2026-02-07"
     data-episode-guest=""
     data-episode-description="Short description for player"
     data-episode-duration="37:41"
     data-episode-guid="prx_120_<uuid>"
     data-peaks-url="https://wondercabinetproductions.com/content/files/...peaks.json">
</div>
```

### Episode Links HTML Card

```html
<ul class="wc-episode-notes-content-links">
<li><a href="https://..." target="_blank" rel="noopener noreferrer">Link text</a></li>
</ul>
```

### Transcript HTML Card

```html
<div id="episode-transcript" class="episode-transcript">
<h2>Transcript</h2>
<p>Speaker: Dialogue...</p>
</div>
```

### JSON-LD Structured Data

Located in `codeinjection_head`:
```json
{
  "@context": "https://schema.org",
  "@type": "PodcastEpisode",
  "name": "Episode Title",
  "description": "Full description...",
  "partOfSeries": {
    "@type": "PodcastSeries",
    "name": "Wonder Cabinet"
  },
  "datePublished": "2026-02-07T12:00:00+00:00",
  "duration": "PT2261S",
  "url": "https://play.prx.org/listen?..."
}
```

---

## Automation Enhancements

### ✅ Completed: Episode Links Formatting

The `format_episode_links()` function in `src/content_builder.py` now automatically:
- Adds CSS class for WC-Episode theme styling
- Adds proper link attributes (`target="_blank"`, `rel="noopener noreferrer"`)
- Extracts descriptive text from PRX URL format
- Wraps in Ghost HTML card markers

### Priority 1: Audio Segment Fallback

```python
# In waveform_peaks.py or new audio_processor.py

def download_episode_audio(episode_data: dict, output_path: Path) -> Path:
    """Download episode audio, handling multi-segment episodes.

    1. Try _links.enclosure.href first
    2. On 404, fall back to media[] segments
    3. Concatenate segments with ffmpeg if needed
    4. Return path to final audio file
    """
```

### Priority 2: Image Metadata Extraction

```python
# In Episode dataclass
@dataclass
class Episode:
    # ... existing fields ...
    image_alt: str = ""
    image_caption: str = ""
    image_credit: str = ""

# In dovetail_client.py
image_data = data.get("image", {})
episode.image_alt = image_data.get("altText", "")
episode.image_credit = image_data.get("credit", "")
```

### Priority 3: Episode Links Formatting

```python
# In content_builder.py

def format_episode_links(description_html: str) -> str:
    """Transform plain <ul> links to styled episode links."""
    import re

    # Find <ul>...</ul> sections
    # Add class and wrap in HTML card markers
    # Return transformed HTML
```

### Priority 4: State Tracker Audio Flag

```python
# In state_tracker.py

@dataclass
class PublishedEpisode:
    # ... existing fields ...
    audio_uploaded: bool = False
    peaks_uploaded: bool = False
```

---

## Manual Intervention Scenarios

### Scenario: Re-import with Audio Upload

When an episode was synced without audio and needs to be re-imported:

```bash
# 1. Backup state
cp data/published_episodes.prod.json data/published_episodes.prod.backup.json

# 2. Remove from state
uv run python3 -c "
from src.state_tracker import StateTracker
from pathlib import Path
tracker = StateTracker(Path('data/published_episodes.prod.json'))
tracker.remove('prx_120_<guid>')
"

# 3. Delete Ghost post (via Admin UI or MCP)

# 4. Re-sync with audio
uv run python3 -m src.main --env prod sync \
    --source api --status draft --upload-audio \
    --guid "prx_120_<guid>" -y
```

### Manual Post Updates

```python
# Update post with fixes
import os, json
from dotenv import load_dotenv
from src.ghost_client import GhostClient

load_dotenv('.env.prod')
client = GhostClient(
    base_url=os.getenv('GHOST_URL'),
    api_key=os.getenv('GHOST_ADMIN_API_KEY')
)

post_id = "<ghost_post_id>"

# Get current post
response = client._request_with_retry(
    "GET", f"{client.api_url}/posts/{post_id}/",
    headers=client._get_headers(), timeout=30
)
post = client._handle_response(response)["posts"][0]

# Update fields
payload = {
    "posts": [{
        "feature_image_alt": "Alt text from PRX",
        "feature_image_caption": "Image credit: ...",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": post["updated_at"]
    }]
}

response = client._request_with_retry(
    "PUT", f"{client.api_url}/posts/{post_id}/",
    json=payload, headers=client._get_headers(), timeout=30
)
```

---

## Verification Checklist

After importing an episode, verify:

- [ ] Audio plays in Ghost preview (no CORS errors)
- [ ] Waveform displays in audio player
- [ ] Feature image has alt text (check in Ghost editor)
- [ ] Feature image has caption/credit
- [ ] Episode links have proper styling (`wc-episode-notes-content-links`)
- [ ] Transcript displays correctly
- [ ] `published_at` is set to import time (not future)
- [ ] State file updated with new post ID
- [ ] JSON-LD structured data in page source

---

## Related Documentation

- [COMPREHENSIVE_DESIGN.md](./COMPREHENSIVE_DESIGN.md) - Full system architecture
- [WAVEFORM_PEAKS_IMPLEMENTATION.md](./WAVEFORM_PEAKS_IMPLEMENTATION.md) - Peaks generation details
- [AUTOMATION_DESIGN.md](./AUTOMATION_DESIGN.md) - GitHub Actions workflow
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Component overview
