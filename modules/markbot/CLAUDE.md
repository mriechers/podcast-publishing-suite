# markbot

**Your Helpful MarkBot!** — centralized Slack bot for the podcast publishing suite.

Single-file CLI (`markbot.py`) that owns all Slack notifications for Wonder Cabinet Productions. Uses `slack-sdk` with Bot Token auth.

## Non-Claude Agents: Workspace Isolation Rules

**If you are NOT Claude Code** (e.g., Gemini CLI, Codex, Copilot, Cursor, or any other LLM agent), you MUST follow these isolation rules to avoid interfering with Claude agent work:

1. **Always work in a git worktree.** Never modify files on the current branch directly. Create a worktree before making any changes:
   ```bash
   git worktree add .worktrees/<your-agent-name>-<feature> -b <your-agent-name>/<feature-description>
   ```
2. **Always commit to a feature branch.** Your branch name must include your agent identifier (e.g., `gemini/fix-typo`, `codex/add-tests`, `copilot/refactor-utils`). Never commit to `main` or any branch you did not create.
3. **Never force-push, rebase, or modify branches you did not create.** Treat all existing branches as read-only references.
4. **Clean up after yourself.** When your work is complete, leave the worktree in place for human review. Do not merge your own branches.
5. **Follow all other rules in this file.** The conventions below (commit format, secrets management, attribution, etc.) apply to all agents equally.

> Claude Code agents are exempt from the worktree requirement because they are the primary agents for this workspace and coordinate directly with the user.


## Commands

| Command | Purpose | Caller |
|---------|---------|--------|
| `transcribe-start` | "Job started" notification | `wc-transcribe` skill |
| `transcribe-ready` | "Transcript ready" with Google Doc link | `wc-transcribe` skill |
| `schedule-alert` | Release readiness alerts (missing/drafted/scheduled) | Airtable automations |
| `ghost-import` | Import lifecycle notifications (start/draft/scheduled/failed) | `prx-to-ghost-publisher` |
| `post` | Generic Block Kit poster | Any caller with custom blocks |

## Usage

```bash
# All commands support --dry-run (prints Block Kit JSON without posting)

# Transcription
markbot.py transcribe-start --episode "007 - Robert MacFarlane" --channel C09QUBVE0DR
markbot.py transcribe-ready --episode "007 - ..." --doc-url URL --channel C --thread-ts TS

# Schedule alerts
markbot.py schedule-alert --state missing --show "Wonder Cabinet" \
    --slot "Podcast Episode" --release-time "Saturday at 6 AM" --channel C09QUBVE0DR

# Ghost import lifecycle
markbot.py ghost-import --state start --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa on the Sacred Feminine" --channel C09QUBVE0DR
markbot.py ghost-import --state draft --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa..." \
    --ghost-url "https://wonder-cabinet.ghost.io/ghost/#/editor/post/abc" \
    --channel C --thread-ts TS
markbot.py ghost-import --state scheduled --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa..." \
    --ghost-url URL --schedule-time "Saturday at 6 AM" --channel C
markbot.py ghost-import --state failed --show "Wonder Cabinet" \
    --episode "Dekila Chungyalpa..." \
    --error "Validation error" --channel C

# Generic posting (accepts JSON string or stdin with "-")
markbot.py post --blocks-json '{"blocks":[...]}' --channel C09QUBVE0DR
echo '{"blocks":[...]}' | markbot.py post --blocks-json - --channel C09QUBVE0DR
```

## Environment

- `SLACK_BOT_TOKEN` — Bot User OAuth Token (starts with `xoxb-`)

## Conventions

- Single-file CLI, not a Python package — no `pyproject.toml` / `src/` overhead
- `--dry-run` prints Block Kit JSON to stdout without posting
- `transcribe-start` prints `thread_ts` to stdout for capture by calling scripts
- `post` command accepts `{"blocks": [...]}` or bare `[...]` JSON
- Channel IDs, not names, for `--channel`

## Channel Reference

| Channel | ID | Purpose |
|---------|----|---------|
| #all-wonder-cabinet-productions | `C09QUBVE0DR` | Production channel (default) |
