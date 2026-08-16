#!/usr/bin/env python3
"""Resolve an episode's audio from Google Drive into canonical local files.

Producer-supplied Drive folders vary in ways the pipeline should not care
about: the MP3s sit in a nested subfolder (always, and sometimes two deep),
separators drift between `_`, space, and hyphen, names carry stray leading
spaces, and the image folder is called `Images`, `Photos`, or
`Images for Newsletter`. What has never varied across E10-E20 is the shape:
exactly three MP3s -- part 1, mid-roll, part 2.

This script keys on that invariant and normalises everything else away. It
replaces two steps the retriever agent previously improvised per episode:
flattening the nested download, and putting the parts in playback order.
`sorted()` was never correct for the latter -- "mid" sorts before "mix", so
midroll landed first for every episode except E19, which was right only by
accident (a stray space in "Flynn _mix_01.mp3").

Usage:
    # Download + flatten into an episode's audio/ directory
    python3 scripts/resolve_audio.py \
        --drive-folder-id 1fxDR... \
        --dest shows/wonder-cabinet/episodes/WC_S01_20_Christian_Wiman \
        --slug WC_S01_20_Christian_Wiman

    # Report what it would do, touching nothing
    python3 scripts/resolve_audio.py --drive-folder-id 1fxDR... --dry-run

    # Just print the image folder's Drive ID (for /wc-episode-art)
    python3 scripts/resolve_audio.py --drive-folder-id 1fxDR... --images-only
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Ordered: this is playback order, and the order captions are stitched in.
# The separator class is explicit rather than \W because `_` is a word
# character -- \W would fail on `mix_01`, the single most common form.
SEP = r"[\s_\-]*"
# `mix` is the producer's word, `part` is the canonical one this script
# writes -- both are accepted so the resolver can re-read its own output.
BODY = r"(?:mix|part)"
PART_PATTERNS = [
    ("part01", re.compile(rf"{BODY}{SEP}0?1\b", re.IGNORECASE)),
    ("midroll", re.compile(rf"mid{SEP}roll", re.IGNORECASE)),
    ("part02", re.compile(rf"{BODY}{SEP}0?2\b", re.IGNORECASE)),
]

IMAGE_DIR_PATTERN = re.compile(r"image|photo", re.IGNORECASE)

AUDIO_SUFFIX = ".mp3"


class AudioResolutionError(Exception):
    """Raised when a Drive folder does not match the three-part shape.

    Always fail loudly here. A wrong guess produces a transcript that is
    subtly out of order, which surfaces only on a human read-through.
    """


def classify_parts(paths: list[str]) -> list[tuple[str, str]]:
    """Map MP3 paths to (role, path) in playback order.

    Accepts bare filenames or full nested paths, in any order. Raises
    AudioResolutionError unless exactly three files map onto the three
    roles one-to-one.
    """
    matched: dict[str, list[str]] = {role: [] for role, _ in PART_PATTERNS}
    unmatched: list[str] = []

    for path in paths:
        name = Path(path).name
        for role, pattern in PART_PATTERNS:
            if pattern.search(name):
                matched[role].append(path)
                break
        else:
            unmatched.append(path)

    problems = []
    if len(paths) != 3:
        problems.append(
            f"  found {len(paths)} MP3 files, expected exactly 3 "
            "(every episode E10-E20 shipped mix 01, midroll, mix 02)"
        )
    for role, _ in PART_PATTERNS:
        found = matched[role]
        if not found:
            problems.append(f"  {role}: no file matched")
        elif len(found) > 1:
            problems.append(f"  {role}: {len(found)} files matched -> {found}")
    if unmatched:
        problems.append(f"  unrecognised: {unmatched}")

    if problems:
        raise AudioResolutionError(
            "Could not map Drive audio onto part01/midroll/part02:\n"
            + "\n".join(problems)
            + f"\nFiles seen: {sorted(paths)}"
        )

    return [(role, matched[role][0]) for role, _ in PART_PATTERNS]


def pick_image_dir(dirnames: list[str]) -> str | None:
    """Choose the source-image folder from a Drive folder's subdirectories.

    Prefers an exact `Images`/`Photos` over a qualified variant such as
    `Images for Newsletter`, which is a different deliverable.
    """
    candidates = [d for d in dirnames if IMAGE_DIR_PATTERN.search(d)]
    if not candidates:
        return None
    exact = [d for d in candidates if d.strip().lower() in ("images", "photos")]
    return sorted(exact)[0] if exact else sorted(candidates, key=len)[0]


# --- Drive I/O ---------------------------------------------------------


def _rclone_json(folder_id: str, *extra_args: str) -> list[dict]:
    cmd = [
        "rclone", "lsjson", "gdrive:",
        "--drive-root-folder-id", folder_id,
        *extra_args,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("rclone not found on PATH. See CLAUDE.md for remote setup.")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"rclone failed for folder {folder_id}:\n{exc.stderr}")
    return json.loads(out)


def list_drive_mp3s(folder_id: str) -> list[str]:
    """Every MP3 under the folder, at any depth."""
    entries = _rclone_json(folder_id, "-R", "--include", f"*{AUDIO_SUFFIX}")
    return [e["Path"] for e in entries if not e["IsDir"]]


def find_images_folder(folder_id: str) -> tuple[str, str] | None:
    """Return (name, drive_id) of the source-image folder, if present."""
    entries = _rclone_json(folder_id, "--dirs-only")
    chosen = pick_image_dir([e["Name"] for e in entries])
    if chosen is None:
        return None
    for entry in entries:
        if entry["Name"] == chosen:
            return chosen, entry["ID"]
    return None


def download_and_flatten(
    folder_id: str, resolved: list[tuple[str, str]], dest_dir: Path, slug: str
) -> list[str]:
    """Download the three parts to dest_dir under canonical flat names.

    Canonical naming does double duty: it strips the spaces that make every
    downstream shell quoting bug possible, and it makes the Whisper output
    directory names predictable for the caption-stitching phase.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    staging = dest_dir / ".resolve-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    written = []
    try:
        for role, remote_path in resolved:
            subprocess.run(
                [
                    "rclone", "copyto",
                    f"gdrive:{remote_path}", str(staging / f"{role}{AUDIO_SUFFIX}"),
                    "--drive-root-folder-id", folder_id,
                ],
                capture_output=True, text=True, check=True,
            )
            final = dest_dir / f"{slug}_{role}{AUDIO_SUFFIX}"
            shutil.move(str(staging / f"{role}{AUDIO_SUFFIX}"), final)
            written.append(final.name)
            print(f"  {remote_path}  ->  {final.name}")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"rclone download failed:\n{exc.stderr}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return written


def update_manifest(dest_dir: Path, parts: list[str], images: tuple[str, str] | None):
    """Record parts in playback order — never re-sorted."""
    manifest_path = dest_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"  (no manifest at {manifest_path}; skipping manifest update)")
        return

    manifest = json.loads(manifest_path.read_text())
    manifest.setdefault("files", {})["audio"] = {
        "parts": [f"audio/{name}" for name in parts],
        "status": "present",
        "order": "playback",
    }
    if images:
        name, drive_id = images
        manifest.setdefault("google_drive", {})["images_folder"] = {
            "name": name,
            "id": drive_id,
        }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  manifest updated: {manifest_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--drive-folder-id", required=True, help="Episode folder ID on Drive")
    parser.add_argument("--dest", help="Canonical episode directory (audio/ is created inside)")
    parser.add_argument("--slug", help="Episode slug used for canonical filenames")
    parser.add_argument("--dry-run", action="store_true", help="Report the plan, write nothing")
    parser.add_argument("--images-only", action="store_true", help="Print the image folder ID and exit")
    args = parser.parse_args()

    if args.images_only:
        images = find_images_folder(args.drive_folder_id)
        if not images:
            sys.exit("No image folder found in that Drive folder.")
        name, drive_id = images
        print(f"{name}\t{drive_id}")
        return

    mp3s = list_drive_mp3s(args.drive_folder_id)
    resolved = classify_parts(mp3s)  # raises loudly on any deviation

    print("Resolved audio (playback order):")
    for role, path in resolved:
        print(f"  {role:8} {path}")

    images = find_images_folder(args.drive_folder_id)
    print(f"Images folder: {images[0]} ({images[1]})" if images else "Images folder: none found")

    if args.dry_run:
        print("\n[DRY RUN] Nothing downloaded.")
        return

    if not args.dest or not args.slug:
        sys.exit("--dest and --slug are required unless --dry-run or --images-only")

    dest = Path(args.dest)
    if not dest.is_absolute():
        dest = Path(__file__).resolve().parent.parent / dest
    audio_dir = dest / "audio"

    print(f"\nDownloading to {audio_dir}/")
    parts = download_and_flatten(args.drive_folder_id, resolved, audio_dir, args.slug)
    update_manifest(dest, parts, images)


if __name__ == "__main__":
    main()
