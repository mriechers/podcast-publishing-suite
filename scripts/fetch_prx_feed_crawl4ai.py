#!/usr/bin/env python3.11
"""
Fetch PRX RSS feed using Crawl4AI (browser-based).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from crawl4ai import AsyncWebCrawler


async def fetch_prx_feed():
    """Fetch the PRX RSS feed using a real browser."""

    feed_url = "https://f.prxu.org/3329/feed-rss.xml"

    print(f"Fetching: {feed_url}")

    output_dir = Path("knowledge/prx")
    output_dir.mkdir(parents=True, exist_ok=True)

    crawler = AsyncWebCrawler()

    try:
        result_container = await crawler.arun(url=feed_url)

        if not result_container or not result_container[0].success:
            raise RuntimeError(f"Crawl failed for {feed_url}")

        result = result_container[0]

        # Save the HTML/XML content
        xml_path = output_dir / "feed-rss.xml"
        xml_path.write_text(result.html or "", encoding='utf-8')

        print(f"✓ Saved feed ({len(result.html or '')} bytes)")
        print(f"Status code: {result.status_code}")

        return 0

    except Exception as exc:
        print(f"✗ Failed: {exc}")
        return 1

    finally:
        await crawler.close()


if __name__ == "__main__":
    exit_code = asyncio.run(fetch_prx_feed())
    raise SystemExit(exit_code)
