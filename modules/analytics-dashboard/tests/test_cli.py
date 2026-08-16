# tests/test_cli.py
"""Tests for analytics CLI."""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from src.cli import refresh


@patch("src.cli.GhostCollector")
@patch("src.cli.PRXCollector")
@patch("src.cli.load_config")
def test_refresh_all(mock_config, mock_prx_cls, mock_ghost_cls, tmp_path):
    """refresh() should invoke both collectors and return snapshot paths."""
    mock_config.return_value = MagicMock(
        ghost_api_base_url="https://test.ghost.io/ghost/api/admin",
        ghost_key_id="abc",
        ghost_key_secret=b"\xaa" * 32,
        prx_client_id="cid",
        prx_client_secret="csec",
        prx_podcast_ids=["120"],
        prx_api_base_url="https://podcasts.dovetail.prx.org/api/v1",
        prx_token_endpoint="https://id.prx.org/token",
        data_dir=tmp_path,
    )
    mock_ghost_cls.return_value.save_snapshot.return_value = tmp_path / "ghost/2026-04-21.json"
    mock_prx_cls.return_value.save_snapshot.return_value = tmp_path / "prx/2026-04-21.json"

    results = refresh()
    assert "ghost" in results
    assert "prx" in results
    mock_ghost_cls.return_value.save_snapshot.assert_called_once()
    mock_prx_cls.return_value.save_snapshot.assert_called_once()


@patch("src.cli.GhostCollector")
@patch("src.cli.load_config")
def test_refresh_single_source(mock_config, mock_ghost_cls, tmp_path):
    """refresh(source='ghost') should only invoke Ghost collector."""
    mock_config.return_value = MagicMock(
        ghost_api_base_url="https://test.ghost.io/ghost/api/admin",
        ghost_key_id="abc",
        ghost_key_secret=b"\xaa" * 32,
        data_dir=tmp_path,
    )
    mock_ghost_cls.return_value.save_snapshot.return_value = tmp_path / "ghost/2026-04-21.json"

    results = refresh(source="ghost")
    assert "ghost" in results
    assert "prx" not in results
