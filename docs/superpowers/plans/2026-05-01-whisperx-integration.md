# WhisperX Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace standard Whisper with WhisperX as the default transcription engine, adding speaker diarization to the podcast pipeline while keeping standard Whisper as a fallback.

**Architecture:** Dual-engine `whisper-transcribe.sh` script with WhisperX (large-v3 + pyannote diarization) as default and standard Whisper (turbo) as fallback. Downstream pipeline (`combine_srts.py`, formatter agent, `wc-transcribe` skill) updated to preserve and use `[SPEAKER_XX]:` labels. Independent copies of the script in both `podcast-publishing-suite` and `the-lodge`.

**Tech Stack:** Bash (whisper-transcribe.sh), Python 3 (combine_srts.py), WhisperX 3.8+ (faster-whisper + pyannote.audio 3.1), openai-whisper (fallback)

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `scripts/whisper-transcribe.sh` | Dual-engine transcription script (WhisperX default, Whisper fallback) |
| Modify | `modules/podcast-whisper-transcription/scripts/combine_srts.py` | Preserve `[SPEAKER_XX]:` prefixes when combining SRT entries |
| Create | `modules/podcast-whisper-transcription/tests/test_combine_srts.py` | Tests for combine_srts.py speaker label preservation |
| Modify | `modules/podcast-whisper-transcription/.claude/agents/transcript-formatter.md` | Add diarization label handling instructions |
| Modify | `.claude/commands/wc-transcribe.md` | Update Phase 2 to use local script with `--max-speakers` flag |
| Create | `~/Developer/the-lodge/scripts/whisper-transcribe.sh` | Independent copy of dual-engine script for the-lodge |

---

### Task 1: Tests for `combine_srts.py` Speaker Label Preservation

**Files:**
- Create: `modules/podcast-whisper-transcription/tests/test_combine_srts.py`

Speaker labels like `[SPEAKER_00]: Hello` appear in WhisperX SRT output as part of the text line. The current `combine_srts.py` passes text through as-is (it doesn't strip labels), but we need tests to lock this behavior in and verify the TXT output also preserves them.

- [ ] **Step 1: Write tests for SRT speaker label passthrough**

```python
"""Tests for combine_srts.py — speaker label preservation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from combine_srts import parse_srt, combine_entries, write_srt, write_txt


class TestSpeakerLabelPreservation:
    """Verify [SPEAKER_XX]: prefixes survive the combine pipeline."""

    def _write_srt(self, tmp_path, name, content):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_parse_preserves_speaker_labels(self, tmp_path):
        """parse_srt should keep [SPEAKER_XX]: prefix in the text field."""
        srt = self._write_srt(tmp_path, "part1.srt", (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "[SPEAKER_00]: Hello world\n"
            "\n"
            "2\n"
            "00:00:02,500 --> 00:00:05,000\n"
            "[SPEAKER_01]: Good morning\n"
        ))
        entries = parse_srt(srt)
        assert len(entries) == 2
        assert entries[0].text == "[SPEAKER_00]: Hello world"
        assert entries[1].text == "[SPEAKER_01]: Good morning"

    def test_combine_preserves_speaker_labels_across_files(self, tmp_path):
        """combine_entries should keep speaker labels from multiple files."""
        srt1 = self._write_srt(tmp_path, "part1.srt", (
            "1\n"
            "00:00:00,000 --> 00:00:03,000\n"
            "[SPEAKER_00]: Part one speech\n"
        ))
        srt2 = self._write_srt(tmp_path, "part2.srt", (
            "1\n"
            "00:00:00,000 --> 00:00:04,000\n"
            "[SPEAKER_01]: Part two speech\n"
        ))
        combined, boundaries = combine_entries([srt1, srt2])
        assert len(combined) == 2
        assert combined[0].text == "[SPEAKER_00]: Part one speech"
        assert combined[1].text == "[SPEAKER_01]: Part two speech"
        # Second file's timecodes should be offset
        assert combined[1].start_ms == 3000

    def test_write_srt_preserves_speaker_labels(self, tmp_path):
        """write_srt should output [SPEAKER_XX]: prefixes in the SRT text."""
        srt_in = self._write_srt(tmp_path, "input.srt", (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "[SPEAKER_00]: Test line\n"
        ))
        entries = parse_srt(srt_in)
        entries[0].index = 1
        out = tmp_path / "output.srt"
        write_srt(entries, out)
        content = out.read_text(encoding="utf-8")
        assert "[SPEAKER_00]: Test line" in content

    def test_write_txt_preserves_speaker_labels(self, tmp_path):
        """write_txt should keep [SPEAKER_XX]: prefixes in plain text output."""
        srt_in = self._write_srt(tmp_path, "input.srt", (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "[SPEAKER_00]: First sentence of the episode hello everyone.\n"
            "\n"
            "2\n"
            "00:00:02,500 --> 00:00:05,000\n"
            "[SPEAKER_01]: Welcome to the show today.\n"
        ))
        entries = parse_srt(srt_in)
        for i, e in enumerate(entries):
            e.index = i + 1
        out = tmp_path / "output.txt"
        write_txt(entries, [len(entries)], out)
        content = out.read_text(encoding="utf-8")
        assert "[SPEAKER_00]:" in content
        assert "[SPEAKER_01]:" in content

    def test_mixed_labeled_and_unlabeled(self, tmp_path):
        """Entries without speaker labels should also work (standard Whisper output)."""
        srt = self._write_srt(tmp_path, "plain.srt", (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "Hello world\n"
            "\n"
            "2\n"
            "00:00:02,500 --> 00:00:05,000\n"
            "Good morning\n"
        ))
        entries = parse_srt(srt)
        assert entries[0].text == "Hello world"
        assert entries[1].text == "Good morning"


class TestCombineBasics:
    """Verify existing combine behavior still works."""

    def _write_srt(self, tmp_path, name, content):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_timecode_offset_between_parts(self, tmp_path):
        """Second file timecodes should be offset by first file's end time."""
        srt1 = self._write_srt(tmp_path, "p1.srt", (
            "1\n00:00:00,000 --> 00:00:10,000\nLine one\n"
        ))
        srt2 = self._write_srt(tmp_path, "p2.srt", (
            "1\n00:00:00,000 --> 00:00:05,000\nLine two\n"
        ))
        combined, _ = combine_entries([srt1, srt2])
        assert combined[0].start_ms == 0
        assert combined[0].end_ms == 10000
        assert combined[1].start_ms == 10000
        assert combined[1].end_ms == 15000

    def test_sequential_indexing(self, tmp_path):
        """Combined entries should have sequential 1-based indices."""
        srt1 = self._write_srt(tmp_path, "p1.srt", (
            "1\n00:00:00,000 --> 00:00:02,000\nA\n\n"
            "2\n00:00:02,000 --> 00:00:04,000\nB\n"
        ))
        srt2 = self._write_srt(tmp_path, "p2.srt", (
            "1\n00:00:00,000 --> 00:00:03,000\nC\n"
        ))
        combined, _ = combine_entries([srt1, srt2])
        assert [e.index for e in combined] == [1, 2, 3]
```

- [ ] **Step 2: Run tests to verify they pass**

The current `combine_srts.py` already passes text through without stripping, so these tests should pass immediately — they lock in existing behavior.

Run:
```bash
cd modules/podcast-whisper-transcription && python -m pytest tests/test_combine_srts.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add modules/podcast-whisper-transcription/tests/test_combine_srts.py
git commit -m "test: add combine_srts tests for speaker label preservation

Lock in existing behavior: [SPEAKER_XX]: prefixes in SRT text
fields pass through parse, combine, write_srt, and write_txt
unchanged. Covers both diarized (WhisperX) and plain (Whisper)
input."
```

---

### Task 2: Create Dual-Engine `whisper-transcribe.sh`

**Files:**
- Create: `scripts/whisper-transcribe.sh`

This is a full rewrite of the transcription script, adding WhisperX as the default engine with standard Whisper as fallback. The script keeps the same UX (colored output, batch processing, `--check`/`--install`/`--force`/`--prompt`/`--help` flags) and adds new flags for engine selection and diarization control.

- [ ] **Step 1: Create the script**

```bash
#!/bin/bash
# whisper-transcribe.sh - Transcribe audio/video files using WhisperX or OpenAI Whisper
#
# Default engine: WhisperX (large-v3 via faster-whisper + pyannote diarization)
# Fallback engine: OpenAI Whisper (turbo model)
#
# Dependencies:
#   WhisperX engine:
#     - whisperx (installed via pipx, requires Python 3.11)
#     - pyannote.audio (bundled with whisperx)
#     - Hugging Face token at ~/.cache/huggingface/token (for diarization)
#   Whisper engine (fallback):
#     - openai-whisper (installed via pipx)
#   Both:
#     - ffmpeg (for audio extraction)
#     - Apple Silicon Mac recommended
#
# Usage:
#   whisper-transcribe.sh [OPTIONS] <audio_file_or_directory>
#
# New flags (vs. original):
#   --engine whisperx|whisper   Select engine (default: whisperx)
#   --diarize                   Enable speaker diarization (default when engine=whisperx)
#   --no-diarize                Disable diarization (faster)
#   --min-speakers N            Diarization hint: minimum speakers (default: 2)
#   --max-speakers N            Diarization hint: maximum speakers (default: 4)
#   --model MODEL               Override model (default: large-v3 for whisperx, turbo for whisper)

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

ENGINE="whisperx"                    # Default engine: whisperx or whisper
DIARIZE=""                           # Empty = auto (on for whisperx, off for whisper)
MIN_SPEAKERS=2
MAX_SPEAKERS=4
MODEL=""                             # Empty = engine default (large-v3 or turbo)
FORMAT="all"
LANGUAGE="en"
FORCE=false
INITIAL_PROMPT=""

# Whisper-specific anti-hallucination settings
HALLUCINATION_SILENCE_THRESHOLD="2.0"
CONDITION_ON_PREVIOUS_TEXT="False"
NO_SPEECH_THRESHOLD="0.8"

# Paths
WHISPERX_BIN="${HOME}/.local/bin/whisperx"
WHISPER_BIN="${HOME}/.local/bin/whisper"
HF_TOKEN_FILE="${HOME}/.cache/huggingface/token"

# Diarization model (user must accept terms on HuggingFace)
DIARIZE_MODEL="pyannote/speaker-diarization-3.1"

# System requirements
MIN_RAM_GB=8
RECOMMENDED_RAM_GB=16

# Supported extensions
EXTENSIONS="mp3|wav|m4a|flac|ogg|opus|wma|aac|mp4|mkv|webm|avi|mov|m4v"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Usage
# ─────────────────────────────────────────────────────────────────────────────

usage() {
    echo "Usage: $(basename "$0") [OPTIONS] <audio_file_or_directory>"
    echo ""
    echo "Transcribe audio/video using WhisperX (default) or OpenAI Whisper."
    echo "Output: Creates a folder next to the source file with all formats."
    echo ""
    echo "Engine options:"
    echo "  --engine whisperx|whisper  Transcription engine (default: whisperx)"
    echo "  --diarize                  Enable speaker diarization (default for whisperx)"
    echo "  --no-diarize               Disable diarization (faster, no speaker labels)"
    echo "  --min-speakers N           Minimum speaker count hint (default: 2)"
    echo "  --max-speakers N           Maximum speaker count hint (default: 4)"
    echo "  --model MODEL              Override model (default: large-v3 / turbo)"
    echo ""
    echo "General options:"
    echo "  --check    Check system compatibility and engine status"
    echo "  --install  Install transcription engines"
    echo "  --prompt TEXT  Initial prompt for transcription (names, context)"
    echo "  --force    Re-transcribe even if output already exists"
    echo "  --help     Show this help message"
    echo ""
    echo "If a directory is provided, all supported files are processed individually."
    echo ""
    echo "Supported formats: mp3, wav, m4a, flac, ogg, opus, wma, aac,"
    echo "                   mp4, mkv, webm, avi, mov, m4v"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") interview.mp3"
    echo "  $(basename "$0") --engine whisper ~/audio/podcast.mp3"
    echo "  $(basename "$0") --max-speakers 3 ~/audio/"
    echo "  $(basename "$0") --no-diarize --model medium ~/audio/"
    echo "  $(basename "$0") --check"
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# System Checks
# ─────────────────────────────────────────────────────────────────────────────

get_system_info() {
    ARCH=$(uname -m)
    OS=$(uname -s)

    if [[ "$OS" == "Darwin" ]]; then
        RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
        RAM_GB=$((RAM_BYTES / 1024 / 1024 / 1024))
        if [[ "$ARCH" == "arm64" ]]; then
            IS_APPLE_SILICON=true
            CHIP=$(system_profiler SPHardwareDataType 2>/dev/null | grep "Chip:" | sed 's/.*: //' || echo "Apple Silicon")
        else
            IS_APPLE_SILICON=false
            CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Intel")
        fi
    else
        RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo 0)
        IS_APPLE_SILICON=false
        CHIP="$ARCH"
    fi
}

check_system_compatibility() {
    get_system_info

    local COMPATIBLE=true
    local WARNINGS=()
    local BLOCKERS=()

    echo -e "${BOLD}${CYAN}System Compatibility Check${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # CPU
    echo -n "  CPU: "
    if [[ "$IS_APPLE_SILICON" == true ]]; then
        echo -e "${GREEN}✓${NC} $CHIP (Apple Silicon)"
    elif [[ "$ARCH" == "x86_64" ]]; then
        echo -e "${YELLOW}⚠${NC} $CHIP (Intel — slower)"
        WARNINGS+=("Intel Macs can run both engines but significantly slower than Apple Silicon")
    else
        echo -e "${RED}✗${NC} $ARCH"
        BLOCKERS+=("Unsupported architecture: $ARCH")
        COMPATIBLE=false
    fi

    # RAM
    echo -n "  RAM: "
    if [[ $RAM_GB -ge $RECOMMENDED_RAM_GB ]]; then
        echo -e "${GREEN}✓${NC} ${RAM_GB}GB (excellent)"
    elif [[ $RAM_GB -ge $MIN_RAM_GB ]]; then
        echo -e "${YELLOW}⚠${NC} ${RAM_GB}GB (minimum met, ${RECOMMENDED_RAM_GB}GB+ recommended)"
        WARNINGS+=("${RAM_GB}GB RAM may cause slowdowns with large-v3 model")
    else
        echo -e "${RED}✗${NC} ${RAM_GB}GB (need ${MIN_RAM_GB}GB+)"
        BLOCKERS+=("Insufficient RAM for large-v3 model")
        COMPATIBLE=false
    fi

    # pipx
    echo -n "  pipx: "
    if command -v pipx &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${YELLOW}○${NC} not found (needed to install engines)"
        WARNINGS+=("Install pipx: brew install pipx && pipx ensurepath")
    fi

    # ffmpeg
    echo -n "  ffmpeg: "
    if command -v ffmpeg &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${YELLOW}○${NC} not found (required for audio processing)"
        WARNINGS+=("Install ffmpeg: brew install ffmpeg")
    fi

    # WhisperX
    echo ""
    echo -e "${BOLD}  Engines:${NC}"
    echo -n "    WhisperX: "
    if [[ -x "$WHISPERX_BIN" ]] || command -v whisperx &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${DIM}○${NC} not installed"
    fi

    # Standard Whisper
    echo -n "    Whisper:  "
    if [[ -x "$WHISPER_BIN" ]] || command -v whisper &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${DIM}○${NC} not installed"
    fi

    # HF token
    echo -n "    HF token: "
    if [[ -f "$HF_TOKEN_FILE" ]] && [[ -s "$HF_TOKEN_FILE" ]]; then
        echo -e "${GREEN}✓${NC} present (for pyannote diarization)"
    else
        echo -e "${YELLOW}○${NC} not found — diarization requires HF token"
        WARNINGS+=("Set up HF token: huggingface-cli login (accept pyannote model terms first)")
    fi

    echo ""

    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
        echo -e "${YELLOW}${BOLD}Warnings:${NC}"
        for warn in "${WARNINGS[@]}"; do
            echo -e "  ${YELLOW}⚠${NC} $warn"
        done
        echo ""
    fi

    if [[ ${#BLOCKERS[@]} -gt 0 ]]; then
        echo -e "${RED}${BOLD}Issues:${NC}"
        for block in "${BLOCKERS[@]}"; do
            echo -e "  ${RED}✗${NC} $block"
        done
        echo ""
    fi

    if [[ "$COMPATIBLE" == true ]]; then
        if [[ "$IS_APPLE_SILICON" == true ]] && [[ $RAM_GB -ge $RECOMMENDED_RAM_GB ]]; then
            echo -e "${GREEN}${BOLD}✓ Excellent${NC} — ideal for WhisperX large-v3 + diarization"
        else
            echo -e "${GREEN}${BOLD}✓ Compatible${NC} — system can run transcription ${DIM}(may be slower)${NC}"
        fi
        return 0
    else
        echo -e "${RED}${BOLD}✗ Not recommended${NC}"
        return 1
    fi
}

install_engines() {
    echo -e "${BOLD}${CYAN}Transcription Engine Installation${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if ! check_system_compatibility; then
        echo ""
        echo -e "${YELLOW}System doesn't meet requirements.${NC}"
        read -p "Install anyway? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            return 1
        fi
    fi

    echo ""

    if ! command -v pipx &>/dev/null; then
        echo -e "${YELLOW}pipx is required. Install it first:${NC}"
        echo -e "  ${CYAN}brew install pipx && pipx ensurepath${NC}"
        return 1
    fi

    # WhisperX
    echo -e "${BOLD}1. WhisperX${NC} (primary engine — large-v3 + diarization)"
    if [[ -x "$WHISPERX_BIN" ]] || command -v whisperx &>/dev/null; then
        echo -e "   ${GREEN}Already installed${NC}"
    else
        echo -e "   ${DIM}Requires Python 3.11 (whisperx doesn't support 3.14)${NC}"
        read -p "   Install WhisperX? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo -e "   ${BLUE}Installing whisperx...${NC}"
            pipx install whisperx --python python3.11
            echo -e "   ${GREEN}✓ WhisperX installed${NC}"
        fi
    fi

    echo ""

    # Standard Whisper
    echo -e "${BOLD}2. OpenAI Whisper${NC} (fallback engine — turbo model)"
    if [[ -x "$WHISPER_BIN" ]] || command -v whisper &>/dev/null; then
        echo -e "   ${GREEN}Already installed${NC}"
    else
        read -p "   Install OpenAI Whisper? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo -e "   ${BLUE}Installing openai-whisper...${NC}"
            pipx install openai-whisper
            echo -e "   ${GREEN}✓ Whisper installed${NC}"
        fi
    fi

    echo ""

    # HF token check
    if [[ ! -f "$HF_TOKEN_FILE" ]] || [[ ! -s "$HF_TOKEN_FILE" ]]; then
        echo -e "${YELLOW}${BOLD}Hugging Face token not found.${NC}"
        echo "  Diarization requires a HF token with accepted pyannote model terms."
        echo "  1. Create account at huggingface.co"
        echo "  2. Accept terms for pyannote/speaker-diarization-3.1"
        echo "  3. Run: huggingface-cli login"
    else
        echo -e "${GREEN}✓ HF token present${NC}"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Engine Resolution
# ─────────────────────────────────────────────────────────────────────────────

resolve_engine() {
    # Determine the actual engine and model to use, applying fallbacks

    # Find actual binary paths
    if [[ -x "$WHISPERX_BIN" ]]; then
        ACTUAL_WHISPERX_BIN="$WHISPERX_BIN"
    elif command -v whisperx &>/dev/null; then
        ACTUAL_WHISPERX_BIN=$(command -v whisperx)
    else
        ACTUAL_WHISPERX_BIN=""
    fi

    if [[ -x "$WHISPER_BIN" ]]; then
        ACTUAL_WHISPER_BIN="$WHISPER_BIN"
    elif command -v whisper &>/dev/null; then
        ACTUAL_WHISPER_BIN=$(command -v whisper)
    else
        ACTUAL_WHISPER_BIN=""
    fi

    # Engine selection with fallback
    if [[ "$ENGINE" == "whisperx" ]]; then
        if [[ -z "$ACTUAL_WHISPERX_BIN" ]]; then
            echo -e "${YELLOW}⚠ WhisperX not found, falling back to Whisper turbo (no diarization).${NC}"
            ENGINE="whisper"
        fi
    fi

    if [[ "$ENGINE" == "whisper" ]]; then
        if [[ -z "$ACTUAL_WHISPER_BIN" ]]; then
            echo -e "${RED}Error: No transcription engine found.${NC}"
            echo "Run: $(basename "$0") --install"
            exit 1
        fi
    fi

    # Resolve model default
    if [[ -z "$MODEL" ]]; then
        if [[ "$ENGINE" == "whisperx" ]]; then
            MODEL="large-v3"
        else
            MODEL="turbo"
        fi
    fi

    # Resolve diarization
    if [[ -z "$DIARIZE" ]]; then
        if [[ "$ENGINE" == "whisperx" ]]; then
            DIARIZE="true"
        else
            DIARIZE="false"
        fi
    fi

    # Check HF token for diarization
    if [[ "$DIARIZE" == "true" ]]; then
        if [[ ! -f "$HF_TOKEN_FILE" ]] || [[ ! -s "$HF_TOKEN_FILE" ]]; then
            echo -e "${YELLOW}⚠ HF token not found — disabling diarization.${NC}"
            echo -e "${DIM}  Run 'huggingface-cli login' to enable speaker diarization.${NC}"
            DIARIZE="false"
        fi
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Transcription — WhisperX Engine
# ─────────────────────────────────────────────────────────────────────────────

transcribe_file_whisperx() {
    local INPUT_FILE="$1"
    local PARENT_DIR=$(dirname "$INPUT_FILE")
    local FILENAME=$(basename "$INPUT_FILE")
    local BASENAME="${FILENAME%.*}"
    local OUTPUT_DIR="${PARENT_DIR}/${BASENAME}"

    # WhisperX writes files flat into output_dir.
    # We use a temp dir, then move outputs into the per-file subdir
    # to match the convention expected by the pipeline.
    local TEMP_OUTPUT_DIR=$(mktemp -d)

    # Build whisperx command
    local WX_ARGS=(
        "$INPUT_FILE"
        --model "$MODEL"
        --language "$LANGUAGE"
        --output_format "all"
        --output_dir "$TEMP_OUTPUT_DIR"
    )

    if [[ "$DIARIZE" == "true" ]]; then
        local HF_TOKEN
        HF_TOKEN=$(cat "$HF_TOKEN_FILE")
        WX_ARGS+=(
            --diarize
            --hf_token "$HF_TOKEN"
            --diarize_model "$DIARIZE_MODEL"
            --min_speakers "$MIN_SPEAKERS"
            --max_speakers "$MAX_SPEAKERS"
        )
    fi

    if [[ -n "$INITIAL_PROMPT" ]]; then
        WX_ARGS+=(--initial_prompt "$INITIAL_PROMPT")
    fi

    "$ACTUAL_WHISPERX_BIN" "${WX_ARGS[@]}"

    # Move outputs from flat temp dir into per-file subdir
    mkdir -p "$OUTPUT_DIR"
    for f in "$TEMP_OUTPUT_DIR"/"${BASENAME}".*; do
        [[ -f "$f" ]] && mv "$f" "$OUTPUT_DIR/"
    done
    rm -rf "$TEMP_OUTPUT_DIR"

    # Verify output
    if [[ -f "${OUTPUT_DIR}/${BASENAME}.srt" ]]; then
        echo ""
        echo -e "${GREEN}✓ Created:${NC} ${BASENAME}/"
        for ext in txt vtt srt tsv json; do
            [[ -f "${OUTPUT_DIR}/${BASENAME}.${ext}" ]] && echo -e "    ${BASENAME}.${ext}"
        done
        return 0
    else
        echo -e "${RED}✗ Error: Output files were not created${NC}"
        return 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Transcription — Standard Whisper Engine
# ─────────────────────────────────────────────────────────────────────────────

transcribe_file_whisper() {
    local INPUT_FILE="$1"
    local PARENT_DIR=$(dirname "$INPUT_FILE")
    local FILENAME=$(basename "$INPUT_FILE")
    local BASENAME="${FILENAME%.*}"
    local OUTPUT_DIR="${PARENT_DIR}/${BASENAME}"

    mkdir -p "$OUTPUT_DIR"

    local W_ARGS=(
        "$INPUT_FILE"
        --model "$MODEL"
        --output_format "$FORMAT"
        --output_dir "$OUTPUT_DIR"
        --language "$LANGUAGE"
        --hallucination_silence_threshold "$HALLUCINATION_SILENCE_THRESHOLD"
        --condition_on_previous_text "$CONDITION_ON_PREVIOUS_TEXT"
        --no_speech_threshold "$NO_SPEECH_THRESHOLD"
        --verbose True
    )

    if [[ -n "$INITIAL_PROMPT" ]]; then
        W_ARGS+=(--initial_prompt "$INITIAL_PROMPT")
    fi

    "$ACTUAL_WHISPER_BIN" "${W_ARGS[@]}"

    if [[ -f "${OUTPUT_DIR}/${BASENAME}.srt" ]]; then
        echo ""
        echo -e "${GREEN}✓ Created:${NC} ${BASENAME}/"
        for ext in txt vtt srt tsv json; do
            [[ -f "${OUTPUT_DIR}/${BASENAME}.${ext}" ]] && echo -e "    ${BASENAME}.${ext}"
        done
        return 0
    else
        echo -e "${RED}✗ Error: Output files were not created${NC}"
        return 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# File Processing (shared logic)
# ─────────────────────────────────────────────────────────────────────────────

transcribe_file() {
    local INPUT_FILE="$1"
    local FILE_NUM="$2"
    local TOTAL_FILES="$3"

    # Resolve absolute path
    INPUT_FILE=$(cd "$(dirname "$INPUT_FILE")" && pwd)/$(basename "$INPUT_FILE")
    local PARENT_DIR=$(dirname "$INPUT_FILE")
    local FILENAME=$(basename "$INPUT_FILE")
    local BASENAME="${FILENAME%.*}"
    local OUTPUT_DIR="${PARENT_DIR}/${BASENAME}"

    # Skip if already transcribed unless --force
    if [[ "$FORCE" != true ]] && [[ -d "$OUTPUT_DIR" ]] && [[ -f "${OUTPUT_DIR}/${BASENAME}.srt" ]]; then
        echo -e "${YELLOW}Skipping${NC} (already exists): ${FILENAME} → ${BASENAME}/"
        return 0
    fi

    # Progress header
    if [[ -n "$TOTAL_FILES" ]] && [[ "$TOTAL_FILES" -gt 1 ]]; then
        echo ""
        echo -e "${BOLD}${BLUE}[$FILE_NUM/$TOTAL_FILES]${NC} ${BOLD}${FILENAME}${NC}"
    else
        echo -e "${BOLD}${FILENAME}${NC}"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Dispatch to engine
    if [[ "$ENGINE" == "whisperx" ]]; then
        transcribe_file_whisperx "$INPUT_FILE"
    else
        transcribe_file_whisper "$INPUT_FILE"
    fi
}

# Find media files (macOS compatible)
find_media_files() {
    local DIR="$1"
    find -E "$DIR" -maxdepth 1 -type f \
        -iregex ".*\\.($EXTENSIONS)$" | sort
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

main() {
    if [[ $# -lt 1 ]]; then
        usage
    fi

    # Parse options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                usage
                ;;
            --check)
                check_system_compatibility
                exit $?
                ;;
            --install)
                install_engines
                exit $?
                ;;
            --engine)
                ENGINE="$2"
                if [[ "$ENGINE" != "whisperx" ]] && [[ "$ENGINE" != "whisper" ]]; then
                    echo -e "${RED}Error: --engine must be 'whisperx' or 'whisper'${NC}"
                    exit 1
                fi
                shift 2
                ;;
            --diarize)
                DIARIZE="true"
                shift
                ;;
            --no-diarize)
                DIARIZE="false"
                shift
                ;;
            --min-speakers)
                MIN_SPEAKERS="$2"
                shift 2
                ;;
            --max-speakers)
                MAX_SPEAKERS="$2"
                shift 2
                ;;
            --model)
                MODEL="$2"
                shift 2
                ;;
            --prompt)
                INITIAL_PROMPT="$2"
                shift 2
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --*)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Run with --help for usage"
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done

    if [[ $# -lt 1 ]]; then
        usage
    fi

    # Resolve engine and fallbacks
    resolve_engine

    local INPUT_PATH="$1"

    # Engine/diarization banner
    local ENGINE_LABEL
    if [[ "$ENGINE" == "whisperx" ]]; then
        ENGINE_LABEL="WhisperX"
        [[ "$DIARIZE" == "true" ]] && ENGINE_LABEL="WhisperX + diarization"
    else
        ENGINE_LABEL="Whisper"
    fi

    # Handle directory
    if [[ -d "$INPUT_PATH" ]]; then
        INPUT_PATH=$(cd "$INPUT_PATH" && pwd)

        echo -e "${GREEN}${BOLD}Transcription — ${ENGINE_LABEL}${NC}"
        echo -e "Directory: ${YELLOW}${INPUT_PATH}${NC}"
        echo -e "Engine: ${ENGINE_LABEL} | Model: ${MODEL} | Language: ${LANGUAGE}"
        [[ "$DIARIZE" == "true" ]] && echo -e "Speakers: ${MIN_SPEAKERS}-${MAX_SPEAKERS}"
        [[ -n "$INITIAL_PROMPT" ]] && echo -e "Prompt: ${DIM}${INITIAL_PROMPT:0:80}$([ ${#INITIAL_PROMPT} -gt 80 ] && echo '...')${NC}"
        [[ "$FORCE" == true ]] && echo -e "${YELLOW}Force mode: re-transcribing existing files${NC}"
        echo ""

        local FILES=()
        while IFS= read -r file; do
            [[ -n "$file" ]] && FILES+=("$file")
        done < <(find_media_files "$INPUT_PATH")

        local TOTAL=${#FILES[@]}

        if [[ $TOTAL -eq 0 ]]; then
            echo -e "${YELLOW}No supported audio/video files found.${NC}"
            exit 0
        fi

        echo -e "Found ${BOLD}${TOTAL}${NC} file(s) to process:"
        for f in "${FILES[@]}"; do
            echo "  • $(basename "$f")"
        done

        local SUCCESS=0 SKIPPED=0 FAILED=0 COUNT=0

        for file in "${FILES[@]}"; do
            ((COUNT++))
            local FILE_NAME=$(basename "${file%.*}")
            local FILE_DIR=$(dirname "$file")
            local OUTPUT_FOLDER="${FILE_DIR}/${FILE_NAME}"

            local WAS_EXISTING=false
            [[ "$FORCE" != true ]] && [[ -d "$OUTPUT_FOLDER" ]] && [[ -f "${OUTPUT_FOLDER}/${FILE_NAME}.srt" ]] && WAS_EXISTING=true

            if transcribe_file "$file" "$COUNT" "$TOTAL"; then
                if $WAS_EXISTING; then
                    ((SKIPPED++))
                else
                    ((SUCCESS++))
                fi
            else
                ((FAILED++))
            fi
        done

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${BOLD}Batch Complete${NC} (${ENGINE_LABEL})"
        echo -e "  ${GREEN}✓ Processed:${NC} $SUCCESS"
        [[ $SKIPPED -gt 0 ]] && echo -e "  ${YELLOW}⊘ Skipped:${NC}   $SKIPPED (already existed)"
        [[ $FAILED -gt 0 ]] && echo -e "  ${RED}✗ Failed:${NC}    $FAILED"

    elif [[ -f "$INPUT_PATH" ]]; then
        echo -e "${GREEN}${BOLD}Transcription — ${ENGINE_LABEL}${NC}"
        echo -e "Engine: ${ENGINE_LABEL} | Model: ${MODEL} | Language: ${LANGUAGE}"
        [[ "$DIARIZE" == "true" ]] && echo -e "Speakers: ${MIN_SPEAKERS}-${MAX_SPEAKERS}"
        [[ -n "$INITIAL_PROMPT" ]] && echo -e "Prompt: ${DIM}${INITIAL_PROMPT:0:80}$([ ${#INITIAL_PROMPT} -gt 80 ] && echo '...')${NC}"
        transcribe_file "$INPUT_PATH"
    else
        echo -e "${RED}Error: Path not found: ${INPUT_PATH}${NC}"
        exit 1
    fi
}

main "$@"
```

- [ ] **Step 2: Make the script executable**

Run:
```bash
chmod +x scripts/whisper-transcribe.sh
```

- [ ] **Step 3: Smoke test — check flag**

Run:
```bash
./scripts/whisper-transcribe.sh --check
```

Expected: System compatibility report showing CPU, RAM, both engines, HF token status.

- [ ] **Step 4: Smoke test — help flag**

Run:
```bash
./scripts/whisper-transcribe.sh --help
```

Expected: Usage text showing all new flags (--engine, --diarize, --min-speakers, etc.)

- [ ] **Step 5: Commit**

```bash
git add scripts/whisper-transcribe.sh
git commit -m "feat: add dual-engine whisper-transcribe.sh with WhisperX + diarization

WhisperX (large-v3 + pyannote 3.1) as default engine with standard
Whisper turbo as fallback. New flags: --engine, --diarize,
--no-diarize, --min-speakers, --max-speakers. Automatic fallback
chain: whisperx→whisper, diarize→no-diarize. Per-file processing
to prevent batch crashes from losing completed output. Normalizes
WhisperX flat output into per-file subdirectories."
```

---

### Task 3: Update `combine_srts.py` Text Output for Speaker Labels

**Files:**
- Modify: `modules/podcast-whisper-transcription/scripts/combine_srts.py:125-163`
- Test: `modules/podcast-whisper-transcription/tests/test_combine_srts.py`

The SRT passthrough already works (text field is preserved as-is). The TXT output's `write_txt()` function merges fragments into paragraphs by joining with spaces. With speaker labels, we should start a new paragraph when the speaker changes, so that `[SPEAKER_00]: text` and `[SPEAKER_01]: text` don't get merged into one run-on paragraph.

- [ ] **Step 1: Write failing test for speaker-aware paragraph breaks**

Add this test to `test_combine_srts.py`:

```python
class TestSpeakerAwareTxtOutput:
    """TXT output should break paragraphs on speaker changes."""

    def _write_srt(self, tmp_path, name, content):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_speaker_change_forces_paragraph_break(self, tmp_path):
        """When speaker changes, start a new paragraph even if under 400 chars."""
        srt = self._write_srt(tmp_path, "input.srt", (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "[SPEAKER_00]: Hello everyone.\n"
            "\n"
            "2\n"
            "00:00:02,500 --> 00:00:04,000\n"
            "[SPEAKER_00]: Welcome to the show.\n"
            "\n"
            "3\n"
            "00:00:04,500 --> 00:00:07,000\n"
            "[SPEAKER_01]: Thanks for having me.\n"
        ))
        entries = parse_srt(srt)
        for i, e in enumerate(entries):
            e.index = i + 1
        out = tmp_path / "output.txt"
        write_txt(entries, [len(entries)], out)
        content = out.read_text(encoding="utf-8")
        # SPEAKER_00 lines should be in one paragraph,
        # SPEAKER_01 should start a new paragraph
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        assert len(paragraphs) >= 2
        assert "[SPEAKER_01]:" in paragraphs[-1]

    def test_no_speaker_labels_unchanged_behavior(self, tmp_path):
        """Without speaker labels, paragraph merging works as before (~400 chars)."""
        srt = self._write_srt(tmp_path, "input.srt", (
            "1\n00:00:00,000 --> 00:00:01,000\nShort line.\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\nAnother short line.\n"
        ))
        entries = parse_srt(srt)
        for i, e in enumerate(entries):
            e.index = i + 1
        out = tmp_path / "output.txt"
        write_txt(entries, [len(entries)], out)
        content = out.read_text(encoding="utf-8")
        # Both short lines merged into one paragraph
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        assert len(paragraphs) == 1
```

- [ ] **Step 2: Run tests to verify the speaker-change test fails**

Run:
```bash
cd modules/podcast-whisper-transcription && python -m pytest tests/test_combine_srts.py::TestSpeakerAwareTxtOutput::test_speaker_change_forces_paragraph_break -v
```

Expected: FAIL — currently all fragments merge by character count only, not speaker boundaries.

- [ ] **Step 3: Update `write_txt()` to break on speaker changes**

In `modules/podcast-whisper-transcription/scripts/combine_srts.py`, replace the `write_txt` function:

```python
SPEAKER_LABEL_RE = re.compile(r"^\[SPEAKER_\d+\]:")


def write_txt(
    entries: list[SrtEntry], boundaries: list[int], output_path: Path
) -> None:
    """Generate a combined plain text transcript from SRT entries.

    Merges subtitle fragments into paragraphs of ~400 chars with ---
    separators between source parts. When speaker labels are present,
    starts a new paragraph on speaker change.
    """
    parts: list[list[SrtEntry]] = []
    prev = 0
    for b in boundaries:
        parts.append(entries[prev:b])
        prev = b

    sections = []
    for part_entries in parts:
        if not part_entries:
            continue

        fragments = [e.text.replace("\n", " ").strip() for e in part_entries]

        paragraphs = []
        current = []
        current_len = 0
        current_speaker = None

        for frag in fragments:
            # Detect speaker label
            speaker_match = SPEAKER_LABEL_RE.match(frag)
            speaker = speaker_match.group(0) if speaker_match else None

            # Break paragraph on speaker change
            if speaker is not None and speaker != current_speaker and current:
                paragraphs.append(" ".join(current))
                current = []
                current_len = 0

            current_speaker = speaker
            current.append(frag)
            current_len += len(frag) + 1
            if current_len >= 400:
                paragraphs.append(" ".join(current))
                current = []
                current_len = 0
                current_speaker = speaker  # preserve for next fragment

        if current:
            paragraphs.append(" ".join(current))

        sections.append("\n\n".join(paragraphs))

    output_path.write_text("\n\n---\n\n".join(sections), encoding="utf-8")
```

- [ ] **Step 4: Run all combine_srts tests**

Run:
```bash
cd modules/podcast-whisper-transcription && python -m pytest tests/test_combine_srts.py -v
```

Expected: All tests PASS (including both new speaker-aware tests and all previous tests).

- [ ] **Step 5: Commit**

```bash
git add modules/podcast-whisper-transcription/scripts/combine_srts.py \
       modules/podcast-whisper-transcription/tests/test_combine_srts.py
git commit -m "feat: break TXT paragraphs on speaker change in combine_srts

When SRT entries contain [SPEAKER_XX]: prefixes (WhisperX output),
write_txt() now starts a new paragraph when the speaker changes.
Standard Whisper output (no labels) continues to merge by ~400
char threshold as before."
```

---

### Task 4: Update Formatter Agent for Diarization Labels

**Files:**
- Modify: `modules/podcast-whisper-transcription/.claude/agents/transcript-formatter.md`

Add instructions for handling WhisperX speaker diarization labels. This goes after the existing "Speaker Attribution" section (currently lines 76-83).

- [ ] **Step 1: Add diarization label section to formatter agent**

In `modules/podcast-whisper-transcription/.claude/agents/transcript-formatter.md`, after the Speaker Attribution subsection (after line 83, the "Unknown speakers" bullet), add:

```markdown
### Speaker Diarization Labels

If the SRT input contains `[SPEAKER_XX]:` prefixes on text lines, use these as the **primary signal** for speaker attribution. These labels come from WhisperX voice-based diarization and are more reliable than conversational cues alone.

**Mapping anonymous IDs to real names:**

1. Identify which `SPEAKER_XX` corresponds to each known speaker using:
   - Self-identification ("I'm Anne Strainchamps", "my name is...")
   - Conversational role (who asks questions vs. gives long answers)
   - Segment count (the guest typically has the most segments)
   - Episode context provided to you (guest name, host names)

2. Speaker IDs may differ between parts — Part 1's `SPEAKER_00` may not be Part 2's `SPEAKER_00`. Map independently per part.

3. When diarization labels conflict with conversational cues, **prefer the diarization label** — it's based on voice, not content.

4. If diarization labels are absent (legacy Whisper output without `[SPEAKER_XX]:` prefixes), fall back to conversational-cue-based attribution as before.
```

- [ ] **Step 2: Verify the file looks correct**

Read the modified file and confirm the new section is correctly placed and formatted.

- [ ] **Step 3: Commit**

```bash
git add modules/podcast-whisper-transcription/.claude/agents/transcript-formatter.md
git commit -m "feat: add diarization label handling to formatter agent

Formatter now uses [SPEAKER_XX]: prefixes from WhisperX output as
primary speaker attribution signal. Maps anonymous IDs to real
names per-part. Falls back to conversational cues when labels are
absent (standard Whisper output)."
```

---

### Task 5: Update `wc-transcribe` Skill Phase 2

**Files:**
- Modify: `.claude/commands/wc-transcribe.md` (lines 133-137)

Change Phase 2 to use the local script instead of the cross-repo dependency on `the-lodge`.

- [ ] **Step 1: Update the Phase 2 command**

In `.claude/commands/wc-transcribe.md`, replace:

```bash
~/Developer/the-lodge/scripts/whisper-transcribe.sh "$CANONICAL_DIR/audio/"
```

with:

```bash
./scripts/whisper-transcribe.sh --max-speakers 3 "$CANONICAL_DIR/audio/"
```

This is relative to the `podcast-publishing-suite` repo root. The `--max-speakers 3` flag is appropriate for Wonder Cabinet (Anne, Steve, + 1 guest).

- [ ] **Step 2: Verify the change**

Read lines 129-150 of `.claude/commands/wc-transcribe.md` to confirm the update is correct and surrounding context is preserved.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/wc-transcribe.md
git commit -m "feat: use local whisper-transcribe.sh in wc-transcribe skill

Replace cross-repo dependency on the-lodge/scripts/whisper-transcribe.sh
with local scripts/whisper-transcribe.sh. Adds --max-speakers 3 for
Wonder Cabinet's typical 3-speaker setup (2 hosts + 1 guest)."
```

---

### Task 6: Copy Script to the-lodge

**Files:**
- Create: `~/Developer/the-lodge/scripts/whisper-transcribe.sh`

The-lodge gets its own independent copy. This is a straight copy — both repos start with the same script, and they may drift independently over time.

- [ ] **Step 1: Copy the script**

```bash
cp scripts/whisper-transcribe.sh ~/Developer/the-lodge/scripts/whisper-transcribe.sh
chmod +x ~/Developer/the-lodge/scripts/whisper-transcribe.sh
```

- [ ] **Step 2: Verify the copy**

```bash
diff scripts/whisper-transcribe.sh ~/Developer/the-lodge/scripts/whisper-transcribe.sh
```

Expected: No differences.

- [ ] **Step 3: Smoke test in the-lodge context**

```bash
~/Developer/the-lodge/scripts/whisper-transcribe.sh --check
```

Expected: Same system compatibility report as the local copy.

- [ ] **Step 4: Commit in the-lodge repo**

```bash
cd ~/Developer/the-lodge
git add scripts/whisper-transcribe.sh
git commit -m "feat: upgrade whisper-transcribe.sh with WhisperX + diarization

Dual-engine script: WhisperX (large-v3 + pyannote 3.1 diarization)
as default, standard Whisper turbo as fallback. New flags: --engine,
--diarize, --no-diarize, --min-speakers, --max-speakers. Per-file
processing prevents batch crashes from losing output."
cd -
```

---

### Task 7: Integration Test — Full Pipeline Dry Run

This task verifies the entire pipeline works end-to-end on a real audio file.

- [ ] **Step 1: Run the new script on a short audio file**

Use the midroll from E12 (22 seconds — fastest test):

```bash
./scripts/whisper-transcribe.sh --max-speakers 1 --force \
  "shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/audio/Henderson_midroll.mp3"
```

Expected: WhisperX processes the file with diarization, creates `Henderson_midroll/` subdir alongside the MP3 with `Henderson_midroll.srt` containing `[SPEAKER_00]:` prefixes.

- [ ] **Step 2: Verify SRT output has speaker labels**

```bash
head -10 "shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/audio/Henderson_midroll/Henderson_midroll.srt"
```

Expected: Lines containing `[SPEAKER_00]:` prefix.

- [ ] **Step 3: Test combine_srts.py with diarized SRT**

```bash
python3 modules/podcast-whisper-transcription/scripts/combine_srts.py \
  "shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/audio/Henderson_midroll/Henderson_midroll.srt" \
  --output-dir /tmp/whisperx-test \
  --output-name "test-combine" \
  --txt
```

Verify:
```bash
cat /tmp/whisperx-test/test-combine.srt | head -10
cat /tmp/whisperx-test/test-combine.txt
```

Expected: Speaker labels preserved in both SRT and TXT output.

- [ ] **Step 4: Test fallback to standard Whisper**

```bash
./scripts/whisper-transcribe.sh --engine whisper --force \
  "shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/audio/Henderson_midroll.mp3"
```

Expected: Standard Whisper turbo processes the file (no `[SPEAKER_XX]:` labels in output).

- [ ] **Step 5: Clean up test outputs**

```bash
rm -rf "shows/wonder-cabinet/episodes/WC_S01_12_Rebecca_Henderson/audio/Henderson_midroll/"
rm -rf /tmp/whisperx-test
```

- [ ] **Step 6: Report results**

Summarize: what worked, any issues found, whether the pipeline is ready for production use.
