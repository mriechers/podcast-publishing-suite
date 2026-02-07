# Feed Sync Quick Start Guide

This guide explains how to sync podcast episodes from both Luminous and Wonder Cabinet to Ghost.

## Quick Sync Commands

### Basic Sync (Import as Drafts)

```bash
# From project directory
./sync_feeds.sh
```

This will:
- Fetch new episodes from both Luminous (podcast 3329) and Wonder Cabinet (podcast 120)
- Import them as **drafts** to Ghost
- Skip episodes that have already been imported

### Dry Run (Preview Without Importing)

```bash
./sync_feeds.sh --dry-run
```

Use this to see what would be imported without actually creating posts.

### Limited Sync (For Testing)

```bash
./sync_feeds.sh --limit 1
```

Import only the first new episode from each feed.

### Dry Run with Limit

```bash
./sync_feeds.sh --dry-run --limit 3
```

Preview up to 3 new episodes from each feed without importing.

### Full Sync (All Episodes)

```bash
./sync_feeds.sh --full
```

By default, the sync uses **incremental mode** - it only fetches episodes modified since the last sync. Use `--full` to re-scan all episodes from both feeds. This is useful for:
- Initial setup
- Testing after configuration changes
- Recovering from missed episodes

**Note**: Full sync still respects the duplicate prevention system - it won't re-import episodes that are already in Ghost.

### Full Sync Preview

```bash
./sync_feeds.sh --full --dry-run --limit 5
```

Preview up to 5 episodes from each feed (including older ones) without importing.

## Shell Aliases (Optional)

For even easier access, add these aliases to your `~/.zshrc` or `~/.bashrc`:

```bash
# PRX-to-Ghost aliases
alias prx-sync='cd ~/Developer/ghost-dev/prx-to-ghost-publisher && ./sync_feeds.sh'
alias prx-sync-dry='cd ~/Developer/ghost-dev/prx-to-ghost-publisher && ./sync_feeds.sh --dry-run'
alias prx-sync-test='cd ~/Developer/ghost-dev/prx-to-ghost-publisher && ./sync_feeds.sh --dry-run --limit 1'
alias prx-sync-full='cd ~/Developer/ghost-dev/prx-to-ghost-publisher && ./sync_feeds.sh --full'
```

After adding these, reload your shell:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

Then you can sync from anywhere:
```bash
prx-sync          # Run incremental sync (only new episodes)
prx-sync-dry      # Preview what would be imported
prx-sync-test     # Preview just the first new episode
prx-sync-full     # Re-scan all episodes (full sync)
```

## What Gets Synced?

### Luminous (Podcast ID: 3329)
- **Feed URL**: `https://f.prxu.org/3329/feed-rss.xml`
- **Ghost Tag**: `luminous` (routes to `/luminous/`)
- **Type**: Psychedelics podcast series

### Wonder Cabinet (Podcast ID: 120)
- **Feed URL**: `https://publicfeeds.net/f/120/wondercabinet`
- **Current Title**: "To The Best Of Our Knowledge" (will change to "Wonder Cabinet" next week)
- **Ghost Tag**: `wonder-cabinet` (routes to `/wonder-cabinet/`)
- **Type**: Main podcast about nature, science, and wonder

## Target Ghost Instance

**Currently syncing to**: Dev/Test Ghost instance
- URL: `https://dev-d414ccab.wondercabinetproductions.com` (from `PROJECT_STATUS.md`)

**Eventually will sync to**: Production Ghost instance
- URL: `https://wondercabinetproductions.com`

## Configuration

The sync script uses these environment variables from `.env`:

```bash
# Required for API access
PRX_CLIENT_ID=your_client_id
PRX_CLIENT_SECRET=your_client_secret

# Ghost instance (test site for now)
GHOST_URL=https://dev-d414ccab.wondercabinetproductions.com
GHOST_ADMIN_KEY=your_admin_key
```

## State Tracking

Episode sync state is tracked in:
```
data/published_episodes.json
```

This file prevents duplicate imports and tracks:
- Published episodes (by GUID)
- Failed imports (for retry)
- Last sync timestamp (for incremental updates)

## Troubleshooting

### "No new episodes found"
This is normal if you've already imported all available episodes. The sync uses incremental updates based on the last sync time.

### Authentication Errors
Make sure `PRX_CLIENT_ID` and `PRX_CLIENT_SECRET` are set correctly in `.env`.

### Ghost API Errors
Verify that:
1. `GHOST_URL` points to your test Ghost instance
2. `GHOST_ADMIN_KEY` is valid (format: `id:secret`)
3. Required tags exist in Ghost: `luminous`, `wonder-cabinet`

## Manual Sync Commands

For more control, you can use the underlying CLI directly:

```bash
# Sync from API (both feeds)
python3 -m src.main sync --source api --status draft

# Sync only Luminous
export PRX_PODCAST_IDS="3329"
python3 -m src.main sync --source api --status draft

# Sync only Wonder Cabinet
export PRX_PODCAST_IDS="120"
python3 -m src.main sync --source api --status draft

# Sync from RSS feed (legacy method)
python3 -m src.main sync --source rss --feed-type luminous --status draft
```

## Next Steps

1. **Test Imports**: Run `./sync_feeds.sh --dry-run --limit 1` to preview
2. **Import First Episode**: Run `./sync_feeds.sh --limit 1` to import one episode
3. **Check Ghost**: Verify the post appears in your Ghost admin
4. **Full Sync**: Run `./sync_feeds.sh` to import all new episodes
5. **Setup Automation** (future): Configure GitHub Actions to run sync every 30 minutes

## Notes

- All imports are created as **drafts** for review before publishing
- Episodes are imported with full metadata (title, description, featured image, audio)
- The system prevents duplicate imports using GUID tracking
- Failed imports are logged and can be retried
