#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bless-seed.py -- the Friday step: record a seed Pip has blessed, then open its week.

WHY THIS EXISTS
---------------
On 2026-11-22 Pip retired the calendar rollover (D1 (i)): a league week opens
because a seed was BLESSED, never because a clock ticked. The calendar version
had two failure modes, both measured here: it opened derived seeds no client
posts to (23 stranded submissions), and when it was parked to stop that, the
league silently stood still for 13 weeks.

This script is the machine half of a blessing. The human half -- Pip's sign-off,
the [Gate 5] checks, and the row in docs/LEAGUE_SEED_LEDGER.md -- stays human.
It prints that row for him; it never writes it, because a row records who blessed
and when, and a script inferring that is how #297 started.

WHAT IT DOES, IN ORDER (and it writes NOTHING until every check has passed)
  1. Reads the SHIPPED client's release_manifest.json (the outside reference --
     a check takes its expectation from outside the system it checks).
  2. Refuses unless the manifest carries exactly this seed on the current ladder.
     A seed no released build posts to is the 23-stranded-submissions defect.
  3. Refuses a ladder fork. An epoch cut needs an epochs[] row, a boundary and
     board-probe-targets.json; that is rare, monthly, and done by hand.
  4. Refuses a seed that is already the blessed one (nothing to do).
  5. Writes public/data/ladder-epochs.json: regularised_from.seed, seed_status,
     seed_blessed_on, and the current epochs[] row's seed -- all four together,
     because check-blessing-consistency.py reads them against each other.
  6. Runs the rollover (weekly-league-manager.start_new_week), which archives the
     previous week at this moment and opens the new one with no end date.

THEN, BY HAND: add the ledger row it prints, run the checks it names, open a PR.
CI checks the chain: manifest -> blessing (check-epoch-drift.py), blessing ->
current.json (validate_data.py league:key), and age (league:blessing_age).

RUN
    python scripts/bless-seed.py --seed weekly-2026-w48
    python scripts/bless-seed.py --seed weekly-2026-w48 --manifest path/to/release_manifest.json
    python scripts/bless-seed.py --seed weekly-2026-w48 --dry-run

EXIT  0 blessed and opened | 1 refused (a check failed; nothing written)
      2 cannot tell (manifest unreachable or unreadable; nothing written)
"""
import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

REPO_ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_manifest(source):
    """(data, error). A path is read from disk; anything else is fetched (GET only)."""
    p = Path(source)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8")), None
        except (OSError, ValueError) as exc:
            return None, f"{p}: {exc}"
    drift = _load("check_epoch_drift", "check-epoch-drift.py")
    return drift.fetch_manifest(source)


def write_json_like(path, data, raw):
    """Write `data` in the same newline convention `raw` used."""
    nl = "\r\n" if "\r\n" in raw else "\n"
    text = json.dumps(data, indent=2, ensure_ascii=False).replace("\n", nl)
    if raw.endswith(nl):
        text += nl
    path.write_bytes(text.encode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", required=True, help="the seed Pip blessed, e.g. weekly-2026-w48")
    ap.add_argument("--on", help="blessing date YYYY-MM-DD (default: today in Hobart)")
    ap.add_argument("--manifest", help="release_manifest.json path or URL "
                                       "(default: the latest pdoom1 release)")
    ap.add_argument("--root", default=str(REPO_ROOT), help="repo root (tests)")
    ap.add_argument("--dry-run", action="store_true", help="check everything, write nothing")
    args = ap.parse_args(argv)
    root = Path(args.root)

    wlm = _load("weekly_league_manager", "weekly-league-manager.py")
    tz = wlm.league_tz()
    today = datetime.now(tz).date()
    try:
        on = datetime.fromisoformat(args.on).date() if args.on else today
    except ValueError:
        print(f"REFUSED: --on {args.on!r} is not a date.")
        return 1
    if on > today:
        print(f"REFUSED: --on {on} is in the future. A blessing is a decision already made.")
        return 1

    epochs_path = root / "public" / "data" / "ladder-epochs.json"
    raw = epochs_path.read_bytes().decode("utf-8")
    contract = json.loads(raw)
    cut = contract["regularised_from"]
    ladder = cut["ladder_version"]

    # ---- 1-2. the outside reference --------------------------------------
    drift = _load("check_epoch_drift", "check-epoch-drift.py")
    source = args.manifest or drift.MANIFEST_URL
    manifest, err = read_manifest(source)
    if err or not isinstance(manifest, dict):
        print(f"CANNOT TELL: could not read the release manifest ({source}): {err}. "
              f"Nothing was written. A blessing must be checked against what a shipped "
              f"client posts to; without the manifest there is nothing to check it against.")
        return 2
    m_seed = manifest.get("league_seed")
    m_ladder, m_err = drift.normalise_epoch(manifest.get("ladder_version"))
    print(f"manifest   league_seed={m_seed!r} ladder={m_ladder!r} "
          f"commit={str(manifest.get('commit_hash'))[:12]!r}  [{source}]")
    print(f"site       blessed=({cut.get('seed')}, {ladder}) since {cut.get('seed_blessed_on')}")
    if m_err:
        print(f"CANNOT TELL: the manifest's ladder_version is {m_err}. Nothing was written.")
        return 2
    if m_seed != args.seed:
        print(f"REFUSED: the shipped client posts to seed {m_seed!r}, not {args.seed!r}. "
              f"Blessing a seed no released build sends is how 23 submissions were "
              f"stranded. Ship a release carrying it first. Nothing was written.")
        return 1

    # ---- 3. ladder fork --------------------------------------------------
    if m_ladder != ladder:
        print(f"REFUSED: the manifest is on ladder {m_ladder}, the site on {ladder}. That "
              f"is an EPOCH CUT, not a seed roll: it needs an epochs[] row, a boundary and "
              f"board-probe-targets.json, done by hand -- see docs/LEAGUE_SEED_LEDGER.md. "
              f"Nothing was written.")
        return 1

    # ---- 4. already blessed ----------------------------------------------
    if cut.get("seed") == args.seed and cut.get("seed_status") == "blessed":
        print(f"NOTHING TO DO: {args.seed} is already the blessed seed (since "
              f"{cut.get('seed_blessed_on')}). Nothing was written.")
        return 1

    # ---- 5. the machine record -------------------------------------------
    current_rows = [e for e in contract.get("epochs", [])
                    if e.get("ladder_version") == ladder and e.get("status") == "current"]
    if len(current_rows) != 1:
        print(f"REFUSED: ladder-epochs.json has {len(current_rows)} current epochs[] rows "
              f"for {ladder}, expected exactly 1. Nothing was written.")
        return 1
    if args.dry_run:
        print(f"DRY RUN: would bless ({args.seed}, {ladder}) on {on} and open its week.")
        return 0
    previous = cut.get("seed")
    cut["seed"] = args.seed
    cut["seed_status"] = "blessed"
    cut["seed_blessed_on"] = on.isoformat()
    current_rows[0]["seed"] = args.seed
    write_json_like(epochs_path, contract, raw)
    print(f"WROTE      {epochs_path.relative_to(root)}: ({previous} -> {args.seed}, {ladder}), "
          f"blessed {on}")

    # ---- 6. the rollover -------------------------------------------------
    wlm._CONTRACT_CACHE[:] = []          # re-read the file just written
    if root != REPO_ROOT:
        wlm._CONTRACT_CACHE.append(contract)
    if not wlm.WeeklyLeagueManager(root=root).start_new_week():
        print("FAILED: the rollover refused or errored (above). ladder-epochs.json HAS "
              "been written -- revert it with git, or fix and re-run the rollover with "
              "`python scripts/weekly-league-manager.py --new-week`.")
        return 1

    print("\nNOW, BY HAND (the human half of the blessing):")
    print("  1. Add this row to docs/LEAGUE_SEED_LEDGER.md (edit the notes; keep the date):")
    print(f"     | {ladder} | `{args.seed}` | {ladder} | `board_{args.seed}__{ladder}.json` "
          f"| {on} | Pip | Weekly seed roll on {ladder}. Verified FROM THE ARTIFACT: "
          f"release_manifest.json league_seed `{args.seed}`, commit "
          f"`{str(manifest.get('commit_hash'))[:12]}`. |")
    print("  2. python scripts/check-blessing-consistency.py   (red until step 1 is done)")
    print("     python scripts/validate_data.py                (league:key, league:blessing_age)")
    print("  3. Open a PR. published-board.json follows by OBSERVATION once a client posts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
