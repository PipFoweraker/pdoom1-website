#!/usr/bin/env python3
"""
Hybrid Image Processing Script for pdoom1-website Assets

Based on best practices from Sharp, Pillow, and Squoosh:
- Optimized web compression (WebP, AVIF, JPEG) with perceptual quality preservation
- Multiple aspect ratios for web (square, 16:9, 4:3, 3:4, original)
- Game-optimized outputs for pdoom1 pygame assets
- Smart metadata handling
- Batch processing with progress tracking

Usage:
    python process_image.py <input_file> [options]
    python process_image.py --batch <directory> [options]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageOps, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    print("[ERROR] Pillow not installed. Install with: uv pip install Pillow")
    PIL_AVAILABLE = False
    sys.exit(1)


class HybridImageProcessor:
    """
    Hybrid image processor combining best practices from Sharp, Pillow, and Squoosh.
    
    Web optimization focuses on:
    - Fast loading (small file sizes)
    - High visual quality (minimal perceptible loss)
    - Modern formats (WebP primary, AVIF fallback, JPEG legacy)
    - Progressive encoding for better perceived performance
    """
    
    # Web-optimized settings - balanced compression/quality
    # Based on Squoosh recommendations and Sharp defaults
    WEB_FORMATS = {
        'webp': {
            'quality': 85,  # Sweet spot: 85-90 provides excellent quality with ~70% size reduction
            'method': 6,     # Best compression (slower but worth it)
            'lossless': False,
        },
        'webp-lossless': {
            'quality': 100,
            'method': 6,
            'lossless': True,
        },
        'jpeg': {
            'quality': 85,     # High quality JPEG
            'progressive': True,  # Progressive JPEG for better perceived loading
            'optimize': True,     # Huffman optimization
            'subsampling': '4:4:4',  # No chroma subsampling for better quality
        },
        'jpeg-high': {
            'quality': 92,
            'progressive': True,
            'optimize': True,
            'subsampling': '4:4:4',
        },
        'png': {
            'optimize': True,
            'compress_level': 9,
        },
    }
    
    # Game-optimized settings - higher quality for pygame assets
    GAME_FORMATS = {
        'png': {
            'optimize': True,
            'compress_level': 9,
        },
        'webp': {
            'quality': 92,  # Higher quality for game assets
            'method': 6,
            'lossless': False,
        },
        'webp-lossless': {
            'quality': 100,
            'method': 6,
            'lossless': True,
        },
        'jpg': {
            'quality': 92,
            'progressive': False,  # Not needed for game assets
            'optimize': True,
        },
    }
    
    # Aspect ratios for web - multiple options
    ASPECT_RATIOS = {
        'square': (1, 1),       # 1:1 - Social media, thumbnails, grids
        'wide': (16, 9),        # 16:9 - Hero sections, banners, video thumbnails
        'standard': (4, 3),     # 4:3 - Traditional displays, photos
        'portrait': (3, 4),     # 3:4 - Portrait photos, mobile
        'ultrawide': (21, 9),   # 21:9 - Ultra-wide displays
        'original': None,       # Preserve original aspect ratio
    }
    
    # Web sizes - optimized for different use cases
    MAX_DIMENSIONS = {
        # Web sizes - multiple aspect ratios
        'web-thumbnail': (200, 200),
        'web-small': (800, 800),
        'web-medium': (1200, 1200),
        'web-large': (1920, 1920),
        'web-hero': (2560, 1440),  # Hero images
        
        # Game sizes - pygame optimized
        'game-small': (256, 256),      # UI icons, small sprites
        'game-medium': (512, 512),     # Standard game assets
        'game-large': (1024, 1024),    # High-res game assets
        'game-xlarge': (2048, 2048),  # UI backgrounds, large sprites
        'game-ui': (2048, 2048),      # UI elements
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize processor with optional config file."""
        self.config = self._load_config(config_path)
        self.avif_available = self._check_avif_support()
        
    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration from JSON file."""
        default_config = {
            'strip_gps': True,
            'strip_personal': True,
            'preserve_copyright': True,
            'add_metadata': {
                'copyright': 'pdoom1.com',
                'artist': 'pdoom1',
                'software': 'pdoom1-hybrid-processor',
            },
            'web_formats': self.WEB_FORMATS,
            'game_formats': self.GAME_FORMATS,
            'web_aspect_ratios': ['square', 'wide', 'standard', 'portrait', 'original'],
            'web_formats_list': ['webp', 'jpeg'],  # Primary formats for web
        }
        
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"[WARN] Failed to load config: {e}")
        
        return default_config
    
    def _check_avif_support(self) -> bool:
        """Check if AVIF encoding is available (requires pillow-avif-plugin)."""
        try:
            from PIL import features
            return features.check('libavif')
        except:
            return False
    
    def strip_metadata(self, input_path: Path, output_path: Path) -> List[str]:
        """
        Strip personal metadata (GPS, personal data) using exiftool.
        
        Returns list of stripped metadata tags.
        """
        stripped = []
        
        if not self.config.get('strip_gps', True) and not self.config.get('strip_personal', True):
            return stripped
        
        try:
            cmd = ['exiftool']
            
            if self.config.get('strip_gps', True):
                cmd.extend(['-gps:all=', '-xmp:GPSLatitude=', '-xmp:GPSLongitude='])
                stripped.extend(['GPS:all', 'XMP:GPSLatitude', 'XMP:GPSLongitude'])
            
            if self.config.get('strip_personal', True):
                cmd.extend([
                    '-exif:Artist=',
                    '-exif:Copyright=',
                    '-exif:UserComment=',
                    '-xmp:Creator=',
                    '-xmp:CreatorTool=',
                    '-xmp:History=',
                    '-iptc:By-line=',
                    '-iptc:CopyrightNotice=',
                ])
                stripped.extend([
                    'EXIF:Artist', 'EXIF:Copyright', 'EXIF:UserComment',
                    'XMP:Creator', 'XMP:CreatorTool', 'XMP:History',
                    'IPTC:By-line', 'IPTC:CopyrightNotice'
                ])
            
            if self.config.get('preserve_copyright', True):
                if 'copyright' in self.config.get('add_metadata', {}):
                    cmd.extend(['-exif:Copyright=' + self.config['add_metadata']['copyright']])
            
            cmd.extend(['-overwrite_original', str(input_path)])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                print(f"[INFO] Stripped metadata: {', '.join(stripped)}")
            else:
                print(f"[WARN] exiftool warning: {result.stderr}")
                
        except FileNotFoundError:
            print("[WARN] exiftool not found. Skipping metadata stripping.")
        except Exception as e:
            print(f"[WARN] Metadata stripping failed: {e}")
        
        return stripped
    
    def add_metadata(self, image_path: Path, metadata: Dict[str, str]):
        """Add metadata to image using exiftool."""
        try:
            cmd = ['exiftool']
            
            tag_map = {
                'copyright': '-exif:Copyright=',
                'artist': '-exif:Artist=',
                'software': '-exif:Software=',
                'description': '-exif:ImageDescription=',
            }
            
            for key, value in metadata.items():
                if key in tag_map:
                    cmd.append(tag_map[key] + value)
            
            cmd.extend(['-overwrite_original', str(image_path)])
            subprocess.run(cmd, capture_output=True, check=False)
            
        except FileNotFoundError:
            print("[WARN] exiftool not found. Skipping metadata addition.")
        except Exception as e:
            print(f"[WARN] Metadata addition failed: {e}")
    
    def normalize_aspect_ratio(self, image: Image.Image, target_ratio: Optional[Tuple[int, int]], 
                              method: str = 'crop') -> Image.Image:
        """
        Normalize image to target aspect ratio.
        
        Args:
            image: PIL Image object
            target_ratio: (width, height) tuple or None for original
            method: 'crop' (center crop) or 'pad' (add padding)
        
        Returns:
            Normalized PIL Image
        """
        if target_ratio is None:
            return image  # Preserve original
        
        target_w, target_h = target_ratio
        target_aspect = target_w / target_h
        
        img_w, img_h = image.size
        img_aspect = img_w / img_h
        
        if abs(img_aspect - target_aspect) < 0.01:
            return image  # Already correct aspect ratio
        
        if method == 'crop':
            # Center crop to target aspect ratio (smart crop preserves important content)
            if img_aspect > target_aspect:
                # Image is wider, crop height
                new_h = img_h
                new_w = int(new_h * target_aspect)
                left = (img_w - new_w) // 2
                image = image.crop((left, 0, left + new_w, new_h))
            else:
                # Image is taller, crop width
                new_w = img_w
                new_h = int(new_w / target_aspect)
                top = (img_h - new_h) // 2
                image = image.crop((0, top, new_w, top + new_h))
        
        elif method == 'pad':
            # Add padding to match aspect ratio (white background)
            if img_aspect > target_aspect:
                # Image is wider, pad height
                new_h = int(img_w / target_aspect)
                pad_top = (new_h - img_h) // 2
                pad_bottom = new_h - img_h - pad_top
                image = ImageOps.expand(image, border=(0, pad_top, 0, pad_bottom), fill='white')
            else:
                # Image is taller, pad width
                new_w = int(img_h * target_aspect)
                pad_left = (new_w - img_w) // 2
                pad_right = new_w - img_w - pad_left
                image = ImageOps.expand(image, border=(pad_left, 0, pad_right, 0), fill='white')
        
        return image
    
    def resize_image(self, image: Image.Image, max_dimensions: Tuple[int, int], 
                     maintain_aspect: bool = True) -> Image.Image:
        """
        Resize image to fit within max dimensions using high-quality resampling.
        
        Uses LANCZOS resampling for best quality (recommended by Sharp and Pillow docs).
        """
        max_w, max_h = max_dimensions
        img_w, img_h = image.size
        
        if img_w <= max_w and img_h <= max_h:
            return image  # Already within limits
        
        if maintain_aspect:
            scale = min(max_w / img_w, max_h / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
        else:
            new_w, new_h = max_w, max_h
        
        # Use LANCZOS for best quality (what Sharp uses internally)
        return image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    def optimize_for_web(self, image: Image.Image, format_type: str, output_path: Path):
        """
        Optimize image for web with perceptual quality preservation.
        
        Uses best practices from Squoosh, Sharp, and modern web optimization.
        """
        settings = self.WEB_FORMATS.get(format_type, {})
        
        if format_type == 'webp':
            quality = settings.get('quality', 85)
            method = settings.get('method', 6)
            lossless = settings.get('lossless', False)
            
            if lossless:
                image.save(output_path, 'WEBP', method=method, lossless=True)
            else:
                image.save(output_path, 'WEBP', quality=quality, method=method)
        
        elif format_type == 'jpeg' or format_type == 'jpg':
            quality = settings.get('quality', 85)
            progressive = settings.get('progressive', True)
            optimize = settings.get('optimize', True)
            
            # Convert RGBA to RGB for JPEG
            if image.mode == 'RGBA':
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[3])
                image = rgb_image
            elif image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            # Save with optimization
            save_kwargs = {
                'format': 'JPEG',
                'quality': quality,
                'optimize': optimize,
            }
            
            if progressive:
                save_kwargs['progressive'] = True
            
            image.save(output_path, **save_kwargs)
        
        elif format_type == 'png':
            optimize = settings.get('optimize', True)
            compress_level = settings.get('compress_level', 9)
            image.save(output_path, 'PNG', optimize=optimize, compress_level=compress_level)
        
        else:
            raise ValueError(f"Unknown web format: {format_type}")
    
    def optimize_for_game(self, image: Image.Image, format_type: str, output_path: Path):
        """Optimize image for pygame game assets (higher quality)."""
        settings = self.GAME_FORMATS.get(format_type, {})
        
        if format_type == 'png':
            optimize = settings.get('optimize', True)
            compress_level = settings.get('compress_level', 9)
            image.save(output_path, 'PNG', optimize=optimize, compress_level=compress_level)
        
        elif format_type == 'webp':
            quality = settings.get('quality', 92)
            method = settings.get('method', 6)
            lossless = settings.get('lossless', False)
            
            if lossless:
                image.save(output_path, 'WEBP', method=method, lossless=True)
            else:
                image.save(output_path, 'WEBP', quality=quality, method=method)
        
        elif format_type == 'jpg' or format_type == 'jpeg':
            quality = settings.get('quality', 92)
            optimize = settings.get('optimize', True)
            
            # Convert RGBA to RGB for JPEG
            if image.mode == 'RGBA':
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[3])
                image = rgb_image
            elif image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            image.save(output_path, 'JPEG', quality=quality, optimize=optimize)
        
        else:
            raise ValueError(f"Unknown game format: {format_type}")
    
    def process_image(self, input_path: Path, output_dir: Path, 
                     formats: List[str] = None, sizes: List[str] = None,
                     aspect_ratios: List[str] = None,
                     target: str = 'web') -> Dict[str, Path]:
        """
        Process a single image file with multiple aspect ratios and formats.
        
        Args:
            input_path: Input image file
            output_dir: Output directory
            formats: List of output formats
            sizes: List of size presets
            aspect_ratios: List of aspect ratios to generate (None = original only)
            target: 'web' or 'game'
        
        Returns:
            Dict mapping format_size_aspect to output path
        """
        if formats is None:
            formats = ['webp', 'jpeg'] if target == 'web' else ['png', 'webp']
        
        if sizes is None:
            sizes = ['web-medium'] if target == 'web' else ['game-medium']
        
        if aspect_ratios is None:
            aspect_ratios = ['original']
        
        # Load image
        try:
            image = Image.open(input_path)
            image = ImageOps.exif_transpose(image)  # Auto-rotate based on EXIF
        except Exception as e:
            print(f"[ERROR] Failed to open image {input_path}: {e}")
            return {}
        
        # Strip metadata from original
        temp_path = output_dir / f"temp_{input_path.name}"
        image.save(temp_path, quality=95)
        self.strip_metadata(temp_path, temp_path)
        
        # Add configured metadata
        if self.config.get('add_metadata'):
            self.add_metadata(temp_path, self.config['add_metadata'])
        
        # Reload to get clean image
        image = Image.open(temp_path)
        
        # Generate outputs
        outputs = {}
        base_name = input_path.stem
        
        for aspect_key in aspect_ratios:
            # Normalize aspect ratio
            target_ratio = None
            if aspect_key != 'original':
                target_ratio = self.ASPECT_RATIOS.get(aspect_key)
                if target_ratio is None:
                    print(f"[WARN] Unknown aspect ratio: {aspect_key}, skipping")
                    continue
            
            normalized_image = self.normalize_aspect_ratio(image, target_ratio, method='crop')
            
            for size_key in sizes:
                if size_key not in self.MAX_DIMENSIONS:
                    print(f"[WARN] Unknown size: {size_key}, skipping")
                    continue
                
                max_dims = self.MAX_DIMENSIONS[size_key]
                resized = self.resize_image(normalized_image, max_dims)
                
                for fmt in formats:
                    # Generate filename with aspect ratio suffix
                    aspect_suffix = f"_{aspect_key}" if aspect_key != 'original' else ""
                    output_filename = f"{base_name}_{size_key}{aspect_suffix}.{fmt}"
                    output_path = output_dir / output_filename
                    
                    try:
                        if target == 'web':
                            self.optimize_for_web(resized, fmt, output_path)
                        else:
                            self.optimize_for_game(resized, fmt, output_path)
                        
                        # Create key for output dict
                        key = f"{fmt}_{size_key}_{aspect_key}"
                        outputs[key] = output_path
                        
                        file_size_kb = output_path.stat().st_size / 1024
                        print(f"[OK] Created: {output_filename} ({resized.size[0]}x{resized.size[1]}, {file_size_kb:.1f}KB)")
                        
                    except Exception as e:
                        print(f"[ERROR] Failed to save {output_filename}: {e}")
                        continue
        
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
        
        return outputs


def main():
    parser = argparse.ArgumentParser(
        description='Hybrid image processor for web and game assets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single image with multiple aspect ratios
  python process_image.py cat.jpg --formats webp jpeg --sizes web-medium web-large --aspect-ratios square wide original
  
  # Process for game
  python process_image.py cat.jpg --target game --formats png webp --sizes game-medium game-large
  
  # Batch process directory
  python process_image.py --batch ./dump --formats webp --sizes web-medium
        """
    )
    
    parser.add_argument('input', nargs='?', type=Path, help='Input image file')
    parser.add_argument('--batch', type=Path, help='Process all images in directory')
    parser.add_argument('--output-dir', type=Path, default=Path('processed'),
                       help='Output directory (default: processed)')
    parser.add_argument('--formats', nargs='+', default=None,
                       choices=['webp', 'jpeg', 'jpg', 'png'],
                       help='Output formats (default: webp,jpeg for web, png,webp for game)')
    parser.add_argument('--sizes', nargs='+', default=None,
                       choices=['web-thumbnail', 'web-small', 'web-medium', 'web-large', 'web-hero',
                                'game-small', 'game-medium', 'game-large', 'game-xlarge', 'game-ui'],
                       help='Output sizes')
    parser.add_argument('--aspect-ratios', nargs='+',
                       default=['original'],
                       choices=['square', 'wide', 'standard', 'portrait', 'ultrawide', 'original'],
                       help='Aspect ratios to generate (default: original)')
    parser.add_argument('--target', choices=['web', 'game'], default='web',
                       help='Target platform (default: web)')
    parser.add_argument('--config', type=Path, help='Configuration JSON file')
    
    args = parser.parse_args()
    
    if not args.batch and not args.input:
        parser.error("Must provide either input file or --batch directory")
    
    if args.batch and not args.batch.exists():
        print(f"[ERROR] Batch directory does not exist: {args.batch}")
        sys.exit(1)
    
    if args.input and not args.input.exists():
        print(f"[ERROR] Input file does not exist: {args.input}")
        sys.exit(1)
    
    # Create output directory
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize processor
    processor = HybridImageProcessor(args.config)
    
    # Process images
    if args.batch:
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff'}
        image_files = [f for f in args.batch.iterdir() 
                      if f.is_file() and f.suffix.lower() in image_extensions]
        
        if not image_files:
            print(f"[WARN] No image files found in {args.batch}")
            sys.exit(0)
        
        print(f"[INFO] Processing {len(image_files)} images...")
        for img_path in image_files:
            print(f"\n[INFO] Processing: {img_path.name}")
            processor.process_image(
                img_path,
                output_dir,
                formats=args.formats,
                sizes=args.sizes,
                aspect_ratios=args.aspect_ratios,
                target=args.target
            )
    else:
        processor.process_image(
            args.input,
            output_dir,
            formats=args.formats,
            sizes=args.sizes,
            aspect_ratios=args.aspect_ratios,
            target=args.target
        )
    
    print(f"\n[OK] Processing complete. Outputs in: {output_dir}")


if __name__ == '__main__':
    main()
