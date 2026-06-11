#!/usr/bin/env python3
"""Apply word-boundary corrections from a glossary to one or more text files.

The pipeline historically applied glossary corrections only when generating
`formatted_transcript.md` (the human-readable deliverable). The raw SRTs —
which become `captions.srt` and ship to Drive/YouTube — never saw the
corrections, so misrendered names ("Strangchamps", "Christoph", "Fersher",
etc.) leaked through to published captions.

This script is the missing step: run it on raw SRTs *before* combine_srts.py,
and the combined captions ship clean from day one. The same tool also serves
`wc-transcript-update`, which applies producer corrections on top.

Two regex traps the implementation handles explicitly:

1. **Trailing-punctuation `\\b` failure.** `\\bexperience\\.\\b` silently fails
   because `\\b` requires a word↔non-word transition, and there's no such
   transition between `.` (non-word) and a following space/newline (also
   non-word). This script uses `(?<!\\w)...(?!\\w)` lookarounds, which only
   require the *absence* of a word char on each side — so phrases ending in
   punctuation match correctly.

2. **REVIEW NOTES corruption in markdown.** Markdown deliverables include
   `<!-- REVIEW NOTES: ... -->` blocks that literally document the
   misrenders ("Strangchamps → Strainchamps") as examples. Blanket regex
   replace turns the documentation into nonsense. With `--skip-html-comments`
   the script masks comment regions before applying corrections and restores
   them afterward.

Idempotent: re-running on already-corrected text is a no-op (no matches).
Word-boundary lookarounds also prevent the `sikere → sikerei` class of bug,
where a correction would otherwise cascade into already-correct output.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from pathlib import Path


HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def load_corrections(glossary_path: Path) -> dict[str, str]:
    data = json.loads(glossary_path.read_text())
    corrections = data.get("corrections")
    if not isinstance(corrections, dict):
        raise SystemExit(f"{glossary_path}: missing or invalid 'corrections' object")
    return corrections


def mask_html_comments(text: str) -> tuple[str, dict[str, str]]:
    """Replace HTML comments with unique placeholders. Returns (masked_text, restore_map)."""
    restore: dict[str, str] = {}

    def _sub(m: re.Match[str]) -> str:
        token = f"\x00GLOSSARYMASK_{uuid.uuid4().hex}\x00"
        restore[token] = m.group(0)
        return token

    return HTML_COMMENT_RE.sub(_sub, text), restore


def unmask(text: str, restore: dict[str, str]) -> str:
    for token, original in restore.items():
        text = text.replace(token, original)
    return text


def apply_corrections(text: str, corrections: dict[str, str]) -> tuple[str, dict[str, int]]:
    """Apply corrections with non-word-char boundary lookarounds. Returns (new_text, counts).

    Keys are applied in length-descending order: longer/more specific patterns win.
    This prevents the `Rickers → Mark Riechers` class of bug where a bare-token
    correction doubles up when the source text already contains a compound form
    ("Mark Rickers" → "Mark Mark Riechers"). With compound entries also in the
    glossary ("Mark Rickers → Mark Riechers"), they fire first and consume the
    text before the bare-token rule sees it.
    """
    counts: dict[str, int] = {}
    sorted_corrections = sorted(corrections.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    for bad, good in sorted_corrections:
        if not bad:
            continue
        pattern = r"(?<!\w)" + re.escape(bad) + r"(?!\w)"
        new_text, n = re.subn(pattern, good, text)
        if n:
            counts[bad] = n
        text = new_text
    return text, counts


def process_file(
    path: Path,
    corrections: dict[str, str],
    *,
    backup: bool,
    skip_html_comments: bool,
) -> dict[str, int]:
    original = path.read_text()

    if skip_html_comments:
        working, restore = mask_html_comments(original)
    else:
        working, restore = original, {}

    corrected, counts = apply_corrections(working, corrections)
    final = unmask(corrected, restore)

    if final == original:
        return counts  # no-op; don't touch backup or file

    if backup:
        backup_path = path.with_suffix(path.suffix + ".original")
        if not backup_path.exists():
            shutil.copy2(path, backup_path)

    path.write_text(final)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply glossary corrections to text files using word-boundary regex.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Files to correct in place (typically *.srt or *.md).",
    )
    parser.add_argument(
        "--glossary",
        required=True,
        type=Path,
        help="Path to glossary.json (must contain a 'corrections' object).",
    )
    parser.add_argument(
        "--skip-html-comments",
        action="store_true",
        help="Preserve HTML <!-- ... --> blocks unchanged (use for markdown).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating .original backup files.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file counts; only print final summary.",
    )
    args = parser.parse_args()

    corrections = load_corrections(args.glossary)

    missing = [f for f in args.files if not f.exists()]
    if missing:
        for f in missing:
            print(f"ERROR: file not found: {f}", file=sys.stderr)
        return 2

    total: dict[str, int] = {}
    files_changed = 0

    for f in args.files:
        counts = process_file(
            f,
            corrections,
            backup=not args.no_backup,
            skip_html_comments=args.skip_html_comments,
        )
        file_total = sum(counts.values())
        if file_total:
            files_changed += 1
        if not args.quiet:
            print(f"{f}: {file_total} replacement(s)")
            for bad, n in sorted(counts.items()):
                print(f"  {bad!r} → {corrections[bad]!r}: {n}")
        for bad, n in counts.items():
            total[bad] = total.get(bad, 0) + n

    grand_total = sum(total.values())
    print(
        f"\nTotal: {grand_total} replacement(s) across {files_changed} file(s)",
        file=sys.stderr if args.quiet else sys.stdout,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
