# Brainstorming

This directory contains design documents, planning notes, ideation sessions, and exploratory work for the project.

## Organization

- **architecture/** - System design documents, architectural decision records (ADRs), infrastructure planning
- **features/** - Feature planning, requirements gathering, user stories, acceptance criteria
- **research/** - Research notes, technical investigations, proof-of-concept findings, competitive analysis

## Usage Patterns

### Active Work
Place active brainstorming and planning documents in the appropriate subdirectory. Use descriptive names that indicate the topic and status.

### Naming Conventions
- Use descriptive names: `oauth-integration-design.md` not `doc1.md`
- Date-prefix exploratory work: `2025-01-15-api-rate-limiting-research.md`
- Indicate status in filename if helpful: `user-auth-flow-draft.md`

### Archival
Once a brainstorming topic is implemented or decided:
- Move resolved discussions to `.archive/` within the appropriate subdirectory
- Or remove entirely if captured in code/docs
- The janitor agent can help with archival and cleanup

## Maintenance

The janitor agent maintains this directory structure:
- Keeps subdirectories organized
- Archives completed brainstorming sessions
- Prevents accumulation of outdated content
- Creates indices for large collections

Invoke the janitor when this directory needs cleanup or reorganization.
