# Ghost Documentation Update Plan

## Overview

This document outlines the strategy for maintaining up-to-date Ghost platform documentation in the `knowledge/ghost/` directory of this project.

## Documentation Source

**Primary Source:** TryGhost/Docs GitHub Repository
**URL:** https://github.com/TryGhost/Docs
**Format:** MDX (Markdown with JSX)
**License:** MIT

## Current Documentation Coverage

The following Ghost documentation has been captured (as of 2025-11-14):

### Core Documentation
- `introduction.md` - Ghost platform introduction and overview
- `admin-api.md` - Complete Admin API reference for creating/updating content
- `content-api.md` - Content API overview for reading published content
- `webhooks.md` - Webhook configuration for event-driven automation
- `publishing.md` - Publishing workflows and content management
- `members.md` - Members and subscription functionality
- `newsletters.md` - Newsletter features and configuration
- `content-api-posts.md` - Detailed posts endpoint documentation

### Why These Files?

For the PRX-to-Ghost automation project, these docs provide:
1. **Admin API** - Required for creating new posts programmatically
2. **Posts endpoint** - Specific details on post structure, fields, and formats
3. **Webhooks** - Potential trigger mechanism for automation
4. **Publishing** - Understanding Ghost's publishing workflow
5. **Content API** - Reading existing posts to avoid duplicates

## Update Strategy

### Update Frequency

**Recommended:** Quarterly (every 3 months)

**Rationale:**
- Ghost has a stable, mature API
- Major breaking changes are infrequent
- API versioning protects against unexpected changes
- Quarterly updates balance freshness with effort

### Update Triggers

Update documentation immediately when:
1. **Ghost announces a major version release** (e.g., Ghost 6.0)
2. **Admin API version changes** affecting post creation
3. **Project encounters API errors** suggesting documentation drift
4. **New Ghost features** are needed for the automation (e.g., new post fields)

### Update Process

#### Automated Update (Preferred)

```bash
# From project root
python3.11 scripts/fetch_ghost_docs_from_github.py
```

This script:
- Fetches latest MDX files from TryGhost/Docs main branch
- Saves markdown to `knowledge/ghost/`
- Updates `knowledge/sources.json` with metadata
- Records retrieval timestamp

#### Verification Steps

After running the update script:

1. **Check for breaking changes:**
   ```bash
   git diff knowledge/ghost/admin-api.md
   git diff knowledge/ghost/content-api.md
   ```

2. **Review authentication changes:**
   ```bash
   grep -i "authentication\|jwt\|token" knowledge/ghost/admin-api.md
   ```

3. **Check posts endpoint changes:**
   ```bash
   grep -i "POST /posts\|PUT /posts" knowledge/ghost/admin-api.md
   ```

4. **Verify embed/player support:**
   ```bash
   grep -i "embed\|html\|iframe" knowledge/ghost/admin-api.md
   ```

#### Manual Verification

If significant changes are detected:

1. Visit https://docs.ghost.org/admin-api
2. Compare with local `knowledge/ghost/admin-api.md`
3. Check the TryGhost/Docs commit history for API changes
4. Test automation against any documented changes

### Monitoring for Updates

**Primary Method:** GitHub Watch

1. Watch the TryGhost/Docs repository
2. Set notifications for "Releases only" or "All activity"
3. Review commits to `admin-api.mdx` and `content-api.mdx`

**Secondary Method:** Ghost Changelog

- URL: https://ghost.org/changelog
- Review for API-related changes
- RSS feed available: https://ghost.org/changelog/rss/

### Version Tracking

Each documentation snapshot includes:
- `retrieved_at` timestamp in JSON metadata files
- Git commit tracking document changes
- Source URL in metadata pointing to specific GitHub content

Example metadata (`knowledge/ghost/admin-api.json`):
```json
{
  "url": "https://raw.githubusercontent.com/TryGhost/Docs/main/admin-api.mdx",
  "slug": "admin-api",
  "category": "ghost",
  "retrieved_at": "2025-11-14T03:35:00.000Z",
  "notes": "Admin API overview and reference",
  "source": "GitHub TryGhost/Docs repository",
  "content_length": 19370
}
```

## Ownership

**Primary Owner:** Project maintainer
**Update Responsibility:** Developer updating automation code
**Review Cadence:** During quarterly dependency updates

## Tooling

### Current Tools

1. **fetch_ghost_docs_from_github.py** - Automated doc fetcher
   - Python 3.11 required
   - No external dependencies (uses stdlib urllib)
   - Fetches from GitHub raw content URLs

2. **sources.json** - Source of truth for documentation inventory
   - Located at `knowledge/sources.json`
   - Lists all fetched documentation files
   - Includes URLs and metadata

### Future Enhancements

Potential improvements:

1. **Automated Update Check**
   - GitHub Action to check for doc changes weekly
   - Opens PR when changes detected
   - Includes diff summary in PR description

2. **API Version Pinning**
   - Track which Ghost API version the automation targets
   - Alert when documentation updates suggest version bump
   - Maintain compatibility matrix

3. **Change Impact Analysis**
   - Script to analyze doc diffs
   - Highlight fields used by automation
   - Flag breaking changes automatically

## Documentation Standards

When updating Ghost documentation:

1. **Preserve Original Format** - Keep MDX as-is when possible
2. **Include Metadata** - Always update JSON metadata files
3. **Commit Message Convention** - Use `docs: update Ghost API documentation (YYYY-MM-DD)`
4. **Git History** - Separate commits for each documentation update
5. **Testing** - Run automation tests after major doc updates

## Fallback Strategy

If GitHub repository becomes unavailable:

1. **Primary Fallback:** https://docs.ghost.org (official docs site)
2. **Secondary Fallback:** Cached copies in git history
3. **Tertiary Fallback:** Ghost source code (`@tryghost/admin-api` npm package)

## Related Documentation

- [Ghost API Versioning](https://ghost.org/docs/faq/api-versioning/)
- [Ghost Changelog](https://ghost.org/changelog)
- [TryGhost/Docs Repository](https://github.com/TryGhost/Docs)
- [Ghost API Demo Scripts](https://github.com/TryGhost/api-demos)

## Update Log

| Date | Updated By | Ghost Version | Changes |
|------|-----------|---------------|---------|
| 2025-11-14 | Claude (Initial) | 5.x | Initial documentation capture from TryGhost/Docs |

---

**Last Updated:** 2025-11-14
**Next Review:** 2025-02-14 (3 months)
