# Claude 4 Prompting Best Practices - Executive Summary

Generated: 2025-12-02
Source: `/Users/mriechers/Developer/workspace_ops/knowledge/claude/raw/claude_4_best_practices.raw.md` (472KB)
Original URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-4-best-practices

## Key Principles

### 1. Explicit Role-Based Prompting
- Define clear roles for Claude in system prompts
- Provide specific context, expertise, and constraints
- Use role definitions to guide tone and approach

### 2. Chain-of-Thought Reasoning
- Explicitly request step-by-step thinking
- Ask Claude to show its work before providing answers
- Improves accuracy on complex reasoning tasks
- Particularly effective for math, logic, and analysis

### 3. XML Framing for Structure
- Use XML tags to organize complex prompts
- Separate instructions, context, and examples
- Helps Claude parse multi-part requests accurately
- Example: `<instructions>`, `<context>`, `<examples>`

### 4. Multishot Examples
- Provide 2-5 examples of desired input-output patterns
- Use diverse examples that cover edge cases
- Format consistently across all examples
- More effective than single-shot for complex tasks

### 5. Structured Outputs
- Request specific output formats (JSON, tables, lists)
- Define schema requirements upfront
- Use examples to demonstrate desired structure
- Enables downstream processing and validation

## Long-Context Best Practices

### Different First-Window Prompts
- First conversation turn has higher attention weight
- Place critical instructions and context in initial message
- Use subsequent messages for additional context
- Particularly important for 100K+ token contexts

### Context Compaction Strategies
- Summarize previous interactions before continuing
- Remove redundant information from conversation history
- Prioritize recent and relevant context
- Maintain key decisions and state information

## Evaluation and Iteration

### Success Criteria
- Define measurable success metrics before prompting
- Create test cases that cover expected scenarios
- Include edge cases and failure modes
- Iterate based on evaluation results

### Test-Driven Prompt Development
- Write test cases first
- Develop prompts to pass all tests
- Refine based on failure analysis
- Track performance across versions

## Agent-Specific Guidance

### For Initialization Agents
- Use first-window advantage for setup instructions
- Include comprehensive context about project goals
- Define clear handoff criteria to subsequent agents
- Establish state-tracking mechanisms (feature lists, progress logs)

### For Coding Agents
- Combine role definition with chain-of-thought
- Request structured outputs (JSON feature lists)
- Use XML to separate code, tests, and documentation sections
- Define clear success criteria for each task

### For Multi-Turn Workflows
- Implement periodic context compaction
- Maintain explicit state in structured formats
- Use consistent XML tags across sessions
- Reference prior work by timestamp or feature ID

## Common Pitfalls

1. **Vague Instructions**: Replace "improve this" with specific criteria
2. **Missing Context**: Provide all relevant background upfront
3. **Unclear Output Format**: Always specify structure explicitly
4. **No Examples**: Use multishot for non-trivial tasks
5. **Ignoring First-Window**: Don't waste initial message on pleasantries

## Workspace Applications

### Template Creation
- Bake these patterns into agent prompt templates
- Store role definitions in `/Users/mriechers/Developer/workspace_ops/conventions/`
- Create reusable XML structures for common workflows

### Documentation Standards
- Update CLAUDE.md files to reference these practices
- Include prompt engineering checklist in AGENT_ONBOARDING.md
- Maintain examples library for common task patterns

### Quality Assurance
- Evaluate agent outputs against these best practices
- Track which techniques work best for which tasks
- Iterate on prompts based on real-world performance

## References

- Full document: `raw/claude_4_best_practices.raw.md`
- Related: `agent_sdk_summary.md` - SDK implementation patterns
- Related: `claude_code_summary.md` - Claude Code-specific guidance
- Related: `/Users/mriechers/Developer/workspace_ops/knowledge/agents/long_running_agents_summary.md` - Harness design
