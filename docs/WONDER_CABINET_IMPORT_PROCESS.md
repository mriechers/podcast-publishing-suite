# Wonder Cabinet Episode Import Process

> **Last Updated**: 2026-02-14
> **Status**: Production-ready

This document captures the complete automated process for importing Wonder Cabinet episodes from PRX Dovetail to Ghost CMS.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Import Process](#import-process)
4. [What the Pipeline Does](#what-the-pipeline-does)
5. [Ghost Post Structure](#ghost-post-structure)
6. [Transcript Attachment](#transcript-attachment)
7. [Manual Intervention Scenarios](#manual-intervention-scenarios)
8. [Verification Checklist](#verification-checklist)

---

## Overview

Wonder Cabinet episodes are published via PRX Dovetail and automatically imported to Ghost CMS at `wonder-cabinet.ghost.io` (production). The sync pipeline handles:

- Multi-segment audio download, concatenation (ffmpeg), and upload to Ghost
- Episode artwork download, OG image generation, and upload
- HTML content transformation (boilerplate stripping, link formatting, sanitization)
- Email CTA button for newsletter subscribers (brand green, email-only visibility)
- Lexical visibility controls (audio player web-only, email CTA email-only, transcript web-only)
- Smart link text splitting (avoids hyperlinking entire paragraphs)
- Image alt text and caption from PRX metadata
- JSON-LD structured data (`PodcastEpisode` schema)
- PRX writeback (sets episode link to Ghost canonical URL)
- State tracking to prevent duplicate imports

### Key Insight: Scheduled vs Published Episodes

| Episode State | `_links.enclosure.href` | `media[]` array |
|---------------|-------------------------|-----------------|
| **Published** | Works (tracking URL) | Works (direct CDN) |
| **Scheduled** | 404 Error | Works (direct CDN) |

The pipeline always uses the `media[]` array for audio downloads.

---

## Prerequisites

### Tools Required

```bash
ffmpeg -version           # Audio concatenation (required)
audiowaveform --version   # Waveform peaks (optional, v1.11.0+)
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

---

## Import Process

### Standard Sync (one command)

```bash
# Sync all new episodes (incremental — only fetches since last sync)
python -m src.main --env prod sync --source api --yes

# Sync a specific episode by GUID
python -m src.main --env prod sync --source api \
    --guid "prx_120_<uuid>" --yes

# Dry run (preview without publishing)
python -m src.main --env prod sync --source api --dry-run

# List available episodes
python -m src.main --env prod list --source api
```

### What Happens Automatically

The sync command performs these steps for each new episode:

1. **Fetch episode** from Dovetail API (or RSS feed)
2. **Download artwork** from PRX CDN, upload to Ghost, generate OG image (1200x630)
3. **Download audio segments** from `media[]` URLs, concatenate with ffmpeg, upload to Ghost
4. **Build HTML content**:
   - Audio player card (`wc-audio-player` div with data attributes)
   - Email CTA button (brand green `#10a544`, white text — for email subscribers)
   - Episode description (boilerplate stripped, links reformatted with smart splitting)
   - Transcript section (if available from RSS `<podcast:transcript>` or local files)
5. **Create Ghost post** with `source=html` (Ghost converts to Lexical internally)
6. **Apply Lexical visibility** — fetch Lexical back, set per-card visibility:
   - Audio player: web-only (email clients can't render custom players)
   - Email CTA: email-only (web visitors use the audio player directly)
   - Transcript: web-only (too long for email)
7. **PRX writeback** — set the episode's `link` field on PRX to the Ghost canonical URL (so podcast app "Visit Website" links point to Ghost)
8. **Record state** — save post ID, slug, timestamps to state tracker

---

## What the Pipeline Does

### Content Transformations

| Transform | Code Location | Description |
|-----------|---------------|-------------|
| Boilerplate stripping | `content_transforms.py` | Removes show description, social links, `--`/`---` dividers |
| HTML sanitization | `content_builder.py:sanitize_html()` | Strips disallowed tags, normalizes whitespace |
| Link formatting | `content_builder.py:format_episode_links()` | Adds CSS class, `target="_blank"`, `rel="noopener"` |
| Smart link splitting | `content_builder.py:_split_link_text()` | Links quoted titles, colon prefixes, or short text — not entire paragraphs |
| Bare URL detection | `content_builder.py:format_episode_links()` | Detects plain URLs in `<li>` items, wraps with descriptive text |

### Smart Link Splitting Heuristics

When PRX descriptions contain links like `"Program Name: Long description of the episode"`, the pipeline intelligently selects what to hyperlink:

| Input Pattern | What Gets Linked | Example |
|---------------|-----------------|---------|
| Text ≤ 60 chars | Entire text | "Rebecca Solnit's newsletter" |
| Text with `"quoted title"` | Quoted portion only | Pre-order **"The Beginning Comes After the End"**, due March 3 |
| Text with colon (prefix ≤ 50 chars) | Text before colon | **To The Best Of Our Knowledge**: Tending a wartime garden... |
| Fallback | Entire text | (long text without quotes or colons) |

### Lexical Visibility (Two-Pass Pipeline)

Ghost's HTML-to-Lexical converter doesn't support per-card visibility, so we use a two-pass approach:

1. **Pass 1**: Create post with `source=html` — Ghost converts to Lexical internally
2. **Pass 2**: Fetch Lexical JSON back, apply `visibility` properties to HTML card nodes, PUT raw Lexical

Visibility markers are matched by CSS class names in the HTML:

| Marker | Visibility | Purpose |
|--------|-----------|---------|
| `wc-audio-player` | Web-only | Email clients can't render custom audio players |
| `wc-email-cta` | Email-only | Web visitors use the audio player directly |
| `episode-transcript` | Web-only | Transcripts are too long for email newsletters |

### PRX Writeback

After publishing to Ghost, the pipeline sets the episode's `link` field on PRX Dovetail to the Ghost canonical URL. This means:

- Podcast app "Visit Website" buttons point to the Ghost post
- PRX directory listings link to Ghost
- The writeback uses `DovetailClient.set_episode_link()` which handles GUID-to-ID resolution

Writeback is only active when using `--source api` (requires PRX API credentials).

---

## Ghost Post Structure

Each published post has this Lexical node structure:

| Node | Type | Visibility | Content |
|------|------|-----------|---------|
| 0 | html | Web-only | Audio player (`wc-audio-player` div with data attributes) |
| 1 | html | Email-only | CTA button ("Listen to this episode" — brand green) |
| 2-3 | paragraph | Everyone | Episode description (from PRX `content:encoded`) |
| 4 | html | Everyone | Episode links (`wc-episode-notes-content-links` list) |
| 5 | html | Web-only | Transcript (added separately — see below) |

### Audio Player HTML Card

```html
<div class="wc-audio-player"
     data-audio-url="https://wondercabinetproductions.com/content/media/2026/02/episode.mp3"
     data-original-audio-url="https://dts.podtrac.com/redirect.mp3/..."
     data-episode-artwork="https://wondercabinetproductions.com/content/images/..."
     data-episode-date="2026-02-14"
     data-episode-guest=""
     data-episode-description="Short description for player"
     data-episode-duration="38:10"
     data-episode-guid="prx_120_<uuid>">
</div>
```

### Email CTA Button

```html
<div class="wc-email-cta" style="text-align: center; margin: 24px 0;">
  <a href="https://wonder-cabinet.ghost.io/<slug>/"
     style="display: inline-block; padding: 12px 24px;
            background-color: #10a544; color: #ffffff;
            text-decoration: none; border-radius: 4px; font-weight: 600;">
    Listen to this episode</a>
</div>
```

### Episode Links

```html
<ul class="wc-episode-notes-content-links">
  <li><a href="..." target="_blank" rel="noopener noreferrer">Short Label</a>: longer description</li>
</ul>
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
  "datePublished": "2026-02-14T12:00:00+00:00",
  "duration": "PT2290S",
  "url": "https://wonder-cabinet.ghost.io/<slug>/"
}
```

---

## Transcript Attachment

Transcripts are attached separately from the main sync because they're often processed after the initial episode import (Whisper transcription, speaker diarization, human editing).

### Automated (from RSS `<podcast:transcript>`)

If the PRX feed includes a `<podcast:transcript>` tag, the sync pipeline fetches and formats it automatically.

### Manual (pre-formatted HTML)

For transcripts processed through the whisper pipeline with human corrections:

```python
import os, json
from dotenv import load_dotenv
load_dotenv('.env.prod')

from src.ghost_client import GhostClient
from src.content_builder import VISIBILITY_WEB_ONLY

client = GhostClient(os.getenv('GHOST_URL'), os.getenv('GHOST_ADMIN_API_KEY'))

# Read transcript HTML
with open('/path/to/transcript.html', 'r') as f:
    transcript_html = f.read()

# Wrap in container
wrapped = (
    '<div class="episode-transcript">'
    '<h3>Transcript</h3>'
    + transcript_html +
    '</div>'
)

# Fetch current Lexical, append transcript node
post_id = "<ghost_post_id>"
post = client.get_post_with_lexical(post_id)
lexical = json.loads(post['lexical'])

lexical['root']['children'].append({
    'type': 'html',
    'version': 1,
    'html': wrapped,
    'visibility': VISIBILITY_WEB_ONLY,
})

client.update_post_lexical(post_id, json.dumps(lexical), post['updated_at'])
```

---

## Manual Intervention Scenarios

### Re-import an Episode

When an episode needs to be deleted and re-imported (content changes, bug fixes):

```python
import os
from dotenv import load_dotenv
load_dotenv('.env.prod')

from src.ghost_client import GhostClient

client = GhostClient(os.getenv('GHOST_URL'), os.getenv('GHOST_ADMIN_API_KEY'))

# 1. Delete Ghost post
url = f'{client.api_url}/posts/<ghost_post_id>/'
client._request_with_retry('DELETE', url, headers=client._get_headers(), timeout=30)
```

Then remove from state tracker (edit `data/published_episodes.prod.json` to remove the entry) and re-sync:

```bash
python -m src.main --env prod sync --source api \
    --guid "prx_120_<uuid>" --yes
```

### Manual PRX Writeback

If the writeback failed or wasn't available during import (e.g., RSS source):

```python
from src.prx_auth import PRXAuthClient
from src.dovetail_client import DovetailClient

auth_client = PRXAuthClient(
    client_id=os.getenv('PRX_CLIENT_ID'),
    client_secret=os.getenv('PRX_CLIENT_SECRET'),
    token_endpoint='https://id.prx.org/token',
)
api_client = DovetailClient(auth_client=auth_client, podcast_id='120')

api_client.set_episode_link(
    'prx_120_<uuid>',
    'https://wonder-cabinet.ghost.io/<slug>/'
)
```

---

## Verification Checklist

After importing an episode, verify:

- [ ] Audio plays in Ghost preview (no CORS errors)
- [ ] Feature image has alt text and caption/credit
- [ ] Episode links use smart splitting (short labels, not full paragraphs)
- [ ] Email CTA button is brand green (`#10a544`) with white text
- [ ] Lexical visibility: audio player web-only, CTA email-only, transcript web-only
- [ ] Transcript displays correctly (web-only)
- [ ] `published_at` is import time (not future PRX scheduled date)
- [ ] State file updated with post ID and slug
- [ ] JSON-LD structured data in page source
- [ ] PRX writeback done (`prx_writeback_done: true` in state tracker)
- [ ] Podcast app "Visit Website" links to Ghost post (verify in PRX admin)

---

## Related Documentation

- [SHOW_NOTES_FORMAT.md](./SHOW_NOTES_FORMAT.md) - Show notes formatting conventions (link format, boilerplate, chapters)
- [COMPREHENSIVE_DESIGN.md](./COMPREHENSIVE_DESIGN.md) - Full system architecture
- [WAVEFORM_PEAKS_IMPLEMENTATION.md](./WAVEFORM_PEAKS_IMPLEMENTATION.md) - Peaks generation details
- [AUTOMATION_DESIGN.md](./AUTOMATION_DESIGN.md) - GitHub Actions workflow
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Component overview
