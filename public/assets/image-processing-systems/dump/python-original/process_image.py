#!/usr/bin/env python3
"""
Image Processing Script for pdoom1-website Assets

Processes images for web and game use with:
- Metadata stripping (GPS, personal data)
- Format conversion (WebP, optimized PNG/JPEG)
- Aspect ratio normalization
- Quality optimization for web and game use
- Multiple output formats and sizes

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
    from PIL import Image, ImageOps, ExifTags
    from PIL.ExifTags import TAGS
except ImportError:
    print("[ERROR] Pillow not installed. Install with: uv pip install Pillow")
    sys.exit(1)


class ImageProcessor:
    """Process images for web and game use."""
    
    # Web-optimized settings
    WEB_FORMATS = {
        'webp': {'quality': 85, 'method': 6},  # Balanced quality/size
        'webp-high': {'quality': 90, 'method': 6},  # Higher quality
        'webp-low': {'quality': 75, 'method': 6},  # Smaller files
    }
    
    # Game-optimized settings (higher quality for in-game assets)
    GAME_FORMATS = {
        'png': {'optimize': True, 'compress_level': 9},
        'webp': {'quality': 92, 'method': 6},
        'jpg': {'quality': 90, 'optimize': True},
    }
    
    # Target aspect ratios for different use cases
    ASPECT_RATIOS = {
        'square': (1, 1),      # 1:1 - Social media, thumbnails, grids
        'wide': (16, 9),       # 16:9 - Banner images, hero sections, video thumbnails
        'standard': (4, 3),    # 4:3 - Standard display, traditional photos
        'portrait': (3, 4),    # 3:4 - Portrait orientation, mobile
        'original': None,      # Preserve original aspect ratio
        'game-ui': (16, 10),   # 16:10 - Game UI elements
    }
    
    # Maximum dimensions for different use cases
    MAX_DIMENSIONS = {
        'web-thumbnail': (200, 200),
        'web-small': (800, 800),
        'web-medium': (1200, 1200),
        'web-large': (1920, 1920),
        'game-small': (256, 256),
        'game-medium': (512, 512),
        'game-large': (1024, 1024),
        'game-ui': (2048, 2048),
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize processor with optional config file."""
        self.config = self._load_config(config_path)
        self.stripped_metadata = []
        
    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration from JSON file."""
        default_config = {
            'strip_gps': True,
            'strip_personal': True,
            'preserve_copyright': True,
            'add_metadata': {
                'copyright': 'pdoom1.com',
                'artist': 'pdoom1',
                'software': 'pdoom1-image-processor'
            },
            'web_formats': self.WEB_FORMATS,
            'game_formats': self.GAME_FORMATS,
        }
        
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"[WARN] Failed to load config: {e}")
        
        return default_config
    
    def strip_metadata(self, input_path: Path, output_path: Path) -> List[str]:
        """
        Strip personal metadata (GPS, personal data) using exiftool.
        
        Returns list of stripped metadata tags.
        """
        stripped = []
        
        if not self.config.get('strip_gps', True) and not self.config.get('strip_personal', True):
            return stripped
        
        try:
            # Build exiftool command to strip metadata
            cmd = ['exiftool']
            
            # Strip GPS data
            if self.config.get('strip_gps', True):
                cmd.extend(['-gps:all=', '-xmp:GPSLatitude=', '-xmp:GPSLongitude='])
                stripped.extend(['GPS:all', 'XMP:GPSLatitude', 'XMP:GPSLongitude'])
            
            # Strip personal data
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
            
            # Preserve copyright if configured
            if self.config.get('preserve_copyright', True):
                if 'copyright' in self.config.get('add_metadata', {}):
                    cmd.extend(['-exif:Copyright=' + self.config['add_metadata']['copyright']])
            
            # Copy file and strip metadata
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
            
            for key, value in metadata.items():
                # Map common keys to exiftool tags
                tag_map = {
                    'copyright': '-exif:Copyright=',
                    'artist': '-exif:Artist=',
                    'software': '-exif:Software=',
                    'description': '-exif:ImageDescription=',
                }
                
                if key in tag_map:
                    cmd.append(tag_map[key] + value)
            
            cmd.extend(['-overwrite_original', str(image_path)])
            
            subprocess.run(cmd, capture_output=True, check=False)
            
        except FileNotFoundError:
            print("[WARN] exiftool not found. Skipping metadata addition.")
        except Exception as e:
            print(f"[WARN] Metadata addition failed: {e}")
    
    def normalize_aspect_ratio(self, image: Image.Image, target_ratio: Tuple[int, int], 
                                method: str = 'crop') -> Image.Image:
        """
        Normalize image to target aspect ratio.
        
        Args:
            image: PIL Image object
            target_ratio: (width, height) tuple
            method: 'crop' (center crop) or 'pad' (add padding)
        
        Returns:
            Normalized PIL Image
        """
        target_w, target_h = target_ratio
        target_aspect = target_w / target_h
        
        img_w, img_h = image.size
        img_aspect = img_w / img_h
        
        if abs(img_aspect - target_aspect) < 0.01:
            return image  # Already correct aspect ratio
        
        if method == 'crop':
            # Center crop to target aspect ratio
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
            # Add padding to match aspect ratio
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
        Resize image to fit within max dimensions.
        
        Args:
            image: PIL Image object
            max_dimensions: (max_width, max_height) tuple
            maintain_aspect: Maintain aspect ratio
        
        Returns:
            Resized PIL Image
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
        
        return image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    def process_image(self, input_path: Path, output_dir: Path, 
                     formats: List[str] = None, sizes: List[str] = None,
                     aspect_ratio: Optional[str] = None) -> Dict[str, Path]:
        """
        Process a single image file.
        
        Returns dict mapping format_size to output path.
        """
        if formats is None:
            formats = ['webp']
        
        if sizes is None:
            sizes = ['web-medium']
        
        # Load image
        try:
            image = Image.open(input_path)
            # Auto-rotate based on EXIF orientation
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            print(f"[ERROR] Failed to open image {input_path}: {e}")
            return {}
        
        # Normalize aspect ratio if specified
        if aspect_ratio and aspect_ratio in self.ASPECT_RATIOS:
            image = self.normalize_aspect_ratio(image, self.ASPECT_RATIOS[aspect_ratio])
        
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
        
        for size_key in sizes:
            if size_key not in self.MAX_DIMENSIONS:
                print(f"[WARN] Unknown size: {size_key}, skipping")
                continue
            
            max_dims = self.MAX_DIMENSIONS[size_key]
            resized = self.resize_image(image, max_dims)
            
            for fmt in formats:
                if fmt == 'webp':
                    quality = self.WEB_FORMATS.get('webp', {}).get('quality', 85)
                    method = self.WEB_FORMATS.get('webp', {}).get('method', 6)
                    output_path = output_dir / f"{base_name}_{size_key}.webp"
                    resized.save(output_path, 'WEBP', quality=quality, method=method)
                    
                elif fmt == 'png':
                    optimize = self.GAME_FORMATS.get('png', {}).get('optimize', True)
                    compress_level = self.GAME_FORMATS.get('png', {}).get('compress_level', 9)
                    output_path = output_dir / f"{base_name}_{size_key}.png"
                    resized.save(output_path, 'PNG', optimize=optimize, compress_level=compress_level)
                    
                elif fmt == 'jpg' or fmt == 'jpeg':
                    # Use web settings for JPEG if available, otherwise game settings
                    if 'jpeg' in self.WEB_FORMATS:
                        quality = self.WEB_FORMATS['jpeg'].get('quality', 85)
                        progressive = self.WEB_FORMATS['jpeg'].get('progressive', True)
                        optimize = self.WEB_FORMATS['jpeg'].get('optimize', True)
                    else:
                        quality = self.GAME_FORMATS.get('jpg', {}).get('quality', 90)
                        progressive = False
                        optimize = self.GAME_FORMATS.get('jpg', {}).get('optimize', True)
                    
                    output_path = output_dir / f"{base_name}_{size_key}.jpg"
                    # Convert RGBA to RGB for JPEG
                    if resized.mode == 'RGBA':
                        rgb_image = Image.new('RGB', resized.size, (255, 255, 255))
                        rgb_image.paste(resized, mask=resized.split()[3])
                        resized = rgb_image
                    elif resized.mode not in ('RGB', 'L'):
                        resized = resized.convert('RGB')
                    
                    save_kwargs = {'quality': quality, 'optimize': optimize}
                    if progressive:
                        save_kwargs['progressive'] = True
                    resized.save(output_path, 'JPEG', **save_kwargs)
                
                else:
                    print(f"[WARN] Unknown format: {fmt}, skipping")
                    continue
                
                outputs[f"{fmt}_{size_key}"] = output_path
                print(f"[OK] Created: {output_path.name} ({resized.size[0]}x{resized.size[1]})")
        
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
        
        return outputs


def main():
    parser = argparse.ArgumentParser(
        description='Process images for web and game use',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single image
  python process_image.py cat.jpg --formats webp png --sizes web-medium web-large
  
  # Process with aspect ratio normalization
  python process_image.py cat.jpg --aspect-ratio square --sizes web-small
  
  # Batch process directory
  python process_image.py --batch ./dump --formats webp --sizes web-medium
        """
    )
    
    parser.add_argument('input', nargs='?', type=Path, help='Input image file')
    parser.add_argument('--batch', type=Path, help='Process all images in directory')
    parser.add_argument('--output-dir', type=Path, default=Path('processed'),
                       help='Output directory (default: processed)')
    parser.add_argument('--formats', nargs='+', default=['webp'],
                       choices=['webp', 'png', 'jpg', 'jpeg'],
                       help='Output formats (default: webp)')
    parser.add_argument('--sizes', nargs='+',
                       default=['web-medium'],
                       choices=['web-thumbnail', 'web-small', 'web-medium', 'web-large',
                                'game-small', 'game-medium', 'game-large', 'game-ui'],
                       help='Output sizes (default: web-medium)')
    parser.add_argument('--aspect-ratio', choices=['square', 'wide', 'standard', 'portrait', 'game-ui'],
                       help='Normalize to aspect ratio')
    parser.add_argument('--config', type=Path, help='Configuration JSON file')
    parser.add_argument('--no-strip-metadata', action='store_true',
                       help='Skip metadata stripping')
    
    args = parser.parse_args()
    
    # Validate inputs
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
    config = {}
    if args.no_strip_metadata:
        config['strip_gps'] = False
        config['strip_personal'] = False
    
    processor = ImageProcessor(args.config)
    if config:
        processor.config.update(config)
    
    # Process images
    if args.batch:
        # Batch processing
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
                aspect_ratio=args.aspect_ratio
            )
    else:
        # Single file processing
        processor.process_image(
            args.input,
            output_dir,
            formats=args.formats,
            sizes=args.sizes,
            aspect_ratio=args.aspect_ratio
        )
    
    print(f"\n[OK] Processing complete. Outputs in: {output_dir}")


if __name__ == '__main__':
    main()
