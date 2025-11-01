# Image Asset Processing Automation

This directory contains automated scripts for processing cat images and other assets for the pdoom1 website and game.

## Overview

The image processing system automatically:
- **Strips personal metadata** (GPS coordinates, personal data)
- **Adds game/web metadata** (copyright, artist, software info)
- **Optimizes for web** (WebP format, multiple sizes, fast loading)
- **Optimizes for game** (PNG/WebP formats, various resolutions)
- **Normalizes aspect ratios** (square for web, preserve for game)
- **Tracks processed images** (manifest system prevents duplicates)

## Quick Start

### 1. Place images in dump folder

```bash
# Copy new cat images to the dump folder
cp /path/to/new/cat/*.jpg public/assets/dump/
cp /path/to/new/cat/*.png public/assets/dump/
```

### 2. Run the workflow

```bash
cd public/assets/dump
python workflow.py
```

This will:
- Scan for new images
- Process them automatically
- Create optimized outputs in `processed/web/` and `processed/game/`
- Archive originals in `dump/archive/`

### 3. Check results

```bash
# View processed images
ls -lh processed/web/
ls -lh processed/game/

# View manifest
cat manifest.json
```

## Directory Structure

```
dump/
??? config.json              # Processing configuration
??? process_image.py         # Core image processor
??? workflow.py              # Batch workflow automation
??? manifest.json            # Processing history (auto-generated)
??? archive/                 # Original images (backed up)
??? processed/               # Output directory
    ??? web/                 # Web-optimized images
    ?   ??? image_web-thumbnail.webp
    ?   ??? image_web-small.webp
    ?   ??? image_web-medium.webp
    ?   ??? image_web-large.webp
    ??? game/                # Game-optimized images
        ??? image_game-small.png
        ??? image_game-small.webp
        ??? image_game-medium.png
        ??? image_game-medium.webp
        ??? image_game-large.png
        ??? image_game-large.webp
```

## Scripts

### `process_image.py`

Core image processing script with full control over formats, sizes, and aspect ratios.

**Basic usage:**
```bash
# Process single image
python process_image.py cat.jpg --formats webp png --sizes web-medium web-large

# Process with aspect ratio normalization
python process_image.py cat.jpg --aspect-ratio square --sizes web-small

# Batch process directory
python process_image.py --batch ./dump --formats webp --sizes web-medium
```

**Options:**
- `--formats`: Output formats (`webp`, `png`, `jpg`)
- `--sizes`: Output sizes (see size presets below)
- `--aspect-ratio`: Normalize to aspect ratio (`square`, `wide`, `standard`, `portrait`, `game-ui`)
- `--config`: Custom configuration file
- `--no-strip-metadata`: Skip metadata stripping
- `--output-dir`: Output directory (default: `processed`)

### `workflow.py`

Automated batch workflow for processing cat images with sensible defaults.

**Usage:**
```bash
# Process new images
python workflow.py

# Scan only (dry run)
python workflow.py --scan-only

# Force reprocess all
python workflow.py --force
```

**Options:**
- `--dump-dir`: Directory with raw images (default: `dump`)
- `--output-dir`: Output directory (default: `processed`)
- `--scan-only`: Only scan, don't process
- `--force`: Reprocess all images

## Size Presets

### Web Sizes
- **web-thumbnail**: 200?200px - Thumbnails, previews
- **web-small**: 800?800px - Mobile, small displays
- **web-medium**: 1200?1200px - Standard web display (default)
- **web-large**: 1920?1920px - High-DPI displays, hero images

### Game Sizes
- **game-small**: 256?256px - UI icons, small sprites
- **game-medium**: 512?512px - Standard game assets
- **game-large**: 1024?1024px - High-res game assets
- **game-ui**: 2048?2048px - UI elements, backgrounds

## Format Optimization

### Web Formats

**WebP** (recommended):
- Quality: 85 (balanced), 90 (high), 75 (low)
- Method: 6 (best compression)
- ~70% smaller than PNG
- Wide browser support

**PNG**:
- Lossless compression
- Good for images with transparency
- Larger file sizes

**JPEG**:
- Lossy compression
- Good for photos without transparency
- Smaller than PNG

### Game Formats

**PNG**:
- Lossless, preserves quality
- Transparency support
- Larger files

**WebP**:
- Quality: 92 (higher than web)
- Good compression with quality
- Supports transparency

**JPEG**:
- Quality: 90
- Smaller files
- No transparency

## Aspect Ratios

The processor supports normalizing images to common aspect ratios:

- **square** (1:1) - Web thumbnails, social media
- **wide** (16:9) - Banner images, hero sections
- **standard** (4:3) - Standard display
- **portrait** (3:4) - Portrait orientation
- **game-ui** (16:10) - Game UI elements

**Methods:**
- **crop**: Center crop to target ratio (default)
- **pad**: Add padding to match ratio

## Metadata Handling

### Stripped Metadata

The processor automatically removes:
- GPS coordinates (latitude, longitude)
- Personal data (artist, creator, user comments)
- Camera settings (some EXIF data)
- XMP metadata (creator tool, history)

### Added Metadata

The processor adds:
- Copyright: `pdoom1.com`
- Artist: `pdoom1`
- Software: `pdoom1-image-processor`
- Description: `Processed cat image for pdoom1 game and website`

You can customize these in `config.json`.

## Configuration

Edit `config.json` to customize:

```json
{
  "strip_gps": true,
  "strip_personal": true,
  "preserve_copyright": true,
  "add_metadata": {
    "copyright": "pdoom1.com",
    "artist": "pdoom1",
    "software": "pdoom1-image-processor"
  },
  "web_formats": {
    "webp": {
      "quality": 85,
      "method": 6
    }
  },
  "game_formats": {
    "png": {
      "optimize": true,
      "compress_level": 9
    }
  }
}
```

## Workflow Integration

### NPM Scripts

Add to `package.json`:

```json
{
  "scripts": {
    "assets:process": "cd public/assets/dump && python workflow.py",
    "assets:scan": "cd public/assets/dump && python workflow.py --scan-only",
    "assets:force": "cd public/assets/dump && python workflow.py --force"
  }
}
```

Then run:
```bash
npm run assets:process
```

### Git Integration

Add to `.gitignore`:
```
public/assets/dump/archive/
public/assets/dump/manifest.json
public/assets/dump/processed/
```

This keeps processed outputs out of version control while preserving the dump folder and scripts.

## Best Practices

### For Web Use

1. **Use WebP format** - Best compression (~70% smaller than PNG)
2. **Multiple sizes** - Use responsive images (`srcset`)
3. **Square aspect ratio** - Consistent display across devices
4. **web-medium default** - Good balance of quality and size

### For Game Use

1. **PNG for transparency** - UI elements, sprites
2. **WebP for photos** - Good compression with quality
3. **Preserve aspect ratio** - Don't force square for game assets
4. **Multiple resolutions** - Support different display densities

### File Organization

```
public/assets/
??? images/              # Final web images (committed)
?   ??? cats/
?   ?   ??? cat1.webp
?   ?   ??? cat2.webp
??? dump/               # Processing workspace (gitignored)
    ??? archive/        # Originals (backed up)
    ??? processed/      # Outputs (before moving to images/)
```

## Troubleshooting

### exiftool not found

Install exiftool:
```bash
# Debian/Ubuntu
sudo apt install libimage-exiftool-perl

# macOS
brew install exiftool
```

### Pillow not installed

Install Pillow:
```bash
uv pip install Pillow
```

### Image processing fails

Check:
1. Image format is supported (JPG, PNG, WebP, GIF, BMP, TIFF)
2. File is not corrupted
3. Sufficient disk space
4. Write permissions on output directory

### Large file sizes

Adjust quality settings in `config.json`:
- Lower WebP quality (75 instead of 85)
- Use smaller size presets
- Consider JPEG for photos without transparency

## References

- [Web Image Optimization Best Practices](https://visualweb.com.au/how-to-optimise-images-for-the-web-best-practices/)
- [Game Image File Options](https://forum.choiceofgames.com/t/optimal-image-file-options-and-recommendations/143374)
- [WebP Format Guide](https://developers.google.com/speed/webp)
- [Pillow Documentation](https://pillow.readthedocs.io/)

## Future Enhancements

Potential improvements:
- [ ] Automatic responsive image generation (`srcset` attributes)
- [ ] Batch processing from URL sources
- [ ] Integration with CDN upload
- [ ] Automatic aspect ratio detection
- [ ] Image comparison/duplicate detection
- [ ] Support for animated GIFs
- [ ] Video thumbnail generation
- [ ] Automatic alt text generation

## License

Part of the pdoom1-website project.
