# Agentic Software Development References
Generated: 2025-11-11

Each entry captures the raw crawl source (kept alongside this file) plus a condensed set of practices relevant to Librarian playbooks.

## Anthropic — Claude Code Best Practices
- Source: https://www.anthropic.com/engineering/claude-code-best-practices
- Local raw capture: `knowledge/anthropic_claude_code_best_practices.raw.md`
- Key ideas:
  - Treat `CLAUDE.md` files as living prompts—document commands, style, workflow rules; tune them via the prompt improver and emphasize must-follow instructions.
  - Curate tool permissions and CLI environment (`gh`, MCP servers, slash commands) so Claude has predictable capabilities without constant approvals.
  - Favor structured workflows (explore → plan → code → commit), test-first loops, screenshot-driven iteration, and `--dangerously-skip-permissions` only inside sandboxed containers.
  - Use explicit course-correction levers (`/clear`, plan-first, ESC interrupts, checklists) to manage context and keep large efforts on track.
  - Headless mode plus multi-Claude setups (parallel repos/worktrees, reviewer agents, pipelines) unlock automation for CI, triage, and large migrations.
- Workspace actions: Adopt/refresh repo `CLAUDE.md` templates, standardize `.claude/settings.json`, and reference these workflows in Librarian audits when checking agent readiness.

## Ran Isenberg — Agentic AI Prompting
- Source: https://www.ranthebuilder.cloud/post/agentic-ai-prompting-best-practices-for-smarter-vibe-coding
- Local raw capture: `knowledge/ranthebuilder_agentic_prompting.raw.md`
- Key ideas:
  - Six-step prompt pattern (persona → problem → context → plan-first → tailor prompt → optionally share) keeps vibe-coding sessions aligned with goals.
  - Encourage plan-first behavior before execution and adjust prompts per task rather than reusing generic templates.
  - Highlight risks: always review commits, keep humans in the loop, chain prompts for complex flows, break infinite loops, keep prompts simple, enforce tests/guardrails.
  - Platform teams should bake safeguards (rate limits, approvals, telemetry) directly into agent harnesses.
- Workspace actions: Fold the six-step template into `CLAUDE.md` guidance and Librarian onboarding materials for new repos.

## Reddit — One Year of AI Agent Lessons
- Source: https://www.reddit.com/r/AI_Agents/comments/1lpj771/ai_agent_best_practices_from_one_year_as_ai/
- Local raw capture: `knowledge/reddit_ai_agent_best_practices.raw.md`
- Key ideas:
  - Start without agents unless workflows are open-ended; simpler LangChain chains or direct API calls cover many needs.
  - Pick models pragmatically: begin with top-tier models to set quality baselines, then downshift until output degrades.
  - Enforce spend caps, structured outputs (JSON schemas), and single-responsibility LLM calls to control costs and simplify debugging.
  - Use transparent planning traces and narrow agent scopes; multi-agent setups make sense only when responsibilities are clearly split.
- Workspace actions: Reference these heuristics when triaging which repos warrant agent automation vs. scripts; add spend-limit checks to Librarian audits.

## GitHub — 500+ AI Agent Projects
- Source: https://github.com/ashishpatel26/500-AI-Agents-Projects
- Local raw capture: `knowledge/ashishpatel26_500_agents.raw.md`
- Key ideas:
  - Catalog of 500+ agent use cases across industries with direct links to OSS repos (healthcare diagnostics, trading bots, tutoring, support, etc.).
  - Framework-specific sections (CrewAI, AutoGen, Agno, LangGraph) map concrete recipes to toolchains and notebooks.
  - Useful for seeding backlog ideas, benchmarking coverage, or finding reference implementations during audits or bootstraps.
- Workspace actions: Link this catalog from Forerunner setup docs so new machines can clone relevant exemplars; leverage entries when prioritizing agent experiments.

## Suggested Next Sources
Resources to fetch next (add to crawl queue when ready):
1. Anthropic “Building Effective Agents” guide — deep dives on agent loop design, memory, evaluation.
2. LangChain/LangGraph agent playbooks — e.g., https://python.langchain.com/docs/how_to/agents/agent_best_practices .
3. OpenAI “Best practices for coding with AI assistants” or equivalent dev-rel posts capturing guardrails for Code Interpreter/Swarm.

## Maintenance Plan
- **Monthly review (Librarian cadence):** During the standard monthly audit window, run `crwl crawl <url> -o markdown -O knowledge/<name>.raw.md --bypass-cache` for each tracked source, diff against existing files, and refresh `agentic_dev_best_practices.md` with any new insights.
- **Change detection:** Subscribe to each source’s RSS/email (Anthropic Engineering blog feed, Ran Isenberg mailing list, GitHub repo watch, Reddit thread follow-up) so the Librarian gets notified when content changes outside the monthly window.
- **Version log:** When updates occur, append a short changelog entry at the bottom of each `.raw.md` noting the date and observed differences; include a brief summary update in the digest file.
- **Quarterly expansion:** Every quarter, scan for new reputable agentic-development writeups (conference talks, framework docs) and add promising URLs to `knowledge/scrape_queue.md` so the backlog stays fresh.
