#!/usr/bin/env python
"""Refuse a merge message that would silently suppress every workflow.

WHAT THIS GUARDS
----------------
`gh pr merge --squash` and the GitHub UI's squash button compose the merge commit
message from the PR **title plus the PR body**. GitHub matches a CI-suppression
token **anywhere in a commit message -- including the body, and including inside
backticks** -- and then runs *nothing*: no queued run, no skipped run, no entry in
`gh run list` at all. It reads exactly like an Actions outage.

So a PR body that merely *explains* how a bot workflow suppresses CI poisons a
commit nobody proof-read, at merge time, after every gate you were watching went
green.

This is not hypothetical. pdoom1-website#244 discussed a sync workflow's own
suppression marker three times in its body. Its merge commit `d3556d1e` ran ONE
check run where its neighbours ran 8, 9 and 15. The PR's own CI had been fully
green. The damage was a missed DEPLOY, not a missed test: #244 changed three files
under `public/`, Auto-Deploy never fired, and pdoom1.com kept serving the old bytes
for hours after the fix was on main.

WHY A GUARD AND NOT A CONVENTION
--------------------------------
The existing convention is "refer to it as the skip-CI marker, never write it".
That is a rule a human must remember at the exact moment they are explaining the
thing the rule is about -- which is when it is hardest to remember. CLAUDE.md has
carried the warning since 2026-08-02 and #244 happened anyway.

NOTE ON THIS FILE'S OWN TEXT
----------------------------
The bracketed literals are never written here. They are assembled from parts at
import time, so this file, its diff, and any commit message quoting it are all
safe to paste anywhere. That is deliberate: a guard you cannot discuss without
triggering the thing it guards is a guard people route around.

USAGE
    python scripts/check-merge-message.py --title "..." --body "..."
    python scripts/check-merge-message.py --from-env      # PR_TITLE / PR_BODY
    python scripts/check-merge-message.py --commits-from -  # messages on stdin

Exit 0 clean, 1 on a finding, 2 on bad usage.
"""

import argparse
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# --- the tokens, assembled so the literal never appears in this source ------
# GitHub honours these inside square brackets, case-insensitively, anywhere in a
# commit message. Written bare here (no brackets) they are inert.
_BARE_TOKENS = (
    "skip ci",
    "ci skip",
    "no ci",
    "skip actions",
    "actions skip",
)
_OPEN, _CLOSE = chr(91), chr(93)          # [ and ]

# HORIZONTAL whitespace only -- `[ \t]`, never `\s`.
#
# `\s` matches a newline, and the squash message is literally `title\n\nbody`, so
# `\s` made a title ending in "[skip" plus a body starting with "ci]" read as a
# suppression token spanning the join. GitHub does not match a token with a
# newline inside the brackets, so that was a FALSE POSITIVE -- the guard refusing
# a merge GitHub would have run fine.
#
# That distinction is not pedantry. CLAUDE.md's standing lesson is that a noisy
# check gets ignored, and a guard people route around protects nothing. The
# forced-failure test pins this case explicitly so the narrowing cannot be undone
# by someone "tidying" the pattern later.
_BRACKETED = [
    re.compile(
        re.escape(_OPEN) + r"[ \t]*" + tok.replace(" ", r"[ \t_-]+") + r"[ \t]*" + re.escape(_CLOSE),
        re.IGNORECASE,
    )
    for tok in _BARE_TOKENS
]

# The trailer form. `skip-checks: true` suppresses checks on some GitHub surfaces
# and is not bracketed, so it needs its own pattern.
_TRAILER = re.compile(r"^\s*skip[-_]checks\s*:\s*true\s*$", re.IGNORECASE | re.MULTILINE)


def find_suppressors(text):
    """Return a list of (kind, matched_text, line_number). Empty means clean."""
    if not text:
        return []
    findings = []
    for pat in _BRACKETED:
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            findings.append(("bracketed-token", m.group(0), line))
    for m in _TRAILER.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        findings.append(("skip-checks-trailer", m.group(0).strip(), line))
    return findings


def report(findings, where):
    print("")
    print("=" * 78)
    print("REFUSING: %s carries %d CI-suppression token(s)." % (where, len(findings)))
    print("=" * 78)
    for kind, matched, line in findings:
        print("  line %-4d  %-22s  %r" % (line, kind, matched))
    print("")
    print("Why this blocks the merge, not just warns:")
    print("  A squash merge composes its commit message from the PR title and BODY.")
    print("  GitHub matches these tokens anywhere in that message -- inside backticks,")
    print("  inside a quote, inside a code fence -- and then runs NOTHING. Not a")
    print("  skipped run. Not a queued run. No entry at all, which reads like an")
    print("  Actions outage and costs a diagnostic cycle to tell apart.")
    print("")
    print("  The cost is a missed DEPLOY, not a missed test. Auto-Deploy would not")
    print("  fire, and pdoom1.com would keep serving the previous bytes.")
    print("")
    print("How to fix it, without losing what you were trying to say:")
    print("  Name it instead of writing it: \"the skip-CI marker\".")
    print("  Or cite the commit SHA of the bot commit you are describing.")
    print("  Do NOT try to defang it with backticks or a code fence -- GitHub does")
    print("  not care about markdown, and that is exactly how #244 happened.")
    print("")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", default=None)
    ap.add_argument("--body", default=None)
    ap.add_argument("--from-env", action="store_true",
                    help="read PR_TITLE and PR_BODY from the environment")
    ap.add_argument("--commits-from", default=None,
                    help="path with concatenated commit messages, or - for stdin")
    args = ap.parse_args(argv)

    title, body = args.title, args.body
    if args.from_env:
        if title is None:
            title = os.environ.get("PR_TITLE", "")
        if body is None:
            body = os.environ.get("PR_BODY", "")

    checked_anything = False
    rc = 0

    # The squash message is title + body, so check them as ONE string: a token
    # split across the boundary is still a token in the composed message.
    if title is not None or body is not None:
        checked_anything = True
        composed = (title or "") + "\n\n" + (body or "")
        findings = find_suppressors(composed)
        if findings:
            rc = report(findings, "the PR title/body (which becomes the squash commit message)")
        else:
            print("OK: PR title and body carry no CI-suppression token.")

    if args.commits_from:
        checked_anything = True
        if args.commits_from == "-":
            text = sys.stdin.read()
        else:
            with open(args.commits_from, encoding="utf-8") as fh:
                text = fh.read()
        findings = find_suppressors(text)
        if findings:
            rc = report(findings, "a commit message on this branch") or rc
        else:
            print("OK: no commit message on this branch carries a suppression token.")

    if not checked_anything:
        # Never exit 0 having checked nothing. This repo has been bitten by a
        # guard whose cheap early-exit was reached on every real run.
        print("ERROR: nothing to check. Pass --title/--body, --from-env, "
              "or --commits-from.", file=sys.stderr)
        return 2

    return rc


if __name__ == "__main__":
    sys.exit(main())
