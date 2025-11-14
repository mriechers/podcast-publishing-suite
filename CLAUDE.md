# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a template repository for bootstrapping generative AI projects. It provides scaffolding for:
- Crawl4AI-powered documentation harvesting
- Agent-based development workflows
- Knowledge base management
- Structured project initialization

## Git Commit Convention

**IMPORTANT**: This project follows workspace-wide commit conventions.

See: `/Users/mriechers/Developer/workspace_ops/conventions/COMMIT_CONVENTIONS.md`

**Quick Reference**: All AI-generated commits must include `[Agent: <name>]` after the subject line.

Example:
```
fix: Description of fix

[Agent: Main Assistant]

Details of the change...

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Template Agents

This repository defines specialized agents for template maintenance and project bootstrapping. Agent definitions are stored in `.claude/agents/`:

- **janitor**: Maintains clean directory structure and creates workspace for agents as needed
- **crawl4ai-knowledge-harvester**: Expert in Crawl4AI workflows and knowledge base curation
- **agent-bootstrap-guide**: Guides new projects through template adoption process
- **template-maintainer**: Maintains template and ensures workspace compliance

See `AGENTS.md` for complete agent documentation and collaboration patterns.

## Initial Agent Workflow

When first working in a project derived from this template:
1. **Invoke agent-bootstrap-guide** to guide through the setup process, OR:
2. Ask the repository owner to clarify the project's purpose and which documentation needs to be collected
3. Use Crawl4AI via `scripts/crawl_docs.py` to harvest requested documentation sources (or invoke crawl4ai-knowledge-harvester)
4. Save gathered references in `knowledge/` with clear source attribution
5. Document the knowledge update strategy (cadence, tooling, ownership) in the project README
6. Stage and commit the onboarding work; ask owner to configure remote if needed

## Python Environment Setup

**Required for Crawl4AI**: Python 3.11

```bash
# Create dedicated virtual environment
python3.11 -m venv .venv-crawl4ai
source .venv-crawl4ai/bin/activate

# Install dependencies
python3.11 -m pip install crawl4ai
python3.11 -m playwright install chromium
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

### Core Structure

```
.
├── AGENTS.md              # Agent architecture design document
├── docs/
│   └── bootstrap.md       # Detailed setup guide for template adopters
├── knowledge/             # Documentation snapshots and metadata
│   └── sources.json       # Crawler source definitions
├── scripts/
│   └── crawl_docs.py      # Interactive Crawl4AI harvester
└── templates/
    └── genai-project/     # Reusable project scaffold
```

### Key Files

- **AGENTS.md**: Living design document describing agent roles, responsibilities, and coordination patterns. Update this when defining new agent architectures.
- **docs/bootstrap.md**: Three-step bootstrap process (create repo, setup Crawl4AI, design agents). Reference when initializing new projects.
- **scripts/crawl_docs.py**: Async crawler with interactive CLI. Supports filtering by category/slug, dry-run mode, and incremental updates.
- **templates/genai-project/**: Copy-ready scaffold with knowledge/, scripts/, and configuration files for new projects.

### Knowledge Management

The `knowledge/` directory stores structured documentation:
- Organized by category (e.g., `knowledge/alfredapp/`, `knowledge/toggl/`)
- Each source has three files: `.md`, `.html`, `.json`
- `sources.json` maintains the authoritative source list
- Commit snapshots to version control for research trail preservation

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

## Templates Usage

The `templates/genai-project/` directory is a copy-ready scaffold:
```bash
cp -R templates/genai-project ~/Projects/new-project
cd ~/Projects/new-project
# Follow BOOTSTRAP.md in copied directory
```

Contains:
- Knowledge directory structure
- Copy of `scripts/crawl_docs.py`
- `.gitignore` for Python virtual environments
- `BOOTSTRAP.md` quickstart guide
- `README.md` template with Co-Authors section

## Agent Architecture Considerations

When documenting agents in `AGENTS.md`:
- Define clear role boundaries and responsibilities
- Document inter-agent communication patterns
- Establish evaluation and testing strategies
- Keep API credentials in `.env` (never commit), use `.env.example` for templates
- Plan for agent evolution (baseline metrics, regression tests)

## Documentation Maintenance

- Keep `knowledge/` snapshots current by re-running crawler periodically
- Update `AGENTS.md` when agent topology changes
- Document any new automation scripts in this file
- When customizing for a specific project, replace this template README with project-specific context
