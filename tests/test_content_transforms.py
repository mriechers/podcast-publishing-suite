"""Tests for content_transforms.py — stripping rules."""

from __future__ import annotations

import re

from src.content_transforms import (
    WC_CHAPTERS_BLOCK,
    WC_EMDASH_DIVIDER,
    WC_SHORT_TIMESTAMP_PARAGRAPHS,
    WC_TIMESTAMP_PARAGRAPHS,
    _wrap_bare_link_paragraphs,
)


class TestChapterTimestampStripping:
    """Verify timestamp patterns match real PRX feed output after nh3."""

    def test_chapters_block_with_br_tags(self):
        html = (
            '<p>Chapters:</p>\n'
            '<p>00:00:00 Introduction<br>00:04:34 The Forest<br>00:15:20 Conclusion</p>'
        )
        assert re.search(WC_CHAPTERS_BLOCK, html, re.DOTALL)

    def test_chapters_block_with_newlines_between(self):
        html = (
            '<p>Chapters:</p>\n\n'
            '<p>00:00:00 Introduction<br>\n00:04:34 The Forest<br>\n00:15:20 Conclusion</p>'
        )
        assert re.search(WC_CHAPTERS_BLOCK, html, re.DOTALL)

    def test_chapters_block_without_colon(self):
        html = '<p>Chapters</p>\n<p>00:00:00 Introduction<br>00:04:34 The Forest</p>'
        assert re.search(WC_CHAPTERS_BLOCK, html, re.DOTALL)

    def test_individual_timestamp_paragraphs(self):
        html = '<p>00:00:00 Introduction</p>\n<p>00:04:34 The Forest</p>\n<p>00:15:20 Conclusion</p>'
        assert re.search(WC_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)

    def test_short_timestamp_paragraphs_with_emdash(self):
        html = '<p>0:00 — Introduction</p>\n<p>4:34 — The Forest</p>\n<p>15:20 — Conclusion</p>'
        assert re.search(WC_SHORT_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)

    def test_short_timestamp_with_hyphen(self):
        html = '<p>0:00 - Introduction</p>\n<p>4:34 - The Forest</p>'
        assert re.search(WC_SHORT_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)

    def test_single_timestamp_paragraph_not_matched(self):
        html = '<p>00:00:00 Introduction</p>'
        assert not re.search(WC_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)


class TestEmdashStripping:
    """Verify emdash divider pattern matches all PRX variants."""

    def test_single_emdash(self):
        assert re.search(WC_EMDASH_DIVIDER, '<p>—</p>')

    def test_double_emdash(self):
        assert re.search(WC_EMDASH_DIVIDER, '<p>——</p>')

    def test_emdash_with_nbsp(self):
        assert re.search(WC_EMDASH_DIVIDER, '<p>\u00a0—\u00a0</p>')

    def test_emdash_with_whitespace(self):
        assert re.search(WC_EMDASH_DIVIDER, '<p>  —  </p>')

    def test_emdash_does_not_match_text(self):
        assert not re.search(WC_EMDASH_DIVIDER, '<p>This — that</p>')

    def test_endash_standalone(self):
        # En dash (U+2013) on its own — appears between body and timestamps in WC feeds
        assert re.search(WC_EMDASH_DIVIDER, '<p>–</p>')

    def test_strong_wrapped_endash(self):
        # Real-world failure: WC E13 (Sharon Blackie, May 2026) had <p><strong>–</strong></p>
        # between body text and Links list, which slipped past the original regex.
        assert re.search(WC_EMDASH_DIVIDER, '<p><strong>–</strong></p>')

    def test_em_wrapped_emdash(self):
        assert re.search(WC_EMDASH_DIVIDER, '<p><em>—</em></p>')

    def test_strong_wrapped_emdash_with_padding(self):
        assert re.search(WC_EMDASH_DIVIDER, '<p><strong> — </strong></p>')

    def test_p_with_attributes(self):
        # Editor-injected attributes like dir="ltr" should not block the match
        assert re.search(WC_EMDASH_DIVIDER, '<p dir="ltr">—</p>')
        assert re.search(WC_EMDASH_DIVIDER, '<p class="x">—</p>')

    def test_emdash_with_nbsp_entity_padding(self):
        # Real-world failure: WC E14 (Christof Koch, May 2026) had <p>—&nbsp;</p>
        # before the chapter block. The literal NBSP in the regex didn't catch
        # the &nbsp; HTML entity form, so this divider survived the strip pass.
        assert re.search(WC_EMDASH_DIVIDER, '<p>—&nbsp;</p>')
        assert re.search(WC_EMDASH_DIVIDER, '<p>&nbsp;<em>—</em>&nbsp;</p>')


class TestBareLinkParagraphWrapping:
    """Tests for _wrap_bare_link_paragraphs."""

    def test_wraps_run_of_bare_link_paragraphs(self):
        html = (
            '<p><a href="https://a.com/">A</a></p>'
            '<p><a href="https://b.com/">B</a></p>'
            '<p><a href="https://c.com/">C</a></p>'
        )
        out = _wrap_bare_link_paragraphs(html)
        assert '<ul class="wc-episode-notes-content-links">' in out
        assert '<li><a href="https://a.com/"' in out
        assert '<li><a href="https://c.com/"' in out

    def test_leaves_solo_link_paragraph_alone(self):
        html = '<p><a href="https://only.com/">Solo</a></p>'
        assert _wrap_bare_link_paragraphs(html) == html

    def test_handles_strong_wrapped_link_text(self):
        # WC E14 pattern: <p><a><strong>Label</strong></a></p>
        html = (
            '<p><a href="https://a.com/"><strong>Personal website</strong></a></p>'
            '<p><a href="https://b.com/"><strong>Allen Institute</strong></a></p>'
        )
        out = _wrap_bare_link_paragraphs(html)
        assert '<li><a href="https://a.com/" target="_blank" rel="noopener noreferrer">Personal website</a></li>' in out
        assert '<li><a href="https://b.com/" target="_blank" rel="noopener noreferrer">Allen Institute</a></li>' in out

    def test_combines_label_prefix_with_link_text(self):
        # WC E14 had: <p>TTBOOK: "<a><strong>Your Brain on Shrooms</strong></a>"&nbsp;</p>
        html = (
            '<p><a href="https://a.com/"><strong>First</strong></a></p>'
            '<p>TTBOOK: "<a href="https://b.com/"><strong>Your Brain on Shrooms</strong></a>"&nbsp;</p>'
        )
        out = _wrap_bare_link_paragraphs(html)
        assert '<li><a href="https://b.com/" target="_blank" rel="noopener noreferrer">TTBOOK: Your Brain on Shrooms</a></li>' in out

    def test_does_not_wrap_mid_prose_links(self):
        # Two prose paragraphs each containing an inline link must NOT be wrapped.
        # Suffix has word characters ("in it.") — the classifier must reject.
        html = (
            '<p>Some prose with <a href="https://a.com/">link a</a> in it.</p>'
            '<p>Other prose with <a href="https://b.com/">link b</a> in it.</p>'
        )
        out = _wrap_bare_link_paragraphs(html)
        assert '<ul class="wc-episode-notes-content-links">' not in out
        assert out == html

    def test_does_not_wrap_run_broken_by_non_link_paragraph(self):
        html = (
            '<p><a href="https://a.com/">A</a></p>'
            '<p>Description paragraph between</p>'
            '<p><a href="https://b.com/">B</a></p>'
        )
        out = _wrap_bare_link_paragraphs(html)
        assert '<ul class="wc-episode-notes-content-links">' not in out
