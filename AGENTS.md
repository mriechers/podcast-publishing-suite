# Agent Instructions

This document provides project-specific guidance for AI agents working with the PRX-to-Ghost Publisher codebase.

## Repository Purpose

**PRX-to-Ghost Publisher** is an automated publishing system that monitors PRX Dovetail RSS feeds for new podcast episodes and automatically creates posts on Ghost CMS with embedded PRX audio players. It handles multiple podcasts publishing to a single Ghost site with proper routing and organization.

**Target Podcasts:**
- **Luminous** (`https://f.prxu.org/3329/feed-rss.xml`) → `/luminous/`
- **Wonder Cabinet** (`https://f.prxu.org/120/ttbook`) → `/wonder-cabinet/`

**Ghost Site:** [Wonder Cabinet Productions](https://wondercabinetproductions.com/)

## Git Commit Convention

**IMPORTANT**: This project follows workspace-wide commit conventions with agent attribution.

**See:** `/Users/mriechers/Developer/the-lodge/conventions/COMMIT_CONVENTIONS.md`

**Quick Reference:** All AI-generated commits must include `[Agent: <name>]` after the subject line.

Example:
```
feat: Add PRX player embedding to episode transformer

[Agent: Main Assistant]

Implemented PRX audio player embedding using the episode GUID
to generate the correct embed URL. Updated transformer to include
player HTML in Ghost post content.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Project Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Trigger Layer  │───>│ Processing Core │───>│  Output Layer   │
│ - GitHub Cron   │    │ - Feed Fetcher  │    │ - Ghost Client  │
│ - Manual Invoke │    │ - State Manager │    │ - State Commit  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Platform:** GitHub Actions (every 30 minutes)
**State:** Git-tracked JSON file
**Cost:** $0/month (runs on GitHub Actions free tier)

### Core Modules

- **FeedFetcher**: Retrieves PRX RSS feeds with fallback strategies (direct access, RSS2JSON proxy, Cloudflare bypass)
- **StateManager**: Manages GUID tracking with atomic writes to prevent duplicate publishing
- **EpisodeTransformer**: Converts RSS items to Ghost post format with PRX player embedding
- **GhostPublisher**: Publishes posts to Ghost CMS using Admin API with JWT authentication

### Key Features

- **Multi-feed support** - Process multiple podcast feeds independently
- **PRX player embedding** - Embed audio players directly in Ghost posts
- **Duplicate prevention** - GUID-based tracking prevents republishing
- **Graceful degradation** - Feed isolation ensures one failure doesn't affect others
- **Zero infrastructure cost** - Runs on GitHub Actions free tier
- **Transcript enrichment** - TTBOOK.org content cached for Luminous episodes

## Development Roadmap

See `README.md` for complete development roadmap.

**Current Status:** Design Complete, Ready for Implementation

### Implementation Phases

1. **Prerequisites** - User provides PRX feed URLs, Ghost API keys, creates Ghost tags
2. **Theme Setup** - Add podcast templates, modify homepage, configure routing
3. **Publisher Core** - Implement feed fetcher, state manager, transformer, publisher
4. **Testing & Go-Live** - Test with real feeds, verify functionality, enable automation

## Python Environment Setup

**Required:** Python 3.11+

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies (when requirements.txt exists)
pip install -r requirements.txt
```

**IMPORTANT:** This project must use a virtual environment. Do not install packages to system Python.

## Environment Variables

Secrets are stored in macOS Keychain (service: `developer.workspace.<KEY_NAME>`).

**See:** `/Users/mriechers/Developer/the-lodge/conventions/SECRETS_MANAGEMENT.md`

Required secrets:
- `GHOST_URL` - Ghost site URL (https://wondercabinetproductions.com)
- `GHOST_ADMIN_KEY` - Ghost Admin API integration key
- `RSS2JSON_API_KEY` - Optional API key for RSS2JSON fallback service

**Retrieve secrets in Python:**
```python
from scripts.keychain_secrets import get_secret

ghost_url = get_secret("GHOST_URL")
ghost_key = get_secret("GHOST_ADMIN_KEY")
```

**Never commit secrets to the repository.**

## Key Documentation

| Document | Description |
|----------|-------------|
| `docs/COMPREHENSIVE_DESIGN.md` | Full system design with multi-feed architecture, Ghost routing, and implementation details |
| `docs/AUTOMATION_DESIGN.md` | Architecture options, data flow, error handling, and cost analysis |
| `docs/PRX_FEED_ACCESS_SOLUTIONS.md` | Solutions for accessing PRX feeds (RSS2JSON proxy, Cloudflare bypass) |
| `docs/GITHUB_ORG_HANDOFF.md` | Guide for transferring repository to client organization |

## Repository Structure

```
├── docs/                    # Design documents and guides
├── knowledge/               # Reference documentation and API specs
├── sample-data/             # Sample PRX feed data
│   └── ttbook-cache/        # Archived TTBOOK.org transcripts
├── scripts/                 # Automation scripts
│   └── keychain_secrets.py  # Keychain secret retrieval
├── .github/workflows/       # GitHub Actions automation
└── brainstorming/           # Planning and research notes
```

## Development Guidelines

### Code Quality Standards

- **RSS Feed Parsing**: Use `feedparser` library for robust RSS parsing
- **Ghost API**: Use official Ghost Admin API client or JWT-based requests
- **Error Handling**: Implement graceful degradation - feed failures should not stop processing
- **State Management**: Atomic writes to prevent corruption, always validate JSON before writing
- **PRX Embedding**: Use episode GUID to construct embed URLs (format documented in `docs/COMPREHENSIVE_DESIGN.md`)
- **Testing**: Include sample data in `sample-data/` for testing without live API calls

### Ghost Content Requirements

All published posts must include:
- **Title** - Episode title from RSS
- **Content** - Episode description + PRX player embed
- **Tags** - Show tag (`luminous` or `wonder-cabinet`), routing tag (`#show-<name>`), and `Podcast`
- **Custom Excerpt** - Episode summary for listing pages
- **Featured Image** - Episode artwork from RSS enclosure

### GitHub Actions Workflow

- **Trigger**: Cron schedule (every 30 minutes) + manual dispatch
- **Permissions**: Requires write access to repository for state commits
- **Secrets**: Store Ghost API key and RSS2JSON key as GitHub repository secrets
- **Notifications**: Log errors to workflow run, optionally send notifications on failure

## Common Development Commands

```bash
# Run feed fetcher (when implemented)
python scripts/fetch_feeds.py

# Test episode transformation
python scripts/test_transformer.py

# Manually trigger publication
python scripts/publish.py

# Check state file integrity
python scripts/validate_state.py
```

## Agent Collaboration

### Workspace-Standard Agents

These agents are available across all workspace projects:

- **Main Assistant** - General development, bug fixes, refactoring
- **code-reviewer** - Code review, architectural feedback, security audits
- **The Fixer** - Infrastructure setup and convention enforcement
- **The Conductor** - Multi-agent orchestration and task coordination

See `/Users/mriechers/Developer/the-lodge/conventions/AGENT_REGISTRY.md` for complete workspace agent documentation.

### Agent Registration

To register a new project-specific agent:

1. Create agent definition file in `.claude/agents/<agent-name>.md`
2. Invoke Agent Registrar via Claude Code
3. Agent Registrar will update workspace registries
4. Update this AGENTS.md file with agent documentation
5. Commit changes with agent attribution

## Git Hooks

This repository uses workspace-wide git hooks from `/Users/mriechers/Developer/the-lodge/conventions/git-hooks/`.

Configured in `.githooks/commit-msg` - delegates to workspace commit-msg hook for validation.

Enable hooks:
```bash
git config core.hooksPath .githooks
```

## Testing Strategy

### Feed Fetching Tests
- Test direct RSS access
- Test RSS2JSON fallback
- Test Cloudflare bypass strategy
- Verify feed parsing with sample data

### State Management Tests
- Test atomic write operations
- Test GUID deduplication
- Test state file corruption recovery
- Verify multi-feed isolation

### Ghost Publishing Tests
- Test JWT authentication
- Test post creation with all required fields
- Test tag assignment
- Test duplicate post prevention

### Integration Tests
- End-to-end test with sample feeds
- Verify GitHub Actions workflow
- Test error handling and logging

## Deployment

### GitHub Actions Setup

1. **Repository Secrets**: Add `GHOST_ADMIN_KEY` and `RSS2JSON_API_KEY` to repository secrets
2. **Workflow File**: Create `.github/workflows/publish-episodes.yml`
3. **State File**: Initialize empty `state.json` in repository
4. **Enable Actions**: Ensure GitHub Actions are enabled for the repository

### Ghost Theme Deployment

1. **Download Theme**: Get current theme from Ghost admin
2. **Add Templates**: Create `podcast.hbs` for show landing pages
3. **Modify Homepage**: Update `index.hbs` for dual-show display
4. **Create Routes**: Add `routes.yaml` for collection routing
5. **Upload Theme**: Deploy modified theme to Ghost
6. **Create Tags**: Ensure all required tags exist (`luminous`, `wonder-cabinet`, `#show-luminous`, `#show-wonder-cabinet`, `Podcast`)

## Troubleshooting

### Feed Access Issues
- Check PRX feed URLs are accessible
- Verify RSS2JSON API key if using fallback
- Test Cloudflare bypass if direct access fails
- Review sample data in `sample-data/` for expected feed structure

### Ghost Publishing Issues
- Verify Ghost Admin API key is valid
- Check Ghost API rate limits (Ghost Standard tier may have limits)
- Ensure required tags exist in Ghost
- Verify routes.yaml is correctly configured

### State Management Issues
- Check state.json is valid JSON
- Verify GitHub Actions has write permissions
- Review git commit history for state changes
- Ensure atomic write logic prevents corruption

## Notes for Claude Code

1. **Follow workspace conventions** - This project uses workspace-wide commit conventions, secrets management, and git hooks
2. **Use virtual environments** - Never install packages to system Python
3. **Store secrets in Keychain** - Never commit API keys or credentials
4. **Reference design documents** - The `docs/` directory contains comprehensive design specifications
5. **Test with sample data** - Use `sample-data/` for testing before live API calls
6. **Graceful degradation** - Feed failures should not crash the entire system
7. **Atomic state writes** - Prevent state corruption with proper file handling
8. **Agent attribution** - Include agent name in all AI-generated commits

## Questions and Support

- **Workspace Conventions**: `/Users/mriechers/Developer/the-lodge/conventions/`
- **Agent Registry**: `/Users/mriechers/Developer/the-lodge/conventions/AGENT_REGISTRY.md`
- **Secrets Management**: `/Users/mriechers/Developer/the-lodge/conventions/SECRETS_MANAGEMENT.md`
- **Project Design**: `docs/COMPREHENSIVE_DESIGN.md`
