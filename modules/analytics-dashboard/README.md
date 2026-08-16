# Analytics Dashboard

Data collection and agentic analysis for Wonder Cabinet Productions.

## Sources

| Source | What it collects | Status |
|--------|-----------------|--------|
| Ghost | Posts, members, newsletters | Active |
| PRX Dovetail | Episode catalog (metadata) | Active |
| Google Analytics | Site traffic | Planned |
| Google Search Console | Search performance | Planned |
| YouTube | Channel metrics | Planned |

## Usage

```bash
# Refresh all data
python -m src.cli refresh

# Refresh a single source
python -m src.cli refresh --source ghost
```

Or use the `/wc-analytics` Claude skill for agentic analysis.
