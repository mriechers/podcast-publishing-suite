# Effective Harnesses for Long-Running Agents - Executive Summary

Generated: 2025-12-02
Source: `/Users/mriechers/Developer/workspace_ops/knowledge/agents/raw/anthropic_effective_harnesses_for_long_running_agents.raw.md` (136KB)
Original URL: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## Core Pattern: Initializer + Coding Agent

### Two-Agent Architecture
1. **Initializer Agent**: Sets up project scaffolding and creates initial artifacts
2. **Coding Agent**: Works iteratively on one feature at a time

### Why Two Agents?
- Separation of concerns: planning vs. implementation
- Different prompting strategies for each phase
- Initializer uses first-window advantage for comprehensive setup
- Coding agent maintains focus on single feature

## Essential Artifacts

### 1. init.sh - Bootstrap Script
- Single command to set up development environment
- Install dependencies (npm install, pip install, etc.)
- Run initial build or compilation
- Start development server
- Provides consistent starting point across sessions

### 2. feature_list.json - Work Queue
```json
{
  "features": [
    {
      "id": "F001",
      "name": "User authentication",
      "description": "Login/logout with email and password",
      "status": "pending",
      "passes": false
    }
  ]
}
```
- Comprehensive list of all features to implement
- Explicit `passes` flag for each feature
- Status tracking: `pending`, `in_progress`, `completed`
- Prevents agent from claiming "done" prematurely

### 3. claude-progress.txt - Session Log
- Date/time stamped entries
- What was accomplished this session
- What tests passed or failed
- Issues encountered and resolutions
- Handoff notes for next session

## Guardrails and Constraints

### Mandatory Behaviors
1. **Read First**: Always start by reading `claude-progress.txt` and `feature_list.json`
2. **One Feature**: Work on exactly one feature per session
3. **Clean Exit**: Leave working tree clean (no uncommitted changes)
4. **Git Commit**: End every session with a commit
5. **Progress Update**: Write to `claude-progress.txt` before finishing
6. **Test Verification**: Run `init.sh` to verify feature works end-to-end

### Forbidden Actions
- **Never**: Remove features from `feature_list.json`
- **Never**: Remove tests once written
- **Never**: Mark feature as passing without running tests
- **Never**: Start new feature before completing current one
- **Never**: Leave uncommitted changes

## Testing Strategy

### End-to-End Testing
- Use browser automation (Puppeteer MCP) for web apps
- Simulate human user flows, not programmatic shortcuts
- Test against actual UI, not just backend APIs
- Verify visual correctness where possible

### Vision Limitations
- Native browser modals (alert, confirm) not visible to Claude
- Some visual regressions require human verification
- Focus on functional correctness that can be automated
- Document manual test steps for visual elements

### Test Coverage Requirements
- Every feature must have at least one E2E test
- Tests must pass before marking feature complete
- Test failures block progress to next feature
- Regression tests for previously completed features

## Common Failure Modes

### 1. Premature "Done"
**Problem**: Agent claims all work is complete when features remain
**Solution**: Comprehensive `feature_list.json` created upfront by initializer
**Guardrail**: `passes: false` prevents claiming success

### 2. Messy State
**Problem**: Uncommitted changes, broken builds, lost context
**Solution**: `claude-progress.txt` tracks state; git commit requirement ensures clean state
**Guardrail**: Always read progress log first; always commit before exiting

### 3. Unverified Features
**Problem**: Features marked complete without actual testing
**Solution**: Mandatory E2E testing via browser automation
**Guardrail**: `passes` flag only set to `true` after test succeeds

### 4. Context Loss Across Sessions
**Problem**: Agent relearns project setup every time
**Solution**: `init.sh` provides one-command bootstrap
**Guardrail**: First action is always run `init.sh` and read logs

## Multi-Session Workflow

### Session N
1. Run `init.sh` to set up environment
2. Read `claude-progress.txt` for context
3. Read `feature_list.json` to find next pending feature
4. Implement one feature
5. Write tests and verify they pass
6. Update `feature_list.json`: mark feature `passes: true`, status `completed`
7. Update `claude-progress.txt` with session summary
8. Git commit with clear message
9. Exit with clean working tree

### Session N+1
1. Run `init.sh` (may be no-op if already set up)
2. Read `claude-progress.txt` - sees what Session N accomplished
3. Read `feature_list.json` - finds next pending feature
4. Continue from where Session N left off

## Future Enhancements

### Specialized Sub-Agents
- **QA Agent**: Focus solely on testing and verification
- **Cleanup Agent**: Refactor and optimize completed features
- **Release Agent**: Handle versioning, changelog, deployment

### Generalization Beyond Web Apps
- Adapt patterns for CLI tools, libraries, mobile apps
- Feature list schema variations for different project types
- Testing strategies for non-UI projects

### Advanced State Management
- Feature dependency graphs (F002 requires F001)
- Parallel feature work with merge coordination
- Automated feature estimation and prioritization

## Workspace Action Items

### Template Creation
- Create `init.sh` template in workspace conventions
- Provide `feature_list.json` schema
- Include `claude-progress.txt` format guide

### Scaffolding Integration
- Bake these files into new project scaffolding
- Update `forerunner_setup.sh` to create them for new repos
- Add to AGENT_ONBOARDING.md checklist

### MCP Browser Testing
- Set up Puppeteer MCP server in workspace
- Document browser testing patterns
- Create E2E test templates

### Harness Script
- Build orchestration script that enforces guardrails
- Automate the "read logs, work feature, commit" cycle
- Integrate with Agent SDK event model

## References

- Full document: `raw/anthropic_effective_harnesses_for_long_running_agents.raw.md`
- Related: `raw/anthropic_autonomous_coding_quickstart.raw.md` - Concrete implementation example
- Related: `/Users/mriechers/Developer/workspace_ops/knowledge/claude/claude_4_summary.md` - Prompting techniques
- Related: `/Users/mriechers/Developer/workspace_ops/knowledge/claude/agent_sdk_summary.md` - SDK integration
- Related: `/Users/mriechers/Developer/workspace_ops/knowledge/community-practices/reddit_discussions_summary.md` - Community implementations
