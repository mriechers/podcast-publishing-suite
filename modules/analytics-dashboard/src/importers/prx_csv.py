"""PRX Dovetail download-metrics CSV importer.

PRX's Dovetail web UI exports per-episode download data as CSVs that the
Dovetail REST API doesn't expose. This importer normalizes those CSVs to a
JSON snapshot consistent with the daily-by-calendar-date schema.

Two CSV shapes are supported:

* **Daily-by-date** (30-day and 90-day window exports). Header columns are
  `Title, GUID, Release Date, <YYYY-MM-DD>, <YYYY-MM-DD>, ...`. Each row is
  an episode and each post-metadata cell is downloads on that calendar day
  (not cumulative).

* **Cumulative-by-days-since-drop** (28-day export). Header columns are
  `Title, GUID, Release Date, Drop, 1, 2, ... 27`. Each row is an episode;
  `Drop` is the day-of-release total, and columns `1..27` are cumulative
  download counts after that many days. Used as fallback for episodes whose
  release date sits outside the coverage window of the daily files.

Derived metrics computed per episode:

* ``drop_day_downloads`` — downloads on the release day (24h)
* ``drop_plus_7`` — cumulative downloads through release_date + 6
* ``drop_plus_30`` — cumulative downloads through release_date + 29 (the
  industry-standard episode comparison window per Buzzsprout/Libsyn/Castos)
* ``incomplete_windows`` — list of window names that don't yet have enough
  elapsed time to be meaningful (e.g. ``drop_plus_30`` for an episode 5
  days old)

Show-level rolling totals (``rolling_30d``, ``rolling_90d``) are computed
by summing daily downloads across all episodes over the relevant date range
ending at the snapshot date.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

DATE_HEADER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DAYS_SINCE_DROP_HEADER_RE = re.compile(r"^\d{1,2}$")


class PRXCSVImporterError(Exception):
    """Raised when a CSV file cannot be parsed or has an unexpected shape."""


@dataclass
class EpisodeDownloads:
    """Per-episode downloads, keyed by calendar date."""

    guid: str
    title: str
    released_at: date
    daily: dict[date, int] = field(default_factory=dict)

    def merge_daily(self, other: dict[date, int]) -> None:
        """Add daily counts from another source, preferring existing values."""
        for d, count in other.items():
            self.daily.setdefault(d, count)

    def cumulative_through(self, end: date) -> int:
        """Total downloads from release date through ``end`` inclusive."""
        return sum(
            count for d, count in self.daily.items()
            if self.released_at <= d <= end
        )

    def derived_metrics(self, snapshot_date: date) -> dict:
        """Compute drop-day, drop+7, drop+30 with incomplete-window flags."""
        elapsed_days = (snapshot_date - self.released_at).days
        incomplete: list[str] = []

        drop_day = self.daily.get(self.released_at, 0)
        drop_plus_7 = self.cumulative_through(self.released_at + timedelta(days=6))
        drop_plus_30 = self.cumulative_through(self.released_at + timedelta(days=29))

        if elapsed_days < 0:
            incomplete.extend(["drop_day_downloads", "drop_plus_7", "drop_plus_30"])
        else:
            if elapsed_days < 6:
                incomplete.append("drop_plus_7")
            if elapsed_days < 29:
                incomplete.append("drop_plus_30")

        return {
            "drop_day_downloads": drop_day,
            "drop_plus_7": drop_plus_7,
            "drop_plus_30": drop_plus_30,
            "incomplete_windows": incomplete,
            "days_since_release": elapsed_days,
        }


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date string."""
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _int_or_zero(value: str) -> int:
    """Parse an integer, treating empty strings as zero."""
    value = value.strip()
    if not value:
        return 0
    return int(value)


def _classify_csv(header: list[str]) -> str:
    """Determine CSV shape from header columns.

    Returns ``"daily"`` for date-keyed exports or ``"cumulative"`` for
    days-since-drop exports.
    """
    data_columns = header[3:]
    if not data_columns:
        raise PRXCSVImporterError(f"CSV header has no data columns: {header}")

    if all(DATE_HEADER_RE.match(c) for c in data_columns):
        return "daily"

    first_col = data_columns[0].strip().lower()
    if first_col == "drop" and all(
        DAYS_SINCE_DROP_HEADER_RE.match(c) for c in data_columns[1:]
    ):
        return "cumulative"

    raise PRXCSVImporterError(
        f"Unrecognized CSV header shape (cols 4+: {data_columns[:5]}...)"
    )


def _parse_daily_csv(path: Path) -> list[EpisodeDownloads]:
    """Parse a daily-by-date CSV into EpisodeDownloads records."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if _classify_csv(header) != "daily":
            raise PRXCSVImporterError(f"{path.name} is not a daily-by-date CSV")
        date_columns = [_parse_date(c) for c in header[3:]]

        episodes: list[EpisodeDownloads] = []
        for row in reader:
            if not row or not row[0]:
                continue
            title, guid, released_at_str = row[0], row[1], row[2]
            released_at = _parse_date(released_at_str)
            daily = {
                date_columns[i]: _int_or_zero(row[3 + i])
                for i in range(len(date_columns))
                if 3 + i < len(row)
            }
            episodes.append(EpisodeDownloads(
                guid=guid,
                title=title,
                released_at=released_at,
                daily=daily,
            ))
    return episodes


def _parse_cumulative_csv(path: Path) -> list[EpisodeDownloads]:
    """Parse a days-since-drop cumulative CSV into EpisodeDownloads records.

    Converts cumulative-by-days-since-drop into daily-by-calendar-date by
    taking first differences and mapping each "day N" column onto
    ``released_at + N`` days.
    """
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if _classify_csv(header) != "cumulative":
            raise PRXCSVImporterError(f"{path.name} is not a cumulative CSV")

        # Day offsets: Drop=0, then 1, 2, 3, ...
        day_offsets = [0] + [int(c) for c in header[4:]]

        episodes: list[EpisodeDownloads] = []
        for row in reader:
            if not row or not row[0]:
                continue
            title, guid, released_at_str = row[0], row[1], row[2]
            released_at = _parse_date(released_at_str)

            cumulative: list[int] = []
            for i in range(len(day_offsets)):
                col_idx = 3 + i
                if col_idx >= len(row) or not row[col_idx].strip():
                    break
                cumulative.append(_int_or_zero(row[col_idx]))

            daily: dict[date, int] = {}
            prev = 0
            for offset, total in zip(day_offsets, cumulative):
                day = released_at + timedelta(days=offset)
                daily[day] = total - prev
                prev = total

            episodes.append(EpisodeDownloads(
                guid=guid,
                title=title,
                released_at=released_at,
                daily=daily,
            ))
    return episodes


def _merge_episodes(
    sources: Iterable[list[EpisodeDownloads]],
) -> dict[str, EpisodeDownloads]:
    """Merge episode records from multiple CSVs, keyed by GUID.

    Earlier sources win on conflicting daily values; later sources fill in
    dates the earlier sources didn't cover. The expected ordering is:
    90-day daily (broadest coverage) → 30-day daily → 28-day cumulative.
    """
    merged: dict[str, EpisodeDownloads] = {}
    for episodes in sources:
        for ep in episodes:
            existing = merged.get(ep.guid)
            if existing is None:
                merged[ep.guid] = EpisodeDownloads(
                    guid=ep.guid,
                    title=ep.title,
                    released_at=ep.released_at,
                    daily=dict(ep.daily),
                )
            else:
                existing.merge_daily(ep.daily)
    return merged


def _find_csvs(directory: Path) -> tuple[Path | None, Path | None, Path | None]:
    """Locate the 90-day, 30-day, and 28-day CSVs in a directory.

    Returns (ninety_day, thirty_day, twenty_eight_day) paths; any may be None
    if not found. Selection uses filename heuristics matching PRX's export
    naming convention.
    """
    csvs = list(directory.glob("*.csv"))
    ninety = thirty = twenty_eight = None

    for path in csvs:
        name = path.name.lower()
        if "28day" in name or "28-day" in name:
            twenty_eight = path
            continue
        # Daily files contain a date range like YYYYMMDD-YYYYMMDD
        match = re.search(r"(\d{8})-(\d{8})", name)
        if match:
            start = datetime.strptime(match.group(1), "%Y%m%d").date()
            end = datetime.strptime(match.group(2), "%Y%m%d").date()
            span = (end - start).days
            if span >= 60:
                ninety = path
            else:
                thirty = path

    return ninety, thirty, twenty_eight


def import_prx_csv_directory(
    directory: Path,
    show_slug: str = "wonder-cabinet",
    snapshot_date: date | None = None,
) -> dict:
    """Read PRX CSV exports from a directory and return a snapshot dict.

    Args:
        directory: Folder containing PRX CSV exports (any combination of
            28-day, 30-day, and 90-day files).
        show_slug: Show identifier matching ``shows/<slug>/``.
        snapshot_date: Override the snapshot date (defaults to today UTC).

    Returns:
        A snapshot dict ready to serialize as JSON.
    """
    if not directory.exists() or not directory.is_dir():
        raise PRXCSVImporterError(f"Directory not found: {directory}")

    ninety, thirty, twenty_eight = _find_csvs(directory)
    if not any([ninety, thirty, twenty_eight]):
        raise PRXCSVImporterError(f"No PRX CSVs found in {directory}")

    sources: list[list[EpisodeDownloads]] = []
    source_files: list[str] = []
    if ninety:
        sources.append(_parse_daily_csv(ninety))
        source_files.append(ninety.name)
    if thirty:
        sources.append(_parse_daily_csv(thirty))
        source_files.append(thirty.name)
    if twenty_eight:
        sources.append(_parse_cumulative_csv(twenty_eight))
        source_files.append(twenty_eight.name)

    episodes = _merge_episodes(sources)

    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).date()

    # Show-level rolling totals from daily-by-date data across all episodes.
    rolling_30_start = snapshot_date - timedelta(days=29)
    rolling_90_start = snapshot_date - timedelta(days=89)
    rolling_30 = 0
    rolling_90 = 0
    for ep in episodes.values():
        for d, count in ep.daily.items():
            if d <= snapshot_date:
                if d >= rolling_30_start:
                    rolling_30 += count
                if d >= rolling_90_start:
                    rolling_90 += count

    episode_records = []
    for ep in sorted(episodes.values(), key=lambda e: e.released_at, reverse=True):
        episode_records.append({
            "guid": ep.guid,
            "title": ep.title,
            "released_at": ep.released_at.isoformat(),
            "daily_downloads": {
                d.isoformat(): count for d, count in sorted(ep.daily.items())
            },
            **ep.derived_metrics(snapshot_date),
        })

    return {
        "source": "prx_dovetail_csv",
        "show": show_slug,
        "snapshot_date": snapshot_date.isoformat(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_files": source_files,
        "episodes": episode_records,
        "show_totals": {
            "rolling_30d": rolling_30,
            "rolling_90d": rolling_90,
        },
        "notes": {
            "ios17_baseline_shift": (
                "Apple iOS 17 (Oct 2023) paused auto-downloads for inactive "
                "followers, causing a 15-25% step-down in measured downloads "
                "industry-wide. Cross-era comparisons require caution."
            ),
            "window_semantics": (
                "drop_plus_30 is the industry-standard episode comparison "
                "window (Buzzsprout, Libsyn, Castos). PRX's native export "
                "is 28-day, derived from the cumulative CSV as fallback."
            ),
        },
    }


def save_snapshot(snapshot: dict, data_dir: Path) -> Path:
    """Persist a snapshot dict to data/prx/downloads/<snapshot_date>.json."""
    out_dir = data_dir / "prx" / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{snapshot['snapshot_date']}.json"
    path.write_text(json.dumps(snapshot, indent=2))
    logger.info("PRX downloads snapshot saved: %s", path)
    return path
