"""Content transformation rules for stripping and replacing boilerplate content.

Each feed/podcast can define rules for:
1. Removing boilerplate text (leaves HTML comment markers)
2. Replacing sections with template content

The marker comments allow templates to inject replacement content later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class RemovalRule:
    """Rule for removing content from feed descriptions.

    Attributes:
        name: Identifier for this rule (e.g., 'about_luminous')
        pattern: Regex pattern to match content to remove
        marker_id: ID used in HTML comment marker (e.g., 'REMOVED:about_luminous')
        description: Human-readable description of what's being removed
    """
    name: str
    pattern: str
    marker_id: str
    description: str

    def apply(self, content: str) -> str:
        """Apply this removal rule to content.

        Returns content with matched text replaced by an HTML comment marker.
        """
        marker = f"<!-- REMOVED:{self.marker_id} -->"
        return re.sub(self.pattern, marker, content, flags=re.DOTALL | re.IGNORECASE)


@dataclass
class TitleRule:
    """Rule for transforming episode titles.

    Attributes:
        name: Identifier for this rule
        pattern: Regex pattern to match in title
        replacement: Replacement string (can use regex groups)
        description: Human-readable description
    """
    name: str
    pattern: str
    replacement: str
    description: str

    def apply(self, title: str) -> str:
        """Apply this title rule."""
        return re.sub(self.pattern, self.replacement, title).strip()


@dataclass
class FeedTransformConfig:
    """Configuration for content transforms for a specific feed.

    Attributes:
        feed_id: Identifier for this feed (e.g., 'luminous', 'ttbook')
        removal_rules: List of content removal rules to apply
        title_rules: List of title transformation rules
        custom_transforms: Optional list of custom transform functions
    """
    feed_id: str
    removal_rules: list[RemovalRule] = field(default_factory=list)
    title_rules: list[TitleRule] = field(default_factory=list)
    custom_transforms: list[Callable[[str], str]] = field(default_factory=list)

    def transform(self, content: str) -> str:
        """Apply all transforms to content."""
        result = content

        # Apply removal rules first
        for rule in self.removal_rules:
            result = rule.apply(result)

        # Apply custom transforms
        for transform_fn in self.custom_transforms:
            result = transform_fn(result)

        return result

    def transform_title(self, title: str) -> str:
        """Apply all title transforms."""
        result = title
        for rule in self.title_rules:
            result = rule.apply(result)
        return result


# =============================================================================
# Feed-specific configurations
# =============================================================================

# Luminous podcast boilerplate to remove
# This pattern handles both:
# 1. Original format with whitespace between tags
# 2. Ghost-converted format with id attributes and no whitespace
LUMINOUS_ABOUT_PATTERN = r'''<h3[^>]*>\s*About Luminous\s*</h3>\s*<p>\s*<em>Luminous</em>\s*is a podcast series from\s*<em>To The Best Of Our Knowledge</em>\s*featuring conversations about psychedelics with scientists,\s*healers and religious scholars\.?\s*Executive producer Steve Paulson\s*explores the philosophical and cultural implications\s*of the psychedelic renaissance\.?\s*</p>\s*<p>\s*For more from Luminous:\s*<a[^>]*>.*?ttbook\.org/luminous.*?</a>\s*</p>'''

# Comprehensive boilerplate pattern - removes everything from "Original Air Date" onwards:
# - Original Air Date line
# - Interviews In This Hour
# - Guests section with links
# - Subscribe to podcast/newsletter links
# - "For more from Luminous" link
# This pattern matches the entire boilerplate block at the end of content:encoded
LUMINOUS_FULL_BOILERPLATE = r'''<p><em>Original Air Date:[^<]*</em></p>.*$'''

# Simpler patterns as fallbacks
LUMINOUS_FOOTER_PATTERN = r'''<p>\s*<em>Original Air Date:[^<]*</em>\s*</p>\s*<p>\s*<br\s*/?>?\s*For more from Luminous[^<]*ttbook\.org/luminous[^<]*</p>'''
LUMINOUS_SIMPLE_FOOTER = r'''<p>\s*<br\s*/?>?\s*For more from Luminous[^<]*ttbook\.org/luminous[^<]*</p>'''

# Subscribe links pattern (catches standalone subscribe blocks)
LUMINOUS_SUBSCRIBE_PATTERN = r'''<p>\s*(?:<br\s*/?>?\s*)?<em>Never want to miss an episode\?</em>.*?Subscribe to our newsletter\.</a>\s*</p>'''

# "For more from Luminous" link pattern
LUMINOUS_MORE_PATTERN = r'''<p>\s*(?:<br\s*/?>?\s*)?For more from Luminous:?\s*<a[^>]*>.*?ttbook\.org/luminous.*?</a>\s*</p>'''

LUMINOUS_CONFIG = FeedTransformConfig(
    feed_id="luminous",
    removal_rules=[
        # First try the comprehensive pattern that removes all boilerplate at once
        RemovalRule(
            name="full_boilerplate",
            pattern=LUMINOUS_FULL_BOILERPLATE,
            marker_id="full_boilerplate",
            description="Removes all boilerplate from 'Original Air Date' onwards"
        ),
        # Fallback patterns for older/different formats
        RemovalRule(
            name="about_luminous",
            pattern=LUMINOUS_ABOUT_PATTERN,
            marker_id="about_luminous",
            description="Removes 'About Luminous' boilerplate section from episode descriptions"
        ),
        RemovalRule(
            name="luminous_footer",
            pattern=LUMINOUS_FOOTER_PATTERN,
            marker_id="luminous_footer",
            description="Removes footer with original air date and luminous link"
        ),
        RemovalRule(
            name="subscribe_links",
            pattern=LUMINOUS_SUBSCRIBE_PATTERN,
            marker_id="subscribe_links",
            description="Removes 'Never want to miss an episode' subscribe links"
        ),
        RemovalRule(
            name="more_from_luminous",
            pattern=LUMINOUS_MORE_PATTERN,
            marker_id="more_from_luminous",
            description="Removes 'For more from Luminous' link"
        ),
        RemovalRule(
            name="luminous_simple_footer",
            pattern=LUMINOUS_SIMPLE_FOOTER,
            marker_id="luminous_simple_footer",
            description="Removes simple 'For more from Luminous' footer"
        ),
    ],
    title_rules=[
        TitleRule(
            name="strip_luminous_prefix",
            pattern=r"^Luminous:\s*",
            replacement="",
            description="Removes 'Luminous: ' prefix from episode titles"
        ),
    ]
)

# Wonder Cabinet / TTBOOK boilerplate to remove

# Promotional footer - matches multiple variants:
# e.g., '<p>Visit <a href="https://wondercabinetproductions.com">...</a></p>'
# e.g., '<p>To follow Wonder Cabinet, sign up here: <a href="...">...</a></p>'
# e.g., '<p>If you love Wonder Cabinet, sign up ... <a href="...">...</a></p>'
# e.g., '<p>Find out more about the show at <a href="...">...</a>, where you can subscribe...</p>'
WC_PROMO_FOOTER = r'''<p>\s*(?:<br\s*/?>?\s*)?(?:Visit|To follow Wonder Cabinet|If you love Wonder Cabinet|Find out more about the show at)[^<]*<a[^>]*wondercabinetproductions\.com[^>]*>.*?</a>[^<]*</p>'''

# "keep your subscription active" paragraph
WC_SUBSCRIPTION_REMINDER = r'''<p>[^<]*keep your subscription active[^<]*</p>'''

# Dash dividers: <p>--</p> or <p>---</p> (with optional whitespace)
WC_DASH_DIVIDER = r'''<p>\s*-{2,}\s*</p>'''

# Single emdash divider: <p>—</p> (Unicode em dash, not ASCII dashes)
WC_EMDASH_DIVIDER = r'''<p>\s*[—\u2014]\s*</p>'''

# Chapters block format 1: a <p>Chapters:</p> heading followed by timestamped lines with <br>
# Matches: <p>Chapters:</p><p>00:00:00 Title<br>00:04:34 Title<br>...</p>
WC_CHAPTERS_BLOCK = r'''<p>\s*Chapters:\s*</p>\s*<p>\s*(?:\d{2}:\d{2}:\d{2}\s+[^<]+(?:<br\s*/?>?\s*)?)+\s*</p>'''

# Chapters format 2: Individual <p> tags for each timestamp (no Chapters: heading)
# Matches consecutive: <p>00:00:00 Title</p><p>00:04:10 Title</p>...
# Requires at least 2 consecutive timestamp paragraphs to avoid false positives
WC_TIMESTAMP_PARAGRAPHS = r'''(?:<p>\s*\d{2}:\d{2}:\d{2}\s+[^<]+</p>\s*){2,}'''

# Chapters format 3: MM:SS timestamps (shorter format without hours)
# Matches: <p>0:00 — Title</p> or <p>4:34 - Title</p>
WC_SHORT_TIMESTAMP_PARAGRAPHS = r'''(?:<p>\s*\d{1,2}:\d{2}\s*[—–\-]\s*.+?</p>\s*){2,}'''

# "Hosted by" closing line - remove the standard show credits
# e.g., '<p><em>Wonder Cabinet</em> is hosted by Anne Strainchamps and Steve Paulson.</p>'
WC_HOSTED_BY = r'''<p>\s*<em>Wonder Cabinet</em>\s+is hosted by[^<]*</p>'''


def _reformat_plain_text_links(content: str) -> str:
    """Reformat link elements where a plain-text title precedes a raw URL link.

    PRX descriptions often contain links formatted as:
      <p>Title text: <a href="URL"><strong>URL</strong></a></p>
      <li>Title text: <a href="URL"><strong>URL</strong></a></li>

    This transforms them into proper links with the title as the label:
      <p><a href="URL" target="_blank" rel="noopener noreferrer">Title text</a></p>
      <li><a href="URL" target="_blank" rel="noopener noreferrer">Title text</a></li>

    The colon at the end of the title text is stripped.
    """
    # Match both <p> and <li> elements
    # The title is everything before the last colon that precedes the <a> tag.
    pattern = re.compile(
        r'<(p|li)>\s*'                     # Opening <p> or <li> (tag name captured)
        r'([^<]+?)'                        # Title text (captured)
        r'[\s\xa0]*'                       # Optional whitespace/nbsp
        r'<a\s+href="([^"]+)"'            # <a href="URL">
        r'[^>]*>'                          # Rest of opening tag attributes
        r'\s*(?:<strong>)?\s*'             # Optional <strong>
        r'https?://[^<]*?'                # The displayed URL text
        r'\s*(?:</strong>)?\s*'            # Optional </strong>
        r'</a>'                            # Closing </a>
        r'(?:\s*\n)?'                      # Optional trailing newline
        r'\s*</\1>',                       # Closing tag matching opening
        re.IGNORECASE,
    )

    def _reformat_match(m: re.Match) -> str:
        tag = m.group(1)
        title = m.group(2).strip()
        url = m.group(3)
        # Strip trailing colon from title
        title = title.rstrip(':').rstrip()
        if not title:
            return m.group(0)  # No title text, leave unchanged
        return (
            f'<{tag}><a href="{url}" target="_blank" '
            f'rel="noopener noreferrer">{title}</a></{tag}>'
        )

    return pattern.sub(_reformat_match, content)


def _style_link_lists(content: str) -> str:
    """Add Wonder Cabinet styling class to all bulleted lists.

    Transforms <ul> elements into:
      <ul class="wc-episode-notes-content-links">...</ul>

    In Wonder Cabinet feeds, bulleted lists are always link lists for episode notes.
    """
    return re.sub(
        r'<ul>',
        '<ul class="wc-episode-notes-content-links">',
        content,
        flags=re.IGNORECASE,
    )


TTBOOK_CONFIG = FeedTransformConfig(
    feed_id="ttbook",
    removal_rules=[
        # Strip chapter blocks first (before dividers, so the surrounding
        # dividers are also caught by the divider rule)
        RemovalRule(
            name="wc_chapters",
            pattern=WC_CHAPTERS_BLOCK,
            marker_id="wc_chapters",
            description="Removes 'Chapters:' block with timestamps"
        ),
        # Strip individual timestamp paragraphs (alternative format)
        RemovalRule(
            name="wc_timestamps",
            pattern=WC_TIMESTAMP_PARAGRAPHS,
            marker_id="wc_timestamps",
            description="Removes consecutive timestamp paragraphs"
        ),
        # Strip short timestamp paragraphs (MM:SS format)
        RemovalRule(
            name="wc_short_timestamps",
            pattern=WC_SHORT_TIMESTAMP_PARAGRAPHS,
            marker_id="wc_short_timestamps",
            description="Removes consecutive MM:SS timestamp paragraphs"
        ),
        # Strip dash dividers (-- or ---)
        RemovalRule(
            name="wc_dividers",
            pattern=WC_DASH_DIVIDER,
            marker_id="wc_dividers",
            description="Removes <p>--</p> and <p>---</p> divider paragraphs"
        ),
        # Strip emdash dividers (single Unicode em dash)
        RemovalRule(
            name="wc_emdash_dividers",
            pattern=WC_EMDASH_DIVIDER,
            marker_id="wc_emdash_dividers",
            description="Removes <p>—</p> emdash divider paragraphs"
        ),
        # Strip "hosted by" credits line
        RemovalRule(
            name="wc_hosted_by",
            pattern=WC_HOSTED_BY,
            marker_id="wc_hosted_by",
            description="Removes 'Wonder Cabinet is hosted by...' line"
        ),
        # Strip promotional footer
        RemovalRule(
            name="wc_promo_footer",
            pattern=WC_PROMO_FOOTER,
            marker_id="wc_promo_footer",
            description="Removes promotional footer with wondercabinetproductions.com link"
        ),
        RemovalRule(
            name="wc_subscription_reminder",
            pattern=WC_SUBSCRIPTION_REMINDER,
            marker_id="wc_subscription_reminder",
            description="Removes 'keep your subscription active' paragraph"
        ),
    ],
    custom_transforms=[
        _reformat_plain_text_links,
        _style_link_lists,
    ],
)

# Registry of all feed configs
FEED_TRANSFORMS: dict[str, FeedTransformConfig] = {
    "luminous": LUMINOUS_CONFIG,
    "ttbook": TTBOOK_CONFIG,
}


def get_transform_config(feed_id: str) -> FeedTransformConfig | None:
    """Get transform configuration for a feed.

    Args:
        feed_id: Feed identifier (e.g., 'luminous', 'ttbook')

    Returns:
        FeedTransformConfig or None if no config exists
    """
    return FEED_TRANSFORMS.get(feed_id.lower())


def apply_transforms(content: str, feed_id: str) -> str:
    """Apply all transforms for a feed to content.

    Args:
        content: HTML content to transform
        feed_id: Feed identifier

    Returns:
        Transformed content with boilerplate removed/marked
    """
    config = get_transform_config(feed_id)
    if config:
        return config.transform(content)
    return content


def strip_boilerplate(content: str, feed_id: str) -> str:
    """Convenience alias for apply_transforms."""
    return apply_transforms(content, feed_id)


def transform_title(title: str, feed_id: str) -> str:
    """Apply title transforms for a feed.

    Args:
        title: Episode title to transform
        feed_id: Feed identifier

    Returns:
        Transformed title with prefixes/suffixes removed
    """
    config = get_transform_config(feed_id)
    if config:
        return config.transform_title(title)
    return title


# =============================================================================
# Utility functions
# =============================================================================

def find_markers(content: str) -> list[str]:
    """Find all REMOVED marker IDs in content.

    Returns list of marker IDs (e.g., ['about_luminous', 'footer_links'])
    """
    pattern = r'<!-- REMOVED:(\w+) -->'
    return re.findall(pattern, content)


def replace_marker(content: str, marker_id: str, replacement: str) -> str:
    """Replace a REMOVED marker with new content.

    Args:
        content: HTML content containing markers
        marker_id: Marker ID to replace (e.g., 'about_luminous')
        replacement: HTML to insert in place of marker

    Returns:
        Content with marker replaced
    """
    marker = f"<!-- REMOVED:{marker_id} -->"
    return content.replace(marker, replacement)


if __name__ == "__main__":
    # Test with sample Luminous content
    sample = '''<p>Episode description here.</p>

<h3>About Luminous</h3>
<p><em>Luminous</em> is a podcast series from <em>To The Best Of Our Knowledge</em> featuring conversations about psychedelics with scientists, healers and religious scholars. Executive producer Steve Paulson explores the philosophical and cultural implications of the psychedelic renaissance.</p>
<p>For more from Luminous: <a href="https://www.ttbook.org/luminous"><strong>ttbook.org/luminous</strong></a></p>

<p>More content after.</p>'''

    print("=== Original ===")
    print(sample)
    print()

    result = strip_boilerplate(sample, "luminous")

    print("=== After Transform ===")
    print(result)
    print()

    print("=== Found Markers ===")
    print(find_markers(result))
