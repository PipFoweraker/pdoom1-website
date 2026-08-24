#!/usr/bin/env python3
"""Force check-league-state.py red, one invariant at a time.

ADR-0002 in this repo: a guard is not installed until a RED run of it has been
observed. Waiting for a real seat to invent an opening is not a test plan, and the
whole point of #351's `player_facing` block is that its failure is silent -- a
fabricated opening looks exactly like a real one from inside the file.

Every case below builds a MUTATED COPY of the real
public/data/ladder-epochs.json in a temp tree and asserts the exit code. The real
file is never written to.

Exit codes under test: 0 ok / 1 invariant violated / 2 cannot tell.

Run: python scripts/test-league-state.py     (exit 0 = pass)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REAL = ROOT / "public" / "data" / "ladder-epochs.json"
CHECKER = ROOT / "scripts" / "check-league-state.py"
LEDGER = ROOT / "docs" / "LEAGUE_SEED_LEDGER.md"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

failures = 0


def run_on(mutate, label: str, want: int, want_text: str | None = None) -> None:
    """Write a mutated copy into a temp tree that mirrors the repo layout."""
    global failures
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        data_dir = tmp / "public" / "data"
        data_dir.mkdir(parents=True)
        (tmp / "docs").mkdir()
        shutil.copyfile(LEDGER, tmp / "docs" / "LEAGUE_SEED_LEDGER.md")

        doc = json.loads(REAL.read_text(encoding="utf-8"))
        mutate(doc)
        target = data_dir / "ladder-epochs.json"
        target.write_text(json.dumps(doc, indent=2), encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(CHECKER), str(target)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace",
        )
    ok = proc.returncode == want
    if ok and want_text:
        ok = want_text.lower() in (proc.stdout + proc.stderr).lower()
    print(("  PASS  " if ok else "  FAIL  ") + "%s -> exit %d (wanted %d)"
          % (label, proc.returncode, want))
    if not ok:
        failures += 1
        for line in (proc.stdout + proc.stderr).splitlines():
            print("          | " + line)


def fresh(doc) -> None:
    """Keep the stamp inside its window so freshness never masks the case."""
    doc["player_facing"]["verified_utc"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


print("-- the file as committed --")
run_on(fresh, "unmutated (with a fresh stamp)", 0)

print()
print("-- an opening nobody performed --")


def _fabricate_open(doc):
    fresh(doc)
    lo = doc["player_facing"]["league_open"]
    lo["state"] = "open"
    lo["seed"] = "weekly-2026-w33"
    lo["ladder_version"] = "L5"
    # opened_by / opened_utc deliberately left null -- this is the exact shape a
    # seat produces when it concludes "the board must be open, scores are landing".


run_on(_fabricate_open, "state=open with no opener and no timestamp", 1, "named human")


def _open_fields_without_open(doc):
    fresh(doc)
    lo = doc["player_facing"]["league_open"]
    lo["seed"] = "weekly-2026-w33"
    lo["ladder_version"] = "L5"


run_on(_open_fields_without_open,
       "an open league's fields set while the state says none-open", 1,
       "opening that did not happen")

print()
print("-- an unblessed seed reaching a visitor --")


def _unblessed_seed(doc):
    fresh(doc)
    doc["player_facing"]["coming"]["seed"] = "weekly-2026-w34"
    doc["player_facing"]["coming"]["seed_blessed"] = False


run_on(_unblessed_seed, "coming.seed set with seed_blessed false", 1, "unblessed seed")


def _seed_not_in_ledger(doc):
    fresh(doc)
    doc["player_facing"]["coming"]["seed"] = "weekly-2026-w99"
    doc["player_facing"]["coming"]["seed_blessed"] = True


run_on(_seed_not_in_ledger, "a seed claiming blessed that the ledger has never seen",
       1, "LEAGUE_SEED_LEDGER")

print()
print("-- the vocabulary --")


def _undefined_state(doc):
    fresh(doc)
    doc["player_facing"]["league_open"]["state"] = "probably-fine"


run_on(_undefined_state, "a state name _states does not define", 1, "_states")


def _no_evidence(doc):
    fresh(doc)
    doc["player_facing"]["league_open"]["evidence"] = ""


run_on(_no_evidence, "a claim with its evidence emptied", 1, "evidence")

print()
print("-- the epoch that no build ships --")


def _unpublished_with_boundary(doc):
    fresh(doc)
    for e in doc["epochs"]:
        if e.get("published") is False:
            e["boundary_local"] = "2026-08-23T00:00:00+10:00"


run_on(_unpublished_with_boundary,
       "published:false epoch given a boundary_local", 1, "relabel")


def _unpublished_blessed(doc):
    fresh(doc)
    for e in doc["epochs"]:
        if e.get("published") is False:
            e["seed_status"] = "blessed"


run_on(_unpublished_blessed, "published:false epoch claiming a blessing", 1, "blessed")

print()
print("-- the frontier and the cut --")


def _cut_contradiction(doc):
    fresh(doc)
    doc["regularised_from"]["cut_ladder_version_published"] = True


run_on(_cut_contradiction,
       "an unpublished cut marked published", 1, "unpublished")


def _downloadable_off_frontier(doc):
    fresh(doc)
    doc["player_facing"]["downloadable_now"]["board_key"]["ladder_version"] = "L6"


run_on(_downloadable_off_frontier,
       "downloadable epoch differing from the frontier", 1, "one fact")

print()
print("-- cannot tell is not a pass --")


def _expired(doc):
    doc["player_facing"]["verified_utc"] = (
        datetime.now(timezone.utc) - timedelta(days=400)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


run_on(_expired, "a verification past its expiry", 2, "cannot tell")


def _no_expiry(doc):
    fresh(doc)
    doc["player_facing"].pop("stale_after_days", None)


run_on(_no_expiry, "a verification date with no expiry", 2, "class-5")


def _no_block(doc):
    doc.pop("player_facing", None)


run_on(_no_block, "the whole block missing", 2, "cannot tell")

print()
print("-" * 70)
if failures:
    print("FAILED: %d case(s) did not produce the expected verdict" % failures)
    sys.exit(1)
print("PASSED: every invariant can still go red, and 'cannot tell' is not a pass")
