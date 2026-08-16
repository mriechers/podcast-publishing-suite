# PRX-to-Ghost Publisher

Automated publishing of podcast episodes from PRX Dovetail RSS feeds to a Ghost-powered website.

## Overview

This system monitors PRX RSS feeds for new podcast episodes and automatically creates posts on Ghost CMS with embedded PRX audio players. It handles multiple podcasts publishing to a single Ghost site with proper routing and organization.

### Target Configuration

| Podcast | Feed URL | Ghost Route |
|---------|----------|-------------|
| **Luminous** | `https://f.prxu.org/3329/feed-rss.xml` | `/luminous/` |
| **Wonder Cabinet** | `https://publicfeeds.net/f/120/wondercabinet` | `/wonder-cabinet/` |

**Ghost Site:** [Wonder Cabinet Productions](https://wondercabinetproductions.com/)

## Project Status

**Phase:** Design Complete, Ready for Implementation

The system architecture is fully designed. See the [Development Roadmap](#development-roadmap) for implementation steps.

## Key Features

- **Multi-feed support** - Process multiple podcast feeds independently
- **PRX player embedding** - Embed audio players directly in Ghost posts
- **Duplicate prevention** - GUID-based tracking prevents republishing
- **Graceful degradation** - Feed isolation ensures one failure doesn't affect others
- **Zero infrastructure cost** - Runs on GitHub Actions free tier
- **Transcript enrichment** - TTBOOK.org content cached for Luminous episodes

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Trigger Layer  │───>│ Processing Core │───>│  Output Layer   │
│ - GitHub Cron   │    │ - Feed Fetcher  │    │ - Ghost Client  │
│ - Manual Invoke │    │ - State Manager │    │ - State Commit  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Platform:** GitHub Actions (every 30 minutes)
**State:** Git-tracked JSON file
**Cost:** $0/month

## Documentation

| Document | Description |
|----------|-------------|
| [Comprehensive Design](docs/COMPREHENSIVE_DESIGN.md) | Full system design with multi-feed architecture, Ghost routing, and implementation details |
| [Automation Design](docs/AUTOMATION_DESIGN.md) | Architecture options, data flow, error handling, and cost analysis |
| [PRX Feed Access](docs/PRX_FEED_ACCESS_SOLUTIONS.md) | Solutions for accessing PRX feeds (RSS2JSON proxy, Cloudflare bypass) |
| [GitHub Org Handoff](docs/GITHUB_ORG_HANDOFF.md) | Guide for transferring repository to client organization |

## Development Roadmap

### Phase 0: Prerequisites (User Actions)
- [ ] Confirm PRX feed URLs are stable
- [ ] Download current Ghost theme
- [ ] Create Ghost Admin API integration
- [ ] Create required Ghost tags (`luminous`, `wonder-cabinet`, `#show-luminous`, `#show-wonder-cabinet`, `Podcast`)

### Phase 1: Theme Setup
- [ ] Add `podcast.hbs` template for show landing pages
- [ ] Modify `index.hbs` for dual-show homepage
- [ ] Create `routes.yaml` for collection routing
- [ ] Deploy theme and routes to Ghost

### Phase 2: Publisher Core
- [ ] Implement FeedFetcher with fallback strategies
- [ ] Implement StateManager with atomic writes
- [ ] Implement EpisodeTransformer with PRX embed
- [ ] Implement GhostPublisher with JWT auth
- [ ] Create GitHub Actions workflow

### Phase 3: Testing & Go-Live
- [ ] Test with real feeds
- [ ] Verify PRX player functionality
- [ ] Enable cron schedule
- [ ] Monitor first automated runs

## Repository Structure

```
├── docs/                    # Design documents and guides
├── knowledge/               # Reference documentation and API specs
├── sample-data/             # Sample PRX feed data
│   └── ttbook-cache/        # Archived TTBOOK.org transcripts
├── scripts/                 # Automation scripts
└── brainstorming/           # Planning and research notes
```

## Requirements

- Python 3.11+
- Ghost Admin API access
- GitHub repository with Actions enabled

## Environment Variables

```bash
GHOST_URL=https://wondercabinetproductions.com
GHOST_ADMIN_KEY=<integration-key>
RSS2JSON_API_KEY=<optional-api-key>
```

## Co-Authors

This repository is developed collaboratively with AI assistance.

| Agent | Role |
|-------|------|
| **Main Assistant** | General development and documentation |
| **code-reviewer** | Code review and architectural feedback |

All AI-generated commits include `[Agent: <name>]` attribution.
