# Sprint Template Usage Guide

## Quick Start: Adapting the Template

For each repository sprint, copy `claude-code-sprint-template.md` and fill in the bracketed sections. Here are pre-filled examples for your three target repos:

---

## Sprint 1: workspace-ops

**Repository Context:**
- **Current State:** Collection of MCP servers and agent tools with informal documentation. Pain points: inconsistent error handling, unclear onboarding process, scattered configuration.
- **Primary Goal:** "Build comprehensive documentation infrastructure and standardize MCP server patterns"
- **Technology Stack:** Python 3.11+, MCP protocol, JSON configuration

**Special Considerations:**
```
- MCP servers must have clear error messages (they're called by other agents)
- Agent onboarding docs should be copy-paste ready
- Shared libraries should be well-documented for reuse
- Configuration patterns should be consistent across servers
- Each server should have integration examples
```

**Expected Outcomes:**
- Standardized MCP server template
- Comprehensive agent onboarding guide
- Centralized documentation hub
- Reusable patterns library
- Integration testing framework

**Estimated Credit Usage:** $75-90 (high documentation needs)

---

## Sprint 2: editorial-assistant

**Repository Context:**
- **Current State:** Working MCP-based editorial workflow with Gemini preprocessing. Pain points: token usage monitoring, workflow phase boundaries, feature evolution without clear architecture.
- **Primary Goal:** "Deep-dive rework of core features with clear separation of concerns and token optimization"
- **Technology Stack:** Python 3.11+, MCP protocol, Gemini API, file-based state management

**Special Considerations:**
```
- Transcript preprocessing should be clearly delegated to cheaper models
- Editorial workflow phases should have clean interfaces
- Token usage should be logged and monitored with warnings
- File versioning logic should be bulletproof
- Integration with PBS metadata standards should be well-documented
```

**Expected Outcomes:**
- Clear phase separation (preprocess → edit → analyze)
- Token usage monitoring dashboard
- Comprehensive workflow documentation
- Error recovery mechanisms
- Template library for common editorial patterns

**Estimated Credit Usage:** $80-100 (complex refactoring needs)

---

## Sprint 3: obsidian-config

**Repository Context:**
- **Current State:** Monolithic configuration repo that could be more modular. Pain points: coupled plugins, unclear boundaries, limited agent integration.
- **Primary Goal:** "Refactor into standalone plugins with robust MCP service for agent collaboration"
- **Technology Stack:** JavaScript/TypeScript (Obsidian plugins), Python (MCP service), PARA methodology

**Special Considerations:**
```
- Plugin separation should enable independent development cycles
- MCP service should have clean API contracts for note operations
- Integration points between plugins should be well-documented
- PARA methodology should be encoded in the MCP service
- Agent collaboration patterns should be clearly defined
```

**Expected Outcomes:**
- Modular plugin architecture
- Comprehensive MCP service for note-taking operations
- Clear plugin development guidelines
- Agent integration patterns
- Migration guide from monolith to modular structure

**Estimated Credit Usage:** $90-110 (significant architectural work)

---

## Execution Order Recommendation

### Option A: Sequential (Conservative)
**Week 1:** workspace-ops (build foundation)
- Establishes MCP patterns used by other projects
- Creates documentation standards to follow
- Builds shared tooling library

**Week 3:** editorial-assistant (apply learnings)
- Uses patterns from workspace-ops
- Implements token monitoring across workflow
- Validates MCP service architecture

**Week 5:** obsidian-config (comprehensive rework)
- Benefits from established patterns
- Integrates with refined MCP architecture
- Demonstrates full agent collaboration

**Total timeline:** ~5-6 weeks with breaks between sprints
**Total credits:** ~$245-300

### Option B: Parallel Prep (Aggressive)
Run all three planning phases (Phase 1) simultaneously:
- Get SPRINT_PLAN.md for all three repos
- Identify cross-repo dependencies
- Batch similar work (e.g., all documentation in one week)
- Execute improvements in logical order

**Benefit:** See the big picture before committing
**Risk:** May reveal need for more credits than budgeted

**Recommendation:** Start with Option A. The sequential approach lets you refine the sprint process as you go and avoid burning all credits before learning what works.

---

## Pre-Sprint Checklist

Before starting each sprint:

- [ ] Repository is in clean state (committed changes)
- [ ] You have 2-3 hours to review Claude Code's plan
- [ ] Backup exists (just in case)
- [ ] You've identified 2-3 "must have" outcomes
- [ ] Credit balance is confirmed
- [ ] You're ready to provide feedback on the plan

## During Sprint

**Your role:**
- Review SPRINT_PLAN.md and approve/adjust priorities
- Spot-check work as it progresses
- Ask questions if implementation isn't clear
- Validate that documentation makes sense
- Test changes in your actual workflow

**Claude Code's role:**
- Understand architecture deeply
- Make improvements autonomously
- Document decisions thoroughly
- Validate changes work correctly
- Capture knowledge for future reference

## Post-Sprint Checklist

After each sprint:

- [ ] Read SPRINT_SUMMARY.md thoroughly
- [ ] Test key workflows in real usage
- [ ] Update your own notes on what improved
- [ ] Identify patterns to apply to next sprint
- [ ] Calculate actual credit usage vs. estimate
- [ ] Note any additional work needed

## Cost Monitoring

Track actual vs. estimated spend:

| Repository | Estimated | Actual | Variance | Notes |
|------------|-----------|--------|----------|-------|
| workspace-ops | $75-90 | $__ | __% | |
| editorial-assistant | $80-100 | $__ | __% | |
| obsidian-config | $90-110 | $__ | __% | |
| **TOTAL** | **$245-300** | **$__** | **__%** | |

If variance is high, adjust expectations for remaining sprints.

## Success Metrics

After all three sprints, measure:

**Time Savings:**
- Hours saved per week on maintenance
- Reduced debugging sessions
- Faster onboarding for new projects

**Token Savings:**
- Fewer "how does this work" questions
- Better error messages reduce troubleshooting
- Documentation answers questions without LLM

**Quality Improvements:**
- Code confidence (subjective rating)
- Test coverage percentage
- Documentation completeness

**Developer Experience:**
- Easier to understand codebases
- Clear patterns to follow
- Better separation of concerns

Target: Each sprint should provide 2-3 hours/month in time savings and reduce token usage by 15-20% for that repository's workflows.

---

## Emergency Brake

If at any point you're burning credits too fast:

1. **Pause and review:** What's taking longer than expected?
2. **Scope reduction:** Cut lower-priority items from sprint
3. **Manual completion:** You finish simpler tasks, save credits for complex ones
4. **Document and defer:** Note what wasn't done for future work

Better to complete 70% really well than 100% rushed.

---

## Getting Started

1. Copy `claude-code-sprint-template.md` to your first target repo
2. Fill in the repository-specific sections (use examples above)
3. Open Claude Code in that repository
4. Paste the completed template
5. Review the SPRINT_PLAN.md it generates
6. Approve and let it work

Good luck with your infrastructure sprints! 🚀