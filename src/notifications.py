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
