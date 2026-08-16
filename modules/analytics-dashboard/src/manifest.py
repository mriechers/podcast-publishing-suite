"""Snapshot manifest utilities.

Provides functions to find and list dated JSON snapshots
in the data directory without maintaining a separate index file.
Uses filename sorting (YYYY-MM-DD.json) for ordering.
"""

from __future__ import annotations

import json
from pathlib import Path


def get_latest_snapshot(data_dir: Path, source: str) -> Path | None:
    """Get the path to the most recent snapshot for a source."""
    source_dir = data_dir / source
    if not source_dir.exists():
        return None
    snapshots = sorted(source_dir.glob("????-??-??.json"))
    return snapshots[-1] if snapshots else None


def list_snapshots(data_dir: Path, source: str) -> list[str]:
    """List all snapshot dates for a source, sorted chronologically."""
    source_dir = data_dir / source
    if not source_dir.exists():
        return []
    return sorted(p.stem for p in source_dir.glob("????-??-??.json"))


def load_latest(data_dir: Path, source: str) -> dict | None:
    """Load and parse the latest snapshot for a source."""
    path = get_latest_snapshot(data_dir, source)
    if path is None:
        return None
    return json.loads(path.read_text())
