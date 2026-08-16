# PRX Feed Access Solutions

## Issue Summary

The PRX Dovetail RSS feed at `https://f.prxu.org/3329/feed-rss.xml` is protected by Cloudflare or similar WAF (Web Application Firewall) that blocks automated requests but allows browser access.

**Symptoms:**
- ✅ Works in Chrome/Firefox browsers
- ❌ Returns HTTP 403 "Access denied" for:
  - Python `urllib`
  - Python `requests`
  - `curl`
  - `feedparser`
  - Headless browsers (Playwright, Puppeteer)

## Root Cause

PRX uses Cloudflare or similar protection that:
1. Checks for valid browser fingerprints
2. May use JavaScript challenges
3. Blocks automated/bot requests by default
4. Requires full browser-like behavior to pass checks

## Solutions (In Order of Preference)

### Solution 1: RSS Proxy Service (Recommended)

Use a specialized RSS proxy service that handles bot detection:

**Option A: FeedBin API**
```python
# Free tier available, handles bot detection
import requests

response = requests.get(
    'https://api.feedbin.com/v2/feeds/preview.json',
    params={'url': 'https://f.prxu.org/3329/feed-rss.xml'}
)
```

**Option B: RSS2JSON**
```python
# Free tier: 10,000 requests/day
import requests

response = requests.get(
    'https://api.rss2json.com/v1/api.json',
    params={'rss_url': 'https://f.prxu.org/3329/feed-rss.xml'}
)
```

**Option C: OpenRSS**
```python
# Self-hostable or use public instance
import feedparser

feed = feedparser.parse(
    'https://openrss.org/https://f.prxu.org/3329/feed-rss.xml'
)
```

**Pros:**
- ✅ Handles bot detection automatically
- ✅ No browser overhead
- ✅ Fast and reliable
- ✅ Works in GitHub Actions

**Cons:**
- ⚠️ Adds dependency on third-party service
- ⚠️ May have rate limits (but generous free tiers)

---

### Solution 2: Playwright with Full Browser (For Development)

Use Playwright with a real browser for local testing:

```python
from playwright.sync_api import sync_playwright

def fetch_feed():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible browser
        page = browser.new_page()
        page.goto('https://f.prxu.org/3329/feed-rss.xml')
        content = page.content()
        browser.close()
        return content
```

**Pros:**
- ✅ Bypasses all bot detection
- ✅ Reliable for local development

**Cons:**
- ❌ Slow (2-5 seconds per fetch)
- ❌ Heavy resource usage
- ❌ Complex GitHub Actions setup
- ❌ May not work in headless mode

---

### Solution 3: Contact PRX for Whitelisting

Reach out to PRX Dovetail support to whitelist your automation:

```
Subject: Automated RSS Feed Access for Ghost Integration

Hi PRX Team,

I'm building an automated integration to publish our podcast episodes
from PRX Dovetail to our Ghost blog. Our RSS feed URL is:
https://f.prxu.org/3329/feed-rss.xml

Could you please whitelist our automation's User-Agent or IP address
to allow programmatic access to the feed?

User-Agent: PodcastPublisher/1.0 (Contact: your@email.com)
IP Range: (if known, e.g., GitHub Actions IPs)

Thank you!
```

**Pros:**
- ✅ Most reliable long-term solution
- ✅ No third-party dependencies
- ✅ Fast and simple

**Cons:**
- ⏳ Requires PRX support response
- ⏳ May take time to implement

---

### Solution 4: Cloudflare Bypass Techniques

Use specialized libraries that bypass Cloudflare:

**Option A: cloudscraper (Python)**
```bash
pip install cloudscraper
```

```python
import cloudscraper
import feedparser

scraper = cloudscraper.create_scraper()
response = scraper.get('https://f.prxu.org/3329/feed-rss.xml')

if response.status_code == 200:
    feed = feedparser.parse(response.content)
```

**Option B: undetected-chromedriver**
```bash
pip install undetected-chromedriver
```

```python
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

driver = uc.Chrome(headless=True)
driver.get('https://f.prxu.org/3329/feed-rss.xml')
xml_content = driver.page_source
driver.quit()
```

**Pros:**
- ✅ No third-party service needed
- ✅ Bypasses most Cloudflare protections

**Cons:**
- ⚠️ May break if Cloudflare updates detection
- ⚠️ Slower than direct requests
- ⚠️ More complex setup

---

### Solution 5: Manual Fallback with Caching

Periodically download feed manually and commit to repo:

```bash
# Manual process (run weekly or when needed)
# 1. Open feed in browser
# 2. Save as XML
# 3. Commit to repo

git add data/feed-cache.xml
git commit -m "Update feed cache"
```

Then automation reads from cache:

```python
import feedparser
from pathlib import Path

feed = feedparser.parse(Path('data/feed-cache.xml').read_text())
```

**Pros:**
- ✅ Always works
- ✅ No API dependencies
- ✅ Fast (reads from file)

**Cons:**
- ❌ Not fully automated
- ❌ Requires manual updates
- ❌ Defeats purpose of automation

---

## Recommended Implementation Strategy

### For Production (GitHub Actions)

**Primary:** RSS Proxy Service (Solution 1)
```python
import requests
import feedparser

# Use RSS2JSON as primary
def fetch_feed(url):
    response = requests.get(
        'https://api.rss2json.com/v1/api.json',
        params={'rss_url': url, 'api_key': 'YOUR_API_KEY'}  # optional
    )
    if response.status_code == 200:
        return response.json()
    raise Exception(f"Failed to fetch feed: {response.status_code}")
```

**Fallback:** Contact PRX (Solution 3)
- If proxy service fails or hits limits
- Email PRX support for whitelisting

### For Local Development

**Primary:** Playwright (Solution 2)
```python
# For testing and development only
from playwright.sync_api import sync_playwright

def fetch_feed_dev(url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        content = page.content()
        browser.close()
        return content
```

## Testing Each Solution

### Test Script

```python
#!/usr/bin/env python3.11
"""Test different methods to access PRX feed."""

import feedparser
import requests

FEED_URL = "https://f.prxu.org/3329/feed-rss.xml"


def test_direct():
    """Test direct feedparser access."""
    print("Testing direct feedparser...")
    feed = feedparser.parse(FEED_URL)
    print(f"  Entries: {len(feed.entries)}")
    return len(feed.entries) > 0


def test_rss2json():
    """Test RSS2JSON proxy."""
    print("Testing RSS2JSON...")
    response = requests.get(
        'https://api.rss2json.com/v1/api.json',
        params={'rss_url': FEED_URL}
    )
    data = response.json()
    print(f"  Status: {data.get('status')}")
    print(f"  Items: {len(data.get('items', []))}")
    return data.get('status') == 'ok'


def test_cloudscraper():
    """Test cloudscraper."""
    print("Testing cloudscraper...")
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        response = scraper.get(FEED_URL)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            print(f"  Entries: {len(feed.entries)}")
            return len(feed.entries) > 0
    except ImportError:
        print("  cloudscraper not installed")
    return False


if __name__ == '__main__':
    tests = [
        test_direct,
        test_rss2json,
        test_cloudscraper,
    ]

    results = {}
    for test in tests:
        try:
            results[test.__name__] = test()
        except Exception as e:
            print(f"  Error: {e}")
            results[test.__name__] = False
        print()

    print("Results:")
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {name}")
```

Save as `scripts/test_feed_access.py` and run:
```bash
python3.11 scripts/test_feed_access.py
```

## Implementation in GitHub Actions

### Using RSS2JSON (Recommended)

```yaml
# .github/workflows/publish-episodes.yml
name: Publish New Episodes

on:
  schedule:
    - cron: '*/30 * * * *'
  workflow_dispatch:

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install feedparser requests

      - name: Publish episodes
        env:
          GHOST_URL: ${{ secrets.GHOST_URL }}
          GHOST_ADMIN_KEY: ${{ secrets.GHOST_ADMIN_KEY }}
          PRX_FEED_URL: ${{ secrets.PRX_FEED_URL }}
          RSS2JSON_API_KEY: ${{ secrets.RSS2JSON_API_KEY }}  # optional
        run: python scripts/publish_new_episodes.py

      - name: Commit state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/published_episodes.json
          git commit -m "Update published episodes [skip ci]" || exit 0
          git push
```

## Cost Analysis

| Solution | Free Tier | Paid Plans | Recommendation |
|----------|-----------|------------|----------------|
| RSS2JSON | 10,000 req/day | $10/mo (100k) | ✅ Sufficient for free |
| FeedBin | Trial only | $5/mo | ⚠️ Paid required |
| OpenRSS | Unlimited | Self-host only | ✅ If self-hosting |
| cloudscraper | Unlimited | N/A | ⚠️ May break |
| PRX Whitelisting | Free | Free | ✅ Best if approved |

**Recommendation:** Start with RSS2JSON free tier (10,000 requests/day = checking every 30 min = ~1,500/day = plenty of headroom)

## Next Steps

1. **Test RSS2JSON** with the script above
2. **If works:** Implement in automation
3. **If fails:** Contact PRX support for whitelisting
4. **Fallback:** Use cloudscraper or Playwright

## References

- [RSS2JSON Documentation](https://rss2json.com/docs)
- [FeedBin API](https://github.com/feedbin/feedbin-api)
- [cloudscraper GitHub](https://github.com/VeNoMouS/cloudscraper)
- [Playwright Python](https://playwright.dev/python/)

---

**Status:** Solutions documented, testing required
**Last Updated:** 2025-11-14
**Recommended:** RSS2JSON (Solution 1) → PRX Whitelisting (Solution 3)
