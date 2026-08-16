"""Tests for Ghost analytics collector."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.ghost import GhostCollector


@pytest.fixture
def collector():
    """Create a GhostCollector with test credentials."""
    return GhostCollector(
        api_base_url="https://test.ghost.io/ghost/api/admin",
        key_id="abc123",
        key_secret=bytes.fromhex("aa" * 32),
    )


def test_generate_jwt(collector):
    """JWT should contain correct header fields and audience."""
    import jwt as pyjwt

    token = collector._generate_jwt()
    decoded = pyjwt.decode(token, options={"verify_signature": False})
    assert decoded["aud"] == "/admin/"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] - decoded["iat"] == 300


@patch("src.collectors.ghost.requests.get")
def test_collect_posts(mock_get, collector):
    """collect_posts should paginate and return all posts."""
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={
            "posts": [
                {"id": "1", "title": "Episode 1", "slug": "ep-1", "status": "published"},
                {"id": "2", "title": "Episode 2", "slug": "ep-2", "status": "draft"},
            ],
            "meta": {"pagination": {"page": 1, "pages": 1, "total": 2}},
        }),
    )
    posts = collector.collect_posts()
    assert len(posts) == 2
    assert posts[0]["title"] == "Episode 1"


@patch("src.collectors.ghost.requests.get")
def test_collect_members_summary(mock_get, collector):
    """collect_members_summary should return count breakdown."""
    def side_effect(url, **kwargs):
        params = kwargs.get("params", {})
        filter_val = params.get("filter", "")
        totals = {"status:free": 50, "status:paid": 5, "status:comped": 2}
        total = totals.get(filter_val, 57)
        resp = MagicMock(ok=True)
        resp.json.return_value = {
            "members": [],
            "meta": {"pagination": {"total": total}},
        }
        return resp

    mock_get.side_effect = side_effect
    summary = collector.collect_members_summary()
    assert summary["free"] == 50
    assert summary["paid"] == 5
    assert summary["total"] == 57


# ---------- Member growth history ----------


def _members_page(members: list[dict], page: int, pages: int) -> dict:
    """Build a Ghost paginated response shape for member fixtures."""
    return {
        "members": members,
        "meta": {"pagination": {"page": page, "pages": pages, "total": sum(
            len(p) for p in [members]
        )}},
    }


@patch("src.collectors.ghost.requests.get")
def test_member_growth_history_groups_by_month_with_cumulative(mock_get, collector):
    """Should bucket signups by month and produce a continuous cumulative series."""
    members = [
        {"id": "1", "created_at": "2025-01-15T10:00:00.000Z"},
        {"id": "2", "created_at": "2025-01-22T10:00:00.000Z"},
        # No signups in Feb — series should still include Feb with added=0.
        {"id": "3", "created_at": "2025-03-05T10:00:00.000Z"},
        {"id": "4", "created_at": "2025-03-18T10:00:00.000Z"},
        {"id": "5", "created_at": "2025-03-30T10:00:00.000Z"},
    ]
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value=_members_page(members, 1, 1)),
    )

    history = collector.collect_member_growth_history()

    assert history == [
        {"month": "2025-01", "added": 2, "cumulative": 2},
        {"month": "2025-02", "added": 0, "cumulative": 2},
        {"month": "2025-03", "added": 3, "cumulative": 5},
    ]


@patch("src.collectors.ghost.requests.get")
def test_member_growth_history_empty_when_no_members(mock_get, collector):
    """An empty member list should produce an empty history."""
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value=_members_page([], 1, 1)),
    )
    assert collector.collect_member_growth_history() == []


@patch("src.collectors.ghost.requests.get")
def test_member_growth_history_ignores_records_without_created_at(mock_get, collector):
    """Records missing created_at (or non-string) shouldn't break the aggregation."""
    members = [
        {"id": "1", "created_at": "2025-04-01T00:00:00.000Z"},
        {"id": "2", "created_at": None},
        {"id": "3"},  # missing entirely
        {"id": "4", "created_at": "2025-04-15T00:00:00.000Z"},
    ]
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value=_members_page(members, 1, 1)),
    )
    history = collector.collect_member_growth_history()
    assert history == [{"month": "2025-04", "added": 2, "cumulative": 2}]


@patch("src.collectors.ghost.requests.get")
def test_member_growth_history_persists_only_aggregated_fields_not_pii(mock_get, collector):
    """Regression: PII from raw member records must NEVER appear in the history output.

    Even if Ghost's API ignores the `fields` filter and returns full records
    with names, emails, and other PII, the collector must extract only the
    timestamps and discard the rest before returning.
    """
    members_with_pii = [
        {
            "id": "1",
            "created_at": "2025-06-01T00:00:00.000Z",
            "email": "alice@example.com",
            "name": "Alice Listener",
            "geolocation": '{"country": "US"}',
            "subscribed": True,
            "labels": [{"name": "vip"}],
        },
        {
            "id": "2",
            "created_at": "2025-06-15T00:00:00.000Z",
            "email": "bob@example.com",
            "name": "Bob Subscriber",
        },
    ]
    mock_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value=_members_page(members_with_pii, 1, 1)),
    )

    history = collector.collect_member_growth_history()

    # Serialize the way save_snapshot() would; this is what would end up on disk.
    serialized = json.dumps(history)

    # No PII strings should appear anywhere in the output.
    forbidden_strings = [
        "alice@example.com", "bob@example.com",
        "Alice Listener", "Bob Subscriber",
        "geolocation", "labels", "subscribed",
        "vip", "country",
    ]
    for needle in forbidden_strings:
        assert needle not in serialized, f"PII leaked into history output: {needle!r}"

    # Only the three aggregated keys per entry, nothing else.
    for entry in history:
        assert set(entry.keys()) == {"month", "added", "cumulative"}, (
            f"Unexpected keys in history entry: {set(entry.keys())}"
        )
