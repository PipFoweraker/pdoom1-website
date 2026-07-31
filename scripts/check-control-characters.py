#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find control characters that should not be in a text file.

WHY THIS EXISTS
---------------
Written 2026-07-31 after a shell heredoc mangled an escape sequence for the third time
in one day, writing a LITERAL newline into a JavaScript regex:

    const src = fs.readFileSync(PAGE, 'utf8').replace(/
    /g, '
    ');

`SyntaxError: Invalid regular expression: missing /` -- the file no longer parsed, so
`test-board-honesty.js` could not run at all, and `main` went red. An earlier instance
that day wrote a raw 0x08 BACKSPACE where `\\b` was intended, inside a working regex,
which is far worse: it did not fail, it silently matched nothing, so a test reported
"found 0 interpolations to check" and PASSED.

That second failure mode is the reason this script exists. A mangled escape that BREAKS
is self-announcing. A mangled escape that merely stops matching is invisible, and it
turns a guard into decoration.

WHAT IT FOUND ON ITS FIRST RUN
------------------------------
Zero surviving heredoc damage -- so the escape problem was a process failure, not a
latent defect. But it did find 57 stray control characters across 8 generated event
pages (0x03 ETX, 0x0b, 0x0c FORM FEED, 0x0f, 0x1c FILE SEPARATOR), all inherited from
upstream PDF-scraped text. Invisible in a browser, real in the file, and the same root
cause as the 75 academic email addresses that were published for weeks: raw PDF text
shipped without sanitising. Tracked at pdoom-data#45.

SEVERITY MODEL
--------------
FAIL on hand-written source -- scripts, workflows, hand-authored pages and docs. A
      control character there is damage: nobody types one on purpose.
WARN on generated output -- the event pages and events.json, whose content is scraped
      upstream. Fixing those means fixing the generator or the source data, which is a
      different repo's decision, so this reports without blocking.

Tabs, newlines and carriage returns are of course allowed everywhere.

Run:  python scripts/check-control-characters.py           (exit 1 on any FAIL)
      python scripts/check-control-characters.py --all     (list every occurrence)
"""

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

TEXT_SUFFIX = re.compile(r"\.(py|js|mjs|cjs|md|json|ya?ml|html|css|sh|txt)$", re.I)

# Everything in C0 except tab (09), newline (0a) and carriage return (0d).
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Paths whose CONTENT is scraped from elsewhere. Damage here is upstream's to fix.
GENERATED = ("public/events/", "public/data/events.json", "public/design-notes/",
             "public/data/issues-cache.json", "public/docs/pdoom1-open-issues.md")

NAMES = {0x00: "NUL", 0x03: "ETX", 0x07: "BEL", 0x08: "BACKSPACE", 0x0b: "VT",
         0x0c: "FORM FEED", 0x0f: "SI", 0x1b: "ESC", 0x1c: "FILE SEP", 0x7f: "DEL"}


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=str(ROOT),
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace").stdout
    return [f for f in out.split("\n") if f and TEXT_SUFFIX.search(f)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="list every occurrence")
    args = ap.parse_args()

    fails, warns, seen = [], [], Counter()
    files = tracked_files()

    for rel in files:
        p = ROOT / rel
        try:
            text = p.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = list(CONTROL.finditer(text))
        if not hits:
            continue
        generated = any(rel.startswith(g) or rel == g for g in GENERATED)
        bucket = warns if generated else fails
        for m in hits:
            code = ord(m.group())
            line = text.count("\n", 0, m.start()) + 1
            seen[code] += 1
            bucket.append((rel, line, code))

    print(f"Scanned {len(files)} tracked text files.")
    print("-" * 70)

    if fails:
        print(f"\nFAIL -- {len(fails)} control character(s) in HAND-WRITTEN source.")
        print("A control character in source is damage; nobody types one deliberately.")
        print("The usual cause here is a shell heredoc eating an escape sequence -- see")
        print("CLAUDE.md. Use the editing tools instead of a heredoc.\n")
        for rel, line, code in (fails if args.all else fails[:25]):
            print(f"  {rel}:{line}  0x{code:02x} {NAMES.get(code, '')}")
        if not args.all and len(fails) > 25:
            print(f"  ... and {len(fails) - 25} more (--all to list)")

    if warns:
        gen_files = sorted({r for r, _, _ in warns})
        print(f"\nWARN -- {len(warns)} control character(s) across {len(gen_files)} "
              f"GENERATED file(s).")
        print("Content is scraped upstream, so the fix belongs to the source data or the")
        print("generator, not here. Reported, never failed on. See pdoom-data#45.\n")
        for rel in (gen_files if args.all else gen_files[:10]):
            n = sum(1 for r, _, _ in warns if r == rel)
            print(f"  {rel}  ({n})")
        if not args.all and len(gen_files) > 10:
            print(f"  ... and {len(gen_files) - 10} more file(s)")

    if seen:
        print("\ncharacters seen: " + ", ".join(
            f"0x{c:02x} {NAMES.get(c, '')} x{n}" for c, n in sorted(seen.items())))

    if not fails and not warns:
        print("\nOK: no stray control characters anywhere.")
    elif not fails:
        print(f"\nOK: no damage in hand-written source. {len(warns)} upstream warning(s).")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
