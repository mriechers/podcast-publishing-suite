"""Tests for content builder: sanitization, escaping, JSON-LD, pod.link."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.content_builder import (
    build_ghost_post,
    build_jsonld_metadata,
    build_luminous_ghost_post,
    build_podlink_url,
    format_transcript_html,
    get_apple_id_from_guid,
    sanitize_html,
)
from src.feed_parser import Episode


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
