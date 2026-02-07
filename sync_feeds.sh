#!/bin/bash
# Sync both Luminous and Wonder Cabinet feeds to Ghost as drafts
# Usage: ./sync_feeds.sh [--env {dev|prod}] [--dry-run] [--limit N] [--full] [--yes]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse arguments
ENV="dev"
DRY_RUN=""
LIMIT=""
FULL_SYNC=false
YES=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
                echo -e "${RED}Error: --env must be 'dev' or 'prod', got '$ENV'${NC}"
                exit 1
            fi
            shift 2
            ;;
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
        --yes|-y)
            YES=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--env {dev|prod}] [--dry-run] [--limit N] [--full] [--yes]"
            exit 1
            ;;
    esac
done

# Environment banner
if [ "$ENV" = "prod" ]; then
    echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  PRX-to-Ghost Feed Sync  ·  PRODUCTION${NC}"
    echo -e "${RED}  Target: https://wonder-cabinet.ghost.io${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
else
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  PRX-to-Ghost Feed Sync  ·  DEV${NC}"
    echo -e "${BLUE}  Target: http://localhost:2368${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
fi
echo ""

# Production safety gate
if [ "$ENV" = "prod" ] && [ "$YES" = false ]; then
    echo -e "${YELLOW}⚠  You are about to sync to PRODUCTION (wonder-cabinet.ghost.io)${NC}"
    read -p "Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
    echo ""
fi

# Check if environment file exists
if [ ! -f ".env.${ENV}" ]; then
    echo -e "${RED}Error: .env.${ENV} not found${NC}"
    echo "Copy .env.example to .env.${ENV} and fill in credentials."
    exit 1
fi

# Export podcast IDs for both feeds
export PRX_PODCAST_IDS="3329,120"

echo -e "${GREEN}Configuration:${NC}"
echo "  Environment: ${ENV}"
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
# State file uses env-specific path: published_episodes.{env}.json
STATE_FILE="data/published_episodes.${ENV}.json"
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

python3 -m src.main --env "$ENV" sync \
    --source api \
    --status draft \
    --yes \
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
