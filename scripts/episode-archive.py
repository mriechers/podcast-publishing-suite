#!/usr/bin/env python3
"""Upload episode deliverables to Google Drive from canonical folder.

This script prepares the upload manifest and generates the commands/instructions
for uploading via the Google Docs MCP server. Since MCP tools are only available
inside Claude Code sessions, the actual upload is performed by the wc-transcribe
skill or manually.

Usage:
    # Show what would be uploaded
    python3 scripts/episode-archive.py --episode-dir shows/wonder-cabinet/episodes/WC_S01_06_Robert_MacFarlane --dry-run

    # Prepare upload manifest (updates manifest.json with upload plan)
    python3 scripts/episode-archive.py --episode-dir shows/wonder-cabinet/episodes/WC_S01_06_Robert_MacFarlane

    # After MCP upload completes, record Drive file IDs
    python3 scripts/episode-archive.py --episode-dir ... --record-upload \
        --file-key formatted_transcript --drive-file-id XXXX
"""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_manifest(episode_dir: Path) -> dict:
    manifest_path = episode_dir / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"No manifest.json found in {episode_dir}")
    return json.loads(manifest_path.read_text())


def save_manifest(episode_dir: Path, manifest: dict):
    manifest_path = episode_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def get_upload_plan(episode_dir: Path, manifest: dict) -> list[dict]:
    """Build list of files to upload with their Drive metadata."""
    files = manifest.get("files", {})
    guest_last = manifest.get("guestName", "Unknown").split()[-1]
    ep_num = manifest.get("episodeNumber", "")
    ep_str = f"{ep_num:03d}" if isinstance(ep_num, int) else str(ep_num)

    plan = []

    # Formatted transcript -> Google Doc
    ft = files.get("formatted_transcript", {})
    ft_path = episode_dir / ft.get("path", "formatted_transcript.md")
    if ft_path.exists():
        plan.append({
            "file_key": "formatted_transcript",
            "local_path": str(ft_path),
            "drive_name": f"{ep_str} {guest_last} — Edit Transcript",
            "mime_type": "text/html",
            "convert_to_google_doc": True,
            "needs_html_conversion": True,
        })

    # Chapters -> Google Doc
    ch = files.get("chapters", {})
    ch_path = episode_dir / ch.get("path", "chapters.md")
    if ch_path.exists():
        plan.append({
            "file_key": "chapters",
            "local_path": str(ch_path),
            "drive_name": f"{ep_str} {guest_last} — Chapters",
            "mime_type": "text/html",
            "convert_to_google_doc": True,
            "needs_html_conversion": True,
        })

    # Captions SRT -> raw file
    cap = files.get("captions", {})
    cap_path = episode_dir / cap.get("path", "captions.srt")
    if cap_path.exists():
        plan.append({
            "file_key": "captions",
            "local_path": str(cap_path),
            "drive_name": f"{ep_str} {guest_last} — Captions.srt",
            "mime_type": "application/x-subrip",
            "convert_to_google_doc": False,
            "needs_html_conversion": False,
        })

    return plan


def convert_md_to_html(md_path: Path) -> str:
    """Convert markdown file to HTML string."""
    try:
        import markdown
        md_text = md_path.read_text()
        return markdown.markdown(md_text)
    except ImportError:
        # Fallback: use python3 -c
        result = subprocess.run(
            ["python3", "-c", f"""
import markdown, pathlib
md = pathlib.Path('{md_path}').read_text()
print(markdown.markdown(md))
"""],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            sys.exit(f"Failed to convert {md_path} to HTML: {result.stderr}")
        return result.stdout


def prepare_base64(file_path: Path, needs_html: bool) -> str:
    """Base64-encode a file, optionally converting from markdown to HTML first."""
    if needs_html:
        html = convert_md_to_html(file_path)
        return base64.b64encode(html.encode()).decode()
    else:
        return base64.b64encode(file_path.read_bytes()).decode()


def main():
    parser = argparse.ArgumentParser(description="Upload episode deliverables to Google Drive")
    parser.add_argument("--episode-dir", required=True, help="Path to canonical episode directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded")
    parser.add_argument("--prepare-base64", action="store_true",
                        help="Generate base64-encoded files for MCP upload")
    parser.add_argument("--record-upload", action="store_true",
                        help="Record a completed upload in manifest")
    parser.add_argument("--file-key", help="File key to record (with --record-upload)")
    parser.add_argument("--drive-file-id", help="Drive file ID to record (with --record-upload)")
    parser.add_argument("--drive-doc-url", help="Drive document URL to record (with --record-upload)")

    args = parser.parse_args()

    episode_dir = Path(args.episode_dir)
    if not episode_dir.is_absolute():
        episode_dir = REPO_ROOT / episode_dir

    manifest = load_manifest(episode_dir)

    # Record upload mode
    if args.record_upload:
        if not args.file_key:
            sys.exit("--file-key required with --record-upload")
        drive_info = manifest.setdefault("google_drive", {})
        if args.drive_file_id:
            drive_info[f"{args.file_key}_file_id"] = args.drive_file_id
        if args.drive_doc_url:
            drive_info[f"{args.file_key}_url"] = args.drive_doc_url
        # Check if all deliverables have been uploaded
        upload_keys = ["formatted_transcript", "chapters", "captions"]
        all_uploaded = all(
            drive_info.get(f"{k}_file_id") for k in upload_keys
            if manifest.get("files", {}).get(k, {}).get("status") == "present"
        )
        if all_uploaded and manifest.get("stage") in ("formatted", "transcribed"):
            manifest["stage"] = "uploaded"
            from datetime import datetime, timezone
            manifest.setdefault("timestamps", {})["uploaded_to_drive"] = datetime.now(timezone.utc).isoformat()
        save_manifest(episode_dir, manifest)
        print(f"Recorded {args.file_key} upload in manifest")
        if all_uploaded:
            print("All deliverables uploaded — stage advanced to 'uploaded'")
        return

    # Build upload plan
    plan = get_upload_plan(episode_dir, manifest)
    drive_folder_id = manifest.get("google_drive", {}).get("episode_folder_id", "UNKNOWN")

    if not plan:
        print("No deliverables found to upload.")
        return

    print(f"Episode: {manifest.get('slug', episode_dir.name)}")
    print(f"Drive folder: {drive_folder_id}")
    print(f"\nUpload plan ({len(plan)} files):")
    print()

    for item in plan:
        status = "exists" if Path(item["local_path"]).exists() else "MISSING"
        convert_note = " (md→html→Google Doc)" if item["convert_to_google_doc"] else ""
        print(f"  [{status}] {item['file_key']}")
        print(f"         Local: {item['local_path']}")
        print(f"         Drive: {item['drive_name']}{convert_note}")
        print()

    if args.dry_run:
        print("[DRY RUN] No uploads performed.")
        return

    if args.prepare_base64:
        # Write base64-encoded versions for MCP upload
        print("Preparing base64-encoded files...")
        for item in plan:
            local = Path(item["local_path"])
            if not local.exists():
                print(f"  SKIP (missing): {item['file_key']}")
                continue
            b64 = prepare_base64(local, item["needs_html_conversion"])
            b64_path = local.with_suffix(local.suffix + ".b64")
            b64_path.write_text(b64)
            print(f"  Wrote: {b64_path} ({len(b64)} chars)")
        print("\nBase64 files ready. Use MCP uploadFile with fileContent from these files.")
        return

    # Default: just show the plan and instructions for Claude Code
    print("To upload, use the /wc-transcribe skill or run in Claude Code with MCP tools.")
    print(f"Drive folder ID: {drive_folder_id}")


if __name__ == "__main__":
    main()
