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
import requests

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


def load_wc_transcript(episode_title: str, transcript_dir: Optional[Path] = None) -> Optional[str]:
    """Load Wonder Cabinet transcript from local transcripts directory.

    Looks for transcript files matching the episode title pattern.
    Files should be named like: 101_Sophie_Strand.txt, 102_Carlo_Rovelli.txt

    Args:
        episode_title: Episode title to search for (partial match on name).
        transcript_dir: Path to transcripts directory, defaults to project /transcripts.

    Returns:
        Transcript text or None if not found.
    """
    if transcript_dir is None:
        transcript_dir = Path(__file__).parent.parent / 'transcripts'

    if not transcript_dir.exists():
        return None

    # Extract a key name from the title for matching
    # E.g., "Sophie Strand: Ecological Storytelling..." -> "Sophie Strand"
    # E.g., "Carlo Rovelli: Cosmic Mysteries..." -> "Carlo Rovelli"
    title_parts = episode_title.split(':')
    guest_name = title_parts[0].strip() if title_parts else episode_title

    # Look for transcript files containing the guest name
    for txt_file in transcript_dir.glob('*.txt'):
        # Normalize for comparison: replace underscores with spaces
        file_stem_normalized = txt_file.stem.replace('_', ' ')
        if guest_name.lower() in file_stem_normalized.lower():
            logger.info(f"Found transcript: {txt_file.name}")
            return txt_file.read_text()

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
# RSS Transcript Support
# =============================================================================

def fetch_rss_transcript(url: str, content_type: str, timeout: int = 30) -> Optional[str]:
    """Download transcript from a URL provided in RSS <podcast:transcript>.

    Args:
        url: Transcript URL from the RSS feed.
        content_type: MIME type (text/plain, text/html, application/json).
        timeout: Request timeout in seconds.

    Returns:
        Raw transcript content as string, or None on failure.
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "PRX-to-Ghost-Publisher/0.1.0"},
        )
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch transcript from {url}: {e}")
        return None


def format_rss_transcript_html(raw_content: str, content_type: str) -> str:
    """Convert a downloaded RSS transcript into HTML for Ghost posts.

    Handles three Podcasting 2.0 transcript formats:
    - text/html: sanitize via nh3 and use directly
    - application/json: parse JSON segments into speaker-attributed paragraphs
    - text/plain: detect speaker format or wrap paragraphs in <p> tags

    Args:
        raw_content: Raw transcript content downloaded from URL.
        content_type: MIME type of the transcript.

    Returns:
        HTML-formatted transcript string.
    """
    if not raw_content:
        return ""

    if content_type == "text/html":
        return sanitize_html(raw_content)

    if content_type == "application/json":
        return _format_json_transcript(raw_content)

    # text/plain or unknown — check for speaker format
    if "- [" in raw_content:
        return format_transcript_html(raw_content)

    # Plain text: wrap paragraphs in <p> tags
    paragraphs = raw_content.strip().split("\n\n")
    html_parts = []
    for para in paragraphs:
        text = para.strip()
        if text:
            html_parts.append(f"<p>{html.escape(text)}</p>")
    return "\n".join(html_parts)


def _format_json_transcript(raw_json: str) -> str:
    """Parse Podcasting 2.0 JSON transcript into HTML.

    JSON format has segments like:
    {"segments": [{"speaker": "Name", "body": "text", "startTime": 0.0}, ...]}
    or a flat array of segments.

    Groups consecutive segments from the same speaker into single paragraphs.

    Args:
        raw_json: Raw JSON transcript string.

    Returns:
        HTML formatted transcript.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON transcript: {e}")
        return f"<p>{html.escape(raw_json[:500])}</p>"

    # Handle both {"segments": [...]} and bare array
    if isinstance(data, dict):
        segments = data.get("segments", [])
    elif isinstance(data, list):
        segments = data
    else:
        return ""

    if not segments:
        return ""

    # Group consecutive segments by speaker
    html_parts = []
    current_speaker = None
    current_texts = []

    for seg in segments:
        speaker = seg.get("speaker", "")
        body = seg.get("body", "")
        if not body:
            continue

        if speaker != current_speaker:
            # Flush previous speaker's text
            if current_texts:
                text = " ".join(current_texts)
                if current_speaker:
                    html_parts.append(
                        f"<p><strong>{html.escape(current_speaker)}:</strong> {html.escape(text)}</p>"
                    )
                else:
                    html_parts.append(f"<p>{html.escape(text)}</p>")
            current_speaker = speaker
            current_texts = [body]
        else:
            current_texts.append(body)

    # Flush final speaker
    if current_texts:
        text = " ".join(current_texts)
        if current_speaker:
            html_parts.append(
                f"<p><strong>{html.escape(current_speaker)}:</strong> {html.escape(text)}</p>"
            )
        else:
            html_parts.append(f"<p>{html.escape(text)}</p>")

    return "\n".join(html_parts)


def build_transcript_section_html(transcript_html: str) -> str:
    """Wrap formatted transcript HTML in the standard Ghost card section.

    Args:
        transcript_html: Pre-formatted transcript HTML content.

    Returns:
        Complete Ghost HTML card with transcript section.
    """
    return (
        '<!--kg-card-begin: html-->\n'
        '<div id="episode-transcript" class="episode-transcript">\n'
        '<h2>Transcript</h2>\n'
        f'{transcript_html}\n'
        '</div>\n'
        '<!--kg-card-end: html-->'
    )


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
    transcript_html: Optional[str] = None,
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
        transcript: Optional raw transcript text (from local cache).
        peaks_url: Optional URL to pre-generated peaks JSON for Wavesurfer.
        ghost_audio_url: Optional Ghost-hosted audio URL (avoids CORS).
        ghost_image_url: Optional Ghost-hosted image URL for artwork.
        transcript_html: Optional pre-formatted transcript HTML (from RSS).
            Takes priority over raw transcript text.

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

    # 4. Transcript section — prefer pre-formatted HTML (from RSS), fall back to raw text (from cache)
    if transcript_html:
        sections.append(build_transcript_section_html(transcript_html))
    elif transcript and not is_placeholder_transcript(transcript):
        formatted = format_transcript_html(transcript)
        sections.append(build_transcript_section_html(formatted))

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
    transcript_html: Optional[str] = None,
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
        transcript_html=transcript_html,
    )

    # Show tag (public) + episode categories as internal tags
    tags = build_tags(episode, primary_tag='Luminous')

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
    transcript_html: Optional[str] = None,
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
        transcript_html: Optional pre-formatted transcript HTML from RSS.

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

    # Transcript section (from RSS <podcast:transcript>)
    if transcript_html:
        sections.append(build_transcript_section_html(transcript_html))

    return "\n".join(sections)


# Tags that remain public (used for Ghost collection routing).
# All other tags are made internal with a '#' prefix.
PUBLIC_SHOW_TAGS = {"Wonder Cabinet", "Luminous"}


def build_tags(
    episode: Episode,
    primary_tag: str = "TTBOOK",
) -> list[dict]:
    """Build Ghost tags array with show tag (public) and category tags (internal).

    The primary show tag (e.g., 'Wonder Cabinet', 'Luminous') stays public
    for Ghost collection routing. All other tags derived from RSS categories
    are prefixed with '#' to make them internal (hidden from public UI but
    usable for filtering in Ghost Admin).

    RSS categories are also preserved in JSON-LD structured data via
    codeinjection_head for SEO value.

    Args:
        episode: Parsed Episode object with categories from RSS.
        primary_tag: The show tag to include (e.g., 'Wonder Cabinet', 'Luminous').

    Returns:
        List of tag dicts in Ghost API format. Show tag is always first.
    """
    tags = [{"name": primary_tag}]

    # Add episode categories as internal tags
    for category in episode.categories:
        cat = category.strip()
        if not cat:
            continue
        # Skip if the category duplicates the show tag (case-insensitive)
        if cat.lower() == primary_tag.lower():
            continue
        # All non-show tags become internal with '#' prefix
        if cat not in PUBLIC_SHOW_TAGS:
            tags.append({"name": f"#{cat}"})
        else:
            tags.append({"name": cat})

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
    primary_tag: str = "Wonder Cabinet",
    feed_type: str = "ttbook",
    peaks_url: Optional[str] = None,
    ghost_audio_url: Optional[str] = None,
    ghost_image_url: Optional[str] = None,
    og_image_url: Optional[str] = None,
    transcript_html: Optional[str] = None,
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
        transcript_html: Optional pre-formatted transcript HTML from RSS.

    Returns:
        GhostPost ready for Ghost API.
    """
    logger.info(f"Building Ghost post for: {episode.title}")

    # Build HTML content
    html_content = build_post_html(
        episode, feed_type=feed_type, peaks_url=peaks_url,
        ghost_audio_url=ghost_audio_url, ghost_image_url=ghost_image_url,
        transcript_html=transcript_html,
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
