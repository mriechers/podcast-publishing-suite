"""Tests for validate_episode.py."""

import json
import sys
from pathlib import Path

# Add scripts/ to path so we can import validate_episode
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_episode import validate_episode


def _make_minimal_episode(tmp_path):
    """Create a minimal valid episode directory for testing."""
    (tmp_path / "captions.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    )
    (tmp_path / "transcript.txt").write_text("Hello")
    (tmp_path / "formatted_transcript.md").write_text("**Anne:** Hello")
    (tmp_path / "chapters.md").write_text("## Chapters\n00:00 Intro")


class TestManifestCheck:
    """Validate the manifest.json check works with the real schema."""

    def test_finds_manifest_json(self, tmp_path):
        """Should check manifest.json, not upload_manifest.json."""
        _make_minimal_episode(tmp_path)

        manifest = {
            "version": 1,
            "stage": "formatted",
            "files": {
                "transcript": {"path": "transcript.txt", "status": "present"},
                "formatted_transcript": {"path": "formatted_transcript.md", "status": "present"},
                "captions": {"path": "captions.srt", "status": "present"},
            },
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        results, _ = validate_episode(tmp_path)
        result_texts = [msg for _, msg in results]

        manifest_results = [r for r in result_texts if "anifest" in r]
        assert len(manifest_results) > 0, f"No manifest check in results: {result_texts}"

        manifest_failures = [(ok, msg) for ok, msg in results if "anifest" in msg and not ok]
        assert len(manifest_failures) == 0, f"Manifest check failed: {manifest_failures}"

    def test_detects_failed_files_in_manifest(self, tmp_path):
        """Should report files with status 'failed'."""
        _make_minimal_episode(tmp_path)

        manifest = {
            "version": 1,
            "stage": "formatted",
            "files": {
                "transcript": {"path": "transcript.txt", "status": "present"},
                "captions": {"path": "captions.srt", "status": "failed"},
            },
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        results, _ = validate_episode(tmp_path)
        manifest_failures = [(ok, msg) for ok, msg in results if "anifest" in msg and not ok]
        assert len(manifest_failures) == 1

    def test_ignores_upload_manifest(self, tmp_path):
        """upload_manifest.json should be ignored — only manifest.json matters."""
        _make_minimal_episode(tmp_path)
        (tmp_path / "upload_manifest.json").write_text('{"bad": "schema"}')

        results, _ = validate_episode(tmp_path)
        result_texts = [msg for _, msg in results]
        assert not any("upload_manifest" in r for r in result_texts)

    def test_shows_stage_when_manifest_ok(self, tmp_path):
        """Should display the stage from manifest when all files OK."""
        _make_minimal_episode(tmp_path)

        manifest = {
            "version": 1,
            "stage": "imported",
            "files": {
                "transcript": {"path": "transcript.txt", "status": "present"},
            },
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        results, _ = validate_episode(tmp_path)
        manifest_results = [msg for _, msg in results if "anifest" in msg]
        assert any("stage=imported" in r for r in manifest_results)
