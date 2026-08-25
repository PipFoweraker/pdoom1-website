#!/usr/bin/env python
"""Forced-failure tests for scripts/repair-orphan-events.py.

    python scripts/test-repair-orphan-events.py      (exit 0 = pass)

WHY THIS FILE EXISTS
--------------------
`repair-orphan-events.py` claims five safety properties in its docstring: it
verifies before writing, it refuses ALL-OR-NOTHING on a single bad page, it has
a corpus floor, it is idempotent, and each of its five repairs actually lands.
CLAUDE.md: *"A claimed safety property needs a forced failure ... A docstring is
documentation, not evidence."*

So every block below FORCES the state and observes the refusal, rather than
watching the happy path go green. Three of them are negative controls: they
re-run the checks against input that should FAIL and assert that it does, because
a verifier that never discriminates and a verifier that is correct look identical
from outside.

Nothing here touches `public/`. Every case runs in a temp dir over `--glob`, and
the last block asserts the real corpus is byte-identical before and after.
"""

import sys
import os
import json
import glob
import shutil
import hashlib
import tempfile
import subprocess
import importlib.util

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "repair-orphan-events.py")
CORPUS = os.path.join(REPO, "public", "events", "alignmentforum_*.html")

passed = 0
failed = 0


def ok(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  PASS %s" % name)
    else:
        failed += 1
        print("  FAIL %s   %s" % (name, detail))


def load_module():
    spec = importlib.util.spec_from_file_location("repair_orphan_events", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(*args):
    proc = subprocess.run(
        [sys.executable, SCRIPT] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# A page carrying every defect this script repairs, in the exact shape the real
# corpus uses (tabs, the Plausible comment marker, the impacts table).
BROKEN_PAGE = """<!DOCTYPE html>
<html lang="en-AU">
<head>
\t<meta charset="UTF-8">
\t<meta name="viewport" content="width=device-width, initial-scale=1.0">
\t<title>A Real Person's Post Title | p(Doom)1 Events</title>

\t<!-- Plausible Analytics -->
\t<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>

\t<link rel="stylesheet" href="/css/site.css">
\t<style>body{background:#12100F}</style>
</head>
<body>
\t<main>
\t\t<div class="event-header">
\t\t\t<h1 class="event-title">A Real Person's Post Title</h1>
\t\t</div>

\t\t<div class="section">
\t\t\t<h2>\U0001F4CA Game Impacts</h2>
\t\t\t<table class="impacts-table">
\t\t\t\t<thead>
\t\t\t\t\t<tr>
\t\t\t\t\t\t<th>Variable</th>
\t\t\t\t\t\t<th>Change</th>
\t\t\t\t\t\t<th>Condition</th>
\t\t\t\t\t</tr>
\t\t\t\t</thead>
\t\t\t\t<tbody>
\t\t\t\t<tr>
\t\t\t\t\t<td>Research</td>
\t\t\t\t\t<td class="impact-positive">+5</td>
\t\t\t\t\t<td>Always</td>
\t\t\t\t</tr>
\t\t\t\t<tr>
\t\t\t\t\t<td>Ethics Risk</td>
\t\t\t\t\t<td class="impact-negative">-5</td>
\t\t\t\t\t<td>Always</td>
\t\t\t\t</tr>
\t\t\t\t</tbody>
\t\t\t</table>
\t\t</div>

\t\t<div class="metadata-item">
\t\t\t<span class="metadata-label">p(Doom) Impact</span>
\t\t\t<span class="metadata-value">No direct impact</span>
\t\t</div>
\t</main>
</body>
</html>
"""


def write_corpus(tmp, n=3, text=BROKEN_PAGE):
    for i in range(n):
        with open(
            os.path.join(tmp, "alignmentforum_%016x.html" % i),
            "w",
            encoding="utf-8",
            newline="",
        ) as fh:
            fh.write(text)
    return os.path.join(tmp, "alignmentforum_*.html")


# ---------------------------------------------------------------------------
def test_each_repair_lands(mod):
    print("\nEach of the five repairs, forced on a page that lacks it")
    fixed, applied = mod.repair(BROKEN_PAGE)

    ok("R1 stops asserting 'No direct impact'", "No direct impact" not in fixed)
    ok("R1 says 'Not recorded' instead", "Not recorded" in fixed)
    ok(
        "R2 drops the keyword-counter magnitude +5",
        '<td class="impact-positive">+5</td>' not in fixed,
    )
    ok("R2 keeps the direction", "proposed: up" in fixed and "proposed: down" in fixed)
    ok("R2 relabels the column Change -> Direction", "<th>Direction</th>" in fixed)
    ok("R3 adds the 'Not verified in game' stamp", "Not verified in game" in fixed)
    ok("R3 links the SHARED stamp.css", "/css/stamp.css" in fixed)
    ok("R4 adds the provenance banner", "orphan-provenance" in fixed)
    ok(
        "R4 states the author is not a participant",
        "have no\n\t\t\t\tassociation with p(Doom)1" in fixed
        or "no association with p(Doom)1" in fixed.replace("\n", " ").replace("\t", ""),
    )
    ok("R4 adds noindex", "noindex" in fixed)
    ok("R5 adds the consent shim", mod.SHIM_TAG in fixed)
    ok(
        "R5 loads the shim BEFORE the tracker",
        fixed.index(mod.SHIM_TAG) < fixed.index("analytics.pdoom1.com"),
    )
    ok("all five repairs reported", len(applied) >= 7, "applied=%r" % (applied,))


def test_negative_control_verify(mod):
    print("\nNEGATIVE CONTROL: verify() must reject each defect on its own")
    fixed, _ = mod.repair(BROKEN_PAGE)
    ok("a fully repaired page passes verify()", mod.verify(fixed, "x") == [])

    cases = [
        ("consent shim removed", fixed.replace(mod.SHIM_TAG, ""), "no consent shim"),
        ("noindex removed", fixed.replace(mod.NOINDEX_TAG, ""), "not noindexed"),
        ("stamp.css removed", fixed.replace(mod.STAMP_CSS, ""), "stamp.css not linked"),
        (
            "'No direct impact' put back",
            fixed.replace("Not recorded", "No direct impact"),
            "still asserts",
        ),
        (
            "banner removed",
            fixed.replace("orphan-provenance", "something-else"),
            "no provenance banner",
        ),
        (
            "a magnitude put back",
            fixed.replace('proposed: up</td>', "+5</td>"),
            "keyword-counter magnitude",
        ),
        (
            "the stamp removed but the table left",
            fixed.replace("Not verified in game", "Looks fine"),
            "Not verified in game",
        ),
    ]
    for name, mutated, needle in cases:
        problems = mod.verify(mutated, "x")
        ok(
            "verify() rejects: %s" % name,
            any(needle in p for p in problems),
            "problems=%r" % problems,
        )

    # The shim being PRESENT is not enough; order is the property that matters.
    swapped = fixed.replace(mod.SHIM_TAG, "", 1).replace(
        "</head>", mod.SHIM_TAG + "\n</head>"
    )
    ok(
        "verify() rejects a shim that loads after the tracker",
        any("AFTER the tracker" in p for p in mod.verify(swapped, "x")),
    )


def test_idempotent(mod):
    print("\nIdempotence")
    once, _ = mod.repair(BROKEN_PAGE)
    twice, applied2 = mod.repair(once)
    ok("running repair() twice changes nothing", once == twice)
    ok("...and reports no repairs the second time", applied2 == [], "%r" % (applied2,))


def test_all_or_nothing():
    print("\nALL-OR-NOTHING: one unrepairable page must block every write")
    tmp = tempfile.mkdtemp()
    try:
        pattern = write_corpus(tmp, n=3)
        # A page whose impacts table cannot be stamped, because the <h2> marker
        # this script anchors on is absent. verify() must catch it, and NOTHING
        # may be written -- not even the two pages that were fine.
        bad = os.path.join(tmp, "alignmentforum_ffffffffffffffff.html")
        with open(bad, "w", encoding="utf-8", newline="") as fh:
            fh.write(BROKEN_PAGE.replace("<h2>\U0001F4CA Game Impacts</h2>", "<h2>Impacts</h2>"))

        before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                  for p in sorted(glob.glob(pattern))}
        rc, out = run("--glob", pattern)

        ok("exits non-zero", rc == 1, "rc=%d" % rc)
        ok("says verification failed", "VERIFICATION FAILED" in out)
        ok("says nothing was written", "NOTHING WRITTEN" in out)

        after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                 for p in sorted(glob.glob(pattern))}
        ok("every page is byte-identical, including the good ones", before == after)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_floor():
    print("\nThe corpus floor")
    tmp = tempfile.mkdtemp()
    try:
        pattern = os.path.join(tmp, "alignmentforum_*.html")
        rc, out = run("--glob", pattern)
        ok("an empty corpus exits 2, not 0", rc == 2, "rc=%d" % rc)
        ok("and says it is refusing", "REFUSING" in out)
        ok(
            "and does NOT report a clean sweep",
            "OK:" not in out,
            "a sweep over nothing must never read as green",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_check_mode_discriminates():
    print("\n--check must go RED on an unrepaired corpus and GREEN after")
    tmp = tempfile.mkdtemp()
    try:
        pattern = write_corpus(tmp, n=2)
        rc_before, out_before = run("--check", "--glob", pattern)
        ok("--check fails on a broken corpus", rc_before == 1, "rc=%d" % rc_before)
        ok("...and says so", "CHECK FAILED" in out_before)

        rc_fix, _ = run("--glob", pattern)
        ok("the repair run exits 0", rc_fix == 0, "rc=%d" % rc_fix)

        rc_after, out_after = run("--check", "--glob", pattern)
        ok("--check passes afterwards", rc_after == 0, "rc=%d" % rc_after)
        ok("...and says every page carries the repairs", "OK:" in out_after)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sitemap_rule_is_the_real_one():
    print("\nThe noindex tag must satisfy generate-sitemap.js's OWN regex")
    js = os.path.join(REPO, "scripts", "generate-sitemap.js")
    src = open(js, encoding="utf-8").read()
    ok("generate-sitemap.js still has a NOINDEX_RE", "NOINDEX_RE" in src)

    mod = load_module()
    fixed, _ = mod.repair(BROKEN_PAGE)
    # Re-implement the JS regex in Python rather than assert on a substring: the
    # property is "the sitemap generator will drop this page", not "the string
    # noindex appears somewhere".
    import re

    noindex_re = re.compile(
        r"""<meta[^>]+name=["']robots["'][^>]*content=["'][^"']*noindex""", re.I
    )
    ok("the emitted tag matches that regex", bool(noindex_re.search(fixed)))
    ok(
        "the tag is inside the first 16 KB the generator reads",
        fixed.index(mod.NOINDEX_TAG) < 16384,
        "at byte %d" % fixed.index(mod.NOINDEX_TAG),
    )


def test_leaves_real_corpus_alone(before):
    print("\nThe test itself")
    after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
             for p in sorted(glob.glob(CORPUS))}
    ok("public/events/ is byte-identical before and after this run", before == after)


def main():
    print("=" * 60)
    print("repair-orphan-events.py -- forced failures")
    print("=" * 60)

    before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
              for p in sorted(glob.glob(CORPUS))}

    mod = load_module()
    test_each_repair_lands(mod)
    test_negative_control_verify(mod)
    test_idempotent(mod)
    test_all_or_nothing()
    test_floor()
    test_check_mode_discriminates()
    test_sitemap_rule_is_the_real_one()
    test_leaves_real_corpus_alone(before)

    print("\n" + "=" * 60)
    print("%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
