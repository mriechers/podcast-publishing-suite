# Markbot Ghost Import Notifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Slack notifications via markbot to the Ghost import pipeline so producers know when episodes are being imported, when drafts are ready for review, when posts are scheduled, and when imports fail.

**Architecture:** New `ghost-import` command in `markbot.py` with `--state start|draft|scheduled|failed`, plus a lightweight `notifications.py` module in the publisher that shells out to markbot via subprocess. Show configs get a new `slack.channel` field. Notifications are best-effort — failures log a warning but never block the import pipeline.

**Tech Stack:** Python 3.11+, slack-sdk (markbot side only), subprocess (publisher side), existing show config JSON

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `modules/markbot/markbot.py` | Modify | Add `ghost-import` command with 4 states and Block Kit builders |
| `modules/prx-to-ghost-publisher/src/notifications.py` | Create | Thin wrapper that locates markbot and shells out; never raises on failure |
| `modules/prx-to-ghost-publisher/src/main.py` | Modify | Call notification hooks at import start, draft creation, and failure |
| `modules/prx-to-ghost-publisher/tests/test_notifications.py` | Create | Unit tests for the notification module |
| `modules/markbot/tests/test_markbot_ghost_import.py` | Create | Unit tests for the ghost-import block builders |
| `shows/wonder-cabinet/config.json` | Modify | Add `slack.channel` field |
| `shows/luminous/config.json` | Modify | Add `slack.channel` field |

---

### Task 1: Add `slack.channel` to Show Configs

**Files:**
- Modify: `shows/wonder-cabinet/config.json`
- Modify: `shows/luminous/config.json`

- [ ] **Step 1: Add slack section to Wonder Cabinet config**

Add a `"slack"` key after the `"schedule"` section in `shows/wonder-cabinet/config.json`:

```json
"slack": {
  "channel": "C09QUBVE0DR"
}
```

Channel `C09QUBVE0DR` is `#all-wonder-cabinet-productions` (from markbot CLAUDE.md).

- [ ] **Step 2: Add slack section to Luminous config**

Add a `"slack"` key after the `"schedule"` section in `shows/luminous/config.json`:

```json
"slack": {
  "channel": "C09QUBVE0DR"
}
```

Same channel for now — both shows share the production channel.

- [ ] **Step 3: Commit**

```bash
git add shows/wonder-cabinet/config.json shows/luminous/config.json
git commit -m "config: Add slack.channel to show configs for markbot notifications"
```

---

### Task 2: Add `ghost-import` Block Kit Builders to Markbot

**Files:**
- Modify: `modules/markbot/markbot.py`
- Create: `modules/markbot/tests/test_markbot_ghost_import.py`

- [ ] **Step 1: Write tests for the block builders**

Create `modules/markbot/tests/test_markbot_ghost_import.py`:

```python
"""Tests for ghost-import Block Kit message builders."""

import sys
from pathlib import Path

# Add markbot to path so we can import it
sys.path.insert(0, str(Path(__file__).parent.parent))

import markbot


def test_build_import_start_blocks():
    """Start blocks include show name, episode title, and site URL."""
    blocks = markbot.build_import_start_blocks(
        show="Wonder Cabinet",
        episode="Dekila Chungyalpa on the Sacred Feminine and the Living Earth",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "Wonder Cabinet" in text
    assert "Dekila Chungyalpa" in text
    assert "wondercabinetproductions.com" in text


def test_build_import_draft_blocks():
    """Draft blocks include episode title and Ghost admin link."""
    blocks = markbot.build_import_draft_blocks(
        show="Wonder Cabinet",
        episode="Dekila Chungyalpa on the Sacred Feminine and the Living Earth",
        ghost_url="https://wonder-cabinet.ghost.io/ghost/#/editor/post/abc123",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "draft" in text.lower() or "review" in text.lower()
    assert "ghost.io" in text


def test_build_import_scheduled_blocks():
    """Scheduled blocks include episode title and public URL."""
    blocks = markbot.build_import_scheduled_blocks(
        show="Wonder Cabinet",
        episode="Dekila Chungyalpa on the Sacred Feminine and the Living Earth",
        ghost_url="https://wondercabinetproductions.com/dekila-chungyalpa/",
        schedule_time="Saturday, April 12 at 6:00 AM CDT",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "scheduled" in text.lower()
    assert "Saturday" in text


def test_build_import_failed_blocks():
    """Failed blocks include episode title and error message."""
    blocks = markbot.build_import_failed_blocks(
        show="Wonder Cabinet",
        episode="Dekila Chungyalpa on the Sacred Feminine and the Living Earth",
        error="Validation error: feature_image_alt exceeds 191 characters",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "failed" in text.lower() or "error" in text.lower()
    assert "191 characters" in text


def test_build_import_failed_blocks_truncates_long_error():
    """Long error messages are truncated to keep Slack blocks readable."""
    long_error = "x" * 500
    blocks = markbot.build_import_failed_blocks(
        show="Wonder Cabinet",
        episode="Test Episode",
        error=long_error,
    )
    text = blocks[0]["text"]["text"]
    # Slack block text limit is 3000 chars; our error should be truncated well before that
    assert len(text) < 3000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd modules/markbot && python3 -m pytest tests/test_markbot_ghost_import.py -v
```

Expected: FAIL — `build_import_start_blocks` not found in markbot module.

- [ ] **Step 3: Implement the block builders in markbot.py**

Add these functions after the existing `build_scheduled_blocks` function (after line 316 in `markbot.py`):

```python
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


def build_import_draft_blocks(
    show: str, episode: str, ghost_url: str,
) -> list[dict]:
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
    show: str, episode: str, ghost_url: str, schedule_time: str,
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
                    f":link: <{ghost_url}|View post>"
                ),
            },
        },
    ]


def build_import_failed_blocks(
    show: str, episode: str, error: str,
) -> list[dict]:
    """Block Kit blocks for import-failed notification."""
    # Truncate error to keep Slack block text under limits
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd modules/markbot && python3 -m pytest tests/test_markbot_ghost_import.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/markbot/markbot.py modules/markbot/tests/test_markbot_ghost_import.py
git commit -m "feat(markbot): Add ghost-import Block Kit builders for import lifecycle notifications"
```

---

### Task 3: Add `ghost-import` CLI Command to Markbot

**Files:**
- Modify: `modules/markbot/markbot.py`

- [ ] **Step 1: Add the command handler function**

Add after the existing `cmd_post` function (after line 448):

```python
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
    resp = client.chat_postMessage(**kwargs)
    # Print thread_ts for start messages (callers can capture for threading)
    if args.state == "start":
        print(resp["ts"])
```

- [ ] **Step 2: Add the subparser**

Add in the `main()` function, after the `post` subparser (after line 503):

```python
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
```

- [ ] **Step 3: Register the command in the dispatch dict**

Update the `commands` dict in `main()` (around line 507):

```python
    commands = {
        "transcribe-start": cmd_transcribe_start,
        "transcribe-ready": cmd_transcribe_ready,
        "schedule-alert": cmd_schedule_alert,
        "post": cmd_post,
        "ghost-import": cmd_ghost_import,
    }
```

- [ ] **Step 4: Test via dry run**

```bash
cd modules/markbot && python3 markbot.py --dry-run ghost-import \
  --state start --show "Wonder Cabinet" \
  --episode "Test Episode" --channel C09QUBVE0DR

python3 markbot.py --dry-run ghost-import \
  --state draft --show "Wonder Cabinet" \
  --episode "Test Episode" \
  --ghost-url "https://wonder-cabinet.ghost.io/ghost/#/editor/post/abc" \
  --channel C09QUBVE0DR

python3 markbot.py --dry-run ghost-import \
  --state failed --show "Wonder Cabinet" \
  --episode "Test Episode" \
  --error "Validation error: something broke" \
  --channel C09QUBVE0DR
```

Expected: Block Kit JSON printed to stdout for each.

- [ ] **Step 5: Commit**

```bash
git add modules/markbot/markbot.py
git commit -m "feat(markbot): Add ghost-import CLI command with start/draft/scheduled/failed states"
```

---

### Task 4: Create `notifications.py` in the Publisher

**Files:**
- Create: `modules/prx-to-ghost-publisher/src/notifications.py`
- Create: `modules/prx-to-ghost-publisher/tests/test_notifications.py`

- [ ] **Step 1: Write tests for the notification module**

Create `modules/prx-to-ghost-publisher/tests/test_notifications.py`:

```python
"""Tests for the markbot notification wrapper."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.notifications import MarkbotNotifier


@pytest.fixture
def notifier(tmp_path: Path) -> MarkbotNotifier:
    """Notifier with a fake markbot path."""
    fake_markbot = tmp_path / "markbot.py"
    fake_markbot.write_text("#!/usr/bin/env python3\n")
    return MarkbotNotifier(
        markbot_path=fake_markbot,
        channel="C09QUBVE0DR",
        show="Wonder Cabinet",
    )


def test_notifier_disabled_when_markbot_missing():
    """Notifier silently does nothing when markbot.py doesn't exist."""
    n = MarkbotNotifier(
        markbot_path=Path("/nonexistent/markbot.py"),
        channel="C09QUBVE0DR",
        show="Wonder Cabinet",
    )
    assert not n.enabled
    # Should not raise
    n.import_start("Test Episode")


def test_notifier_disabled_when_no_channel():
    """Notifier is disabled when channel is empty."""
    n = MarkbotNotifier(
        markbot_path=Path("/some/markbot.py"),
        channel="",
        show="Wonder Cabinet",
    )
    assert not n.enabled


@patch("src.notifications.subprocess.run")
def test_import_start_calls_markbot(mock_run: MagicMock, notifier: MarkbotNotifier):
    """import_start shells out to markbot with correct args."""
    mock_run.return_value = MagicMock(returncode=0, stdout="1234567890.123456\n")
    ts = notifier.import_start("Test Episode")

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "ghost-import" in args
    assert "--state" in args
    assert "start" in args
    assert "--episode" in args
    assert "Test Episode" in args
    assert ts == "1234567890.123456"


@patch("src.notifications.subprocess.run")
def test_import_draft_calls_markbot(mock_run: MagicMock, notifier: MarkbotNotifier):
    """import_draft shells out to markbot with ghost URL."""
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    notifier.thread_ts = "111.222"
    notifier.import_draft(
        episode="Test Episode",
        ghost_post_id="abc123",
        ghost_admin_url="https://wonder-cabinet.ghost.io",
    )

    args = mock_run.call_args[0][0]
    assert "draft" in args
    assert "--ghost-url" in args
    assert "--thread-ts" in args
    assert "111.222" in args


@patch("src.notifications.subprocess.run")
def test_import_failed_calls_markbot(mock_run: MagicMock, notifier: MarkbotNotifier):
    """import_failed shells out to markbot with error message."""
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    notifier.import_failed("Test Episode", "Something went wrong")

    args = mock_run.call_args[0][0]
    assert "failed" in args
    assert "--error" in args
    assert "Something went wrong" in args


@patch("src.notifications.subprocess.run")
def test_subprocess_failure_does_not_raise(mock_run: MagicMock, notifier: MarkbotNotifier):
    """Markbot subprocess failures are logged but never raise."""
    mock_run.side_effect = OSError("No such file")
    # Should not raise
    notifier.import_start("Test Episode")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_notifications.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.notifications'`

- [ ] **Step 3: Implement `notifications.py`**

Create `modules/prx-to-ghost-publisher/src/notifications.py`:

```python
"""Markbot notification wrapper for Ghost import lifecycle.

Shells out to markbot.py for Slack notifications. All methods are
best-effort — subprocess failures are logged but never raised, so
the import pipeline is never blocked by notification issues.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class MarkbotNotifier:
    """Thin wrapper around markbot.py subprocess calls.

    Args:
        markbot_path: Absolute path to markbot.py.
        channel: Slack channel ID for notifications.
        show: Show name (e.g. "Wonder Cabinet").
    """

    def __init__(
        self,
        markbot_path: Path,
        channel: str,
        show: str,
    ) -> None:
        self.markbot_path = markbot_path
        self.channel = channel
        self.show = show
        self.thread_ts: str | None = None
        self.enabled = bool(channel) and markbot_path.is_file()

        if not self.enabled:
            if not channel:
                logger.debug("Markbot notifications disabled: no channel configured")
            elif not markbot_path.is_file():
                logger.debug(f"Markbot notifications disabled: {markbot_path} not found")

    def _run(self, args: list[str]) -> str:
        """Run markbot with args. Returns stdout. Never raises."""
        if not self.enabled:
            return ""
        cmd = [sys.executable, str(self.markbot_path)] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    f"Markbot exited {result.returncode}: {result.stderr.strip()}"
                )
            return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Markbot notification failed: {e}")
            return ""

    def import_start(self, episode: str) -> str | None:
        """Send 'import started' notification. Returns thread_ts for threading."""
        ts = self._run([
            "ghost-import",
            "--state", "start",
            "--show", self.show,
            "--episode", episode,
            "--channel", self.channel,
        ])
        if ts:
            self.thread_ts = ts
        return ts or None

    def import_draft(
        self,
        episode: str,
        ghost_post_id: str,
        ghost_admin_url: str,
    ) -> None:
        """Send 'draft ready for review' notification."""
        editor_url = f"{ghost_admin_url.rstrip('/')}/ghost/#/editor/post/{ghost_post_id}"
        args = [
            "ghost-import",
            "--state", "draft",
            "--show", self.show,
            "--episode", episode,
            "--ghost-url", editor_url,
            "--channel", self.channel,
        ]
        if self.thread_ts:
            args += ["--thread-ts", self.thread_ts]
        self._run(args)

    def import_scheduled(
        self,
        episode: str,
        ghost_url: str,
        schedule_time: str,
    ) -> None:
        """Send 'episode scheduled' notification."""
        args = [
            "ghost-import",
            "--state", "scheduled",
            "--show", self.show,
            "--episode", episode,
            "--ghost-url", ghost_url,
            "--schedule-time", schedule_time,
            "--channel", self.channel,
        ]
        if self.thread_ts:
            args += ["--thread-ts", self.thread_ts]
        self._run(args)

    def import_failed(self, episode: str, error: str) -> None:
        """Send 'import failed' notification."""
        args = [
            "ghost-import",
            "--state", "failed",
            "--show", self.show,
            "--episode", episode,
            "--error", error,
            "--channel", self.channel,
        ]
        if self.thread_ts:
            args += ["--thread-ts", self.thread_ts]
        self._run(args)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_notifications.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/prx-to-ghost-publisher/src/notifications.py modules/prx-to-ghost-publisher/tests/test_notifications.py
git commit -m "feat: Add MarkbotNotifier wrapper for Ghost import lifecycle notifications"
```

---

### Task 5: Wire Notifications into the Publisher's Sync Pipeline

**Files:**
- Modify: `modules/prx-to-ghost-publisher/src/main.py:182-542` (sync_episodes function)
- Modify: `modules/prx-to-ghost-publisher/src/main.py:626-780` (_run_sync function, notifier initialization)

- [ ] **Step 1: Add import for MarkbotNotifier**

At the top of `main.py`, add after the existing imports (around line 61):

```python
from .notifications import MarkbotNotifier
```

- [ ] **Step 2: Add `notifier` parameter to `sync_episodes()`**

Add `notifier: Optional[MarkbotNotifier] = None` to the function signature at line 182. Add it after the `transcript_dir` parameter:

```python
def sync_episodes(
    episodes: list[Episode],
    client: GhostClient,
    tracker: StateTracker,
    status: str = "draft",
    dry_run: bool = False,
    primary_tag: str = "Wonder Cabinet",
    feed_type: str = "ttbook",
    feed_url: str = "",
    export_transcripts: bool = False,
    generate_peaks: bool = False,
    peaks_dir: Optional[Path] = None,
    ghost_url: str = "",
    upload_audio: bool = False,
    dovetail_client: Optional[DovetailClient] = None,
    ghost_site_url: str = "",
    transcript_dir: Optional[Path] = None,
    notifier: Optional[MarkbotNotifier] = None,
) -> SyncResult:
```

- [ ] **Step 3: Add notification hooks in the sync loop**

Three insertion points in the episode loop inside `sync_episodes()`:

**3a. Import start — after the duplicate check (line 233), before image processing (line 250):**

Insert after `result.new_episodes.append(...)` block (after line 248):

```python
        # Notify: import started
        if notifier and not dry_run:
            notifier.import_start(episode.title)
```

**3b. Draft ready — after successful post creation (after line 530):**

Insert after `result.published_posts.append(...)` (after line 531):

```python
            # Notify: draft ready for review
            if notifier:
                notifier.import_draft(
                    episode=episode.title,
                    ghost_post_id=ghost_post_id,
                    ghost_admin_url=ghost_url or client.api_url.rsplit("/ghost/api", 1)[0],
                )
```

**3c. Import failed — in the except block (after line 540):**

Insert after `result.failed += 1` (after line 540):

```python
            # Notify: import failed
            if notifier:
                notifier.import_failed(episode.title, str(e))
```

- [ ] **Step 4: Initialize notifier in `_run_sync()`**

In `_run_sync()`, after the Ghost client is created and before `sync_episodes()` is called, initialize the notifier. Find the section where `sync_episodes()` is called (around line 770-790) and add notifier creation before it.

Find the meta-repo root relative to the publisher module:

```python
        # Initialize markbot notifier (best-effort)
        notifier = None
        if not dry_run:
            show_name = "Luminous" if feed_type == "luminous" else "Wonder Cabinet"
            show_slug = "luminous" if feed_type == "luminous" else "wonder-cabinet"

            # Resolve markbot path relative to meta-repo root
            publisher_dir = Path(__file__).resolve().parent.parent  # src/ -> publisher root
            meta_repo_root = publisher_dir.parent.parent  # modules/ -> meta-repo root
            markbot_path = meta_repo_root / "modules" / "markbot" / "markbot.py"

            # Read channel from show config
            show_config_path = meta_repo_root / "shows" / show_slug / "config.json"
            slack_channel = ""
            if show_config_path.is_file():
                try:
                    import json as _json
                    show_config = _json.loads(show_config_path.read_text())
                    slack_channel = show_config.get("slack", {}).get("channel", "")
                except Exception:
                    pass

            notifier = MarkbotNotifier(
                markbot_path=markbot_path,
                channel=slack_channel,
                show=show_name,
            )
```

Then pass `notifier=notifier` to the `sync_episodes()` call.

- [ ] **Step 5: Run existing tests to verify nothing broke**

```bash
cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/ -v --timeout=30
```

Expected: all existing tests PASS. The notifier is `None` by default so no existing code paths are affected.

- [ ] **Step 6: Commit**

```bash
git add modules/prx-to-ghost-publisher/src/main.py
git commit -m "feat: Wire markbot notifications into Ghost import pipeline"
```

---

### Task 6: Update Markbot CLAUDE.md and README

**Files:**
- Modify: `modules/markbot/CLAUDE.md`
- Modify: `modules/markbot/README.md`

- [ ] **Step 1: Update CLAUDE.md command table**

Add `ghost-import` to the Commands table:

```markdown
| `ghost-import` | Import lifecycle notifications (start/draft/scheduled/failed) | `prx-to-ghost-publisher` |
```

And add usage example to the Usage section:

```markdown
# Ghost import lifecycle
markbot.py ghost-import --state start --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa on the Sacred Feminine" --channel C09QUBVE0DR
markbot.py ghost-import --state draft --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa..." --ghost-url URL --channel C --thread-ts TS
markbot.py ghost-import --state scheduled --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa..." --ghost-url URL --schedule-time "Saturday at 6 AM" --channel C
markbot.py ghost-import --state failed --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa..." --error "msg" --channel C
```

- [ ] **Step 2: Update README.md**

Add `ghost-import` to the Commands list:

```markdown
- **`ghost-import`** — Import lifecycle notifications (start, draft ready, scheduled, failed)
```

- [ ] **Step 3: Commit**

```bash
git add modules/markbot/CLAUDE.md modules/markbot/README.md
git commit -m "docs(markbot): Document ghost-import command"
```

---

## Notes

### The `scheduled` state

The `scheduled` notification is built into markbot but **not yet wired into the publisher pipeline**. Currently, the publisher only creates drafts — scheduling happens manually in Ghost's admin UI. The `scheduled` state is ready for when either:
1. A `schedule` command is added to the publisher CLI
2. A Ghost webhook integration is built
3. The Airtable automation pipeline triggers it

### Thread continuity

The `ghost-import start` command prints `thread_ts` to stdout (same pattern as `transcribe-start`). The `MarkbotNotifier` captures this and threads subsequent `draft`/`failed` messages as replies to the start message — keeping the full import lifecycle in one Slack thread.

### Failure isolation

`MarkbotNotifier._run()` catches all exceptions and logs warnings. A Slack outage, missing `SLACK_BOT_TOKEN`, or markbot bug will never cause an import to fail. The import pipeline always takes priority.
