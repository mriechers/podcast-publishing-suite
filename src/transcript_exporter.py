"""Transcript exporter for PRX-compatible formats.

Exports transcripts from TTBOOK cache to PRX-compatible formats (JSON, HTML, SRT, VTT)
for manual upload via PRX GUI or future API integration.

Supported formats:
- JSON: Podcasting 2.0 transcript JSON format with segments
- HTML: Simple HTML with speaker formatting
- SRT: SubRip subtitle format (basic, no timestamps from source)
- VTT: WebVTT format (basic, no timestamps from source)

Note: Since our source transcripts don't have timestamps, SRT/VTT outputs
use placeholder timings. JSON and HTML are recommended for PRX upload.
"""

import html as html_mod
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default transcript cache location
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "sample-data" / "ttbook-cache" / "luminous"

# Default export directory
DEFAULT_EXPORT_DIR = Path(__file__).parent.parent / "transcripts"


@dataclass
class TranscriptSegment:
    """A segment of transcript with speaker and text."""
    speaker: str
    text: str
    start_time: Optional[float] = None  # seconds
    end_time: Optional[float] = None  # seconds


@dataclass
class Transcript:
    """Parsed transcript with metadata."""
    segments: list[TranscriptSegment] = field(default_factory=list)
    episode_slug: str = ""
    episode_title: str = ""
    source_file: Optional[Path] = None

    @property
    def full_text(self) -> str:
        """Get full transcript as plain text."""
        return "\n\n".join(
            f"{seg.speaker}: {seg.text}" for seg in self.segments
        )

    @property
    def speakers(self) -> list[str]:
        """Get unique list of speakers."""
        seen = set()
        speakers = []
        for seg in self.segments:
            if seg.speaker not in seen:
                seen.add(seg.speaker)
                speakers.append(seg.speaker)
        return speakers


def parse_transcript_file(file_path: Path) -> Transcript:
    """Parse a TTBOOK transcript file into structured segments.

    Handles format: - [Speaker] Text content...

    Args:
        file_path: Path to transcript .txt file

    Returns:
        Parsed Transcript object
    """
    transcript = Transcript(source_file=file_path)

    # Extract slug from filename
    if file_path.name.endswith("_transcript.txt"):
        transcript.episode_slug = file_path.stem.replace("_transcript", "")

    content = file_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    current_speaker = "Unknown"
    current_text_parts = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for speaker attribution: - [Speaker]
        speaker_match = re.match(r'^-\s*\[([^\]]+)\]\s*(.*)$', line)

        if speaker_match:
            # Save previous segment if exists
            if current_text_parts:
                transcript.segments.append(TranscriptSegment(
                    speaker=current_speaker,
                    text=" ".join(current_text_parts)
                ))
                current_text_parts = []

            current_speaker = speaker_match.group(1)
            remaining_text = speaker_match.group(2).strip()
            if remaining_text:
                current_text_parts.append(remaining_text)
        else:
            # Continuation of previous speaker's text
            current_text_parts.append(line)

    # Don't forget the last segment
    if current_text_parts:
        transcript.segments.append(TranscriptSegment(
            speaker=current_speaker,
            text=" ".join(current_text_parts)
        ))

    logger.info(f"Parsed {len(transcript.segments)} segments from {file_path.name}")
    return transcript


def export_to_json(transcript: Transcript) -> str:
    """Export transcript to Podcasting 2.0 JSON format.

    Format spec: https://github.com/Podcastindex-org/podcast-namespace/blob/main/transcripts/transcripts.md

    Args:
        transcript: Parsed Transcript object

    Returns:
        JSON string in Podcasting 2.0 transcript format
    """
    output = {
        "version": "1.0.0",
        "segments": []
    }

    # Since we don't have timestamps, we'll estimate based on word count
    # Average speaking rate: ~150 words per minute
    words_per_second = 150 / 60
    current_time = 0.0

    for segment in transcript.segments:
        word_count = len(segment.text.split())
        duration = word_count / words_per_second

        output["segments"].append({
            "speaker": segment.speaker,
            "startTime": round(current_time, 2),
            "endTime": round(current_time + duration, 2),
            "body": segment.text
        })

        current_time += duration + 0.5  # Small gap between speakers

    return json.dumps(output, indent=2, ensure_ascii=False)


def export_to_html(transcript: Transcript) -> str:
    """Export transcript to HTML format.

    Creates a clean HTML document with speaker-attributed paragraphs.

    Args:
        transcript: Parsed Transcript object

    Returns:
        HTML string
    """
    lines = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '  <meta charset="UTF-8">',
        f'  <title>Transcript: {html_mod.escape(transcript.episode_title or transcript.episode_slug)}</title>',
        '  <style>',
        '    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; line-height: 1.6; }',
        '    .segment { margin-bottom: 1.5em; }',
        '    .speaker { font-weight: bold; color: #333; }',
        '    .text { margin-top: 0.25em; }',
        '  </style>',
        '</head>',
        '<body>',
    ]

    if transcript.episode_title:
        lines.append(f'  <h1>{html_mod.escape(transcript.episode_title)}</h1>')

    lines.append('  <div class="transcript">')

    for segment in transcript.segments:
        lines.append('    <div class="segment">')
        lines.append(f'      <p class="speaker">{html_mod.escape(segment.speaker)}:</p>')
        lines.append(f'      <p class="text">{html_mod.escape(segment.text)}</p>')
        lines.append('    </div>')

    lines.extend([
        '  </div>',
        '</body>',
        '</html>'
    ])

    return '\n'.join(lines)


def export_to_srt(transcript: Transcript) -> str:
    """Export transcript to SRT (SubRip) format.

    Note: Timestamps are estimated since source doesn't have them.

    Args:
        transcript: Parsed Transcript object

    Returns:
        SRT formatted string
    """
    lines = []
    words_per_second = 150 / 60
    current_time = 0.0

    for i, segment in enumerate(transcript.segments, 1):
        word_count = len(segment.text.split())
        duration = word_count / words_per_second

        start = format_srt_time(current_time)
        end = format_srt_time(current_time + duration)

        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(f"[{segment.speaker}] {segment.text}")
        lines.append("")  # Blank line between entries

        current_time += duration + 0.5

    return '\n'.join(lines)


def export_to_vtt(transcript: Transcript) -> str:
    """Export transcript to WebVTT format.

    Note: Timestamps are estimated since source doesn't have them.

    Args:
        transcript: Parsed Transcript object

    Returns:
        WebVTT formatted string
    """
    lines = ["WEBVTT", ""]
    words_per_second = 150 / 60
    current_time = 0.0

    for i, segment in enumerate(transcript.segments, 1):
        word_count = len(segment.text.split())
        duration = word_count / words_per_second

        start = format_vtt_time(current_time)
        end = format_vtt_time(current_time + duration)

        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(f"<v {segment.speaker}>{segment.text}")
        lines.append("")

        current_time += duration + 0.5

    return '\n'.join(lines)


def format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format seconds as WebVTT timestamp (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def export_transcript(
    transcript: Transcript,
    output_dir: Path,
    formats: list[str] = None,
) -> dict[str, Path]:
    """Export transcript to multiple formats.

    Args:
        transcript: Parsed Transcript object
        output_dir: Directory to write files to (will be created if needed)
        formats: List of formats to export ('json', 'html', 'srt', 'vtt')
                 Defaults to ['json', 'html']

    Returns:
        Dict mapping format name to output file path
    """
    if formats is None:
        formats = ['json', 'html']

    output_dir.mkdir(parents=True, exist_ok=True)

    exporters = {
        'json': (export_to_json, '.json'),
        'html': (export_to_html, '.html'),
        'srt': (export_to_srt, '.srt'),
        'vtt': (export_to_vtt, '.vtt'),
    }

    results = {}
    base_name = transcript.episode_slug or "transcript"

    for fmt in formats:
        if fmt not in exporters:
            logger.warning(f"Unknown format '{fmt}', skipping")
            continue

        exporter, ext = exporters[fmt]
        output_path = output_dir / f"{base_name}{ext}"

        content = exporter(transcript)
        output_path.write_text(content, encoding='utf-8')

        logger.info(f"Exported {fmt.upper()} to {output_path}")
        results[fmt] = output_path

    return results


def find_transcript_for_episode(
    episode_slug: str,
    episode_title: str = "",
    cache_dir: Path = None,
) -> Optional[Path]:
    """Find cached transcript file for an episode.

    Tries multiple matching strategies:
    1. Exact slug match
    2. With/without 'luminous-' prefix
    3. Fuzzy title matching

    Args:
        episode_slug: Episode slug from URL
        episode_title: Episode title for fuzzy matching
        cache_dir: Transcript cache directory

    Returns:
        Path to transcript file, or None if not found
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    if not cache_dir.exists():
        return None

    # Strategy 1: Exact slug match
    candidates = [
        cache_dir / f"{episode_slug}_transcript.txt",
        cache_dir / f"luminous-{episode_slug}_transcript.txt",
    ]

    # If slug starts with 'luminous-', also try without
    if episode_slug.startswith("luminous-"):
        candidates.append(cache_dir / f"{episode_slug[9:]}_transcript.txt")

    for path in candidates:
        if path.exists():
            return path

    # Strategy 2: Fuzzy matching on title
    if episode_title:
        title_normalized = re.sub(r'[^\w\s]', '', episode_title.lower())
        title_words = set(title_normalized.split())

        best_match = None
        best_score = 0

        for transcript_file in cache_dir.glob("*_transcript.txt"):
            file_slug = transcript_file.stem.replace("_transcript", "")
            file_normalized = re.sub(r'[^\w\s]', ' ', file_slug.lower().replace("-", " "))
            file_words = set(file_normalized.split())

            overlap = len(title_words & file_words)
            if overlap > best_score and overlap >= 2:
                best_score = overlap
                best_match = transcript_file

        return best_match

    return None


def export_episode_transcript(
    episode_slug: str,
    episode_title: str = "",
    episode_guid: str = "",
    cache_dir: Path = None,
    export_base_dir: Path = None,
    formats: list[str] = None,
) -> Optional[dict[str, Path]]:
    """Find and export transcript for an episode.

    This is the main entry point for the transcript export workflow.
    Creates a folder structure: transcripts/{episode_slug}/

    Args:
        episode_slug: Episode slug (from URL)
        episode_title: Episode title
        episode_guid: Episode GUID (for folder naming fallback)
        cache_dir: Source transcript cache directory
        export_base_dir: Base directory for exports (default: project/transcripts)
        formats: Export formats (default: ['json', 'html'])

    Returns:
        Dict of format -> path, or None if no transcript found
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    if export_base_dir is None:
        export_base_dir = DEFAULT_EXPORT_DIR
    if formats is None:
        formats = ['json', 'html']

    # Find the source transcript
    source_path = find_transcript_for_episode(episode_slug, episode_title, cache_dir)

    if source_path is None:
        logger.debug(f"No transcript found for episode: {episode_slug}")
        return None

    # Parse the transcript
    transcript = parse_transcript_file(source_path)
    transcript.episode_title = episode_title
    transcript.episode_slug = episode_slug

    # Create episode folder
    folder_name = episode_slug or episode_guid.replace(":", "_") or "unknown"
    episode_dir = export_base_dir / folder_name

    # Export to all requested formats
    results = export_transcript(transcript, episode_dir, formats)

    logger.info(f"Exported transcript for '{episode_title or episode_slug}' to {episode_dir}")

    return results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    parser = argparse.ArgumentParser(description="Export TTBOOK transcripts to PRX-compatible formats")
    parser.add_argument("--slug", required=True, help="Episode slug to export")
    parser.add_argument("--title", default="", help="Episode title")
    parser.add_argument("--formats", nargs="+", default=["json", "html"],
                        choices=["json", "html", "srt", "vtt"],
                        help="Output formats (default: json html)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EXPORT_DIR,
                        help="Base output directory")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
                        help="Transcript cache directory")

    args = parser.parse_args()

    results = export_episode_transcript(
        episode_slug=args.slug,
        episode_title=args.title,
        cache_dir=args.cache_dir,
        export_base_dir=args.output_dir,
        formats=args.formats,
    )

    if results:
        print(f"\nExported {len(results)} files:")
        for fmt, path in results.items():
            print(f"  {fmt.upper()}: {path}")
    else:
        print(f"No transcript found for slug: {args.slug}")
