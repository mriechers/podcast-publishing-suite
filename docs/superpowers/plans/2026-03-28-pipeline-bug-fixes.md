# Pipeline Bug Fixes — prx-to-ghost-publisher & podcast-whisper-transcription

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical and high-priority bugs across the two active pipeline modules so the transcription → Ghost import flow works end-to-end without destructive behavior.

**Architecture:** Bug fixes in two git submodules (`modules/prx-to-ghost-publisher/` and `modules/podcast-whisper-transcription/`) plus two repo-level git config fixes. Each task produces an independently committable change. Tests use pytest (existing framework in publisher; new test setup needed in whisper module).

**Tech Stack:** Python 3.11+, pytest, Ghost Admin API (Lexical JSON), git submodules

---

## File Map

### prx-to-ghost-publisher (`modules/prx-to-ghost-publisher/`)

| File | Responsibility | Tasks |
|------|---------------|-------|
| `src/ghost_client.py` | Ghost API client — create/update posts | Task 1 (add `update_post_metadata`) |
| `src/main.py` | CLI commands — `update-metadata`, `update-transcripts` | Task 1 (switch to safe update path) |
| `src/content_builder.py` | HTML generation, transcript loading, post building | Tasks 2, 5, 6 |
| `src/content_transforms.py` | Feed content stripping rules | Tasks 3, 4 |
| `tests/test_ghost_client.py` | Ghost client tests | Task 1 |
| `tests/test_content_builder.py` | Content builder tests | Tasks 2, 5, 6 |
| `tests/test_content_transforms.py` | Content transforms tests (new) | Tasks 3, 4 |

### podcast-whisper-transcription (`modules/podcast-whisper-transcription/`)

| File | Responsibility | Tasks |
|------|---------------|-------|
| `scripts/validate_episode.py` | Episode QC validation | Task 7 |
| `tests/test_validate_episode.py` | Validation tests (new) | Task 7 |
| `pyproject.toml` | Project config (new, for pytest) | Task 7 |

### Repo root

| File | Responsibility | Tasks |
|------|---------------|-------|
| `.gitmodules` | Submodule URL registry | Task 8 |
| `modules/prx-to-ghost-publisher/.gitmodules` | Nested ghost-mcp submodule | Task 9 |

---

## Task 1: Fix destructive Lexical overwrite in `update-metadata` (publisher#18)

**Priority:** P0 — CRITICAL. This bug destroys post content.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/src/ghost_client.py:432-459`
- Modify: `modules/prx-to-ghost-publisher/src/main.py:1113-1144`
- Test: `modules/prx-to-ghost-publisher/tests/test_ghost_client.py`

**Problem:** `cmd_update_metadata` uses `client.get_post()` (HTML-only) then `client.update_post()` (`source=html`) on Lexical posts. This round-trips through HTML, destroying visibility controls and custom nodes.

**Fix:** Add a `update_post_metadata` method to `GhostClient` that sends only non-content fields without `source=html`. Then use `get_post_with_lexical()` in `cmd_update_metadata` to detect post type and route to the safe path.

- [ ] **Step 1: Write the failing test for metadata-only update**

In `tests/test_ghost_client.py`, add:

```python
class TestUpdatePostMetadata:
    """Tests for metadata-only updates that preserve Lexical content."""

    def test_update_metadata_does_not_send_html(self, ghost_client, mock_response):
        """Metadata updates must not include html or source=html."""
        mock_response({"posts": [{"id": "abc123", "updated_at": "2026-01-01T00:00:00.000Z"}]})

        ghost_client.update_post_metadata(
            post_id="abc123",
            updated_at="2026-01-01T00:00:00.000Z",
            tags=[{"name": "Wonder Cabinet"}],
            codeinjection_head="<script>jsonld</script>",
            canonical_url="https://wondercabinetproductions.com/wonder-cabinet/test/",
        )

        # Verify the request payload
        call_args = ghost_client._request_with_retry.call_args
        url = call_args[0][1]  # Second positional arg is URL
        payload = call_args[1]["json"]

        assert "source=html" not in url
        assert "html" not in payload["posts"][0]

    def test_update_metadata_sends_only_provided_fields(self, ghost_client, mock_response):
        """Only fields explicitly provided should be in the payload."""
        mock_response({"posts": [{"id": "abc123", "updated_at": "2026-01-01T00:00:00.000Z"}]})

        ghost_client.update_post_metadata(
            post_id="abc123",
            updated_at="2026-01-01T00:00:00.000Z",
            tags=[{"name": "Wonder Cabinet"}],
        )

        payload = ghost_client._request_with_retry.call_args[1]["json"]
        post_data = payload["posts"][0]
        assert "tags" in post_data
        assert "codeinjection_head" not in post_data
        assert "canonical_url" not in post_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_ghost_client.py::TestUpdatePostMetadata -v`
Expected: FAIL — `AttributeError: 'GhostClient' object has no attribute 'update_post_metadata'`

- [ ] **Step 3: Implement `update_post_metadata` in ghost_client.py**

Add after `update_post_lexical()` (after line ~459):

```python
def update_post_metadata(
    self,
    post_id: str,
    updated_at: str,
    tags: list[dict] | None = None,
    codeinjection_head: str | None = None,
    canonical_url: str | None = None,
) -> dict:
    """Update only non-content metadata fields on a post.

    Unlike update_post(), this does NOT send html or source=html,
    so it is safe for Lexical posts — content is not touched.

    Args:
        post_id: Ghost post ID.
        updated_at: Current updated_at timestamp from the post.
        tags: Optional new tags list.
        codeinjection_head: Optional new code injection.
        canonical_url: Optional new canonical URL.

    Returns:
        Updated post data from API response.
    """
    url = f"{self.api_url}/posts/{post_id}/"

    post_data: dict[str, Any] = {"updated_at": updated_at}
    if tags is not None:
        post_data["tags"] = tags
    if codeinjection_head is not None:
        post_data["codeinjection_head"] = codeinjection_head
    if canonical_url is not None:
        post_data["canonical_url"] = canonical_url

    payload = {"posts": [post_data]}

    logger.info(f"Updating post metadata: {post_id}")
    logger.debug(f"PUT {url}")

    response = self._request_with_retry(
        "PUT", url, json=payload, headers=self._get_headers(), timeout=30,
    )

    result = self._handle_response(response)
    posts = result.get("posts", [])
    if not posts:
        raise GhostAPIError("No post returned in response")
    return posts[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_ghost_client.py::TestUpdatePostMetadata -v`
Expected: PASS

- [ ] **Step 5: Update `cmd_update_metadata` in main.py to use safe path**

Replace lines 1113–1144 in `src/main.py`. Change from:

```python
current_post = client.get_post(ghost_post_id)
updated_at = current_post.get("updated_at")
# ... builds GhostPost with html=current_post.get("html", "") ...
result = client.update_post(ghost_post_id, update_post, updated_at)
```

To:

```python
current_post = client.get_post(ghost_post_id)
updated_at = current_post.get("updated_at")

if not updated_at:
    logger.error(f"No updated_at for post: {title}")
    failed += 1
    continue

# Build canonical URL for the post
if post_slug:
    base = config.ghost_url.rstrip('/')
    if url_prefix:
        canonical_url = f"{base}/{url_prefix}/{post_slug}/"
    else:
        canonical_url = f"{base}/{post_slug}/"
else:
    canonical_url = episode.link  # Fallback

# Safe metadata-only update: no html, no source=html
result = client.update_post_metadata(
    ghost_post_id,
    updated_at=updated_at,
    tags=new_tags,
    codeinjection_head=jsonld,
    canonical_url=canonical_url,
)
```

- [ ] **Step 6: Run full test suite**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd modules/prx-to-ghost-publisher
git add src/ghost_client.py src/main.py tests/test_ghost_client.py
git commit -m "fix: Use metadata-only API path for update-metadata command

The update-metadata command was sending html with source=html, which
destroys Lexical post content (visibility controls, custom nodes).
New update_post_metadata() method sends only non-content fields
without source=html, preserving the Lexical tree.

Fixes #18"
```

---

## Task 2: Fix `load_wc_transcript()` file naming mismatch (publisher#20)

**Priority:** P1 — High. Transcripts not found during Ghost import.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/src/content_builder.py:553-563`
- Test: `modules/prx-to-ghost-publisher/tests/test_content_builder.py`

**Problem:** When `--transcript-dir` points to a canonical episode folder, the function checks for `formatted_transcript.md` then `transcript.txt` by exact name. But the whisper pipeline may produce files named `WC_002_Rovelli_transcript.txt` instead of `transcript.txt`. The `formatted_transcript.md` check (line 554) works for episodes that went through the formatter agent, but pre-migration episodes only have the `*_transcript.txt` variant.

- [ ] **Step 1: Write the failing test**

In `tests/test_content_builder.py`, add:

```python
class TestLoadWcTranscript:
    """Tests for load_wc_transcript file discovery."""

    def test_finds_formatted_transcript_md(self, tmp_path):
        """Prefer formatted_transcript.md when it exists."""
        (tmp_path / "formatted_transcript.md").write_text("**Anne:** Hello")
        result = load_wc_transcript("Test Episode", tmp_path)
        assert result == "**Anne:** Hello"

    def test_finds_plain_transcript_txt(self, tmp_path):
        """Fall back to transcript.txt."""
        (tmp_path / "transcript.txt").write_text("Hello world")
        result = load_wc_transcript("Test Episode", tmp_path)
        assert result == "Hello world"

    def test_finds_suffixed_transcript_txt(self, tmp_path):
        """Find *_transcript.txt when transcript.txt doesn't exist."""
        (tmp_path / "WC_002_Rovelli_transcript.txt").write_text("Physics is beautiful")
        result = load_wc_transcript("Carlo Rovelli: Physics", tmp_path)
        assert result == "Physics is beautiful"

    def test_prefers_formatted_over_suffixed(self, tmp_path):
        """formatted_transcript.md takes priority over *_transcript.txt."""
        (tmp_path / "formatted_transcript.md").write_text("**Anne:** Formatted")
        (tmp_path / "WC_002_Rovelli_transcript.txt").write_text("Raw text")
        result = load_wc_transcript("Carlo Rovelli: Physics", tmp_path)
        assert result == "**Anne:** Formatted"

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = load_wc_transcript("Nobody: Nothing", tmp_path)
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_builder.py::TestLoadWcTranscript -v`
Expected: `test_finds_suffixed_transcript_txt` FAILS (returns None)

- [ ] **Step 3: Add `*_transcript.txt` glob fallback in content_builder.py**

After the `transcript.txt` check (line 563), before the guest-name extraction (line 565), add:

```python
    # Fallback: glob for *_transcript.txt (whisper pipeline naming convention)
    for f in sorted(transcript_dir.glob('*_transcript.txt')):
        logger.info(f"Found suffixed transcript: {f}")
        return f.read_text()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_builder.py::TestLoadWcTranscript -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd modules/prx-to-ghost-publisher
git add src/content_builder.py tests/test_content_builder.py
git commit -m "fix: Find *_transcript.txt in canonical episode folders

load_wc_transcript() only checked for exact 'transcript.txt' name.
The whisper pipeline produces files like WC_002_Rovelli_transcript.txt.
Added glob fallback for *_transcript.txt pattern.

Fixes #20"
```

---

## Task 3: Strip chapter timestamps from PRX show notes (publisher#25)

**Priority:** P1 — High. Timestamps appear in published Ghost posts.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/src/content_transforms.py:197-208`
- Create: `modules/prx-to-ghost-publisher/tests/test_content_transforms.py`

**Problem:** The three regex patterns for chapter timestamps may not match after nh3 sanitization normalizes whitespace. The patterns require exact sequences that nh3 may alter.

- [ ] **Step 1: Write failing tests for timestamp stripping**

Create `tests/test_content_transforms.py`:

```python
"""Tests for content_transforms.py — stripping rules."""

import re
from src.content_transforms import (
    WC_CHAPTERS_BLOCK,
    WC_TIMESTAMP_PARAGRAPHS,
    WC_SHORT_TIMESTAMP_PARAGRAPHS,
    WC_EMDASH_DIVIDER,
)


class TestChapterTimestampStripping:
    """Verify timestamp patterns match real PRX feed output after nh3."""

    def test_chapters_block_with_br_tags(self):
        """Standard format: Chapters: heading + br-separated timestamps."""
        html = (
            '<p>Chapters:</p>\n'
            '<p>00:00:00 Introduction<br>00:04:34 The Forest<br>00:15:20 Conclusion</p>'
        )
        assert re.search(WC_CHAPTERS_BLOCK, html, re.DOTALL)

    def test_chapters_block_with_newlines_between(self):
        """After nh3, there may be newlines between the heading and timestamp p."""
        html = (
            '<p>Chapters:</p>\n\n'
            '<p>00:00:00 Introduction<br>\n00:04:34 The Forest<br>\n00:15:20 Conclusion</p>'
        )
        assert re.search(WC_CHAPTERS_BLOCK, html, re.DOTALL)

    def test_individual_timestamp_paragraphs(self):
        """Format 2: Each timestamp in its own <p> tag."""
        html = '<p>00:00:00 Introduction</p>\n<p>00:04:34 The Forest</p>\n<p>00:15:20 Conclusion</p>'
        assert re.search(WC_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)

    def test_short_timestamp_paragraphs_with_emdash(self):
        """Format 3: MM:SS with em dash separator."""
        html = '<p>0:00 — Introduction</p>\n<p>4:34 — The Forest</p>\n<p>15:20 — Conclusion</p>'
        assert re.search(WC_SHORT_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)

    def test_short_timestamp_with_hyphen(self):
        """Format 3: MM:SS with regular dash."""
        html = '<p>0:00 - Introduction</p>\n<p>4:34 - The Forest</p>'
        assert re.search(WC_SHORT_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)

    def test_single_timestamp_paragraph_not_matched(self):
        """A single timestamp should NOT match (requires 2+)."""
        html = '<p>00:00:00 Introduction</p>'
        assert not re.search(WC_TIMESTAMP_PARAGRAPHS, html, re.DOTALL)
```

- [ ] **Step 2: Run tests to see which patterns fail**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_transforms.py::TestChapterTimestampStripping -v`
Expected: Some tests may fail due to whitespace sensitivity.

- [ ] **Step 3: Fix patterns if tests fail**

If `WC_CHAPTERS_BLOCK` fails on nh3-normalized output, make whitespace matching more permissive. Replace line 199 of `content_transforms.py`:

```python
WC_CHAPTERS_BLOCK = r'''<p>\s*Chapters:?\s*</p>\s*<p>\s*(?:\d{1,2}:\d{2}(?::\d{2})?\s+[^<]+(?:<br\s*/?>?\s*|\s*))+\s*</p>'''
```

Key changes: `Chapters:?` (optional colon), `\d{1,2}:\d{2}(?::\d{2})?` (accept both MM:SS and HH:MM:SS), more permissive internal whitespace.

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_transforms.py::TestChapterTimestampStripping -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd modules/prx-to-ghost-publisher
git add src/content_transforms.py tests/test_content_transforms.py
git commit -m "fix: Make chapter timestamp patterns resilient to nh3 normalization

Timestamp regex patterns were brittle against whitespace changes
introduced by nh3 HTML sanitization. Relaxed patterns to handle
newlines between elements, optional colons, and both HH:MM:SS
and MM:SS timestamp formats.

Fixes #25"
```

---

## Task 4: Strip emdash spacer variants (publisher#24)

**Priority:** P1 — High. Emdash dividers appear in published posts.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/src/content_transforms.py:195`
- Test: `modules/prx-to-ghost-publisher/tests/test_content_transforms.py`

- [ ] **Step 1: Write failing tests for emdash variants**

Add to `tests/test_content_transforms.py`:

```python
class TestEmdashStripping:
    """Verify emdash divider pattern matches all PRX variants."""

    def test_single_emdash(self):
        html = '<p>—</p>'
        assert re.search(WC_EMDASH_DIVIDER, html)

    def test_double_emdash(self):
        html = '<p>——</p>'
        assert re.search(WC_EMDASH_DIVIDER, html)

    def test_emdash_with_nbsp(self):
        """nh3 may convert &nbsp; to U+00A0."""
        html = '<p>\u00a0—\u00a0</p>'
        assert re.search(WC_EMDASH_DIVIDER, html)

    def test_emdash_with_whitespace(self):
        html = '<p>  —  </p>'
        assert re.search(WC_EMDASH_DIVIDER, html)

    def test_emdash_does_not_match_text(self):
        """Paragraphs with actual text content should not match."""
        html = '<p>This — that</p>'
        assert not re.search(WC_EMDASH_DIVIDER, html)
```

- [ ] **Step 2: Run tests to verify failures**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_transforms.py::TestEmdashStripping -v`
Expected: `test_double_emdash` and `test_emdash_with_nbsp` FAIL

- [ ] **Step 3: Fix the emdash pattern**

Replace line 195 of `content_transforms.py`:

```python
WC_EMDASH_DIVIDER = r'''<p>[\s\u00a0]*[—\u2014]{1,3}[\s\u00a0]*</p>'''
```

Changes: `[\s\u00a0]*` handles non-breaking spaces, `{1,3}` handles 1-3 consecutive emdashes.

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_transforms.py::TestEmdashStripping -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd modules/prx-to-ghost-publisher
git add src/content_transforms.py tests/test_content_transforms.py
git commit -m "fix: Handle double-emdash and NBSP-padded divider variants

Single-char emdash pattern missed double em dashes and non-breaking
space padding that nh3 preserves from PRX show notes.

Fixes #24"
```

---

## Task 5: Replace TTBOOK references with Wonder Cabinet (publisher#6)

**Priority:** P1 — User-visible text in published posts.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/src/content_builder.py:1242,1322`
- Test: `modules/prx-to-ghost-publisher/tests/test_content_builder.py`

- [ ] **Step 1: Write the failing test**

```python
class TestTtbookReferences:
    """Ensure no TTBOOK references appear in generated HTML."""

    def test_episode_meta_html_no_ttbook(self):
        html = build_episode_meta_html("https://example.com/episode")
        assert "TTBOOK" not in html
        assert "ttbook" not in html.lower()
        assert "Listen on" in html or "View episode" in html

    def test_build_tags_default_not_ttbook(self):
        from src.feed_parser import Episode
        from datetime import datetime
        ep = Episode(
            title="Test", guid="test-guid", link="https://example.com",
            pub_date=datetime.now(), description="Test", categories=["Science"],
        )
        tags = build_tags(ep)
        tag_names = [t["name"] for t in tags]
        assert "TTBOOK" not in tag_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_builder.py::TestTtbookReferences -v`
Expected: FAIL — `assert "TTBOOK" not in html`

- [ ] **Step 3: Fix the references**

In `content_builder.py`:

Line 1242 — change:
```python
  <p><a href="{safe_link}">Listen on TTBOOK.org</a></p>
```
to:
```python
  <p><a href="{safe_link}">View episode on PRX</a></p>
```

Line 1322 — change:
```python
def build_tags(
    episode: Episode,
    primary_tag: str = "TTBOOK",
```
to:
```python
def build_tags(
    episode: Episode,
    primary_tag: str = "Wonder Cabinet",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_builder.py::TestTtbookReferences -v`
Expected: PASS

- [ ] **Step 5: Grep for remaining TTBOOK references**

Run: `cd modules/prx-to-ghost-publisher && grep -rn "TTBOOK\|ttbook" src/ --include="*.py" | grep -v "^.*:#"`

Verify only comments remain (the feed_parser chartable ID comment and main.py GUID prefix comment are fine).

- [ ] **Step 6: Commit**

```bash
cd modules/prx-to-ghost-publisher
git add src/content_builder.py tests/test_content_builder.py
git commit -m "fix: Replace user-visible TTBOOK references with Wonder Cabinet

Episode meta HTML showed 'Listen on TTBOOK.org' in published posts.
Changed to 'View episode on PRX'. Updated build_tags() default from
'TTBOOK' to 'Wonder Cabinet'.

Fixes #6"
```

---

## Task 6: Fix `published_at` date handling (publisher#11)

**Priority:** P1 — Affects draft scheduling behavior.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/src/content_builder.py:1456`
- Test: `modules/prx-to-ghost-publisher/tests/test_content_builder.py`

**Problem:** `published_at=None` always. Should use PRX date for historical episodes, `None` for future episodes.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone, timedelta

class TestPublishedAtHandling:
    """published_at should be set for past episodes, None for future."""

    def test_past_episode_gets_published_at(self):
        from src.feed_parser import Episode
        past_date = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)
        ep = Episode(
            title="Past Episode", guid="past-guid", link="https://example.com",
            pub_date=past_date, description="Test", categories=[],
        )
        post = build_ghost_post(ep, primary_tag="Wonder Cabinet")
        assert post.published_at is not None
        assert "2025-06-15" in post.published_at

    def test_future_episode_gets_none(self):
        from src.feed_parser import Episode
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        ep = Episode(
            title="Future Episode", guid="future-guid", link="https://example.com",
            pub_date=future_date, description="Test", categories=[],
        )
        post = build_ghost_post(ep, primary_tag="Wonder Cabinet")
        assert post.published_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_builder.py::TestPublishedAtHandling -v`
Expected: `test_past_episode_gets_published_at` FAILS — `published_at` is always None

- [ ] **Step 3: Implement conditional date logic**

In `content_builder.py`, replace line 1456:

```python
published_at=None,  # Let Ghost use import time (PRX dates can be in the future)
```

with:

```python
published_at=format_published_at(episode) if episode.pub_date <= datetime.now(timezone.utc) else None,
```

Add `from datetime import timezone` to the imports at the top of the file if not already present.

Apply the same fix in `build_luminous_ghost_post()` (around line 1173) if it has the same pattern.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd modules/prx-to-ghost-publisher && .venv/bin/python -m pytest tests/test_content_builder.py::TestPublishedAtHandling -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd modules/prx-to-ghost-publisher
git add src/content_builder.py tests/test_content_builder.py
git commit -m "fix: Set published_at for historical episodes, None for future

Drafts for future episodes had published_at=None (correct).
But historical back-imports also had None, causing them to appear
as newly published. Now uses PRX pub_date for past episodes.

Fixes #11"
```

---

## Task 7: Fix `validate_episode.py` manifest reference and add tests

**Priority:** P2 — QC gate doesn't work correctly.

**Files:**
- Modify: `modules/podcast-whisper-transcription/scripts/validate_episode.py:152`
- Create: `modules/podcast-whisper-transcription/tests/test_validate_episode.py`
- Create: `modules/podcast-whisper-transcription/pyproject.toml`

**Problem:** References `upload_manifest.json` (line 152) but the actual file is `manifest.json`. The JSON structure check also expects `files[].status` (array) but the real schema uses `files.{key}.status` (dict).

- [ ] **Step 1: Set up pytest in the whisper module**

Create `modules/podcast-whisper-transcription/pyproject.toml`:

```toml
[project]
name = "podcast-whisper-transcription"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest>=7.0.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `modules/podcast-whisper-transcription/tests/__init__.py` (empty).

- [ ] **Step 2: Write the failing test**

Create `modules/podcast-whisper-transcription/tests/test_validate_episode.py`:

```python
"""Tests for validate_episode.py."""

import json
import sys
from pathlib import Path

# Add scripts/ to path so we can import validate_episode
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_episode import validate_episode


class TestManifestCheck:
    """Validate the manifest.json check works with the real schema."""

    def test_finds_manifest_json(self, tmp_path):
        """Should check manifest.json, not upload_manifest.json."""
        # Create minimal valid episode structure
        (tmp_path / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        (tmp_path / "transcript.txt").write_text("Hello")
        (tmp_path / "formatted_transcript.md").write_text("**Anne:** Hello")
        (tmp_path / "chapters.md").write_text("## Chapters\n00:00 Intro")

        # Write manifest.json with the REAL schema
        manifest = {
            "version": 1,
            "stage": "formatted",
            "files": {
                "transcript": {"path": "transcript.txt", "status": "present"},
                "formatted_transcript": {"path": "formatted_transcript.md", "status": "present"},
                "captions": {"path": "captions.srt", "status": "present"},
            }
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        results, exit_code = validate_episode(tmp_path)
        result_texts = [msg for _, msg in results]

        # Should find and parse the manifest
        manifest_results = [r for r in result_texts if "manifest" in r.lower() or "Manifest" in r]
        assert len(manifest_results) > 0, f"No manifest check in results: {result_texts}"
        # Should not report failures from the manifest check
        manifest_failures = [(ok, msg) for ok, msg in results if "manifest" in msg.lower() and not ok]
        assert len(manifest_failures) == 0, f"Manifest check failed: {manifest_failures}"

    def test_does_not_require_upload_manifest(self, tmp_path):
        """upload_manifest.json should NOT be checked — only manifest.json."""
        (tmp_path / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        (tmp_path / "upload_manifest.json").write_text('{"bad": "schema"}')
        # No manifest.json — the upload_manifest.json should be ignored

        results, _ = validate_episode(tmp_path)
        result_texts = [msg for _, msg in results]
        # Should not reference upload_manifest.json
        assert not any("upload_manifest" in r for r in result_texts)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd modules/podcast-whisper-transcription && python -m pytest tests/test_validate_episode.py -v`
Expected: FAIL — manifest.json not found (script checks upload_manifest.json instead)

- [ ] **Step 4: Fix validate_episode.py**

In `scripts/validate_episode.py`, replace lines 151-164:

```python
    # Episode manifest
    manifest = episode_dir / "manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text())
            files = data.get("files", {})
            if isinstance(files, dict):
                # Real schema: files.{key}.status
                failed_files = [k for k, v in files.items()
                                if isinstance(v, dict) and v.get("status") == "failed"]
            else:
                # Legacy array schema
                failed_files = [f for f in files if isinstance(f, dict) and f.get("status") == "failed"]

            if failed_files:
                results.append(
                    (False, f"Manifest: {len(failed_files)} files failed ({', '.join(failed_files)})")
                )
            else:
                stage = data.get("stage", "unknown")
                results.append((True, f"Manifest: stage={stage}, all files OK"))
        except (json.JSONDecodeError, KeyError):
            results.append((False, "Manifest: invalid JSON"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd modules/podcast-whisper-transcription && python -m pytest tests/test_validate_episode.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd modules/podcast-whisper-transcription
git add scripts/validate_episode.py tests/ pyproject.toml
git commit -m "fix: Check manifest.json instead of upload_manifest.json

validate_episode.py referenced upload_manifest.json which doesn't
exist. The canonical schema uses manifest.json with files as a dict
(files.{key}.status), not an array. Added pytest setup and tests.

Relates to podcast-publishing-suite#11"
```

---

## Task 8: Update submodule remote URLs from MarkOnFire to correct org

**Priority:** P1 — Blocks fresh clones and CI.

**Files:**
- Modify: `.gitmodules` (repo root)

**Problem:** Four submodules point to `MarkOnFire/` which may be a stale GitHub username. Repos were transferred to `Wonder-Cabinet-Productions` org or `mriechers`.

- [ ] **Step 1: Verify which remote URLs resolve**

```bash
# Check each URL
gh repo view MarkOnFire/podcast-audiogram-tools --json url 2>&1
gh repo view MarkOnFire/podcast-whisper-transcription --json url 2>&1
gh repo view MarkOnFire/prx-to-ghost-publisher --json url 2>&1
gh repo view MarkOnFire/robo-social --json url 2>&1

# Check correct orgs
gh repo view mriechers/podcast-whisper-transcription --json url 2>&1
gh repo view mriechers/prx-to-ghost-publisher --json url 2>&1
gh repo view mriechers/podcast-audiogram-tools --json url 2>&1
gh repo view mriechers/robo-social --json url 2>&1
gh repo view Wonder-Cabinet-Productions/podcast-publishing-suite --json url 2>&1
```

- [ ] **Step 2: Update `.gitmodules` with correct URLs**

Based on what resolves, update each `url =` line in `.gitmodules`. Expected result:

```ini
[submodule "modules/audiogram-tools"]
    path = modules/audiogram-tools
    url = git@github.com:mriechers/podcast-audiogram-tools.git
[submodule "modules/podcast-whisper-transcription"]
    path = modules/podcast-whisper-transcription
    url = git@github.com:mriechers/podcast-whisper-transcription.git
[submodule "modules/prx-to-ghost-publisher"]
    path = modules/prx-to-ghost-publisher
    url = git@github.com:mriechers/prx-to-ghost-publisher.git
[submodule "modules/robo-social"]
    path = modules/robo-social
    url = git@github.com:mriechers/robo-social.git
[submodule "modules/podcast-production-schedule"]
    path = modules/podcast-production-schedule
    url = git@github.com:mriechers/podcast-production-schedule.git
```

- [ ] **Step 3: Sync submodule configs**

```bash
cd /Volumes/Mark's\ SSD/Developer/wonder-cabinet/podcast-publishing-suite
git submodule sync
```

- [ ] **Step 4: Verify sync**

```bash
git config --file .git/modules/podcast-whisper-transcription/config remote.origin.url
git config --file .git/modules/prx-to-ghost-publisher/config remote.origin.url
```

- [ ] **Step 5: Commit**

```bash
git add .gitmodules
git commit -m "chore: Update submodule URLs from MarkOnFire to mriechers

All submodule remotes pointed to MarkOnFire/ (stale username).
Updated to mriechers/ which is the current GitHub account.
Ran git submodule sync to propagate.

Fixes #29"
```

---

## Task 9: Remove ghost-mcp nested submodule from prx-to-ghost-publisher

**Priority:** P1 — Blocks worktree operations.

**Files:**
- Modify: `modules/prx-to-ghost-publisher/.gitmodules`
- Remove: `modules/prx-to-ghost-publisher/ghost-mcp` (git tracked)

**Problem:** The nested `ghost-mcp` submodule inside `prx-to-ghost-publisher` causes `fatal: not a git repository` errors when working in git worktrees. The ghost-mcp server is a runtime MCP tool dependency, not a build-time code dependency — it should not be a submodule.

- [ ] **Step 1: Check current state**

```bash
cd modules/prx-to-ghost-publisher
cat .gitmodules
ls -la ghost-mcp/ 2>/dev/null || echo "ghost-mcp not checked out"
cat .mcp.json 2>/dev/null || echo "no .mcp.json"
```

- [ ] **Step 2: Remove the nested submodule**

```bash
cd modules/prx-to-ghost-publisher
git submodule deinit -f ghost-mcp 2>/dev/null || true
git rm -f ghost-mcp
rm -rf .git/modules/ghost-mcp 2>/dev/null || true
```

- [ ] **Step 3: Remove `.gitmodules` file if it's now empty**

If `.gitmodules` only contained the ghost-mcp entry, remove it entirely:

```bash
# Check if anything remains
cat .gitmodules
# If only whitespace/empty, remove it
git rm .gitmodules
```

If other submodules exist, just verify the ghost-mcp section is gone.

- [ ] **Step 4: Verify worktree operations work**

```bash
cd /Volumes/Mark's\ SSD/Developer/wonder-cabinet/podcast-publishing-suite
git status 2>&1 | head -5  # Should no longer error on prx-to-ghost-publisher
```

- [ ] **Step 5: Commit in the submodule first, then update pointer**

```bash
cd modules/prx-to-ghost-publisher
git add -A
git commit -m "chore: Remove ghost-mcp nested submodule

The ghost-mcp MCP server is a runtime tool dependency, not a
build-time code dependency. As a nested submodule it breaks git
worktree operations in the parent repo. Reference it via .mcp.json
or install instructions instead.

Fixes podcast-publishing-suite#28"

# Back in parent repo, update submodule pointer
cd /Volumes/Mark's\ SSD/Developer/wonder-cabinet/podcast-publishing-suite
git add modules/prx-to-ghost-publisher
git commit -m "chore: Update prx-to-ghost-publisher pointer (ghost-mcp removed)

Fixes #28"
```

---

## Execution Order

Tasks can be parallelized in two groups:

**Group 1 (publisher bugs — independent of each other):**
- Task 1 (P0, destructive Lexical fix)
- Task 2 (P1, transcript file naming)
- Task 3 (P1, chapter timestamps)
- Task 4 (P1, emdash spacers)
- Task 5 (P1, TTBOOK references)
- Task 6 (P1, published_at dates)

**Group 2 (infrastructure — depends on nothing):**
- Task 7 (P2, validate_episode.py)
- Task 8 (P1, submodule URLs)
- Task 9 (P1, nested submodule removal)

Within Group 1, tasks 3+4 touch the same file (`content_transforms.py`) and share a test file — run them sequentially. All others are independent.

Task 9 should run after Task 8 (URL update) so the submodule pointer commit uses the correct remote.
