"""Publication filter for the producer-facing dashboard.

Snapshots in ``data/`` capture more than the dashboard should ever expose:
draft post titles, newsletter sender emails, free/paid/comped member
breakdowns. The publication filter is the explicit boundary between
*local snapshot* and *producer-visible artifact* — anything shipped to
the dashboard bundle must pass through here first.

Design principle: **safelist over blacklist.** Only fields explicitly
named here survive into the bundle. New schema additions (e.g. a future
``member_email_audit_log`` field) are silently dropped until a maintainer
consciously adds them to the safelist. The cost of forgetting to update
the filter is a missing chart, not a privacy incident.

This module also handles the cross-source join between PRX downloads and
Ghost posts (matching by normalized title) so the dashboard can render
episode cover art and direct links — both are public data on the
wondercabinetproductions.com site.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Iterable

from ..manifest import get_latest_snapshot

logger = logging.getLogger(__name__)


# Fields kept from each episode in a downloads snapshot. Anything not in
# this set is dropped from the published bundle. ``image_url`` and
# ``episode_url`` are populated by the Ghost join during build, not
# present on the raw PRX snapshot.
EPISODE_SAFELIST = frozenset({
    "guid",
    "title",
    "released_at",
    "daily_downloads",
    "drop_day_downloads",
    "drop_plus_7",
    "drop_plus_30",
    "incomplete_windows",
    "days_since_release",
    "image_url",
    "episode_url",
})

# Fields kept from each published Ghost post in the bundle. Public data
# only — the show's posts are visible on the Ghost-hosted site, so title
# / slug / feature_image / published_at don't expose anything new.
GHOST_POST_SAFELIST = frozenset({
    "title",
    "slug",
    "feature_image",
    "published_at",
})


def filter_ghost_snapshot(snapshot: dict) -> dict:
    """Produce a dashboard-safe view of a Ghost snapshot.

    Kept:
        - ``members.total`` (the headline subscriber count)
        - ``member_growth_history`` (monthly cumulative time series)
        - ``published_posts`` (safelisted fields only — title, slug,
          feature_image, published_at — all public on the Ghost site)
        - ``published_post_count`` (count of published posts)
        - ``most_recent_published_at`` (for "is the show on schedule?")
        - ``collected_at`` / ``snapshot_date``

    Dropped:
        - ``members.free`` / ``members.paid`` / ``members.comped`` (the breakdown
          isn't useful to producers and "paid: 0" reads as a negative signal in
          some funder contexts)
        - All draft and scheduled posts (unpublished editorial)
        - Newsletter ``sender_email`` / ``sender_reply_to`` and all newsletter
          configuration (none of it serves the dashboard)
        - Custom excerpts, post bodies, tags, IDs (not used by the dashboard)
    """
    members = snapshot.get("members") or {}
    posts = snapshot.get("posts") or []

    published_raw = [p for p in posts if p.get("status") == "published"]
    published_filtered = [
        {k: p[k] for k in GHOST_POST_SAFELIST if k in p}
        for p in published_raw
    ]
    most_recent = max(
        (p.get("published_at") for p in published_raw if p.get("published_at")),
        default=None,
    )

    collected_at = snapshot.get("collected_at", "")
    return {
        "source": "ghost",
        "snapshot_date": collected_at[:10] if collected_at else None,
        "collected_at": collected_at or None,
        "members": {
            "total": members.get("total", 0),
        },
        "member_growth_history": list(snapshot.get("member_growth_history") or []),
        "published_posts": published_filtered,
        "published_post_count": len(published_filtered),
        "most_recent_published_at": most_recent,
    }


_TITLE_NORM_RE = re.compile(r"[^\w\s]")


def _normalize_title(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Matches across small punctuation differences between PRX titles (which
    may use straight quotes or em-dashes) and Ghost titles (which may use
    curly quotes or different dash variants).
    """
    if not s:
        return ""
    s = s.replace("—", " ").replace("–", " ")  # em/en dashes → space
    s = _TITLE_NORM_RE.sub(" ", s.lower())
    return " ".join(s.split())


def join_episodes_to_ghost_posts(
    episodes: list[dict],
    posts: list[dict],
    ghost_site_url: str | None = None,
) -> list[dict]:
    """Enrich each episode with image_url + episode_url from matching Ghost post.

    Match key: normalized title (case-insensitive, punctuation-stripped).
    Falls back to release-date match if title doesn't pair.

    If ``ghost_site_url`` is provided, ``episode_url`` is constructed as
    ``{site_url}/{slug}/`` (matching Wonder Cabinet's flat permalink
    pattern). If absent, only ``image_url`` is added.

    Episodes without a matching Ghost post are passed through unchanged.
    """
    by_normalized_title: dict[str, dict] = {}
    by_date: dict[str, dict] = {}
    for p in posts:
        if t := p.get("title"):
            by_normalized_title[_normalize_title(t)] = p
        if pub := p.get("published_at"):
            by_date[pub[:10]] = p

    site_url = (ghost_site_url or "").rstrip("/")
    enriched: list[dict] = []
    matched = 0
    for ep in episodes:
        match = by_normalized_title.get(_normalize_title(ep.get("title") or ""))
        if match is None and ep.get("released_at"):
            match = by_date.get(ep["released_at"][:10])

        if match is None:
            enriched.append(dict(ep))
            continue

        matched += 1
        out = dict(ep)
        if image := match.get("feature_image"):
            out["image_url"] = image
        if site_url and (slug := match.get("slug")):
            out["episode_url"] = f"{site_url}/{slug}/"
        enriched.append(out)

    logger.info("Ghost join: %d/%d episodes matched", matched, len(episodes))
    return enriched


def filter_downloads_snapshot(snapshot: dict) -> dict:
    """Produce a dashboard-safe view of a PRX downloads snapshot.

    The downloads snapshot is already PII-free, but we still safelist the
    episode fields to prevent accidental leakage if the importer schema
    grows. We also drop ``collection_errors`` since the dashboard doesn't
    need failure logs.
    """
    episodes_in = snapshot.get("episodes") or []
    episodes_out = [
        {k: ep[k] for k in EPISODE_SAFELIST if k in ep}
        for ep in episodes_in
    ]

    return {
        "source": snapshot.get("source", "prx_dovetail_csv"),
        "show": snapshot.get("show"),
        "snapshot_date": snapshot.get("snapshot_date"),
        "collected_at": snapshot.get("collected_at"),
        "episodes": episodes_out,
        "show_totals": dict(snapshot.get("show_totals") or {}),
        "notes": dict(snapshot.get("notes") or {}),
    }


def _load_snapshot(path: Path | None) -> dict | None:
    """Load a snapshot file, returning None if path is None or unreadable."""
    if path is None:
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not load snapshot %s: %s", path, e)
        return None


def build_dashboard_bundle(
    data_dir: Path,
    out_dir: Path,
    dashboard_html: Path | None = None,
    extra_assets: Iterable[Path] = (),
    assets_dir: Path | None = None,
    ghost_site_url: str | None = None,
) -> dict[str, Path]:
    """Assemble a publishable bundle from the latest snapshots.

    Reads the latest Ghost snapshot from ``data/ghost/`` and the latest
    downloads snapshot from ``data/prx/downloads/``, runs both through the
    publication filter, joins PRX episodes to Ghost posts so each
    episode picks up its cover art + public URL, and writes everything to
    ``out_dir/data/``. Copies the dashboard HTML and assets into
    ``out_dir/`` and ``out_dir/assets/``.

    Args:
        data_dir: Root of the local snapshot directory (parent of
            ``ghost/`` and ``prx/``).
        out_dir: Destination for the bundle. Created if missing.
        dashboard_html: Optional path to the dashboard ``index.html``.
            Copied to ``out_dir/index.html`` if provided.
        extra_assets: Additional static files to copy into ``out_dir/``.
        assets_dir: Optional folder of assets to copy to ``out_dir/assets/``
            (logos, etc.).
        ghost_site_url: Base URL for constructing episode permalinks
            (e.g. ``https://wondercabinetproductions.com``). If absent,
            episode rows render without links.

    Returns:
        Dict mapping output filename to its absolute path.
    """
    out_dir = out_dir.resolve()
    out_data_dir = out_dir / "data"
    out_data_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    ghost_filtered: dict | None = None
    ghost_path = get_latest_snapshot(data_dir, "ghost")
    ghost_raw = _load_snapshot(ghost_path)
    if ghost_raw is not None:
        ghost_filtered = filter_ghost_snapshot(ghost_raw)
        out_path = out_data_dir / "ghost.json"
        out_path.write_text(json.dumps(ghost_filtered, indent=2, default=str))
        written["data/ghost.json"] = out_path
        logger.info("Wrote filtered Ghost snapshot: %s", out_path)
    else:
        logger.warning("No Ghost snapshot found in %s/ghost/", data_dir)

    downloads_path = get_latest_snapshot(data_dir, "prx/downloads")
    downloads_raw = _load_snapshot(downloads_path)
    if downloads_raw is not None:
        downloads_filtered = filter_downloads_snapshot(downloads_raw)
        # Join episode rows to Ghost posts so each row picks up cover art
        # and a public URL. Both are already in GHOST_POST_SAFELIST; this
        # is just convenience for the dashboard renderer.
        if ghost_filtered is not None:
            posts = ghost_filtered.get("published_posts", [])
            downloads_filtered["episodes"] = join_episodes_to_ghost_posts(
                downloads_filtered["episodes"],
                posts,
                ghost_site_url=ghost_site_url,
            )
        out_path = out_data_dir / "downloads.json"
        out_path.write_text(json.dumps(downloads_filtered, indent=2, default=str))
        written["data/downloads.json"] = out_path
        logger.info("Wrote filtered downloads snapshot: %s", out_path)
    else:
        logger.warning(
            "No downloads snapshot found in %s/prx/downloads/. "
            "Run `import-csv` first.",
            data_dir,
        )

    if dashboard_html and dashboard_html.exists():
        dest = out_dir / "index.html"
        shutil.copy2(dashboard_html, dest)
        written["index.html"] = dest
        logger.info("Copied dashboard HTML: %s", dest)

    if assets_dir and assets_dir.exists():
        out_assets = out_dir / "assets"
        out_assets.mkdir(parents=True, exist_ok=True)
        copied = 0
        # Recursive so nested folders (e.g. assets/fonts/*.woff2) are bundled.
        for src in assets_dir.rglob("*"):
            if src.is_file():
                rel = src.relative_to(assets_dir)
                dest = out_assets / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                written[f"assets/{rel.as_posix()}"] = dest
                copied += 1
        logger.info("Copied %d asset file(s) from %s", copied, assets_dir)

    for asset in extra_assets:
        if asset.exists():
            dest = out_dir / asset.name
            shutil.copy2(asset, dest)
            written[asset.name] = dest

    return written
