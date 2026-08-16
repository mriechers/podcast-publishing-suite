# Inline Modules & Wire Related Repos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull all live module code into the base repo with its history, wire WCP and the PBSWI fork to that base, and retire the standalone module repos — without changing any module's behavior.

**Architecture:** `git subtree add` each live module repo into `modules/<name>/` on a branch of the base repo, after a blocking security audit for the two private modules. Then strip WCP's dead submodule wiring and point it at base as a second remote. Archive the module repos last, once nothing references them.

**Tech Stack:** git (`subtree`, `remote`, `submodule`), `gh` CLI, pytest, npm/tsc.

**Spec:** `docs/superpowers/specs/2026-08-15-generalized-base-fork-topology-design.md`

## How to read this plan

**This is an infrastructure migration, not feature code — there are no failing unit tests to write.** The test cycle per task is instead:

1. **Verify the precondition** — prove the change has not already happened and the inputs are what the plan claims. If a precondition check surprises you, STOP; the plan is out of date.
2. **Act.**
3. **Verify the postcondition** — an exact command with an exact expected output.
4. **Commit.**

Where a module has a real test suite, running it green after inlining *is* the test. Today changes location, not behavior, so any new failure is an inlining defect — never "fix" it by editing module source.

## Global Constraints

- Base repo is `mriechers/podcast-publishing-suite` (public, `main`). All issues live here.
- WCP is `Wonder-Cabinet-Productions/podcast-publishing-suite` (private, **keeps `master`**). Never force-push `master`.
- PBSWI fork is `public-media-work/podcast-publishing-suite` (public, `main`, issues stay disabled).
- Live module repos, all default branch `main`: `mriechers/podcast-audiogram-tools` (public), `mriechers/markbot` (public), `mriechers/podcast-whisper-transcription` (**private**), `mriechers/prx-to-ghost-publisher` (**private**).
- **Archive module repos, never delete.**
- **`--squash` is the default posture** for any module whose history is not affirmatively cleared by the Task 3 audit.
- Do not generalize, de-Wonder-Cabinet, or refactor any module. That is a separate deferred pass.
- Working directory for all base-repo tasks: `/Users/mriechers/Developer/pbswi/podcast-publishing-suite`, on branch `chore/inline-modules`.

## File Structure

Most of this plan changes *repository wiring*, not files. The files that do change:

| File | Change | Task |
|---|---|---|
| `modules/audiogram-tools/` | replaced by subtree import | 7 |
| `modules/markbot/` | replaced by subtree import | 8 |
| `modules/podcast-whisper-transcription/` | replaced by subtree import | 9 |
| `modules/prx-to-ghost-publisher/` | replaced by subtree import | 10 |
| `modules/robo-social/` | deleted | 11 |
| `docs/agents/issue-tracker.md` | submodule-scoping rules removed | 12 |
| `CLAUDE.md` | module table + conventions corrected | 12 |
| WCP `.gitmodules` | deleted | 14 |
| `docs/audits/2026-08-15-*.md` | created (audit sign-offs) | 3, 4 |

---

### Task 1: Safety snapshot and working branch

Nothing later in this plan is safely reversible without this. Mirror clones capture every ref, including ones `gh` will not show you after archiving.

**Files:**
- Create: `~/backups/2026-08-15-module-repos/*.git` (5 mirror clones)

**Interfaces:**
- Produces: verified mirror backups at `~/backups/2026-08-15-module-repos/`; branch `chore/inline-modules` tracking `base/main`

- [ ] **Step 1: Verify precondition — no unpushed work in any local module clone**

Several clones of this project exist across `~/Developer` and `~/developer`. Confirm none holds commits that exist nowhere else.

```bash
for d in ~/Developer/podcast-publishing-suite ~/Developer/wonder-cabinet/podcast-publishing-suite ~/Developer/pbswi/podcast-publishing-suite; do
  for m in "$d"/modules/*/; do
    [ -d "$m/.git" ] || continue
    echo "--- $m"
    git -C "$m" status --porcelain
    git -C "$m" log --branches --not --remotes --oneline
  done
done
```

Expected: no output under any heading. Any commit listed by the `--not --remotes` line exists only on this disk — push it to its module repo before continuing.

- [ ] **Step 2: Take mirror backups**

```bash
mkdir -p ~/backups/2026-08-15-module-repos
cd ~/backups/2026-08-15-module-repos
for r in podcast-audiogram-tools markbot podcast-whisper-transcription prx-to-ghost-publisher; do
  git clone --mirror "git@github.com:mriechers/$r.git"
done
git clone --mirror git@github.com:Wonder-Cabinet-Productions/podcast-publishing-suite.git wcp.git
```

- [ ] **Step 3: Verify postcondition — backups are real and complete**

```bash
cd ~/backups/2026-08-15-module-repos
for g in *.git; do echo "$g: $(git -C "$g" rev-list --all --count) commits, $(git -C "$g" for-each-ref --format='%(refname)' | wc -l) refs"; done
```

Expected, matching the audit: `podcast-audiogram-tools` 38 commits, `markbot` 15, `podcast-whisper-transcription` 19, `prx-to-ghost-publisher` 68. `wcp.git` non-zero. A zero anywhere means the clone failed silently — re-run it.

- [ ] **Step 4: Create the working branch from base, not from the fork**

The current checkout's `origin` is the PBSWI fork, which is one README commit ahead of base. Branch from base so that commit does not ride along.

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
git remote rename upstream base
git fetch base
git checkout -b chore/inline-modules base/main
git remote -v
```

Expected: `base` → `mriechers/podcast-publishing-suite`, `origin` → `public-media-work/…`. The uncommitted spec and plan documents carry over to the new branch automatically.

- [ ] **Step 5: Commit the spec and this plan**

```bash
git add docs/superpowers/specs/2026-08-15-generalized-base-fork-topology-design.md \
        docs/superpowers/plans/2026-08-15-inline-modules-and-wire-repos.md
git commit -m "docs: design + plan for inlining modules and wiring related repos"
```

---

### Task 2: Resolve the two blocking pull requests

GitHub cannot transfer pull requests between repositories. PRs #55 and #44 on `prx-to-ghost-publisher` are lost the moment that repo is archived, so they are resolved first.

**Files:** none in this repo.

**Interfaces:**
- Depends on: Task 1 backups
- Produces: zero open PRs on `mriechers/prx-to-ghost-publisher`

- [ ] **Step 1: Verify precondition — exactly two open PRs**

```bash
gh pr list --repo mriechers/prx-to-ghost-publisher --state open --json number,title,headRefName
```

Expected: #55 (`fix/strip-duplicate-links-heading`) and #44 (`fix/silent-failures`). A different set means the repo moved since planning — re-read both before deciding.

- [ ] **Step 2: Read both PRs and decide, one at a time**

```bash
gh pr view 55 --repo mriechers/prx-to-ghost-publisher --comments
gh pr diff 55 --repo mriechers/prx-to-ghost-publisher
gh pr view 44 --repo mriechers/prx-to-ghost-publisher --comments
gh pr diff 44 --repo mriechers/prx-to-ghost-publisher
```

**This step needs a human decision — do not merge unreviewed code to make a checklist pass.** Both are bugfixes and both look worth keeping; #44 ("three silent-failure bugs in the publish pipeline") is the higher-value one. For each: merge if the diff is sound, or close it and open an equivalent issue on base capturing the intent so the work is not lost.

- [ ] **Step 3: Act on the decision**

```bash
# for a PR being kept:
gh pr merge 44 --repo mriechers/prx-to-ghost-publisher --squash
# for a PR being dropped — capture it first, then close:
gh issue create --repo mriechers/podcast-publishing-suite \
  --title "prx: strip producer-typed 'Links:' heading above links list" \
  --body "Carried over from closed PR mriechers/prx-to-ghost-publisher#55, which could not be transferred when that repo was archived. Original branch: fix/strip-duplicate-links-heading"
gh pr close 55 --repo mriechers/prx-to-ghost-publisher --comment "Closing ahead of repo archival; carried to base as an issue."
```

- [ ] **Step 4: Verify postcondition**

```bash
gh pr list --repo mriechers/prx-to-ghost-publisher --state open --json number --jq 'length'
```

Expected: `0`.

Merged PRs change `main`, so Task 10 will pick the merge up automatically — that is the correct ordering.

---

### Task 3: Audit gate — code history of the two private modules

**This is the only irreversible step in the plan.** Inlining a private module into a public repo publishes it, and `git subtree add` without `--squash` publishes *every historical commit*, so a key deleted three commits ago still ships.

**Files:**
- Create: `docs/audits/2026-08-15-prx-to-ghost-publisher.md`
- Create: `docs/audits/2026-08-15-podcast-whisper-transcription.md`

**Interfaces:**
- Depends on: Task 1 mirrors
- Produces: a per-module verdict of `clean` (full history import) or `not-clean` (`--squash`), consumed by Tasks 9 and 10

- [ ] **Step 1: Scan full history for credentials**

Run against the mirrors, which contain every ref including deleted branches.

```bash
cd ~/backups/2026-08-15-module-repos
for g in prx-to-ghost-publisher.git podcast-whisper-transcription.git; do
  echo "=========== $g"
  git -C "$g" log --all -p | grep -nEi \
    "(api[_-]?key|secret|passwd|password|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN)" \
    | head -60
done
```

- [ ] **Step 2: Scan for sensitive files ever added, even if later deleted**

```bash
cd ~/backups/2026-08-15-module-repos
for g in prx-to-ghost-publisher.git podcast-whisper-transcription.git; do
  echo "=========== $g"
  git -C "$g" log --all --diff-filter=A --name-only --format= | sort -u \
    | grep -iE "\.env$|\.env\.|credential|service.?account|\.pem$|\.p12$|\.key$|token|\.pfx$"
done
```

- [ ] **Step 3: Scan for personal and client data**

Beyond credentials, these repos may carry real names, contributor emails, and unreleased episode content — all of which become public.

```bash
cd ~/backups/2026-08-15-module-repos
for g in prx-to-ghost-publisher.git podcast-whisper-transcription.git; do
  echo "=========== $g"
  git -C "$g" log --all --format='%ae' | sort -u
  git -C "$g" log --all -p | grep -nEi "(ghost.*admin.*key|prx.*token|@wondercabinet|internal\.|\.local\b)" | head -30
done
```

If `gitleaks` is available, run `gitleaks detect --source <mirror> --no-git` as a second opinion. It is a supplement, not a replacement — a clean gitleaks run does not clear personal data.

- [ ] **Step 4: Write the verdict, one file per module**

**Split the findings from the sign-off.** The sign-off is committed and Task 13 pushes it to a
*public* repo — so "Ghost admin key in commit abc1234" would publish a map to the secret while
the mirror backups remain readable. Specific findings never go in the committed file.

Detailed findings go to the git-ignored workspace, one file per module:
`.superpowers/sdd/2026-08-15-inline-modules-and-wire-repos/audit-findings-<module>.md` —
file paths, commit SHAs, matched strings, all of it.

The committed sign-off at `docs/audits/2026-08-15-<module>.md` carries only:

```markdown
# Audit: <module> — 2026-08-15

**Scope:** full history (all refs) via mirror backup
**Commits scanned:** <n>
**Findings:** <count> — details held privately, not published with this file

## Verdict
**clean** — import with full history
<or>
**not-clean** — import with `--squash`; history stays in the mirror backup only

Signed off: <name>, 2026-08-15
```

Before this plan's workspace is deleted, move the findings files somewhere durable and private —
they are the only record of what was found.

- [ ] **Step 5: Verify postcondition — both verdicts exist**

```bash
ls docs/audits/2026-08-15-*.md
grep -h "^\*\*clean\|^\*\*not-clean" docs/audits/2026-08-15-*.md
```

Expected: two files, each with exactly one verdict line. **A module with no verdict file does not get inlined.**

- [ ] **Step 6: Commit**

```bash
git add docs/audits/
git commit -m "docs(audit): history sign-off for the two private modules ahead of public inlining"
```

---

### Task 4: Audit gate — issue bodies from the private repos

Transferring an issue out of a private repo into a public one publishes its title, body, and every comment. `prx-to-ghost-publisher` has 44 issues (28 open, 16 closed) and `podcast-whisper-transcription` has 6 (5 open, 1 closed). The spec's original audit gate covered only code; this closes the same hole for issues.

**Files:**
- Create: `docs/audits/2026-08-15-private-issue-transfer.md`

**Interfaces:**
- Produces: a per-repo list of issue numbers cleared to transfer, consumed by Task 6

- [ ] **Step 1: Dump every issue body and comment for review**

```bash
mkdir -p /tmp/issue-audit
for r in prx-to-ghost-publisher podcast-whisper-transcription; do
  gh issue list --repo "mriechers/$r" --state all --limit 200 \
    --json number,title,body,comments > "/tmp/issue-audit/$r.json"
done
```

- [ ] **Step 2: Scan for the same patterns as Task 3**

```bash
grep -nEi "(api[_-]?key|secret|password|ghp_|xox[baprs]-|@[a-z]+\.(com|org)|BEGIN [A-Z ]*PRIVATE KEY)" \
  /tmp/issue-audit/*.json | head -40
```

- [ ] **Step 3: Read the flagged issues in full and decide each**

Three outcomes per issue: **transfer as-is**, **edit then transfer** (strip the sensitive part, keeping the issue useful), or **do not transfer** (leave it to die with the archived repo, or re-file a sanitized version on base). Record every decision.

- [ ] **Step 4: Write the sign-off**

Same split as Task 3: the reasons an issue was withheld describe the sensitive content, so they
stay private. The committed file carries the number lists — which are needed by Task 6 — and no
reasons.

Committed at `docs/audits/2026-08-15-private-issue-transfer.md`:

```markdown
# Audit: private-repo issue transfer — 2026-08-15

## prx-to-ghost-publisher (44 issues)
- Cleared to transfer: <numbers>
- Edit before transfer: <numbers>
- Do not transfer: <numbers>

## podcast-whisper-transcription (6 issues)
- Cleared to transfer: <numbers>
- Edit before transfer: <numbers>
- Do not transfer: <numbers>

Reasons and redactions held privately, not published with this file.

Signed off: <name>, 2026-08-15
```

Per-issue reasons and the exact text to strip go to the git-ignored
`.superpowers/sdd/2026-08-15-inline-modules-and-wire-repos/audit-findings-issues.md`.

- [ ] **Step 5: Verify postcondition and commit**

```bash
test -f docs/audits/2026-08-15-private-issue-transfer.md && echo OK
git add docs/audits/2026-08-15-private-issue-transfer.md
git commit -m "docs(audit): issue-transfer sign-off for the private module repos"
```

Expected: `OK`. Every one of the 50 private-repo issues appears in exactly one of the three categories.

---

### Task 5: Create the label vocabulary on base

Base currently has only GitHub's stock labels (`bug`, `documentation`, `enhancement`, …). The 53 incoming issues carry `type:`/`executor:`/triage labels that do not exist there, and **`gh issue transfer` silently drops labels the target repo lacks.** Labels must exist before the transfer, not after.

**Files:** none.

**Interfaces:**
- Produces: the full label set on base, consumed by Task 6

- [ ] **Step 1: Verify precondition — base lacks the vocabulary**

```bash
gh label list --repo mriechers/podcast-publishing-suite --limit 50 --json name --jq '[.[].name] | join(", ")'
```

Expected: stock labels only, no `needs-triage` and no `type:` prefixes.

- [ ] **Step 2: Create the triage roles and the type/executor vocabulary**

These five names are canonical per `docs/agents/triage-labels.md` and must match verbatim.

```bash
R=mriechers/podcast-publishing-suite
gh label create needs-triage    --repo $R --color ededed --description "Maintainer needs to evaluate this issue"
gh label create needs-info      --repo $R --color fbca04 --description "Waiting on reporter for more information"
gh label create ready-for-agent --repo $R --color 5319e7 --description "Fully specified, ready for an AFK agent"
gh label create ready-for-human --repo $R --color 0e8a16 --description "Requires human implementation"
gh label create "type: bug"         --repo $R --color d73a4a --description "Something is not working"
gh label create "type: enhancement" --repo $R --color a2eeef --description "New feature or improvement"
gh label create "type: documentation" --repo $R --color 0075ca --description "Documentation update needed"
gh label create "executor: agent"   --repo $R --color 5319e7 --description "Best suited for AI agent execution"
gh label create agent-discovered    --repo $R --color f9d0c4 --description "Discovered by an AI agent during work"
```

`wontfix` already exists on base and is reused as-is.

- [ ] **Step 3: Create one origin label per module so transferred issues stay findable**

```bash
R=mriechers/podcast-publishing-suite
gh label create "module: audiogram-tools"  --repo $R --color c5def5 --description "Originated in podcast-audiogram-tools"
gh label create "module: markbot"          --repo $R --color c5def5 --description "Originated in markbot"
gh label create "module: whisper"          --repo $R --color c5def5 --description "Originated in podcast-whisper-transcription"
gh label create "module: prx-to-ghost"     --repo $R --color c5def5 --description "Originated in prx-to-ghost-publisher"
```

- [ ] **Step 4: Verify postcondition**

```bash
gh label list --repo mriechers/podcast-publishing-suite --limit 60 --json name --jq '[.[].name] | sort | join("\n")'
```

Expected: all five triage roles, three `type:`, one `executor:`, `agent-discovered`, four `module:`, and `wontfix` present.

---

### Task 6: Transfer issues to base

53 open and 19 closed issues across four repos. `gh issue transfer` moves one issue at a time and **assigns a new number in the target repo** — cross-references like "see #12" inside issue bodies will point at the wrong thing afterward. That is accepted; the origin labels from Task 5 are the mitigation.

**Files:** none.

**Interfaces:**
- Depends on: Task 4 clearances, Task 5 labels
- Produces: all cleared issues present on base

- [ ] **Step 1: Verify precondition — counts still match the plan**

```bash
for r in podcast-audiogram-tools markbot podcast-whisper-transcription prx-to-ghost-publisher; do
  echo -n "$r open: "; gh issue list --repo "mriechers/$r" --state open --limit 100 --json number --jq 'length'
done
```

Expected: 11, 9, 5, 28. A change means new issues arrived since planning — audit those before transferring.

- [ ] **Step 2: Label each issue at its origin, before it moves**

Labelling first means the origin survives the transfer without a second pass.

```bash
label_all() {  # $1 = repo, $2 = module label
  for n in $(gh issue list --repo "mriechers/$1" --state all --limit 200 --json number --jq '.[].number'); do
    gh issue edit "$n" --repo "mriechers/$1" --add-label "$2"
  done
}
label_all podcast-audiogram-tools "module: audiogram-tools"
label_all markbot "module: markbot"
label_all podcast-whisper-transcription "module: whisper"
label_all prx-to-ghost-publisher "module: prx-to-ghost"
```

If a label does not exist on the *source* repo, `gh issue edit` fails — create it there first with `gh label create`.

- [ ] **Step 3: Transfer the two public repos in full**

```bash
for n in $(gh issue list --repo mriechers/podcast-audiogram-tools --state all --limit 200 --json number --jq '.[].number'); do
  gh issue transfer "$n" mriechers/podcast-publishing-suite --repo mriechers/podcast-audiogram-tools
done
for n in $(gh issue list --repo mriechers/markbot --state all --limit 200 --json number --jq '.[].number'); do
  gh issue transfer "$n" mriechers/podcast-publishing-suite --repo mriechers/markbot
done
```

- [ ] **Step 4: Transfer only the cleared issues from the private repos**

Use the explicit number lists from the Task 4 sign-off. Do not loop over everything here — that is the whole point of the gate.

```bash
# replace with the cleared numbers from docs/audits/2026-08-15-private-issue-transfer.md
for n in <cleared-prx-numbers>; do
  gh issue transfer "$n" mriechers/podcast-publishing-suite --repo mriechers/prx-to-ghost-publisher
done
for n in <cleared-whisper-numbers>; do
  gh issue transfer "$n" mriechers/podcast-publishing-suite --repo mriechers/podcast-whisper-transcription
done
```

- [ ] **Step 5: Verify postcondition**

```bash
gh issue list --repo mriechers/podcast-publishing-suite --state all --limit 300 --json number --jq 'length'
gh issue list --repo mriechers/podcast-publishing-suite --state all --limit 300 --json labels \
  --jq '[.[].labels[].name] | map(select(startswith("module:"))) | group_by(.) | map({(.[0]): length}) | add'
```

Expected: total equals 13 (audiogram) + 9 (markbot) + cleared-private count. Every issue carries exactly one `module:` label.

---

### Task 7: Inline `audiogram-tools`

Public module, so no audit gate. Done first because it is the lowest-risk of the four and proves the mechanics.

**Files:**
- Modify: `modules/audiogram-tools/` (replaced wholesale)

**Interfaces:**
- Depends on: Task 1 branch
- Produces: the `git rm` → `subtree add` → diff-review → verify pattern reused by Tasks 8–10

- [ ] **Step 1: Verify precondition — the current directory is a flat snapshot with no module history**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
git log --oneline -- modules/audiogram-tools | wc -l
test -f .gitmodules && echo "UNEXPECTED: .gitmodules present" || echo "no .gitmodules (expected)"
```

Expected: a very small number (the snapshot import), and `no .gitmodules`.

- [ ] **Step 2: Record the snapshot for comparison**

```bash
git ls-tree -r HEAD --name-only -- modules/audiogram-tools | sort > /tmp/before-audiogram.txt
wc -l < /tmp/before-audiogram.txt
```

Expected: 97 files.

- [ ] **Step 3: Remove the snapshot — `subtree add` refuses to write into an existing path**

```bash
git rm -r --quiet modules/audiogram-tools
git commit -m "chore(audiogram-tools): remove flattened snapshot ahead of subtree import"
```

- [ ] **Step 4: Import with full history**

```bash
git subtree add --prefix=modules/audiogram-tools \
  git@github.com:mriechers/podcast-audiogram-tools.git main
```

- [ ] **Step 5: Verify postcondition — history arrived and content is close to the snapshot**

```bash
git log --oneline -- modules/audiogram-tools | wc -l          # expect ~38, not 1
git ls-tree -r HEAD --name-only -- modules/audiogram-tools | sort > /tmp/after-audiogram.txt
diff /tmp/before-audiogram.txt /tmp/after-audiogram.txt
```

A commit count near 38 confirms real history. **Read the diff rather than skimming it.** Files present before but absent after mean the snapshot carried local edits that were never pushed upstream — recover them from the Task 1 mirror before continuing. Files added are expected: upstream moved since the snapshot.

- [ ] **Step 6: Verify the module still builds**

```bash
cd modules/audiogram-tools && npm install && npm run typecheck; cd -
```

Expected: typecheck passes. This module has no test script; `tsc --noEmit` is the gate. If it fails, compare against the same command run in the Task 1 mirror — a failure that reproduces there is pre-existing and not yours to fix today.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore(audiogram-tools): inline module with full history via subtree" --allow-empty
```

---

### Task 8: Inline `markbot`

Public module, no audit gate. Same pattern as Task 7, repeated in full because tasks are read out of order.

**Files:**
- Modify: `modules/markbot/` (replaced wholesale)

**Interfaces:**
- Depends on: Task 7 pattern

- [ ] **Step 1: Record the snapshot**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
git ls-tree -r HEAD --name-only -- modules/markbot | sort > /tmp/before-markbot.txt
wc -l < /tmp/before-markbot.txt
```

Expected: 9 files.

- [ ] **Step 2: Remove the snapshot**

```bash
git rm -r --quiet modules/markbot
git commit -m "chore(markbot): remove flattened snapshot ahead of subtree import"
```

- [ ] **Step 3: Import with full history**

```bash
git subtree add --prefix=modules/markbot git@github.com:mriechers/markbot.git main
```

- [ ] **Step 4: Verify postcondition**

```bash
git log --oneline -- modules/markbot | wc -l          # expect ~15, not 1
git ls-tree -r HEAD --name-only -- modules/markbot | sort > /tmp/after-markbot.txt
diff /tmp/before-markbot.txt /tmp/after-markbot.txt
```

Read the diff. Missing files mean unpushed local work — recover from the mirror.

- [ ] **Step 5: Run the module's tests**

```bash
cd modules/markbot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
deactivate && cd -
```

Expected: pass. A failure that also reproduces in the Task 1 mirror is pre-existing — record it as an issue on base, do not fix it here.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore(markbot): inline module with full history via subtree" --allow-empty
```

---

### Task 9: Inline `podcast-whisper-transcription`

**Gated on Task 3.** Private module going into a public repo.

**Files:**
- Modify: `modules/podcast-whisper-transcription/` (replaced wholesale)

**Interfaces:**
- Depends on: Task 3 verdict for this module

- [ ] **Step 1: Verify the gate — refuse to proceed without a verdict**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
grep -E "^\*\*(clean|not-clean)" docs/audits/2026-08-15-podcast-whisper-transcription.md
```

Expected: exactly one verdict line. **No verdict, no import — stop and finish Task 3.**

- [ ] **Step 2: Record the snapshot**

```bash
git ls-tree -r HEAD --name-only -- modules/podcast-whisper-transcription | sort > /tmp/before-whisper.txt
wc -l < /tmp/before-whisper.txt
```

Expected: 45 files.

- [ ] **Step 3: Remove the snapshot**

```bash
git rm -r --quiet modules/podcast-whisper-transcription
git commit -m "chore(whisper): remove flattened snapshot ahead of subtree import"
```

- [ ] **Step 4: Import, honoring the verdict**

If the verdict is **clean**:

```bash
git subtree add --prefix=modules/podcast-whisper-transcription \
  git@github.com:mriechers/podcast-whisper-transcription.git main
```

If the verdict is **not-clean** — this collapses the module to a single commit, which is the intended trade:

```bash
git subtree add --squash --prefix=modules/podcast-whisper-transcription \
  git@github.com:mriechers/podcast-whisper-transcription.git main
```

- [ ] **Step 5: Verify postcondition**

```bash
git log --oneline -- modules/podcast-whisper-transcription | wc -l
git ls-tree -r HEAD --name-only -- modules/podcast-whisper-transcription | sort > /tmp/after-whisper.txt
diff /tmp/before-whisper.txt /tmp/after-whisper.txt
```

Expected: ~19 commits under a **clean** verdict, 1–2 under **not-clean**. A count near 19 when the verdict was not-clean means `--squash` was forgotten — **reset the branch and redo it before pushing**, because pushing publishes the history the audit rejected.

- [ ] **Step 6: Run the module's tests**

```bash
cd modules/podcast-whisper-transcription
python3 -m venv .venv && source .venv/bin/activate
pip install -e . 2>/dev/null || pip install -r requirements.txt
pytest tests/ -v
deactivate && cd -
```

Expected: `test_apply_glossary.py` and `test_validate_episode.py` pass.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore(whisper): inline module via subtree" --allow-empty
```

---

### Task 10: Inline `prx-to-ghost-publisher`

**Gated on Task 3.** The largest and most active module — 274 files, 68 commits, pushed the day of planning. Task 2's merges are included automatically because this imports current `main`.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/` (replaced wholesale)

**Interfaces:**
- Depends on: Task 2 (PRs resolved), Task 3 verdict for this module

- [ ] **Step 1: Verify the gate**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
grep -E "^\*\*(clean|not-clean)" docs/audits/2026-08-15-prx-to-ghost-publisher.md
gh pr list --repo mriechers/prx-to-ghost-publisher --state open --json number --jq 'length'
```

Expected: one verdict line, and `0` open PRs.

- [ ] **Step 2: Record the snapshot**

```bash
git ls-tree -r HEAD --name-only -- modules/prx-to-ghost-publisher | sort > /tmp/before-prx.txt
wc -l < /tmp/before-prx.txt
```

Expected: 274 files.

- [ ] **Step 3: Remove the snapshot**

```bash
git rm -r --quiet modules/prx-to-ghost-publisher
git commit -m "chore(prx): remove flattened snapshot ahead of subtree import"
```

- [ ] **Step 4: Import, honoring the verdict**

Clean:

```bash
git subtree add --prefix=modules/prx-to-ghost-publisher \
  git@github.com:mriechers/prx-to-ghost-publisher.git main
```

Not-clean:

```bash
git subtree add --squash --prefix=modules/prx-to-ghost-publisher \
  git@github.com:mriechers/prx-to-ghost-publisher.git main
```

- [ ] **Step 5: Verify postcondition**

```bash
git log --oneline -- modules/prx-to-ghost-publisher | wc -l
git ls-tree -r HEAD --name-only -- modules/prx-to-ghost-publisher | sort > /tmp/after-prx.txt
diff /tmp/before-prx.txt /tmp/after-prx.txt
```

Expected: ~68 commits under **clean**, 1–2 under **not-clean**. The diff should show upstream additions since the snapshot, including whatever Task 2 merged. As in Task 9, a full history under a not-clean verdict means stop and redo before pushing.

- [ ] **Step 6: Run the module's test suite — 11 test files, the largest in the repo**

```bash
cd modules/prx-to-ghost-publisher
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pytest -v
deactivate && cd -
```

Expected: pass. `pyproject.toml` sets `testpaths = ["tests"]`, so bare `pytest` is correct. Compare any failure against the Task 1 mirror before touching source.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore(prx): inline module via subtree" --allow-empty
```

---

### Task 11: Prune the two dead module directories

`robo-social` is a 1-file placeholder whose repo no longer resolves. `podcast-production-schedule` is an empty submodule with no HEAD and is not present in this checkout at all. `analytics-dashboard` stays exactly as-is — it has no upstream repo, so its current content is authoritative and there is nothing to import.

**Files:**
- Delete: `modules/robo-social/`

**Interfaces:**
- Depends on: nothing

- [ ] **Step 1: Verify precondition — confirm there is nothing to lose**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
git ls-tree -r HEAD --name-only -- modules/robo-social
gh repo view mriechers/robo-social 2>&1 | head -2
ls modules/ | grep -c podcast-production-schedule
```

Expected: one or two placeholder files; `Could not resolve to a Repository`; `0`. **If the repo unexpectedly resolves, stop** — it has content, and this task's premise is wrong.

- [ ] **Step 2: Remove it**

```bash
git rm -r --quiet modules/robo-social
```

- [ ] **Step 3: Verify postcondition and commit**

```bash
ls modules/
git commit -m "chore(modules): drop robo-social placeholder; its repo no longer exists"
```

Expected `modules/` listing: `analytics-dashboard`, `audiogram-tools`, `markbot`, `podcast-whisper-transcription`, `prx-to-ghost-publisher`.

---

### Task 12: Correct the docs that describe the removed topology

This cannot wait for the deferred generalization pass. `docs/agents/issue-tracker.md` currently instructs agents that running `gh` inside `modules/<name>` targets that module's repo — after Task 16 those repos are archived, so following it files issues into archived repos.

**Files:**
- Modify: `docs/agents/issue-tracker.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Depends on: Tasks 7–11

- [ ] **Step 1: Verify precondition — the stale guidance is present**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
grep -n "Submodule scoping" docs/agents/issue-tracker.md
grep -n "submodule" CLAUDE.md | head
```

Expected: both match.

- [ ] **Step 2: Replace the submodule-scoping paragraph in `docs/agents/issue-tracker.md`**

Delete the `**Submodule scoping.**` paragraph entirely and put in its place:

```markdown
**Single repo, no submodules.** Module code lives inline under `modules/<name>/` in this
repository; the standalone module repos were archived on 2026-08-15. There is no per-module
repo to file against. Issues carried over from the archived repos keep a `module: *` label
recording where they came from.
```

- [ ] **Step 2b: Fix the tracker repo name — three lines still name the wrong repo**

`docs/agents/issue-tracker.md` line 3 and line 18, and `CLAUDE.md` line 104, all say issues live
on `Wonder-Cabinet-Productions/podcast-publishing-suite`. Tasks 5 and 6 made
`mriechers/podcast-publishing-suite` the tracker. Left alone, this plan ends with the docs
pointing at the wrong repo — the exact bug the original audit of this repo found.

This file flows base→forks, so one wording has to be true in every copy. Replace line 3 with a
routing rule rather than a repo name:

```markdown
Issues live in two places, by kind. **Code issues — anything about `modules/`, `frontend/`,
`scripts/`, or the pipeline itself — go to the base repo,
`mriechers/podcast-publishing-suite`.** Organization-specific operational issues (a given
episode, a show's content, a station's workflow) go to that organization's own tracker where it
has one; Wonder Cabinet Productions keeps its own. Use the `gh` CLI for all operations.
```

Then replace the line-18 paragraph (`**Always pass --repo …**`) with:

```markdown
**Always pass `--repo` explicitly.** The base repo is not necessarily a remote of the clone you
are standing in — a fork's `origin` points at the fork, and `gh` will infer that instead. Pass
`--repo mriechers/podcast-publishing-suite` for code issues.
```

And in `CLAUDE.md`, replace the `### Issue tracker` line under `## Agent skills`:

```markdown
Code issues go to the base repo `mriechers/podcast-publishing-suite` via the `gh` CLI — always
pass `--repo` explicitly. Organization-specific operational issues go to that org's own tracker.
See `docs/agents/issue-tracker.md`.
```

- [ ] **Step 3: Correct `CLAUDE.md`**

Three edits.

First, in the Directory Structure block, change the `modules/` comment:

```
├── modules/                          # Pipeline tools (inline source, not submodules)
```

Second, replace the Module Status table's header row and drop the now-meaningless middle column, keeping one row per surviving module:

```markdown
| Module | Status | Notes |
|--------|--------|-------|
| audiogram-tools | Active | Remotion compositions, galaxy spiral animations |
| podcast-whisper-transcription | Active | Whisper turbo, speaker diarization |
| prx-to-ghost-publisher | Active | Supports both shows, Ghost theme in development |
| markbot | Active | Centralized Slack bot |
| analytics-dashboard | Active | PRX CSV import, publication stats |
```

`robo-social` leaves the table; Task 11 deleted it.

Third, in Conventions, replace the submodule-cleanup bullet ("**Submodule cleanup**: removing a submodule requires cleaning 3 places…") with:

```markdown
- **Modules are inline** — `modules/<name>/` is ordinary source in this repo, imported via
  `git subtree` on 2026-08-15. There are no submodules and no `.gitmodules`; the former module
  repos are archived read-only. Do not re-extract a module into its own repo.
```

- [ ] **Step 4: Verify postcondition**

```bash
grep -c "Submodule scoping" docs/agents/issue-tracker.md              # expect 0
grep -c "Wonder-Cabinet-Productions" docs/agents/issue-tracker.md      # expect 0
grep -c "Wonder-Cabinet-Productions" CLAUDE.md                         # expect 0
grep -n "mriechers/podcast-publishing-suite" docs/agents/issue-tracker.md CLAUDE.md
grep -rn "module's own repo" docs/agents/issue-tracker.md
```

Expected: `0` for the first three. The fourth must show the base repo named in both files. The fifth should return nothing — no surviving instruction to file issues on a module repo.

- [ ] **Step 5: Commit**

```bash
git add docs/agents/issue-tracker.md CLAUDE.md
git commit -m "docs: modules are inline; drop submodule issue-routing guidance"
```

---

### Task 13: Push the branch and merge to base

**Files:** none.

**Interfaces:**
- Depends on: Tasks 7–12
- Produces: base `main` carrying all inlined modules

- [ ] **Step 1: Final pre-push check — this is the last moment before anything becomes public**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
git log --oneline base/main..HEAD
for m in podcast-whisper-transcription prx-to-ghost-publisher; do
  echo "$m: $(git log --oneline -- modules/$m | wc -l) commits"
done
grep -h "^\*\*clean\|^\*\*not-clean" docs/audits/2026-08-15-*.md
```

**Confirm by eye that each not-clean module shows 1–2 commits, not its full history.** After the push, this is no longer fixable by amending.

- [ ] **Step 2: Push and open the PR**

```bash
git push -u base chore/inline-modules
gh pr create --repo mriechers/podcast-publishing-suite \
  --base main --head chore/inline-modules \
  --title "chore: inline module code and wire related repos" \
  --body "Implements docs/superpowers/specs/2026-08-15-generalized-base-fork-topology-design.md, Phases 0-4. Module code imported via git subtree; no behavior changes. Generalization is deferred to a separate pass."
```

- [ ] **Step 3: Merge, preserving the imported history**

```bash
gh pr merge --repo mriechers/podcast-publishing-suite --merge
```

Use `--merge`. **Not `--squash`** — squashing the PR would collapse every module's imported history into one commit and undo Tasks 7–10.

- [ ] **Step 4: Verify postcondition**

```bash
git fetch base && git log --oneline base/main | head -20
git ls-tree base/main --name-only -- modules/
```

Expected: the merge is on `base/main`, and `modules/` lists the five surviving modules.

---

### Task 14: Wire WCP to base and remove its dead submodules

WCP is a production repo. Three of its seven submodule entries already point at repos that do not resolve, so `git clone --recurse-submodules` fails there today — this task fixes that as a side effect.

**Files:**
- Delete: WCP `.gitmodules`
- Modify: WCP submodule gitlinks

**Interfaces:**
- Depends on: Task 13

- [ ] **Step 1: Verify precondition — reproduce the broken clone**

```bash
cd /tmp && rm -rf wcp-check
git clone --recurse-submodules git@github.com:Wonder-Cabinet-Productions/podcast-publishing-suite.git wcp-check 2>&1 | tail -5
```

Expected: failure on `robo-social`, `podcast-production-schedule`, or `analytics-dashboard`. This is the "failing test" this task fixes.

- [ ] **Step 2: Branch from `master` — never work on it directly**

```bash
cd ~/Developer/wonder-cabinet/podcast-publishing-suite
git fetch origin && git checkout -b chore/depend-on-base origin/master
```

- [ ] **Step 3: Remove every submodule**

```bash
for m in audiogram-tools markbot podcast-whisper-transcription prx-to-ghost-publisher robo-social podcast-production-schedule analytics-dashboard; do
  git submodule deinit -f "modules/$m" 2>/dev/null
  git rm -f "modules/$m" 2>/dev/null
  rm -rf ".git/modules/$m"
done
git rm -f .gitmodules
```

Submodule cleanup touches three places — the index, `.gitmodules`, and `.git/modules/` — which is why all three appear above.

- [ ] **Step 4: Add base as a second remote and merge**

```bash
git remote add base git@github.com:mriechers/podcast-publishing-suite.git
git fetch base
git merge base/main --allow-unrelated-histories -m "chore: adopt base repo as upstream for module code"
```

`--allow-unrelated-histories` is required: WCP was never a fork of base, so the two histories share no ancestor. Expect conflicts on root files (`CLAUDE.md`, `README.md`, `docs/`). Resolve them in favor of **WCP's** versions for anything describing Wonder Cabinet operations, and **base's** for anything describing module code.

- [ ] **Step 5: Verify postcondition**

```bash
test -f .gitmodules && echo "FAIL: .gitmodules survives" || echo "OK: no .gitmodules"
ls modules/
git -C . log --oneline -- modules/prx-to-ghost-publisher | wc -l
```

Expected: `OK`, a populated `modules/` with real files rather than empty gitlink directories, and a non-trivial commit count.

- [ ] **Step 6: Confirm WCP still has its show data — this is what the fork exists for**

```bash
ls shows/wonder-cabinet/ shows/luminous/
```

Expected: `config.json`, `brand.json`, `assets/` under each. **If either is missing, the merge clobbered fork data — stop and re-resolve.**

- [ ] **Step 7: Push the branch and open a PR; do not merge to `master` unattended**

```bash
git push -u origin chore/depend-on-base
gh pr create --repo Wonder-Cabinet-Productions/podcast-publishing-suite \
  --base master --head chore/depend-on-base \
  --title "chore: depend on base repo for module code" \
  --body "Removes all submodules (three of which pointed at deleted repos) and adopts mriechers/podcast-publishing-suite as the code upstream. Show data unchanged."
```

This repo ships real episodes. A human merges this one, scheduled against the episode calendar.

---

### Task 15: Merge base into the PBSWI fork

**Files:** none.

**Interfaces:**
- Depends on: Task 13

- [ ] **Step 1: Merge and push**

```bash
cd /Users/mriechers/Developer/pbswi/podcast-publishing-suite
git checkout main
git fetch base origin
git merge base/main -m "chore: take inlined module code from base"
git push origin main
```

The fork and base differ only by one README commit, so this should be a fast-forward or a trivial merge.

- [ ] **Step 2: Verify postcondition**

```bash
git log --oneline -3
git ls-tree HEAD --name-only -- modules/
gh repo view public-media-work/podcast-publishing-suite --json hasIssuesEnabled --jq '.hasIssuesEnabled'
```

Expected: five modules, and `false` for issues — issues live on base by design, so leave this off.

---

### Task 16: Archive the module repos

Last, and only once nothing references them. **Archive, never delete** — archiving is read-only and reversible; deletion is permanent and frees the name for anyone to claim.

**Files:** none.

**Interfaces:**
- Depends on: Tasks 13, 14, 15

- [ ] **Step 1: Verify precondition — nothing references the module repos any more**

```bash
cd /tmp && rm -rf wcp-verify
git clone --recurse-submodules git@github.com:Wonder-Cabinet-Productions/podcast-publishing-suite.git wcp-verify 2>&1 | tail -3
grep -rn "mriechers/podcast-audiogram-tools\|mriechers/markbot\|mriechers/prx-to-ghost-publisher\|mriechers/podcast-whisper-transcription" \
  /Users/mriechers/Developer/pbswi/podcast-publishing-suite --include="*.md" --include="*.json" --include="*.yml" 2>/dev/null | grep -v docs/audits | grep -v docs/superpowers
```

Expected: the clone **succeeds** (it failed in Task 14 Step 1), and no live references outside the audit and planning docs, which are historical records and may keep them.

**Task 14's PR must be merged to `master` before this step.** If it is still open, stop — archiving now re-breaks WCP.

- [ ] **Step 2: Leave a pointer in each repo before archiving**

An archived repo is read-only, so the README must be updated first.

```bash
for r in podcast-audiogram-tools markbot podcast-whisper-transcription prx-to-ghost-publisher; do
  d=$(mktemp -d); git clone "git@github.com:mriechers/$r.git" "$d/$r" && cd "$d/$r"
  printf '\n> **Archived 2026-08-15.** This module now lives at `modules/%s/` in\n> https://github.com/mriechers/podcast-publishing-suite — file issues there.\n' "$r" >> README.md
  git add README.md && git commit -m "docs: point at podcast-publishing-suite ahead of archival" && git push
  cd - >/dev/null
done
```

- [ ] **Step 3: Archive**

```bash
for r in podcast-audiogram-tools markbot podcast-whisper-transcription prx-to-ghost-publisher; do
  gh repo archive "mriechers/$r" --yes
done
```

- [ ] **Step 4: Verify postcondition**

```bash
for r in podcast-audiogram-tools markbot podcast-whisper-transcription prx-to-ghost-publisher; do
  echo -n "$r archived: "; gh repo view "mriechers/$r" --json isArchived --jq '.isArchived'
done
ls ~/backups/2026-08-15-module-repos/
```

Expected: `true` four times, and the mirror backups still present. **Keep the backups until the deferred generalization pass is complete** — they are the only copy of any history a `--squash` import dropped.

---

## Done criteria

Mapping to the spec's "Today" verification:

- [ ] Each module directory shows real history (`git log --oneline modules/<name>`), except where Task 3 chose `--squash`
- [ ] `git clone --recurse-submodules` of WCP succeeds
- [ ] No `.gitmodules` in any of the three repos
- [ ] All cleared issues reachable on base; PRs #55 and #44 merged or closed before archival
- [ ] Each module's tests pass at its new location exactly as before
- [ ] The four module repos are archived, not deleted, each with a README pointer
