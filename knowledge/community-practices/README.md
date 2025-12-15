# Community Discussions and Insights

This directory contains curated community discussions from Reddit, forums, and other sources that provide practical insights into agent development.

## Contents

### Executive Summaries

**reddit_discussions_summary.md**
- ClaudeCode long-range work patterns
- Orchestrator pattern convergence
- Community tooling approaches
- AI search optimization for documentation

### Raw Source Material

Located in `raw/` subdirectory:
- `reddit_claudecode_long_range_work.raw.json` (156KB) - Discussion thread on long-running agents
- `reddit_ai_searchoptimization_long_range_work.raw.json` (13KB) - Documentation structure for RAG

## Key Insights

### Orchestrator Pattern
Community independently converged on initializer + coder pattern before Anthropic formalized it:
- Separate planning from execution
- MCP-backed task databases
- Progress logs for continuity
- One task at a time focus

### Tooling Approaches
- Custom MCP servers for task state
- JSON-based local task files
- Git-based state tracking
- Integration with external trackers (Linear, Jira)

### Testing Strategies
- Playwright for browser automation
- Vitest/Jest for unit tests
- CI/CD for validation
- Manual checkpoints for complex features

### Documentation Optimization
Content structured for snippet extraction:
- Clear hierarchical headers
- Standalone section introductions
- Examples with context
- Question-answer format for FAQs

## Patterns from Community

### Spec-Kit Approach
1. Human writes comprehensive spec
2. Agent generates implementation plan
3. Agent works through plan incrementally
4. Human reviews milestones

### Taskmaster Pattern
1. Agent maintains task database
2. Tasks have dependencies and criteria
3. Agent marks done only after tests pass
4. Human can modify tasks anytime

### Checkpoint/Resume
1. Git commits as savepoints
2. Agent summarizes state at session end
3. Next session reads summary
4. JSON state for complex information

## Workspace Applications

### Validate Against Community Patterns
- Librarian workflow aligns with orchestrator pattern
- Feature development uses initializer + coder split
- Compare our approaches to community solutions

### Enhance Documentation
- Restructure for snippet retrieval
- Add clear headers to conventions
- Ensure standalone sections in CLAUDE.md files

### Build Supporting Tools
- MCP server for task management
- Browser automation for E2E testing
- Progress log aggregation

## Related Resources

- `/Users/mriechers/Developer/workspace_ops/knowledge/agents/long_running_agents_summary.md` - Official patterns
- `/Users/mriechers/Developer/workspace_ops/conventions/AGENT_COOPERATION.md` - Multi-agent standards
- `/Users/mriechers/Developer/workspace_ops/knowledge/mcp/mcp_overview.md` - MCP integration

## Adding New Content

When adding community resources:
1. Capture full discussion threads as `.raw.json` or `.raw.md`
2. Create summary extracting key patterns and insights
3. Cross-reference with official documentation
4. Note any conflicts or alternative approaches
