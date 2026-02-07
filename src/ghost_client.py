"""Ghost Admin API client for publishing posts."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jwt
import requests

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds; exponential: 1, 2, 4
RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class GhostAPIError(Exception):
    """Raised when Ghost API request fails."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


@dataclass
class GhostPost:
    """Data structure for creating a Ghost post."""

    title: str
    html: str
    status: str = "draft"
    published_at: Optional[str] = None
    feature_image: Optional[str] = None
    custom_excerpt: Optional[str] = None
    canonical_url: Optional[str] = None
    tags: list[dict] = field(default_factory=list)
    authors: list[dict] = field(default_factory=list)
    og_image: Optional[str] = None
    twitter_image: Optional[str] = None
    codeinjection_head: Optional[str] = None

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to Ghost API format."""
        data: dict[str, Any] = {
            "title": self.title,
            "html": self.html,
            "status": self.status,
        }

        if self.published_at:
            data["published_at"] = self.published_at
        if self.feature_image:
            data["feature_image"] = self.feature_image
        if self.custom_excerpt:
            data["custom_excerpt"] = self.custom_excerpt
        if self.canonical_url:
            data["canonical_url"] = self.canonical_url
        if self.tags:
            data["tags"] = self.tags
        if self.authors:
            data["authors"] = self.authors
        if self.og_image:
            data["og_image"] = self.og_image
        if self.twitter_image:
            data["twitter_image"] = self.twitter_image
        if self.codeinjection_head:
            data["codeinjection_head"] = self.codeinjection_head

        return data


def generate_jwt_token(api_key: str) -> str:
    """Generate a JWT token for Ghost Admin API authentication.

    Args:
        api_key: Ghost Admin API key in format 'key_id:secret'.

    Returns:
        Signed JWT token string.

    Raises:
        ValueError: If api_key format is invalid.
    """
    if ":" not in api_key:
        raise ValueError("API key must be in format 'key_id:secret'")

    key_id, secret = api_key.split(":", 1)

    # Decode the hex secret
    secret_bytes = bytes.fromhex(secret)

    # Create timestamps
    iat = int(datetime.now(timezone.utc).timestamp())
    exp = iat + 5 * 60  # 5 minutes from now

    # Create header and payload
    header = {
        "alg": "HS256",
        "typ": "JWT",
        "kid": key_id,
    }

    payload = {
        "iat": iat,
        "exp": exp,
        "aud": "/admin/",
    }

    # Sign the token
    token = jwt.encode(
        payload,
        secret_bytes,
        algorithm="HS256",
        headers=header,
    )

    return token


class GhostClient:
    """Client for Ghost Admin API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_version: str = "v5.0",
    ):
        """Initialize Ghost client.

        Args:
            base_url: Ghost site URL (e.g., 'http://localhost:2368').
            api_key: Ghost Admin API key in format 'key_id:secret'.
            api_version: Ghost API version (default 'v5.0').
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_version = api_version
        self._token: Optional[str] = None
        self._token_generated_at: Optional[datetime] = None
        self._session = requests.Session()

    @property
    def api_url(self) -> str:
        """Get the full Admin API base URL."""
        return f"{self.base_url}/ghost/api/admin"

    def _get_token(self) -> str:
        """Get a valid JWT token, regenerating if needed."""
        now = datetime.now(timezone.utc)

        # Regenerate if no token or token is older than 4 minutes
        if (
            self._token is None
            or self._token_generated_at is None
            or (now - self._token_generated_at).total_seconds() > 4 * 60
        ):
            self._token = generate_jwt_token(self.api_key)
            self._token_generated_at = now
            logger.debug("Generated new JWT token")

        return self._token

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Ghost {self._get_token()}",
            "Content-Type": "application/json",
            "Accept-Version": self.api_version,
        }

    def _handle_response(self, response: requests.Response) -> dict:
        """Handle API response, raising errors as needed.

        Args:
            response: Response from requests library.

        Returns:
            Parsed JSON response body.

        Raises:
            GhostAPIError: If response indicates an error.
        """
        try:
            body = response.json()
        except ValueError:
            body = {"error": response.text}

        if response.status_code == 401:
            raise GhostAPIError(
                "Authentication failed. Check your API key.",
                status_code=401,
                response_body=body,
            )

        if response.status_code == 422:
            # Validation error
            errors = body.get("errors", [])
            error_msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise GhostAPIError(
                f"Validation error: {error_msg}",
                status_code=422,
                response_body=body,
            )

        if response.status_code == 429:
            # Rate limited
            retry_after = response.headers.get("Retry-After", "60")
            raise GhostAPIError(
                f"Rate limited. Retry after {retry_after} seconds.",
                status_code=429,
                response_body=body,
            )

        if not response.ok:
            raise GhostAPIError(
                f"API error: {response.status_code}",
                status_code=response.status_code,
                response_body=body,
            )

        return body

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """Make an HTTP request with retry logic for transient failures.

        Retries on 429 (rate limit, respects Retry-After header) and
        500/502/503 (server errors, exponential backoff).

        Args:
            method: HTTP method (GET, POST, PUT).
            url: Full URL.
            **kwargs: Passed through to requests.

        Returns:
            requests.Response object.

        Raises:
            GhostAPIError: After all retries exhausted, or on non-retryable error.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._session.request(method, url, **kwargs)

                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response

                # Retryable status — calculate delay
                if response.status_code == 429:
                    delay = float(response.headers.get("Retry-After", RETRY_BASE_DELAY))
                else:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)

                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"HTTP {response.status_code} from {url}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(delay)
                else:
                    return response  # Final attempt, let _handle_response raise

            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Request error: {e}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(delay)
                else:
                    raise GhostAPIError(f"Request failed after {MAX_RETRIES} retries: {e}")

        # Should not reach here, but just in case
        raise GhostAPIError(f"Request failed after {MAX_RETRIES} retries: {last_exception}")

    def create_post(self, post: GhostPost) -> dict:
        """Create a new post in Ghost.

        Args:
            post: GhostPost object with post data.

        Returns:
            Created post data from API response.

        Raises:
            GhostAPIError: If post creation fails.
        """
        # Use source=html to tell Ghost we're providing HTML content
        url = f"{self.api_url}/posts/?source=html"

        payload = {"posts": [post.to_api_dict()]}

        logger.info(f"Creating post: {post.title}")
        logger.debug(f"POST {url}")

        response = self._request_with_retry(
            "POST", url, json=payload, headers=self._get_headers(), timeout=30,
        )

        result = self._handle_response(response)

        # Return the created post
        posts = result.get("posts", [])
        if not posts:
            raise GhostAPIError("No post returned in response")

        created_post = posts[0]
        logger.info(f"Created post with ID: {created_post.get('id')}")

        return created_post

    def get_post(self, post_id: str) -> dict:
        """Get a post by ID.

        Args:
            post_id: Ghost post ID.

        Returns:
            Post data from API response.

        Raises:
            GhostAPIError: If request fails.
        """
        url = f"{self.api_url}/posts/{post_id}/"

        logger.debug(f"GET {url}")

        response = self._request_with_retry(
            "GET", url, headers=self._get_headers(), timeout=30,
        )

        result = self._handle_response(response)

        posts = result.get("posts", [])
        if not posts:
            raise GhostAPIError(f"Post not found: {post_id}")

        return posts[0]

    def update_post(self, post_id: str, post: GhostPost, updated_at: str) -> dict:
        """Update an existing post.

        Args:
            post_id: Ghost post ID.
            post: GhostPost object with updated data.
            updated_at: Current updated_at timestamp from the post.

        Returns:
            Updated post data from API response.

        Raises:
            GhostAPIError: If update fails.
        """
        # Use source=html to tell Ghost we're providing HTML content
        url = f"{self.api_url}/posts/{post_id}/?source=html"

        post_data = post.to_api_dict()
        post_data["updated_at"] = updated_at

        payload = {"posts": [post_data]}

        logger.info(f"Updating post: {post_id}")
        logger.debug(f"PUT {url}")

        response = self._request_with_retry(
            "PUT", url, json=payload, headers=self._get_headers(), timeout=30,
        )

        result = self._handle_response(response)

        posts = result.get("posts", [])
        if not posts:
            raise GhostAPIError("No post returned in response")

        return posts[0]

    def _upload_to_endpoint(
        self, file_path: Path, endpoint: str, content_type: str, timeout: int = 300
    ) -> str:
        """Upload a file to a Ghost Admin API endpoint.

        Ghost has separate upload endpoints for different file types:
        - /media/upload/ for audio/video
        - /images/upload/ for images
        - /files/upload/ for general files (JSON, PDF, etc.)

        Args:
            file_path: Local path to the file.
            endpoint: API endpoint path (e.g., 'media/upload', 'files/upload').
            content_type: MIME type of the file.
            timeout: Request timeout in seconds.

        Returns:
            URL to the uploaded file on Ghost.

        Raises:
            GhostAPIError: If upload fails.
        """
        url = f"{self.api_url}/{endpoint}/"

        # Build headers without Content-Type — requests sets multipart boundary
        headers = {
            "Authorization": f"Ghost {self._get_token()}",
            "Accept-Version": self.api_version,
        }

        logger.info(f"Uploading {endpoint}: {file_path.name} ({content_type})")
        logger.debug(f"POST {url}")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, content_type)}
                response = self._session.post(
                    url, files=files, headers=headers, timeout=timeout
                )
        except requests.exceptions.RequestException as e:
            raise GhostAPIError(f"Upload request failed: {e}")

        try:
            body = response.json()
        except ValueError:
            body = {"error": response.text}

        if not response.ok:
            error_msg = (
                body.get("errors", [{}])[0].get("message", response.text)
                if isinstance(body.get("errors"), list)
                else response.text
            )
            raise GhostAPIError(
                f"Upload failed ({endpoint}): {error_msg}",
                status_code=response.status_code,
                response_body=body,
            )

        # Ghost returns the uploaded file URL — location varies by endpoint
        uploaded_url = body.get("url", "")
        if not uploaded_url:
            for key in ("files", "media", "images"):
                items = body.get(key, [])
                if items and isinstance(items, list):
                    uploaded_url = items[0].get("url", "")
                    if uploaded_url:
                        break

        if not uploaded_url:
            raise GhostAPIError(
                "No URL returned from upload",
                response_body=body,
            )

        logger.info(f"Uploaded: {uploaded_url}")
        return uploaded_url

    def upload_media(self, file_path: Path) -> str:
        """Upload an audio/video file to Ghost's media library.

        Args:
            file_path: Local path to the media file (mp3, wav, ogg, m4a).

        Returns:
            URL to the uploaded file on Ghost.

        Raises:
            GhostAPIError: If upload fails.
        """
        mime_types = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
        }
        ext = file_path.suffix.lower()
        content_type = mime_types.get(ext, "audio/mpeg")
        return self._upload_to_endpoint(file_path, "media/upload", content_type)

    def upload_image(self, file_path: Path) -> str:
        """Upload an image to Ghost's image library.

        Args:
            file_path: Local path to the image file (jpg, png, gif, webp, svg).

        Returns:
            URL to the uploaded image on Ghost.

        Raises:
            GhostAPIError: If upload fails.
        """
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }
        ext = file_path.suffix.lower()
        content_type = mime_types.get(ext, "image/jpeg")
        return self._upload_to_endpoint(file_path, "images/upload", content_type)

    def upload_file(self, file_path: Path) -> str:
        """Upload a general file to Ghost's file library.

        Use this for non-media files like JSON, PDF, etc.
        Ghost stores these at /content/files/.

        Args:
            file_path: Local path to the file.

        Returns:
            URL to the uploaded file on Ghost.

        Raises:
            GhostAPIError: If upload fails.
        """
        mime_types = {
            ".json": "application/json",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".csv": "text/csv",
        }
        ext = file_path.suffix.lower()
        content_type = mime_types.get(ext, "application/octet-stream")
        return self._upload_to_endpoint(file_path, "files/upload", content_type)

    def test_connection(self) -> bool:
        """Test the API connection and authentication.

        Returns:
            True if connection is successful.

        Raises:
            GhostAPIError: If connection fails.
        """
        url = f"{self.api_url}/site/"

        logger.debug(f"Testing connection: GET {url}")

        response = self._request_with_retry(
            "GET", url, headers=self._get_headers(), timeout=10,
        )

        self._handle_response(response)
        logger.info("Ghost API connection successful")
        return True


if __name__ == "__main__":
    # Test the client
    import os
    from pathlib import Path

    from dotenv import load_dotenv

    logging.basicConfig(level=logging.DEBUG)

    # Load environment
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    ghost_url = os.getenv("GHOST_URL")
    api_key = os.getenv("GHOST_ADMIN_API_KEY")

    if not ghost_url or not api_key:
        print("GHOST_URL and GHOST_ADMIN_API_KEY required in .env")
        exit(1)

    client = GhostClient(ghost_url, api_key)

    try:
        client.test_connection()
        print("Connection successful!")
    except GhostAPIError as e:
        print(f"Connection failed: {e}")
        exit(1)
