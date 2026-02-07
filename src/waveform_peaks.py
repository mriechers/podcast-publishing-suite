"""Waveform peaks generation using BBC audiowaveform.

This module generates pre-computed waveform peaks JSON files for Wavesurfer.js
to solve CORS issues with PRX/Podtrac redirect URLs.

Technical Background:
- PRX audio URLs use Podtrac redirects: https://dts.podtrac.com/redirect.mp3/dovetail.prxu.org/...
- These redirects cause CORS failures when Wavesurfer tries to fetch and decode audio
- Solution: Pre-generate peaks JSON files using audiowaveform CLI
- Wavesurfer uses `peaks` option with JSON data + `url` option for playback

Requirements:
- audiowaveform CLI tool: brew install audiowaveform
- Output: JSON format compatible with Wavesurfer.js
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class WaveformError(Exception):
    """Exception raised for waveform generation errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


def check_audiowaveform_installed() -> bool:
    """Check if audiowaveform CLI is installed and accessible.

    Returns:
        True if audiowaveform is available, False otherwise.
    """
    return shutil.which("audiowaveform") is not None


def download_audio_file(
    audio_url: str,
    output_path: Path,
    timeout: int = 300,
    chunk_size: int = 8192,
) -> None:
    """Download audio file from URL to local path.

    Args:
        audio_url: URL to the audio file (may be a redirect URL).
        output_path: Local path to save the downloaded file.
        timeout: Request timeout in seconds (default: 5 minutes).
        chunk_size: Download chunk size in bytes.

    Raises:
        WaveformError: If download fails.
    """
    try:
        logger.info(f"Downloading audio from: {audio_url}")
        response = requests.get(
            audio_url,
            stream=True,
            timeout=timeout,
            headers={"User-Agent": "PRX-to-Ghost-Publisher/1.0"},
        )
        response.raise_for_status()

        # Write in chunks to handle large files
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)

        file_size = output_path.stat().st_size
        logger.info(f"Downloaded {file_size:,} bytes to {output_path}")

    except requests.exceptions.RequestException as e:
        raise WaveformError(f"Failed to download audio file", str(e))


def generate_peaks_json(
    audio_path: Path,
    output_path: Path,
    pixels_per_second: int = 20,
    bits: int = 8,
) -> None:
    """Generate waveform peaks JSON using audiowaveform CLI.

    Args:
        audio_path: Path to the input audio file.
        output_path: Path to save the output JSON file.
        pixels_per_second: Waveform resolution (default: 20).
        bits: Bit depth for waveform data (default: 8).

    Raises:
        WaveformError: If audiowaveform execution fails.
    """
    if not check_audiowaveform_installed():
        raise WaveformError(
            "audiowaveform not installed",
            "Install with: brew install audiowaveform",
        )

    if not audio_path.exists():
        raise WaveformError(f"Audio file not found: {audio_path}")

    cmd = [
        "audiowaveform",
        "-i", str(audio_path),
        "-o", str(output_path),
        "--pixels-per-second", str(pixels_per_second),
        "--bits", str(bits),
    ]

    try:
        logger.info(f"Generating peaks: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,  # 2 minute timeout
        )

        if result.stdout:
            logger.debug(f"audiowaveform stdout: {result.stdout}")

        if not output_path.exists():
            raise WaveformError("Peaks file was not created")

        file_size = output_path.stat().st_size
        logger.info(f"Generated peaks JSON: {file_size:,} bytes")

    except subprocess.CalledProcessError as e:
        raise WaveformError(
            f"audiowaveform failed (exit code {e.returncode})",
            e.stderr or str(e),
        )
    except subprocess.TimeoutExpired:
        raise WaveformError("audiowaveform timed out after 120 seconds")
    except Exception as e:
        raise WaveformError(f"Failed to execute audiowaveform", str(e))


def generate_peaks_for_episode(
    audio_url: str,
    episode_slug: str,
    output_dir: Path,
    pixels_per_second: int = 20,
    keep_temp_audio: bool = False,
) -> Path:
    """Generate waveform peaks JSON for an episode.

    Complete workflow:
    1. Download audio file to temporary location
    2. Run audiowaveform to generate peaks JSON
    3. Save peaks JSON to output directory
    4. Clean up temporary audio file

    Args:
        audio_url: URL to the episode audio file.
        episode_slug: Episode slug for naming the output file.
        output_dir: Directory to save the peaks JSON file.
        pixels_per_second: Waveform resolution (default: 20).
        keep_temp_audio: Keep temporary audio file for debugging (default: False).

    Returns:
        Path to the generated peaks JSON file.

    Raises:
        WaveformError: If any step in the workflow fails.
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine audio file extension from URL
    parsed_url = urlparse(audio_url)
    path = parsed_url.path
    ext = Path(path).suffix or ".mp3"

    # Create temporary directory for audio download
    temp_dir = Path(tempfile.mkdtemp(prefix="waveform_"))

    try:
        # Download audio to temp location
        temp_audio = temp_dir / f"{episode_slug}{ext}"
        download_audio_file(audio_url, temp_audio)

        # Generate peaks JSON
        peaks_filename = f"{episode_slug}.json"
        peaks_path = output_dir / peaks_filename

        generate_peaks_json(
            audio_path=temp_audio,
            output_path=peaks_path,
            pixels_per_second=pixels_per_second,
        )

        # Validate generated JSON
        try:
            with open(peaks_path) as f:
                peaks_data = json.load(f)

            # Basic validation - check for required Wavesurfer fields
            if not isinstance(peaks_data, dict):
                raise WaveformError("Peaks JSON is not a valid object")

            logger.info(f"Successfully generated peaks for {episode_slug}")
            return peaks_path

        except json.JSONDecodeError as e:
            raise WaveformError(f"Generated peaks file is not valid JSON", str(e))

    finally:
        # Clean up temporary files
        if not keep_temp_audio and temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temporary directory: {temp_dir}")


def download_and_generate_peaks(
    audio_url: str,
    episode_slug: str,
    peaks_dir: Path,
    pixels_per_second: int = 20,
) -> tuple[Path, Path]:
    """Download audio and generate peaks, returning both file paths.

    Unlike generate_peaks_for_episode(), this function keeps the downloaded
    audio file so the caller can upload it to Ghost's media library.
    The caller is responsible for cleaning up both files when done.

    Args:
        audio_url: URL to the episode audio file.
        episode_slug: Episode slug for naming files.
        peaks_dir: Directory to save the peaks JSON file.
        pixels_per_second: Waveform resolution (default: 20).

    Returns:
        Tuple of (audio_file_path, peaks_json_path).

    Raises:
        WaveformError: If download or peaks generation fails.
    """
    peaks_dir.mkdir(parents=True, exist_ok=True)

    # Determine audio file extension from URL
    parsed_url = urlparse(audio_url)
    ext = Path(parsed_url.path).suffix or ".mp3"

    # Create temp directory for audio download (caller cleans up)
    temp_dir = Path(tempfile.mkdtemp(prefix="ghost_upload_"))
    temp_audio = temp_dir / f"{episode_slug}{ext}"

    # Download audio
    download_audio_file(audio_url, temp_audio)

    # Generate peaks JSON
    peaks_path = peaks_dir / f"{episode_slug}.json"
    generate_peaks_json(
        audio_path=temp_audio,
        output_path=peaks_path,
        pixels_per_second=pixels_per_second,
    )

    # Validate peaks JSON
    try:
        with open(peaks_path) as f:
            peaks_data = json.load(f)
        if not isinstance(peaks_data, dict):
            raise WaveformError("Peaks JSON is not a valid object")
    except json.JSONDecodeError as e:
        raise WaveformError("Generated peaks file is not valid JSON", str(e))

    logger.info(f"Downloaded audio and generated peaks for {episode_slug}")
    return temp_audio, peaks_path


def get_peaks_url(
    episode_slug: str,
    ghost_url: str,
    peaks_base_path: str = "/assets/peaks",
) -> str:
    """Build the URL to access a peaks JSON file via Ghost.

    Args:
        episode_slug: Episode slug.
        ghost_url: Base Ghost site URL (e.g., https://wondercabinetproductions.com).
        peaks_base_path: Path within theme assets (default: /assets/peaks).

    Returns:
        Full URL to the peaks JSON file.
    """
    ghost_url = ghost_url.rstrip("/")
    peaks_base_path = peaks_base_path.rstrip("/")
    return f"{ghost_url}{peaks_base_path}/{episode_slug}.json"


if __name__ == "__main__":
    # Test/demo
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Check installation
    if not check_audiowaveform_installed():
        logger.error("audiowaveform not installed. Install with: brew install audiowaveform")
        sys.exit(1)

    logger.info("audiowaveform is installed and ready")

    # Example usage (would need actual audio URL)
    # peaks_path = generate_peaks_for_episode(
    #     audio_url="https://example.com/episode.mp3",
    #     episode_slug="test-episode",
    #     output_dir=Path("./peaks"),
    # )
    # print(f"Generated: {peaks_path}")
