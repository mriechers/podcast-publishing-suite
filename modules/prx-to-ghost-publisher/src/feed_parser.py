"""RSS feed fetching and parsing for PRX/Dovetail podcasts."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class FeedFetchError(Exception):
    """Raised when feed cannot be fetched."""
    pass


class FeedParseError(Exception):
    """Raised when feed XML cannot be parsed."""
    pass


# XML Namespaces used in PRX feeds
NAMESPACES = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
    "atom": "http://www.w3.org/2005/Atom",
}


@dataclass
class Episode:
    """Represents a podcast episode parsed from RSS feed."""

    guid: str
    title: str
    description: str
    subtitle: str
    pub_date: datetime
    link: str
    enclosure_url: str
    enclosure_type: str
    duration: str
    image_url: str
    categories: list[str] = field(default_factory=list)
    episode_type: str = "full"
    author: str = ""
    transcript_url: str = ""
    transcript_type: str = ""  # MIME type: text/plain, text/html, application/json
    media_segments: list[dict] = field(default_factory=list)  # Direct CDN URLs from Dovetail media[] array
    image_alt: str = ""  # Alt text for episode artwork
    image_caption: str = ""  # Caption/credit for episode artwork

    def __str__(self) -> str:
        return f"Episode({self.guid}: {self.title})"


def _validate_feed_url(url: str) -> None:
    """Validate that a feed URL is safe to fetch.

    Rejects file:// scheme, URLs without hostname, and non-HTTP(S) schemes
    to prevent SSRF and local file disclosure.

    Args:
        url: URL to validate.

    Raises:
        FeedFetchError: If URL is not safe.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FeedFetchError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only http/https allowed."
        )
    if not parsed.hostname:
        raise FeedFetchError(f"Feed URL missing hostname: {url}")


def fetch_feed(url: str, timeout: int = 30) -> str:
    """Fetch RSS feed content from URL.

    Args:
        url: RSS feed URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Raw XML content as string.

    Raises:
        FeedFetchError: If request fails or URL is invalid.
    """
    _validate_feed_url(url)

    headers = {
        "User-Agent": "PRX-to-Ghost-Publisher/0.1.0 (+https://github.com/prx-publisher)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        raise FeedFetchError(f"Timeout fetching feed: {url}")
    except requests.exceptions.HTTPError as e:
        raise FeedFetchError(f"HTTP error {e.response.status_code}: {url}")
    except requests.exceptions.RequestException as e:
        raise FeedFetchError(f"Failed to fetch feed: {e}")


def _get_text(element: Optional[ET.Element], default: str = "") -> str:
    """Safely get text content from an XML element."""
    if element is None:
        return default
    return element.text or default


def _get_attr(element: Optional[ET.Element], attr: str, default: str = "") -> str:
    """Safely get attribute from an XML element."""
    if element is None:
        return default
    return element.get(attr, default)


def _parse_date(date_str: str) -> datetime:
    """Parse RFC 2822 date string to datetime.

    Falls back to current time if parsing fails.
    """
    if not date_str:
        return datetime.now()

    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return datetime.now()


def _parse_episode(item: ET.Element) -> Optional[Episode]:
    """Parse a single RSS item element into an Episode.

    Args:
        item: XML Element representing an RSS item.

    Returns:
        Episode object, or None if parsing fails.
    """
    try:
        # Extract GUID
        guid_elem = item.find("guid")
        guid = _get_text(guid_elem)
        if not guid:
            logger.warning("Skipping episode without GUID")
            return None

        # Extract title
        title = _get_text(item.find("title"))
        if not title:
            logger.warning(f"Skipping episode {guid} without title")
            return None

        # Extract description - prefer content:encoded, fall back to description
        content_encoded = item.find("content:encoded", NAMESPACES)
        description_elem = item.find("description")

        if content_encoded is not None and content_encoded.text:
            description = content_encoded.text
        else:
            description = _get_text(description_elem)

        # Extract subtitle from itunes:subtitle
        subtitle = _get_text(
            item.find("itunes:subtitle", NAMESPACES)
        )

        # Extract publication date
        pub_date = _parse_date(_get_text(item.find("pubDate")))

        # Extract link
        link = _get_text(item.find("link"))

        # Extract enclosure (audio file)
        enclosure = item.find("enclosure")
        enclosure_url = _get_attr(enclosure, "url")
        enclosure_type = _get_attr(enclosure, "type", "audio/mpeg")

        # Extract duration from itunes:duration
        duration = _get_text(
            item.find("itunes:duration", NAMESPACES),
            default="00:00"
        )

        # Extract image from itunes:image
        itunes_image = item.find("itunes:image", NAMESPACES)
        image_url = _get_attr(itunes_image, "href")

        # Extract categories
        categories = []
        for cat_elem in item.findall("category"):
            cat_text = _get_text(cat_elem)
            if cat_text:
                categories.append(cat_text.strip())

        # Extract episode type from itunes:episodeType
        episode_type = _get_text(
            item.find("itunes:episodeType", NAMESPACES),
            default="full"
        )

        # Extract author from itunes:author or author
        author = _get_text(item.find("itunes:author", NAMESPACES))
        if not author:
            author = _get_text(item.find("author"))

        # Extract transcript URL from <podcast:transcript> elements
        # Prefer types in order: text/html > application/json > text/plain > other
        transcript_url = ""
        transcript_type = ""
        transcript_elements = item.findall("podcast:transcript", NAMESPACES)
        if transcript_elements:
            type_priority = {
                "text/html": 3,
                "application/json": 2,
                "text/plain": 1,
            }
            best_priority = -1
            for t_elem in transcript_elements:
                t_url = t_elem.get("url", "")
                t_type = t_elem.get("type", "")
                if not t_url:
                    continue
                priority = type_priority.get(t_type, 0)
                if priority > best_priority:
                    best_priority = priority
                    transcript_url = t_url
                    transcript_type = t_type

        return Episode(
            guid=guid,
            title=title,
            description=description,
            subtitle=subtitle,
            pub_date=pub_date,
            link=link,
            enclosure_url=enclosure_url,
            enclosure_type=enclosure_type,
            duration=duration,
            image_url=image_url,
            categories=categories,
            episode_type=episode_type,
            author=author,
            transcript_url=transcript_url,
            transcript_type=transcript_type,
        )

    except Exception as e:
        logger.error(f"Failed to parse episode: {e}")
        return None


def parse_feed(xml_content: str) -> list[Episode]:
    """Parse RSS feed XML into list of Episode objects.

    Args:
        xml_content: Raw XML string of RSS feed.

    Returns:
        List of Episode objects, newest first (by pub_date).

    Raises:
        FeedParseError: If XML cannot be parsed.
    """
    try:
        # Register namespaces to preserve them in parsing
        for prefix, uri in NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise FeedParseError(f"Failed to parse XML: {e}")

    # Find all items in the feed
    channel = root.find("channel")
    if channel is None:
        raise FeedParseError("No channel element found in feed")

    items = channel.findall("item")
    logger.info(f"Found {len(items)} items in feed")

    episodes = []
    for item in items:
        episode = _parse_episode(item)
        if episode:
            episodes.append(episode)

    # Sort by publication date, newest first
    episodes.sort(key=lambda e: e.pub_date, reverse=True)

    logger.info(f"Successfully parsed {len(episodes)} episodes")
    return episodes


def get_episodes(feed_url: str) -> list[Episode]:
    """Convenience function to fetch and parse a feed in one step.

    Args:
        feed_url: URL of the RSS feed.

    Returns:
        List of Episode objects.

    Raises:
        FeedFetchError: If feed cannot be fetched.
        FeedParseError: If feed cannot be parsed.
    """
    xml_content = fetch_feed(feed_url)
    return parse_feed(xml_content)


def parse_feed_file(file_path: str) -> list[Episode]:
    """Parse a local RSS feed file.

    Args:
        file_path: Path to local XML file.

    Returns:
        List of Episode objects.

    Raises:
        FeedParseError: If file cannot be parsed.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        xml_content = f.read()
    return parse_feed(xml_content)


if __name__ == "__main__":
    # Test with sample feed file
    import sys
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    sample_feed = Path(__file__).parent.parent / "sample-data" / "prx-sample-feed.xml"

    if sample_feed.exists():
        print(f"Parsing sample feed: {sample_feed}")
        episodes = parse_feed_file(str(sample_feed))
        print(f"\nParsed {len(episodes)} episodes:\n")
        for ep in episodes[:5]:  # Show first 5
            print(f"  - {ep.title}")
            print(f"    GUID: {ep.guid}")
            print(f"    Date: {ep.pub_date}")
            print(f"    Duration: {ep.duration}")
            print(f"    Categories: {', '.join(ep.categories[:3])}")
            print()
    else:
        print(f"Sample feed not found: {sample_feed}", file=sys.stderr)
        sys.exit(1)
