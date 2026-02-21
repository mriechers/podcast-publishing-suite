#!/usr/bin/env python3
"""Combine multiple SRT files into a single continuous transcript.

Stitches SRT files with continuous timecodes and sequential numbering.
Optionally generates a combined plain text transcript and organizes
individual source files into a raw_transcripts/ subfolder.

Usage:
    python combine_srts.py part01.srt midroll.srt part02.srt
    python combine_srts.py part01.srt midroll.srt part02.srt --output-dir ./output --txt --organize
"""

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


@dataclass
class SrtEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str


def ts_to_ms(h: int, m: int, s: int, ms: int) -> int:
    return ((h * 3600) + (m * 60) + s) * 1000 + ms


def ms_to_ts(ms: int) -> str:
    total_seconds, millis = divmod(ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def ms_to_display(ms: int) -> str:
    """Format milliseconds as HH:MM:SS for display."""
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_srt(path: Path) -> list[SrtEntry]:
    """Parse an SRT file into a list of entries."""
    content = path.read_text(encoding="utf-8")
    entries = []
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        match = TIMESTAMP_RE.search(lines[1])
        if not match:
            continue

        g = [int(x) for x in match.groups()]
        start_ms = ts_to_ms(g[0], g[1], g[2], g[3])
        end_ms = ts_to_ms(g[4], g[5], g[6], g[7])
        text = "\n".join(lines[2:])

        entries.append(SrtEntry(index=0, start_ms=start_ms, end_ms=end_ms, text=text))

    return entries


def combine_entries(
    srt_files: list[Path],
) -> tuple[list[SrtEntry], list[int]]:
    """Combine entries from multiple SRT files with continuous timecodes.

    Returns combined entries and a list of boundary indices (where each
    source file ends in the combined sequence).
    """
    combined = []
    offset_ms = 0
    boundaries = []

    for srt_path in srt_files:
        entries = parse_srt(srt_path)
        if not entries:
            print(f"Warning: No entries parsed from {srt_path}", file=sys.stderr)
            boundaries.append(len(combined))
            continue

        for entry in entries:
            combined.append(
                SrtEntry(
                    index=len(combined) + 1,
                    start_ms=entry.start_ms + offset_ms,
                    end_ms=entry.end_ms + offset_ms,
                    text=entry.text,
                )
            )

        # Next file starts where this one ended
        offset_ms = combined[-1].end_ms
        boundaries.append(len(combined))

    return combined, boundaries


def write_srt(entries: list[SrtEntry], output_path: Path) -> None:
    """Write entries to an SRT file."""
    lines = []
    for entry in entries:
        lines.append(str(entry.index))
        lines.append(f"{ms_to_ts(entry.start_ms)} --> {ms_to_ts(entry.end_ms)}")
        lines.append(entry.text)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_txt(
    entries: list[SrtEntry], boundaries: list[int], output_path: Path
) -> None:
    """Generate a combined plain text transcript from SRT entries.

    Merges subtitle fragments into paragraphs of ~400 chars with ---
    separators between source parts.
    """
    parts: list[list[SrtEntry]] = []
    prev = 0
    for b in boundaries:
        parts.append(entries[prev:b])
        prev = b

    sections = []
    for part_entries in parts:
        if not part_entries:
            continue

        # Collect all text fragments
        fragments = [e.text.replace("\n", " ").strip() for e in part_entries]

        # Merge into paragraphs of ~400 chars
        paragraphs = []
        current = []
        current_len = 0
        for frag in fragments:
            current.append(frag)
            current_len += len(frag) + 1
            if current_len >= 400:
                paragraphs.append(" ".join(current))
                current = []
                current_len = 0
        if current:
            paragraphs.append(" ".join(current))

        sections.append("\n\n".join(paragraphs))

    output_path.write_text("\n\n---\n\n".join(sections), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Combine multiple SRT files into a single continuous transcript."
    )
    parser.add_argument(
        "srt_files",
        nargs="+",
        type=Path,
        help="SRT files to combine, in playback order",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same directory as first SRT file)",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="Base name for output files (default: 'combined')",
    )
    parser.add_argument(
        "--txt",
        action="store_true",
        help="Also generate a combined plain text transcript",
    )
    parser.add_argument(
        "--organize",
        action="store_true",
        help="Move individual SRT files into a raw_transcripts/ subfolder",
    )
    args = parser.parse_args()

    # Validate inputs
    for srt in args.srt_files:
        if not srt.exists():
            print(f"Error: File not found: {srt}", file=sys.stderr)
            sys.exit(1)

    output_dir = args.output_dir or args.srt_files[0].parent
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = args.output_name or "combined"

    # Combine
    entries, boundaries = combine_entries(args.srt_files)
    if not entries:
        print("Error: No SRT entries found in any input file", file=sys.stderr)
        sys.exit(1)

    total_duration = ms_to_display(entries[-1].end_ms)
    print(f"Combined {len(entries)} entries, total duration: {total_duration}")

    # Write combined SRT
    srt_out = output_dir / f"{base_name}.srt"
    write_srt(entries, srt_out)
    print(f"  SRT: {srt_out}")

    # Write combined TXT
    if args.txt:
        txt_out = output_dir / f"{base_name}.txt"
        write_txt(entries, boundaries, txt_out)
        print(f"  TXT: {txt_out}")

    # Organize source files
    if args.organize:
        raw_dir = output_dir / "raw_transcripts"
        raw_dir.mkdir(exist_ok=True)
        for srt in args.srt_files:
            dest = raw_dir / srt.name
            if srt.resolve() != dest.resolve():
                shutil.move(str(srt), str(dest))
                print(f"  Moved: {srt.name} → raw_transcripts/")

    print(f"\nDone. {len(entries)} entries, {total_duration}")


if __name__ == "__main__":
    main()
