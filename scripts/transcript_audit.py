#!/usr/bin/env python3
"""
Transcript Audit Script

Compares PRX episodes against cached TTBOOK transcripts to identify:
1. Episodes that have transcripts in our cache
2. Episodes missing transcripts
3. Mapping between PRX episode slugs and TTBOOK page slugs

This helps identify which episodes need transcripts and validates
the matching logic before attempting any updates.

Usage:
    python scripts/transcript_audit.py
    python scripts/transcript_audit.py --podcast-id 3329
    python scripts/transcript_audit.py --output report.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config, ConfigError
from src.prx_auth import PRXAuthClient, PRXAuthError
from src.dovetail_client import DovetailClient, DovetailAPIError
from src.content_builder import extract_slug_from_link


# Transcript cache location
CACHE_DIR = Path(__file__).parent.parent / "sample-data" / "ttbook-cache" / "luminous"


def normalize_slug(slug: str) -> str:
    """Normalize a slug for comparison.

    Handles variations like:
    - 'luminous-melissa-etheridge-ayahuasca' vs 'melissa-etheridge-ayahuasca'
    - URL-encoded characters
    """
    # Remove 'luminous-' prefix if present
    if slug.startswith("luminous-"):
        slug = slug[9:]
    # Lowercase and strip
    return slug.lower().strip()


def find_cached_transcript(episode_link: str, episode_title: str) -> Optional[Path]:
    """Find a cached transcript file for an episode.

    Tries multiple matching strategies:
    1. Extract slug from episode link and match directly
    2. Fuzzy match on title keywords

    Args:
        episode_link: Episode URL (e.g., https://www.ttbook.org/show/luminous-...)
        episode_title: Episode title for fuzzy matching

    Returns:
        Path to transcript file, or None if not found
    """
    if not CACHE_DIR.exists():
        return None

    # Strategy 1: Direct slug match from URL
    slug = extract_slug_from_link(episode_link)
    if slug:
        # Try exact match
        transcript_path = CACHE_DIR / f"{slug}_transcript.txt"
        if transcript_path.exists():
            return transcript_path

        # Try with 'luminous-' prefix
        transcript_path = CACHE_DIR / f"luminous-{slug}_transcript.txt"
        if transcript_path.exists():
            return transcript_path

        # Try without 'luminous-' prefix
        if slug.startswith("luminous-"):
            transcript_path = CACHE_DIR / f"{slug[9:]}_transcript.txt"
            if transcript_path.exists():
                return transcript_path

    # Strategy 2: Match based on title keywords
    # Build a normalized version of the title for matching
    title_normalized = re.sub(r'[^\w\s]', '', episode_title.lower())
    title_words = set(title_normalized.split())

    best_match = None
    best_score = 0

    for transcript_file in CACHE_DIR.glob("*_transcript.txt"):
        # Extract slug from filename
        file_slug = transcript_file.stem.replace("_transcript", "")
        file_slug_normalized = re.sub(r'[^\w\s]', ' ', file_slug.lower().replace("-", " "))
        file_words = set(file_slug_normalized.split())

        # Calculate overlap score
        overlap = len(title_words & file_words)
        if overlap > best_score and overlap >= 2:  # Require at least 2 matching words
            best_score = overlap
            best_match = transcript_file

    return best_match


def load_manifest() -> dict:
    """Load the TTBOOK scrape manifest."""
    manifest_path = CACHE_DIR / "_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return {"episodes": []}


def audit_transcripts(podcast_id: str) -> dict:
    """Audit transcript availability for a podcast.

    Args:
        podcast_id: PRX podcast ID to audit

    Returns:
        Audit report dictionary
    """
    config = get_config()

    # Initialize API client
    auth = PRXAuthClient(
        client_id=config.prx_client_id,
        client_secret=config.prx_client_secret,
        token_endpoint=f"{config.prx_id_base_url}/token",
    )
    client = DovetailClient(
        auth_client=auth,
        podcast_id=podcast_id,
        api_base_url=config.prx_api_base_url,
    )

    # Fetch all episodes
    print(f"Fetching episodes from PRX for podcast {podcast_id}...")
    episodes = client.get_all_episodes(podcast_id=podcast_id)
    print(f"Found {len(episodes)} episodes")

    # Load manifest for reference
    manifest = load_manifest()
    cached_slugs = {ep["slug"] for ep in manifest.get("episodes", [])}
    print(f"Found {len(cached_slugs)} cached transcripts in TTBOOK archive")

    # Audit each episode
    results = {
        "podcast_id": podcast_id,
        "audit_time": datetime.now().isoformat(),
        "total_episodes": len(episodes),
        "with_transcript": [],
        "without_transcript": [],
        "cache_stats": {
            "cached_transcripts": len(cached_slugs),
            "matched": 0,
            "unmatched": 0,
        }
    }

    print("\nAuditing episodes...")
    for episode in episodes:
        episode_info = {
            "guid": episode.guid,
            "title": episode.title,
            "link": episode.link,
            "pub_date": episode.pub_date.isoformat(),
        }

        # Try to find cached transcript
        transcript_path = find_cached_transcript(episode.link, episode.title)

        if transcript_path:
            episode_info["transcript_source"] = str(transcript_path.name)
            episode_info["transcript_size"] = transcript_path.stat().st_size
            results["with_transcript"].append(episode_info)
            results["cache_stats"]["matched"] += 1
        else:
            episode_info["transcript_source"] = None
            results["without_transcript"].append(episode_info)
            results["cache_stats"]["unmatched"] += 1

    return results


def print_report(results: dict) -> None:
    """Print a human-readable report."""
    print("\n" + "=" * 60)
    print("TRANSCRIPT AUDIT REPORT")
    print("=" * 60)

    print(f"\nPodcast ID: {results['podcast_id']}")
    print(f"Audit Time: {results['audit_time']}")
    print(f"Total Episodes: {results['total_episodes']}")

    print(f"\n{'Category':<30} {'Count':>10}")
    print("-" * 42)
    print(f"{'Episodes with transcript':<30} {len(results['with_transcript']):>10}")
    print(f"{'Episodes without transcript':<30} {len(results['without_transcript']):>10}")
    print(f"{'Cached transcripts available':<30} {results['cache_stats']['cached_transcripts']:>10}")

    if results["with_transcript"]:
        print("\n" + "-" * 60)
        print("EPISODES WITH TRANSCRIPTS:")
        print("-" * 60)
        for ep in results["with_transcript"][:10]:  # Show first 10
            print(f"\n  {ep['title'][:50]}...")
            print(f"    Source: {ep['transcript_source']}")
        if len(results["with_transcript"]) > 10:
            print(f"\n  ... and {len(results['with_transcript']) - 10} more")

    if results["without_transcript"]:
        print("\n" + "-" * 60)
        print("EPISODES WITHOUT TRANSCRIPTS:")
        print("-" * 60)
        for ep in results["without_transcript"][:10]:  # Show first 10
            print(f"\n  {ep['title'][:50]}...")
            print(f"    Link: {ep['link']}")
        if len(results["without_transcript"]) > 10:
            print(f"\n  ... and {len(results['without_transcript']) - 10} more")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Audit transcript availability for PRX podcast episodes"
    )
    parser.add_argument(
        "--podcast-id",
        default="3329",
        help="PRX podcast ID to audit (default: 3329 for Luminous)"
    )
    parser.add_argument(
        "--output",
        help="Output JSON report to file"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output JSON, no progress messages"
    )

    args = parser.parse_args()

    try:
        results = audit_transcripts(args.podcast_id)

        if not args.quiet:
            print_report(results)

        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nReport saved to: {output_path}")

    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except PRXAuthError as e:
        print(f"PRX authentication error: {e}", file=sys.stderr)
        sys.exit(1)
    except DovetailAPIError as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
