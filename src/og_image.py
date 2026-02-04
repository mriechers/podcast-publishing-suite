"""OG image generation for podcast episodes.

Downloads square episode artwork from PRX and generates 1200x630
Open Graph images with the artwork centered on a background image.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# Standard Open Graph image dimensions (1.91:1 ratio)
OG_WIDTH = 1200
OG_HEIGHT = 630

# Default background image for OG compositing
DEFAULT_BG_PATH = Path(__file__).parent.parent / "images" / "og-left-logo.png"


def download_image(url: str, dest_dir: Path) -> Path:
    """Download image from URL to a local file.

    Preserves the original file extension from the URL. Streams the
    download to avoid loading large images entirely into memory.

    Args:
        url: Image URL to download.
        dest_dir: Directory to save the downloaded file.

    Returns:
        Path to the downloaded image file.

    Raises:
        requests.HTTPError: If download fails.
        OSError: If file cannot be written.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Extract filename and extension from URL path
    parsed = urlparse(url)
    url_path = Path(parsed.path)
    ext = url_path.suffix.lower() if url_path.suffix else ".jpg"
    dest_path = dest_dir / f"episode_artwork{ext}"

    logger.info(f"Downloading image: {url}")

    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info(f"Downloaded image: {dest_path} ({dest_path.stat().st_size} bytes)")
    return dest_path


def generate_og_image(
    square_image_path: Path,
    output_path: Path,
    background_path: Optional[Path] = None,
) -> Path:
    """Generate a 1200x630 OG image from square podcast artwork.

    Places the square image right-justified on a background canvas, resized
    to fit the 630px height. Uses a background image if provided (or the
    default og-left-logo.png with Wonder Cabinet branding on the left),
    falling back to solid black if not available.

    Args:
        square_image_path: Path to the square source image.
        output_path: Path for the output JPEG file.
        background_path: Optional path to a 1200x630 background image.
                         Defaults to images/og-left-logo.png in the repo root.

    Returns:
        Path to the generated OG image.

    Raises:
        OSError: If image cannot be read or written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve background: explicit arg → default swirl → solid black
    bg_path = background_path or DEFAULT_BG_PATH

    if bg_path.is_file():
        canvas = Image.open(bg_path).convert("RGB")
        # Resize to exact OG dimensions if needed
        if canvas.size != (OG_WIDTH, OG_HEIGHT):
            canvas = canvas.resize((OG_WIDTH, OG_HEIGHT), Image.LANCZOS)
    else:
        logger.debug(f"Background not found at {bg_path}, using solid black")
        canvas = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), (0, 0, 0))

    with Image.open(square_image_path) as img:
        # Convert to RGB if necessary (e.g., PNG with alpha channel)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize square image to fit the canvas height
        scale = OG_HEIGHT / max(img.size[0], img.size[1])
        new_width = int(img.size[0] * scale)
        new_height = int(img.size[1] * scale)
        resized = img.resize((new_width, new_height), Image.LANCZOS)

        # Paste right-justified artwork onto background
        x_offset = OG_WIDTH - new_width
        y_offset = (OG_HEIGHT - new_height) // 2
        canvas.paste(resized, (x_offset, y_offset))

    canvas.save(output_path, "JPEG", quality=85)

    logger.info(f"Generated OG image: {output_path} ({OG_WIDTH}x{OG_HEIGHT})")
    return output_path
