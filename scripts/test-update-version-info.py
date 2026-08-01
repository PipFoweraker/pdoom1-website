#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Destructive tests for scripts/update-version-info.py.

# WHY THIS EXISTS
# ---------------
# update-version-info.py writes public/data/version.json and public/data/status.json
# and REWRITES public/index.html in place. version.json is the source of truth for
# the download buttons, /game-changelog/, and -- via latest_release.platforms -- for
# check-platform-claims.py, the guard that stops a page advertising an OS with no
# build. Two workflows run it on 6-hourly crons and COMMIT the result
# (auto-update-data.yml, health-checks.yml). It had no test.
#
# The apparent coverage was fake. test-orchestrator.py and test-integration.py both
# reference this script, but neither asserts anything about its output: they shell
# out to it and check the exit code, against the LIVE GitHub API, writing into the
# real public/ tree. A run that fetched garbage and wrote it would pass both.
#
# Four claimed safety properties, all of which were prose until now:
#
#   1. "Refusing to write a guessed version"  -- a literal fallback ships exactly
#      when the lookup failed, i.e. when nobody is watching.
#   2. "Refusing to publish zeroes as if they were measured" -- 0 stars is a claim,
#      not an absence of one.
#   3. status.json is not clobbered when the release lookup fell back.
#   4. platforms is DERIVED from the release's attached assets.
#
# Plus three defects this file was written to lock down after finding them
# (2026-08-01):
#
#   * 'x86_64' is an architecture, not an OS. `PDoom-v0.13.1-macos-x86_64.dmg`
#     matched the linux pattern as well as the macos one, so a Mac-only release
#     would have published platforms.linux: true -- handing check-platform-claims.py
#     a false positive, in the one field that exists to stop false platform claims.
#   * game_stats was hardcoded to {baseline_doom_percent: 23, frontier_labs_count: 7,
#     strategic_possibilities: 10000} on every run. calculate-game-stats.py writes the
#     same file and deliberately nulls two of those with a "not yet measured"
#     explanation, carrying the comment "DO NOT restore a literal here 'temporarily'.
#     That is exactly how these two survived for months." This script was the thing
#     restoring them, and it wins whenever it runs last.
#   * The version string is a GitHub tag_name -- upstream data -- and was passed as
#     the REPLACEMENT TEMPLATE of re.sub() while rewriting index.html. \\1 or \\g<0>
#     in a tag was interpreted; a lone backslash raised re.error mid-rewrite.
#
# ASSERTING THE RULE, NOT AN ENUMERATION
# --------------------------------------
# Section 1 does not list the platform keys it expects. It asserts the invariant
# "every key in the result is a key of _PLATFORM_PATTERNS, and a platform is true
# iff some attached asset is a build for that OS and no other" over a table of asset
# names. A fourth platform added tomorrow is covered without editing a list.
#
# Nothing here is compared against a moving value. The deployed version is READ from
# the fixture the test built, never pinned to a literal -- test_ingest_scores.py
# pinned v0.11.0 against a rule about the deployed version and stayed red for three
# releases.
#
# HOW IT ISOLATES
# ---------------
# fetch_github_data is replaced with a stub and DATA_DIR is redirected into a temp
# dir for every case. No test issues an HTTP request or touches public/.
#
# Run:  python scripts/test-update-version-info.py     (exit 0 = pass)
"""

import importlib.util
import io
import json
import os
import re
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
    "update_version_info", ROOT / "scripts" / "update-version-info.py")
uvi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uvi)

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


class Sandbox:
    """Redirect DATA_DIR into a temp dir and stub the GitHub API.

    `api` maps an endpoint substring -> payload. A missing entry means the fetch
    failed, which is how every refusal path below is forced.
    """

    def __init__(self, api=None, version_json=None, status_json=None):
        self.api = api or {}
        self.version_json = version_json
        self.status_json = status_json

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved_dir = uvi.DATA_DIR
        self._saved_fetch = uvi.fetch_github_data
        uvi.DATA_DIR = str(self.tmp)
        if self.version_json is not None:
            (self.tmp / "version.json").write_text(
                json.dumps(self.version_json), encoding="utf-8")
        if self.status_json is not None:
            (self.tmp / "status.json").write_text(
                json.dumps(self.status_json), encoding="utf-8")

        api = self.api
        uvi.fetch_github_data = lambda endpoint: next(
            (v for k, v in api.items() if k in endpoint), None)
        return self

    def __exit__(self, *a):
        uvi.DATA_DIR = self._saved_dir
        uvi.fetch_github_data = self._saved_fetch
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False

    def read(self, name):
        p = self.tmp / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def quiet(fn, *a, **k):
    """Call fn, swallowing its stdout; return (result_or_exception, output)."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            return fn(*a, **k), buf.getvalue()
    except Exception as exc:  # noqa: BLE001 - the exception IS the assertion
        return exc, buf.getvalue()


RELEASE = {
    "tag_name": "v9.9.9", "name": "P(Doom) v9.9.9",
    "published_at": "2030-01-02T03:04:05Z",
    "html_url": "https://github.com/PipFoweraker/pdoom1/releases/tag/v9.9.9",
    "body": "notes",
    "assets": [{"name": "PDoom-v9.9.9-windows.zip"}],
}
STATS = {"stargazers_count": 8, "forks_count": 1,
         "open_issues_count": 174, "updated_at": "2030-01-01T00:00:00Z"}
FULL_API = {"/releases/latest": RELEASE, "/repos/PipFoweraker/pdoom1": STATS}


# =========================================================================== 1
print("\n1. platforms is DERIVED from attached assets, never asserted")

# name -> the set of platforms that name may legitimately claim.
# The rule under test: an asset counts for an OS iff it is a downloadable build AND
# no OTHER OS is named in the filename. Architecture hints never outvote an OS name.
CASES = [
    ("PDoom-v0.13.0-windows.zip",        {"windows"}),
    ("PDoom.exe",                        {"windows"}),          # v0.13.1 dropped "windows"
    ("PDoom-v0.13.1-macos.dmg",          {"macos"}),
    ("PDoom-v0.13.1-macos-x86_64.dmg",   {"macos"}),            # THE BUG: not linux too
    ("PDoom-osx-x86_64.zip",             {"macos"}),
    ("PDoom-windows-x86_64.zip",         {"windows"}),
    ("PDoom-v0.13.1-linux.tar.gz",       {"linux"}),
    ("PDoom.x86_64",                     {"linux"}),            # Godot linux export
    ("PDoom-v0.13.1.AppImage",           {"linux"}),
    ("README-windows.md",                set()),                # not a build
    ("checksums.txt",                    set()),
    ("Source code (zip)",                set()),
    ("PDoom-windows-and-linux.zip",      {"windows", "linux"}),  # genuinely ambiguous
]

for name, expected in CASES:
    got = uvi.derive_platforms([{"name": name}])
    check(set(uvi._PLATFORM_PATTERNS) == set(got),
          f"result covers exactly the declared platform keys for {name!r}")
    actual = {k for k, v in got.items() if v}
    check(actual == expected,
          f"{name!r} -> {sorted(actual)} (expected {sorted(expected)})")

check(all(v is False for v in uvi.derive_platforms([]).values()),
      "no assets -> every platform False (only ever written on a FRESH fetch)")
check(all(v is False for v in uvi.derive_platforms(None).values()),
      "None assets -> every platform False, no crash")

combined = uvi.derive_platforms(
    [{"name": "PDoom.exe"}, {"name": "PDoom-linux.tar.gz"}])
check(combined == {"windows": True, "macos": False, "linux": True},
      "several assets union correctly, and an ABSENT platform stays False")


# =========================================================================== 2
print("\n2. FORCED FAILURE: a failed release lookup never invents a version")

with Sandbox(api={}) as sb:  # nothing on disk, nothing from the API
    err, _ = quiet(uvi.get_latest_release)
    check(isinstance(err, RuntimeError), f"raises rather than guessing (got {type(err).__name__})")
    check("Refusing" in str(err), "says it is refusing, in those words")
    check(sb.read("version.json") is None, "wrote nothing")

# The version literal in the fixture is arbitrary and local to this test. The RULE
# is "whatever was already on disk comes back unchanged", so it is read, not pinned.
PRIOR = {"latest_release": {"version": "v1.2.3", "html_url": "https://x/tag/v1.2.3",
                            "platforms": {"windows": True, "macos": False, "linux": False}},
         "repository_stats": {"stars": 4, "forks": 0, "open_issues": 9,
                              "last_updated": "2029-01-01T00:00:00Z"},
         "game_stats": {"baseline_doom_percent": None, "frontier_labs_count": 5,
                        "strategic_possibilities": None,
                        "pending": {"baseline_doom_percent": {"status": "not yet measured"}}}}

with Sandbox(api={}, version_json=PRIOR) as sb:
    got, out = quiet(uvi.get_latest_release)
    check(got == PRIOR["latest_release"],
          "a transient API failure preserves the last known-good release verbatim")
    check(got["platforms"] == PRIOR["latest_release"]["platforms"],
          "THE BIG ONE: platforms is PRESERVED, not recomputed to all-False from an "
          "empty asset list -- all-False would read as 'no build ships anywhere'")
    check("preserving" in out.lower(), "says out loud that it preserved rather than fetched")


# =========================================================================== 3
print("\n3. FORCED FAILURE: zeroes are a claim, and are refused")

with Sandbox(api={}) as sb:
    err, _ = quiet(uvi.get_repo_stats)
    check(isinstance(err, RuntimeError), "raises when stats cannot be fetched and none exist")
    check("zeroes" in str(err), "names the specific lie it is refusing to tell")

with Sandbox(api={}, version_json=PRIOR) as sb:
    got, _ = quiet(uvi.get_repo_stats)
    check(got == PRIOR["repository_stats"], "otherwise preserves the last known-good stats")
    check(got["stars"] != 0, "never substitutes 0 for 'unknown'")


# =========================================================================== 4
print("\n4. game_stats is not this script's to invent")

with Sandbox(api=FULL_API, version_json=PRIOR) as sb:
    _, _ = quiet(uvi.update_version_data)
    wrote = sb.read("version.json")
    check(wrote["game_stats"] == PRIOR["game_stats"],
          "the calculator's derived game_stats survives a version update untouched")
    check(wrote["game_stats"]["baseline_doom_percent"] is None,
          "REGRESSION: an honest null is NOT overwritten with the literal 23")
    check("pending" in wrote["game_stats"],
          "the 'not yet measured' explanation survives too -- the reader keeps the reason")

with Sandbox(api=FULL_API) as sb:  # no version.json at all
    _, _ = quiet(uvi.update_version_data)
    wrote = sb.read("version.json")
    check("game_stats" not in wrote,
          "with nothing derived yet, the key is OMITTED -- absence is honest, a "
          "number would be a fiction")

# The rule, stated as a scan rather than a list of three field names: no numeric
# literal in this module may end up under game_stats. Someone re-adding a stub
# fails here without anyone remembering these particular keys.
src = (ROOT / "scripts" / "update-version-info.py").read_text(encoding="utf-8").replace("\r\n", "\n")
body = src.split("def update_version_data", 1)[1].split("\ndef ", 1)[0]
assigned = re.findall(r"^\s*'(\w+)':\s*(-?\d[\d_.]*)\s*,?\s*$", body, re.M)
check(not assigned,
      f"update_version_data() assigns no numeric literal to any key (found {assigned})")


# =========================================================================== 5
print("\n5. status.json is not clobbered by a fallback release")

STATUS = {"game": {"latestRelease": {"version": "v1.2.3", "date": "2029-01-01",
                                     "downloadUrl": "https://real/download"},
                   "development": {"progress": "v1.2.3 released"}},
          "website": {"version": "3.0.0"}}

# A preserved release keeps its real html_url, so force the genuine fallback shape:
# a release dict whose url is NOT a /releases/tag/ link.
with Sandbox(api={}, status_json=STATUS) as sb:
    _, out = quiet(uvi.sync_status_json,
                   {"latest_release": {"version": "v0.0.0-guess", "html_url": ""}})
    check(sb.read("status.json") == STATUS,
          "a non-release URL leaves status.json byte-identical")
    check("Skipping" in out, "says it skipped")

with Sandbox(api=FULL_API, status_json=STATUS) as sb:
    vd, _ = quiet(uvi.update_version_data)
    _, _ = quiet(uvi.sync_status_json, vd)
    st = sb.read("status.json")
    # Read the version out of the fixture rather than repeating a literal.
    expected_version = RELEASE["tag_name"]
    check(st["game"]["latestRelease"]["version"] == expected_version,
          "a real release DOES update status.json")
    check(st["website"]["version"] == STATUS["website"]["version"],
          "website.version is left alone -- that bump is a separate, deliberate act")
    check(st["game"]["latestRelease"]["downloadUrl"] == "https://real/download",
          "an existing downloadUrl is not replaced by the generic /releases/latest link")


# =========================================================================== 6
print("\n6. The tag name is upstream data, not code, when index.html is rewritten")

INDEX = ('<!doctype html>\n<html><body>\n'
         '<a class="dl">Download Latest Release</a>\n'
         '<a class="dl2">Download v0.0.1</a>\n</body></html>\n')

HOSTILE_TAGS = [
    r"v1.0\g<0>",          # a re.sub group reference in the replacement template
    "v1.0\\1",             # a backreference
    "v1.0\\",              # a lone backslash -- used to raise re.error mid-rewrite
    '"><script>alert(1)</script>',
    "v1.0 & <b>bold</b>",
]

for tag in HOSTILE_TAGS:
    with Sandbox() as sb:
        idx = sb.tmp / "index.html"
        idx.write_text(INDEX, encoding="utf-8", newline="")
        saved = uvi.os.path.join
        # update_download_links() builds its own path to public/index.html; point it
        # at the temp copy instead of the real homepage.
        uvi.os.path.join = lambda *p: str(idx) if p and p[-1] == "index.html" else saved(*p)
        try:
            res, _ = quiet(uvi.update_download_links, {"latest_release": {"version": tag}})
        finally:
            uvi.os.path.join = saved
        out = open(idx, encoding="utf-8", newline="").read()
        check(not isinstance(res, Exception),
              f"no exception rewriting the homepage with tag {tag!r}: {res}")
        check("<script>" not in out and "<b>" not in out,
              f"tag {tag!r} cannot open an element on the front page")
        check("Download Latest Release" not in out, f"the button text was replaced for {tag!r}")
        # A replacement TEMPLATE would have expanded these into the matched text.
        check("Download Latest Release (Latest)" not in out,
              f"\\g<0> was not expanded as a group reference for {tag!r}")
        check("\r\n" not in out, f"LF input stays LF after the rewrite ({tag!r})")

# Idempotence: the cron runs this 4x a day against a file it already rewrote.
with Sandbox() as sb:
    idx = sb.tmp / "index.html"
    idx.write_text(INDEX, encoding="utf-8", newline="")
    saved = uvi.os.path.join
    uvi.os.path.join = lambda *p: str(idx) if p and p[-1] == "index.html" else saved(*p)
    try:
        quiet(uvi.update_download_links, {"latest_release": {"version": "v9.9.9"}})
        once = open(idx, encoding="utf-8", newline="").read()
        quiet(uvi.update_download_links, {"latest_release": {"version": "v9.9.9"}})
        twice = open(idx, encoding="utf-8", newline="").read()
    finally:
        uvi.os.path.join = saved
    check(once == twice, "a second run on the same version changes nothing")
    check(RELEASE["tag_name"] in once, "the version actually reached the button")


# =========================================================================== 7
print("\n7. A malformed API response is a failure, not a publish")

for bad in ({}, {"assets": []}, {"tag_name": "", "name": ""}, {"body": "only notes"}):
    with Sandbox(api={"/releases/latest": bad}) as sb:
        err, _ = quiet(uvi.get_latest_release)
        check(isinstance(err, RuntimeError),
              f"a response with no usable tag is refused, not published: {bad}")


print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: update-version-info refuses rather than guessing, derives platforms from "
      "real assets, and invents no game stats.")
