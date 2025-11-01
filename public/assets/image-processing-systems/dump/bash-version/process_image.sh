#!/bin/bash
# Image Processing Script for pdoom1-website Assets (Bash Implementation)
#
# Processes images for web and game use with:
# - Metadata stripping (GPS, personal data)
# - Format conversion (WebP, optimized PNG/JPEG)
# - Aspect ratio normalization
# - Quality optimization for web and game use
# - Multiple output formats and sizes
#
# Usage:
#     ./process_image.sh <input_file> [options]
#     ./process_image.sh --batch <directory> [options]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/processed"
CONFIG_FILE="${SCRIPT_DIR}/config.sh"
BATCH_MODE=false
INPUT_FILE=""
FORMATS=("webp")
SIZES=("web-medium")
ASPECT_RATIO=""
NO_STRIP_METADATA=false

# Size presets (width x height)
declare -A MAX_DIMENSIONS=(
    ["web-thumbnail"]="200x200"
    ["web-small"]="800x800"
    ["web-medium"]="1200x1200"
    ["web-large"]="1920x1920"
    ["game-small"]="256x256"
    ["game-medium"]="512x512"
    ["game-large"]="1024x1024"
    ["game-ui"]="2048x2048"
)

# Aspect ratios (width:height)
declare -A ASPECT_RATIOS=(
    ["square"]="1:1"
    ["wide"]="16:9"
    ["standard"]="4:3"
    ["portrait"]="3:4"
    ["game-ui"]="16:10"
)

# Load configuration if exists
if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
fi

# Default metadata settings
STRIP_GPS="${STRIP_GPS:-true}"
STRIP_PERSONAL="${STRIP_PERSONAL:-true}"
COPYRIGHT="${COPYRIGHT:-pdoom1.com}"
ARTIST="${ARTIST:-pdoom1}"
SOFTWARE="${SOFTWARE:-pdoom1-image-processor-bash}"

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

# Check dependencies
check_dependencies() {
    local missing=()
    
    command -v convert >/dev/null 2>&1 || missing+=("ImageMagick (convert)")
    command -v identify >/dev/null 2>&1 || missing+=("ImageMagick (identify)")
    command -v exiftool >/dev/null 2>&1 || missing+=("exiftool")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing dependencies:"
        for dep in "${missing[@]}"; do
            log_error "  - $dep"
        done
        log_error ""
        log_error "Install with:"
        log_error "  sudo apt install imagemagick libimage-exiftool-perl"
        exit 1
    fi
}

# Strip metadata from image
strip_metadata() {
    local input_file="$1"
    
    if [[ "$NO_STRIP_METADATA" == "true" ]]; then
        return 0
    fi
    
    log_info "Stripping metadata from: $(basename "$input_file")"
    
    local stripped_tags=()
    
    if [[ "$STRIP_GPS" == "true" ]]; then
        exiftool -q -gps:all= -xmp:GPSLatitude= -xmp:GPSLongitude= "$input_file" 2>/dev/null || true
        stripped_tags+=("GPS")
    fi
    
    if [[ "$STRIP_PERSONAL" == "true" ]]; then
        exiftool -q \
            -exif:Artist= \
            -exif:Copyright= \
            -exif:UserComment= \
            -xmp:Creator= \
            -xmp:CreatorTool= \
            -xmp:History= \
            -iptc:By-line= \
            -iptc:CopyrightNotice= \
            "$input_file" 2>/dev/null || true
        stripped_tags+=("Personal")
    fi
    
    # Add new metadata
    exiftool -q -overwrite_original \
        -exif:Copyright="$COPYRIGHT" \
        -exif:Artist="$ARTIST" \
        -exif:Software="$SOFTWARE" \
        "$input_file" 2>/dev/null || true
    
    if [[ ${#stripped_tags[@]} -gt 0 ]]; then
        log_info "Stripped metadata: ${stripped_tags[*]}"
    fi
}

# Normalize aspect ratio
normalize_aspect_ratio() {
    local input_file="$1"
    local output_file="$2"
    local ratio="$3"
    local method="${4:-crop}"
    
    # If ratio is empty, preserve original
    if [[ -z "$ratio" ]]; then
        cp "$input_file" "$output_file"
        return 0
    fi
    
    local width height
    IFS=':' read -r width height <<< "$ratio"
    
    local current_dims
    current_dims=$(identify -format "%wx%h" "$input_file")
    local current_w current_h
    IFS='x' read -r current_w current_h <<< "$current_dims"
    
    local target_aspect
    target_aspect=$(echo "scale=10; $width / $height" | bc)
    local current_aspect
    current_aspect=$(echo "scale=10; $current_w / $current_h" | bc)
    
    # Check if already correct aspect ratio (within 1% tolerance)
    local diff
    diff=$(echo "scale=10; $target_aspect - $current_aspect" | bc | sed 's/^-//')
    if (( $(echo "$diff < 0.01" | bc -l) )); then
        cp "$input_file" "$output_file"
        return 0
    fi
    
    if [[ "$method" == "crop" ]]; then
        # Center crop to target aspect ratio
        if (( $(echo "$current_aspect > $target_aspect" | bc -l) )); then
            # Image is wider, crop height
            local new_h=$current_h
            local new_w
            new_w=$(echo "scale=0; $new_h * $target_aspect / 1" | bc)
            local left
            left=$(( (current_w - new_w) / 2 ))
            convert "$input_file" -crop "${new_w}x${new_h}+${left}+0" "$output_file"
        else
            # Image is taller, crop width
            local new_w=$current_w
            local new_h
            new_h=$(echo "scale=0; $new_w / $target_aspect / 1" | bc)
            local top
            top=$(( (current_h - new_h) / 2 ))
            convert "$input_file" -crop "${new_w}x${new_h}+0+${top}" "$output_file"
        fi
    else
        # Pad to match aspect ratio
        if (( $(echo "$current_aspect > $target_aspect" | bc -l) )); then
            # Image is wider, pad height
            local new_h
            new_h=$(echo "scale=0; $current_w / $target_aspect / 1" | bc)
            local pad_top pad_bottom
            pad_top=$(( (new_h - current_h) / 2 ))
            pad_bottom=$(( new_h - current_h - pad_top ))
            convert "$input_file" -gravity center -background white \
                -extent "${current_w}x${new_h}" "$output_file"
        else
            # Image is taller, pad width
            local new_w
            new_w=$(echo "scale=0; $current_h * $target_aspect / 1" | bc)
            local pad_left pad_right
            pad_left=$(( (new_w - current_w) / 2 ))
            pad_right=$(( new_w - current_w - pad_left ))
            convert "$input_file" -gravity center -background white \
                -extent "${new_w}x${current_h}" "$output_file"
        fi
    fi
}

# Resize image to fit within max dimensions
resize_image() {
    local input_file="$1"
    local output_file="$2"
    local max_dims="$3"
    
    local max_w max_h
    IFS='x' read -r max_w max_h <<< "$max_dims"
    
    convert "$input_file" -resize "${max_w}x${max_h}>" "$output_file"
}

# Process image in specific format
process_format() {
    local input_file="$1"
    local output_file="$2"
    local format="$3"
    local size_key="$4"
    
    local max_dims="${MAX_DIMENSIONS[$size_key]}"
    
    # Resize first
    local temp_resized
    temp_resized=$(mktemp --suffix=".tmp")
    resize_image "$input_file" "$temp_resized" "$max_dims"
    
    case "$format" in
        webp)
            # WebP with quality 85
            convert "$temp_resized" -quality 85 -define webp:method=6 "$output_file"
            ;;
        png)
            # PNG with optimization
            convert "$temp_resized" -strip -quality 92 "$output_file"
            optipng -quiet -o2 "$output_file" 2>/dev/null || true
            ;;
        jpg|jpeg)
            # JPEG with quality 90
            # Convert RGBA to RGB if needed
            local temp_rgb
            temp_rgb=$(mktemp --suffix=".jpg")
            convert "$temp_resized" -alpha off -background white \
                -quality 90 -strip "$temp_rgb"
            mv "$temp_rgb" "$output_file"
            ;;
        *)
            log_warn "Unknown format: $format"
            rm -f "$temp_resized"
            return 1
            ;;
    esac
    
    rm -f "$temp_resized"
    
    local dims
    dims=$(identify -format "%wx%h" "$output_file")
    log_ok "Created: $(basename "$output_file") ($dims)"
}

# Process single image
process_single_image() {
    local input_file="$1"
    local base_name
    base_name=$(basename "$input_file" | sed 's/\.[^.]*$//')
    
    log_info "Processing: $(basename "$input_file")"
    
    # Create temp file for processing
    local temp_file
    temp_file=$(mktemp --suffix=".$(basename "$input_file" | sed 's/.*\.//')")
    cp "$input_file" "$temp_file"
    
    # Strip metadata
    strip_metadata "$temp_file"
    
    # Normalize aspect ratio if specified
    local processed_file="$temp_file"
    if [[ -n "$ASPECT_RATIO" && -n "${ASPECT_RATIOS[$ASPECT_RATIO]:-}" ]]; then
        local ratio="${ASPECT_RATIOS[$ASPECT_RATIO]}"
        local temp_normalized
        temp_normalized=$(mktemp --suffix=".png")
        normalize_aspect_ratio "$temp_file" "$temp_normalized" "$ratio"
        processed_file="$temp_normalized"
        rm -f "$temp_file"
    fi
    
    # Process each format and size combination
    for format in "${FORMATS[@]}"; do
        for size_key in "${SIZES[@]}"; do
            if [[ -z "${MAX_DIMENSIONS[$size_key]:-}" ]]; then
                log_warn "Unknown size: $size_key, skipping"
                continue
            fi
            
            local output_file
            output_file="${OUTPUT_DIR}/${base_name}_${size_key}.${format}"
            
            process_format "$processed_file" "$output_file" "$format" "$size_key"
        done
    done
    
    # Cleanup
    rm -f "$temp_file" "$processed_file"
}

# Batch process directory
process_batch() {
    local batch_dir="$1"
    
    log_info "Scanning directory: $batch_dir"
    
    local image_files=()
    while IFS= read -r -d '' file; do
        image_files+=("$file")
    done < <(find "$batch_dir" -maxdepth 1 -type f \
        \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \
        -o -iname "*.webp" -o -iname "*.gif" -o -iname "*.bmp" \
        -o -iname "*.tiff" \) -print0)
    
    if [[ ${#image_files[@]} -eq 0 ]]; then
        log_warn "No image files found in $batch_dir"
        return 0
    fi
    
    log_info "Found ${#image_files[@]} images to process"
    
    for img_file in "${image_files[@]}"; do
        process_single_image "$img_file"
    done
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --batch)
                BATCH_MODE=true
                INPUT_FILE="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --formats)
                shift
                FORMATS=()
                while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                    FORMATS+=("$1")
                    shift
                done
                ;;
            --sizes)
                shift
                SIZES=()
                while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                    SIZES+=("$1")
                    shift
                done
                ;;
            --aspect-ratio)
                ASPECT_RATIO="$2"
                shift 2
                ;;
            --config)
                CONFIG_FILE="$2"
                if [[ -f "$CONFIG_FILE" ]]; then
                    source "$CONFIG_FILE"
                fi
                shift 2
                ;;
            --no-strip-metadata)
                NO_STRIP_METADATA=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                if [[ -z "$INPUT_FILE" && "$BATCH_MODE" != "true" ]]; then
                    INPUT_FILE="$1"
                else
                    log_error "Unknown option: $1"
                    show_help
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    if [[ "$BATCH_MODE" != "true" && -z "$INPUT_FILE" ]]; then
        log_error "Must provide input file or --batch directory"
        show_help
        exit 1
    fi
}

show_help() {
    cat << EOF
Usage: $0 <input_file> [options]
       $0 --batch <directory> [options]

Options:
    --batch <dir>         Process all images in directory
    --output-dir <dir>    Output directory (default: processed)
    --formats <fmt>...    Output formats: webp, png, jpg (default: webp)
    --sizes <size>...     Output sizes: web-thumbnail, web-small, web-medium,
                          web-large, game-small, game-medium, game-large,
                          game-ui (default: web-medium)
    --aspect-ratio <ratio> Normalize to: square, wide, standard, portrait, original, game-ui
    --config <file>       Configuration file (default: config.sh)
    --no-strip-metadata   Skip metadata stripping
    --help, -h            Show this help

Examples:
    # Process single image
    $0 cat.jpg --formats webp png --sizes web-medium web-large
    
    # Process with aspect ratio
    $0 cat.jpg --aspect-ratio square --sizes web-small
    
    # Batch process directory
    $0 --batch ./dump --formats webp --sizes web-medium
EOF
}

# Main
main() {
    check_dependencies
    
    parse_args "$@"
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Process images
    if [[ "$BATCH_MODE" == "true" ]]; then
        if [[ ! -d "$INPUT_FILE" ]]; then
            log_error "Batch directory does not exist: $INPUT_FILE"
            exit 1
        fi
        process_batch "$INPUT_FILE"
    else
        if [[ ! -f "$INPUT_FILE" ]]; then
            log_error "Input file does not exist: $INPUT_FILE"
            exit 1
        fi
        process_single_image "$INPUT_FILE"
    fi
    
    log_ok "Processing complete. Outputs in: $OUTPUT_DIR"
}

main "$@"
