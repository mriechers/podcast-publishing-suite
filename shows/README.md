# Show Identity Structure

Each directory under `shows/` defines a complete identity package for one podcast show. Modules read from these files instead of hardcoding show-specific values.

## Directory Layout

```
shows/<slug>/
├── config.json    # Service configuration (PRX, Ghost, routing)
├── brand.json     # Visual identity (colors, typography, color schemes)
└── assets/        # Branding assets (logos, backgrounds)
    ├── logo-primary.png
    ├── logo-wordmark.png
    ├── background.png
    └── ...
```

## File Responsibilities

### `config.json` — Service Configuration

Connects the show to external services. Contains identifiers, URLs, and routing — not visual styling.

```json
{
  "name": "Show Name",
  "slug": "show-slug",
  "prx": {
    "podcastId": 123,
    "feedUrl": "https://..."
  },
  "ghost": {
    "siteUrl": "https://...",
    "tag": "show-slug",
    "internalTags": ["#show-slug", "Podcast"],
    "route": "/show-slug/"
  },
  "google_drive": {
    "audio_folder_id": "...",
    "transcripts_folder_id": "..."
  },
  "branding": {
    "primaryColor": "#hex",
    "logoPath": "images/show-logo.png"
  }
}
```

The `google_drive` block maps the show's Google Drive folder structure. `audio_folder_id` is the root folder containing per-episode audio subfolders. `transcripts_folder_id` is the destination for finished deliverables. Not all shows require this — omit if Drive is not used.

The `branding` block is a simplified reference kept for backward compatibility. The full visual identity lives in `brand.json`.

#### `ingest` — Where Episodes Arrive

Declares where production drops this show's episodes and which artifacts to pull. Read by `scripts/ingest_scan.py` (`/new-episode`).

```json
{
  "ingest": {
    "url": "https://mmingest.pbswi.wisc.edu/InFocus/",
    "episodePattern": "^6INF\\d{4}(?:_REV\\d{8})?$",
    "artifacts": {
      ".wav": { "dest": "audio", "required": true },
      ".srt": { "dest": "captions" },
      ".scc": { "dest": "captions" },
      ".txt": { "dest": "captions" }
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `url` | Apache index listing the show's arrivals. A trailing slash is added if missing |
| `episodePattern` | Regex matched against a filename's **stem** (no extension). The stem that matches *is* the episode key. Case-sensitive |
| `artifacts` | Extension → `{dest, required}`. `dest` is a subdirectory of the episode folder (`""` for its root). Only declared extensions are pulled; `required` artifacts block a fetch when absent |

**Make `episodePattern` narrow.** It is the only thing separating this show's episodes from everything else in a shared drop folder — `^HAN\d{4}MCROSS$` picks the McCoshen & Ross body out of a Here & Now folder that also carries `HAN2507SHUR`, `HAN2507IWP`, `HAN2507FUNERAL`, and the short-form `6HNS<date>McRoss<n>` cut. It must also exclude the show's own non-episode files: `^6INF\d{4}(?:_REV\d{8})?$` matches `6INF0123` but not `6INF0120_podtile2`.

**Revisions are separate episodes.** A `_REV<YYYYMMDD>` recut gets its own key and its own folder; `/new-episode` flags it as superseding the base key rather than silently merging them, because stitching the superseded cut is a real and quiet failure.

**Not everything on the server is wanted.** Production also drops `.mp4` and its own `.mp3`. Pull the `.wav` — re-encoding the delivered MP3 would be a second lossy generation.

The scanner is deliberately self-contained (stdlib `urllib`, no dependencies) and parses the listing directly rather than going through Cardigan's mmingest MCP index. That index is another product's internal service, and it keys on the strict 8-character Media ID grammar, so it misses `HAN2507MCROSS` entirely.

#### `stitch` — Segment Structure

Declares how a finished episode is assembled from its pieces. Read by `scripts/stitch_audio.py` (`/stitch-audio`). A show without this block cannot be stitched; nothing else requires it.

```json
{
  "stitch": {
    "output": "{episode}.mp3",
    "encode": { "bitrate": "192k", "sampleRate": 44100 },
    "segments": [
      { "id": "intro",   "source": "asset",   "file": "assets/audio/INTRO.wav" },
      { "id": "program", "source": "episode", "match": "\\d?INF\\d{4}",
        "fadeInMs": 250, "fadeOutMs": 250 },
      { "id": "outro",   "source": "asset",   "file": "assets/audio/OUTRO.wav" }
    ]
  }
}
```

| Field | Meaning |
|-------|---------|
| `segments` | **Ordered — list position is playback order.** Never re-sorted, never re-derived from filenames |
| `id` | Slot name; unique. What `--slot <id>=<path>` addresses |
| `source` | `asset` = a fixed file the show owns, at `file` relative to the show dir. `episode` = supplied per episode |
| `match` | Case-insensitive regex tested against a candidate's **basename**. Used for `episode` slots |
| `required` | Default `true`. A missing optional slot is dropped; a missing required slot is a hard failure |
| `fadeInMs` / `fadeOutMs` | Default `0`. Non-zero forces a re-encode. Useful where a segment is cut from a longer broadcast file and the edit point is abrupt |
| `output` | Filename template for the deliverable. `{episode}` and `{show}` are available; default `"{episode}.mp3"`. The extension picks the format |
| `encode.bitrate` | Lossy target, e.g. `"192k"`. `null` derives it from the inputs, capped, defaulting to 192k for lossless sources |
| `encode.sampleRate` | Pins the output rate, e.g. `44100`. `null` follows the highest input rate |

**Where the deliverable lands.** Everything for an episode stays under the show folder, the stitched output included. `stitch_audio.py --show <slug> --episode <ep>` reads the pieces from that episode's audio directory and writes the result back beside them:

```
shows/<slug>/episodes/<episode-slug>/audio/
    <episode-slug>.wav     # body, from ingest
    <episode-slug>.mp3     # stitched deliverable
```

The location comes from the `episodes` block — `localPath` and `subdirs.audio`, the same keys `scripts/episode-init.py` writes. **`localPath` may be absolute**, which is the seam for moving a show's folder off the repo (onto the production SSD, say) without touching code. The stitcher excludes its own output from the input scan, so re-running an episode is safe even though the deliverable matches the same `match` pattern as its source body.

The same grammar covers a two-part-plus-midroll show (`segment_a` / `midroll` / `segment_b`) and a bookended one (`intro` / `program` / `outro`) without any special-casing.

**On `match` patterns:** make them specific enough to exclude the show's own bookends and any sibling deliverables in the same drop folder. `\d?INF\d{4}` matches `6INF0123.wav` but not `INFOCUS_INTRO.wav`; `mcross` matches the McCoshen & Ross body but not the other Here & Now segments that land beside it. The resolver fails loudly on both ambiguity and orphans rather than guessing.

### `brand.json` — Visual Identity

Full color palette, typography, color schemes, and asset references. Extracted from (and replaces) hardcoded branding in individual modules.

```json
{
  "colors": {
    "primary": "#hex",
    "primaryDark": "#hex",
    "primaryLight": "#hex",
    "backgroundDark": "#hex",
    "backgroundMedium": "#hex",
    "backgroundSurface": "#hex",
    "textPrimary": "#hex",
    "textSecondary": "#hex",
    "textMuted": "#hex",
    "accentWarm": "#hex",
    "accentCool": "#hex"
  },
  "colorSchemes": {
    "dark": {
      "background": "<color-name>",
      "backgroundSecondary": "<color-name>",
      "accent": "<color-name>",
      "waveform": "<color-name>",
      "text": "<color-name>"
    }
  },
  "typography": {
    "fontFamily": "...",
    "weights": { "regular": 400, "medium": 500, "semibold": 600, "bold": 700 }
  },
  "show": {
    "name": "Show Name",
    "tagline": "..."
  },
  "assets": {
    "logoPrimary": "assets/logo-primary.png",
    "logoWordmark": "assets/logo-wordmark.png",
    "background": "assets/background.png"
  }
}
```

**Color scheme references:** Values in `colorSchemes` are keys into the `colors` object, not raw hex values. A consuming module resolves `colorSchemes.dark.accent` → `colors.primary` → `"#10a544"`.

### `assets/` — Branding Assets

Git-tracked image files used by modules at build/render time. Standardized filenames:

| File | Purpose | Typical Size |
|------|---------|-------------|
| `logo-primary.png` | Icon/mark logo (no text) | ~200KB |
| `logo-wordmark.png` | Logo with show name text | ~30KB |
| `background.png` | Default background for video/graphics | ~900KB |

Assets are small and rarely change, making them appropriate for git tracking.

## Episodes Directory

Each show can have a local `episodes/` directory for canonical episode deliverables (transcripts, SRTs, chapters). This mirrors the per-episode folder structure on Google Drive and provides a predictable location for downstream tools like the Ghost publisher.

### Directory Layout

```
shows/<slug>/episodes/<episode-slug>/
├── transcript.txt              # Plain text transcript (combined from SRT)
├── formatted_transcript.md     # Speaker-attributed, paragraph-formatted transcript
├── captions.srt                # Combined SRT subtitle file
└── chapters.md                 # Chapter markers (timestamps + JSON)
```

### Episode Slug Conventions

| Show | Pattern | Example |
|------|---------|---------|
| Wonder Cabinet | `WC_{number}_{Guest_Name}` | `WC_104_Carlo_Rovelli` |
| Luminous | URL slug from RSS link | `melissa-etheridge-ayahuasca` |

### Config Schema

The `episodes` section in `config.json` declares what deliverables exist per show:

```json
{
  "episodes": {
    "localPath": "shows/wonder-cabinet/episodes",
    "fileMap": {
      "transcript": "transcript.txt",
      "formatted_transcript": "formatted_transcript.md",
      "captions": "captions.srt",
      "chapters": "chapters.md"
    }
  }
}
```

- `localPath`: Relative to the meta-repo root
- `fileMap`: Maps deliverable type → canonical filename within each episode folder

Not all shows have every deliverable. Luminous currently only has `transcript`. The `fileMap` documents what's expected — consuming code should check for file existence.

### Gitignore

**Structural definitions are tracked; media is not.** The rule is an allowlist — only three filenames per show reach GitHub:

```
shows/*
!shows/README.md
!shows/*/
shows/*/*
!shows/*/config.json
!shows/*/brand.json
!shows/*/glossary.json
```

Everything else under a show folder is ignored no matter what it is, so a stray `.wav` dropped into a show root cannot reach GitHub by accident. `assets/` and `episodes/` hold production audio, artwork, and per-episode working files, and stay local.

The consequence is that a show's **media is local-only state**. If it is lost it has to be rebuilt from the production archive, not pulled — `config.json` will still be there describing what is missing, and `--dry-run` names the exact files. See "Rebuilding the PBS Wisconsin bookend assets" below for the recipes.

## How Modules Should Read Show Config

Modules accept a `--show <slug>` flag (or equivalent) that resolves to the show directory:

```python
# Python example
import json
from pathlib import Path

def load_show_config(slug: str, repo_root: Path) -> dict:
    show_dir = repo_root / "shows" / slug
    config = json.loads((show_dir / "config.json").read_text())
    brand = json.loads((show_dir / "brand.json").read_text())
    return {"config": config, "brand": brand, "assets_dir": show_dir / "assets"}
```

```typescript
// TypeScript example
import { readFileSync } from 'fs';
import { join } from 'path';

function loadShowConfig(slug: string, repoRoot: string) {
  const showDir = join(repoRoot, 'shows', slug);
  const config = JSON.parse(readFileSync(join(showDir, 'config.json'), 'utf-8'));
  const brand = JSON.parse(readFileSync(join(showDir, 'brand.json'), 'utf-8'));
  return { config, brand, assetsDir: join(showDir, 'assets') };
}
```

## Current Shows

| Show | Slug | Primary Color | Status |
|------|------|---------------|--------|
| Wonder Cabinet | `wonder-cabinet` | `#10a544` (green) | Full brand.json + assets |
| Luminous | `luminous` | `#8b5cf6` (purple) | brand.json only, assets TBD |
| In Focus with Murv Seymour | `in-focus` | — | `stitch` config + intro/outro assets. No brand.json |
| McCoshen & Ross | `mccoshen-ross` | — | `stitch` config + intro/outro assets. No brand.json |

Both PBS Wisconsin shows are stitch-only so far: they carry a `config.json` with a `stitch` block and nothing else. `brand.json` is not required by `stitch_audio.py` and has not been authored for either.

### Rebuilding the PBS Wisconsin bookend assets

Show audio is gitignored, so these files are local-only. This section is the tracked record of where they came from. Source archive: `/Volumes/WPM SSD/PBSWI/Podcasts`.

**In Focus** — copy directly, no editing required:

```
In Focus/PROJECTS/In Focus - Regular Episodes/Audio Files/INFOCUS_INTRO.wav  (11.520s)
In Focus/PROJECTS/In Focus - Regular Episodes/Audio Files/INFOCUS_OUTRO.wav  (16.997s)
```

**McCoshen & Ross** — no discrete bookend files exist. Every session from season 2151 through 2501 places two regions cut from the same 165.9s compilation, `Here & Now/PROJECTS/McCoshen and Ross/Audio Files/HN_podcast_headers_ALL.WAV`, at byte-identical source offsets. Session rate is 48 kHz. Recut them sample-accurately with:

```bash
SRC=shows/mccoshen-ross/assets/audio/HN_podcast_headers_ALL.WAV
ffmpeg -y -i "$SRC" -af "atrim=start_sample=5965696:end_sample=6483456,asetpts=N/SR/TB" \
    -c:a pcm_s24le shows/mccoshen-ross/assets/audio/MCROSS_INTRO.wav   # 124.285s, 10.787s long
ffmpeg -y -i "$SRC" -af "atrim=start_sample=6521216:end_sample=7524864,asetpts=N/SR/TB" \
    -c:a pcm_s24le shows/mccoshen-ross/assets/audio/MCROSS_OUTRO.wav   # 135.859s, 20.909s long
```

Use `atrim` with sample counts rather than `-ss`/`-t` seconds — the offsets came out of the session as exact sample positions and should stay that way.

Those offsets were read out of the `.ptx` sessions with [`ptformat`](https://github.com/zamaudio/ptformat) (`clang++ -o ptftool -I. -w ptftool.cc ptformat.cc`, then `ptftool <session>.ptx`). These sessions are unobfuscated, so no decryption step is needed. Its last output section lists every timeline region as `@ <absolute> + <into-sample>, <length>` in samples — that is the authoritative source for how a show is assembled, and it beats inferring structure from delivered durations.
