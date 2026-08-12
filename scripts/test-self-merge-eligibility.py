#!/usr/bin/env python
"""Tests for scripts/check-self-merge-eligibility.py -- the R1 self-merge gate.

Run: python scripts/test-self-merge-eligibility.py

Hermetic: no network, no GitHub, no git history. Everything here is a pure
function over (labels, changed paths, PR body), so the rule stays provable
offline -- which is the point of a gate whose whole job is deciding whether a
human may skip review.

The checker also carries a `--self-test` that replays its full rule table and
prints the failure text a reader will see. That is the louder evidence; this
file exists because it pins the individual rules, so they cannot be weakened one
at a time behind a table that still passes.

What these lock down:

- **The gate can actually fail.** class:guard with no RED-RUN line in the body
  MUST produce a finding. A check that cannot fail is indistinguishable from a
  check that passes.
- **It never blocks a normal PR.** No class label -> no findings, whatever the
  diff contains. A gate that fires on PRs making no claim gets switched off.
- **public/ is not documentation on this repo.** Everything under public/ is
  served to visitors, so it is a public claim, which R1 keeps with Pip -- and
  the prime directive makes it the highest-stakes edit here. A published blog
  post is a .md file and must still fail the docs class.
- **The frozen copy baseline is not documentation.** Editing
  docs/copy-baseline/ is how a copy-drift check is made to agree with drifted
  copy.
"""

import importlib.util
import sys
from pathlib import Path

# Windows consoles default to cp1252. No-op on UTF-8 platforms.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sme", ROOT / "scripts" / "check-self-merge-eligibility.py"
)
sme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sme)

RED_URL = "https://github.com/PipFoweraker/pdoom1-website/actions/runs/1234567890"
GOOD_BODY = "Adds the gate.\n\nRED-RUN: %s -- guard label, no declaration in body\n" % RED_URL

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" -> " + detail) if detail else ""))


def section(title):
    print("\n%s" % title)


# ---------------------------------------------------------------------------
section("What counts as documentation")
# ---------------------------------------------------------------------------

for path in ("docs/TECH_DEBT.md", "CLAUDE.md", "content/INSIGHTS.md", "docs/adr/0001.md"):
    check("documentation: %s" % path, sme.is_documentation(path))

for path in (
    "public/index.html",
    "public/blog/2025-09-10-version-0-2-12-release.md",  # published, not internal
    "public/assets/js/escape.js",
    "docs/copy-baseline/about/index.html.txt",  # the frozen snapshot itself
    "deploy-excludes.txt",  # decides what never ships
    "requirements.txt",
    "runtime.txt",
    "scripts/check-self-merge-eligibility.py",
    ".github/workflows/self-merge-eligibility.yml",
):
    check("not documentation: %s" % path, not sme.is_documentation(path))

check("windows separators normalised", sme.is_documentation("docs\\TECH_DEBT.md"))

# ---------------------------------------------------------------------------
section("The RED-RUN declaration: a verdict is not a record without a reason")
# ---------------------------------------------------------------------------

check("empty body has no declaration", sme.find_red_run("") is None)
check("prose alone has no declaration", sme.find_red_run("Adds a check. It works.") is None)
check("bare run id is not a declaration", sme.find_red_run("RED-RUN: 1234567890") is None)
check("bare url is not a declaration", sme.find_red_run("RED-RUN: %s" % RED_URL) is None)
check("token reason is not a reason", sme.find_red_run("RED-RUN: 1234567890 -- x") is None)
check(
    "url plus reason parses",
    sme.find_red_run("RED-RUN: %s -- inverted the assertion" % RED_URL) is not None,
)
check(
    "numeric id plus reason parses",
    sme.find_red_run("RED-RUN: 1234567890 -- inverted the assertion") is not None,
)
check("a short number is not a run id", sme.find_red_run("RED-RUN: 42 -- inverted it") is None)
check(
    "case-insensitive, found among prose",
    sme.find_red_run("Fixes it.\n\nred-run: 1234567890 -- ran with the guard removed\n\nCheers")
    is not None,
)
check(
    "the format string the failure message prints actually parses",
    sme.find_red_run(
        sme.RED_RUN_FORMAT.replace("<run-url-or-run-id>", "1234567890").replace(
            "<what was broken to make it fail>", "removed the assertion"
        )
    )
    is not None,
)

# ---------------------------------------------------------------------------
section("Label parsing: seeing zero labels would pass everything")
# ---------------------------------------------------------------------------

check(
    "json array of names",
    sme.parse_labels('["class:guard", "ship:now"]') == ["class:guard", "ship:now"],
)
check("json array of objects", sme.parse_labels('[{"name": "class:docs"}]') == ["class:docs"])
check(
    "comma separated", sme.parse_labels("class:guard, needs:pip") == ["class:guard", "needs:pip"]
)
check(
    "newline separated",
    sme.parse_labels("class:guard\nneeds:pip\n") == ["class:guard", "needs:pip"],
)
check("empty", sme.parse_labels("") == [])
check("malformed json", sme.parse_labels("[not json") == [])

# ---------------------------------------------------------------------------
section("The five rules, end to end")
# ---------------------------------------------------------------------------

check("no class label is neutral", sme.run([], ["public/index.html"], "") == [])
check("unrelated labels are neutral", sme.run(["bug"], ["public/index.html"], "") == [])
check("needs:pip alone is neutral", sme.run(["needs:pip"], ["public/index.html"], "") == [])

check("docs-only diff passes", sme.run(["class:docs"], ["docs/TECH_DEBT.md"], "") == [])

_mixed = sme.run(["class:docs"], ["docs/TECH_DEBT.md", "public/about/index.html"], "")
check("docs class over a served page fails", bool(_mixed))
check(
    "and it names the offending path",
    bool(_mixed) and "public/about/index.html" in _mixed[0] and "docs/TECH_DEBT.md" not in _mixed[0],
)

check("docs class with no changed paths fails", bool(sme.run(["class:docs"], [], "")))

_undeclared = sme.run(["class:guard"], [".github/workflows/x.yml"], "Adds a check.")
check("guard class with no declaration fails", bool(_undeclared))
check("and it prints the expected format", bool(_undeclared) and "RED-RUN:" in _undeclared[0])

check(
    "guard class with a declaration passes",
    sme.run(["class:guard"], [".github/workflows/x.yml"], GOOD_BODY) == [],
)
check(
    "a guard may live anywhere in the tree",
    sme.run(["class:guard"], ["scripts/check-thing.py"], GOOD_BODY) == [],
)

check(
    "needs:pip fails a guard claim even with a RED run",
    bool(sme.run(["class:guard", "needs:pip"], [".github/workflows/x.yml"], GOOD_BODY)),
)
check(
    "needs:pip fails a docs claim even on a clean docs diff",
    bool(sme.run(["class:docs", "needs:pip"], ["docs/TECH_DEBT.md"], "")),
)
check(
    "both class labels fail",
    bool(sme.run(["class:guard", "class:docs"], ["docs/TECH_DEBT.md"], GOOD_BODY)),
)
check(
    "label matching is case-insensitive",
    bool(sme.run(["Class:Guard"], [".github/workflows/x.yml"], "no declaration")),
)

# ---------------------------------------------------------------------------
section("The checker's own rule table")
# ---------------------------------------------------------------------------

check("--self-test agrees with these tests", sme.self_test() == 0)
check(
    "the table contains both polarities",
    {case[4] for case in sme.SELF_TEST_CASES} == {0, 1},
    "a table with one polarity proves nothing",
)

print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
