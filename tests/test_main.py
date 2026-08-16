"""Tests for CLI argument parsing and CLI-vs-config precedence.

Regression coverage for a bug where `dry_run = args.dry_run or config.dry_run`
let DRY_RUN=true in .env.prod win with no CLI escape hatch: an operator could
not force a real sync no matter what flags they passed. The fix makes
--dry-run/--source tri-state (None/True/False, None/"api"/"rss") so explicit
CLI intent always wins over ambient config, and only an unspecified flag
defers to it.
"""

from __future__ import annotations

import argparse

import pytest

from src.main import build_parser, _resolve_dry_run, _resolve_source


class TestResolveDryRun:
    """Unit tests for the dry_run precedence resolver."""

    def test_cli_dry_run_flag_wins_over_config_false(self):
        value, note = _resolve_dry_run(True, False, "dev")
        assert value is True
        assert "--dry-run flag" in note

    def test_cli_no_dry_run_flag_wins_over_config_true(self):
        """The core regression: --no-dry-run must override DRY_RUN=true."""
        value, note = _resolve_dry_run(False, True, "prod")
        assert value is False
        assert "--no-dry-run flag" in note

    def test_unspecified_defers_to_config_true(self):
        value, note = _resolve_dry_run(None, True, "prod")
        assert value is True
        assert "DRY_RUN" in note
        assert ".env.prod" in note

    def test_unspecified_defers_to_config_false(self):
        value, note = _resolve_dry_run(None, False, "dev")
        assert value is False
        assert ".env.dev" in note

    def test_source_note_states_which_env_file(self):
        _, note = _resolve_dry_run(None, True, "prod")
        assert "prod" in note


class TestResolveSource:
    """Unit tests for the episode-source precedence resolver."""

    def test_cli_source_rss_wins_over_config_use_api_true(self):
        """The parallel regression: --source rss must override PRX_USE_API=true."""
        source, use_api, note = _resolve_source("rss", True, "prod")
        assert source == "rss"
        assert use_api is False
        assert "--source rss flag" in note

    def test_cli_source_api_wins_over_config_use_api_false(self):
        source, use_api, note = _resolve_source("api", False, "dev")
        assert source == "api"
        assert use_api is True
        assert "--source api flag" in note

    def test_unspecified_defers_to_config_use_api_true(self):
        source, use_api, note = _resolve_source(None, True, "dev")
        assert source == "api"
        assert use_api is True
        assert "PRX_USE_API" in note

    def test_unspecified_defers_to_config_use_api_false(self):
        source, use_api, note = _resolve_source(None, False, "dev")
        assert source == "rss"
        assert use_api is False
        assert "default" in note


class TestSyncParserDefaults:
    """Validate the argparse wiring itself: bare invocation must be tri-state."""

    def test_dry_run_defaults_to_none_when_unspecified(self):
        parser = build_parser()
        args = parser.parse_args(["sync"])
        assert args.dry_run is None

    def test_dry_run_flag_sets_true(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--dry-run"])
        assert args.dry_run is True

    def test_no_dry_run_flag_sets_false(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--no-dry-run"])
        assert args.dry_run is False

    def test_source_defaults_to_none_when_unspecified(self):
        parser = build_parser()
        args = parser.parse_args(["sync"])
        assert args.source is None

    def test_source_explicit_rss(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--source", "rss"])
        assert args.source == "rss"

    def test_source_explicit_api(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--source", "api"])
        assert args.source == "api"

    def test_bare_invocation_defaults_are_also_none(self):
        """No-subcommand invocation (parser.set_defaults) must match the
        sync subparser's tri-state sentinel, not silently reintroduce
        False/"rss" as a stand-in for "unspecified"."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.dry_run is None
        assert args.source is None

    def test_update_metadata_dry_run_is_unaffected_plain_flag(self):
        """update-metadata's own --dry-run is a separate, simple store_true
        flag (no ambient config to defer to) and should stay that way."""
        parser = build_parser()
        args = parser.parse_args(["update-metadata"])
        assert args.dry_run is False
        args = parser.parse_args(["update-metadata", "--dry-run"])
        assert args.dry_run is True
