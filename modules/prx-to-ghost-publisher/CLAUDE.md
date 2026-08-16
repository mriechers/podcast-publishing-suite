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
feat: Add PRX API authentication handler

[Agent: Main Assistant]

Implement OAuth flow for PRX API access with token refresh logic.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Project Bootstrap Workflow

When starting work on this project, follow these steps:

### Phase 1: Knowledge Capture
1. **Harvest PRX API documentation**
   ```bash
   python3.11 scripts/crawl_docs.py --init
   # Add: https://www.prx.org/api-docs (or relevant PRX developer docs)
   ```

2. **Harvest Ghost API documentation**
   ```bash
   python3.11 scripts/crawl_docs.py --append
   # Add: https://ghost.org/docs/admin-api/
   # Add: https://ghost.org/docs/content-api/
   ```

3. **Save documentation snapshots** to `knowledge/prx/` and `knowledge/ghost/`

4. **Document update strategy** - Define how often to refresh docs (monthly? quarterly?)

### Phase 2: Architecture Design
1. Review harvested documentation in `knowledge/`
2. Design data transformation pipeline (PRX format → Ghost format)
3. Define authentication/authorization requirements for both APIs
4. Plan error handling and retry logic
5. Document architecture decisions in `docs/architecture/`

### Phase 3: Implementation
1. Set up development environment with required SDKs/libraries
2. Implement PRX API client
3. Implement Ghost API client
4. Build content transformation layer
5. Create publishing orchestration logic
6. Add testing and validation

### Phase 4: Deployment
1. Define deployment target (serverless function? scheduled job? web service?)
2. Set up CI/CD pipeline
3. Configure secrets management for API credentials
4. Implement monitoring and alerting

## Available Agents

This repository includes specialized agents for different aspects of development:

### Template Agents (in `.claude/agents/`)
- **janitor**: Maintains clean directory structure and creates workspace for agents as needed
- **crawl4ai-knowledge-harvester**: Expert in Crawl4AI workflows and knowledge base curation
- **agent-bootstrap-guide**: Guides new projects through template adoption process
- **template-maintainer**: Maintains template and ensures workspace compliance

### Workspace-Standard Agents
- **Main Assistant**: General development, bug fixes, documentation
- **code-reviewer**: Code review, architectural feedback, security audits
- **librarian**: Repository health monitoring

See `AGENTS.md` for complete agent documentation and collaboration patterns.

## Python Environment Setup

**Required for Crawl4AI**: Python 3.11

```bash
# Create dedicated virtual environment
python3.11 -m venv .venv-crawl4ai
source .venv-crawl4ai/bin/activate

# Install Crawl4AI dependencies
python3.11 -m pip install crawl4ai
python3.11 -m playwright install chromium
```

**For project development**, you'll likely need additional dependencies:
```bash
# Create project virtual environment (Python 3.11+)
python3.11 -m venv .venv
source .venv/bin/activate

# Install project dependencies (once requirements.txt is created)
pip install -r requirements.txt
```

## Common Development Commands

### Knowledge Capture (Crawl4AI)

```bash
# Interactive setup - define initial sources
python3.11 scripts/crawl_docs.py --init

# Append additional sources
python3.11 scripts/crawl_docs.py --append

# Re-crawl specific source by slug
python3.11 scripts/crawl_docs.py --slug <slug-name>

# Re-crawl specific category
python3.11 scripts/crawl_docs.py --category <category-name>

# Dry run (fetch without writing)
python3.11 scripts/crawl_docs.py --dry-run

# Default run (crawl all sources)
python3.11 scripts/crawl_docs.py
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

### Current Structure

```
.
├── .claude/
│   └── agents/                # Specialized agent definitions
├── .githooks/
│   └── commit-msg             # Workspace-wide commit convention enforcement
├── artifacts/                 # Generated content (exports, reports, diagrams)
│   ├── diagrams/
│   ├── exports/
│   └── reports/
├── brainstorming/             # Planning and research documents
│   ├── architecture/          # Architecture decision records
│   ├── features/              # Feature specifications
│   └── research/              # Background research
├── docs/
│   └── bootstrap.md           # Template adoption guide
├── knowledge/                 # Documentation snapshots and metadata
│   └── sources.json           # Crawler source definitions
├── scripts/
│   └── crawl_docs.py          # Interactive Crawl4AI harvester
├── templates/
│   └── genai-project/         # Reusable project scaffold
├── AGENTS.md                  # Agent architecture documentation
├── CLAUDE.md                  # This file - project guidance for AI assistants
├── CONVENTIONS_ANALYSIS.md   # Workspace compliance report
└── README.md                  # Project overview
```

### Planned Structure (as project develops)

```
src/                           # Source code for PRX-to-Ghost publisher
├── prx/
│   ├── client.py              # PRX API client
│   └── models.py              # PRX data models
├── ghost/
│   ├── client.py              # Ghost API client
│   └── models.py              # Ghost data models
├── transformer/
│   └── content.py             # PRX → Ghost content transformation
└── publisher/
    └── orchestrator.py        # Publishing orchestration logic

tests/                         # Test suite
├── unit/
├── integration/
└── fixtures/

config/                        # Configuration files
├── .env.example               # Template for environment variables
└── settings.py                # Application settings

scripts/                       # Utility scripts
├── crawl_docs.py              # Documentation harvester
└── publish.py                 # CLI for manual publishing
```

### Key Files

- **AGENTS.md**: Living design document describing agent roles, responsibilities, and coordination patterns. Update this when defining new agent architectures or project-specific agents.
- **docs/bootstrap.md**: Three-step bootstrap process (create repo, setup Crawl4AI, design agents). Reference when initializing new projects.
- **scripts/crawl_docs.py**: Async crawler with interactive CLI. Supports filtering by category/slug, dry-run mode, and incremental updates.
- **knowledge/**: Stores PRX and Ghost API documentation, transformation specs, and other reference materials.
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

The `knowledge/` directory stores structured documentation:
- Organized by category (e.g., `knowledge/prx/`, `knowledge/ghost/`)
- Each source has three files: `.md`, `.html`, `.json`
- `sources.json` maintains the authoritative source list
- Commit snapshots to version control for research trail preservation

**Recommended categories for this project**:
- `prx` - PRX API documentation, authentication guides, data schemas
- `ghost` - Ghost API documentation, content structure, admin API guides
- `integration` - Third-party integration guides, authentication patterns
- `deployment` - Hosting documentation, serverless platform guides

### Git Hooks
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

### Error Handling

- Failed crawls are reported but don't stop batch processing
- Exit code 1 if any source failed, 0 if all succeeded
- Dry-run mode fetches but skips file writes

## Project-Specific Guidance

### Security Considerations

**CRITICAL**: This project will handle API credentials for both PRX and Ghost platforms.

- Store API keys, tokens, and secrets in `.env` files (NEVER commit these)
- Use `.env.example` to document required environment variables
- Implement proper secret rotation strategies
- Use environment-specific credentials (dev/staging/prod)
- Follow OAuth best practices for PRX authentication
- Use Ghost Admin API keys with minimal required permissions

### API Rate Limiting

Both PRX and Ghost APIs likely have rate limits:
- Implement exponential backoff for retry logic
- Add request throttling to stay within limits
- Cache responses where appropriate
- Log rate limit encounters for monitoring

### Content Transformation Strategy

When transforming PRX content to Ghost format:
- Preserve metadata (author, publish date, categories/tags)
- Convert audio embeds to Ghost-compatible format
- Handle markdown/HTML content appropriately
- Map PRX content types to Ghost post types
- Implement validation before publishing

### Testing Strategy

- **Unit tests**: Individual API clients, transformers
- **Integration tests**: End-to-end publishing flow with test accounts
- **Fixtures**: Sample PRX responses for repeatable tests
- **Mocking**: Mock external API calls for fast, reliable tests
- **Validation**: Verify published content matches source

## Agent Collaboration Patterns

When working on this project:

1. **Use janitor** for workspace organization and directory structure maintenance
2. **Use crawl4ai-knowledge-harvester** when updating API documentation
3. **Use code-reviewer** before committing significant features
4. **Use Main Assistant** for general development tasks

Document new project-specific agents in `AGENTS.md` if specialized behavior is needed (e.g., a dedicated "prx-transformer-specialist").

## Development Workflow

### First-Time Setup
1. Invoke **agent-bootstrap-guide** OR manually harvest documentation
2. Review `knowledge/` to understand PRX and Ghost APIs
3. Create development plan in `brainstorming/architecture/`
4. Set up Python environment and install dependencies

### Feature Development
1. Create feature branch from main
2. Document feature in `brainstorming/features/`
3. Implement with tests
4. Run code-reviewer agent
5. Commit with proper attribution
6. Push to feature branch
7. Create pull request

### Documentation Updates
1. Run `python3.11 scripts/crawl_docs.py --category prx` (or ghost)
2. Review changes to ensure documentation is current
3. Commit updated knowledge base

## Next Steps

**To move this project from bootstrap to implementation**:

1. **Define exact requirements**:
   - Which PRX content needs to be published?
   - What Ghost site(s) are the target?
   - What's the publishing frequency/trigger?
   - What transformations are needed?

2. **Harvest documentation**:
   ```bash
   python3.11 scripts/crawl_docs.py --init
   # Add PRX and Ghost API documentation URLs
   ```

3. **Create technical design**:
   - Document in `docs/architecture/`
   - Define data models
   - Design API integration patterns
   - Plan error handling and monitoring

4. **Set up development environment**:
   - Create `requirements.txt` with needed libraries
   - Set up `.env.example` with required credentials
   - Create basic project structure in `src/`

5. **Implement core features**:
   - PRX API client
   - Ghost API client
   - Content transformer
   - Publishing orchestrator
   - Testing suite

6. **Deploy and monitor**:
   - Choose deployment platform
   - Set up CI/CD
   - Implement logging and monitoring
   - Document operational runbook

## Templates Usage

The `templates/genai-project/` directory contains the original template scaffold. You can use this to create additional related projects or reference the original template structure.
Enable hooks:
```bash
git config core.hooksPath .githooks
```

## Quick Reference

**Full Documentation:** See [AGENTS.md](./AGENTS.md)

**Design Specifications:** See `docs/COMPREHENSIVE_DESIGN.md`

- Keep `knowledge/` snapshots current by re-running crawler periodically (monthly recommended)
- Update `AGENTS.md` when agent topology changes
- Document any new automation scripts in this file
- Update README.md with project-specific context once implementation begins
- Keep architecture docs in `docs/architecture/` synchronized with implementation
**Workspace Conventions:** `/Users/mriechers/Developer/the-lodge/conventions/`
