"""Tests for state tracker: atomic writes, locking, corruption recovery."""

from __future__ import annotations

import json
import multiprocessing
import os
import signal
import time
from pathlib import Path

import pytest

from src.state_tracker import StateLockError, StateTracker


class TestAtomicWrites:
    """Validate atomic write behavior (Phase 1.1)."""

    def test_save_creates_state_file(self, tracker: StateTracker, tmp_state_file: Path):
        """State file should be created on first save."""
        tracker.record_publish(
            guid="test-guid",
            ghost_post_id="ghost-1",
            title="Test",
            published_at="2025-01-01T00:00:00Z",
        )
        assert tmp_state_file.exists()

    def test_backup_created_on_save(self, tracker: StateTracker, tmp_state_file: Path):
        """A .bak file should be created after the first save."""
        tracker.record_publish(
            guid="test-guid-1",
            ghost_post_id="ghost-1",
            title="First",
            published_at="2025-01-01T00:00:00Z",
        )
        # First save — no .bak yet (no pre-existing file to back up)
        bak = tmp_state_file.with_suffix(".bak")

        # Second save should create .bak
        tracker.record_publish(
            guid="test-guid-2",
            ghost_post_id="ghost-2",
            title="Second",
            published_at="2025-01-02T00:00:00Z",
        )
        assert bak.exists()
        # .bak should contain only the first episode
        bak_data = json.loads(bak.read_text())
        assert "test-guid-1" in bak_data
        assert "test-guid-2" not in bak_data

    def test_round_trip_write_read(self, tracker: StateTracker, tmp_state_file: Path):
        """Data should survive a write/read cycle through a new tracker."""
        tracker.record_publish(
            guid="round-trip-guid",
            ghost_post_id="ghost-rt",
            title="Round Trip Test",
            published_at="2025-06-15T00:00:00Z",
        )

        # Create a new tracker from the same file
        tracker2 = StateTracker(tmp_state_file)
        assert tracker2.is_published("round-trip-guid")
        episode = tracker2.get_episode("round-trip-guid")
        assert episode is not None
        assert episode.title == "Round Trip Test"
        assert episode.ghost_post_id == "ghost-rt"

    def test_state_file_is_valid_json(self, tracker: StateTracker, tmp_state_file: Path):
        """State file must always be valid JSON."""
        tracker.record_publish(
            guid="json-test",
            ghost_post_id="ghost-j",
            title="JSON Test",
            published_at="2025-01-01T00:00:00Z",
        )
        # Should not raise
        json.loads(tmp_state_file.read_text())


class TestCorruptionRecovery:
    """Validate corruption recovery behavior (Phase 2.6)."""

    def test_corrupted_file_backed_up_and_raises(self, tmp_state_file: Path):
        """Corrupted JSON should be backed up and raise, not silently reset."""
        tmp_state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_state_file.write_text("{this is not valid json")

        tracker = StateTracker(tmp_state_file)

        with pytest.raises(json.JSONDecodeError):
            tracker.is_published("any-guid")

        # Corrupted file should be backed up
        corrupted_path = tmp_state_file.with_suffix(".corrupted")
        assert corrupted_path.exists()
        assert corrupted_path.read_text() == "{this is not valid json"


class TestLockFile:
    """Validate file locking behavior (Phase 1.2)."""

    def test_acquire_and_release_lock(self, tracker: StateTracker):
        """Lock should be acquirable and releasable."""
        tracker.acquire_lock()
        tracker.release_lock()

    def test_double_acquire_same_process(self, tracker: StateTracker):
        """Same process can re-acquire its own lock (flock is per-fd)."""
        tracker.acquire_lock()
        # Acquiring again on a *new* tracker sharing the file should fail
        tracker2 = StateTracker(tracker.state_file)
        with pytest.raises(StateLockError):
            tracker2.acquire_lock()
        tracker.release_lock()

    def test_release_without_acquire(self, tracker: StateTracker):
        """Releasing without acquiring should not raise."""
        tracker.release_lock()  # No-op, should not raise


class TestClearFailures:
    """Validate clear_failures only removes failed records."""

    def test_clear_failures_only_removes_failed(self, populated_state_file: Path):
        tracker = StateTracker(populated_state_file)
        count = tracker.clear_failures()
        assert count == 1

        # Published record should still exist
        assert tracker.is_published("prx_3329_guid-1")
        # Failed record should be gone
        assert not tracker.is_published("prx_3329_guid-2")


class TestLastSyncTime:
    """Validate last sync time metadata."""

    def test_set_and_get_sync_time(self, tracker: StateTracker):
        from datetime import datetime

        tracker.set_last_sync_time()
        result = tracker.get_last_sync_time()
        assert result is not None
        assert isinstance(result, datetime)
