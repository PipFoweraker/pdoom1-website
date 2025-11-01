# Image Processing Implementations

This directory contains 3 different implementations of the cat image processing system for the pdoom1 website and game.

## 📁 Implementations

### 1. python-original/
**Original Python Implementation**
- Basic metadata stripping and optimization
- Web and game format support (WebP, PNG, JPEG)
- Simple configuration via `config.json`
- Good for straightforward batch processing

**Files:**
- `process_image.py` - Core image processor
- `workflow.py` - Batch processing automation
- `config.json` - Configuration settings
- `README.md` - Full documentation

### 2. bash-version/
**Bash Shell Implementation**
- No Python dependencies required
- Uses ImageMagick and exiftool directly
- Fast for simple operations
- Good for shell scripts and automation

**Files:**
- `process_image.sh` - Core image processor
- `workflow.sh` - Batch processing automation
- `config.sh` - Configuration settings
- `test.sh` - Testing script

### 3. python-hybrid/
**Enhanced Python Implementation** ⭐ RECOMMENDED
- **5 aspect ratios:** square, wide, standard, portrait, original
- Best practices from Sharp, Pillow, and Squoosh
- Optimized compression settings (85% web, 92% game)
- Generates ~80 files per image
- Most comprehensive feature set

**Files:**
- `process_image.py` - Enhanced image processor
- `workflow.py` - Advanced batch automation
- `config.json` - Comprehensive configuration
- `README.md` - Full documentation

## 🚀 Quick Start

### Python Hybrid (Recommended)
```bash
cd python-hybrid
python workflow.py
```

### Python Original
```bash
cd python-original
python workflow.py
```

### Bash Version
```bash
cd bash-version
./workflow.sh
```

## 📊 Feature Comparison

| Feature | Python Original | Bash Version | Python Hybrid |
|---------|----------------|--------------|---------------|
| Multiple formats | ✅ | ✅ | ✅ |
| Multiple sizes | ✅ | ✅ | ✅ |
| Multiple aspect ratios | ❌ | ❌ | ✅ (5 ratios) |
| Metadata stripping | ✅ | ✅ | ✅ |
| Web optimization | ✅ | ✅ | ✅ Enhanced |
| Game optimization | ✅ | ✅ | ✅ Enhanced |
| Dependencies | Python + Pillow | Bash + ImageMagick | Python + Pillow |
| Processing speed | Medium | Fast | Medium |
| Output files/image | ~16 | ~16 | ~80 |

## 🎯 Use Cases

**Use python-original when:**
- You need simple, straightforward processing
- You want minimal configuration
- Basic web and game optimization is sufficient

**Use bash-version when:**
- You need shell script integration
- You want to avoid Python dependencies
- You need fast, simple batch processing

**Use python-hybrid when:**
- You need multiple aspect ratios for responsive design
- You want the highest quality optimization
- You need comprehensive web and game support
- File size is less important than flexibility

## 📝 Notes

All implementations:
- Strip GPS and personal metadata
- Add copyright and attribution metadata
- Support batch processing with manifest tracking
- Create organized output directories
- Preserve originals in archive/

## 🔗 Related Documentation

- See individual README.md files in each implementation directory
- Check `public/assets/IMPLEMENTATION_COMPARISON.md` for detailed comparison
- View `public/assets/IMAGE_PROCESSING_CHANGELOG.md` for implementation history

## 📅 Last Updated

2025-11-01 - Organized all implementations into structured subdirectories
