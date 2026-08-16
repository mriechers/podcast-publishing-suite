# TTBook Import Fixes: Waveform, Transcript Visibility, Link Formatting

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three issues blocking clean Wonder Cabinet episode imports: maxed-out waveform, transcript visible in email, and broken show notes links.

**Architecture:** Three independent, targeted fixes in existing files. No new files needed.

**Tech Stack:** Python, audiowaveform CLI, Ghost Lexical JSON

---

### Task 1: Fix waveform peaks bit depth

**Files:**
- Modify: `src/waveform_peaks.py:100`
- Test: `tests/test_content_builder.py` (no new test needed — this is a default param change verified by re-import)

- [ ] **Step 1: Change default bits from 8 to 16**

In `src/waveform_peaks.py`, line 100, change:

```python
    bits: int = 8,
```

to:

```python
    bits: int = 16,
```

- [ ] **Step 2: Verify audiowaveform accepts the change**

Run:
```bash
echo "Test" | audiowaveform --help 2>&1 | grep -i bits
```
Expected: Documentation showing `--bits` accepts 8 or 16.

- [ ] **Step 3: Commit**

```bash
git add src/waveform_peaks.py
git commit -m "fix: use 16-bit peaks for better waveform dynamic range"
```

---

### Task 2: Fix transcript section HTML for email visibility

**Files:**
- Modify: `src/content_builder.py:862-867`
- Test: `tests/test_content_builder.py:284-292` (existing test already expects correct format)

- [ ] **Step 1: Run the existing failing test to confirm it fails**

Run:
```bash
.venv/bin/python -m pytest tests/test_content_builder.py::TestTranscriptSectionHTML::test_section_has_correct_structure -v
```
Expected: FAIL — test expects `<!--kg-card-begin: html-->`, `id="episode-transcript"`, and `<h2>` but current code outputs bare `<div>` with `<h3>`.

- [ ] **Step 2: Fix build_transcript_section_html()**

In `src/content_builder.py`, replace lines 862-867:

```python
    return (
        '<div class="episode-transcript">'
        '<h3>Transcript</h3>'
        f'{transcript_html}'
        '</div>'
    )
```

with:

```python
    return (
        '<!--kg-card-begin: html-->\n'
        '<div id="episode-transcript" class="episode-transcript">\n'
        '<h2>Transcript</h2>\n'
        f'{transcript_html}\n'
        '</div>\n'
        '<!--kg-card-end: html-->'
    )
```

This ensures:
- Ghost preserves it as a discrete Lexical HTML node
- `process_lexical_visibility()` finds `"episode-transcript"` in `child.get("html")` and applies `VISIBILITY_WEB_ONLY`
- Transcript is hidden in email, visible on web

- [ ] **Step 3: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m pytest tests/test_content_builder.py::TestTranscriptSectionHTML::test_section_has_correct_structure -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/content_builder.py
git commit -m "fix: restore Ghost card markers on transcript section for email visibility"
```

---

### Task 3: Fix double-processed show notes links

**Files:**
- Modify: `src/content_builder.py:1268`

- [ ] **Step 1: Remove format_episode_links() call from build_post_html()**

In `src/content_builder.py`, lines 1264-1269, change:

```python
    if episode.description:
        description = strip_boilerplate(episode.description, feed_type)
        description = sanitize_html(description)
        description = format_episode_links(description)
        sections.append(description)
```

to:

```python
    if episode.description:
        description = strip_boilerplate(episode.description, feed_type)
        description = sanitize_html(description)
        sections.append(description)
```

`strip_boilerplate()` already applies `_reformat_plain_text_links()` and `_style_link_lists()` via `TTBOOK_CONFIG.custom_transforms`. The second pass through `format_episode_links()` was clobbering already-transformed links.

- [ ] **Step 2: Run full test suite**

Run:
```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: All tests pass (no tests depend on format_episode_links being called from build_post_html).

- [ ] **Step 3: Commit**

```bash
git add src/content_builder.py
git commit -m "fix: remove double link processing in ttbook build_post_html"
```

---

### Task 4: Verify with re-import

- [ ] **Step 1: Delete existing Haskell draft from Ghost**

```python
client.delete_post('69c751e05c589800013c34ef')  # or via API
```

- [ ] **Step 2: Clear Haskell from state tracker**

Remove the `prx_120_6f754c1c-3871-4219-978f-896cb11797be` entry from `data/published_episodes.prod.json`.

- [ ] **Step 3: Re-import with transcript-dir**

```bash
.venv/bin/python -m src.main --env prod sync --source api --feed-type ttbook \
  --status draft --limit 1 \
  --transcript-dir "/Volumes/Mark's SSD/Developer/wonder-cabinet/podcast-publishing-suite/shows/wonder-cabinet/episodes/WC_S01_07_David_Haskell" \
  --yes
```

- [ ] **Step 4: Verify post structure in Ghost**

Check:
- Waveform has visible dynamic range (not maxed out)
- Transcript section is NOT visible in email preview
- Show notes links have readable labels (not raw URLs)
- Email CTA button present and email-only
- Audio player loads
