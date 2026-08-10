#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-state tests for scripts/check-epoch-drift.py.

WHY THIS EXISTS
---------------
Workshop 2 ruled (R6) that no guard counts as installed until a RED run of it has
been observed. This file is how the red is produced on demand instead of by
waiting for pdoom1 to fork the ladder again.

Every test FORCES a state. None watches the happy path and infers the rest -- the
repo's standing rule is that a guard seen only in its passing state has not been
shown to work, because green is equally consistent with "the condition is safe"
and "the check never fires".

THE STATE THAT MATTERS MOST is not drift. It is a MISSING FIELD. The bet this
script was written for predicted, in advance and in public, that the way it turns
into another green-and-wrong check is by treating an absent or renamed field as
agreement. Tests 3 and 4 exist to make that impossible to reintroduce quietly.

NO NETWORK. Every case feeds a fixture through --manifest, and the fetch path is
never exercised, so this is safe offline and in CI and cannot depend on pdoom1
having shipped anything today.

Run:  python scripts/test-epoch-drift.py     (exit 0 = pass)
"""

import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        try:
            if _s is sys.stdout:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-epoch-drift.py"

failures = []
tmp = Path(tempfile.mkdtemp())


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def write(name, obj):
    p = tmp / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def targets(epoch, seeds, sourced=True):
    """A board-probe-targets.json shaped like the real one."""
    return {
        "current_ladder_epoch": ({"value": epoch, "source": "test fixture"}
                                 if epoch else {}),
        "extra_seeds": [
            ({"value": s, "source": "test fixture"} if sourced else {"value": s})
            for s in seeds
        ],
    }


def run(manifest_obj, targets_obj, manifest_missing=False):
    m = write("manifest.json", manifest_obj if manifest_obj is not None else {})
    t = write("targets.json", targets_obj)
    argv = [sys.executable, str(SCRIPT), "--targets", str(t), "--json"]
    argv += ["--manifest", str(tmp / "does-not-exist.json") if manifest_missing else str(m)]
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
    out = (p.stdout or "") + (p.stderr or "")
    try:
        payload = json.loads(out[out.index("{", out.rindex("\n{")):])
    except Exception:
        payload = {}
    return p.returncode, out, payload


GOOD = {"version": "v0.14.1", "ladder_version": "4", "league_seed": "weekly-2026-w32"}
SITE = targets("L4", ["weekly-2026-w31", "weekly-2026-w32"])

print("\n1. In step -> exit 0")
code, out, r = run(GOOD, SITE)
check(code == 0, "exit 0 when the site's declaration matches the manifest (got %s)" % code)
check(r.get("verdict") == "in-step", "verdict in-step (got %r)" % r.get("verdict"))
check(r.get("published_epoch") == "L4", "normalises the manifest's '4' to 'L4'")

print("\n2. THE REAL INCIDENT: the ladder forked and the site still says L3 -> RED")
code, out, r = run(GOOD, targets("L3", ["weekly-2026-w31"]))
check(code == 1, "exit 1 -- this is an incident, not an admission (got %s)" % code)
check(r.get("verdict") == "drift", "verdict drift (got %r)" % r.get("verdict"))
check("L3" in out and "L4" in out, "names BOTH values so the reader can act")
check("ARCHIVE the outgoing board" in out,
      "tells the reader to archive BEFORE flipping -- the step that turns a live "
      "board into an unarchived orphan if skipped")
check("blessing" in out.lower(), "reminds that the seed needs Pip's blessing")

print("\n3. PREDICTED FAILURE MODE: ladder_version absent -> unknown, NEVER agreement")
code, out, r = run({"version": "v0.15.0", "league_seed": "weekly-2026-w33"}, SITE)
check(code == 2, "exit 2, not 0 (got %s)" % code)
check(r.get("verdict") == "unknown", "verdict unknown (got %r)" % r.get("verdict"))
check(r.get("epoch_agrees") is None,
      "makes NO agreement claim when it cannot read the field")
check("never treated" in out and "agreement" in out,
      "says out loud that absence is not agreement")

print("\n4. Same for a RENAMED field -- the cross-repo contract breaking")
code, out, r = run({"version": "v0.15.0", "ladderVersion": "5",
                    "leagueSeed": "weekly-2026-w33"}, SITE)
check(code == 2, "a rename reads as unknown, not as agreement (got %s)" % code)
check("breaking change" in out, "calls a rename a breaking change wanting an issue")

print("\n5. Manifest unreachable -> unreachable, and NO drift claim either way")
code, out, r = run(None, targets("L3", ["weekly-2026-w31"]), manifest_missing=True)
check(code == 2, "exit 2 (got %s)" % code)
check(r.get("verdict") == "unreachable", "verdict unreachable (got %r)" % r.get("verdict"))
check(r.get("epoch_agrees") is None and r.get("verdict") != "drift",
      "OBSERVATION OUTRANKS STORED STATE: the site's L3 declaration is stale here, "
      "but with nothing observed the script must not say so")
check("Nothing was observed" in out, "says plainly that nothing was observed")

print("\n6. Seed rolled but epoch held (an ordinary weekly roll) -> RED on the seed")
code, out, r = run({"version": "v0.14.2", "ladder_version": "4",
                    "league_seed": "weekly-2026-w33"}, SITE)
check(code == 1, "exit 1 (got %s)" % code)
check(r.get("epoch_agrees") is True and r.get("seed_pinned") is False,
      "epoch agrees, seed does not -- reported separately")
check("cannot discover a seed it has never seen" in out,
      "explains WHY the pin matters: #229, the probe cannot find an unseen seed")

print("\n7. A pinned seed with NO source does not count as a declaration")
code, out, r = run(GOOD, targets("L4", ["weekly-2026-w32"], sourced=False))
check(code == 1, "unsourced pin is ignored, so the seed reads as unpinned (got %s)" % code)
check(any("no source recorded" in n for n in (r.get("notes") or [])),
      "says which pin it ignored and why")

print("\n8. Site declares nothing -> cannot tell, and it is not drift")
code, out, r = run(GOOD, targets(None, []))
check(code == 2, "exit 2 (got %s)" % code)
check(r.get("verdict") == "site-undeclared", "verdict site-undeclared (got %r)" % r.get("verdict"))
check("weekly-2026-w32" in out, "still reports the published value, so it is actionable")

print()
if failures:
    print("%d FAILURE(S)" % len(failures))
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: drift is red, absence is unknown, an unreachable source claims nothing, "
      "and an unsourced pin is not a declaration.")
