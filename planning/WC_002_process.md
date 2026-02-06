# WC_002 Rovelli -- Production Process

How episode WC_002 (Carlo Rovelli) was processed from raw audio to publication-ready deliverables.

## Source Material

Three MP3 files in `audio-to-transcribe/WC_002_Rovelli/`:

| File | Duration | Content |
|---|---|---|
| `Rovelli part 01.mp3` | ~16:50 | Intro, archival Rovelli clip (gravitational waves), new interview first half |
| `Rovelli mid-roll.mp3` | ~0:22 | Anne's promo (follow on Apple Podcasts) |
| `Rovelli part 02.mp3` | ~20:20 | Interview second half, outro, credits |

Combined episode duration: ~37:30

## Pipeline

### Step 1: Whisper Transcription

**Tool:** `whisper-transcribe.sh` (via `/transcribe` skill)
**Model:** turbo
**Command:** `~/Developer/the-lodge/scripts/whisper-transcribe.sh ./WC_002_Rovelli/`

The script batch-processed all three MP3 files sequentially. For each file, it created a subfolder containing all five output formats (txt, srt, vtt, tsv, json).

**Output structure:**
```
WC_002_Rovelli/
  Rovelli part 01/
    Rovelli part 01.{txt,srt,vtt,tsv,json}
  Rovelli mid-roll/
    Rovelli mid-roll.{txt,srt,vtt,tsv,json}
  Rovelli part 02/
    Rovelli part 02.{txt,srt,vtt,tsv,json}
```

**Notes:**
- Whisper ran on CPU (FP16 not supported warning, fell back to FP32). MPS/Metal backend would be faster but `openai-whisper` via pipx defaults to CPU.
- Language detected as English automatically for all three files.
- Total processing time: ~17 minutes for ~37 minutes of audio.

### Step 2: Quick Combined Transcript

**Tool:** Python script (inline, not saved)
**Input:** All three SRT files in episode order (part 1 + mid-roll + part 2)

A Python script parsed the SRT format, merged subtitle fragments into flowing sentences, and grouped them into paragraphs at ~400-character intervals. This produced a raw combined text file with horizontal rule separators between the three parts.

**Output:** `WC_002_Rovelli/WC_002_Rovelli_transcript.txt`

This was an intermediate artifact -- readable but lacking speaker attribution or editorial polish. It served as a quick proof that the transcription was coherent before investing in the full formatting pass.

### Step 3: Agent Creation

Before running the formatting and chapters passes, two project agents were created in `.claude/agents/` based on reference documents in `docs/`:

| Agent | Source Doc | Purpose |
|---|---|---|
| `timestamps` | `docs/timestamps.md` | Generate chapter markers in three formats (description timestamps, Podcasting 2.0 JSON, YouTube) |
| `transcript-formatter` | `docs/transcripts.md` | Transform raw SRT into clean speaker-attributed markdown |

The source documents served different purposes:
- `timestamps.md` was a **platform reference** (Apple, Spotify, YouTube specs) that needed to be internalized as operational rules
- `transcripts.md` was already **agent instructions** (from the PBS Wisconsin Editorial Assistant pipeline) that needed adaptation for the podcast project

Both agents use `model: sonnet` and follow the project's YAML frontmatter convention.

### Step 4: Formatted Transcript

**Agent:** `transcript-formatter`
**Input:** Three SRT files + episode context (show name, host/guest names, topic list, production credits)

The formatter agent read all three SRT files in sequence, identified speakers from context, and produced a clean markdown transcript with:
- Consistent `**First Last:**` speaker attribution
- Proper punctuation and filler word removal
- Natural paragraph breaks at topic shifts
- `**Narrator:**` for the press conference clip in the archival section
- Metadata header (project, program, duration, date)
- Status: `ready_for_editing`

**Output:** `WC_002_Rovelli/formatted_transcript.md`

**Known issue:** Without diarization data, some speaker attributions in the back-and-forth conversational sections may be swapped. The `ready_for_editing` status signals a human review pass is expected.

### Step 5: Chapter Markers

**Agent:** `timestamps`
**Input:** Three SRT files + episode context (content flow, topic breakdown)

The timestamps agent read all three SRT files, calculated combined timecodes (offsetting mid-roll and part 2 by prior durations), and identified five chapter boundaries:

| Timestamp | Chapter |
|---|---|
| 00:00:00 | Introduction & The Chirp of Black Holes |
| 00:04:10 | Early Years in Verona |
| 00:10:00 | Falling in Love with Physics |
| 00:17:30 | Search for Truth |
| 00:25:05 | Politics of Wonder |

The mid-roll ad break (~16:48-17:10) was excluded from chapters per Apple Podcasts best practices.

**Output:** `WC_002_Rovelli/chapters.md` (contains all three format variants + a chapter breakdown with content summaries)

Steps 4 and 5 ran in parallel as independent tasks.

## Final Deliverables

```
WC_002_Rovelli/
  Rovelli part 01.mp3                    # source audio
  Rovelli mid-roll.mp3                   # source audio
  Rovelli part 02.mp3                    # source audio
  Rovelli part 01/                       # Whisper output (5 formats)
  Rovelli mid-roll/                      # Whisper output (5 formats)
  Rovelli part 02/                       # Whisper output (5 formats)
  WC_002_Rovelli_transcript.txt          # quick combined transcript (intermediate)
  formatted_transcript.md                # publication-ready transcript
  chapters.md                            # chapter markers (3 formats)
```

## Process Diagram

```
  MP3 files (x3)
       |
       v
  [whisper-transcribe.sh]  ---- turbo model, batch mode
       |
       v
  SRT/TXT/VTT/TSV/JSON (x3 sets)
       |
       +---> [quick combine script] ---> WC_002_Rovelli_transcript.txt (intermediate)
       |
       +---> [transcript-formatter agent] ---> formatted_transcript.md
       |          reads SRT files + episode context
       |
       +---> [timestamps agent] ---> chapters.md
                  reads SRT files + episode context
                  calculates combined timecodes
```

## Observations and Improvements

### What worked well
- Batch transcription handled the multi-file episode cleanly with skip-existing support
- Parallel agent execution (formatter + timestamps simultaneously) saved time
- SRT format proved ideal as the common input for both agents -- it carries timecodes that the timestamps agent needs while also being parseable for text extraction

### Areas for improvement
- **Speaker diarization**: Whisper alone doesn't identify speakers. Adding `whisperx` with pyannote diarization at the transcription stage would make downstream speaker attribution far more reliable and reduce the need for human review.
- **GPU acceleration**: Running Whisper on CPU (FP32) is slow. Configuring the `openai-whisper` pipx environment to use MPS/Metal on Apple Silicon would significantly reduce transcription time.
- **Multi-file timecode handling**: When an episode ships as multiple files, the timecodes reset to 00:00 in each. The timestamps agent handled the offset math, but a utility to pre-merge SRT files with corrected timecodes would simplify this for all downstream consumers.
- **Mid-roll detection**: Currently manual (provided as episode context). Could be automated by detecting short files between longer ones, or by audio analysis (music/jingle detection).
