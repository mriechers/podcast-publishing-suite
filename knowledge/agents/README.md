# Agent Design Patterns and Best Practices

This directory contains resources for building effective AI agents, with emphasis on long-running, multi-session workflows.

## Contents

### Executive Summaries

**long_running_agents_summary.md**
- Initializer + coding agent architecture
- Essential artifacts: init.sh, feature_list.json, claude-progress.txt
- Guardrails and testing strategies
- Multi-session workflow patterns

**agentic_prompting_summary.md**
- 500+ agent project examples
- Framework comparisons (LangChain, AutoGPT, CrewAI)
- Common design patterns (ReAct, Plan-Execute-Review)
- Tool integration strategies

### Notes

**notes/long_running_agents_notes.md**
- Annotated takeaways from Anthropic harness guidance
- Additional implementation reminders that complement `long_running_agents_summary.md`

### Raw Source Material

Located in `raw/` subdirectory:
- `anthropic_effective_harnesses_for_long_running_agents.raw.md` (136KB)
- `anthropic_autonomous_coding_quickstart.raw.md` (6KB)
- `ashishpatel26_500_agents.raw.md` (92KB)
- `ranthebuilder_agentic_prompting.raw.md` (24KB)
- `reddit_ai_agent_best_practices.raw.md` (40KB)

## Key Concepts

### Long-Running Agent Harness
Architecture for multi-session agent workflows:
1. **Initialization Phase**: Set up project scaffold, create artifacts
2. **Coding Phase**: Iterative feature implementation
3. **Testing Phase**: Automated E2E verification
4. **Handoff**: Clean state for next session

### Essential Artifacts
- **init.sh**: One-command environment setup
- **feature_list.json**: Work queue with pass/fail tracking
- **claude-progress.txt**: Session log and handoff notes

### Guardrails
- Read logs and feature list first
- Work one feature at a time
- Test before marking complete
- Commit at end of session
- Leave clean working tree

## Patterns and Frameworks

### Two-Agent Architecture
- **Initializer**: Planning, scaffold, initial artifacts
- **Coder**: Feature-by-feature implementation
- Clear separation of concerns
- Different prompting strategies for each

### Multi-Agent Collaboration
- Specialized agents for different tasks (QA, cleanup, release)
- Task handoff via shared state (JSON files, git commits)
- Orchestrator controls workflow
- See `/Users/mriechers/Developer/workspace_ops/conventions/AGENT_COOPERATION.md`

## Workspace Applications

### Template Creation
Create reusable templates in workspace_ops:
- `init.sh` template for new projects
- `feature_list.json` schema
- `claude-progress.txt` format guide

### Bootstrap Integration
Update `forerunner_setup.sh` to:
- Create harness artifacts for new repos
- Set up MCP browser testing
- Initialize git with proper hooks

### Convention Documentation
Document in `/Users/mriechers/Developer/workspace_ops/conventions/`:
- Harness architecture standard
- Artifact format specifications
- Testing requirements

## Testing Strategies

### End-to-End Testing
- Browser automation (Puppeteer MCP)
- Human-like user flows
- Visual verification where possible
- Regression test suite

### Verification Requirements
- Every feature needs E2E test
- Tests must pass to mark feature complete
- No premature "done" claims
- Manual verification for visual elements

## Common Pitfalls

1. **Premature Completion**: Agent claims done without finishing all features
   - Fix: Comprehensive feature list upfront with pass flags

2. **Context Loss**: Agent forgets previous work
   - Fix: Read progress log first every session

3. **Messy State**: Uncommitted changes, broken builds
   - Fix: Require clean working tree, git commit before exit

4. **Unverified Features**: Marked complete without testing
   - Fix: Mandatory E2E testing, explicit pass criteria

## Related Resources

- `/Users/mriechers/Developer/workspace_ops/knowledge/claude/agent_sdk_summary.md` - SDK implementation
- `/Users/mriechers/Developer/workspace_ops/knowledge/claude/claude_4_summary.md` - Prompting techniques
- `/Users/mriechers/Developer/workspace_ops/knowledge/community-practices/reddit_discussions_summary.md` - Community patterns
- `/Users/mriechers/Developer/workspace_ops/conventions/AGENT_COOPERATION.md` - Multi-agent collaboration

## Adding New Content

When adding agent-related resources:
1. Large files (>50KB): Place in `raw/`, create summary
2. Small files (<10KB): Place directly in this directory
3. Update this README with new content
4. Cross-reference in `/Users/mriechers/Developer/workspace_ops/knowledge/INDEX.md`
