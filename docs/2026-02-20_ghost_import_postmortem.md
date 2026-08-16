# Ghost Import Post-Mortem: WC S01E04 (George Saunders)

**Date:** 2026-02-20
**Episode:** George Saunders: Angels, Ghosts and the Moral Imagination
**Show:** Wonder Cabinet (PRX podcast 120)
**Operator:** Claude Code via `/ghost-import` skill
**Final outcome:** Draft successfully created with all sections correct

---

## Timeline

| Time | Action | Result |
|------|--------|--------|
| 18:55 | Connectivity tests | Failed — used bare `python3` instead of `.venv/bin/python` |
| 18:55 | Retry with venv | Both Ghost and PRX APIs connected |
| 18:56 | Transcript discovery (Step 1.5) | Checked `shows/wonder-cabinet/episodes/` — empty. Missed transcript in transcription module |
| 18:56 | Dry run | Found Saunders episode, 1 new |
| 18:57 | Import (without transcript) | Post created, audio uploaded (64MB, 22s), Lexical visibility applied, PRX writeback done |
| — | User noted local transcript exists in transcription module | — |
| ~19:00 | Attempted to append transcript via `html=` update | **Destroyed entire Lexical structure** — replaced multi-card post with single HTML card |
| ~19:05 | Deleted corrupted post, removed from state, re-imported | Clean post recreated (another 64MB audio upload) |
| ~19:10 | Manually appended transcript as Lexical HTML node | Transcript added but with wrong format (kg-card wrappers, id attr, no h3, no speaker bolding) |
| 20:50 | User asked to compare with previous post (Solnit) | Discovered 4 formatting differences |
| ~21:00 | Fixed transcript format to match Solnit | Correct: class-only div, h3, escaped entities, web-only visibility |
| ~21:05 | Discovered wrong transcript file used | `WC_S01_04_transcript.txt` = raw (no speakers). `formatted_transcript.md` = correct (speaker attribution) |
| ~21:10 | Replaced transcript with formatted version | Correct speaker bolding now matches Solnit |
| ~21:15 | User spotted broken link section | Source names discarded, descriptions used as link text |
| ~21:20 | Fixed links on live post | Matches Solnit format |
| ~21:25 | Verified PRX writeback | URL correct on PRX, fixed state tracker flag |

## Total wasted effort
- **2 full audio uploads** (64MB each) — one for the corrupted post, one for the re-import
- **3 transcript updates** to the live post before getting it right
- **1 link fix** on the live post

---

## Issues Encountered (6 total)

### Issue 1: Venv not in skill commands
**Severity:** Low (every session, easy workaround)
**What happened:** `/ghost-import` skill uses `python3 -m src.main` but dependencies are in `.venv/`. First command always fails with `ModuleNotFoundError`.
**Filed:** [PBS #5](https://github.com/Wonder-Cabinet-Productions/podcast-publishing-suite/issues/5)

### Issue 2: Transcript discovery missed transcription module
**Severity:** Medium (led to import without transcript)
**What happened:** Step 1.5 of the skill only checks `shows/wonder-cabinet/episodes/` (canonical path). The actual transcript was in `modules/podcast-whisper-transcription/audio-to-transcribe/WC_S01_04_Saunders/`. The skill has no fallback to check the transcription module's working directory.
**Filed:** [PBS #5](https://github.com/Wonder-Cabinet-Productions/podcast-publishing-suite/issues/5)

### Issue 3: `load_wc_transcript()` filename matching failure
**Severity:** Medium (even when pointed at the right directory, couldn't find the file)
**What happened:** Function extracts "George Saunders" from episode title and searches `*.txt` filenames. The file is `WC_S01_04_transcript.txt` (episode code, not guest name). Also doesn't check parent directory name (`WC_S01_04_Saunders` contains "Saunders"). Also doesn't look for `formatted_transcript.md`.
**Filed:** [Publisher #20](https://github.com/mriechers/prx-to-ghost-publisher/issues/20)

### Issue 4: HTML update destroyed Lexical post (DATA LOSS)
**Severity:** **Critical** — silent data destruction
**What happened:** Attempted to append transcript to existing post by reading `post.html` (returned empty for Lexical posts) and updating with `GhostPost(html=new_html)`. Ghost replaced the entire multi-card Lexical structure with a single HTML card. Lost: audio player with web-only visibility, email CTA with email-only visibility, show notes, link cards.
**Root cause:** Lexical posts store content in the `lexical` field, not `html`. The `html` field reads as empty. Writing `html=` triggers Ghost to discard Lexical and convert the new HTML, producing a single undifferentiated card.
**The `update-transcripts` CLI command has this same bug** (lines 1286-1295 of `main.py`).
**Filed:** [Publisher #18](https://github.com/mriechers/prx-to-ghost-publisher/issues/18)

### Issue 5: Wrong transcript file and format
**Severity:** Medium (produced visually broken output)
**What happened:** Three compounding problems:
1. Used `WC_S01_04_transcript.txt` (raw Whisper output, no speaker attribution) instead of `formatted_transcript.md` (has `**Speaker:**` markdown format)
2. Used `build_transcript_section_html()` which produces HTML meant as *input* to Ghost's HTML-to-Lexical converter — not suitable for direct Lexical node injection
3. Result had `<!--kg-card-begin-->` wrappers, `id=` attribute, `<h2>` instead of `<h3>`, unescaped apostrophes — none of which match Ghost's normalized format

**Correct format** (as seen in Solnit post, which went through the full pipeline):
```html
<div class="episode-transcript"><h3>Transcript</h3><p><strong>Anne Strainchamps:</strong>...
```
- No `kg-card` comments
- No `id=` attribute (class only)
- `<h3>` not `<h2>`
- Apostrophes as `&#x27;`
- Speaker names in `<strong>` tags

### Issue 6: Link formatter discards source names
**Severity:** Medium (visible formatting error in every affected post)
**What happened:** PRX description has links in this format:
```html
<a href="..."><strong>To the Best of Our Knowledge</strong></a> — On his short story collection...
```
The source name is *inside* the `<a>` tag. `transform_li()` strips the `<a>` tag to find "descriptive text", discarding the source name. The remaining text (`— On his short story collection...`) becomes the link text.
**Filed:** [Publisher #22](https://github.com/mriechers/prx-to-ghost-publisher/issues/22)

---

## No-import path for post-hoc transcript addition
**Filed:** [Publisher #19](https://github.com/mriechers/prx-to-ghost-publisher/issues/19) and [Publisher #21](https://github.com/mriechers/prx-to-ghost-publisher/issues/21)

There is no supported way to add a transcript to an already-imported post:
- `update-transcripts` only handles RSS feeds, not local files
- `update-transcripts` uses the HTML update path which destroys Lexical posts (#18)
- No `reset-episode` command to clear state and re-import cleanly

The only option today is manual: delete post via API, hand-edit state JSON, re-run sync. This is what we had to do.

---

## Key Lessons for Future Imports

### Before importing
1. **Always use `.venv/bin/python`** — not bare `python3`
2. **Check both locations for transcripts:**
   - Canonical: `shows/{show}/episodes/{slug}/`
   - Transcription module: `modules/podcast-whisper-transcription/audio-to-transcribe/{episode_code}/`
3. **Use `formatted_transcript.md`**, not `*_transcript.txt` — only the formatted version has speaker attribution
4. **Pass `--transcript-dir`** when a local transcript exists — avoids needing to add it later

### If you need to modify a Lexical post after import
1. **NEVER update via `html=`** — this destroys the Lexical structure
2. **Read the `lexical` field**, parse as JSON, modify the `root.children` array directly
3. **Match Ghost's normalized format** when creating HTML nodes:
   - No `<!--kg-card-begin-->` wrappers
   - No `id=` attributes (use `class=` only)
   - `<h3>` for transcript header (Ghost downgrades from `<h2>`)
   - Escape apostrophes as `&#x27;`
4. **Set visibility on the node directly** using the `VISIBILITY_WEB_ONLY` constant
5. **PUT the modified Lexical JSON** back via the admin API

### If an import goes wrong
1. Delete the Ghost post via admin API (status 204 = success)
2. Remove the episode entry from `data/published_episodes.{env}.json`
3. Re-run `sync` — it will pick up the episode as new
4. (Future: use `reset-episode --guid` when #21 is implemented)

---

## Filed Issues Summary

| # | Repo | Title | Priority |
|---|------|-------|----------|
| [PBS #5](https://github.com/Wonder-Cabinet-Productions/podcast-publishing-suite/issues/5) | podcast-publishing-suite | ghost-import skill: venv, transcript discovery, formatted_transcript.md | — |
| [#18](https://github.com/mriechers/prx-to-ghost-publisher/issues/18) | prx-to-ghost-publisher | update-transcripts overwrites Lexical posts via HTML path | High |
| [#19](https://github.com/mriechers/prx-to-ghost-publisher/issues/19) | prx-to-ghost-publisher | update-transcripts: add --transcript-dir for local files | Normal |
| [#20](https://github.com/mriechers/prx-to-ghost-publisher/issues/20) | prx-to-ghost-publisher | load_wc_transcript() fails to match transcription module naming | Normal |
| [#21](https://github.com/mriechers/prx-to-ghost-publisher/issues/21) | prx-to-ghost-publisher | Add reset-episode command | Normal |
| [#22](https://github.com/mriechers/prx-to-ghost-publisher/issues/22) | prx-to-ghost-publisher | Link formatter discards source name inside `<a>` tag | Normal |
