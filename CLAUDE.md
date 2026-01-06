# CLAUDE.md

> **See [AGENTS.md](./AGENTS.md)** for complete project instructions.

This file provides Claude-specific configuration and notes for working with the PRX-to-Ghost Publisher codebase.

## Repository Purpose

**PRX-to-Ghost Publisher** is an automated publishing system that monitors PRX Dovetail RSS feeds for new podcast episodes and automatically creates posts on Ghost CMS with embedded PRX audio players.

**See AGENTS.md** for complete architecture documentation, development guidelines, and troubleshooting information.

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

## Key Project Constraints

### Python Environment
- **Required:** Python 3.11+
- **Virtual Environment Required:** Never install packages to system Python
- See AGENTS.md for setup instructions

### Secrets Management
- **Never commit secrets** - API keys stored in macOS Keychain
- **See:** `/Users/mriechers/Developer/the-lodge/conventions/SECRETS_MANAGEMENT.md`
- Required secrets: `GHOST_URL`, `GHOST_ADMIN_KEY`, `RSS2JSON_API_KEY`

### Design Documents
All implementation details are documented in `docs/`:
- `COMPREHENSIVE_DESIGN.md` - Full system design with multi-feed architecture
- `AUTOMATION_DESIGN.md` - GitHub Actions workflow and error handling
- `PRX_FEED_ACCESS_SOLUTIONS.md` - Feed access strategies
- `GITHUB_ORG_HANDOFF.md` - Client handoff guide

## Claude-Specific Notes

### Code Generation Guidelines
1. **Follow design documents** - Implementation details are in `docs/COMPREHENSIVE_DESIGN.md`
2. **Test with sample data** - Use `sample-data/` for testing before live API calls
3. **Graceful degradation** - Feed failures should not crash the entire system
4. **Atomic state writes** - Prevent state corruption with proper file handling
5. **Agent attribution** - Include agent name in all AI-generated commits

### Ghost API Integration
- Use JWT authentication (documented in `docs/COMPREHENSIVE_DESIGN.md`)
- All posts require: title, content, tags, custom excerpt, featured image
- Tags: show tag, routing tag (`#show-<name>`), and `Podcast`
- PRX player embed format documented in `COMPREHENSIVE_DESIGN.md`

### Error Handling Patterns
- Feed fetching: Try direct access, fallback to RSS2JSON, fallback to Cloudflare bypass
- State management: Validate JSON before writing, use atomic writes
- Ghost publishing: Log errors but continue processing other feeds
- See `docs/AUTOMATION_DESIGN.md` for complete error handling architecture

### Testing Before Implementation
Always reference:
1. Sample PRX feed data in `sample-data/`
2. Cached TTBOOK.org transcripts in `sample-data/ttbook-cache/`
3. Design specifications in `docs/COMPREHENSIVE_DESIGN.md`

## Project Status

**Phase:** Design Complete, Ready for Implementation

See `README.md` and `AGENTS.md` for complete development roadmap.

## Git Hooks

This repository uses workspace-wide git hooks from `/Users/mriechers/Developer/the-lodge/conventions/git-hooks/`.

Enable hooks:
```bash
git config core.hooksPath .githooks
```

## Quick Reference

**Full Documentation:** See [AGENTS.md](./AGENTS.md)

**Design Specifications:** See `docs/COMPREHENSIVE_DESIGN.md`

**Workspace Conventions:** `/Users/mriechers/Developer/the-lodge/conventions/`
