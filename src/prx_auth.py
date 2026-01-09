"""OAuth2 authentication client for PRX Dovetail API.

This module provides OAuth2 client credentials flow authentication
for accessing the PRX Dovetail Podcasts API.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class PRXAuthError(Exception):
    """Exception raised for PRX authentication errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code if applicable.
        response_body: Raw response body for debugging.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)


@dataclass
class TokenInfo:
    """Cached OAuth2 token information.

    Attributes:
        access_token: The bearer token for API requests.
        token_type: Token type (typically 'bearer').
        expires_at: Unix timestamp when token expires.
    """

    access_token: str
    token_type: str
    expires_at: float

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if token is expired or will expire soon.

        Args:
            buffer_seconds: Seconds before expiration to consider expired.
                Defaults to 60 seconds for proactive refresh.

        Returns:
            True if token is expired or will expire within buffer period.
        """
        return time.time() >= (self.expires_at - buffer_seconds)


class PRXAuthClient:
    """OAuth2 client for PRX Dovetail API authentication.

    Uses OAuth2 client credentials flow to obtain and manage access tokens.
    Tokens are cached and automatically refreshed before expiration.

    Example:
        >>> auth = PRXAuthClient(
        ...     client_id="your_client_id",
        ...     client_secret="your_client_secret"
        ... )
        >>> headers = auth.get_auth_headers()
        >>> response = requests.get(api_url, headers=headers)

    Attributes:
        PRODUCTION_TOKEN_ENDPOINT: Production OAuth2 token endpoint.
        STAGING_TOKEN_ENDPOINT: Staging OAuth2 token endpoint.
    """

    PRODUCTION_TOKEN_ENDPOINT = "https://id.prx.org/token"
    STAGING_TOKEN_ENDPOINT = "https://id.staging.prx.tech/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_endpoint: Optional[str] = None,
        use_staging: bool = False,
        request_timeout: int = 30,
    ):
        """Initialize the PRX authentication client.

        Args:
            client_id: OAuth2 client ID from PRX.
            client_secret: OAuth2 client secret from PRX.
            token_endpoint: Custom token endpoint URL. If not provided,
                uses production or staging based on use_staging flag.
            use_staging: If True, use staging endpoint. Ignored if
                token_endpoint is provided.
            request_timeout: HTTP request timeout in seconds.

        Raises:
            ValueError: If client_id or client_secret is empty.
        """
        if not client_id:
            raise ValueError("client_id is required")
        if not client_secret:
            raise ValueError("client_secret is required")

        self.client_id = client_id
        self.client_secret = client_secret
        self.request_timeout = request_timeout

        if token_endpoint:
            self.token_endpoint = token_endpoint
        elif use_staging:
            self.token_endpoint = self.STAGING_TOKEN_ENDPOINT
        else:
            self.token_endpoint = self.PRODUCTION_TOKEN_ENDPOINT

        self._token: Optional[TokenInfo] = None

        logger.debug(f"PRXAuthClient initialized with endpoint: {self.token_endpoint}")

    def _request_token(self) -> TokenInfo:
        """Request a new access token from the OAuth2 server.

        Returns:
            TokenInfo with the new access token.

        Raises:
            PRXAuthError: If token request fails.
        """
        logger.debug("Requesting new access token")

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            response = requests.post(
                self.token_endpoint,
                data=data,
                headers=headers,
                timeout=self.request_timeout,
            )
        except requests.exceptions.Timeout:
            raise PRXAuthError(
                f"Token request timed out after {self.request_timeout}s"
            )
        except requests.exceptions.ConnectionError as e:
            raise PRXAuthError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise PRXAuthError(f"Request failed: {e}")

        if not response.ok:
            raise PRXAuthError(
                f"Token request failed",
                status_code=response.status_code,
                response_body=response.text,
            )

        try:
            token_data = response.json()
        except ValueError:
            raise PRXAuthError(
                "Invalid JSON response from token endpoint",
                response_body=response.text,
            )

        access_token = token_data.get("access_token")
        if not access_token:
            raise PRXAuthError(
                "No access_token in response",
                response_body=response.text,
            )

        token_type = token_data.get("token_type", "bearer")

        # Calculate expiration time
        # Default to 1 hour if expires_in not provided
        expires_in = token_data.get("expires_in", 3600)
        expires_at = time.time() + expires_in

        logger.info(f"Obtained access token, expires in {expires_in}s")

        return TokenInfo(
            access_token=access_token,
            token_type=token_type,
            expires_at=expires_at,
        )

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Get a valid access token, refreshing if necessary.

        Returns a cached token if still valid, otherwise requests a new one.
        Tokens are proactively refreshed 60 seconds before expiration.

        Args:
            force_refresh: If True, always request a new token.

        Returns:
            Valid access token string.

        Raises:
            PRXAuthError: If token cannot be obtained.
        """
        if force_refresh or self._token is None or self._token.is_expired():
            self._token = self._request_token()

        return self._token.access_token

    def get_auth_headers(self, force_refresh: bool = False) -> dict[str, str]:
        """Get headers dict with Authorization header for API requests.

        Convenience method that returns a complete headers dict ready
        for use with requests library.

        Args:
            force_refresh: If True, force token refresh.

        Returns:
            Dict with Authorization and content type headers.

        Raises:
            PRXAuthError: If token cannot be obtained.
        """
        token = self.get_access_token(force_refresh=force_refresh)

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def invalidate_token(self) -> None:
        """Invalidate the cached token.

        Call this method if you receive a 401 Unauthorized response
        to force a token refresh on the next request.
        """
        logger.debug("Invalidating cached token")
        self._token = None

    @property
    def is_authenticated(self) -> bool:
        """Check if a valid (non-expired) token is cached.

        Returns:
            True if a valid token is available without making a request.
        """
        return self._token is not None and not self._token.is_expired()


if __name__ == "__main__":
    # Simple test/demo
    import os

    logging.basicConfig(level=logging.DEBUG)

    client_id = os.getenv("PRX_CLIENT_ID")
    client_secret = os.getenv("PRX_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Set PRX_CLIENT_ID and PRX_CLIENT_SECRET environment variables")
        exit(1)

    try:
        auth = PRXAuthClient(client_id, client_secret)
        token = auth.get_access_token()
        print(f"Successfully obtained token: {token[:20]}...")
        print(f"Is authenticated: {auth.is_authenticated}")
    except PRXAuthError as e:
        print(f"Authentication failed: {e}")
        if e.response_body:
            print(f"Response: {e.response_body}")
        exit(1)
