# WC -- Episode Prep Workflow Notes (S01E01)

Session notes from the first episode prep run using Claude Code. The goal is to work out a repeatable automation workflow for producing two deliverables per episode:

1. **Show description package** -- description text, links, chapter markers, boilerplate/sign-off
2. **Formatted transcript** -- clean, stitched transcript posted to Google Drive

---

## What Was Done This Session

### Transcription
- Transcribed 3 MP3 files in `~/Developer/transcription/WC_101/` using OpenAI Whisper (turbo model)
- Files:
  - `WC_S01_001_01.mp3` (37MB, ~27 min) -- Part 1 of interview
  - `WC_S01_001_house ad.mp3` (743KB, ~30 sec) -- Mid-roll promo
  - `WC_S01_001 _02.mp3` (15MB, ~11 min) -- Part 2 of interview
- Output: each file gets a subfolder with txt, vtt, srt, tsv, json formats
- Script: `~/Developer/the-lodge/scripts/whisper-transcribe.sh`

### Chapter Markers
- Generated detailed chapter timestamps treating the 3 parts as a single combined file (01 -> house ad -> 02)
- Calculated offsets: Part 01 starts at 0:00, house ad at ~27:19, Part 02 at ~27:49
- Total combined runtime: ~39:00
- Initially produced 18 granular topic markers, then consolidated to 6 per Apple Podcasts guidelines

### Apple Podcasts Chapter Format
- Reference doc at `~/Developer/transcription/timestamps.md` has the full spec
- Key constraints applied:
  - Max 6 chapters per hour
  - Each chapter >= 2 minutes
  - Titles: fewer than 5 words, max 45 chars, title case
  - No repeated words across chapter titles
  - Format: `HH:MM:SS Title`

**Final chapters for S01E01:**
```
00:00:00 Meet Sophie Strand
00:04:34 Body as Ancestor
00:10:08 Roots of Sin
00:18:21 Spores and Consciousness
00:27:49 Stories We Can't Explain
00:35:39 Science as Wonder
```

**JSON (Podcasting 2.0) version:**
```json
{
  "version": "1.2.0",
  "chapters": [
    { "startTime": 0, "title": "Meet Sophie Strand" },
    { "startTime": 274, "title": "Body as Ancestor" },
    { "startTime": 608, "title": "Roots of Sin" },
    { "startTime": 1101, "title": "Spores and Consciousness" },
    { "startTime": 1669, "title": "Stories We Can't Explain" },
    { "startTime": 2139, "title": "Science as Wonder" }
  ]
}
```

### Transcript to Google Drive
- Stitched Part 01 + Part 02 transcripts (skipping house ad) into a single document
- Posted as Google Doc titled "101 - Sophie Strand" in the WC transcripts folder
- Folder: https://drive.google.com/drive/u/0/folders/1yb8YzWGpMcJ4kSgDpr6YHs4hcwysP05Z
- Doc ID: `1R1tsXEBLalgQ_29vOaOezpnxeQCbLX-Eqd1-ov2jRT8`
- Uses the **personal** Google account (MCP server: `google-docs-personal`)

---

## Infrastructure Notes

### Whisper Setup
- Installed via pipx, runs locally on Apple Silicon
- Current issue: Falls back to FP32 on CPU instead of using Metal/MPS GPU acceleration
- Turbo model is fine for quality; speed could improve if MPS is enabled in the torch build
- First run downloads model (~1.5GB), subsequent runs are fast

### Google Docs MCP Server
- Located at `~/Developer/the-lodge/mcp-servers/google-docs-mcp/`
- OAuth token expired during session (`invalid_grant` error)
- Fix: delete `credentials/personal/token.json`, re-run `node dist/server.js` with env vars to trigger browser OAuth flow
- Token path: `credentials/personal/token.json`
- Do NOT use the `google-docs-work` MCP for this project

### Reference Docs
- `~/Developer/transcription/timestamps.md` -- Chapter format spec for Apple, Spotify, YouTube
- `~/Developer/transcription/formatter.md` -- Was listed in directory but may have been removed; investigate if it contained transcript formatting rules

---

## Episode Structure Discovered

The raw audio for an episode arrives as multiple files:

```
WC_S01_001_01.mp3    <- Interview Part 1 (includes host intro/cold open)
WC_S01_001_house ad.mp3  <- Mid-roll promo spot
WC_S01_001 _02.mp3   <- Interview Part 2 (includes credits/sign-off)
```

The naming convention appears to be: `WC_S{season}_{episode}_{segment}.mp3`

Note: the `_02` file has a stray space before the underscore in the filename.

---

## Toward a Repeatable Workflow

### Two Deliverables Per Episode

**Deliverable 1: Show Description Package**
- Episode title
- Short description / summary
- Guest bio
- Chapter markers (HH:MM:SS format for episode description)
- Chapter markers (JSON for RSS/Podcasting 2.0)
- Links mentioned in episode (books, substacks, websites)
- Boilerplate sign-off / newsletter CTA

**Deliverable 2: Formatted Transcript**
- Stitched from all interview segments (excluding ads/promos)
- Posted as Google Doc in the WC transcripts Drive folder
- Potentially needs further formatting (speaker labels, paragraph breaks, etc.)

### Open Questions / Order of Operations

- [ ] What comes first -- chapters or transcript? (Chapters need content understanding; transcript is the raw material)
- [ ] Should chapters be generated from the detailed 18-point outline, then consolidated? Or go straight to 6?
- [ ] How much transcript cleanup is expected? Raw Whisper output vs. edited for readability?
- [ ] Should the show description be a Google Doc too, or a different format (markdown, Airtable, etc.)?
- [ ] Is there a template for the show description package?
- [ ] Where do links get extracted from -- the transcript itself, or provided separately?
- [ ] Does the house ad content change per episode, or is it the same across a season?
- [ ] What's the role of `formatter.md` -- was it meant to define transcript formatting rules?
- [ ] Should chapter JSON files be saved alongside the audio in the transcription directory?

### Proposed Sequence (Draft)

```
1. TRANSCRIBE  -- Run Whisper on all audio segments
2. STITCH      -- Combine interview parts into single transcript
3. ANALYZE     -- Read through transcript, identify topics/chapters
4. CHAPTERS    -- Generate chapter markers per Apple guidelines
5. EXTRACT     -- Pull links, names, references from transcript
6. FORMAT      -- Clean up transcript for publishing
7. PACKAGE     -- Assemble show description with chapters + links + boilerplate
8. PUBLISH     -- Post transcript to Google Drive, chapters to wherever they go
```

Steps 2-4 could potentially happen in a single pass. Steps 5-7 could be templated.

---

## S01E01 Episode Details

- **Show:** Wonder Cabinet
- **Season:** 1, Episode: 1
- **Guest:** Sophie Strand (poet, writer, author of *The Body is a Doorway*)
- **Hosts:** Anne Strainchamps, Steve Paulson
- **Runtime:** ~39 minutes
- **Key topics:** Ancestral embodiment, material reincarnation, monarch butterflies, Aramaic roots of sin, Bronze Age collapse & cultural dissociation, mushroom spores creating weather, butterfly consciousness/memory, Ehlers-Danlos syndrome, hermit crab shell exchange as metaphor, communal storytelling, time loops (Rip Van Winkle country), fantasy as medicine, science as wonder, original Wonder Cabinets (16th-18th century)
- **Key references:**
  - *The Body is a Doorway* -- Sophie Strand (memoir)
  - *Make Me Good Soil* -- Sophie Strand (Substack)
  - *The Flowering Wand* -- Sophie Strand (myths)
  - *The Madonna Secret* -- Sophie Strand (historical fiction)
  - *The Chalice and the Blade* -- Rianne Eisler
  - Haudenosaunee seven generations principle
  - Carlo Rovelli (teased for next episode on physics)
  - wondercabinetproductions.com
