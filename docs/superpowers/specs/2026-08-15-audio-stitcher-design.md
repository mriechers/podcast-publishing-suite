# Audio Stitcher — pre-publishing segment assembly

*2026-08-15*

## Problem

Joining a show's segments into one deliverable already happened twice in this
repo, both times inside the *publisher*, both times with the structure
hardcoded:

- `modules/prx-to-ghost-publisher/src/main.py` `download_media_segments()` —
  concatenates PRX Dovetail's `media[]` array in array order. Post-publishing;
  never sees local files.
- `modules/prx-to-ghost-publisher/src/wc_correction_review.py`
  `ensure_stitched()` — joins local part01/midroll/part02, but hardcodes the
  producer globs `*mix_01` / `*midroll` / `*mix_02`, doesn't know the canonical
  names `scripts/resolve_audio.py` writes, and returns `None` when a part is
  missing.

Neither is reusable for another show, because neither expresses structure as
data. This adds a pre-publishing step that does.

## Design

### Structure is data, in the show folder

`shows/<slug>/config.json` gains a `stitch` block: an **ordered** list of
slots, each either an `asset` (a file the show owns) or an `episode` file
located by a `match` pattern. Full field contract in `shows/README.md`.

One grammar covers both structures in play — Wonder Cabinet's
`segment_a` / `midroll` / `segment_b` and the PBS Wisconsin shows'
`intro` / `program` / `outro` — so no repeatable-body grammar was needed.

### `scripts/stitch_audio.py`

Split along the convention set by the correction-review work: **pure logic is
unit-tested, the ffmpeg layer is verified by a real run.**

Pure core — `load_stitch_spec`, `resolve_slots`, `plan_encoding`,
`build_filter_graph`, `concat_list_text`. I/O layer — `require_binaries`,
`probe`, `run_stitch`, `verify_output`.

Three behaviours worth calling out:

**Resolution fails loudly and completely.** Every problem is accumulated and
reported in one message, the idiom borrowed from `classify_parts()` in
`scripts/resolve_audio.py`. A stitch with a segment silently dropped or
reordered sounds correct for its first minute and is wrong thereafter — the
failure that reaches air. Precedence is `--slot` override → `match` pattern →
asset `file`. An override *supersedes* the file its pattern would have taken,
so that file stops counting as an orphan; a genuinely stray file still fails.

**Stream copy is gated on three conditions, not one.** No fades requested,
every input agreeing on codec/rate/channels, *and* the output container
accepting that codec unchanged. Both prior implementations skip the last two
and `-c copy` unconditionally, which can emit a file with drifting timing. The
PBS Wisconsin masters are 24-bit/48k WAV bound for a 44.1k MP3, so in practice
they always take the re-encode path — a check that only compared inputs to
each other would have got this wrong.

**The deliverable stays inside the show folder.** `--episode <slug>` derives
both the input directory and the output path from the show's `episodes` block,
so the normal invocation names a show and an episode and nothing else. Two
consequences worth noting: the output lands beside the very files it was made
from and matches the same `match` pattern as its source body, so
`scan_candidates` excludes it — without that, a second run fails as ambiguous.
And `episodes.localPath` is honoured when absolute, which is the seam for
relocating a show's folder outside the repo later without a code change.

**The output length is verified.** Measured duration is compared against the
sum of the inputs; a drift past 2s exits non-zero with the file retained. This
mirrors the shortfall guard in `wc_correction_review.py` and is what catches a
dropped segment.

### `scripts/ingest_scan.py` — intake

The stitcher assumes the pieces are already on disk. Intake is what puts them
there, driven by an `ingest` block in the same show config: listing URL, an
`episodePattern` matched against filename stems, and an extension → `{dest,
required}` artifact map. Two subcommands — `discover` (what's on the server
that isn't local yet) and `fetch` (pull one episode's artifacts into its
folder).

**It owns its own scanning.** Cardigan's `editorial-assistant` MCP exposes an
indexed mmingest feed that at first looked ideal — timestamps, show-name
resolution, artifact URLs. It was rejected: it is another product's internal
service, and it keys on the strict 8-character Media ID grammar, so
`HAN2507MCROSS` does not appear in it at all (`prefix=HAN2` returns nothing,
and the `6HNS` short-form entries index with a URL where the media ID belongs).
A publishing pipeline should not break when another repo's server changes.
The listings are plain Apache FancyIndexing tables; stdlib `urllib` and one
regex cover it, with no new dependencies — matching the deliberate
"plain `python3`, no venv" choice already made for `apply_glossary.py`.

Details that came out of the real data:

- **Revisions stay separate.** `6INF0121` and `6INF0121_REV20260409` are
  distinct episodes with distinct folders, flagged as sharing a base. Merging
  them would risk stitching the superseded cut.
- **Required-but-absent is reported, not guessed.** Older In Focus episodes
  have aged their `.wav` off the server while keeping captions; those are
  listed as `MISSING .wav` and refuse to fetch.
- **Downloads stream to `.part` and rename.** That is what makes the
  skip-if-exists behaviour safe — an interrupted pull never leaves a truncated
  file that looks complete. Content-Length is checked before the rename.
- **Path math is shared, not duplicated.** `episode_dirs()` lives in
  `stitch_audio.py` and is imported here; two copies is how the downloader and
  the stitcher would quietly stop agreeing on where an episode lives.

**AirTable is not wired up, and the blocker is registration.** The first
diagnosis — "the env vars are unset" — was wrong. `lodge-doctor` answers
directly: `AIRTABLE_API_KEY` is *not registered with backend=infisical*, so
setting `INFISICAL_TOKEN` would not have helped. The key exists only in the
macOS keychain, unreadable from any agent process (rc=36).

Two things came out of chasing it. `.mcp.json.disabled` carries a ready config
that resolves through `get-secret.sh` instead of the raw
`security find-generic-password` call the parent workspace uses — that raw call
is what the workspace convention forbids, and it is why AirTable works by hand
and fails for agents. And `get-secret.sh` itself reports a locked keychain item
as "not found", filed as the-lodge#707; its remediation text even suggests
re-adding a secret that is already present and correct.

The `ingest` block is where an AirTable lookup attaches once access is sorted.

## Evidence from the production archive

Read from `/Volumes/WPM SSD/PBSWI/Podcasts` and the Pro Tools sessions.

**In Focus.** `INFOCUS_INTRO.wav` (11.520s) and `INFOCUS_OUTRO.wav` (16.997s),
24-bit/48k stereo. The session for episode 121 references exactly those two
plus the episode body, confirming the three-slot structure. Delivered episodes
are MP3 / 44.1k / stereo / 192kbps — the encode targets now pinned in the show
config.

**The Pro Tools sessions are the authoritative source, and they are readable.**
These `.ptx` files are unobfuscated (`0x03` followed by the plain version
bitstring), so [`ptformat`](https://github.com/zamaudio/ptformat) parses them
directly — `clang++ -o ptftool -I. -w ptftool.cc ptformat.cc`. Its final
output section lists every timeline region as
`@ <absolute> + <into-sample>, <length>` in samples. Reading the sessions
replaced inference from delivered durations, which had been misleading: the
5–10s shortfall measured across 16 delivered episodes turned out to be two
unrelated things (a small outro overlap plus a trailing trim), not one rule.

**In Focus is very nearly a butt-splice already.** From sessions 119, 120 and
121 (48 kHz, both bookends used whole, unedited):

| Episode | Intro→body overlap | Body→outro overlap |
|---|---|---|
| 119 | 0.181s | 0.293s |
| 120 | 0.373s | 4.141s |
| 121 | 0.384s | 4.301s |

The head overlap is sub-0.4s — inaudible, effectively a splice. The tail
overlap swings between 0.3s and 4.3s across consecutive episodes, so it is
hand-placed by ear, not a rule that could be encoded. A butt-spliced stitch is
therefore faithful at the head and differs at the tail only by an overlap the
producer improvises. Sessions 101–110 predate the standalone bookend files and
cut their intro/outro out of `6INF0102.wav` instead; only 119+ use
`INFOCUS_INTRO.wav` / `INFOCUS_OUTRO.wav`.

**McCoshen & Ross bookends were recovered from the sessions.** No discrete
files exist — every session pulls two regions from `HN_podcast_headers_ALL.WAV`
(165.9s, a compilation of headers for several Here & Now podcasts, continuous
with no silence at -30dB/0.4s, so it cannot be split by detection). Across all
ten sessions, seasons 2151 through 2501, the source offsets are **identical**:

| Element | Source offset | Length |
|---|---|---|
| Intro | 5,965,696 samples (124.285s) | 517,760 samples (10.787s) |
| Outro | 6,521,216 samples (135.859s) | 1,003,648 samples (20.909s) |

Cut with `atrim` at those sample counts (exact commands in `shows/README.md`).
Head and tail overlaps here run 0.5–1.5s and 0.07–1.45s respectively —
again hand-placed, again small.

**Ingest naming**, which the `match` patterns are built against:
`6INF01NN.wav` (revisions `_REV<YYYYMMDD>`) at
`mmingest.pbswi.wisc.edu/InFocus/`, and `HAN<season><week>MCROSS.wav` at
`mmingest.pbswi.wisc.edu/HereNow/`, where it sits among every other HAN
segment.

## Decisions

| Question | Decision |
|---|---|
| Segment model | Fixed ordered slots, declared per show |
| Slot source | Per-slot `asset` or `episode`; `--slot` overrides either |
| Joins | Hard butt-splice, optional per-slot fades. No crossfade |
| Loudness | None. Concatenation only |
| Input contract | Folder scan against patterns; `--slot` pins what it can't resolve |
| Placement | In-repo `scripts/` + `/stitch-audio`, not a new module |
| `shows/` in git | Allowlist: `config.json` / `brand.json` / `glossary.json` tracked, all media ignored |

## Known gaps

- **No overlap/crossfade support.** Both shows currently tuck the outro under
  the end of the body by a hand-placed amount (In Focus 0.3–4.3s, McCoshen &
  Ross 0.07–1.45s). A butt-splice is faithful at the head and slightly long at
  the tail. If that seam matters, the schema would need a per-join
  `overlapMs` and the concat filter would have to become `acrossfade`.
- **Show media is local-only state.** `.gitignore` allowlists
  `shows/*/config.json`, `brand.json`, and `glossary.json` and ignores
  everything else under a show folder, so structural definitions are versioned
  while no audio can reach GitHub. Media still has to be rebuilt from the
  production archive rather than pulled; `shows/README.md` holds the recipes,
  and `--dry-run` names any missing file exactly.
- **No manifest integration.** The output now lands in the episode folder, so
  writing `files.stitched` into that episode's `manifest.json` is the natural
  next step — deliberately left out of this change. Note the
  `"order": "playback"` trust problem before reading anything back out of a
  manifest (CLAUDE.md records E10–E18 holding parts in lexical order).
- **Show folders are repo-relative by default.** `episodes.localPath` accepts
  an absolute path, but the show folder itself (`shows/<slug>/`, and therefore
  `assets/`) is still resolved under the repo root. Moving a whole show
  package onto external storage would need that resolution made configurable
  too.
- **`ensure_stitched()` is not retired.** It can be, once Wonder Cabinet has a
  `stitch` block.
- **`shows/wonder-cabinet/` and `shows/luminous/` do not exist in this fork**,
  along with the `.claude/commands/` that CLAUDE.md documents. Unrelated to
  this change, worth an issue.
