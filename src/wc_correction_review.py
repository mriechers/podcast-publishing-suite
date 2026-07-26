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

import base64
import html as _html
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .transcript_provenance import _normalize
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
# We distrust the timeline only when the audio is meaningfully SHORTER than the
# SRT's last cue: that means the wrong or a truncated file was loaded and clip
# offsets would point past the end of audio. Audio LONGER than the transcript is
# benign (trailing outro music) and must never suppress clips, however long.
_AUDIO_SHORTFALL_MARGIN = 2.0  # seconds of slack for rounding

_SPEAKER_PREFIX = re.compile(r"^\s*\[SPEAKER_\d+\]:\s*")
_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")

# Compare this many leading chars of the passage against each cue.
_MATCH_WINDOW = 140


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class PassageMatch:
    start: float
    confidence: float


def _parse_time(ts: str) -> float:
    match = _TIME.match(ts)
    if match is None:
        raise ValueError(f"bad SRT timestamp: {ts!r}")
    h, m, s, ms = match.groups()
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


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


@dataclass(frozen=True)
class ReviewEntry:
    episode: int
    guest: str
    passage: str
    from_label: str
    to_label: str
    timestamp: Optional[str]
    clip_data_uri: Optional[str]
    contested: bool
    confidence: Optional[float] = None


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
.confidence{color:#888;font-size:.8rem;margin-left:.4rem}
.confidence-warn{color:#b00;font-weight:600}
h2{margin-top:2rem;border-bottom:2px solid #eee;padding-bottom:.3rem}
"""


def _card_html(e: ReviewEntry) -> str:
    badge = '<span class="badge">CONTESTED — needs your call</span>' if e.contested else ""
    labels = (
        f'<div class="labels"><span class="from">{_html.escape(e.from_label)}</span>'
        f' → <span class="to">{_html.escape(e.to_label)}</span>{badge}</div>'
    )
    if e.timestamp is not None:
        confidence_note = ""
        if e.confidence is not None:
            score = f"{e.confidence:.2f}"
            if e.confidence < 0.65:
                confidence_note = (
                    f' <span class="confidence confidence-warn">'
                    f'match {score} — verify by ear</span>'
                )
            else:
                confidence_note = (
                    f' <span class="confidence">match {score}</span>'
                )
        meta = f'<div class="meta">@ {_html.escape(e.timestamp)}{confidence_note}</div>'
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


# ---------------------------------------------------------------------------
# I/O layer: episode/audio resolution, stitching, clip extraction, orchestration
# ---------------------------------------------------------------------------


def _index() -> dict:
    return json.loads((_MANIFEST_DIR / "_INDEX.json").read_text())


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
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("ffprobe failed (rc=%d) for %s", result.returncode, path.name)
    return float(result.stdout.strip()) if result.stdout.strip() else 0.0


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
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
             "-c", "copy", str(stitched)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.warning(
                "ffmpeg concat failed (rc=%d) for episode dir %s",
                result.returncode, episode_dir.name,
            )
    finally:
        os.unlink(listfile)
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
        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ss:.2f}", "-t", f"{DURATION:.2f}",
             "-i", str(audio_path), "-ac", "1", "-b:a", "48k", str(out)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.warning(
                "ffmpeg clip failed (rc=%d) for %s at %.2fs",
                result.returncode, audio_path.name, start,
            )
        if not out.exists():
            # ffmpeg failed to produce the clip: degrade to no-clip rather than
            # crashing the whole review pass with FileNotFoundError.
            return ""
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
    slug_to_ep = {e["slug"]: e["episode"] for e in idx["episodes"]}
    target = slugs or [e["slug"] for e in idx["episodes"]]
    entries: list[ReviewEntry] = []
    located = clipped = total = 0

    for slug in target:
        ep = slug_to_ep.get(slug)
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
                shortfall = cues[-1].end - audio_duration(audio_path)
                if shortfall > _AUDIO_SHORTFALL_MARGIN:
                    logger.warning(
                        "%s: audio %s ends %.1fs before the SRT's last cue — "
                        "wrong/short file, timestamp-only",
                        slug, audio_path.name, shortfall)
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
                if data_uri:
                    clipped += 1
            entries.append(ReviewEntry(
                episode=ep or 0, guest=slug_to_guest.get(slug, slug),
                passage=passage, from_label=frm, to_label=to,
                timestamp=ts, clip_data_uri=data_uri, contested=contested,
                confidence=match.confidence if match else None))

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
