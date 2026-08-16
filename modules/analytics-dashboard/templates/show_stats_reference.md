# Wonder Cabinet — Show Stats Reference

Quick-recall numbers for producers in peer-outlet conversations (promo swaps, partnership discussions) and funder pitches. Snapshot from the analytics-dashboard module.

**Snapshot:** {{snapshot_date_human}} · refreshed roughly weekly

---

## The three numbers

- **{{avg_drop_plus_30}} downloads per episode** (first 30 days, 12-month average; range {{drop_plus_30_min}} – {{drop_plus_30_max}})
- **{{rolling_30d}} downloads per month** (rolling 30-day total, show-wide)
- **{{newsletter_total}} newsletter subscribers** ({{newsletter_delta_4w}} in the last 4 weeks, all free tier)

---

## How to say it

**For peer-outlet conversations (promo swaps, etc.):**
> "Wonder Cabinet averages {{avg_drop_plus_30}} downloads per episode in the first 30 days. Our strongest recent episodes have crossed {{drop_plus_30_max_rounded}}."

**If they want a monthly framing instead:**
> "We're at about {{rolling_30d}} downloads per month across the show, with another {{tail_60_90}} in the 60–90 day tail per episode."

**For funders or partners interested in audience depth:**
> "Beyond the podcast itself, we've built a direct relationship with our audience — {{newsletter_total}} newsletter subscribers as of {{snapshot_date_human}}, with steady organic growth ({{newsletter_delta_4w}} in the last four weeks)."

---

## Methodology (if asked)

Downloads measured via **PRX Dovetail**, IAB v2.2 compliant. The 30-day window is industry-standard (Buzzsprout, Libsyn, Castos).

Does **not** include Spotify listens — Spotify caches audio on their own infrastructure, so those plays are measured separately on Spotify's side and add to the totals here (a future integration will surface them).

iOS 17 (Oct 2023) paused auto-downloads for inactive followers, causing a 15–25% step-down in measured downloads industry-wide. Comparisons spanning that boundary need a flag.

---

## Detailed figures ({{snapshot_date_human}})

| Metric | Value | Notes |
| --- | --- | --- |
| Average drop+30 (completed episodes) | {{avg_drop_plus_30}} | 12-month average; range {{drop_plus_30_min}} – {{drop_plus_30_max}} |
| Rolling 30-day downloads | {{rolling_30d}} | Show-wide |
| Rolling 90-day downloads | {{rolling_90d}} | For longer-window framing |
| Newsletter subscribers (total) | {{newsletter_total}} | All free tier |
| Newsletter subscriber growth (last 4 weeks) | {{newsletter_delta_4w}} | {{newsletter_growth_rate}} organic |

### Top 5 episodes by drop+30

{{top_episodes_table}}

---

## How this note is maintained

- Snapshot data lives at `modules/analytics-dashboard/data/` on the SSD repo
- Refresh: `python -m src.cli refresh --source ghost` and `python -m src.cli import-csv --dir <PRX export>`
- After refresh, the `/wc-analytics` skill regenerates this report from this template and pushes it to both the Obsidian note (`3 - RESOURCES/WONDER CABINET DOCUMENTATION/WC — Show Stats Reference.md`) and the Google Doc (id: `1ez2k-oyrLYX8OuQKOMxIWuec9U3Kgx13NuvfoEyl9m4`)
- The dashboard MVP (in progress) will eventually surface this same content as a live web page

<!--
Placeholder reference (filled by /wc-analytics skill from the latest snapshot):
  snapshot_date_human        — e.g. "May 18, 2026"
  avg_drop_plus_30           — comma-formatted integer, e.g. "10,351"
  drop_plus_30_min/max       — comma-formatted, range of completed episodes over last 12 months
  drop_plus_30_max_rounded   — top performer rounded down to nearest 100, e.g. "12,700"
  rolling_30d                — comma-formatted, show-wide last-30-days
  rolling_90d                — comma-formatted, show-wide last-90-days
  tail_60_90                 — comma-formatted, approx (rolling_90d - rolling_30d), rounded
  newsletter_total           — comma-formatted, Ghost members.total
  newsletter_delta_4w        — signed e.g. "+48", change vs prior snapshot ~26-30 days back
  newsletter_growth_rate     — e.g. "~5%/month"
  top_episodes_table         — full markdown table, top 5 completed episodes by drop+30
-->
