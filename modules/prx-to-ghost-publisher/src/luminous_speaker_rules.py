"""Speaker attribution rules for Luminous podcast transcripts.

This module defines the speaker patterns and rules for reformatting
Luminous episode transcripts from bare dash format to properly
attributed speaker format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Known hosts for Luminous/TTBOOK
HOSTS = {
    "Steve",
    "Anne",
    "Steve Paulson",
    "Anne Strainchamps",
}

# Common short responses that typically come from the interviewer (Steve)
# when following a guest's statement
INTERVIEWER_RESPONSES = {
    "yeah",
    "yeah.",
    "yes",
    "yes.",
    "okay",
    "okay.",
    "oh",
    "oh.",
    "wow",
    "wow.",
    "right",
    "right.",
    "exactly",
    "exactly.",
    "hmm",
    "hmm.",
    "mm-hmm",
    "mm-hmm.",
    "interesting",
    "interesting.",
    "fascinating",
    "fascinating.",
    "really",
    "really?",
    "huh",
    "huh.",
}

# Common short responses that are likely from the guest
# when following the interviewer's question
GUEST_AFFIRMATIONS = {
    "yeah",
    "yeah.",
    "yes",
    "yes.",
    "exactly",
    "exactly.",
    "right",
    "right.",
    "correct",
    "correct.",
    "that's right",
    "that's right.",
    "that's correct",
    "that's correct.",
    "yep",
    "yep.",
}


@dataclass
class SpeakerContext:
    """Tracks speaker context for attribution decisions."""

    last_speaker: Optional[str] = None
    last_was_host: bool = False
    episode_guest: Optional[str] = None
    known_speakers: set = None  # All speakers seen in transcript
    last_non_host_speaker: Optional[str] = None  # Last guest who spoke

    def __post_init__(self):
        if self.known_speakers is None:
            self.known_speakers = set()

    def update(self, speaker: str) -> None:
        """Update context with new speaker."""
        self.last_speaker = speaker
        self.last_was_host = speaker in HOSTS or speaker in {"Steve", "Anne"}
        self.known_speakers.add(speaker)
        if not self.last_was_host:
            self.last_non_host_speaker = speaker


def extract_speaker_from_line(line: str) -> tuple[Optional[str], str]:
    """Extract speaker name from a formatted line.

    Args:
        line: HTML paragraph line from transcript

    Returns:
        Tuple of (speaker_name or None, remaining_content)
    """
    # Pattern: <p><strong>Speaker:</strong> content</p>
    match = re.match(
        r'<p><strong>([^:]+):</strong>\s*(.*?)</p>',
        line,
        re.IGNORECASE | re.DOTALL
    )
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # Pattern: <p>- content</p> (bare dash, no speaker)
    match = re.match(r'<p>-\s*(.*?)</p>', line, re.DOTALL)
    if match:
        return None, match.group(1).strip()

    # Plain paragraph
    match = re.match(r'<p>(.*?)</p>', line, re.DOTALL)
    if match:
        return None, match.group(1).strip()

    return None, line


def is_question(text: str) -> bool:
    """Check if text is likely a question."""
    # Strip HTML and check for question mark
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip().endswith('?')


def is_short_response(text: str) -> bool:
    """Check if text is a short interjection/response."""
    clean = re.sub(r'<[^>]+>', '', text).strip().lower()
    return len(clean) < 50 and (
        clean in INTERVIEWER_RESPONSES or
        clean in GUEST_AFFIRMATIONS or
        len(clean.split()) <= 3
    )


def infer_speaker(
    content: str,
    context: SpeakerContext,
    line_index: int,
    all_lines: list[str],
) -> str:
    """Infer speaker for a bare-dash line based on context.

    Uses conversational flow patterns to determine who is speaking:
    - Questions typically come from the host (interviewer)
    - Short affirmations after questions come from the guest
    - Short affirmations after guest statements come from the host
    - Alternating pattern in back-and-forth dialogue

    Args:
        content: The text content without speaker attribution
        context: Current speaker tracking context
        line_index: Index of current line in transcript
        all_lines: All lines for look-ahead context

    Returns:
        Inferred speaker name
    """
    content_lower = content.lower().strip()

    # Default host is Steve for Luminous
    default_host = "Steve"

    # If we don't have a last speaker, assume it's the host starting
    if context.last_speaker is None:
        return default_host

    # Short responses typically alternate
    if is_short_response(content):
        # If last speaker was host, this is likely guest
        if context.last_was_host:
            return context.episode_guest or context.last_speaker
        # If last speaker was guest, this is likely host (Steve)
        return default_host

    # Questions are typically from the host
    if is_question(content):
        return default_host

    # Longer statements: check if it continues the same speaker or alternates
    # If the previous was a question from Steve, this is likely the guest's answer
    if context.last_was_host:
        # Check if previous line was a question
        if line_index > 0:
            prev_speaker, prev_content = extract_speaker_from_line(all_lines[line_index - 1])
            if prev_speaker and prev_speaker in HOSTS and is_question(prev_content):
                return context.episode_guest or "Guest"

    # Default: alternate from last speaker
    if context.last_was_host:
        return context.episode_guest or context.last_speaker
    return default_host


def extract_guest_from_title(title: str) -> Optional[str]:
    """Extract guest name from episode title.

    Common patterns:
    - "Guest Name: Topic Discussion"
    - "Guest Name on Topic"
    - "Interview with Guest Name"

    Args:
        title: Episode title

    Returns:
        Guest first name or None
    """
    # Pattern: "Name: Topic" or "Name on Topic"
    match = re.match(r'^([A-Z][a-z]+ [A-Z][a-z]+?)(?:\s*[:\-]|\s+on\s+)', title)
    if match:
        full_name = match.group(1)
        # Return first name for transcript attribution
        return full_name.split()[0]

    # Pattern: "Firstname Lastname"
    match = re.match(r'^([A-Z][a-z]+)\s+([A-Z][a-z]+)', title)
    if match:
        return match.group(1)

    return None


# Episode-specific guest mappings for Luminous
# Key: episode slug, Value: primary guest first name
EPISODE_GUESTS = {
    "what-can-psychedelics-teach-us-about-dying": "Roland",  # Roland Griffiths + Lou Lukas + Tony Bossis
    "building-the-psychedelic-revolution": "Bill",  # Bill Linton + Alex Sherwood
    "melissa-etheridge-on-ayahuasca": "Melissa",
    "your-brain-on-shrooms": None,  # Multiple guests
    "octopus-on-mdma": "Gul",  # Gul Dolen
    "can-psychedelics-be-decolonized": None,  # Multiple guests
    "can-you-have-too-much-transcendence": "Jules",  # Jules Evans
    "is-it-the-drug-or-is-it-the-trip": None,  # Multiple guests
    "a-brief-history-of-getting-high": "Mike",  # Mike Jay
    "did-ancient-greeks-use-drugs-to-find-god": "Brian",  # Brian Muraresku
    "erik-davis-on-lsd": "Erik",  # Erik Davis
    "katherine-maclean": "Katherine",  # Katherine MacLean
    "do-psychedelics-reveal-deeper-dimension": None,  # Multiple guests
    "spring-washam-buddhist-shaman": "Spring",  # Spring Washam
    "chris-timmerman-how-dmt": "Chris",  # Chris Timmerman
    "marcelo-and-kari-gleiser": "Marcelo",  # Marcelo Gleiser + Kari Gleiser
    "thomas-metzinger": "Thomas",  # Thomas Metzinger
    "reclaiming-the-acid-queen": "Susannah",  # Susannah Cahalan
}


def get_episode_guest(slug: str, title: str) -> Optional[str]:
    """Get the primary guest name for an episode.

    Args:
        slug: Episode URL slug
        title: Episode title

    Returns:
        Guest first name or None
    """
    # Check explicit mapping first
    if slug in EPISODE_GUESTS:
        return EPISODE_GUESTS[slug]

    # Try to extract from title
    return extract_guest_from_title(title)
