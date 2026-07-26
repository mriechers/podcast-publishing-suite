"""Wonder Cabinet live-transcript speaker-label corrector.

Backfills producer-caught speaker-label corrections onto already-published WC
Ghost posts. Each correction is content-addressed by a distinctive *passage* of
dialogue plus the label it currently carries on the live page (``from_label``)
and the label it should carry (``to_label``) — exactly the shape of the
manifests under ``planning/transcript-corrections/<slug>.json``.

The patcher is deliberately surgical and fail-safe:

* It matches a passage by the same normalized key the provenance audit used, so
  it edits the *same* paragraph the audit flagged.
* It swaps **only** the ``<strong>Label:</strong>`` token of the matched
  paragraph; every other byte of the post is left identical.
* It refuses to touch a paragraph whose current label is neither ``from_label``
  nor ``to_label`` (``label-mismatch``) — that means the live page no longer
  matches our assumptions and a human must look.

Pure parse/swap logic lives here and is unit-tested. The Ghost GET-by-slug →
back up → PUT-by-id flow is thin I/O in :func:`correct_episode`, mirroring the
split in ``transcript_provenance.py`` and ``luminous_transcript_formatter.py``.

CLI::

    python -m src.wc_transcript_corrector --slug <slug> --dry-run   # diff only
    python -m src.wc_transcript_corrector --slug <slug>             # apply + PUT
    python -m src.wc_transcript_corrector --all --dry-run           # whole set
"""

from __future__ import annotations

import argparse
import difflib
import html as html_mod
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .transcript_provenance import _key, _speaker_equiv

logger = logging.getLogger(__name__)

# Where the reviewed correction manifests live (one JSON per slug + _INDEX.json).
_MANIFEST_DIR = (
    Path(__file__).resolve().parents[3]
    / "planning"
    / "transcript-corrections"
)

_PARA = re.compile(r"<p>(.*?)</p>", re.DOTALL)
# Leading speaker label of a rendered paragraph: ``<strong>Name:</strong>``.
_STRONG_LABEL = re.compile(r"^\s*<strong>\s*(.*?):\s*</strong>", re.DOTALL)
_FIRST_STRONG = re.compile(r"<strong>.*?:\s*</strong>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class LabelCorrection:
    """One reviewed speaker-label correction to apply to a live transcript."""

    passage: str
    from_label: str
    to_label: str


@dataclass
class CorrectionResult:
    """Outcome of attempting one correction against the live transcript."""

    correction: LabelCorrection
    status: str  # applied | already-correct | label-mismatch | passage-not-found | duplicate-passage
    found_label: Optional[str] = None


def corrections_from_manifest(manifest: dict) -> list[LabelCorrection]:
    """Map a ``planning/transcript-corrections/<slug>.json`` manifest into
    :class:`LabelCorrection` objects."""
    out: list[LabelCorrection] = []
    for c in (manifest or {}).get("corrections", []):
        out.append(
            LabelCorrection(
                passage=c["passage"],
                from_label=c["current_web_label"],
                to_label=c["correct_label"],
            )
        )
    return out


def _paragraph_label_and_body(inner_html: str) -> tuple[Optional[str], str]:
    """Split a ``<p>`` inner-HTML into (speaker label, plain-text dialogue).

    Returns ``(None, plain_text)`` for a paragraph with no leading speaker label.
    """
    m = _STRONG_LABEL.match(inner_html)
    if m:
        label = m.group(1).strip()
        body = inner_html[m.end():]
    else:
        label = None
        body = inner_html
    body_text = html_mod.unescape(_TAG.sub("", body))
    return label, body_text


def apply_label_corrections(
    transcript_html: str,
    corrections: list[LabelCorrection],
) -> tuple[str, list[CorrectionResult]]:
    """Apply speaker-label corrections to published transcript HTML.

    Returns ``(new_html, results)``. ``new_html`` differs from the input only in
    the ``<strong>`` label tokens of paragraphs that were actually ``applied``;
    everything else is byte-identical.
    """
    # Index paragraphs by the normalized key of their dialogue (first match wins,
    # matching the provenance audit's first-occurrence alignment).
    by_key: dict[str, dict] = {}
    for m in _PARA.finditer(transcript_html):
        label, body_text = _paragraph_label_and_body(m.group(1))
        k = _key(body_text)
        if k:
            by_key.setdefault(k, {"full": m.group(0), "label": label})

    result_html = transcript_html
    results: list[CorrectionResult] = []

    for c in corrections:
        match = by_key.get(_key(c.passage))
        if match is None:
            results.append(CorrectionResult(c, "passage-not-found"))
            continue

        found = match["label"]
        if found is not None and _speaker_equiv(found, c.to_label):
            results.append(CorrectionResult(c, "already-correct", found_label=found))
            continue
        if found is None or not _speaker_equiv(found, c.from_label):
            results.append(CorrectionResult(c, "label-mismatch", found_label=found))
            continue

        new_full = _FIRST_STRONG.sub(
            f"<strong>{html_mod.escape(c.to_label)}:</strong>",
            match["full"],
            count=1,
        )
        patched_html = result_html.replace(match["full"], new_full, 1)
        if patched_html == result_html:
            # The matched paragraph was already consumed by an earlier
            # correction sharing this passage key (by_key is indexed once from
            # the original HTML and never refreshed). The replace is a no-op, so
            # this is not a real "applied" — surface it for a human rather than
            # silently report a correction that never touched the page.
            results.append(CorrectionResult(c, "duplicate-passage", found_label=found))
            continue
        result_html = patched_html
        results.append(CorrectionResult(c, "applied", found_label=found))

    return result_html, results


# --------------------------------------------------------------------------
# Diff preview (pure; safety rail (b) from the correction plan)
# --------------------------------------------------------------------------

def unified_label_diff(before: str, after: str, slug: str) -> str:
    """A unified diff of before/after transcript HTML, one paragraph per line,
    for human approval before any PUT."""
    before_lines = [m.group(0) for m in _PARA.finditer(before)]
    after_lines = [m.group(0) for m in _PARA.finditer(after)]
    return "\n".join(
        difflib.unified_diff(
            before_lines, after_lines,
            fromfile=f"{slug} (live)", tofile=f"{slug} (corrected)",
            lineterm="",
        )
    )


# --------------------------------------------------------------------------
# Ghost I/O (thin; not unit-tested, mirrors luminous_transcript_formatter)
# --------------------------------------------------------------------------

def _extract_transcript_html(lexical_json: str) -> Optional[str]:
    """Return the ``episode-transcript`` HTML node from Ghost lexical content."""
    try:
        lexical = json.loads(lexical_json)
    except json.JSONDecodeError:
        return None
    for node in lexical.get("root", {}).get("children", []):
        if node.get("type") == "html":
            h = node.get("html", "")
            if 'class="episode-transcript"' in h or 'id="episode-transcript"' in h:
                return h
    return None


def _replace_transcript_html(lexical_json: str, new_html: str) -> str:
    lexical = json.loads(lexical_json)
    for node in lexical.get("root", {}).get("children", []):
        if node.get("type") == "html":
            h = node.get("html", "")
            if 'class="episode-transcript"' in h or 'id="episode-transcript"' in h:
                node["html"] = new_html
                break
    return json.dumps(lexical)


def load_manifest(slug: str) -> dict:
    """Read the reviewed correction manifest for ``slug``."""
    path = _MANIFEST_DIR / f"{slug}.json"
    return json.loads(path.read_text())


def correct_episode(
    client,
    slug: str,
    corrections: list[LabelCorrection],
    *,
    dry_run: bool = True,
    backup_dir: Optional[Path] = None,
) -> list[CorrectionResult]:
    """Fetch a live post by slug, apply corrections to its transcript, and
    (unless ``dry_run``) back up + PUT the result.

    Always prints a unified diff for human approval. Backs up the full original
    post payload to ``backup_dir`` before any write.
    """
    url = f"{client.api_url}/posts/slug/{slug}/"
    resp = client._session.get(url, headers=client._get_headers(), timeout=30)
    posts = client._handle_response(resp).get("posts", [])
    if not posts:
        logger.error("Post not found: %s", slug)
        return []

    post = posts[0]
    lexical = post.get("lexical", "")
    transcript_html = _extract_transcript_html(lexical) if lexical else None
    if not transcript_html:
        logger.error("No episode-transcript section in post: %s", slug)
        return []

    new_html, results = apply_label_corrections(transcript_html, corrections)

    print(f"\n=== {slug} ===")
    for r in results:
        snippet = r.correction.passage[:70] + ("…" if len(r.correction.passage) > 70 else "")
        line = f"  [{r.status}] {r.correction.from_label} -> {r.correction.to_label}: “{snippet}”"
        if r.status in ("label-mismatch", "passage-not-found", "duplicate-passage"):
            line += f"  (live label: {r.found_label})"
        print(line)

    applied = [r for r in results if r.status == "applied"]
    if not applied:
        print("  No applicable corrections; nothing to write.")
        return results

    diff = unified_label_diff(transcript_html, new_html, slug)
    if diff:
        print("\n--- diff ---\n" + diff)

    if dry_run:
        print(f"\n[DRY RUN] Would update {slug} ({len(applied)} label(s)).")
        return results

    backup_dir = backup_dir or (_MANIFEST_DIR / "backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (backup_dir / f"{slug}-{stamp}.json").write_text(json.dumps(post, indent=2))

    new_lexical = _replace_transcript_html(lexical, new_html)
    update_url = f"{client.api_url}/posts/{post['id']}/"
    payload = {"posts": [{"lexical": new_lexical, "updated_at": post["updated_at"]}]}
    update_resp = client._session.put(
        update_url, json=payload, headers=client._get_headers(), timeout=30
    )
    client._handle_response(update_resp)
    print(f"\nUpdated {slug} ({len(applied)} label(s)). Backup in {backup_dir}.")
    return results


def _index_slugs() -> list[str]:
    index = json.loads((_MANIFEST_DIR / "_INDEX.json").read_text())
    return [ep["slug"] for ep in index.get("episodes", [])]


def main():
    parser = argparse.ArgumentParser(
        description="Backfill producer speaker-label corrections to live WC transcripts"
    )
    parser.add_argument("--slug", help="Correct a single episode by slug")
    parser.add_argument("--all", action="store_true", help="Correct every episode in _INDEX.json")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually PUT changes to live Ghost. Without this flag the tool is "
        "dry-run (diff only) — the safe default, since these are live posts.",
    )
    parser.add_argument("--env", default="prod", choices=["dev", "prod"])
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")

    if not args.slug and not args.all:
        parser.error("Must specify --slug or --all")

    from .config import get_config
    from .ghost_client import GhostClient, GhostAPIError

    config = get_config(env_name=args.env)
    client = GhostClient(config.ghost_url, config.ghost_admin_api_key)
    try:
        client.test_connection()
    except GhostAPIError as e:
        logger.error("Failed to connect to Ghost: %s", e)
        sys.exit(1)

    slugs = [args.slug] if args.slug else _index_slugs()
    for slug in slugs:
        corrections = corrections_from_manifest(load_manifest(slug))
        correct_episode(client, slug, corrections, dry_run=dry_run)

    if dry_run:
        print("\n[DRY RUN] No changes were made to Ghost. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
