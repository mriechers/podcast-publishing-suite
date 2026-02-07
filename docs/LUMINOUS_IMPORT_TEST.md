# Luminous Import Test Handoff

This document provides instructions for testing the Luminous episode import from the live PRX feed.

## Overview

The Luminous podcast is a sub-series of To The Best Of Our Knowledge focusing on psychedelics. This test validates the full import pipeline from PRX RSS feed to Ghost CMS draft posts.

## Prerequisites

1. **Environment configured** - `.env` file with Ghost credentials:
   ```
   GHOST_URL=http://192.168.5.156:2368
   GHOST_ADMIN_API_KEY=<your-key>
   ```

2. **Python dependencies installed**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ghost dev instance running** at `http://192.168.5.156:2368`

## Test Commands

### Dry Run (Recommended First Step)

Preview what would be imported without publishing:

```bash
python -m src.main -v sync --feed-type luminous --dry-run
```

Expected output:
- 19 episodes found
- 18 episodes have cached transcripts
- Titles display without "Luminous:" prefix
- Tags include: Luminous, Psychedelics, TTBOOK

### Single Episode Test

Import one episode as draft for review:

```bash
python -m src.main sync --feed-type luminous --limit 1
```

### Full Import (All Episodes as Drafts)

Import all 19 Luminous episodes as draft posts:

```bash
python -m src.main sync --feed-type luminous
```

## What to Verify

### In Ghost Admin

After importing, check the Ghost admin panel for:

1. **Post Title** - "Luminous:" prefix should be removed
2. **Feature Image** - Episode artwork from `itunes:image`
3. **Custom Excerpt** - From `itunes:subtitle`
4. **Tags** - Should include Luminous, Psychedelics, TTBOOK plus feed categories
5. **Canonical URL** - Points to ttbook.org episode page
6. **Published Date** - Matches original RSS pubDate

### In Post Content

Each post should contain:

1. **Metadata line**: "Duration: XX:XX | Original Air Date: Month DD, YYYY"
2. **Episode description** (boilerplate stripped)
3. **PRX embeddable player** (iframe)
4. **Transcript section** (for 18 of 19 episodes)
5. **Subscribe footer links**

### Content Transforms

The import applies these transformations:

- **Title**: Removes "Luminous: " prefix
- **Description**: Strips "About Luminous" boilerplate section
- **Transcript**: Formats speaker attributions as `<strong>Speaker:</strong>`

## Feed Details

| Property | Value |
|----------|-------|
| Feed URL | `https://f.prxu.org/3329/feed-rss.xml` |
| Episode Count | 19 |
| With Transcripts | 18 |
| Feed Type Flag | `--feed-type luminous` |

## Transcript Cache

Transcripts are cached locally in:
```
sample-data/ttbook-cache/luminous/{slug}_transcript.txt
```

One episode lacks a transcript (may need to be fetched or created).

## State Tracking

The importer uses state tracking to prevent duplicates:
- State file: `state/published.json`
- To re-import previously imported episodes, delete the state file or specific GUIDs

## Troubleshooting

### CLI Argument Order

The `-v` verbose flag must come before the subcommand:
```bash
# Correct
python -m src.main -v sync --feed-type luminous --dry-run

# Incorrect (will fail)
python -m src.main sync --feed-type luminous --dry-run -v
```

### Ghost Connection Issues

Test connection first:
```bash
python -m src.main test-connection
```

### Feed Fetch Errors

Try fetching with verbose logging:
```bash
python -m src.main -v sync --feed-type luminous --dry-run
```

## Files Involved

| File | Purpose |
|------|---------|
| `src/main.py` | CLI entry point, sync orchestration |
| `src/feed_parser.py` | RSS parsing, Episode dataclass |
| `src/content_builder.py` | `build_luminous_ghost_post()`, `build_luminous_post_html()` |
| `src/content_transforms.py` | Boilerplate removal rules |
| `src/ghost_client.py` | Ghost Admin API client |
| `src/state_tracker.py` | Duplicate prevention |

## Success Criteria

- [ ] All 19 episodes import without errors
- [ ] 18 transcripts attached to posts
- [ ] Feature images display correctly
- [ ] PRX player embeds work
- [ ] No "Luminous:" prefix in titles
- [ ] Tags properly assigned
- [ ] Posts appear as drafts in Ghost admin
