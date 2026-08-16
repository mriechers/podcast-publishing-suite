# Podcast Timestamps & Chapters Reference

Quick reference for adding timestamps/chapters to podcast episodes across platforms.

## Format: Episode Description Timestamps

The simplest, most universal method. Add to your episode description in your hosting provider:

```
00:00:00 Introduction
00:02:15 Topic One Title
00:08:30 Topic Two Title
00:15:00 Topic Three Title
00:22:45 Wrap-Up
```

Supported by: Apple Podcasts, Spotify, YouTube Music, most podcast apps.

## Format: RSS Feed (`<podcast:chapters>`)

For richer chapter support (artwork, URLs), use the Podcasting 2.0 `<podcast:chapters>` tag in your RSS feed. Your hosting provider must support this. The tag references a JSON chapters file:

```xml
<podcast:chapters url="https://example.com/episode1/chapters.json" type="application/json+chapters" />
```

The JSON file follows this structure:

```json
{
  "version": "1.2.0",
  "chapters": [
    {
      "startTime": 0,
      "title": "Introduction",
      "img": "https://example.com/chapter1.jpg",
      "url": "https://example.com/related-link"
    },
    {
      "startTime": 135,
      "title": "Topic One",
      "img": "https://example.com/chapter2.jpg"
    }
  ]
}
```

`startTime` is in seconds. `img` and `url` are optional.

## Format: MP3 ID3 Tags / MP4 Headers

Chapters can be embedded directly in the audio file metadata:
- **MP3**: ID3v2 CHAP and CTOC frames
- **MP4/M4A**: Chapter markers in the file header

Tools like Forecast (by Relay FM), Hindenburg, or ffmpeg can write these.

---

## Apple Podcasts

**Source:** [Chapters on Apple Podcasts](https://podcasters.apple.com/support/5482-using-chapters-on-apple-podcasts)

### How to Provide Chapters

1. **Episode Description** - Add timestamps and titles directly. Start at `00:00:00`. Minimum 3 chapters.
2. **RSS Feed** - Use `<podcast:chapters>` tag. Check [hosting provider support](https://podcasters.apple.com/partner-search).
3. **File Metadata** - ID3 tags (MP3/AAC) or MP4 headers.

### Best Practices

- Minimum 3 chapters per episode
- No more than 6 chapters per hour
- Only add chapters for episodes > 10 minutes
- Each chapter should be at least 2 minutes long
- Chapter titles: max 45 characters, fewer than 5 words
- Use title case
- Spell out numbers 1-9, use digits for 10+
- Avoid repeating words across chapter titles

### Auto-Generated Chapters

- Available starting iOS 26.2
- English only, full and bonus episodes
- Not generated for trailers or episodes < 10 minutes
- Can be downloaded as TXT from Apple Podcasts Connect and edited
- Can be disabled per-show or per-episode in Apple Podcasts Connect

### Chapter Art

- Optional artwork for each chapter (via RSS only)
- Displays in player and on Lock Screen
- Use Apple's [Chapter Art template](https://podcasters.apple.com/support/5528-chapter-art-template)
- Must be high-resolution, fill entire template

## Spotify

Spotify supports chapters via the Podcasting 2.0 `<podcast:chapters>` RSS tag or episode description timestamps. Their native creation tools have been deprecated — use your hosting provider's chapter tools instead.

Spotify does not have separate chapter documentation; support comes through standard RSS chapter support.

## YouTube Music

YouTube Music ingests podcasts via RSS and supports chapters through episode description timestamps in `HH:MM:SS Title` format. The same description timestamps you add for Apple Podcasts work here.

For YouTube video podcasts, timestamps in the video description create chapters in the YouTube player. Format: `0:00 Title` (first timestamp must be `0:00`).

---

## Practical Workflow

For maximum compatibility across platforms:

1. **Add timestamps to your episode description** - This is the single action that works everywhere.
2. **Use `<podcast:chapters>` in RSS** if your host supports it - Adds chapter art and links for Apple Podcasts and apps that support Podcasting 2.0.
3. **Embed in file metadata** as a fallback for apps that read ID3/MP4 chapter markers.

### Timestamp Format

```
00:00:00 Chapter Title Here
```

- Use `HH:MM:SS` for episodes over 1 hour
- Use `MM:SS` for shorter episodes (some platforms require `HH:MM:SS`)
- Safest: always use `HH:MM:SS`

---

## Library References

For full platform documentation:

```
read_documentation("apple-podcasts", "chapters")
read_documentation("spotify")
read_documentation("youtube")
```
