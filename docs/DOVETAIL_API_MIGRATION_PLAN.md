# Dovetail API Migration Plan

## Orchestrator/Agent Architecture

This plan uses The Conductor pattern to coordinate parallel work streams for migrating from RSS to Dovetail API while maintaining both data sources.

```
┌─────────────────────────────────────────────────────────────────┐
│                     THE CONDUCTOR                                │
│         Orchestrates migration, manages dependencies             │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   DRONE-A     │    │   DRONE-B     │    │   DRONE-C     │
│  OAuth Client │    │ Episode Parser│    │  CLI & Config │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │   DRONE-D     │
                    │  Integration  │
                    │   & Testing   │
                    └───────────────┘
```

---

## Phase 1: Parallel Implementation (Drones A, B, C)

### DRONE-A: OAuth2 Client Foundation

**File:** `src/prx_auth.py`

**Tasks:**
1. Implement OAuth2 client credentials flow
2. Token caching with expiration handling
3. Automatic token refresh before API calls
4. Environment variable loading for credentials

**Deliverables:**
```python
# src/prx_auth.py
class PRXAuthClient:
    def __init__(self, client_id: str, client_secret: str, id_base_url: str)
    def get_access_token(self) -> str
    def _refresh_token(self) -> None
    def _is_token_expired(self) -> bool
```

**Test Cases:**
- Token acquisition with valid credentials
- Token refresh before expiration
- Error handling for invalid credentials
- Environment variable fallback

**Dependencies:** None (can start immediately)

**Estimated LOC:** ~80-100

---

### DRONE-B: Dovetail API Client

**File:** `src/dovetail_client.py`

**Tasks:**
1. Implement base HTTP client with auth injection
2. GET /authorization endpoint for discovery
3. GET /authorization/podcasts with pagination
4. GET /authorization/episodes with `?since=` support
5. GET /podcasts/{id}/guids/{guid} for direct lookup
6. Response parsing into existing `Episode` dataclass

**Deliverables:**
```python
# src/dovetail_client.py
class DovetailAPIError(Exception): ...

class DovetailClient:
    def __init__(self, auth_client: PRXAuthClient, api_base_url: str)
    def get_podcasts(self, page: int = 1, per: int = 50) -> list[dict]
    def get_episodes(self, since: Optional[datetime] = None, page: int = 1) -> list[Episode]
    def get_episode_by_guid(self, podcast_id: str, guid: str) -> Optional[Episode]
    def _parse_api_episode(self, data: dict) -> Episode
```

**Test Cases:**
- Pagination handling
- Incremental sync with `since` parameter
- GUID lookup returns correct episode
- API error handling (401, 404, 429)
- Episode dataclass mapping accuracy

**Dependencies:**
- DRONE-A (PRXAuthClient) for authenticated requests

**Estimated LOC:** ~150-180

---

### DRONE-C: Configuration & CLI Updates

**File:** `src/config.py` (modify), `src/main.py` (modify)

**Tasks:**
1. Add new config fields for PRX API credentials
2. Add `--source api|rss` flag to sync command
3. Add `PRX_USE_API` environment variable
4. Update `.env.example` with new variables
5. Add `test-prx-connection` command

**Config Additions:**
```python
# In Config dataclass
prx_client_id: str = ""
prx_client_secret: str = ""
prx_podcast_id: str = ""  # e.g., "120" for TTBOOK
prx_api_base_url: str = "https://podcasts.dovetail.prx.org/api/v1"
prx_id_base_url: str = "https://id.prx.org"
use_dovetail_api: bool = False
```

**CLI Additions:**
```bash
# New flag
python -m src.main sync --source api    # Use Dovetail API
python -m src.main sync --source rss    # Use RSS feed (default)

# New command
python -m src.main test-prx-connection  # Verify PRX API access
```

**Dependencies:** None (can start immediately)

**Estimated LOC:** ~60-80 (config) + ~40-50 (CLI)

---

## Phase 2: Integration (Drone-D, after Phase 1 complete)

### DRONE-D: Integration & Testing

**Files:** `src/main.py` (modify), `tests/test_dovetail_client.py` (create)

**Tasks:**
1. Wire up DovetailClient in cmd_sync()
2. Implement source selection logic
3. Update StateTracker to store last sync timestamp
4. Create integration tests with mocked API responses
5. Create end-to-end test with staging API (if available)
6. Update documentation

**Integration Logic:**
```python
# In cmd_sync()
if config.use_dovetail_api or args.source == "api":
    auth = PRXAuthClient(config.prx_client_id, config.prx_client_secret, ...)
    api = DovetailClient(auth, config.prx_api_base_url)

    # Get last sync time from tracker
    last_sync = tracker.get_last_sync_time()
    episodes = api.get_episodes(since=last_sync)
else:
    episodes = get_episodes(config.prx_feed_url)  # Existing RSS path
```

**Test Coverage:**
- API source selection via CLI flag
- API source selection via config
- Fallback to RSS on API failure (optional enhancement)
- Incremental sync only fetches new episodes
- State tracker records sync timestamps

**Dependencies:**
- DRONE-A complete
- DRONE-B complete
- DRONE-C complete

**Estimated LOC:** ~100-120

---

## Orchestration Timeline

```
Time ──────────────────────────────────────────────────▶

Phase 1 (Parallel):
┌──────────────┐
│   DRONE-A    │  OAuth2 Client
│   ~1.5 hrs   │
└──────────────┘
┌──────────────────────┐
│      DRONE-B         │  Dovetail API Client
│      ~2-2.5 hrs      │  (can stub auth initially)
└──────────────────────┘
┌──────────────┐
│   DRONE-C    │  Config & CLI
│   ~1.5 hrs   │
└──────────────┘

Phase 2 (Sequential):
                        ┌──────────────────────┐
                        │      DRONE-D         │  Integration & Testing
                        │      ~2-2.5 hrs      │
                        └──────────────────────┘

                        ┌──────────────┐
                        │ CODE REVIEW  │  code-troubleshooter
                        │   ~30 min    │
                        └──────────────┘
```

---

## Conductor Checkpoints

### Checkpoint 1: Phase 1 Complete
**Gate Criteria:**
- [ ] `src/prx_auth.py` exists and passes unit tests
- [ ] `src/dovetail_client.py` exists with all endpoint methods
- [ ] `src/config.py` has new PRX fields
- [ ] `src/main.py` has `--source` flag and `test-prx-connection` command
- [ ] `.env.example` updated with new variables

### Checkpoint 2: Integration Complete
**Gate Criteria:**
- [ ] `python -m src.main sync --source api --dry-run` works
- [ ] Incremental sync respects `since` parameter
- [ ] `python -m src.main test-prx-connection` validates credentials
- [ ] Integration tests pass

### Checkpoint 3: Review Complete
**Gate Criteria:**
- [ ] code-troubleshooter has reviewed implementation
- [ ] No security issues with credential handling
- [ ] Error handling covers all failure modes
- [ ] Documentation updated

---

## Agent Prompts

### Conductor Initialization Prompt

```
You are The Conductor orchestrating the Dovetail API migration for prx-to-ghost-publisher.

Context:
- Project: /Users/markriechers/Developer/prx-to-ghost-publisher
- Plan: /Users/markriechers/Developer/prx-to-ghost-publisher/docs/DOVETAIL_API_MIGRATION_PLAN.md
- Existing code: src/feed_parser.py, src/config.py, src/main.py
- API docs: knowledge/prx/DOVETAIL_API.md

Your task:
1. Launch DRONE-A, DRONE-B, and DRONE-C in parallel for Phase 1
2. Monitor completion of each drone
3. When all Phase 1 drones complete, launch DRONE-D for integration
4. After DRONE-D completes, invoke code-troubleshooter for review
5. Report final status

Use the Task tool to spawn each drone with appropriate prompts from this plan.
```

### DRONE-A Prompt

```
You are DRONE-A implementing OAuth2 authentication for the PRX Dovetail API.

Project: /Users/markriechers/Developer/prx-to-ghost-publisher
API Docs: knowledge/prx/DOVETAIL_API.md

Create src/prx_auth.py with:
1. PRXAuthClient class with OAuth2 client credentials flow
2. Token caching and expiration handling
3. Automatic refresh before API calls
4. PRXAuthError exception class

Production endpoint: https://id.prx.org/token
Staging endpoint: https://id.staging.prx.tech/token

Include type hints and docstrings. Handle network errors gracefully.
```

### DRONE-B Prompt

```
You are DRONE-B implementing the Dovetail API client.

Project: /Users/markriechers/Developer/prx-to-ghost-publisher
API Docs: knowledge/prx/DOVETAIL_API.md
Existing Episode model: src/feed_parser.py (Episode dataclass)

Create src/dovetail_client.py with:
1. DovetailClient class that uses PRXAuthClient for auth
2. get_podcasts() - paginated podcast listing
3. get_episodes(since: Optional[datetime]) - incremental episode fetch
4. get_episode_by_guid(podcast_id, guid) - direct lookup
5. _parse_api_episode(data) - convert API response to Episode dataclass

API base: https://podcasts.dovetail.prx.org/api/v1

Map API fields to existing Episode dataclass. Maintain compatibility with
content_builder.py and ghost_client.py expectations.
```

### DRONE-C Prompt

```
You are DRONE-C updating configuration and CLI for Dovetail API support.

Project: /Users/markriechers/Developer/prx-to-ghost-publisher
Existing config: src/config.py
Existing CLI: src/main.py

Tasks:
1. Add to Config dataclass:
   - prx_client_id, prx_client_secret, prx_podcast_id
   - prx_api_base_url, prx_id_base_url
   - use_dovetail_api (bool, default False)

2. Add to CLI:
   - --source api|rss flag on sync command
   - test-prx-connection subcommand

3. Update .env.example with new variables

Maintain backward compatibility - RSS remains the default.
```

### DRONE-D Prompt

```
You are DRONE-D integrating the Dovetail API into the sync workflow.

Project: /Users/markriechers/Developer/prx-to-ghost-publisher

Prerequisites (verify these exist):
- src/prx_auth.py (PRXAuthClient)
- src/dovetail_client.py (DovetailClient)
- Updated src/config.py with PRX fields

Tasks:
1. In cmd_sync(), add source selection logic:
   - If --source api or config.use_dovetail_api: use DovetailClient
   - Otherwise: use existing RSS path

2. Update StateTracker to track last_sync_time for incremental sync

3. Implement test-prx-connection command handler

4. Create tests/test_dovetail_client.py with:
   - Mocked API response tests
   - Episode parsing validation
   - Error handling tests

Ensure the existing RSS path continues to work unchanged.
```

---

## Files Created/Modified

| File | Action | Drone |
|------|--------|-------|
| `src/prx_auth.py` | Create | DRONE-A |
| `src/dovetail_client.py` | Create | DRONE-B |
| `src/config.py` | Modify | DRONE-C |
| `src/main.py` | Modify | DRONE-C, DRONE-D |
| `.env.example` | Modify | DRONE-C |
| `tests/test_dovetail_client.py` | Create | DRONE-D |
| `docs/DOVETAIL_API_MIGRATION_PLAN.md` | Create | Conductor |
| `knowledge/prx/DOVETAIL_API.md` | Already created | - |

---

## Rollback Strategy

If issues arise post-migration:
1. Set `PRX_USE_API=false` in .env
2. Remove `--source api` from any automation
3. System reverts to RSS feed automatically

The RSS code path remains fully functional and tested.
