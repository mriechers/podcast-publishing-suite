#!/usr/bin/env python3
"""
Remove 'episode-listen-links' HTML blocks from all Ghost posts.

These blocks contain pod.link buttons that were added by the Luminous feed
importer. Editorial decision: they are no longer wanted.

Usage:
    python scripts/remove_listen_links.py           # dry-run (default)
    python scripts/remove_listen_links.py --execute  # apply changes

Follows the same auth/update pattern as scripts/update_test_posts.py.
"""

import argparse
import re
import sys

import jwt
import requests
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = '695986a3fd51b4640fe0a714:1a2b9fb8986fe7d5b31753f8cb37d2ff809fb03c676ec19e59a2abd98ee7bd6a'
BASE_URL = 'http://192.168.5.156:2368'
PAGE_SIZE = 15

# Matches the entire HTML card wrapping the listen-links div.
# Uses re.DOTALL so `.*?` spans newlines inside the div.
LISTEN_LINKS_RE = re.compile(
    r'<!--kg-card-begin: html-->\s*'
    r'<div class="episode-listen-links">'
    r'.*?'
    r'</div>\s*'
    r'<!--kg-card-end: html-->',
    re.DOTALL,
)

# After removal the HTML may have runs of 3+ newlines; collapse to 2.
EXCESS_NEWLINES_RE = re.compile(r'\n{3,}')


# ---------------------------------------------------------------------------
# Auth (same as update_test_posts.py)
# ---------------------------------------------------------------------------
def get_auth_headers(api_key: str) -> dict:
    """Generate Ghost Admin API JWT auth headers."""
    key_id, secret = api_key.split(':')
    iat = int(datetime.now(timezone.utc).timestamp())
    header = {'alg': 'HS256', 'typ': 'JWT', 'kid': key_id}
    payload = {'iat': iat, 'exp': iat + 300, 'aud': '/admin/'}
    token = jwt.encode(
        payload, bytes.fromhex(secret), algorithm='HS256', headers=header
    )
    return {
        'Authorization': f'Ghost {token}',
        'Accept-Version': 'v5.0',
        'Content-Type': 'application/json',
    }


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------
def fetch_all_posts(headers: dict) -> list[dict]:
    """Paginate through all posts, returning a list of post dicts."""
    posts = []
    page = 1
    while True:
        url = (
            f'{BASE_URL}/ghost/api/admin/posts/'
            f'?limit={PAGE_SIZE}&page={page}&formats=html'
        )
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        posts.extend(data['posts'])
        meta = data.get('meta', {}).get('pagination', {})
        if page >= meta.get('pages', 1):
            break
        page += 1
    return posts


def refetch_post(headers: dict, post_id: str) -> dict:
    """Re-fetch a single post to get a fresh updated_at for the PUT."""
    url = f'{BASE_URL}/ghost/api/admin/posts/{post_id}/?formats=html'
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()['posts'][0]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def strip_listen_links(html: str) -> str | None:
    """Remove listen-links block from HTML. Returns None if no match."""
    if not LISTEN_LINKS_RE.search(html):
        return None
    cleaned = LISTEN_LINKS_RE.sub('', html)
    cleaned = EXCESS_NEWLINES_RE.sub('\n\n', cleaned)
    return cleaned.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Remove episode-listen-links blocks from Ghost posts.'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually apply changes (default is dry-run).',
    )
    args = parser.parse_args()

    mode = 'EXECUTE' if args.execute else 'DRY-RUN'
    print(f'Mode: {mode}\n')

    headers = get_auth_headers(API_KEY)

    # 1. Fetch all posts
    print('Fetching posts...')
    posts = fetch_all_posts(headers)
    print(f'Total posts: {len(posts)}\n')

    # 2. Identify affected posts
    affected: list[dict] = []
    for post in posts:
        html = post.get('html') or ''
        cleaned = strip_listen_links(html)
        if cleaned is not None:
            affected.append({
                'id': post['id'],
                'title': post['title'],
                'status': post['status'],
                'cleaned_html': cleaned,
            })

    if not affected:
        print('No posts contain listen-links blocks. Nothing to do.')
        return 0

    print(f'Affected posts ({len(affected)}):')
    for p in affected:
        print(f'  [{p["status"]:>9}]  {p["title"]}')
    print()

    if not args.execute:
        print('Run with --execute to apply changes.')
        return 0

    # 3. Apply changes
    success = 0
    failed = 0
    for p in affected:
        try:
            fresh = refetch_post(headers, p['id'])
            payload = {
                'html': p['cleaned_html'],
                'updated_at': fresh['updated_at'],
            }
            resp = requests.put(
                f'{BASE_URL}/ghost/api/admin/posts/{p["id"]}/?source=html',
                headers=headers,
                json={'posts': [payload]},
            )
            if resp.status_code == 200:
                print(f'  ✓ Updated: {p["title"]}')
                success += 1
            else:
                print(f'  ✗ Failed ({resp.status_code}): {p["title"]}')
                print(f'    {resp.text[:200]}')
                failed += 1
        except Exception as exc:
            print(f'  ✗ Error: {p["title"]} — {exc}')
            failed += 1

    print(f'\nDone. Updated: {success}, Failed: {failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
