"""HTML content generation for Ghost posts from podcast episodes."""

from __future__ import annotations

import base64
import html
import json
import logging
import re
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


def format_episode_links(description_html: str) -> str:
    """Transform episode resource links for proper WC-Episode theme styling.

    PRX episode descriptions contain links in plain <ul> elements. This function:
    1. Detects <ul> elements containing episode resource links
    2. Adds class="wc-episode-notes-content-links" for CSS styling
    3. Adds target="_blank" rel="noopener noreferrer" to links
    4. Wraps in Ghost HTML card markers to prevent Lexical conversion

    Args:
        description_html: Sanitized episode description HTML.

    Returns:
        HTML with properly formatted episode links.

    Example:
        Input:
            <ul>
            <li>Link text: <a href="..."><strong>URL</strong></a></li>
            </ul>

        Output:
            <!--kg-card-begin: html-->
            <ul class="wc-episode-notes-content-links">
            <li><a href="..." target="_blank" rel="noopener noreferrer">Link text</a></li>
            </ul>
            <!--kg-card-end: html-->
    """
    # Pattern to match <ul>...</ul> blocks that contain links
    ul_pattern = re.compile(
        r'<ul>\s*((?:<li>.*?</li>\s*)+)</ul>',
        re.DOTALL | re.IGNORECASE
    )

    # Pattern for detecting bare URLs (no <a> wrapper)
    bare_url_pattern = re.compile(r'https?://[^\s<>"]+')

    # Patterns for smart link text splitting (quoted titles, curly quotes)
    quoted_pattern = re.compile(r'["\u201c](.+?)["\u201d]')

    def _split_link_text(text: str) -> tuple[str, str, str]:
        """Split descriptive text into (prefix, link_label, suffix).

        Instead of hyperlinking the entire text, identifies the most
        meaningful short portion to link:
        - Quoted titles: 'Pre-order "The Book" on sale' → ('Pre-order ', '"The Book"', ' on sale')
        - Colon-separated names: 'Program Name: long description' → ('', 'Program Name', ': long description')
        - Short text (≤ 60 chars): link everything

        Returns:
            Tuple of (prefix_text, link_label, suffix_text).
        """
        if len(text) <= 60:
            return ('', text, '')

        # Quoted text: link just the quoted portion (handles book titles, etc.)
        qm = quoted_pattern.search(text)
        if qm:
            return (text[:qm.start()], text[qm.start():qm.end()], text[qm.end():])

        # Colon separator: link the name/title before the colon
        colon_idx = text.find(':')
        if 0 < colon_idx <= 50:
            return ('', text[:colon_idx], text[colon_idx:])

        # Fallback: link everything
        return ('', text, '')

    def _format_smart_li(href: str, text: str) -> str:
        """Format a <li> with smart link text splitting."""
        prefix, label, suffix = _split_link_text(text)
        link = f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'
        return f'<li>{prefix}{link}{suffix}</li>'

    def transform_list(match: re.Match) -> str:
        """Transform a matched <ul> block."""
        list_content = match.group(1)

        # Check if this list contains links (either <a> tags or bare URLs)
        has_link_tags = '<a href=' in list_content.lower()
        has_bare_urls = bool(bare_url_pattern.search(list_content))

        if not has_link_tags and not has_bare_urls:
            return match.group(0)

        # Transform each <li> item
        li_pattern = re.compile(
            r'<li>\s*(.*?)\s*</li>',
            re.DOTALL | re.IGNORECASE
        )

        def transform_li(li_match: re.Match) -> str:
            """Transform a single <li> element."""
            content = li_match.group(1).strip()

            # Extract URL from existing <a> tag
            href_match = re.search(r'<a\s+href=["\']([^"\']+)["\']', content, re.IGNORECASE)
            if href_match:
                href = href_match.group(1)

                # Extract the descriptive text (everything before the URL display)
                text_without_link = re.sub(r'<a\s+[^>]*>.*?</a>', '', content, flags=re.DOTALL | re.IGNORECASE)
                text_without_link = re.sub(r'<strong>|</strong>', '', text_without_link)
                text_without_link = text_without_link.strip().rstrip(':').strip()

                # Check if remaining text is just punctuation/suffix (source name was inside the <a> tag)
                stripped_remaining = text_without_link.lstrip()
                if not stripped_remaining or stripped_remaining[0:1] in '—–-:,':
                    inner_match = re.search(r'<a\s+[^>]*>(.*?)</a>', content, re.DOTALL | re.IGNORECASE)
                    if inner_match:
                        source_name = re.sub(r'<[^>]+>', '', inner_match.group(1)).strip()
                        if source_name:
                            suffix = text_without_link.strip()
                            # Clean up leading punctuation for display
                            if suffix and suffix[0] in '—–-':
                                suffix = ' ' + suffix  # ensure space before emdash
                            link = f'<a href="{href}" target="_blank" rel="noopener noreferrer">{source_name}</a>'
                            return f'<li>{link}{suffix}</li>'

                if text_without_link:
                    link_text = text_without_link
                else:
                    inner_match = re.search(r'<a\s+[^>]*>(.*?)</a>', content, re.DOTALL | re.IGNORECASE)
                    if inner_match:
                        link_text = re.sub(r'<[^>]+>', '', inner_match.group(1)).strip()
                    else:
                        link_text = href

                return _format_smart_li(href, link_text)

            # No <a> tag — check for bare URLs
            url_match = bare_url_pattern.search(content)
            if url_match:
                url = url_match.group(0)
                # Use text before the URL as link text (strip trailing colon/whitespace)
                text_before = content[:url_match.start()].strip().rstrip(':').strip()
                link_text = text_before if text_before else url
                return _format_smart_li(url, link_text)

            return f'<li>{content}</li>'

        transformed_items = li_pattern.sub(transform_li, list_content)

        # Wrap in styled <ul> with Ghost HTML card markers
        return (
            '<!--kg-card-begin: html-->\n'
            '<ul class="wc-episode-notes-content-links">\n'
            f'{transformed_items}'
            '</ul>\n'
            '<!--kg-card-end: html-->'
        )

    return ul_pattern.sub(transform_list, description_html)


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
# Email CTA (for email subscribers who can't see the web audio player)
# =============================================================================

def build_email_cta_html(post_url: str) -> str:
    """Build an email-only CTA block for newsletter subscribers.

    Email subscribers can't see the web audio player, so this provides
    a styled "Listen to this episode" link that takes them to the web post.
    Matches the style used in the manually-polished Rovelli post.

    Args:
        post_url: Full URL to the Ghost post.

    Returns:
        HTML string with Ghost card markers (visibility applied via Lexical post-processing).
    """
    safe_url = html.escape(post_url, quote=True)
    return (
        '<!--kg-card-begin: html-->\n'
        '<div class="wc-email-cta" style="text-align: center; margin: 24px 0;">'
        f'<a href="{safe_url}" '
        'style="display: inline-block; padding: 12px 24px; background-color: #10a544; '
        'color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: 600;">'
        'Listen to this episode</a></div>\n'
        '<!--kg-card-end: html-->'
    )


# =============================================================================
# Lexical Visibility Controls
# =============================================================================

# Ghost Lexical visibility: web-only (hidden from email newsletters)
VISIBILITY_WEB_ONLY = {
    "web": {"nonMember": True, "memberSegment": "status:free,status:-free"},
    "email": {"memberSegment": ""},
}

# Ghost Lexical visibility: email-only (hidden from web)
VISIBILITY_EMAIL_ONLY = {
    "web": {"nonMember": False, "memberSegment": ""},
    "email": {"memberSegment": "status:free,status:-free"},
}

# Content markers used to identify nodes during Lexical post-processing
_LEXICAL_WEB_ONLY_MARKERS = ["wc-audio-player", "episode-transcript"]
_LEXICAL_EMAIL_ONLY_MARKERS = ["wc-email-cta"]


def _is_timestamp_node(child: dict) -> bool:
    """Check if a Lexical node is a chapter timestamp block.

    Detects paragraph nodes where all text children are HH:MM:SS timestamps,
    separated by linebreaks. These slip through HTML-level stripping when
    the API returns chapters as newline-separated text in a single paragraph.
    """
    import re
    timestamp_re = re.compile(r'^\d{2}:\d{2}:\d{2}\s+')
    text_children = [
        c for c in child.get("children", [])
        if c.get("type") not in ("linebreak",)
    ]
    if not text_children:
        return False
    return all(
        timestamp_re.match(c.get("text", ""))
        for c in text_children
        if c.get("text")
    ) and any(c.get("text") for c in text_children)


def process_lexical_visibility(lexical_str: str) -> str:
    """Apply visibility controls and cleanup to Lexical JSON nodes.

    Walks the Lexical root children and:
    1. Removes chapter timestamp nodes that slipped through HTML stripping
    2. Sets visibility based on content markers:
       - Audio player (wc-audio-player): web-only
       - Email CTA (wc-email-cta): email-only
       - Transcript (episode-transcript): web-only

    Args:
        lexical_str: Raw Lexical JSON string from Ghost.

    Returns:
        Modified Lexical JSON string with visibility applied.
    """
    lexical = json.loads(lexical_str)
    children = lexical.get("root", {}).get("children", [])

    # Remove chapter timestamp nodes
    children[:] = [c for c in children if not _is_timestamp_node(c)]

    for child in children:
        child_html = child.get("html", "")
        if not child_html:
            continue

        # Check for web-only markers
        for marker in _LEXICAL_WEB_ONLY_MARKERS:
            if marker in child_html:
                child["visibility"] = VISIBILITY_WEB_ONLY
                break
        else:
            # Check for email-only markers
            for marker in _LEXICAL_EMAIL_ONLY_MARKERS:
                if marker in child_html:
                    child["visibility"] = VISIBILITY_EMAIL_ONLY
                    break

    return json.dumps(lexical)


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
    """Load transcript from TTBOOK cache or canonical episode folder.

    Args:
        slug: Episode slug (e.g., 'luminous-melissa-etheridge-ayahuasca')
        cache_dir: Path to cache directory or canonical episode folder.
            If the directory contains a transcript.txt, loads it directly.
            Otherwise falls back to {slug}_transcript.txt naming convention.
            Defaults to sample-data/ttbook-cache/luminous.

    Returns:
        Transcript text or None if not found.
    """
    if cache_dir is None:
        # Default to project sample-data
        cache_dir = Path(__file__).parent.parent / 'sample-data' / 'ttbook-cache' / 'luminous'

    # Canonical episode folder: prefer formatted_transcript.md (speaker attribution)
    formatted_md = cache_dir / 'formatted_transcript.md'
    if formatted_md.exists():
        logger.info(f"Found formatted transcript: {formatted_md}")
        return formatted_md.read_text()

    # Fallback to plain transcript.txt
    canonical = cache_dir / 'transcript.txt'
    if canonical.exists():
        logger.info(f"Found canonical transcript: {canonical}")
        return canonical.read_text()

    # Legacy naming convention
    transcript_file = cache_dir / f'{slug}_transcript.txt'
    if transcript_file.exists():
        return transcript_file.read_text()
    return None


def load_wc_transcript(episode_title: str, transcript_dir: Optional[Path] = None) -> Optional[str]:
    """Load Wonder Cabinet transcript from local transcripts directory.

    Looks for transcript files matching the episode title pattern.
    Files should be named like: 101_Sophie_Strand.txt, 102_Carlo_Rovelli.txt

    When transcript_dir points to a canonical episode folder containing
    transcript.txt, loads it directly without fuzzy matching.

    Args:
        episode_title: Episode title to search for (partial match on name).
        transcript_dir: Path to transcripts directory or canonical episode folder.
            Defaults to project /transcripts.

    Returns:
        Transcript text or None if not found.
    """
    if transcript_dir is None:
        transcript_dir = Path(__file__).parent.parent / 'transcripts'

    if not transcript_dir.exists():
        return None

    # Canonical episode folder: prefer formatted_transcript.md (speaker attribution)
    formatted_md = transcript_dir / 'formatted_transcript.md'
    if formatted_md.exists():
        logger.info(f"Found formatted transcript: {formatted_md}")
        return formatted_md.read_text()

    # Fallback to plain transcript.txt
    canonical = transcript_dir / 'transcript.txt'
    if canonical.exists():
        logger.info(f"Found canonical transcript: {canonical}")
        return canonical.read_text()

    # Extract a key name from the title for matching
    # E.g., "Sophie Strand: Ecological Storytelling..." -> "Sophie Strand"
    # E.g., "Carlo Rovelli: Cosmic Mysteries..." -> "Carlo Rovelli"
    title_parts = episode_title.split(':')
    guest_name = title_parts[0].strip() if title_parts else episode_title

    # Look for subdirectories matching guest name, prefer formatted_transcript.md
    for subdir in transcript_dir.iterdir():
        if subdir.is_dir():
            subdir_name_normalized = subdir.name.replace('_', ' ')
            if guest_name.lower() in subdir_name_normalized.lower():
                # Try formatted_transcript.md first
                formatted_subdir = subdir / 'formatted_transcript.md'
                if formatted_subdir.exists():
                    logger.info(f"Found formatted transcript in subdir: {formatted_subdir}")
                    return formatted_subdir.read_text()
                # Fallback to any .txt file in matching subdir
                for txt_file in subdir.glob('*.txt'):
                    logger.info(f"Found transcript in subdir: {txt_file}")
                    return txt_file.read_text()

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


def _strip_transcript_metadata(text: str) -> str:
    """Strip frontmatter and postscript from a formatted transcript.

    Formatted transcripts have a consistent structure:
    - Frontmatter: title, episode metadata, followed by ---
    - Body: the actual dialogue
    - Postscript: --- followed by status field and formatting notes

    This extracts only the dialogue body between the first and last
    --- separators. If no separators exist, returns the text unchanged.
    """
    parts = re.split(r'^---\s*$', text, flags=re.MULTILINE)
    if len(parts) >= 3:
        # Has both frontmatter and postscript — take the middle
        return '\n'.join(parts[1:-1]).strip()
    if len(parts) == 2:
        # Has only one separator — frontmatter or postscript
        # If the first part looks like metadata (short, has **Key:** lines),
        # take the second part; otherwise take the first
        if re.search(r'^\*\*(Episode|Guest|Hosts|Duration|Status):\*\*', parts[0], re.MULTILINE):
            return parts[1].strip()
        return parts[0].strip()
    return text.strip()


def format_transcript_html(transcript: str) -> str:
    """Convert transcript text to HTML with speaker formatting.

    Handles two formats:
    - Markdown (formatted_transcript.md): **Speaker:** dialogue, # headings, ---
    - Plain text (transcript.txt): - [Speaker] dialogue

    For markdown transcripts, strips frontmatter (title, episode metadata)
    and postscript (status, formatting notes) before rendering.

    Args:
        transcript: Raw transcript text with speaker attributions.

    Returns:
        HTML formatted transcript.
    """
    if not transcript:
        return ''

    # Detect markdown format: has **bold** speaker attributions or # headings
    if re.search(r'^\*\*[^*]+:\*\*', transcript, re.MULTILINE) or transcript.startswith('#'):
        import markdown
        body = _strip_transcript_metadata(transcript)
        return markdown.markdown(body)

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


def slugify_title(title: str) -> str:
    """Generate a URL-safe slug from an episode title.

    Mirrors Ghost's default slug generation: lowercase, hyphens for spaces,
    strip non-alphanumeric characters, collapse multiple hyphens.

    Args:
        title: Episode title string.

    Returns:
        URL-safe slug (e.g., 'rebecca-solnit-hope-after-the-end').
    """
    slug = title.lower().strip()
    # Remove common prefixes that Ghost would also strip
    slug = re.sub(r'^(wonder cabinet|luminous):\s*', '', slug)
    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Collapse multiple hyphens and strip leading/trailing
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


# Generic path segments that indicate the link has no episode-specific slug
_GENERIC_SLUGS = {"listen", "episode", "episodes", "show", "podcast", "player", "embed"}


def extract_slug_from_link(link: str, title: str = "") -> Optional[str]:
    """Extract episode slug from episode link, with title fallback.

    For RSS-sourced episodes, the link typically contains a slug-friendly path
    (e.g., ttbook.org/show/episode-name). For API-sourced episodes, the link
    may be a generic player URL (e.g., play.prx.org/listen) — in that case,
    falls back to generating a slug from the episode title.

    Args:
        link: Episode URL.
        title: Episode title (used as fallback for slug generation).

    Returns:
        Slug string or None.
    """
    if link:
        path = urllib.parse.urlparse(link).path
        parts = path.strip('/').split('/')
        if parts:
            candidate = parts[-1]
            # Only use the link-derived slug if it looks episode-specific
            if candidate and candidate not in _GENERIC_SLUGS:
                return candidate

    # Fallback: generate slug from title
    if title:
        return slugify_title(title)
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

def strip_html_tags(text: str) -> str:
    """Remove HTML tags from text, returning plain text.

    Args:
        text: Text that may contain HTML tags.

    Returns:
        Plain text with HTML tags removed.
    """
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    clean = html.unescape(clean)
    # Normalize whitespace
    clean = ' '.join(clean.split())
    return clean.strip()


def build_jsonld_metadata(
    episode: "Episode",
    show_name: str,
    ghost_url: Optional[str] = None,
    post_slug: Optional[str] = None,
    url_prefix: Optional[str] = None,
) -> str:
    """Generate JSON-LD structured data for SEO.

    Stores episode categories and metadata in Schema.org format,
    keeping them out of Ghost's tag system while preserving SEO value.

    Schema.org PodcastEpisode type provides rich results in search engines,
    including podcast-specific features like episode duration and series info.

    Args:
        episode: Parsed Episode object with metadata.
        show_name: Name of the podcast series (e.g., 'Luminous', 'Wonder Cabinet').
        ghost_url: Base Ghost site URL (e.g., 'https://wondercabinetproductions.com').
            When provided with post_slug, generates canonical URL to Ghost post.
        post_slug: Ghost post slug. Used with ghost_url to build canonical URL.
        url_prefix: Optional path prefix for the URL (e.g., 'luminous' for
            Luminous episodes living at /luminous/{slug}/).

    Returns:
        HTML script tag containing JSON-LD structured data for injection
        into Ghost's codeinjection_head field.
    """
    # Use subtitle (short summary) for description, not full HTML content
    # Strip any HTML tags to ensure clean plain text
    description = strip_html_tags(episode.subtitle) if episode.subtitle else None

    # Build canonical URL: prefer Ghost site URL over RSS link
    if ghost_url and post_slug:
        base = ghost_url.rstrip('/')
        if url_prefix:
            canonical_url = f"{base}/{url_prefix.strip('/')}/{post_slug}/"
        else:
            canonical_url = f"{base}/{post_slug}/"
    else:
        canonical_url = episode.link  # Fallback to RSS link

    # Only include keywords if there are actual categories
    keywords = episode.categories if episode.categories else None

    schema = {
        "@context": "https://schema.org",
        "@type": "PodcastEpisode",
        "name": episode.title,
        "description": description,
        "partOfSeries": {
            "@type": "PodcastSeries",
            "name": show_name
        },
        "keywords": keywords,
        "datePublished": episode.pub_date.isoformat() if episode.pub_date else None,
        "duration": f"PT{episode.duration}S" if episode.duration and episode.duration.isdigit() else None,
        "url": canonical_url,
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
    ghost_url: Optional[str] = None,
    post_slug: Optional[str] = None,
) -> str:
    """Build HTML content for a Luminous episode post.

    Template structure:
    1. HTML5 audio player (theme-stylable, web-only via Lexical visibility)
    2. Email CTA link (email-only via Lexical visibility)
    3. Episode description (from content:encoded, boilerplate stripped)
    4. Transcript section (web-only via Lexical visibility)

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
        ghost_url: Ghost site URL for building email CTA link.
        post_slug: Post slug for building email CTA link.

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

    # 2. Email CTA — "Listen to this episode" link for email subscribers
    if ghost_url and post_slug:
        cta_url = f"{ghost_url.rstrip('/')}/luminous/{post_slug}/"
        sections.append(build_email_cta_html(cta_url))

    # 3. Episode description (from content:encoded, with boilerplate stripped and sanitized)
    if episode.description:
        description = strip_boilerplate(episode.description, 'luminous')
        description = sanitize_html(description)
        description = format_episode_links(description)
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
    ghost_url: Optional[str] = None,
    post_slug: Optional[str] = None,
) -> GhostPost:
    """Build a GhostPost for a Luminous episode.

    Field mapping:
    - Title: Episode title with 'Luminous: ' prefix removed
    - custom_excerpt: itunes:subtitle (short summary)
    - feature_image: Episode-specific itunes:image
    - canonical_url: Ghost site /luminous/{slug}/ (or ttbook.org fallback)
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
        ghost_url: Base Ghost site URL for canonical URL generation.
        post_slug: Ghost post slug for canonical URL generation.

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
        ghost_url=ghost_url, post_slug=post_slug,
    )

    # Show tag (public) + episode categories as internal tags
    tags = build_tags(episode, primary_tag='Luminous')

    # Build JSON-LD structured data (preserves categories for SEO)
    # Luminous episodes live at /luminous/{slug}/
    jsonld = build_jsonld_metadata(
        episode,
        show_name="Luminous",
        ghost_url=ghost_url,
        post_slug=post_slug,
        url_prefix="luminous",
    )

    # Use subtitle as custom_excerpt (Ghost limit is 300 chars)
    excerpt = episode.subtitle
    if excerpt and len(excerpt) > 300:
        excerpt = excerpt[:297] + '...'

    # Build canonical URL: prefer Ghost site URL with /luminous/ prefix
    if ghost_url and post_slug:
        canonical_url = f"{ghost_url.rstrip('/')}/luminous/{post_slug}/"
    else:
        canonical_url = episode.link  # Fallback to ttbook.org

    return GhostPost(
        title=title,
        html=html_content,
        status=status,
        published_at=None,  # Let Ghost use import time (PRX dates can be in the future)
        feature_image=ghost_image_url or episode.image_url,  # Prefer Ghost-hosted
        custom_excerpt=excerpt,  # From itunes:subtitle
        canonical_url=canonical_url,
        tags=tags,
        authors=FEED_AUTHORS.get("luminous", []),
        og_image=og_image_url,
        twitter_image=og_image_url,
        codeinjection_head=jsonld,
        feature_image_alt=episode.image_alt or None,
        feature_image_caption=episode.image_caption or None,
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
    ghost_url: Optional[str] = None,
    post_slug: Optional[str] = None,
    url_prefix: Optional[str] = None,
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
        ghost_url: Ghost site URL for building email CTA link.
        post_slug: Post slug for building email CTA link.
        url_prefix: Optional path prefix (e.g., 'luminous').

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

    # Email CTA — "Listen to this episode" link for email subscribers
    if ghost_url and post_slug:
        base = ghost_url.rstrip('/')
        if url_prefix:
            cta_url = f"{base}/{url_prefix.strip('/')}/{post_slug}/"
        else:
            cta_url = f"{base}/{post_slug}/"
        sections.append(build_email_cta_html(cta_url))

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
    ghost_url: Optional[str] = None,
    post_slug: Optional[str] = None,
    url_prefix: Optional[str] = None,
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
        ghost_url: Base Ghost site URL (e.g., 'https://wondercabinetproductions.com').
            Used to build canonical URL for JSON-LD schema.
        post_slug: Ghost post slug. Used with ghost_url to build canonical URL.
        url_prefix: Optional path prefix for URL (e.g., 'luminous' for /luminous/{slug}/).

    Returns:
        GhostPost ready for Ghost API.
    """
    logger.info(f"Building Ghost post for: {episode.title}")

    # Build HTML content
    html_content = build_post_html(
        episode, feed_type=feed_type, peaks_url=peaks_url,
        ghost_audio_url=ghost_audio_url, ghost_image_url=ghost_image_url,
        transcript_html=transcript_html,
        ghost_url=ghost_url, post_slug=post_slug, url_prefix=url_prefix,
    )

    # Build tags (show tag only - categories in JSON-LD)
    tags = build_tags(episode, primary_tag=primary_tag)

    # Build JSON-LD structured data (preserves categories for SEO)
    # Pass ghost_url and post_slug for canonical URL generation
    jsonld = build_jsonld_metadata(
        episode,
        show_name=primary_tag,
        ghost_url=ghost_url,
        post_slug=post_slug,
        url_prefix=url_prefix,
    )

    # Truncate excerpt if too long (Ghost limit is 300 chars)
    excerpt = episode.subtitle
    if excerpt and len(excerpt) > 300:
        excerpt = excerpt[:297] + "..."

    # Build the post
    authors = FEED_AUTHORS.get(feed_type, [])

    # Build canonical URL: prefer Ghost site URL if available
    if ghost_url and post_slug:
        base = ghost_url.rstrip('/')
        if url_prefix:
            canonical_url = f"{base}/{url_prefix.strip('/')}/{post_slug}/"
        else:
            canonical_url = f"{base}/{post_slug}/"
    else:
        canonical_url = episode.link if episode.link else None

    post = GhostPost(
        title=episode.title,
        html=html_content,
        status=status,
        published_at=None,  # Let Ghost use import time (PRX dates can be in the future)
        feature_image=ghost_image_url or episode.image_url or None,  # Prefer Ghost-hosted
        custom_excerpt=excerpt if excerpt else None,
        canonical_url=canonical_url,
        tags=tags,
        authors=authors,
        og_image=og_image_url,
        twitter_image=og_image_url,
        codeinjection_head=jsonld,
        feature_image_alt=episode.image_alt or None,
        feature_image_caption=episode.image_caption or None,
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
