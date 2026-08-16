# Claude-Specific Documentation

This directory contains official Anthropic documentation and best practices for Claude models, Claude Code, and the Agent SDK.

## Contents

### Executive Summaries

**claude_4_summary.md**
- Prompting best practices for Claude 4
- Chain-of-thought reasoning
- XML framing and structured outputs
- Long-context strategies
- Evaluation and testing

**claude_code_summary.md**
- Tool usage patterns (Read, Edit, Write, Grep, Glob)
- Git integration and commit conventions
- Code editing best practices
- Project navigation strategies

**agent_sdk_summary.md**
- Event-driven agent architecture
- Session management and compaction
- MCP integration
- Cost tracking and budgeting
- Hosting and deployment

### Raw Source Material

Located in `raw/` subdirectory:
- `claude_4_best_practices.raw.md` (472KB) - Comprehensive prompting guide
- `anthropic_claude_code_best_practices.raw.md` (36KB) - Claude Code workflows
- `anthropic_agent_sdk_overview.raw.md` (332KB) - SDK reference documentation

## Key Concepts

### Prompting Techniques
1. **Role-Based Prompting**: Define clear roles and context
2. **Chain-of-Thought**: Request explicit reasoning steps
3. **XML Framing**: Structure complex prompts with tags
4. **Multishot Examples**: Provide 2-5 diverse examples
5. **Structured Outputs**: Specify JSON/table formats

### Long-Context Best Practices
- **First-Window Advantage**: Critical info in initial message
- **Context Compaction**: Summarize before running out of space
- **Structured State**: Maintain explicit state in JSON
- **Progressive Refinement**: Build up context across turns

### Tool Usage (Claude Code)
- **Read First**: Always read files before editing
- **Prefer Tools**: Use Read/Edit/Grep, not bash commands
- **Test Often**: Run tests after each change
- **Commit Frequently**: Small, focused commits

### Agent SDK Architecture
- **Event-Driven**: System events vs. user events
- **Session State**: Persistent conversation context
- **MCP Integration**: Automatic tool discovery from MCP servers
- **Cost Tracking**: Monitor usage and set budgets

## Workspace Applications

### Prompt Engineering Standards
Update workspace conventions to include:
- Role definitions for specialized agents
- XML tag standards for structured prompts
- Example libraries for common tasks
- Evaluation criteria templates

### Claude Code Workflows
Standardize tool usage across projects:
- Always read CLAUDE.md first
- Use absolute paths for file references
- Include agent attribution in commits
- Test before committing

### Agent SDK Integration
Align workspace tooling with SDK:
- MCP server registration standards
- Session state management patterns
- Cost logging and reporting
- Deployment configurations

## Best Practices by Use Case

### For Initialization Agents
- Use first-window advantage for setup context
- Create comprehensive project scaffolds
- Define clear handoff criteria
- Establish state-tracking artifacts

### For Coding Agents
- Read files before editing (never assume)
- Work in small, testable increments
- Update progress logs regularly
- Leave clean working tree

### For Review Agents
- Read full context before commenting
- Suggest specific, testable improvements
- Verify suggestions would work
- Test before recommending

### For Orchestrator Agents
- Maintain explicit task state (JSON)
- Control task assignment carefully
- Monitor sub-agent progress
- Handle errors gracefully

## Common Pitfalls

1. **Editing Without Reading**: Causes indentation errors and broken code
2. **Relative Paths**: Break when working directory changes
3. **Skipping Tests**: Leads to undetected regressions
4. **Vague Prompts**: Results in generic or off-target responses
5. **Ignoring First-Window**: Wastes high-attention context slot

## Testing and Validation

### Prompt Testing
- Define success criteria upfront
- Create test cases covering edge cases
- Iterate based on failures
- Track performance across versions

### Code Testing
- Unit tests for logic
- Integration tests for workflows
- E2E tests for user scenarios
- Manual verification for visuals

## Related Resources

- `/Users/mriechers/Developer/workspace_ops/knowledge/agents/long_running_agents_summary.md` - Harness patterns
- `/Users/mriechers/Developer/workspace_ops/knowledge/mcp/mcp_overview.md` - MCP protocol
- `/Users/mriechers/Developer/workspace_ops/conventions/COMMIT_CONVENTIONS.md` - Git conventions
- `/Users/mriechers/Developer/workspace_ops/conventions/AGENT_REGISTRY.md` - Agent catalog

## Adding New Content

When adding Claude-related documentation:
1. Official Anthropic docs: Place raw in `raw/`, create summary if >50KB
2. Community resources: Consider if belongs in `/community/` instead
3. Cross-reference with agent patterns in `/agents/`
4. Update this README and main INDEX.md
