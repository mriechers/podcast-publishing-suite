# WC Speaker-Correction Review Page — Design

**Date:** 2026-06-20
**Status:** Approved (brainstorm), pending implementation plan
**Related:** `planning/wonder-cabinet-live-transcript-correction-plan.md` (step 0c — producer sign-off surface), `planning/wonder-cabinet-speaker-flip-audit.md`, `modules/prx-to-ghost-publisher/src/wc_transcript_corrector.py`

## Problem

The 22 producer-authoritative speaker-label corrections (plus 2 contested Macfarlane host/guest flips) are currently only machine-readable JSON manifests in `planning/transcript-corrections/`. Before any correction is applied to the live site (the next gate in the plan), producers Anne/Steve need to **sign off** — and for host↔guest flips, the only reliable confirmation is hearing who actually speaks the line. There is no producer-facing surface today, and the contested Macfarlane flips explicitly need audio adjudication.

## Goal

Generate a single, self-contained review artifact that lets a producer confirm each speaker-label correction **by ear**, with a timestamp anchor into the episode and a press-play audio clip — no repo access, no broken links, no hosting.

## Solution Overview

A standalone generator produces one self-contained `.html` file. Each correction is a card:

- the passage of dialogue,
- `current label → corrected label`,
- the episode timestamp (e.g. `24:18`),
- an inline `<audio>` player whose ~25s clip is **embedded as base64** (so the file is portable and unbreakable),
- a status badge: producer-authoritative vs **CONTESTED — needs your call**.

Producers open it in any browser, play each clip, and confirm. The corrector (already built) runs *after* sign-off; this artifact is a pre-sign-off step and stays **standalone** — separate command, no change to the corrector.

## Scope

- **In:** all 22 producer-authoritative corrections (E05 Bergland ×9, E06 Macfarlane ×5, E12 Henderson ×4, E14 Koch ×4) + the 2 contested E06 host/guest flips from `contested_internal_consistency`. 24 cards across 4 episodes.
- **Out:** the 11 clean episodes; applying corrections (that's the corrector); any change to publish flow.

## Components (isolation & testing)

Lives at `modules/prx-to-ghost-publisher/src/wc_correction_review.py`, mirroring the corrector's pure-logic/thin-I/O split.

### Pure logic — unit-tested
1. **SRT parse** — `parse_srt(text) -> list[Cue]` where `Cue = (index, start_seconds, end_seconds, text)`. Ignores the SRT's `[SPEAKER_0X]` labels entirely (they are the unreliable diarization).
2. **Passage location** — `locate_passage(cues, passage) -> Optional[Match]` returning `(start_seconds, confidence)`. Matches the passage's normalized **opening words** against cue text (the manifest passage is *edited* prose; the SRT is raw Whisper, so opening-word + normalization is the robust anchor). Reuses `transcript_provenance._normalize`. Returns `None` (not a guess) when no confident match exists.
3. **Timestamp format** — `format_timestamp(seconds) -> "M:SS"` / `"H:MM:SS"`.
4. **HTML render** — `render_review_html(entries) -> str`. Pure string assembly from a list of plain dataclasses (passage, from/to label, timestamp-or-None, clip-data-uri-or-None, contested flag). No I/O.

### Thin I/O — not unit-tested (same convention as the corrector's Ghost calls)
5. **Episode resolution** — slug → folder via `_INDEX.json` episode number → glob `shows/wonder-cabinet/episodes/WC_S01_<NN>_*`. Picks the audio file: existing `stitched.mp3` / `*_full.mp3`; for Koch, `ensure_stitched()` ffmpeg-concats `mix_01 + midroll + mix_02`.
6. **Koch stitch + verification** — concat parts to `stitched.mp3`, then verify alignment by cutting the cue at `00:00` ("Welcome to Wonder Cabinet") and confirming a sane offset before trusting later timestamps. Abort Koch clips (fall back to timestamp-only cards) if verification fails — never emit a misaligned clip.
7. **Clip extraction** — `extract_clip(audio_path, start_seconds) -> bytes`: ffmpeg cut starting `LEAD_IN` (~4s, clamped at 0) before the matched cue, `DURATION` ~25s, mono low-bitrate mp3. Returned bytes are base64-embedded into the HTML as a `data:audio/mpeg;base64,…` URI.

### Orchestrator
8. `build_review(slugs, out_path) -> Path`: load manifests → resolve episode + SRT + audio → locate each passage → cut clip → assemble entries → write HTML. Logs any passage that couldn't be located or clipped (no silent truncation).

## CLI

```
python -m src.wc_correction_review                 # all 4 episodes from _INDEX.json
python -m src.wc_correction_review --slug <slug>    # one episode
python -m src.wc_correction_review --no-clips       # timestamp-only (skip ffmpeg)
```

Output: `planning/transcript-corrections/review/2026-06-20-wc-speaker-corrections-review.html`.

## Data flow

```
_INDEX.json ─► slugs ─► load_manifest(slug) ─► corrections_from_manifest()
                         + contested_internal_consistency entries
   each correction.passage
        └─► locate_passage(parse_srt(captions.srt)) ─► (start, confidence)
                 └─► extract_clip(resolve_audio(episode)) ─► mp3 bytes ─► base64
   entries ─► render_review_html ─► write .html ─► deliver to user
```

## Error handling / safety

- **No wrong anchors:** unlocatable passage → card shows "timestamp not auto-located — please scrub manually"; no clip. Never a guessed time.
- **No misaligned clips:** Koch clips only emitted if the 00:00 verification passes.
- **No silent gaps:** the run logs a summary (located N/24, clipped M/24) so a missing clip is visible, not hidden.
- **Fail-soft per card:** one episode's missing audio/SRT degrades only its cards (timestamp-only or text-only), never aborts the whole page.
- **ffmpeg dependency:** required for clips; `--no-clips` path needs only the SRTs.

## Artifact handling

- Output dir `planning/transcript-corrections/review/` added to `.gitignore` (the HTML carries multi-MB base64 audio — a generated artifact, not source).
- The reconstructed Koch `stitched.mp3` stays in its episode `audio/` folder (already gitignored by the suite's mp3 rule).

## Testing

TDD. Unit tests for: SRT parsing (incl. multi-line cues, `H:MM:SS`), passage location (exact, opening-word-with-edited-tail, no-match → None, smart-quote tolerance), timestamp formatting, HTML render (card structure, contested badge, timestamp-absent and clip-absent fallbacks). ffmpeg clip/stitch and base64 embedding are exercised by a real run against the four episodes, not unit tests.

## Out of scope / future

- Wiring review-generation into the corrector (chosen: standalone for now).
- Producer response capture (they confirm out-of-band: Slack/Doc/email). A future iteration could add checkboxes + an export, but YAGNI now.
