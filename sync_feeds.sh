#!/bin/bash
# Sync both Luminous and Wonder Cabinet feeds to Ghost as drafts
# Usage: ./sync_feeds.sh [--dry-run] [--limit N]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=""
LIMIT=""
FULL_SYNC=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --limit)
            LIMIT="--limit $2"
            shift 2
            ;;
        --full)
            FULL_SYNC=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--limit N] [--full]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PRX-to-Ghost Feed Sync${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Make sure PRX_CLIENT_ID and PRX_CLIENT_SECRET are set in your environment"
    echo ""
fi

# Export podcast IDs for both feeds
export PRX_PODCAST_IDS="3329,120"

echo -e "${GREEN}Configuration:${NC}"
echo "  Source: Dovetail API"
echo "  Podcasts: 3329 (Luminous), 120 (Wonder Cabinet)"
echo "  Status: draft"
if [ -n "$DRY_RUN" ]; then
    echo -e "  Mode: ${YELLOW}DRY RUN${NC} (no posts will be created)"
else
    echo "  Mode: Live import"
fi
if [ "$FULL_SYNC" = true ]; then
    echo -e "  Sync Type: ${YELLOW}FULL SYNC${NC} (ignoring last sync time)"
else
    echo "  Sync Type: Incremental (only new episodes since last sync)"
fi
if [ -n "$LIMIT" ]; then
    echo "  Limit: $LIMIT episodes per feed"
fi
echo ""

# Temporarily clear last_sync_time for full sync
STATE_FILE="data/published_episodes.json"
BACKUP_FILE=""
if [ "$FULL_SYNC" = true ] && [ -f "$STATE_FILE" ]; then
    echo -e "${YELLOW}Clearing last sync time for full sync...${NC}"
    BACKUP_FILE="${STATE_FILE}.backup.$(date +%s)"
    cp "$STATE_FILE" "$BACKUP_FILE"

    # Remove last_sync_time from metadata using python
    python3 -c "
import json
with open('$STATE_FILE', 'r') as f:
    data = json.load(f)
if '_metadata' in data and 'last_sync_time' in data['_metadata']:
    del data['_metadata']['last_sync_time']
    with open('$STATE_FILE', 'w') as f:
        json.dump(data, f, indent=4)
    print('  Cleared last_sync_time from state')
"
    echo ""
fi

# Run sync with API source
echo -e "${BLUE}Starting sync...${NC}"
echo ""

python3 -m src.main sync \
    --source api \
    --status draft \
    $DRY_RUN \
    $LIMIT

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Sync completed successfully!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
else
    echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  Sync completed with errors (exit code: $EXIT_CODE)${NC}"
    echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
fi

exit $EXIT_CODE
