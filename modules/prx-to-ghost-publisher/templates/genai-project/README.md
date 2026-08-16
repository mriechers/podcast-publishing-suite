# Generative AI Project Template

Copy this directory to jump-start a new generative AI project. It captures the core setup we follow when bootstrapping a workspace, analysing an unfamiliar repository, and harvesting external documentation for reference. For a step-by-step checklist, see `BOOTSTRAP.md` in this folder.

## Quickstart
1. **Create the project folder**  
   ```bash
   cp -R templates/genai-project ~/Projects/new-project
   cd ~/Projects/new-project
   ```

2. **Set up Crawl4AI tooling (Python 3.11)**  
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   python3.11 -m pip install --upgrade pip
   python3.11 -m pip install crawl4ai
   python3.11 -m playwright install chromium
   ```

3. **Collect knowledge sources**  
   Run the interactive crawler to define documentation targets and capture first snapshots:
   ```bash
   python3.11 scripts/crawl_docs.py --init
   ```
   The script will prompt for each source (category, slug, URL, notes) and write the details to `knowledge/sources.json`. After confirmation, it saves Markdown, HTML, and metadata into `knowledge/<category>/`.

4. **Refresh or extend sources later**  
   - Add more references interactively: `python3.11 scripts/crawl_docs.py --append`  
   - Re-crawl specific entries: `python3.11 scripts/crawl_docs.py --slug workflow-docs`  
   - Dry run without writing files: `python3.11 scripts/crawl_docs.py --dry-run`

5. **Document insights**  
   Use `GENAI_BOOTSTRAP.md` (copied from the root repository) or your own notes to record environment details, commands, and analysis findings.

## Folder Overview
- `knowledge/` — Markdown/HTML snapshots and metadata for documentation sources defined in `knowledge/sources.json`.
- `scripts/` — Automation scripts. `crawl_docs.py` handles interactive Crawl4AI runs.
- `.gitignore` — Keeps virtual environments and artifacts out of version control.

Adapt the template as needed: add workflow-specific commands, seed the knowledge directory with domain references, or include additional setup scripts. The goal is to provide a repeatable starting point that pairs project analysis with a curated knowledge base.

## Co-Authors

This project is developed collaboratively with AI assistance. Commit attribution follows the workspace conventions in `/Users/mriechers/Developer/workspace_ops/conventions/COMMIT_CONVENTIONS.md`.

| Agent | Role | Recent Commits |
|-------|------|----------------|
| Main Assistant | Primary development (update per project) | `git log --grep="Agent: Main Assistant"` |
| code-reviewer | Code review and QA | `git log --grep="Agent: code-reviewer"` |

Update this table with any project-specific agents. Run `git log --grep="Agent:" --oneline` to see the full agent history for the repository. See the workspace conventions document for more query examples.
