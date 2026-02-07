#!/usr/bin/env python3.11
"""
Fetch Ghost documentation directly from the TryGhost/Docs GitHub repository.

This fetches the markdown source files directly from GitHub.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError


# Key Ghost documentation files to fetch from GitHub
DOCS_BASE_URL = "https://raw.githubusercontent.com/TryGhost/Docs/main"

GHOST_DOCS_FILES = [
    {
        "slug": "introduction",
        "path": "introduction.mdx",
        "notes": "Introduction to Ghost platform"
    },
    {
        "slug": "admin-api",
        "path": "admin-api.mdx",
        "notes": "Admin API overview and reference"
    },
    {
        "slug": "content-api",
        "path": "content-api.mdx",
        "notes": "Content API overview and reference"
    },
    {
        "slug": "webhooks",
        "path": "webhooks.mdx",
        "notes": "Webhooks for event-driven automation"
    },
    {
        "slug": "publishing",
        "path": "publishing.mdx",
        "notes": "Publishing content with Ghost"
    },
    {
        "slug": "members",
        "path": "members.mdx",
        "notes": "Members and subscriptions"
    },
    {
        "slug": "newsletters",
        "path": "newsletters.mdx",
        "notes": "Newsletter functionality"
    },
    {
        "slug": "admin-api-posts",
        "path": "admin-api/posts.mdx",
        "notes": "Posts endpoint in Admin API"
    },
    {
        "slug": "admin-api-tags",
        "path": "admin-api/tags.mdx",
        "notes": "Tags endpoint in Admin API"
    },
    {
        "slug": "admin-api-authentication",
        "path": "admin-api/authentication.mdx",
        "notes": "Authentication for Admin API"
    },
    {
        "slug": "content-api-posts",
        "path": "content-api/posts.mdx",
        "notes": "Posts endpoint in Content API"
    },
]


def fetch_doc(doc_info: dict, output_dir: Path) -> tuple[bool, str]:
    """Fetch a single documentation file from GitHub."""

    url = f"{DOCS_BASE_URL}/{doc_info['path']}"
    slug = doc_info['slug']

    print(f"Fetching: {slug} ({url})")

    try:
        with urlopen(url) as response:
            if response.status != 200:
                return False, f"HTTP {response.status}"

            content = response.read().decode('utf-8')

            # Save as markdown
            md_path = output_dir / f"{slug}.md"
            md_path.write_text(content, encoding='utf-8')

            # Save metadata
            metadata = {
                "url": url,
                "slug": slug,
                "category": "ghost",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "notes": doc_info.get("notes", ""),
                "source": "GitHub TryGhost/Docs repository",
                "content_length": len(content),
            }

            json_path = output_dir / f"{slug}.json"
            json_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')

            print(f"  ✓ Saved {slug} ({len(content)} bytes)")
            return True, ""

    except HTTPError as e:
        return False, f"HTTP error: {e.code}"
    except Exception as e:
        return False, str(e)


def main():
    """Fetch all Ghost documentation files."""

    output_dir = Path("knowledge/ghost")
    output_dir.mkdir(parents=True, exist_ok=True)

    succeeded = []
    failed = []

    for doc_info in GHOST_DOCS_FILES:
        success, error = fetch_doc(doc_info, output_dir)

        if success:
            succeeded.append(doc_info['slug'])
        else:
            failed.append((doc_info['slug'], error))
            print(f"  ✗ Failed {doc_info['slug']}: {error}")

    # Update sources.json
    sources_file = Path("knowledge/sources.json")
    sources = {
        "sources": [
            {
                "category": "ghost",
                "slug": doc["slug"],
                "url": f"{DOCS_BASE_URL}/{doc['path']}",
                "notes": doc["notes"]
            }
            for doc in GHOST_DOCS_FILES
        ]
    }
    sources_file.write_text(json.dumps(sources, indent=2), encoding='utf-8')

    print("\n" + "="*60)
    print(f"Succeeded: {len(succeeded)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed files:")
        for slug, error in failed:
            print(f"  - {slug}: {error}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
