# Ghost Post Audit — All Wonder Cabinet Episodes

**Date:** 2026-02-20
**Audited by:** Claude Code
**Reference post:** Rebecca Solnit (the only post with zero issues)

---

## Summary

| # | Episode | Status | Issues |
|---|---------|--------|--------|
| 1 | Introducing Wonder Cabinet | published | 4 issues |
| 2 | Coming Soon! Wonder Cabinet! | **404 — post deleted/missing** | — |
| 3 | Sophie Strand | published | 3 issues |
| 4 | Carlo Rovelli | **404 — post deleted/missing** | — |
| 5 | Rebecca Solnit | published | **None (reference post)** |
| 6 | George Saunders | scheduled | **None (fixed during this session)** |

---

## Reference Format (Solnit — correct)

```
[0] html     WEB-ONLY    Audio player (wc-audio-player div)
[1] html     EMAIL-ONLY  Email CTA (wc-email-cta div, brand green #10a544)
[2] paragraph            Description paragraphs...
[N] html     BOTH        Episode links (wc-episode-notes-content-links)
[N] html     WEB-ONLY    Transcript (div.episode-transcript, <h3>, speaker <strong>)
```

Key format properties:
- Audio player: `wc-audio-player` class, **web-only** visibility
- Email CTA: `wc-email-cta` class, **email-only** visibility, brand green `#10a544`
- Links: source name as `<a>` text, description as suffix
- Transcript: `<div class="episode-transcript">`, `<h3>Transcript</h3>`, no `kg-card` wrappers, no `id=`, `&#x27;` for apostrophes, `<strong>Speaker:</strong>` format

---

## Post-by-Post Findings

### 1. Introducing Wonder Cabinet

**Post ID:** `697c47ef00bb33000106877e` | **Status:** published | **Slug:** `introducing-wonder-cabinet`

**Structure:**
```
[0] html     BOTH(!)     Audio player
[1] paragraph            Description...
[2] paragraph            Description...
[3] paragraph            Description...
[4] paragraph            Description...
```

**Issues:**
1. **Audio player visibility is BOTH, not WEB-ONLY** — the `email.memberSegment` is set to `status:free,status:-free` (visible to email subscribers). Should be email-only empty string. This means the audio player HTML div shows in email newsletters where it can't render.
2. **Missing email CTA** — no `wc-email-cta` node at all. Email subscribers don't get a "Listen to this episode" button.
3. **No transcript** — `transcript_synced: false` in state. May be intentional (trailer/intro episode).
4. **No episode links section** — no `wc-episode-notes-content-links`. May be intentional (no external links in this episode).

**Assessment:** Issues 1-2 are real bugs from an early import before the CTA feature existed. Issues 3-4 may be intentional for a trailer episode. Audio player visibility should still be fixed.

---

### 2. Coming Soon! Wonder Cabinet!

**Post ID:** `697c482100bb330001068783` | **Status:** 404

The Ghost post no longer exists but is still tracked in state (`prx_writeback_done: false`, `ghost_slug: ""`). This is a teaser/promo episode.

**Action needed:** Remove from state tracker or re-import if the post was accidentally deleted.

---

### 3. Sophie Strand: Ecological Storytelling and Mythic Imagination

**Post ID:** `697db99300bb33000106882a` | **Status:** published | **Slug:** `sophie-strand-ecological-storytelling-and-mythic-imagination`

**Structure:**
```
[0]  html            WEB-ONLY     Audio player
[1]  html            EMAIL-ONLY   CTA (but missing wc-email-cta class!)
[2]  paragraph                    Description...
[3]  paragraph                    Description...
[4]  paragraph                    Description...
[5]  paragraph                    Description...
[6]  paragraph                    Description...
[7]  html            BOTH         Links (wc-episode-notes-content-links)
[8]  extended-heading              (empty?)
[9]  html            WEB-ONLY     Transcript (has issues)
[10] paragraph                    (empty?)
```

**Issues:**
1. **Email CTA missing `wc-email-cta` class** — The CTA button exists and has correct email-only visibility, but uses inline styles without the `wc-email-cta` class name. The HTML is:
   ```html
   <div style="text-align: center; margin: 24px 0;">
     <a href="..." style="...background-color: #10A544...">Listen to this episode →</a>
   </div>
   ```
   vs Solnit's correct format:
   ```html
   <div class="wc-email-cta" style="text-align: center; margin: 24px 0;">...</div>
   ```
   This means the theme CSS targeting `.wc-email-cta` won't apply, and the Lexical visibility scanner (which checks for `wc-email-cta` string) won't detect it for future re-processing.

2. **Transcript has `<!--kg-card-begin: html-->` wrappers** — Was likely added manually post-import, not through the two-pass pipeline. The wrappers are raw HTML that shouldn't be in Lexical.

3. **Transcript uses `<h2>` instead of `<h3>`** and is missing the `<div class="episode-transcript">` wrapper — doesn't match the normalized format. The transcript content itself is correct (has `<strong>Speaker:</strong>` bolding with `&#x27;` escaping).

4. **Stale nodes:** An empty `extended-heading` at [8] and empty paragraph at [10] — probably artifacts from manual editing in Ghost admin.

---

### 4. Carlo Rovelli: Cosmic Mysteries and the Politics of Wonder

**Post ID:** `6986911eaa8b2100016a9c28` | **Status:** 404

The Ghost post no longer exists but is still tracked in state (`prx_writeback_done: true`, `ghost_slug: ""`).

**Action needed:** Remove from state tracker and re-import. The PRX writeback was done but to what URL? The empty `ghost_slug` suggests the slug wasn't recorded.

---

### 5. Rebecca Solnit: Hope After the End (REFERENCE — no issues)

**Post ID:** `6990234ae3e894000119a2ea` | **Status:** published | **Slug:** `rebecca-solnit-hope-after-the-end`

**Structure:**
```
[0] html     WEB-ONLY     Audio player
[1] html     EMAIL-ONLY   Email CTA (wc-email-cta class ✓)
[2] paragraph              Description
[3] paragraph              Description
[4] html     BOTH         Links
[5] html     WEB-ONLY     Transcript (class-only div ✓, <h3> ✓, <strong> ✓, &#x27; ✓)
```

This is the gold standard. All sections present, correct visibility, correct formatting.

---

### 6. George Saunders: Angels, Ghosts and the Moral Imagination (FIXED)

**Post ID:** `69991d73e3ea5c00018c4466` | **Status:** scheduled | **Slug:** `george-saunders-angels-ghosts-and-the-moral-imagination`

**Structure:**
```
[0] html     WEB-ONLY     Audio player
[1] html     EMAIL-ONLY   Email CTA (wc-email-cta class ✓)
[2-5] paragraphs           Description
[6] html     BOTH         Links (fixed during this session)
[7] html     WEB-ONLY     Transcript (fixed during this session)
```

All issues from the import session were resolved. Matches Solnit format.

---

## Fixes Applied (2026-02-21)

All issues below were resolved by directly modifying Lexical JSON via `update_post_lexical()`.

### Introducing Wonder Cabinet (`697c47ef00bb33000106877e`)
- Fixed audio player visibility from BOTH to WEB-ONLY
- Added email CTA node with `wc-email-cta` class and EMAIL-ONLY visibility

### Sophie Strand (`697db99300bb33000106882a`)
- Added `wc-email-cta` class to CTA div, normalized inline styles to match Solnit
- Fixed transcript: stripped `<!--kg-card-begin-->` wrappers, added `<div class="episode-transcript">` wrapper, changed `<h2>` to `<h3>`
- Removed empty extended-heading and trailing paragraph nodes

### Carlo Rovelli (`69869aa3aa8b2100016a9c3a`)
- Added `wc-email-cta` class to CTA div, normalized inline styles to match Solnit
- Fixed transcript: removed `id="episode-transcript"` (class-only), changed `<h2>` to `<h3>`

### State tracker cleanup
- Removed stale "Coming Soon! Wonder Cabinet!" entry (Ghost post deleted)
- Fixed Rovelli `ghost_post_id` from stale ID to actual `69869aa3aa8b2100016a9c3a`
- Filled in missing `ghost_slug` values for Sophie Strand and Carlo Rovelli

### Verification

All posts now match the Solnit reference structure:

```
[0] Audio player    WEB-ONLY
[1] Email CTA       EMAIL-ONLY   [wc-email-cta class]
[2-N] Paragraphs    -
[N] Links           BOTH         [wc-episode-notes-content-links]
[N] Transcript      WEB-ONLY     [div.episode-transcript, h3, no id=, no kg-card]
```

(Introducing WC has no links or transcript — intentional for trailer episode.)

---

## Pipeline Evolution Timeline

Based on the differences across posts, the pipeline clearly evolved:

| Episode | Import era | CTA format | Transcript format | Notes |
|---------|-----------|------------|-------------------|-------|
| Introducing WC | Earliest | No CTA → **fixed** | No transcript | Pre-CTA feature; CTA added retroactively |
| Sophie Strand | Early | Inline-style CTA (no class) → **fixed** | Manual add (kg-card, h2, no wrapper div) → **fixed** | All issues resolved |
| Carlo Rovelli | Mid | Inline-style CTA (no class) → **fixed** | Manual add (id=, h2) → **fixed** | State tracker also corrected |
| Solnit | Current | `wc-email-cta` class | Full pipeline (class div, h3, normalized) | Reference standard |
| Saunders | Current (fixed) | `wc-email-cta` class | Manual add then fixed | Matches Solnit after corrections |

Format stabilized at the Solnit import. All earlier posts have been retroactively fixed to match.
