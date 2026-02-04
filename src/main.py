#!/usr/bin/env python3
"""PRX-to-Ghost Publisher CLI.

Sync podcast episodes from PRX/Dovetail RSS feed to Ghost CMS.
"""

from __future__ import annotations

import argparse
import json as json_module
import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from .config import ConfigError, get_config
from .content_builder import (
    build_ghost_post,
    build_jsonld_metadata,
    build_luminous_ghost_post,
    extract_slug_from_link,
    format_published_at,
    load_transcript,
)
from .waveform_peaks import (
    WaveformError,
    check_audiowaveform_installed,
    download_and_generate_peaks,
    download_audio_file,
    generate_peaks_for_episode,
    get_peaks_url,
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
from .og_image import download_image, generate_og_image
from .state_tracker import StateLockError, StateTracker

# Exit codes for CI/CD differentiation
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_CONFIG_ERROR = 2
EXIT_AUTH_ERROR = 3
EXIT_FEED_ERROR = 4
EXIT_LOCKED = 5

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
    primary_tag: str = "Wonder Cabinet",
    feed_type: str = "ttbook",
    feed_url: str = "",
    export_transcripts: bool = False,
    generate_peaks: bool = False,
    peaks_dir: Optional[Path] = None,
    ghost_url: str = "",
    upload_audio: bool = False,
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
        generate_peaks: If True, generate waveform peaks JSON files.
        peaks_dir: Directory to save peaks files (required if generate_peaks=True).
        ghost_url: Ghost site URL for building peaks URLs (required if generate_peaks=True).
        upload_audio: If True, download audio and upload to Ghost media library.

    Returns:
        Tuple of (published_count, skipped_count, failed_count).
    """
    published = 0
    skipped = 0
    failed = 0

    for episode in episodes:
        ep_start = time.monotonic()

        # Check if already published
        if tracker.is_published(episode.guid):
            logger.info(f"Skipping (already published): {episode.title}")
            skipped += 1
            continue

        # Image processing pipeline: download artwork → upload to Ghost → generate OG image
        ghost_image_url = None
        og_image_url = None

        if episode.image_url and not dry_run:
            img_temp_dir = Path(tempfile.mkdtemp(prefix="ghost_img_"))
            try:
                # Download square art from PRX
                img_path = download_image(episode.image_url, img_temp_dir)

                # Upload square art to Ghost → feature_image
                try:
                    ghost_image_url = client.upload_image(img_path)
                    logger.info(f"  Ghost image URL: {ghost_image_url}")
                except GhostAPIError as e:
                    logger.warning(f"  Image upload failed, using PRX URL: {e}")

                # Generate OG image (1200x630, black background)
                try:
                    og_path = generate_og_image(img_path, img_temp_dir / "og_image.jpg")
                    og_image_url = client.upload_image(og_path)
                    logger.info(f"  Ghost OG image URL: {og_image_url}")
                except GhostAPIError as e:
                    logger.warning(f"  OG image upload failed: {e}")
                except Exception as e:
                    logger.warning(f"  OG image generation failed: {e}")

            except Exception as e:
                logger.warning(f"  Image processing failed, using PRX URL: {e}")
            finally:
                shutil.rmtree(img_temp_dir, ignore_errors=True)

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

            # Audio upload + peaks generation pipeline
            peaks_url = None
            ghost_audio_url = None
            temp_audio_path = None

            if upload_audio and episode.enclosure_url and slug and not dry_run:
                # Combined pipeline: download audio → generate peaks → upload both to Ghost
                try:
                    logger.info(f"  Downloading audio + generating peaks for: {slug}")
                    temp_audio_path, peaks_path = download_and_generate_peaks(
                        audio_url=episode.enclosure_url,
                        episode_slug=slug,
                        peaks_dir=peaks_dir or Path("/tmp/peaks"),
                        pixels_per_second=20,
                    )
                    logger.info(f"  Generated peaks: {peaks_path}")

                    # Upload audio MP3 to Ghost
                    try:
                        logger.info(f"  Uploading audio to Ghost...")
                        ghost_audio_url = client.upload_media(temp_audio_path)
                        logger.info(f"  Ghost audio URL: {ghost_audio_url}")
                    except GhostAPIError as e:
                        logger.warning(f"  Audio upload failed, using PRX URL: {e}")

                    # Upload peaks JSON to Ghost (uses /files/upload, not /media/upload)
                    try:
                        logger.info(f"  Uploading peaks JSON to Ghost...")
                        peaks_url = client.upload_file(peaks_path)
                        logger.info(f"  Ghost peaks URL: {peaks_url}")
                    except GhostAPIError as e:
                        logger.warning(f"  Peaks upload failed: {e}")
                        # Fall back to theme assets path if available
                        if ghost_url:
                            peaks_url = get_peaks_url(slug, ghost_url)

                except WaveformError as e:
                    logger.warning(f"  Download/peaks pipeline failed: {e}")
                except Exception as e:
                    logger.warning(f"  Unexpected error in upload pipeline: {e}")
                finally:
                    # Clean up temp audio file (peaks file stays if uploaded)
                    if temp_audio_path and temp_audio_path.exists():
                        temp_audio_path.unlink(missing_ok=True)
                        # Clean up temp directory too
                        temp_dir = temp_audio_path.parent
                        if temp_dir.exists() and temp_dir.name.startswith("ghost_upload_"):
                            shutil.rmtree(temp_dir, ignore_errors=True)

            elif generate_peaks and episode.enclosure_url and slug:
                # Legacy peaks-only flow (no audio upload)
                try:
                    logger.info(f"  Generating waveform peaks for: {slug}")
                    peaks_path = generate_peaks_for_episode(
                        audio_url=episode.enclosure_url,
                        episode_slug=slug,
                        output_dir=peaks_dir,
                        pixels_per_second=20,
                    )
                    peaks_url = get_peaks_url(slug, ghost_url)
                    logger.info(f"  Generated peaks: {peaks_path}")
                    logger.info(f"  Peaks URL: {peaks_url}")
                except WaveformError as e:
                    logger.warning(f"  Failed to generate peaks: {e}")
                except Exception as e:
                    logger.warning(f"  Unexpected error generating peaks: {e}")

            ghost_post = build_luminous_ghost_post(
                episode,
                status=status,
                transcript=transcript,
                feed_url=feed_url or LUMINOUS_FEED_URL,
                peaks_url=peaks_url,
                ghost_audio_url=ghost_audio_url,
                ghost_image_url=ghost_image_url,
                og_image_url=og_image_url,
            )
        else:
            ghost_post = build_ghost_post(
                episode, status=status, primary_tag=primary_tag,
                ghost_image_url=ghost_image_url, og_image_url=og_image_url,
            )

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

            ep_elapsed = time.monotonic() - ep_start
            logger.info(f"Published: {episode.title} (ID: {ghost_post_id}) [{ep_elapsed:.1f}s]")
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
        Exit code (see EXIT_* constants).
    """
    sync_start = time.monotonic()

    try:
        config = get_config(env_name=args.env)
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return EXIT_CONFIG_ERROR

    # Override config with CLI args
    status = args.status or config.publish_status
    dry_run = args.dry_run or config.dry_run
    feed_type = args.feed_type
    source = args.source
    json_output = getattr(args, 'json_output', False)
    skip_confirm = getattr(args, 'yes', False)

    # Environment banner (ANSI colors: green for dev, red for prod)
    # Use sys.stderr to stay in sync with logging output
    if args.env == "prod":
        sys.stderr.write("\033[0;31m" + "=" * 60 + "\n")
        sys.stderr.write(f"  PRODUCTION  ·  {config.ghost_url}\n")
        sys.stderr.write("=" * 60 + "\033[0m\n")
    else:
        sys.stderr.write("\033[0;32m" + "=" * 60 + "\n")
        sys.stderr.write(f"  DEV  ·  {config.ghost_url}\n")
        sys.stderr.write("=" * 60 + "\033[0m\n")
    sys.stderr.flush()

    # Production confirmation prompt
    if args.env == "prod" and not dry_run and not skip_confirm:
        try:
            confirm = input(
                "\033[1;33m⚠  Sync to PRODUCTION — continue? [y/N] \033[0m"
            )
            if confirm.strip().lower() not in ("y", "yes"):
                logger.info("Aborted by user.")
                return EXIT_SUCCESS
        except (EOFError, KeyboardInterrupt):
            print()
            logger.info("Aborted.")
            return EXIT_SUCCESS

    # Determine if we should use API
    use_api = source == "api" or config.use_dovetail_api

    # Determine feed URL (for RSS mode)
    if args.feed_url:
        feed_url = args.feed_url
    elif feed_type == "luminous":
        feed_url = LUMINOUS_FEED_URL
    else:
        feed_url = config.prx_feed_url

    logger.info(f"Environment: {args.env} ({config.ghost_url})")
    logger.info(f"Starting sync (source={source}, feed_type={feed_type}, status={status}, dry_run={dry_run})")

    # Initialize state tracker and acquire lock for incremental sync
    tracker = StateTracker(config.state_file)

    if not dry_run:
        try:
            tracker.acquire_lock()
        except StateLockError as e:
            logger.error(str(e))
            return EXIT_LOCKED

    try:
        return _run_sync(
            args, config, tracker, status, dry_run, feed_type, source,
            use_api, feed_url, json_output, sync_start,
        )
    finally:
        tracker.release_lock()


def _run_sync(
    args: argparse.Namespace,
    config,
    tracker: StateTracker,
    status: str,
    dry_run: bool,
    feed_type: str,
    source: str,
    use_api: bool,
    feed_url: str,
    json_output: bool,
    sync_start: float,
) -> int:
    """Inner sync logic, separated so the lock is always released.

    Returns:
        Exit code (see EXIT_* constants).
    """
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
                return EXIT_CONFIG_ERROR
            if not podcast_ids:
                logger.error("PRX_PODCAST_ID or PRX_PODCAST_IDS required for API mode")
                return EXIT_CONFIG_ERROR

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
        return EXIT_FEED_ERROR
    except PRXAuthError as e:
        logger.error(f"PRX authentication failed: {e}")
        return EXIT_AUTH_ERROR
    except DovetailAPIError as e:
        logger.error(f"Dovetail API error: {e}")
        return EXIT_FEED_ERROR

    logger.info(f"Found {len(episodes)} episodes in feed")

    # Filter by GUID if specified
    if args.guid:
        episodes = [e for e in episodes if e.guid == args.guid]
        if not episodes:
            logger.error(f"No episode found with GUID: {args.guid}")
            return EXIT_FEED_ERROR
        logger.info(f"Filtered to 1 episode by GUID")

    # Limit if specified
    if args.limit and args.limit > 0:
        episodes = episodes[: args.limit]
        logger.info(f"Limited to {len(episodes)} episodes")

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
            return EXIT_AUTH_ERROR
    else:
        client = None  # type: ignore

    # Sync episodes
    export_transcripts = args.export_transcripts
    generate_peaks = args.generate_peaks
    upload_audio = args.upload_audio

    # --upload-audio implies --generate-peaks (audio download is needed for both)
    if upload_audio:
        generate_peaks = True

    # Check audiowaveform if peaks generation requested
    if generate_peaks and not check_audiowaveform_installed():
        logger.error("audiowaveform not installed. Install with: brew install audiowaveform")
        logger.error("Peaks generation disabled.")
        generate_peaks = False
        if upload_audio:
            logger.error("Audio upload requires peaks generation. Upload disabled.")
            upload_audio = False

    # Set peaks directory (temp dir for upload mode, theme assets for generate-only mode)
    peaks_dir = None
    if generate_peaks:
        peaks_dir = args.peaks_dir
        if peaks_dir:
            peaks_dir = Path(peaks_dir)
        elif upload_audio:
            # Upload mode uses temp dir since peaks go to Ghost media library
            peaks_dir = Path(tempfile.mkdtemp(prefix="peaks_"))
        else:
            logger.error("--peaks-dir required when --generate-peaks is enabled (without --upload-audio)")
            return EXIT_CONFIG_ERROR

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
        generate_peaks=generate_peaks,
        peaks_dir=peaks_dir,
        ghost_url=config.ghost_url,
        upload_audio=upload_audio,
    )

    elapsed = round(time.monotonic() - sync_start, 1)

    # Summary
    logger.info(
        f"Sync complete: {published} published, {skipped} skipped, "
        f"{failed} failed [{elapsed}s]"
    )

    # Structured JSON output for CI/CD consumption
    if json_output:
        exit_status = "success" if failed == 0 else "partial_failure"
        summary = {
            "status": exit_status,
            "published": published,
            "skipped": skipped,
            "failed": failed,
            "feed_type": feed_type,
            "source": source,
            "dry_run": dry_run,
            "elapsed_seconds": elapsed,
        }
        print(json_module.dumps(summary))

    return EXIT_SUCCESS if failed == 0 else EXIT_PARTIAL_FAILURE


def cmd_list(args: argparse.Namespace) -> int:
    """Handle the list command.

    Returns:
        Exit code (0 for success).
    """
    try:
        config = get_config(env_name=args.env)
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
        config = get_config(env_name=args.env)
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
        config = get_config(env_name=args.env)
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
        config = get_config(env_name=args.env)
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
        logger.debug(f"Obtained access token: {token[:20]}...")
        print(f"   Success! Obtained access token.")
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


def cmd_update_metadata(args: argparse.Namespace) -> int:
    """Handle the update-metadata command.

    Updates existing Ghost posts to use simplified tags (show tag only)
    and adds JSON-LD structured data via codeinjection_head.

    This is a migration command to apply the new tag structure to
    previously imported episodes without re-importing them.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        config = get_config(env_name=args.env)
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    dry_run = args.dry_run
    feed_type = getattr(args, 'feed_type', 'luminous')

    # Determine feed URL
    if args.feed_url:
        feed_url = args.feed_url
    elif feed_type == "luminous":
        feed_url = LUMINOUS_FEED_URL
    else:
        feed_url = config.prx_feed_url

    logger.info(f"Starting metadata update (feed_type={feed_type}, dry_run={dry_run})")

    # Load state tracker to get existing post mappings
    tracker = StateTracker(config.state_file)
    published = tracker.get_all_published()

    if not published:
        logger.info("No published episodes found in state tracker.")
        return 0

    # Filter by feed type based on GUID prefix
    # Luminous GUIDs start with 'prx_3329_', TTBOOK with 'prx_120_'
    feed_prefix = "prx_3329_" if feed_type == "luminous" else "prx_120_"
    episodes_to_update = {
        guid: data for guid, data in published.items()
        if guid.startswith(feed_prefix)
    }

    if not episodes_to_update:
        logger.info(f"No {feed_type} episodes found to update.")
        return 0

    logger.info(f"Found {len(episodes_to_update)} {feed_type} episodes to update")

    # Fetch current feed to get episode metadata (categories, etc.)
    try:
        logger.info(f"Fetching feed: {feed_url}")
        feed_episodes = get_episodes(feed_url)
        # Create lookup by GUID
        episodes_by_guid = {ep.guid: ep for ep in feed_episodes}
        logger.info(f"Found {len(feed_episodes)} episodes in feed")
    except (FeedFetchError, FeedParseError) as e:
        logger.error(f"Failed to fetch feed: {e}")
        return 1

    # Initialize Ghost client
    if not dry_run:
        client = GhostClient(
            config.ghost_url,
            config.ghost_admin_api_key,
            config.ghost_api_version,
        )
        try:
            client.test_connection()
        except GhostAPIError as e:
            logger.error(f"Ghost connection failed: {e}")
            return 1
    else:
        client = None

    # Determine show tag based on feed type
    show_tag = "Luminous" if feed_type == "luminous" else "Wonder Cabinet"

    # Update each episode
    updated = 0
    skipped = 0
    failed = 0

    for guid, state_data in episodes_to_update.items():
        ghost_post_id = state_data.ghost_post_id
        title = state_data.title

        # Get episode metadata from feed
        episode = episodes_by_guid.get(guid)
        if not episode:
            logger.warning(f"Episode not found in feed: {title} ({guid})")
            skipped += 1
            continue

        # Build new metadata
        new_tags = [{"name": show_tag}]
        jsonld = build_jsonld_metadata(episode, show_name=show_tag)

        if dry_run:
            logger.info(f"[DRY RUN] Would update: {title}")
            logger.info(f"  Post ID: {ghost_post_id}")
            logger.info(f"  New tags: {new_tags}")
            logger.info(f"  Categories in JSON-LD: {episode.categories}")
            updated += 1
            continue

        # Fetch current post to get updated_at timestamp
        try:
            current_post = client.get_post(ghost_post_id)
            updated_at = current_post.get("updated_at")

            if not updated_at:
                logger.error(f"No updated_at for post: {title}")
                failed += 1
                continue

            # Create minimal update post (only changing tags and codeinjection_head)
            # We need to preserve the existing content
            update_post = GhostPost(
                title=current_post.get("title", title),
                html=current_post.get("html", ""),
                tags=new_tags,
                codeinjection_head=jsonld,
            )

            # Update the post
            result = client.update_post(ghost_post_id, update_post, updated_at)
            logger.info(f"Updated: {title}")
            updated += 1

        except GhostAPIError as e:
            logger.error(f"Failed to update '{title}': {e}")
            failed += 1

    # Summary
    logger.info(f"Update complete: {updated} updated, {skipped} skipped, {failed} failed")

    return 0 if failed == 0 else 1


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
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        default="dev",
        help="Target environment (default: dev). Loads .env.{env} and uses data/published_episodes.{env}.json",
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
    sync_parser.add_argument(
        "--generate-peaks",
        action="store_true",
        help="Generate waveform peaks JSON files for Wavesurfer (requires audiowaveform CLI)",
    )
    sync_parser.add_argument(
        "--peaks-dir",
        help="Directory to save peaks JSON files (e.g., /path/to/theme/assets/peaks)",
    )
    sync_parser.add_argument(
        "--upload-audio",
        action="store_true",
        help="Download audio and upload to Ghost media library (solves CORS issues, implies --generate-peaks)",
    )
    sync_parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit structured JSON summary to stdout (for CI/CD consumption)",
    )
    sync_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts (for automation/CI)",
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

    # update-metadata command
    update_parser = subparsers.add_parser(
        "update-metadata",
        help="Update existing posts with simplified tags and JSON-LD structured data",
    )
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    update_parser.add_argument(
        "--feed-type",
        choices=["ttbook", "luminous"],
        default="luminous",
        help="Feed type to update (default: luminous)",
    )
    update_parser.add_argument(
        "--feed-url",
        help="Override feed URL",
    )
    update_parser.set_defaults(func=cmd_update_metadata)

    # Set defaults on the main parser so no-subcommand invocation works
    parser.set_defaults(
        func=cmd_sync,
        status=None,
        dry_run=False,
        guid=None,
        limit=None,
        file=None,
        feed_type="ttbook",
        feed_url=None,
        source="rss",
        export_transcripts=False,
        generate_peaks=False,
        peaks_dir=None,
        upload_audio=False,
        json_output=False,
        yes=False,
    )

    args = parser.parse_args(argv)

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
