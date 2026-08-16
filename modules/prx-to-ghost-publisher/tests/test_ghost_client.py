"""Tests for Ghost client: JWT generation, retry logic, connection pooling."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.ghost_client import (
    GhostAPIError,
    GhostClient,
    GhostPost,
    generate_jwt_token,
)


class TestJWTGeneration:
    """Validate JWT token generation."""

    def test_valid_key_generates_token(self):
        """Valid API key should produce a JWT string."""
        # Use a well-formed hex secret (64 hex chars = 32 bytes)
        key = "abc123:" + "0" * 64
        token = generate_jwt_token(key)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_invalid_key_format_raises(self):
        """API key without colon should raise ValueError."""
        with pytest.raises(ValueError, match="format"):
            generate_jwt_token("no-colon-here")


class TestGhostClientTokenCache:
    """Validate JWT token caching behavior."""

    def test_token_is_cached(self):
        key = "test123:" + "0" * 64
        client = GhostClient("https://ghost.example.com", key)
        token1 = client._get_token()
        token2 = client._get_token()
        # Same token should be returned within cache window
        assert token1 == token2


class TestRetryLogic:
    """Validate retry behavior on transient errors."""

    def _make_client(self) -> GhostClient:
        key = "test123:" + "0" * 64
        return GhostClient("https://ghost.example.com", key)

    def test_429_retries_with_backoff(self):
        """429 responses should trigger retry."""
        client = self._make_client()
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "0.01"}

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.ok = True
        mock_response_ok.json.return_value = {"site": {"title": "Test"}}

        client._session.request = MagicMock(
            side_effect=[mock_response_429, mock_response_ok]
        )

        # Should succeed after retry
        response = client._request_with_retry(
            "GET", "https://ghost.example.com/ghost/api/admin/site/",
            headers={}, timeout=10,
        )
        assert response.status_code == 200
        assert client._session.request.call_count == 2

    def test_500_retries_then_returns(self):
        """500 errors should retry up to MAX_RETRIES then return the response."""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        client._session.request = MagicMock(return_value=mock_response)

        # Patch sleep to avoid actual delays
        with patch("src.ghost_client.time.sleep"):
            response = client._request_with_retry(
                "GET", "https://ghost.example.com/ghost/api/admin/site/",
                headers={}, timeout=10,
            )
        assert response.status_code == 500
        # 1 initial + MAX_RETRIES retries = 4 total
        assert client._session.request.call_count == 4

    def test_create_post_success(self):
        """create_post should return post data on success."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.ok = True
        mock_response.json.return_value = {
            "posts": [{"id": "post-123", "title": "Test Post"}]
        }

        client._session.request = MagicMock(return_value=mock_response)

        post = GhostPost(title="Test Post", html="<p>Hello</p>")
        result = client.create_post(post)
        assert result["id"] == "post-123"


class TestUploadMIME:
    """Validate MIME type mapping for uploads."""

    def test_mp3_mime_type(self):
        client = self._make_client()
        # Check that upload_media calls with correct MIME
        from pathlib import Path
        from unittest.mock import patch

        with patch.object(client, "_upload_to_endpoint", return_value="https://example.com/audio.mp3") as mock:
            client.upload_media(Path("/tmp/test.mp3"))
            mock.assert_called_once_with(Path("/tmp/test.mp3"), "media/upload", "audio/mpeg")

    def test_json_mime_type(self):
        client = self._make_client()
        from pathlib import Path
        from unittest.mock import patch

        with patch.object(client, "_upload_to_endpoint", return_value="https://example.com/peaks.json") as mock:
            client.upload_file(Path("/tmp/peaks.json"))
            mock.assert_called_once_with(Path("/tmp/peaks.json"), "files/upload", "application/json")

    @staticmethod
    def _make_client() -> GhostClient:
        key = "test123:" + "0" * 64
        return GhostClient("https://ghost.example.com", key)


class TestUpdatePostMetadata:
    """Validate update_post_metadata sends safe metadata-only payloads."""

    @staticmethod
    def _make_client() -> GhostClient:
        key = "test123:" + "0" * 64
        return GhostClient("https://ghost.example.com", key)

    def test_url_does_not_contain_source_html(self):
        """Request URL must NOT include source=html query parameter."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "posts": [{"id": "post-123", "updated_at": "2026-01-01T00:00:00.000Z"}]
        }

        client._session.request = MagicMock(return_value=mock_response)

        client.update_post_metadata(
            "post-123",
            updated_at="2026-01-01T00:00:00.000Z",
            tags=[{"name": "Test"}],
        )

        call_args = client._session.request.call_args
        url = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("url", "")
        assert "source=html" not in url

    def test_payload_does_not_contain_html_key(self):
        """Payload must NOT include an html field."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "posts": [{"id": "post-123", "updated_at": "2026-01-01T00:00:00.000Z"}]
        }

        client._session.request = MagicMock(return_value=mock_response)

        client.update_post_metadata(
            "post-123",
            updated_at="2026-01-01T00:00:00.000Z",
            tags=[{"name": "Test"}],
        )

        call_args = client._session.request.call_args
        payload = call_args[1].get("json", {})
        post_data = payload["posts"][0]
        assert "html" not in post_data

    def test_only_provided_fields_in_payload(self):
        """Only fields explicitly passed should appear in the payload (plus updated_at)."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "posts": [{"id": "post-123", "updated_at": "2026-01-01T00:00:00.000Z"}]
        }

        client._session.request = MagicMock(return_value=mock_response)

        # Only pass tags — no codeinjection_head, no canonical_url
        client.update_post_metadata(
            "post-123",
            updated_at="2026-01-01T00:00:00.000Z",
            tags=[{"name": "Tag1"}],
        )

        call_args = client._session.request.call_args
        payload = call_args[1].get("json", {})
        post_data = payload["posts"][0]
        assert set(post_data.keys()) == {"updated_at", "tags"}

    def test_updated_at_always_included(self):
        """updated_at must always be present in the payload."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "posts": [{"id": "post-123", "updated_at": "2026-01-01T00:00:00.000Z"}]
        }

        client._session.request = MagicMock(return_value=mock_response)

        # Call with no optional fields at all
        client.update_post_metadata(
            "post-123",
            updated_at="2026-01-01T00:00:00.000Z",
        )

        call_args = client._session.request.call_args
        payload = call_args[1].get("json", {})
        post_data = payload["posts"][0]
        assert "updated_at" in post_data
        assert post_data["updated_at"] == "2026-01-01T00:00:00.000Z"

    def test_all_fields_included_when_provided(self):
        """When all optional fields are given, all should appear in payload."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "posts": [{"id": "post-123", "updated_at": "2026-01-01T00:00:00.000Z"}]
        }

        client._session.request = MagicMock(return_value=mock_response)

        client.update_post_metadata(
            "post-123",
            updated_at="2026-01-01T00:00:00.000Z",
            tags=[{"name": "Tag1"}],
            codeinjection_head="<script>test</script>",
            canonical_url="https://example.com/post/",
        )

        call_args = client._session.request.call_args
        payload = call_args[1].get("json", {})
        post_data = payload["posts"][0]
        assert set(post_data.keys()) == {
            "updated_at", "tags", "codeinjection_head", "canonical_url",
        }
