#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check-board-liveness.py -- READ-ONLY live probe of the PHP score API.

WHY THIS EXISTS
---------------
A leaderboard board is keyed by (seed, game_version) -- pdoom1 PR #679. When a
submitting client's key does not match the board anyone reads, the score lands on
a board nobody looks at and the player is shown no error. From the outside that is
indistinguishable from "nobody is playing".

Nothing in this repo has ever read the score API. The website publishes
leaderboard.json by aggregating LOCAL seed files, so "0 entries" on the site has
never been evidence about the API one way or the other. This script closes that
gap: it asks the API directly and records what it found, with a timestamp, so
"the board is empty" becomes a dated observation instead of a mystery.

CONTRACT (do not break)
-----------------------
pdoom1 PR #679 makes this repo a READ-ONLY consumer of ONE score API. This script
issues GETs only. It never POSTs, never writes to the API, and never re-stamps a
version -- re-stamping would fabricate history. It writes exactly one local file,
public/leaderboard/data/board-liveness.json, which is an OBSERVATION record, not a
score store.

WHAT IT REPORTS
---------------
  1. The deployed board -- (current weekly seed, deployed game version) -- and how
     many entries the API holds for it.
  2. Every other (seed, version) board it probes that DOES hold entries. Those are
     orphaned scores: real runs by real players that no visitor to pdoom1.com can
     see.

EXIT CODES (so CI can go red on the state that matters)
  0  consistent -- either the deployed board has entries, or nothing anywhere does
  1  LOUD -- entries exist on some board, but not on the deployed one. Scores are
     being recorded and are invisible to visitors.
  2  the API could not be reached / did not answer usefully (unknown, not "empty")

RUN
    python scripts/check-board-liveness.py
    python scripts/check-board-liveness.py --seed weekly-2026-w0 --seed other-seed
    python scripts/check-board-liveness.py --check      # no file write, exit code only
"""

import argparse
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# CLAUDE.md: the Windows console is cp1252 and dies on the FIRST non-ASCII print,
# before doing any work. Reconfigure before anything else can print.
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
PUBLIC = ROOT / "public"
LB_DIR = PUBLIC / "leaderboard" / "data"
VERSION_JSON = PUBLIC / "data" / "version.json"
WEEKLY_JSON = LB_DIR / "weekly" / "current.json"
SNAPSHOT_JSON = LB_DIR / "leaderboard.json"
OUT_JSON = LB_DIR / "board-liveness.json"

SCORE_API = "https://api.pdoom1.com/score_api.php"
RELEASES_API = "https://api.github.com/repos/PipFoweraker/pdoom1/releases"

# Seeds observed in real client traffic that the website does not derive itself.
# This is a PROBE LIST, not a source of truth: it exists so the check can still see
# an orphaned board whose seed the website has no other way to learn. Nothing here
# is ever published as "the current seed" -- that always comes from weekly/current.json.
OBSERVED_CLIENT_SEEDS = [
    "weekly-2026-w0",   # seen live 2026-07-28 holding v0.11.0 and v0.12.0 entries
]

# Versions probed in addition to the deployed one. Derived from the pdoom1 releases
# API at run time so this list cannot rot into a hardcoded literal; the constant below
# is only the fallback COUNT of recent releases to look back over.
RECENT_RELEASES_TO_PROBE = 6


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def get_json(url, headers=None, timeout=20):
    """GET only. Returns (data, error_string)."""
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %s" % e.code
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def deployed_version():
    """The version the site says is current. Absence is 'unknown', never a literal."""
    v = load_json(VERSION_JSON, {}) or {}
    lr = v.get("latest_release") if isinstance(v, dict) else None
    return (lr or {}).get("version")


def website_weekly_seed():
    w = load_json(WEEKLY_JSON, {}) or {}
    return w.get("seed"), ((w.get("meta") or {}).get("game_version"))


def probe_board(seed, version):
    """Read one board. Returns dict with count, or error."""
    q = urllib.parse.urlencode({"seed": seed, "version": version})
    data, err = get_json("%s?%s" % (SCORE_API, q))
    if err:
        return {"seed": seed, "version": version, "error": err, "entries": None}
    if not isinstance(data, dict) or not data.get("ok"):
        return {"seed": seed, "version": version,
                "error": "unexpected payload: %s" % json.dumps(data)[:120],
                "entries": None}
    entries = data.get("entries") or []
    players = sorted({e.get("player_name") for e in entries if e.get("player_name")})
    dates = sorted(e.get("date") for e in entries if e.get("date"))
    return {
        "seed": seed,
        "version": version,
        "entries": len(entries),
        "players": len(players),
        "first_entry": dates[0] if dates else None,
        "last_entry": dates[-1] if dates else None,
    }


def candidate_versions(deployed, extra):
    """Deployed + recent published releases + anything the caller named.

    Pulled from the releases API rather than hardcoded, so the probe set follows the
    game instead of rotting. If GitHub is unreachable we probe what we know locally
    and SAY SO -- we do not silently shrink the search and call it a clean result.
    """
    seen, out, note = set(), [], None
    for v in [deployed] + list(extra):
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    rel, err = get_json(RELEASES_API, {"Accept": "application/vnd.github+json"})
    if err:
        note = "GitHub releases unreachable (%s) -- probed only locally-known versions" % err
    else:
        for r in (rel or [])[:RECENT_RELEASES_TO_PROBE]:
            tag = r.get("tag_name")
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return out, note


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="append", default=[],
                    help="extra seed to probe (repeatable)")
    ap.add_argument("--version", action="append", default=[],
                    help="extra version to probe (repeatable)")
    ap.add_argument("--check", action="store_true",
                    help="exit code only, do not write board-liveness.json")
    args = ap.parse_args()

    deployed = deployed_version()
    site_seed, weekly_stamp = website_weekly_seed()
    snapshot = load_json(SNAPSHOT_JSON, {}) or {}
    snap_ver = (snapshot.get("meta") or {}).get("game_version")
    snap_entries = len(snapshot.get("entries") or [])

    print("Board liveness probe -- %s" % now_iso())
    print("=" * 72)
    print("  deployed game version   %s" % (deployed or "UNKNOWN (version.json has no latest_release.version)"))
    print("  website weekly seed     %s" % (site_seed or "UNKNOWN"))
    print("  weekly stamp            %s" % (weekly_stamp or "UNKNOWN"))
    print("  published snapshot      %s, %d entries" % (snap_ver or "UNKNOWN", snap_entries))
    print()

    if not deployed:
        # A missing deployed version is itself the loud condition: every comparison
        # downstream would be vacuously "fine". Never treat absence as agreement.
        print("  FAIL: cannot determine the deployed version, so no board comparison is")
        print("        meaningful. version.json has no latest_release.version.")
        return 2

    seeds, seen = [], set()
    for s in [site_seed] + OBSERVED_CLIENT_SEEDS + list(args.seed):
        if s and s not in seen:
            seen.add(s)
            seeds.append(s)
    versions, ver_note = candidate_versions(deployed, [snap_ver] + list(args.version))
    if ver_note:
        print("  note: %s" % ver_note)

    results, errors = [], 0
    for s in seeds:
        for v in versions:
            r = probe_board(s, v)
            if r.get("error"):
                errors += 1
            results.append(r)

    deployed_board = next(
        (r for r in results if r["seed"] == site_seed and r["version"] == deployed), None)
    populated = [r for r in results if (r.get("entries") or 0) > 0]
    orphaned = [r for r in populated
                if not (r["seed"] == site_seed and r["version"] == deployed)]
    deployed_count = (deployed_board or {}).get("entries")

    print("  probed %d board(s) across %d seed(s) x %d version(s); %d unreachable"
          % (len(results), len(seeds), len(versions), errors))
    print("-" * 72)
    for r in results:
        if r.get("error"):
            print("  [ERR ] %-28s %-9s  %s" % (r["seed"][:28], r["version"], r["error"]))
        elif r["entries"]:
            print("  [%4d] %-28s %-9s  %d player(s), %s .. %s"
                  % (r["entries"], r["seed"][:28], r["version"], r["players"],
                     (r["first_entry"] or "?")[:10], (r["last_entry"] or "?")[:10]))
    if not populated:
        print("  (no probed board holds any entry)")
    print("-" * 72)

    # ---- the verdict, stated in counts, never as a bare "0 entries" ----------
    if orphaned:
        total = sum(r["entries"] for r in orphaned)
        verdict = "orphaned-scores"
        exit_code = 1
        print()
        print("  !! LOUD: %d score entr%s exist on the live API on %d board(s) that NO"
              % (total, "y" if total == 1 else "ies", len(orphaned)))
        print("     visitor to pdoom1.com can see.")
        print("     Deployed board (%s, %s) holds %s."
              % (site_seed, deployed,
                 "%d entries" % deployed_count if deployed_count is not None
                 else "an unknown number of entries -- it could not be read"))
        for r in orphaned:
            print("       - (%s, %s): %d entries, %d player(s), %s .. %s"
                  % (r["seed"], r["version"], r["entries"], r["players"],
                     (r["first_entry"] or "?")[:10], (r["last_entry"] or "?")[:10]))
        print()
        print("     The board key is (seed, game_version). These entries did not fail to")
        print("     save -- they saved to a key nothing reads. Do NOT 'fix' this by")
        print("     re-stamping a version: that fabricates history. The game must submit")
        print("     to the board the site publishes, or the site must publish the board")
        print("     the game submits to.")
    elif deployed_count:
        verdict = "live"
        exit_code = 0
        print()
        print("  OK: deployed board (%s, %s) holds %d entries."
              % (site_seed, deployed, deployed_count))
    elif errors == len(results):
        verdict = "unreachable"
        exit_code = 2
        print()
        print("  UNKNOWN: every probe failed. This is NOT evidence that the board is")
        print("  empty -- it is evidence that we cannot tell. Treat as unknown.")
    else:
        verdict = "genuinely-empty"
        exit_code = 0
        print()
        print("  Deployed board (%s, %s) holds 0 entries, and no other probed board"
              % (site_seed, deployed))
        print("  holds any either. As of this timestamp, nobody has submitted a score")
        print("  that this probe can see. That is an observation, not an assumption.")

    record = {
        "_comment": "Read-only observation of the live score API. Not a score store. "
                    "Written by scripts/check-board-liveness.py.",
        "checked_at": now_iso(),
        "api": SCORE_API,
        "verdict": verdict,
        "deployed": {"version": deployed, "seed": site_seed,
                     "entries": deployed_count},
        "published_snapshot": {"game_version": snap_ver, "entries": snap_entries},
        "probe": {"seeds": seeds, "versions": versions,
                  "boards_probed": len(results), "unreachable": errors,
                  "note": ver_note},
        "orphaned_boards": orphaned,
        "orphaned_entries_total": sum(r["entries"] for r in orphaned),
        "boards": results,
    }

    if not args.check:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(record, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
        print()
        print("  wrote %s" % OUT_JSON.relative_to(ROOT))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
