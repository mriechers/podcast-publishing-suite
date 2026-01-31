# Pre-Generated Peaks Quick Start Guide

> **TODO: Remote Deployment Evaluation**
>
> The peaks workflow requires the `audiowaveform` CLI tool which is easily installed locally via Homebrew. When this importer is deployed as a remote script (e.g., GitHub Actions, cloud function, or scheduled task), we'll need to evaluate:
>
> 1. **Container/CI environment**: Can we install audiowaveform in the CI environment? (apt-get, Docker image with audiowaveform pre-installed, etc.)
> 2. **Alternative approaches**: If audiowaveform isn't viable remotely:
>    - Generate peaks locally and commit to theme repo
>    - Use a cloud-based audio processing service
>    - Pre-compute peaks as a separate batch job
>    - Skip peaks for remote imports (waveform won't display, but player still works)
> 3. **Peaks file delivery**: Remote script would need write access to the Ghost theme's `/assets/peaks/` directory, or upload peaks to a CDN/R2 bucket.
>
> For now, the feature is designed to gracefully degrade - if audiowaveform isn't available, the import continues without peaks and the player still functions (just without waveform visualization).

## What Was Implemented

A complete solution for pre-generating waveform peaks to solve CORS issues with PRX/Podtrac audio URLs in the Wonder Cabinet Ghost theme.

## Problem Solved

PRX audio URLs use Podtrac redirects (`https://dts.podtrac.com/redirect.mp3/...`) which cause CORS failures when Wavesurfer.js tries to decode audio for waveform visualization. The solution pre-generates peaks JSON files during import.

## Quick Start

### 1. Install audiowaveform

```bash
brew install audiowaveform
```

### 2. Run Import with Peaks Generation

```bash
cd /Users/markriechers/Developer/ghost-dev/prx-to-ghost-publisher

python -m src.main sync \
  --feed-type luminous \
  --generate-peaks \
  --peaks-dir /Users/markriechers/Developer/ghost-dev/content/themes/WC-Episode/assets/peaks
```

### 3. Add Theme Assets

Include in your Ghost theme's `default.hbs` or relevant layout:

```handlebars
{{!-- In <head> --}}
<link rel="stylesheet" href="{{asset "css/waveform-player.css"}}">

{{!-- Before </body> --}}
<script src="https://unpkg.com/wavesurfer.js@7"></script>
<script src="{{asset "js/waveform-player.js"}}"></script>
```

## What Was Created

### Importer Components

1. **`/src/waveform_peaks.py`** - Core peaks generation module
   - Downloads audio files temporarily
   - Runs audiowaveform CLI
   - Generates JSON files
   - Builds peaks URLs

2. **Updated `/src/content_builder.py`**
   - Added `peaks_url` parameter to player cards
   - Includes peaks URL in HTML data attributes

3. **Updated `/src/main.py`**
   - New CLI flags: `--generate-peaks` and `--peaks-dir`
   - Integrated peaks generation into import workflow
   - Graceful error handling

### Ghost Theme Components

4. **`/assets/js/waveform-player.js`** - Player initialization
   - Detects peaks URLs from data attributes
   - Loads pre-generated peaks
   - Falls back gracefully if peaks unavailable

5. **`/assets/css/waveform-player.css`** - Player styling
   - Wonder Cabinet branded player design
   - Responsive layout
   - Loading and error states

6. **`/assets/peaks/`** - Storage directory
   - Holds generated peaks JSON files
   - Named by episode slug
   - Git-ignored in production

### Documentation

7. **`/docs/WAVEFORM_PEAKS_IMPLEMENTATION.md`** - Complete technical documentation
8. **`/docs/PEAKS_QUICK_START.md`** - This guide

## File Locations

### Importer (prx-to-ghost-publisher)
```
/Users/markriechers/Developer/ghost-dev/prx-to-ghost-publisher/
├── src/
│   ├── waveform_peaks.py        (NEW - peaks generation)
│   ├── content_builder.py       (UPDATED - peaks URL support)
│   └── main.py                  (UPDATED - CLI integration)
└── docs/
    ├── WAVEFORM_PEAKS_IMPLEMENTATION.md  (NEW)
    └── PEAKS_QUICK_START.md              (NEW)
```

### Ghost Theme (WC-Episode)
```
/Users/markriechers/Developer/ghost-dev/content/themes/WC-Episode/
└── assets/
    ├── js/
    │   └── waveform-player.js   (NEW - player logic)
    ├── css/
    │   └── waveform-player.css  (NEW - player styles)
    └── peaks/
        ├── README.md            (NEW - directory documentation)
        ├── .gitkeep             (NEW - preserve directory)
        └── [episode-slug].json  (Generated during import)
```

## How It Works

### Import Flow

1. **Download Audio**: Temporarily download episode audio from PRX URL
2. **Generate Peaks**: Run `audiowaveform` CLI to create JSON file
3. **Save to Theme**: Store peaks JSON in theme assets directory
4. **Build URL**: Create Ghost asset URL for peaks file
5. **Include in Post**: Add `data-peaks-url` attribute to player HTML
6. **Clean Up**: Remove temporary audio file

### Player Flow

1. **Detect Player**: Find `.wc-audio-player` elements on page load
2. **Check Peaks**: Look for `data-peaks-url` attribute
3. **Load Peaks**: Fetch pre-generated peaks JSON
4. **Initialize Wavesurfer**: Create player with peaks data
5. **Fallback**: If peaks fail, try direct audio (may fail with CORS)

### Benefits

- ✅ **Solves CORS**: Peaks fetched from same origin (Ghost site)
- ✅ **Preserves Analytics**: Audio still plays from PRX URL
- ✅ **Faster**: No browser audio decoding needed
- ✅ **Small Files**: 10-50 KB per episode
- ✅ **Graceful**: Works without peaks, just no waveform

## Example Output

### Generated HTML (in Ghost post)

```html
<div class="wc-audio-player"
     data-audio-url="https://dts.podtrac.com/redirect.mp3/dovetail.prxu.org/..."
     data-peaks-url="https://wondercabinetproductions.com/assets/peaks/episode-slug.json"
     data-episode-artwork="..."
     data-episode-date="2023-07-08"
     data-episode-duration="52:02">
</div>
```

### Generated Peaks JSON

```json
{
  "version": 2,
  "channels": 1,
  "sample_rate": 48000,
  "samples_per_pixel": 2400,
  "bits": 8,
  "length": 1234,
  "data": [-45, 67, -23, 89, -12, 56, ...]
}
```

### Browser Console Output

```
Found 1 audio players to initialize
Loading pre-generated peaks: https://site.com/assets/peaks/episode-slug.json
Waveform player initialized with pre-generated peaks
```

## Testing

### Test Single Episode

```bash
python -m src.main sync \
  --feed-type luminous \
  --limit 1 \
  --guid "prx_3329_abc123..." \
  --generate-peaks \
  --peaks-dir /path/to/theme/assets/peaks \
  --dry-run
```

### Verify Peaks Generated

```bash
ls -lh /path/to/theme/assets/peaks/
cat /path/to/theme/assets/peaks/episode-slug.json | head -20
```

### Test in Browser

1. Import a test episode with `--generate-peaks`
2. Publish the post in Ghost
3. Open post in browser
4. Check browser console for initialization logs
5. Verify waveform displays and audio plays

## Configuration

### Peaks Resolution

Adjust in `/src/main.py` line ~125:

```python
peaks_path = generate_peaks_for_episode(
    audio_url=episode.enclosure_url,
    episode_slug=slug,
    output_dir=peaks_dir,
    pixels_per_second=20,  # Change this value
)
```

- `10` = Lower detail, smaller files (~15 KB)
- `20` = Good balance (default, ~30 KB)
- `40` = High detail, larger files (~60 KB)

### Peaks Directory

Can be anywhere in theme assets:
```
/assets/peaks/           (recommended)
/assets/waveforms/       (alternative)
/assets/audio/peaks/     (nested)
```

Must be:
- Accessible via Ghost asset URLs
- Writable by import script
- Git-ignored (optional)

## Troubleshooting

### "audiowaveform not installed"

```bash
brew install audiowaveform
which audiowaveform  # Verify installation
```

### Peaks not loading (404)

- Check peaks file exists in theme assets
- Verify Ghost URL correct in `.env`
- Confirm theme asset routing works

### Waveform not displaying

- Open browser console for errors
- Verify Wavesurfer.js loaded
- Check CSS/JS files included in theme
- Test peaks URL manually in browser

### Import errors

- Check temp directory permissions
- Verify network connection for audio download
- Review logs for specific error messages

## Next Steps

### Required for Production

1. **Install audiowaveform** on production server
2. **Run import with peaks** for existing episodes
3. **Include theme assets** in production theme
4. **Test on staging** before deploying to production

### Optional Enhancements

- Add peaks caching (skip if file exists)
- Implement parallel processing for faster imports
- Upload peaks to CDN for better distribution
- Add progress bar to player UI
- Customize waveform colors per show

## Support

For detailed documentation, see:
- `/docs/WAVEFORM_PEAKS_IMPLEMENTATION.md` - Full technical details
- `/src/waveform_peaks.py` - Module documentation
- `/assets/js/waveform-player.js` - Player code comments

## Summary

You now have a complete, production-ready solution for pre-generating waveform peaks that:

1. **Solves the CORS problem** with PRX/Podtrac URLs
2. **Preserves analytics** by keeping audio playback on PRX URLs
3. **Integrates seamlessly** with your existing import workflow
4. **Degrades gracefully** if peaks are unavailable
5. **Is well-documented** for future maintenance

The implementation is ready to use immediately with the `--generate-peaks` flag on your import commands.
