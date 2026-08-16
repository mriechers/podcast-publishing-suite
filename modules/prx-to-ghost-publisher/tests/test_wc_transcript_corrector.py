"""Tests for wc_transcript_corrector.py — the surgical speaker-label patcher
that backfills producer-caught corrections onto live WC Ghost transcripts.

Pure logic only (parse + targeted label swap + diff). The Ghost GET/PUT path is
thin I/O and not exercised here.

The patcher operates on the published transcript HTML, which the WC publisher
renders as markdown -> ``<p><strong>Speaker Name:</strong> dialogue…</p>``
paragraphs inside ``<div id="episode-transcript" class="episode-transcript">``.
"""

from __future__ import annotations

from src.wc_transcript_corrector import (
    LabelCorrection,
    apply_label_corrections,
    corrections_from_manifest,
)


# A small but realistic transcript HTML body (markdown-rendered), matching what
# content_builder.format_transcript_html + build_transcript_section_html emit.
TRANSCRIPT_HTML = (
    '<div id="episode-transcript" class="episode-transcript">\n'
    "<h2>Transcript</h2>\n"
    "<p><strong>Anne Strainchamps:</strong> Welcome to Wonder Cabinet, "
    "I'm Anne Strainchamps.</p>\n"
    "<p><strong>Steve Paulson:</strong> William James, one of the great writers, "
    "the father of American psychology, wrote a beautiful book in 1902.</p>\n"
    "<p><strong>Anne Strainchamps:</strong> So I find your story absolutely "
    "fascinating, and my little armchair psychoanalysis here.</p>\n"
    "</div>"
)


class TestApplyLabelCorrections:
    def test_applies_host_to_guest_swap_on_matched_passage(self):
        corrections = [
            LabelCorrection(
                passage="William James, one of the great writers, the father of "
                "American psychology, wrote a beautiful book in 1902.",
                from_label="Steve Paulson",
                to_label="Christof Koch",
            )
        ]
        new_html, results = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        assert results[0].status == "applied"
        assert "<p><strong>Christof Koch:</strong> William James" in new_html
        # The wrong label is gone from that passage.
        assert "<strong>Steve Paulson:</strong> William James" not in new_html

    def test_leaves_other_paragraphs_byte_identical(self):
        corrections = [
            LabelCorrection(
                passage="William James, one of the great writers, the father of "
                "American psychology, wrote a beautiful book in 1902.",
                from_label="Steve Paulson",
                to_label="Christof Koch",
            )
        ]
        new_html, _ = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        # Both Anne paragraphs and the wrapper survive untouched.
        assert (
            "<p><strong>Anne Strainchamps:</strong> Welcome to Wonder Cabinet, "
            "I'm Anne Strainchamps.</p>" in new_html
        )
        assert (
            "<p><strong>Anne Strainchamps:</strong> So I find your story absolutely "
            "fascinating, and my little armchair psychoanalysis here.</p>" in new_html
        )
        assert '<div id="episode-transcript" class="episode-transcript">' in new_html
        # Exactly one label token changed, everything else identical.
        assert new_html == TRANSCRIPT_HTML.replace(
            "<strong>Steve Paulson:</strong> William James",
            "<strong>Christof Koch:</strong> William James",
        )

    def test_already_correct_is_noop(self):
        corrections = [
            LabelCorrection(
                passage="William James, one of the great writers, the father of "
                "American psychology, wrote a beautiful book in 1902.",
                from_label="Anne Strainchamps",  # producer says it's already Steve
                to_label="Steve Paulson",
            )
        ]
        new_html, results = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        assert results[0].status == "already-correct"
        assert new_html == TRANSCRIPT_HTML  # untouched

    def test_label_mismatch_refuses_to_patch(self):
        # The passage exists, but its current label is neither from nor to.
        # That means our assumption about the live page is stale — do NOT touch.
        corrections = [
            LabelCorrection(
                passage="William James, one of the great writers, the father of "
                "American psychology, wrote a beautiful book in 1902.",
                from_label="Renee Bergland",
                to_label="David Haskell",
            )
        ]
        new_html, results = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        assert results[0].status == "label-mismatch"
        assert results[0].found_label == "Steve Paulson"
        assert new_html == TRANSCRIPT_HTML  # untouched

    def test_passage_not_found(self):
        corrections = [
            LabelCorrection(
                passage="This sentence appears nowhere in the published transcript.",
                from_label="Steve Paulson",
                to_label="Christof Koch",
            )
        ]
        new_html, results = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        assert results[0].status == "passage-not-found"
        assert new_html == TRANSCRIPT_HTML  # untouched

    def test_matching_tolerates_smart_quotes_and_entities(self):
        # Live HTML often carries &amp; / smart quotes that the manifest passage
        # (plain text) does not. The match must still land.
        html = (
            '<div id="episode-transcript" class="episode-transcript">\n'
            "<h2>Transcript</h2>\n"
            "<p><strong>Steve Paulson:</strong> It’s an act of unearned grace "
            "that I don’t feel responsible for.</p>\n"
            "</div>"
        )
        corrections = [
            LabelCorrection(
                passage="It's an act of unearned grace that I don't feel "
                "responsible for.",
                from_label="Steve Paulson",
                to_label="Christof Koch",
            )
        ]
        new_html, results = apply_label_corrections(html, corrections)

        assert results[0].status == "applied"
        assert "<strong>Christof Koch:</strong>" in new_html

    def test_speaker_equiv_first_name_matches_full_name(self):
        # Producer docs sometimes use first names ("Steve"); web uses full.
        corrections = [
            LabelCorrection(
                passage="William James, one of the great writers, the father of "
                "American psychology, wrote a beautiful book in 1902.",
                from_label="Steve",
                to_label="Christof Koch",
            )
        ]
        new_html, results = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        assert results[0].status == "applied"
        assert "<strong>Christof Koch:</strong>" in new_html

    def test_multiple_corrections_applied_independently(self):
        corrections = [
            LabelCorrection(
                passage="William James, one of the great writers, the father of "
                "American psychology, wrote a beautiful book in 1902.",
                from_label="Steve Paulson",
                to_label="Christof Koch",
            ),
            LabelCorrection(
                passage="So I find your story absolutely fascinating, and my little "
                "armchair psychoanalysis here.",
                from_label="Anne Strainchamps",
                to_label="Steve Paulson",
            ),
        ]
        new_html, results = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        assert [r.status for r in results] == ["applied", "applied"]
        assert "<p><strong>Christof Koch:</strong> William James" in new_html
        assert (
            "<p><strong>Steve Paulson:</strong> So I find your story" in new_html
        )
        # The first (Welcome) paragraph is still Anne.
        assert (
            "<p><strong>Anne Strainchamps:</strong> Welcome to Wonder Cabinet"
            in new_html
        )

    def test_duplicate_passage_key_is_not_falsely_reported_applied(self):
        # Two corrections whose passages normalize to the SAME paragraph key.
        # The first consumes the paragraph; the second's replace silently
        # no-ops (the original paragraph is already gone from result_html), so
        # it must NOT be reported as "applied" — that would tell the producer a
        # label was fixed when the HTML never changed.
        passage = (
            "William James, one of the great writers, the father of "
            "American psychology, wrote a beautiful book in 1902."
        )
        corrections = [
            LabelCorrection(passage=passage, from_label="Steve Paulson", to_label="Christof Koch"),
            LabelCorrection(passage=passage, from_label="Steve Paulson", to_label="Anne Strainchamps"),
        ]
        new_html, results = apply_label_corrections(TRANSCRIPT_HTML, corrections)

        assert results[0].status == "applied"
        assert results[1].status != "applied"
        # The paragraph was corrected exactly once, to the first label.
        assert "<p><strong>Christof Koch:</strong> William James" in new_html
        assert "Anne Strainchamps:</strong> William James" not in new_html


class TestCorrectionsFromManifest:
    def test_maps_manifest_fields(self):
        manifest = {
            "slug": "christof-koch-on-the-cosmic-toad",
            "corrections": [
                {
                    "passage": "Some distinctive passage of dialogue here.",
                    "current_web_label": "Steve Paulson",
                    "correct_label": "Christof Koch",
                    "type": "host/guest",
                    "authority": "producer-edited Drive doc",
                }
            ],
        }
        corrections = corrections_from_manifest(manifest)
        assert corrections == [
            LabelCorrection(
                passage="Some distinctive passage of dialogue here.",
                from_label="Steve Paulson",
                to_label="Christof Koch",
            )
        ]

    def test_empty_manifest_yields_no_corrections(self):
        assert corrections_from_manifest({"corrections": []}) == []
