# WC Speaker-Correction Review Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a single self-contained HTML page where producers confirm each WC speaker-label correction by ear, via a timestamp anchor and an embedded audio clip.

**Architecture:** A standalone module in the `prx-to-ghost-publisher` submodule, mirroring the existing corrector's pure-logic/thin-I/O split. Pure units (SRT parse, fuzzy passage→time location, timestamp format, HTML render) are TDD'd; ffmpeg clip/stitch + base64 embedding are thin I/O verified by a real run against the four episodes.

**Tech Stack:** Python 3.11+, stdlib only for the pure logic (`re`, `difflib`, `dataclasses`, `html`, `base64`), `ffmpeg`/`ffprobe` (already on PATH) for audio. pytest via `.venv/bin/pytest`.

## Global Constraints

- Working directory for all commands: `modules/prx-to-ghost-publisher/` (run tests as `.venv/bin/pytest`).
- New module: `src/wc_correction_review.py`; new test: `tests/test_wc_correction_review.py`.
- Reuse, do not duplicate: `transcript_provenance._normalize` (smart-quote/whitespace normalization) and `wc_transcript_corrector.{load_manifest, corrections_from_manifest, _MANIFEST_DIR}`.
- Pure logic is unit-tested; ffmpeg/ffprobe I/O is NOT unit-tested (verified by real run), matching the convention in `transcript_provenance.py` and `wc_transcript_corrector.py`.
- The SRT's own `[SPEAKER_0X]:` labels are unreliable diarization — strip them on parse, never surface them.
- Never emit a guessed timestamp or a misaligned clip. Unlocatable passage → timestamp-only card; audio whose duration doesn't match the SRT timeline → timestamp-only for that whole episode.
- Clip parameters: `LEAD_IN = 4.0` seconds (clamped at 0), `DURATION = 25.0` seconds, mono, `-b:a 48k`.
- Episodes in scope come from `planning/transcript-corrections/_INDEX.json`: 5 Bergland, 6 Macfarlane, 12 Henderson, 14 Koch.
- Commit convention (this submodule): subject line, blank line, `[Agent: <name>]`, body, then the Claude trailers. Keep commits per-task.

---

### Task 1: SRT parsing

**Files:**
- Create: `src/wc_correction_review.py`
- Test: `tests/test_wc_correction_review.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Cue` dataclass `(index: int, start: float, end: float, text: str)` where `text` has the `[SPEAKER_0X]:` prefix stripped; `parse_srt(text: str) -> list[Cue]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wc_correction_review.py
from __future__ import annotations

from src.wc_correction_review import Cue, parse_srt


class TestParseSrt:
    def test_parses_cues_and_strips_speaker_labels(self):
        srt = (
            "1\n"
            "00:00:00,547 --> 00:00:01,927\n"
            "[SPEAKER_00]: Welcome to Wonder Cabinet.\n"
            "\n"
            "2\n"
            "00:01:05,000 --> 00:01:08,500\n"
            "[SPEAKER_01]: And I'm Steve Paulson.\n"
        )
        cues = parse_srt(srt)
        assert cues == [
            Cue(index=1, start=0.547, end=1.927, text="Welcome to Wonder Cabinet."),
            Cue(index=2, start=65.0, end=68.5, text="And I'm Steve Paulson."),
        ]

    def test_joins_multiline_cue_text(self):
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "[SPEAKER_00]: First line\n"
            "second line\n"
        )
        cues = parse_srt(srt)
        assert cues[0].text == "First line second line"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py -v`
Expected: FAIL — `ImportError: cannot import name 'Cue'` (module/symbols not defined).

- [ ] **Step 3: Write minimal implementation**

```python
# src/wc_correction_review.py
"""Wonder Cabinet speaker-correction review page generator.

Produces a single self-contained HTML file where producers confirm each
speaker-label correction by ear: passage, current->corrected label, an episode
timestamp, and an inline audio clip embedded as base64.

Pure logic (SRT parse, fuzzy passage location, timestamp format, HTML render)
is unit-tested. ffmpeg/ffprobe clip + stitch and base64 embedding are thin I/O,
verified by a real run against the four episodes (mirrors transcript_provenance
and wc_transcript_corrector).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SPEAKER_PREFIX = re.compile(r"^\s*\[SPEAKER_\d+\]:\s*")
_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    text: str


def _parse_time(ts: str) -> float:
    h, m, s, ms = _TIME.match(ts).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip() != ""]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        index = int(lines[0].strip())
        start_s, end_s = [p.strip() for p in lines[1].split("-->")]
        body = " ".join(lines[2:])
        body = _SPEAKER_PREFIX.sub("", body).strip()
        cues.append(Cue(index, _parse_time(start_s), _parse_time(end_s), body))
    return cues
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wc_correction_review.py tests/test_wc_correction_review.py
git commit -m "feat: SRT parsing for correction review page

[Agent: Main Assistant]

Parse captions.srt into timestamped cues, stripping the unreliable
[SPEAKER_0X] diarization labels."
```

---

### Task 2: Fuzzy passage → timestamp location

**Files:**
- Modify: `src/wc_correction_review.py`
- Test: `tests/test_wc_correction_review.py`

**Interfaces:**
- Consumes: `Cue`, `parse_srt` (Task 1); `transcript_provenance._normalize`.
- Produces: `PassageMatch` dataclass `(start: float, confidence: float)`; `locate_passage(cues: list[Cue], passage: str, *, min_ratio: float = 0.5) -> Optional[PassageMatch]`. Returns the cue whose text best matches the passage opening; `None` when the best ratio is below `min_ratio`.

**Why fuzzy:** manifest passages are producer-*edited* prose; the SRT is raw Whisper. Real example — manifest "William James, one of the **great** writers - the father of American psychology - wrote this beautiful book in 1902" vs SRT "So William James, one of the **best** writers, you know, the American sort of father of American psychology, wrote this beautiful book in 1902". Words drift inside the opening, so match by token-level ratio over a leading window, not an exact prefix.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_wc_correction_review.py
import pytest

from src.wc_correction_review import PassageMatch, locate_passage


# Real strings: Koch manifest passage opening vs the raw SRT cue (edit drift).
_KOCH_CUE = (
    "So William James, one of the best writers, you know, the American sort of "
    "father of American psychology, wrote this beautiful book in 1902, The "
    "Varieties of Religious Experiences, which is essentially a large part of "
    "that has to do with these, what he called religious experiences."
)
_KOCH_PASSAGE = (
    "William James, one of the great writers - the father of American psychology "
    "- wrote this beautiful book in 1902, The Varieties of Religious Experience, "
    "which is essentially largely about what he called religious experiences."
)


class TestLocatePassage:
    def test_matches_despite_edit_drift(self):
        cues = [
            Cue(1, 0.0, 3.0, "Welcome to Wonder Cabinet."),
            Cue(2, 1462.0, 1490.0, _KOCH_CUE),
        ]
        match = locate_passage(cues, _KOCH_PASSAGE)
        assert match is not None
        assert match.start == 1462.0
        assert match.confidence >= 0.5

    def test_returns_none_when_no_cue_is_close(self):
        cues = [
            Cue(1, 0.0, 3.0, "Welcome to Wonder Cabinet."),
            Cue(2, 10.0, 14.0, "Completely unrelated chatter about the weather today."),
        ]
        match = locate_passage(cues, _KOCH_PASSAGE)
        assert match is None

    def test_picks_best_of_several_cues(self):
        cues = [
            Cue(1, 5.0, 8.0, "William James was a person, broadly speaking."),
            Cue(2, 1462.0, 1490.0, _KOCH_CUE),
        ]
        match = locate_passage(cues, _KOCH_PASSAGE)
        assert match.start == 1462.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py::TestLocatePassage -v`
Expected: FAIL — `ImportError: cannot import name 'PassageMatch'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/wc_correction_review.py
from difflib import SequenceMatcher
from typing import Optional

from .transcript_provenance import _normalize

# Compare this many leading chars of the passage against each cue.
_MATCH_WINDOW = 140


@dataclass(frozen=True)
class PassageMatch:
    start: float
    confidence: float


def _norm_lower(s: str) -> str:
    return _normalize(s).lower()


def locate_passage(
    cues: list[Cue], passage: str, *, min_ratio: float = 0.5
) -> Optional[PassageMatch]:
    needle = _norm_lower(passage)[:_MATCH_WINDOW]
    best_start = 0.0
    best_ratio = 0.0
    for cue in cues:
        hay = _norm_lower(cue.text)[: _MATCH_WINDOW + 40]
        ratio = SequenceMatcher(None, needle, hay).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = cue.start
    if best_ratio < min_ratio:
        return None
    return PassageMatch(start=best_start, confidence=best_ratio)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py::TestLocatePassage -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wc_correction_review.py tests/test_wc_correction_review.py
git commit -m "feat: fuzzy passage->timestamp location

[Agent: Main Assistant]

Match an edited manifest passage to its raw-Whisper SRT cue by
token-level ratio over a leading window; return None below threshold
rather than guessing."
```

---

### Task 3: Timestamp formatting

**Files:**
- Modify: `src/wc_correction_review.py`
- Test: `tests/test_wc_correction_review.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `format_timestamp(seconds: float) -> str` — `"M:SS"` under an hour, `"H:MM:SS"` at/over an hour.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_wc_correction_review.py
from src.wc_correction_review import format_timestamp


class TestFormatTimestamp:
    def test_under_an_hour(self):
        assert format_timestamp(1462.0) == "24:22"

    def test_pads_seconds(self):
        assert format_timestamp(65.0) == "1:05"

    def test_over_an_hour(self):
        assert format_timestamp(3725.0) == "1:02:05"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py::TestFormatTimestamp -v`
Expected: FAIL — `ImportError: cannot import name 'format_timestamp'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/wc_correction_review.py
def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py::TestFormatTimestamp -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wc_correction_review.py tests/test_wc_correction_review.py
git commit -m "feat: timestamp formatting for review cards

[Agent: Main Assistant]"
```

---

### Task 4: HTML render

**Files:**
- Modify: `src/wc_correction_review.py`
- Test: `tests/test_wc_correction_review.py`

**Interfaces:**
- Consumes: nothing (operates on plain dataclasses).
- Produces: `ReviewEntry` dataclass with fields `episode: int`, `guest: str`, `passage: str`, `from_label: str`, `to_label: str`, `timestamp: Optional[str]`, `clip_data_uri: Optional[str]`, `contested: bool`; `render_review_html(entries: list[ReviewEntry]) -> str`.

Rendering rules: one card per entry; show `from_label → to_label`; if `contested` show a "CONTESTED — needs your call" badge; if `timestamp` is None show "timestamp not auto-located — please scrub manually"; if `clip_data_uri` is None render no `<audio>`; escape passage/labels with `html.escape`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_wc_correction_review.py
from src.wc_correction_review import ReviewEntry, render_review_html


def _entry(**kw):
    base = dict(
        episode=14, guest="Christof Koch", passage="William James wrote a book.",
        from_label="Steve Paulson", to_label="Christof Koch",
        timestamp="24:22", clip_data_uri="data:audio/mpeg;base64,AAAA",
        contested=False,
    )
    base.update(kw)
    return ReviewEntry(**base)


class TestRenderReviewHtml:
    def test_card_shows_passage_labels_and_timestamp(self):
        html_out = render_review_html([_entry()])
        assert "William James wrote a book." in html_out
        assert "Steve Paulson" in html_out and "Christof Koch" in html_out
        assert "24:22" in html_out
        assert "<audio" in html_out
        assert "data:audio/mpeg;base64,AAAA" in html_out

    def test_contested_badge(self):
        html_out = render_review_html([_entry(contested=True)])
        assert "CONTESTED" in html_out

    def test_missing_timestamp_shows_scrub_note(self):
        html_out = render_review_html([_entry(timestamp=None, clip_data_uri=None)])
        assert "scrub manually" in html_out
        assert "<audio" not in html_out

    def test_escapes_html_in_passage(self):
        html_out = render_review_html([_entry(passage="a < b & c")])
        assert "a &lt; b &amp; c" in html_out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py::TestRenderReviewHtml -v`
Expected: FAIL — `ImportError: cannot import name 'ReviewEntry'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/wc_correction_review.py
import html as _html


@dataclass
class ReviewEntry:
    episode: int
    guest: str
    passage: str
    from_label: str
    to_label: str
    timestamp: Optional[str]
    clip_data_uri: Optional[str]
    contested: bool


_PAGE_CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:820px;
margin:2rem auto;padding:0 1rem;color:#1a1a1a;background:#faf9f7}
.card{border:1px solid #ddd;border-radius:10px;padding:1rem 1.25rem;margin:1rem 0;
background:#fff}
.labels{font-weight:600;margin:.25rem 0}.from{color:#b00}.to{color:#070}
.meta{color:#666;font-size:.9rem}.passage{margin:.6rem 0;line-height:1.5}
.badge{display:inline-block;background:#fde68a;color:#7c4a00;border-radius:6px;
padding:.1rem .5rem;font-size:.8rem;font-weight:700;margin-left:.5rem}
.scrub{color:#a15c00;font-style:italic}audio{width:100%;margin-top:.5rem}
h2{margin-top:2rem;border-bottom:2px solid #eee;padding-bottom:.3rem}
"""


def _card_html(e: ReviewEntry) -> str:
    badge = '<span class="badge">CONTESTED — needs your call</span>' if e.contested else ""
    labels = (
        f'<div class="labels"><span class="from">{_html.escape(e.from_label)}</span>'
        f' → <span class="to">{_html.escape(e.to_label)}</span>{badge}</div>'
    )
    if e.timestamp:
        meta = f'<div class="meta">@ {_html.escape(e.timestamp)}</div>'
    else:
        meta = '<div class="meta scrub">timestamp not auto-located — please scrub manually</div>'
    audio = (
        f'<audio controls preload="none" src="{e.clip_data_uri}"></audio>'
        if e.clip_data_uri else ""
    )
    return (
        '<div class="card">'
        f"{labels}{meta}"
        f'<div class="passage">{_html.escape(e.passage)}</div>'
        f"{audio}</div>"
    )


def render_review_html(entries: list[ReviewEntry]) -> str:
    by_ep: dict[tuple[int, str], list[ReviewEntry]] = {}
    for e in entries:
        by_ep.setdefault((e.episode, e.guest), []).append(e)
    sections = []
    for (ep, guest), items in sorted(by_ep.items()):
        cards = "\n".join(_card_html(e) for e in items)
        sections.append(f"<h2>Episode {ep} — {_html.escape(guest)}</h2>\n{cards}")
    body = "\n".join(sections)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>WC speaker-label corrections — producer review</title>"
        f"<style>{_PAGE_CSS}</style></head><body>"
        "<h1>Wonder Cabinet — speaker-label corrections for review</h1>"
        "<p>Play each clip and confirm the corrected speaker. Contested items "
        "need your decision.</p>"
        f"{body}</body></html>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_wc_correction_review.py::TestRenderReviewHtml -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wc_correction_review.py tests/test_wc_correction_review.py
git commit -m "feat: HTML render for correction review page

[Agent: Main Assistant]

One card per correction with labels, timestamp, contested badge, and
inline audio; degrades to a scrub note when no timestamp is found."
```

---

### Task 5: Audio I/O, orchestration, CLI, and real run

**Files:**
- Modify: `src/wc_correction_review.py`
- Modify: `../../.gitignore` (suite root — add review output dir)

**Interfaces:**
- Consumes: everything above; `wc_transcript_corrector.{load_manifest, corrections_from_manifest, _MANIFEST_DIR}`.
- Produces (thin I/O, not unit-tested): `resolve_episode_dir(episode: int) -> Path`; `resolve_audio(episode_dir: Path) -> Optional[Path]`; `ensure_stitched(episode_dir: Path) -> Optional[Path]`; `audio_duration(path: Path) -> float`; `extract_clip_b64(audio_path: Path, start: float) -> str`; `build_review(slugs: Optional[list[str]], out_path: Path, *, clips: bool = True) -> Path`; `main()`.

This is one task: it is all glue with no pure logic to TDD, and its only meaningful verification is producing the real page. Build the functions, then run for real.

- [ ] **Step 1: Implement the I/O + orchestration**

```python
# add to src/wc_correction_review.py
import base64
import json
import logging
import subprocess
import tempfile
from pathlib import Path

from .wc_transcript_corrector import (
    _MANIFEST_DIR,
    corrections_from_manifest,
    load_manifest,
)

logger = logging.getLogger(__name__)

LEAD_IN = 4.0
DURATION = 25.0
_EPISODES_DIR = (
    Path(__file__).resolve().parents[3]
    / "shows" / "wonder-cabinet" / "episodes"
)
_REVIEW_DIR = _MANIFEST_DIR / "review"
# Max drift between chosen audio duration and the SRT's last cue end before we
# distrust the timeline and fall back to timestamp-only for that episode.
_DURATION_TOLERANCE = 8.0


def _index() -> dict:
    return json.loads((_MANIFEST_DIR / "_INDEX.json").read_text())


def _episode_number(slug: str) -> Optional[int]:
    for ep in _index().get("episodes", []):
        if ep["slug"] == slug:
            return ep["episode"]
    return None


def resolve_episode_dir(episode: int) -> Optional[Path]:
    matches = sorted(_EPISODES_DIR.glob(f"WC_S01_{episode:02d}_*"))
    return matches[0] if matches else None


def _find_srt(episode_dir: Path) -> Optional[Path]:
    cand = episode_dir / "captions.srt"
    if cand.exists():
        return cand
    others = sorted(episode_dir.glob("*.srt"))
    return others[0] if others else None


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip()) if out.stdout.strip() else 0.0


def ensure_stitched(episode_dir: Path) -> Optional[Path]:
    """Reconstruct a continuous stitched.mp3 from mix_01 + midroll + mix_02
    when no single-file audio exists (Koch). Idempotent."""
    stitched = episode_dir / "stitched.mp3"
    if stitched.exists():
        return stitched
    audio = episode_dir / "audio"
    def one(glob): 
        hits = sorted(audio.glob(glob))
        return hits[0] if hits else None
    parts = [one("*mix_01.mp3"), one("*midroll.mp3"), one("*mix_02.mp3")]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in parts:
            f.write(f"file '{p.resolve()}'\n")
        listfile = f.name
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c", "copy", str(stitched)],
        capture_output=True, text=True,
    )
    return stitched if stitched.exists() else None


def resolve_audio(episode_dir: Path) -> Optional[Path]:
    audio = episode_dir / "audio"
    for pat in ("stitched.mp3", "*_full.mp3", "*full.mp3"):
        hits = sorted(audio.glob(pat))
        if hits:
            return hits[0]
    return ensure_stitched(episode_dir)


def extract_clip_b64(audio_path: Path, start: float) -> str:
    ss = max(0.0, start - LEAD_IN)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "clip.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ss:.2f}", "-t", f"{DURATION:.2f}",
             "-i", str(audio_path), "-ac", "1", "-b:a", "48k", str(out)],
            capture_output=True, text=True,
        )
        data = out.read_bytes()
    return "data:audio/mpeg;base64," + base64.b64encode(data).decode("ascii")


def _manifest_entries(slug: str) -> list[tuple[str, str, str, bool]]:
    """Return (passage, from_label, to_label, contested) for a slug:
    producer-authoritative corrections + contested_internal_consistency."""
    m = load_manifest(slug)
    out: list[tuple[str, str, str, bool]] = []
    for c in corrections_from_manifest(m):
        out.append((c.passage, c.from_label, c.to_label, False))
    for c in m.get("contested_internal_consistency", []):
        out.append((c["passage"], c["current_web_label"],
                    c["internal_consistency_label"], True))
    return out


def build_review(slugs, out_path: Path, *, clips: bool = True) -> Path:
    idx = _index()
    slug_to_guest = {e["slug"]: e["guest"] for e in idx["episodes"]}
    target = slugs or [e["slug"] for e in idx["episodes"]]
    entries: list[ReviewEntry] = []
    located = clipped = total = 0

    for slug in target:
        ep = _episode_number(slug)
        ep_dir = resolve_episode_dir(ep) if ep else None
        cues = []
        if ep_dir:
            srt = _find_srt(ep_dir)
            if srt:
                cues = parse_srt(srt.read_text())

        audio_path = None
        if clips and ep_dir and cues:
            audio_path = resolve_audio(ep_dir)
            if audio_path:
                drift = abs(audio_duration(audio_path) - cues[-1].end)
                if drift > _DURATION_TOLERANCE:
                    logger.warning(
                        "%s: audio %s drifts %.1fs from SRT end — timestamp-only",
                        slug, audio_path.name, drift)
                    audio_path = None

        for passage, frm, to, contested in _manifest_entries(slug):
            total += 1
            match = locate_passage(cues, passage) if cues else None
            ts = format_timestamp(match.start) if match else None
            if match:
                located += 1
            data_uri = None
            if match and audio_path:
                data_uri = extract_clip_b64(audio_path, match.start)
                clipped += 1
            entries.append(ReviewEntry(
                episode=ep or 0, guest=slug_to_guest.get(slug, slug),
                passage=passage, from_label=frm, to_label=to,
                timestamp=ts, clip_data_uri=data_uri, contested=contested))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_review_html(entries))
    logger.info("Review page: %s (located %d/%d, clipped %d/%d)",
                out_path, located, total, clipped, total)
    return out_path


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate the WC speaker-correction producer review page")
    parser.add_argument("--slug", action="append", help="Limit to slug(s)")
    parser.add_argument("--no-clips", action="store_true",
                        help="Timestamp-only; skip ffmpeg clip extraction")
    parser.add_argument("--out", help="Output HTML path")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    out = Path(args.out) if args.out else (
        _REVIEW_DIR / "2026-06-21-wc-speaker-corrections-review.html")
    path = build_review(args.slug, out, clips=not args.no_clips)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add the output dir to the suite .gitignore**

Append to `/Users/mriechers/Developer/wonder-cabinet/podcast-publishing-suite/.gitignore`:

```
# Generated producer-review pages (multi-MB base64 audio)
planning/transcript-corrections/review/
```

- [ ] **Step 3: Confirm the whole unit test suite is green**

Run: `.venv/bin/pytest -q`
Expected: PASS (all prior tests + the new `test_wc_correction_review.py` tests).

- [ ] **Step 4: Real run — timestamp-only first (fast, no ffmpeg)**

Run: `.venv/bin/python -m src.wc_correction_review --no-clips -v`
Expected: writes the HTML; log line `located N/24`. Inspect N — investigate any episode with 0 located (likely an SRT naming mismatch) before proceeding.

- [ ] **Step 5: Real run — full, with clips**

Run: `.venv/bin/python -m src.wc_correction_review -v`
Expected: log shows `clipped M/24`; any episode whose audio drifts from the SRT logs a "timestamp-only" warning (acceptable — those cards keep their timestamp). Open the HTML; spot-check that the Koch "William James" clip actually plays Koch's voice (validates the stitch + offset end-to-end).

- [ ] **Step 6: Commit**

```bash
git add src/wc_correction_review.py
git commit -m "feat: audio clips, orchestration, and CLI for review page

[Agent: Main Assistant]

Resolve episode audio (stitching Koch's parts when needed), verify the
audio timeline against the SRT, cut base64 clips, and assemble the
self-contained review HTML. Falls back to timestamp-only on any timeline
drift or unlocatable passage."
# Commit the .gitignore change in the suite repo separately (different repo):
# cd ../.. && git add .gitignore && git commit -m "chore: gitignore generated review pages"
```

---

## Self-Review

**Spec coverage:**
- Self-contained HTML, card per correction, timestamp + embedded clip → Task 4 (render) + Task 5 (clips). ✓
- Scope = 22 producer-authoritative + 2 contested → `_manifest_entries` reads both `corrections` and `contested_internal_consistency`. ✓
- SRT parse ignoring `[SPEAKER_0X]` → Task 1. ✓
- Fuzzy opening-anchor match, None when unconfident → Task 2. ✓
- Koch stitch + timeline verification → `ensure_stitched` + duration-drift guard in `build_review` (Task 5). Note: spec said "verify against the 00:00 cue"; the plan uses a stronger end-to-end check (chosen audio duration vs last cue end, tolerance 8s) that validates concat order/gaps for the whole timeline, then the Step 5 ear spot-check on the Koch clip confirms offset. ✓
- Clip params (4s lead-in, 25s, mono, low bitrate) → constants in Task 5. ✓
- No wrong anchors / no misaligned clips / no silent gaps → None fallback, duration guard, located/clipped logging. ✓
- Output to gitignored `planning/transcript-corrections/review/` → Task 5 Step 2. ✓
- Standalone, corrector untouched → only new module + reused helpers; no edits to `wc_transcript_corrector.py`. ✓

**Placeholder scan:** No TBD/TODO; all code shown; commands concrete. ✓

**Type consistency:** `Cue`, `PassageMatch(start, confidence)`, `ReviewEntry(...)`, `locate_passage(...) -> Optional[PassageMatch]`, `format_timestamp`, `render_review_html`, `extract_clip_b64`, `build_review` consistent across tasks. ✓

**Known deviation from spec (intentional):** stitch verification uses duration-vs-last-cue rather than a 00:00-cue cut — strictly stronger, plus the manual ear-check on the Koch clip in Task 5 Step 5.
