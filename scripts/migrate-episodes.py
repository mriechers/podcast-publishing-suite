#!/usr/bin/env python3
"""One-time migration: consolidate episode files into canonical folder structure.

Scans all known locations (Whisper module, publisher cache, images dir, existing
canonical folders) and copies files into shows/{show}/episodes/{slug}/ with proper
subdirectory organization and manifest.json generation.

Usage:
    # Preview what would happen
    python3 scripts/migrate-episodes.py --dry-run

    # Run the migration (copies, does not move)
    python3 scripts/migrate-episodes.py

    # Migrate a single episode
    python3 scripts/migrate-episodes.py --only WC_S01_05
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WHISPER_BASE = REPO_ROOT / "modules" / "podcast-whisper-transcription" / "audio-to-transcribe"
PUBLISHER_CACHE = REPO_ROOT / "modules" / "prx-to-ghost-publisher" / "transcripts"
IMAGES_BASE = REPO_ROOT / "images"

# Known Wonder Cabinet episodes with their metadata and file locations
WC_EPISODES = [
    {
        "episode": 1,
        "guest": "Sophie Strand",
        "slug": "WC_S01_01_Sophie_Strand",
        "title": "The Flowering Wand",
        "whisper_dir": None,
        "publisher_transcript": "101_Sophie_Strand.txt",
        "image_dir": None,
        "image_files": [],
        "existing_canonical": None,
    },
    {
        "episode": 2,
        "guest": "Carlo Rovelli",
        "slug": "WC_S01_02_Carlo_Rovelli",
        "title": "Time, Reality, and Wonder",
        "whisper_dir": "WC_002_Rovelli",
        "publisher_transcript": "102_Carlo_Rovelli.txt",
        "image_dir": None,
        "image_files": ["102 - Carlo.png"],
        "existing_canonical": None,
    },
    {
        "episode": 3,
        "guest": "Rebecca Solnit",
        "slug": "WC_S01_03_Rebecca_Solnit",
        "title": "Maps, Wandering, and Hope",
        "whisper_dir": "WC_S01_03_Solnit",
        "publisher_transcript": None,
        "image_dir": "103 - Rebecca Solnit",
        "image_files": ["103-solnit.jpg"],
        "existing_canonical": None,
    },
    {
        "episode": 4,
        "guest": "George Saunders",
        "slug": "WC_S01_04_George_Saunders",
        "title": "Kindness and Storytelling",
        "whisper_dir": "WC_S01_04_Saunders",
        "publisher_transcript": None,
        "image_dir": "104 - saunders",
        "image_files": [],
        "existing_canonical": None,
    },
    {
        "episode": 5,
        "guest": "Renee Bergland",
        "slug": "WC_S01_05_Renee_Bergland",
        "title": "American Curiosity",
        "whisper_dir": "WC_S01_05_Bergland",
        "publisher_transcript": None,
        "image_dir": None,
        "image_files": [],
        "existing_canonical": "WC_005_Renee_Bergland",
    },
    {
        "episode": 6,
        "guest": "Robert MacFarlane",
        "slug": "WC_S01_06_Robert_MacFarlane",
        "title": "Underland",
        "whisper_dir": "WC_S01_06_MacFarlane",
        "publisher_transcript": None,
        "image_dir": None,
        "image_files": [],
        "existing_canonical": "WC_106_Macfarlane",
    },
]

SUBDIRS = {"audio": "audio", "images": "images", "whisper": "whisper", "audiogram": "audiogram"}
FILE_MAP = {
    "transcript": "transcript.txt",
    "formatted_transcript": "formatted_transcript.md",
    "captions": "captions.srt",
    "chapters": "chapters.md",
    "manifest": "manifest.json",
}


def load_show_config():
    config_path = REPO_ROOT / "shows" / "wonder-cabinet" / "config.json"
    return json.loads(config_path.read_text())


def plan_episode_migration(ep: dict) -> list[dict]:
    """Build a list of copy operations for one episode."""
    operations = []
    episodes_base = REPO_ROOT / "shows" / "wonder-cabinet" / "episodes"
    target_dir = episodes_base / ep["slug"]

    # --- From existing canonical folder (rename/restructure) ---
    if ep["existing_canonical"]:
        old_dir = episodes_base / ep["existing_canonical"]
        if old_dir.exists() and old_dir.name != ep["slug"]:
            operations.append({
                "type": "rename_dir",
                "source": str(old_dir),
                "dest": str(target_dir),
                "note": f"Rename {ep['existing_canonical']} -> {ep['slug']}",
            })

    # --- From Whisper module ---
    if ep["whisper_dir"]:
        whisper_dir = WHISPER_BASE / ep["whisper_dir"]
        if whisper_dir.exists():
            for item in sorted(whisper_dir.iterdir()):
                if item.name.startswith("."):
                    continue

                if item.is_dir():
                    # Whisper output subdirs (per-segment with .srt, .json, etc.)
                    has_whisper_files = any(item.glob("*.srt")) or any(item.glob("*.json"))
                    if has_whisper_files:
                        operations.append({
                            "type": "copy_dir",
                            "source": str(item),
                            "dest": str(target_dir / "whisper" / item.name),
                            "note": f"Whisper segment: {item.name}/",
                        })
                    elif item.name == "raw_transcripts":
                        operations.append({
                            "type": "copy_dir",
                            "source": str(item),
                            "dest": str(target_dir / "whisper" / "raw_transcripts"),
                            "note": "Raw transcript SRTs",
                        })
                    continue

                # Files
                suffix = item.suffix.lower()
                name = item.name.lower()

                if suffix in (".mp3", ".wav", ".m4a"):
                    operations.append({
                        "type": "copy_file",
                        "source": str(item),
                        "dest": str(target_dir / "audio" / item.name),
                        "note": f"Audio: {item.name}",
                    })
                elif name == "formatted_transcript.md":
                    operations.append({
                        "type": "copy_file",
                        "source": str(item),
                        "dest": str(target_dir / "formatted_transcript.md"),
                        "note": "Formatted transcript",
                    })
                elif name == "chapters.md":
                    operations.append({
                        "type": "copy_file",
                        "source": str(item),
                        "dest": str(target_dir / "chapters.md"),
                        "note": "Chapter markers",
                    })
                elif suffix == ".srt" and "raw_transcripts" not in str(item):
                    operations.append({
                        "type": "copy_file",
                        "source": str(item),
                        "dest": str(target_dir / "captions.srt"),
                        "note": f"Combined SRT: {item.name}",
                    })
                elif suffix == ".txt" and "transcript" in name:
                    operations.append({
                        "type": "copy_file",
                        "source": str(item),
                        "dest": str(target_dir / "transcript.txt"),
                        "note": f"Plain transcript: {item.name}",
                    })
                elif suffix == ".docx":
                    # Skip Word docs — they're intermediaries
                    pass
                elif suffix == ".html":
                    # Skip HTML conversions — intermediaries for Drive upload
                    pass
                elif name == "upload_manifest.json":
                    # Legacy upload manifest — skip
                    pass

    # --- From publisher transcript cache ---
    if ep["publisher_transcript"]:
        pub_file = PUBLISHER_CACHE / ep["publisher_transcript"]
        if pub_file.exists():
            operations.append({
                "type": "copy_file",
                "source": str(pub_file),
                "dest": str(target_dir / "transcript.txt"),
                "note": f"Publisher cache transcript: {ep['publisher_transcript']}",
            })

    # --- From images directory ---
    if ep["image_dir"]:
        img_dir = IMAGES_BASE / ep["image_dir"]
        if img_dir.exists():
            for item in sorted(img_dir.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir() and item.name in ("source-files", "source", "originals"):
                    operations.append({
                        "type": "copy_dir",
                        "source": str(item),
                        "dest": str(target_dir / "images" / "originals"),
                        "note": f"Image originals: {item.name}/",
                        "merge": True,
                    })
                elif item.is_file():
                    operations.append({
                        "type": "copy_file",
                        "source": str(item),
                        "dest": str(target_dir / "images" / item.name),
                        "note": f"Episode artwork: {item.name}",
                    })

    for img_file in ep.get("image_files", []):
        img_path = IMAGES_BASE / img_file
        if img_path.exists():
            operations.append({
                "type": "copy_file",
                "source": str(img_path),
                "dest": str(target_dir / "images" / img_file),
                "note": f"Episode image: {img_file}",
            })

    # --- From existing canonical with non-standard structure (WC_106_Macfarlane) ---
    if ep["existing_canonical"] == "WC_106_Macfarlane":
        old_dir = episodes_base / "WC_106_Macfarlane"
        if old_dir.exists():
            # Audio nested in WC_S01_06_MacFarlane subfolder
            nested_audio = old_dir / "WC_S01_06_MacFarlane"
            if nested_audio.exists():
                for mp3 in nested_audio.glob("*.mp3"):
                    operations.append({
                        "type": "copy_file",
                        "source": str(mp3),
                        "dest": str(target_dir / "audio" / mp3.name),
                        "note": f"Audio from nested dir: {mp3.name}",
                    })
            # Images in non-standard "Images" folder
            images_dir = old_dir / "Images"
            if images_dir.exists():
                final_dir = images_dir / "final"
                originals_dir = images_dir / "originals"
                if final_dir.exists():
                    for img in final_dir.iterdir():
                        if not img.name.startswith("."):
                            operations.append({
                                "type": "copy_file",
                                "source": str(img),
                                "dest": str(target_dir / "images" / img.name),
                                "note": f"Final image: {img.name}",
                            })
                if originals_dir.exists():
                    operations.append({
                        "type": "copy_dir",
                        "source": str(originals_dir),
                        "dest": str(target_dir / "images" / "originals"),
                        "note": "Image originals from WC_106",
                        "merge": True,
                    })
            # .docx files — keep as-is in top level
            for docx in old_dir.glob("*.docx"):
                operations.append({
                    "type": "copy_file",
                    "source": str(docx),
                    "dest": str(target_dir / docx.name),
                    "note": f"Production doc: {docx.name}",
                })

    return operations


def create_manifest(ep: dict, target_dir: Path) -> dict:
    """Create manifest.json for a migrated episode."""
    now = datetime.now(timezone.utc).isoformat()

    # Detect stage from available files
    has_formatted = (target_dir / "formatted_transcript.md").exists()
    has_transcript = (target_dir / "transcript.txt").exists()
    has_audio = (target_dir / "audio").exists() and any((target_dir / "audio").iterdir()) if (target_dir / "audio").exists() else False

    if has_formatted:
        stage = "formatted"
    elif has_transcript:
        stage = "transcribed"
    elif has_audio:
        stage = "audio_ready"
    else:
        stage = "init"

    manifest = {
        "version": 1,
        "show": "wonder-cabinet",
        "slug": ep["slug"],
        "episodeNumber": ep["episode"],
        "season": 1,
        "guestName": ep["guest"],
        "title": ep.get("title", ""),
        "stage": stage,
        "files": {},
        "timestamps": {
            "created": now,
            "migrated": now,
        },
    }

    # Populate files section
    for key, filename in FILE_MAP.items():
        if key == "manifest":
            continue
        filepath = target_dir / filename
        manifest["files"][key] = {
            "path": filename,
            "status": "present" if filepath.exists() else "missing",
        }

    # Audio files
    audio_dir = target_dir / "audio"
    if audio_dir.exists():
        audio_files = sorted([f.name for f in audio_dir.iterdir() if f.suffix in (".mp3", ".wav", ".m4a")])
        if audio_files:
            manifest["files"]["audio"] = {
                "parts": [f"audio/{f}" for f in audio_files],
                "status": "present",
            }

    return manifest


def execute_operations(operations: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Execute copy operations. Returns (success_count, skip_count)."""
    success = 0
    skipped = 0

    for op in operations:
        source = Path(op["source"])
        dest = Path(op["dest"])

        if not source.exists():
            print(f"  SKIP (source missing): {op['note']}")
            skipped += 1
            continue

        if dest.exists() and op["type"] != "rename_dir" and not op.get("merge"):
            print(f"  SKIP (exists): {op['note']}")
            skipped += 1
            continue

        if dry_run:
            print(f"  WOULD {op['type']}: {op['note']}")
            print(f"         {source}")
            print(f"      -> {dest}")
            success += 1
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        if op["type"] == "rename_dir":
            if not dest.exists():
                shutil.copytree(source, dest)
                print(f"  COPIED dir: {op['note']}")
                success += 1
            else:
                print(f"  SKIP (target exists): {op['note']}")
                skipped += 1
        elif op["type"] == "copy_dir":
            if op.get("merge") and dest.exists():
                # Merge: copy individual files
                for item in Path(source).iterdir():
                    item_dest = dest / item.name
                    if not item_dest.exists():
                        if item.is_dir():
                            shutil.copytree(item, item_dest)
                        else:
                            shutil.copy2(item, item_dest)
                print(f"  MERGED dir: {op['note']}")
            else:
                shutil.copytree(source, dest)
                print(f"  COPIED dir: {op['note']}")
            success += 1
        elif op["type"] == "copy_file":
            shutil.copy2(source, dest)
            print(f"  COPIED: {op['note']}")
            success += 1

    return success, skipped


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate episode files to canonical structure")
    parser.add_argument("--dry-run", action="store_true", help="Preview without copying")
    parser.add_argument("--only", help="Migrate only episodes matching this prefix (e.g., WC_S01_05)")

    args = parser.parse_args()

    config = load_show_config()
    episodes_base = REPO_ROOT / "shows" / "wonder-cabinet" / "episodes"

    print("=" * 60)
    print("Episode Migration to Canonical Structure")
    print("=" * 60)
    print(f"Target: {episodes_base}/")
    if args.dry_run:
        print("[DRY RUN MODE]")
    print()

    total_success = 0
    total_skipped = 0

    for ep in WC_EPISODES:
        if args.only and args.only not in ep["slug"]:
            continue

        target_dir = episodes_base / ep["slug"]
        print(f"\n{'─' * 50}")
        print(f"Episode {ep['episode']}: {ep['guest']} ({ep['slug']})")
        print(f"Target: {target_dir}")

        # Plan operations
        operations = plan_episode_migration(ep)

        if not operations:
            print("  No files to migrate.")
            continue

        # Create directory tree first (unless dry run)
        if not args.dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            for subdir in SUBDIRS.values():
                (target_dir / subdir).mkdir(exist_ok=True)
            (target_dir / "images" / "originals").mkdir(parents=True, exist_ok=True)

        # Execute
        success, skipped = execute_operations(operations, dry_run=args.dry_run)
        total_success += success
        total_skipped += skipped

        # Create manifest
        if not args.dry_run:
            manifest = create_manifest(ep, target_dir)
            manifest_path = target_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            print(f"  MANIFEST: stage={manifest['stage']}")

    # Summary
    print(f"\n{'=' * 60}")
    print("Migration Summary")
    print(f"{'=' * 60}")
    action = "Would process" if args.dry_run else "Processed"
    print(f"{action}: {total_success} operations, {total_skipped} skipped")

    if not args.dry_run:
        print(f"\nVerify with:")
        print(f"  ls -la {episodes_base}/*/manifest.json")
        print(f"\nOriginal files were COPIED (not moved). Clean up module-internal copies")
        print(f"after verification if desired — they're gitignored anyway.")


if __name__ == "__main__":
    main()
