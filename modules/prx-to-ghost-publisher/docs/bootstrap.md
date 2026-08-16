# Generative AI Project Bootstrap Guide

Use this guide after choosing “Use this template” on GitHub. It covers the three core steps every generative‑AI project should follow: launch a fresh repo from `_PROJECT-TEMPLATE`, stand up Crawl4AI-powered knowledge capture locally, and design an agent architecture that follows team conventions.

## Step 1 – Create a Repository from the Template
- Click **Use this template** ➜ **Create a new repository** on GitHub. Name the repo for the engagement, make it private by default, and commit the template’s README and docs.
- Add a short project blurb and ownership contact in the GitHub repo description so future collaborators know the scope.
- Enable required automation (branch protection, Actions, Codespaces) to match your preferred workflow before anyone clones the repo.
- File a kickoff issue or discussion for setup tasks (environment prep, knowledge sources, agent backlog) so progress is tracked from day one.

## Step 2 – Clone Locally and Stand Up Crawl4AI

### 2.1 Survey the Workspace
- Clone the new repository locally and run `ls` / `rg --files` to confirm the template contents landed correctly.
- Skim existing docs, scripts, and configuration. Note languages, package managers, and deployment targets so you can prioritise environment setup.

### 2.2 Prepare the Python Environment
- Record `python3 --version` and install/use Python 3.11 for Crawl4AI (`python3.11 --version`). If 3.11 is missing, install it before proceeding.
- Create a dedicated virtual environment (e.g., `python3.11 -m venv .venv-crawl4ai`) and activate it when running Crawl4AI or Playwright. Keep legacy tooling in isolated venvs to avoid dependency clashes.

### 2.3 Bootstrap Knowledge Capture
- Ensure the `knowledge/` directory stays in the repo; commit metadata and Markdown outputs, but keep personal caches ignored.
- Install Crawl4AI and Playwright inside the 3.11 environment:
  - `python3.11 -m pip install crawl4ai`
  - `python3.11 -m playwright install chromium`
- Copy or adapt `scripts/crawl_docs.py` so it references `knowledge/sources.json`. The script should support incremental crawls and metadata tagging.

### 2.4 Collect Initial Documentation
- Run `python3.11 scripts/crawl_docs.py --init` and enter source details (category, slug, URL, notes). The script saves the list to `knowledge/sources.json` and scrapes immediately.
- Re-run with filters (`--slug`, `--category`, `--dry-run`) whenever you need updates. Commit new knowledge artifacts to version control to preserve research trails.

## Step 3 – Design the Agent Architecture
- Map the project’s goals into an initial agent topology (planner, specialist tools, evaluators) and capture the plan in `AGENTS.md` so the team shares a common vocabulary.
- Audit existing workflows with `rg`, language-specific CLIs, or IDE tooling; log findings and gaps that agents must cover.
- Document API credentials and operational runbooks in the knowledge base, never in the repo. Add stubs or environment variable examples in `.env.example`.
- Establish testing and evaluation baselines early (simulation harnesses, regression suites) so agents can be validated as the system evolves.

---

Copy `templates/genai-project/` when you need a preconfigured scaffold (crawler scripts, notebook patterns, agent snippets). Following these three steps keeps every template-derived repo consistent, discoverable, and ready for collaborative agent development.
