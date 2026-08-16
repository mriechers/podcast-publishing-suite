"""Tests for scripts/resolve_audio.py.

The corpus below is real: every filename set is taken verbatim from a
Wonder Cabinet episode folder on Google Drive (E10-E20). The variance is
the point — separators, leading spaces, nesting depth, and guest-name
spelling all drift between episodes, while the three-part shape does not.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from resolve_audio import (  # noqa: E402
    AudioResolutionError,
    classify_parts,
    pick_image_dir,
)

# Real Drive filename sets, keyed by episode.
REAL_EPISODES = {
    "E12 Henderson": [" Henderson_midroll.mp3", "Henderson_mix_01.mp3", "Henderson_mix_02.mp3"],
    "E14 Koch": [" Koch_-midroll.mp3", "Koch_mix_01.mp3", "Koch_mix_02.mp3"],
    "E15 Burnett": ["Burnett_midroll.mp3", "Burnett_mix_02.mp3", "Burnett_mix_01.mp3"],
    "E16 Lightman": ["Lightman_mix_02.mp3", "Lightman_mix_01.mp3", "Lightman_midroll.mp3"],
    "E17 Vaughn-Lee": ["vaugn-lee_mix_02.mp3", "vaugn-lee_mix_01.mp3", "vaugn-lee_midroll.mp3"],
    "E18 Goff": ["Goff_mix_01.mp3", "Goff_midroll.mp3", "Goff_mix_02.mp3"],
    "E19 Flyn": ["Flynn _mix_01.mp3", "Flynn_midroll.mp3", "Flynn_mix_02.mp3"],
    "E20 Wiman": ["Wiman_mix 01.mp3", "Wiman_midroll.mp3", "Wiman_mix 02.mp3"],
}


@pytest.mark.parametrize("episode,names", REAL_EPISODES.items(), ids=list(REAL_EPISODES))
def test_real_episodes_classify_in_semantic_order(episode, names):
    """Every historical episode resolves to part01 -> midroll -> part02."""
    resolved = classify_parts(names)

    assert [role for role, _ in resolved] == ["part01", "midroll", "part02"]
    part01, midroll, part02 = (name for _, name in resolved)
    assert "01" in part01 or "_1" in part01
    assert "midroll" in midroll.lower().replace("-", "").replace("_", "")
    assert "02" in part02 or "_2" in part02


def test_wiman_defeats_lexical_sort():
    """E20 is the case that breaks sorted(): 'mid' < 'mix ' puts midroll first."""
    names = REAL_EPISODES["E20 Wiman"]
    assert sorted(names)[0] == "Wiman_midroll.mp3"  # the bug we are fixing

    resolved = classify_parts(names)
    assert resolved[0] == ("part01", "Wiman_mix 01.mp3")


def test_canonical_output_is_reclassifiable():
    """The names this script writes must survive a second pass through it."""
    slug = "WC_S01_20_Christian_Wiman"
    names = [f"{slug}_part02.mp3", f"{slug}_midroll.mp3", f"{slug}_part01.mp3"]
    assert classify_parts(names) == [
        ("part01", f"{slug}_part01.mp3"),
        ("midroll", f"{slug}_midroll.mp3"),
        ("part02", f"{slug}_part02.mp3"),
    ]


def test_input_order_does_not_matter():
    """Classification is by pattern, not by the order Drive listed the files."""
    names = REAL_EPISODES["E18 Goff"]
    baseline = classify_parts(names)
    assert classify_parts(list(reversed(names))) == baseline
    assert classify_parts(sorted(names)) == baseline


def test_full_paths_are_preserved():
    """Nested Drive paths (E17 was two levels deep) survive classification."""
    names = [
        "WC_117_Vaughn_Lee/WC_01_17_Vaughn-Lee/vaugn-lee_mix_01.mp3",
        "WC_117_Vaughn_Lee/WC_01_17_Vaughn-Lee/vaugn-lee_midroll.mp3",
        "WC_117_Vaughn_Lee/WC_01_17_Vaughn-Lee/vaugn-lee_mix_02.mp3",
    ]
    resolved = classify_parts(names)
    assert [role for role, _ in resolved] == ["part01", "midroll", "part02"]
    assert all("/" in name for _, name in resolved)


@pytest.mark.parametrize(
    "variant",
    [
        ["X_mix_01.mp3", "X_midroll.mp3", "X_mix_02.mp3"],
        ["X_mix 01.mp3", "X_mid-roll.mp3", "X_mix 02.mp3"],
        ["X_MIX_01.MP3", "X_MidRoll.MP3", "X_MIX_02.MP3"],
        ["X_mix1.mp3", "X_midroll.mp3", "X_mix2.mp3"],
        ["X-mix-1.mp3", "X-midroll.mp3", "X-mix-2.mp3"],
    ],
    ids=["underscore", "space-and-hyphen", "uppercase", "no-zero-pad", "hyphen"],
)
def test_separator_and_case_variants(variant):
    assert [role for role, _ in classify_parts(variant)] == ["part01", "midroll", "part02"]


# --- Failure modes: these must be loud, not silent ---


def test_missing_part_raises():
    with pytest.raises(AudioResolutionError, match="part02"):
        classify_parts(["X_mix_01.mp3", "X_midroll.mp3"])


def test_extra_mp3_raises():
    with pytest.raises(AudioResolutionError, match="4 MP3"):
        classify_parts(
            ["X_mix_01.mp3", "X_midroll.mp3", "X_mix_02.mp3", "X_outtakes.mp3"]
        )


def test_duplicate_role_raises():
    with pytest.raises(AudioResolutionError, match="part01"):
        classify_parts(["a/X_mix_01.mp3", "b/X_mix_01.mp3", "X_midroll.mp3"])


def test_unrecognisable_names_raise():
    with pytest.raises(AudioResolutionError):
        classify_parts(["one.mp3", "two.mp3", "three.mp3"])


def test_empty_input_raises():
    with pytest.raises(AudioResolutionError, match="0 MP3"):
        classify_parts([])


# --- Image folder discovery ---


@pytest.mark.parametrize(
    "dirs,expected",
    [
        (["Images"], "Images"),
        (["Photos"], "Photos"),
        (["WC_01_19_Flynn", "Photos"], "Photos"),
        (["Images", "Images for Newsletter"], "Images"),
        (["images"], "images"),
        (["WC_01_15_Burnett"], None),
        ([], None),
    ],
    ids=["images", "photos", "with-audio-dir", "prefers-exact", "lowercase", "none", "empty"],
)
def test_pick_image_dir(dirs, expected):
    assert pick_image_dir(dirs) == expected
