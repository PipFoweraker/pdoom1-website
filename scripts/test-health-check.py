#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Destructive tests for scripts/health-check.py.

# WHY THIS EXISTS
# ---------------
# health-check.py writes public/data/health-check-results.json. health-checks.yml
# runs it on a 6-hourly cron and COMMITS the result, so whatever it says is served
# from pdoom1.com. Its apparent test coverage was fake: test-orchestrator.py and
# test-integration.py both name it, but both merely shell out to it against the real
# repo and check the exit code. Neither looks at a single byte it publishes.
#
# The thing it publishes has already been a privacy incident. A cp1252
# UnicodeEncodeError traceback -- which names the interpreter's own
# encodings/cp1252.py -- was captured into a published JSON file and served from
# pdoom1.com, exposing the maintainer's OS username and local directory layout
# ("C:\\Users\\<name>\\Documents\\A Local Code\\..."). rel() and scrub() were added
# in response, with the docstring rule "Never interpolate a raw filepath into a
# result message -- call this instead."
#
# THE HOLE THIS LOCKS DOWN (found 2026-08-01)
# -------------------------------------------
# That rule was enforced by everyone remembering it, and four handlers did not:
#
#   test_json_valid:              f"Error reading {shown}: {e}"
#   test_script_executable:       f"Error testing script: {e}"
#   test_version_data_integrity:  f"Could not parse timestamp: {e}"
#                                 f"Error validating data: {e}"
#
# `shown` is scrubbed; `{e}` is not. str(OSError) embeds the absolute path it failed
# on, so a permission error or an unreadable file re-published exactly the class of
# string the guard exists to remove -- through the guard, on a cron, to a public URL.
#
# The fix was to scrub at the ONE chokepoint every message passes through
# (log_result) instead of at each call site. This file is the evidence, and section
# 2 asserts it as a rule over the whole published document rather than as four named
# messages: it runs the regex over every string anywhere in the output. A fifth
# handler added next year is covered on the day it is written.
#
# WHAT IS DELIBERATELY NOT ASSERTED
# ---------------------------------
# No test here pins a file count, a version, a date, or a success percentage. Those
# move. Section 4 asserts the arithmetic RELATIONSHIP between the summary counters
# instead, which does not.
#
# HOW IT ISOLATES
# ---------------
# Every case builds a repo-shaped tree in a temp dir and points the checker's
# base_dir / public_dir / data_dir at it. No test reads or writes the real public/,
# and nothing here touches the network.
#
# Run:  python scripts/test-health-check.py     (exit 0 = pass)
"""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "health_check", ROOT / "scripts" / "health-check.py")
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


# The shapes that actually leaked, plus the ones that would.
SECRET_PATHS = [
    r"C:\Users\gday\Documents\A Local Code\pdoom1-website\public\data\version.json",
    r"C:\Users\gday\AppData\Local\Programs\Python\Python311\lib\encodings\cp1252.py",
    "/home/runner/work/pdoom1-website/pdoom1-website/public/data/version.json",
    "/Users/pip/Code/pdoom1-website/scripts/health-check.py",
    "/var/folders/xx/T/tmpabc123/version.json",
    "/root/.ssh/config",
]
# The identifying fragments that must never survive. Usernames and directory
# layout are the payload; the basename is harmless and is what scrub() keeps.
SECRETS = ["gday", "AppData", "Documents", "A Local Code", "/home/runner",
           "/Users/pip", "/var/folders", "/root", "Python311"]


def strings_in(value):
    """Every string anywhere in a nested structure, keys included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from strings_in(v)


class FakeRepo:
    """A repo-shaped temp tree with a checker pointed at it."""

    def __init__(self, version_json=None, extra=None):
        self.version_json = version_json
        self.extra = extra or {}

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "public" / "data").mkdir(parents=True)
        (self.tmp / "scripts").mkdir()
        (self.tmp / "public" / "index.html").write_text("<html></html>", encoding="utf-8")
        (self.tmp / "public" / "config.json").write_text("{}", encoding="utf-8")
        (self.tmp / "public" / "data" / "changes.json").write_text("[]", encoding="utf-8")
        if self.version_json is not None:
            (self.tmp / "public" / "data" / "version.json").write_text(
                self.version_json, encoding="utf-8")
        for rel, body in self.extra.items():
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

        self.c = hc.HealthChecker()
        self.c.base_dir = str(self.tmp)
        self.c.public_dir = str(self.tmp / "public")
        self.c.data_dir = str(self.tmp / "public" / "data")
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False

    def run(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            return self.c.run_all_checks()

    def published(self):
        p = self.tmp / "public" / "data" / "health-check-results.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


GOOD_VERSION = json.dumps({
    "latest_release": {"version": "v1.0.0", "name": "n",
                       "published_at": "2030-01-01T00:00:00Z", "html_url": "u"},
    "repository_stats": {"stars": 1},
    "game_stats": {"baseline_doom_percent": None, "frontier_labs_count": 5,
                   "strategic_possibilities": None},
    "last_updated": "2030-01-01T00:00:00",
})


# =========================================================================== 1
print("\n1. scrub() removes an absolute path wherever it appears in free text")

for p in SECRET_PATHS:
    out = hc.HealthChecker.scrub(f"[Errno 13] Permission denied: '{p}'")
    check(not any(s in out for s in SECRETS),
          f"nothing identifying survives: {p[:44]}")
    check(os.path.basename(p.rstrip("\\/")) in out,
          f"the BASENAME survives, so the message still says which file: {p[:34]}")

check(hc.HealthChecker.scrub("public/data/version.json") == "public/data/version.json",
      "a repo-relative path is left alone -- scrubbing is not blanket deletion")
check("cp1252.py" in hc.HealthChecker.scrub(
    r'  File "C:\Python311\lib\encodings\cp1252.py", line 19, in encode'),
    "the real traceback line reduces to a basename")
check(hc.HealthChecker.scrub(OSError(2, "no such file", "/home/runner/x/y.json")),
      "scrub accepts a non-str (an exception object) without raising")


# =========================================================================== 2
print("\n2. THE RULE: no absolute path can reach the published document, from ANY handler")

# Force every failure branch at once, and force them with path-bearing errors.
# unreadable.json is a directory named like a file: open() on it raises IsADirectoryError
# / PermissionError whose str() carries the absolute path -- the exact leak shape.
with FakeRepo(version_json='{"bad json"') as fr:
    (Path(fr.c.data_dir) / "changes.json").unlink()
    (Path(fr.c.data_dir) / "changes.json").mkdir()
    (Path(fr.c.base_dir) / "scripts" / "update-version-info.py").write_text(
        "def broken(:\n", encoding="utf-8")   # syntax error -> py_compile traceback
    summary = fr.run()
    doc = fr.published()

    check(doc is not None, "a failing run still publishes a results file")
    check(summary["overall_status"] == "FAIL", "and it says FAIL")

    offenders = []
    for s in strings_in(doc):
        if hc.HealthChecker._ABS_PATH.search(s):
            offenders.append(s[:110])
    check(not offenders,
          f"no string ANYWHERE in the published JSON matches an absolute path "
          f"(offenders: {offenders[:2]})")

    blob = json.dumps(doc)
    leaked = [s for s in SECRETS if s in blob]
    check(not leaked, f"no username or directory-layout fragment survives ({leaked})")

    # Guard against the test passing because nothing was recorded at all.
    check(len(summary["failed_test_details"]) >= 2,
          f"the run actually recorded failures to scrub "
          f"({len(summary['failed_test_details'])} of them)")

# The same rule, aimed straight at the four handlers, via log_result's chokepoint.
for p in SECRET_PATHS:
    with FakeRepo(version_json=GOOD_VERSION) as fr:
        fr.c.log_result(f"Test at {p}", False, f"[Errno 13] Permission denied: '{p}'")
        rec = fr.c.results[-1]
        check(not hc.HealthChecker._ABS_PATH.search(rec["message"]),
              f"log_result scrubs the MESSAGE it was handed: {p[:38]}")
        check(not hc.HealthChecker._ABS_PATH.search(rec["test"]),
              f"log_result scrubs the TEST NAME too: {p[:38]}")
        check(not any(hc.HealthChecker._ABS_PATH.search(s) for s in fr.c.failed_tests),
              "the aggregated failure list is clean as well")


# =========================================================================== 3
print("\n3. rel() never emits anything above the repo root")

with FakeRepo(version_json=GOOD_VERSION) as fr:
    inside = os.path.join(fr.c.public_dir, "data", "version.json")
    check(fr.c.rel(inside) == "public/data/version.json",
          "a path inside the repo becomes a forward-slashed relative path")
    check("\\" not in fr.c.rel(inside),
          "backslashes are normalised, so the published string is platform-neutral")
    # A path on another drive has no relative form. The fallback must be a basename,
    # not the original absolute path.
    other = fr.c.rel(r"Z:\Someone Else\secret\thing.json")
    check(not hc.HealthChecker._ABS_PATH.search(other),
          f"a cross-drive path degrades to something non-absolute (got {other!r})")
    check(fr.c.rel(None) and not hc.HealthChecker._ABS_PATH.search(fr.c.rel(None)),
          "rel(None) returns a harmless string rather than raising")


# =========================================================================== 4
print("\n4. The summary reports what happened, not a shape decided in advance")

with FakeRepo(version_json=GOOD_VERSION) as fr:
    summary = fr.run()
    n = summary["total_tests"]
    check(n == len(summary["results"]), "total_tests equals the number of results recorded")
    check(summary["passed_tests"] + summary["failed_tests"] == n,
          "passed + failed == total (the counters are derived, not asserted)")
    expected_rate = summary["passed_tests"] / n * 100 if n else 0
    check(abs(summary["success_rate"] - expected_rate) < 1e-9,
          "success_rate is computed from the counters, not stated")
    check((summary["overall_status"] == "PASS")
          == (len(summary["failed_test_details"]) == 0),
          "overall_status is PASS iff nothing non-warning failed")

# A warning must stay visible as a warning. Recording an unmeasurable thing as a
# silent pass is how "we could not check" becomes indistinguishable from "it is fine".
with FakeRepo(version_json=json.dumps({
        "latest_release": {"version": "v1", "name": "n", "published_at": "p", "html_url": "u"},
        "repository_stats": {}, "game_stats": {"baseline_doom_percent": None,
                                               "frontier_labs_count": None,
                                               "strategic_possibilities": None},
        "last_updated": "not-a-timestamp"})) as fr:
    summary = fr.run()
    warned = [r for r in summary["results"] if r["is_warning"]]
    check(warned, "an unparseable timestamp is recorded, not swallowed")
    check(summary["warnings"] == len(summary["warnings_details"]),
          "the warning count matches the warning list")
    check(all("not-a-timestamp" not in json.dumps(r) or r["is_warning"]
              for r in summary["results"]),
          "the un-checkable case is flagged as a warning rather than a bare pass")


# =========================================================================== 5
print("\n5. A missing or malformed version.json is reported, never assumed fine")

with FakeRepo() as fr:  # no version.json at all
    summary = fr.run()
    check(summary["overall_status"] == "FAIL", "absent version.json fails the run")
    check(any("not found" in d.lower() or "missing" in d.lower()
              for d in summary["failed_test_details"]),
          "and says what is missing")

# Absence of a required field is a failure, and the check must not name only the
# fields someone thought of at the time: drop each required field in turn.
BASE = json.loads(GOOD_VERSION)
for field in ("latest_release", "repository_stats", "game_stats", "last_updated"):
    partial = {k: v for k, v in BASE.items() if k != field}
    with FakeRepo(version_json=json.dumps(partial)) as fr:
        summary = fr.run()
        check(summary["overall_status"] == "FAIL",
              f"version.json missing {field!r} fails the run")
        check(field in json.dumps(summary["failed_test_details"]),
              f"and names {field!r} as the missing one")

with FakeRepo(version_json="{not json at all") as fr:
    summary = fr.run()
    check(summary["overall_status"] == "FAIL", "malformed version.json fails the run")
    doc = fr.published()
    check(not any(hc.HealthChecker._ABS_PATH.search(s) for s in strings_in(doc)),
          "and the JSONDecodeError path publishes no absolute path either")


print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: health-check publishes no absolute path from any handler, and its summary "
      "counters are derived rather than asserted.")
