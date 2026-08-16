#!/usr/bin/env bash
# Backfill render of Wonder Cabinet episodes E01-E10 as 16:9 YouTube videos.
#
# Per episode:
#   1. Match guest name against PRX feed to pick up the canonical title + enclosure URL.
#   2. Download stitched.mp3 (the PRX-baked, midroll-included master) into the episode's
#      audio/ folder if not already cached.
#   3. Verify the episode's collage art exists.
#   4. Invoke render-trigger.ts with --show wonder-cabinet, writing the MP4 into the
#      episode's audiogram/ folder.
#
# Usage:
#   ./scripts/batch-render.sh                  # render E01-E10
#   ./scripts/batch-render.sh --only 10        # render just E10 (canary)
#   ./scripts/batch-render.sh --skip-existing  # skip episodes with an existing MP4
#   ./scripts/batch-render.sh --dry-run        # show plan without rendering
#
# Re-runnable: stitched audio is cached on disk, --skip-existing avoids re-renders.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIOGRAM="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$AUDIOGRAM/../.." && pwd)"
EPISODES_DIR="$REPO_ROOT/shows/wonder-cabinet/episodes"
FEED_URL="https://publicfeeds.net/f/120/wondercabinet"

# Episode table: EP|SLUG|GUEST|ART_FILE
# Guest names match what should appear in the rendered video.
# Art filenames are the curated final collage for each episode (see canonical
# plan: docs/superpowers/plans/2026-04-20-wc-youtube-batch-render.md).
EPISODES=(
  "1|WC_S01_01_Sophie_Strand|Sophie Strand|101-Sophie-Strand_v2.jpg"
  "2|WC_S01_02_Carlo_Rovelli|Carlo Rovelli|102 - Carlo.png"
  "3|WC_S01_03_Rebecca_Solnit|Rebecca Solnit|103-solnit.jpg"
  "4|WC_S01_04_George_Saunders|George Saunders|104-saunders.jpg"
  "5|WC_S01_05_Bergland|Renee Bergland|WC005-berglund.jpg"
  "6|WC_S01_06_Macfarlane|Robert Macfarlane|WC_S01_06_MacFarlane.jpg"
  "7|WC_S01_07_David_Haskell|David George Haskell|107-David-Haskell.jpg"
  "8|WC_S01_08_Manvir_Singh|Manvir Singh|WC_S01_08_Manvir_Singh_rev2.jpg"
  "9|WC_S01_09_Dekila_Chungyalpa|Dekila Chungyalpa|S1E9-art-v1.jpg"
  "10|WC_S01_10_Rubenstein|Mary-Jane Rubenstein|WC_S01_10_Rubenstein_rev2.jpg"
)

ONLY=""
SKIP_EXISTING=0
DRY_RUN=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Renders Wonder Cabinet episodes E01-E10 as 16:9 YouTube videos using
render-trigger.ts. Stitched audio is pulled from the PRX feed if missing.

Options:
  --only N         Render just episode N (1-10)
  --skip-existing  Skip episodes that already have an MP4 in audiogram/
  --dry-run        Show what would happen without downloading or rendering
  -h, --help       This help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) ONLY="$2"; shift 2;;
    --skip-existing) SKIP_EXISTING=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

# Fetch the PRX feed and build an EP -> title|url map keyed by guest match.
echo "Fetching PRX feed: $FEED_URL"

META_FILE=$(mktemp)
trap 'rm -f "$META_FILE"' EXIT

FEED_URL="$FEED_URL" python3 - > "$META_FILE" <<'PY'
import os, sys, re, urllib.request, xml.etree.ElementTree as ET

feed_url = os.environ["FEED_URL"]
try:
    with urllib.request.urlopen(feed_url, timeout=30) as resp:
        data = resp.read()
except Exception as e:
    sys.stderr.write(f"Error fetching PRX feed: {e}\n")
    sys.exit(2)

try:
    root = ET.fromstring(data)
except ET.ParseError as e:
    sys.stderr.write(f"Error parsing PRX feed XML: {e}\n")
    sys.exit(2)

# Guest substring pattern -> EP number. Patterns are matched case-insensitively
# against feed item titles. Must agree with the EPISODES array in the shell script.
GUESTS = [
    (r"Sophie Strand",   1),
    (r"Carlo Rovelli",   2),
    (r"Rebecca Solnit",  3),
    (r"George Saunders", 4),
    (r"Bergland",        5),
    (r"Macfarlane",      6),
    (r"Haskell",         7),
    (r"Manvir Singh",    8),
    (r"Dekila",          9),
    (r"Rubenstein",     10),
]
patterns = [(re.compile(p, re.I), n) for p, n in GUESTS]

for it in root.findall(".//item"):
    title = (it.findtext("title") or "").strip()
    enc = it.find("enclosure")
    url = enc.get("url") if enc is not None else ""
    for pat, ep_num in patterns:
        if pat.search(title):
            safe_title = title.replace("|", "/")  # protect field delimiter
            print(f"{ep_num}|{safe_title}|{url}")
            break
PY

if [[ ! -s "$META_FILE" ]]; then
  echo "Error: PRX feed parse produced no matches" >&2
  exit 1
fi

# Quick coverage check.
matched_eps=$(awk -F'|' '{print $1}' "$META_FILE" | sort -n | paste -sd, -)
echo "Feed matched episodes: $matched_eps"
echo

lookup_feed() {
  awk -F'|' -v ep="$1" '$1 == ep { print; exit }' "$META_FILE"
}

render_episode() {
  local row="$1"
  local ep slug guest art_file
  IFS='|' read -r ep slug guest art_file <<< "$row"

  local ep_dir="$EPISODES_DIR/$slug"
  local art_path="$ep_dir/images/$art_file"
  local stitched_path="$ep_dir/audio/stitched.mp3"
  local output_dir="$ep_dir/audiogram"

  printf '\n'
  printf '═══════════════════════════════════════════════════════════\n'
  printf '  EP%02d — %s\n' "$ep" "$guest"
  printf '═══════════════════════════════════════════════════════════\n'

  if [[ ! -d "$ep_dir" ]]; then
    echo "  ✗ Episode folder missing: $ep_dir" >&2
    return 1
  fi
  if [[ ! -f "$art_path" ]]; then
    echo "  ✗ Art file missing: $art_path" >&2
    return 1
  fi

  local feed_row title url
  feed_row=$(lookup_feed "$ep")
  if [[ -z "$feed_row" ]]; then
    echo "  ✗ No feed match for EP$ep — check guest regex in feed parser" >&2
    return 1
  fi
  IFS='|' read -r _ title url <<< "$feed_row"

  echo "  Title: $title"
  echo "  Art:   $art_file"

  if [[ "$SKIP_EXISTING" == 1 ]] && compgen -G "$output_dir/EP${ep}_*.mp4" > /dev/null 2>&1; then
    local existing
    existing=$(compgen -G "$output_dir/EP${ep}_*.mp4" | head -1)
    echo "  → Skip: existing render at $(basename "$existing")"
    return 0
  fi

  if [[ ! -f "$stitched_path" ]]; then
    if [[ "$DRY_RUN" == 1 ]]; then
      echo "  ↓ (dry-run) would download stitched audio from $url"
    else
      echo "  ↓ Downloading stitched audio…"
      mkdir -p "$(dirname "$stitched_path")"
      curl -fsSL "$url" -o "$stitched_path"
      echo "    Saved: $(du -h "$stitched_path" | cut -f1)"
    fi
  else
    echo "  ✓ Stitched audio cached: $(du -h "$stitched_path" | cut -f1)"
  fi

  mkdir -p "$output_dir"

  if [[ "$DRY_RUN" == 1 ]]; then
    echo "  ▶ (dry-run) would invoke render-trigger.ts; output → $output_dir/"
    return 0
  fi

  echo "  ▶ Rendering…"
  (
    cd "$AUDIOGRAM"
    OUTPUT_DIR="$output_dir" \
      npx tsx src/automation/render-trigger.ts "$stitched_path" \
        --episode \
        --show wonder-cabinet \
        --guest "$guest" \
        --ep "$ep" \
        --title "$title" \
        --art "$art_path"
  )
}

if [[ -n "$ONLY" ]]; then
  for row in "${EPISODES[@]}"; do
    ep_num="${row%%|*}"
    if [[ "$ep_num" == "$ONLY" ]]; then
      render_episode "$row"
      exit $?
    fi
  done
  echo "Error: --only $ONLY did not match any episode in table" >&2
  exit 1
fi

for row in "${EPISODES[@]}"; do
  render_episode "$row"
done

printf '\n✓ Batch complete.\n'
