"""Tests for feed parser: URL validation, XML parsing, error handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.feed_parser import (
    Episode,
    FeedFetchError,
    FeedParseError,
    _validate_feed_url,
    parse_feed,
)


class TestFeedURLValidation:
    """Validate feed URL security checks (Phase 2.4)."""

    def test_https_url_accepted(self):
        """HTTPS URLs should pass validation."""
        _validate_feed_url("https://f.prxu.org/3329/feed-rss.xml")

    def test_http_url_accepted(self):
        """HTTP URLs should pass validation (some feeds are HTTP-only)."""
        _validate_feed_url("http://example.com/feed.xml")

    def test_file_scheme_rejected(self):
        """file:// URLs must be rejected to prevent local file access."""
        with pytest.raises(FeedFetchError, match="Unsupported URL scheme"):
            _validate_feed_url("file:///etc/passwd")

    def test_ftp_scheme_rejected(self):
        """ftp:// URLs must be rejected."""
        with pytest.raises(FeedFetchError, match="Unsupported URL scheme"):
            _validate_feed_url("ftp://example.com/feed.xml")

    def test_empty_scheme_rejected(self):
        """URLs without a scheme should be rejected."""
        with pytest.raises(FeedFetchError, match="Unsupported URL scheme"):
            _validate_feed_url("example.com/feed.xml")

    def test_missing_hostname_rejected(self):
        """URLs without a hostname should be rejected."""
        with pytest.raises(FeedFetchError, match="missing hostname"):
            _validate_feed_url("https://")


class TestFeedParsing:
    """Validate RSS XML parsing."""

    SAMPLE_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
         xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <title>Test Podcast</title>
        <item>
          <guid>prx_3329_test-guid-1</guid>
          <title>Episode One</title>
          <description>First episode description.</description>
          <pubDate>Sat, 13 Sep 2025 11:00:00 +0000</pubDate>
          <link>https://example.com/ep1</link>
          <enclosure url="https://example.com/ep1.mp3" type="audio/mpeg" />
          <itunes:duration>45:30</itunes:duration>
        </item>
        <item>
          <guid>prx_3329_test-guid-2</guid>
          <title>Episode Two</title>
          <description>Second episode description.</description>
          <pubDate>Sat, 06 Sep 2025 11:00:00 +0000</pubDate>
        </item>
      </channel>
    </rss>
    """

    def test_parses_valid_feed(self):
        """Valid RSS feed should parse into Episode objects."""
        episodes = parse_feed(self.SAMPLE_FEED_XML)
        assert len(episodes) == 2
        assert episodes[0].title == "Episode One"
        assert episodes[0].guid == "prx_3329_test-guid-1"
        assert episodes[0].enclosure_url == "https://example.com/ep1.mp3"

    def test_episodes_sorted_newest_first(self):
        """Episodes should be sorted by pub_date, newest first."""
        episodes = parse_feed(self.SAMPLE_FEED_XML)
        assert episodes[0].pub_date > episodes[1].pub_date

    def test_malformed_xml_raises(self):
        """Malformed XML should raise FeedParseError."""
        with pytest.raises(FeedParseError, match="Failed to parse XML"):
            parse_feed("<not>valid<xml")

    def test_missing_channel_raises(self):
        """RSS without <channel> should raise FeedParseError."""
        with pytest.raises(FeedParseError, match="No channel element"):
            parse_feed('<?xml version="1.0"?><rss version="2.0"></rss>')

    def test_episodes_without_guid_skipped(self):
        """Items without a GUID should be silently skipped."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test</title>
            <item>
              <title>No GUID Episode</title>
              <description>Missing GUID.</description>
            </item>
            <item>
              <guid>valid-guid</guid>
              <title>Valid Episode</title>
            </item>
          </channel>
        </rss>
        """
        episodes = parse_feed(xml)
        assert len(episodes) == 1
        assert episodes[0].guid == "valid-guid"
