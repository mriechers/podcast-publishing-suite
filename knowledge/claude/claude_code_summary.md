# Claude Code Best Practices - Executive Summary

Generated: 2025-12-02
Source: `/Users/mriechers/Developer/workspace_ops/knowledge/claude/raw/anthropic_claude_code_best_practices.raw.md` (36KB)
Original URL: https://www.anthropic.com/engineering/claude-code-best-practices

## Core Principles

### 1. Explicit File Context
- Always specify which files you're referring to
- Use absolute paths, not relative references
- Read files before editing to understand context
- Verify changes after editing

### 2. Tool Usage Patterns
- Prefer Read over cat commands
- Use Edit for targeted changes, Write for new files
- Leverage Grep for code search, not bash grep
- Use Glob for file discovery

### 3. Git Integration
- Create meaningful commit messages
- Include agent attribution: `[Agent: <name>]`
- Review changes with git diff before committing
- Keep commits atomic and focused

### 4. Error Recovery
- Read error messages carefully
- Check file paths and permissions
- Verify syntax before running code
- Test incrementally, not all at once

## Code Editing Best Practices

### When to Use Edit vs Write
- **Edit**: Modifying existing files (preferred)
- **Write**: Creating new files or complete rewrites
- Always read file first before editing
- Preserve exact indentation from Read output

### Indentation Handling
- Read tool shows line numbers with tabs
- Match indentation exactly as shown after the tab
- Don't include line number prefix in edit strings
- Verify indentation in diff after editing

### Making Multiple Changes
- Group related changes in single edit call when possible
- Use separate edits for logically distinct changes
- Test after each significant change
- Commit frequently to save progress

## Testing and Validation

### Before Committing
1. Run relevant tests (unit, integration, E2E)
2. Check for syntax errors (linters, type checkers)
3. Verify functionality manually if needed
4. Review git diff for unintended changes

### After Changes
- Start development server and spot-check
- Run affected tests to verify no regressions
- Check console/logs for errors
- Verify documentation still accurate

## Project Navigation

### Understanding Codebase
- Read README and CLAUDE.md first
- Check package.json/pyproject.toml for scripts
- Explore directory structure before diving in
- Use Grep to find patterns and examples

### File Discovery
- Use Glob for pattern-based file finding
- Check git status for modified files
- Look for configuration files (.env, config/)
- Identify entry points (main.py, index.js)

## Agent-Specific Guidance

### For Coding Agents
- Work in small, testable increments
- Commit after each working feature
- Update progress logs regularly
- Leave working tree clean at end of session

### For Initializer Agents
- Create comprehensive project scaffold
- Set up testing infrastructure
- Document all setup steps in init.sh
- Create feature list with clear acceptance criteria

### For Review Agents
- Read full context before commenting
- Suggest specific improvements, not vague critiques
- Verify suggestions would actually work
- Test before recommending changes

## Common Pitfalls

1. **Editing without reading**: Causes mismatched indentation, broken code
2. **Relative paths**: Breaks when working directory changes
3. **Skipping tests**: Leads to undetected regressions
4. **Large commits**: Makes debugging and rollback difficult
5. **Assuming file contents**: Files change, always re-read

## Workspace Integration

### CLAUDE.md Files
- Every project should have CLAUDE.md
- Include project-specific context and conventions
- Document common commands and workflows
- Reference workspace-wide conventions

### Git Hooks
- Use workspace_ops/conventions/git-hooks/
- Enable with: `git config core.hooksPath .githooks`
- Validate commit messages for agent attribution
- Run linters and tests pre-commit

### MCP Integration
- Tools exposed via MCP available automatically
- Use MCP servers for project-specific tools
- Browser automation via Playwright MCP
- Database access via custom MCP servers

## Key Takeaways

1. **Read First**: Always read files before editing
2. **Test Often**: Run tests after each logical change
3. **Commit Frequently**: Small, focused commits with clear messages
4. **Use Right Tools**: Read/Edit/Grep, not bash commands
5. **Check Context**: Verify CLAUDE.md and conventions

## References

- Full document: `raw/anthropic_claude_code_best_practices.raw.md`
- Related: `claude_4_summary.md` - General prompting guidance
- Related: `agent_sdk_summary.md` - SDK integration patterns
- Related: `/Users/mriechers/Developer/workspace_ops/conventions/COMMIT_CONVENTIONS.md` - Git conventions
