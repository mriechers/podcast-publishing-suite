# podcast-whisper-transcription

A simple podcast transcription toolkit built on OpenAI Whisper. Two tools, one goal: turn audio into text.

- **`whisper-transcribe.sh`** -- Batch-transcribe local audio/video files. Drop it on a folder of episode recordings and walk away.
- **`video_processor.py`** -- Pull transcripts from YouTube, TikTok, or Instagram URLs. Uses the YouTube transcript API when available (fast, no download), falls back to Whisper for platforms that don't expose one.

Both are optimized for Apple Silicon Macs with automatic mlx-whisper backend detection, and fall back gracefully to faster-whisper on any platform.

## Prerequisites

| Dependency | Required by | Install |
|---|---|---|
| **ffmpeg** | Both tools | `brew install ffmpeg` |
| **pipx** | `whisper-transcribe.sh` | `brew install pipx` |
| **OpenAI Whisper** | `whisper-transcribe.sh` | `pipx install openai-whisper` (script will offer to install) |
| **Python 3.10+** | `video_processor.py` | `brew install python` |

## Quick start

### Local file transcription

```bash
# Single file
./whisper-transcribe.sh episode-01.mp3

# Entire directory (skips already-transcribed files)
./whisper-transcribe.sh ./recordings/
```

Output lands in a folder next to each source file with all formats: `.txt`, `.srt`, `.vtt`, `.tsv`, `.json`.

### URL-based transcription

```bash
pip install -r requirements.txt
```

```python
from video_processor import extract_transcript

result = extract_transcript("https://youtube.com/watch?v=...")
print(result["transcript"])
```

Supports YouTube (API-first, no download), TikTok, and Instagram (download + Whisper).

## Configuration

All configuration is through environment variables:

| Variable | Default | Used by | Description |
|---|---|---|---|
| `WHISPER_MODEL` | `base` | `video_processor.py` | Model size: `tiny`, `base`, `small`, `medium`, `large` |
| `WHISPER_BACKEND` | `auto` | `video_processor.py` | Force a backend: `auto`, `mlx`, `faster-whisper` |
| `VIDEO_ARCHIVE_PATH` | `~/Media/archived-videos` | `video_processor.py` | Where to save downloaded videos when archiving |

The shell script defaults to the `turbo` model (best speed/accuracy on Apple Silicon). Edit the `MODEL` variable at the top of the script to change it.

### Model sizes

| Model | RAM | Notes |
|---|---|---|
| `tiny` | ~1 GB | Fast, lower accuracy |
| `base` | ~1 GB | Good for clear audio |
| `small` | ~2 GB | Balanced |
| `medium` | ~5 GB | High accuracy |
| `turbo` | ~6 GB | Best speed/accuracy on Apple Silicon (shell script default) |
| `large` | ~10 GB | Highest accuracy, slow |

## Output formats

Each transcription produces five formats:

| Format | Use case |
|---|---|
| `.txt` | Plain text -- the transcript itself |
| `.srt` | SubRip subtitles -- standard for video players |
| `.vtt` | WebVTT -- web-native subtitle format |
| `.tsv` | Tab-separated -- for spreadsheet analysis |
| `.json` | Raw Whisper output -- segment-level timing, confidence, tokens |

See `examples/WC_S01_trailer/` for a complete set of outputs from a real episode.

## Docs

- **`docs/transcripts.md`** -- Formatting guide for cleaning up raw transcripts into publishable markdown.
- **`docs/timestamps.md`** -- Reference for podcast chapter formats across platforms (Apple Podcasts, Spotify, YouTube).

## Supported input formats

**Audio:** mp3, wav, m4a, flac, ogg, opus, wma, aac
**Video:** mp4, mkv, webm, avi, mov, m4v
**URLs:** YouTube, TikTok, Instagram
