from __future__ import annotations

import pytest

import src.wc_correction_review as review
from src.wc_correction_review import Cue, PassageMatch, ReviewEntry, extract_clip_b64, format_timestamp, locate_passage, parse_srt, render_review_html


# Real strings: Koch manifest passage opening vs the raw SRT cue (edit drift).
_KOCH_CUE = (
    "So William James, one of the best writers, you know, the American sort of "
    "father of American psychology, wrote this beautiful book in 1902, The "
    "Varieties of Religious Experiences, which is essentially a large part of "
    "that has to do with these, what he called religious experiences."
)
_KOCH_PASSAGE = (
    "William James, one of the great writers - the father of American psychology "
    "- wrote this beautiful book in 1902, The Varieties of Religious Experience, "
    "which is essentially largely about what he called religious experiences."
)


class TestLocatePassage:
    def test_matches_despite_edit_drift(self):
        cues = [
            Cue(1, 0.0, 3.0, "Welcome to Wonder Cabinet."),
            Cue(2, 1462.0, 1490.0, _KOCH_CUE),
        ]
        match = locate_passage(cues, _KOCH_PASSAGE)
        assert match is not None
        assert match.start == 1462.0
        assert match.confidence >= 0.5

    def test_returns_none_when_no_cue_is_close(self):
        cues = [
            Cue(1, 0.0, 3.0, "Welcome to Wonder Cabinet."),
            Cue(2, 10.0, 14.0, "Completely unrelated chatter about the weather today."),
        ]
        match = locate_passage(cues, _KOCH_PASSAGE)
        assert match is None

    def test_picks_best_of_several_cues(self):
        cues = [
            Cue(1, 5.0, 8.0, "William James was a person, broadly speaking."),
            Cue(2, 1462.0, 1490.0, _KOCH_CUE),
        ]
        match = locate_passage(cues, _KOCH_PASSAGE)
        assert match.start == 1462.0


class TestParseSrt:
    def test_parses_cues_and_strips_speaker_labels(self):
        srt = (
            "1\n"
            "00:00:00,547 --> 00:00:01,927\n"
            "[SPEAKER_00]: Welcome to Wonder Cabinet.\n"
            "\n"
            "2\n"
            "00:01:05,000 --> 00:01:08,500\n"
            "[SPEAKER_01]: And I'm Steve Paulson.\n"
        )
        cues = parse_srt(srt)
        assert cues == [
            Cue(index=1, start=0.547, end=1.927, text="Welcome to Wonder Cabinet."),
            Cue(index=2, start=65.0, end=68.5, text="And I'm Steve Paulson."),
        ]

    def test_joins_multiline_cue_text(self):
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "[SPEAKER_00]: First line\n"
            "second line\n"
        )
        cues = parse_srt(srt)
        assert cues[0].text == "First line second line"

    def test_parses_dot_decimal_separator(self):
        # Whisper/yt-dlp SRTs sometimes use a '.' millisecond separator.
        srt = (
            "1\n"
            "00:00:00.547 --> 00:00:01.927\n"
            "[SPEAKER_00]: Welcome to Wonder Cabinet.\n"
        )
        cues = parse_srt(srt)
        assert cues[0].start == 0.547
        assert cues[0].end == 1.927

    def test_malformed_timestamp_raises_readable_error(self):
        # A '-->' line with an unparseable timestamp must fail with a readable
        # ValueError, not a cryptic AttributeError from NoneType.groups().
        srt = "1\n00:00 --> 00:01\n[SPEAKER_00]: broken timing.\n"
        with pytest.raises(ValueError):
            parse_srt(srt)


class TestFormatTimestamp:
    def test_under_an_hour(self):
        assert format_timestamp(1462.0) == "24:22"

    def test_pads_seconds(self):
        assert format_timestamp(65.0) == "1:05"

    def test_over_an_hour(self):
        assert format_timestamp(3725.0) == "1:02:05"

    def test_zero_start(self):
        # A clip that starts at the very top of the audio.
        assert format_timestamp(0.0) == "0:00"


class TestExtractClipB64:
    def test_returns_empty_when_ffmpeg_fails_to_produce_a_file(self, monkeypatch, tmp_path):
        # When ffmpeg fails and writes no output file, extraction must degrade
        # to an empty data-uri, not crash the whole build_review pass with
        # FileNotFoundError on the missing clip.
        class _Failed:
            returncode = 1
            stdout = ""
            stderr = "ffmpeg: boom"

        monkeypatch.setattr(review.subprocess, "run", lambda *a, **k: _Failed())
        result = extract_clip_b64(tmp_path / "audio.mp3", 100.0)
        assert result == ""


def _entry(**kw):
    base = dict(
        episode=14, guest="Christof Koch", passage="William James wrote a book.",
        from_label="Steve Paulson", to_label="Christof Koch",
        timestamp="24:22", clip_data_uri="data:audio/mpeg;base64,AAAA",
        contested=False, confidence=None,
    )
    base.update(kw)
    return ReviewEntry(**base)


class TestRenderReviewHtml:
    def test_card_shows_passage_labels_and_timestamp(self):
        html_out = render_review_html([_entry()])
        assert "William James wrote a book." in html_out
        assert "Steve Paulson" in html_out and "Christof Koch" in html_out
        assert "24:22" in html_out
        assert "<audio" in html_out
        assert "data:audio/mpeg;base64,AAAA" in html_out

    def test_contested_badge(self):
        html_out = render_review_html([_entry(contested=True)])
        assert "CONTESTED" in html_out

    def test_missing_timestamp_shows_scrub_note(self):
        html_out = render_review_html([_entry(timestamp=None, clip_data_uri=None)])
        assert "scrub manually" in html_out
        assert "<audio" not in html_out

    def test_escapes_html_in_passage(self):
        html_out = render_review_html([_entry(passage="a < b & c")])
        assert "a &lt; b &amp; c" in html_out

    def test_low_confidence_renders_verify_warning(self):
        # confidence=0.54 is below 0.65 — must show "verify" warning
        html_out = render_review_html([_entry(confidence=0.54)])
        assert "0.54" in html_out
        assert "verify" in html_out.lower()

    def test_high_confidence_renders_score_without_verify_warning(self):
        # confidence=0.90 is at or above 0.65 — score shown, no "verify"
        html_out = render_review_html([_entry(confidence=0.90)])
        assert "0.90" in html_out
        assert "verify" not in html_out.lower()

    def test_no_confidence_renders_no_score_note(self):
        # confidence=None — no score note at all
        html_out = render_review_html([_entry(confidence=None)])
        assert "match" not in html_out.lower()
