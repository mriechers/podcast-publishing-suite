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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import subprocess

from .config import ConfigError, get_config
from .content_builder import (
    build_ghost_post,
    build_jsonld_metadata,
    build_luminous_ghost_post,
    build_tags,
    build_transcript_section_html,
    extract_slug_from_link,
    slugify_title,
    fetch_rss_transcript,
    format_published_at,
    format_rss_transcript_html,
    format_transcript_html,
    load_transcript,
    load_wc_transcript,
    process_lexical_visibility,
)
from .waveform_peaks import (
    WaveformError,
    check_audiowaveform_installed,
    download_and_generate_peaks,
    download_audio_file,
    generate_peaks_for_episode,
    generate_peaks_json,
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


def download_media_segments(
    segments: list[dict],
    output_path: Path,
    fallback_url: str = "",
) -> None:
    """Download audio from media segments, concatenating with ffmpeg if needed.

    Uses the direct CDN URLs from the Dovetail media[] array, which work
    for both scheduled and published episodes (unlike the enclosure tracking
    URL which 404s for scheduled episodes).

    Args:
        segments: List of media segment dicts with 'href' and 'fileName' keys.
        output_path: Path to save the final concatenated audio file.
        fallback_url: Enclosure URL to try if no segments are available.

    Raises:
        WaveformError: If download or concatenation fails.
    """
    if not segments and fallback_url:
        download_audio_file(fallback_url, output_path)
        return
    if not segments:
        raise WaveformError("No media segments or fallback URL available")

    if len(segments) == 1:
        # Single segment — download directly
        download_audio_file(segments[0]["href"], output_path)
        return

    # Multiple segments — download each, then concatenate with ffmpeg
    temp_dir = output_path.parent
    segment_paths = []

    try:
        for i, seg in enumerate(segments):
            seg_path = temp_dir / f"segment_{i:03d}.mp3"
            download_audio_file(seg["href"], seg_path)
            segment_paths.append(seg_path)

        # Build ffmpeg concat file
        concat_list = temp_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for sp in segment_paths:
                f.write(f"file '{sp}'\n")

        # Concatenate with ffmpeg
        logger.info(f"  Concatenating {len(segment_paths)} audio segments with ffmpeg...")
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_list), "-c", "copy", str(output_path)],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise WaveformError(
                f"ffmpeg concat failed (exit {result.returncode})",
                result.stderr[-500:] if result.stderr else "",
            )

        file_size = output_path.stat().st_size
        logger.info(f"  Concatenated audio: {file_size:,} bytes")

    finally:
        # Clean up segment files and concat list
        for sp in segment_paths:
            sp.unlink(missing_ok=True)
        concat_list = temp_dir / "concat.txt"
        if concat_list.exists():
            concat_list.unlink()


@dataclass
class SyncResult:
    """Result of syncing episodes to Ghost.

    Used for detailed JSON output in CI/CD workflows.
    """
    published: int = 0
    skipped: int = 0
    failed: int = 0
    new_episodes: list = None  # Episodes that would be/were published
    published_posts: list = None  # Details of actually published posts

    def __post_init__(self):
        if self.new_episodes is None:
            self.new_episodes = []
        if self.published_posts is None:
            self.published_posts = []

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "published": self.published,
            "skipped": self.skipped,
            "failed": self.failed,
            "new_episodes": self.new_episodes,
            "published_posts": self.published_posts,
        }


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
    dovetail_client: Optional[DovetailClient] = None,
    ghost_site_url: str = "",
    transcript_dir: Optional[Path] = None,
) -> SyncResult:
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
        ghost_url: Ghost admin URL for API operations and building peaks URLs.
        upload_audio: If True, download audio and upload to Ghost media library.
        dovetail_client: Optional DovetailClient for PRX writeback (sets episode link to Ghost URL).
        ghost_site_url: Public site URL for PRX writeback canonical links. Defaults to ghost_url.
        transcript_dir: Optional directory containing a transcript.txt file (canonical episode folder).
            When provided, overrides default transcript search paths for both WC and Luminous.

    Returns:
        SyncResult with counts and episode details.
    """
    result = SyncResult()

    for episode in episodes:
        ep_start = time.monotonic()

        # Check if already published
        if tracker.is_published(episode.guid):
            logger.info(f"Skipping (already published): {episode.title}")
            result.skipped += 1
            continue

        # Extract podcast ID from GUID for new_episodes list
        podcast_id = ""
        if episode.guid.startswith("prx_"):
            parts = episode.guid.split("_")
            if len(parts) >= 2:
                podcast_id = parts[1]

        # Track as new episode (for dry-run detection mode)
        result.new_episodes.append({
            "guid": episode.guid,
            "title": episode.title,
            "podcast_id": podcast_id,
            "pub_date": episode.pub_date.isoformat() if episode.pub_date else "",
        })

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
            slug = extract_slug_from_link(episode.link, episode.title)
            transcript = load_transcript(slug, cache_dir=transcript_dir) if slug else None
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

            # RSS transcript fallback: if no cached transcript, try RSS <podcast:transcript>
            rss_transcript_html = None
            if not transcript and episode.transcript_url:
                logger.info(f"  Fetching RSS transcript: {episode.transcript_url}")
                raw = fetch_rss_transcript(episode.transcript_url, episode.transcript_type)
                if raw:
                    rss_transcript_html = format_rss_transcript_html(raw, episode.transcript_type)
                    logger.info(f"  Formatted RSS transcript ({episode.transcript_type})")

            # Audio upload + peaks generation pipeline
            peaks_url = None
            ghost_audio_url = None
            temp_audio_path = None

            if upload_audio and (episode.media_segments or episode.enclosure_url) and slug and not dry_run:
                # Audio upload pipeline (peaks generation optional)
                try:
                    # Download audio — prefer media segments (direct CDN, works for scheduled episodes)
                    temp_dir = Path(tempfile.mkdtemp(prefix="ghost_upload_"))
                    temp_audio_path = temp_dir / f"{slug}.mp3"
                    download_media_segments(episode.media_segments, temp_audio_path, episode.enclosure_url)

                    # Upload audio MP3 to Ghost
                    try:
                        logger.info(f"  Uploading audio to Ghost...")
                        ghost_audio_url = client.upload_media(temp_audio_path)
                        logger.info(f"  Ghost audio URL: {ghost_audio_url}")
                    except GhostAPIError as e:
                        logger.warning(f"  Audio upload failed, using PRX URL: {e}")

                    # Generate and upload peaks if audiowaveform is available
                    if generate_peaks:
                        try:
                            peaks_path = (peaks_dir or Path("/tmp/peaks")) / f"{slug}.json"
                            peaks_path.parent.mkdir(parents=True, exist_ok=True)
                            generate_peaks_json(temp_audio_path, peaks_path)
                            logger.info(f"  Generated peaks: {peaks_path}")
                            peaks_url = client.upload_file(peaks_path)
                            logger.info(f"  Ghost peaks URL: {peaks_url}")
                        except (WaveformError, GhostAPIError) as e:
                            logger.warning(f"  Peaks generation/upload failed: {e}")
                            if ghost_url:
                                peaks_url = get_peaks_url(slug, ghost_url)

                except WaveformError as e:
                    logger.warning(f"  Audio download failed: {e}")
                except Exception as e:
                    logger.warning(f"  Unexpected error in upload pipeline: {e}")
                finally:
                    # Clean up temp audio file
                    if temp_audio_path and temp_audio_path.exists():
                        temp_audio_path.unlink(missing_ok=True)
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
                transcript_html=rss_transcript_html,
                ghost_url=ghost_url,
                post_slug=slug,
            )
        else:
            # Try to load local transcript first (from /transcripts directory)
            ttbook_transcript_html = None
            wc_transcript = load_wc_transcript(episode.title, transcript_dir=transcript_dir)
            if wc_transcript:
                logger.info(f"  Found local transcript for: {episode.title}")
                ttbook_transcript_html = format_transcript_html(wc_transcript)

            # Fall back to RSS transcript if no local transcript found
            if not ttbook_transcript_html and episode.transcript_url:
                logger.info(f"  Fetching RSS transcript: {episode.transcript_url}")
                raw = fetch_rss_transcript(episode.transcript_url, episode.transcript_type)
                if raw:
                    ttbook_transcript_html = format_rss_transcript_html(raw, episode.transcript_type)
                    logger.info(f"  Formatted RSS transcript ({episode.transcript_type})")

            # Audio upload pipeline for Wonder Cabinet (same as Luminous)
            wc_peaks_url = None
            wc_ghost_audio_url = None
            wc_slug = extract_slug_from_link(episode.link, episode.title)

            if upload_audio and (episode.media_segments or episode.enclosure_url) and wc_slug and not dry_run:
                try:
                    # Download audio — prefer media segments (direct CDN, works for scheduled episodes)
                    temp_dir = Path(tempfile.mkdtemp(prefix="ghost_upload_"))
                    temp_audio_path = temp_dir / f"{wc_slug}.mp3"
                    download_media_segments(episode.media_segments, temp_audio_path, episode.enclosure_url)

                    # Upload audio MP3 to Ghost
                    try:
                        logger.info(f"  Uploading audio to Ghost...")
                        wc_ghost_audio_url = client.upload_media(temp_audio_path)
                        logger.info(f"  Ghost audio URL: {wc_ghost_audio_url}")
                    except GhostAPIError as e:
                        logger.warning(f"  Audio upload failed, using PRX URL: {e}")

                    # Generate and upload peaks if audiowaveform is available
                    if generate_peaks:
                        try:
                            peaks_path = (peaks_dir or Path("/tmp/peaks")) / f"{wc_slug}.json"
                            peaks_path.parent.mkdir(parents=True, exist_ok=True)
                            generate_peaks_json(temp_audio_path, peaks_path)
                            logger.info(f"  Generated peaks: {peaks_path}")
                            wc_peaks_url = client.upload_file(peaks_path)
                            logger.info(f"  Ghost peaks URL: {wc_peaks_url}")
                        except (WaveformError, GhostAPIError) as e:
                            logger.warning(f"  Peaks generation/upload failed: {e}")

                except WaveformError as e:
                    logger.warning(f"  Audio download failed: {e}")
                except Exception as e:
                    logger.warning(f"  Unexpected error in upload pipeline: {e}")
                finally:
                    if temp_audio_path and temp_audio_path.exists():
                        temp_audio_path.unlink(missing_ok=True)
                        temp_dir = temp_audio_path.parent
                        if temp_dir.exists() and temp_dir.name.startswith("ghost_upload_"):
                            shutil.rmtree(temp_dir, ignore_errors=True)

            ghost_post = build_ghost_post(
                episode, status=status, primary_tag=primary_tag,
                ghost_image_url=ghost_image_url, og_image_url=og_image_url,
                peaks_url=wc_peaks_url,
                ghost_audio_url=wc_ghost_audio_url,
                transcript_html=ttbook_transcript_html,
                ghost_url=ghost_url,
                post_slug=wc_slug,
            )

        if dry_run:
            logger.info(f"[DRY RUN] Would publish: {episode.title}")
            logger.debug(f"  Status: {status}")
            logger.debug(f"  Tags: {[t['name'] for t in ghost_post.tags]}")
            result.published += 1
            continue

        # Publish to Ghost
        try:
            post_result = client.create_post(ghost_post)
            ghost_post_id = post_result.get("id", "")
            ghost_slug = post_result.get("slug", "")

            # Lexical post-processing: apply visibility controls
            # (audio player = web-only, email CTA = email-only, transcript = web-only)
            if ghost_post_id:
                try:
                    lexical_post = client.get_post_with_lexical(ghost_post_id)
                    lexical_str = lexical_post.get("lexical")
                    if lexical_str:
                        modified_lexical = process_lexical_visibility(lexical_str)
                        client.update_post_lexical(
                            ghost_post_id, modified_lexical,
                            lexical_post.get("updated_at"),
                        )
                        logger.info(f"  Applied Lexical visibility controls")
                except Exception as e:
                    logger.warning(f"  Lexical visibility post-processing failed: {e}")

            # PRX writeback: set episode url to public Ghost canonical URL
            site_url = ghost_site_url or ghost_url
            if dovetail_client and ghost_slug and site_url:
                try:
                    url_prefix = "luminous" if feed_type == "luminous" else None
                    base = site_url.rstrip("/")
                    if url_prefix:
                        canonical = f"{base}/{url_prefix}/{ghost_slug}/"
                    else:
                        canonical = f"{base}/{ghost_slug}/"
                    success = dovetail_client.set_episode_link(episode.guid, canonical)
                    if success:
                        tracker.record_prx_writeback(episode.guid)
                        logger.info(f"  PRX writeback: {canonical}")
                    else:
                        logger.warning(f"  PRX writeback: episode not found for GUID {episode.guid}")
                except Exception as e:
                    logger.warning(f"  PRX writeback failed: {e}")

            # Record the publish
            tracker.record_publish(
                guid=episode.guid,
                ghost_post_id=ghost_post_id,
                title=episode.title,
                published_at=format_published_at(episode),
                status=status,
            )

            # Update ghost_slug in state tracker
            if ghost_slug:
                tracker.update_ghost_slug(episode.guid, ghost_slug)

            ep_elapsed = time.monotonic() - ep_start
            logger.info(f"Published: {episode.title} (ID: {ghost_post_id}) [{ep_elapsed:.1f}s]")
            result.published += 1

            # Track published post details for JSON output
            result.published_posts.append({
                "guid": episode.guid,
                "ghost_post_id": ghost_post_id,
                "slug": ghost_slug,
                "title": episode.title,
            })

        except GhostAPIError as e:
            logger.error(f"Failed to publish '{episode.title}': {e}")
            tracker.record_failure(
                guid=episode.guid,
                title=episode.title,
                published_at=format_published_at(episode),
            )
            result.failed += 1

    return result


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
    api_client = None  # Set when using Dovetail API (enables PRX writeback)
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
    upload_audio = not getattr(args, 'no_upload_audio', False)

    # --upload-audio implies --generate-peaks (audio download is needed for both)
    if upload_audio:
        generate_peaks = True

    # Check audiowaveform if peaks generation requested
    if generate_peaks and not check_audiowaveform_installed():
        logger.warning("audiowaveform not installed. Install with: brew install audiowaveform")
        logger.warning("Peaks generation disabled (audio upload will still proceed).")
        generate_peaks = False

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

    # Resolve transcript directory from CLI arg
    transcript_dir = None
    if hasattr(args, 'transcript_dir') and args.transcript_dir:
        transcript_dir = Path(args.transcript_dir)

    sync_result = sync_episodes(
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
        dovetail_client=api_client,
        ghost_site_url=config.ghost_site_url,
        transcript_dir=transcript_dir,
    )

    elapsed = round(time.monotonic() - sync_start, 1)

    # Summary
    logger.info(
        f"Sync complete: {sync_result.published} published, {sync_result.skipped} skipped, "
        f"{sync_result.failed} failed [{elapsed}s]"
    )

    # Structured JSON output for CI/CD consumption
    if json_output:
        exit_status = "success" if sync_result.failed == 0 else "partial_failure"
        summary = {
            "status": exit_status,
            "published": sync_result.published,
            "skipped": sync_result.skipped,
            "failed": sync_result.failed,
            "feed_type": feed_type,
            "source": source,
            "dry_run": dry_run,
            "elapsed_seconds": elapsed,
            # New fields for CI/CD workflows
            "new_episodes": sync_result.new_episodes,
            "published_posts": sync_result.published_posts,
        }
        print(json_module.dumps(summary))

    return EXIT_SUCCESS if sync_result.failed == 0 else EXIT_PARTIAL_FAILURE


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

        # Extract slug from episode link for canonical URL generation
        post_slug = extract_slug_from_link(episode.link, episode.title)

        # Determine URL prefix based on feed type
        # Luminous episodes live at /luminous/{slug}/, Wonder Cabinet at /{slug}/
        url_prefix = "luminous" if feed_type == "luminous" else None

        # Build new metadata (show tag public, categories as internal tags)
        new_tags = build_tags(episode, primary_tag=show_tag)
        jsonld = build_jsonld_metadata(
            episode,
            show_name=show_tag,
            ghost_url=config.ghost_url,
            post_slug=post_slug,
            url_prefix=url_prefix,
        )

        if dry_run:
            logger.info(f"[DRY RUN] Would update: {title}")
            logger.info(f"  Post ID: {ghost_post_id}")
            logger.info(f"  New tags: {new_tags}")
            logger.info(f"  Categories in JSON-LD: {episode.categories}")
            logger.info(f"  Canonical URL: {config.ghost_url}/{url_prefix + '/' if url_prefix else ''}{post_slug}/")
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

            # Build canonical URL for the post
            if post_slug:
                base = config.ghost_url.rstrip('/')
                if url_prefix:
                    canonical_url = f"{base}/{url_prefix}/{post_slug}/"
                else:
                    canonical_url = f"{base}/{post_slug}/"
            else:
                canonical_url = episode.link  # Fallback

            # Create minimal update post (only changing tags, codeinjection_head, and canonical_url)
            # We need to preserve the existing content
            update_post = GhostPost(
                title=current_post.get("title", title),
                html=current_post.get("html", ""),
                tags=new_tags,
                codeinjection_head=jsonld,
                canonical_url=canonical_url,
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


def cmd_update_transcripts(args: argparse.Namespace) -> int:
    """Handle the update-transcripts command.

    Fetches RSS transcripts and adds them to existing Ghost posts
    that don't yet have transcripts.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        config = get_config(env_name=args.env)
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    dry_run = args.dry_run
    target_guid = getattr(args, 'guid', None)

    # Determine feed URL
    if args.feed_url:
        feed_url = args.feed_url
    else:
        feed_url = LUMINOUS_FEED_URL

    logger.info(f"Starting transcript update (dry_run={dry_run})")

    # Load state tracker
    tracker = StateTracker(config.state_file)
    published = tracker.get_all_published()

    if not published:
        logger.info("No published episodes found in state tracker.")
        return 0

    # Filter to episodes that haven't had transcripts synced
    candidates = {}
    for guid, ep_state in published.items():
        if target_guid and guid != target_guid:
            continue
        if ep_state.transcript_synced:
            continue
        if ep_state.status == "failed":
            continue
        candidates[guid] = ep_state

    if not candidates:
        logger.info("No episodes need transcript updates.")
        return 0

    logger.info(f"Found {len(candidates)} candidate episodes for transcript update")

    # Fetch current RSS feed to get transcript URLs
    try:
        logger.info(f"Fetching feed: {feed_url}")
        feed_episodes = get_episodes(feed_url)
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

    updated = 0
    skipped = 0
    failed = 0

    for guid, ep_state in candidates.items():
        title = ep_state.title
        ghost_post_id = ep_state.ghost_post_id

        # Find episode in RSS feed
        episode = episodes_by_guid.get(guid)
        if not episode or not episode.transcript_url:
            logger.debug(f"No transcript URL for: {title}")
            skipped += 1
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would add transcript to: {title}")
            logger.info(f"  Transcript URL: {episode.transcript_url}")
            logger.info(f"  Transcript type: {episode.transcript_type}")
            updated += 1
            continue

        # Fetch current Ghost post to check for existing transcript
        try:
            current_post = client.get_post(ghost_post_id)
            current_html = current_post.get("html", "")
            updated_at = current_post.get("updated_at")

            if not updated_at:
                logger.error(f"No updated_at for post: {title}")
                failed += 1
                continue

            # Skip if transcript already present in post
            if 'id="episode-transcript"' in current_html:
                logger.info(f"Transcript already present: {title}")
                tracker.record_transcript_synced(guid)
                skipped += 1
                continue

            # Fetch and format transcript from RSS
            raw = fetch_rss_transcript(episode.transcript_url, episode.transcript_type)
            if not raw:
                logger.warning(f"Failed to fetch transcript for: {title}")
                skipped += 1
                continue

            transcript_html = format_rss_transcript_html(raw, episode.transcript_type)
            if not transcript_html:
                logger.warning(f"Empty transcript after formatting: {title}")
                skipped += 1
                continue

            # Append transcript section to existing post HTML
            transcript_section = build_transcript_section_html(transcript_html)
            new_html = current_html + "\n" + transcript_section

            # Update the Ghost post
            update_post = GhostPost(
                title=current_post.get("title", title),
                html=new_html,
            )
            client.update_post(ghost_post_id, update_post, updated_at)
            tracker.record_transcript_synced(guid)
            logger.info(f"Added transcript to: {title}")
            updated += 1

        except GhostAPIError as e:
            logger.error(f"Failed to update '{title}': {e}")
            failed += 1

    logger.info(f"Transcript update complete: {updated} updated, {skipped} skipped, {failed} failed")
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
        "--transcript-dir",
        help="Directory containing transcript.txt (canonical episode folder). Overrides default transcript search paths.",
    )
    sync_parser.add_argument(
        "--no-upload-audio",
        action="store_true",
        help="Skip downloading audio and uploading to Ghost media library (use PRX tracking URLs instead)",
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

    # update-transcripts command
    transcript_parser = subparsers.add_parser(
        "update-transcripts",
        help="Add RSS transcripts to existing Ghost posts that don't have them yet",
    )
    transcript_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    transcript_parser.add_argument(
        "--guid",
        help="Update only the episode with this GUID",
    )
    transcript_parser.add_argument(
        "--feed-url",
        help="Override feed URL (default: Luminous feed)",
    )
    transcript_parser.set_defaults(func=cmd_update_transcripts)

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
        no_upload_audio=False,
        transcript_dir=None,
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
