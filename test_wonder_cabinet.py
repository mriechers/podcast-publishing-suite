#!/usr/bin/env python3
"""Test script to fetch the first episode from Wonder Cabinet using Dovetail API."""

import json
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.prx_auth import PRXAuthClient, PRXAuthError
from src.dovetail_client import DovetailClient, DovetailAPIError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Fetch and display the first episode from Wonder Cabinet."""

    # Get credentials from environment
    client_id = os.getenv("PRX_CLIENT_ID")
    client_secret = os.getenv("PRX_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error("PRX_CLIENT_ID and PRX_CLIENT_SECRET environment variables are required")
        logger.info("Please set them in your .env file or environment")
        return 1

    # Wonder Cabinet podcast ID
    podcast_id = "120"

    try:
        logger.info("Authenticating with PRX Dovetail API...")
        auth_client = PRXAuthClient(client_id, client_secret)

        logger.info("First, let's check what podcasts are available...")
        dovetail_client = DovetailClient(auth_client, podcast_id=podcast_id)

        # List podcasts to see what's available
        podcasts = dovetail_client.get_podcasts(per=50)
        logger.info(f"Found {len(podcasts)} podcasts")

        # Look for Wonder Cabinet or TTBOOK
        wonder_cabinet_podcast = None
        for p in podcasts:
            title = p.get("title", "")
            pid = str(p.get("id", ""))
            logger.info(f"  - Podcast ID {pid}: {title}")
            if pid == podcast_id or "ttbook" in title.lower() or "wonder" in title.lower() or "best of our knowledge" in title.lower():
                wonder_cabinet_podcast = p
                logger.info(f"    ^ This looks like Wonder Cabinet!")

        if wonder_cabinet_podcast:
            logger.info(f"\nUsing podcast: {wonder_cabinet_podcast.get('title')} (ID: {wonder_cabinet_podcast.get('id')})")
            podcast_id = str(wonder_cabinet_podcast.get('id'))

        logger.info(f"\nFetching episodes for Wonder Cabinet (podcast ID: {podcast_id})...")

        # Fetch first page of episodes (should get the most recent ones)
        episodes = dovetail_client.get_episodes(podcast_id=podcast_id, per=1)

        if not episodes:
            logger.warning(f"No episodes found with client filtering for podcast ID {podcast_id}")
            logger.info("Fetching episodes directly from API...")
            # Try getting episodes without client-side filtering and parse manually
            response = dovetail_client._make_request("GET", "/authorization/episodes", params={"page": 1, "per": 50})

            # Extract items from response
            if "_embedded" in response and "prx:items" in response["_embedded"]:
                items = response["_embedded"]["prx:items"]
                logger.info(f"Found {len(items)} raw episode items")

                # Find episodes for our podcast
                for item in items:
                    # Check podcast ID from _links
                    podcast_link = item.get("_links", {}).get("prx:podcast", {}).get("href", "")
                    item_podcast_id = podcast_link.rstrip("/").split("/")[-1] if podcast_link else ""

                    logger.debug(f"Episode '{item.get('title', 'Unknown')}' belongs to podcast: {item_podcast_id}")

                    if item_podcast_id == podcast_id:
                        logger.info(f"\nFound Wonder Cabinet episode!")
                        try:
                            episode = dovetail_client._parse_api_episode(item)
                            episodes = [episode]
                            break
                        except Exception as e:
                            logger.error(f"Failed to parse episode: {e}")
                            continue

            if not episodes:
                logger.error("Could not find any Wonder Cabinet episodes in the response")
                return 1

        # Display the first episode
        episode = episodes[0]

        print("\n" + "="*80)
        print("FIRST EPISODE FROM WONDER CABINET")
        print("="*80)
        print(f"\nTitle: {episode.title}")
        print(f"GUID: {episode.guid}")
        print(f"Published: {episode.pub_date}")
        print(f"Duration: {episode.duration}")
        print(f"Link: {episode.link}")
        print(f"\nSubtitle: {episode.subtitle}")
        print(f"\nDescription (first 200 chars):")
        print(episode.description[:200] + "..." if len(episode.description) > 200 else episode.description)
        print(f"\nImage URL: {episode.image_url}")
        print(f"Audio URL: {episode.enclosure_url}")
        print(f"Audio Type: {episode.enclosure_type}")
        print(f"\nCategories: {', '.join(episode.categories) if episode.categories else 'None'}")
        print(f"Episode Type: {episode.episode_type}")
        print(f"Author: {episode.author}")

        print("\n" + "="*80)
        print("FULL EPISODE DATA (JSON)")
        print("="*80)

        # Convert episode to dict for JSON display
        episode_dict = {
            "guid": episode.guid,
            "title": episode.title,
            "subtitle": episode.subtitle,
            "description": episode.description,
            "pub_date": episode.pub_date.isoformat(),
            "duration": episode.duration,
            "link": episode.link,
            "image_url": episode.image_url,
            "enclosure_url": episode.enclosure_url,
            "enclosure_type": episode.enclosure_type,
            "categories": episode.categories,
            "episode_type": episode.episode_type,
            "author": episode.author,
        }

        print(json.dumps(episode_dict, indent=2))
        print("\n" + "="*80)

        return 0

    except PRXAuthError as e:
        logger.error(f"Authentication failed: {e}")
        if hasattr(e, "response_body") and e.response_body:
            logger.error(f"Response: {e.response_body}")
        return 1

    except DovetailAPIError as e:
        logger.error(f"API error: {e}")
        if hasattr(e, "response_body") and e.response_body:
            logger.error(f"Response: {e.response_body}")
        return 1

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
