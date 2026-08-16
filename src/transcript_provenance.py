"""Transcript provenance gate.

Confirms that the transcript about to be published (the pipeline's local
``formatted_transcript.md``) actually reflects the producer's speaker-label
edits, which live in a human-edited Google Doc on Drive.

Background: the publish path (``content_builder.load_*_transcript``) prefers
``formatted_transcript.md`` from the canonical episode folder. That file
reflects producer edits ONLY if ``/wc-transcript-update`` has already folded
the producer's Google-Doc edits back into it. Several early episodes shipped
raw pipeline speaker labels because that fold-back never happened before
publish (see planning/wonder-cabinet-speaker-flip-audit.md). This module is the
pre-publish gate that catches that: it diffs the local transcript's speaker
labels against the producer-edited Drive doc and HARD-BLOCKS on any divergence.

Pure parse/diff logic is unit-tested; the Drive fetch is thin I/O.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Canonical vocabulary of labels that appear as "Key: value" (or "**Key:** value")
# lines in formatted transcripts but are never speaker names — per the
# transcript-formatter agent spec, speaker labels are always First+Last, never a
# bare generic word like "Status".
#
# Single source of truth: content_builder imports this to build its
# trailing-metadata regex. Keep it a tuple — order is load-bearing there, where
# the labels become a regex alternation and a longer label must precede any
# prefix of itself ("Date Processed" before "Date") or the shorter one wins.
METADATA_LABELS = (
    "Status", "Duration", "Episode", "Guest", "Guests", "Hosts", "Host",
    "Project", "Program", "Date Processed", "Date", "Title", "Season",
    "Chapters", "Transcript", "Formatted Transcript",
)

# Metadata keys that look like "Key: value" but are not speaker turns.
_METADATA_KEYS = frozenset(label.lower() for label in METADATA_LABELS)

# Minimum normalized-key length for a turn to participate in alignment.
# Short lines ("Yeah.", "Right.") collide across a transcript and would produce
# spurious matches, so we only align on reasonably distinctive passages.
_MIN_KEY_LEN = 15


@dataclass(frozen=True)
class Divergence:
    """One passage where the local transcript and the producer doc disagree
    on who is speaking."""

    passage: str
    local_label: str
    producer_label: str


class TranscriptProvenanceError(Exception):
    """Raised to hard-block a publish when the local transcript does not
    reflect the producer's speaker-label edits."""

    def __init__(self, divergences: list[Divergence]):
        self.divergences = divergences
        lines = [
            f"Transcript provenance check FAILED: {len(divergences)} speaker-label "
            f"divergence(s) between the transcript about to be published and the "
            f"producer-edited Drive doc.",
            "The local formatted_transcript.md does NOT reflect the producer's edits.",
            "Fix: run /wc-transcript-update against the producer's edited Google Doc "
            "to fold the corrections in, then re-publish.",
            "",
        ]
        for d in divergences:
            snippet = d.passage[:90] + ("…" if len(d.passage) > 90 else "")
            lines.append(
                f'  • “{snippet}”\n'
                f"      published-as: {d.local_label}  |  producer says: {d.producer_label}"
            )
        super().__init__("\n".join(lines))


def _normalize(s: str) -> str:
    for a, b in [("“", '"'), ("”", '"'), ("’", "'"),
                 ("‘", "'"), ("—", "-"), ("–", "-")]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def _key(body: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", _normalize(body).lower()).strip()[:55]


def _speaker_equiv(a: str, b: str) -> bool:
    """True if two speaker labels plausibly name the same person.

    Handles full-name vs last-name vs first-name forms
    (e.g. 'Anne' ≈ 'Anne Strainchamps' ≈ 'Strainchamps').
    """
    na, nb = a.lower().strip(), b.lower().strip()
    if na == nb:
        return True
    ta, tb = na.split(), nb.split()
    if not ta or not tb:
        return False
    if ta[-1] == tb[-1]:  # shared last name
        return True
    if ta[0] == tb[0] and (len(ta) == 1 or len(tb) == 1):  # first-name vs full
        return True
    return False


_BOLD_INLINE = re.compile(r"^\*\*([^*:]{1,40}?):\*\*\s*(.+)$")
_BOLD_ALONE = re.compile(r"^\*\*([^*:]{1,40}?):\*\*\s*$")
_PLAIN = re.compile(r"^([A-Z][A-Za-z.'\- ]{1,38}?):\s+(.+)$")


def parse_speaker_turns(text: str) -> list[tuple[str, str]]:
    """Parse a transcript into ``(speaker, body)`` turns.

    Handles the three shapes we see in practice:
    - ``**Name:** body``        (formatted_transcript.md, inline bold)
    - ``**Name:**`` / ``body``  (formatted_transcript.md, label on its own line)
    - ``Name: body``            (producer docx exported to text)
    """
    turns: list[tuple[str, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue

        m = _BOLD_INLINE.match(line)
        if m:
            turns.append((m.group(1).strip(), _normalize(m.group(2))))
            continue

        m = _BOLD_ALONE.match(line)
        if m:
            # body is the next non-empty line
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                turns.append((m.group(1).strip(), _normalize(lines[i].strip())))
                i += 1
            continue

        m = _PLAIN.match(line)
        if m:
            speaker, body = m.group(1).strip(), m.group(2).strip()
            if speaker.lower() in _METADATA_KEYS:
                continue
            if not re.search(r"[A-Za-z]", body):  # e.g. "Duration: 00:40:00"
                continue
            turns.append((speaker, _normalize(body)))
            continue

    return turns


def find_speaker_divergences(local_text: str, producer_text: str) -> list[Divergence]:
    """Return passages where the local transcript and the producer doc assign
    a turn to different speakers.

    Only distinctive, alignable passages are compared; turns that don't align
    (text edited beyond the key window, or present in only one source) are
    silently skipped rather than reported as false positives.
    """
    local_turns = parse_speaker_turns(local_text)
    producer_turns = parse_speaker_turns(producer_text)

    producer_by_key: dict[str, str] = {}
    for speaker, body in producer_turns:
        k = _key(body)
        if len(k) > _MIN_KEY_LEN:
            producer_by_key.setdefault(k, speaker)

    divergences: list[Divergence] = []
    seen: set[str] = set()
    for speaker, body in local_turns:
        k = _key(body)
        if len(k) <= _MIN_KEY_LEN or k in seen:
            continue
        seen.add(k)
        producer_label = producer_by_key.get(k)
        if producer_label and not _speaker_equiv(speaker, producer_label):
            divergences.append(Divergence(passage=body, local_label=speaker,
                                          producer_label=producer_label))
    return divergences


def verify_against_producer(local_text: str, producer_text: str) -> int:
    """Hard gate. Returns the number of aligned turns on success; raises
    :class:`TranscriptProvenanceError` if any speaker label diverges."""
    divergences = find_speaker_divergences(local_text, producer_text)
    if divergences:
        raise TranscriptProvenanceError(divergences)

    producer_keys = {
        _key(b) for _, b in parse_speaker_turns(producer_text) if len(_key(b)) > _MIN_KEY_LEN
    }
    aligned = sum(
        1 for _, b in parse_speaker_turns(local_text)
        if _key(b) in producer_keys and len(_key(b)) > _MIN_KEY_LEN
    )
    return aligned


# --------------------------------------------------------------------------
# Drive fetch + episode-level verification (thin I/O; not unit-tested)
# --------------------------------------------------------------------------

class ProducerDocUnavailable(TranscriptProvenanceError):
    """Raised (fail-closed) when the producer doc cannot be fetched, so a
    publish is never allowed to proceed unverified."""

    def __init__(self, message: str):
        # Bypass the parent's divergence-formatting constructor.
        Exception.__init__(self, message)
        self.divergences = []


def producer_doc_id_from_manifest(manifest: dict) -> Optional[str]:
    """Pull the producer edit-transcript Drive doc id from an episode manifest.

    Looks at ``google_drive.uploads.edit_transcript.id``. Returns ``None`` if
    the manifest predates the upload step or has no such reference (e.g.
    Luminous episodes), in which case the provenance gate simply doesn't engage.
    """
    return (
        (manifest or {})
        .get("google_drive", {})
        .get("uploads", {})
        .get("edit_transcript", {})
        .get("id")
    ) or None


def gate_published_transcript(
    transcript_text: Optional[str],
    verify_doc_id: Optional[str],
    *,
    fetcher=None,
    rclone_remote: str = "gdrive",
) -> Optional[int]:
    """Publish-loop glue: if a producer doc id is supplied and we have a
    transcript to publish, fetch the producer doc and hard-gate against it.

    Returns the aligned-turn count when verified, or ``None`` when there is
    nothing to check (no doc id / no transcript). Raises
    :class:`TranscriptProvenanceError` to block on divergence. ``fetcher`` is
    injectable for testing; it defaults to the rclone Drive export.
    """
    if not verify_doc_id or not transcript_text:
        return None
    if fetcher is None:
        producer_text = fetch_drive_doc_text(verify_doc_id, rclone_remote=rclone_remote)
    else:
        producer_text = fetcher(verify_doc_id)
    return verify_against_producer(transcript_text, producer_text)


def fetch_drive_doc_text(drive_id: str, *, rclone_remote: str = "gdrive") -> str:
    """Export a Google Doc (by Drive file ID) to plain text via rclone.

    Raises :class:`ProducerDocUnavailable` on any failure so the caller can
    fail-closed rather than publish unverified.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "producer.txt"
        proc = subprocess.run(
            ["rclone", "--drive-export-formats", "txt", "backend", "copyid",
             f"{rclone_remote}:", drive_id, str(out)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not out.exists():
            raise ProducerDocUnavailable(
                f"Could not export producer transcript doc {drive_id} via rclone "
                f"(rc={proc.returncode}): {proc.stderr.strip()[:300]}. "
                "Refusing to publish unverified — fix Drive access or run "
                "/wc-transcript-update."
            )
        return out.read_text()


def verify_episode(transcript_dir: Path, producer_drive_id: str,
                   *, rclone_remote: str = "gdrive") -> int:
    """Episode-level gate used by the publish flow.

    Reads the local ``formatted_transcript.md`` from ``transcript_dir`` and
    diffs its speaker labels against the producer-edited Drive doc identified
    by ``producer_drive_id``. Returns aligned-turn count on success; raises
    :class:`TranscriptProvenanceError` (hard block) otherwise.
    """
    formatted = Path(transcript_dir) / "formatted_transcript.md"
    if not formatted.exists():
        raise ProducerDocUnavailable(
            f"No formatted_transcript.md in {transcript_dir}; cannot verify "
            "transcript provenance."
        )
    producer_text = fetch_drive_doc_text(producer_drive_id, rclone_remote=rclone_remote)
    aligned = verify_against_producer(formatted.read_text(), producer_text)
    logger.info(
        "Transcript provenance OK: %d aligned turns match producer doc %s",
        aligned, producer_drive_id,
    )
    return aligned
