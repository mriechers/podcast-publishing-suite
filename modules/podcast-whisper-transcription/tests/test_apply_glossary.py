"""Tests for apply_glossary.py.

Focus: the tool must never report work it did not do. An identity rule
(key == value) matches the text but rewrites nothing, and counting it made
`apply_glossary.py` print phantom replacements for files it left untouched --
which in turn inflated the "files changed" tally and made the step's output
useless as a signal once it was wired into the transcription pipeline.
"""

import sys
from pathlib import Path

# Add scripts/ to path so we can import apply_glossary
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from apply_glossary import apply_corrections, process_file


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


class TestIdentityRules:
    """A rule whose key equals its value is a no-op and must not be counted."""

    def test_identity_rule_not_counted(self):
        text = "Wonder Cabinet is based in Vershire, Vermont."
        new_text, counts = apply_corrections(text, {"Vershire": "Vershire"})

        assert new_text == text
        assert counts == {}

    def test_identity_rule_writes_no_file_and_no_backup(self, tmp_path):
        text = "Wonder Cabinet is based in Vershire, Vermont."
        p = _write(tmp_path, "captions.srt", text)
        before = p.stat().st_mtime_ns

        counts = process_file(
            p, {"Vershire": "Vershire"}, backup=True, skip_html_comments=False
        )

        assert counts == {}
        assert p.read_text() == text
        assert p.stat().st_mtime_ns == before
        assert not (tmp_path / "captions.srt.original").exists()

    def test_identity_rule_mixed_with_real_rule(self, tmp_path):
        """The real correction is reported; the identity rule alongside it is not."""
        p = _write(tmp_path, "captions.srt", "Versher, Vermont and Vershire, Vermont")

        counts = process_file(
            p,
            {"Versher": "Vershire", "Vershire": "Vershire"},
            backup=True,
            skip_html_comments=False,
        )

        assert counts == {"Versher": 1}
        assert "Versher," not in p.read_text()

    def test_case_only_correction_is_counted(self):
        """A case-only fix isn't an identity rule and must still be applied and counted.

        Guards against a future "compare case-insensitively" tweak to the
        identity skip silently swallowing real corrections like this one.
        """
        text = "we visited vershire last spring"
        new_text, counts = apply_corrections(text, {"vershire": "Vershire"})

        assert new_text == "we visited Vershire last spring"
        assert counts == {"vershire": 1}


class TestIdempotence:
    """Re-running on corrected text must be a true no-op, including in the report."""

    def test_second_pass_reports_zero(self, tmp_path):
        corrections = {"Gottscher": "Steve Gotcher", "Versher": "Vershire"}
        p = _write(tmp_path, "captions.srt", "engineer Gottscher in Versher, Vermont")

        first = process_file(p, corrections, backup=True, skip_html_comments=False)
        second = process_file(p, corrections, backup=True, skip_html_comments=False)

        assert first == {"Gottscher": 1, "Versher": 1}
        assert second == {}

    def test_real_correction_counted_and_backed_up(self, tmp_path):
        original = "based in Versher, Vermont"
        p = _write(tmp_path, "captions.srt", original)

        counts = process_file(
            p, {"Versher": "Vershire"}, backup=True, skip_html_comments=False
        )

        assert counts == {"Versher": 1}
        assert p.read_text() == "based in Vershire, Vermont"
        assert (tmp_path / "captions.srt.original").read_text() == original

    def test_backup_holds_pristine_text_after_second_correction(self, tmp_path):
        """`.original` must keep the pre-first-correction state, not the prior run's."""
        original = "Gottscher in Versher"
        p = _write(tmp_path, "captions.srt", original)
        backup = tmp_path / "captions.srt.original"

        process_file(p, {"Versher": "Vershire"}, backup=True, skip_html_comments=False)
        process_file(
            p, {"Gottscher": "Steve Gotcher"}, backup=True, skip_html_comments=False
        )

        assert backup.read_text() == original
        assert p.read_text() == "Steve Gotcher in Vershire"


class TestHtmlCommentMasking:
    """REVIEW NOTES blocks quote misrenders as examples and must survive."""

    def test_skip_html_comments_preserves_review_notes(self, tmp_path):
        note = '<!-- REVIEW NOTES:\n- Corrected "Strangchamps" to "Strainchamps".\n-->'
        body = "\n\n**Strangchamps:**\nHello."
        p = _write(tmp_path, "formatted_transcript.md", note + body)

        counts = process_file(
            p,
            {"Strangchamps": "Strainchamps"},
            backup=True,
            skip_html_comments=True,
        )

        result = p.read_text()
        assert note in result, "the review-notes block must be left byte-identical"
        assert "**Strainchamps:**" in result, "body text must still be corrected"
        assert counts == {"Strangchamps": 1}

    def test_without_flag_the_comment_is_rewritten(self, tmp_path):
        """Guard the contrast: this is exactly why --skip-html-comments exists."""
        note = '<!-- Corrected "Strangchamps" to "Strainchamps". -->'
        p = _write(tmp_path, "formatted_transcript.md", note)

        process_file(
            p, {"Strangchamps": "Strainchamps"}, backup=True, skip_html_comments=False
        )

        assert "Strangchamps" not in p.read_text()


class TestBoundaryBehavior:
    """Regression guards for the two documented regex traps."""

    def test_longer_keys_win(self, tmp_path):
        """Compound rules fire before bare-token rules, avoiding doubled names."""
        new_text, _ = apply_corrections(
            "thanks to Mark Rickers",
            {"Rickers": "Mark Riechers", "Mark Rickers": "Mark Riechers"},
        )

        assert new_text == "thanks to Mark Riechers"

    def test_trailing_punctuation_matches(self):
        new_text, counts = apply_corrections(
            "He described the experience.", {"experience.": "encounter."}
        )

        assert new_text == "He described the encounter."
        assert counts == {"experience.": 1}

    def test_no_match_inside_longer_word(self):
        """Lookarounds must not fire on a substring of a larger token."""
        new_text, counts = apply_corrections("Vershireshire", {"Vershire": "Corrected"})

        assert new_text == "Vershireshire"
        assert counts == {}
