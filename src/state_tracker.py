"""State tracking for published episodes to prevent duplicates.

Provides atomic file writes, file locking to prevent concurrent corruption,
and corruption recovery with backup files.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StateLockError(Exception):
    """Raised when the state file lock cannot be acquired."""
    pass


@dataclass
class PublishedEpisode:
    """Record of a published episode."""

    ghost_post_id: str
    title: str
    published_at: str
    synced_at: str
    status: str = "published"
    transcript_synced: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PublishedEpisode":
        """Create from dictionary."""
        return cls(
            ghost_post_id=data.get("ghost_post_id", ""),
            title=data.get("title", ""),
            published_at=data.get("published_at", ""),
            synced_at=data.get("synced_at", ""),
            status=data.get("status", "published"),
            transcript_synced=data.get("transcript_synced", False),
        )


class StateTracker:
    """Tracks published episodes to prevent duplicates.

    Uses JSON file storage for simplicity. Thread-safe for single-process use.
    Also tracks last sync time for incremental API fetches.
    """

    def __init__(self, state_file: Path):
        """Initialize state tracker.

        Args:
            state_file: Path to the JSON state file.
        """
        self.state_file = state_file
        self._state: dict[str, PublishedEpisode] = {}
        self._metadata: dict[str, str] = {}
        self._loaded = False
        self._lock_fd: Optional[int] = None

    def acquire_lock(self) -> None:
        """Acquire an exclusive file lock to prevent concurrent access.

        Uses fcntl.flock() on a .lock file adjacent to the state file.
        Non-blocking: raises StateLockError immediately if lock is held.

        Raises:
            StateLockError: If lock is already held by another process.
        """
        lock_path = self.state_file.with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._lock_fd = os.open(
                str(lock_path), os.O_CREAT | os.O_RDWR, 0o644
            )
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.debug(f"Acquired state lock: {lock_path}")
        except OSError:
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            raise StateLockError(
                "Another sync process is already running. "
                "If this is unexpected, remove the lock file: "
                f"{lock_path}"
            )

    def release_lock(self) -> None:
        """Release the file lock if held."""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                logger.debug("Released state lock")
            except OSError as e:
                logger.warning(f"Error releasing lock: {e}")
            finally:
                self._lock_fd = None

    def _ensure_loaded(self) -> None:
        """Load state from disk if not already loaded.

        On JSON corruption, backs up the corrupted file and raises rather
        than silently resetting to empty state (which would cause duplicate posts).
        """
        if self._loaded:
            return

        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Load metadata (like last_sync_time) if present
                if "_metadata" in data:
                    self._metadata = data.pop("_metadata")

                for guid, record in data.items():
                    self._state[guid] = PublishedEpisode.from_dict(record)

                logger.info(f"Loaded {len(self._state)} episodes from state file")
            except json.JSONDecodeError as e:
                # Back up corrupted file for forensics, then raise
                corrupted_path = self.state_file.with_suffix(".corrupted")
                shutil.copy2(self.state_file, corrupted_path)
                logger.critical(
                    f"State file is corrupted (backed up to {corrupted_path}): {e}"
                )
                raise
            except IOError as e:
                logger.error(f"Failed to read state file: {e}")
                raise
        else:
            logger.info("No existing state file, starting fresh")
            self._state = {}
            self._metadata = {}

        self._loaded = True

    def _save(self) -> None:
        """Save state to disk atomically.

        Uses the write-to-temp, fsync, rename pattern to prevent
        corruption from crashes or power loss mid-write. Also creates
        a .bak backup before replacing the current file.
        """
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        data = {guid: ep.to_dict() for guid, ep in self._state.items()}

        # Include metadata in saved state
        if self._metadata:
            data["_metadata"] = self._metadata

        try:
            # Write to temp file in the same directory (same filesystem for atomic rename)
            fd, tmp_path = tempfile.mkstemp(
                dir=self.state_file.parent,
                prefix=".state_",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                # Back up current state file before replacing
                if self.state_file.exists():
                    bak_path = self.state_file.with_suffix(".bak")
                    shutil.copy2(self.state_file, bak_path)

                # Atomic replace (POSIX rename is atomic within same filesystem)
                os.replace(tmp_path, self.state_file)
            except BaseException:
                # Clean up temp file on any failure
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

            logger.debug(f"Saved {len(self._state)} episodes to state file")
        except IOError as e:
            logger.error(f"Failed to save state file: {e}")
            raise

    def is_published(self, guid: str) -> bool:
        """Check if an episode has already been published.

        Args:
            guid: Episode GUID from RSS feed.

        Returns:
            True if episode has been published, False otherwise.
        """
        self._ensure_loaded()
        return guid in self._state

    def get_episode(self, guid: str) -> Optional[PublishedEpisode]:
        """Get published episode record by GUID.

        Args:
            guid: Episode GUID from RSS feed.

        Returns:
            PublishedEpisode if found, None otherwise.
        """
        self._ensure_loaded()
        return self._state.get(guid)

    def record_publish(
        self,
        guid: str,
        ghost_post_id: str,
        title: str,
        published_at: str,
        status: str = "published",
    ) -> None:
        """Record a newly published episode.

        Args:
            guid: Episode GUID from RSS feed.
            ghost_post_id: Ghost post ID returned from API.
            title: Episode title.
            published_at: Original publication date from RSS.
            status: Publication status ('published', 'draft', 'failed').
        """
        self._ensure_loaded()

        synced_at = datetime.now().isoformat()

        self._state[guid] = PublishedEpisode(
            ghost_post_id=ghost_post_id,
            title=title,
            published_at=published_at,
            synced_at=synced_at,
            status=status,
        )

        self._save()
        logger.info(f"Recorded publish for: {title} (GUID: {guid})")

    def record_failure(self, guid: str, title: str, published_at: str) -> None:
        """Record a failed publish attempt.

        Args:
            guid: Episode GUID from RSS feed.
            title: Episode title.
            published_at: Original publication date from RSS.
        """
        self.record_publish(
            guid=guid,
            ghost_post_id="",
            title=title,
            published_at=published_at,
            status="failed",
        )

    def get_all_published(self) -> dict[str, PublishedEpisode]:
        """Get all published episode records.

        Returns:
            Dictionary mapping GUID to PublishedEpisode.
        """
        self._ensure_loaded()
        return dict(self._state)

    def get_published_guids(self) -> set[str]:
        """Get set of all published episode GUIDs.

        Returns:
            Set of GUID strings.
        """
        self._ensure_loaded()
        return set(self._state.keys())

    def get_successful_count(self) -> int:
        """Get count of successfully published episodes.

        Returns:
            Number of episodes with status 'published' or 'draft'.
        """
        self._ensure_loaded()
        return sum(
            1
            for ep in self._state.values()
            if ep.status in ("published", "draft")
        )

    def get_failed_count(self) -> int:
        """Get count of failed publish attempts.

        Returns:
            Number of episodes with status 'failed'.
        """
        self._ensure_loaded()
        return sum(1 for ep in self._state.values() if ep.status == "failed")

    def clear_failures(self) -> int:
        """Remove all failed records so they can be retried.

        Returns:
            Number of records removed.
        """
        self._ensure_loaded()

        failed_guids = [
            guid for guid, ep in self._state.items() if ep.status == "failed"
        ]

        for guid in failed_guids:
            del self._state[guid]

        if failed_guids:
            self._save()
            logger.info(f"Cleared {len(failed_guids)} failed records")

        return len(failed_guids)

    def remove(self, guid: str) -> bool:
        """Remove an episode record.

        Args:
            guid: Episode GUID to remove.

        Returns:
            True if record was removed, False if not found.
        """
        self._ensure_loaded()

        if guid in self._state:
            del self._state[guid]
            self._save()
            logger.info(f"Removed record for GUID: {guid}")
            return True

        return False

    def record_transcript_synced(self, guid: str) -> None:
        """Mark an episode's transcript as synced to Ghost.

        Args:
            guid: Episode GUID.
        """
        self._ensure_loaded()
        if guid in self._state:
            self._state[guid].transcript_synced = True
            self._save()
            logger.info(f"Recorded transcript synced for GUID: {guid}")

    def reload(self) -> None:
        """Force reload state from disk."""
        self._loaded = False
        self._state = {}
        self._metadata = {}
        self._ensure_loaded()

    def get_last_sync_time(self) -> Optional[datetime]:
        """Get the last sync timestamp for incremental API fetches.

        Returns:
            datetime of last sync, or None if never synced.
        """
        self._ensure_loaded()
        last_sync_str = self._metadata.get("last_sync_time")
        if last_sync_str:
            try:
                return datetime.fromisoformat(last_sync_str)
            except ValueError:
                logger.warning(f"Invalid last_sync_time format: {last_sync_str}")
                return None
        return None

    def set_last_sync_time(self, timestamp: Optional[datetime] = None) -> None:
        """Set the last sync timestamp.

        Args:
            timestamp: Sync time to record. Defaults to current time.
        """
        self._ensure_loaded()
        if timestamp is None:
            timestamp = datetime.now()
        self._metadata["last_sync_time"] = timestamp.isoformat()
        self._save()
        logger.info(f"Recorded last sync time: {timestamp.isoformat()}")


if __name__ == "__main__":
    # Test the state tracker
    import tempfile

    logging.basicConfig(level=logging.DEBUG)

    # Create a temp state file
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "test_state.json"

        tracker = StateTracker(state_file)

        # Test recording
        tracker.record_publish(
            guid="prx_120_test-guid-1",
            ghost_post_id="ghost-123",
            title="Test Episode 1",
            published_at="2025-09-13T11:00:00Z",
        )

        tracker.record_publish(
            guid="prx_120_test-guid-2",
            ghost_post_id="ghost-456",
            title="Test Episode 2",
            published_at="2025-09-06T11:00:00Z",
        )

        tracker.record_failure(
            guid="prx_120_test-guid-3",
            title="Failed Episode",
            published_at="2025-09-01T11:00:00Z",
        )

        # Test queries
        print(f"Is test-guid-1 published? {tracker.is_published('prx_120_test-guid-1')}")
        print(f"Is test-guid-99 published? {tracker.is_published('prx_120_test-guid-99')}")
        print(f"Successful count: {tracker.get_successful_count()}")
        print(f"Failed count: {tracker.get_failed_count()}")
        print(f"Published GUIDs: {tracker.get_published_guids()}")

        # Test reload
        tracker2 = StateTracker(state_file)
        print(f"\nAfter reload, successful count: {tracker2.get_successful_count()}")

        # Show state file contents
        print(f"\nState file contents:")
        with open(state_file, "r") as f:
            print(f.read())
