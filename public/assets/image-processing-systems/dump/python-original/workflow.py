#!/usr/bin/env python3
"""
Batch Image Processing Workflow for pdoom1-website Assets

Automated workflow for processing cat images and other assets:
1. Scans dump folder for new images
2. Processes with appropriate settings
3. Organizes outputs by format and size
4. Generates manifest for tracking

Usage:
    python workflow.py [--scan-only] [--force]
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Import the processor
from process_image import ImageProcessor


class AssetWorkflow:
    """Automated workflow for processing image assets."""
    
    def __init__(self, dump_dir: Path, output_base: Path):
        self.dump_dir = dump_dir.resolve()
        self.output_base = output_base.resolve()
        self.processed_dir = self.output_base / 'processed'
        self.archive_dir = self.dump_dir / 'archive'
        self.manifest_file = self.dump_dir / 'manifest.json'
        
        # Create directories
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Load manifest
        self.manifest = self._load_manifest()
    
    def _load_manifest(self) -> Dict:
        """Load processing manifest."""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load manifest: {e}")
        
        return {
            'processed': {},
            'last_run': None,
            'statistics': {
                'total_processed': 0,
                'total_outputs': 0,
            }
        }
    
    def _save_manifest(self):
        """Save processing manifest."""
        try:
            with open(self.manifest_file, 'w') as f:
                json.dump(self.manifest, f, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save manifest: {e}")
    
    def scan_new_images(self) -> List[Path]:
        """Scan dump directory for unprocessed images."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff'}
        
        all_images = []
        for ext in image_extensions:
            all_images.extend(self.dump_dir.glob(f'*{ext}'))
            all_images.extend(self.dump_dir.glob(f'*{ext.upper()}'))
        
        # Filter out already processed
        processed = set(self.manifest.get('processed', {}).keys())
        new_images = [img for img in all_images if str(img.name) not in processed]
        
        return sorted(new_images)
    
    def process_cat_images(self, image_path: Path, force: bool = False) -> Dict:
        """
        Process cat images with multiple aspect ratios and optimized web compression.
        
        Web outputs:
        - Multiple aspect ratios: square, wide, standard, portrait, original
        - Optimized formats: WebP (primary), JPEG (fallback for compatibility)
        - Multiple sizes: thumbnail, small, medium, large
        - Fast loading with high visual quality (85% quality WebP)
        
        Game outputs:
        - Original aspect ratio preserved
        - High quality formats: PNG, WebP
        - Game-optimized sizes
        """
        base_name = image_path.stem
        
        # Check if already processed
        if not force and base_name in self.manifest.get('processed', {}):
            print(f"[INFO] Skipping {image_path.name} (already processed)")
            return self.manifest['processed'][base_name]
        
        print(f"\n[INFO] Processing cat image: {image_path.name}")
        
        processor = ImageProcessor()
        
        # Web-optimized outputs with multiple aspect ratios
        # Generate square, wide, standard, portrait, and original aspect ratios
        web_aspect_ratios = ['square', 'wide', 'standard', 'portrait', 'original']
        all_web_outputs = {}
        
        for aspect_ratio in web_aspect_ratios:
            aspect_outputs = processor.process_image(
                image_path,
                self.processed_dir / 'web',
                formats=['webp', 'jpeg'],  # WebP primary, JPEG fallback
                sizes=['web-thumbnail', 'web-small', 'web-medium', 'web-large'],
                aspect_ratio=aspect_ratio if aspect_ratio != 'original' else None
            )
            # Add aspect ratio suffix to keys
            for key, value in aspect_outputs.items():
                all_web_outputs[f"{key}_{aspect_ratio}"] = value
        
        # Game-optimized outputs (preserve original aspect)
        game_outputs = processor.process_image(
            image_path,
            self.processed_dir / 'game',
            formats=['png', 'webp'],
            sizes=['game-small', 'game-medium', 'game-large'],
            aspect_ratio=None  # Preserve original aspect for game
        )
        
        # Combine outputs
        all_outputs = {**all_web_outputs, **game_outputs}
        
        # Calculate total file sizes
        total_size_kb = sum(p.stat().st_size for p in all_outputs.values() if p.exists()) / 1024
        
        # Record in manifest
        result = {
            'source': str(image_path.name),
            'processed_at': datetime.now().isoformat(),
            'outputs': {k: str(v) for k, v in all_outputs.items()},
            'file_size_mb': round(image_path.stat().st_size / (1024 * 1024), 2),
            'output_size_kb': round(total_size_kb, 2),
            'web_aspect_ratios': web_aspect_ratios,
        }
        
        self.manifest['processed'][base_name] = result
        self.manifest['statistics']['total_processed'] += 1
        self.manifest['statistics']['total_outputs'] += len(all_outputs)
        self.manifest['last_run'] = datetime.now().isoformat()
        
        # Archive original
        archive_path = self.archive_dir / image_path.name
        if not archive_path.exists():
            shutil.copy2(image_path, archive_path)
            print(f"[INFO] Archived original to: {archive_path}")
        
        return result
    
    def run(self, force: bool = False, scan_only: bool = False):
        """Run the complete workflow."""
        print("[INFO] Starting asset processing workflow...")
        
        # Ensure output directories exist
        (self.processed_dir / 'web').mkdir(parents=True, exist_ok=True)
        (self.processed_dir / 'game').mkdir(parents=True, exist_ok=True)
        
        # Scan for new images
        new_images = self.scan_new_images()
        
        if not new_images:
            print("[INFO] No new images to process.")
            if scan_only:
                print(f"[INFO] Already processed: {len(self.manifest.get('processed', {}))} images")
            return
        
        if scan_only:
            print(f"[INFO] Found {len(new_images)} new images to process:")
            for img in new_images:
                size_mb = img.stat().st_size / (1024 * 1024)
                print(f"  - {img.name} ({size_mb:.2f} MB)")
            return
        
        # Process each image
        print(f"[INFO] Processing {len(new_images)} new images...")
        for image_path in new_images:
            try:
                self.process_cat_images(image_path, force=force)
            except Exception as e:
                print(f"[ERROR] Failed to process {image_path.name}: {e}")
                continue
        
        # Save manifest
        self._save_manifest()
        
        # Print summary
        print(f"\n[OK] Workflow complete!")
        print(f"  Processed: {len(new_images)} images")
        print(f"  Total outputs: {self.manifest['statistics']['total_outputs']}")
        print(f"  Web outputs: {self.processed_dir / 'web'}")
        print(f"  Game outputs: {self.processed_dir / 'game'}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch image processing workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process new images
  python workflow.py
  
  # Scan only (dry run)
  python workflow.py --scan-only
  
  # Force reprocess all
  python workflow.py --force
        """
    )
    
    parser.add_argument('--dump-dir', type=Path, default=Path('dump'),
                       help='Directory containing raw images (default: dump)')
    parser.add_argument('--output-dir', type=Path, default=Path('processed'),
                       help='Output directory (default: processed)')
    parser.add_argument('--scan-only', action='store_true',
                       help='Only scan for new images, do not process')
    parser.add_argument('--force', action='store_true',
                       help='Reprocess all images even if already processed')
    
    args = parser.parse_args()
    
    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    dump_dir = (script_dir / args.dump_dir).resolve()
    output_dir = (script_dir / args.output_dir).resolve()
    
    if not dump_dir.exists():
        print(f"[ERROR] Dump directory does not exist: {dump_dir}")
        sys.exit(1)
    
    workflow = AssetWorkflow(dump_dir, output_dir)
    workflow.run(force=args.force, scan_only=args.scan_only)


if __name__ == '__main__':
    main()
