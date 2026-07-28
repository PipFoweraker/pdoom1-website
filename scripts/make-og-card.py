#!/usr/bin/env python
"""Regenerate the OpenGraph / Twitter share card from the full-size source art.

Why this exists
---------------
`public/assets/pdoom_logo_1.png` is the 2.49 MB, 1024x1536 **source** painting.
It is a press-kit download (linked from /press/), not a share card. It was once
used directly as `og:image`; at 2.49 MB it sits above Twitter's practical fetch
budget, so shares could render with *no image at all* -- strictly worse than a
small one.

An interim 235 KB card shipped in 3aa21ba6, but it kept the source's 1024x1536
**portrait** shape. Every page here declares `twitter:card=summary_large_image`,
which renders at ~1.91:1; a portrait image gets centre-cropped, and on this
painting the centre band is the cat's chest and the hand -- the laser eyes, the
whole point of the image, fall outside the crop.

So: crop to 1.91:1 *deliberately*, around the head, and let no scraper choose
the framing for us. 1200x630 is the size issue #16 asks for and the size both
Facebook and X document.

The crop box is hand-chosen, not computed: y=230 clears the ear tips, y=768
keeps the collar as a base line, and the full source width keeps both laser
beams. Re-derive it by eye if the source art is ever replaced.

Run:  python scripts/make-og-card.py [--check]

--check verifies the committed card matches what this script would produce
(dimensions and approximate size), without writing.
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required (pip install Pillow)")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "public", "assets", "pdoom_logo_1.png")
DST = os.path.join(ROOT, "public", "assets", "og-card.jpg")

# Target: the size Facebook's OG docs and X's summary_large_image both want.
TARGET = (1200, 630)
# Hand-chosen crop on the 1024x1536 source. Full width; vertical band around
# the head. See module docstring before changing.
CROP = (0, 230, 1024, 768)
QUALITY = 84
# A card should stay small enough that every scraper fetches it comfortably.
# X's documented limit is 5 MB; the practical failure mode is slow fetches, so
# hold a far tighter budget and fail loudly if a re-encode blows past it.
MAX_BYTES = 300 * 1024


def build():
    im = Image.open(SRC).convert("RGB")
    if im.size != (CROP[2], 1536):
        print(f"WARN: source is {im.size}, CROP was chosen for (1024, 1536)")
    return im.crop(CROP).resize(TARGET, Image.LANCZOS)


def main():
    check = "--check" in sys.argv

    if not os.path.exists(SRC):
        print(f"ERROR: missing source {SRC}")
        return 1

    if check:
        if not os.path.exists(DST):
            print(f"FAIL: {DST} does not exist")
            return 1
        got = Image.open(DST)
        size = os.path.getsize(DST)
        ok = True
        if got.size != TARGET:
            print(f"FAIL: og-card.jpg is {got.size}, expected {TARGET}")
            ok = False
        if size > MAX_BYTES:
            print(f"FAIL: og-card.jpg is {size} bytes, budget is {MAX_BYTES}")
            ok = False
        if ok:
            print(f"PASS: og-card.jpg {got.size}, {size} bytes")
        return 0 if ok else 1

    before = os.path.getsize(DST) if os.path.exists(DST) else 0
    card = build()
    card.save(DST, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    after = os.path.getsize(DST)
    if after > MAX_BYTES:
        print(f"ERROR: produced {after} bytes, over the {MAX_BYTES} budget")
        return 1
    print(f"source  {SRC}  {os.path.getsize(SRC)} bytes")
    print(f"card    {DST}  {before} -> {after} bytes, {TARGET[0]}x{TARGET[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
