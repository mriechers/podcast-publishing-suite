---
status: DRAFT — IN PROGRESS
created: 2026-04-03
last_updated: 2026-04-03
destination: Google Drive > Wonder Cabinet > TECH BIBLE (when stable)
---

# Podcast Publishing Suite Guide

A guide for Wonder Cabinet Productions staff on the tools that power our podcast publishing pipeline.

> **Note:** This document is a work in progress. The publishing suite is still under active development. Sections marked with **[COMING SOON]** describe planned functionality that isn't available yet. This guide will be moved to the shared TECH BIBLE folder on Google Drive once the workflow is finalized.

---

## What Is the Publishing Suite?

The publishing suite is a collection of tools that automate the repetitive parts of getting a podcast episode from a finished audio file to everywhere it needs to be — the website, podcast platforms, YouTube, and social media.

Instead of manually copying metadata, generating transcripts, creating video versions, and posting to each platform one at a time, the suite handles these steps through a connected pipeline.

### What It Does

| Step | What Happens | Status |
|------|-------------|--------|
| **Transcription** | Automatically transcribes episodes with speaker names identified | Working |
| **Website Publishing** | Creates episode pages on the Wonder Cabinet website from podcast feed data | Working |
| **Video Audiograms** | Generates animated video versions of episodes and clips for YouTube and social | Working |
| **Social Distribution** | Posts to social media platforms with appropriate formatting | Planned |
| **Dashboard** | A single interface to monitor and manage all of the above | In Development |

### Shows Supported

The suite currently supports two shows:

- **Wonder Cabinet** — fully configured
- **Luminous** — configured for website publishing; other tools being adapted

---

## The Pipeline: How an Episode Flows Through the System

Here's what happens after a finished audio file is ready:

```
Finished Audio
     |
     v
1. TRANSCRIPTION
   Audio is transcribed using AI (OpenAI Whisper).
   Speaker names are identified and labeled.
   Output: transcript, captions file, chapter markers.
     |
     v
2. WEBSITE PUBLISHING
   Episode metadata is pulled from the PRX podcast feed.
   A page is created on the Wonder Cabinet website (Ghost CMS)
   with the episode description, audio player, and transcript.
     |
     v
3. VIDEO CREATION
   Animated video versions are generated automatically:
   - Full episode video (16:9, for YouTube)
   - Social clips (9:16, for Reels/Shorts/TikTok)
   Each includes the Wonder Cabinet animated background,
   waveform visualization, and episode metadata.
     |
     v
4. SOCIAL DISTRIBUTION [COMING SOON]
   Posts are drafted and scheduled to social platforms
   with platform-appropriate formatting.
     |
     v
5. DASHBOARD [IN DEVELOPMENT]
   A web interface to see the status of each step,
   review outputs, and manage the process without
   using the command line.
```

> **Important:** Right now, each step is triggered separately. The goal is for the dashboard to eventually orchestrate the full pipeline from a single interface.

---

## Transcription

**What it does:** Takes a podcast audio file and produces a written transcript with speakers identified (e.g., "Anne Strainchamps:" and "Guest Name:").

**What you get:**
- **Plain text transcript** — full text of the episode
- **Formatted transcript** — organized by speaker, with paragraphs
- **Captions file (.srt)** — timed subtitles for video
- **Chapter markers** — timestamps for major sections

**Known quirks:**
The AI transcription consistently misspells certain names. These are corrected automatically when possible, but always double-check:
- "Vershire" (Vermont) often appears as "Versher"
- "Anne Strainchamps" may appear as "Anne Strange-Hamps"
- "Steve Gotcher" may appear as "Gottscher"
- "Mark Riechers" may appear as "Rickers"

**Current process:** Transcription is currently run from the command line. **[COMING SOON]** The dashboard will allow you to upload audio and receive deliverables without command-line access.

---

## Website Publishing

**What it does:** Creates episode pages on [wondercabinetproductions.com](https://wondercabinetproductions.com) by reading episode data from the PRX podcast feed.

**What gets created:**
- An episode page with the show description, embedded audio player, and guest information
- Proper tagging so the episode appears in the correct show collection (Wonder Cabinet or Luminous)
- Transcript content attached to the episode page (when available)

**How shows are organized on the site:**
- Wonder Cabinet episodes live at `wondercabinetproductions.com/wonder-cabinet/`
- Luminous episodes live at `wondercabinetproductions.com/luminous/`

**Current process:** Publishing is triggered from the command line using the PRX feed as the data source. **[COMING SOON]** The dashboard will show publishing status and allow manual review before pages go live.

---

## Video Audiograms

**What it does:** Generates animated video versions of podcast audio — either full episodes or short clips — with the Wonder Cabinet visual branding.

**Video types:**

| Type | Dimensions | Use Case |
|------|-----------|----------|
| Full Episode | 1920x1080 (16:9) | YouTube |
| Social Clip | 1080x1920 (9:16) | Reels, Shorts, TikTok |

**What the videos look like:**
- Animated galaxy spiral background (Wonder Cabinet branding)
- Audio waveform visualization that responds to the audio
- Episode title, guest name, and show branding overlaid
- Multiple visual styles available (different waveform and color options)

**Render times:**
Generating video from audio takes time — roughly 1:1 (a 30-minute episode takes about 30 minutes to render, sometimes longer).

**Current process:** Videos are rendered from the command line using Remotion Studio, which also provides a visual preview. **[COMING SOON]** The dashboard will allow you to select episodes, choose a visual style, and queue renders.

---

## Social Distribution

**[COMING SOON]** — This module is planned but not yet built.

The goal is to automate the process of formatting and posting episode content to social media platforms, including:
- Drafting platform-appropriate posts
- Attaching audiogram clips
- Scheduling posts to queue

---

## The Dashboard

**[IN DEVELOPMENT]** — The web dashboard is being built to serve as the primary way staff interact with the publishing suite.

**Planned features:**
- See the status of each episode across the pipeline (transcribed? published? video rendered?)
- Upload audio and trigger processing steps
- Review and approve outputs before they go live
- Switch between shows (Wonder Cabinet, Luminous)
- Monitor the overall health of the system

The dashboard is intended to replace command-line workflows entirely for day-to-day production tasks.

---

## Show Identity and Branding

Each show has its own identity package that the tools read from, so branding is consistent everywhere:

**Wonder Cabinet:**
- Colors: Black, Green (#10A544), Cream
- Fonts: Jost (headlines), EB Garamond (body text)
- Animated galaxy background for video

**Luminous:**
- Colors: Purple (#8B5CF6) primary palette
- Branding assets are still being finalized

When the tools generate videos, create website pages, or format social posts, they pull from these identity packages automatically. Updating a show's branding in one place updates it everywhere.

---

## Glossary

| Term | What It Means |
|------|--------------|
| **PRX** | Public Radio Exchange — the platform that distributes our podcast to listening apps (Apple Podcasts, Spotify, etc.) |
| **Ghost** | The content management system (CMS) that powers the Wonder Cabinet website |
| **Audiogram** | A video version of audio content, with visual elements like waveforms and branding |
| **Whisper** | OpenAI's AI transcription tool that converts audio to text |
| **Diarization** | The process of identifying which speaker is talking at any given point in a recording |
| **SRT** | A subtitle/caption file format with timestamps |
| **Remotion** | The video generation framework used to create audiograms programmatically |
| **Pipeline** | The sequence of automated steps that process an episode from audio to published content |

---

## Questions or Issues

If something in the publishing pipeline isn't working as expected, or if you have questions about any of these tools, contact the production team.

---

*This document will be updated as the publishing suite develops. When the workflow is stable, it will be moved to the shared TECH BIBLE folder on Google Drive alongside the Wonder Cabinet Production Guide.*
