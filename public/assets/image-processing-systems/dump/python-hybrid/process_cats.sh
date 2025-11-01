#!/bin/bash
# Process cat images with python-hybrid implementation

mkdir -p output/web output/game archive

for img in input/*.jpg; do
    if [ -f "$img" ]; then
        echo "Processing: $img"
        python3 process_image.py "$img" \
            --formats webp jpeg \
            --sizes web-thumbnail web-small web-medium web-large \
            --aspect-ratios square wide original \
            --target web \
            --output-dir output \
            --config config.json
        
        # Archive original
        mv "$img" archive/
    fi
done

echo "✓ Python-hybrid processing complete"
echo "Output: $(pwd)/output/"
ls -lh output/web/ | head -20
