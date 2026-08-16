"""CLI entry point for analytics dashboard."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .collectors.ghost import GhostCollector, GhostCollectorError
from .collectors.prx import PRXCollector, PRXCollectorError
from .dashboard.publication_filter import build_dashboard_bundle
from .importers.prx_csv import (
    PRXCSVImporterError,
    import_prx_csv_directory,
    save_snapshot as save_prx_csv_snapshot,
)

logger = logging.getLogger(__name__)

VALID_SOURCES = ("ghost", "prx")


def refresh(source: str | None = None, env: str = "prod") -> dict[str, Path]:
    """Refresh analytics data from one or all sources."""
    config = load_config(env)
    results: dict[str, Path] = {}

    if source is None or source == "ghost":
        ghost = GhostCollector(
            api_base_url=config.ghost_api_base_url,
            key_id=config.ghost_key_id,
            key_secret=config.ghost_key_secret,
        )
        results["ghost"] = ghost.save_snapshot(config.data_dir)

    if source is None or source == "prx":
        prx = PRXCollector(
            client_id=config.prx_client_id,
            client_secret=config.prx_client_secret,
            podcast_ids=config.prx_podcast_ids,
            api_base_url=config.prx_api_base_url,
            token_endpoint=config.prx_token_endpoint,
        )
        results["prx"] = prx.save_snapshot(config.data_dir)

    return results


def main():
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Wonder Cabinet Analytics Dashboard")
    sub = parser.add_subparsers(dest="command")

    refresh_cmd = sub.add_parser("refresh", help="Refresh analytics data")
    refresh_cmd.add_argument("--source", choices=VALID_SOURCES, help="Specific source to refresh")
    refresh_cmd.add_argument("--env", default="prod", choices=("dev", "prod"), help="Environment")

    import_cmd = sub.add_parser(
        "import-csv",
        help="Import PRX Dovetail download CSVs into a downloads snapshot",
    )
    import_cmd.add_argument("--dir", required=True, help="Directory containing PRX CSV exports")
    import_cmd.add_argument("--show", default="wonder-cabinet", help="Show slug")
    import_cmd.add_argument("--env", default="prod", choices=("dev", "prod"), help="Environment")

    build_cmd = sub.add_parser(
        "build-dashboard",
        help="Filter snapshots for publication and assemble a deployable bundle",
    )
    build_cmd.add_argument(
        "--out", default="dist", help="Output directory for the bundle (default: dist/)",
    )
    build_cmd.add_argument(
        "--html",
        default=None,
        help="Path to dashboard index.html to include in the bundle (optional)",
    )
    build_cmd.add_argument(
        "--assets",
        default=None,
        help="Path to a folder of static assets (logo, etc.) — copied into dist/assets/",
    )
    build_cmd.add_argument(
        "--show",
        default="wonder-cabinet",
        help="Show slug — reads shows/<slug>/config.json for the Ghost site URL",
    )
    build_cmd.add_argument("--env", default="prod", choices=("dev", "prod"), help="Environment")

    args = parser.parse_args()

    if args.command == "refresh":
        try:
            results = refresh(source=args.source, env=args.env)
        except ConfigError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)
        except (GhostCollectorError, PRXCollectorError) as e:
            print(f"Collection failed: {e}", file=sys.stderr)
            sys.exit(1)
        for source_name, path in results.items():
            print(f"  {source_name}: {path}")
    elif args.command == "import-csv":
        try:
            config = load_config(args.env)
            snapshot = import_prx_csv_directory(Path(args.dir), show_slug=args.show)
            path = save_prx_csv_snapshot(snapshot, config.data_dir)
        except ConfigError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)
        except PRXCSVImporterError as e:
            print(f"Import failed: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"  prx_downloads: {path}")
        print(f"    episodes: {len(snapshot['episodes'])}")
        print(f"    rolling_30d: {snapshot['show_totals']['rolling_30d']:,}")
        print(f"    rolling_90d: {snapshot['show_totals']['rolling_90d']:,}")
    elif args.command == "build-dashboard":
        try:
            config = load_config(args.env)
        except ConfigError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)

        # Pull Ghost site URL from the show config so episode rows can
        # link to the public-facing Ghost permalinks.
        ghost_site_url: str | None = None
        repo_root = Path(__file__).resolve().parents[3]
        show_config_path = repo_root / "shows" / args.show / "config.json"
        if show_config_path.exists():
            try:
                show_config = json.loads(show_config_path.read_text())
                ghost_site_url = (show_config.get("ghost") or {}).get("siteUrl")
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: could not read {show_config_path}: {e}", file=sys.stderr)

        out_dir = Path(args.out)
        html = Path(args.html) if args.html else None
        assets = Path(args.assets) if args.assets else None
        written = build_dashboard_bundle(
            data_dir=config.data_dir,
            out_dir=out_dir,
            dashboard_html=html,
            assets_dir=assets,
            ghost_site_url=ghost_site_url,
        )
        if not written:
            print("No snapshots found — nothing to publish.", file=sys.stderr)
            sys.exit(1)
        print(f"  bundle: {out_dir.resolve()}")
        for name, path in written.items():
            print(f"    {name}: {path}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
