#!/usr/bin/env python
"""Forced-failure test for check-skip-ci-marker.py.

A guard seen only in its passing state has not been shown to work: green is
equally consistent with "no marker present" and "the check never fires".
Every case below that MUST fail is run and observed failing, and the
negative controls prove it is not simply failing on everything.

The real #354 body sentence is reproduced as the headline case, because
that is the shape that got through: not a marker used as an instruction,
but one quoted inside prose explaining another workflow.

Run: python scripts/test-skip-ci-marker.py     (exit 0 = pass)
"""
import importlib.util
import io
import os
import sys
from contextlib import redirect_stdout

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "guard", os.path.join(HERE, "check-skip-ci-marker.py"))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

# Built the same way the guard builds them, so this file carries no literal
# marker either -- otherwise running the guard over this repo's own tree, or
# quoting this test in a PR, would trip it.
S, C, N, A = "skip", "ci", "no", "actions"
M = f"[{S} {C}]"
M_REV = f"[{C} {S}]"
M_NO = f"[{N} {C}]"
M_ACT = f"[{S} {A}]"

failures = 0


def check(cond, msg):
    global failures
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures += 1


def run(title=None, body=None):
    """Return (exit_code, captured_output)."""
    argv = []
    if title is not None:
        argv += ["--title", title]
    if body is not None:
        argv += ["--body", body]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = guard.main(argv)
    return rc, buf.getvalue()


print("1. THE CASE THAT ACTUALLY HAPPENED (#354, 2026-08-29)")
real = ("The file the work panel reads. NOTE: update-game-data.yml commits this "
        f"with {M}, so no push event fires and a push-triggered guard never sees it.")
rc, out = run(title="front page: the development panel counted PRs as issues", body=real)
check(rc == 1, "a marker quoted inside an explanatory sentence is caught")
check("body line 1" in out, "the failure names where it is")
check("skip-CI marker" in out, "and says how to refer to it instead")

print("\n2. Every marker GitHub honours")
for name, mk in [("skip ci", M), ("ci skip", M_REV), ("no ci", M_NO), ("skip actions", M_ACT)]:
    rc, _ = run(body=f"some text {mk} more text")
    check(rc == 1, f"{name} is caught")

print("\n3. Markdown does not exempt it -- GitHub matches the token, not the markup")
for label, text in [
    ("inside backticks", f"the workflow commits with `{M}` which is why"),
    ("inside a fenced block", f"```\ngit commit -m 'thing {M}'\n```"),
    ("inside a blockquote", f"> and then it commits with {M}"),
    ("in a table cell", f"| marker | {M} | suppresses everything |"),
    ("upper case", f"some text {M.upper()} more"),
    ("in the TITLE", None),
]:
    if label == "in the TITLE":
        rc, _ = run(title=f"chore: quiet the bot {M}", body="clean body")
    else:
        rc, _ = run(body=text)
    check(rc == 1, f"{label}: caught")

print("\n4. NEGATIVE CONTROLS -- it must not fail on everything")
for label, text in [
    ("the recommended phrasing", "Refer to it as the skip-CI marker instead of quoting it."),
    ("a bare word 'skip'", "We skip the slow test on PRs."),
    ("a bare word 'ci'", "CI is green on this branch."),
    ("brackets without the token", "[skip the queue] and [ci-adjacent] are fine."),
    ("a SHA reference", "The marker is in commit d3556d1e, see that message."),
    ("hyphenated", "The skip-ci-marker guard lives in scripts/."),
    ("empty body", ""),
]:
    rc, out = run(title="a normal title", body=text)
    check(rc == 0, f"{label}: allowed")

print("\n5. Shape of the contract")
rc, out = run(title="clean", body="clean")
check(rc == 0 and "OK:" in out, "a clean PR exits 0 and says so")
check(len(guard.find_markers(f"{M} and {M_REV}")) == 2, "every occurrence is reported, not just the first")
check(guard.find_markers("") == [], "empty text finds nothing")
check(guard.find_markers(None) == [], "None is tolerated (an empty PR body is null, not '')")

print()
if failures:
    print(f"FAIL: {failures} check(s) failed")
    sys.exit(1)
print("OK: the guard fires on every marker GitHub honours, in title or body,")
print("    inside markdown, and stays quiet on text that merely mentions it.")
