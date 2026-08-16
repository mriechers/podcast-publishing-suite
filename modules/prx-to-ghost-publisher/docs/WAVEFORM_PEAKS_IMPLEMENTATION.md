# Waveform Peaks Pre-Generation Implementation

## Overview

This document describes the implementation of pre-generated waveform peaks for Wavesurfer.js audio players in the prx-to-ghost importer and Wonder Cabinet Ghost theme.

## Problem Statement

### CORS Issues with PRX/Podtrac URLs

PRX audio files use Podtrac redirect URLs for analytics tracking:
```
https://dts.podtrac.com/redirect.mp3/dovetail.prxu.org/[episode-path]/[file].mp3
```

When Wavesurfer.js tries to generate waveforms on-the-fly, it needs to:
1. Fetch the audio file
2. Decode it with Web Audio API
3. Analyze the waveform data

This process fails due to CORS restrictions on the Podtrac redirect URLs, preventing waveform visualization while still allowing audio playback through HTML5 `<audio>` elements.

## Solution: Pre-Generated Peaks

### Architecture

Instead of generating waveforms in the browser, we:

1. **During Import**: Generate peaks JSON files using BBC audiowaveform CLI
2. **Store Peaks**: Save JSON files in Ghost theme assets directory
3. **Reference Peaks**: Include peaks URL in post HTML data attributes
4. **Load Peaks**: Wavesurfer loads pre-computed peaks instead of analyzing audio

This approach:
- ✅ Solves CORS issues (peaks fetched from same origin)
- ✅ Preserves Podtrac analytics (audio still played from PRX URL)
- ✅ Faster waveform rendering (no client-side audio decoding)
- ✅ Graceful degradation (player works without peaks, just no waveform)

## Implementation Components

### 1. Waveform Peaks Generation Module

**File**: `/src/waveform_peaks.py`

Core functions:
- `check_audiowaveform_installed()` - Verify CLI tool availability
- `download_audio_file()` - Download audio to temporary location
- `generate_peaks_json()` - Run audiowaveform CLI to create peaks JSON
- `generate_peaks_for_episode()` - Complete workflow for episode
- `get_peaks_url()` - Build Ghost URL for peaks file

### 2. Content Builder Integration

**File**: `/src/content_builder.py`

Updates:
- `build_audio_player_card()` - Accepts optional `peaks_url` parameter
- `build_luminous_post_html()` - Passes peaks URL to player card
- `build_luminous_ghost_post()` - Accepts peaks URL and passes through

HTML output includes new data attribute:
```html
<div class="wc-audio-player"
     data-audio-url="[PRX URL]"
     data-peaks-url="[Peaks JSON URL]"
     ...>
</div>
```

### 3. Main Sync Integration

**File**: `/src/main.py`

New CLI arguments:
```bash
python -m src.main sync \
  --feed-type luminous \
  --generate-peaks \
  --peaks-dir /path/to/theme/assets/peaks
```

Workflow additions:
1. Check if audiowaveform is installed
2. For each episode, generate peaks JSON file
3. Build peaks URL for Ghost asset
4. Pass peaks URL to post builder
5. Gracefully handle failures (continue without peaks)

### 4. Ghost Theme Player

**File**: `/assets/js/waveform-player.js`

JavaScript initialization:
```javascript
// Detect peaks URL from data attribute
const peaksUrl = container.dataset.peaksUrl;

if (peaksUrl) {
  // Load peaks JSON
  fetch(peaksUrl)
    .then(response => response.json())
    .then(peaksData => {
      // Initialize Wavesurfer with peaks
      const ws = WaveSurfer.create({
        peaks: [peaksData.data],
        duration: peaksData.length / peaksData.sample_rate,
        url: audioUrl, // PRX URL for playback only
        // ... other config
      });
    });
}
```

**File**: `/assets/css/waveform-player.css`

Styles for:
- Player container with Wonder Cabinet branding
- Play/pause controls
- Time display
- Waveform container
- Loading and error states
- Responsive design

## Installation & Setup

### Prerequisites

1. **Install audiowaveform CLI** (macOS):
   ```bash
   brew install audiowaveform
   ```

   Other platforms: See [audiowaveform documentation](https://github.com/bbc/audiowaveform)

2. **Create peaks directory** in Ghost theme:
   ```bash
   mkdir -p /path/to/ghost/content/themes/WC-Episode/assets/peaks
   ```

3. **Add CSS/JS to theme** (if not already included):
   - Copy `waveform-player.css` to theme assets
   - Copy `waveform-player.js` to theme assets
   - Include Wavesurfer.js CDN or bundle
   - Reference in theme templates

### Theme Template Integration

Add to `default.hbs` or relevant layout template:

```handlebars
{{!-- In <head> --}}
<link rel="stylesheet" href="{{asset "css/waveform-player.css"}}">

{{!-- Before </body> --}}
<script src="https://unpkg.com/wavesurfer.js@7"></script>
<script src="{{asset "js/waveform-player.js"}}"></script>
```

## Usage

### Basic Import with Peaks

```bash
python -m src.main sync \
  --feed-type luminous \
  --generate-peaks \
  --peaks-dir /Users/you/ghost/content/themes/WC-Episode/assets/peaks
```

### Import Single Episode with Peaks

```bash
python -m src.main sync \
  --feed-type luminous \
  --guid "prx_3329_abc123..." \
  --generate-peaks \
  --peaks-dir /path/to/theme/assets/peaks
```

### Dry Run (Test Peaks Generation)

```bash
python -m src.main sync \
  --feed-type luminous \
  --limit 1 \
  --dry-run \
  --generate-peaks \
  --peaks-dir ./test-peaks
```

## Peaks File Format

Audiowaveform generates JSON in this format:

```json
{
  "version": 2,
  "channels": 1,
  "sample_rate": 48000,
  "samples_per_pixel": 2400,
  "bits": 8,
  "length": 1234,
  "data": [-45, 67, -23, 89, ...]
}
```

Wavesurfer.js consumes the `data` array directly as pre-computed waveform peaks.

### File Size Considerations

- **Typical size**: 10-50 KB per episode
- **Depends on**: Audio duration and `pixels_per_second` setting
- **Storage impact**: Minimal compared to audio files (which aren't stored)

Example: 60-minute episode at 20 pixels/second ≈ 30 KB peaks file

## Configuration Options

### Waveform Resolution

Adjust `pixels_per_second` parameter in `main.py`:

```python
peaks_path = generate_peaks_for_episode(
    audio_url=episode.enclosure_url,
    episode_slug=slug,
    output_dir=peaks_dir,
    pixels_per_second=20,  # Higher = more detail, larger file
)
```

Recommended values:
- `20` - Good balance (default)
- `10` - Lower detail, smaller files
- `40` - High detail, larger files

### Peaks Directory Location

The peaks directory should be:
- Inside Ghost theme assets (accessible via URL)
- Git-ignored if theme is version controlled
- Writable by the import script

Example paths:
```
/content/themes/WC-Episode/assets/peaks/
/content/themes/WC-Episode/assets/waveforms/
```

### Ghost URL Configuration

Set in `.env`:
```bash
GHOST_URL=https://wondercabinetproductions.com
```

Used to build peaks URLs:
```
https://wondercabinetproductions.com/assets/peaks/episode-slug.json
```

## Error Handling

### Graceful Degradation

The implementation includes multiple fallback layers:

1. **Peaks Generation Fails**: Episode imports without peaks URL
2. **Peaks Load Fails**: Player falls back to direct audio loading
3. **Audiowaveform Missing**: Import continues, peaks generation skipped
4. **Audio Download Fails**: Episode skipped, import continues

### Logging

All peaks-related operations log clearly:

```
INFO: Generating waveform peaks for: episode-slug
INFO: Downloaded 25,467,392 bytes to /tmp/waveform_abc123/episode.mp3
INFO: Generated peaks JSON: 28,934 bytes
INFO: Peaks URL: https://site.com/assets/peaks/episode-slug.json
```

Warnings for failures:
```
WARNING: Failed to generate peaks: audiowaveform not installed
WARNING: Failed to load peaks, falling back to direct audio
```

## Testing

### Test Peaks Generation

1. **Verify audiowaveform**:
   ```bash
   which audiowaveform
   audiowaveform --version
   ```

2. **Test on single episode**:
   ```bash
   python -m src.main sync \
     --feed-type luminous \
     --limit 1 \
     --generate-peaks \
     --peaks-dir ./test-peaks \
     --dry-run
   ```

3. **Check output**:
   ```bash
   ls -lh ./test-peaks/
   cat ./test-peaks/[episode-slug].json | jq '.version, .length'
   ```

### Test Theme Integration

1. **Publish test post** with peaks
2. **Open browser console** on post page
3. **Look for logs**:
   ```
   Found 1 audio players to initialize
   Loading pre-generated peaks: [URL]
   Waveform player initialized with pre-generated peaks
   ```

4. **Verify waveform** displays and audio plays

## Maintenance

### Regenerating Peaks

If you need to regenerate peaks (e.g., changed resolution):

```bash
# Clear existing peaks
rm /path/to/theme/assets/peaks/*.json

# Re-import with peaks
python -m src.main sync \
  --feed-type luminous \
  --generate-peaks \
  --peaks-dir /path/to/theme/assets/peaks
```

The importer checks for existing peaks files and can skip already-processed episodes.

### Cleaning Up Old Peaks

Peaks files for deleted episodes can be removed manually:

```bash
# List peaks files
ls /path/to/theme/assets/peaks/

# Remove specific episode
rm /path/to/theme/assets/peaks/old-episode-slug.json
```

## Performance Considerations

### Import Speed

- Peaks generation adds ~10-30 seconds per episode
- Majority of time is audio download (depends on file size)
- Audiowaveform processing is fast (<5 seconds)

For large imports:
- Run overnight or during low-traffic periods
- Consider `--limit` flag for batching
- Network speed is the main bottleneck

### Browser Performance

- Peaks loading is nearly instant (small JSON files)
- No audio decoding in browser (much faster than on-the-fly)
- Waveform renders immediately when peaks available

## Troubleshooting

### Audiowaveform Not Found

**Error**: `audiowaveform not installed`

**Solution**:
```bash
brew install audiowaveform  # macOS
# or build from source on Linux
```

### Peaks Load 404

**Error**: `Failed to load peaks: 404`

**Causes**:
- Peaks directory not in theme assets
- Peaks file not generated
- Incorrect Ghost URL in config

**Solution**:
- Verify peaks file exists
- Check Ghost URL matches actual site URL
- Ensure theme asset routing is correct

### CORS Error on Peaks

**Error**: `CORS policy: No 'Access-Control-Allow-Origin'`

**Cause**: Peaks URL is external to Ghost site

**Solution**: Peaks must be served from same origin as Ghost site (in theme assets)

### Waveform Not Displaying

**Debugging steps**:
1. Open browser console
2. Check for JavaScript errors
3. Verify Wavesurfer.js loaded
4. Check peaks URL in data attribute
5. Test peaks URL manually in browser

## Future Enhancements

Potential improvements:

1. **Caching**: Skip regeneration if peaks file already exists
2. **Parallel Processing**: Generate peaks for multiple episodes concurrently
3. **Cloud Storage**: Upload peaks to CDN for better distribution
4. **Batch Command**: Dedicated CLI command for batch peaks generation
5. **Admin UI**: Ghost admin panel integration for regenerating peaks

## References

- [BBC Audiowaveform](https://github.com/bbc/audiowaveform)
- [Wavesurfer.js Documentation](https://wavesurfer-js.org/)
- [PRX Dovetail Documentation](https://dovetail.prx.org/)
- [Ghost Theme Assets](https://ghost.org/docs/themes/assets/)

## Support

For issues or questions:
- Check logs for error messages
- Verify all prerequisites installed
- Test with a single episode first
- Review Ghost theme console for JavaScript errors
