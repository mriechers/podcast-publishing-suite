"""Pure-logic tests for scripts/ingest_scan.py.

Network I/O is not exercised here -- the fixtures below are real rows copied
verbatim from https://mmingest.pbswi.wisc.edu/InFocus/ and /HereNow/, so the
parser is tested against the markup it will actually meet.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ingest_scan import (  # noqa: E402
    IngestConfigError,
    base_key,
    group_episodes,
    load_ingest_spec,
    local_episode_keys,
    parse_listing,
    plan_fetch,
    split_stem,
)

# --- fixtures: verbatim rows from the live servers ---------------------

IN_FOCUS_HTML = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html><head><title>Index of /InFocus</title></head><body>
<h1>Index of /InFocus</h1><table>
<tr><th valign="top"><img src="/icons/blank.gif" alt="[ICO]"></th><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">Last modified</a></th><th><a href="?C=S;O=A">Size</a></th></tr>
<tr><td valign="top"><img src="/icons/back.gif" alt="[PARENTDIR]"></td><td><a href="/">Parent Directory</a></td><td>&nbsp;</td><td align="right">  - </td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/sound2.gif" alt="[SND]"></td><td><a href="6INF0123.wav">6INF0123.wav</a></td><td align="right">2026-08-13 16:58  </td><td align="right">823M</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/movie.gif" alt="[VID]"></td><td><a href="6INF0123.mp4">6INF0123.mp4</a></td><td align="right">2026-08-13 16:56  </td><td align="right">5.1G</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/sound2.gif" alt="[SND]"></td><td><a href="6INF0123.mp3">6INF0123.mp3</a></td><td align="right">2026-08-13 16:58  </td><td align="right"> 69M</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/text.gif" alt="[TXT]"></td><td><a href="6INF0122.srt">6INF0122.srt</a></td><td align="right">2026-08-09 20:56  </td><td align="right"> 59K</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/sound2.gif" alt="[SND]"></td><td><a href="6INF0122.wav">6INF0122.wav</a></td><td align="right">2026-08-09 21:09  </td><td align="right">595M</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/text.gif" alt="[TXT]"></td><td><a href="6INF0122.txt">6INF0122.txt</a></td><td align="right">2026-08-09 20:57  </td><td align="right"> 31K</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/unknown.gif" alt="[   ]"></td><td><a href="6INF0122.scc">6INF0122.scc</a></td><td align="right">2026-08-09 20:56  </td><td align="right">112K</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/image2.gif" alt="[IMG]"></td><td><a href="6INF0120_podtile2.jpg">6INF0120_podtile2.jpg</a></td><td align="right">2026-04-13 17:40  </td><td align="right">594K</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/sound2.gif" alt="[SND]"></td><td><a href="6INF0121_REV20260409.wav">6INF0121_REV20260409.wav</a></td><td align="right">2026-04-10 14:49  </td><td align="right">645M</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/sound2.gif" alt="[SND]"></td><td><a href="6INF0121.wav">6INF0121.wav</a></td><td align="right">2026-04-07 12:41  </td><td align="right">640M</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/unknown.gif" alt="[   ]"></td><td><a href="Thumbs.db">Thumbs.db</a></td><td align="right">2025-07-09 13:38  </td><td align="right">260K</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/folder.gif" alt="[DIR]"></td><td><a href="2400%20season/">2400 season/</a></td><td align="right">2025-08-01 13:36  </td><td align="right">  - </td><td>&nbsp;</td></tr>
</table></body></html>"""

IN_FOCUS_CONFIG = {
    "slug": "in-focus",
    "episodes": {"localPath": "shows/in-focus/episodes", "subdirs": {"audio": "audio"}},
    "ingest": {
        "url": "https://mmingest.pbswi.wisc.edu/InFocus/",
        "episodePattern": r"^6INF\d{4}(?:_REV\d{8})?$",
        "artifacts": {
            ".wav": {"dest": "audio", "required": True},
            ".srt": {"dest": "captions", "required": False},
            ".scc": {"dest": "captions", "required": False},
            ".txt": {"dest": "captions", "required": False},
        },
    },
}

MCROSS_CONFIG = {
    "slug": "mccoshen-ross",
    "ingest": {
        "url": "https://mmingest.pbswi.wisc.edu/HereNow/",
        "episodePattern": r"^HAN\d{4}MCROSS$",
        "artifacts": {".wav": {"dest": "audio", "required": True}},
    },
}


def spec(config=IN_FOCUS_CONFIG):
    return load_ingest_spec(config)


def episodes(html=IN_FOCUS_HTML, config=IN_FOCUS_CONFIG):
    return group_episodes(parse_listing(html), load_ingest_spec(config))


# --- listing parser ----------------------------------------------------


def test_parses_name_modified_and_size():
    entries = {e.name: e for e in parse_listing(IN_FOCUS_HTML)}
    assert entries["6INF0123.wav"].modified == "2026-08-13 16:58"
    assert entries["6INF0123.wav"].size == "823M"
    assert entries["6INF0123.mp3"].size == "69M"  # leading pad stripped


def test_skips_parent_directory_and_subfolders():
    names = [e.name for e in parse_listing(IN_FOCUS_HTML)]
    assert "Parent Directory" not in names
    assert not any(n.endswith("/") for n in names)
    assert "2400 season/" not in names


def test_empty_listing_is_not_an_error():
    assert parse_listing("<html><body>nothing here</body></html>") == []


@pytest.mark.parametrize(
    "name,stem,ext",
    [
        ("6INF0123.wav", "6INF0123", ".wav"),
        ("6INF0121_REV20260409.wav", "6INF0121_REV20260409", ".wav"),
        ("HAN2507MCROSS.wav", "HAN2507MCROSS", ".wav"),
        ("Thumbs.db", "Thumbs", ".db"),
        ("noextension", "noextension", ""),
    ],
)
def test_split_stem(name, stem, ext):
    assert split_stem(name) == (stem, ext)


# --- grouping ----------------------------------------------------------


def test_groups_files_by_episode():
    found = {e.key: e for e in episodes()}
    assert set(found["6INF0122"].files) == {".srt", ".wav", ".txt", ".scc"}
    assert found["6INF0122"].files[".wav"].size == "595M"


def test_ignores_files_that_are_not_episodes():
    keys = {e.key for e in episodes()}
    assert "Thumbs" not in keys
    assert "6INF0120_podtile2" not in keys  # a tile, not an episode


def test_only_declared_artifacts_are_collected():
    """The .mp4 and production's own .mp3 are on the server and unwanted."""
    found = {e.key: e for e in episodes()}
    assert set(found["6INF0123"].files) == {".wav"}


def test_episodes_are_newest_first():
    keys = [e.key for e in episodes()]
    assert keys[0] == "6INF0123"
    assert keys.index("6INF0122") < keys.index("6INF0121")


def test_latest_modified_is_the_newest_file_in_the_episode():
    found = {e.key: e for e in episodes()}
    assert found["6INF0122"].latest_modified == "2026-08-09 21:09"


@pytest.mark.parametrize(
    "key,base",
    [
        ("6INF0121_REV20260409", "6INF0121"),
        ("6INF0121", "6INF0121"),
        ("HAN2507MCROSS", "HAN2507MCROSS"),
        ("6INF0107_REV20240501", "6INF0107"),
    ],
)
def test_base_key_strips_the_revision_suffix(key, base):
    assert base_key(key) == base


def test_revisions_are_distinct_episodes_but_share_a_base():
    found = {e.key: e for e in episodes()}
    assert "6INF0121" in found and "6INF0121_REV20260409" in found
    assert found["6INF0121_REV20260409"].base == "6INF0121"
    assert found["6INF0121_REV20260409"].is_revision
    assert not found["6INF0121"].is_revision


def test_mccoshen_ross_pattern_excludes_other_here_and_now_segments():
    html = IN_FOCUS_HTML.replace("6INF0123.wav", "HAN2507MCROSS.wav").replace(
        "6INF0122.wav", "HAN2507SHUR.wav"
    )
    keys = {e.key for e in group_episodes(parse_listing(html), spec(MCROSS_CONFIG))}
    assert keys == {"HAN2507MCROSS"}


# --- config validation -------------------------------------------------


def test_missing_ingest_block_is_an_error():
    with pytest.raises(IngestConfigError) as exc:
        load_ingest_spec({"slug": "x"})
    assert "ingest" in str(exc.value)


def test_missing_url_is_an_error():
    with pytest.raises(IngestConfigError):
        load_ingest_spec({"ingest": {"episodePattern": "^x$", "artifacts": {".wav": {}}}})


def test_bad_pattern_is_an_error():
    with pytest.raises(IngestConfigError):
        load_ingest_spec(
            {"ingest": {"url": "http://x/", "episodePattern": "([a-", "artifacts": {".wav": {}}}}
        )


def test_no_artifacts_is_an_error():
    with pytest.raises(IngestConfigError):
        load_ingest_spec({"ingest": {"url": "http://x/", "episodePattern": "^x$", "artifacts": {}}})


def test_extension_must_start_with_a_dot():
    with pytest.raises(IngestConfigError) as exc:
        load_ingest_spec(
            {"ingest": {"url": "http://x/", "episodePattern": "^x$", "artifacts": {"wav": {}}}}
        )
    assert "wav" in str(exc.value)


def test_artifact_defaults():
    parsed = spec().artifacts[".srt"]
    assert parsed.dest == "captions"
    assert parsed.required is False


# --- fetch planning ----------------------------------------------------


def test_fetch_plan_routes_each_artifact_to_its_subdir(tmp_path):
    episode = {e.key: e for e in episodes()}["6INF0122"]
    items, missing = plan_fetch(episode, spec(), tmp_path)
    by_ext = {i.ext: i for i in items}

    assert by_ext[".wav"].dest == tmp_path / "audio" / "6INF0122.wav"
    assert by_ext[".srt"].dest == tmp_path / "captions" / "6INF0122.srt"
    assert by_ext[".wav"].url == "https://mmingest.pbswi.wisc.edu/InFocus/6INF0122.wav"
    assert missing == []


def test_missing_required_artifact_is_reported(tmp_path):
    """An episode whose body has not landed yet is not ready to pull."""
    html = IN_FOCUS_HTML.replace('href="6INF0122.wav"', 'href="6INF0122.zzz"')
    episode = {e.key: e for e in episodes(html)}["6INF0122"]
    _, missing = plan_fetch(episode, spec(), tmp_path)
    assert missing == [".wav"]


def test_already_downloaded_files_are_skipped(tmp_path):
    episode = {e.key: e for e in episodes()}["6INF0122"]
    (tmp_path / "audio").mkdir(parents=True)
    (tmp_path / "audio" / "6INF0122.wav").write_bytes(b"already here")

    items, missing = plan_fetch(episode, spec(), tmp_path)
    assert ".wav" not in {i.ext for i in items}
    assert missing == []  # present locally counts as satisfied


def test_fetch_plan_is_empty_when_everything_is_local(tmp_path):
    episode = {e.key: e for e in episodes()}["6INF0122"]
    for sub, ext in (("audio", ".wav"), ("captions", ".srt"),
                     ("captions", ".scc"), ("captions", ".txt")):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
        (tmp_path / sub / f"6INF0122{ext}").write_bytes(b"x")
    items, missing = plan_fetch(episode, spec(), tmp_path)
    assert items == [] and missing == []


# --- local state -------------------------------------------------------


def test_local_episode_keys_reads_the_episodes_directory(tmp_path):
    (tmp_path / "6INF0122" / "audio").mkdir(parents=True)
    (tmp_path / "6INF0121_REV20260409").mkdir()
    (tmp_path / ".DS_Store").write_bytes(b"")
    assert local_episode_keys(tmp_path) == {"6INF0122", "6INF0121_REV20260409"}


def test_local_episode_keys_on_a_missing_directory_is_empty(tmp_path):
    assert local_episode_keys(tmp_path / "nope") == set()
