"""Tests for the PRX Dovetail CSV importer."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.importers.prx_csv import (
    EpisodeDownloads,
    PRXCSVImporterError,
    _classify_csv,
    _find_csvs,
    _merge_episodes,
    _parse_cumulative_csv,
    _parse_daily_csv,
    import_prx_csv_directory,
    save_snapshot,
)


# ---------- Fixtures ----------


def write_daily_csv(path: Path, dates: list[str], rows: list[list[str]]) -> Path:
    """Write a daily-by-date CSV with arbitrary date columns and rows."""
    header = ["Title", "GUID", "Release Date"] + dates
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n")
    return path


def write_cumulative_csv(path: Path, day_offsets: list[str], rows: list[list[str]]) -> Path:
    """Write a cumulative-by-days-since-drop CSV."""
    header = ["Title", "GUID", "Release Date", "Drop"] + day_offsets
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n")
    return path


# ---------- _classify_csv ----------


def test_classify_csv_recognizes_daily_shape():
    header = ["Title", "GUID", "Release Date", "2026-04-19", "2026-04-20"]
    assert _classify_csv(header) == "daily"


def test_classify_csv_recognizes_cumulative_shape():
    header = ["Title", "GUID", "Release Date", "Drop", "1", "2", "3"]
    assert _classify_csv(header) == "cumulative"


def test_classify_csv_rejects_unknown_shape():
    header = ["Title", "GUID", "Release Date", "Plays", "Streams"]
    with pytest.raises(PRXCSVImporterError, match="Unrecognized"):
        _classify_csv(header)


# ---------- _parse_daily_csv ----------


def test_parse_daily_csv_maps_dates_to_downloads(tmp_path):
    path = write_daily_csv(
        tmp_path / "30day.csv",
        dates=["2026-05-01", "2026-05-02", "2026-05-03"],
        rows=[
            ["Ep One", "guid-1", "2026-05-01", "1000", "400", "200"],
        ],
    )
    episodes = _parse_daily_csv(path)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.guid == "guid-1"
    assert ep.released_at == date(2026, 5, 1)
    assert ep.daily == {
        date(2026, 5, 1): 1000,
        date(2026, 5, 2): 400,
        date(2026, 5, 3): 200,
    }


def test_parse_daily_csv_treats_empty_cells_as_zero(tmp_path):
    path = write_daily_csv(
        tmp_path / "30day.csv",
        dates=["2026-05-01", "2026-05-02"],
        rows=[["Ep One", "guid-1", "2026-05-01", "1000", ""]],
    )
    episodes = _parse_daily_csv(path)
    assert episodes[0].daily[date(2026, 5, 2)] == 0


# ---------- _parse_cumulative_csv ----------


def test_parse_cumulative_csv_converts_to_dailies_via_first_differences(tmp_path):
    # Cumulative: 1000, 1400, 1600 → dailies: 1000, 400, 200
    path = write_cumulative_csv(
        tmp_path / "28day.csv",
        day_offsets=["1", "2"],
        rows=[["Ep One", "guid-1", "2026-05-01", "1000", "1400", "1600"]],
    )
    episodes = _parse_cumulative_csv(path)
    assert episodes[0].daily == {
        date(2026, 5, 1): 1000,
        date(2026, 5, 2): 400,
        date(2026, 5, 3): 200,
    }


def test_parse_cumulative_csv_handles_truncated_rows(tmp_path):
    # Episode released only 2 days ago: only Drop + day 1 columns populated.
    # Cumulative: 3000 → 4500 means day-0 daily 3000, day-1 daily 1500.
    path = write_cumulative_csv(
        tmp_path / "28day.csv",
        day_offsets=["1", "2", "3"],
        rows=[["Brand New Ep", "guid-new", "2026-05-17", "3000", "4500"]],
    )
    episodes = _parse_cumulative_csv(path)
    assert episodes[0].daily == {
        date(2026, 5, 17): 3000,
        date(2026, 5, 18): 1500,
    }


# ---------- EpisodeDownloads derived metrics ----------


def test_derived_metrics_sums_correct_windows():
    ep = EpisodeDownloads(
        guid="g",
        title="T",
        released_at=date(2026, 4, 1),
        daily={date(2026, 4, 1) + timedelta(days=i): 100 for i in range(40)},
    )
    metrics = ep.derived_metrics(snapshot_date=date(2026, 5, 18))
    assert metrics["drop_day_downloads"] == 100
    assert metrics["drop_plus_7"] == 700  # days 0..6 inclusive
    assert metrics["drop_plus_30"] == 3000  # days 0..29 inclusive
    assert metrics["incomplete_windows"] == []
    assert metrics["days_since_release"] == 47


def test_derived_metrics_flags_incomplete_windows_for_young_episodes():
    ep = EpisodeDownloads(
        guid="g",
        title="T",
        released_at=date(2026, 5, 16),
        daily={
            date(2026, 5, 16): 3000,
            date(2026, 5, 17): 1500,
            date(2026, 5, 18): 500,
        },
    )
    metrics = ep.derived_metrics(snapshot_date=date(2026, 5, 18))
    assert metrics["days_since_release"] == 2
    assert "drop_plus_7" in metrics["incomplete_windows"]
    assert "drop_plus_30" in metrics["incomplete_windows"]
    # drop_day should NOT be incomplete — day 0 always exists if episode released
    assert "drop_day_downloads" not in metrics["incomplete_windows"]


# ---------- _merge_episodes ----------


def test_merge_episodes_prefers_earlier_source_on_overlap():
    a = EpisodeDownloads(
        guid="g",
        title="T",
        released_at=date(2026, 5, 1),
        daily={date(2026, 5, 1): 1000, date(2026, 5, 2): 400},
    )
    b = EpisodeDownloads(
        guid="g",
        title="T",
        released_at=date(2026, 5, 1),
        # Overlap on May 1 (different value) + new data on May 3
        daily={date(2026, 5, 1): 9999, date(2026, 5, 3): 200},
    )
    merged = _merge_episodes([[a], [b]])
    assert merged["g"].daily == {
        date(2026, 5, 1): 1000,  # earlier source wins
        date(2026, 5, 2): 400,
        date(2026, 5, 3): 200,  # later source fills gap
    }


def test_merge_episodes_adds_new_guids_from_later_source():
    a = EpisodeDownloads("g1", "T1", date(2026, 5, 1), {date(2026, 5, 1): 100})
    b = EpisodeDownloads("g2", "T2", date(2026, 5, 2), {date(2026, 5, 2): 200})
    merged = _merge_episodes([[a], [b]])
    assert set(merged.keys()) == {"g1", "g2"}


# ---------- _find_csvs ----------


def test_find_csvs_distinguishes_by_filename_heuristics(tmp_path):
    (tmp_path / "WonderCabinet_28day-20260518_Daily_downloads.csv").write_text("dummy")
    (tmp_path / "WonderCabinet_20260419-20260518_Daily_downloads.csv").write_text("dummy")
    (tmp_path / "WonderCabinet_20260218-20260518_Daily_downloads.csv").write_text("dummy")

    ninety, thirty, twenty_eight = _find_csvs(tmp_path)
    assert ninety is not None and "20260218-20260518" in ninety.name
    assert thirty is not None and "20260419-20260518" in thirty.name
    assert twenty_eight is not None and "28day" in twenty_eight.name


# ---------- End-to-end importer ----------


def test_import_prx_csv_directory_produces_full_snapshot(tmp_path):
    # 30-day window: covers May 1 – May 18, episode released May 1
    write_daily_csv(
        tmp_path / "WonderCabinet_20260501-20260518_Daily_downloads.csv",
        dates=[f"2026-05-{d:02d}" for d in range(1, 19)],
        rows=[
            ["Sample Ep", "guid-1", "2026-05-01"]
            + [str(v) for v in [1000, 400, 200, 100, 80, 70, 60, 55, 50, 45, 40, 35, 30, 25, 20, 18, 16, 14]],
        ],
    )
    # 28-day cumulative: same episode, day 0..17
    write_cumulative_csv(
        tmp_path / "WonderCabinet_28day-20260518_Daily_downloads.csv",
        day_offsets=[str(i) for i in range(1, 28)],
        rows=[
            ["Sample Ep", "guid-1", "2026-05-01"]
            + ["1000", "1400", "1600", "1700", "1780", "1850", "1910", "1965",
               "2015", "2060", "2100", "2135", "2165", "2190", "2210", "2228", "2244", "2258"],
        ],
    )

    snapshot = import_prx_csv_directory(
        tmp_path, snapshot_date=date(2026, 5, 18)
    )

    assert snapshot["source"] == "prx_dovetail_csv"
    assert snapshot["snapshot_date"] == "2026-05-18"
    assert len(snapshot["episodes"]) == 1

    ep = snapshot["episodes"][0]
    assert ep["guid"] == "guid-1"
    assert ep["drop_day_downloads"] == 1000
    assert ep["drop_plus_7"] == 1910  # cumulative through day 6
    # drop_plus_30 incomplete — only 17 days elapsed
    assert "drop_plus_30" in ep["incomplete_windows"]

    # Rolling totals should sum dailies across the 30/90 day windows
    assert snapshot["show_totals"]["rolling_30d"] > 0
    assert snapshot["show_totals"]["rolling_90d"] >= snapshot["show_totals"]["rolling_30d"]


def test_import_raises_when_directory_missing(tmp_path):
    with pytest.raises(PRXCSVImporterError, match="not found"):
        import_prx_csv_directory(tmp_path / "does-not-exist")


def test_import_raises_when_no_csvs_present(tmp_path):
    (tmp_path / "readme.txt").write_text("not a csv")
    with pytest.raises(PRXCSVImporterError, match="No PRX CSVs"):
        import_prx_csv_directory(tmp_path)


# ---------- save_snapshot ----------


def test_save_snapshot_writes_to_downloads_subdir(tmp_path):
    snapshot = {
        "source": "prx_dovetail_csv",
        "snapshot_date": "2026-05-18",
        "episodes": [],
        "show_totals": {"rolling_30d": 0, "rolling_90d": 0},
    }
    path = save_snapshot(snapshot, tmp_path)
    assert path == tmp_path / "prx" / "downloads" / "2026-05-18.json"
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["snapshot_date"] == "2026-05-18"
