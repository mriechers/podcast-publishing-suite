"""Tests for content_transforms.py — stripping rules."""

from __future__ import annotations

import re

from src.content_transforms import (
    WC_CHAPTERS_BLOCK,
    WC_EMDASH_DIVIDER,
    WC_SHORT_TIMESTAMP_PARAGRAPHS,
    WC_TIMESTAMP_PARAGRAPHS,
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
