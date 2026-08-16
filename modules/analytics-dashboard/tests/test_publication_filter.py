"""Tests for the dashboard publication filter.

The filter is the privacy/safety boundary between local snapshots (which
may contain unpublished editorial, sender emails, and other internal
data) and the producer-facing bundle that gets deployed. These tests
guard the boundary — they should be the loudest red flag if anyone ever
relaxes the safelist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dashboard.publication_filter import (
    EPISODE_SAFELIST,
    GHOST_POST_SAFELIST,
    build_dashboard_bundle,
    filter_downloads_snapshot,
    filter_ghost_snapshot,
    join_episodes_to_ghost_posts,
)


# ---------- Ghost filter ----------


def test_filter_ghost_drops_draft_and_scheduled_posts():
    """Only published posts survive into the bundle.

    Note: published post titles DO ship (they're public on the Ghost site
    and needed to join PRX episodes to cover art). Drafts and scheduled
    posts never ship under any circumstance.
    """
    snapshot = {
        "collected_at": "2026-05-18T16:00:00+00:00",
        "members": {"total": 1000, "free": 1000, "paid": 0, "comped": 0},
        "member_growth_history": [],
        "posts": [
            {
                "id": "1", "title": "Published Episode", "status": "published",
                "published_at": "2026-05-10T00:00:00Z", "slug": "published-episode",
                "feature_image": "https://example.com/cover.jpg",
            },
            {"id": "2", "title": "Secret Draft About Upcoming Guest", "status": "draft"},
            {"id": "3", "title": "Scheduled For Next Week", "status": "scheduled",
             "published_at": "2026-05-25T00:00:00Z"},
        ],
    }
    out = filter_ghost_snapshot(snapshot)
    assert out["published_post_count"] == 1
    serialized = json.dumps(out)
    # Draft and scheduled titles must NOT leak under any circumstance.
    assert "Secret Draft" not in serialized
    assert "Scheduled For Next Week" not in serialized
    # Published title DOES ship now (it's public data).
    assert "Published Episode" in serialized
    # And it has all the join-relevant fields.
    assert len(out["published_posts"]) == 1
    assert out["published_posts"][0]["slug"] == "published-episode"
    assert out["published_posts"][0]["feature_image"] == "https://example.com/cover.jpg"


def test_filter_ghost_post_safelist_drops_unknown_fields():
    """Posts go through the GHOST_POST_SAFELIST — extra fields drop out."""
    snapshot = {
        "collected_at": "2026-05-18T16:00:00+00:00",
        "members": {"total": 0},
        "member_growth_history": [],
        "posts": [{
            "status": "published",
            "title": "An Episode",
            "slug": "an-episode",
            "feature_image": "https://example.com/c.jpg",
            "published_at": "2026-05-10T00:00:00Z",
            # Hypothetical fields that must NOT ship:
            "html": "<p>secret body</p>",
            "plaintext": "secret body text",
            "authors": [{"email": "host@example.com"}],
            "email_subject": "Internal subject line",
        }],
    }
    out = filter_ghost_snapshot(snapshot)
    assert len(out["published_posts"]) == 1
    keys = set(out["published_posts"][0].keys())
    assert keys <= GHOST_POST_SAFELIST
    serialized = json.dumps(out)
    assert "secret body" not in serialized
    assert "host@example.com" not in serialized
    assert "Internal subject line" not in serialized


def test_filter_ghost_drops_paid_comped_breakdown():
    snapshot = {
        "collected_at": "2026-05-18T16:00:00+00:00",
        "members": {"total": 1000, "free": 998, "paid": 2, "comped": 0},
        "member_growth_history": [],
        "posts": [],
    }
    out = filter_ghost_snapshot(snapshot)
    assert out["members"] == {"total": 1000}
    # paid/comped/free must not leak through, even though they're not PII —
    # the producer dashboard doesn't need them and "paid: 0" is information
    # that reads poorly in some funder contexts.
    assert "paid" not in out["members"]
    assert "comped" not in out["members"]
    assert "free" not in out["members"]


def test_filter_ghost_drops_newsletter_sender_email():
    snapshot = {
        "collected_at": "2026-05-18T16:00:00+00:00",
        "members": {"total": 100},
        "member_growth_history": [],
        "posts": [],
        "newsletters": [
            {
                "id": "n1",
                "name": "Wonder Cabinet",
                "sender_email": "host@wondercabinetproductions.com",
                "sender_reply_to": "host@wondercabinetproductions.com",
            }
        ],
    }
    out = filter_ghost_snapshot(snapshot)
    serialized = json.dumps(out)
    assert "host@wondercabinetproductions.com" not in serialized
    assert "sender_email" not in serialized
    assert "newsletters" not in out  # entire newsletters block dropped


def test_filter_ghost_preserves_member_growth_history():
    history = [
        {"month": "2025-09", "added": 241, "cumulative": 241},
        {"month": "2025-10", "added": 96, "cumulative": 337},
    ]
    snapshot = {
        "collected_at": "2026-05-18T16:00:00+00:00",
        "members": {"total": 337},
        "member_growth_history": history,
        "posts": [],
    }
    out = filter_ghost_snapshot(snapshot)
    assert out["member_growth_history"] == history


def test_filter_ghost_computes_most_recent_published_at():
    snapshot = {
        "collected_at": "2026-05-18T16:00:00+00:00",
        "members": {"total": 0},
        "member_growth_history": [],
        "posts": [
            {"id": "1", "status": "published", "published_at": "2026-05-10T00:00:00Z"},
            {"id": "2", "status": "published", "published_at": "2026-05-15T00:00:00Z"},
            {"id": "3", "status": "draft"},
        ],
    }
    out = filter_ghost_snapshot(snapshot)
    assert out["most_recent_published_at"] == "2026-05-15T00:00:00Z"


def test_filter_ghost_handles_missing_fields_gracefully():
    """A minimal snapshot should still produce a valid filtered output."""
    out = filter_ghost_snapshot({})
    assert out["members"] == {"total": 0}
    assert out["member_growth_history"] == []
    assert out["published_post_count"] == 0
    assert out["most_recent_published_at"] is None


# ---------- Downloads filter ----------


def test_filter_downloads_safelist_drops_unknown_episode_fields():
    """Any episode field not in EPISODE_SAFELIST should be dropped."""
    snapshot = {
        "source": "prx_dovetail_csv",
        "show": "wonder-cabinet",
        "snapshot_date": "2026-05-18",
        "collected_at": "2026-05-18T16:00:00+00:00",
        "show_totals": {"rolling_30d": 40000, "rolling_90d": 100000},
        "episodes": [
            {
                "guid": "abc-123",
                "title": "An Episode",
                "released_at": "2026-05-01",
                "drop_plus_30": 10000,
                # Hypothetical fields that should be stripped:
                "internal_notes": "guest was a no-show on first booking",
                "ad_revenue_usd": 124.50,
                "host_personal_email": "host@example.com",
            }
        ],
    }
    out = filter_downloads_snapshot(snapshot)
    assert len(out["episodes"]) == 1
    keys = set(out["episodes"][0].keys())
    assert keys <= EPISODE_SAFELIST
    serialized = json.dumps(out)
    assert "internal_notes" not in serialized
    assert "ad_revenue" not in serialized
    assert "host@example.com" not in serialized
    assert "no-show" not in serialized


def test_filter_downloads_preserves_metrics_and_dailies():
    snapshot = {
        "snapshot_date": "2026-05-18",
        "episodes": [
            {
                "guid": "abc",
                "title": "Test",
                "released_at": "2026-05-01",
                "daily_downloads": {"2026-05-01": 100, "2026-05-02": 50},
                "drop_day_downloads": 100,
                "drop_plus_7": 250,
                "drop_plus_30": 400,
                "incomplete_windows": ["drop_plus_30"],
                "days_since_release": 17,
            }
        ],
        "show_totals": {"rolling_30d": 1000, "rolling_90d": 3000},
    }
    out = filter_downloads_snapshot(snapshot)
    ep = out["episodes"][0]
    assert ep["drop_plus_30"] == 400
    assert ep["daily_downloads"] == {"2026-05-01": 100, "2026-05-02": 50}
    assert ep["incomplete_windows"] == ["drop_plus_30"]
    assert out["show_totals"] == {"rolling_30d": 1000, "rolling_90d": 3000}


# ---------- Ghost join ----------


def test_join_episodes_matches_by_normalized_title():
    """Title match should ignore case + punctuation + dash variants."""
    episodes = [
        {"guid": "g1", "title": "Why We Need Fairy Tales Now — with Sharon Blackie", "released_at": "2026-05-09"},
        {"guid": "g2", "title": "Carlo Rovelli: Cosmic Mysteries and the Politics of Wonder", "released_at": "2026-02-07"},
    ]
    posts = [
        {"title": "Why we need fairy tales now -- with sharon blackie",  # case + dash variant
         "slug": "fairy-tales", "feature_image": "https://x.com/a.jpg"},
        {"title": "Carlo Rovelli: Cosmic Mysteries and the Politics of Wonder",
         "slug": "rovelli", "feature_image": "https://x.com/b.jpg"},
    ]
    out = join_episodes_to_ghost_posts(
        episodes, posts, ghost_site_url="https://example.com",
    )
    assert out[0]["image_url"] == "https://x.com/a.jpg"
    assert out[0]["episode_url"] == "https://example.com/fairy-tales/"
    assert out[1]["episode_url"] == "https://example.com/rovelli/"


def test_join_episodes_falls_back_to_release_date():
    """If title doesn't match, fall back to matching on release date."""
    episodes = [
        {"guid": "g1", "title": "PRX Title Variant", "released_at": "2026-05-09"},
    ]
    posts = [
        {"title": "Completely Different Ghost Title", "slug": "ghost-slug",
         "published_at": "2026-05-09T12:00:00Z", "feature_image": "https://x.com/img.jpg"},
    ]
    out = join_episodes_to_ghost_posts(
        episodes, posts, ghost_site_url="https://example.com",
    )
    assert out[0]["image_url"] == "https://x.com/img.jpg"
    assert out[0]["episode_url"] == "https://example.com/ghost-slug/"


def test_join_episodes_no_match_returns_episode_unchanged():
    """Episodes without a Ghost match should pass through with no image/url."""
    episodes = [{"guid": "g1", "title": "Orphan Episode", "released_at": "2026-05-09"}]
    posts = [{"title": "Unrelated Post", "slug": "unrelated",
              "published_at": "2025-01-01T00:00:00Z", "feature_image": "https://x.com/i.jpg"}]
    out = join_episodes_to_ghost_posts(episodes, posts, ghost_site_url="https://example.com")
    assert "image_url" not in out[0]
    assert "episode_url" not in out[0]
    assert out[0]["title"] == "Orphan Episode"


def test_join_episodes_without_site_url_skips_episode_url():
    """No ghost_site_url means no episode_url, but image_url still lands."""
    episodes = [{"guid": "g1", "title": "Hello", "released_at": "2026-05-09"}]
    posts = [{"title": "Hello", "slug": "hello", "feature_image": "https://x.com/i.jpg"}]
    out = join_episodes_to_ghost_posts(episodes, posts, ghost_site_url=None)
    assert out[0]["image_url"] == "https://x.com/i.jpg"
    assert "episode_url" not in out[0]


# ---------- build_dashboard_bundle ----------


def _write_snapshot(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content))


def test_build_dashboard_bundle_writes_filtered_snapshots(tmp_path):
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "dist"

    _write_snapshot(
        data_dir / "ghost" / "2026-05-18.json",
        {
            "collected_at": "2026-05-18T16:00:00+00:00",
            "members": {"total": 1000, "free": 1000, "paid": 0, "comped": 0},
            "member_growth_history": [
                {"month": "2026-04", "added": 75, "cumulative": 925},
                {"month": "2026-05", "added": 75, "cumulative": 1000},
            ],
            "posts": [
                {"id": "1", "status": "published", "published_at": "2026-04-01T00:00:00Z",
                 "title": "Episode 1", "slug": "episode-1",
                 "feature_image": "https://example.com/ep1.jpg",
                 "html": "should not ship"},
                {"id": "2", "status": "draft", "title": "Secret Draft"},
            ],
            "newsletters": [{"sender_email": "host@example.com"}],
        },
    )
    _write_snapshot(
        data_dir / "prx" / "downloads" / "2026-05-18.json",
        {
            "source": "prx_dovetail_csv",
            "show": "wonder-cabinet",
            "snapshot_date": "2026-05-18",
            "episodes": [
                {"guid": "ep1", "title": "Episode 1", "released_at": "2026-04-01",
                 "drop_plus_30": 10000, "incomplete_windows": [], "days_since_release": 47,
                 "drop_day_downloads": 4000, "drop_plus_7": 8000, "daily_downloads": {}},
            ],
            "show_totals": {"rolling_30d": 40000, "rolling_90d": 100000},
        },
    )

    written = build_dashboard_bundle(
        data_dir=data_dir, out_dir=out_dir,
        ghost_site_url="https://example.com",
    )

    assert "data/ghost.json" in written
    assert "data/downloads.json" in written

    ghost_out = json.loads((out_dir / "data" / "ghost.json").read_text())
    assert ghost_out["members"] == {"total": 1000}
    assert ghost_out["published_post_count"] == 1
    serialized_ghost = json.dumps(ghost_out)
    assert "Secret Draft" not in serialized_ghost
    assert "host@example.com" not in serialized_ghost
    assert "should not ship" not in serialized_ghost  # html body dropped
    # Published title DOES ship.
    assert "Episode 1" in serialized_ghost

    # Episodes are joined to Ghost posts during build.
    downloads_out = json.loads((out_dir / "data" / "downloads.json").read_text())
    ep = downloads_out["episodes"][0]
    assert ep["drop_plus_30"] == 10000
    assert ep["image_url"] == "https://example.com/ep1.jpg"
    assert ep["episode_url"] == "https://example.com/episode-1/"


def test_build_dashboard_bundle_copies_assets_dir(tmp_path):
    """Assets folder should be copied verbatim into out_dir/assets/."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "dist"
    assets_dir = tmp_path / "src-assets"
    assets_dir.mkdir()
    (assets_dir / "logo.svg").write_text('<svg></svg>')
    (assets_dir / "icon.png").write_bytes(b'\x89PNG\r\n\x1a\n')

    _write_snapshot(
        data_dir / "ghost" / "2026-05-18.json",
        {"collected_at": "2026-05-18T16:00:00+00:00", "members": {"total": 100}},
    )

    written = build_dashboard_bundle(
        data_dir=data_dir, out_dir=out_dir, assets_dir=assets_dir,
    )
    assert "assets/logo.svg" in written
    assert "assets/icon.png" in written
    assert (out_dir / "assets" / "logo.svg").exists()


def test_build_dashboard_bundle_no_snapshots(tmp_path):
    """Empty data_dir should return an empty dict, not crash."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "dist"
    data_dir.mkdir()
    written = build_dashboard_bundle(data_dir=data_dir, out_dir=out_dir)
    assert written == {}


def test_build_dashboard_bundle_copies_html_when_provided(tmp_path):
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "dist"
    html_src = tmp_path / "src" / "index.html"
    html_src.parent.mkdir(parents=True)
    html_src.write_text("<!doctype html><h1>Wonder Cabinet</h1>")

    _write_snapshot(
        data_dir / "ghost" / "2026-05-18.json",
        {"collected_at": "2026-05-18T16:00:00+00:00", "members": {"total": 100}},
    )

    written = build_dashboard_bundle(
        data_dir=data_dir, out_dir=out_dir, dashboard_html=html_src,
    )
    assert "index.html" in written
    assert (out_dir / "index.html").read_text().startswith("<!doctype html>")
