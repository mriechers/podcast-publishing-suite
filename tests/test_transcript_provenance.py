"""Tests for transcript_provenance.py — the pre-publish gate that confirms
the transcript being published reflects the producer's speaker-label edits.

Pure logic only (parse + diff). The Drive-fetch path is thin I/O and not
exercised here.
"""

from __future__ import annotations

import pytest

from src.transcript_provenance import (
    Divergence,
    TranscriptProvenanceError,
    find_speaker_divergences,
    gate_published_transcript,
    parse_speaker_turns,
    producer_doc_id_from_manifest,
    verify_against_producer,
)


def _boom(_doc_id):  # a fetcher that must never be called
    raise AssertionError("fetcher should not have been called")


class TestParseSpeakerTurns:
    def test_parses_inline_markdown_bold(self):
        text = "**Anne Strainchamps:** Welcome to Wonder Cabinet.\n**Steve Paulson:** And I'm Steve."
        turns = parse_speaker_turns(text)
        assert turns == [
            ("Anne Strainchamps", "Welcome to Wonder Cabinet."),
            ("Steve Paulson", "And I'm Steve."),
        ]

    def test_parses_own_line_bold_then_body(self):
        text = "**Anne Strainchamps:**\nWelcome to Wonder Cabinet."
        assert parse_speaker_turns(text) == [("Anne Strainchamps", "Welcome to Wonder Cabinet.")]

    def test_parses_plain_colon_form(self):
        # Producer docx exports as "Name: text"
        text = "Anne Strainchamps: Welcome.\nRenee Bergland: Thanks for having me."
        assert parse_speaker_turns(text) == [
            ("Anne Strainchamps", "Welcome."),
            ("Renee Bergland", "Thanks for having me."),
        ]

    def test_ignores_frontmatter_and_non_speaker_lines(self):
        text = "# Formatted Transcript\n\nDuration: 00:40:00\n\n**Anne Strainchamps:** Hello there everyone."
        assert parse_speaker_turns(text) == [("Anne Strainchamps", "Hello there everyone.")]


class TestFindSpeakerDivergences:
    def test_no_divergence_when_labels_match(self):
        local = "**Anne Strainchamps:** Welcome to the show, it is a delight to have you here today."
        producer = "Anne Strainchamps: Welcome to the show, it is a delight to have you here today."
        assert find_speaker_divergences(local, producer) == []

    def test_last_name_equivalence_is_not_a_divergence(self):
        local = "**Strainchamps:** Welcome to the show, it is a delight to have you here today."
        producer = "Anne Strainchamps: Welcome to the show, it is a delight to have you here today."
        assert find_speaker_divergences(local, producer) == []

    def test_first_name_equivalence_is_not_a_divergence(self):
        local = "**Anne:** Welcome to the show, it is a delight to have you here today."
        producer = "Anne Strainchamps: Welcome to the show, it is a delight to have you here today."
        assert find_speaker_divergences(local, producer) == []

    def test_detects_host_guest_flip(self):
        local = "**Steve Paulson:** I don't think I'm much different from anyone else, it depends on the setting."
        producer = "Christof Koch: I don't think I'm much different from anyone else, it depends on the setting."
        divs = find_speaker_divergences(local, producer)
        assert len(divs) == 1
        assert divs[0].local_label == "Steve Paulson"
        assert divs[0].producer_label == "Christof Koch"

    def test_spelling_only_edit_same_speaker_is_not_a_divergence(self):
        # Producer fixed a spelling ("McFarlane"->"Macfarlane") but speaker unchanged.
        local = "**Steve Paulson:** This is Robert McFarlane, a celebrated nature writer and explorer."
        producer = "Steve Paulson: This is Robert Macfarlane, a celebrated nature writer and explorer."
        assert find_speaker_divergences(local, producer) == []

    def test_unaligned_turn_does_not_produce_false_divergence(self):
        # A turn only present in the producer doc shouldn't be reported.
        local = "**Anne Strainchamps:** Welcome to the show, so glad you could join us this afternoon."
        producer = (
            "Anne Strainchamps: Welcome to the show, so glad you could join us this afternoon.\n"
            "Renee Bergland: An entirely different sentence that has no match in the local file at all."
        )
        assert find_speaker_divergences(local, producer) == []


class TestVerifyAgainstProducer:
    def test_passes_silently_when_clean(self):
        local = "**Anne Strainchamps:** Welcome to the show, it is a delight to have you here today."
        producer = "Anne Strainchamps: Welcome to the show, it is a delight to have you here today."
        # returns the count of aligned turns; does not raise
        assert verify_against_producer(local, producer) >= 1

    def test_raises_hard_block_on_divergence(self):
        local = "**Steve Paulson:** I don't think I'm much different from anyone else, it depends on the setting."
        producer = "Christof Koch: I don't think I'm much different from anyone else, it depends on the setting."
        with pytest.raises(TranscriptProvenanceError) as exc:
            verify_against_producer(local, producer)
        assert len(exc.value.divergences) == 1
        assert isinstance(exc.value.divergences[0], Divergence)
        # The error message should be actionable (mention the fix command).
        assert "wc-transcript-update" in str(exc.value)


class TestGatePublishedTranscript:
    """The thin glue the publish loop calls: fetch producer doc (injectable),
    then verify. Skips cleanly when there's nothing to check."""

    def test_skips_when_no_doc_id(self):
        assert gate_published_transcript("**Anne:** anything at all here", None, fetcher=_boom) is None

    def test_skips_when_no_transcript(self):
        assert gate_published_transcript(None, "doc-id", fetcher=_boom) is None
        assert gate_published_transcript("", "doc-id", fetcher=_boom) is None

    def test_raises_on_divergence(self):
        local = "**Steve Paulson:** I don't think I'm much different from anyone else, it depends on the setting."
        fetcher = lambda _id: "Christof Koch: I don't think I'm much different from anyone else, it depends on the setting."
        with pytest.raises(TranscriptProvenanceError):
            gate_published_transcript(local, "doc-id", fetcher=fetcher)

    def test_passes_clean_and_returns_aligned_count(self):
        local = "**Anne Strainchamps:** Welcome to the show, delighted to have you here with us today."
        fetcher = lambda _id: "Anne Strainchamps: Welcome to the show, delighted to have you here with us today."
        assert gate_published_transcript(local, "doc-id", fetcher=fetcher) >= 1


class TestProducerDocIdFromManifest:
    def test_reads_edit_transcript_id(self):
        m = {"google_drive": {"uploads": {"edit_transcript": {"id": "abc123"}}}}
        assert producer_doc_id_from_manifest(m) == "abc123"

    def test_returns_none_when_absent(self):
        assert producer_doc_id_from_manifest({}) is None
        assert producer_doc_id_from_manifest({"google_drive": {"uploads": {}}}) is None
        assert producer_doc_id_from_manifest({"google_drive": {"uploads": {"edit_transcript": {}}}}) is None
