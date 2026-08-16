# Audit: prx-to-ghost-publisher — 2026-08-15

**Scope:** full history (all refs) via mirror backup, re-verified against current upstream after
PRs #44/#55 merged
**Commits scanned:** 73 (gitleaks 8.30.1, `detect --redact`), ~20.9 MB
**Findings:** 71 raw → 1 after triage; **0 at HEAD**. Details held privately, not published with
this file.

## Triage summary

- **70 findings** were entropy false positives in `sample-data/ttbook-cache/*.html` — cached
  copies of public third-party web pages kept as test fixtures. Now suppressed at source by a
  `.gitleaks.toml` allowlist committed upstream, so future scans of this module produce signal
  rather than noise.
- **1 finding** was an example webhook secret in vendored Ghost/Stripe documentation
  (`knowledge/ghost/webhooks.md`). Confirmed by the repo owner as a dummy value. It read as a
  dummy to a human but not to an entropy scanner, so it was replaced upstream with a
  self-evidently fake placeholder.

A history scan still reports the original dummy in an old commit. It is a verified non-secret
and needs no remediation.

## Verdict

**clean** — import with full history

No live credential exists at HEAD or in history. Full history is safe to publish.

Signed off: automated audit + owner confirmation of the one ambiguous value, 2026-08-16
