#!/usr/bin/env python3.11
"""
Fetch PRX RSS feed using Playwright with full browser context.
This bypasses bot detection by using a real browser.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: playwright not installed")
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)

import feedparser


async def fetch_feed_with_playwright(url: str) -> str:
    """Fetch RSS feed using real browser to bypass bot detection."""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            ignore_https_errors=True
        )
        page = await context.new_page()

        response = await page.goto(url, wait_until='networkidle')
        content = await page.content()

        await browser.close()

        return content


async def main():
    """Test fetching and parsing the PRX feed."""

    feed_url = "https://f.prxu.org/3329/feed-rss.xml"

    print(f"Fetching: {feed_url}")
    print("Using Playwright with real browser...")

    try:
        xml_content = await fetch_feed_with_playwright(feed_url)

        print(f"✓ Fetched {len(xml_content)} bytes")

        # Parse with feedparser
        feed = feedparser.parse(xml_content)

        print(f"\nFeed Information:")
        print(f"  Title: {feed.feed.get('title', 'N/A')}")
        print(f"  Description: {feed.feed.get('description', 'N/A')[:100]}...")
        print(f"  Total Episodes: {len(feed.entries)}")

        if feed.entries:
            print(f"\nFirst Episode:")
            first = feed.entries[0]
            print(f"  Title: {first.get('title', 'N/A')}")
            print(f"  Published: {first.get('published', 'N/A')}")
            print(f"  GUID: {first.get('id', 'N/A')}")

            # Save full feed to file
            output_dir = Path("knowledge/prx")
            output_dir.mkdir(parents=True, exist_ok=True)

            feed_file = output_dir / "feed-rss.xml"
            feed_file.write_text(xml_content, encoding='utf-8')
            print(f"\n✓ Saved feed to {feed_file}")

            # Run full analysis
            print("\nRunning full feed analysis...")
            import subprocess
            subprocess.run([sys.executable, "scripts/analyze_prx_feed.py"])

        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
