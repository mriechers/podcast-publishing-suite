# PRX-to-Ghost Publisher: Project Status & Remaining Work

**Last Updated**: 2026-01-09
**Status**: Theme Development Phase
**Target**: Production deployment to wondercabinetproductions.com

---

## Current State Summary

### Completed Work

| Component | Status | Notes |
|-----------|--------|-------|
| RSS Feed Parser | ✅ Complete | `src/feed_parser.py` - Episode dataclass, namespace handling |
| Dovetail API Client | ✅ Complete | `src/dovetail_client.py` + `src/prx_auth.py` - OAuth2 auth |
| Ghost Admin API Client | ✅ Complete | `src/ghost_client.py` - JWT auth, post creation |
| Content Builder | ✅ Complete | `src/content_builder.py` - Theme-hydrated audio player, pod.link |
| Content Transforms | ✅ Complete | `src/content_transforms.py` - Boilerplate removal |
| State Tracker | ✅ Complete | `src/state_tracker.py` - Duplicate prevention |
| Transcript Exporter | ✅ Complete | `src/transcript_exporter.py` - JSON/HTML export |
| CLI Interface | ✅ Complete | `src/main.py` - sync, dry-run, export-transcripts |
| Luminous Import | ✅ Complete | 19 episodes imported and published |
| Wonder Cabinet Test Data | ✅ Complete | 10 dummy episodes created |

### Test Environment

- **Ghost Dev Instance**: `http://192.168.5.156:2368`
- **Tunnel URL**: `https://dev-d414ccab.wondercabinetproductions.com`
- **Tunnel Script**: `~/Developer/ghost-dev/tunnel.sh` (run to re-establish if down)
- **Luminous Episodes**: 19 published
- **Wonder Cabinet Episodes**: 10 dummy (physicist guests)
- **Theme**: In active development

---

## Remaining Work to Deployment

### Phase 1: Theme Completion (IN PROGRESS)

**Owner**: Theme Developer Agent + User Review

| Task | Priority | Status | Notes |
|------|----------|--------|-------|
| Theme-hydrated audio player (wc-audio-player) | Critical | 🔄 In Progress | Using Wavesurfer/AmplitudeJS |
| Pod.link button styling | High | ⏳ Pending | CSS for `.podlink-button` |
| Transcript section styling | High | ⏳ Pending | Collapsible `#episode-transcript` div |
| Episode card layout | High | ⏳ Pending | Grid/list views for podcast pages |
| Homepage dual-show sections | Medium | ⏳ Pending | Latest from Luminous + Wonder Cabinet |
| Responsive design testing | Medium | ⏳ Pending | Mobile/tablet breakpoints |
| Dark mode support | Low | ⏳ Pending | Optional enhancement |

### Phase 2: Production Configuration

**Owner**: User (with agent assistance)

| Task | Priority | Status | Notes |
|------|----------|--------|-------|
| Create Ghost Admin integration on production | Critical | ⏳ Pending | wondercabinetproductions.com |
| Configure production API credentials | Critical | ⏳ Pending | Update `.env` or GitHub secrets |
| Create/verify Ghost tags | Critical | ⏳ Pending | `luminous`, `wonder-cabinet` |
| Deploy routes.yaml | Critical | ⏳ Pending | Collection routing |
| Upload finalized theme | Critical | ⏳ Pending | After theme complete |
| Test production connectivity | High | ⏳ Pending | Verify API access |

### Phase 3: Deployment Infrastructure

**Owner**: Agent (Conductor)

| Task | Priority | Status | Notes |
|------|----------|--------|-------|
| Create GitHub Actions workflow | High | ⏳ Pending | Cron + manual dispatch |
| Configure GitHub secrets | High | ⏳ Pending | GHOST_URL, GHOST_ADMIN_KEY |
| Set up health monitoring | Medium | ⏳ Pending | Healthchecks.io integration |
| Create deployment documentation | Medium | ⏳ Pending | Runbook for operations |

### Phase 4: Production Validation

**Owner**: User + Agent

| Task | Priority | Status | Notes |
|------|----------|--------|-------|
| Dry-run on production | Critical | ⏳ Pending | Test without publishing |
| Import single test episode | Critical | ⏳ Pending | Verify end-to-end |
| Verify audio player works | Critical | ⏳ Pending | Theme hydration test |
| Verify routing (/luminous/, /wonder-cabinet/) | Critical | ⏳ Pending | Collection pages work |
| Full Luminous import | High | ⏳ Pending | All 19 episodes |
| Full Wonder Cabinet import | High | ⏳ Pending | From PRX feed 120 |
| Enable scheduled automation | High | ⏳ Pending | Cron trigger |

### Phase 5: Post-Launch

**Owner**: User (ongoing)

| Task | Priority | Status | Notes |
|------|----------|--------|-------|
| Monitor first 24 hours | High | ⏳ Pending | Watch for failures |
| Confirm new episode auto-publishes | High | ⏳ Pending | Wait for real release |
| Document any issues found | Medium | ⏳ Pending | Update troubleshooting guide |
| API key rotation calendar | Low | ⏳ Pending | Annual rotation reminder |

---

## Agent Workflow Assignment

### The Conductor (Orchestration)
- Coordinate phase transitions
- Monitor progress across agents
- Unblock dependencies
- Final deployment coordination

### Theme Agent (adhd-friendly-ui-designer)
- Complete audio player styling
- Implement responsive layouts
- Create episode card components
- Handle accessibility requirements

### Drone Agents (Implementation)
- **Drone-A**: GitHub Actions workflow, deployment scripts
- **Drone-B**: Production configuration, routes.yaml
- **Drone-C**: Monitoring setup, health checks

### Investigator Agent (Verification)
- Production connectivity testing
- End-to-end validation
- Post-deployment monitoring

### Code Troubleshooter (Review)
- Review theme implementation
- Validate deployment scripts
- Catch over-engineering

---

## Critical Path to Deployment

```
CURRENT STATE
     │
     ▼
┌─────────────────────────────────────┐
│ Phase 1: Theme Completion           │ ← YOU ARE HERE
│ - Audio player styling              │
│ - Episode layouts                   │
│ - Responsive testing                │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ Phase 2: Production Config          │
│ - Ghost integration setup           │
│ - API credentials                   │
│ - Routes.yaml deployment            │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ Phase 3: Deployment Infrastructure  │
│ - GitHub Actions workflow           │
│ - Secrets configuration             │
│ - Monitoring setup                  │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ Phase 4: Production Validation      │
│ - Test import                       │
│ - Full content import               │
│ - Enable automation                 │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ Phase 5: LIVE                       │
│ - Monitor                           │
│ - Confirm auto-publish              │
└─────────────────────────────────────┘
```

---

## Audio Player Data Contract

The importer outputs this structure for theme hydration:

```html
<!--kg-card-begin: html-->
<div class="wc-audio-player"
     data-audio-url="https://dts.podtrac.com/redirect.mp3/..."
     data-episode-artwork="https://f.prxu.org/3329/.../image.png"
     data-episode-date="2025-11-08"
     data-episode-guest=""
     data-episode-description="Short description here"
     data-episode-duration="45:30"
     data-episode-guid="prx_3329_uuid-here">
</div>
<!--kg-card-end: html-->
```

Theme JavaScript should:
1. Find all `.wc-audio-player` divs
2. Read data attributes
3. Initialize chosen player library (Wavesurfer, AmplitudeJS, etc.)
4. Render player UI with episode metadata

---

## Quick Reference Commands

```bash
# Sync Luminous episodes (dry run)
python -m src.main sync --feed-type luminous --dry-run

# Sync and publish
python -m src.main sync --feed-type luminous --export-transcripts

# Sync with limit
python -m src.main sync --feed-type luminous --limit 5

# Test Ghost connection
python -m src.main test-ghost

# Test PRX API connection
python -m src.main test-prx-connection
```

---

## Environment Variables Required

```bash
# Ghost CMS (dev instance)
GHOST_URL=http://192.168.5.156:2368
GHOST_ADMIN_API_KEY=key_id:secret

# Ghost CMS (production - TBD)
# GHOST_URL=https://wondercabinetproductions.com
# GHOST_ADMIN_API_KEY=production_key_id:secret

# PRX Dovetail API (optional, for API mode)
PRX_CLIENT_ID=your_client_id
PRX_CLIENT_SECRET=your_client_secret
PRX_PODCAST_IDS=120,3329
PRX_USE_API=false
```

---

## Files Modified Since Last Roadmap

| File | Change |
|------|--------|
| `src/content_builder.py` | Added `build_audio_player_card()` with data attributes |
| `src/content_builder.py` | Added pod.link with Apple Podcasts ID lookup |
| `src/content_builder.py` | Added placeholder transcript filtering |
| `src/content_transforms.py` | Comprehensive boilerplate removal patterns |
| `data/published_episodes.json` | 19 Luminous episodes tracked |

---

*Document generated by Main Assistant for Conductor handoff*

## Pending Verification (Post-Deployment)

The following verification steps require the theme to be deployed and the importer running in production:

1. **Page Source Verification** - View source on a published post and search for `application/ld+json` to see the structured data in the `<head>`
2. **Google Rich Results Test** - Paste a published post URL at https://search.google.com/test/rich-results to validate the PodcastEpisode schema
3. **Search Console** - Monitor Google Search Console for rich result enhancements after indexing

**Completed Verification:**
- ✅ Ghost Admin UI shows only show-level tags (Luminous) per post
- ✅ RSS categories successfully moved to JSON-LD structured data
- ✅ 19 Luminous episodes migrated via `update-metadata` command
