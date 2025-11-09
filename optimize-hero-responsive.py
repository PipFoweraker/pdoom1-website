#!/usr/bin/env python3
"""
Generate responsive background images for different screen sizes
Mobile: 800px, Tablet: 1200px, Desktop: 1600px, Full: 2400px
"""

from PIL import Image
import os

def create_responsive_variant(input_path, output_base, width, quality=85):
    """Create a single responsive variant"""
    img = Image.open(input_path)

    # Calculate new height maintaining aspect ratio
    ratio = width / img.size[0]
    new_size = (width, int(img.size[1] * ratio))

    # Resize
    img_resized = img.resize(new_size, Image.Resampling.LANCZOS)

    # Save as WebP (primary)
    webp_path = f"{output_base}-{width}w.webp"
    img_resized.save(webp_path, 'WebP', quality=quality, method=6)
    webp_size = os.path.getsize(webp_path) / 1024

    # Save as JPEG (fallback)
    jpg_path = f"{output_base}-{width}w.jpg"
    img_resized.save(jpg_path, 'JPEG', quality=quality, optimize=True)
    jpg_size = os.path.getsize(jpg_path) / 1024

    print(f"  {width}w: WebP {webp_size:.0f}KB | JPEG {jpg_size:.0f}KB")

def main():
    screenshots_dir = "public/assets/screenshots"
    input_file = "hero-main-office.png"
    output_base = "hero-bg"

    input_path = os.path.join(screenshots_dir, input_file)
    output_path = os.path.join(screenshots_dir, output_base)

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found!")
        return

    print("Creating Responsive Background Images")
    print("=" * 50)

    # Create variants for different screen sizes
    sizes = [
        (800, 90),   # Mobile - higher quality since it's smaller
        (1200, 88),  # Tablet
        (1600, 85),  # Desktop
        (2400, 82),  # Large desktop/retina
    ]

    for width, quality in sizes:
        create_responsive_variant(input_path, output_path, width, quality)

    print("=" * 50)
    print(f"Responsive variants created in {screenshots_dir}")

if __name__ == "__main__":
    main()
