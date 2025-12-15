# Long-Running Agent References
Generated: 2025-12-01

This note distills the latest Anthropic guidance on long-horizon harnesses plus community reactions, with raw captures kept alongside for full detail.

## Anthropic — Effective Harnesses for Long-Running Agents
- Sources: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents and sublinks (Agent SDK overview, autonomous coding quickstart, Claude 4 best practices).
- Local raws: `knowledge/anthropic_effective_harnesses_for_long_running_agents.raw.md`, `knowledge/anthropic_agent_sdk_overview.raw.md`, `knowledge/anthropic_autonomous_coding_quickstart.raw.md`, `knowledge/claude_4_best_practices.raw.md`.
- Core pattern: pair an initializer agent (creates `init.sh`, `feature_list.json`, `claude-progress.txt`, initial git commit) with a coding agent that only works one feature at a time, leaves a clean tree, and logs progress.
- Guardrails: keep the feature list as JSON with explicit `passes` flags; forbid removal of tests/features; require end-of-session git commit and progress note; always start by reading logs, feature list, and running a basic e2e check via `init.sh`.
- Testing: push the agent to use browser automation (e.g., Puppeteer MCP) and human-like flows to mark features cgemiomplete; vision limitations mean native modals and visual regressions need extra care.
- Failure modes & fixes: (1) premature “done” → comprehensive feature list; (2) messy state → progress log + clean exit; (3) unverified features → mandatory e2e testing; (4) relearn setup → `init.sh` bootstrap.
- Future work: consider specialized sub-agents (QA, cleanup, release); generalize beyond web apps.
- Workspace actions: bake `init.sh`, `claude-progress.txt`, and `feature_list.json` templates into the repo scaffolding; add MCP browser testing hooks; enforce “one feature per session” and required git commits in the harness script.

## Anthropic — Agent SDK Overview
- Source: https://platform.claude.com/docs/en/agent-sdk/overview (`knowledge/anthropic_agent_sdk_overview.raw.md`).
- Highlights: event-driven SDK with system/user tool separation, session state + compaction, built-in cost tracking, hosting guidance, and MCP integration for tools, slash commands, and remote servers.
- Workspace actions: align our MCP server registration and cost logging with the SDK’s session/usage hooks; reference SDK hosting guidance in `forerunner_setup.sh` for local testing.

## Anthropic — Autonomous Coding Quickstart
- Source: https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding (`knowledge/anthropic_autonomous_coding_quickstart.raw.md`).
- Highlights: concrete initializer/coding agent prompts, file layout (`feature_list.json`, `claude-progress.txt`, `init.sh`), and example commands for multi-session progress.
- Workspace actions: copy prompt scaffolds into our agent harness config; mirror file layout in the template project so new repos start with the expected artifacts.

## Claude 4.x Prompting Best Practices
- Source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-4-best-practices (`knowledge/claude_4_best_practices.raw.md`).
- Highlights: explicit, roleful prompts; chain-of-thought and XML framing; multishot examples; structured outputs; long-context tactics (different first-window prompt, compaction); evaluation guidance with success criteria and test cases.
- Workspace actions: update `CLAUDE.md` patterns to emphasize first-window prompts for initializers, CoT + XML for plans, and structured JSON outputs for feature/state files.

## Reddit — Community Takeaways
- ClaudeCode thread (`knowledge/reddit_claudecode_long_range_work.raw.json`): community converges on orchestrator patterns mirroring the Anthropic harness; folks use MCP-backed planners and task DBs, with git+progress logs and spec-kit/taskmaster analogs.
- AI_SearchOptimization thread (`knowledge/reddit_ai_searchoptimization_long_range_work.raw.json`): reminder that web search APIs return snippets; content should be chunked with clear headers and tight intro paragraphs for retrieval/RAG.
- Workspace actions: validate our harness against these patterns (orchestrator + MCP task DB); tune documentation and site content for snippet-friendly headings if we rely on search-powered ingestion.
