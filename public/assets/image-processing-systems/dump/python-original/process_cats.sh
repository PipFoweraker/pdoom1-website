#!/bin/bash
# Process cat images with python-original implementation

mkdir -p output/web output/game archive

for img in input/*.jpg; do
    if [ -f "$img" ]; then
        echo "Processing: $img"
        python3 process_image.py "$img" \
            --formats webp png \
            --sizes web-thumbnail web-small web-medium \
            --output-dir output \
            --config config.json
        
        # Archive original
        mv "$img" archive/
    fi
done

echo "✓ Python-original processing complete"
echo "Output: $(pwd)/output/"
ls -lh output/web/ output/game/
