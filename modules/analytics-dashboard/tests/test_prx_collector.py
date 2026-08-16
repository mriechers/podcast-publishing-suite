"""Tests for PRX Dovetail analytics collector."""

from unittest.mock import MagicMock, patch

import pytest

from src.collectors.prx import PRXCollector


@pytest.fixture
def collector():
    return PRXCollector(
        client_id="test_id",
        client_secret="test_secret",
        podcast_ids=["120", "3329"],
    )


@patch("src.collectors.prx.requests.post")
def test_authenticate(mock_post, collector):
    """Should obtain bearer token via client credentials flow."""
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_abc123",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    token = collector._authenticate()
    assert token == "tok_abc123"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs[1]["data"]["grant_type"] == "client_credentials"


@patch("src.collectors.prx.requests.get")
@patch("src.collectors.prx.requests.post")
def test_collect_episodes(mock_post, mock_get, collector):
    """Should fetch and simplify episode data from Dovetail API."""
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_abc",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "total": 2,
            "_embedded": {
                "prx:items": [
                    {"id": 1, "guid": "g1", "title": "Ep 1", "publishedAt": "2026-04-01", "duration": 1800},
                    {"id": 2, "guid": "g2", "title": "Ep 2", "publishedAt": "2026-04-08", "duration": 2100},
                ],
            },
        }),
    )
    episodes = collector.collect_episodes("120")
    assert len(episodes) == 2
    assert episodes[0]["title"] == "Ep 1"
    assert episodes[1]["duration"] == 2100


@patch("src.collectors.prx.requests.post")
def test_authenticate_caches_token(mock_post, collector):
    """Should cache token and not re-authenticate until near expiry."""
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_cached",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    t1 = collector._get_token()
    t2 = collector._get_token()
    assert t1 == t2 == "tok_cached"
    assert mock_post.call_count == 1


@patch("src.collectors.prx.requests.post")
def test_authenticate_failure_raises(mock_post, collector):
    """Should raise PRXCollectorError when authentication fails."""
    from src.collectors.prx import PRXCollectorError
    mock_post.return_value = MagicMock(ok=False, status_code=401, text="Unauthorized")
    with pytest.raises(PRXCollectorError):
        collector._authenticate()


@patch("src.collectors.prx.requests.get")
@patch("src.collectors.prx.requests.post")
def test_collect_podcasts(mock_post, mock_get, collector):
    """Should fetch and simplify podcast metadata for all configured IDs."""
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_abc",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "id": "120",
            "title": "Wonder Cabinet",
            "subtitle": "A show about wonder",
            "episodeCount": 42,
        }),
    )
    podcasts, errors = collector.collect_podcasts()
    assert len(podcasts) == 2  # two podcast_ids
    assert len(errors) == 0
    assert podcasts[0]["title"] == "Wonder Cabinet"
    assert podcasts[0]["episodeCount"] == 42


@patch("src.collectors.prx.requests.get")
@patch("src.collectors.prx.requests.post")
def test_collect_all_structure(mock_post, mock_get, collector):
    """Should return snapshot with expected top-level keys."""
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_abc",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    # First call per podcast for collect_podcasts, then per podcast for collect_episodes
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "id": "120",
            "title": "Wonder Cabinet",
            "episodeCount": 0,
            "total": 0,
            "_embedded": {"prx:items": []},
        }),
    )
    snapshot = collector.collect_all()
    assert snapshot["source"] == "prx"
    assert "collected_at" in snapshot
    assert "podcasts" in snapshot
    assert "episodes" in snapshot
    assert "collection_errors" in snapshot
    assert snapshot["collection_errors"] == []


@patch("src.collectors.prx.requests.get")
@patch("src.collectors.prx.requests.post")
def test_episode_fields_simplified(mock_post, mock_get, collector):
    """Should only return specified simplified fields, not the full raw record."""
    mock_post.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "access_token": "tok_abc",
            "token_type": "bearer",
            "expires_in": 3600,
        }),
    )
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "total": 1,
            "_embedded": {
                "prx:items": [{
                    "id": 99,
                    "guid": "g99",
                    "title": "Test Episode",
                    "publishedAt": "2026-01-01",
                    "releasedAt": "2026-01-01",
                    "episodeType": "full",
                    "duration": 900,
                    "subtitle": "A test",
                    "tags": ["science"],
                    "someOtherField": "should not appear",
                }],
            },
        }),
    )
    episodes = collector.collect_episodes("120")
    ep = episodes[0]
    expected_keys = {"id", "guid", "title", "publishedAt", "releasedAt", "episodeType", "duration", "subtitle", "tags"}
    assert set(ep.keys()) == expected_keys
    assert "someOtherField" not in ep
