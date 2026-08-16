#!/usr/bin/env python3
"""
Video Processor Module

Extracts transcripts from video URLs (YouTube, TikTok, Instagram) and generates
summaries. Supports optional archiving of video files.

Platform support:
- YouTube: Uses youtube-transcript-api (fast, no download needed)
- TikTok/Instagram: Uses yt-dlp + Whisper for local transcription

Whisper backends (configurable):
- mlx-whisper: Optimized for Apple Silicon (default on M-series Macs)
- faster-whisper: Cross-platform fallback

[Agent: Main Assistant]
"""

import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Archive location for videos tagged with #archive
VIDEO_ARCHIVE_PATH = Path(os.environ.get(
    "VIDEO_ARCHIVE_PATH",
    Path.home() / "Media" / "archived-videos"
))

# Whisper configuration
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")  # tiny, base, small, medium, large
WHISPER_BACKEND = os.environ.get("WHISPER_BACKEND", "auto")  # auto, mlx, faster-whisper

# Detect Apple Silicon
def _is_apple_silicon() -> bool:
    """Check if running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _get_whisper_backend() -> str:
    """Determine which Whisper backend to use."""
    if WHISPER_BACKEND != "auto":
        return WHISPER_BACKEND

    # Auto-detect: prefer mlx-whisper on Apple Silicon
    if _is_apple_silicon():
        try:
            import mlx_whisper
            return "mlx"
        except ImportError:
            pass

    # Fallback to faster-whisper
    try:
        import faster_whisper
        return "faster-whisper"
    except ImportError:
        pass

    return "none"


# =============================================================================
# Platform Detection
# =============================================================================

def detect_platform(url: str) -> Optional[str]:
    """Detect video platform from URL.

    Returns: 'youtube', 'tiktok', 'instagram', or None if not recognized.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # YouTube
    if any(yt in domain for yt in ['youtube.com', 'youtu.be', 'youtube-nocookie.com']):
        return 'youtube'

    # TikTok
    if 'tiktok.com' in domain or 'vm.tiktok.com' in domain:
        return 'tiktok'

    # Instagram
    if 'instagram.com' in domain or 'instagr.am' in domain:
        return 'instagram'

    return None


def is_video_url(url: str) -> bool:
    """Check if URL is from a supported video platform."""
    return detect_platform(url) is not None


# =============================================================================
# YouTube Transcript Extraction
# =============================================================================

def extract_youtube_transcript(url: str) -> dict:
    """Extract transcript from YouTube video using youtube-transcript-api.

    This is fast and doesn't require downloading the video.

    Returns dict with:
        - transcript: The full transcript text
        - title: Video title (if available)
        - duration: Video duration in seconds (if available)
        - error: Error message if failed
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable
        )
    except ImportError:
        return {"error": "youtube-transcript-api not installed. Run: pip install youtube-transcript-api"}

    # Extract video ID from URL
    video_id = _extract_youtube_id(url)
    if not video_id:
        return {"error": f"Could not extract YouTube video ID from URL: {url}"}

    try:
        # Get transcript (API v1.x uses instance method .fetch() returning FetchedTranscriptSnippet objects)
        api = YouTubeTranscriptApi()
        transcript_result = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        transcript_list = list(transcript_result)  # Convert to list of FetchedTranscriptSnippet

        # Combine transcript segments (v1.x uses .text attribute instead of dict)
        full_transcript = ' '.join([entry.text for entry in transcript_list])

        # Calculate approximate duration
        last_entry = transcript_list[-1] if transcript_list else None
        duration = (last_entry.start + getattr(last_entry, 'duration', 0)) if last_entry else 0

        # Try to get title via yt-dlp (lightweight metadata fetch)
        title = _get_youtube_title(url)

        return {
            "transcript": full_transcript,
            "title": title,
            "duration": int(duration),
            "platform": "youtube",
            "error": None
        }

    except TranscriptsDisabled:
        return {"error": "Transcripts are disabled for this video"}
    except NoTranscriptFound:
        return {"error": "No English transcript available for this video"}
    except VideoUnavailable:
        return {"error": "Video is unavailable"}
    except Exception as e:
        return {"error": f"YouTube transcript extraction failed: {str(e)}"}


def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def _get_youtube_title(url: str) -> str:
    """Get YouTube video title using yt-dlp (metadata only, no download)."""
    try:
        import yt_dlp

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title', 'YouTube Video')

    except Exception:
        return "YouTube Video"


# =============================================================================
# TikTok/Instagram Transcript Extraction (via Whisper)
# =============================================================================

def extract_video_transcript_whisper(url: str, archive: bool = False) -> dict:
    """Extract transcript from TikTok/Instagram using yt-dlp + Whisper.

    Downloads the video, transcribes with Whisper, optionally archives.

    Args:
        url: Video URL
        archive: If True, keep the video file in VIDEO_ARCHIVE_PATH

    Returns dict with:
        - transcript: The transcribed text
        - title: Video title
        - duration: Video duration in seconds
        - archived_path: Path to archived video (if archive=True)
        - error: Error message if failed
    """
    platform = detect_platform(url)

    try:
        import yt_dlp
    except ImportError:
        return {"error": "yt-dlp not installed. Run: pip install yt-dlp"}

    # Check Whisper availability
    whisper_backend = _get_whisper_backend()
    if whisper_backend == "none":
        return {"error": "No Whisper backend available. Install mlx-whisper or faster-whisper"}

    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Download video
        logger.info(f"Downloading video from {platform}: {url[:60]}...")
        download_result = _download_video(url, temp_path)

        if download_result.get("error"):
            return download_result

        video_path = download_result["video_path"]
        title = download_result.get("title", f"{platform.title()} Video")
        duration = download_result.get("duration", 0)

        # Transcribe with Whisper
        logger.info(f"Transcribing with {whisper_backend} (model: {WHISPER_MODEL})...")
        transcript = _transcribe_with_whisper(video_path, whisper_backend)

        if transcript.get("error"):
            return transcript

        result = {
            "transcript": transcript["text"],
            "title": title,
            "duration": duration,
            "platform": platform,
            "error": None
        }

        # Archive if requested
        if archive:
            archived_path = _archive_video(video_path, title, platform)
            result["archived_path"] = str(archived_path) if archived_path else None

        return result


def _download_video(url: str, output_dir: Path) -> dict:
    """Download video using yt-dlp with browser impersonation for TikTok/Instagram."""
    try:
        import yt_dlp

        output_template = str(output_dir / '%(title)s.%(ext)s')
        platform = detect_platform(url)

        ydl_opts = {
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'format': 'best[ext=mp4]/best',  # Prefer mp4
            'max_filesize': 100 * 1024 * 1024,  # 100MB limit
        }

        # Use browser impersonation for TikTok/Instagram (requires curl_cffi)
        if platform in ('tiktok', 'instagram'):
            try:
                import curl_cffi  # noqa: F401
                from yt_dlp.networking.impersonate import ImpersonateTarget
                # Use Chrome on macOS impersonation for best compatibility
                # Note: Python API requires ImpersonateTarget object, not string
                ydl_opts['impersonate'] = ImpersonateTarget.from_str('chrome:macos-14')
                logger.info(f"Using browser impersonation for {platform}")
            except ImportError:
                logger.warning("curl_cffi not installed - TikTok/Instagram may fail")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Find the downloaded file
            video_files = list(output_dir.glob('*'))
            if not video_files:
                return {"error": "Video download completed but file not found"}

            video_path = video_files[0]

            return {
                "video_path": video_path,
                "title": info.get('title', 'Video'),
                "duration": info.get('duration', 0),
                "error": None
            }

    except Exception as e:
        error_msg = str(e)
        if 'login' in error_msg.lower() or 'authentication' in error_msg.lower():
            return {"error": f"Video requires login (authentication required): {url}"}
        if 'ip' in error_msg.lower() and 'block' in error_msg.lower():
            return {
                "error": f"TikTok/Instagram IP block - your network IP is banned. "
                         f"Try: (1) Use VPN, (2) Send link via cobalt.tools, or "
                         f"(3) Open in browser and copy transcript manually."
            }
        return {"error": f"Video download failed: {error_msg}"}


def _transcribe_with_whisper(video_path: Path, backend: str) -> dict:
    """Transcribe video/audio using specified Whisper backend."""

    if backend == "mlx":
        return _transcribe_mlx_whisper(video_path)
    elif backend == "faster-whisper":
        return _transcribe_faster_whisper(video_path)
    else:
        return {"error": f"Unknown Whisper backend: {backend}"}


def _transcribe_mlx_whisper(video_path: Path) -> dict:
    """Transcribe using mlx-whisper (Apple Silicon optimized)."""
    try:
        import mlx_whisper

        result = mlx_whisper.transcribe(
            str(video_path),
            path_or_hf_repo=f"mlx-community/whisper-{WHISPER_MODEL}-mlx"
        )

        return {
            "text": result.get("text", "").strip(),
            "error": None
        }

    except ImportError:
        return {"error": "mlx-whisper not installed. Run: pip install mlx-whisper"}
    except Exception as e:
        return {"error": f"mlx-whisper transcription failed: {str(e)}"}


def _transcribe_faster_whisper(video_path: Path) -> dict:
    """Transcribe using faster-whisper (cross-platform)."""
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(WHISPER_MODEL, device="auto", compute_type="auto")
        segments, info = model.transcribe(str(video_path), language="en")

        # Combine segments
        full_text = ' '.join([segment.text for segment in segments])

        return {
            "text": full_text.strip(),
            "error": None
        }

    except ImportError:
        return {"error": "faster-whisper not installed. Run: pip install faster-whisper"}
    except Exception as e:
        return {"error": f"faster-whisper transcription failed: {str(e)}"}


def _archive_video(video_path: Path, title: str, platform: str) -> Optional[Path]:
    """Archive video to permanent storage."""
    try:
        # Ensure archive directory exists
        VIDEO_ARCHIVE_PATH.mkdir(parents=True, exist_ok=True)

        # Create platform subdirectory
        platform_dir = VIDEO_ARCHIVE_PATH / platform
        platform_dir.mkdir(exist_ok=True)

        # Create safe filename
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)[:50]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{safe_title}-{timestamp}{video_path.suffix}"

        dest_path = platform_dir / filename
        shutil.copy2(video_path, dest_path)

        logger.info(f"Archived video to: {dest_path}")
        return dest_path

    except Exception as e:
        logger.error(f"Failed to archive video: {e}")
        return None


# =============================================================================
# Main Extraction Interface
# =============================================================================

def extract_transcript(url: str, archive: bool = False) -> dict:
    """Extract transcript from a video URL.

    Automatically detects platform and uses the appropriate method:
    - YouTube: Fast transcript API (no video download)
    - TikTok/Instagram: yt-dlp download + Whisper transcription

    Args:
        url: Video URL
        archive: If True and platform requires download, keep the video file

    Returns dict with:
        - transcript: The full transcript text
        - title: Video title
        - duration: Video duration in seconds
        - platform: Detected platform
        - archived_path: Path to archived video (if applicable)
        - error: Error message if failed
    """
    platform = detect_platform(url)

    if not platform:
        return {"error": f"Unsupported video platform: {url}"}

    logger.info(f"Extracting transcript from {platform}: {url[:60]}...")

    if platform == 'youtube':
        result = extract_youtube_transcript(url)
        # YouTube doesn't need archiving (video stays on platform)
        # But if archive requested, we could download it
        if archive and not result.get("error"):
            logger.info("Archive requested for YouTube - downloading video...")
            archive_result = extract_video_transcript_whisper(url, archive=True)
            if archive_result.get("archived_path"):
                result["archived_path"] = archive_result["archived_path"]
        return result
    else:
        # TikTok/Instagram - need to download and transcribe
        return extract_video_transcript_whisper(url, archive=archive)


# =============================================================================
# CLI Testing
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("Video Processor Module")
    print("=" * 50)
    print(f"Apple Silicon: {_is_apple_silicon()}")
    print(f"Whisper Backend: {_get_whisper_backend()}")
    print(f"Whisper Model: {WHISPER_MODEL}")
    print(f"Archive Path: {VIDEO_ARCHIVE_PATH}")
    print()

    # Test platform detection
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.tiktok.com/@user/video/1234567890",
        "https://www.instagram.com/reel/ABC123/",
        "https://example.com/not-a-video",
    ]

    print("Platform Detection:")
    for url in test_urls:
        platform = detect_platform(url)
        print(f"  {url[:50]}... -> {platform or 'not supported'}")
