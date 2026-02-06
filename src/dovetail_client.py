"""Dovetail Podcasts API client for PRX.

This module provides a client for interacting with the PRX Dovetail
Podcasts API to fetch podcast and episode data.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

import requests

from .feed_parser import Episode
from .prx_auth import PRXAuthClient, PRXAuthError

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class DovetailAPIError(Exception):
    """Exception raised for Dovetail API errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code if applicable.
        response_body: Raw response body for debugging.
        endpoint: The API endpoint that was called.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.endpoint = endpoint

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        if self.endpoint:
            parts.append(f"[{self.endpoint}]")
        return " ".join(parts)


class DovetailClient:
    """Client for the PRX Dovetail Podcasts API.

    Provides methods for fetching podcasts and episodes from the
    Dovetail API with automatic authentication handling.

    Example:
        >>> from prx_auth import PRXAuthClient
        >>> auth = PRXAuthClient(client_id, client_secret)
        >>> client = DovetailClient(auth, podcast_id="120")
        >>> episodes = client.get_episodes(since=last_sync_time)

    Attributes:
        PRODUCTION_API_BASE: Production API base URL.
        STAGING_API_BASE: Staging API base URL.
    """

    PRODUCTION_API_BASE = "https://podcasts.dovetail.prx.org/api/v1"
    STAGING_API_BASE = "https://podcasts.dovetail.staging.prx.tech/api/v1"

    def __init__(
        self,
        auth_client: PRXAuthClient,
        podcast_id: str = "",
        api_base_url: Optional[str] = None,
        request_timeout: int = 30,
    ):
        """Initialize the Dovetail API client.

        Args:
            auth_client: PRXAuthClient instance for authentication.
            podcast_id: Default podcast ID for episode operations.
            api_base_url: Custom API base URL. Defaults to production.
            request_timeout: HTTP request timeout in seconds.
        """
        self.auth_client = auth_client
        self.podcast_id = podcast_id
        self.api_base_url = (api_base_url or self.PRODUCTION_API_BASE).rstrip("/")
        self.request_timeout = request_timeout
        self._session = requests.Session()

        logger.debug(f"DovetailClient initialized with base: {self.api_base_url}")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path (e.g., '/authorization/podcasts').
            params: Query parameters.
            json_data: JSON body for POST/PUT requests.
            retry_on_401: If True, retry once with fresh token on 401.

        Returns:
            Parsed JSON response as dict.

        Raises:
            DovetailAPIError: If request fails.
        """
        url = f"{self.api_base_url}{endpoint}"

        try:
            headers = self.auth_client.get_auth_headers()
        except PRXAuthError as e:
            raise DovetailAPIError(
                f"Authentication failed: {e}",
                endpoint=endpoint,
            )

        last_exception: Optional[Exception] = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=self.request_timeout,
                )
            except requests.exceptions.Timeout:
                last_exception = DovetailAPIError(
                    f"Request timed out after {self.request_timeout}s",
                    endpoint=endpoint,
                )
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Timeout on {endpoint}, retrying in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise last_exception
            except requests.exceptions.ConnectionError as e:
                last_exception = DovetailAPIError(
                    f"Connection error: {e}", endpoint=endpoint,
                )
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Connection error on {endpoint}, retrying in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise last_exception
            except requests.exceptions.RequestException as e:
                raise DovetailAPIError(
                    f"Request failed: {e}", endpoint=endpoint,
                )

            # Handle 401 with token refresh retry
            if response.status_code == 401 and retry_on_401:
                logger.warning("Received 401, retrying with fresh token")
                self.auth_client.invalidate_token()
                return self._make_request(
                    method, endpoint, params, json_data, retry_on_401=False
                )

            # Retry on 5xx / 429
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < MAX_RETRIES:
                    if response.status_code == 429:
                        delay = float(response.headers.get("Retry-After", RETRY_BASE_DELAY))
                    else:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"HTTP {response.status_code} from {endpoint}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(delay)
                    continue

            if not response.ok:
                raise DovetailAPIError(
                    f"API request failed",
                    status_code=response.status_code,
                    response_body=response.text,
                    endpoint=endpoint,
                )

            try:
                return response.json()
            except ValueError:
                raise DovetailAPIError(
                    "Invalid JSON response",
                    response_body=response.text,
                    endpoint=endpoint,
                )

        # Exhausted retries
        raise DovetailAPIError(
            f"Request failed after {MAX_RETRIES} retries",
            endpoint=endpoint,
        )

    def get_authorization(self) -> dict[str, Any]:
        """Get authorization root with available operations.

        Returns:
            Dict with available API operations and links.

        Raises:
            DovetailAPIError: If request fails.
        """
        return self._make_request("GET", "/authorization")

    def get_podcasts(
        self,
        page: int = 1,
        per: int = 50,
    ) -> list[dict[str, Any]]:
        """Get paginated list of podcasts.

        Args:
            page: Page number (1-indexed).
            per: Items per page (max 50).

        Returns:
            List of podcast dictionaries.

        Raises:
            DovetailAPIError: If request fails.
        """
        params = {
            "page": page,
            "per": min(per, 50),  # API max is typically 50
        }

        response = self._make_request("GET", "/authorization/podcasts", params=params)

        # Handle HAL+JSON format
        if "_embedded" in response and "prx:items" in response["_embedded"]:
            return response["_embedded"]["prx:items"]

        # Fallback for direct array response
        if isinstance(response, list):
            return response

        # Return items if present
        return response.get("items", [])

    def get_all_podcasts(self) -> list[dict[str, Any]]:
        """Get all podcasts across all pages.

        Returns:
            Complete list of all podcast dictionaries.

        Raises:
            DovetailAPIError: If any request fails.
        """
        all_podcasts = []
        page = 1

        while True:
            podcasts = self.get_podcasts(page=page)
            if not podcasts:
                break
            all_podcasts.extend(podcasts)
            if len(podcasts) < 50:
                break
            page += 1

        return all_podcasts

    @staticmethod
    def _extract_items(response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract item list from a HAL+JSON response.

        Handles the three common response shapes from the Dovetail API:
        1. HAL+JSON with _embedded.prx:items
        2. Direct list
        3. Dict with 'items' key

        Args:
            response: Parsed JSON response from the API.

        Returns:
            List of item dicts.
        """
        if "_embedded" in response and "prx:items" in response["_embedded"]:
            return response["_embedded"]["prx:items"]
        if isinstance(response, list):
            return response
        return response.get("items", [])

    @staticmethod
    def _extract_podcast_id(item: dict[str, Any]) -> str:
        """Extract podcast ID from an episode item.

        Tries multiple fields in order:
        1. _links.prx:podcast.href (e.g., "/api/v1/podcasts/3329")
        2. GUID prefix (e.g., "prx_3329_uuid...")
        3. Direct podcastId / podcast_id field

        Args:
            item: Episode dict from API response.

        Returns:
            Podcast ID string, or empty string if not found.
        """
        # Try _links first
        if "_links" in item and "prx:podcast" in item["_links"]:
            podcast_href = item["_links"]["prx:podcast"].get("href", "")
            if podcast_href:
                return podcast_href.rstrip("/").split("/")[-1]

        # Fall back to GUID prefix
        guid = item.get("guid", "")
        if guid.startswith("prx_"):
            parts = guid.split("_")
            if len(parts) >= 2:
                return parts[1]

        # Fall back to direct field
        return str(item.get("podcastId", item.get("podcast_id", "")))

    def get_episodes(
        self,
        podcast_id: Optional[str] = None,
        since: Optional[datetime] = None,
        page: int = 1,
        per: int = 50,
    ) -> list[Episode]:
        """Get paginated list of episodes.

        Args:
            podcast_id: Podcast ID. Uses default if not provided.
            since: Only return episodes modified since this datetime.
            page: Page number (1-indexed).
            per: Items per page (max 50).

        Returns:
            List of Episode objects.

        Raises:
            DovetailAPIError: If request fails.
            ValueError: If no podcast_id available.
        """
        pid = podcast_id or self.podcast_id
        if not pid:
            raise ValueError("podcast_id is required")

        params: dict[str, Any] = {
            "page": page,
            "per": min(per, 50),
        }

        if since:
            # Format as ISO 8601 for API
            params["since"] = since.isoformat()

        response = self._make_request("GET", "/authorization/episodes", params=params)
        items = self._extract_items(response)

        # Filter by podcast_id and parse into Episode objects
        episodes = []
        for item in items:
            item_podcast_id = self._extract_podcast_id(item)
            if item_podcast_id and item_podcast_id != pid:
                continue

            try:
                episode = self._parse_api_episode(item)
                episodes.append(episode)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse episode: {e}")
                continue

        return episodes

    def get_all_episodes(
        self,
        podcast_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[Episode]:
        """Get all episodes across all pages.

        Args:
            podcast_id: Podcast ID. Uses default if not provided.
            since: Only return episodes modified since this datetime.

        Returns:
            Complete list of all Episode objects.

        Raises:
            DovetailAPIError: If any request fails.
        """
        pid = podcast_id or self.podcast_id
        all_episodes = []
        page = 1
        per_page = 100  # Use max page size for efficiency

        while True:
            # Fetch raw items without filtering to check true page size
            params: dict[str, Any] = {
                "page": page,
                "per": per_page,
            }
            if since:
                params["since"] = since.isoformat()

            response = self._make_request("GET", "/authorization/episodes", params=params)
            items = self._extract_items(response)

            if not items:
                break

            # Filter and parse episodes for our podcast
            for item in items:
                item_podcast_id = self._extract_podcast_id(item)
                if pid and item_podcast_id != pid:
                    continue

                try:
                    episode = self._parse_api_episode(item)
                    all_episodes.append(episode)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse episode: {e}")
                    continue

            # Check if we've reached the last page
            if len(items) < per_page:
                break
            page += 1

        logger.info(f"Fetched {len(all_episodes)} episodes total")
        return all_episodes

    def get_episode_by_guid(
        self,
        guid: str,
        podcast_id: Optional[str] = None,
    ) -> Optional[Episode]:
        """Look up an episode by its GUID.

        Args:
            guid: Episode GUID.
            podcast_id: Podcast ID. Uses default if not provided.

        Returns:
            Episode if found, None otherwise.

        Raises:
            DovetailAPIError: If request fails (except 404).
            ValueError: If no podcast_id available.
        """
        pid = podcast_id or self.podcast_id
        if not pid:
            raise ValueError("podcast_id is required")

        endpoint = f"/podcasts/{pid}/guids/{guid}"

        try:
            response = self._make_request("GET", endpoint)
            return self._parse_api_episode(response)
        except DovetailAPIError as e:
            if e.status_code == 404:
                return None
            raise

    def _parse_api_episode(self, data: dict[str, Any]) -> Episode:
        """Parse API response data into an Episode object.

        Maps Dovetail API fields to the Episode dataclass fields
        used by the rest of the application.

        Args:
            data: Episode data from API response.

        Returns:
            Episode object.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If data cannot be parsed.
        """
        # Extract GUID - try multiple possible field names
        guid = data.get("guid") or data.get("id") or data.get("episodeGuid", "")
        if not guid:
            raise KeyError("Episode missing guid/id")

        # Extract title
        title = data.get("title", "")
        if not title:
            raise KeyError("Episode missing title")

        # Extract description - try multiple fields
        description = (
            data.get("description")
            or data.get("content")
            or data.get("summary")
            or ""
        )

        # Extract subtitle
        subtitle = data.get("subtitle", "")

        # Parse publication date
        pub_date_str = (
            data.get("publishedAt")
            or data.get("published_at")
            or data.get("pubDate")
            or data.get("releasedAt")
            or ""
        )
        if pub_date_str:
            try:
                # Handle ISO 8601 format
                if pub_date_str.endswith("Z"):
                    pub_date_str = pub_date_str[:-1] + "+00:00"
                pub_date = datetime.fromisoformat(pub_date_str)
            except ValueError:
                logger.warning(f"Could not parse date: {pub_date_str}")
                pub_date = datetime.now()
        else:
            pub_date = datetime.now()

        # Extract link/URL
        link = data.get("link") or data.get("url") or data.get("webUrl") or ""

        # Extract enclosure/media info
        # Prefer _links.enclosure — this is the stitched delivery URL that
        # combines all segments and goes through Podtrac/Dovetail tracking.
        # The media[] array contains raw per-segment files on f.prxu.org
        # which are typically just the first segment, not the full episode.
        enclosure_url = ""
        enclosure_type = "audio/mpeg"

        links = data.get("_links", {})
        enclosure_link = links.get("enclosure", {})
        if enclosure_link and enclosure_link.get("href"):
            enclosure_url = enclosure_link["href"]
            enclosure_type = enclosure_link.get("type", "audio/mpeg")
        elif data.get("enclosure"):
            enc = data["enclosure"]
            enclosure_url = enc.get("url", "")
            enclosure_type = enc.get("type", "audio/mpeg")
        else:
            media = data.get("media", [])
            if media and isinstance(media, list) and len(media) > 0:
                first_media = media[0]
                enclosure_url = first_media.get("href") or first_media.get("url", "")
                enclosure_type = first_media.get("type", "audio/mpeg")
            elif data.get("audioUrl"):
                enclosure_url = data["audioUrl"]

        # Extract duration — prefer _links.enclosure.duration (total stitched
        # duration in seconds) over the top-level field
        duration = ""
        if enclosure_link and enclosure_link.get("duration"):
            raw_dur = enclosure_link["duration"]
            if isinstance(raw_dur, (int, float)) and raw_dur > 0:
                minutes, seconds = divmod(int(raw_dur), 60)
                hours, minutes = divmod(minutes, 60)
                if hours:
                    duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    duration = f"{minutes:02d}:{seconds:02d}"
        if not duration:
            duration = data.get("duration") or data.get("itunes:duration") or "00:00"
        if isinstance(duration, (int, float)):
            # Convert seconds to HH:MM:SS
            minutes, seconds = divmod(int(duration), 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration = f"{minutes:02d}:{seconds:02d}"

        # Extract image URL
        # Try episode-level fields first, then fall back to podcastImage
        # (the show-level artwork attached to each episode in the API response)
        image_url = (
            data.get("imageUrl")
            or data.get("image")
            or data.get("itunes:image")
            or ""
        )
        if isinstance(image_url, dict):
            image_url = image_url.get("href", "")
        if not image_url:
            podcast_image = data.get("podcastImage")
            if isinstance(podcast_image, dict):
                image_url = podcast_image.get("href", "")

        # Extract categories
        categories = []
        itunes_categories = data.get("itunesCategories", [])
        for cat in itunes_categories:
            if isinstance(cat, dict):
                cat_name = cat.get("name", "")
                if cat_name:
                    categories.append(cat_name)
            elif isinstance(cat, str):
                categories.append(cat)

        # Also check for tags
        tags = data.get("tags", [])
        if tags:
            categories.extend(tags)

        # Extract episode type
        episode_type = data.get("episodeType") or data.get("itunes:episodeType") or "full"

        # Extract author
        author = (
            data.get("author")
            or data.get("itunes:author")
            or data.get("creator")
            or ""
        )

        # Extract transcript URL if present in API response
        transcript_url = data.get("transcriptUrl", "")
        transcript_type = data.get("transcriptType", "")

        return Episode(
            guid=str(guid),
            title=title,
            description=description,
            subtitle=subtitle,
            pub_date=pub_date,
            link=link,
            enclosure_url=enclosure_url,
            enclosure_type=enclosure_type,
            duration=str(duration),
            image_url=image_url,
            categories=categories,
            episode_type=episode_type,
            author=author,
            transcript_url=transcript_url,
            transcript_type=transcript_type,
        )


if __name__ == "__main__":
    # Simple test/demo
    import os

    logging.basicConfig(level=logging.DEBUG)

    client_id = os.getenv("PRX_CLIENT_ID")
    client_secret = os.getenv("PRX_CLIENT_SECRET")
    podcast_id = os.getenv("PRX_PODCAST_ID", "120")

    if not client_id or not client_secret:
        print("Set PRX_CLIENT_ID and PRX_CLIENT_SECRET environment variables")
        exit(1)

    try:
        from .prx_auth import PRXAuthClient

        auth = PRXAuthClient(client_id, client_secret)
        client = DovetailClient(auth, podcast_id=podcast_id)

        # Test authorization endpoint
        print("Testing authorization endpoint...")
        auth_info = client.get_authorization()
        print(f"Authorization response: {auth_info}")

        # Test podcast listing
        print("\nFetching podcasts...")
        podcasts = client.get_podcasts()
        print(f"Found {len(podcasts)} podcasts")

        # Test episode listing
        print(f"\nFetching episodes for podcast {podcast_id}...")
        episodes = client.get_episodes(podcast_id=podcast_id, per=5)
        print(f"Found {len(episodes)} episodes")
        for ep in episodes[:3]:
            print(f"  - {ep.title} ({ep.guid})")

    except (DovetailAPIError, PRXAuthError) as e:
        print(f"API error: {e}")
        if hasattr(e, "response_body") and e.response_body:
            print(f"Response: {e.response_body}")
        exit(1)
