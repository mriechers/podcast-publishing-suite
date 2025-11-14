# Bootstrap Checklist

Follow this checklist whenever you copy this template into a new generative AI project.

1. **Survey the repository**
   - `ls`, `rg --files` to understand layout before modifying anything.
   - Note languages, package managers, existing docs, and automation scripts.

2. **Prepare Python environments**
   - Ensure system Python 3.11 is available; create a local venv for scraping:
     ```bash
     python3.11 -m venv .venv
     source .venv/bin/activate
     python3.11 -m pip install --upgrade pip crawl4ai
     python3.11 -m playwright install chromium
     ```
   - If legacy CLIs (e.g., `gpt`) are needed, create a separate venv (e.g., `.venv-gptcli`) and pin their dependencies there.

3. **Build the knowledge base**
   - Run `python3.11 scripts/crawl_docs.py --init` to enter documentation sources (category, slug, URL, notes).
   - Snapshots are saved to `knowledge/<category>/` as Markdown, HTML, and JSON metadata.
   - Re-run with `--append`, `--slug`, `--category`, or `--dry-run` to evolve the knowledge set.

4. **Capture findings**
   - Record environment notes, key commands, and workflow insights in project docs (e.g., `AGENTS.md`, tickets, or project README).
   - Keep secrets and personal caches out of version control; document setup steps instead.

5. **Iterate**
   - Add or update sources in `knowledge/sources.json` as requirements expand.
   - Extend `scripts/` with additional tooling (linting, packaging, automation) tailored to the project.

This checklist mirrors the broader guidance in `GENAI_BOOTSTRAP.md` at the repository root; keep both in sync as the process evolves.*** End Patch
