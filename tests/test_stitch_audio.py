"""Pure-logic tests for scripts/stitch_audio.py.

ffmpeg/ffprobe I/O is deliberately not exercised here -- that follows the
convention set by the correction-review work: pure logic is unit-tested, the
ffmpeg layer is verified by a real run. Everything below is slot resolution,
config validation, and command-string construction.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from stitch_audio import (  # noqa: E402
    Probe,
    ResolvedSegment,
    StitchConfigError,
    StitchResolutionError,
    build_filter_graph,
    concat_list_text,
    episode_paths,
    load_stitch_spec,
    scan_candidates,
    plan_encoding,
    resolve_slots,
    snap_bitrate,
)

# --- fixtures ----------------------------------------------------------

SHOW_DIR = Path("/repo/shows/in-focus")

IN_FOCUS = {
    "name": "In Focus with Murv Seymour",
    "slug": "in-focus",
    "stitch": {
        "segments": [
            {"id": "intro", "source": "asset", "file": "assets/audio/intro.mp3"},
            {
                "id": "program",
                "source": "episode",
                "match": "program|body|seg",
                "fadeInMs": 250,
                "fadeOutMs": 250,
            },
            {"id": "outro", "source": "asset", "file": "assets/audio/outro.mp3"},
        ]
    },
}

# The Wonder Cabinet shape, expressed in the same schema. Present here to
# prove one config grammar covers both structures -- and to pin the ordering
# regression CLAUDE.md records in production manifests.
WONDER_CABINET = {
    "slug": "wonder-cabinet",
    "stitch": {
        "segments": [
            {"id": "segment_a", "source": "episode", "match": r"(?:mix|part)[\s_-]*0?1\b"},
            {"id": "midroll", "source": "episode", "match": r"mid[\s_-]*roll"},
            {"id": "segment_b", "source": "episode", "match": r"(?:mix|part)[\s_-]*0?2\b"},
        ]
    },
}


def exists_all(_path):
    return True


def exists_only(*paths):
    wanted = {str(Path(p)) for p in paths}
    return lambda p: str(Path(p)) in wanted


def resolve(config, candidates, overrides=None, show_dir=SHOW_DIR, exists=exists_all):
    return resolve_slots(
        load_stitch_spec(config), show_dir, candidates, overrides or {}, exists=exists
    )


def probe(duration, sample_rate=44100, channels=2, codec="mp3", bitrate=128000):
    return Probe(
        codec=codec,
        sample_rate=sample_rate,
        channels=channels,
        duration=duration,
        bitrate=bitrate,
    )


# --- ordering ----------------------------------------------------------


def test_declared_order_is_playback_order():
    resolved = resolve(IN_FOCUS, ["/raw/0815_segment.mp3"])
    assert [r.id for r in resolved] == ["intro", "program", "outro"]
    assert resolved[0].path == SHOW_DIR / "assets/audio/intro.mp3"
    assert resolved[1].path == Path("/raw/0815_segment.mp3")
    assert resolved[2].path == SHOW_DIR / "assets/audio/outro.mp3"


def test_candidate_order_does_not_matter():
    parts = [
        "/e/WC_S01_20_Wiman_mix 01.mp3",
        "/e/WC_S01_20_Wiman_midroll.mp3",
        "/e/WC_S01_20_Wiman_mix 02.mp3",
    ]
    expected = ["segment_a", "midroll", "segment_b"]
    for candidates in (parts, list(reversed(parts)), sorted(parts)):
        resolved = resolve(WONDER_CABINET, candidates)
        assert [r.id for r in resolved] == expected


def test_wonder_cabinet_shape_defeats_lexical_sort():
    """`mid` sorts before `mix`, so sorted() puts the midroll first.

    This is the live bug CLAUDE.md documents in the E10-E18 manifests. Slot
    order comes from the config, never from the filesystem.
    """
    candidates = [
        "/e/WC_S01_20_Wiman_mix 01.mp3",
        "/e/WC_S01_20_Wiman_midroll.mp3",
        "/e/WC_S01_20_Wiman_mix 02.mp3",
    ]
    resolved = resolve(WONDER_CABINET, candidates)
    stitched = [str(r.path) for r in resolved]
    assert stitched != sorted(candidates)
    assert Path(stitched[0]).name.endswith("mix 01.mp3")
    assert Path(stitched[1]).name.endswith("midroll.mp3")


# --- precedence --------------------------------------------------------


def test_override_beats_pattern():
    resolved = resolve(
        IN_FOCUS,
        ["/raw/0815_segment.mp3"],
        overrides={"program": "/elsewhere/final_cut.mp3"},
    )
    assert resolved[1].path == Path("/elsewhere/final_cut.mp3")


def test_override_replaces_an_asset_slot():
    """A one-off episode swapping the standard intro."""
    resolved = resolve(
        IN_FOCUS,
        ["/raw/0815_segment.mp3"],
        overrides={"intro": "/raw/special_open.mp3"},
    )
    assert resolved[0].path == Path("/raw/special_open.mp3")


def test_override_consumes_the_candidate_it_names():
    resolved = resolve(
        IN_FOCUS,
        ["/raw/0815_segment.mp3", "/raw/special_open.mp3"],
        overrides={"intro": "/raw/special_open.mp3"},
    )
    assert [str(r.path) for r in resolved] == [
        "/raw/special_open.mp3",
        "/raw/0815_segment.mp3",
        str(SHOW_DIR / "assets/audio/outro.mp3"),
    ]


def test_fades_carry_through_from_config():
    resolved = resolve(IN_FOCUS, ["/raw/0815_segment.mp3"])
    assert (resolved[1].fade_in_ms, resolved[1].fade_out_ms) == (250, 250)
    assert (resolved[0].fade_in_ms, resolved[0].fade_out_ms) == (0, 0)


# --- failure modes -----------------------------------------------------


def test_missing_required_slot_names_the_slot_and_its_pattern():
    with pytest.raises(StitchResolutionError) as exc:
        resolve(IN_FOCUS, ["/raw/notes.mp3"])
    message = str(exc.value)
    assert "program" in message
    assert "program|body|seg" in message


def test_ambiguous_slot_lists_every_match():
    with pytest.raises(StitchResolutionError) as exc:
        resolve(IN_FOCUS, ["/raw/segment_a.mp3", "/raw/segment_b.mp3"])
    message = str(exc.value)
    assert "segment_a.mp3" in message and "segment_b.mp3" in message
    assert "--slot" in message


def test_an_ambiguous_file_is_not_also_called_an_orphan():
    """One fault, one line. The file matched a slot -- the slot was crowded.

    The pattern here is the real one from shows/in-focus/config.json, and the
    filenames are the real ingest shape: an episode and its later revision
    both sit in the drop folder.
    """
    config = {
        "stitch": {
            "segments": [{"id": "program", "source": "episode", "match": r"\d?INF\d{4}"}]
        }
    }
    with pytest.raises(StitchResolutionError) as exc:
        resolve(config, ["/raw/6INF0199.wav", "/raw/6INF0199_REV20260815.wav"])
    message = str(exc.value)
    assert "2 files matched" in message
    assert "matched no slot" not in message


def test_the_in_focus_pattern_ignores_its_own_bookend_assets():
    """`INFOCUS_INTRO.wav` must not read as an episode body."""
    pattern = load_stitch_spec(
        {"stitch": {"segments": [{"id": "program", "source": "episode",
                                  "match": r"\d?INF\d{4}"}]}}
    ).segments[0].match
    assert pattern.search("6INF0123.wav")
    assert pattern.search("6INF0121_REV20260409.wav")
    assert not pattern.search("INFOCUS_INTRO.wav")
    assert not pattern.search("INFOCUS_OUTRO.wav")


def test_the_mccoshen_ross_pattern_matches_both_ingest_shapes():
    pattern = load_stitch_spec(
        {"stitch": {"segments": [{"id": "program", "source": "episode",
                                  "match": "mcross"}]}}
    ).segments[0].match
    assert pattern.search("HAN2507MCROSS.wav")
    assert pattern.search("6HNS20260814McRoss1.wav")
    assert not pattern.search("HAN2507SHUR.wav")
    assert not pattern.search("HAN2507IWP.wav")


def test_unmatched_candidate_is_fatal():
    with pytest.raises(StitchResolutionError) as exc:
        resolve(IN_FOCUS, ["/raw/0815_segment.mp3", "/raw/bonus_interview.mp3"])
    message = str(exc.value)
    assert "bonus_interview.mp3" in message
    assert "--slot" in message


def test_candidate_claimed_by_two_slots_is_fatal():
    config = {
        "stitch": {
            "segments": [
                {"id": "a", "source": "episode", "match": "seg"},
                {"id": "b", "source": "episode", "match": "ment"},
            ]
        }
    }
    with pytest.raises(StitchResolutionError) as exc:
        resolve(config, ["/raw/segment.mp3"])
    message = str(exc.value)
    assert "segment.mp3" in message
    assert "a" in message and "b" in message


def test_optional_slot_absent_is_dropped_not_fatal():
    config = {
        "stitch": {
            "segments": [
                {"id": "cold_open", "source": "episode", "match": "cold", "required": False},
                {"id": "program", "source": "episode", "match": "program"},
            ]
        }
    }
    resolved = resolve(config, ["/raw/program.mp3"])
    assert [r.id for r in resolved] == ["program"]


def test_missing_asset_file_is_reported():
    with pytest.raises(StitchResolutionError) as exc:
        resolve(
            IN_FOCUS,
            ["/raw/0815_segment.mp3"],
            exists=exists_only("/raw/0815_segment.mp3", SHOW_DIR / "assets/audio/intro.mp3"),
        )
    assert "outro.mp3" in str(exc.value)


def test_unknown_override_slot_is_reported():
    with pytest.raises(StitchResolutionError) as exc:
        resolve(IN_FOCUS, ["/raw/0815_segment.mp3"], overrides={"progrma": "/x.mp3"})
    message = str(exc.value)
    assert "progrma" in message
    assert "program" in message  # lists the slots that do exist


def test_episode_slot_without_pattern_or_override_is_reported():
    config = {"stitch": {"segments": [{"id": "program", "source": "episode"}]}}
    with pytest.raises(StitchResolutionError) as exc:
        resolve(config, [])
    assert "--slot" in str(exc.value)


def test_every_problem_is_reported_at_once():
    """One run, one complete list -- not fix-one-rerun-find-the-next."""
    with pytest.raises(StitchResolutionError) as exc:
        resolve(
            IN_FOCUS,
            ["/raw/bonus.mp3"],
            overrides={"nope": "/x.mp3"},
            exists=exists_only("/raw/bonus.mp3"),
        )
    message = str(exc.value)
    assert "nope" in message  # unknown override slot
    assert "program" in message  # required slot matched nothing
    assert "bonus.mp3" in message  # candidate matched no slot
    assert "intro.mp3" in message  # asset file does not exist


# --- config validation -------------------------------------------------


def test_missing_stitch_block_is_a_config_error():
    with pytest.raises(StitchConfigError) as exc:
        load_stitch_spec({"slug": "in-focus"})
    assert "stitch" in str(exc.value)


def test_empty_segments_is_a_config_error():
    with pytest.raises(StitchConfigError):
        load_stitch_spec({"stitch": {"segments": []}})


def test_duplicate_slot_ids_are_a_config_error():
    config = {
        "stitch": {
            "segments": [
                {"id": "program", "source": "episode", "match": "a"},
                {"id": "program", "source": "episode", "match": "b"},
            ]
        }
    }
    with pytest.raises(StitchConfigError) as exc:
        load_stitch_spec(config)
    assert "program" in str(exc.value)


def test_unknown_source_is_a_config_error():
    config = {"stitch": {"segments": [{"id": "x", "source": "drive", "match": "x"}]}}
    with pytest.raises(StitchConfigError) as exc:
        load_stitch_spec(config)
    assert "drive" in str(exc.value)


def test_asset_slot_without_file_is_a_config_error():
    config = {"stitch": {"segments": [{"id": "intro", "source": "asset"}]}}
    with pytest.raises(StitchConfigError) as exc:
        load_stitch_spec(config)
    assert "file" in str(exc.value)


def test_uncompilable_pattern_is_a_config_error():
    config = {"stitch": {"segments": [{"id": "x", "source": "episode", "match": "([a-"}]}}
    with pytest.raises(StitchConfigError):
        load_stitch_spec(config)


def test_negative_fade_is_a_config_error():
    config = {
        "stitch": {"segments": [{"id": "x", "source": "episode", "match": "x", "fadeInMs": -5}]}
    }
    with pytest.raises(StitchConfigError):
        load_stitch_spec(config)


def test_config_errors_accumulate():
    config = {
        "stitch": {
            "segments": [
                {"id": "intro", "source": "asset"},
                {"id": "intro", "source": "wat"},
            ]
        }
    }
    with pytest.raises(StitchConfigError) as exc:
        load_stitch_spec(config)
    message = str(exc.value)
    assert "file" in message and "wat" in message and "intro" in message


def test_patterns_are_case_insensitive():
    spec = load_stitch_spec(IN_FOCUS)
    assert spec.segments[1].match.search("0815_PROGRAM.MP3")


def test_bitrate_override_is_read():
    config = {
        "stitch": {
            "encode": {"bitrate": "192k"},
            "segments": [{"id": "x", "source": "episode", "match": "x"}],
        }
    }
    assert load_stitch_spec(config).bitrate == "192k"


# --- encode planning ---------------------------------------------------


def seg(name, fade_in=0, fade_out=0):
    return ResolvedSegment(
        id=name, path=Path(f"/raw/{name}.mp3"), fade_in_ms=fade_in, fade_out_ms=fade_out
    )


def test_matching_inputs_without_fades_take_the_copy_path():
    resolved = [seg("intro"), seg("program"), seg("outro")]
    probes = [probe(5.0), probe(12.0), probe(3.0)]
    plan = plan_encoding(resolved, probes, None)
    assert plan.mode == "copy"
    assert plan.reasons == ()
    assert plan.total_duration == pytest.approx(20.0)


def test_any_fade_forces_a_re_encode():
    resolved = [seg("intro"), seg("program", fade_in=250, fade_out=250)]
    plan = plan_encoding(resolved, [probe(5.0), probe(12.0)], None)
    assert plan.mode == "reencode"
    assert any("fade" in r and "program" in r for r in plan.reasons)


def test_sample_rate_mismatch_forces_a_re_encode_and_says_so():
    resolved = [seg("intro"), seg("program")]
    plan = plan_encoding(resolved, [probe(5.0), probe(12.0, sample_rate=22050)], None)
    assert plan.mode == "reencode"
    assert any("sample rate" in r for r in plan.reasons)
    assert plan.sample_rate == 44100  # normalises up, never down


def test_channel_mismatch_forces_a_re_encode():
    plan = plan_encoding(
        [seg("a"), seg("b")], [probe(5.0, channels=1), probe(5.0, channels=2)], None
    )
    assert plan.mode == "reencode"
    assert any("channel" in r for r in plan.reasons)
    assert plan.channels == 2


def test_codec_mismatch_forces_a_re_encode():
    plan = plan_encoding([seg("a"), seg("b")], [probe(5.0), probe(5.0, codec="aac")], None)
    assert plan.mode == "reencode"
    assert any("codec" in r for r in plan.reasons)


def test_re_encode_bitrate_matches_the_richest_input():
    plan = plan_encoding(
        [seg("a", fade_in=100), seg("b")],
        [probe(5.0, bitrate=128000), probe(5.0, bitrate=192000)],
        None,
    )
    assert plan.bitrate == "192k"


def test_derived_bitrate_snaps_back_onto_the_standard_ladder():
    """A 192k MP3 measures ~196k; without snapping every pass creeps upward."""
    plan = plan_encoding(
        [seg("a", fade_in=100), seg("b")],
        [probe(5.0, bitrate=196000), probe(5.0, bitrate=196000)],
        None,
    )
    assert plan.bitrate == "192k"


@pytest.mark.parametrize(
    "measured,expected",
    [(196000, 192), (192000, 192), (128000, 128), (129500, 128),
     (2304000, 320), (40000, 64)],
)
def test_snap_bitrate(measured, expected):
    assert snap_bitrate(measured) == expected


def test_configured_bitrate_wins_over_the_probe():
    plan = plan_encoding([seg("a", fade_in=100)], [probe(5.0, bitrate=128000)], "320k")
    assert plan.bitrate == "320k"


def test_copy_path_carries_no_bitrate():
    plan = plan_encoding([seg("a")], [probe(5.0)], "320k")
    assert plan.mode == "copy"
    assert plan.bitrate is None


# The real source material is 24-bit/48k WAV and the deliverable is an MP3, so
# a copy-path decision that only compares inputs to each other gets this wrong.


def test_wav_sources_cannot_be_stream_copied_into_an_mp3():
    resolved = [seg("intro"), seg("program"), seg("outro")]
    probes = [probe(11.52, codec="pcm_s24le", sample_rate=48000, bitrate=2304000)] * 3
    plan = plan_encoding(resolved, probes, None, ".mp3")
    assert plan.mode == "reencode"
    assert any("stream-copied" in r and ".mp3" in r for r in plan.reasons)
    assert plan.encoder == "libmp3lame"


def test_wav_sources_into_a_wav_output_still_copy():
    resolved = [seg("intro"), seg("program")]
    probes = [probe(11.52, codec="pcm_s24le", sample_rate=48000)] * 2
    assert plan_encoding(resolved, probes, None, ".wav").mode == "copy"


def test_lossless_input_bitrate_does_not_leak_into_the_mp3_target():
    """A 24-bit WAV reports ~2304 kbps. Carrying that over is nonsense."""
    probes = [probe(11.52, codec="pcm_s24le", sample_rate=48000, bitrate=2304000)] * 2
    plan = plan_encoding([seg("a"), seg("b")], probes, None, ".mp3")
    assert plan.bitrate == "192k"  # what these shows actually ship


def test_lossy_bitrate_is_capped():
    probes = [probe(5.0, bitrate=640000), probe(5.0, codec="aac", bitrate=128000)]
    plan = plan_encoding([seg("a"), seg("b")], probes, None, ".mp3")
    assert plan.bitrate == "320k"


def test_output_sample_rate_follows_the_sources():
    probes = [probe(11.52, codec="pcm_s24le", sample_rate=48000)] * 2
    assert plan_encoding([seg("a"), seg("b")], probes, None, ".mp3").sample_rate == 48000


def test_configured_sample_rate_pins_the_output_and_forces_a_re_encode():
    """The masters are 48k but the published catalogue is 44.1k."""
    probes = [probe(11.52, codec="mp3", sample_rate=48000)] * 2
    plan = plan_encoding([seg("a"), seg("b")], probes, None, ".mp3", 44100)
    assert plan.sample_rate == 44100
    assert plan.mode == "reencode"
    assert any("resampling" in r for r in plan.reasons)


def test_configured_sample_rate_that_already_matches_stays_on_the_copy_path():
    probes = [probe(5.0, codec="mp3", sample_rate=44100)] * 2
    plan = plan_encoding([seg("a"), seg("b")], probes, None, ".mp3", 44100)
    assert plan.mode == "copy"
    assert plan.sample_rate == 44100


def test_sample_rate_config_is_validated():
    config = {
        "stitch": {
            "encode": {"sampleRate": "44.1k"},
            "segments": [{"id": "x", "source": "episode", "match": "x"}],
        }
    }
    with pytest.raises(StitchConfigError):
        load_stitch_spec(config)


def test_sample_rate_defaults_to_none():
    assert load_stitch_spec(IN_FOCUS).sample_rate is None


# --- override supersedes rather than orphans ---------------------------


def test_override_supersedes_the_file_its_pattern_would_have_taken():
    """--slot means "use this instead", not "now you have a stray file"."""
    resolved = resolve(
        IN_FOCUS,
        ["/raw/0815_segment.mp3"],
        overrides={"program": "/elsewhere/final_cut.mp3"},
    )
    assert resolved[1].path == Path("/elsewhere/final_cut.mp3")


def test_a_genuinely_stray_file_is_still_fatal_alongside_an_override():
    with pytest.raises(StitchResolutionError) as exc:
        resolve(
            IN_FOCUS,
            ["/raw/0815_segment.mp3", "/raw/stray_take.mp3"],
            overrides={"program": "/elsewhere/final_cut.mp3"},
        )
    message = str(exc.value)
    assert "stray_take.mp3" in message
    assert "0815_segment.mp3" not in message  # superseded, not orphaned


def test_two_slots_never_silently_share_one_file():
    config = {
        "stitch": {
            "segments": [
                {"id": "a", "source": "episode", "match": "seg"},
                {"id": "b", "source": "episode", "match": "ment"},
            ]
        }
    }
    with pytest.raises(StitchResolutionError):
        resolve(config, ["/raw/segment.mp3"])


# --- command construction ----------------------------------------------


def test_filter_graph_normalises_every_input_and_applies_fades():
    resolved = [seg("intro"), seg("program", fade_in=250, fade_out=250)]
    probes = [probe(5.0), probe(12.0)]
    plan = plan_encoding(resolved, probes, None)
    assert build_filter_graph(resolved, probes, plan) == (
        "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a0];"
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
        "afade=t=in:st=0.000:d=0.250,afade=t=out:st=11.750:d=0.250[a1];"
        "[a0][a1]concat=n=2:v=0:a=1[out]"
    )


def test_fade_out_start_never_goes_negative_on_a_short_segment():
    resolved = [seg("sting", fade_out=2000)]
    probes = [probe(0.5)]
    plan = plan_encoding(resolved, probes, None)
    graph = build_filter_graph(resolved, probes, plan)
    assert "afade=t=out:st=0.000:d=0.500" in graph


def test_mono_inputs_produce_a_mono_layout():
    resolved = [seg("a", fade_in=100)]
    probes = [probe(5.0, channels=1)]
    plan = plan_encoding(resolved, probes, None)
    assert "channel_layouts=mono" in build_filter_graph(resolved, probes, plan)


def test_concat_list_escapes_single_quotes():
    text = concat_list_text([Path("/raw/Murv's cut.mp3"), Path("/raw/plain.mp3")])
    assert text == "file '/raw/Murv'\\''s cut.mp3'\nfile '/raw/plain.mp3'\n"


def test_concat_list_ends_with_a_newline():
    assert concat_list_text([Path("/a.mp3")]).endswith("\n")


# --- episode paths -----------------------------------------------------

REPO = Path("/repo")


def paths_for(config, episode="6INF0123", show="in-focus"):
    return episode_paths(config, load_stitch_spec(config), show, episode, REPO)


def test_output_lands_in_the_episode_folder():
    p = paths_for(IN_FOCUS)
    assert p.episode_dir == REPO / "shows/in-focus/episodes/6INF0123"
    assert p.audio_dir == REPO / "shows/in-focus/episodes/6INF0123/audio"
    assert p.out_path == REPO / "shows/in-focus/episodes/6INF0123/audio/6INF0123.mp3"


def test_episode_paths_honour_the_configured_locations():
    config = dict(IN_FOCUS)
    config["episodes"] = {"localPath": "shows/in-focus/eps", "subdirs": {"audio": "mixes"}}
    config["stitch"] = dict(IN_FOCUS["stitch"], output="{show}_{episode}_final.mp3")
    p = paths_for(config)
    assert p.out_path == REPO / "shows/in-focus/eps/6INF0123/mixes/in-focus_6INF0123_final.mp3"


def test_absolute_localpath_escapes_the_repo():
    """The seam for moving show folders off the repo later."""
    config = dict(IN_FOCUS)
    config["episodes"] = {"localPath": "/Volumes/WPM SSD/shows/in-focus/episodes"}
    p = paths_for(config)
    assert p.out_path == Path(
        "/Volumes/WPM SSD/shows/in-focus/episodes/6INF0123/audio/6INF0123.mp3"
    )


def test_output_template_is_validated():
    config = dict(IN_FOCUS)
    config["stitch"] = dict(IN_FOCUS["stitch"], output="{guest}.mp3")
    with pytest.raises(StitchConfigError) as exc:
        load_stitch_spec(config)
    assert "guest" in str(exc.value)


def test_output_template_defaults():
    assert load_stitch_spec(IN_FOCUS).output == "{episode}.mp3"


def test_scan_excludes_the_stitchers_own_output(tmp_path):
    """The deliverable lands beside its inputs and matches the same pattern.

    Without this, a second run sees last run's HAN2507MCROSS.mp3 as another
    candidate body and fails as ambiguous.
    """
    audio = tmp_path / "audio"
    audio.mkdir()
    body = audio / "HAN2507MCROSS.wav"
    output = audio / "HAN2507MCROSS.mp3"
    for f in (body, output):
        f.write_bytes(b"")
    (audio / ".DS_Store").write_bytes(b"")

    assert scan_candidates(audio) == [output, body]
    assert scan_candidates(audio, exclude=output) == [body]
