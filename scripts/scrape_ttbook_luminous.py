#!/usr/bin/env python3
"""
Scrape TTBOOK.org Luminous episode pages before the site goes away.

Extracts:
- Full HTML (for archival)
- Transcript text
- Guest information
- Interview segment links
- Metadata

Outputs to sample-data/ttbook-cache/luminous/
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    from crawl4ai import AsyncWebCrawler
except ImportError:
    print("Error: crawl4ai not installed. Run:")
    print("  source .venv-crawl4ai/bin/activate")
    print("  pip install crawl4ai")
    sys.exit(1)

# Episode URLs from the RSS feed
LUMINOUS_URLS = [
    "https://www.ttbook.org/show/luminous-reclaiming-acid-queen",
    "https://www.ttbook.org/show/luminous-thomas-metzinger-why-we-need-culture-consciousness",
    "https://www.ttbook.org/show/luminous-marcelo-and-kari-gleiser-tripping-your-partner",
    "https://www.ttbook.org/show/luminous-chris-timmerman-how-dmt-can-deconstruct-mind",
    "https://www.ttbook.org/show/luminous-spring-washam-buddhist-shaman",
    "https://www.ttbook.org/interview/luminous-do-psychedelics-reveal-deeper-dimension-reality",
    "https://www.ttbook.org/show/luminous-katherine-maclean-mushrooms-and-limits-consensus-reality",
    "https://www.ttbook.org/show/erik-davis-lsd-psychedelic-underground-and-visionary-experience",
    "https://www.ttbook.org/show/did-ancient-greeks-use-drugs-find-god",
    "https://www.ttbook.org/show/luminous-brief-history-getting-high",
    "https://www.ttbook.org/show/luminous-it-drug-or-it-trip",
    "https://www.ttbook.org/show/luminous-can-you-have-too-much-transcendence",
    "https://www.ttbook.org/show/luminous-can-psychedelics-be-decolonized",
    "https://www.ttbook.org/show/luminous-giving-mdma-octopuses",
    "https://www.ttbook.org/show/luminous-your-brain-shrooms",
    "https://www.ttbook.org/show/luminous-melissa-etheridge-ayahuasca",
    "https://www.ttbook.org/show/luminous-building-psychedelic-revolution",
    "https://www.ttbook.org/show/luminous-what-can-psychedelics-teach-us-about-dying",
]

# Also grab the series landing page
SERIES_URL = "https://www.ttbook.org/series/luminous"

OUTPUT_DIR = Path(__file__).parent.parent / "sample-data" / "ttbook-cache" / "luminous"


def extract_slug(url: str) -> str:
    """Extract slug from URL for filename."""
    path = urlparse(url).path
    return path.split("/")[-1]


def extract_transcript(html: str) -> str | None:
    """Extract transcript text from the HTML."""
    # Look for the transcript fieldset
    match = re.search(
        r'<fieldset[^>]*id="transcript"[^>]*>.*?<div class="field-item even">(.*?)</div>\s*</div>\s*</div>\s*</fieldset>',
        html,
        re.DOTALL | re.IGNORECASE
    )
    if match:
        transcript_html = match.group(1)
        # Strip HTML tags but preserve paragraph breaks
        transcript = re.sub(r'<p[^>]*>', '\n\n', transcript_html)
        transcript = re.sub(r'</p>', '', transcript)
        transcript = re.sub(r'<br\s*/?>', '\n', transcript)
        transcript = re.sub(r'<em>', '', transcript)
        transcript = re.sub(r'</em>', '', transcript)
        transcript = re.sub(r'<[^>]+>', '', transcript)
        transcript = re.sub(r'\n{3,}', '\n\n', transcript.strip())
        return transcript
    return None


def extract_guests(html: str) -> list[dict]:
    """Extract guest information from the HTML."""
    guests = []

    # Find the guests section
    guests_section = re.search(
        r'<div class="field field-name-field-guests[^>]*>.*?<div class="field-items">(.*?)</div>\s*</div>\s*</div>',
        html,
        re.DOTALL | re.IGNORECASE
    )

    if guests_section:
        section_html = guests_section.group(1)

        # Extract individual guest entries
        guest_blocks = re.findall(
            r'<h\d[^>]*><a href="([^"]+)"[^>]*>([^<]+)</a></h\d>',
            section_html
        )

        for link, name in guest_blocks:
            guests.append({
                "name": name.strip(),
                "url": f"https://www.ttbook.org{link}" if link.startswith("/") else link
            })

    return guests


def extract_interviews(html: str) -> list[dict]:
    """Extract interview segment information."""
    interviews = []

    # Find interview nodes
    interview_matches = re.findall(
        r'<div[^>]*class="[^"]*node--interview[^"]*"[^>]*>.*?<a href="(/interview/[^"]+)"[^>]*>([^<]+)</a>',
        html,
        re.DOTALL
    )

    for link, title in interview_matches:
        interviews.append({
            "title": title.strip(),
            "url": f"https://www.ttbook.org{link}"
        })

    return interviews


def extract_metadata(html: str, url: str) -> dict:
    """Extract page metadata."""
    metadata = {"source_url": url, "scraped_at": datetime.now().isoformat()}

    # Title
    title_match = re.search(r'<title>([^<]+)</title>', html)
    if title_match:
        metadata["title"] = title_match.group(1).split("|")[0].strip()

    # Description
    desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
    if desc_match:
        metadata["description"] = desc_match.group(1)

    # Air date
    date_match = re.search(r'Original Air Date:\s*([^<]+)', html)
    if date_match:
        metadata["air_date"] = date_match.group(1).strip()

    return metadata


async def scrape_page(crawler, url: str) -> dict | None:
    """Scrape a single TTBOOK page."""
    slug = extract_slug(url)
    print(f"  Scraping: {slug}")

    try:
        result = await crawler.arun(url=url)

        if not result.success:
            print(f"    Failed: {result.error_message}")
            return None

        html = result.html

        return {
            "slug": slug,
            "url": url,
            "html": html,
            "markdown": result.markdown,
            "transcript": extract_transcript(html),
            "guests": extract_guests(html),
            "interviews": extract_interviews(html),
            "metadata": extract_metadata(html, url),
        }

    except Exception as e:
        print(f"    Error: {e}")
        return None


async def main():
    """Main scraping routine."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scraping {len(LUMINOUS_URLS)} Luminous episode pages...")
    print(f"Output: {OUTPUT_DIR}\n")

    results = []
    failed = []

    async with AsyncWebCrawler() as crawler:
        # Scrape series landing page first
        print("Scraping series landing page...")
        series_result = await scrape_page(crawler, SERIES_URL)
        if series_result:
            series_path = OUTPUT_DIR / "_series_landing.json"
            with open(series_path, "w") as f:
                json.dump(series_result, f, indent=2)
            print(f"  Saved: {series_path.name}\n")

        # Scrape each episode
        print("Scraping episode pages...")
        for url in LUMINOUS_URLS:
            result = await scrape_page(crawler, url)

            if result:
                results.append(result)

                # Save individual file
                slug = result["slug"]

                # Save JSON with all extracted data
                json_path = OUTPUT_DIR / f"{slug}.json"
                with open(json_path, "w") as f:
                    json.dump(result, f, indent=2)

                # Save raw HTML
                html_path = OUTPUT_DIR / f"{slug}.html"
                with open(html_path, "w") as f:
                    f.write(result["html"])

                # Save transcript if available
                if result["transcript"]:
                    transcript_path = OUTPUT_DIR / f"{slug}_transcript.txt"
                    with open(transcript_path, "w") as f:
                        f.write(result["transcript"])

                print(f"    Saved: {slug} (transcript: {'yes' if result['transcript'] else 'no'})")
            else:
                failed.append(url)

            # Be polite to the server
            await asyncio.sleep(1)

    # Write manifest
    manifest = {
        "scraped_at": datetime.now().isoformat(),
        "total_urls": len(LUMINOUS_URLS),
        "successful": len(results),
        "failed": len(failed),
        "failed_urls": failed,
        "episodes": [
            {
                "slug": r["slug"],
                "url": r["url"],
                "title": r["metadata"].get("title"),
                "has_transcript": r["transcript"] is not None,
                "guest_count": len(r["guests"]),
                "interview_count": len(r["interviews"]),
            }
            for r in results
        ]
    }

    manifest_path = OUTPUT_DIR / "_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Scraping complete!")
    print(f"  Successful: {len(results)}/{len(LUMINOUS_URLS)}")
    print(f"  Failed: {len(failed)}")
    print(f"  Manifest: {manifest_path}")

    if failed:
        print(f"\nFailed URLs:")
        for url in failed:
            print(f"  - {url}")


if __name__ == "__main__":
    asyncio.run(main())
