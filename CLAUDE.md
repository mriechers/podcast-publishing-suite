# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

**Project**: PRX to Ghost Publisher
**Status**: Bootstrap Phase - Template scaffolding in place, core functionality not yet implemented

This project aims to build a publishing pipeline that:
- Fetches content from PRX (Public Radio Exchange) platform
- Transforms/adapts content for Ghost CMS format
- Publishes to Ghost via API
- Manages content lifecycle and updates

**Current State**: This is a fresh instance of a generative AI project template. The repository contains scaffolding for agent-based development and documentation harvesting, but **no PRX or Ghost integration has been implemented yet**.

### What is PRX?
Public Radio Exchange (prx.org) is a public media distribution platform that enables producers to distribute and monetize their audio content to radio stations and digital platforms.

### What is Ghost?
Ghost (ghost.org) is a modern open-source headless CMS and publishing platform, commonly used for blogs, newsletters, and content-driven websites with robust API capabilities.

## Git Commit Convention

**IMPORTANT**: This project follows workspace-wide commit conventions.

See: `/Users/mriechers/Developer/workspace_ops/conventions/COMMIT_CONVENTIONS.md`

**Quick Reference**: All AI-generated commits must include `[Agent: <name>]` after the subject line.

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
```

The crawler writes outputs to `knowledge/<category>/`:
- `<slug>.md` - Markdown conversion
- `<slug>.html` - Raw HTML
- `<slug>.json` - Metadata (URL, timestamp, status)

Source definitions are stored in `knowledge/sources.json`.

## Repository Architecture

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

### Knowledge Management

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

The repository uses workspace-wide git hooks from `/Users/mriechers/Developer/workspace_ops/conventions/git-hooks/`.

Configured in `.githooks/commit-msg` - delegates to workspace commit-msg hook for enforcement.

## Crawl4AI Script Details

The `scripts/crawl_docs.py` script:
- Requires Python 3.11 shebang (`#!/usr/bin/env python3.11`)
- Uses `AsyncWebCrawler` from crawl4ai package
- Supports multiple operational modes via CLI flags
- Validates source structure (requires `category`, `slug`, `url`)
- Generates slugs from URLs if not provided
- Writes three artifacts per source (HTML, Markdown, JSON metadata)
- Includes timestamp and status tracking in metadata

### Interactive Prompts

When run with `--init` or `--append`:
- Prompts for: category, URL, slug (with auto-generated default), notes
- Leave category blank to finish input loop
- Sources are immediately saved to `knowledge/sources.json`

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

## Documentation Maintenance

- Keep `knowledge/` snapshots current by re-running crawler periodically (monthly recommended)
- Update `AGENTS.md` when agent topology changes
- Document any new automation scripts in this file
- Update README.md with project-specific context once implementation begins
- Keep architecture docs in `docs/architecture/` synchronized with implementation
