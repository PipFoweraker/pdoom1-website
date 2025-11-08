#!/usr/bin/env python3
"""
Optimize game screenshots for web use
Converts large PNGs to web-optimized formats while keeping originals
"""

from PIL import Image
import os

def optimize_screenshot(input_path, output_base, max_width=1200, quality=85):
    """
    Optimize a screenshot for web use

    Args:
        input_path: Path to original image
        output_base: Base path for output (without extension)
        max_width: Maximum width for web version
        quality: JPEG/WebP quality (1-100)
    """
    print(f"Processing: {os.path.basename(input_path)}")

    # Open image
    img = Image.open(input_path)
    original_size = os.path.getsize(input_path) / 1024 / 1024  # MB
    print(f"  Original: {img.size[0]}x{img.size[1]} ({original_size:.2f}MB)")

    # Calculate new size maintaining aspect ratio
    if img.size[0] > max_width:
        ratio = max_width / img.size[0]
        new_size = (max_width, int(img.size[1] * ratio))
        img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
    else:
        img_resized = img
        new_size = img.size

    # Convert RGBA to RGB if needed
    if img_resized.mode == 'RGBA':
        # Create white background
        background = Image.new('RGB', img_resized.size, (0, 0, 0))
        background.paste(img_resized, mask=img_resized.split()[3])  # Use alpha channel as mask
        img_resized = background
    elif img_resized.mode != 'RGB':
        img_resized = img_resized.convert('RGB')

    # Save as WebP (best compression)
    webp_path = f"{output_base}.webp"
    img_resized.save(webp_path, 'WebP', quality=quality, method=6)
    webp_size = os.path.getsize(webp_path) / 1024  # KB
    print(f"  WebP: {new_size[0]}x{new_size[1]} ({webp_size:.0f}KB)")

    # Save as JPEG (fallback)
    jpg_path = f"{output_base}.jpg"
    img_resized.save(jpg_path, 'JPEG', quality=quality, optimize=True)
    jpg_size = os.path.getsize(jpg_path) / 1024  # KB
    print(f"  JPEG: {new_size[0]}x{new_size[1]} ({jpg_size:.0f}KB)")

    print(f"  [OK] Saved to {os.path.basename(output_base)}.*\n")

def main():
    screenshots_dir = "public/assets/screenshots"

    screenshots = [
        ("hero-main-office.png", "hero-main-office-web", 1400),
        ("gameplay-office-1.png", "gameplay-office-1-web", 1200),
        ("gameplay-office-2.png", "gameplay-office-2-web", 1200),
        ("doom-cat-closeup.png", "doom-cat-closeup-web", 800),
    ]

    print("Optimizing Screenshots for Web\n" + "="*50 + "\n")

    for filename, output_base, max_width in screenshots:
        input_path = os.path.join(screenshots_dir, filename)
        output_path = os.path.join(screenshots_dir, output_base)

        if os.path.exists(input_path):
            optimize_screenshot(input_path, output_path, max_width=max_width, quality=85)
        else:
            print(f"WARNING: Not found: {filename}\n")

    print("="*50)
    print("Optimization complete!")
    print(f"Output directory: {screenshots_dir}")

if __name__ == "__main__":
    main()
