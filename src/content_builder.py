"""HTML content generation for Ghost posts from podcast episodes."""

from __future__ import annotations

import base64
import html
import json
import logging
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

import nh3

from .feed_parser import Episode
from .ghost_client import GhostPost
from .content_transforms import transform_title, strip_boilerplate

logger = logging.getLogger(__name__)

# Allowed HTML tags for RSS content sanitization.
# Strips <script>, <style>, <iframe>, event handlers, etc.
SAFE_HTML_TAGS = {
    "p", "br", "em", "strong", "b", "i", "a",
    "ul", "ol", "li",
    "h2", "h3", "h4",
    "blockquote", "div", "span",
}

# Allowed attributes per tag
SAFE_HTML_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "div": {"class", "id"},
    "span": {"class"},
}


def sanitize_html(raw_html: str) -> str:
    """Sanitize HTML from RSS feeds to prevent XSS.

    Allows only safe structural/formatting tags. Strips <script>,
    <style>, <iframe>, event handler attributes, and data: URIs.

    Args:
        raw_html: Untrusted HTML from RSS feed.

    Returns:
        Sanitized HTML string.
    """
    return nh3.clean(
        raw_html,
        tags=SAFE_HTML_TAGS,
        attributes=SAFE_HTML_ATTRIBUTES,
    )


# =============================================================================
# Pod.link Smart Links
# =============================================================================

# Default authors by feed type (Ghost user slugs)
FEED_AUTHORS = {
    "ttbook": [{"slug": "anne"}, {"slug": "steve"}],   # Anne Strainchamps & Steve Paulson
    "luminous": [{"slug": "steve"}],                    # Steve Paulson
}

# Apple Podcasts IDs for our podcasts
APPLE_PODCASTS_IDS = {
    "3329": "1680986776",  # Luminous
    "120": "471896367",     # TTBOOK main feed
}


def build_podlink_url(guid: str, apple_id: str = None, feed_url: str = None) -> str:
    """Build a pod.link episode URL.

    Pod.link provides a universal podcast link that redirects users
    to their preferred podcast app (Apple Podcasts, Spotify, etc.)

    Using Apple Podcasts ID is preferred as it provides better platform matching.

    Args:
        guid: Episode GUID (e.g., 'prx_3329_53b83d2b-57d2-434b-bc8b-c05091e1348d')
        apple_id: Apple Podcasts ID (preferred, e.g., '1680986776')
        feed_url: RSS feed URL (fallback if no apple_id)

    Returns:
        Pod.link URL for the specific episode
    """
    # URL-safe base64 encode the GUID, strip padding
    guid_b64 = base64.urlsafe_b64encode(guid.encode()).decode().rstrip('=')

    if apple_id:
        # Use Apple Podcasts ID (better platform matching)
        return f"https://pod.link/{apple_id}/episode/{guid_b64}"
    elif feed_url:
        # Fallback to RSS feed URL
        feed_b64 = base64.urlsafe_b64encode(feed_url.encode()).decode().rstrip('=')
        return f"https://pod.link/{feed_b64}/episode/{guid_b64}"
    else:
        return None


def get_apple_id_from_guid(guid: str) -> str | None:
    """Extract podcast ID from GUID and look up Apple Podcasts ID.

    Args:
        guid: Episode GUID (e.g., 'prx_3329_53b83d2b-...')

    Returns:
        Apple Podcasts ID or None if not found
    """
    # GUIDs are formatted as 'prx_{podcast_id}_{episode_uuid}'
    if guid and guid.startswith("prx_"):
        parts = guid.split("_")
        if len(parts) >= 2:
            podcast_id = parts[1]
            return APPLE_PODCASTS_IDS.get(podcast_id)
    return None


def build_listen_links_html(guid: str, feed_url: str = None) -> str:
    """Build HTML for "Listen on your favorite app" links.

    Creates a pod.link that works across all major podcast platforms.

    Args:
        guid: Episode GUID
        feed_url: RSS feed URL (fallback)

    Returns:
        HTML string with Ghost card markers for the listen links section
    """
    apple_id = get_apple_id_from_guid(guid)
    podlink = build_podlink_url(guid, apple_id=apple_id, feed_url=feed_url)

    if not podlink:
        return ""

    return f'''<!--kg-card-begin: html-->
<div class="episode-listen-links">
  <a href="{podlink}" class="podlink-button" target="_blank" rel="noopener">
    Listen on your favorite podcast app
  </a>
</div>
<!--kg-card-end: html-->'''


# =============================================================================
# Audio Player
# =============================================================================

def build_audio_player_card(
    episode: "Episode",
    guest: Optional[str] = None,
    peaks_url: Optional[str] = None,
    ghost_audio_url: Optional[str] = None,
    ghost_image_url: Optional[str] = None,
) -> str:
    """Build a Custom HTML Card with data attributes for theme-hydrated audio player.

    The theme's post.hbs template detects this div and hydrates it with the
    chosen player (Wavesurfer, AmplitudeJS, etc.). This keeps content portable
    while letting the theme control presentation.

    Args:
        episode: Parsed Episode object with audio data.
        guest: Optional guest name (parsed from title if not provided).
        peaks_url: Optional URL to pre-generated peaks JSON for Wavesurfer
                   (solves CORS issues with PRX redirect URLs).
        ghost_audio_url: Optional Ghost-hosted audio URL. When provided,
                         used as data-audio-url (avoids CORS). The original
                         PRX URL is preserved in data-original-audio-url.
        ghost_image_url: Optional Ghost-hosted image URL for artwork.
                         When provided, used for data-episode-artwork instead
                         of the original PRX image URL.

    Returns:
        HTML string with Ghost card markers and data attributes.
    """
    if not episode.enclosure_url:
        return ""

    # Determine which URL the player should use
    if ghost_audio_url:
        audio_url = html.escape(ghost_audio_url, quote=True)
        original_url_attr = f'\n     data-original-audio-url="{html.escape(episode.enclosure_url, quote=True)}"'
    else:
        audio_url = html.escape(episode.enclosure_url, quote=True)
        original_url_attr = ""

    artwork = html.escape(ghost_image_url or episode.image_url or "", quote=True)
    date = episode.pub_date.strftime("%Y-%m-%d")
    description = html.escape(episode.subtitle or "", quote=True)
    duration = html.escape(episode.duration or "", quote=True)
    guid = html.escape(episode.guid or "", quote=True)
    guest_attr = html.escape(guest or "", quote=True)

    # Add peaks URL if provided
    peaks_attr = ""
    if peaks_url:
        peaks_attr = f'\n     data-peaks-url="{html.escape(peaks_url, quote=True)}"'

    return f'''<!--kg-card-begin: html-->
<div class="wc-audio-player"
     data-audio-url="{audio_url}"{original_url_attr}
     data-episode-artwork="{artwork}"
     data-episode-date="{date}"
     data-episode-guest="{guest_attr}"
     data-episode-description="{description}"
     data-episode-duration="{duration}"
     data-episode-guid="{guid}"{peaks_attr}>
</div>
<!--kg-card-end: html-->'''


# =============================================================================
# Transcript Loading
# =============================================================================

def load_transcript(slug: str, cache_dir: Optional[Path] = None) -> Optional[str]:
    """Load transcript from TTBOOK cache.

    Args:
        slug: Episode slug (e.g., 'luminous-melissa-etheridge-ayahuasca')
        cache_dir: Path to cache directory, defaults to sample-data/ttbook-cache/luminous

    Returns:
        Transcript text or None if not found.
    """
    if cache_dir is None:
        # Default to project sample-data
        cache_dir = Path(__file__).parent.parent / 'sample-data' / 'ttbook-cache' / 'luminous'

    transcript_file = cache_dir / f'{slug}_transcript.txt'
    if transcript_file.exists():
        return transcript_file.read_text()
    return None


# Transcript placeholder text that indicates no actual transcript is available
TRANSCRIPT_PLACEHOLDER = "Transcripts are typically available for new episodes within 48 hours of their original airdate."


def is_placeholder_transcript(transcript: str) -> bool:
    """Check if transcript is just the placeholder text.

    Args:
        transcript: Raw transcript text.

    Returns:
        True if transcript is only the placeholder message.
    """
    if not transcript:
        return True
    # Check if the transcript contains only the placeholder text
    return TRANSCRIPT_PLACEHOLDER in transcript and len(transcript.strip()) < 250


def format_transcript_html(transcript: str) -> str:
    """Convert transcript text to HTML with speaker formatting.

    Args:
        transcript: Raw transcript text with speaker attributions.

    Returns:
        HTML formatted transcript.
    """
    if not transcript:
        return ''

    lines = transcript.strip().split('\n')
    html_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Format speaker attribution: "- [Speaker]" -> "<p><strong>Speaker:</strong>"
        if line.startswith('- ['):
            bracket_end = line.find(']')
            if bracket_end > 3:
                speaker = html.escape(line[3:bracket_end])
                content = html.escape(line[bracket_end + 1:].strip())
                html_lines.append(f'<p><strong>{speaker}:</strong> {content}</p>')
            else:
                html_lines.append(f'<p>{html.escape(line)}</p>')
        else:
            html_lines.append(f'<p>{html.escape(line)}</p>')

    return '\n'.join(html_lines)


def extract_slug_from_link(link: str) -> Optional[str]:
    """Extract episode slug from TTBOOK link.

    Args:
        link: Episode URL (e.g., 'https://www.ttbook.org/show/luminous-melissa-etheridge-ayahuasca')

    Returns:
        Slug string or None.
    """
    if not link:
        return None
    # Extract the last path component
    path = urllib.parse.urlparse(link).path
    parts = path.strip('/').split('/')
    if parts:
        return parts[-1]
    return None


# =============================================================================
# JSON-LD Structured Data
# =============================================================================

def build_jsonld_metadata(episode: "Episode", show_name: str) -> str:
    """Generate JSON-LD structured data for SEO.

    Stores episode categories and metadata in Schema.org format,
    keeping them out of Ghost's tag system while preserving SEO value.

    Schema.org PodcastEpisode type provides rich results in search engines,
    including podcast-specific features like episode duration and series info.

    Args:
        episode: Parsed Episode object with metadata.
        show_name: Name of the podcast series (e.g., 'Luminous', 'TTBOOK').

    Returns:
        HTML script tag containing JSON-LD structured data for injection
        into Ghost's codeinjection_head field.
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "PodcastEpisode",
        "name": episode.title,
        "description": episode.description or episode.subtitle,
        "partOfSeries": {
            "@type": "PodcastSeries",
            "name": show_name
        },
        "keywords": episode.categories,  # RSS categories preserved here
        "datePublished": episode.pub_date.isoformat() if episode.pub_date else None,
        "duration": f"PT{episode.duration}S" if episode.duration and episode.duration.isdigit() else None,
        "url": episode.link,
    }

    # Handle duration in MM:SS or HH:MM:SS format
    if episode.duration and ":" in episode.duration:
        parts = episode.duration.split(":")
        try:
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                total_seconds = minutes * 60 + seconds
            elif len(parts) == 3:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                total_seconds = hours * 3600 + minutes * 60 + seconds
            else:
                total_seconds = None
            if total_seconds:
                schema["duration"] = f"PT{total_seconds}S"
        except ValueError:
            pass  # Leave duration as None if parsing fails

    # Remove None values for cleaner output
    schema = {k: v for k, v in schema.items() if v is not None}

    return f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'


# =============================================================================
# Luminous Episode Builder
# =============================================================================

def format_pub_date(pub_date: datetime) -> str:
    """Format publication date for display.

    Args:
        pub_date: Episode publication datetime.

    Returns:
        Formatted date string (e.g., 'July 8, 2023').
    """
    return pub_date.strftime('%B %-d, %Y')


def build_luminous_post_html(
    episode: Episode,
    feed_url: str = 'https://f.prxu.org/3329/feed-rss.xml',
    transcript: Optional[str] = None,
    peaks_url: Optional[str] = None,
    ghost_audio_url: Optional[str] = None,
    ghost_image_url: Optional[str] = None,
) -> str:
    """Build HTML content for a Luminous episode post.

    Template structure:
    1. HTML5 audio player (theme-stylable)
    2. Pod.link "Listen on your favorite app" button
    3. Episode description (from content:encoded, boilerplate stripped)
    4. Transcript section (only if transcript exists)

    Removed elements (per client feedback):
    - Original Air Date metadata line
    - Interviews In This Hour / Guests sections
    - Subscribe footer links

    Args:
        episode: Parsed Episode object.
        feed_url: URL to the Luminous RSS feed for pod.link generation.
        transcript: Optional transcript text.
        peaks_url: Optional URL to pre-generated peaks JSON for Wavesurfer.
        ghost_audio_url: Optional Ghost-hosted audio URL (avoids CORS).
        ghost_image_url: Optional Ghost-hosted image URL for artwork.

    Returns:
        Complete HTML for Ghost post body.
    """
    sections = []

    # 1. Theme-hydrated audio player with data attributes
    if episode.enclosure_url:
        sections.append(build_audio_player_card(
            episode, peaks_url=peaks_url, ghost_audio_url=ghost_audio_url,
            ghost_image_url=ghost_image_url,
        ))

    # Listen links removed per editorial decision — pod.link buttons
    # were not wanted in the imported Luminous content.
    # if episode.guid and feed_url:
    #     sections.append(build_listen_links_html(episode.guid, feed_url))

    # 3. Episode description (from content:encoded, with boilerplate stripped and sanitized)
    if episode.description:
        description = strip_boilerplate(episode.description, 'luminous')
        description = sanitize_html(description)
        sections.append(description)

    # 4. Transcript section (only if real transcript available, not placeholder)
    # Wrapped in a div with id="episode-transcript" for theme styling
    if transcript and not is_placeholder_transcript(transcript):
        transcript_html = format_transcript_html(transcript)
        sections.append('<!--kg-card-begin: html-->')
        sections.append('<div id="episode-transcript" class="episode-transcript">')
        sections.append('<h2>Transcript</h2>')
        sections.append(transcript_html)
        sections.append('</div>')
        sections.append('<!--kg-card-end: html-->')

    # No footer - theme handles navigation/subscription CTAs

    return '\n'.join(sections)


def build_luminous_ghost_post(
    episode: Episode,
    status: str = 'draft',
    transcript: Optional[str] = None,
    feed_url: str = 'https://f.prxu.org/3329/feed-rss.xml',
    peaks_url: Optional[str] = None,
    ghost_audio_url: Optional[str] = None,
    ghost_image_url: Optional[str] = None,
    og_image_url: Optional[str] = None,
) -> GhostPost:
    """Build a GhostPost for a Luminous episode.

    Field mapping:
    - Title: Episode title with 'Luminous: ' prefix removed
    - custom_excerpt: itunes:subtitle (short summary)
    - feature_image: Episode-specific itunes:image
    - canonical_url: ttbook.org episode link
    - html: Full template with description, player, transcript

    Args:
        episode: Parsed Episode object.
        status: Post status ('draft' or 'published').
        transcript: Optional transcript text.
        feed_url: Luminous feed URL for player embed.
        peaks_url: Optional URL to pre-generated peaks JSON for Wavesurfer.
        ghost_audio_url: Optional Ghost-hosted audio URL (avoids CORS).
        ghost_image_url: Optional Ghost-hosted image URL for feature_image and artwork.
        og_image_url: Optional Ghost-hosted OG image URL (1200x630).

    Returns:
        GhostPost ready for Ghost API.
    """
    logger.info(f"Building Luminous Ghost post for: {episode.title}")

    # Transform title (remove 'Luminous: ' prefix)
    title = transform_title(episode.title, 'luminous')

    # Build HTML content with transcript if available
    html_content = build_luminous_post_html(
        episode, feed_url, transcript, peaks_url, ghost_audio_url,
        ghost_image_url=ghost_image_url,
    )

    # Single show tag only - categories moved to JSON-LD structured data
    tags = [{'name': 'Luminous'}]

    # Build JSON-LD structured data (preserves categories for SEO)
    jsonld = build_jsonld_metadata(episode, show_name="Luminous")

    # Format published_at
    published_at = episode.pub_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')

    # Use subtitle as custom_excerpt (Ghost limit is 300 chars)
    excerpt = episode.subtitle
    if excerpt and len(excerpt) > 300:
        excerpt = excerpt[:297] + '...'

    return GhostPost(
        title=title,
        html=html_content,
        status=status,
        published_at=published_at,
        feature_image=ghost_image_url or episode.image_url,  # Prefer Ghost-hosted
        custom_excerpt=excerpt,  # From itunes:subtitle
        canonical_url=episode.link,
        tags=tags,
        authors=FEED_AUTHORS.get("luminous", []),
        og_image=og_image_url,
        twitter_image=og_image_url,
        codeinjection_head=jsonld,
    )


def build_audio_player_html(
    enclosure_url: str,
    duration: str,
    enclosure_type: str = "audio/mpeg",
) -> str:
    """Generate HTML for the audio player embed.

    Args:
        enclosure_url: URL to the audio file.
        duration: Episode duration string (e.g., '52:02').
        enclosure_type: MIME type of the audio file.

    Returns:
        HTML string for the audio player section.
    """
    # Escape URLs for HTML attributes
    safe_url = html.escape(enclosure_url, quote=True)

    return f'''<div class="episode-player">
  <audio controls preload="metadata">
    <source src="{safe_url}" type="{enclosure_type}">
    Your browser does not support the audio element.
  </audio>
  <p class="episode-duration">Duration: {duration}</p>
</div>'''


def build_episode_content_html(description: str) -> str:
    """Generate HTML for the episode content section.

    Args:
        description: Episode description HTML (from content:encoded).

    Returns:
        HTML string for the content section.
    """
    # The description is already HTML from content:encoded
    # Wrap it in a container for styling
    return f'''<div class="episode-content">
{description}
</div>'''


def build_episode_meta_html(link: str) -> str:
    """Generate HTML for the episode metadata section.

    Args:
        link: URL to the original episode page.

    Returns:
        HTML string for the metadata section.
    """
    safe_link = html.escape(link, quote=True)

    return f'''<div class="episode-meta">
  <p><a href="{safe_link}">Listen on TTBOOK.org</a></p>
</div>'''


def build_post_html(
    episode: Episode,
    feed_type: str = "ttbook",
    peaks_url: Optional[str] = None,
    ghost_audio_url: Optional[str] = None,
    ghost_image_url: Optional[str] = None,
) -> str:
    """Build the complete HTML content for a Ghost post.

    Uses the theme-hydrated audio player card (same as Luminous builder)
    and strips feed-specific boilerplate from descriptions.

    Args:
        episode: Parsed Episode object from RSS feed.
        feed_type: Feed identifier for boilerplate stripping rules.
        peaks_url: Optional URL to pre-generated peaks JSON for Wavesurfer.
        ghost_audio_url: Optional Ghost-hosted audio URL (avoids CORS).
        ghost_image_url: Optional Ghost-hosted image URL for artwork.

    Returns:
        Complete HTML string for the Ghost post body.
    """
    sections = []

    # Theme-hydrated audio player with data attributes
    if episode.enclosure_url:
        sections.append(build_audio_player_card(
            episode, peaks_url=peaks_url, ghost_audio_url=ghost_audio_url,
            ghost_image_url=ghost_image_url,
        ))

    # Episode description with boilerplate stripped and sanitized
    if episode.description:
        description = strip_boilerplate(episode.description, feed_type)
        description = sanitize_html(description)
        sections.append(description)

    return "\n".join(sections)


def build_tags(
    episode: Episode,
    primary_tag: str = "TTBOOK",
) -> list[dict]:
    """Build Ghost tags array - show tag only.

    RSS categories are now stored in JSON-LD structured data via
    codeinjection_head rather than as Ghost tags. This keeps the
    Ghost admin UI clean while preserving SEO value.

    Args:
        episode: Parsed Episode object (unused, kept for API compatibility).
        primary_tag: The show tag to include (e.g., 'TTBOOK', 'Luminous').

    Returns:
        List with single tag dict in Ghost API format: [{'name': 'Tag'}].
    """
    return [{"name": primary_tag}]


def format_published_at(episode: Episode) -> str:
    """Format episode publication date for Ghost API.

    Ghost expects ISO 8601 format with timezone.

    Args:
        episode: Parsed Episode object.

    Returns:
        ISO 8601 formatted date string.
    """
    return episode.pub_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_ghost_post(
    episode: Episode,
    status: str = "draft",
    primary_tag: str = "Wonder Cabinet",
    feed_type: str = "ttbook",
    peaks_url: Optional[str] = None,
    ghost_audio_url: Optional[str] = None,
    ghost_image_url: Optional[str] = None,
    og_image_url: Optional[str] = None,
) -> GhostPost:
    """Build a complete GhostPost from an Episode.

    This is the main function that transforms RSS episode data
    into a ready-to-publish Ghost post.

    Args:
        episode: Parsed Episode object from RSS feed.
        status: Post status ('draft' or 'published').
        primary_tag: Primary tag for the post (used as show name for JSON-LD).
        feed_type: Feed identifier for boilerplate stripping rules.
        peaks_url: Optional URL to pre-generated peaks JSON for Wavesurfer.
        ghost_audio_url: Optional Ghost-hosted audio URL (avoids CORS).
        ghost_image_url: Optional Ghost-hosted image URL for feature_image and artwork.
        og_image_url: Optional Ghost-hosted OG image URL (1200x630).

    Returns:
        GhostPost ready for Ghost API.
    """
    logger.info(f"Building Ghost post for: {episode.title}")

    # Build HTML content
    html_content = build_post_html(
        episode, feed_type=feed_type, peaks_url=peaks_url,
        ghost_audio_url=ghost_audio_url, ghost_image_url=ghost_image_url,
    )

    # Build tags (show tag only - categories in JSON-LD)
    tags = build_tags(episode, primary_tag=primary_tag)

    # Build JSON-LD structured data (preserves categories for SEO)
    jsonld = build_jsonld_metadata(episode, show_name=primary_tag)

    # Truncate excerpt if too long (Ghost limit is 300 chars)
    excerpt = episode.subtitle
    if excerpt and len(excerpt) > 300:
        excerpt = excerpt[:297] + "..."

    # Build the post
    authors = FEED_AUTHORS.get(feed_type, [])

    post = GhostPost(
        title=episode.title,
        html=html_content,
        status=status,
        published_at=format_published_at(episode),
        feature_image=ghost_image_url or episode.image_url or None,  # Prefer Ghost-hosted
        custom_excerpt=excerpt if excerpt else None,
        canonical_url=episode.link if episode.link else None,
        tags=tags,
        authors=authors,
        og_image=og_image_url,
        twitter_image=og_image_url,
        codeinjection_head=jsonld,
    )

    logger.debug(f"Built post with {len(tags)} tags, status={status}")

    return post


if __name__ == "__main__":
    # Test content builder with sample episode
    from datetime import datetime
    from pathlib import Path

    logging.basicConfig(level=logging.DEBUG)

    # Create a sample episode for testing
    sample_episode = Episode(
        guid="prx_120_test-guid",
        title="Test Episode: The Art of Testing",
        description="<p>This is a <strong>test</strong> episode description.</p>",
        subtitle="A short subtitle for testing purposes.",
        pub_date=datetime.now(),
        link="https://www.ttbook.org/show/test-episode",
        enclosure_url="https://example.com/audio.mp3",
        enclosure_type="audio/mpeg",
        duration="45:30",
        image_url="https://example.com/image.png",
        categories=["testing", "development", "automation"],
        episode_type="full",
        author="Wisconsin Public Radio",
    )

    # Build the Ghost post
    ghost_post = build_ghost_post(sample_episode)

    print("Generated Ghost Post:")
    print("=" * 50)
    print(f"Title: {ghost_post.title}")
    print(f"Status: {ghost_post.status}")
    print(f"Published At: {ghost_post.published_at}")
    print(f"Feature Image: {ghost_post.feature_image}")
    print(f"Tags: {ghost_post.tags}")
    print(f"\nHTML Content:\n{ghost_post.html}")
