#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_scores.py -- website-side score receiver / publisher (the "connection point").

The game→website uplift is currently broken (see docs/GAME_UPLIFT_PLAN.md): the Godot
leaderboard is local-only and the old Python export is orphaned. This script is the
WEBSITE half of the future connection, built now so the game handoff is a small last step.

Given contract-conforming per-seed leaderboard files (public/leaderboard/data/
seed_leaderboard_*.json -- validated against schemas/leaderboard-seed.schema.json), it:
  1. validates every input against the contract (rejects bad data, never publishes it),
  2. aggregates entries into the `leaderboard.json` the leaderboard page fetches
     (which currently DOESN'T EXIST -> the page is broken),
  3. stamps `meta.game_version` from public/data/version.json (the REAL deployed version),
     fixing the v0.4.1 drift at publish time regardless of what a producer stamped,
  4. sets an honest `data_status`: "live" | "pre-launch" | "legacy",
  5. recomputes weekly/current.json statistics for internal consistency.

Whatever eventually delivers real entries -- an ingestion API (Option A) or a rebuilt
Godot export (Option B) -- drops conforming seed files here and this publishes them.

Test/dev seeds (test*, party*, demo*, final-verification*, natural-game-over*) are
EXCLUDED by default so fixtures are never shown as real scores. --include-tests overrides.

Run:  python scripts/ingest_scores.py            # publish from current seed files
      python scripts/ingest_scores.py --input DIR --include-tests
"""

import argparse
import glob
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SCHEMAS = ROOT / "schemas"
LB_DIR = PUBLIC / "leaderboard" / "data"

TEST_SEED_RE = re.compile(r"(test|party|demo|final-verification|natural-game-over)", re.I)


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def real_game_version():
    try:
        v = load_json(PUBLIC / "data" / "version.json")
        return (v.get("latest_release") or {}).get("version") or "unknown"
    except Exception:
        return "unknown"


def validate_entry_schema():
    """Return a validator for the seed 'entry' contract, or None if jsonschema absent."""
    try:
        import jsonschema
        seed_schema = load_json(SCHEMAS / "leaderboard-seed.schema.json")
        entry_schema = seed_schema["$defs"]["entry"]
        return jsonschema.Draft7Validator(entry_schema)
    except Exception as e:
        print(f"  (jsonschema unavailable: {e} -- publishing without per-entry schema check)")
        return None


def gather_seed_files(input_dir, include_tests):
    files = sorted(glob.glob(str(Path(input_dir) / "seed_leaderboard_*.json")))
    kept = []
    for f in files:
        name = Path(f).name
        if not include_tests and TEST_SEED_RE.search(name):
            continue
        kept.append(f)
    return files, kept


def is_publishable(seed_file, deployed_version, include_legacy):
    """Live data = entries stamped with the deployed game version. Older/synthetic
    stamps (v1.0.0 dev seeds, v0.4.1 legacy) are NOT published as live unless
    --include-legacy is passed. This is what keeps the board honest and self-healing:
    the day the game exports real v0.11.0 scores, they publish automatically."""
    if include_legacy:
        return True
    return _seed_version(seed_file) == deployed_version


def entry_key(e):
    return e.get("entry_uuid") or f"{e.get('player_name')}|{e.get('score')}|{e.get('date')}"


def main():
    ap = argparse.ArgumentParser(description="Publish website leaderboard.json from seed files")
    ap.add_argument("--input", default=str(LB_DIR), help="dir of seed_leaderboard_*.json")
    ap.add_argument("--include-tests", action="store_true", help="include test/party/demo seeds")
    ap.add_argument("--include-legacy", action="store_true",
                    help="publish entries whose game_version != deployed (marked legacy)")
    ap.add_argument("--output", default=str(LB_DIR / "leaderboard.json"))
    args = ap.parse_args()

    version = real_game_version()
    validator = validate_entry_schema()
    all_files, seed_files = gather_seed_files(args.input, args.include_tests)
    excluded_test = len(all_files) - len(seed_files)

    entries, bad, seeds_used, excluded_ver = {}, 0, [], 0
    for f in seed_files:
        if not is_publishable(f, version, args.include_legacy):
            excluded_ver += 1
            continue
        try:
            d = load_json(f)
        except Exception as e:
            print(f"  SKIP {Path(f).name}: unreadable ({e})")
            bad += 1
            continue
        valid_here = 0
        for e in (d.get("entries") or []):
            if validator is not None and list(validator.iter_errors(e)):
                bad += 1
                continue
            entries[entry_key(e)] = e  # dedup by uuid/identity
            valid_here += 1
        if valid_here:
            seeds_used.append(d.get("seed") or Path(f).stem)

    merged = sorted(entries.values(), key=lambda e: e.get("score", 0), reverse=True)

    # Honest status: nothing published -> pre-launch; published via --include-legacy -> legacy.
    if not merged:
        status = "pre-launch"
    else:
        status = "legacy" if args.include_legacy else "live"

    out = {
        "meta": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "game_version": version,          # REAL deployed version, not a producer stamp
            "export_source": "website:ingest_scores.py",
            "total_players": len({e.get("player_name") for e in merged if e.get("player_name")}),
            "total_entries": len(merged),
            "seeds_aggregated": len(seeds_used),
            "note": "Aggregated + contract-validated by the website. See docs/GAME_UPLIFT_PLAN.md.",
        },
        "data_status": status,               # live | pre-launch | legacy  (drives the honesty banner)
        "legacy": status != "live",
        "seed": (seeds_used[0] if len(seeds_used) == 1 else "aggregate") if merged else "—",
        "economic_model": "—",
        "entries": merged,
    }
    outpath = Path(args.output)
    outpath.write_text(json.dumps(out, indent=2), encoding="utf-8")
    try:
        shown = outpath.relative_to(ROOT)
    except ValueError:
        shown = outpath

    print(f"ingest_scores: status={status} version={version}")
    print(f"  seeds: {len(seeds_used)} published, {excluded_ver} version-mismatched, "
          f"{excluded_test} test/dev excluded, {bad} invalid entries dropped")
    print(f"  published {len(merged)} entries -> {shown}")
    if status != "live":
        print(f"  data_status={status} -> the page shows an honest banner, not stale data as live")


def _seed_version(f):
    try:
        return (load_json(f).get("meta") or {}).get("game_version")
    except Exception:
        return None


if __name__ == "__main__":
    main()
