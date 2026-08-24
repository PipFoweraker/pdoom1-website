#!/usr/bin/env python
"""Forced-failure test: the syndication-docs guard must be able to go red.

check-syndication-docs.py passes today. Green is equally consistent with "the
document is complete" and "the check never looks at anything" -- and this repo
has shipped the second kind before (check-platform-claims.py returned 0 before
opening a single page). So this drives it against documents that are wrong in
each of the three ways it claims to catch, and asserts it fails.

Run: python scripts/test-check-syndication-docs.py
"""

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "checkdocs", REPO_ROOT / "scripts" / "check-syndication-docs.py")
checkdocs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checkdocs)

PASS = 0
FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" -> " + str(detail)) if detail else ""))


REAL_DOC = checkdocs.DOC.read_text(encoding="utf-8")
tmp = Path(tempfile.mkdtemp(prefix="syndocs-test-"))


def run_against(text):
    """Point the checker at a substitute document and return its exit code."""
    path = tmp / "doc.md"
    path.write_text(text, encoding="utf-8")
    real = checkdocs.DOC
    checkdocs.DOC = path
    try:
        return checkdocs.main()
    finally:
        checkdocs.DOC = real


try:
    print("the real document passes")
    ok("exit 0 on the committed doc", run_against(REAL_DOC) == 0)

    print("a missing credential is caught")
    # The exact historical defect: everything documented except the token whose
    # absence 503s every endpoint.
    without_token = "\n".join(
        line for line in REAL_DOC.splitlines()
        if "SYNDICATION_TOKEN" not in line)
    ok("exit 1 when SYNDICATION_TOKEN is not named",
       run_against(without_token) == 1)

    print("the wrong side is caught")
    # Named, but filed as a GitHub secret only -- the half-setup that yields a
    # green workflow and a 401.
    wrong_side = REAL_DOC.replace(
        "| `BLUESKY_HANDLE` | **Netlify** site env |",
        "| `BLUESKY_HANDLE` | **GitHub** secret |")
    ok("the substitution actually changed the text",
       wrong_side != REAL_DOC,
       "the table row moved; update this test, not the guard")
    ok("exit 1 when a Netlify value is documented as a GitHub secret",
       run_against(wrong_side) == 1)

    print("an empty document is caught")
    ok("exit 1 on an empty doc", run_against("# nothing here\n") == 1)

    print("the derivation itself is not vacuous")
    need = checkdocs.collect()
    ok("at least one credential was derived from the code", len(need) >= 3,
       len(need))
    ok("SYNDICATION_TOKEN is derived as needing BOTH sides",
       need.get("SYNDICATION_TOKEN", {}).get("sides") == {"github", "netlify"},
       need.get("SYNDICATION_TOKEN"))
    ok("report-bug.js credentials are OUT of scope",
       "HCAPTCHA_SECRET" not in need and "GITHUB_DISPATCH_TOKEN" not in need,
       sorted(need))

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
