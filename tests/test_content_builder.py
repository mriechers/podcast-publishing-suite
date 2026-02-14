"""Tests for content builder: sanitization, escaping, JSON-LD, pod.link, RSS transcripts."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.content_builder import (
    build_ghost_post,
    build_jsonld_metadata,
    build_luminous_ghost_post,
    build_podlink_url,
    build_transcript_section_html,
    format_episode_links,
    format_rss_transcript_html,
    format_transcript_html,
    get_apple_id_from_guid,
    sanitize_html,
)
from src.feed_parser import Episode


class TestEpisodeLinksFormatting:
    """Validate episode links are formatted with proper CSS class for WC-Episode theme."""

    def test_adds_css_class_to_ul(self):
        """Links list should get wc-episode-notes-content-links class."""
        html = '<ul><li><a href="https://example.com">Link</a></li></ul>'
        result = format_episode_links(html)
        assert 'class="wc-episode-notes-content-links"' in result

    def test_adds_target_blank_to_links(self):
        """Links should open in new tab."""
        html = '<ul><li><a href="https://example.com">Link</a></li></ul>'
        result = format_episode_links(html)
        assert 'target="_blank"' in result
        assert 'rel="noopener noreferrer"' in result

    def test_wraps_in_ghost_html_card_markers(self):
        """Links list should be wrapped in Ghost HTML card markers."""
        html = '<ul><li><a href="https://example.com">Link</a></li></ul>'
        result = format_episode_links(html)
        assert '<!--kg-card-begin: html-->' in result
        assert '<!--kg-card-end: html-->' in result

    def test_extracts_descriptive_text_from_prx_format(self):
        """PRX format 'Description: <a>URL</a>' should become '<a>Description</a>'."""
        html = '''<ul>
<li>Deep Time: <a href="https://example.com"><strong>https://example.com</strong></a></li>
</ul>'''
        result = format_episode_links(html)
        assert '>Deep Time</a>' in result
        assert 'https://example.com</strong>' not in result

    def test_preserves_link_text_when_inside_anchor(self):
        """Format '<a>Link text</a>' should preserve the link text."""
        html = '<ul><li><a href="https://example.com">Sophie Strand\'s website</a></li></ul>'
        result = format_episode_links(html)
        assert ">Sophie Strand's website</a>" in result

    def test_preserves_non_link_lists(self):
        """Plain lists without links should not be modified."""
        html = '<ul><li>Item one</li><li>Item two</li></ul>'
        result = format_episode_links(html)
        assert 'wc-episode-notes-content-links' not in result
        assert result == html

    def test_preserves_surrounding_content(self):
        """Content before and after the links list should be preserved."""
        html = '<p>Before</p><ul><li><a href="https://x.com">Link</a></li></ul><p>After</p>'
        result = format_episode_links(html)
        assert '<p>Before</p>' in result
        assert '<p>After</p>' in result


class TestHTMLSanitization:
    """Validate RSS content sanitization strips dangerous tags (Phase 2.1)."""

    def test_script_tags_stripped(self):
        """<script> tags must be completely removed."""
        html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        result = sanitize_html(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "<p>Hello</p>" in result
        assert "<p>World</p>" in result

    def test_safe_tags_preserved(self):
        """Standard formatting tags should survive sanitization."""
        html = '<p>A <strong>bold</strong> and <em>italic</em> paragraph.</p>'
        result = sanitize_html(html)
        assert "<strong>" in result
        assert "<em>" in result
        assert "<p>" in result

    def test_links_preserved_with_href(self):
        """<a> tags with href should be preserved."""
        html = '<a href="https://example.com">Link</a>'
        result = sanitize_html(html)
        assert 'href="https://example.com"' in result
        assert ">Link</a>" in result

    def test_event_handlers_stripped(self):
        """Event handler attributes like onclick must be stripped."""
        html = '<p onclick="alert(1)">Click me</p>'
        result = sanitize_html(html)
        assert "onclick" not in result
        assert "<p>" in result

    def test_iframe_stripped(self):
        """<iframe> tags should be removed."""
        html = '<iframe src="https://evil.com"></iframe><p>After</p>'
        result = sanitize_html(html)
        assert "<iframe" not in result
        assert "<p>After</p>" in result

    def test_style_tags_stripped(self):
        """<style> tags should be removed."""
        html = '<style>body{display:none}</style><p>Visible</p>'
        result = sanitize_html(html)
        assert "<style>" not in result
        assert "<p>Visible</p>" in result

    def test_lists_preserved(self):
        """<ul>/<ol>/<li> should be preserved."""
        html = '<ul><li>Item 1</li><li>Item 2</li></ul>'
        result = sanitize_html(html)
        assert "<ul>" in result
        assert "<li>" in result


class TestTranscriptHTMLEscaping:
    """Validate transcript text is properly escaped (Phase 2.2)."""

    def test_speaker_name_escaped(self):
        """Speaker names with special chars should be escaped."""
        transcript = '- [Speaker <script>] Some text here'
        result = format_transcript_html(transcript)
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_content_text_escaped(self):
        """Content text with HTML entities should be escaped."""
        transcript = '- [Steve] This has <b>bold</b> & "quotes"'
        result = format_transcript_html(transcript)
        assert "&lt;b&gt;" in result
        assert "&amp;" in result
        assert "&quot;" not in result or "&#x27;" not in result  # html.escape default

    def test_plain_text_escaped(self):
        """Non-speaker lines should also be escaped."""
        transcript = 'Some line with <img src=x onerror=alert(1)>'
        result = format_transcript_html(transcript)
        assert "&lt;img" in result
        assert "onerror" not in result or "&lt;" in result


class TestJSONLD:
    """Validate JSON-LD structured data output."""

    def test_valid_json_output(self, sample_episode: Episode):
        """JSON-LD output should be valid JSON within a script tag."""
        jsonld = build_jsonld_metadata(sample_episode, show_name="Test Show")
        assert jsonld.startswith('<script type="application/ld+json">')
        assert jsonld.endswith("</script>")

        # Extract and parse the JSON
        json_str = jsonld.replace('<script type="application/ld+json">\n', "").replace(
            "\n</script>", ""
        )
        data = json.loads(json_str)
        assert data["@type"] == "PodcastEpisode"
        assert data["name"] == sample_episode.title

    def test_duration_parsing(self, sample_episode: Episode):
        """Duration in MM:SS format should be converted to ISO 8601."""
        sample_episode.duration = "45:30"
        jsonld = build_jsonld_metadata(sample_episode, show_name="Test")
        json_str = jsonld.replace('<script type="application/ld+json">\n', "").replace(
            "\n</script>", ""
        )
        data = json.loads(json_str)
        assert data["duration"] == "PT2730S"  # 45*60 + 30 = 2730


class TestPodLink:
    """Validate pod.link URL encoding."""

    def test_apple_id_lookup(self):
        """GUIDs should map to correct Apple Podcast IDs."""
        assert get_apple_id_from_guid("prx_3329_some-uuid") == "1680986776"
        assert get_apple_id_from_guid("prx_120_some-uuid") == "471896367"
        assert get_apple_id_from_guid("unknown_guid") is None

    def test_podlink_url_with_apple_id(self):
        """Pod.link URL should use Apple ID when available."""
        url = build_podlink_url("prx_3329_test-guid", apple_id="1680986776")
        assert url.startswith("https://pod.link/1680986776/episode/")
        assert len(url) > len("https://pod.link/1680986776/episode/")

    def test_podlink_url_without_ids_returns_none(self):
        """Should return None when neither apple_id nor feed_url provided."""
        result = build_podlink_url("some-guid")
        assert result is None


class TestRSSTranscriptFormatting:
    """Validate RSS transcript formatting for different content types."""

    def test_html_transcript_sanitized(self):
        """text/html transcripts should be sanitized through nh3."""
        raw = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        result = format_rss_transcript_html(raw, "text/html")
        assert "<script>" not in result
        assert "<p>Hello</p>" in result
        assert "<p>World</p>" in result

    def test_plain_text_wrapped_in_paragraphs(self):
        """text/plain without speaker format should wrap paragraphs in <p> tags."""
        raw = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = format_rss_transcript_html(raw, "text/plain")
        assert "<p>First paragraph.</p>" in result
        assert "<p>Second paragraph.</p>" in result
        assert "<p>Third paragraph.</p>" in result

    def test_plain_text_with_speaker_format(self):
        """text/plain with '- [Speaker]' format should use existing transcript formatter."""
        raw = "- [Steve] Hello there.\n- [Anne] Welcome to the show."
        result = format_rss_transcript_html(raw, "text/plain")
        assert "<strong>Steve:</strong>" in result
        assert "<strong>Anne:</strong>" in result

    def test_json_transcript_segments(self):
        """application/json transcript with segments should produce speaker-attributed HTML."""
        raw = json.dumps({
            "segments": [
                {"speaker": "Steve", "body": "Hello there.", "startTime": 0.0},
                {"speaker": "Steve", "body": "Welcome to Luminous.", "startTime": 2.5},
                {"speaker": "Anne", "body": "Thanks Steve.", "startTime": 5.0},
            ]
        })
        result = format_rss_transcript_html(raw, "application/json")
        # Consecutive Steve segments should be merged
        assert result.count("<strong>Steve:</strong>") == 1
        assert "Hello there. Welcome to Luminous." in result
        assert "<strong>Anne:</strong>" in result

    def test_json_transcript_flat_array(self):
        """application/json with a bare array of segments should also work."""
        raw = json.dumps([
            {"speaker": "Host", "body": "Welcome."},
            {"speaker": "Guest", "body": "Thank you."},
        ])
        result = format_rss_transcript_html(raw, "application/json")
        assert "<strong>Host:</strong>" in result
        assert "<strong>Guest:</strong>" in result

    def test_json_transcript_invalid_json_fallback(self):
        """Invalid JSON should fall back to escaped text."""
        raw = "this is not json {"
        result = format_rss_transcript_html(raw, "application/json")
        assert "<p>" in result
        assert "this is not json" in result

    def test_empty_content_returns_empty(self):
        """Empty content should return empty string."""
        assert format_rss_transcript_html("", "text/plain") == ""
        assert format_rss_transcript_html("", "text/html") == ""
        assert format_rss_transcript_html("", "application/json") == ""

    def test_html_entities_escaped_in_plain_text(self):
        """HTML entities in plain text should be escaped."""
        raw = "This has <b>bold</b> & \"quotes\""
        result = format_rss_transcript_html(raw, "text/plain")
        assert "&lt;b&gt;" in result
        assert "&amp;" in result


class TestTranscriptSectionHTML:
    """Validate transcript section wrapper."""

    def test_section_has_correct_structure(self):
        """Transcript section should have Ghost card markers and correct IDs."""
        result = build_transcript_section_html("<p>Hello</p>")
        assert '<!--kg-card-begin: html-->' in result
        assert '<!--kg-card-end: html-->' in result
        assert 'id="episode-transcript"' in result
        assert 'class="episode-transcript"' in result
        assert '<h2>Transcript</h2>' in result
        assert '<p>Hello</p>' in result


@pytest.fixture
def sample_episode() -> Episode:
    return Episode(
        guid="prx_3329_test-guid-1",
        title="Test Episode: The Art of Testing",
        description="<p>A <strong>test</strong> description.</p>",
        subtitle="A short subtitle.",
        pub_date=datetime(2025, 9, 13, 11, 0, 0),
        link="https://www.ttbook.org/show/test-episode",
        enclosure_url="https://example.com/audio.mp3",
        enclosure_type="audio/mpeg",
        duration="45:30",
        image_url="https://example.com/image.png",
        categories=["testing", "development"],
        episode_type="full",
        author="Wisconsin Public Radio",
    )
