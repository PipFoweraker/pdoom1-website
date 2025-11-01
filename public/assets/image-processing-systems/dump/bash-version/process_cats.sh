#!/bin/bash
# Process cat images with bash-version implementation

mkdir -p output archive

echo "Processing with bash-version..."
./process_image.sh --batch input --output-dir output --formats webp png --sizes web-thumbnail web-small web-medium

# Archive originals
mv input/*.jpg archive/ 2>/dev/null

echo "✓ Bash-version processing complete"
echo "Output: $(pwd)/output/"
ls -lh output/
