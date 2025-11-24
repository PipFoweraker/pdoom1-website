#!/usr/bin/env python3
"""
Sync game icons from pdoom1 repository to website

This script copies game icons from the pdoom1 repository
to the website's assets directory for use in events pages
and other documentation.

Usage:
    python scripts/sync/sync-game-icons.py [--pdoom1-path PATH] [--size 128]
"""

import argparse
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
WEBSITE_ROOT = SCRIPT_DIR.parent.parent
ICONS_DIR = WEBSITE_ROOT / "public" / "assets" / "icons" / "game"

DEFAULT_PDOOM1 = WEBSITE_ROOT.parent / "pdoom1"


def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def sync_icons(pdoom1_path: Path, icon_size: int = 128):
    """
    Sync game icons from pdoom1 repository

    Args:
        pdoom1_path: Path to pdoom1 repo
        icon_size: Icon size to sync (default 128px for web use)
    """
    icons_source = pdoom1_path / "art_generated" / "game_icons" / "v1"

    if not icons_source.exists():
        log(f"ERROR: Icons directory not found: {icons_source}")
        log("Make sure pdoom1 repository is cloned and contains art_generated/game_icons/v1/")
        return False

    # Ensure destination exists
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    # Find all icons of the specified size
    pattern = f"*_{icon_size}.png"
    icon_files = list(icons_source.glob(pattern))

    if not icon_files:
        log(f"WARN: No icons found matching pattern: {pattern}")
        return False

    # Copy icons
    copied = 0
    for icon_file in icon_files:
        dest = ICONS_DIR / icon_file.name
        shutil.copy2(icon_file, dest)
        copied += 1

    log(f"✅ Synced {copied} icons ({icon_size}px) from pdoom1")
    log(f"   Source: {icons_source}")
    log(f"   Destination: {ICONS_DIR}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Sync game icons from pdoom1 repository")
    parser.add_argument(
        "--pdoom1-path",
        type=Path,
        default=DEFAULT_PDOOM1,
        help=f"Path to pdoom1 repository (default: {DEFAULT_PDOOM1})"
    )
    parser.add_argument(
        "--size",
        type=int,
        default=128,
        choices=[64, 128, 256, 512, 1024],
        help="Icon size to sync (default: 128px for web)"
    )

    args = parser.parse_args()

    log("=" * 60)
    log("Syncing game icons from pdoom1 repository")
    log("=" * 60)

    success = sync_icons(args.pdoom1_path, args.size)

    if success:
        log("=" * 60)
        log("✅ Icon sync complete!")
        log("=" * 60)
    else:
        log("❌ Icon sync failed")
        exit(1)


if __name__ == "__main__":
    main()
