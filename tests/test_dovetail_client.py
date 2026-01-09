"""Tests for Dovetail API client."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.dovetail_client import DovetailAPIError, DovetailClient
from src.feed_parser import Episode
from src.prx_auth import PRXAuthClient


@pytest.fixture
def mock_auth_client():
    """Create a mock PRXAuthClient."""
    mock_client = MagicMock(spec=PRXAuthClient)
    mock_client.get_auth_headers.return_value = {
        "Authorization": "Bearer test_token",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return mock_client


@pytest.fixture
def dovetail_client(mock_auth_client):
    """Create a DovetailClient with mock auth."""
    return DovetailClient(
        auth_client=mock_auth_client,
        podcast_id="120",
        api_base_url="https://podcasts.dovetail.prx.org/api/v1",
    )


class TestParseApiEpisode:
    """Tests for _parse_api_episode method."""

    def test_parse_minimal_episode(self, dovetail_client):
        """Test parsing episode with minimal required fields."""
        data = {
            "guid": "prx_120_episode-1",
            "title": "Test Episode",
        }

        episode = dovetail_client._parse_api_episode(data)

        assert episode.guid == "prx_120_episode-1"
        assert episode.title == "Test Episode"
        assert episode.description == ""
        assert episode.episode_type == "full"

    def test_parse_full_episode(self, dovetail_client):
        """Test parsing episode with all fields."""
        data = {
            "guid": "prx_120_episode-2",
            "title": "Full Episode",
            "description": "This is a test episode with full data.",
            "subtitle": "A subtitle",
            "publishedAt": "2025-09-13T11:00:00Z",
            "link": "https://example.com/episode-2",
            "media": [
                {
                    "href": "https://example.com/audio.mp3",
                    "type": "audio/mpeg"
                }
            ],
            "duration": 3600,
            "imageUrl": "https://example.com/image.jpg",
            "itunesCategories": [
                {"name": "Technology"},
                {"name": "Science"}
            ],
            "episodeType": "full",
            "author": "Test Author",
        }

        episode = dovetail_client._parse_api_episode(data)

        assert episode.guid == "prx_120_episode-2"
        assert episode.title == "Full Episode"
        assert episode.description == "This is a test episode with full data."
        assert episode.subtitle == "A subtitle"
        assert episode.pub_date.year == 2025
        assert episode.pub_date.month == 9
        assert episode.link == "https://example.com/episode-2"
        assert episode.enclosure_url == "https://example.com/audio.mp3"
        assert episode.enclosure_type == "audio/mpeg"
        assert episode.duration == "01:00:00"
        assert episode.image_url == "https://example.com/image.jpg"
        assert "Technology" in episode.categories
        assert "Science" in episode.categories
        assert episode.episode_type == "full"
        assert episode.author == "Test Author"

    def test_parse_episode_missing_guid_raises(self, dovetail_client):
        """Test that missing guid raises KeyError."""
        data = {
            "title": "Episode without GUID",
        }

        with pytest.raises(KeyError, match="guid"):
            dovetail_client._parse_api_episode(data)

    def test_parse_episode_missing_title_raises(self, dovetail_client):
        """Test that missing title raises KeyError."""
        data = {
            "guid": "prx_120_no-title",
        }

        with pytest.raises(KeyError, match="title"):
            dovetail_client._parse_api_episode(data)

    def test_parse_episode_alternative_field_names(self, dovetail_client):
        """Test parsing with alternative API field names."""
        data = {
            "id": "alternative-id-format",
            "title": "Alternative Fields Episode",
            "content": "Description via content field",
            "published_at": "2025-08-15T10:00:00Z",
            "audioUrl": "https://example.com/alt-audio.mp3",
        }

        episode = dovetail_client._parse_api_episode(data)

        assert episode.guid == "alternative-id-format"
        assert episode.description == "Description via content field"
        assert episode.enclosure_url == "https://example.com/alt-audio.mp3"

    def test_parse_duration_seconds_to_timestamp(self, dovetail_client):
        """Test duration conversion from seconds to HH:MM:SS."""
        # Test short duration (under an hour)
        data = {"guid": "test-1", "title": "Test", "duration": 325}
        episode = dovetail_client._parse_api_episode(data)
        assert episode.duration == "05:25"

        # Test long duration (over an hour)
        data = {"guid": "test-2", "title": "Test", "duration": 3725}
        episode = dovetail_client._parse_api_episode(data)
        assert episode.duration == "01:02:05"


class TestGetPodcasts:
    """Tests for get_podcasts method."""

    @patch("src.dovetail_client.requests.request")
    def test_get_podcasts_hal_format(self, mock_request, dovetail_client):
        """Test parsing HAL+JSON format response."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "_embedded": {
                "prx:items": [
                    {"id": "120", "title": "TTBOOK"},
                    {"id": "121", "title": "Another Show"},
                ]
            },
            "_links": {
                "next": {"href": "/api/v1/authorization/podcasts?page=2"}
            }
        }
        mock_request.return_value = mock_response

        podcasts = dovetail_client.get_podcasts(page=1, per=50)

        assert len(podcasts) == 2
        assert podcasts[0]["id"] == "120"
        assert podcasts[1]["title"] == "Another Show"

    @patch("src.dovetail_client.requests.request")
    def test_get_podcasts_pagination_params(self, mock_request, dovetail_client):
        """Test that pagination parameters are passed correctly."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"_embedded": {"prx:items": []}}
        mock_request.return_value = mock_response

        dovetail_client.get_podcasts(page=3, per=25)

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["params"]["page"] == 3
        assert call_kwargs["params"]["per"] == 25


class TestGetEpisodes:
    """Tests for get_episodes method."""

    @patch("src.dovetail_client.requests.request")
    def test_get_episodes_with_since(self, mock_request, dovetail_client):
        """Test episodes fetch with since parameter."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "_embedded": {
                "prx:items": [
                    {
                        "guid": "prx_120_ep1",
                        "title": "Episode 1",
                        "podcastId": "120",
                    }
                ]
            }
        }
        mock_request.return_value = mock_response

        since = datetime(2025, 9, 1, 0, 0, 0)
        episodes = dovetail_client.get_episodes(podcast_id="120", since=since)

        assert len(episodes) == 1
        assert episodes[0].guid == "prx_120_ep1"

        # Verify since was passed
        call_kwargs = mock_request.call_args[1]
        assert "since" in call_kwargs["params"]

    @patch("src.dovetail_client.requests.request")
    def test_get_episodes_filters_by_podcast_id(self, mock_request, dovetail_client):
        """Test that episodes are filtered by podcast_id."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "_embedded": {
                "prx:items": [
                    {"guid": "prx_120_ep1", "title": "Ep 1", "podcastId": "120"},
                    {"guid": "prx_999_ep1", "title": "Other Show", "podcastId": "999"},
                ]
            }
        }
        mock_request.return_value = mock_response

        episodes = dovetail_client.get_episodes(podcast_id="120")

        # Should only return episode from podcast 120
        assert len(episodes) == 1
        assert episodes[0].guid == "prx_120_ep1"

    def test_get_episodes_requires_podcast_id(self, dovetail_client):
        """Test that get_episodes raises without podcast_id."""
        client = DovetailClient(
            auth_client=dovetail_client.auth_client,
            podcast_id="",  # No default
        )

        with pytest.raises(ValueError, match="podcast_id is required"):
            client.get_episodes()


class TestGetEpisodeByGuid:
    """Tests for get_episode_by_guid method."""

    @patch("src.dovetail_client.requests.request")
    def test_get_episode_by_guid_found(self, mock_request, dovetail_client):
        """Test successful GUID lookup."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "guid": "prx_120_specific-episode",
            "title": "Specific Episode",
        }
        mock_request.return_value = mock_response

        episode = dovetail_client.get_episode_by_guid(
            guid="prx_120_specific-episode",
            podcast_id="120"
        )

        assert episode is not None
        assert episode.guid == "prx_120_specific-episode"

    @patch("src.dovetail_client.requests.request")
    def test_get_episode_by_guid_not_found(self, mock_request, dovetail_client):
        """Test GUID lookup returns None for 404."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_request.return_value = mock_response

        episode = dovetail_client.get_episode_by_guid(
            guid="nonexistent",
            podcast_id="120"
        )

        assert episode is None


class TestErrorHandling:
    """Tests for API error handling."""

    @patch("src.dovetail_client.requests.request")
    def test_401_triggers_token_refresh(self, mock_request, dovetail_client):
        """Test that 401 response triggers token refresh and retry."""
        # First call returns 401, second succeeds
        mock_401 = MagicMock()
        mock_401.ok = False
        mock_401.status_code = 401
        mock_401.text = "Unauthorized"

        mock_success = MagicMock()
        mock_success.ok = True
        mock_success.json.return_value = {"_embedded": {"prx:items": []}}

        mock_request.side_effect = [mock_401, mock_success]

        dovetail_client.get_podcasts()

        # Should have invalidated token and retried
        dovetail_client.auth_client.invalidate_token.assert_called_once()
        assert mock_request.call_count == 2

    @patch("src.dovetail_client.requests.request")
    def test_api_error_includes_details(self, mock_request, dovetail_client):
        """Test that API errors include status and response body."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = '{"error": "Internal server error"}'
        mock_request.return_value = mock_response

        with pytest.raises(DovetailAPIError) as exc_info:
            dovetail_client.get_podcasts()

        error = exc_info.value
        assert error.status_code == 500
        assert "Internal server error" in error.response_body

    @patch("src.dovetail_client.requests.request")
    def test_connection_error_handled(self, mock_request, dovetail_client):
        """Test graceful handling of connection errors."""
        from requests.exceptions import ConnectionError

        mock_request.side_effect = ConnectionError("Connection refused")

        with pytest.raises(DovetailAPIError) as exc_info:
            dovetail_client.get_podcasts()

        assert "Connection error" in str(exc_info.value)


class TestEpisodeDataclassCompatibility:
    """Tests ensuring API episodes are compatible with existing code."""

    def test_episode_has_required_fields(self, dovetail_client):
        """Test that parsed episodes have all fields needed by content_builder."""
        data = {
            "guid": "prx_120_test",
            "title": "Test Episode",
            "description": "Test description",
            "publishedAt": "2025-09-13T11:00:00Z",
            "media": [{"href": "https://example.com/audio.mp3"}],
        }

        episode = dovetail_client._parse_api_episode(data)

        # These fields are used by content_builder.py
        assert hasattr(episode, "guid")
        assert hasattr(episode, "title")
        assert hasattr(episode, "description")
        assert hasattr(episode, "subtitle")
        assert hasattr(episode, "pub_date")
        assert hasattr(episode, "link")
        assert hasattr(episode, "enclosure_url")
        assert hasattr(episode, "enclosure_type")
        assert hasattr(episode, "duration")
        assert hasattr(episode, "image_url")
        assert hasattr(episode, "categories")
        assert hasattr(episode, "episode_type")
        assert hasattr(episode, "author")

    def test_episode_is_correct_type(self, dovetail_client):
        """Test that parsed episode is an Episode instance."""
        data = {"guid": "test", "title": "Test"}
        episode = dovetail_client._parse_api_episode(data)
        assert isinstance(episode, Episode)
