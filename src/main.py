#!/usr/bin/env python3
"""PRX-to-Ghost Publisher CLI.

Sync podcast episodes from PRX/Dovetail RSS feed to Ghost CMS.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from .config import ConfigError, get_config
from .content_builder import (
    build_ghost_post,
    build_luminous_ghost_post,
    extract_slug_from_link,
    format_published_at,
    load_transcript,
)
from .transcript_exporter import export_episode_transcript
from .feed_parser import (
    Episode,
    FeedFetchError,
    FeedParseError,
    get_episodes,
    parse_feed_file,
)
from .prx_auth import PRXAuthClient, PRXAuthError
from .dovetail_client import DovetailClient, DovetailAPIError
from .ghost_client import GhostAPIError, GhostClient, GhostPost
from .state_tracker import StateTracker

# Luminous feed URL
LUMINOUS_FEED_URL = "https://f.prxu.org/3329/feed-rss.xml"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def sync_episodes(
    episodes: list[Episode],
    client: GhostClient,
    tracker: StateTracker,
    status: str = "draft",
    dry_run: bool = False,
    primary_tag: str = "TTBOOK",
    feed_type: str = "ttbook",
    feed_url: str = "",
    export_transcripts: bool = False,
) -> tuple[int, int, int]:
    """Sync episodes to Ghost.

    Args:
        episodes: List of Episode objects to sync.
        client: Initialized GhostClient.
        tracker: StateTracker for duplicate prevention.
        status: Post status ('draft' or 'published').
        dry_run: If True, log but don't actually publish.
        primary_tag: Primary tag for all posts.
        feed_type: Type of feed ('luminous' or 'ttbook').
        feed_url: Feed URL for embedding players.
        export_transcripts: If True, export transcripts to /transcripts folder.

    Returns:
        Tuple of (published_count, skipped_count, failed_count).
    """
    published = 0
    skipped = 0
    failed = 0

    for episode in episodes:
        # Check if already published
        if tracker.is_published(episode.guid):
            logger.info(f"Skipping (already published): {episode.title}")
            skipped += 1
            continue

        # Build the Ghost post based on feed type
        if feed_type == "luminous":
            # Try to load transcript from cache
            slug = extract_slug_from_link(episode.link)
            transcript = load_transcript(slug) if slug else None
            if transcript:
                logger.info(f"  Found transcript for: {slug}")

                # Export transcript to /transcripts folder if enabled
                if export_transcripts:
                    try:
                        export_results = export_episode_transcript(
                            episode_slug=slug,
                            episode_title=episode.title,
                            episode_guid=episode.guid,
                            formats=['json', 'html'],
                        )
                        if export_results:
                            logger.info(f"  Exported transcript: {list(export_results.keys())}")
                    except Exception as e:
                        logger.warning(f"  Failed to export transcript: {e}")

            ghost_post = build_luminous_ghost_post(
                episode,
                status=status,
                transcript=transcript,
                feed_url=feed_url or LUMINOUS_FEED_URL,
            )
        else:
            ghost_post = build_ghost_post(episode, status=status, primary_tag=primary_tag)

        if dry_run:
            logger.info(f"[DRY RUN] Would publish: {episode.title}")
            logger.debug(f"  Status: {status}")
            logger.debug(f"  Tags: {[t['name'] for t in ghost_post.tags]}")
            published += 1
            continue

        # Publish to Ghost
        try:
            result = client.create_post(ghost_post)
            ghost_post_id = result.get("id", "")

            # Record the publish
            tracker.record_publish(
                guid=episode.guid,
                ghost_post_id=ghost_post_id,
                title=episode.title,
                published_at=format_published_at(episode),
                status=status,
            )

            logger.info(f"Published: {episode.title} (ID: {ghost_post_id})")
            published += 1

        except GhostAPIError as e:
            logger.error(f"Failed to publish '{episode.title}': {e}")
            tracker.record_failure(
                guid=episode.guid,
                title=episode.title,
                published_at=format_published_at(episode),
            )
            failed += 1

    return published, skipped, failed


def cmd_sync(args: argparse.Namespace) -> int:
    """Handle the sync command.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        config = get_config()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    # Override config with CLI args
    status = args.status or config.publish_status
    dry_run = args.dry_run or config.dry_run
    feed_type = getattr(args, 'feed_type', 'ttbook')
    source = getattr(args, 'source', 'rss')

    # Determine if we should use API
    use_api = source == "api" or config.use_dovetail_api

    # Determine feed URL (for RSS mode)
    if args.feed_url:
        feed_url = args.feed_url
    elif feed_type == "luminous":
        feed_url = LUMINOUS_FEED_URL
    else:
        feed_url = config.prx_feed_url

    logger.info(f"Starting sync (source={source}, feed_type={feed_type}, status={status}, dry_run={dry_run})")

    # Initialize state tracker for incremental sync
    tracker = StateTracker(config.state_file)

    # Fetch and parse episodes
    try:
        if args.file:
            logger.info(f"Parsing local file: {args.file}")
            episodes = parse_feed_file(args.file)
        elif use_api:
            # Use Dovetail API
            podcast_ids = config.prx_podcast_ids or ([config.prx_podcast_id] if config.prx_podcast_id else [])
            logger.info(f"Fetching episodes from Dovetail API (podcast_ids={podcast_ids})")

            # Validate API credentials
            if not config.prx_client_id or not config.prx_client_secret:
                logger.error("PRX_CLIENT_ID and PRX_CLIENT_SECRET required for API mode")
                return 1
            if not podcast_ids:
                logger.error("PRX_PODCAST_ID or PRX_PODCAST_IDS required for API mode")
                return 1

            # Create API clients
            auth_client = PRXAuthClient(
                client_id=config.prx_client_id,
                client_secret=config.prx_client_secret,
                token_endpoint=f"{config.prx_id_base_url}/token",
            )
            api_client = DovetailClient(
                auth_client=auth_client,
                podcast_id=podcast_ids[0],  # Default podcast for client
                api_base_url=config.prx_api_base_url,
            )

            # Get last sync time for incremental fetch
            last_sync = tracker.get_last_sync_time()
            if last_sync:
                logger.info(f"Incremental sync since: {last_sync.isoformat()}")

            # Fetch episodes from all configured podcasts
            episodes = []
            for podcast_id in podcast_ids:
                logger.info(f"Fetching from podcast {podcast_id}...")
                podcast_episodes = api_client.get_all_episodes(
                    podcast_id=podcast_id,
                    since=last_sync,
                )
                logger.info(f"  Found {len(podcast_episodes)} episodes from podcast {podcast_id}")
                episodes.extend(podcast_episodes)

            # Sort combined episodes by pub_date, newest first
            episodes.sort(key=lambda e: e.pub_date, reverse=True)

            # Update last sync time
            tracker.set_last_sync_time()

        else:
            # Use RSS feed
            logger.info(f"Fetching feed: {feed_url}")
            episodes = get_episodes(feed_url)
    except (FeedFetchError, FeedParseError) as e:
        logger.error(f"Failed to get episodes: {e}")
        return 1
    except PRXAuthError as e:
        logger.error(f"PRX authentication failed: {e}")
        return 1
    except DovetailAPIError as e:
        logger.error(f"Dovetail API error: {e}")
        return 1

    logger.info(f"Found {len(episodes)} episodes in feed")

    # Filter by GUID if specified
    if args.guid:
        episodes = [e for e in episodes if e.guid == args.guid]
        if not episodes:
            logger.error(f"No episode found with GUID: {args.guid}")
            return 1
        logger.info(f"Filtered to 1 episode by GUID")

    # Limit if specified
    if args.limit and args.limit > 0:
        episodes = episodes[: args.limit]
        logger.info(f"Limited to {len(episodes)} episodes")

    # tracker already initialized above for incremental sync

    if not dry_run:
        client = GhostClient(
            config.ghost_url,
            config.ghost_admin_api_key,
            config.ghost_api_version,
        )

        # Test connection
        try:
            client.test_connection()
        except GhostAPIError as e:
            logger.error(f"Ghost connection failed: {e}")
            return 1
    else:
        client = None  # type: ignore

    # Sync episodes
    export_transcripts = getattr(args, 'export_transcripts', False)
    published, skipped, failed = sync_episodes(
        episodes,
        client,  # type: ignore
        tracker,
        status=status,
        dry_run=dry_run,
        primary_tag=config.primary_tag,
        feed_type=feed_type,
        feed_url=feed_url,
        export_transcripts=export_transcripts,
    )

    # Summary
    logger.info(f"Sync complete: {published} published, {skipped} skipped, {failed} failed")

    return 0 if failed == 0 else 1


def cmd_list(args: argparse.Namespace) -> int:
    """Handle the list command.

    Returns:
        Exit code (0 for success).
    """
    try:
        config = get_config()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    tracker = StateTracker(config.state_file)
    episodes = tracker.get_all_published()

    if not episodes:
        print("No episodes tracked yet.")
        return 0

    print(f"\nTracked Episodes ({len(episodes)} total):\n")
    print(f"{'Status':<10} {'Synced At':<20} {'Title'}")
    print("-" * 70)

    for guid, ep in sorted(episodes.items(), key=lambda x: x[1].synced_at, reverse=True):
        synced = ep.synced_at[:19] if ep.synced_at else "N/A"
        print(f"{ep.status:<10} {synced:<20} {ep.title[:40]}")

    print()
    print(f"Successful: {tracker.get_successful_count()}")
    print(f"Failed: {tracker.get_failed_count()}")

    return 0


def cmd_clear_failures(args: argparse.Namespace) -> int:
    """Handle the clear-failures command.

    Returns:
        Exit code (0 for success).
    """
    try:
        config = get_config()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    tracker = StateTracker(config.state_file)
    count = tracker.clear_failures()

    print(f"Cleared {count} failed records.")
    return 0


def cmd_test_connection(args: argparse.Namespace) -> int:
    """Handle the test-connection command.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        config = get_config()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    client = GhostClient(
        config.ghost_url,
        config.ghost_admin_api_key,
        config.ghost_api_version,
    )

    try:
        client.test_connection()
        print(f"Successfully connected to Ghost at {config.ghost_url}")
        return 0
    except GhostAPIError as e:
        print(f"Connection failed: {e}")
        return 1


def cmd_test_prx_connection(args: argparse.Namespace) -> int:
    """Handle the test-prx-connection command.

    Tests connectivity to the PRX Dovetail API by:
    1. Obtaining an OAuth2 access token
    2. Fetching the authorization endpoint

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        config = get_config()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    # Check for required PRX credentials
    if not config.prx_client_id or not config.prx_client_secret:
        print("Error: PRX_CLIENT_ID and PRX_CLIENT_SECRET must be set")
        print("Set these in your .env file or environment variables")
        return 1

    print(f"Testing PRX Dovetail API connection...")
    print(f"  ID endpoint: {config.prx_id_base_url}")
    print(f"  API endpoint: {config.prx_api_base_url}")

    # Step 1: Test OAuth2 authentication
    print("\n1. Testing OAuth2 authentication...")
    try:
        auth_client = PRXAuthClient(
            client_id=config.prx_client_id,
            client_secret=config.prx_client_secret,
            token_endpoint=f"{config.prx_id_base_url}/token",
        )
        token = auth_client.get_access_token()
        print(f"   Success! Obtained access token: {token[:20]}...")
    except PRXAuthError as e:
        print(f"   Failed: {e}")
        if e.response_body:
            print(f"   Response: {e.response_body}")
        return 1

    # Step 2: Test API authorization endpoint
    print("\n2. Testing API authorization endpoint...")
    try:
        api_client = DovetailClient(
            auth_client=auth_client,
            podcast_id=config.prx_podcast_id,
            api_base_url=config.prx_api_base_url,
        )
        auth_info = api_client.get_authorization()
        print(f"   Success! Authorization endpoint accessible")

        # Show available resources if present
        if "_links" in auth_info:
            links = auth_info["_links"]
            print(f"   Available resources: {', '.join(links.keys())}")

    except DovetailAPIError as e:
        print(f"   Failed: {e}")
        if e.response_body:
            print(f"   Response: {e.response_body}")
        return 1

    # Step 3: Test podcast access for all configured podcast IDs
    podcast_ids = config.prx_podcast_ids or ([config.prx_podcast_id] if config.prx_podcast_id else [])
    if podcast_ids:
        print(f"\n3. Testing podcast access ({len(podcast_ids)} podcast(s))...")
        for podcast_id in podcast_ids:
            try:
                episodes = api_client.get_episodes(
                    podcast_id=podcast_id,
                    per=1,
                )
                print(f"   Podcast {podcast_id}: OK")
                if episodes:
                    print(f"     Latest: {episodes[0].title[:50]}...")
            except DovetailAPIError as e:
                print(f"   Podcast {podcast_id}: FAILED - {e}")
                # Not a fatal error, podcast_id might be wrong

    print("\nPRX Dovetail API connection test passed!")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        prog="prx-to-ghost",
        description="Sync PRX/Dovetail podcast episodes to Ghost CMS.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync episodes from PRX feed to Ghost",
    )
    sync_parser.add_argument(
        "--status",
        choices=["draft", "published"],
        help="Post status (default: from config)",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and transform but don't publish",
    )
    sync_parser.add_argument(
        "--guid",
        help="Sync only the episode with this GUID",
    )
    sync_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of episodes to sync",
    )
    sync_parser.add_argument(
        "--file",
        help="Parse local XML file instead of fetching feed",
    )
    sync_parser.add_argument(
        "--feed-type",
        choices=["ttbook", "luminous"],
        default="ttbook",
        help="Feed type: ttbook (main feed) or luminous (psychedelics series)",
    )
    sync_parser.add_argument(
        "--feed-url",
        help="Override feed URL (default: from config or feed-type default)",
    )
    sync_parser.add_argument(
        "--source",
        choices=["api", "rss"],
        default="rss",
        help="Episode source: 'api' for Dovetail API, 'rss' for RSS feed (default: rss)",
    )
    sync_parser.add_argument(
        "--export-transcripts",
        action="store_true",
        help="Export transcripts to /transcripts folder in PRX-compatible formats (JSON, HTML)",
    )
    sync_parser.set_defaults(func=cmd_sync)

    # list command
    list_parser = subparsers.add_parser(
        "list",
        help="List tracked episodes",
    )
    list_parser.set_defaults(func=cmd_list)

    # clear-failures command
    clear_parser = subparsers.add_parser(
        "clear-failures",
        help="Clear failed records to retry sync",
    )
    clear_parser.set_defaults(func=cmd_clear_failures)

    # test-connection command
    test_parser = subparsers.add_parser(
        "test-connection",
        help="Test Ghost API connection",
    )
    test_parser.set_defaults(func=cmd_test_connection)

    # test-prx-connection command
    test_prx_parser = subparsers.add_parser(
        "test-prx-connection",
        help="Test PRX Dovetail API connection",
    )
    test_prx_parser.set_defaults(func=cmd_test_prx_connection)

    args = parser.parse_args(argv)

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Default to sync if no command given
    if args.command is None:
        args.command = "sync"
        args.status = None
        args.dry_run = False
        args.guid = None
        args.limit = None
        args.file = None
        args.feed_type = "ttbook"
        args.feed_url = None
        args.source = "rss"
        args.export_transcripts = False
        args.func = cmd_sync

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
