"""Tests for content builder: sanitization, escaping, JSON-LD, pod.link, RSS transcripts."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.content_builder import (
    build_episode_meta_html,
    build_ghost_post,
    build_jsonld_metadata,
    build_luminous_ghost_post,
    build_podlink_url,
    build_tags,
    build_transcript_section_html,
    format_episode_links,
    format_rss_transcript_html,
    format_transcript_html,
    get_apple_id_from_guid,
    load_transcript,
    load_wc_transcript,
    sanitize_html,
    _strip_transcript_metadata,
    _strip_trailing_metadata_lines,
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


class TestLoadWcTranscript:
    """Tests for load_wc_transcript file discovery."""

    def test_finds_formatted_transcript_md(self, tmp_path):
        (tmp_path / "formatted_transcript.md").write_text("**Anne:** Hello")
        result = load_wc_transcript("Test Episode", tmp_path)
        assert result == "**Anne:** Hello"

    def test_finds_plain_transcript_txt(self, tmp_path):
        (tmp_path / "transcript.txt").write_text("Hello world")
        result = load_wc_transcript("Test Episode", tmp_path)
        assert result == "Hello world"

    def test_finds_suffixed_transcript_txt(self, tmp_path):
        (tmp_path / "WC_002_Rovelli_transcript.txt").write_text("Physics is beautiful")
        result = load_wc_transcript("Carlo Rovelli: Physics", tmp_path)
        assert result == "Physics is beautiful"

    def test_prefers_formatted_over_suffixed(self, tmp_path):
        (tmp_path / "formatted_transcript.md").write_text("**Anne:** Formatted")
        (tmp_path / "WC_002_Rovelli_transcript.txt").write_text("Raw text")
        result = load_wc_transcript("Carlo Rovelli: Physics", tmp_path)
        assert result == "**Anne:** Formatted"

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = load_wc_transcript("Nobody: Nothing", tmp_path)
        assert result is None


# Realistic dialogue body shared across the trailing-metadata fixtures below,
# matching the transcript-formatter agent's speaker-label conventions.
DIALOGUE_BODY = (
    "**Anne Strainchamps:**\n"
    "Welcome to the show. Today we're talking about consciousness.\n\n"
    "**Philip Goff:**\n"
    "Thanks for having me. It's a subject I find endlessly fascinating."
)

FRONTMATTER = (
    "# Formatted Transcript\n"
    "**Project:** WC_S01_18_Philip_Goff\n"
    "**Program:** Wonder Cabinet\n"
    "**Duration:** 00:42:10\n"
    "**Date Processed:** 2026-07-30\n"
)


class TestStripTranscriptMetadata:
    """Unit tests for _strip_transcript_metadata / _strip_trailing_metadata_lines.

    Regression coverage for a production incident: a trailing
    `**Status:** corrected` line (added by a later correction pass, with no
    preceding `---` separator) rendered straight into a published Ghost post
    because the old stripping logic only handled metadata bounded by `---`
    separators — it silently no-op'd when the separator was missing.
    """

    def test_compliant_frontmatter_and_postscript_stripped(self):
        """The documented, well-formed shape: frontmatter --- body --- status."""
        text = f"{FRONTMATTER}\n---\n\n{DIALOGUE_BODY}\n\n---\n\n**Status:** ready_for_editing\n"
        result = _strip_transcript_metadata(text)
        assert result == DIALOGUE_BODY
        assert "Status" not in result
        assert "Project" not in result

    def test_trailing_status_with_no_separator_is_stripped(self):
        """The actual production bug: status appended with no `---` at all."""
        text = f"{DIALOGUE_BODY}\n\n**Status:** corrected\n"
        result = _strip_transcript_metadata(text)
        assert result == DIALOGUE_BODY
        assert "Status" not in result
        assert "corrected" not in result

    def test_frontmatter_only_no_postscript(self):
        """Single separator, frontmatter before it, no status line at all."""
        text = f"{FRONTMATTER}\n---\n\n{DIALOGUE_BODY}"
        result = _strip_transcript_metadata(text)
        assert result == DIALOGUE_BODY

    def test_no_metadata_at_all_is_unchanged(self):
        """A transcript with no frontmatter, no separators, no status line
        must survive byte-identical — dialogue is never touched."""
        result = _strip_transcript_metadata(DIALOGUE_BODY)
        assert result == DIALOGUE_BODY

    def test_multiple_trailing_metadata_lines_all_stripped(self):
        """More than one trailing metadata line (e.g. Status + a stray
        Duration correction note) should all be stripped, blank lines
        between them included."""
        text = f"{DIALOGUE_BODY}\n\n**Status:** corrected\n**Duration:** 00:42:15\n"
        result = _strip_transcript_metadata(text)
        assert result == DIALOGUE_BODY

    def test_speaker_label_never_mistaken_for_metadata(self):
        """A real speaker line must never be eaten, even one ending the
        document, even if it mentions a metadata word in the dialogue."""
        text = DIALOGUE_BODY + " We should check our status on this."
        result = _strip_transcript_metadata(text)
        assert result == text

    def test_status_line_is_last_line_no_trailing_newline(self):
        """No trailing newline after the status line — still stripped."""
        text = f"{DIALOGUE_BODY}\n\n**Status:** needs_review"
        result = _strip_transcript_metadata(text)
        assert result == DIALOGUE_BODY


class TestStripTrailingMetadataLines:
    """Direct tests for the separator-independent trailing-line stripper."""

    def test_strips_single_trailing_status_line(self):
        text = f"{DIALOGUE_BODY}\n\n**Status:** corrected"
        assert _strip_trailing_metadata_lines(text) == DIALOGUE_BODY

    def test_no_trailing_metadata_unchanged(self):
        assert _strip_trailing_metadata_lines(DIALOGUE_BODY) == DIALOGUE_BODY

    def test_stops_at_first_non_metadata_line_from_the_end(self):
        """Only a contiguous run of trailing metadata/blank lines is
        stripped — it must stop the instant it hits real content."""
        text = "**Status:** ready_for_editing\n\n" + DIALOGUE_BODY
        # The metadata here is at the START, not the end — nothing trailing
        # to strip, so this must be returned unchanged.
        assert _strip_trailing_metadata_lines(text) == text.rstrip()


class TestLoadTranscriptSanitizesOnLoad:
    """load_transcript()/load_wc_transcript() must sanitize formatted_transcript.md
    at the load boundary — the one place this happens (see content_builder
    module docstrings)."""

    def test_load_wc_transcript_strips_trailing_status_no_separator(self, tmp_path):
        """Realistic fixture: last speaker turn immediately followed by a
        stray status line with no `---` — the exact production shape."""
        (tmp_path / "formatted_transcript.md").write_text(
            f"{FRONTMATTER}\n---\n\n{DIALOGUE_BODY}\n\n**Status:** corrected\n"
        )
        result = load_wc_transcript("Philip Goff", tmp_path)
        assert result == DIALOGUE_BODY
        assert "Status" not in result
        assert "corrected" not in result

    def test_load_wc_transcript_no_status_line_dialogue_byte_identical(self, tmp_path):
        """Without any status line, dialogue must come back byte-identical."""
        (tmp_path / "formatted_transcript.md").write_text(
            f"{FRONTMATTER}\n---\n\n{DIALOGUE_BODY}"
        )
        result = load_wc_transcript("Philip Goff", tmp_path)
        assert result == DIALOGUE_BODY

    def test_load_transcript_strips_trailing_status_no_separator(self, tmp_path):
        (tmp_path / "formatted_transcript.md").write_text(
            f"{FRONTMATTER}\n---\n\n{DIALOGUE_BODY}\n\n**Status:** corrected\n"
        )
        result = load_transcript("some-slug", cache_dir=tmp_path)
        assert result == DIALOGUE_BODY

    def test_load_wc_transcript_subdir_variant_also_sanitized(self, tmp_path):
        """The guest-name subdirectory fallback path must sanitize too."""
        subdir = tmp_path / "Philip_Goff"
        subdir.mkdir()
        (subdir / "formatted_transcript.md").write_text(
            f"{FRONTMATTER}\n---\n\n{DIALOGUE_BODY}\n\n**Status:** corrected\n"
        )
        result = load_wc_transcript("Philip Goff: On Consciousness", tmp_path)
        assert result == DIALOGUE_BODY

    def test_format_transcript_html_no_longer_sees_status_line(self, tmp_path):
        """End-to-end: the HTML actually sent to Ghost has no Status text,
        matching the incident this fixes (a **Status:** line rendered as a
        <p><strong>Status:</strong> ...</p> at the bottom of a real post)."""
        (tmp_path / "formatted_transcript.md").write_text(
            f"{FRONTMATTER}\n---\n\n{DIALOGUE_BODY}\n\n**Status:** corrected\n"
        )
        transcript = load_wc_transcript("Philip Goff", tmp_path)
        html = format_transcript_html(transcript)
        assert "Status" not in html
        assert "corrected" not in html
        assert "Philip Goff" in html


class TestTtbookReferences:
    """Ensure no TTBOOK references appear in generated HTML or tags."""

    def test_episode_meta_html_no_ttbook(self):
        html = build_episode_meta_html("https://example.com/episode")
        assert "TTBOOK" not in html
        assert "ttbook" not in html.lower()

    def test_build_tags_default_not_ttbook(self, sample_episode):
        tags = build_tags(sample_episode)
        tag_names = [t["name"] for t in tags]
        assert "TTBOOK" not in tag_names


class TestPublishedAtHandling:
    """published_at should be set for past episodes, None for future."""

    @staticmethod
    def _make_episode(pub_date):
        return Episode(
            title="Test Episode", guid="test-guid",
            link="https://example.com", description="Test",
            subtitle="", enclosure_url="https://example.com/audio.mp3",
            enclosure_type="audio/mpeg", duration="30:00",
            image_url="https://example.com/img.jpg",
            pub_date=pub_date, categories=[],
        )

    def test_past_episode_gets_published_at(self):
        from datetime import timezone
        ep = self._make_episode(datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc))
        post = build_ghost_post(ep, primary_tag="Wonder Cabinet")
        assert post.published_at is not None
        assert "2025-06-15" in post.published_at

    def test_future_episode_gets_none(self):
        from datetime import timezone, timedelta
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        ep = self._make_episode(future_date)
        post = build_ghost_post(ep, primary_tag="Wonder Cabinet")
        assert post.published_at is None

    def test_non_utc_timezone_converted_correctly(self):
        """A non-UTC pub_date must be converted to UTC before formatting."""
        from datetime import timezone, timedelta
        edt = timezone(timedelta(hours=-4))
        # 14:30 EDT = 18:30 UTC
        ep = self._make_episode(datetime(2025, 7, 8, 14, 30, 0, tzinfo=edt))
        post = build_ghost_post(ep, primary_tag="Wonder Cabinet")
        assert post.published_at == "2025-07-08T18:30:00.000Z"


class TestRedundantLinksHeading:
    """A producer-typed "Links:" label above the links list must be dropped.

    The WC-Episode theme generates that heading itself in CSS
    (`.wc-episode-notes-content-links::before { content: "Links" }`), so a
    typed one renders the heading twice. Typing it is the natural thing to do
    and looks correct in Dovetail, so this is expected to recur.
    """

    LIST = '<ul><li><a href="https://example.com">A Book</a></li></ul>'

    @pytest.mark.parametrize(
        "heading",
        [
            "<p><strong>Links:</strong></p>",   # the shape WC E20 shipped with
            "<p>Links:</p>",
            "<p>Links</p>",
            "<h3>LINKS:</h3>",
            "<p><strong>&nbsp;Links:&nbsp;</strong></p>",
            "<p><b>Link:</b></p>",
        ],
    )
    def test_strips_heading_above_links_list(self, heading: str) -> None:
        out = format_episode_links(f"<p>Intro.</p>{heading}{self.LIST}")
        assert "Links:" not in out
        assert "Link:" not in out
        assert ">Links<" not in out
        # the list itself still gets formatted
        assert 'class="wc-episode-notes-content-links"' in out
        assert "A Book" in out
        assert "<p>Intro.</p>" in out

    def test_keeps_heading_above_non_link_list(self) -> None:
        """Nothing generates a duplicate heading for a plain bulleted list."""
        html_str = '<p><strong>Links:</strong></p><ul><li>no url here</li></ul>'
        out = format_episode_links(html_str)
        assert "Links:" in out
        assert 'class="wc-episode-notes-content-links"' not in out

    def test_keeps_heading_separated_from_list(self) -> None:
        """Only a label directly adjacent to the list is redundant."""
        out = format_episode_links(
            f"<p><strong>Links:</strong></p><p>Other text.</p>{self.LIST}"
        )
        assert "Links:" in out

    def test_leaves_unrelated_headings_alone(self) -> None:
        out = format_episode_links(f"<p><strong>Guests:</strong></p>{self.LIST}")
        assert "Guests:" in out
