# WC YouTube Video Batch Render — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render 16:9 horizontal YouTube videos for all published Wonder Cabinet episodes (E01-E10) using the WC-Horizontal template composition, with stitched audio from the PRX feed and episode collage art.

**Architecture:** A batch script iterates through episode folders, pulls stitched audio from the PRX Dovetail feed, copies episode art to `public/`, and invokes `render-trigger.ts` with `--show wonder-cabinet` for each episode.

**Tech Stack:** Remotion 4.0, PRX RSS feed (enclosure URLs), existing render-trigger CLI

**Prerequisite:** mriechers/podcast-audiogram-tools#3 (per-show video template system) — MERGED

---

## Episode Inventory

All episode files are staged at `shows/wonder-cabinet/episodes/` (gitignored, local SSD only).

| EP | Slug | Guest | Collage Art | Audio Source | Status |
|----|------|-------|-------------|--------------|--------|
| 01 | WC_S01_01_Sophie_Strand | Sophie Strand | `101-Sophie-Strand_v2.jpg` | PRX feed | Ready |
| 02 | WC_S01_02_Carlo_Rovelli | Carlo Rovelli | `102 - Carlo.png` | PRX feed | Ready |
| 03 | WC_S01_03_Rebecca_Solnit | Rebecca Solnit | `103-solnit.jpg` | PRX feed | Ready |
| 04 | WC_S01_04_George_Saunders | George Saunders | `104-saunders.jpg` | PRX feed | Ready |
| 05 | WC_S01_05_Bergland | Bergland | `WC005-berglund.jpg` | PRX feed | Ready |
| 06 | WC_S01_06_Macfarlane | Robert Macfarlane | `WC_S01_06_MacFarlane.jpg` | PRX feed | Ready |
| 07 | WC_S01_07_David_Haskell | David Haskell | `107-David-Haskell.jpg` | PRX feed | Ready |
| 08 | WC_S01_08_Manvir_Singh | Manvir Singh | `WC_S01_08_Manvir_Singh_rev2.jpg` | PRX feed | Ready |
| 09 | WC_S01_09_Dekila_Chungyalpa | Dekila Chungyalpa | `S1E9-art-v1.jpg` | PRX feed | Ready |
| 10 | WC_S01_10_Rubenstein | Mary-Jane Rubenstein | `WC_S01_10_Rubenstein_rev2.jpg` | PRX feed | Ready |
| 11 | WC_S01_11_Winterer | Caroline Winterer | No collage yet (originals only) | No audio on Drive | NOT READY |
| Bonus | WC-bonus-sun-salutation | Marcelo Gleiser | Separate (already in Remotion) | Already configured | SKIP (use existing SunSalutation composition) |

**E11 is excluded from this batch** — needs collage art compositing and audio delivery first.

---

## Audio Strategy

Local Drive folders have split audio segments (pre-midroll, midroll, post-midroll) that PRX Dovetail stitches at distribution time. Rather than concatenating manually, we pull the stitched enclosure MP3 from the PRX RSS feed.

- **Feed URL:** `https://publicfeeds.net/f/120/wondercabinet`
- **Parser:** `modules/prx-to-ghost-publisher/src/feed_parser.py` — extracts `enclosure_url` per episode
- **Enclosure URL** is a Dovetail redirect that serves the final stitched MP3

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `modules/audiogram-tools/scripts/batch-render.sh` | Batch orchestration script |
| Read | `shows/wonder-cabinet/episodes/*/images/` | Episode collage art (source) |
| Read | PRX RSS feed enclosure URLs | Stitched audio (download per episode) |
| Write | `modules/audiogram-tools/public/` | Temporary art + audio for each render |
| Write | `modules/audiogram-tools/output/` | Rendered MP4s |

---

## Task 1: Pull Stitched Audio from PRX Feed

- [ ] **Step 1: Parse the PRX feed and extract episode enclosure URLs**

```bash
curl -s "https://publicfeeds.net/f/120/wondercabinet" | \
  python3 -c "
import sys, xml.etree.ElementTree as ET
tree = ET.parse(sys.stdin)
for item in tree.findall('.//item'):
    title = item.find('title').text
    enclosure = item.find('enclosure')
    url = enclosure.get('url') if enclosure is not None else 'NO_AUDIO'
    print(f'{title}\t{url}')
"
```

Map each feed entry to its episode folder by matching guest name or episode number from the title.

- [ ] **Step 2: Download stitched MP3 for each episode**

For each episode E01-E10, download the enclosure URL to:
`shows/wonder-cabinet/episodes/<slug>/audio/stitched.mp3`

```bash
curl -L -o "shows/wonder-cabinet/episodes/WC_S01_01_Sophie_Strand/audio/stitched.mp3" "<enclosure_url>"
```

- [ ] **Step 3: Verify audio durations**

```bash
for ep in shows/wonder-cabinet/episodes/WC_S01_*/audio/stitched.mp3; do
  dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$ep" 2>/dev/null)
  echo "$(dirname $(dirname $ep) | xargs basename): ${dur}s"
done
```

---

## Task 2: Identify Collage Art per Episode

Each episode needs a single collage art image identified. Some folders have multiple images — pick the final composite (typically named with the episode number or `_rev2`).

| EP | Art File to Use |
|----|----------------|
| 01 | `images/101-Sophie-Strand_v2.jpg` |
| 02 | `images/102 - Carlo.png` |
| 03 | `images/103-solnit.jpg` |
| 04 | `images/104-saunders.jpg` |
| 05 | `images/WC005-berglund.jpg` |
| 06 | `images/WC_S01_06_MacFarlane.jpg` |
| 07 | `images/107-David-Haskell.jpg` |
| 08 | `images/WC_S01_08_Manvir_Singh_rev2.jpg` |
| 09 | `images/S1E9-art-v1.jpg` |
| 10 | `images/WC_S01_10_Rubenstein_rev2.jpg` |

- [ ] **Step 1: Verify all art files exist and are valid images**

```bash
for art in <list of art paths>; do
  identify "$art" 2>/dev/null | head -1 || echo "MISSING: $art"
done
```

---

## Task 3: Create Batch Render Script

- [ ] **Step 1: Write `modules/audiogram-tools/scripts/batch-render.sh`**

The script should:
1. Accept a `--episodes-dir` argument (path to `shows/wonder-cabinet/episodes/`)
2. For each episode folder, copy the art to `public/`, run the render, clean up the art
3. Use `render-trigger.ts --show wonder-cabinet --art <path> --episode` for each
4. Output to `output/WC-S01-<ep>-<guest>.mp4`

Key considerations:
- Each render takes several minutes for a full episode (30-60min audio)
- The script should log progress and handle failures gracefully
- Art files need to be in `public/` for `staticFile()` resolution
- Audio needs to be accessible as a file path or `staticFile()` reference

- [ ] **Step 2: Test with a single episode (E10 Rubenstein — known good art)**

```bash
cd modules/audiogram-tools
bash scripts/batch-render.sh --episodes-dir ../../shows/wonder-cabinet/episodes --episode WC_S01_10_Rubenstein
```

- [ ] **Step 3: Run full batch (E01-E10)**

```bash
cd modules/audiogram-tools
bash scripts/batch-render.sh --episodes-dir ../../shows/wonder-cabinet/episodes
```

---

## Task 4: Verify Outputs

- [ ] **Step 1: Check all 10 MP4s rendered successfully**

```bash
ls -lh modules/audiogram-tools/output/WC-S01-*.mp4
```

- [ ] **Step 2: Spot-check frame from each video**

Extract a frame at the 30-second mark from each and visually verify:
- Green background with spiral
- Cabinet silhouette with correct episode art
- "WONDER" / "CABINET" title flanking

- [ ] **Step 3: Verify audio sync**

Play a few renders and confirm audio matches the expected episode.

---

## Notes

- **E11 (Winterer)** is excluded — needs collage art compositing and audio upload to Drive first
- **Bonus (Sun Salutation)** already has its own Remotion composition — skip
- **Audio from PRX** is the stitched version with midroll baked in — this is what goes on YouTube
- **Render time estimate:** Each full episode (30-60 min) takes ~10-20 minutes to render at 1920x1080. Full batch of 10 episodes: ~2-3 hours
- **Disk space:** Each MP4 is ~200-500MB depending on duration. Budget ~5GB for the full batch
