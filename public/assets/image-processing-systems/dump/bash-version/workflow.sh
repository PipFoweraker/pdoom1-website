#!/bin/bash
# Batch Image Processing Workflow for pdoom1-website Assets (Bash Implementation)
#
# Automated workflow for processing cat images and other assets:
# 1. Scans dump folder for new images
# 2. Processes with appropriate settings
# 3. Organizes outputs by format and size
# 4. Generates manifest for tracking
#
# Usage:
#     ./workflow.sh [--scan-only] [--force]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DUMP_DIR="${SCRIPT_DIR}"
OUTPUT_BASE="${SCRIPT_DIR}/processed"
PROCESSED_DIR="${OUTPUT_BASE}"
ARCHIVE_DIR="${DUMP_DIR}/archive"
MANIFEST_FILE="${DUMP_DIR}/manifest.json"

# Defaults
SCAN_ONLY=false
FORCE=false

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_ok() {
    echo -e "${GREEN}[OK]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Load manifest
load_manifest() {
    if [[ -f "$MANIFEST_FILE" ]]; then
        cat "$MANIFEST_FILE"
    else
        cat << EOF
{
  "processed": {},
  "last_run": null,
  "statistics": {
    "total_processed": 0,
    "total_outputs": 0
  }
}
EOF
    fi
}

# Save manifest
save_manifest() {
    echo "$MANIFEST_CONTENT" > "$MANIFEST_FILE"
}

# Check if image is already processed
is_processed() {
    local base_name="$1"
    echo "$MANIFEST_CONTENT" | jq -e --arg name "$base_name" \
        '.processed[$name]' >/dev/null 2>&1
}

# Get file size in MB
get_file_size_mb() {
    local file="$1"
    local size_bytes
    size_bytes=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
    echo "scale=2; $size_bytes / 1024 / 1024" | bc
}

# Process cat image
process_cat_image() {
    local image_path="$1"
    local base_name
    base_name=$(basename "$image_path" | sed 's/\.[^.]*$//')
    
    # Check if already processed
    if [[ "$FORCE" != "true" ]] && is_processed "$base_name"; then
        log_info "Skipping $base_name (already processed)"
        return 0
    fi
    
    log_info "Processing cat image: $(basename "$image_path")"
    
    # Web-optimized outputs with multiple aspect ratios
    log_info "Creating web-optimized outputs with multiple aspect ratios..."
    local web_aspect_ratios=("square" "wide" "standard" "portrait" "original")
    for aspect_ratio in "${web_aspect_ratios[@]}"; do
        "$SCRIPT_DIR/process_image.sh" "$image_path" \
            --output-dir "$PROCESSED_DIR/web" \
            --formats webp jpeg \
            --sizes web-thumbnail web-small web-medium web-large \
            --aspect-ratio "$aspect_ratio" || true
    done
    
    # Game-optimized outputs (preserve original aspect)
    log_info "Creating game-optimized outputs..."
    "$SCRIPT_DIR/process_image.sh" "$image_path" \
        --output-dir "$PROCESSED_DIR/game" \
        --formats png webp \
        --sizes game-small game-medium game-large \
        --aspect-ratio original || true
    
    # Count outputs
    local web_count game_count
    web_count=$(find "$PROCESSED_DIR/web" -name "${base_name}_*" 2>/dev/null | wc -l)
    game_count=$(find "$PROCESSED_DIR/game" -name "${base_name}_*" 2>/dev/null | wc -l)
    local total_outputs=$((web_count + game_count))
    
    # Get file size
    local file_size_mb
    file_size_mb=$(get_file_size_mb "$image_path")
    
    # Update manifest
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    MANIFEST_CONTENT=$(echo "$MANIFEST_CONTENT" | jq \
        --arg name "$base_name" \
        --arg source "$(basename "$image_path")" \
        --arg timestamp "$timestamp" \
        --arg size "$file_size_mb" \
        --argjson outputs "$total_outputs" \
        '
        .processed[$name] = {
            "source": $source,
            "processed_at": $timestamp,
            "file_size_mb": ($size | tonumber),
            "output_count": $outputs
        } |
        .statistics.total_processed = (.processed | length) |
        .statistics.total_outputs = (.statistics.total_outputs + $outputs) |
        .last_run = $timestamp
        ')
    
    # Archive original
    local archive_path="$ARCHIVE_DIR/$(basename "$image_path")"
    if [[ ! -f "$archive_path" ]]; then
        cp "$image_path" "$archive_path"
        log_info "Archived original to: $archive_path"
    fi
    
    log_ok "Processed $base_name ($total_outputs outputs)"
}

# Scan for new images
scan_new_images() {
    local image_files=()
    while IFS= read -r -d '' file; do
        image_files+=("$file")
    done < <(find "$DUMP_DIR" -maxdepth 1 -type f \
        \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \
        -o -iname "*.webp" -o -iname "*.gif" -o -iname "*.bmp" \
        -o -iname "*.tiff" \) -print0)
    
    # Filter out already processed
    local new_images=()
    for img_file in "${image_files[@]}"; do
        local base_name
        base_name=$(basename "$img_file" | sed 's/\.[^.]*$//')
        if [[ "$FORCE" == "true" ]] || ! is_processed "$base_name"; then
            new_images+=("$img_file")
        fi
    done
    
    printf '%s\n' "${new_images[@]}"
}

# Main workflow
run_workflow() {
    log_info "Starting asset processing workflow..."
    log_info "Web: Multiple aspect ratios with optimized compression (85% quality WebP)"
    log_info "Game: High-quality assets with original aspect ratio"
    
    # Ensure directories exist
    mkdir -p "$PROCESSED_DIR/web"
    mkdir -p "$PROCESSED_DIR/game"
    mkdir -p "$ARCHIVE_DIR"
    
    # Load manifest
    MANIFEST_CONTENT=$(load_manifest)
    
    # Check for jq dependency
    if ! command -v jq >/dev/null 2>&1; then
        log_error "jq is required for manifest handling"
        log_error "Install with: sudo apt install jq"
        exit 1
    fi
    
    # Scan for new images
    local new_images
    mapfile -t new_images < <(scan_new_images)
    
    if [[ ${#new_images[@]} -eq 0 ]]; then
        log_info "No new images to process."
        if [[ "$SCAN_ONLY" == "true" ]]; then
            local processed_count
            processed_count=$(echo "$MANIFEST_CONTENT" | jq '.processed | length')
            log_info "Already processed: $processed_count images"
        fi
        return 0
    fi
    
    if [[ "$SCAN_ONLY" == "true" ]]; then
        log_info "Found ${#new_images[@]} new images to process:"
        for img in "${new_images[@]}"; do
            local size_mb
            size_mb=$(get_file_size_mb "$img")
            echo "  - $(basename "$img") ($size_mb MB)"
        done
        return 0
    fi
    
    # Process each image
    log_info "Processing ${#new_images[@]} new images..."
    for image_path in "${new_images[@]}"; do
        if ! process_cat_image "$image_path"; then
            log_error "Failed to process: $image_path"
            continue
        fi
    done
    
    # Save manifest
    save_manifest
    
    # Print summary
    local total_processed total_outputs
    total_processed=$(echo "$MANIFEST_CONTENT" | jq '.statistics.total_processed')
    total_outputs=$(echo "$MANIFEST_CONTENT" | jq '.statistics.total_outputs')
    
    log_ok "Workflow complete!"
    log_info "  Processed: $total_processed images"
    log_info "  Total outputs: $total_outputs"
    log_info "  Web outputs: $PROCESSED_DIR/web"
    log_info "  Game outputs: $PROCESSED_DIR/game"
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --scan-only)
                SCAN_ONLY=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --dump-dir)
                DUMP_DIR="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_BASE="$2"
                PROCESSED_DIR="$OUTPUT_BASE"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Usage: $0 [options]

Options:
    --scan-only        Only scan for new images, do not process
    --force           Reprocess all images even if already processed
    --dump-dir <dir>  Directory containing raw images (default: script dir)
    --output-dir <dir> Output directory (default: processed)
    --help, -h        Show this help

Examples:
    # Process new images
    $0
    
    # Scan only (dry run)
    $0 --scan-only
    
    # Force reprocess all
    $0 --force
EOF
}

# Main
main() {
    parse_args "$@"
    
    if [[ ! -d "$DUMP_DIR" ]]; then
        log_error "Dump directory does not exist: $DUMP_DIR"
        exit 1
    fi
    
    run_workflow
}

main "$@"
