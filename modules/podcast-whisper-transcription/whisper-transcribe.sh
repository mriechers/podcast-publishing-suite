#!/bin/bash
# whisper-transcribe.sh - Transcribe audio/video files using OpenAI Whisper
# Uses turbo model for best speed/accuracy balance on Apple Silicon
#
# Dependencies:
#   - OpenAI Whisper (installed via pipx)
#   - Apple Silicon Mac recommended (M1/M2/M3/M4) for turbo model
#   - ~8GB RAM minimum for turbo model
#   - ffmpeg (for audio extraction from video)
#
# Installation (if not present, script will offer to install):
#   pipx install openai-whisper
#
# Model sizes and RAM requirements:
#   tiny:   ~1GB RAM   (fast, lower accuracy)
#   base:   ~1GB RAM   (good for simple audio)
#   small:  ~2GB RAM   (balanced)
#   medium: ~5GB RAM   (high accuracy)
#   turbo:  ~6GB RAM   (best speed/accuracy on Apple Silicon) ← default
#   large:  ~10GB RAM  (highest accuracy, slow)

set -e

# Configuration
MODEL="turbo"
FORMAT="all"  # Output all formats (txt, vtt, srt, tsv, json)
WHISPER_BIN="${HOME}/.local/bin/whisper"

# Minimum requirements for turbo model
MIN_RAM_GB=8
RECOMMENDED_RAM_GB=16

# Supported audio/video extensions
EXTENSIONS="mp3|wav|m4a|flac|ogg|opus|wma|aac|mp4|mkv|webm|avi|mov|m4v"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $(basename "$0") [OPTIONS] <audio_file_or_directory>"
    echo ""
    echo "Transcribe audio/video using Whisper turbo model."
    echo "Output: Creates a folder next to the source file with all formats."
    echo ""
    echo "Options:"
    echo "  --check    Check system compatibility without transcribing"
    echo "  --install  Install Whisper (after checking compatibility)"
    echo "  --help     Show this help message"
    echo ""
    echo "If a directory is provided, all supported files are processed sequentially."
    echo ""
    echo "Supported formats: mp3, wav, m4a, flac, ogg, opus, wma, aac,"
    echo "                   mp4, mkv, webm, avi, mov, m4v"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") interview.mp3"
    echo "  $(basename "$0") ~/Downloads/podcast.m4a"
    echo "  $(basename "$0") ~/Videos/interviews/"
    echo "  $(basename "$0") --check"
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# System Compatibility Checks
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

    # Architecture check
    echo -n "  CPU: "
    if [[ "$IS_APPLE_SILICON" == true ]]; then
        echo -e "${GREEN}✓${NC} $CHIP (Apple Silicon)"
    elif [[ "$ARCH" == "x86_64" ]]; then
        echo -e "${YELLOW}⚠${NC} $CHIP (Intel)"
        WARNINGS+=("Intel Macs can run Whisper but significantly slower than Apple Silicon")
    else
        echo -e "${RED}✗${NC} $ARCH"
        BLOCKERS+=("Unsupported architecture: $ARCH")
        COMPATIBLE=false
    fi

    # RAM check
    echo -n "  RAM: "
    if [[ $RAM_GB -ge $RECOMMENDED_RAM_GB ]]; then
        echo -e "${GREEN}✓${NC} ${RAM_GB}GB (excellent)"
    elif [[ $RAM_GB -ge $MIN_RAM_GB ]]; then
        echo -e "${YELLOW}⚠${NC} ${RAM_GB}GB (minimum met, ${RECOMMENDED_RAM_GB}GB+ recommended)"
        WARNINGS+=("${RAM_GB}GB RAM may cause slowdowns on large files")
    else
        echo -e "${RED}✗${NC} ${RAM_GB}GB (need ${MIN_RAM_GB}GB+ for turbo model)"
        BLOCKERS+=("Insufficient RAM. Use 'small' or 'base' model instead (edit MODEL in script).")
        COMPATIBLE=false
    fi

    # Check for pipx
    echo -n "  pipx: "
    if command -v pipx &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${YELLOW}○${NC} not found (needed to install Whisper)"
        WARNINGS+=("Install pipx first: brew install pipx && pipx ensurepath")
    fi

    # Check for ffmpeg
    echo -n "  ffmpeg: "
    if command -v ffmpeg &>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${YELLOW}○${NC} not found (needed for video files)"
        WARNINGS+=("Install ffmpeg: brew install ffmpeg")
    fi

    # Check Whisper status
    echo -n "  Whisper: "
    if [[ -x "$WHISPER_BIN" ]]; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${DIM}○${NC} not installed"
    fi

    echo ""

    # Show warnings
    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
        echo -e "${YELLOW}${BOLD}Warnings:${NC}"
        for warn in "${WARNINGS[@]}"; do
            echo -e "  ${YELLOW}⚠${NC} $warn"
        done
        echo ""
    fi

    # Show blockers
    if [[ ${#BLOCKERS[@]} -gt 0 ]]; then
        echo -e "${RED}${BOLD}Issues:${NC}"
        for block in "${BLOCKERS[@]}"; do
            echo -e "  ${RED}✗${NC} $block"
        done
        echo ""
    fi

    # Final verdict
    if [[ "$COMPATIBLE" == true ]]; then
        if [[ "$IS_APPLE_SILICON" == true ]] && [[ $RAM_GB -ge $RECOMMENDED_RAM_GB ]]; then
            echo -e "${GREEN}${BOLD}✓ Excellent${NC} - System is ideal for Whisper turbo model"
        else
            echo -e "${GREEN}${BOLD}✓ Compatible${NC} - System can run Whisper ${DIM}(may be slower)${NC}"
        fi
        return 0
    else
        echo -e "${RED}${BOLD}✗ Not recommended${NC} for turbo model"
        echo -e "${DIM}Tip: Edit MODEL=\"small\" in script for lower RAM usage${NC}"
        return 1
    fi
}

install_whisper() {
    echo -e "${BOLD}${CYAN}Whisper Installation${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Check compatibility first
    if ! check_system_compatibility; then
        echo ""
        echo -e "${YELLOW}System doesn't meet requirements for turbo model.${NC}"
        read -p "Install anyway (will work with smaller models)? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            return 1
        fi
    fi

    echo ""

    # Already installed?
    if [[ -x "$WHISPER_BIN" ]]; then
        echo -e "${GREEN}Whisper is already installed at ${WHISPER_BIN}${NC}"
        return 0
    fi

    # Need pipx
    if ! command -v pipx &>/dev/null; then
        echo -e "${YELLOW}pipx is required but not installed.${NC}"
        echo ""
        echo "Install pipx first:"
        echo -e "  ${CYAN}brew install pipx${NC}"
        echo -e "  ${CYAN}pipx ensurepath${NC}"
        echo ""
        echo "Then re-run: $(basename "$0") --install"
        return 1
    fi

    # Recommend ffmpeg
    if ! command -v ffmpeg &>/dev/null; then
        echo -e "${YELLOW}Note: ffmpeg recommended for video transcription${NC}"
        echo -e "  ${CYAN}brew install ffmpeg${NC}"
        echo ""
    fi

    echo "Ready to install OpenAI Whisper via pipx."
    echo ""
    echo -e "${DIM}This will:${NC}"
    echo -e "${DIM}  • Install openai-whisper in isolated environment${NC}"
    echo -e "${DIM}  • Create 'whisper' command at ~/.local/bin/whisper${NC}"
    echo -e "${DIM}  • First run downloads turbo model (~1.5GB)${NC}"
    echo ""

    read -p "Proceed? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}Installing openai-whisper...${NC}"
        pipx install openai-whisper

        if [[ -x "$WHISPER_BIN" ]]; then
            echo ""
            echo -e "${GREEN}${BOLD}✓ Whisper installed successfully!${NC}"
            echo ""
            echo "Transcribe files with:"
            echo -e "  ${CYAN}$(basename "$0") <audio_file>${NC}"
        else
            echo ""
            echo -e "${YELLOW}Installation completed but whisper not at expected path.${NC}"
            echo "Try: which whisper"
            return 1
        fi
    else
        echo "Installation cancelled."
        return 1
    fi
}

# Check whisper is installed (called before transcription)
check_whisper() {
    if [[ ! -x "$WHISPER_BIN" ]]; then
        echo -e "${RED}${BOLD}Whisper Not Installed${NC}"
        echo ""
        echo "Checking system compatibility..."
        echo ""

        if check_system_compatibility; then
            echo ""
            echo -e "To install Whisper, run:"
            echo -e "  ${CYAN}$(basename "$0") --install${NC}"
        fi

        exit 1
    fi
}

# Transcribe a single file
transcribe_file() {
    local INPUT_FILE="$1"
    local FILE_NUM="$2"
    local TOTAL_FILES="$3"

    # Get absolute path and directory
    INPUT_FILE=$(cd "$(dirname "$INPUT_FILE")" && pwd)/$(basename "$INPUT_FILE")
    local PARENT_DIR=$(dirname "$INPUT_FILE")
    local FILENAME=$(basename "$INPUT_FILE")
    local BASENAME="${FILENAME%.*}"
    local OUTPUT_DIR="${PARENT_DIR}/${BASENAME}"

    # Skip if already transcribed (folder exists with srt file)
    if [[ -d "$OUTPUT_DIR" ]] && [[ -f "${OUTPUT_DIR}/${BASENAME}.srt" ]]; then
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

    # Create output directory
    mkdir -p "$OUTPUT_DIR"

    # Run whisper with verbose output for progress bar
    "$WHISPER_BIN" "$INPUT_FILE" \
        --model "$MODEL" \
        --output_format "$FORMAT" \
        --output_dir "$OUTPUT_DIR" \
        --verbose True

    # Check if outputs were created
    if [[ -f "${OUTPUT_DIR}/${BASENAME}.srt" ]]; then
        echo ""
        echo -e "${GREEN}✓ Created:${NC} ${BASENAME}/"
        for ext in txt vtt srt tsv json; do
            if [[ -f "${OUTPUT_DIR}/${BASENAME}.${ext}" ]]; then
                echo -e "    ${BASENAME}.${ext}"
            fi
        done
    else
        echo -e "${RED}✗ Error: Output files were not created${NC}"
        return 1
    fi
}

# Find media files in directory (macOS compatible)
find_media_files() {
    local DIR="$1"
    find -E "$DIR" -maxdepth 1 -type f \
        -iregex ".*\\.($EXTENSIONS)$" | sort
}

# Main logic
main() {
    # Check arguments
    if [[ $# -lt 1 ]]; then
        usage
    fi

    # Handle options
    case "$1" in
        --help|-h)
            usage
            ;;
        --check)
            check_system_compatibility
            exit $?
            ;;
        --install)
            install_whisper
            exit $?
            ;;
        --*)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Run with --help for usage"
            exit 1
            ;;
    esac

    check_whisper

    local INPUT_PATH="$1"

    # Handle directory
    if [[ -d "$INPUT_PATH" ]]; then
        # Get absolute path
        INPUT_PATH=$(cd "$INPUT_PATH" && pwd)

        echo -e "${GREEN}${BOLD}Whisper Batch Transcription${NC}"
        echo -e "Directory: ${YELLOW}${INPUT_PATH}${NC}"
        echo -e "Model: ${MODEL} | Output: all formats (txt, vtt, srt, tsv, json)"
        echo ""

        # Find all media files
        local FILES=()
        while IFS= read -r file; do
            [[ -n "$file" ]] && FILES+=("$file")
        done < <(find_media_files "$INPUT_PATH")

        local TOTAL=${#FILES[@]}

        if [[ $TOTAL -eq 0 ]]; then
            echo -e "${YELLOW}No supported audio/video files found in directory.${NC}"
            exit 0
        fi

        echo -e "Found ${BOLD}${TOTAL}${NC} file(s) to process:"
        for f in "${FILES[@]}"; do
            echo "  • $(basename "$f")"
        done

        # Process each file
        local SUCCESS=0
        local SKIPPED=0
        local FAILED=0
        local COUNT=0

        for file in "${FILES[@]}"; do
            ((COUNT++))
            local FILE_BASENAME="${file%.*}"
            local FILE_DIR=$(dirname "$file")
            local FILE_NAME=$(basename "${file%.*}")
            local OUTPUT_FOLDER="${FILE_DIR}/${FILE_NAME}"

            # Check if already exists before calling transcribe
            local WAS_EXISTING=false
            [[ -d "$OUTPUT_FOLDER" ]] && [[ -f "${OUTPUT_FOLDER}/${FILE_NAME}.srt" ]] && WAS_EXISTING=true

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

        # Summary
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${BOLD}Batch Complete${NC}"
        echo -e "  ${GREEN}✓ Processed:${NC} $SUCCESS"
        if [[ $SKIPPED -gt 0 ]]; then
            echo -e "  ${YELLOW}⊘ Skipped:${NC}   $SKIPPED (already existed)"
        fi
        if [[ $FAILED -gt 0 ]]; then
            echo -e "  ${RED}✗ Failed:${NC}    $FAILED"
            exit 1
        fi

    # Handle single file
    elif [[ -f "$INPUT_PATH" ]]; then
        echo -e "${GREEN}${BOLD}Whisper Transcription${NC}"
        echo -e "Model: ${MODEL} | Output: all formats (txt, vtt, srt, tsv, json)"
        transcribe_file "$INPUT_PATH"

    else
        echo -e "${RED}Error: Path not found: ${INPUT_PATH}${NC}"
        exit 1
    fi
}

main "$@"
