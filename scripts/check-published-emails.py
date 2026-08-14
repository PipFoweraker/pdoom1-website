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
    """Import EMAIL_PATTERN / REDACTION_MARKER / residue_scan from sync-events.py.

    The module name has a hyphen, so a plain import is impossible; importlib
    is the supported way. Reusing EMAIL_PATTERN is the point -- a second copy of
    the regex would drift from the one that actually protects the generated
    pages.

    BUT REUSING IT IS ALSO THIS SCRIPT'S BLIND SPOT, and it is worth being
    explicit about which half is which. Sharing the pattern means this check
    cannot disagree with the generator about a KNOWN shape, which is what we
    want. It also means that if the pattern is WRONG, this check confirms the
    generator's own mistake and reports PASS -- which is exactly what happened
    between 2026-08-09 and 2026-08-15, when the brace-group mode was
    unmatchable here and upstream had already fixed it.

    So residue_scan() is imported alongside it: same module, DIFFERENT
    PRINCIPLE. It walks '@' characters rather than matching an address shape,
    so it is not blind in the same places, and a count it can see that
    EMAIL_PATTERN cannot is reported as a DISAGREEMENT below.
    """
    path = REPO_ROOT / "scripts" / "sync" / "sync-events.py"
    spec = importlib.util.spec_from_file_location("sync_events", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EMAIL_PATTERN, module.REDACTION_MARKER, module.unexplained_residue


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


def scan_residue(unexplained_residue):
    """Return {relative_path: unexplained_count} where the independent scanner
    sees address-shaped text EMAIL_PATTERN cannot account for.

    This is a DISAGREEMENT check, not a second detector: everything
    EMAIL_PATTERN can see is already handled by scan() above, so what matters is
    the remainder. A positive remainder means the shared pattern has a hole,
    which is the one failure that cannot be seen from inside the pattern.

    The comparison is POSITIONAL, done in sync-events.py. Comparing totals
    instead does not work -- the footer's allowed addresses are counted by
    EMAIL_PATTERN and ignored by the independent scanner, so on any ordinary
    page the subtraction goes negative and hides a real leak.
    """
    findings = {}
    for path in sorted(PUBLIC_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        text = read(path)
        if "@" not in text:
            continue
        unexplained = unexplained_residue(text)
        if unexplained > 0:
            findings[path.relative_to(REPO_ROOT).as_posix()] = unexplained
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

    pattern, marker, unexplained_residue = load_generator_pattern()
    findings = scan(pattern)
    residue = scan_residue(unexplained_residue)

    if not findings and not residue:
        print("PASS: no third-party email addresses published under public/ "
              "(and the independent scanner agrees)")
        return 0

    if findings:
        distinct = {a for hits in findings.values() for a in hits}
        total = sum(len(h) for h in findings.values())
        # COUNTS AND PATHS ONLY, NEVER THE ADDRESS TEXT.
        #
        # This script runs in content-honesty.yml on a PUBLIC repository, so its
        # stdout is a published artefact. Printing the matches would republish
        # every address the run just found -- to a wider audience than the page
        # it was found on, and permanently, because Actions logs outlive the
        # commit that triggered them.
        #
        # That is not hypothetical: pdoom1#1212, the PR that CLOSED the original
        # exposure, quoted a severed address verbatim in its body to explain the
        # defect, and update-game-data.yml then harvested that body into
        # public/data/issues-cache.json and served it. The fix and the leak were
        # the same sentence. sync-events.py already prints counts only for this
        # reason; this script did not, and it is the one wired into CI.
        #
        # A maintainer who needs the text has the path and the line count, and
        # can look at the file locally where the disclosure stops.
        print(f"FOUND {len(distinct)} distinct third-party address(es), "
              f"{total} occurrence(s), across {len(findings)} file(s):")
        for rel in sorted(findings):
            print(f"  {rel}: {len(findings[rel])} occurrence(s)")
        print("\nAddresses are deliberately NOT printed: this log is public.")

    if residue:
        total_r = sum(residue.values())
        print(f"\nDISAGREEMENT: the independent scanner found {total_r} "
              f"address-shaped item(s) across {len(residue)} file(s) that "
              f"EMAIL_PATTERN cannot account for:")
        for rel in sorted(residue):
            print(f"  {rel}: {residue[rel]} unexplained")
        print("\nThis means the shared pattern has a hole in it. Widen "
              "EMAIL_PATTERN in scripts/sync/sync-events.py to cover the mode, "
              "or characterise the new false-positive family STRUCTURALLY in "
              "residue_scan() -- never by adding a name to an allowlist.")

    if not args.fix:
        print("\nFAIL. Fix at the generator where one owns the page; "
              "re-run with --fix only for pages no generator owns.")
        return 1

    if residue:
        print("\nFAIL: --fix cannot clear a DISAGREEMENT. It rewrites what "
              "EMAIL_PATTERN matches, and by definition the pattern cannot see "
              "these. Fix the pattern first.")
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
