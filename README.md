# Generative AI Project Template

This repository is the starting point for new agent-based engagements. Launch a fresh GitHub repo from this template, then follow the Quickstart below to get Crawl4AI knowledge capture and agent scaffolding in place.

## Quickstart
1. **Create a repo from the template**  
   Use GitHub’s “Use this template” ➜ “Create a new repository.” Configure visibility, branch protections, and project metadata before anyone clones the repo.  
   → See `docs/bootstrap.md#step-1--create-a-repository-from-the-template` for launch checklist items.
2. **Clone locally and enable Crawl4AI**  
   Clone your new repo, survey the workspace, and spin up Python 3.11 tooling plus Crawl4AI/Playwright inside a dedicated virtual environment. Seed `knowledge/` using `scripts/crawl_docs.py`.  
   → Follow `docs/bootstrap.md#step-2--clone-locally-and-stand-up-crawl4ai`.
3. **Design the agent architecture**  
   Document the initial agent roles in `AGENTS.md`, capture research in `knowledge/`, and set up evaluation loops so the system can evolve safely.  
   → Reference `docs/bootstrap.md#step-3--design-the-agent-architecture` for best practices.

## Repository Highlights
- `docs/bootstrap.md` — full bootstrap guide for template adopters.
- `AGENTS.md` — living design document for the agent network and responsibilities.
- `knowledge/` — structured storage for scraped docs, metadata, and research artifacts.
- `scripts/` — utilities for Crawl4AI workflows and other automation helpers.
- `templates/` — reusable snippets and scaffolds (e.g., `templates/genai-project/`).

When you customise this template for a project, update this README with context about the engagement, environment setup, and deployment targets so new collaborators can ramp quickly.

## Co-Authors

This repository is developed collaboratively with AI assistance. Contributors are tracked via git commits following workspace conventions.

### Template Agents

| Agent | Role | Invocation |
|-------|------|------------|
| **Main Assistant** | General development, bug fixes, documentation | Primary assistant for all standard tasks |
| **code-reviewer** | Code review, architectural feedback, security audits | Invoke for quality assurance |
| **janitor** | Workspace organization and cleanup | Invoke when project needs cleanup or new workspace structure |
| **template-maintainer** | Template evolution and workspace compliance | Invoke when updating template for convention changes |
| **agent-bootstrap-guide** | Guide projects through template adoption | Invoke when helping new projects use this template |
| **crawl4ai-knowledge-harvester** | Documentation harvesting and knowledge base curation | Invoke for Crawl4AI and knowledge base tasks |

### Agent Contributions

View agent-specific contributions using git log:

```bash
# View all commits by specific agent
git log --grep="Agent: Main Assistant"
git log --grep="Agent: template-maintainer"

# View all agent-attributed commits
git log --grep="Agent:" --oneline

# Count commits by agent
git log --oneline | grep -o '\[Agent: [^]]*\]' | sort | uniq -c

# View commits from last week by agent
git log --grep="Agent: crawl4ai-knowledge-harvester" --since="1 week ago"
```

### Workspace Integration

This template follows workspace-wide conventions for agent collaboration:

- **Commit Attribution**: All AI-generated commits include `[Agent: <name>]` after the subject line
- **Agent Registry**: Template agents registered in `/Users/mriechers/Developer/workspace_ops/conventions/AGENT_REGISTRY.md`
- **Infrastructure Compliance**: Maintains Level 3 compliance with workspace requirements
- **Cross-Platform**: Agents work with Claude Code, Cursor, GitHub Copilot, and other AI tools

See [workspace conventions](../../workspace_ops/conventions/COMMIT_CONVENTIONS.md) for complete details on agent collaboration and commit standards.
