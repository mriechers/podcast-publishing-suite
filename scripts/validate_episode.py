#!/usr/bin/env python3
"""Validate an episode directory against the transcription pipeline deliverable convention.

Checks for required files, naming conventions, and directory structure.

Usage:
    python validate_episode.py /path/to/episode/directory
    python validate_episode.py /path/to/episode/directory --episode 102 --guest "Carlo Rovelli"
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Pattern: "{ep#} - {Guest Name}" with optional extension
DELIVERABLE_RE = re.compile(r"^(\d+)\s*-\s*(.+?)(\.\w+)?$")


def check_file(path: Path, label: str) -> tuple[bool, str]:
    """Check if a file exists and is non-empty."""
    if not path.exists():
        return False, f"Missing: {label} ({path.name})"
    if path.stat().st_size == 0:
        return False, f"Empty: {label} ({path.name})"
    return True, f"Found: {label} ({path.name})"


def validate_srt(path: Path) -> list[str]:
    """Basic SRT validation: sequential numbering, continuous timecodes."""
    issues = []
    content = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip())

    expected_idx = 1
    last_end_ms = 0

    ts_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    )

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        # Check index
        try:
            idx = int(lines[0].strip())
            if idx != expected_idx:
                issues.append(
                    f"SRT numbering gap: expected {expected_idx}, got {idx}"
                )
                expected_idx = idx
        except ValueError:
            issues.append(f"SRT non-numeric index: {lines[0][:20]}")

        # Check timecodes
        match = ts_re.search(lines[1])
        if match:
            g = [int(x) for x in match.groups()]
            start_ms = ((g[0] * 3600) + (g[1] * 60) + g[2]) * 1000 + g[3]
            end_ms = ((g[4] * 3600) + (g[5] * 60) + g[6]) * 1000 + g[7]

            if start_ms < last_end_ms - 100:  # 100ms tolerance
                issues.append(
                    f"SRT timecode reset at entry {expected_idx}: "
                    f"starts at {start_ms}ms but previous ended at {last_end_ms}ms"
                )
            last_end_ms = end_ms

        expected_idx += 1

    return issues


def validate_episode(
    episode_dir: Path,
    episode_num: str | None = None,
    guest_name: str | None = None,
) -> tuple[list[tuple[bool, str]], int]:
    """Validate an episode directory. Returns (results, exit_code)."""
    results: list[tuple[bool, str]] = []

    if not episode_dir.is_dir():
        return [(False, f"Not a directory: {episode_dir}")], 1

    # Try to infer episode number and guest from directory contents
    if not episode_num or not guest_name:
        srt_files = list(episode_dir.glob("*.srt"))
        for srt in srt_files:
            m = DELIVERABLE_RE.match(srt.stem + srt.suffix)
            if m and m.group(3) == ".srt":
                episode_num = episode_num or m.group(1)
                guest_name = guest_name or m.group(2)
                break

    # Build expected file patterns
    if episode_num and guest_name:
        expected_srt = f"{episode_num} - {guest_name}.srt"
        expected_transcript = "formatted_transcript.md"
        expected_chapters = "chapters.md"

        # Combined SRT
        ok, msg = check_file(episode_dir / expected_srt, "Combined SRT")
        results.append((ok, msg))
        if ok:
            srt_issues = validate_srt(episode_dir / expected_srt)
            for issue in srt_issues:
                results.append((False, f"  SRT issue: {issue}"))

        # Formatted transcript
        ok, msg = check_file(episode_dir / expected_transcript, "Formatted transcript")
        results.append((ok, msg))

        # Chapters
        ok, msg = check_file(episode_dir / expected_chapters, "Chapters")
        results.append((ok, msg))

        # Combined TXT (optional but expected)
        txt_candidates = list(episode_dir.glob("*_transcript.txt")) + list(
            episode_dir.glob("*.txt")
        )
        if txt_candidates:
            results.append((True, f"Found: Combined TXT ({txt_candidates[0].name})"))
        else:
            results.append((False, "Missing: Combined TXT (no .txt file found)"))
    else:
        # Can't infer naming — check for generic presence
        results.append(
            (False, "Cannot infer episode number/guest from directory contents")
        )
        srt_count = len(list(episode_dir.glob("*.srt")))
        md_count = len(list(episode_dir.glob("*.md")))
        results.append(
            (srt_count > 0, f"SRT files: {srt_count} found")
        )
        results.append(
            (md_count > 0, f"Markdown files: {md_count} found")
        )

    # Raw transcripts subfolder
    raw_dir = episode_dir / "raw_transcripts"
    if raw_dir.is_dir():
        raw_srts = list(raw_dir.glob("*.srt"))
        results.append((len(raw_srts) > 0, f"Found: raw_transcripts/ ({len(raw_srts)} SRTs)"))
    else:
        results.append((False, "Missing: raw_transcripts/ subfolder"))

    # Upload manifest (optional)
    manifest = episode_dir / "upload_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text())
            failed = [f for f in data.get("files", []) if f.get("status") == "failed"]
            if failed:
                results.append(
                    (False, f"Upload manifest: {len(failed)} files failed upload")
                )
            else:
                results.append((True, "Upload manifest: all files uploaded"))
        except (json.JSONDecodeError, KeyError):
            results.append((False, "Upload manifest: invalid JSON"))

    exit_code = 0 if all(ok for ok, _ in results) else 1
    return results, exit_code


def main():
    parser = argparse.ArgumentParser(
        description="Validate an episode directory against deliverable conventions."
    )
    parser.add_argument(
        "episode_dir",
        type=Path,
        help="Path to the episode directory",
    )
    parser.add_argument(
        "--episode",
        type=str,
        default=None,
        help="Episode number (e.g., '102'). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--guest",
        type=str,
        default=None,
        help="Guest name (e.g., 'Carlo Rovelli'). Auto-detected if omitted.",
    )
    args = parser.parse_args()

    results, exit_code = validate_episode(args.episode_dir, args.episode, args.guest)

    print(f"Validating: {args.episode_dir}\n")
    for ok, msg in results:
        symbol = "\u2713" if ok else "\u2717"
        print(f"  {symbol} {msg}")

    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    print(f"\n{'PASS' if exit_code == 0 else 'FAIL'}: {passed}/{total} checks passed")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
