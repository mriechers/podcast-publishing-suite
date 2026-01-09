"""Configuration management for PRX-to-Ghost Publisher."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid or missing required values."""
    pass


@dataclass
class Config:
    """Application configuration with typed properties.

    Loads settings from environment variables (which can come from .env file)
    and falls back to config.json for defaults.
    """
    ghost_url: str
    ghost_admin_api_key: str
    prx_feed_url: str
    ghost_api_version: str = "v5.0"
    publish_status: str = "draft"
    dry_run: bool = False
    state_file: Path = Path("data/published_episodes.json")
    default_author: str = "Wisconsin Public Radio"
    primary_tag: str = "TTBOOK"

    # PRX Dovetail API settings
    prx_client_id: str = ""
    prx_client_secret: str = ""
    prx_podcast_id: str = ""  # Primary podcast ID (e.g., "120" for TTBOOK)
    prx_podcast_ids: list[str] = None  # Multiple podcast IDs (e.g., ["120", "3329"])
    prx_api_base_url: str = "https://podcasts.dovetail.prx.org/api/v1"
    prx_id_base_url: str = "https://id.prx.org"
    use_dovetail_api: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Initialize prx_podcast_ids if None
        if self.prx_podcast_ids is None:
            self.prx_podcast_ids = []

        # If prx_podcast_id is set but not in prx_podcast_ids, add it
        if self.prx_podcast_id and self.prx_podcast_id not in self.prx_podcast_ids:
            self.prx_podcast_ids.insert(0, self.prx_podcast_id)

        # If prx_podcast_ids has values but prx_podcast_id is empty, use first
        if self.prx_podcast_ids and not self.prx_podcast_id:
            self.prx_podcast_id = self.prx_podcast_ids[0]

        # Validate required fields
        if not self.ghost_url:
            raise ConfigError("GHOST_URL is required")
        if not self.ghost_admin_api_key:
            raise ConfigError("GHOST_ADMIN_API_KEY is required")
        if not self.prx_feed_url:
            raise ConfigError("PRX_FEED_URL is required")

        # Validate API key format (should be id:secret)
        if ":" not in self.ghost_admin_api_key:
            raise ConfigError(
                "GHOST_ADMIN_API_KEY must be in format 'key_id:secret'"
            )

        # Validate publish_status
        if self.publish_status not in ("draft", "published"):
            raise ConfigError(
                f"PUBLISH_STATUS must be 'draft' or 'published', got '{self.publish_status}'"
            )

        # Ensure state_file is a Path
        if isinstance(self.state_file, str):
            self.state_file = Path(self.state_file)

    @property
    def ghost_api_base_url(self) -> str:
        """Get the full Ghost Admin API base URL."""
        base = self.ghost_url.rstrip("/")
        return f"{base}/ghost/api/admin"


# Module-level singleton
_config: Optional[Config] = None


def _parse_podcast_ids(env_value: str, json_value: list[str]) -> list[str]:
    """Parse podcast IDs from environment variable or JSON config.

    Args:
        env_value: Comma-separated string from PRX_PODCAST_IDS env var.
        json_value: List from config.json prx.podcast_ids.

    Returns:
        List of podcast ID strings.
    """
    if env_value:
        # Parse comma-separated env var (e.g., "120,3329")
        return [pid.strip() for pid in env_value.split(",") if pid.strip()]
    return json_value or []


def get_config(reload: bool = False) -> Config:
    """Get the application configuration singleton.

    Args:
        reload: If True, reload configuration from disk even if already loaded.

    Returns:
        Config instance with validated settings.

    Raises:
        ConfigError: If required configuration is missing or invalid.
    """
    global _config

    if _config is not None and not reload:
        return _config

    # Determine project root (where .env and config.json live)
    project_root = Path(__file__).parent.parent

    # Load .env file
    env_path = project_root / ".env"
    load_dotenv(env_path)

    # Load config.json for defaults
    config_json_path = project_root / "config.json"
    json_config: dict = {}
    if config_json_path.exists():
        with open(config_json_path, "r") as f:
            json_config = json.load(f)

    # Get nested ghost config
    ghost_config = json_config.get("ghost", {})
    defaults = json_config.get("defaults", {})

    # Build configuration, environment variables take precedence
    state_file_str = json_config.get("state_file", "data/published_episodes.json")
    state_file = Path(state_file_str)

    # Make state_file path absolute relative to project root
    if not state_file.is_absolute():
        state_file = project_root / state_file

    # Get PRX API config from json
    prx_config = json_config.get("prx", {})

    _config = Config(
        ghost_url=os.getenv("GHOST_URL", ghost_config.get("url", "")),
        ghost_admin_api_key=os.getenv("GHOST_ADMIN_API_KEY", ""),
        prx_feed_url=os.getenv("PRX_FEED_URL", json_config.get("feed_url", "")),
        ghost_api_version=ghost_config.get("api_version", "v5.0"),
        publish_status=os.getenv("PUBLISH_STATUS", defaults.get("status", "draft")),
        dry_run=os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes"),
        state_file=state_file,
        default_author=defaults.get("author", "Wisconsin Public Radio"),
        primary_tag=defaults.get("primary_tag", "TTBOOK"),
        # PRX Dovetail API settings
        prx_client_id=os.getenv("PRX_CLIENT_ID", prx_config.get("client_id", "")),
        prx_client_secret=os.getenv("PRX_CLIENT_SECRET", prx_config.get("client_secret", "")),
        prx_podcast_id=os.getenv("PRX_PODCAST_ID", prx_config.get("podcast_id", "")),
        prx_podcast_ids=_parse_podcast_ids(
            os.getenv("PRX_PODCAST_IDS", ""),
            prx_config.get("podcast_ids", [])
        ),
        prx_api_base_url=os.getenv(
            "PRX_API_BASE_URL",
            prx_config.get("api_base_url", "https://podcasts.dovetail.prx.org/api/v1")
        ),
        prx_id_base_url=os.getenv(
            "PRX_ID_BASE_URL",
            prx_config.get("id_base_url", "https://id.prx.org")
        ),
        use_dovetail_api=os.getenv("PRX_USE_API", "false").lower() in ("true", "1", "yes"),
    )

    return _config


def reset_config() -> None:
    """Reset the configuration singleton (useful for testing)."""
    global _config
    _config = None
