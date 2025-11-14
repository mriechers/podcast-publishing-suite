#!/usr/bin/env python3.11
"""
Interactive documentation harvester powered by Crawl4AI.

Usage examples:
    python3.11 scripts/crawl_docs.py
    python3.11 scripts/crawl_docs.py --init
    python3.11 scripts/crawl_docs.py --slug help
    python3.11 scripts/crawl_docs.py --category toggl --append
    python3.11 scripts/crawl_docs.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

from crawl4ai import AsyncWebCrawler


def load_sources(path: Path) -> List[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError(f"Expected 'sources' to be a list in {path}")
    return sources


def save_sources(path: Path, sources: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sources": sources}, indent=2), encoding="utf-8")


def slugify(value: str) -> str:
    candidate = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return candidate or "source"


def prompt_for_sources(existing: List[dict]) -> List[dict]:
    print("Enter documentation sources (leave category blank to finish):")
    captured: List[dict] = []
    while True:
        category = input("  Category (e.g., alfredapp): ").strip()
        if not category:
            break
        url = input("  URL: ").strip()
        if not url:
            print("    URL required; skipping entry.")
            continue
        default_slug = slugify(url.split("/")[-1] or category)
        slug = input(f"  Slug [{default_slug}]: ").strip() or default_slug
        notes = input("  Notes (optional): ").strip()
        captured.append({"category": category, "slug": slug, "url": url, "notes": notes})
        print(f"    Added {category}/{slug}")

    if not captured:
        print("No new sources captured.")
        return existing

    return existing + captured


def filter_sources(
    sources: Iterable[dict], categories: set[str] | None, slugs: set[str] | None
) -> List[dict]:
    filtered = []
    for entry in sources:
        if categories and entry.get("category") not in categories:
            continue
        if slugs and entry.get("slug") not in slugs:
            continue
        filtered.append(entry)

    if not filtered:
        raise ValueError("No sources matched the requested filters.")
    return filtered


def write_outputs(
    base_path: Path, entry: dict, html: str, markdown: str, metadata: dict, dry_run: bool
) -> None:
    category_path = base_path / entry["category"]
    stem = entry["slug"]
    print(f"  -> {entry['category']}/{stem} (dry-run={dry_run})")
    if dry_run:
        return

    category_path.mkdir(parents=True, exist_ok=True)
    (category_path / f"{stem}.html").write_text(html, encoding="utf-8")
    (category_path / f"{stem}.md").write_text(markdown, encoding="utf-8")
    (category_path / f"{stem}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


async def crawl_sources(
    sources: Iterable[dict], base_path: Path, dry_run: bool
) -> Tuple[list, list]:
    timestamp = datetime.now(timezone.utc).isoformat()
    succeeded, failed = [], []
    crawler = AsyncWebCrawler()

    try:
        for entry in sources:
            url = entry["url"]
            try:
                container = await crawler.arun(url=url)
                if not container or not container[0].success:
                    raise RuntimeError("crawl failed or returned empty result")
                result = container[0]
                metadata = {
                    "url": url,
                    "category": entry["category"],
                    "slug": entry["slug"],
                    "retrieved_at": timestamp,
                    "notes": entry.get("notes", ""),
                    "status_code": result.status_code,
                    "success": result.success,
                    "content_length": len(result.html or ""),
                }
                write_outputs(
                    base_path,
                    entry,
                    result.html or "",
                    result.markdown.raw_markdown or "",
                    metadata,
                    dry_run,
                )
                succeeded.append((entry["category"], entry["slug"]))
            except Exception as exc:  # noqa: BLE001
                failed.append((entry, exc))
    finally:
        await crawler.close()

    return succeeded, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Snapshot documentation sources with Crawl4AI.")
    parser.add_argument("--sources", default="knowledge/sources.json", type=Path, help="JSON file describing documentation sources.")
    parser.add_argument("--output", default="knowledge", type=Path, help="Base directory for scraped outputs.")
    parser.add_argument("--category", action="append", dest="categories", help="Limit crawl to specific categories.")
    parser.add_argument("--slug", action="append", dest="slugs", help="Limit crawl to specific slugs.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch pages but skip writing artifacts.")
    parser.add_argument("--init", action="store_true", help="Interactively define the sources list (replaces existing entries unless --append is set).")
    parser.add_argument("--append", action="store_true", help="Interactively append sources to the existing list.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = load_sources(args.sources)

    if args.init and not args.append:
        sources = prompt_for_sources(existing=[])
    elif args.append or (args.init and sources):
        sources = prompt_for_sources(existing=sources)
    elif not sources:
        print(f"No sources defined. Launching interactive setup for {args.sources}.")
        sources = prompt_for_sources(existing=[])

    if not sources:
        print("Nothing to crawl.")
        return 0

    save_sources(args.sources, sources)

    categories = set(args.categories) if args.categories else None
    slugs = set(args.slugs) if args.slugs else None
    if categories or slugs:
        sources = filter_sources(sources, categories, slugs)

    succeeded, failed = asyncio.run(crawl_sources(sources, args.output, args.dry_run))

    for category, slug in succeeded:
        print(f"[OK] {category}/{slug}")
    for entry, exc in failed:
        print(f"[FAIL] {entry.get('category')}/{entry.get('slug')}: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
