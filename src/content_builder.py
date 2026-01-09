"""HTML content generation for Ghost posts from podcast episodes."""

from __future__ import annotations

import base64
import html
import logging
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from .feed_parser import Episode
from .ghost_client import GhostPost
from .content_transforms import transform_title, strip_boilerplate

logger = logging.getLogger(__name__)


# =============================================================================
# Pod.link Smart Links
# =============================================================================

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
# Audio Player (HTML5)
# =============================================================================

def build_html5_audio_player(enclosure_url: str, enclosure_type: str = "audio/mpeg") -> str:
    """Build a plain HTML5 audio element for theme styling (deprecated).

    Use build_audio_player_card() instead for theme-hydrated players.
    """
    safe_url = html.escape(enclosure_url, quote=True)

    return f'''<!--kg-card-begin: html-->
<div class="episode-audio-player">
  <audio controls preload="metadata">
    <source src="{safe_url}" type="{enclosure_type}">
    Your browser does not support the audio element.
  </audio>
</div>
<!--kg-card-end: html-->'''


def build_audio_player_card(
    episode: "Episode",
    guest: Optional[str] = None,
) -> str:
    """Build a Custom HTML Card with data attributes for theme-hydrated audio player.

    The theme's post.hbs template detects this div and hydrates it with the
    chosen player (Wavesurfer, AmplitudeJS, etc.). This keeps content portable
    while letting the theme control presentation.

    Args:
        episode: Parsed Episode object with audio data.
        guest: Optional guest name (parsed from title if not provided).

    Returns:
        HTML string with Ghost card markers and data attributes.
    """
    if not episode.enclosure_url:
        return ""

    # Escape all values for HTML attributes
    audio_url = html.escape(episode.enclosure_url, quote=True)
    artwork = html.escape(episode.image_url or "", quote=True)
    date = episode.pub_date.strftime("%Y-%m-%d")
    description = html.escape(episode.subtitle or "", quote=True)
    duration = html.escape(episode.duration or "", quote=True)
    guid = html.escape(episode.guid or "", quote=True)
    guest_attr = html.escape(guest or "", quote=True)

    return f'''<!--kg-card-begin: html-->
<div class="wc-audio-player"
     data-audio-url="{audio_url}"
     data-episode-artwork="{artwork}"
     data-episode-date="{date}"
     data-episode-guest="{guest_attr}"
     data-episode-description="{description}"
     data-episode-duration="{duration}"
     data-episode-guid="{guid}">
</div>
<!--kg-card-end: html-->'''


def build_prx_player_embed(guid: str, feed_url: str) -> str:
    """Build PRX embeddable player iframe (deprecated - use build_html5_audio_player).

    Args:
        guid: Episode GUID (e.g., 'prx_3329_a6ad4b02-0db2-4fa9-8cf3-95764fd1e1fe')
        feed_url: Feed URL for the podcast

    Returns:
        HTML string with Ghost card markers for raw HTML embed.
    """
    encoded_feed = urllib.parse.quote(feed_url, safe='')

    return f'''<!--kg-card-begin: html-->
<iframe allow="monetization" frameborder="0" height="200" scrolling="no" src="https://play.prx.org/e?ge={guid}&uf={encoded_feed}" style="min-width: 300px;" width="100%"></iframe>
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
                speaker = line[3:bracket_end]
                content = line[bracket_end + 1:].strip()
                html_lines.append(f'<p><strong>{speaker}:</strong> {content}</p>')
            else:
                html_lines.append(f'<p>{line}</p>')
        else:
            html_lines.append(f'<p>{line}</p>')

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

    Returns:
        Complete HTML for Ghost post body.
    """
    sections = []

    # 1. Theme-hydrated audio player with data attributes
    if episode.enclosure_url:
        sections.append(build_audio_player_card(episode))

    # 2. Pod.link - universal "Listen on your favorite app" link
    if episode.guid and feed_url:
        sections.append(build_listen_links_html(episode.guid, feed_url))

    # 3. Episode description (from content:encoded, with boilerplate stripped)
    if episode.description:
        description = strip_boilerplate(episode.description, 'luminous')
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

    Returns:
        GhostPost ready for Ghost API.
    """
    logger.info(f"Building Luminous Ghost post for: {episode.title}")

    # Transform title (remove 'Luminous: ' prefix)
    title = transform_title(episode.title, 'luminous')

    # Build HTML content with transcript if available
    html_content = build_luminous_post_html(episode, feed_url, transcript)

    # Build tags
    tags = [
        {'name': 'Luminous'},
        {'name': 'Psychedelics'},
        {'name': 'TTBOOK'},
    ]

    # Add categories from feed
    for cat in episode.categories:
        cat_clean = cat.strip()
        if cat_clean and not any(t['name'].lower() == cat_clean.lower() for t in tags):
            tags.append({'name': cat_clean})

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
        feature_image=episode.image_url,  # Episode-specific art from itunes:image
        custom_excerpt=excerpt,  # From itunes:subtitle
        canonical_url=episode.link,
        tags=tags,
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


def build_post_html(episode: Episode) -> str:
    """Build the complete HTML content for a Ghost post.

    Combines audio player, episode content, and metadata into
    a single HTML document following the architecture spec.

    Args:
        episode: Parsed Episode object from RSS feed.

    Returns:
        Complete HTML string for the Ghost post body.
    """
    sections = []

    # Audio player (if enclosure URL exists)
    if episode.enclosure_url:
        sections.append(
            build_audio_player_html(
                episode.enclosure_url,
                episode.duration,
                episode.enclosure_type,
            )
        )

    # Episode content
    if episode.description:
        sections.append(build_episode_content_html(episode.description))

    # Episode metadata with link
    if episode.link:
        sections.append(build_episode_meta_html(episode.link))

    return "\n\n".join(sections)


def build_tags(
    episode: Episode,
    primary_tag: str = "TTBOOK",
    include_categories: bool = True,
    include_episode_type: bool = True,
) -> list[dict]:
    """Build Ghost tags array from episode data.

    Args:
        episode: Parsed Episode object.
        primary_tag: Primary tag to always include.
        include_categories: Whether to include RSS categories as tags.
        include_episode_type: Whether to include episode type as a tag.

    Returns:
        List of tag dicts in Ghost API format: [{'name': 'Tag'}].
    """
    tags = []

    # Always include primary tag first
    tags.append({"name": primary_tag})

    # Add episode type if not 'full' (since full is default)
    if include_episode_type and episode.episode_type and episode.episode_type != "full":
        tags.append({"name": episode.episode_type.capitalize()})

    # Add categories from RSS feed
    if include_categories and episode.categories:
        for category in episode.categories:
            # Skip duplicates and primary tag
            category_clean = category.strip()
            if category_clean and category_clean.lower() != primary_tag.lower():
                # Check for duplicates (case-insensitive)
                if not any(t["name"].lower() == category_clean.lower() for t in tags):
                    tags.append({"name": category_clean})

    return tags


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
    primary_tag: str = "TTBOOK",
) -> GhostPost:
    """Build a complete GhostPost from an Episode.

    This is the main function that transforms RSS episode data
    into a ready-to-publish Ghost post.

    Args:
        episode: Parsed Episode object from RSS feed.
        status: Post status ('draft' or 'published').
        primary_tag: Primary tag for the post.

    Returns:
        GhostPost ready for Ghost API.
    """
    logger.info(f"Building Ghost post for: {episode.title}")

    # Build HTML content
    html_content = build_post_html(episode)

    # Build tags
    tags = build_tags(episode, primary_tag=primary_tag)

    # Truncate excerpt if too long (Ghost limit is 300 chars)
    excerpt = episode.subtitle
    if excerpt and len(excerpt) > 300:
        excerpt = excerpt[:297] + "..."

    # Build the post
    post = GhostPost(
        title=episode.title,
        html=html_content,
        status=status,
        published_at=format_published_at(episode),
        feature_image=episode.image_url if episode.image_url else None,
        custom_excerpt=excerpt if excerpt else None,
        canonical_url=episode.link if episode.link else None,
        tags=tags,
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
