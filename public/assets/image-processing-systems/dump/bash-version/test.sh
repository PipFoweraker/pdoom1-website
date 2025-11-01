#!/bin/bash
# Quick test script for bash image processing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[INFO] Testing bash image processing workflow..."

# Check if we have test images
if [[ -f "../pdoom1-office-cat-default.png" ]]; then
    echo "[INFO] Found test image: pdoom1-office-cat-default.png"
    
    # Copy to dump for testing
    mkdir -p .
    cp "../pdoom1-office-cat-default.png" "./test-cat.png"
    
    echo "[INFO] Testing workflow scan..."
    ./workflow.sh --scan-only
    
    echo "[INFO] Test complete!"
else
    echo "[WARN] No test images found. Place images in dump-bash/ to test."
fi
