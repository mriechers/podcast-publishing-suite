"""Ghost Admin API client for publishing posts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import jwt
import requests

logger = logging.getLogger(__name__)


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

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            raise GhostAPIError(f"Request failed: {e}")

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

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            raise GhostAPIError(f"Request failed: {e}")

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

        try:
            response = requests.put(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            raise GhostAPIError(f"Request failed: {e}")

        result = self._handle_response(response)

        posts = result.get("posts", [])
        if not posts:
            raise GhostAPIError("No post returned in response")

        return posts[0]

    def test_connection(self) -> bool:
        """Test the API connection and authentication.

        Returns:
            True if connection is successful.

        Raises:
            GhostAPIError: If connection fails.
        """
        url = f"{self.api_url}/site/"

        logger.debug(f"Testing connection: GET {url}")

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10,
            )
        except requests.exceptions.RequestException as e:
            raise GhostAPIError(f"Connection failed: {e}")

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
