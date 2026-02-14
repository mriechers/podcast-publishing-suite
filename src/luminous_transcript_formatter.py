"""Luminous episode transcript reformatter.

This module transforms Luminous podcast episode transcripts from bare-dash
format to properly attributed speaker format matching Wonder Cabinet standards.

Usage:
    python -m src.luminous_transcript_formatter --slug episode-slug
    python -m src.luminous_transcript_formatter --all --dry-run
    python -m src.luminous_transcript_formatter --all
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import get_config
from .ghost_client import GhostClient, GhostAPIError
from .luminous_speaker_rules import (
    SpeakerContext,
    extract_speaker_from_line,
    get_episode_guest,
    infer_speaker,
    HOSTS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TransformResult:
    """Result of a transcript transformation."""

    episode_id: str
    slug: str
    title: str
    success: bool
    lines_fixed: int
    error: Optional[str] = None
    original_html: Optional[str] = None
    transformed_html: Optional[str] = None


def extract_transcript_html(lexical_json: str) -> Optional[str]:
    """Extract transcript HTML from Ghost lexical content.

    Args:
        lexical_json: JSON string of Ghost lexical content

    Returns:
        Transcript HTML string or None if not found
    """
    try:
        lexical = json.loads(lexical_json)
    except json.JSONDecodeError:
        logger.error("Failed to parse lexical JSON")
        return None

    # Find HTML node containing episode-transcript div
    root = lexical.get("root", {})
    children = root.get("children", [])

    for node in children:
        if node.get("type") == "html":
            html_content = node.get("html", "")
            if 'class="episode-transcript"' in html_content or 'id="episode-transcript"' in html_content:
                return html_content

    return None


def transform_transcript_html(
    transcript_html: str,
    episode_slug: str,
    episode_title: str,
) -> tuple[str, int]:
    """Transform transcript HTML to use proper speaker attribution.

    Converts bare-dash lines like:
        <p>- Yeah.</p>
    To properly attributed lines like:
        <p><strong>Steve:</strong> Yeah.</p>

    Args:
        transcript_html: Original transcript HTML
        episode_slug: Episode URL slug for guest lookup
        episode_title: Episode title for guest extraction

    Returns:
        Tuple of (transformed HTML, count of lines fixed)
    """
    # Get guest name for this episode
    guest_name = get_episode_guest(episode_slug, episode_title)
    logger.info(f"Episode guest: {guest_name or 'Unknown'}")

    # Initialize speaker context
    context = SpeakerContext(episode_guest=guest_name)

    # Split into lines while preserving structure
    # We need to handle the HTML structure carefully
    lines = re.findall(r'<p>.*?</p>', transcript_html, re.DOTALL)

    if not lines:
        logger.warning("No paragraph lines found in transcript")
        return transcript_html, 0

    transformed_lines = []
    lines_fixed = 0

    for i, line in enumerate(lines):
        speaker, content = extract_speaker_from_line(line)

        if speaker:
            # Line already has speaker attribution
            context.update(speaker)
            transformed_lines.append(line)
        elif content:
            # Bare dash line - needs attribution
            inferred = infer_speaker(content, context, i, lines)
            new_line = f'<p><strong>{html.escape(inferred)}:</strong> {content}</p>'
            transformed_lines.append(new_line)
            context.update(inferred)
            lines_fixed += 1
            logger.debug(f"Fixed: '{content[:50]}...' -> {inferred}")
        else:
            # Empty or malformed line
            transformed_lines.append(line)

    # Reconstruct the full HTML
    # Replace the paragraph section in the original
    result = transcript_html

    # Replace each original line with its transformed version
    for orig, trans in zip(lines, transformed_lines):
        if orig != trans:
            result = result.replace(orig, trans, 1)

    return result, lines_fixed


def update_lexical_content(
    lexical_json: str,
    new_transcript_html: str,
) -> str:
    """Update lexical JSON with transformed transcript.

    Args:
        lexical_json: Original lexical JSON string
        new_transcript_html: Transformed transcript HTML

    Returns:
        Updated lexical JSON string
    """
    lexical = json.loads(lexical_json)
    root = lexical.get("root", {})
    children = root.get("children", [])

    for node in children:
        if node.get("type") == "html":
            html_content = node.get("html", "")
            if 'class="episode-transcript"' in html_content or 'id="episode-transcript"' in html_content:
                node["html"] = new_transcript_html
                break

    return json.dumps(lexical)


def format_episode(
    client: GhostClient,
    slug: str,
    dry_run: bool = False,
) -> TransformResult:
    """Format a single episode's transcript.

    Args:
        client: Ghost API client
        slug: Episode URL slug
        dry_run: If True, don't actually update the post

    Returns:
        TransformResult with operation details
    """
    logger.info(f"Processing: {slug}")

    try:
        # Fetch the post
        # We need to use the browse API with filter since read doesn't work by slug directly
        # Actually the MCP tool supports slug parameter
        from .ghost_client import GhostAPIError

        # Use the API directly to get the post by slug
        url = f"{client.api_url}/posts/slug/{slug}/"
        response = client._session.get(
            url,
            headers=client._get_headers(),
            timeout=30,
        )

        if response.status_code == 404:
            return TransformResult(
                episode_id="",
                slug=slug,
                title="",
                success=False,
                lines_fixed=0,
                error=f"Post not found: {slug}",
            )

        result = client._handle_response(response)
        posts = result.get("posts", [])
        if not posts:
            return TransformResult(
                episode_id="",
                slug=slug,
                title="",
                success=False,
                lines_fixed=0,
                error=f"Post not found: {slug}",
            )

        post = posts[0]
        post_id = post["id"]
        title = post["title"]
        lexical = post.get("lexical", "")
        updated_at = post["updated_at"]

        if not lexical:
            return TransformResult(
                episode_id=post_id,
                slug=slug,
                title=title,
                success=False,
                lines_fixed=0,
                error="No lexical content found",
            )

        # Extract transcript
        transcript_html = extract_transcript_html(lexical)
        if not transcript_html:
            return TransformResult(
                episode_id=post_id,
                slug=slug,
                title=title,
                success=False,
                lines_fixed=0,
                error="No transcript found in post",
            )

        # Transform the transcript
        transformed_html, lines_fixed = transform_transcript_html(
            transcript_html,
            slug,
            title,
        )

        if lines_fixed == 0:
            logger.info(f"  No bare-dash lines found in {slug}")
            return TransformResult(
                episode_id=post_id,
                slug=slug,
                title=title,
                success=True,
                lines_fixed=0,
                original_html=transcript_html,
                transformed_html=transformed_html,
            )

        logger.info(f"  Fixed {lines_fixed} lines in {slug}")

        if dry_run:
            logger.info(f"  [DRY RUN] Would update {slug}")
            return TransformResult(
                episode_id=post_id,
                slug=slug,
                title=title,
                success=True,
                lines_fixed=lines_fixed,
                original_html=transcript_html,
                transformed_html=transformed_html,
            )

        # Update lexical content
        new_lexical = update_lexical_content(lexical, transformed_html)

        # Update the post via API
        update_url = f"{client.api_url}/posts/{post_id}/"
        update_payload = {
            "posts": [{
                "lexical": new_lexical,
                "updated_at": updated_at,
            }]
        }

        update_response = client._session.put(
            update_url,
            json=update_payload,
            headers=client._get_headers(),
            timeout=30,
        )

        client._handle_response(update_response)
        logger.info(f"  Updated {slug} successfully")

        return TransformResult(
            episode_id=post_id,
            slug=slug,
            title=title,
            success=True,
            lines_fixed=lines_fixed,
            original_html=transcript_html,
            transformed_html=transformed_html,
        )

    except GhostAPIError as e:
        logger.error(f"  API error for {slug}: {e}")
        return TransformResult(
            episode_id="",
            slug=slug,
            title="",
            success=False,
            lines_fixed=0,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"  Unexpected error for {slug}: {e}")
        return TransformResult(
            episode_id="",
            slug=slug,
            title="",
            success=False,
            lines_fixed=0,
            error=str(e),
        )


def get_luminous_episode_slugs(client: GhostClient) -> list[str]:
    """Get all Luminous episode slugs from Ghost.

    Args:
        client: Ghost API client

    Returns:
        List of episode slugs
    """
    slugs = []
    page = 1

    while True:
        url = f"{client.api_url}/posts/?filter=tag:luminous&limit=50&page={page}"
        response = client._session.get(
            url,
            headers=client._get_headers(),
            timeout=30,
        )

        result = client._handle_response(response)
        posts = result.get("posts", [])

        if not posts:
            break

        for post in posts:
            slugs.append(post["slug"])

        # Check for more pages
        meta = result.get("meta", {}).get("pagination", {})
        if page >= meta.get("pages", 1):
            break
        page += 1

    return slugs


def main():
    """Main entry point for the formatter."""
    parser = argparse.ArgumentParser(
        description="Format Luminous episode transcripts"
    )
    parser.add_argument(
        "--slug",
        help="Process a specific episode by slug",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all Luminous episodes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually update posts, just show what would change",
    )
    parser.add_argument(
        "--env",
        default="dev",
        choices=["dev", "prod"],
        help="Environment to use (default: dev)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.slug and not args.all:
        parser.error("Must specify --slug or --all")

    # Load config and create client
    config = get_config(env_name=args.env)
    client = GhostClient(config.ghost_url, config.ghost_admin_api_key)

    # Test connection
    try:
        client.test_connection()
    except GhostAPIError as e:
        logger.error(f"Failed to connect to Ghost: {e}")
        sys.exit(1)

    # Process episodes
    if args.slug:
        slugs = [args.slug]
    else:
        logger.info("Fetching all Luminous episodes...")
        slugs = get_luminous_episode_slugs(client)
        logger.info(f"Found {len(slugs)} Luminous episodes")

    results = []
    for slug in slugs:
        result = format_episode(client, slug, dry_run=args.dry_run)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = len(results)
    successful = sum(1 for r in results if r.success)
    fixed = sum(r.lines_fixed for r in results)
    failed = [r for r in results if not r.success]

    print(f"Total episodes processed: {total}")
    print(f"Successfully processed: {successful}")
    print(f"Total lines fixed: {fixed}")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for r in failed:
            print(f"  - {r.slug}: {r.error}")

    if args.dry_run:
        print("\n[DRY RUN] No changes were made to Ghost")


if __name__ == "__main__":
    main()
