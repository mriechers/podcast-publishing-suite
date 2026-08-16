"""Configuration for analytics dashboard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid."""


@dataclass
class Config:
    """Analytics dashboard configuration."""

    ghost_url: str
    ghost_admin_api_key: str
    prx_client_id: str
    prx_client_secret: str
    prx_podcast_ids: list[str]
    data_dir: Path

    prx_api_base_url: str = "https://podcasts.dovetail.prx.org/api/v1"
    prx_token_endpoint: str = "https://id.prx.org/token"

    @property
    def ghost_api_base_url(self) -> str:
        return f"{self.ghost_url.rstrip('/')}/ghost/api/admin"

    ghost_key_id: str = ""
    ghost_key_secret: bytes = b""


def load_config(env_name: str = "prod") -> Config:
    """Load configuration from .env file."""
    project_root = Path(__file__).parent.parent
    env_path = project_root / f".env.{env_name}"

    if not env_path.exists():
        raise ConfigError(f"Environment file not found: {env_path}")

    load_dotenv(env_path, override=True)

    # Validate required fields
    ghost_url = os.getenv("GHOST_URL", "")
    ghost_key = os.getenv("GHOST_ADMIN_API_KEY", "")
    prx_client_id = os.getenv("PRX_CLIENT_ID", "")
    prx_client_secret = os.getenv("PRX_CLIENT_SECRET", "")

    required = {
        "GHOST_URL": ghost_url,
        "GHOST_ADMIN_API_KEY": ghost_key,
        "PRX_CLIENT_ID": prx_client_id,
        "PRX_CLIENT_SECRET": prx_client_secret,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

    # Parse and validate Ghost Admin API key
    parts = ghost_key.split(":")
    if len(parts) != 2:
        raise ConfigError(
            "GHOST_ADMIN_API_KEY must be exactly 'key_id:hex_secret' "
            f"(got {len(parts)} colon-separated parts)"
        )
    ghost_key_id = parts[0]
    try:
        ghost_key_secret = bytes.fromhex(parts[1])
    except ValueError as e:
        raise ConfigError(f"GHOST_ADMIN_API_KEY secret is not valid hex: {e}") from e

    podcast_ids_raw = os.getenv("PRX_PODCAST_IDS", "")
    podcast_ids = [pid.strip() for pid in podcast_ids_raw.split(",") if pid.strip()]
    if not podcast_ids:
        raise ConfigError("PRX_PODCAST_IDS is empty or not set — no podcasts configured")

    data_dir = project_root / os.getenv("DATA_DIR", "data")
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        ghost_url=ghost_url,
        ghost_admin_api_key=ghost_key,
        ghost_key_id=ghost_key_id,
        ghost_key_secret=ghost_key_secret,
        prx_client_id=prx_client_id,
        prx_client_secret=prx_client_secret,
        prx_podcast_ids=podcast_ids,
        data_dir=data_dir,
    )
