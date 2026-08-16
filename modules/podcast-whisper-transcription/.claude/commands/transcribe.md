Transcribe audio or video files using OpenAI Whisper (turbo model).

**Path to transcribe:** $ARGUMENTS

## Instructions

1. If no path was provided in $ARGUMENTS, ask the user for the path to the audio/video file or directory.

2. **First-time setup**: If Whisper isn't installed, run the compatibility check:
   ```bash
   ./whisper-transcribe.sh --check
   ```

   If the system is compatible and the user wants to proceed:
   ```bash
   ./whisper-transcribe.sh --install
   ```

3. Validate the path exists:
   ```bash
   ls -la "$PATH" 2>/dev/null || echo "Path not found"
   ```

4. Run the transcription script:
   ```bash
   ./whisper-transcribe.sh "$PATH"
   ```

5. The script handles both single files and directories:
   - **Single file**: Creates a folder with all output formats
   - **Directory**: Finds all media files, processes sequentially with `[1/N]` progress

6. After completion, summarize what was created.

## Features

- **System compatibility check**: Verifies Apple Silicon, RAM, and dependencies
- **Guided installation**: Helps install Whisper via pipx on compatible machines
- **All output formats**: Creates txt, vtt, srt, tsv, and json in a folder
- **Progress display**: Shows Whisper's real-time progress bar
- **Skip existing**: Won't re-transcribe files that already have outputs
- **Batch summary**: Shows processed/skipped/failed counts

## System Requirements

- **Recommended**: Apple Silicon Mac (M1/M2/M3/M4) with 16GB+ RAM
- **Minimum**: 8GB RAM for turbo model
- **Dependencies**: pipx, ffmpeg (for video files)

## Notes

- Uses the **turbo** model (best speed/accuracy for Apple Silicon)
- Output saved in a folder next to source file(s) with all formats
- First run downloads the model (~1.5GB), subsequent runs are fast
- Supports: mp3, wav, m4a, flac, ogg, opus, wma, aac, mp4, mkv, webm, avi, mov, m4v

## Examples

```bash
# Check system compatibility
/transcribe --check

# Install Whisper (guided)
/transcribe --install

# Single file
/transcribe ~/Downloads/interview.mp3

# Entire directory
/transcribe ~/Videos/interviews/
```
