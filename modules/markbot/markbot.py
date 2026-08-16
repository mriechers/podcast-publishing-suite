#!/usr/bin/env python3
"""Your Helpful MarkBot! — Slack bot for podcast publishing notifications.

Centralized CLI for all Slack notifications in the publishing suite.
Posts as a single bot identity using slack-sdk (Bot Token auth).

Commands:
    transcribe-start   Post "job started" notification (prints thread_ts)
    transcribe-ready   Post "transcript ready" with Google Doc link
    schedule-alert     Post release readiness alerts (missing/drafted/scheduled)
    post               Post raw Block Kit JSON (for callers with custom blocks)

Usage:
    # Transcription notifications
    markbot.py transcribe-start --episode "007 - Robert MacFarlane" --channel C09QUBVE0DR
    markbot.py transcribe-ready --episode "007 - ..." --doc-url URL --channel C --thread-ts TS

    # Schedule alerts
    markbot.py schedule-alert --state missing --show "Wonder Cabinet" \
        --slot "Podcast Episode" --release-time "Saturday at 6 AM" --channel C09QUBVE0DR

    # Generic posting
    markbot.py post --blocks-json '{"blocks":[...]}' --channel C09QUBVE0DR

    # Dry run (all commands)
    markbot.py --dry-run transcribe-start --episode "Test" --channel X
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Slack client
# ---------------------------------------------------------------------------

def get_slack_client():
    """Create Slack WebClient from SLACK_BOT_TOKEN env var."""
    from slack_sdk import WebClient

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)
    return WebClient(token=token)


# ---------------------------------------------------------------------------
# Helpers — transcription
# ---------------------------------------------------------------------------

def extract_short_name(episode: str) -> str:
    """Extract short display name from episode string.

    '005 - Renee Bergland' -> 'Renee Bergland'
    'Some Episode'         -> 'Some Episode'
    """
    match = re.match(r"^\d+\s*[-–—]\s*(.+)$", episode)
    return match.group(1).strip() if match else episode


def extract_episode_number(episode: str) -> str:
    """Extract episode number prefix.

    '005 - Renee Bergland' -> '005'
    """
    match = re.match(r"^(\d+)\s*[-–—]", episode)
    return match.group(1) if match else ""


def extract_last_name(episode: str) -> str:
    """Extract guest last name from episode string.

    '005 - Renee Bergland' -> 'Bergland'
    """
    guest = extract_short_name(episode)
    parts = guest.split()
    return parts[-1] if parts else guest


def parse_chapters(chapters_path: str) -> list[str]:
    """Extract chapter lines from chapters.md.

    Looks for lines matching HH:MM:SS — Title pattern.
    """
    text = Path(chapters_path).read_text()
    chapters = []
    for line in text.splitlines():
        match = re.match(r"^\s*(\d{1,2}:\d{2}:\d{2})\s*[-–—]\s*(.+)$", line)
        if match:
            chapters.append(f"{match.group(1)} — {match.group(2).strip()}")
    return chapters


def extract_transcript_preview(transcript_path: str, max_chars: int = 200) -> str:
    """Extract first meaningful speaker line from formatted transcript.

    Skips YAML frontmatter and headers, finds the first '**Speaker:**' line.
    """
    text = Path(transcript_path).read_text()
    in_frontmatter = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not stripped or stripped.startswith("#"):
            continue
        preview = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        if len(preview) > max_chars:
            preview = preview[:max_chars].rsplit(" ", 1)[0] + "…"
        return preview
    return ""


# ---------------------------------------------------------------------------
# Message builders — transcription
# ---------------------------------------------------------------------------

def build_start_blocks(episode: str) -> list[dict]:
    """Build Block Kit blocks for the transcription start message."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":studio_microphone: *Transcription started* — {episode}\n\n"
                    "Working on a transcript for editing. I'll post a link here "
                    "when it's ready (usually about 20 minutes)."
                ),
            },
        }
    ]


def build_ready_blocks(
    episode: str,
    doc_url: str,
    chapters: list[str] | None = None,
    preview: str | None = None,
    speaker_note: str | None = None,
) -> list[dict]:
    """Build Block Kit blocks for the transcript ready message."""
    ep_num = extract_episode_number(episode)
    last_name = extract_last_name(episode)
    short_name = extract_short_name(episode)
    doc_label = f"{ep_num} {last_name} — Edit Transcript" if ep_num else short_name

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: *Transcript ready to edit* — {short_name}\n\n"
                    f":page_facing_up: *<{doc_url}|{doc_label}>*\n"
                    "Open in Google Docs to start reviewing."
                ),
            },
        },
        {"type": "divider"},
    ]

    if chapters:
        chapter_text = "\n".join(chapters)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Chapters:*\n{chapter_text}",
                },
            }
        )

    if preview:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Preview:*\n>{preview}",
                },
            }
        )

    if chapters or preview:
        blocks.append({"type": "divider"})

    if speaker_note:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":warning: {speaker_note}",
                    }
                ],
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "When editing, stick to speaker names and spelling corrections.\n"
                        "Structural changes can't sync back to the timed caption files.\n\n"
                        "Caption and chapter files were also generated for podcast platforms."
                    ),
                }
            ],
        }
    )

    return blocks


# ---------------------------------------------------------------------------
# Message builders — schedule alerts
# ---------------------------------------------------------------------------

def build_missing_blocks(
    show: str, slot_label: str, release_info: str,
) -> list[dict]:
    """Block Kit blocks for a missing-content alert."""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":rotating_light: ACTION NEEDED — {slot_label}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{show}* — *{slot_label}*\n"
                    f"No content found for the upcoming release.\n\n"
                    f":calendar: {release_info}"
                ),
            },
        },
        {"type": "divider"},
    ]


def build_drafted_blocks(
    show: str, slot_label: str, release_info: str, title: str | None = None,
) -> list[dict]:
    """Block Kit blocks for a draft-needs-scheduling alert."""
    title_line = f'\n:page_facing_up: Draft: *"{title}"*' if title else ""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":warning: Draft Needs Scheduling — {slot_label}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{show}* — *{slot_label}*\n"
                    f"A draft exists but hasn't been scheduled yet.{title_line}\n\n"
                    f":calendar: {release_info}"
                ),
            },
        },
        {"type": "divider"},
    ]


def build_scheduled_blocks(
    show: str,
    slot_label: str,
    release_info: str,
    title: str | None = None,
    url: str | None = None,
) -> list[dict]:
    """Block Kit blocks for an on-track scheduled alert."""
    title_line = f'\n:white_check_mark: *"{title}"*' if title else ""
    url_line = f"\n:link: <{url}|View post>" if url else ""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":white_check_mark: On Track — {slot_label}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{show}* — *{slot_label}*\n"
                    f"Content is scheduled and ready to go.{title_line}{url_line}\n\n"
                    f":calendar: {release_info}"
                ),
            },
        },
        {"type": "divider"},
    ]


# ---------------------------------------------------------------------------
# Message builders — ghost import
# ---------------------------------------------------------------------------

GHOST_SITE_URL = "wondercabinetproductions.com"


def build_import_start_blocks(show: str, episode: str) -> list[dict]:
    """Block Kit blocks for import-started notification."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":incoming_envelope: *New episode importing* — {show}\n\n"
                    f"*{episode}*\n"
                    f"A new episode has been scheduled on PRX and is being "
                    f"imported into {GHOST_SITE_URL}."
                ),
            },
        },
    ]


def build_import_draft_blocks(show: str, episode: str, ghost_url: str) -> list[dict]:
    """Block Kit blocks for draft-ready notification."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":pencil2: *Draft ready for review* — {show}\n\n"
                    f"*{episode}*\n"
                    f"The episode has been imported as a draft. "
                    f"Review it before publishing.\n\n"
                    f":link: <{ghost_url}|Open in Ghost>"
                ),
            },
        },
    ]


def build_import_scheduled_blocks(
    show: str, episode: str, ghost_url: str, schedule_time: str
) -> list[dict]:
    """Block Kit blocks for post-scheduled notification."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":calendar: *Episode scheduled* — {show}\n\n"
                    f"*{episode}*\n"
                    f"Scheduled for release: {schedule_time}\n\n"
                    f":link: <{ghost_url}|Preview post>"
                ),
            },
        },
    ]


def build_import_failed_blocks(show: str, episode: str, error: str) -> list[dict]:
    """Block Kit blocks for import-failed notification."""
    if len(error) > 300:
        error = error[:297] + "..."
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":x: *Import failed* — {show}\n\n"
                    f"*{episode}*\n"
                    f"```{error}```\n"
                    f"Check the CLI output for full details."
                ),
            },
        },
    ]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_transcribe_start(args):
    """Send the 'job started' message. Prints thread_ts to stdout."""
    blocks = build_start_blocks(args.episode)

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    resp = client.chat_postMessage(
        channel=args.channel,
        blocks=blocks,
        text=f"Transcription started — {args.episode}",
    )
    print(resp["ts"])


def cmd_transcribe_ready(args):
    """Send the 'transcript ready' message as a threaded reply."""
    chapters = None
    if args.chapters_file and Path(args.chapters_file).exists():
        chapters = parse_chapters(args.chapters_file)

    preview = None
    if args.transcript_file and Path(args.transcript_file).exists():
        preview = extract_transcript_preview(args.transcript_file)

    speaker_note = args.speaker_note if args.speaker_note else None

    blocks = build_ready_blocks(
        episode=args.episode,
        doc_url=args.doc_url,
        chapters=chapters,
        preview=preview,
        speaker_note=speaker_note,
    )

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    short_name = extract_short_name(args.episode)
    client.chat_postMessage(
        channel=args.channel,
        thread_ts=args.thread_ts,
        reply_broadcast=True,
        blocks=blocks,
        text=f"Transcript ready to edit — {short_name}",
    )


def cmd_schedule_alert(args):
    """Send a release readiness alert."""
    builders = {
        "missing": build_missing_blocks,
        "drafted": build_drafted_blocks,
        "scheduled": build_scheduled_blocks,
    }

    builder = builders[args.state]

    if args.state == "missing":
        blocks = builder(args.show, args.slot, args.release_time)
    elif args.state == "drafted":
        blocks = builder(args.show, args.slot, args.release_time, title=args.title)
    elif args.state == "scheduled":
        blocks = builder(
            args.show, args.slot, args.release_time,
            title=args.title, url=args.url,
        )

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    state_labels = {
        "missing": "ACTION NEEDED",
        "drafted": "Draft Needs Scheduling",
        "scheduled": "On Track",
    }
    client.chat_postMessage(
        channel=args.channel,
        blocks=blocks,
        text=f"{state_labels[args.state]} — {args.show} — {args.slot}",
    )


def cmd_post(args):
    """Post raw Block Kit JSON to a channel."""
    blocks_input = args.blocks_json
    if blocks_input == "-":
        blocks_input = sys.stdin.read()

    try:
        payload = json.loads(blocks_input)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON — {e}", file=sys.stderr)
        sys.exit(1)

    # Accept either {"blocks": [...]} or bare [...]
    if isinstance(payload, list):
        blocks = payload
    elif isinstance(payload, dict) and "blocks" in payload:
        blocks = payload["blocks"]
    else:
        print('Error: JSON must be a list or {"blocks": [...]}', file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    kwargs = {
        "channel": args.channel,
        "blocks": blocks,
        "text": "Notification from Your Helpful MarkBot!",
    }
    if args.thread_ts:
        kwargs["thread_ts"] = args.thread_ts
    if args.reply_broadcast:
        kwargs["reply_broadcast"] = True

    client.chat_postMessage(**kwargs)


def cmd_ghost_import(args):
    """Send a ghost import lifecycle notification."""
    builders = {
        "start": lambda: build_import_start_blocks(args.show, args.episode),
        "draft": lambda: build_import_draft_blocks(
            args.show, args.episode, args.ghost_url,
        ),
        "scheduled": lambda: build_import_scheduled_blocks(
            args.show, args.episode, args.ghost_url, args.schedule_time,
        ),
        "failed": lambda: build_import_failed_blocks(
            args.show, args.episode, args.error,
        ),
    }

    blocks = builders[args.state]()

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    state_labels = {
        "start": f"Importing {args.episode}",
        "draft": f"Draft ready — {args.episode}",
        "scheduled": f"Scheduled — {args.episode}",
        "failed": f"Import failed — {args.episode}",
    }
    kwargs = {
        "channel": args.channel,
        "blocks": blocks,
        "text": state_labels[args.state],
    }
    if args.thread_ts:
        kwargs["thread_ts"] = args.thread_ts
    if args.reply_broadcast:
        kwargs["reply_broadcast"] = True
    resp = client.chat_postMessage(**kwargs)
    # Print resp["ts"] for every state so callers can capture for later threading.
    print(resp["ts"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="markbot.py",
        description="Your Helpful MarkBot! — Slack bot for podcast publishing notifications",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print Block Kit JSON without posting to Slack",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- transcribe-start ---
    p_ts = sub.add_parser("transcribe-start", help="Post transcription-started message")
    p_ts.add_argument("--episode", required=True, help='e.g. "005 - Renee Bergland"')
    p_ts.add_argument("--channel", required=True, help="Slack channel ID")

    # --- transcribe-ready ---
    p_tr = sub.add_parser("transcribe-ready", help="Post transcript-ready message")
    p_tr.add_argument("--episode", required=True, help='e.g. "005 - Renee Bergland"')
    p_tr.add_argument("--doc-url", required=True, help="Google Docs URL for transcript")
    p_tr.add_argument("--chapters-file", help="Path to chapters.md")
    p_tr.add_argument("--transcript-file", help="Path to formatted_transcript.md")
    p_tr.add_argument("--speaker-note", help="Optional QC note about speaker attribution")
    p_tr.add_argument("--channel", required=True, help="Slack channel ID")
    p_tr.add_argument("--thread-ts", required=True, help="Thread timestamp from start message")

    # --- schedule-alert ---
    p_sa = sub.add_parser("schedule-alert", help="Post release readiness alert")
    p_sa.add_argument(
        "--state", required=True, choices=["missing", "drafted", "scheduled"],
        help="Readiness state",
    )
    p_sa.add_argument("--show", required=True, help='e.g. "Wonder Cabinet"')
    p_sa.add_argument("--slot", required=True, help='e.g. "Podcast Episode"')
    p_sa.add_argument("--release-time", required=True, help='e.g. "Saturday, March 7 at 6:00 AM CST (12h from now)"')
    p_sa.add_argument("--title", help="Ghost post title (for drafted/scheduled)")
    p_sa.add_argument("--url", help="Ghost post URL (for scheduled)")
    p_sa.add_argument("--channel", required=True, help="Slack channel ID")

    # --- post ---
    p_post = sub.add_parser("post", help="Post raw Block Kit JSON")
    p_post.add_argument(
        "--blocks-json", required=True,
        help='JSON string or "-" to read from stdin',
    )
    p_post.add_argument("--channel", required=True, help="Slack channel ID")
    p_post.add_argument("--thread-ts", help="Thread timestamp for reply")
    p_post.add_argument("--reply-broadcast", action="store_true", help="Broadcast threaded reply to channel")

    # --- ghost-import ---
    p_gi = sub.add_parser("ghost-import", help="Ghost import lifecycle notification")
    p_gi.add_argument(
        "--state", required=True,
        choices=["start", "draft", "scheduled", "failed"],
        help="Import lifecycle state",
    )
    p_gi.add_argument("--show", required=True, help='e.g. "Wonder Cabinet"')
    p_gi.add_argument("--episode", required=True, help="Episode title")
    p_gi.add_argument("--ghost-url", help="Ghost editor or public URL (for draft/scheduled)")
    p_gi.add_argument("--schedule-time", help="Scheduled release time (for scheduled)")
    p_gi.add_argument("--error", help="Error message (for failed)")
    p_gi.add_argument("--channel", required=True, help="Slack channel ID")
    p_gi.add_argument("--thread-ts", help="Thread timestamp for threading replies")
    p_gi.add_argument(
        "--reply-broadcast", action="store_true",
        help="When threading, also broadcast the reply to the main channel feed",
    )

    args = parser.parse_args()

    commands = {
        "transcribe-start": cmd_transcribe_start,
        "transcribe-ready": cmd_transcribe_ready,
        "schedule-alert": cmd_schedule_alert,
        "post": cmd_post,
        "ghost-import": cmd_ghost_import,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
