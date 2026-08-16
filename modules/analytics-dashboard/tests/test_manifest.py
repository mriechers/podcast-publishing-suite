"""Tests for snapshot manifest."""

import json
from pathlib import Path

import pytest

from src.manifest import get_latest_snapshot, list_snapshots, load_latest


def test_get_latest_snapshot(tmp_path):
    """Should return the most recent snapshot file for a source."""
    ghost_dir = tmp_path / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "2026-04-19.json").write_text('{"source": "ghost"}')
    (ghost_dir / "2026-04-21.json").write_text('{"source": "ghost"}')
    (ghost_dir / "2026-04-20.json").write_text('{"source": "ghost"}')

    latest = get_latest_snapshot(tmp_path, "ghost")
    assert latest is not None
    assert latest.name == "2026-04-21.json"


def test_get_latest_snapshot_empty(tmp_path):
    """Should return None if no snapshots exist."""
    latest = get_latest_snapshot(tmp_path, "ghost")
    assert latest is None


def test_list_snapshots(tmp_path):
    """Should return sorted list of snapshot dates."""
    ghost_dir = tmp_path / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "2026-04-19.json").write_text("{}")
    (ghost_dir / "2026-04-21.json").write_text("{}")

    snapshots = list_snapshots(tmp_path, "ghost")
    assert snapshots == ["2026-04-19", "2026-04-21"]


def test_load_latest(tmp_path):
    """Should load and parse the latest snapshot."""
    ghost_dir = tmp_path / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "2026-04-21.json").write_text('{"source": "ghost", "posts": []}')

    data = load_latest(tmp_path, "ghost")
    assert data is not None
    assert data["source"] == "ghost"


def test_load_latest_empty(tmp_path):
    """Should return None when no snapshots exist."""
    assert load_latest(tmp_path, "ghost") is None
