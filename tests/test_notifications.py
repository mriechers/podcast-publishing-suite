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
