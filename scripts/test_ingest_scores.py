#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke test for scripts/ingest_scores.py -- proves the two paths that matter:

  1. Real (deployed-version) scores publish as data_status="live" and populate the board.
     This is the self-healing behaviour: the day the game exports matching scores, the
     leaderboard goes live automatically -- no code change.

WHY THE FIXTURE IS RESTAMPED AT RUN TIME
The fixture used to carry a FROZEN "game_version": "v0.11.0" and the test asserted it
would publish as live. That silently stopped being a test of anything at the v0.12.0
release: deployed moved on, the fixture no longer matched, and the "live" path it claims
to cover went red and STAYED red -- through v0.12.0, v0.13.0 and v0.13.1. A test in the
documented pre-PR suite that is red on a clean checkout of main teaches everyone to skip
the suite, so the rot costs more than the coverage was worth.

The rule under test is "entries stamped with the DEPLOYED version publish as live". So
the fixture is copied to a temp dir and restamped with whatever version.json currently
says. The literal is gone; the rule is what is asserted, and the next release cannot rot
it. Test 2 still uses the real repo data unmodified, so the pre-launch path keeps its
teeth.
  2. The current repo data (all synthetic / older versions) publishes as "pre-launch"
     with zero entries -- the honest state, never showing dev data as live.

Run:  python scripts/test_ingest_scores.py     (exit 0 = pass)
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "scripts" / "fixtures" / "leaderboard"
PY = sys.executable


def deployed_version():
    ver = json.loads((ROOT / "public" / "data" / "version.json").read_text(encoding="utf-8"))
    return ver["latest_release"]["version"]


def restamped_fixtures():
    """The fixture dir, copied and restamped to the CURRENT deployed version.

    Returns a temp path. Never mutates the committed fixture -- a test that edits its own
    inputs in place is a test that passes once.
    """
    tmp = Path(tempfile.mkdtemp()) / "fixtures"
    shutil.copytree(FIXTURES, tmp)
    version = deployed_version()
    for f in tmp.glob("seed_leaderboard_*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        d.setdefault("meta", {})["game_version"] = version
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
    return tmp


def run(*args):
    out = Path(tempfile.mkdtemp()) / "leaderboard.json"
    r = subprocess.run(
        [PY, str(ROOT / "scripts" / "ingest_scores.py"), "--output", str(out), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert r.returncode == 0, f"ingest_scores exited {r.returncode}\n{r.stderr}"
    return json.loads(out.read_text(encoding="utf-8"))


def main():
    failures = []

    # 1. Fixture stamped with the deployed version -> LIVE
    live = run("--input", str(restamped_fixtures()))
    if live["data_status"] != "live":
        failures.append(f"fixture expected data_status=live, got {live['data_status']}")
    if len(live["entries"]) != 2:
        failures.append(f"fixture expected 2 entries, got {len(live['entries'])}")
    if live["entries"] and live["entries"][0]["score"] < live["entries"][-1]["score"]:
        failures.append("entries not sorted by score desc")
    if live["legacy"] is not False:
        failures.append("live data should not be flagged legacy")

    # 2. Real repo data (synthetic/older) -> PRE-LAUNCH, empty
    prelaunch = run()  # default input = public/leaderboard/data
    if prelaunch["data_status"] != "pre-launch":
        failures.append(f"repo data expected pre-launch, got {prelaunch['data_status']}")
    if len(prelaunch["entries"]) != 0:
        failures.append(f"pre-launch should have 0 entries, got {len(prelaunch['entries'])}")

    # 3. Version stamp is the real deployed one, never a producer stamp
    deployed = deployed_version()
    if live["meta"]["game_version"] != deployed:
        failures.append(f"expected version {deployed}, got {live['meta']['game_version']}")

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print(f"PASS: live path (2 entries, {deployed}), pre-launch path (0 entries), version stamp correct")


if __name__ == "__main__":
    main()
