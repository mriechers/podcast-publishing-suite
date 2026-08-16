# podcast-publishing-suite

Meta-repository for the podcast publishing pipeline at **Wonder Cabinet Productions**. Manages per-show configuration, pipeline tool modules, and a unified dashboard frontend.

## Directory Structure

```
podcast-publishing-suite/
├── modules/                          # Pipeline tools (inline source, not submodules)
│   ├── analytics-dashboard/          # PRX CSV import, publication stats
│   ├── audiogram-tools/              # Remotion-based animated audiogram generation
│   ├── markbot/                      # Centralized Slack bot
│   ├── podcast-whisper-transcription/ # OpenAI Whisper transcription pipeline
│   └── prx-to-ghost-publisher/       # PRX Dovetail → Ghost CMS publisher
├── frontend/                         # Unified dashboard (React 18 + Vite + Tailwind / FastAPI)
│   ├── api/                          # FastAPI backend
│   ├── web/                          # React frontend
│   └── branding.json                 # White-label configuration
├── docs/                             # Meta-repo documentation
│   └── MODULE_DESIGN_TEMPLATE.md     # Standardized module design document template
├── shows/                            # Per-show identity packages (read by modules)
│   ├── wonder-cabinet/
│   │   ├── config.json               # Service config (PRX, Ghost, routing)
│   │   ├── brand.json                # Visual identity (colors, typography, schemes)
│   │   └── assets/                   # Logos, backgrounds (git-tracked)
│   ├── luminous/
│   │   ├── config.json
│   │   ├── brand.json
│   │   └── assets/
│   └── README.md                     # Show config schema documentation
├── images/                           # Episode artwork (gitignored)
└── reference/                        # Archived material (gitignored)
```

## Shows

| Show | PRX ID | Feed | Ghost Route |
|------|--------|------|-------------|
| Wonder Cabinet | 120 | `publicfeeds.net/f/120/wondercabinet` | `/wonder-cabinet/` |
| Luminous | 3329 | `f.prxu.org/3329/feed-rss.xml` | `/luminous/` |

Ghost site: [wondercabinetproductions.com](https://wondercabinetproductions.com)

## Module Status

| Module | Status | Notes |
|--------|--------|-------|
| audiogram-tools | Active | Remotion compositions, galaxy spiral animations |
| podcast-whisper-transcription | Active | Whisper turbo, speaker diarization |
| prx-to-ghost-publisher | Active | Supports both shows, Ghost theme in development |
| markbot | Active | Centralized Slack bot |
| analytics-dashboard | Active | PRX CSV import, publication stats |

### Pipeline commands (in-repo, `.claude/commands/`)

These are slash commands tracked in this repo — `.gitignore` excludes `.claude/*` but re-includes `!.claude/commands/`. Edit them here; they are not external skills.

| Command | Pipeline Step | Notes |
|-------|--------------|-------|
| `/episode-init` | New guest → canonical episode folder | Scaffolds `shows/<show>/episodes/<slug>/`, resolves Drive subfolder |
| `/wc-transcribe` | Audio → transcripts, chapters, captions | Drives whisper-transcription; also pulls source images for `/wc-episode-art` |
| `/wc-episode-art` | Source images → branded 3-panel collage | 3000×3000, green/black borders, rclone sync-back, markbot alert. **Reconstructed 2026-07-31** after being lost from `~/.claude/skills/` (never version-controlled) — see the file header for provenance and open questions |
| `/wc-transcript-update` | Producer-edited Google Doc → corrected transcript/captions | Applies speaker + spelling corrections back to episode files |
| `/ghost-import` | PRX Dovetail → Ghost CMS drafts | Drives prx-to-ghost-publisher module |
| `/wc-youtube-export` | Episode folder → YouTube draft upload | Renders horizontal video via audiogram-tools, uploads via YouTube Data API |
| `/validate-podcast-feed` | RSS feed → validation report | Checks a show's public feed against podcast/RSS spec |

## Key Commands

```bash
# Clone — modules are inline source, no submodule init needed
# Base repo — organization forks clone their own fork instead
git clone git@github.com:mriechers/podcast-publishing-suite.git

# Frontend development
cd frontend/web && npm install && npm run dev     # React dev server
cd frontend && pip install -r requirements.txt     # API dependencies
cd frontend && uvicorn api.main:app --reload       # FastAPI dev server
```

## Conventions

- **Never force-push master** — current module iterations are in production
- **Feature work on branches** — always branch from master for structural changes
- **Modules are inline** — `modules/<name>/` is ordinary source in this repo, imported via
  `git subtree`. There are no submodules and no `.gitmodules`; the standalone module repos are
  retired and no longer the source of truth. Do not re-extract a module into its own repo.
- **Naming**: "Podbridge" was an earlier editorial-assistant repurposing (archived in `reference/`). "Cardigan" refers to the PBS Wisconsin project — do not conflate them
- **Show configs**: `shows/<slug>/` is the source of truth for per-show settings. `config.json` for service config, `brand.json` for visual identity, `assets/` for images. Modules should read from here rather than hardcoding values
- **Module design docs**: each module should have `docs/MODULE_DESIGN.md` following the template at `docs/MODULE_DESIGN_TEMPLATE.md`
- **Episode audio is resolved, never globbed**: producer-supplied Drive folders vary in everything except shape — the MP3s always sit in a nested `WC_01_NN_Name/` subfolder (twice-nested for E17), separators drift between `_`, space, and hyphen, names carry stray leading spaces, and the image folder is `Images`, `Photos`, or `Images for Newsletter`. What never varies: exactly three MP3s — part 1, mid-roll, part 2. `scripts/resolve_audio.py` keys on that invariant, flattens the download to `{slug}_part01|_midroll|_part02.mp3`, and writes `files.audio.parts` in playback order. **Never order parts with `sorted()`** — `"mid"` sorts before `"mix"`, so lexical order puts the mid-roll first for every episode named `*_mix_01.mp3` (E10–E18 all have this wrong in their manifests; it never reached production only because caption stitching takes its order from the command's literal part-01/mid-roll/part-02 sequence rather than from the manifest). The resolver hard-fails instead of guessing; tests in `tests/test_resolve_audio.py` pin the real filename corpus from E12–E20.
- **Known Whisper errors**: Per-show glossary files at `shows/<slug>/glossary.json` contain Whisper misrenderings and correct spellings. Common examples: "Versher" → Vershire, "Rickers" → Mark Riechers, "Strain-Champs" → Anne Strainchamps. The transcription pipeline applies these automatically: `whisper-transcribe.sh --glossary shows/<slug>/glossary.json` rewrites each part's `.srt`/`.txt`/`.vtt`/`.tsv` right after transcription (never the `.json` — it is the machine artifact of record), via `modules/podcast-whisper-transcription/scripts/apply_glossary.py`. **Keys are applied unattended, so they must be full misheard phrases** — never a bare common word or standalone given name, since a bare `"Immanuel"` key would rewrite *Immanuel Kant*. Matching is case-sensitive; see the `description` field in the glossary for the full authoring contract.

## Future Work

- **Module genericization** — make audiogram-tools and whisper-transcription show-agnostic (read from `shows/` configs). Always on feature branches
- **Frontend buildout** — replace cardigan template scaffolding with podcast pipeline views (episode runs, module status, show switching)
- **robo-social implementation** — social media distribution automation
- **CI/CD** — automated testing across modules, frontend deployment

## Agent skills

### Issue tracker

Code issues go to the base repo `mriechers/podcast-publishing-suite` via the `gh` CLI — always
pass `--repo` explicitly. Organization-specific operational issues go to that org's own tracker.
See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), applied *alongside* this repo's existing `type:`/`executor:`/`priority:` vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — a root `CONTEXT.md` plus `docs/adr/`, both created lazily by `/domain-modeling`. See `docs/agents/domain.md`.

### Long-range planning

Consolidation of this suite into a single repo is charted as a `/mattpocock-skills:wayfinder` map on this repo's tracker (label `wayfinder:map`). Background evidence: `../planning/2026-08-12-wayfinder-charting-brief.md` in the metarepo.
