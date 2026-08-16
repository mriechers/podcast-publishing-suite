# Knowledge Directory

Populate this folder by running:

```bash
python3.11 scripts/crawl_docs.py --init
```

The crawler prompts for each documentation source (category, slug, URL, notes) and stores:
- `<category>/<slug>.md` — Markdown scrape
- `<category>/<slug>.html` — Raw HTML
- `<category>/<slug>.json` — Metadata (timestamp, status, notes)

Keep this directory under version control to track the evolution of your knowledge base, but avoid committing sensitive credentials or personal caches.*** End Patch
