#!/usr/bin/env python3.11
"""
Scrape Ghost documentation for the PRX to Ghost Publisher project.

This script crawls key Ghost documentation pages and saves them to the knowledge/ directory.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler


# Key Ghost documentation pages to scrape
GHOST_DOCS_URLS = [
    {
        "slug": "introduction",
        "url": "https://docs.ghost.org/introduction",
        "notes": "Main introduction to Ghost platform"
    },
    {
        "slug": "content-api-overview",
        "url": "https://docs.ghost.org/content-api",
        "notes": "Content API overview for reading posts, tags, etc."
    },
    {
        "slug": "content-api-reference",
        "url": "https://docs.ghost.org/content-api/reference",
        "notes": "Detailed Content API reference"
    },
    {
        "slug": "admin-api-overview",
        "url": "https://docs.ghost.org/admin-api",
        "notes": "Admin API overview for creating/updating content"
    },
    {
        "slug": "admin-api-reference",
        "url": "https://docs.ghost.org/admin-api/reference",
        "notes": "Detailed Admin API reference"
    },
    {
        "slug": "posts-api",
        "url": "https://docs.ghost.org/admin-api/reference/posts",
        "notes": "Posts API endpoint documentation"
    },
    {
        "slug": "tags-api",
        "url": "https://docs.ghost.org/admin-api/reference/tags",
        "notes": "Tags API endpoint documentation"
    },
    {
        "slug": "webhooks",
        "url": "https://docs.ghost.org/webhooks",
        "notes": "Webhooks for event-driven automation"
    },
    {
        "slug": "authentication",
        "url": "https://docs.ghost.org/admin-api/authentication",
        "notes": "Authentication methods for Admin API"
    },
    {
        "slug": "custom-integrations",
        "url": "https://docs.ghost.org/integrations/custom-integrations",
        "notes": "Building custom integrations with Ghost"
    },
]


async def scrape_ghost_docs():
    """Scrape Ghost documentation pages and save to knowledge/ghost/"""

    output_dir = Path("knowledge/ghost")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    crawler = AsyncWebCrawler()

    succeeded = []
    failed = []

    try:
        for doc in GHOST_DOCS_URLS:
            url = doc["url"]
            slug = doc["slug"]

            print(f"Crawling: {slug} ({url})")

            try:
                result_container = await crawler.arun(url=url)

                if not result_container or not result_container[0].success:
                    raise RuntimeError(f"Crawl failed for {url}")

                result = result_container[0]

                # Save HTML
                html_path = output_dir / f"{slug}.html"
                html_path.write_text(result.html or "", encoding="utf-8")

                # Save Markdown
                md_path = output_dir / f"{slug}.md"
                md_path.write_text(result.markdown.raw_markdown or "", encoding="utf-8")

                # Save metadata
                metadata = {
                    "url": url,
                    "slug": slug,
                    "category": "ghost",
                    "retrieved_at": timestamp,
                    "notes": doc.get("notes", ""),
                    "status_code": result.status_code,
                    "success": result.success,
                    "content_length": len(result.html or ""),
                }

                json_path = output_dir / f"{slug}.json"
                json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

                print(f"  ✓ Saved {slug}")
                succeeded.append(slug)

                # Be nice to the server
                await asyncio.sleep(1)

            except Exception as exc:
                print(f"  ✗ Failed {slug}: {exc}")
                failed.append((slug, str(exc)))

    finally:
        await crawler.close()

    # Save sources.json
    sources_file = Path("knowledge/sources.json")
    sources = {
        "sources": [
            {
                "category": "ghost",
                "slug": doc["slug"],
                "url": doc["url"],
                "notes": doc["notes"]
            }
            for doc in GHOST_DOCS_URLS
        ]
    }
    sources_file.write_text(json.dumps(sources, indent=2), encoding="utf-8")

    print("\n" + "="*60)
    print(f"Succeeded: {len(succeeded)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed pages:")
        for slug, error in failed:
            print(f"  - {slug}: {error}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(scrape_ghost_docs())
    raise SystemExit(exit_code)
