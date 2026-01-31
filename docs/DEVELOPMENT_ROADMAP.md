# PRX-to-Ghost Publisher: Development Roadmap

**Created**: 2026-01-04
**Status**: Active Development
**Orchestrated by**: The Conductor

---

## Project Overview

A Python automation tool that fetches TTBOOK podcast episodes from the PRX/Dovetail RSS feed and publishes them as posts to a Ghost CMS instance.

### Current State Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| Architecture Document | Complete | `docs/ARCHITECTURE.md` |
| Ghost Dev Instance | Running | `http://192.168.5.156:2368` |
| API Key | Configured | `.env` verified |
| Dependencies | Installed | pyjwt, requests, python-dotenv |
| Sample Data | Available | 3.5MB PRX feed in `sample-data/` |
| Implementation | Not Started | `src/` directory does not exist |

---

## Development Phases

### Phase 1: Foundation (Parallelizable)

**Goal**: Establish project structure and core modules that have no interdependencies.

| Work Package | Module | Dependencies | Agent Assignment | Priority |
|--------------|--------|--------------|------------------|----------|
| WP-1.1 | Project Structure | None | Conductor | Critical |
| WP-1.2 | `config.py` | None | Drone-A | High |
| WP-1.3 | `feed_parser.py` | None | Drone-B | High |
| WP-1.4 | `ghost_client.py` | None | Drone-C | High |

**Parallelization Strategy**: WP-1.2, WP-1.3, and WP-1.4 can run simultaneously after WP-1.1 completes (structure setup).

#### WP-1.1: Project Structure Setup
```
Create:
  src/
  ├── __init__.py
  ├── main.py (placeholder)
  ├── feed_parser.py
  ├── ghost_client.py
  ├── content_builder.py
  ├── state_tracker.py
  └── config.py
  data/
  └── .gitkeep
  tests/
  ├── __init__.py
  ├── test_feed_parser.py
  ├── test_ghost_client.py
  └── fixtures/
      └── sample_episode.xml
  pyproject.toml
  config.json
```

#### WP-1.2: Configuration Management (`config.py`)
- Load environment variables from `.env`
- Parse `config.json` for defaults
- Provide typed configuration access
- Validate required settings at startup

**Success Criteria**:
- [ ] Environment variables loaded correctly
- [ ] Config JSON parsed with defaults
- [ ] Missing required config raises clear error
- [ ] Type hints on all config properties

#### WP-1.3: Feed Parser (`feed_parser.py`)
- Fetch RSS feed from PRX URL
- Parse XML using `xml.etree.ElementTree`
- Extract episode metadata per field mapping in architecture doc
- Handle namespaces: `itunes:`, `content:`, `media:`, `podcast:`
- Return typed Episode dataclass objects

**Success Criteria**:
- [ ] Successfully fetches live feed from `https://feeds.ttbook.org/ttbook`
- [ ] Parses sample-data/prx-sample-feed.xml correctly
- [ ] Extracts all mapped fields (title, guid, pubDate, etc.)
- [ ] Handles CDATA content in description/content:encoded
- [ ] Returns list of Episode dataclass objects

#### WP-1.4: Ghost Client (`ghost_client.py`)
- Generate JWT tokens from Admin API key
- Implement POST /ghost/api/admin/posts/
- Handle authentication headers and Accept-Version
- Parse Ghost API responses
- Handle common errors (401, 422, rate limits)

**Success Criteria**:
- [ ] JWT generation matches architecture spec
- [ ] Successfully authenticates with dev Ghost instance
- [ ] Can create a test post with title and HTML
- [ ] Proper error handling for auth failures
- [ ] Returns created post ID on success

---

### Phase 2: Content Pipeline (Sequential)

**Goal**: Transform RSS data into Ghost-ready content.

| Work Package | Module | Dependencies | Agent Assignment | Priority |
|--------------|--------|--------------|------------------|----------|
| WP-2.1 | `content_builder.py` | WP-1.3 | Drone-A | High |
| WP-2.2 | `state_tracker.py` | None | Drone-B | High |

**Parallelization Strategy**: WP-2.1 and WP-2.2 can run simultaneously.

#### WP-2.1: Content Builder (`content_builder.py`)
- Generate HTML structure per architecture spec
- Build audio player embed from enclosure URL
- Map RSS categories to Ghost tags array
- Format episode duration display
- Handle featured image URLs

**HTML Output Template**:
```html
<div class="episode-player">
  <audio controls preload="metadata">
    <source src="{enclosure_url}" type="audio/mpeg">
  </audio>
  <p class="episode-duration">Duration: {itunes:duration}</p>
</div>

<div class="episode-content">
  {content:encoded}
</div>

<div class="episode-meta">
  <p><a href="{link}">Listen on TTBOOK.org</a></p>
</div>
```

**Success Criteria**:
- [ ] Generates valid HTML from Episode dataclass
- [ ] Audio player embeds correctly
- [ ] RSS categories map to Ghost tags array
- [ ] Duration formatted and displayed
- [ ] Featured image URL extracted

#### WP-2.2: State Tracker (`state_tracker.py`)
- Track published episodes by GUID
- Store Ghost post IDs for potential updates
- JSON-based storage initially (SQLite later)
- Check if episode already published
- Log publish timestamps

**Data Structure**:
```json
{
  "prx_120_guid-here": {
    "ghost_post_id": "6789abc...",
    "title": "Episode Title",
    "published_at": "2025-09-13T11:00:00Z",
    "synced_at": "2025-09-14T10:30:00Z"
  }
}
```

**Success Criteria**:
- [ ] Creates state file if not exists
- [ ] Correctly identifies unpublished episodes
- [ ] Records new publishes with timestamps
- [ ] Thread-safe file operations
- [ ] Can query by GUID

---

### Phase 3: Integration & CLI (Sequential)

**Goal**: Wire components together with a usable CLI.

| Work Package | Module | Dependencies | Agent Assignment | Priority |
|--------------|--------|--------------|------------------|----------|
| WP-3.1 | `main.py` CLI | WP-1.*, WP-2.* | Drone-A | High |
| WP-3.2 | Integration Testing | WP-3.1 | Investigator | Medium |

#### WP-3.1: CLI Entry Point (`main.py`)
- Implement `sync` command (default)
- Add `--status draft|published` flag
- Add `--dry-run` flag
- Add `--guid` for single episode sync
- Implement `list` command for state review
- Add logging with configurable verbosity

**CLI Specification**:
```bash
# Sync all new episodes as drafts (default)
python -m src.main sync

# Sync and publish immediately
python -m src.main sync --status published

# Dry run (fetch + transform, no publish)
python -m src.main sync --dry-run

# Sync specific episode
python -m src.main sync --guid "prx_120_f49f790d-..."

# List tracked episodes
python -m src.main list
```

**Success Criteria**:
- [ ] All CLI commands functional
- [ ] Dry-run mode logs but doesn't publish
- [ ] Single episode sync by GUID works
- [ ] List command shows state tracker contents
- [ ] Exit codes reflect success/failure

#### WP-3.2: Integration Testing
- Test full pipeline with sample feed
- Verify posts appear correctly in Ghost
- Test duplicate prevention
- Validate error handling paths

---

### Phase 4: Polish & Testing (Sequential)

**Goal**: Production-ready code with comprehensive tests.

| Work Package | Description | Dependencies | Agent Assignment | Priority |
|--------------|-------------|--------------|------------------|----------|
| WP-4.1 | Unit Tests | WP-1.*, WP-2.* | Drone-A | Medium |
| WP-4.2 | Error Handling | WP-3.1 | Drone-B | Medium |
| WP-4.3 | Documentation | WP-3.1 | Drone-C | Low |

---

## Agent Assignments

### Drone Agents (Implementation)

| Agent ID | Assignment | Work Packages |
|----------|------------|---------------|
| Drone-A | Config + Content | WP-1.2, WP-2.1, WP-3.1 |
| Drone-B | Feed Parser + State | WP-1.3, WP-2.2 |
| Drone-C | Ghost Client | WP-1.4 |

### Investigator Agent (Verification)
- WP-3.2: Integration testing and validation
- Verify Ghost API responses match expectations
- Validate feed parsing against sample data

### The Conductor (Orchestration)
- Project structure setup (WP-1.1)
- Coordinate handoffs between phases
- Monitor progress and unblock issues

---

## Dependency Graph

```
Phase 1 (Parallel):
┌─────────┐
│ WP-1.1  │ ← Conductor creates structure
└────┬────┘
     │
     ├──────────────┬──────────────┐
     ▼              ▼              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│ WP-1.2  │   │ WP-1.3  │   │ WP-1.4  │
│ config  │   │  feed   │   │  ghost  │
└────┬────┘   └────┬────┘   └────┬────┘
     │              │              │
     └──────────────┼──────────────┘
                    │
Phase 2 (Parallel): │
     ┌──────────────┴──────────────┐
     ▼                             ▼
┌─────────┐                  ┌─────────┐
│ WP-2.1  │                  │ WP-2.2  │
│ content │                  │  state  │
└────┬────┘                  └────┬────┘
     │                             │
     └──────────────┬──────────────┘
                    │
Phase 3 (Sequential):
                    ▼
              ┌─────────┐
              │ WP-3.1  │
              │   CLI   │
              └────┬────┘
                   │
                   ▼
              ┌─────────┐
              │ WP-3.2  │
              │  test   │
              └─────────┘
```

---

## Success Criteria (Overall)

### MVP Definition
- [ ] Fetch episodes from PRX feed
- [ ] Create Ghost posts with embedded audio player
- [ ] Prevent duplicate publishes via state tracking
- [ ] CLI with sync, list, and dry-run commands
- [ ] Basic error handling and logging

### Quality Gates

| Phase | Gate | Verification |
|-------|------|--------------|
| Phase 1 | Core modules work independently | Unit tests pass |
| Phase 2 | Content transformation correct | Manual inspection of HTML output |
| Phase 3 | End-to-end sync works | Post appears in Ghost Admin |
| Phase 4 | Production ready | All tests pass, docs complete |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| PRX feed access blocked (403) | Use local sample-data for development |
| Ghost API changes | Pin Accept-Version header to v5.0 |
| JWT token expiration | Regenerate token per request (5-min validity) |
| Rate limiting | Add configurable delay between publishes |
| Large feed (3.5MB) | Pagination and incremental sync |

---

## Execution Plan

### Immediate Actions (Phase 1)

1. **Conductor**: Create project structure (WP-1.1)
2. **Launch Parallel Agents**:
   - Drone-A: Implement `config.py` (WP-1.2)
   - Drone-B: Implement `feed_parser.py` (WP-1.3)
   - Drone-C: Implement `ghost_client.py` (WP-1.4)

### Timeline Estimate

| Phase | Duration | Notes |
|-------|----------|-------|
| Phase 1 | 30-45 min | Parallel execution |
| Phase 2 | 20-30 min | Parallel execution |
| Phase 3 | 30-45 min | Sequential, integration focus |
| Phase 4 | 45-60 min | Testing and polish |

**Total Estimated Time**: 2-3 hours

---

## References

- [Architecture Document](/Users/markriechers/Developer/ghost-dev/prx-to-ghost-publisher/docs/ARCHITECTURE.md)
- [PRX Feed Analysis](/Users/markriechers/Developer/ghost-dev/prx-to-ghost-publisher/knowledge/prx/PRX_FEED_STRUCTURE_ANALYSIS.md)
- [Ghost Admin API](/Users/markriechers/Developer/ghost-dev/prx-to-ghost-publisher/knowledge/ghost/admin-api.md)
- [Sample PRX Feed](/Users/markriechers/Developer/ghost-dev/prx-to-ghost-publisher/sample-data/prx-sample-feed.xml)
