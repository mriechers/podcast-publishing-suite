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
    primary_tag: str = "Wonder Cabinet"

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

# Valid environment names
VALID_ENVIRONMENTS = ("dev", "prod")


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


def get_config(reload: bool = False, env_name: str = "dev") -> Config:
    """Get the application configuration singleton.

    Args:
        reload: If True, reload configuration from disk even if already loaded.
        env_name: Environment name ('dev' or 'prod'). Determines which .env
                  file and state file to use.

    Returns:
        Config instance with validated settings.

    Raises:
        ConfigError: If required configuration is missing or invalid.
    """
    global _config

    if _config is not None and not reload:
        return _config

    # Validate environment name
    if env_name not in VALID_ENVIRONMENTS:
        raise ConfigError(
            f"Invalid environment '{env_name}'. Must be one of: {', '.join(VALID_ENVIRONMENTS)}"
        )

    # Determine project root (where .env and config.json live)
    project_root = Path(__file__).parent.parent

    # Load environment-specific .env file (no fallback to .env)
    env_path = project_root / f".env.{env_name}"
    if not env_path.exists():
        raise ConfigError(
            f"Environment file not found: .env.{env_name}\n"
            f"Copy .env.example to .env.{env_name} and fill in credentials."
        )
    load_dotenv(env_path, override=True)

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
    # Use environment-specific state file: published_episodes.{env}.json
    state_file = Path(f"data/published_episodes.{env_name}.json")

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
        primary_tag=defaults.get("primary_tag", "Wonder Cabinet"),
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

    # Enforce HTTPS in production (JWT tokens sent in cleartext over HTTP)
    if env_name == "prod" and _config.ghost_url.startswith("http://"):
        raise ConfigError(
            "GHOST_URL must use HTTPS in production. "
            f"Got: {_config.ghost_url}"
        )

    return _config


def reset_config() -> None:
    """Reset the configuration singleton (useful for testing)."""
    global _config
    _config = None
