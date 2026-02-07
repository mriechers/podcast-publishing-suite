"""Shared fixtures for the test suite."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.feed_parser import Episode
from src.state_tracker import StateTracker


@pytest.fixture
def tmp_state_file(tmp_path: Path) -> Path:
    """Provide a temporary state file path."""
    return tmp_path / "test_state.json"


@pytest.fixture
def tracker(tmp_state_file: Path) -> StateTracker:
    """Provide a fresh StateTracker with a temporary state file."""
    return StateTracker(tmp_state_file)


@pytest.fixture
def sample_episode() -> Episode:
    """Provide a sample Episode for testing."""
    return Episode(
        guid="prx_3329_test-guid-1",
        title="Test Episode: The Art of Testing",
        description="<p>This is a <strong>test</strong> description.</p>",
        subtitle="A short subtitle for testing.",
        pub_date=datetime(2025, 9, 13, 11, 0, 0),
        link="https://www.ttbook.org/show/test-episode",
        enclosure_url="https://example.com/audio.mp3",
        enclosure_type="audio/mpeg",
        duration="45:30",
        image_url="https://example.com/image.png",
        categories=["testing", "development"],
        episode_type="full",
        author="Wisconsin Public Radio",
    )


@pytest.fixture
def populated_state_file(tmp_state_file: Path) -> Path:
    """Provide a state file with pre-existing data."""
    data = {
        "prx_3329_guid-1": {
            "ghost_post_id": "ghost-123",
            "title": "Published Episode",
            "published_at": "2025-09-13T11:00:00Z",
            "synced_at": "2025-09-14T10:00:00",
            "status": "published",
        },
        "prx_3329_guid-2": {
            "ghost_post_id": "",
            "title": "Failed Episode",
            "published_at": "2025-09-06T11:00:00Z",
            "synced_at": "2025-09-07T10:00:00",
            "status": "failed",
        },
        "_metadata": {
            "last_sync_time": "2025-09-14T10:00:00",
        },
    }
    tmp_state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_state_file.write_text(json.dumps(data, indent=2))
    return tmp_state_file
