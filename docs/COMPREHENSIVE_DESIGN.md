# PRX-to-Ghost Publisher: Comprehensive Design Document

**Version:** 1.1
**Date:** 2025-12-08
**Status:** Design Phase
**Author:** Claude (Design Architect)

---

## Executive Summary

This document provides a comprehensive design for an automated system that publishes podcast episodes from **multiple PRX Dovetail RSS feeds** to a single Ghost-powered website. The system will ingest episodes from two podcasts—**Luminous** and **Wonder Cabinet**—and publish them to Wonder Cabinet Productions (https://wondercabinetproductions.com/) with proper routing to show-specific pages.

The design prioritizes **long-term stability**, **minimal maintenance**, and **graceful degradation** to ensure the system continues working reliably for years with minimal intervention.

### Target Configuration

| Podcast | Feed URL | Ghost Route |
|---------|----------|-------------|
| **Luminous** | `https://f.prxu.org/3329/feed-rss.xml` | `/luminous/` |
| **Wonder Cabinet** | `https://f.prxu.org/120/ttbook` | `/wonder-cabinet/` |

**Ghost Site:** https://wondercabinetproductions.com/

### Key Design Principles

1. **Simplicity Over Cleverness** - Use the most straightforward approach that meets requirements
2. **Defense in Depth** - Multiple layers of protection against failures
3. **Observable by Default** - Every operation is logged and trackable
4. **Graceful Degradation** - Failures are contained, not catastrophic
5. **Self-Healing** - Automatic recovery from transient issues
6. **Future-Proof** - Designed to accommodate changes in external APIs

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Multi-Feed Architecture](#2-multi-feed-architecture)
3. [Ghost Routing and Content Organization](#3-ghost-routing-and-content-organization)
4. [Component Design](#4-component-design)
5. [Data Flow and State Management](#5-data-flow-and-state-management)
6. [Error Handling and Resilience](#6-error-handling-and-resilience)
7. [Long-Term Stability Analysis](#7-long-term-stability-analysis)
8. [Security Considerations](#8-security-considerations)
9. [Monitoring and Observability](#9-monitoring-and-observability)
10. [Maintenance Operations](#10-maintenance-operations)
11. [Risk Assessment and Mitigations](#11-risk-assessment-and-mitigations)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Ghost Theme Customization](#13-ghost-theme-customization)
14. [Further Research Recommendations](#14-further-research-recommendations) (includes TTBOOK Cache)
15. [Agent-Driven Development Plan](#15-agent-driven-development-plan)
16. [Development Roadmap with Action Items](#16-development-roadmap-with-action-items)

---

## 1. System Architecture

### 1.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRX-to-Ghost Publisher                                │
│                                                                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  Trigger Layer  │───>│ Processing Core │───>│  Output Layer   │         │
│  │                 │    │                 │    │                 │         │
│  │ - GitHub Cron   │    │ - Feed Fetcher  │    │ - Ghost Client  │         │
│  │ - Manual Invoke │    │ - State Manager │    │ - Notification  │         │
│  │ - Webhook (opt) │    │ - Transformer   │    │ - State Commit  │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│           │                      │                      │                    │
│           v                      v                      v                    │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ External Inputs │    │  Internal State │    │ External Outputs │        │
│  │                 │    │                 │    │                 │         │
│  │ - PRX RSS Feed  │    │ - episodes.json │    │ - Ghost API     │         │
│  │ - Environment   │    │ - run_history   │    │ - Git History   │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Decision: GitHub Actions

**Choice:** GitHub Actions as the orchestration platform

**Rationale:**
- **Zero operational cost** - Free tier covers all requirements
- **Zero infrastructure** - No servers to maintain, patch, or monitor
- **Built-in reliability** - GitHub's infrastructure handles availability
- **Git-native state** - State files are version-controlled automatically
- **Easy debugging** - Complete logs accessible via GitHub UI
- **Manual override** - `workflow_dispatch` allows on-demand runs
- **Scalability path** - Can migrate to dedicated infrastructure if needed

**Trade-offs:**
- 5-minute minimum cron interval (acceptable for podcast publishing)
- 2-3 minute cold start per run (acceptable for non-real-time use case)
- GitHub rate limits apply (well within limits for this use case)

### 1.3 Alternative Architectures (for Future Migration)

If requirements change, these alternatives are pre-designed:

| Trigger | When to Migrate | Implementation |
|---------|-----------------|----------------|
| AWS Lambda + EventBridge | Need < 5-minute intervals | Same Python code, add handler wrapper |
| Fly.io Container | Need web dashboard or webhooks | Containerize, add FastAPI endpoints |
| Cloudflare Workers | Need edge deployment | Rewrite in JavaScript, use Durable Objects |

---

## 2. Multi-Feed Architecture

### 2.1 Feed Configuration

The system ingests from multiple RSS feeds, each with its own configuration:

```python
# config/feeds.py
FEEDS = {
    "luminous": {
        "name": "Luminous",
        "feed_url": "https://f.prxu.org/3329/feed-rss.xml",
        "ghost_primary_tag": "luminous",        # Routes to /luminous/
        "ghost_internal_tag": "#show-luminous", # Hidden organizational tag
        "slug_prefix": "luminous-",             # Prevents slug collisions
        "default_tags": ["Podcast", "Luminous"],
        "prx_series_id": "3329",
    },
    "wonder-cabinet": {
        "name": "Wonder Cabinet",
        "feed_url": "https://f.prxu.org/120/ttbook",
        "ghost_primary_tag": "wonder-cabinet",
        "ghost_internal_tag": "#show-wonder-cabinet",
        "slug_prefix": "wonder-cabinet-",
        "default_tags": ["Podcast", "Wonder Cabinet"],
        "prx_series_id": "120",
    }
}
```

### 2.2 Multi-Feed Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Multi-Feed Processing                                  │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     For Each Configured Feed                         │    │
│  │                                                                       │    │
│  │   ┌───────────────┐                                                  │    │
│  │   │ Feed: Luminous │────┐                                            │    │
│  │   └───────────────┘    │                                            │    │
│  │                         │    ┌──────────────┐    ┌──────────────┐   │    │
│  │   ┌───────────────┐    ├───>│   Unified    │───>│   Unified    │   │    │
│  │   │ Feed: Wonder  │────┘    │  Feed Parser │    │  Publisher   │   │    │
│  │   │    Cabinet    │         └──────────────┘    └──────────────┘   │    │
│  │   └───────────────┘                │                    │          │    │
│  │                                    v                    v          │    │
│  │                           ┌──────────────┐    ┌──────────────┐    │    │
│  │                           │ Per-Feed     │    │ Ghost API    │    │    │
│  │                           │ State Mgmt   │    │ (Single Site)│    │    │
│  │                           └──────────────┘    └──────────────┘    │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 State Structure for Multiple Feeds

```json
{
  "schema_version": "2.0",
  "last_successful_run": "2025-12-08T10:30:00Z",
  "feeds": {
    "luminous": {
      "last_checked": "2025-12-08T10:30:00Z",
      "last_successful_fetch": "2025-12-08T10:30:00Z",
      "published_episodes": {
        "prx:3329:episode:12345": {
          "ghost_post_id": "abc123",
          "ghost_slug": "luminous-episode-5-title",
          "published_at": "2025-12-08T10:30:00Z",
          "title": "Episode 5: Title Here"
        }
      }
    },
    "wonder-cabinet": {
      "last_checked": "2025-12-08T10:30:00Z",
      "last_successful_fetch": "2025-12-08T10:30:00Z",
      "published_episodes": {
        "prx:120:episode:67890": {
          "ghost_post_id": "def456",
          "ghost_slug": "wonder-cabinet-episode-10-title",
          "published_at": "2025-12-08T10:30:00Z",
          "title": "Episode 10: Another Title"
        }
      }
    }
  },
  "run_history": [...]
}
```

### 2.4 Feed Isolation Principle

Each feed is processed **independently**:
- Failure in one feed doesn't affect the other
- State is tracked per-feed
- Run history captures per-feed results
- Alerts can be feed-specific

```python
def process_all_feeds():
    """Process each feed independently, collecting results."""
    results = {}

    for feed_id, config in FEEDS.items():
        try:
            result = process_single_feed(feed_id, config)
            results[feed_id] = {"status": "success", "published": result.count}
        except FeedError as e:
            results[feed_id] = {"status": "failed", "error": str(e)}
            logger.error(f"Feed {feed_id} failed: {e}")
            # Continue to next feed - don't let one failure stop others

    return results
```

---

## 3. Ghost Routing and Content Organization

### 3.1 Ghost Tags Strategy

Ghost uses **tags** for content organization and routing. For multi-show support:

| Tag Type | Purpose | Example | Visibility |
|----------|---------|---------|------------|
| **Primary Tag** | Routes post to correct collection | `luminous` | Public |
| **Internal Tag** | Additional filtering, won't display | `#show-luminous` | Hidden |
| **Content Tags** | Episode categorization | `Season 2`, `Interview` | Public |
| **Format Tags** | Content type | `Podcast`, `Episode` | Public |

### 3.2 Ghost routes.yaml Configuration

This file must be configured in Ghost to enable separate podcast pages:

```yaml
# Ghost routes.yaml - Deploy via Ghost Admin > Settings > Labs > Routes

routes:
  # Static pages for each show (optional - can be Ghost Pages instead)
  # /luminous/about/: luminous-about
  # /wonder-cabinet/about/: wonder-cabinet-about

collections:
  # Main homepage - shows all content or curated selection
  /:
    permalink: /{slug}/
    template: index

  # Luminous podcast collection
  /luminous/:
    permalink: /luminous/{slug}/
    template: podcast
    filter: primary_tag:luminous
    data:
      tag: luminous

  # Wonder Cabinet podcast collection
  /wonder-cabinet/:
    permalink: /wonder-cabinet/{slug}/
    template: podcast
    filter: primary_tag:wonder-cabinet
    data:
      tag: wonder-cabinet

taxonomies:
  tag: /tag/{slug}/
  author: /author/{slug}/
```

### 3.3 How Posts Are Routed

When a post is created with `primary_tag: luminous`:
1. Ghost assigns it to the `/luminous/` collection
2. The URL becomes `/luminous/{slug}/`
3. It appears on the `/luminous/` listing page
4. It can optionally appear on homepage (depends on homepage template)

**Critical:** The `primary_tag` (first tag in the tags array) determines routing.

### 3.4 Post Creation with Tags

```python
def transform_episode_to_ghost_post(episode: RSSItem, feed_config: dict) -> dict:
    """Transform RSS episode to Ghost post with proper tagging."""

    # Build tags array - PRIMARY TAG MUST BE FIRST
    tags = [
        {"name": feed_config["ghost_primary_tag"]},  # FIRST = routing
        {"name": feed_config["ghost_internal_tag"]}, # Internal marker
    ]

    # Add default tags from config
    for tag_name in feed_config.get("default_tags", []):
        tags.append({"name": tag_name})

    # Add episode-specific tags
    if season := episode.get("itunes_season"):
        tags.append({"name": f"Season {season}"})
    if ep_type := episode.get("itunes_episodeType"):
        tags.append({"name": ep_type.capitalize()})

    return {
        "title": episode.title,
        "slug": f"{feed_config['slug_prefix']}{slugify(episode.title)}",
        "html": build_post_html(episode, feed_config),
        "status": "published",
        "published_at": parse_date(episode.pubDate),
        "feature_image": episode.get("itunes_image"),
        "custom_excerpt": truncate(episode.description, 300),
        "tags": tags,  # Primary tag FIRST for routing
        "meta_title": episode.title,
        "meta_description": truncate(episode.description, 160),
    }
```

### 3.5 Slug Collision Prevention

Since both podcasts publish to the same Ghost instance, slug collisions are possible (e.g., both shows have "Episode 1"). Prevention strategy:

```python
def generate_unique_slug(episode: RSSItem, feed_config: dict) -> str:
    """Generate a slug guaranteed to be unique across feeds."""

    base_slug = slugify(episode.title)

    # Option 1: Prefix with show identifier (recommended)
    return f"{feed_config['slug_prefix']}{base_slug}"

    # Option 2: Include PRX episode ID
    # prx_id = extract_prx_id(episode.guid)
    # return f"{base_slug}-{prx_id}"

# Examples:
# "luminous-episode-5-future-of-storytelling"
# "wonder-cabinet-episode-5-different-topic"
```

### 3.6 Ghost Theme Requirements

The Ghost theme for wondercabinetproductions.com needs:

1. **podcast.hbs template** - For episode listing pages
2. **Tag filtering support** - To show only episodes from each collection
3. **Audio player styling** - CSS for PRX embedded player
4. **Show-specific branding** - Different headers/colors per collection (optional)

**Minimum theme check:**
```handlebars
{{!-- podcast.hbs or index.hbs --}}
{{#foreach posts}}
  <article class="episode {{post_class}}">
    <h2>{{title}}</h2>
    {{content}}
  </article>
{{/foreach}}
```

### 3.7 Homepage Strategy Options

| Option | Description | Implementation |
|--------|-------------|----------------|
| **Combined Feed** | All episodes from both shows | Default homepage, no filtering |
| **Separate Sections** | Two sections, one per show | Custom template with `{{#get}}` blocks |
| **Featured Only** | Manually curated episodes | Use `featured: true` flag |
| **Latest Each** | Most recent from each show | Template with filtered `{{#get}}` queries |

**Recommended for Wonder Cabinet Productions:**

```handlebars
{{!-- index.hbs - Homepage with both shows --}}

<section class="luminous-latest">
  <h2>Latest from Luminous</h2>
  {{#get "posts" filter="primary_tag:luminous" limit="3"}}
    {{#foreach posts}}
      <article>{{title}}</article>
    {{/foreach}}
  {{/get}}
</section>

<section class="wonder-cabinet-latest">
  <h2>Latest from Wonder Cabinet</h2>
  {{#get "posts" filter="primary_tag:wonder-cabinet" limit="3"}}
    {{#foreach posts}}
      <article>{{title}}</article>
    {{/foreach}}
  {{/get}}
</section>
```

---

## 4. Component Design

### 4.1 Feed Fetcher Module

**Responsibility:** Retrieve and parse PRX RSS feeds reliably

```python
# Pseudo-structure
class FeedFetcher:
    """Handles RSS feed retrieval with multiple fallback strategies."""

    strategies = [
        DirectFetch,      # Try direct HTTP first
        RSS2JSONProxy,    # Use proxy service if direct fails
        CloudscraperFetch, # Cloudflare bypass as fallback
    ]

    def fetch(self, url: str) -> Feed:
        """Attempt each strategy until one succeeds."""
        for strategy in self.strategies:
            try:
                return strategy.fetch(url)
            except FetchError as e:
                self.log_failure(strategy, e)
                continue
        raise AllStrategiesFailed(url)
```

**Key Design Decisions:**

1. **Strategy Pattern** - Multiple fetch mechanisms with automatic fallback
2. **Timeout Boundaries** - Each strategy has independent timeout (30s)
3. **Parse Validation** - Feed is validated before returning (required fields check)
4. **Caching** - Optional local cache for development/testing

**Feed Access Strategies (Priority Order):**

1. **Direct `feedparser`** - Simplest, try first
2. **RSS2JSON API** - Handles most bot detection (10k free requests/day)
3. **cloudscraper** - Cloudflare bypass library
4. **Contact PRX** - Request IP whitelisting (one-time operational task)

### 4.2 State Manager Module

**Responsibility:** Track published episodes and operational history

```python
# State file structure
{
    "schema_version": "1.0",
    "last_successful_run": "2025-12-08T10:30:00Z",
    "published_episodes": {
        "prx:3329:episode:12345": {
            "ghost_post_id": "abc123",
            "published_at": "2025-12-08T10:30:00Z",
            "title": "Episode 5: Future of Public Media",
            "checksum": "sha256:..."
        }
    },
    "run_history": [
        {
            "timestamp": "2025-12-08T10:30:00Z",
            "status": "success",
            "episodes_checked": 10,
            "episodes_published": 1,
            "duration_seconds": 45
        }
    ]
}
```

**Key Design Decisions:**

1. **Schema Versioning** - Enables future migrations without breaking old data
2. **GUID as Primary Key** - PRX episode GUID is globally unique
3. **Content Checksum** - Detect if episode content changed (enable updates)
4. **Run History** - Bounded array (last 100 runs) for operational visibility
5. **Atomic Writes** - Write to temp file, then rename (prevents corruption)

### 4.3 Episode Transformer Module

**Responsibility:** Convert RSS episode data to Ghost post format

```python
class EpisodeTransformer:
    """Transforms PRX RSS items to Ghost post payloads."""

    def transform(self, episode: RSSItem) -> GhostPost:
        return {
            "title": self.extract_title(episode),
            "slug": self.generate_slug(episode),
            "html": self.build_html_content(episode),
            "status": "published",
            "published_at": self.parse_date(episode.pubDate),
            "feature_image": self.extract_image(episode),
            "custom_excerpt": self.build_excerpt(episode),
            "tags": self.extract_tags(episode),
            "meta_title": self.extract_title(episode),
            "meta_description": self.build_meta_description(episode),
        }

    def build_html_content(self, episode: RSSItem) -> str:
        """Build HTML with PRX player embed and episode content."""
        return f"""
        <div class="prx-player-container">
            <iframe
                src="https://exchange.prx.org/embed/episodes/{self.extract_prx_id(episode)}"
                width="100%"
                height="200"
                frameborder="0"
                scrolling="no">
            </iframe>
        </div>

        <div class="episode-metadata">
            <p><strong>Duration:</strong> {episode.itunes_duration or 'N/A'}</p>
        </div>

        <div class="episode-description">
            {self.sanitize_html(episode.description)}
        </div>
        """
```

**Key Design Decisions:**

1. **Template-Based** - HTML structure is configurable, not hardcoded
2. **Sanitization** - All user content is sanitized before embedding
3. **Graceful Defaults** - Missing fields have sensible defaults (not failures)
4. **PRX ID Extraction** - Multiple strategies to find embed ID (GUID parsing, link parsing)

### 4.4 Ghost Publisher Module

**Responsibility:** Create posts via Ghost Admin API

```python
class GhostPublisher:
    """Manages Ghost API interactions with retry logic."""

    def __init__(self, url: str, admin_key: str):
        self.url = url
        self.admin_key = admin_key

    def publish(self, post: GhostPost) -> GhostResult:
        """Publish post with automatic retry and duplicate detection."""

        # Check if post already exists (belt-and-suspenders)
        if self.post_exists(post.slug):
            return GhostResult(status="duplicate", post_id=existing_id)

        # Create post with retry
        for attempt in range(3):
            try:
                token = self.generate_jwt()
                response = self.api_request("POST", "/posts/", post, token)
                return GhostResult(status="created", post_id=response.id)
            except RateLimitError:
                time.sleep(2 ** attempt)  # Exponential backoff
            except AuthError:
                raise  # Don't retry auth errors

        raise PublishFailed(post.title)
```

**Key Design Decisions:**

1. **JWT Generation** - Tokens generated per-request (5-minute expiry)
2. **Duplicate Detection** - Query API before creating (GUID tracking + slug check)
3. **Retry Logic** - Exponential backoff for transient failures
4. **Non-Retriable Errors** - Auth failures fail immediately (no point retrying)

---

## 5. Data Flow and State Management

### 5.1 Normal Operation Flow

```
1. TRIGGER
   └── GitHub Actions cron (*/30 * * * *) or manual dispatch

2. INITIALIZE
   ├── Load state file (data/published_episodes.json)
   ├── Validate state schema
   └── Initialize run context (timestamp, attempt ID)

3. FETCH
   ├── Attempt primary feed fetch strategy
   ├── On failure: try fallback strategies
   └── On success: parse and validate feed structure

4. COMPARE
   ├── Extract episode GUIDs from feed
   ├── Compare against published_episodes state
   └── Identify new episodes (GUID not in state)

5. TRANSFORM (for each new episode)
   ├── Extract required fields (title, description, date)
   ├── Build HTML content with PRX player embed
   ├── Generate slug and metadata
   └── Validate transformed post structure

6. PUBLISH (for each transformed episode)
   ├── Generate Ghost API JWT
   ├── Check for duplicate via API (belt-and-suspenders)
   ├── POST to /ghost/api/admin/posts/
   └── Capture response (post ID, URL)

7. UPDATE STATE
   ├── Add published episodes to state
   ├── Update run_history with results
   └── Write state file atomically

8. COMMIT
   ├── Stage state file changes
   ├── Commit with descriptive message
   └── Push to repository

9. NOTIFY (if configured)
   ├── On success: silent (or webhook)
   └── On failure: alert via configured channel
```

### 5.2 State Consistency Guarantees

**Problem:** What if the script crashes after publishing but before committing state?

**Solution: Idempotent Operations**

```python
def publish_episode_idempotently(episode, state, ghost_client):
    """Ensure episode is published exactly once."""

    guid = episode.guid

    # Layer 1: Check local state
    if guid in state.published_episodes:
        logger.info(f"Episode {guid} in local state, skipping")
        return ExistingPost(state.published_episodes[guid])

    # Layer 2: Check Ghost API
    existing = ghost_client.find_by_slug(slugify(episode.title))
    if existing:
        logger.warning(f"Episode {guid} found in Ghost but not state, updating state")
        state.published_episodes[guid] = {
            "ghost_post_id": existing.id,
            "published_at": existing.published_at,
            "recovered": True  # Flag for debugging
        }
        return ExistingPost(existing)

    # Layer 3: Create new post
    post = transform_episode(episode)
    result = ghost_client.create(post)
    state.published_episodes[guid] = {
        "ghost_post_id": result.id,
        "published_at": result.published_at
    }
    return NewPost(result)
```

### 5.3 State Recovery Scenarios

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| Crash after Ghost publish, before state commit | State missing episode that exists in Ghost | Next run finds via API, updates state |
| Corrupt state file | JSON parse fails | Rebuild from Ghost API (manual script) |
| Missing state file | File not found | Start fresh, optionally scan Ghost for existing posts |
| Partial write | Checksum mismatch | Restore from git history |

---

## 6. Error Handling and Resilience

### 6.1 Error Classification

```python
class ErrorSeverity(Enum):
    TRANSIENT = "transient"    # Retry will likely succeed
    RECOVERABLE = "recoverable"  # Skip item, continue with others
    FATAL = "fatal"            # Stop run, alert immediately
```

| Error Type | Severity | Response |
|------------|----------|----------|
| Network timeout | TRANSIENT | Retry with backoff |
| HTTP 429 (rate limit) | TRANSIENT | Wait for Retry-After, then retry |
| HTTP 5xx (server error) | TRANSIENT | Retry with backoff |
| HTTP 403 (feed blocked) | RECOVERABLE | Try fallback strategy |
| Malformed episode data | RECOVERABLE | Log, skip episode, continue |
| HTTP 401 (auth failure) | FATAL | Stop, alert admin |
| State file corruption | FATAL | Stop, alert admin |
| Ghost API unavailable | RECOVERABLE | Queue for next run |

### 6.2 Retry Strategy

```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "initial_delay_seconds": 1,
    "max_delay_seconds": 30,
    "exponential_base": 2,
    "jitter": True  # Add randomness to prevent thundering herd
}

def retry_with_backoff(func, config=RETRY_CONFIG):
    """Execute function with exponential backoff retry."""

    for attempt in range(config["max_attempts"]):
        try:
            return func()
        except TransientError as e:
            if attempt == config["max_attempts"] - 1:
                raise  # Final attempt failed

            delay = min(
                config["initial_delay_seconds"] * (config["exponential_base"] ** attempt),
                config["max_delay_seconds"]
            )

            if config["jitter"]:
                delay *= random.uniform(0.5, 1.5)

            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
            time.sleep(delay)
```

### 6.3 Circuit Breaker Pattern

For repeated failures, implement a circuit breaker to avoid hammering failing services:

```python
class CircuitBreaker:
    """Prevents repeated calls to failing services."""

    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func):
        if self.state == "open":
            if self._should_attempt_recovery():
                self.state = "half-open"
            else:
                raise CircuitOpenError("Service unavailable")

        try:
            result = func()
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _should_attempt_recovery(self):
        return time.time() - self.last_failure_time > self.recovery_timeout
```

### 6.4 Failure Notification

```yaml
# Notification channels (priority order)
notifications:
  - type: github_issue
    trigger: consecutive_failures >= 3
    template: |
      ## PRX-to-Ghost Publisher Alert

      **Status:** {failure_count} consecutive failures
      **Last Error:** {last_error}
      **Last Success:** {last_success_time}

      ### Recent Logs
      {recent_logs}

      ### Suggested Actions
      - Check PRX feed accessibility
      - Verify Ghost API credentials
      - Review error logs

  - type: email
    trigger: fatal_error
    recipients: [admin@example.com]

  - type: healthchecks_io
    trigger: every_run
    ping_url: $HEALTHCHECK_URL
```

---

## 7. Long-Term Stability Analysis

### 7.1 External Dependency Risk Assessment

| Dependency | Change Risk | Detection | Mitigation |
|------------|-------------|-----------|------------|
| PRX RSS Feed Format | Low | Schema validation fails | Flexible parsing, alert on new fields |
| PRX Player Embed URL | Low | Visual inspection, 404s | Monitor embed health, fallback to audio link |
| Ghost Admin API | Medium | API version changes, breaking responses | Use Accept-Version header, test in staging |
| GitHub Actions | Low | Workflow syntax changes | Pin action versions, annual review |
| Python Dependencies | Medium | Security updates, breaking changes | Pin versions, Dependabot alerts |

### 7.2 Versioning Strategy

**API Versioning:**
```python
# Ghost API
GHOST_API_VERSION = "v5.0"  # Explicit version in requests
headers = {
    "Accept-Version": GHOST_API_VERSION,
    "Authorization": f"Ghost {token}"
}

# Configuration versioning
CONFIG_VERSION = "1.0"
STATE_SCHEMA_VERSION = "1.0"
```

**Dependency Pinning:**
```text
# requirements.txt - Pin major.minor, allow patch updates
feedparser>=6.0,<7.0
requests>=2.31,<3.0
PyJWT>=2.8,<3.0
python-dateutil>=2.8,<3.0
cloudscraper>=1.2,<2.0
```

### 7.3 Self-Diagnostic Capabilities

```python
def run_self_diagnostics():
    """Verify system health before processing."""

    diagnostics = {
        "feed_accessible": check_feed_accessibility(),
        "ghost_api_healthy": check_ghost_api_health(),
        "state_file_valid": validate_state_file(),
        "disk_space_ok": check_disk_space(),
        "dependencies_ok": verify_dependencies(),
    }

    if not all(diagnostics.values()):
        failed = [k for k, v in diagnostics.items() if not v]
        logger.error(f"Diagnostics failed: {failed}")
        return False

    return True
```

### 7.4 Anticipated Breaking Changes

**PRX:**
- Feed URL change → Environment variable, easy to update
- Embed format change → Template-based, single file update
- Authentication requirement → Add credentials to secrets

**Ghost:**
- API version deprecation → Update GHOST_API_VERSION constant
- Authentication method change → JWT is standard, unlikely to change
- Post schema changes → Transform module is isolated, easy to update

**GitHub:**
- Actions runner changes → Pin ubuntu version, test annually
- Secrets management changes → Follow GitHub announcements

### 7.5 Maintenance Calendar

| Frequency | Task | Owner |
|-----------|------|-------|
| Weekly | Review GitHub Actions logs for warnings | Automated check |
| Monthly | Spot-check published posts on Ghost | Manual (15 min) |
| Quarterly | Update dependencies, review Ghost API changelog | Manual (30 min) |
| Annually | Rotate Ghost API keys, full system review | Manual (1 hour) |

---

## 8. Security Considerations

### 8.1 Secrets Management

```yaml
# GitHub Secrets (repository settings)
GHOST_URL: https://yourblog.ghost.io
GHOST_ADMIN_KEY: {id}:{secret}  # Never commit!
PRX_FEED_URL: https://f.prxu.org/3329/feed-rss.xml
RSS2JSON_API_KEY: (optional)
HEALTHCHECK_URL: (optional)
```

**Key Protection:**
- Secrets only accessible to GitHub Actions
- Never logged or printed in output
- Rotate annually (or immediately if compromised)
- Use dedicated Ghost integration (not admin account)

### 8.2 Input Sanitization

```python
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'blockquote']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title']}

def sanitize_episode_content(html: str) -> str:
    """Remove potentially dangerous HTML from episode descriptions."""
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
```

### 8.3 Principle of Least Privilege

**Ghost Integration Permissions:**
- `posts:write` - Create and edit posts (required)
- `tags:write` - Create tags (optional but recommended)
- NO: `members`, `settings`, `users` access

**GitHub Actions Permissions:**
```yaml
permissions:
  contents: write  # For committing state
  issues: write    # For failure notifications (optional)
```

### 8.4 Audit Trail

Every operation is logged and committed to git:
- State file changes are git-committed
- Run history includes timestamps and outcomes
- GitHub Actions logs retained for 90 days
- Git history provides complete audit trail

---

## 9. Monitoring and Observability

### 9.1 Logging Strategy

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """JSON-formatted logging for easy parsing."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def log(self, level: str, event: str, **context):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": self.run_id,
            "level": level,
            "event": event,
            **context
        }
        self.logger.log(getattr(logging, level.upper()), json.dumps(entry))

# Usage
logger = StructuredLogger("prx-to-ghost")
logger.log("info", "episode_published",
           guid="prx:3329:episode:12345",
           ghost_id="abc123",
           duration_ms=1234)
```

### 9.2 Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `run_success_rate` | Percentage of successful runs | < 90% over 24h |
| `episodes_published` | New episodes published per run | None (informational) |
| `run_duration_seconds` | Time to complete run | > 300s |
| `feed_fetch_failures` | Failed feed retrieval attempts | > 3 consecutive |
| `ghost_api_errors` | Ghost API error responses | > 0 (immediate) |
| `state_file_size_bytes` | Size of state file | > 1MB |

### 9.3 Health Check Integration

```python
# Healthchecks.io integration
def ping_healthcheck(status: str, url: str):
    """Notify external monitoring service."""
    if not url:
        return

    endpoint = url if status == "success" else f"{url}/fail"
    try:
        requests.get(endpoint, timeout=10)
    except Exception as e:
        logger.warning(f"Healthcheck ping failed: {e}")

# In main workflow
try:
    run_publisher()
    ping_healthcheck("success", os.environ.get("HEALTHCHECK_URL"))
except Exception as e:
    ping_healthcheck("fail", os.environ.get("HEALTHCHECK_URL"))
    raise
```

### 9.4 Dashboard Recommendations

For visual monitoring, consider:

1. **GitHub Actions Insights** - Built-in, free, shows run history
2. **Healthchecks.io** - Free tier, cron monitoring, email alerts
3. **Better Uptime** - Free tier, status pages
4. **Custom Dashboard** - Optional future enhancement via Ghost API

---

## 10. Maintenance Operations

### 10.1 Common Operations Runbook

#### Force Re-publish an Episode

```bash
# 1. Remove episode from state file
# Edit data/published_episodes.json, remove the GUID entry

# 2. Delete the Ghost post (via Ghost Admin UI)

# 3. Trigger manual run
gh workflow run publish-episodes.yml
```

#### Reset State (Rebuild from Scratch)

```bash
# 1. Backup current state
cp data/published_episodes.json data/published_episodes.backup.json

# 2. Clear published episodes
echo '{"schema_version":"1.0","published_episodes":{},"run_history":[]}' > data/published_episodes.json

# 3. Commit the reset
git add data/published_episodes.json
git commit -m "chore: Reset publisher state for rebuild"

# 4. Run publisher (will re-check all episodes)
# Note: Duplicate detection via Ghost API prevents re-publishing existing posts
gh workflow run publish-episodes.yml
```

#### Recover from Corrupted State

```bash
# Option A: Restore from git history
git log --oneline data/published_episodes.json  # Find last good commit
git checkout {commit_sha} -- data/published_episodes.json

# Option B: Rebuild from Ghost API
python scripts/rebuild_state_from_ghost.py  # Script to be created
```

### 10.2 Dependency Updates

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Update dependencies
pip install --upgrade pip
pip install --upgrade -r requirements.txt

# Test locally
python scripts/publish_new_episodes.py --dry-run

# Update requirements.txt with tested versions
pip freeze > requirements.txt

# Commit
git add requirements.txt
git commit -m "chore: Update Python dependencies"
```

### 10.3 API Key Rotation

```bash
# 1. Create new Ghost integration key in Ghost Admin
# Settings > Integrations > PRX Publisher > Regenerate

# 2. Update GitHub secret
gh secret set GHOST_ADMIN_KEY

# 3. Test
gh workflow run publish-episodes.yml

# 4. Verify success in Actions log
```

---

## 11. Risk Assessment and Mitigations

### 11.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation | Contingency |
|------|------------|--------|------------|-------------|
| PRX feed becomes permanently inaccessible | Low | Critical | Multiple fetch strategies, contact PRX | Manual publish, alternative feed source |
| Ghost API introduces breaking changes | Low | High | Version pinning, quarterly review | Rapid patch via agent-driven update |
| GitHub Actions discontinues free tier | Very Low | High | Alternative platforms pre-designed | Migrate to Lambda or Fly.io |
| PRX changes embed format | Low | Medium | Template-based HTML, easy update | Quick template modification |
| State file corruption | Very Low | Medium | Git history backup, atomic writes | Rebuild from Ghost API |
| Duplicate posts created | Low | Low | GUID tracking + API check | Deduplicate script |

### 11.2 Operational Risks

| Risk | Likelihood | Impact | Mitigation | Contingency |
|------|------------|--------|------------|-------------|
| Secrets leaked | Very Low | Critical | GitHub Secrets, never in code | Rotate immediately, audit access |
| Human error in configuration | Medium | Medium | Infrastructure as code, peer review | Rollback via git |
| Knowledge loss (bus factor) | Medium | Medium | Comprehensive documentation | This design document |
| Alert fatigue | Medium | Low | Tuned thresholds, summary alerts | Weekly digest instead |

### 11.3 Business Continuity

**Single Point of Failure Analysis:**

| Component | Is SPOF? | Mitigation |
|-----------|----------|------------|
| GitHub Actions | Yes | Pre-designed alternatives (Lambda, Fly.io) |
| PRX RSS Feed | Yes | Cache last known feed, contact PRX for redundancy |
| Ghost API | Yes | Queue episodes locally, batch publish when restored |
| State File | No | Git history provides backup |
| Python Runtime | No | Version pinned, reproducible environment |

---

## 12. Implementation Roadmap

### 12.1 Phase 1: Core Implementation (Priority)

**Estimated Effort:** 6-8 hours

1. **Create core publisher script** (`scripts/publish_new_episodes.py`)
   - Feed fetcher with fallback strategies
   - State manager with atomic writes
   - Episode transformer with PRX embed
   - Ghost publisher with retry logic

2. **Create GitHub Actions workflow** (`.github/workflows/publish-episodes.yml`)
   - Cron trigger (every 30 minutes)
   - Manual dispatch option
   - Secrets configuration
   - State commit automation

3. **Initialize state file** (`data/published_episodes.json`)
   - Schema version
   - Empty published_episodes
   - Empty run_history

4. **Create requirements.txt**
   - feedparser, requests, PyJWT, python-dateutil
   - cloudscraper (fallback)
   - bleach (sanitization)

### 12.2 Phase 2: Testing & Validation

**Estimated Effort:** 2-3 hours

1. **Local testing**
   - Unit tests for transformer
   - Integration test with mock feed
   - Dry-run mode (transform without publishing)

2. **Staging deployment**
   - Test against real PRX feed
   - Publish to test Ghost instance (if available)
   - Verify PRX player functionality

3. **Production deployment**
   - Configure secrets
   - Enable workflow
   - Monitor first runs closely

### 12.3 Phase 3: Monitoring & Polish

**Estimated Effort:** 1-2 hours

1. **Set up monitoring**
   - Healthchecks.io ping
   - GitHub issue creation on failure

2. **Documentation**
   - Update README with operational instructions
   - Create troubleshooting guide
   - Document key rotation procedure

### 12.4 Phase 4: Future Enhancements (Optional)

- Transcript support (if available in feed)
- Chapter markers → post sections
- Social share image generation
- Web dashboard for monitoring

---

## 13. Ghost Theme Customization

### 13.1 Current Theme Status

The Wonder Cabinet Productions site uses a **customized Ghost theme** with the following characteristics:

| Attribute | Value |
|-----------|-------|
| **Font** | Mona Sans (GitHub's typeface - not in standard themes) |
| **Accent Color** | `#FF1A75` (pink/magenta) |
| **Hosting** | Ghost Pro (`wonder-cabinet.ghost.io`) |
| **Base Theme** | Likely customized Source or custom-built |

### 13.2 Required Theme Modifications

To support dual-podcast publishing with proper routing:

#### Homepage Template (`index.hbs`)

```handlebars
{{!-- Hero section --}}
<section class="hero">
  <h1>{{@site.title}}</h1>
  <p>{{@site.description}}</p>
</section>

{{!-- Latest from Luminous --}}
<section class="show-section luminous">
  <h2>Latest from Luminous</h2>
  <a href="/luminous/" class="view-all">View all episodes →</a>
  {{#get "posts" filter="primary_tag:luminous" limit="3" include="tags"}}
    {{#foreach posts}}
      {{> "episode-card"}}
    {{/foreach}}
  {{/get}}
</section>

{{!-- Latest from Wonder Cabinet --}}
<section class="show-section wonder-cabinet">
  <h2>Latest from Wonder Cabinet</h2>
  <a href="/wonder-cabinet/" class="view-all">View all episodes →</a>
  {{#get "posts" filter="primary_tag:wonder-cabinet" limit="3" include="tags"}}
    {{#foreach posts}}
      {{> "episode-card"}}
    {{/foreach}}
  {{/get}}
</section>
```

#### Show Landing Template (`podcast.hbs`)

Used for `/luminous/` and `/wonder-cabinet/` collection pages:

```handlebars
{{!-- Show header with branding --}}
<header class="show-header {{#match @tag.slug "luminous"}}luminous{{else}}wonder-cabinet{{/match}}">
  {{#if @tag.feature_image}}
    <img src="{{@tag.feature_image}}" alt="{{@tag.name}}" class="show-logo">
  {{/if}}
  <h1>{{@tag.name}}</h1>
  {{#if @tag.description}}
    <p class="show-description">{{@tag.description}}</p>
  {{/if}}

  {{!-- Podcast subscription links --}}
  <div class="subscribe-links">
    <a href="#" class="subscribe-btn apple">Apple Podcasts</a>
    <a href="#" class="subscribe-btn spotify">Spotify</a>
    <a href="#" class="subscribe-btn rss">RSS</a>
  </div>
</header>

{{!-- Episode listing --}}
<main class="episodes-grid">
  {{#foreach posts}}
    {{> "episode-card"}}
  {{/foreach}}
</main>

{{!-- Pagination --}}
{{pagination}}
```

#### Episode Card Partial (`partials/episode-card.hbs`)

```handlebars
<article class="episode-card {{post_class}}">
  {{#if feature_image}}
    <a href="{{url}}" class="episode-image">
      <img src="{{feature_image}}" alt="{{title}}">
    </a>
  {{/if}}
  <div class="episode-content">
    <time datetime="{{date format="YYYY-MM-DD"}}">{{date format="MMMM D, YYYY"}}</time>
    <h3><a href="{{url}}">{{title}}</a></h3>
    {{#if custom_excerpt}}
      <p>{{custom_excerpt}}</p>
    {{/if}}
  </div>
</article>
```

#### PRX Player Styling (`assets/css/prx-player.css`)

```css
/* PRX Embedded Player Container */
.prx-player-container {
  margin: 2rem 0;
  border-radius: 8px;
  overflow: hidden;
  background: var(--color-lighter-gray, #f5f5f5);
}

.prx-player-container iframe {
  display: block;
  width: 100%;
  height: 200px;
  border: none;
}

/* Dark mode support */
:root.has-light-text .prx-player-container {
  background: var(--color-darker-gray, #222);
}

/* Episode metadata block */
.episode-metadata {
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border, #e5e5e5);
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
  color: var(--color-secondary-text, #666);
}
```

### 13.3 Theme File Structure

After downloading from Ghost Admin, expected structure:

```
theme/
├── assets/
│   ├── css/
│   │   ├── screen.css          # Main styles
│   │   └── prx-player.css      # NEW: PRX player styles
│   ├── js/
│   │   └── main.js
│   └── images/
├── partials/
│   ├── episode-card.hbs        # NEW: Episode card partial
│   ├── icons/
│   └── ...
├── default.hbs                  # Base template
├── index.hbs                    # Homepage (MODIFY)
├── post.hbs                     # Single episode page
├── page.hbs                     # Static pages
├── podcast.hbs                  # NEW: Show collection template
├── tag.hbs                      # Tag archive
├── author.hbs                   # Author archive
├── package.json                 # Theme metadata
└── routes.yaml                  # NEW: Collection routing
```

### 13.4 Ghost Tag Configuration

Create these tags in Ghost Admin before automation goes live:

| Tag | Slug | Description | Feature Image |
|-----|------|-------------|---------------|
| **Luminous** | `luminous` | Show description for Luminous | Show artwork |
| **Wonder Cabinet** | `wonder-cabinet` | Show description for Wonder Cabinet | Show artwork |
| **#show-luminous** | `hash-show-luminous` | Internal routing tag | — |
| **#show-wonder-cabinet** | `hash-show-wonder-cabinet` | Internal routing tag | — |
| **Podcast** | `podcast` | General podcast content marker | — |

### 13.5 Theme Deployment Process

1. **Download current theme** from Ghost Admin
2. **Add to repository** in `theme/` directory
3. **Make modifications** (index.hbs, add podcast.hbs, etc.)
4. **Test locally** using `gscan` and Ghost local install (optional)
5. **Upload to Ghost** via Admin → Design → Upload theme
6. **Deploy routes.yaml** via Admin → Labs → Routes

---

## 14. Further Research Recommendations

Before proceeding with implementation, the following research would strengthen the design:

### 14.1 Critical Research (Blocking)

1. **PRX Feed Accessibility**
   - **Question:** Is the feed URL correct and publicly accessible?
   - **Method:** User verification via browser, contact PRX if needed
   - **Impact:** Cannot proceed without confirmed feed access

2. **PRX Player Embed Format**
   - **Question:** What is the exact embed code format for current PRX player?
   - **Method:** Inspect existing PRX-powered sites, PRX documentation
   - **Impact:** Ensures player renders correctly in Ghost posts

### 14.2 High-Value Research (Recommended)

3. **Ghost API Rate Limits**
   - **Question:** What are Ghost's API rate limits for integrations?
   - **Method:** Ghost documentation, empirical testing
   - **Impact:** Informs batch size and retry timing

4. **RSS2JSON Reliability**
   - **Question:** How reliable is RSS2JSON as a proxy service?
   - **Method:** Test with PRX feed, review uptime history
   - **Impact:** Validates primary fallback strategy

5. **PRX Feed Update Frequency**
   - **Question:** How often does PRX update the RSS feed after episode publication?
   - **Method:** Monitor feed pubDate vs. episode release times
   - **Impact:** Informs optimal polling interval

### 14.3 Nice-to-Have Research

6. **Ghost Webhook Triggers**
   - **Question:** Can we trigger automation via PRX webhook instead of polling?
   - **Method:** Review PRX Dovetail webhook documentation
   - **Impact:** Could eliminate polling, reduce latency

7. **Transcript Integration** ✅ RESOLVED
   - **Question:** Does PRX provide transcripts in the feed or via API?
   - **Finding:** PRX RSS feeds now include a `<podcast:transcript>` field, but for Luminous episodes, the canonical TTBOOK.org pages contain richer transcript content with speaker attribution.
   - **Solution:** TTBOOK.org content has been scraped and cached locally (see below).
   - **Impact:** Transcripts available for Luminous episodes; future enhancement for other shows.

### 14.4 TTBOOK.org Content Cache (Luminous Series)

**Status:** Scraped & Archived ✅
**Date:** December 10, 2025
**Reason:** TTBOOK.org website will be decommissioned; content preserved for enrichment.

**Location:** `sample-data/ttbook-cache/luminous/`

**What's Cached:**
- 18 Luminous episode pages (all episodes in the feed)
- Full transcripts with speaker attribution (e.g., `- [Steve] ...`)
- Interview segment metadata (titles and URLs)
- Raw HTML and markdown for future parsing needs
- Manifest file for easy lookup

**Matching Strategy:**
The PRX RSS feed `<link>` element contains the TTBOOK.org canonical URL. Extract the slug from the URL path to match cached files:

```
RSS: <link>https://www.ttbook.org/show/luminous-what-can-psychedelics-teach-us-about-dying</link>
                                     ↓
Cache: sample-data/ttbook-cache/luminous/luminous-what-can-psychedelics-teach-us-about-dying.json
```

**Integration Point:**
During episode transformation, check for cached TTBOOK data:
1. Parse `<link>` from RSS item
2. Extract slug from URL path
3. Look up `sample-data/ttbook-cache/luminous/{slug}.json`
4. If found, merge transcript and interview data into Ghost post

**Scraper Script:** `scripts/scrape_ttbook_luminous.py`

**Note:** This cache is critical—once TTBOOK.org goes offline, it's the only source for this enriched content

8. **Multi-Feed Architecture**
   - **Question:** If managing multiple podcasts, should state be per-feed or unified?
   - **Method:** Design review
   - **Impact:** Future scalability consideration

---

## 15. Agent-Driven Development Plan

Applying the principles from the agentic development knowledge base, here is the recommended approach for implementation:

### 15.1 Initializer + Coding Agent Pattern

Following Anthropic's recommended harness pattern:

**Initializer Agent Tasks:**
1. Create `init.sh` bootstrap script
2. Generate comprehensive `feature_list.json`
3. Set up `claude-progress.txt` tracking
4. Create initial project scaffolding

**Coding Agent Tasks (One Per Session):**
1. Implement FeedFetcher module
2. Implement StateManager module
3. Implement EpisodeTransformer module
4. Implement GhostPublisher module
5. Create GitHub Actions workflow
6. Implement error handling
7. Add monitoring/alerting
8. Write tests
9. Create documentation

### 15.2 Feature List Template

```json
{
  "features": [
    {
      "id": "F001",
      "name": "Feed fetcher with fallback strategies",
      "description": "Implement FeedFetcher class with direct, RSS2JSON, and cloudscraper strategies",
      "acceptance_criteria": [
        "Direct fetch works when feed is accessible",
        "Fallback to RSS2JSON when direct fails",
        "Proper error handling and logging"
      ],
      "status": "pending",
      "passes": false
    },
    {
      "id": "F002",
      "name": "State manager with atomic writes",
      "description": "Implement StateManager class for tracking published episodes",
      "acceptance_criteria": [
        "Load and validate state schema",
        "Atomic write (temp file + rename)",
        "Run history bounded to 100 entries"
      ],
      "status": "pending",
      "passes": false
    },
    // ... additional features
  ]
}
```

### 15.3 Session Workflow

```
Each coding session:
1. Run init.sh to set up environment
2. Read claude-progress.txt for context
3. Read feature_list.json to find next pending feature
4. Implement ONE feature
5. Write/run tests to verify
6. Update feature_list.json (passes: true if tests pass)
7. Update claude-progress.txt with session summary
8. Git commit with clear message
9. Exit with clean working tree
```

### 15.4 Guardrails for Agent Development

**Must Do:**
- Read progress log before starting work
- Work on exactly one feature per session
- Run tests before marking complete
- Commit at end of session
- Update progress log

**Must Not:**
- Remove features from feature_list.json
- Remove tests once written
- Mark feature passing without test verification
- Leave uncommitted changes
- Start new feature before completing current

### 15.5 Agent Coordination for This Project

```
[Initializer Agent]
      │
      v
┌─────────────────────────────────────────────────┐
│ 1. Create init.sh                               │
│ 2. Create feature_list.json with all features  │
│ 3. Create claude-progress.txt                   │
│ 4. Set up directory structure                   │
│ 5. Create requirements.txt                      │
└─────────────────────────────────────────────────┘
      │
      v
[Coding Agent - Session 1]
      │
      v
┌─────────────────────────────────────────────────┐
│ Feature: F001 - Feed Fetcher                    │
│ - Read progress, feature list                   │
│ - Implement feed_fetcher.py                     │
│ - Write tests                                   │
│ - Update feature passes: true                   │
│ - Commit                                        │
└─────────────────────────────────────────────────┘
      │
      v
[Coding Agent - Session 2]
      │
      v
┌─────────────────────────────────────────────────┐
│ Feature: F002 - State Manager                   │
│ - Read progress (knows F001 done)               │
│ - Implement state_manager.py                    │
│ - Write tests                                   │
│ - Update feature passes: true                   │
│ - Commit                                        │
└─────────────────────────────────────────────────┘
      │
      v
[Continue for each feature...]
      │
      v
[QA Agent - Final Verification]
      │
      v
┌─────────────────────────────────────────────────┐
│ - Run full test suite                           │
│ - Verify all features pass                      │
│ - Integration testing                           │
│ - Document any issues                           │
└─────────────────────────────────────────────────┘
```

---

## 16. Development Roadmap with Action Items

This section provides a complete sequenced roadmap showing **user action items** (things you need to do) and **agent tasks** (things Claude can implement). Dependencies are clearly marked.

### 16.1 Phase 0: Prerequisites (User Actions)

These items must be completed before development can proceed:

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| P0.1 | **Confirm PRX feed URLs are stable** | User | ⏳ Pending | Both feeds accessible; confirm they won't change |
| P0.2 | **Download current Ghost theme** | User | ⏳ Pending | Ghost Admin → Design → Advanced → Download |
| P0.3 | **Add theme to repository** | User | ⏳ Pending | Unzip to `theme/` directory, commit |
| P0.4 | **Create Ghost Admin API integration** | User | ⏳ Pending | Settings → Integrations → Add custom integration |
| P0.5 | **Note the Admin API key** | User | ⏳ Pending | Format: `{id}:{secret}` - don't commit to repo |
| P0.6 | **Create required Ghost tags** | User | ⏳ Pending | See Section 13.4 for tag list |

**Checklist for Ghost Tags to Create:**
- [ ] `luminous` - Primary tag for Luminous episodes
- [ ] `wonder-cabinet` - Primary tag for Wonder Cabinet episodes
- [ ] `#show-luminous` - Internal tag (type with # prefix)
- [ ] `#show-wonder-cabinet` - Internal tag (type with # prefix)
- [ ] `Podcast` - General content type tag

### 16.2 Phase 1: Theme Setup (Collaborative)

| # | Task | Owner | Depends On | Notes |
|---|------|-------|------------|-------|
| T1.1 | Review downloaded theme structure | Agent | P0.3 | Identify base theme, understand customizations |
| T1.2 | Create `podcast.hbs` template | Agent | T1.1 | Show landing page template |
| T1.3 | Modify `index.hbs` for dual-show homepage | Agent | T1.1 | Add sections for both shows |
| T1.4 | Create `episode-card.hbs` partial | Agent | T1.1 | Reusable episode display component |
| T1.5 | Add PRX player CSS styles | Agent | T1.1 | `prx-player.css` with dark mode support |
| T1.6 | Create `routes.yaml` | Agent | — | Collection routing configuration |
| T1.7 | **Test theme locally (optional)** | User | T1.2-T1.6 | Use `gscan` or Ghost local install |
| T1.8 | **Upload modified theme to Ghost** | User | T1.7 | Admin → Design → Upload theme |
| T1.9 | **Deploy routes.yaml** | User | T1.6 | Admin → Labs → Upload routes YAML |
| T1.10 | **Verify routing works** | User | T1.8, T1.9 | Check /luminous/ and /wonder-cabinet/ |

### 16.3 Phase 2: Publisher Core (Agent)

| # | Task | Owner | Depends On | Notes |
|---|------|-------|------------|-------|
| C2.1 | Create project structure | Agent | P0.1 | `scripts/`, `config/`, `data/` directories |
| C2.2 | Implement feed configuration (`config/feeds.py`) | Agent | C2.1 | Both feeds with metadata |
| C2.3 | Implement FeedFetcher module | Agent | C2.1 | With fallback strategies |
| C2.4 | Implement StateManager module | Agent | C2.1 | Multi-feed state tracking |
| C2.5 | Implement EpisodeTransformer module | Agent | C2.1 | RSS → Ghost post with PRX embed |
| C2.6 | Implement GhostPublisher module | Agent | C2.1 | JWT auth, retry logic |
| C2.7 | Create main orchestrator script | Agent | C2.3-C2.6 | `publish_new_episodes.py` |
| C2.8 | Add dry-run mode | Agent | C2.7 | Test without publishing |
| C2.9 | Create requirements.txt | Agent | C2.7 | Pin all dependencies |

### 16.4 Phase 3: GitHub Actions Setup (Collaborative)

| # | Task | Owner | Depends On | Notes |
|---|------|-------|------------|-------|
| G3.1 | Create workflow YAML | Agent | C2.7 | `.github/workflows/publish-episodes.yml` |
| G3.2 | Initialize state file | Agent | C2.4 | `data/published_episodes.json` |
| G3.3 | **Add secrets to GitHub repo** | User | P0.5 | `GHOST_URL`, `GHOST_ADMIN_KEY` |
| G3.4 | **Enable GitHub Actions** | User | G3.1 | If not already enabled |
| G3.5 | **Run first manual test** | User | G3.1-G3.4 | Actions → Run workflow |
| G3.6 | **Verify posts created correctly** | User | G3.5 | Check Ghost Admin for new posts |

### 16.5 Phase 4: Testing & Validation (Collaborative)

| # | Task | Owner | Depends On | Notes |
|---|------|-------|------------|-------|
| V4.1 | Create unit tests | Agent | C2.3-C2.6 | Test each module independently |
| V4.2 | Create integration test with mock | Agent | C2.7 | End-to-end without real API |
| V4.3 | **Manual end-to-end test** | User | G3.5 | Publish test episode, verify on site |
| V4.4 | **Verify PRX player works** | User | V4.3 | Audio plays correctly |
| V4.5 | **Verify routing works** | User | V4.3 | Episodes appear on correct show page |
| V4.6 | **Verify homepage displays both shows** | User | V4.3 | Latest episodes from each |
| V4.7 | Delete test posts | User | V4.6 | Clean up before go-live |

### 16.6 Phase 5: Go-Live & Monitoring (User-Led)

| # | Task | Owner | Depends On | Notes |
|---|------|-------|------------|-------|
| L5.1 | **Enable cron schedule** | User | V4.6 | Uncomment schedule in workflow |
| L5.2 | Set up Healthchecks.io (optional) | Agent | L5.1 | External monitoring |
| L5.3 | **Monitor first 24 hours** | User | L5.1 | Watch for failures |
| L5.4 | **Confirm first real episode publishes** | User | L5.1 | Wait for next episode release |
| L5.5 | Document any issues | Agent | L5.3-L5.4 | Update troubleshooting guide |

### 16.7 Complete Sequenced Timeline

```
WEEK 1: Setup & Theme
─────────────────────────────────────────────────────────────────

Day 1-2 (User)
  ├─ P0.1: Confirm feed URLs stable
  ├─ P0.2: Download Ghost theme
  ├─ P0.3: Add theme to repo
  ├─ P0.4: Create Ghost API integration
  ├─ P0.5: Save Admin API key
  └─ P0.6: Create Ghost tags

Day 2-3 (Agent, after theme in repo)
  ├─ T1.1: Review theme structure
  ├─ T1.2: Create podcast.hbs
  ├─ T1.3: Modify index.hbs
  ├─ T1.4: Create episode-card partial
  ├─ T1.5: Add PRX player CSS
  └─ T1.6: Create routes.yaml

Day 3-4 (User)
  ├─ T1.7: Test theme locally (optional)
  ├─ T1.8: Upload modified theme
  ├─ T1.9: Deploy routes.yaml
  └─ T1.10: Verify routing

WEEK 2: Publisher Implementation
─────────────────────────────────────────────────────────────────

Day 5-6 (Agent)
  ├─ C2.1-C2.6: Implement all modules
  ├─ C2.7: Create orchestrator
  ├─ C2.8: Add dry-run mode
  └─ C2.9: Create requirements.txt

Day 6-7 (Agent + User)
  ├─ G3.1: Create workflow YAML
  ├─ G3.2: Initialize state file
  ├─ G3.3: Add secrets (User)
  ├─ G3.4: Enable Actions (User)
  └─ G3.5: First manual test (User)

WEEK 3: Testing & Go-Live
─────────────────────────────────────────────────────────────────

Day 8-9 (Agent + User)
  ├─ V4.1-V4.2: Create tests
  ├─ V4.3-V4.6: Manual validation (User)
  └─ V4.7: Clean up test posts (User)

Day 10 (User)
  ├─ L5.1: Enable cron schedule
  ├─ L5.3: Monitor first 24 hours
  └─ L5.4: Confirm first real episode
```

### 16.8 Quick Reference: Your Immediate To-Dos

**This Week:**
1. ☐ Confirm both PRX feed URLs won't change
2. ☐ Download theme from Ghost Admin → Design → Advanced
3. ☐ Create a new directory `theme/` in this repo and add theme files
4. ☐ Create Ghost Admin integration (Settings → Integrations → Add)
5. ☐ Create the 5 tags in Ghost Admin (see 16.1)

**Once theme is in repo, ping me to:**
- Review theme structure
- Implement theme modifications
- Create publisher automation

**After implementation, you'll need to:**
- Upload modified theme
- Deploy routes.yaml
- Add GitHub secrets
- Run first test
- Monitor and go live

---

## Appendix A: Configuration Reference

### Environment Variables

```bash
# Required - Ghost Configuration
GHOST_URL=https://wondercabinetproductions.com
GHOST_ADMIN_KEY=id:secret

# Feed URLs (configured in code, not environment - see config/feeds.py)
# LUMINOUS_FEED_URL=https://f.prxu.org/3329/feed-rss.xml
# WONDER_CABINET_FEED_URL=https://f.prxu.org/120/ttbook

# Optional
RSS2JSON_API_KEY=your-api-key
HEALTHCHECK_URL=https://hc-ping.com/uuid
LOG_LEVEL=INFO
DRY_RUN=false
```

### Feed Configuration (config/feeds.py)

```python
FEEDS = {
    "luminous": {
        "name": "Luminous",
        "feed_url": "https://f.prxu.org/3329/feed-rss.xml",
        "ghost_primary_tag": "luminous",
        "ghost_internal_tag": "#show-luminous",
        "slug_prefix": "luminous-",
        "default_tags": ["Podcast", "Luminous"],
        "prx_series_id": "3329",
    },
    "wonder-cabinet": {
        "name": "Wonder Cabinet",
        "feed_url": "https://f.prxu.org/120/ttbook",
        "ghost_primary_tag": "wonder-cabinet",
        "ghost_internal_tag": "#show-wonder-cabinet",
        "slug_prefix": "wonder-cabinet-",
        "default_tags": ["Podcast", "Wonder Cabinet"],
        "prx_series_id": "120",
    }
}
```

### Ghost routes.yaml (Deploy to Ghost Admin > Labs > Routes)

```yaml
collections:
  /:
    permalink: /{slug}/
    template: index
  /luminous/:
    permalink: /luminous/{slug}/
    template: podcast
    filter: primary_tag:luminous
  /wonder-cabinet/:
    permalink: /wonder-cabinet/{slug}/
    template: podcast
    filter: primary_tag:wonder-cabinet

taxonomies:
  tag: /tag/{slug}/
  author: /author/{slug}/
```

### State Schema (Multi-Feed)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["schema_version", "feeds"],
  "properties": {
    "schema_version": {"type": "string", "const": "2.0"},
    "last_successful_run": {"type": "string", "format": "date-time"},
    "feeds": {
      "type": "object",
      "properties": {
        "luminous": {"$ref": "#/definitions/feed_state"},
        "wonder-cabinet": {"$ref": "#/definitions/feed_state"}
      }
    },
    "run_history": {
      "type": "array",
      "maxItems": 100,
      "items": {
        "type": "object",
        "properties": {
          "timestamp": {"type": "string", "format": "date-time"},
          "status": {"enum": ["success", "partial", "failure"]},
          "feed_results": {
            "type": "object",
            "additionalProperties": {
              "type": "object",
              "properties": {
                "status": {"type": "string"},
                "episodes_checked": {"type": "integer"},
                "episodes_published": {"type": "integer"}
              }
            }
          },
          "duration_seconds": {"type": "number"}
        }
      }
    }
  },
  "definitions": {
    "feed_state": {
      "type": "object",
      "properties": {
        "last_checked": {"type": "string", "format": "date-time"},
        "last_successful_fetch": {"type": "string", "format": "date-time"},
        "published_episodes": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "required": ["ghost_post_id", "published_at", "title"],
            "properties": {
              "ghost_post_id": {"type": "string"},
              "ghost_slug": {"type": "string"},
              "published_at": {"type": "string", "format": "date-time"},
              "title": {"type": "string"}
            }
          }
        }
      }
    }
  }
}
```

---

## Appendix B: Troubleshooting Guide

### Feed Fetch Failures

**Symptom:** `FeedFetchError: All strategies failed`

**Diagnosis:**
1. Test feed URL in browser
2. Check RSS2JSON API status
3. Review Cloudflare bypass status

**Resolution:**
1. Verify feed URL is correct
2. If 403, try different User-Agent
3. Contact PRX for whitelisting

### Ghost API Errors

**Symptom:** `GhostAPIError: 401 Unauthorized`

**Diagnosis:**
1. Check GHOST_ADMIN_KEY secret is set
2. Verify key format (id:secret)
3. Check key hasn't been rotated in Ghost Admin

**Resolution:**
1. Generate new key in Ghost Admin
2. Update GitHub secret
3. Re-run workflow

### Duplicate Posts

**Symptom:** Same episode appears multiple times on Ghost

**Diagnosis:**
1. Check state file for episode GUID
2. Check for race condition (multiple simultaneous runs)

**Resolution:**
1. Delete duplicate posts in Ghost Admin
2. Update state file to include all published GUIDs
3. Review run history for concurrent executions

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| GUID | Globally Unique Identifier - unique episode identifier from RSS feed |
| JWT | JSON Web Token - authentication token for Ghost API |
| PRX | Public Radio Exchange - podcast distribution platform |
| Dovetail | PRX's podcast publishing and analytics platform |
| Ghost | Open-source publishing platform (CMS) |
| RSS | Really Simple Syndication - feed format for podcast episodes |
| Circuit Breaker | Pattern that stops calling a failing service temporarily |
| Idempotent | Operation that produces same result regardless of how many times executed |

---

**Document Status:** Ready for Review
**Next Steps:**
1. User verification of PRX feed accessibility
2. Confirmation of Ghost instance details
3. Review and approval of this design
4. Begin agent-driven implementation following Section 12

---

*This document was generated with the assistance of Claude to ensure comprehensive coverage of design considerations, stability requirements, and maintenance operations.*
