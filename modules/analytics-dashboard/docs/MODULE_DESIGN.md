# Module Design: analytics-dashboard

> **Path:** `modules/analytics-dashboard/`
> **Version:** 0.2.0
> **Maturity:** 5/10 (collectors stable; dashboard MVP in progress)
> **Language:** Python 3.11+ (collectors/importers/CLI), HTML+JS (dashboard frontend, planned)
> **Runtime:** stdlib + `requests` + `pyjwt` + `python-dotenv`
> **Last Updated:** 2026-05-18

---

## 1. Purpose

Collects and publishes Wonder Cabinet Productions audience analytics. Pulls Ghost CMS member/post data and PRX Dovetail episode catalogs via API; imports per-episode download numbers from manual PRX CSV exports (the Dovetail REST API doesn't expose downloads). Computes industry-standard metrics (drop+30 per episode, rolling 30/90-day show-wide totals) and renders a producer-facing **Show Stats Reference** that lives in Obsidian and Google Docs today, and will live as a single-file HTML dashboard tomorrow.

The producer-facing artifact answers one specific question — *"what figure should I use when negotiating peer-outlet promo swaps or talking to funders?"* — with a defensible methodology and a number ready to recall mid-conversation.

### Pipeline Position

```
PRX Dovetail API ─────────┐
                          ├──→ [ THIS MODULE ] ──→ Show Stats Reference (Obsidian + Google Doc)
PRX CSV exports (manual) ─┤                        Dashboard HTML (planned)
                          │                        /wc-analytics skill queries
Ghost CMS API ────────────┘
```

---

## 2. Architecture

```
┌─────────────────────┐      ┌─────────────────────────┐      ┌──────────────────────────┐
│   Data Sources      │ ──→ │   Snapshot Layer        │ ──→ │   Publication Surfaces    │
│                     │      │                         │      │                          │
│ - Ghost Admin API   │      │ data/ghost/*.json       │      │ - Obsidian note (REST)   │
│ - PRX Dovetail API  │      │ data/prx/*.json          │      │ - Google Doc (MCP)      │
│ - PRX CSV exports   │      │ data/prx/downloads/*.json│      │ - Dashboard HTML (TBD)  │
│                     │      │                         │      │                          │
└─────────────────────┘      └─────────────────────────┘      └──────────────────────────┘
                                       │
                                       ├──→ /wc-analytics skill (agentic queries)
                                       └──→ build-dashboard (publication filter, TBD)
```

### Components

| Component | File Path | Responsibility |
|-----------|-----------|----------------|
| Config | `src/config.py` | Load `.env.prod` / `.env.dev`, validate required vars, derive data dir |
| Manifest | `src/manifest.py` | Find latest dated snapshot for a source; list available snapshots |
| Ghost collector | `src/collectors/ghost.py` | Pull posts, members, newsletters via Admin API (JWT auth). Member growth history pending (#11) |
| PRX collector | `src/collectors/prx.py` | Pull podcast catalog + episode metadata via Dovetail REST (OAuth2 client credentials) |
| PRX CSV importer | `src/importers/prx_csv.py` | Parse daily-by-date and cumulative-by-days-since-drop CSVs, normalize to daily-by-calendar-date schema, compute drop_day / drop+7 / drop+30 / rolling totals |
| CLI | `src/cli.py` | Subcommands: `refresh [--source]`, `import-csv --dir`, future `build-dashboard --out` |
| Report template | `templates/show_stats_reference.md` | Canonical markdown layout for the Show Stats Reference, with `{{placeholder}}` markers |
| Publication filter (TBD #14) | `src/dashboard/publication_filter.py` | Strip drafts, sender emails, paid/comped counts from snapshots before bundling for dashboard deploy |
| Dashboard HTML (TBD #15) | `dashboard/index.html` (or similar) | Single-file interactive view reading `dist/data/*.json` |

---

## 3. Data Flow

1. **Ghost collector** (`refresh --source ghost`) calls Ghost Admin API endpoints (`/posts/`, `/members/`, `/newsletters/`), simplifies records, writes `data/ghost/YYYY-MM-DD.json`.
2. **PRX collector** (`refresh --source prx`) authenticates via OAuth2 client credentials, paginates Dovetail's HAL+JSON `/podcasts/{id}/episodes` for each configured podcast, writes simplified catalog to `data/prx/YYYY-MM-DD.json`.
3. **PRX CSV importer** (`import-csv --dir <path>`) reads any combination of 28-day cumulative + 30-day daily + 90-day daily exports from a directory, merges via guid keying (daily files win on conflicts; cumulative is fallback for episodes outside daily coverage), computes derived metrics, writes `data/prx/downloads/YYYY-MM-DD.json`.
4. **`/wc-analytics` skill** reads latest snapshots from `data/`, renders `templates/show_stats_reference.md` with placeholders filled from the snapshot, PUTs the result to the Obsidian note and pushes to the Google Doc via MCP.
5. **`build-dashboard` (TBD)** runs the publication filter against the latest snapshots, outputs sanitized JSON to `dist/data/`, copies `dashboard/index.html` into `dist/`.
6. **Dashboard HTML (TBD)** fetches `data/downloads.json` and `data/ghost.json` at page load, renders three hero numbers + suggested phrasing + methodology + member growth sparkline.

---

## 4. CLI Interface

```bash
# Refresh API-sourced snapshots (Ghost + PRX catalog)
python -m src.cli refresh [--source ghost|prx] [--env dev|prod]

# Import PRX download CSV exports
python -m src.cli import-csv --dir <path-to-csv-folder> [--show wonder-cabinet]

# (TBD #14) Build deployable dashboard bundle
python -m src.cli build-dashboard --out dist/ [--show wonder-cabinet]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | (all) | Limit refresh to one source |
| `--env` | `prod` | Which `.env.<env>` file to load |
| `--dir` | _(required)_ | Path to folder of PRX CSV exports |
| `--show` | `wonder-cabinet` | Show slug (forward-looking; today only WC has CSV exports) |
| `--out` | `dist/` | Output dir for dashboard bundle |

---

## 5. Configuration

### From `.env.prod` / `.env.dev`

| Variable | Required | Description |
|----------|----------|-------------|
| `GHOST_URL` | Yes | Ghost site URL (e.g. `https://wondercabinetproductions.com`) |
| `GHOST_ADMIN_API_KEY` | Yes | `key_id:hex_secret` format from Ghost integrations page |
| `PRX_CLIENT_ID` | Yes | PRX OAuth2 client ID (shared with prx-to-ghost-publisher) |
| `PRX_CLIENT_SECRET` | Yes | PRX OAuth2 client secret |
| `PRX_PODCAST_IDS` | Yes | Comma-separated Dovetail podcast IDs (`120,3329` for WC + Luminous) |
| `DATA_DIR` | No | Override for snapshot directory (default: `./data/`) |

### From `shows/<slug>/config.json`

Not currently read by this module. Future work: when a second show grows enough to warrant its own analytics surface, the dashboard build step should read `shows/<slug>/brand.json` for the hero typography / color treatment.

---

## 6. Dependencies

### System Requirements

- Python 3.11+
- macOS Keychain (for Obsidian Local REST API key, when publishing)
- Obsidian Local REST API plugin running on `localhost:27124` (when publishing to Obsidian)
- Google Docs MCP server configured (when publishing to Google Doc — see `/refresh-google-creds` skill)

### Packages

Listed in `pyproject.toml`: `pyjwt>=2.8.0`, `requests>=2.31.0`, `python-dotenv>=1.0.0`. Dev: `pytest>=7.0.0`.

### External Services

| Service | Purpose | Auth Method |
|---------|---------|-------------|
| Ghost Admin API | Posts, members, newsletters | JWT signed with key from `GHOST_ADMIN_API_KEY` |
| PRX Dovetail | Episode catalog metadata | OAuth2 client credentials |
| Obsidian Local REST API | Publish Show Stats Reference note | Bearer token from macOS Keychain |
| Google Docs API (via MCP) | Publish Show Stats Reference doc | OAuth2 user grant, refreshed via `refresh-google-creds` skill |

---

## 7. Error Handling

| Error | Detection | Recovery |
|-------|-----------|----------|
| Expired Ghost JWT | 401 from Ghost API | Regenerate from `GHOST_ADMIN_API_KEY` (already done per-request) |
| Expired PRX token | 401 from Dovetail | One retry after re-auth; raise after |
| Invalid CSV shape | Header doesn't match daily or cumulative pattern | `PRXCSVImporterError` raised — log and skip the file |
| Missing 30-day data for new episode | `days_since_release < 30` | Flag `drop_plus_30` as incomplete; don't surface in averages |
| Google MCP `invalid_grant` | Token cached in MCP server is stale | Run `/refresh-google-creds`, restart Claude Code |
| Obsidian API unreachable | Connection refused on `localhost:27124` | Log warning, skip Obsidian publish, continue with Google Doc |

### Gotchas

- **Dovetail does not expose download numbers via API.** Per-episode listen data is web-UI-export only. PRX support explicitly states this. Documented in `src/collectors/prx.py` docstring.
- **Spotify listens are NOT in PRX downloads.** Spotify caches audio on their own infrastructure; Dovetail's user-agent-based platform breakdown can't see them. Total reach is undercounted by the Spotify share (typically 30–50% for shows like WC). Tracked as Issue #74.
- **iOS 17 download cliff (Oct 2023).** Apple paused auto-downloads for inactive followers; industry-wide 15–25% step-down in measured downloads. Cross-era comparisons must flag this.
- **PRX's "28-day" export is non-standard.** Industry-standard episode comparison window is 30 days (Buzzsprout, Libsyn, Castos). The importer derives drop+30 from the 90-day daily file rather than trusting PRX's 28-day cumulative output.
- **Snapshot files are gitignored.** Only schemas and importers are version-controlled; data is local-only on the SSD. Re-runnable via API + CSV exports.
- **MCP server caches OAuth tokens at startup.** Refreshing the token on disk does NOT propagate to the running MCP server. Claude Code must be restarted after `/refresh-google-creds`.

---

## 8. Claude Code Skills

### Skills

| Skill | Description | Trigger |
|-------|-------------|---------|
| `/wc-analytics` | Refresh data, analyze, and publish the Show Stats Reference | Manual invocation or any time the user mentions WC analytics / "fresh data" / a producer ping |

### Skill Design Notes

The `/wc-analytics` skill is currently the *operational* surface for this module — until the dashboard MVP ships, the skill is what producers see (indirectly, via the Obsidian note and Google Doc the skill keeps current).

Skill responsibilities:
1. Run data refresh (Ghost + optional PRX CSV import)
2. Load latest snapshots
3. Answer the user's question (if any) using the data
4. **Publish the Show Stats Reference** to Obsidian + Google Doc when fresh data has been imported
5. Recommend 2–3 actionable observations

The skill should NOT republish identical content on every invocation — only when fresh data has changed something. Republishing on every call creates timestamp noise in Drive and the Obsidian backlinks index.

---

## 9. Current State vs Target State

| Area | Current | Target | Priority |
|------|---------|--------|----------|
| Ghost collector | Pulls posts + member counts + newsletters | Also pulls member growth history (monthly cumulative) | **High** (Issue #11) |
| PRX downloads | Daily-by-date snapshot, drop+30 / rolling 30/90 computed | Same + Apple platform breakdown via Dovetail user-agent | Medium (Issue #73) |
| Spotify listens | Not captured | Manual CSV import mirror of PRX importer | Low (Issue #74) |
| Producer surface | Obsidian note + Google Doc, manually maintained | Skill auto-publishes after refresh | **High** (Step 5 of `/wc-analytics`) |
| Dashboard MVP | Does not exist | Single-file HTML, three hero numbers, sparkline, methodology | **High** (this work) |
| Dashboard hosting | N/A | Cloudflare Pages behind Access | Medium (after local validation) |
| Multi-show support | WC only for CSV importer | Generalize to Luminous when episode count justifies | Low |
| Tests | 33 (collectors + importer) | Add PII-not-persisted regression for Ghost growth history | High (Issue #12) |

### Priority Actions

1. Extend Ghost collector with member growth history (#11) + PII regression test (#12) + refresh (#13)
2. Build publication filter (#14)
3. Build single-file HTML dashboard (#15) + local verification (#16)
4. (Later) Cloudflare Pages deploy with Access
5. (Later) Apple platform breakdown via Dovetail
6. (Later) Spotify Plays importer

---

## 10. Verification Checklist

After running the data pipeline + skill:

- [ ] `data/ghost/<today>.json` exists with `members.total > 0` and `member_growth_history` array (post-#11)
- [ ] `data/prx/downloads/<today>.json` exists with `show_totals.rolling_30d > 0` and at least one episode with `drop_plus_30` not in `incomplete_windows`
- [ ] `pytest` passes 33+ tests including PII regression
- [ ] Obsidian note at `3 - RESOURCES/WONDER CABINET DOCUMENTATION/WC — Show Stats Reference.md` reflects latest snapshot date
- [ ] Google Doc `1ez2k-oyrLYX8OuQKOMxIWuec9U3Kgx13NuvfoEyl9m4` reflects latest snapshot date and renders the rounded `~10,000` framing in the suggested phrasing
- [ ] (Post-#15) Dashboard HTML opens in a browser and shows three hero numbers without errors in the console

---

## 11. References

- Module README: `modules/analytics-dashboard/README.md`
- Repo CLAUDE.md: top-level conventions for the publishing suite
- Show configs: `shows/wonder-cabinet/config.json`, `shows/luminous/config.json`
- `/wc-analytics` skill: `~/.claude/skills/wc-analytics/skill.md`
- `/refresh-google-creds` skill: `~/.claude/skills/refresh-google-creds/skill.md`
- Brainstorm note: Obsidian → `2 - AREAS/Brainstorming/data viz/Wonder Cabinet Analytics Dashboard MVP.md`
- Open issues: [#73 Apple via Dovetail](https://github.com/Wonder-Cabinet-Productions/podcast-publishing-suite/issues/73), [#74 Spotify Plays](https://github.com/Wonder-Cabinet-Productions/podcast-publishing-suite/issues/74)
