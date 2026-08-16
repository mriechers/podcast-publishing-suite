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

Episode directories are gitignored (`shows/*/episodes/`) since they contain working files that are also stored on Google Drive. The canonical episode folder is a local staging area, not version-controlled content.

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
