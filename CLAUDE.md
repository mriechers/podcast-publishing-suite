# podcast-publishing-suite

Meta-repository for the podcast publishing pipeline at **Wonder Cabinet Productions**. Manages per-show configuration, pipeline tool submodules, and a unified dashboard frontend.

## Directory Structure

```
podcast-publishing-suite/
├── modules/                          # Git submodules — pipeline tools
│   ├── audiogram-tools/              # Remotion-based animated audiogram generation
│   ├── podcast-whisper-transcription/ # OpenAI Whisper transcription pipeline
│   ├── prx-to-ghost-publisher/       # PRX Dovetail → Ghost CMS publisher
│   └── robo-social/                  # Social media distribution (placeholder)
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

PBS Wisconsin shows using this suite for **audio stitching only** (no PRX/Ghost publishing here):

| Show | Slug | Ingest | Body file |
|------|------|--------|-----------|
| In Focus with Murv Seymour | `in-focus` | `mmingest.pbswi.wisc.edu/InFocus/` | `6INF01NN.wav`, revisions `_REV<YYYYMMDD>` |
| McCoshen & Ross | `mccoshen-ross` | `mmingest.pbswi.wisc.edu/HereNow/` | `HAN<season><week>MCROSS.wav` |

The ingest server is on the PBS Wisconsin network — a connection failure is almost always VPN, not a bad URL. `scripts/ingest_scan.py` parses its Apache listings with stdlib only and deliberately does **not** use Cardigan's mmingest MCP index: that is another product's internal service, and it keys on the 8-character Media ID grammar, so `HAN2507MCROSS` is invisible to it.

**AirTable is not reachable from this repo, and the blocker is registration, not configuration.** `AIRTABLE_API_KEY` has never been registered in Infisical — `lodge-doctor secret infisical-locator AIRTABLE_API_KEY` returns "no active infisical secret found". It exists only in the macOS keychain, which no agent process can read (rc=36, `errSecInteractionNotAllowed`). Setting `INFISICAL_TOKEN` does **not** fix this on its own.

To enable: add the key in the Infisical UI, run `/add-secret` to register it, verify with `GET_SECRET_DEBUG=1 get-secret.sh AIRTABLE_API_KEY >/dev/null`, then `mv .mcp.json.disabled .mcp.json`. That file carries the full note and resolves the secret through `get-secret.sh` rather than the raw `security find-generic-password` call the parent workspace's `.mcp.json` uses — the raw call is what the workspace convention forbids and is why AirTable appears to work by hand and fails for every agent.

Beware: `get-secret.sh` currently reports a locked keychain item as "not found" (the-lodge#707), so its error text will misdirect you. Until this is sorted, ask the user for episode titles or air dates rather than assuming a lookup will work.

Ghost site: [wondercabinetproductions.com](https://wondercabinetproductions.com)

## Module Status

| Module | Status | Show-Specific? | Notes |
|--------|--------|----------------|-------|
| audiogram-tools | Active | Yes — Wonder Cabinet branding hardcoded | Remotion compositions, galaxy spiral animations |
| podcast-whisper-transcription | Active | Partially — processing scripts reference WC episodes | Whisper turbo, speaker diarization |
| prx-to-ghost-publisher | Active | Multi-show via config | Supports both shows, Ghost theme in development |
| markbot | Active | Multi-show via config | Centralized Slack bot; `post`, `transcribe-*`, `ghost-import`, `schedule-alert` commands |
| robo-social | Placeholder | N/A | README only, not yet implemented |

### Pipeline commands (in-repo, `.claude/commands/`)

These are slash commands tracked in this repo — `.gitignore` excludes `.claude/*` but re-includes `!.claude/commands/`. Edit them here; they are not external skills.

| Command | Pipeline Step | Notes |
|-------|--------------|-------|
| `/episode-init` | New guest → canonical episode folder | Scaffolds `shows/<show>/episodes/<slug>/`, resolves Drive subfolder |
| `/wc-transcribe` | Audio → transcripts, chapters, captions | Drives whisper-transcription; also pulls source images for `/wc-episode-art` |
| `/wc-episode-art` | Source images → branded 3-panel collage | 3000×3000, green/black borders, rclone sync-back, markbot alert. **Reconstructed 2026-07-31** after being lost from `~/.claude/skills/` (never version-controlled) — see the file header for provenance and open questions |
| `/new-episode` | Ingest server → staged episode folder + verified stitch plan | "There's a new episode of In Focus." Discovers, confirms, fetches, dry-runs the stitch, then stops for a human. Driven by `scripts/ingest_scan.py` off each show's `ingest` config block |
| `/stitch-audio` | Show segments → one deliverable audio file | Pre-publishing assembly. Structure declared per show in `shows/<slug>/config.json` under `stitch`; reads and writes inside `shows/<slug>/episodes/<ep>/audio/`; driven by `scripts/stitch_audio.py` |
| `/wc-transcript-update` | Producer-edited Google Doc → corrected transcript/captions | Applies speaker + spelling corrections back to episode files |
| `/ghost-import` | PRX Dovetail → Ghost CMS drafts | Drives prx-to-ghost-publisher module |
| `/wc-youtube-export` | Episode folder → YouTube draft upload | Renders horizontal video via audiogram-tools, uploads via YouTube Data API |
| `/validate-podcast-feed` | RSS feed → validation report | Checks a show's public feed against podcast/RSS spec |

## Key Commands

> **Note on `modules/`:** this fork has no `.gitmodules` — the module directories are committed inline, not as git submodules. The clone/init commands below are kept for the upstream layout; in this checkout they are no-ops.

```bash
# Clone (upstream layout used submodules; this fork vendors them)
git clone git@github.com:Wonder-Cabinet-Productions/podcast-publishing-suite.git

# Run the test suite
python3 -m pytest tests/

# Frontend development
cd frontend/web && npm install && npm run dev     # React dev server
cd frontend && pip install -r requirements.txt     # API dependencies
cd frontend && uvicorn api.main:app --reload       # FastAPI dev server
```

## Conventions

- **Never force-push master** — current submodule iterations are in production
- **Feature work on branches** — always branch from master for structural changes
- **Submodule cleanup**: removing a submodule requires cleaning 3 places (`.gitmodules`, `.git/config`, `.git/modules/`)
- **Naming**: "Podbridge" was an earlier editorial-assistant repurposing (archived in `reference/`). "Cardigan" refers to the PBS Wisconsin project — do not conflate them
- **Show configs**: `shows/<slug>/` is the source of truth for per-show settings. `config.json` for service config and segment structure (`stitch`), `brand.json` for visual identity, `assets/` for images and audio elements. Modules should read from here rather than hardcoding values. Consuming code should require only the files it actually needs — `stitch_audio.py` reads `config.json` and never touches `brand.json`, so a stitch-only show doesn't need one
- **Show definitions are tracked, show media is not.** `.gitignore` allowlists exactly `shows/*/config.json`, `brand.json`, and `glossary.json`; everything else under a show folder is ignored regardless of type, so a stray `.wav` in a show root can't reach GitHub. `assets/` and `episodes/` are local-only — if lost they're rebuilt from the production archive, not pulled, and `shows/README.md` carries the recipes. The structural definitions stay in git deliberately: losing those is the exposure that lost `/wc-episode-art`
- **Episode assembly is declared, never inferred**: a show's segment structure lives in `stitch.segments` in its `config.json` as an ordered list of slots, each either an `asset` the show owns or an `episode` file located by a `match` pattern. `scripts/stitch_audio.py` resolves files onto slots and hard-fails — reporting every problem at once — on ambiguity, orphans, or a missing required slot. **List position is playback order**; see the `sorted()` warning below for why nothing is ever re-derived from filenames. Stream copy is used only when no fades are requested, every input agrees on codec/rate/channels, *and* the output container accepts that codec unchanged — the PBS Wisconsin masters are 24-bit/48k WAV bound for a 44.1k MP3, so they always re-encode
- **Module design docs**: each module should have `docs/MODULE_DESIGN.md` following the template at `docs/MODULE_DESIGN_TEMPLATE.md`
- **Episode audio is resolved, never globbed**: producer-supplied Drive folders vary in everything except shape — the MP3s always sit in a nested `WC_01_NN_Name/` subfolder (twice-nested for E17), separators drift between `_`, space, and hyphen, names carry stray leading spaces, and the image folder is `Images`, `Photos`, or `Images for Newsletter`. What never varies: exactly three MP3s — part 1, mid-roll, part 2. `scripts/resolve_audio.py` keys on that invariant, flattens the download to `{slug}_part01|_midroll|_part02.mp3`, and writes `files.audio.parts` in playback order. **Never order parts with `sorted()`** — `"mid"` sorts before `"mix"`, so lexical order puts the mid-roll first for every episode named `*_mix_01.mp3` (E10–E18 all have this wrong in their manifests; it never reached production only because caption stitching takes its order from the command's literal part-01/mid-roll/part-02 sequence rather than from the manifest). The resolver hard-fails instead of guessing; tests in `tests/test_resolve_audio.py` pin the real filename corpus from E12–E20.
- **Known Whisper errors**: Per-show glossary files at `shows/<slug>/glossary.json` contain Whisper misrenderings and correct spellings. Common examples: "Versher" → Vershire, "Rickers" → Mark Riechers, "Strain-Champs" → Anne Strainchamps. The transcription pipeline applies these automatically: `whisper-transcribe.sh --glossary shows/<slug>/glossary.json` rewrites each part's `.srt`/`.txt`/`.vtt`/`.tsv` right after transcription (never the `.json` — it is the machine artifact of record), via `modules/podcast-whisper-transcription/scripts/apply_glossary.py`. **Keys are applied unattended, so they must be full misheard phrases** — never a bare common word or standalone given name, since a bare `"Immanuel"` key would rewrite *Immanuel Kant*. Matching is case-sensitive; see the `description` field in the glossary for the full authoring contract.

## Future Work

- **Module genericization** — make audiogram-tools and whisper-transcription show-agnostic (read from `shows/` configs). Always on feature branches
- **Frontend buildout** — replace cardigan template scaffolding with podcast pipeline views (episode runs, module status, show switching)
- **robo-social implementation** — social media distribution automation
- **CI/CD** — automated testing across submodules, frontend deployment

## Agent skills

### Issue tracker

GitHub Issues on `Wonder-Cabinet-Productions/podcast-publishing-suite`, via the `gh` CLI — module-specific work is filed on the module's own repo. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), applied *alongside* this repo's existing `type:`/`executor:`/`priority:` vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — a root `CONTEXT.md` plus `docs/adr/`, both created lazily by `/domain-modeling`. See `docs/agents/domain.md`.

### Long-range planning

Consolidation of this suite into a single repo is charted as a `/mattpocock-skills:wayfinder` map on this repo's tracker (label `wayfinder:map`). Background evidence: `../planning/2026-08-12-wayfinder-charting-brief.md` in the metarepo.
