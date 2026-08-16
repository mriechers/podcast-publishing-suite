# Show Notes Formatting Guide

> **Last Updated**: 2026-02-14
> **Applies to**: Wonder Cabinet, Luminous

This guide documents the preferred formatting conventions for episode show notes written in Google Docs and pasted into PRX Dovetail. The PRX-to-Ghost import pipeline depends on these conventions to properly transform content.

---

## Table of Contents

1. [Overview](#overview)
2. [Description Structure](#description-structure)
3. [Link Formatting](#link-formatting)
4. [Sections the Pipeline Strips](#sections-the-pipeline-strips)
5. [Chapter Markers](#chapter-markers)
6. [Inline Formatting](#inline-formatting)
7. [Show-Specific Notes](#show-specific-notes)

---

## Overview

Episode show notes flow through this pipeline:

```
Google Docs  →  PRX Dovetail  →  Import Pipeline  →  Ghost CMS
(authoring)     (paste HTML)     (transforms)        (publishing)
```

Google Docs preserves hyperlinks and basic formatting (bold, italic, lists) when content is pasted into PRX. The import pipeline then:

1. Strips boilerplate (show descriptions, social links, dividers, credits)
2. Sanitizes HTML (removes scripts, iframes, event handlers)
3. Reformats links (adds CSS classes, `target="_blank"`, smart label splitting)
4. Wraps link lists in Ghost HTML cards for theme styling

Getting the format right in Google Docs means the pipeline can do its job cleanly.

---

## Description Structure

### Short Description (under 150 characters)

This appears in podcast app previews. It must work as a standalone sentence.

**Good**: "As institutions unravel, Solnit argues despair is a mistake -- and that a more just world is already being born."

**Bad**: "Rebecca Solnit joins us to discuss hope, gardens, and..." (trailing off, not a complete thought)

### Full Description (under 4,000 characters)

Structure the full description as prose paragraphs. The pipeline preserves `<p>`, `<em>`, `<strong>`, `<a>`, `<ul>`, `<ol>`, `<li>`, `<h2>`, `<h3>`, `<h4>`, and `<blockquote>` tags. Everything else is stripped.

**Template structure** (in the Google Doc):

```
[2-3 paragraphs of episode description with inline hyperlinks]

[Disclaimer paragraph in italics, if applicable]

---

[Bulleted list of episode resource links]

---

[Chapter markers - timestamps with titles]

---

[Show boilerplate - hosts, website, subscribe links]
```

The pipeline strips everything from the dividers onward (links, chapters, boilerplate). The link list is preserved but reformatted for Ghost styling.

---

## Link Formatting

### Preferred Format: Hyperlinked Labels

Use **Cmd+K** in Google Docs to create hyperlinks with short, descriptive label text. This is the format that works best across the entire pipeline.

**Do this** (hyperlinked labels):
- [TTBOOK Interview](https://www.ttbook.org/interview/...) -- Carlo Rovelli's white holes, where time dissolves
- [Carlo Rovelli's Website](https://www.cpt.univ-mrs.fr/~rovelli/) -- Official research and publications
- [Pre-order "The Beginning Comes After the End"](https://bookshop.org/...) -- due March 3

**Avoid this** (bare URLs):
- Deep Time: Carlo Rovelli's white holes: https://www.ttbook.org/interview/carlo-rovellis-white-holes-where-time-dissolves
- More from Carlo Rovelli: https://www.cpt.univ-mrs.fr/~rovelli/

### Why Hyperlinked Labels Matter

| Stage | Bare URLs | Hyperlinked Labels |
|-------|-----------|-------------------|
| **Podcast apps** | Raw URL displayed as text | Clean clickable label |
| **PRX Dovetail** | URL visible in description | Label with hidden URL |
| **Ghost import** | Pipeline must guess what to link | Pipeline preserves your labels |
| **Email newsletter** | Ugly long URLs | Clean, styled links |

### How the Pipeline Handles Links

The import pipeline (`format_episode_links()` in `content_builder.py`) processes links in `<ul>` elements:

1. **Already-hyperlinked labels**: Preserved as-is, with `target="_blank"` and `rel="noopener noreferrer"` added
2. **Bare URLs with preceding text**: The text before the URL becomes the link label (smart splitting applied)
3. **Bare URLs without text**: The URL itself becomes the link label (worst case)

### Smart Link Splitting (for legacy bare-URL format)

When the pipeline encounters bare URLs with descriptive text, it applies heuristics to avoid hyperlinking entire paragraphs:

| Text Pattern | What Gets Linked | Example |
|-------------|-----------------|---------|
| Short text (60 chars or fewer) | Entire text | "Rebecca Solnit's newsletter" |
| Text with "quoted title" | Quoted portion | Pre-order **"The Book Title"**, on sale now |
| Text with colon (prefix under 50 chars) | Text before colon | **Program Name**: Long episode description... |
| Long text, no quotes or colon | Entire text (fallback) | Full descriptive paragraph |

Using hyperlinked labels from the start avoids this heuristic entirely -- the pipeline simply uses your labels.

### Links Must Be in a Bulleted List

The pipeline only transforms links inside `<ul>` (bulleted list) elements. Links in regular paragraphs are left as-is. Always format your resource links as a bulleted list in Google Docs.

---

## Sections the Pipeline Strips

The following content is automatically removed during import. You should still include it in the PRX description (for podcast apps and the RSS feed), but it won't appear in the Ghost post.

### Wonder Cabinet (`content_transforms.py` TTBOOK_CONFIG)

| Content | Pattern | Notes |
|---------|---------|-------|
| Dash dividers | `--` or `---` on their own line | Used to separate sections in PRX |
| Chapter markers | `Chapters:` heading or consecutive timestamp paragraphs | Stripped; Ghost theme handles chapters separately |
| "Hosted by" line | `Wonder Cabinet is hosted by Anne Strainchamps and Steve Paulson.` | Credits are in the theme footer |
| Promotional footer | `Visit/Find out more...wondercabinetproductions.com...` | Website promo handled by theme |
| Subscription reminder | `keep your subscription active` | Not needed in Ghost |

### Luminous (`content_transforms.py` LUMINOUS_CONFIG)

| Content | Pattern | Notes |
|---------|---------|-------|
| Full boilerplate | Everything from `Original Air Date:` onward | Removes air date, guest lists, subscribe links |
| "About Luminous" section | `About Luminous` heading + description paragraph | Show description is in the theme |
| Subscribe links | `Never want to miss an episode?` | Ghost has its own subscription |
| "For more from Luminous" | Link to ttbook.org/luminous | Ghost replaces this |

### Important

If you change the wording of boilerplate sections (e.g., renaming "Wonder Cabinet is hosted by" to "Your hosts are"), the regex patterns in `content_transforms.py` won't match and the boilerplate will leak through to Ghost. Stick to the established patterns or update the transform rules.

---

## Chapter Markers

Chapter markers are stripped from the Ghost post (the theme handles them separately), but they're preserved in the PRX feed for podcast apps that support chapters.

### Preferred Format

```
00:00:00 Introduction & The Chirp of Black Holes
00:04:10 Early Years in Verona
00:10:00 Falling in Love with Physics
00:17:30 Search for Truth
00:25:05 Politics of Wonder
```

### Format Rules

- Use `HH:MM:SS` format (zero-padded)
- One timestamp per line
- Title follows the timestamp, separated by a space
- No bullet points or list formatting -- plain lines
- Place after a `---` divider, before the show boilerplate

### What the Pipeline Matches

Two chapter formats are recognized for stripping:

1. **Heading format**: A `Chapters:` heading followed by a paragraph with `<br>`-separated timestamps
2. **Paragraph format**: Consecutive `<p>00:00:00 Title</p>` paragraphs (2+ required to avoid false positives)

---

## Inline Formatting

### Supported in Ghost Import

| Format | Google Docs | Ghost Result |
|--------|-------------|-------------|
| **Bold** | Cmd+B | `<strong>` |
| *Italic* | Cmd+I | `<em>` |
| [Hyperlink](url) | Cmd+K | `<a href="url">` |
| Bulleted list | List button | `<ul><li>` |
| Numbered list | List button | `<ol><li>` |

### Not Supported / Stripped

| Format | What Happens |
|--------|-------------|
| Headings (H1-H6) | Preserved but rarely needed in episode descriptions |
| Images | Stripped (use Ghost's image upload instead) |
| Tables | Stripped |
| Fonts/colors | Stripped (Ghost theme controls styling) |
| Comments | Stripped |

### Book Titles and Show Names

- Book titles: Use italic with a hyperlink to a bookshop/publisher page
  - Example: *[Seven Brief Lessons on Physics](https://www.penguinrandomhouse.com/...)*
- Show names: Use italic only (no link needed for our own shows)
  - Example: *To The Best Of Our Knowledge*

---

## Show-Specific Notes

### Wonder Cabinet

- **Title format**: `Guest Name: Topic Description` (under 60 characters)
  - The pipeline does NOT strip a show prefix (Wonder Cabinet titles don't have one)
- **Primary tag**: `Wonder Cabinet`
- **Authors**: Anne Strainchamps and Steve Paulson (set automatically)
- **Disclaimer**: Include the WPM non-affiliation disclaimer in italics at the end of the description body

### Luminous

- **Title format**: `Luminous: Episode Title`
  - The pipeline strips the `Luminous: ` prefix automatically
- **Primary tag**: `Luminous`
- **Authors**: Steve Paulson (set automatically)
- **URL prefix**: Posts live at `/luminous/{slug}/` (handled automatically)

---

## Quick Reference

### Google Docs Checklist (per episode)

- [ ] Short description under 150 characters, complete thought
- [ ] Full description under 4,000 characters
- [ ] Inline hyperlinks in body text (Cmd+K on book titles, show references, etc.)
- [ ] Resource links as a bulleted list with hyperlinked labels (not bare URLs)
- [ ] Chapter markers in `HH:MM:SS Title` format
- [ ] Boilerplate uses standard wording (don't rephrase -- the pipeline matches it by regex)
- [ ] Sections separated by `---` dividers

### PRX Paste Checklist

- [ ] Paste from Google Docs (preserves hyperlinks and formatting)
- [ ] Verify links are clickable in PRX preview
- [ ] Don't manually edit HTML in PRX (can break formatting)
