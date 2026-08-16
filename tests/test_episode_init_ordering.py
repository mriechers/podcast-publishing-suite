"""Tests for manifest audio ordering in scripts/episode-init.py.

episode-init refreshes metadata for directories that may hold more than the
three source parts, so its ordering is best-effort where the resolver's is
strict. These cases pin that difference.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

# episode-init.py is not an importable module name (hyphen), so load by path.
_spec = importlib.util.spec_from_file_location("episode_init", SCRIPTS / "episode-init.py")
episode_init = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(episode_init)
order_audio_parts = episode_init.order_audio_parts


def test_orders_three_parts_for_playback():
    assert order_audio_parts(
        ["Wiman_midroll.mp3", "Wiman_mix 01.mp3", "Wiman_mix 02.mp3"]
    ) == ["Wiman_mix 01.mp3", "Wiman_midroll.mp3", "Wiman_mix 02.mp3"]


def test_stitched_full_audio_sorts_last():
    """E19's directory shape: three parts plus a stitched full episode."""
    ordered = order_audio_parts(
        [
            "Flynn _mix_01.mp3",
            "Flynn_midroll.mp3",
            "Flynn_mix_02.mp3",
            "WC_S01_19_Cal_Flyn_full.mp3",
        ]
    )
    assert ordered[:3] == ["Flynn _mix_01.mp3", "Flynn_midroll.mp3", "Flynn_mix_02.mp3"]
    assert ordered[3] == "WC_S01_19_Cal_Flyn_full.mp3"


def test_canonical_names_round_trip():
    """Names this pipeline now writes must re-order correctly on refresh."""
    slug = "WC_S01_20_Christian_Wiman"
    assert order_audio_parts(
        [f"{slug}_midroll.mp3", f"{slug}_part02.mp3", f"{slug}_part01.mp3"]
    ) == [f"{slug}_part01.mp3", f"{slug}_midroll.mp3", f"{slug}_part02.mp3"]


@pytest.mark.parametrize(
    "files",
    [
        ["mystery_a.mp3", "mystery_b.mp3"],
        ["only_one_mix_01.mp3"],
        [],
    ],
    ids=["unrecognisable", "incomplete", "empty"],
)
def test_falls_back_instead_of_raising(files):
    """A manifest refresh must never crash over unexpected audio naming."""
    assert order_audio_parts(files) == files
