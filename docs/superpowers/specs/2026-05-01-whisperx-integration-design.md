# WhisperX Integration Design

**Date:** 2026-05-01
**Status:** Draft
**Scope:** Replace standard Whisper with WhisperX as the default transcription engine, adding speaker diarization to the podcast pipeline.

## Problem

The current transcription pipeline uses OpenAI Whisper (turbo model) via `~/Developer/the-lodge/scripts/whisper-transcribe.sh`. This has two problems:

1. **No speaker diarization.** The formatter agent guesses who's speaking based on conversational cues. This is approximate and error-prone, especially during rapid host exchanges.
2. **Cross-repo dependency.** The pipeline depends on a script in `the-lodge`, a separate repo. On a portable SSD, this path is fragile.

## Solution

Upgrade `whisper-transcribe.sh` to support WhisperX (with pyannote diarization) as the default engine, with standard Whisper as a fallback. Place a copy in both `podcast-publishing-suite/scripts/` and `the-lodge/scripts/`, eliminating the cross-repo dependency.

## Comparison (from E12 Henderson test run)

| Dimension | Whisper turbo | WhisperX large-v3 |
|---|---|---|
| Speaker diarization | None | 3 speakers correctly separated |
| "Anne Strainchamps" | "Strangeamps" (wrong) | "Strainchamps" (correct) |
| "sangha" | "sango" (wrong) | "sangha" (correct) |
| "war footing" | "wall footing" (wrong) | "war footing" (correct) |
| Processing time | ~8 min | ~15 min |
| Word count | 8,581 | 8,560 |

WhisperX uses the large-v3 model via faster-whisper (CTranslate2) and adds pyannote 3.1 for diarization. Better proper noun accuracy, comparable word count, 2x processing time.

## Script Design: `whisper-transcribe.sh`

### Location

Two independent copies:
- `podcast-publishing-suite/scripts/whisper-transcribe.sh` — used by wc-transcribe pipeline
- `the-lodge/scripts/whisper-transcribe.sh` — standalone use

### New flags

| Flag | Default | Description |
|---|---|---|
| `--engine whisperx\|whisper` | `whisperx` | Transcription engine |
| `--diarize` | on (when engine=whisperx) | Enable speaker diarization |
| `--no-diarize` | — | Disable diarization (faster) |
| `--min-speakers N` | 2 | Diarization hint: minimum speakers |
| `--max-speakers N` | 4 | Diarization hint: maximum speakers |
| `--model MODEL` | `large-v3` (whisperx) / `turbo` (whisper) | Override model |

### Preserved flags

`--check`, `--install`, `--force`, `--prompt`, `--help` — all carry over from the current script with updated behavior for the WhisperX engine.

### Engine detection and fallback

On invocation:
1. If `--engine whisper` is specified, use standard Whisper (current behavior).
2. If `--engine whisperx` (or default), check that `whisperx` binary exists.
3. If whisperx is not installed, warn and fall back to standard Whisper with a message: "WhisperX not found, falling back to Whisper turbo (no diarization)."

### HF token

When diarization is enabled, the script reads `~/.cache/huggingface/token`. If the token is missing, it warns and falls back to `--no-diarize` mode (WhisperX transcription without pyannote).

### Per-file processing

Files are processed individually, not batched to WhisperX CLI. This prevents a crash on one file from losing output on already-completed files. The batch directory logic in the shell script iterates files and calls whisperx once per file.

### Diarization model

Uses `pyannote/speaker-diarization-3.1` explicitly via `--diarize_model`. This is the model the user has accepted terms for on Hugging Face.

### Output format

**Important difference from standard Whisper:** WhisperX writes output files flat into the `--output_dir` (e.g., `Henderson_mix_01.srt` alongside `Henderson_mix_01.json`), whereas standard Whisper creates a subdirectory per input file. The upgraded script normalizes this: after WhisperX completes each file, the script moves outputs into a per-file subdirectory to match the existing convention. This keeps the downstream move-to-whisper/ step and combine_srts.py working unchanged.

The only content difference is that WhisperX SRT/TXT lines include `[SPEAKER_XX]:` prefixes when diarization is enabled.

### Install flow

`--install` updated to offer installation of both engines:
- `pipx install whisperx --python python3.11` (WhisperX + pyannote)
- `pipx install openai-whisper` (standard Whisper, fallback)

The `--check` flag reports status of both engines plus HF token presence.

## Pipeline Changes

### wc-transcribe skill (`.claude/commands/wc-transcribe.md`)

**Phase 2** command changes from:
```bash
~/Developer/the-lodge/scripts/whisper-transcribe.sh "$CANONICAL_DIR/audio/"
```
to:
```bash
./scripts/whisper-transcribe.sh --max-speakers 3 "$CANONICAL_DIR/audio/"
```

The move-output-dirs step remains the same (whisperx creates subdirs alongside MP3s, we move them to `whisper/`).

### combine_srts.py

Update to preserve `[SPEAKER_XX]:` prefixes when combining SRT entries. Currently strips everything except timecodes and text. The combined SRT should retain speaker labels so the formatter can use them.

When combining, speaker labels are passed through as-is. The labels are per-file (SPEAKER_00 in Part 1 is not the same as SPEAKER_00 in Part 2), but the formatter handles cross-part mapping.

### Formatter agent (`transcript-formatter.md`)

Add a new section to the agent instructions:

> **Speaker diarization labels:** If the SRT input contains `[SPEAKER_XX]:` prefixes, use these as the primary signal for speaker attribution. Map the anonymous speaker IDs to real names using episode context:
> - Identify which `SPEAKER_XX` corresponds to each known speaker based on self-identification ("I'm Anne Strainchamps"), conversational role (who asks questions vs. gives long answers), and segment count (the guest typically has the most segments).
> - Speaker IDs may differ between parts (Part 1's SPEAKER_00 may not be Part 2's SPEAKER_00). Map independently per part.
> - When diarization labels conflict with conversational cues, prefer the diarization label — it's based on voice, not content.
> - If diarization labels are absent (legacy Whisper output), fall back to conversational-cue-based attribution as before.

### Chapters agent

No changes. Chapters reads the combined SRT for timecodes and content flow. Speaker labels are irrelevant to chapter boundary detection.

### QC pass

The existing anti-hallucination checks are unchanged. Add one new check:
- **Diarization consistency** — verify that each speaker ID maps to exactly one real name, and that the mapping is consistent within each part. Flag any segment where the formatter assigned a different real name to the same SPEAKER_XX ID.

### Episode validator (`validate_episode.py`)

No changes needed. It checks for file presence, not content format.

## What's NOT changing

- Episode folder structure (`shows/<show>/episodes/<slug>/`)
- Manifest schema
- Output file names (`captions.srt`, `transcript.txt`, `formatted_transcript.md`, `chapters.md`)
- Google Drive upload flow
- Slack notifications
- Glossary correction system (still needed for names both engines get wrong: Vershire, Riechers, etc.)

## Dependencies

| Dependency | Purpose | Installation |
|---|---|---|
| whisperx 3.8+ | Transcription + alignment | `pipx install whisperx --python python3.11` |
| pyannote.audio | Speaker diarization | Bundled with whisperx |
| Hugging Face token | Access gated pyannote models | `~/.cache/huggingface/token` |
| Python 3.11 | Required by whisperx (3.14 not supported) | `brew install python@3.11` |
| openai-whisper | Fallback engine | `pipx install openai-whisper` (existing) |
| ffmpeg | Audio extraction | `brew install ffmpeg` (existing) |

## Future enhancements (not in scope)

- **Cross-part speaker alignment** — use voice embeddings to map speaker IDs consistently across parts. Deferred: formatter handles this adequately now.
- **Voice profile bank** — pre-computed embeddings for recurring hosts (Anne, Steve) to enable automatic speaker-to-name mapping without conversational cues.
- **Concatenated-audio processing** — combine all MP3s into one file before WhisperX to avoid per-file speaker ID resets. Trade-off: loses part-boundary awareness.
