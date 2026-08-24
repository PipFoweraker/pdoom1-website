#!/usr/bin/env python
"""Forced-failure test: the /issues/ surface guard must be able to go red.

check-issues-surface.py passes on the committed cache. Green is equally
consistent with "the surface is honest" and "the check never looks", and this
repo has shipped the second kind before. So this drives it against caches that
are wrong in each way it claims to catch, and asserts it fails.

It also pins the two things that made the original defect invisible:
  - `count` and `len(issues)` can NEVER disagree, so a check comparing them
    verifies nothing. The guard must require a SEPARATELY SOURCED total.
  - a missing total must read as UNKNOWN, never as the sample size.

Run: python scripts/test-issues-surface.py
"""

import copy
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "chk", REPO_ROOT / "scripts" / "check-issues-surface.py")
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

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


REAL_CACHE = json.loads(chk.CACHE.read_text(encoding="utf-8"))
REAL_PAGE = chk.PAGE.read_text(encoding="utf-8")
tmp = Path(tempfile.mkdtemp(prefix="issues-surface-"))


def run(cache=None, page=None, write_cache=True):
    """Point the guard at substitutes and return its exit code."""
    cpath, ppath = tmp / "cache.json", tmp / "index.html"
    if write_cache:
        cpath.write_text(
            cache if isinstance(cache, str)
            else json.dumps(cache, indent=2), encoding="utf-8")
    elif cpath.exists():
        cpath.unlink()
    ppath.write_text(REAL_PAGE if page is None else page, encoding="utf-8")
    real_c, real_p = chk.CACHE, chk.PAGE
    chk.CACHE, chk.PAGE = cpath, ppath
    import contextlib, io as _io
    buf = _io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return chk.main()
    finally:
        chk.CACHE, chk.PAGE = real_c, real_p


try:
    print("the committed surface passes")
    ok("exit 0 on what is in the repo", run(REAL_CACHE) == 0)

    print("cannot tell is distinct from clean")
    ok("exit 2 when the cache is absent", run(write_cache=False) == 2)
    ok("exit 2 on malformed JSON", run("{not json") == 2)
    ok("exit 2 when the cache is a list, not an object", run([1, 2, 3]) == 2)

    print("THE DEFECT ITSELF -- a sample size passing as a count")
    # The exact pre-2026-08-24 shape: issues + count + last_updated, nothing else.
    # `count` equals len(issues) by construction, which is why nothing noticed.
    legacy = {"issues": REAL_CACHE["issues"], "count": len(REAL_CACHE["issues"]),
              "last_updated": REAL_CACHE["last_updated"]}
    ok("exit 1 on the legacy cache shape", run(legacy) == 1)
    ok("`count` == len(issues) in that shape, so a check comparing them "
       "would have passed", legacy["count"] == len(legacy["issues"]))

    print("a missing or bad total is caught")
    c = copy.deepcopy(REAL_CACHE); c.pop("total_open_issues")
    ok("exit 1 when total_open_issues is absent", run(c) == 1)
    c = copy.deepcopy(REAL_CACHE); c["total_open_issues"] = "205"
    ok("exit 1 when the total is a string", run(c) == 1)
    c = copy.deepcopy(REAL_CACHE); c["total_open_issues"] = 2
    ok("exit 1 when the total is smaller than the sample", run(c) == 1)

    print("null total is ALLOWED -- it means unknown, and the page says unknown")
    c = copy.deepcopy(REAL_CACHE); c["total_open_issues"] = None
    ok("exit 0 with a null total", run(c) == 0,
       "null must be permitted or the producer's only option on a failed "
       "fetch is to invent a number")

    print("sample labelling, timestamp, PRs and bodies")
    c = copy.deepcopy(REAL_CACHE); c.pop("sample_size")
    ok("exit 1 without sample_size", run(c) == 1)
    c = copy.deepcopy(REAL_CACHE); c["sample_size"] = 999
    ok("exit 1 when sample_size disagrees with the array", run(c) == 1)
    c = copy.deepcopy(REAL_CACHE); c["last_updated"] = ""
    ok("exit 1 without a real timestamp", run(c) == 1)
    c = copy.deepcopy(REAL_CACHE)
    c["issues"] = c["issues"] + [{"number": 1, "pull_request": {"url": "x"}}]
    c["sample_size"] = len(c["issues"])
    ok("exit 1 when a pull request is in the sample", run(c) == 1)
    c = copy.deepcopy(REAL_CACHE)
    if c["issues"]:
        c["issues"][0]["body"] = "some third party's prose"
    ok("exit 1 when an item still carries `body`", run(c) == 1)

    print("the page must not assert health from an absence")
    bad_page = REAL_PAGE.replace(
        "<title>", "<div>No open issues! Everything is working smoothly.</div><title>", 1)
    ok("exit 1 when the page renders the health claim", run(REAL_CACHE, bad_page) == 1)

    print("...and the scan must not fire on a COMMENT about it")
    # The first version of the guard matched the whole file and failed on
    # index.html's own comment explaining the removed sentence -- which would have
    # forced the fix "stop documenting the defect".
    commented = REAL_PAGE.replace(
        "<title>",
        "<!-- No open issues! Everything is working smoothly. -->\n"
        "\t\t\t\t\t\t// No open issues! Everything is working smoothly.\n<title>", 1)
    ok("exit 0 when the phrase appears only in HTML and JS comments",
       run(REAL_CACHE, commented) == 0,
       "the guard is matching its own documentation")
    ok("stripping comments does not eat the page",
       "https://" in chk._strip_comments(REAL_PAGE),
       "a naive // split would delete every URL and pass by emptying the file")

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
