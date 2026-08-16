# Generalized Base + Per-Organization Forks — Design

**Date:** 2026-08-15
**Status:** Draft, awaiting review
**Supersedes:** the submodule topology described in `CLAUDE.md` and `docs/agents/issue-tracker.md`

## Problem

`podcast-publishing-suite` exists three times with three different shapes, and none of the
repos' own documentation describes the actual state:

| Repo | Visibility | Issues | Fork graph | Branch | Content |
|---|---|---|---|---|---|
| `mriechers/podcast-publishing-suite` | public | enabled | **root** | `main` | 558 files, 2 commits; modules inlined, `shows/` empty |
| `public-media-work/podcast-publishing-suite` | public | **disabled** | fork of `mriechers` | `main` | identical 558-file tree, 3 commits — differs only by a README edit |
| `Wonder-Cabinet-Productions/podcast-publishing-suite` | **private** | 156 issues | **standalone** (`parent: null`) | **`master`** | full tree, submodules, both shows |

Module code lives in a fourth place again — six `mriechers/*` repos referenced by WCP's
`.gitmodules`. Three of those six no longer resolve, so a fresh
`git clone --recurse-submodules` of WCP fails today.

The goal is a single generalized base that organization-specific forks descend from, with
Wonder Cabinet Productions as the first downstream consumer and PBS Wisconsin as the second.

## Scope

**This document covers plumbing, not generalization.** Today's work is: pull all module code
into the base with its history, wire the related repos together so they can iterate, and retire
the standalone module repos. The base ends the day structurally correct and functionally
unchanged.

**In scope today:**

- preserving issues and PRs that decommissioning would destroy
- auditing the two private modules before they land in a public repo
- inlining module code into the base via `git subtree`
- pointing WCP and the PBSWI fork at the base, and removing dead submodule references
- correcting the repo docs that describe the topology being removed
- archiving the module repos

**Explicitly deferred** to a later generalization pass, which gets its own grilling session and
its own design doc: decoupling the code from Wonder Cabinet, the `shows/example/` fixture, and
actually achieving the code/data boundary described below. Nothing today depends on that work,
and today's work does not make it harder.

The boundary and topology sections below therefore describe the **destination**, recorded now so
the deferred pass has a target to aim at — not the state at end of day.

## Decisions

These were settled during brainstorming and are the spine of everything below.

1. **Base repo is `mriechers/podcast-publishing-suite`.** It is already the fork-graph root,
   already the parent of `public-media-work`, public, and has issues enabled. Its history is two
   commits, so there is nothing to untangle. Issues are tracked here.

   Note that base and the `public-media-work` fork are currently the *same tree* — the PBSWI
   fork holds no PBSWI content yet. All work below therefore happens on base; the fork's only
   job today is to merge from it (Phase 3).
2. **Code-only base, data-only forks.** The base holds all code plus a synthetic fixture show.
   A fork adds only data. Forks never edit shared code, which is what keeps base→fork merges
   conflict-free indefinitely. **This is the destination, not today's outcome** — today the base
   still carries Wonder Cabinet specifics throughout, and `shows/` stays empty.
3. **Modules are inlined permanently.** The standalone module repos are decommissioned.
   `modules/<name>/` becomes ordinary source in a monorepo.
4. **WCP becomes downstream via a second remote, not a GitHub fork.** It keeps its history,
   its 156 issues, its private status, and its production deploys.
5. **The base stays public, gated on a security audit** of the two currently-private modules
   before they are inlined. The audit is a blocking gate, not a formality.

## Target topology

```
mriechers/podcast-publishing-suite          (public, issues live here)
│   code only: modules/, frontend/, scripts/, tests/, docs/
│   shows/example/  ← synthetic fixture, drives tests
│
├── public-media-work/podcast-publishing-suite   (GitHub fork)
│     + shows/<pbswi-shows>/
│
└── Wonder-Cabinet-Productions/…               (separate repo, `base` remote)
      + shows/wonder-cabinet/, shows/luminous/
```

Code flows one direction only: base → forks, by merge. A fix made in a fork is not a fix;
it is drift. Fixes go to base and come back down.

## The code/data boundary

This boundary is the entire contract. If it holds, merges are trivial forever. If it leaks,
this design degrades into three diverging repos with extra steps.

**Base owns:** every module's source, the frontend, `scripts/`, `tests/`, generic docs,
CI, and `shows/example/` — a synthetic show with invented names used by the test suite.

**A fork owns, and base never contains:**

- `shows/<slug>/config.json` — service config (PRX IDs, Ghost routes, feed URLs)
- `shows/<slug>/brand.json` — colors, typography, schemes
- `shows/<slug>/assets/` — logos, backgrounds
- `shows/<slug>/glossary.json` — Whisper corrections; contains real personal names
- `frontend/branding.json` — white-label configuration
- org-specific documentation and runbooks

**Consequence, stated plainly:** the boundary does not hold today, and today's work does not
make it hold. Per this repo's own docs, `audiogram-tools` has Wonder Cabinet branding hardcoded
and the whisper-transcription scripts reference WC episodes by name. Roughly 30 tracked files in
the current checkout still carry WC references, including `frontend/branding.json`, six
`docs/superpowers/plans/*`, two Ghost postmortems, and
`modules/audiogram-tools/public/WC_S01_trailer.mp3`.

Achieving the boundary is refactoring, not file moves — it is the whole of the deferred
generalization pass, and the reason that pass deserves a grilling session rather than a
checklist. Recorded here so the target is written down while the context is fresh.

## Migration sequence

The ordering constraints are real. `git subtree` can only preserve module history while the
module repos still exist, and WCP breaks if repos it references are deleted first.
**Decommissioning is the last step, never the first.**

### Phase 0 — Preserve what deletion would destroy

Nothing here is reversible after the repos are gone.

**Ordering caveat:** the issue transfer below is gated on Phase 1's issue audit and runs after
it. Only the PR resolution and the unpushed-work check are genuinely first — the transfer is
listed here because it belongs to preservation, not because it runs before the gate.

- Merge or close the **2 open PRs** on `prx-to-ghost-publisher`. GitHub cannot transfer pull
  requests between repos; they are lost on archive.
- Transfer open and closed issues to the base with `gh issue transfer`: 53 open and 19 closed
  across `podcast-audiogram-tools` (11/2), `markbot` (9/0), `podcast-whisper-transcription`
  (5/1), `prx-to-ghost-publisher` (28/16). Transfers assign new issue numbers, so any `#n`
  cross-reference inside a body will point somewhere wrong afterward. Accepted.
- **Create the label vocabulary on base first.** Base has only GitHub's stock labels, and
  `gh issue transfer` silently drops any label the target repo lacks — so transferring before
  the labels exist quietly strips `type:`, `executor:`, and triage state from all 72 issues.
- Label transferred issues by origin module so they stay findable.
- Confirm no unpushed commits in any local module clone.

### Phase 1 — Security audit gate (blocks Phase 2 for the private modules)

Applies to `prx-to-ghost-publisher` (274 files, 68 commits) and
`podcast-whisper-transcription` (45 files, 19 commits).

Audit **both `HEAD` and full history** — `git subtree add` without `--squash` republishes every
historical commit, so a key deleted three commits ago still becomes public. Scan for:

- credentials of any kind: Ghost Admin API keys, PRX API tokens, service-account JSON,
  `.env` files, OAuth client secrets
- private infrastructure: internal hostnames, webhook URLs, Slack tokens
- personal data: real names, contributor emails, unreleased episode content
- anything that reads as a client deliverable rather than a tool

Each module needs a written sign-off before it moves. **If history is not clean, inline that
module with `git subtree add --squash`**, accepting the loss of its history in exchange for not
publishing the bad commits. This choice is made per module, at audit time.

**The same gate applies to issues, not just code.** Transferring an issue out of a private repo
into a public one publishes its title, body, and every comment — 44 issues on
`prx-to-ghost-publisher` and 6 on `podcast-whisper-transcription`. Each is cleared to transfer
as-is, edited then transferred, or left behind. This is a second sign-off, gating Phase 0's
transfer step rather than Phase 2's import.

Both already-public modules (`podcast-audiogram-tools`, `markbot`) skip both gates.

### Phase 2 — Refresh the base's module code

The base already contains `modules/`, but as a flattened snapshot with no module history and
no link to the module repos. Those repos are ahead of it: `prx-to-ghost-publisher` was pushed
2026-08-15, while the snapshot is two commits old. So this phase *replaces* rather than seeds.

Per cleared module, in one commit each:

1. `git rm -r modules/<name>` — `git subtree add` refuses to write into an existing path.
2. `git subtree add --prefix=modules/<name> <module-repo> main`, or with `--squash` when
   Phase 1 did not affirmatively clear that module's history.
3. Diff the result against the removed snapshot and read it. A surprise here means the
   snapshot carried local edits that were never pushed upstream — recover them before moving on.

Then:

- Keep `analytics-dashboard` as-is. It has no upstream repo, so its current content is
  authoritative and there is nothing to subtree from.
- **Drop `robo-social` and `podcast-production-schedule`.** The former is a 1-file placeholder
  whose repo no longer resolves; the latter is an empty submodule with no HEAD. Neither has
  content to preserve. Re-create them as normal directories if and when they are actually built.
- Keep the existing root shell unchanged: `shows/` is already empty, MIT licensed, public.

### Phase 3 — Wire the related repos together

This is the "set up for future iteration" half of today. No code changes — only remotes,
references, and the docs that describe them.

- **WCP**: remove `.gitmodules` and every submodule gitlink, add `base` as a second remote, and
  take a first merge from it. Three of its seven submodule entries already point at repos that
  no longer resolve, so this also fixes a clone that is broken today.
  **WCP keeps `master`.** Branch names do not have to match for `git merge base/main` to work,
  and renaming a production repo's default branch breaks deploys, CI triggers, and integrations
  for no benefit this design needs. The convention against force-pushing `master` stands.
- **`public-media-work`**: merge base. Leave issues disabled — issues live on base.
- **Docs**: correct `CLAUDE.md` and `docs/agents/issue-tracker.md`. Both currently describe the
  submodule topology this phase removes, including an issue-routing rule ("running `gh` from
  inside `modules/<name>` targets that module's repo") that stops being true today. This is not
  deferrable with the rest of the generalization: leaving it stale would route issues to
  archived repos.

### Phase 4 — Decommission

**Archive the four module repos; do not delete them.** Archiving is read-only, preserves issue
history and stars, and can be undone. Deletion is permanent and frees the name for anyone to
claim. Add a README pointer to the base first. This phase runs only after Phase 3, once no repo
references any module repo.

## Deferred — the generalization pass

Its own grilling session and its own design doc, using the `mattpocock-skills:grilling` and
`brainstorming` skills against the base repo. The work, as understood today:

- replace hardcoded show values with reads from `shows/<slug>/`, one module per PR
- add `shows/example/` and point the test suite at it
- scrub the ~30 WC-referencing files
- move `shows/wonder-cabinet/` and `shows/luminous/` out of base's reach for good

Deferring this costs nothing today. It gets harder only if a fork starts patching shared code
in the meantime — see Risks.

## Verification

**Today:**

- Every module directory in base has real history: `git log --oneline modules/<name>` shows the
  module's commits, not a single squashed import (except where Phase 1 chose `--squash`).
- `git clone --recurse-submodules` of WCP succeeds — it fails today.
- No `.gitmodules` remains in any of the three repos, and `grep -r "mriechers/podcast-" ` finds
  no live submodule URLs.
- All 53 open issues are reachable on base, and the 2 `prx-to-ghost-publisher` PRs are merged or
  closed, before any repo is archived.
- Each module's test suite passes at its new location exactly as it did in its own repo. Today
  changes location, not behavior, so any new failure is an inlining defect.

**At the destination** (deferred pass, recorded so it is not relitigated):

- a fresh clone of base, with no fork data, runs the suite green against `shows/example/`
- `grep -ri "wonder cabinet\|wondercabinet\|luminous"` over base returns nothing outside
  intentionally-kept historical `docs/`
- WCP publishes a real episode using only base code plus its own `shows/` data
- a trivial change on base merges into both forks with zero conflicts

## Risks

- **The audit misses something.** Public is permanent, and this is the one irreversible step
  taken today. Mitigation: `--squash` is the default posture for any module whose history is not
  affirmatively cleared.
- **Deferral becomes permanent, and forks start patching shared code.** The boundary is unbuilt,
  so nothing prevents WCP from editing module source directly — and every such edit is drift
  that the eventual generalization has to reconcile. Mitigation: until the deferred pass lands,
  treat base as the only place module code changes.
- **WCP reconciliation lands during production work.** Phase 3 touches a repo shipping real
  episodes. Mitigation: schedule against the episode calendar, and do it on a branch with a
  tested merge before touching `master`.
- **Inlining silently drops unpushed local work.** Several local clones exist across
  `~/Developer` and `~/developer`. Mitigation: Phase 0's unpushed-commit check, and Phase 2's
  diff-and-read step.

## Out of scope

Distinct from *deferred* above: these are not planned at all, rather than planned for later.

- Populating PBS Wisconsin shows in the `public-media-work` fork
- Plugin or extension-point architecture — revisit only if a third organization needs behavior
  that configuration cannot express
- Re-extracting any module into a standalone repo; decommissioning is a one-way decision
- Changing WCP's default branch, its visibility, or its 156 issues
