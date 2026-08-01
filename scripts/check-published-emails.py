#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail if pdoom1.com publishes a third party's email address.

Why this exists
---------------
Event descriptions are raw text scraped out of paper PDFs, and arXiv/ACM author
blocks carry the authors' institutional addresses. Before 2026-07-29 the site
served 75 distinct academics' addresses across 44 pages, in plain text, which is
exactly the form a spam harvester reads. Nobody consented to that.

The generator (scripts/sync/sync-events.py) now redacts them at the source, so
anything this script finds is either (a) a page no generator owns, or (b) a new
leak path. Both are worth failing on.

The regex is IMPORTED from the generator rather than copied, so there is exactly
one definition of "what an email address looks like" in this repo.

Usage:
    python scripts/check-published-emails.py          # report + exit 1 on find
    python scripts/check-published-emails.py --fix    # rewrite offenders in place

The --fix path exists for the ~1,000 public/events/alignmentforum_*.html pages,
which no current sync regenerates (docs/TECH_DEBT.md E-0: pdoom-data holds them
in a separate collection the sync has never read). Scrubbing them in place is a
stopgap, NOT the fix -- when E-0 is closed and the sync reads that collection,
the generator's redaction supersedes this. Never delete a page here; rsync
--delete makes a deletion a production removal.
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = REPO_ROOT / "public"
SCAN_SUFFIXES = {".html", ".json", ".md", ".xml", ".txt"}

# Addresses the project publishes ON PURPOSE, plus form placeholders. Matched
# against the whole address, anchored, so "notpress@pdoom1.com.evil.example"
# does not sneak through.
ALLOWED = re.compile(
    r"^(?:"
    r"[A-Za-z0-9._%+\-]+@pdoom1\.com"          # our own contact addresses
    r"|you@example\.com"                        # bug-report form placeholder
    r"|[A-Za-z0-9._%+\-]+@example\.(?:com|org)" # documentation placeholders
    # The maintainer's own address, published on purpose. /bug-report/ tells a player
    # to mail their saved report to "the address the game's confirmation message shows
    # you -- it currently names pip@beacongcr.org". Withholding it would make the page
    # useless; it is first-party, not a third party's address harvested out of a PDF,
    # which is the disclosure this script exists to prevent. Landed in #197.
    r"|pip@beacongcr\.org"
    r")$"
)


def load_generator_pattern():
    """Import EMAIL_PATTERN / REDACTION_MARKER from sync-events.py.

    The module name has a hyphen, so a plain import is impossible; importlib
    is the supported way. Reusing it is the point -- a second copy of the
    regex would drift from the one that actually protects the generated pages.
    """
    path = REPO_ROOT / "scripts" / "sync" / "sync-events.py"
    spec = importlib.util.spec_from_file_location("sync_events", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EMAIL_PATTERN, module.REDACTION_MARKER


def is_allowed(match: str) -> bool:
    """True for addresses we publish deliberately.

    The generator's pattern swallows an optional 'mailto:' prefix, so strip it
    before anchoring -- otherwise every 'mailto:team@pdoom1.com' link on the
    site (2,200 of them) reads as a leak.
    """
    return bool(ALLOWED.match(match.split("mailto:", 1)[-1]))


def read(path: Path) -> str:
    # newline="" disables universal-newline translation, so an existing CRLF
    # file round-trips unchanged and --fix produces a one-line diff instead of
    # a whole-file line-ending rewrite.
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def scan(pattern):
    """Return {relative_path: [address, ...]} for every disallowed address."""
    findings = {}
    for path in sorted(PUBLIC_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        hits = [m for m in pattern.findall(read(path)) if not is_allowed(m)]
        if hits:
            findings[path.relative_to(REPO_ROOT).as_posix()] = hits
    return findings


def fix(pattern, marker, findings):
    """Replace disallowed addresses in place, leaving allowed ones alone."""
    for rel in findings:
        path = REPO_ROOT / rel
        new = pattern.sub(
            lambda m: m.group(0) if is_allowed(m.group(0)) else marker,
            read(path),
        )
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print(f"  scrubbed {rel}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true",
                        help="rewrite offending files in place")
    args = parser.parse_args()

    pattern, marker = load_generator_pattern()
    findings = scan(pattern)

    if not findings:
        print("PASS: no third-party email addresses published under public/")
        return 0

    distinct = {a for hits in findings.values() for a in hits}
    total = sum(len(h) for h in findings.values())
    print(f"Found {len(distinct)} distinct third-party addresses, "
          f"{total} occurrences, across {len(findings)} files:")
    for rel, hits in findings.items():
        print(f"  {rel}: {', '.join(sorted(set(hits)))}")

    if not args.fix:
        print("\nFAIL. Fix at the generator where one owns the page; "
              "re-run with --fix only for pages no generator owns.")
        return 1

    print()
    fix(pattern, marker, findings)
    remaining = scan(pattern)
    if remaining:
        print(f"\nFAIL: {len(remaining)} files still carry addresses after --fix")
        return 1
    print("\nPASS: all occurrences scrubbed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
