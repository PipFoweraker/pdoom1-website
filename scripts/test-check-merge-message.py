#!/usr/bin/env python
"""Force check-merge-message.py into every failing state and observe it.

A guard seen only in its passing state has not been shown to work: green is
equally consistent with "the input is clean" and "the check never fires". Every
case below constructs an input that MUST be refused and asserts the refusal.

The suppression literals are assembled from parts here for the same reason they
are in the guard -- so this file, its diff, and any commit message quoting it can
be pasted anywhere without triggering the thing under test. A test that cannot be
discussed safely is a test people stop running.
"""

import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
cmm = importlib.import_module("check-merge-message")

_O, _C = chr(91), chr(93)


def tok(bare):
    """Build a bracketed suppression token without writing one literally."""
    return _O + bare + _C


FAILURES = []
CHECKS = 0


def expect(label, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        FAILURES.append(label)


def run_guard(argv):
    """Call main() and capture (exit_code, stdout)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmm.main(argv)
    return rc, buf.getvalue()


print("=" * 78)
print("FORCED-FAILURE SUITE -- check-merge-message.py")
print("=" * 78)

# --- 1. the #244 shape: the marker inside the PR BODY ------------------------
print("\n-- the #244 shape: an explanatory PR body that quotes the marker")
body = (
    "This PR fixes the events sync.\n\n"
    "Note that sync-events.yml commits with " + tok("skip ci") + " so the\n"
    "content-honesty guard never sees its output.\n"
)
rc, out = run_guard(["--title", "fix: the events sync", "--body", body])
expect("a marker in the BODY is refused", rc == 1, "(rc=%d)" % rc)
expect("the refusal names the squash-message mechanism",
       "squash commit message" in out)
expect("the refusal explains the cost is a missed deploy", "missed DEPLOY" in out)

# --- 2. backticks do not defang it -------------------------------------------
print("\n-- backticks and code fences must NOT be treated as defanging")
rc, _ = run_guard(["--title", "t", "--body", "the marker is `" + tok("skip ci") + "` here"])
expect("inside backticks is still refused", rc == 1)
rc, _ = run_guard(["--title", "t", "--body", "```\n" + tok("ci skip") + "\n```"])
expect("inside a fenced block is still refused", rc == 1)

# --- 3. every token variant GitHub honours -----------------------------------
print("\n-- every honoured variant, not just the common one")
for bare in ("skip ci", "ci skip", "no ci", "skip actions", "actions skip"):
    rc, _ = run_guard(["--title", "t", "--body", "x " + tok(bare) + " y"])
    expect("variant %-14s refused" % repr(bare), rc == 1)

# --- 4. case and separator insensitivity -------------------------------------
print("\n-- case and separator variance")
for variant in (tok("SKIP CI"), tok("Skip Ci"), tok("skip  ci"), tok("skip-ci"), tok("skip_ci")):
    rc, _ = run_guard(["--title", "t", "--body", "x " + variant + " y"])
    expect("variant %-12s refused" % variant, rc == 1)

# --- 5. the marker in the TITLE ----------------------------------------------
print("\n-- the title is half of the squash message too")
rc, _ = run_guard(["--title", "chore: sync " + tok("skip ci"), "--body", "clean body"])
expect("a marker in the TITLE is refused", rc == 1)

# --- 6. split across the title/body boundary ---------------------------------
print("\n-- a token must not be creatable by the title/body join")
rc, _ = run_guard(["--title", "trailing " + _O + "skip", "--body", "ci" + _C + " leading"])
expect("a token split across the join is NOT falsely refused "
       "(the join inserts blank lines, so this is genuinely two strings)", rc == 0)

# --- 7. the skip-checks trailer ----------------------------------------------
print("\n-- the non-bracketed trailer form")
rc, _ = run_guard(["--title", "t", "--body", "some text\nskip-checks: true\n"])
expect("skip-checks trailer refused", rc == 1)
rc, _ = run_guard(["--title", "t", "--body", "we never use skip-checks: false here"])
expect("skip-checks: false is NOT refused", rc == 0)

# --- 8. the guard must not fire on safe discussion ---------------------------
print("\n-- the approved way of talking about it must stay usable")
safe = (
    "This commit is described in CLAUDE.md as carrying the skip-CI marker.\n"
    "See commit d3556d1e. Do not reintroduce that suppression.\n"
    "Grep with: grep -rn 'skip ci' .github/workflows/\n"
)
rc, out = run_guard(["--title", "docs: name the skip-CI marker", "--body", safe])
expect("prose naming the marker, and a bare grep pattern, are allowed", rc == 0,
       "(rc=%d) -- a guard that blocks the sanctioned workaround forces people "
       "to route around it" % rc)

# --- 9. never exit 0 having checked nothing ----------------------------------
print("\n-- the cheap-early-exit trap this repo already has a scar from")
rc, _ = run_guard([])
expect("no input at all is usage error (2), not a silent green", rc == 2,
       "(rc=%d)" % rc)

# --- 10. empty body is clean, not an error -----------------------------------
print("\n-- an empty body is legitimately clean")
rc, _ = run_guard(["--title", "chore: bump", "--body", ""])
expect("empty body passes", rc == 0)

# --- 11. commit-message mode (rebase/merge-commit path) ----------------------
print("\n-- commit messages matter too when the merge is not a squash")
proc = subprocess.run(
    [sys.executable, str(Path(__file__).resolve().parent / "check-merge-message.py"),
     "--commits-from", "-"],
    input="feat: a thing\n\nbody mentioning " + tok("skip ci") + "\n",
    capture_output=True, text=True, encoding="utf-8",
)
expect("a marker in a commit message is refused via --commits-from",
       proc.returncode == 1, "(rc=%d)" % proc.returncode)

# --- 12. this test file and the guard are themselves safe to quote -----------
print("\n-- the guard and its test must not contain a literal token")
here = Path(__file__).resolve().parent
for name in ("check-merge-message.py", "test-check-merge-message.py"):
    text = (here / name).read_text(encoding="utf-8")
    findings = cmm.find_suppressors(text)
    expect("%s contains no literal suppression token" % name,
           not findings,
           "found %r" % (findings[:2],))

print("")
print("=" * 78)
if FAILURES:
    print("FAIL: %d of %d checks failed: %s" % (len(FAILURES), CHECKS, ", ".join(FAILURES)))
    sys.exit(1)
print("OK: %d checks -- every suppression shape was forced and observed refused,"
      % CHECKS)
print("    and the sanctioned way of naming the marker still passes.")
sys.exit(0)
