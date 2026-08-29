#!/usr/bin/env python
"""Refuse a PR whose TITLE or BODY carries a CI-skip marker.

WHY THIS EXISTS, AND WHY CHECKING AFTERWARDS WAS NOT ENOUGH
`gh pr merge --squash` and the GitHub UI's squash button compose the merge
commit message from the PR title plus the PR BODY. GitHub then matches a
CI-skip marker anywhere in that message -- including inside backticks, and
including a sentence that is merely *explaining* one -- and runs NOTHING.
Not skipped, not queued: the workflow runs do not exist.

That is not hypothetical here. It has now happened twice:

  #244 (2026-08-02) discussed sync-events.yml's own marker three times in
  its body. Its merge commit d3556d1e ran 1 check run where its neighbours
  ran 8, 9 and 15.

  #354 (2026-08-29) explained update-game-data.yml's use of one in a single
  sentence -- "update-game-data.yml commits with <marker>, so no push
  event fires". Its merge commit ran ZERO check runs. Five files under
  public/ changed and Auto-Deploy never fired, so pdoom1.com kept serving
  the previous bytes until a human dispatched the manual deploy.

CLAUDE.md already prescribed checking the check-run count AFTER a squash
merge. That is detection, and by the time it fires the deploy has already
been skipped; recovery is a manual rsync to production. This checks the
thing that causes it, while it is still an edit to a text box.

THE DAMAGE IS A MISSED DEPLOY, NOT A MISSED TEST. The PR's own CI is green
-- suppression happens at merge, after every gate anyone was watching.

Usage:
    python scripts/check-skip-ci-marker.py --title "$T" --body "$B"
    python scripts/check-skip-ci-marker.py --file message.txt
    echo "$MSG" | python scripts/check-skip-ci-marker.py

Exit 0 = clean. Exit 1 = a marker is present. Exit 2 = bad invocation.
"""
import argparse
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

# Assembled from fragments rather than written out, so this file does not
# itself contain a literal marker. It gets quoted into commit messages and
# release notes like any other source file, and a guard that trips the thing
# it guards against is a bad joke waiting to happen.
_SKIP = "skip"
_CI = "ci"
_NO = "no"
_ACTIONS = "actions"

# The set GitHub actually honours, per its own docs. Order within the
# brackets varies, so both are listed rather than guessed at.
MARKERS = [
    f"[{_SKIP} {_CI}]",
    f"[{_CI} {_SKIP}]",
    f"[{_NO} {_CI}]",
    f"[{_SKIP} {_ACTIONS}]",
    f"[{_ACTIONS} {_SKIP}]",
    f"***{_NO}_{_CI}***",
]

# GitHub matches the literal token anywhere in the message. Backticks, code
# fences and blockquotes do NOT exempt it, which is exactly why a PR that
# only DESCRIBES a marker still suppresses its own merge. So the pattern is
# deliberately unanchored and case-insensitive, and no attempt is made to
# skip over markdown -- matching GitHub's behaviour, not markdown's.
PATTERN = re.compile("|".join(re.escape(m) for m in MARKERS), re.IGNORECASE)


def find_markers(text):
    """[(line_number, line_text, matched_token)] for every marker in text."""
    hits = []
    for n, line in enumerate((text or "").splitlines(), 1):
        for m in PATTERN.finditer(line):
            hits.append((n, line.strip(), m.group(0)))
    return hits


def report(where, text):
    hits = find_markers(text)
    for n, line, token in hits:
        shown = line if len(line) <= 100 else line[:97] + "..."
        print(f"  {where} line {n}: {shown}")
        print(f"      ^ contains {token!r}")
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--title", default=None)
    ap.add_argument("--body", default=None)
    ap.add_argument("--file", default=None,
                    help="read the whole message from this file")
    args = ap.parse_args(argv)

    parts = []
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                parts.append(("message", f.read()))
        except OSError as exc:
            print(f"FAIL: cannot read {args.file}: {exc}")
            return 2
    if args.title is not None:
        parts.append(("title", args.title))
    if args.body is not None:
        parts.append(("body", args.body))
    if not parts:
        data = sys.stdin.read()
        parts.append(("stdin", data))

    hits = []
    for where, text in parts:
        hits += report(where, text)

    if not hits:
        print("OK: no CI-skip marker in the pull request title or body.")
        print("    The squash commit message composed from them will run CI normally.")
        return 0

    print()
    print(f"FAIL: {len(hits)} CI-skip marker(s) in text that becomes the squash "
          "commit message.")
    print()
    print("  Squash-merging this PR would compose its commit message from the title")
    print("  plus the body, and GitHub would then run NOTHING on the merge commit --")
    print("  not skipped, not queued, absent. Auto-Deploy is one of the workflows")
    print("  that would not fire, so anything this PR changes under public/ would")
    print("  not reach pdoom1.com until someone noticed and deployed by hand.")
    print()
    print("  A marker inside backticks or a code fence still counts. GitHub matches")
    print("  the token, not the markdown, so merely EXPLAINING one is enough.")
    print()
    print("  FIX: edit the pull request title or body so the token is not present.")
    print("  Refer to it as the skip-CI marker, or name the commit SHA that carries")
    print("  it. Do not quote the token itself, not even inside backticks.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
