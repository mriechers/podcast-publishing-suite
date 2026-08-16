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
#     - Hugging Face token for diarization, from any of:
#         $HF_TOKEN / $HUGGING_FACE_HUB_TOKEN, or ~/.cache/huggingface/token
#         (written by `huggingface-cli login`)
#       Resolved by huggingface_hub itself — this script never reads the token and
#       never passes it on a command line, so it stays out of `ps` output. whisperx
#       logs "No --hf_token provided..." even when resolution succeeds; that warning
#       is expected and harmless.
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
#   --max-speakers N            Diarization hint: maximum speakers (default: 6).
#                               This is a CEILING, not a target — pyannote estimates the
#                               cluster count and only then clamps it into [min, max], so a
#                               clean 2-person interview still resolves to 2. Set it high
#                               enough to cover archival clips and extra voices: a too-low
#                               ceiling MERGES speakers and needs a full re-run to fix,
#                               while a too-high one only risks a split that QC can catch.
#   --model MODEL               Override model (default: large-v3 for whisperx, turbo for whisper)
#   --relabel-references DIR    Map SPEAKER_NN clusters to real names using voice-anchor reels in DIR.
#                               DIR must contain *.wav references and a name_map.json mapping
#                               filenames to display names, e.g. {"anne.wav": "Anne Strainchamps"}.
#                               Only applied when diarization is enabled.
#   --glossary PATH             Apply proper-noun corrections from a glossary.json to the
#                               freshly written .srt/.txt/.vtt/.tsv (never the .json — see
#                               apply_glossary() for why). Runs AFTER relabel so speaker
#                               names are already resolved. Keeps <file>.original backups.
#                               Non-fatal: a missing file or script warns and continues.

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

ENGINE="whisperx"                    # Default engine: whisperx or whisper
DIARIZE=""                           # Empty = auto (on for whisperx, off for whisper)
MIN_SPEAKERS=2
MAX_SPEAKERS=6                       # Ceiling, not a target — see --max-speakers in the header
MODEL=""                             # Empty = engine default (large-v3 or turbo)
RELABEL_REFERENCES_DIR=""            # Empty = relabel disabled
RELABEL_THRESHOLD="0.5"              # Cosine sim threshold for cluster→name assignment
RELABEL_PY="${HOME}/.local/pipx/venvs/whisperx/bin/python"
GLOSSARY_FILE=""                     # Empty = glossary correction disabled

# Resolve script's own directory so we can locate sibling resources independently
# of how the script was invoked (relative path, symlink, etc.)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
    echo "  --max-speakers N           Maximum speaker count ceiling (default: 6)"
    echo "  --relabel-references DIR   Apply voice-anchor relabel post-diarization (DIR with *.wav + name_map.json)"
    echo "  --glossary PATH            Apply glossary.json corrections to .srt/.txt/.vtt/.tsv after relabel"
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
    echo "  $(basename "$0") --min-speakers 2 --max-speakers 6 ~/audio/"
    echo "  $(basename "$0") --glossary shows/wonder-cabinet/glossary.json ~/audio/"
    echo "  $(basename "$0") --no-diarize --model medium ~/audio/"
    echo "  $(basename "$0") --check"
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# Hugging Face token
# ─────────────────────────────────────────────────────────────────────────────
#
# We never read the token ourselves — whisperx passes token=None to
# Pipeline.from_pretrained, and huggingface_hub resolves it as
#   HF_TOKEN → HUGGING_FACE_HUB_TOKEN → $HF_TOKEN_FILE
# This predicate mirrors that exact order so our "can we diarize?" answer matches
# what the library will actually do. Checking only the file would wrongly disable
# diarization for anyone who exports HF_TOKEN but never ran `huggingface-cli login`.

have_hf_token() {
    [[ -n "${HF_TOKEN:-}" ]] && return 0
    [[ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]] && return 0
    [[ -f "$HF_TOKEN_FILE" ]] && [[ -s "$HF_TOKEN_FILE" ]] && return 0
    return 1
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

    # Engines
    echo ""
    echo -e "${BOLD}  Engines:${NC}"
    echo -n "    WhisperX: "
    if [[ -x "$WHISPERX_BIN" ]] || command -v whisperx &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${DIM}○${NC} not installed"
    fi

    echo -n "    Whisper:  "
    if [[ -x "$WHISPER_BIN" ]] || command -v whisper &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${DIM}○${NC} not installed"
    fi

    # HF token
    echo -n "    HF token: "
    if [[ -n "${HF_TOKEN:-}" ]]; then
        echo -e "${GREEN}✓${NC} present via \$HF_TOKEN (for pyannote diarization)"
    elif [[ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]]; then
        echo -e "${GREEN}✓${NC} present via \$HUGGING_FACE_HUB_TOKEN (for pyannote diarization)"
    elif [[ -f "$HF_TOKEN_FILE" ]] && [[ -s "$HF_TOKEN_FILE" ]]; then
        echo -e "${GREEN}✓${NC} present at ${HF_TOKEN_FILE/#$HOME/~} (for pyannote diarization)"
    else
        echo -e "${YELLOW}○${NC} not found — diarization requires HF token"
        WARNINGS+=("Set up HF token: huggingface-cli login (accept pyannote model terms first), or export HF_TOKEN")
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
    if ! have_hf_token; then
        echo -e "${YELLOW}${BOLD}Hugging Face token not found.${NC}"
        echo "  Diarization requires a HF token with accepted pyannote model terms."
        echo "  1. Create account at huggingface.co"
        echo "  2. Accept terms for pyannote/speaker-diarization-3.1"
        echo "  3. Run: huggingface-cli login"
        echo "     (or export HF_TOKEN=hf_... in your shell)"
    else
        echo -e "${GREEN}✓ HF token present${NC}"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Engine Resolution
# ─────────────────────────────────────────────────────────────────────────────

resolve_engine() {
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

    # Check HF token for diarization. Accept any source huggingface_hub accepts —
    # see have_hf_token(). Checking only the file would wrongly disable diarization
    # for someone who exports HF_TOKEN but never ran `huggingface-cli login`.
    if [[ "$DIARIZE" == "true" ]] && ! have_hf_token; then
        echo -e "${YELLOW}⚠ No Hugging Face token found — disabling diarization.${NC}"
        echo -e "${DIM}  Run 'huggingface-cli login', or export HF_TOKEN, to enable speaker diarization.${NC}"
        DIARIZE="false"
    fi

    # Issue #63: pyannote raises
    #   ValueError: min_speakers must be smaller than (or equal to) max_speakers
    # Clamp instead of aborting — an explicit --max-speakers is the operator's real
    # intent, and this script's contract is graceful degradation, not hard failure.
    # Runs before the banner, so the banner shows the value actually used.
    if [[ "$DIARIZE" == "true" ]] && [[ "$MIN_SPEAKERS" -gt "$MAX_SPEAKERS" ]]; then
        echo -e "${YELLOW}⚠ --min-speakers ($MIN_SPEAKERS) > --max-speakers ($MAX_SPEAKERS); clamping min to $MAX_SPEAKERS.${NC}"
        MIN_SPEAKERS="$MAX_SPEAKERS"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Transcription — WhisperX Engine
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Voice-anchor relabel (optional, post-diarization)
# ─────────────────────────────────────────────────────────────────────────────
#
# Maps anonymous SPEAKER_NN clusters from pyannote to real names by comparing
# each cluster's mean voice embedding to a set of reference reels in
# RELABEL_REFERENCES_DIR. Rewrites the just-produced .srt/.txt/.vtt/.tsv/.json
# in place with the real names.
#
# Skipped silently if RELABEL_REFERENCES_DIR is empty, diarization is off, or
# the references dir is missing required files.

apply_relabel() {
    local AUDIO_FILE="$1"
    local OUTPUT_DIR="$2"
    local BASENAME="$3"

    [[ -z "$RELABEL_REFERENCES_DIR" ]] && return 0
    [[ "$DIARIZE" != "true" ]] && return 0

    local REF_DIR="$RELABEL_REFERENCES_DIR"
    if [[ ! -d "$REF_DIR" ]]; then
        echo -e "${YELLOW}⚠ relabel skipped: references dir not found: $REF_DIR${NC}"
        return 0
    fi
    local NAME_MAP="$REF_DIR/name_map.json"
    if [[ ! -f "$NAME_MAP" ]]; then
        echo -e "${YELLOW}⚠ relabel skipped: $NAME_MAP missing (needed for filename → speaker name)${NC}"
        return 0
    fi

    local RELABEL_SCRIPT="$SCRIPT_DIR/../modules/podcast-whisper-transcription/scripts/relabel_speakers.py"
    if [[ ! -f "$RELABEL_SCRIPT" ]]; then
        echo -e "${YELLOW}⚠ relabel skipped: $RELABEL_SCRIPT not found${NC}"
        return 0
    fi
    if [[ ! -x "$RELABEL_PY" ]]; then
        echo -e "${YELLOW}⚠ relabel skipped: $RELABEL_PY not found (whisperx pipx venv missing)${NC}"
        return 0
    fi

    local JSON_FILE="$OUTPUT_DIR/$BASENAME.json"
    if [[ ! -f "$JSON_FILE" ]]; then
        echo -e "${YELLOW}⚠ relabel skipped: no JSON output at $JSON_FILE${NC}"
        return 0
    fi

    # Build --reference flags from name_map.json (one per entry).
    # Path passed via env var so apostrophes/spaces in paths don't break the python -c quoting.
    local REF_ARGS=()
    while IFS=$'\t' read -r filename speaker; do
        [[ -z "$filename" ]] && continue
        local ref_path="$REF_DIR/$filename"
        if [[ ! -f "$ref_path" ]]; then
            echo -e "${YELLOW}⚠ relabel: $ref_path listed in name_map.json but missing on disk; skipping that ref${NC}"
            continue
        fi
        REF_ARGS+=(--reference "${speaker}=${ref_path}")
    done < <(NAME_MAP_PATH="$NAME_MAP" python3 -c '
import json, os
with open(os.environ["NAME_MAP_PATH"]) as f: m = json.load(f)
for k, v in m.items(): print(f"{k}\t{v}")
')

    if [[ ${#REF_ARGS[@]} -eq 0 ]]; then
        echo -e "${YELLOW}⚠ relabel skipped: no usable references in $NAME_MAP${NC}"
        return 0
    fi

    echo -e "${CYAN}▸ Applying voice-anchor relabel...${NC}"
    local MAPPING_OUT="$OUTPUT_DIR/$BASENAME.relabel_mapping.json"
    local APPLY_FILES=()
    for ext in srt txt vtt tsv json; do
        local f="$OUTPUT_DIR/$BASENAME.$ext"
        [[ -f "$f" ]] && APPLY_FILES+=("$f")
    done

    if "$RELABEL_PY" "$RELABEL_SCRIPT" \
        --model "pyannote/wespeaker-voxceleb-resnet34-LM" \
        --audio "$AUDIO_FILE" \
        --json  "$JSON_FILE" \
        "${REF_ARGS[@]}" \
        --threshold "$RELABEL_THRESHOLD" \
        --out-mapping "$MAPPING_OUT" \
        --apply "${APPLY_FILES[@]}" 2>&1 | grep -vE "UserWarning|torchcodec|FFmpeg|PyTorch|Another runtime|Reason:|in your environment|We support|version compatibility|see exceptions|conda install|use audio preloaded|/opt/homebrew|/System/Volumes|warnings.warn|versions 4|table:" >&2; then
        echo -e "${GREEN}  ✓ relabel applied${NC} (mapping: $BASENAME.relabel_mapping.json)"
        return 0
    else
        echo -e "${YELLOW}  ⚠ relabel failed (transcript files left with raw SPEAKER_NN labels)${NC}"
        return 0  # don't fail the overall transcription on relabel issues
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Glossary corrections (optional, post-relabel)
# ─────────────────────────────────────────────────────────────────────────────
#
# Applies word-boundary proper-noun corrections from a show glossary.json to the
# freshly written .srt/.txt/.vtt/.tsv. Fixes the class of bug where a name already
# known to the glossary still shipped misspelled in the captions.
#
# Deliberately NOT applied to .json. That file is the machine artifact of record:
# it is apply_relabel's input, and its segments[].words[] array holds individually
# quoted tokens, so a multi-word correction would rewrite segments[].text while
# leaving the word array stale — silently desynchronising the two for any consumer
# that rebuilds captions from word timings.
#
# Runs AFTER apply_relabel, so speaker labels are already real names and each
# <file>.original backup means exactly one thing: post-relabel, pre-glossary.
# Reversing the order would make that backup capture raw SPEAKER_NN labels, and
# restoring from it would silently discard speaker names as well as corrections.
#
# Corollary for glossary authors: a key must never equal a canonical name from
# name_map.json, or it would rewrite the labels relabel just applied.
#
# Skipped silently when GLOSSARY_FILE is empty; warns and continues on any other
# problem. Never fails the transcription.

apply_glossary() {
    local OUTPUT_DIR="$1"
    local BASENAME="$2"

    [[ -z "$GLOSSARY_FILE" ]] && return 0

    if [[ ! -f "$GLOSSARY_FILE" ]]; then
        echo -e "${YELLOW}⚠ glossary skipped: file not found: $GLOSSARY_FILE${NC}"
        return 0
    fi

    local GLOSSARY_SCRIPT="$SCRIPT_DIR/../modules/podcast-whisper-transcription/scripts/apply_glossary.py"
    if [[ ! -f "$GLOSSARY_SCRIPT" ]]; then
        echo -e "${YELLOW}⚠ glossary skipped: $GLOSSARY_SCRIPT not found${NC}"
        echo -e "${DIM}  Run: git submodule update --init modules/podcast-whisper-transcription${NC}"
        return 0
    fi

    # Prose formats only — see the note above on why .json is excluded.
    local APPLY_FILES=()
    for ext in srt txt vtt tsv; do
        local f="$OUTPUT_DIR/$BASENAME.$ext"
        [[ -f "$f" ]] && APPLY_FILES+=("$f")
    done

    if [[ ${#APPLY_FILES[@]} -eq 0 ]]; then
        echo -e "${YELLOW}⚠ glossary skipped: no correctable outputs in $OUTPUT_DIR${NC}"
        return 0
    fi

    echo -e "${CYAN}▸ Applying glossary corrections...${NC}"
    # Plain python3: apply_glossary.py is pure stdlib and does not need the torch venv.
    # Backups are kept deliberately — they are the safety net if a glossary key turns
    # out to be over-broad, and QC diffs them.
    if python3 "$GLOSSARY_SCRIPT" --glossary "$GLOSSARY_FILE" "${APPLY_FILES[@]}"; then
        return 0
    else
        echo -e "${YELLOW}  ⚠ glossary failed (transcript files left uncorrected)${NC}"
        return 0  # don't fail the overall transcription on glossary issues
    fi
}

transcribe_file_whisperx() {
    local INPUT_FILE="$1"
    local PARENT_DIR=$(dirname "$INPUT_FILE")
    local FILENAME=$(basename "$INPUT_FILE")
    local BASENAME="${FILENAME%.*}"
    local OUTPUT_DIR="${PARENT_DIR}/${BASENAME}"

    # WhisperX writes files flat into output_dir.
    # Use a temp dir, then move outputs into the per-file subdir
    # to match the convention expected by the pipeline.
    local TEMP_OUTPUT_DIR=$(mktemp -d)

    local WX_ARGS=(
        "$INPUT_FILE"
        --model "$MODEL"
        --language "$LANGUAGE"
        --output_format "all"
        --output_dir "$TEMP_OUTPUT_DIR"
    )

    if [[ "$DIARIZE" == "true" ]]; then
        # No --hf_token: whisperx passes token=None to Pipeline.from_pretrained and
        # huggingface_hub resolves HF_TOKEN → HUGGING_FACE_HUB_TOKEN → the token file
        # itself. Passing it here would put the secret in `ps` output for every local
        # user. (Do not reintroduce a `local HF_TOKEN` here — it would shadow the real
        # env var that have_hf_token() consults.) whisperx logs a "No --hf_token
        # provided" warning even on success; that is expected.
        WX_ARGS+=(
            --diarize
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
        apply_relabel "$INPUT_FILE" "$OUTPUT_DIR" "$BASENAME"
        apply_glossary "$OUTPUT_DIR" "$BASENAME"   # must follow relabel — see apply_glossary()
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
        # No apply_relabel here: relabel needs diarization, which plain whisper never
        # does. Glossary correction is pure text and has no such dependency — skipping
        # it would ship misspelled captions whenever whisperx is unavailable.
        apply_glossary "$OUTPUT_DIR" "$BASENAME"
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
                if ! [[ "${2:-}" =~ ^[1-9][0-9]*$ ]]; then
                    echo -e "${RED}Error: --min-speakers requires a positive integer (got: '${2:-<missing>}')${NC}"
                    exit 1
                fi
                MIN_SPEAKERS="$2"
                shift 2
                ;;
            --max-speakers)
                if ! [[ "${2:-}" =~ ^[1-9][0-9]*$ ]]; then
                    echo -e "${RED}Error: --max-speakers requires a positive integer (got: '${2:-<missing>}')${NC}"
                    exit 1
                fi
                MAX_SPEAKERS="$2"
                shift 2
                ;;
            --relabel-references)
                RELABEL_REFERENCES_DIR="$2"
                shift 2
                ;;
            --glossary)
                GLOSSARY_FILE="$2"
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
        [[ -n "$RELABEL_REFERENCES_DIR" ]] && echo -e "Relabel: ${RELABEL_REFERENCES_DIR}"
        [[ -n "$GLOSSARY_FILE" ]] && echo -e "Glossary: ${GLOSSARY_FILE}"
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
        [[ -n "$RELABEL_REFERENCES_DIR" ]] && echo -e "Relabel: ${RELABEL_REFERENCES_DIR}"
        [[ -n "$GLOSSARY_FILE" ]] && echo -e "Glossary: ${GLOSSARY_FILE}"
        [[ -n "$INITIAL_PROMPT" ]] && echo -e "Prompt: ${DIM}${INITIAL_PROMPT:0:80}$([ ${#INITIAL_PROMPT} -gt 80 ] && echo '...')${NC}"
        transcribe_file "$INPUT_PATH"
    else
        echo -e "${RED}Error: Path not found: ${INPUT_PATH}${NC}"
        exit 1
    fi
}

main "$@"
