#!/usr/bin/env python3
"""Create a canonical episode folder with manifest.json.

Usage:
    # New episode
    python3 scripts/episode-init.py --show wonder-cabinet --episode 6 --guest "Robert MacFarlane"

    # With Drive folder for audio download (used by wc-transcribe skill)
    python3 scripts/episode-init.py --show wonder-cabinet --episode 6 --guest "Robert MacFarlane" \
        --drive-folder-id XXXXX

    # Migration: populate from existing local files
    python3 scripts/episode-init.py --show wonder-cabinet --episode 5 --guest "Renee Bergland" \
        --migrate-from modules/podcast-whisper-transcription/audio-to-transcribe/WC_S01_05_Bergland

    # Luminous (slug-based)
    python3 scripts/episode-init.py --show luminous --slug "melissa-etheridge-ayahuasca" \
        --title "Melissa Etheridge on Ayahuasca"
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_audio import AudioResolutionError, classify_parts  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGES = ["init", "audio_ready", "transcribed", "formatted", "uploaded", "imported", "published"]


def order_audio_parts(filenames: list[str]) -> list[str]:
    """Order audio parts for playback, keeping non-part files at the end.

    Unlike resolve_audio's CLI path, this is best-effort: an episode
    directory legitimately holds extras (a stitched `*_full.mp3`, say), and
    refreshing a manifest should never hard-fail over file naming.
    """
    parts = [f for f in filenames if not f.endswith("_full.mp3")]
    extras = [f for f in filenames if f not in parts]
    try:
        ordered = [name for _, name in classify_parts(parts)]
    except AudioResolutionError:
        return filenames  # leave as-is; the resolver reports properly
    return ordered + extras


def load_show_config(show_slug: str) -> dict:
    config_path = REPO_ROOT / "shows" / show_slug / "config.json"
    if not config_path.exists():
        sys.exit(f"Show config not found: {config_path}")
    return json.loads(config_path.read_text())


def build_slug(config: dict, args) -> str:
    episodes = config["episodes"]
    prefix = episodes.get("slugPrefix", "EP")
    fmt = episodes.get("slugFormat", "{prefix}_{number}_{guest}")

    if args.slug:
        # Luminous-style: use provided slug directly
        return f"{prefix}_{args.slug}" if not args.slug.startswith(prefix) else args.slug

    if args.episode is None or args.guest is None:
        sys.exit("--episode and --guest are required for this show (or use --slug)")

    guest_parts = args.guest.strip().split()
    guest_formatted = "_".join(guest_parts)
    number = f"{int(args.episode):02d}"

    slug = fmt.format(prefix=prefix, number=number, guest=guest_formatted)
    return slug


def detect_stage(episode_dir: Path, file_map: dict) -> str:
    """Detect the furthest stage based on which files exist."""
    has_audio = (episode_dir / "audio").exists() and any((episode_dir / "audio").iterdir())
    has_transcript = (episode_dir / file_map.get("transcript", "transcript.txt")).exists()
    has_formatted = (episode_dir / file_map.get("formatted_transcript", "formatted_transcript.md")).exists()

    if has_formatted:
        return "formatted"
    if has_transcript:
        return "transcribed"
    if has_audio:
        return "audio_ready"
    return "init"


def create_manifest(episode_dir: Path, config: dict, args, slug: str, stage: str = "init") -> dict:
    file_map = config["episodes"].get("fileMap", {})
    now = datetime.now(timezone.utc).isoformat()

    manifest = {
        "version": 1,
        "show": config["slug"],
        "slug": slug,
        "stage": stage,
        "timestamps": {
            "created": now,
        },
        "files": {},
    }

    if args.episode is not None:
        manifest["episodeNumber"] = int(args.episode)
    if args.guest:
        manifest["guestName"] = args.guest
    if args.title:
        manifest["title"] = args.title
    if args.season:
        manifest["season"] = int(args.season)

    if args.drive_folder_id:
        manifest["google_drive"] = {"episode_folder_id": args.drive_folder_id}

    # Populate files section based on what exists
    for key, filename in file_map.items():
        if key == "manifest":
            continue
        filepath = episode_dir / filename
        manifest["files"][key] = {
            "path": filename,
            "status": "present" if filepath.exists() else "missing",
        }

    # Check audio. Parts are ordered by role (part 1 -> mid-roll -> part 2),
    # not lexically: "mid" sorts before "mix", so a plain sorted() puts the
    # mid-roll first for any episode whose files are named `*_mix_01.mp3`.
    audio_dir = episode_dir / config["episodes"].get("subdirs", {}).get("audio", "audio")
    if audio_dir.exists():
        audio_files = sorted([f.name for f in audio_dir.iterdir() if f.suffix in (".mp3", ".wav", ".m4a")])
        if audio_files:
            manifest["files"]["audio"] = {
                "parts": [f"audio/{f}" for f in order_audio_parts(audio_files)],
                "status": "present",
            }

    return manifest


def create_directory_tree(episode_dir: Path, subdirs: dict):
    episode_dir.mkdir(parents=True, exist_ok=True)
    for subdir in subdirs.values():
        (episode_dir / subdir).mkdir(exist_ok=True)
    # Also create images/originals
    (episode_dir / subdirs.get("images", "images") / "originals").mkdir(parents=True, exist_ok=True)


def categorize_file(filepath: Path) -> tuple[str, str]:
    """Return (subdir, relative_path) for a file based on its type."""
    name = filepath.name.lower()
    suffix = filepath.suffix.lower()

    if suffix in (".mp3", ".wav", ".m4a", ".flac"):
        return "audio", filepath.name
    if suffix in (".jpg", ".jpeg", ".png", ".psd", ".tif", ".tiff"):
        return "images", filepath.name
    if suffix in (".json",) and "whisper" in name:
        return "whisper", filepath.name
    if name == "formatted_transcript.md":
        return "", "formatted_transcript.md"
    if name == "chapters.md":
        return "", "chapters.md"
    if suffix == ".srt" and "raw_transcripts" not in str(filepath):
        return "", "captions.srt"
    if suffix == ".txt" and "transcript" in name:
        return "", "transcript.txt"

    return "", filepath.name


def migrate_from_source(source_dir: Path, episode_dir: Path, config: dict):
    """Copy files from a source directory into canonical structure."""
    subdirs = config["episodes"].get("subdirs", {})
    file_map = config["episodes"].get("fileMap", {})

    for item in sorted(source_dir.iterdir()):
        if item.name.startswith("."):
            continue

        if item.is_dir():
            dir_name = item.name.lower()
            # Whisper output subdirectories (contain .srt, .json, .vtt, .tsv per segment)
            whisper_files = list(item.glob("*.srt")) + list(item.glob("*.json")) + list(item.glob("*.vtt"))
            if whisper_files:
                dest = episode_dir / subdirs.get("whisper", "whisper") / item.name
                if not dest.exists():
                    shutil.copytree(item, dest)
                    print(f"  Copied whisper dir: {item.name}/ -> whisper/{item.name}/")
            elif dir_name == "raw_transcripts":
                dest = episode_dir / subdirs.get("whisper", "whisper") / "raw_transcripts"
                if not dest.exists():
                    shutil.copytree(item, dest)
                    print(f"  Copied raw_transcripts/ -> whisper/raw_transcripts/")
            continue

        subdir, dest_name = categorize_file(item)
        if subdir:
            dest = episode_dir / subdirs.get(subdir, subdir) / dest_name
        else:
            dest = episode_dir / dest_name

        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            rel = dest.relative_to(episode_dir)
            print(f"  Copied: {item.name} -> {rel}")
        else:
            print(f"  Skipped (exists): {dest_name}")


def main():
    parser = argparse.ArgumentParser(description="Create a canonical episode folder")
    parser.add_argument("--show", required=True, help="Show slug (e.g., wonder-cabinet)")
    parser.add_argument("--episode", type=int, help="Episode number")
    parser.add_argument("--guest", help="Guest name (e.g., 'Robert MacFarlane')")
    parser.add_argument("--title", help="Episode title")
    parser.add_argument("--season", type=int, default=1, help="Season number (default: 1)")
    parser.add_argument("--slug", help="Full slug override (for Luminous-style episodes)")
    parser.add_argument("--drive-folder-id", help="Google Drive folder ID for audio download")
    parser.add_argument("--migrate-from", help="Local directory to migrate files from")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without doing it")

    args = parser.parse_args()
    config = load_show_config(args.show)
    episodes_config = config["episodes"]
    subdirs = episodes_config.get("subdirs", {})

    slug = build_slug(config, args)
    episodes_path = REPO_ROOT / episodes_config["localPath"]
    episode_dir = episodes_path / slug

    print(f"Episode: {slug}")
    print(f"Directory: {episode_dir}")

    if args.dry_run:
        print("\n[DRY RUN] Would create:")
        print(f"  {episode_dir}/")
        for sd in subdirs.values():
            print(f"  {episode_dir}/{sd}/")
        print(f"  {episode_dir}/{subdirs.get('images', 'images')}/originals/")
        print(f"  {episode_dir}/manifest.json")
        if args.migrate_from:
            source = Path(args.migrate_from)
            if not source.is_absolute():
                source = REPO_ROOT / source
            print(f"\nWould migrate from: {source}")
            if source.exists():
                for item in sorted(source.iterdir()):
                    if not item.name.startswith("."):
                        print(f"  {item.name}")
        return

    if episode_dir.exists():
        print(f"\nDirectory already exists. Updating manifest only.")
    else:
        print(f"\nCreating directory tree...")
        create_directory_tree(episode_dir, subdirs)

    # Migrate files if requested
    if args.migrate_from:
        source = Path(args.migrate_from)
        if not source.is_absolute():
            source = REPO_ROOT / source
        if not source.exists():
            sys.exit(f"Migration source not found: {source}")
        print(f"\nMigrating from: {source}")
        migrate_from_source(source, episode_dir, config)

    # Detect stage and create manifest
    file_map = episodes_config.get("fileMap", {})
    stage = detect_stage(episode_dir, file_map)
    if args.drive_folder_id and stage == "init":
        # Drive folder provided but no audio yet — still init, will become audio_ready after download
        pass

    manifest = create_manifest(episode_dir, config, args, slug, stage)
    manifest_path = episode_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nManifest written: {manifest_path}")
    print(f"Stage: {stage}")

    # Summary
    print(f"\nNext steps:")
    if stage == "init":
        if args.drive_folder_id:
            print(f"  - Download audio from Drive folder {args.drive_folder_id} to {episode_dir}/audio/")
        else:
            print(f"  - Add audio files to {episode_dir}/audio/")
        print(f"  - Run /wc-transcribe to process")
    elif stage == "audio_ready":
        print(f"  - Run /wc-transcribe to process")
    elif stage == "transcribed":
        print(f"  - Run formatter to create formatted_transcript.md")
    elif stage == "formatted":
        print(f"  - Run /ghost-import or episode-archive.py to upload")


if __name__ == "__main__":
    main()
