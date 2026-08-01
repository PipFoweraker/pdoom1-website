#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke test for scripts/ingest_scores.py -- proves the paths that matter:

  1. Seeds stamped with the DEPLOYED game version publish as data_status="live".
     This is the self-healing behaviour: the day the game exports scores stamped
     with the shipped version, the leaderboard goes live automatically -- no code
     change.
  2. Seeds stamped with anything else publish as "pre-launch" with zero entries --
     the honest state, never showing dev/legacy data as live.
  3. Test/dev seed FILENAMES (test*, party*, demo*, ...) are excluded by default,
     so fixtures are never shown as real player scores.
  4. meta.game_version is stamped from public/data/version.json, never from what a
     producer wrote into the seed file.

EVERY fixture is built in a temp directory by this test. Nothing here reads
public/leaderboard/data/ or scripts/fixtures/, so the result depends on
ingest_scores.py's behaviour and NOT on what the live leaderboard currently holds.

That was the old bug (TECH_DEBT "Flaky / stateful tests"): case 1 used a checked-in
fixture whose meta.game_version was the hardcoded literal "v0.11.0", so the test
started failing the moment version.json advanced to v0.13.1 -- a red mark caused by
a routine release, not by a code change. Case 2 read the live seed directory, so a
single real score landing there would have flipped it too. Both are gone: the
deployed version is now READ from version.json and stamped into the fixture, so the
test tracks releases instead of rotting against them.

Run:  python scripts/test_ingest_scores.py     (exit 0 = pass)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# The one thing we deliberately read from the repo: the deployed version. It is the
# same source ingest_scores.py reads, so fixtures stamped from it stay in step with
# every release rather than going stale against a hardcoded literal.
DEPLOYED = json.loads(
    (ROOT / "public" / "data" / "version.json").read_text(encoding="utf-8")
)["latest_release"]["version"]


def seed_doc(version, seed_name, entries):
    return {
        "meta": {
            "generated": "2026-01-01T00:00:00Z",
            "game_version": version,
            "total_players": len(entries),
            "export_source": "test_ingest_scores.py",
        },
        "seed": seed_name,
        "economic_model": "Bootstrap_test",
        "entries": entries,
    }


def entry(name, score, doom_integral, uuid):
    return {
        "score": score,
        "doom_integral": doom_integral,
        "player_name": name,
        "date": "2026-01-01",
        "level_reached": int(score),
        "game_mode": "standard",
        "duration_seconds": 300.0,
        "entry_uuid": uuid,
    }


TWO_ENTRIES = [
    entry("Alpha", 42, 18.5, "test-entry-1"),
    entry("Beta", 37, 22.0, "test-entry-2"),
]


def publish(seed_files, *flags):
    """Write seed_files ({filename: doc}) into a fresh temp dir, run ingest_scores
    against it, and return the published leaderboard document."""
    tmp = Path(tempfile.mkdtemp())
    indir = tmp / "in"
    indir.mkdir()
    for name, doc in seed_files.items():
        (indir / name).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    out = tmp / "leaderboard.json"
    r = subprocess.run(
        [PY, str(ROOT / "scripts" / "ingest_scores.py"),
         "--input", str(indir), "--output", str(out), *flags],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT),
    )
    assert r.returncode == 0, f"ingest_scores exited {r.returncode}\n{r.stdout}\n{r.stderr}"
    return json.loads(out.read_text(encoding="utf-8"))


def main():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # 1. Seeds stamped with the deployed version -> LIVE
    live = publish({
        "seed_leaderboard_live_abc123.json": seed_doc(DEPLOYED, "live_seed", TWO_ENTRIES),
    })
    check(live["data_status"] == "live",
          f"deployed-version seed expected data_status=live, got {live['data_status']}")
    check(len(live["entries"]) == 2,
          f"expected 2 entries, got {len(live['entries'])}")
    check([e["player_name"] for e in live["entries"]] == ["Alpha", "Beta"],
          "entries not sorted by score DESC (ADR-0002)")
    check(live["legacy"] is False, "live data should not be flagged legacy")
    check(live["meta"]["game_version"] == DEPLOYED,
          f"expected version {DEPLOYED}, got {live['meta']['game_version']}")

    # 1b. ADR-0002 tiebreak: equal score -> doom_integral DESC
    tie = publish({
        "seed_leaderboard_tie_abc123.json": seed_doc(DEPLOYED, "tie_seed", [
            entry("LowIntegral", 50, 5.0, "tie-low"),
            entry("HighIntegral", 50, 90.0, "tie-high"),
        ]),
    })
    check([e["player_name"] for e in tie["entries"]] == ["HighIntegral", "LowIntegral"],
          "equal scores not tiebroken by doom_integral DESC (ADR-0002)")

    # 2. Seeds stamped with anything else -> PRE-LAUNCH, empty
    # Deliberately NOT a version-shaped literal: a numeric placeholder here would
    # register as a rotting hardcoded version in check-stale-facts.py, and the test
    # only needs "some stamp that is not the deployed one".
    stale = publish({
        "seed_leaderboard_stale_abc123.json": seed_doc("vNOT-THE-DEPLOYED-VERSION", "stale_seed", TWO_ENTRIES),
    })
    check(stale["data_status"] == "pre-launch",
          f"version-mismatched seed expected pre-launch, got {stale['data_status']}")
    check(len(stale["entries"]) == 0,
          f"pre-launch should have 0 entries, got {len(stale['entries'])}")

    # 3. Test/dev seed filenames are excluded even when correctly version-stamped.
    #    (Without this, a fixture run on a dev box would publish as real scores.)
    testseed = {"seed_leaderboard_test_abc123.json": seed_doc(DEPLOYED, "test_seed", TWO_ENTRIES)}
    excluded = publish(testseed)
    check(excluded["data_status"] == "pre-launch",
          f"test-named seed should be excluded, got {excluded['data_status']} "
          f"with {len(excluded['entries'])} entries")
    included = publish(testseed, "--include-tests")
    check(included["data_status"] == "live" and len(included["entries"]) == 2,
          "--include-tests should publish the test seed")

    # 4. The published stamp is the DEPLOYED version, never the producer's claim.
    lied = publish({
        "seed_leaderboard_lied_abc123.json": seed_doc("vPRODUCER-CLAIMED-STAMP", "lied_seed", TWO_ENTRIES),
    }, "--include-legacy")
    check(lied["data_status"] == "legacy",
          f"--include-legacy expected data_status=legacy, got {lied['data_status']}")
    check(lied["meta"]["game_version"] == DEPLOYED,
          f"producer stamp leaked through: expected {DEPLOYED}, "
          f"got {lied['meta']['game_version']}")
    check(lied["legacy"] is True, "legacy publication must be flagged legacy")

    # 5. No seed files at all -> pre-launch, not a crash.
    empty = publish({})
    check(empty["data_status"] == "pre-launch",
          f"empty input expected pre-launch, got {empty['data_status']}")
    check(len(empty["entries"]) == 0, "empty input should publish 0 entries")

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print(f"PASS: live/pre-launch/legacy paths, ADR-0002 sort + tiebreak, "
          f"test-seed exclusion, version stamp pinned to {DEPLOYED} "
          f"(all fixtures built in temp dirs -- no live-data dependency)")


if __name__ == "__main__":
    main()
