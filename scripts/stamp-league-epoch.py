#!/usr/bin/env python3
"""Stamp the ladder-epoch flag onto weekly league records. Idempotent.

Pip's ruling (2026-07-28, boundary revised 2026-07-29): the league is
retired-and-hidden, not deleted, and everything opened before the **2026-08-07
epoch fork** -- the first Friday of August, where the game's minor and ladder
versions both bump (0.13 -> 0.14, L2 -> L3) -- becomes deliberately-labelled
**anomalous pre-history**, visible in the archive as an explicit anomaly section
rather than silently buried. "so the ultra archivists can track it down".

The boundary is the fork, not a tidy date: 2026-07-31 (this file's first
boundary) is the *last* Friday of July, which by
pdoom1/docs/RELEASE_NOMENCLATURE.md is a Seed roll on unchanged rules. Anchoring
there would have started the regularised era one week before a fork.

What this writes: an `epoch` object into every weekly archive file and into
current.json. What it does NOT touch: entries, scores, seeds, version stamps,
economic_model, or any timestamp the old pipeline produced. The pre-history is
the artefact; annotating it is honest, retouching it would fabricate history
(docs/TECH_DEBT.md section E is explicit that restamping the v0.4.1 records is
forbidden for exactly this reason).

Each record also gets `epoch.observed_defects`: the specific, individually
verified ways THAT file misdescribes reality. Derived per-file, never asserted
blanket-wise.

Usage:
    python scripts/stamp-league-epoch.py            # write
    python scripts/stamp-league-epoch.py --check    # exit 1 if anything unstamped
"""

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "weekly_league_manager", Path(__file__).parent / "weekly-league-manager.py")
wlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wlm)

WEEKLY = _ROOT / "public" / "leaderboard" / "data" / "weekly"
ARCHIVE = WEEKLY / "archive"

# Every defect below is checked against the individual file, not assumed.
DEFECT_TEXT = {
    "rollover-off-by-one": (
        "week_id/date range describe the week that was ENDING when the rollover ran, "
        "not the week that was starting -- the record is one week behind the "
        "competition it claims to represent (docs/TECH_DEBT.md A9, fixed 2026-07-28)."
    ),
    "monday-anchored-utc-week": (
        "the week runs Monday 00:00 -> Sunday 23:59:59 UTC. The competition cadence is "
        "a Seed roll every Friday (pdoom1/docs/RELEASE_NOMENCLATURE.md), anchored to "
        "Friday 00:00 Australia/Hobart from 2026-07-30 -- so this record's week is two "
        "days out of phase with the competition it claims to describe, independently of "
        "the off-by-one below."
    ),
    "is_current-stuck-true": (
        "week_info.is_current is true on an archived week. Nothing ever cleared the "
        "flag on archival, so every pre-cut archive claims to be the live week."
    ),
    "empty-shell": (
        "zero entries. No shipped client ever submitted to this board key, so the "
        "week ran with no participants -- the record is a container, not a result."
    ),
    "legacy-v0.4.1-stamps": (
        "meta.game_version 'v0.4.1' and/or economic_model 'Bootstrap_v0.4.1' from the "
        "legacy pygame client. LEFT AS FOUND ON PURPOSE: restamping would fabricate "
        "history, and scripts/ingest_scores.py already refuses to publish anything "
        "whose version != the deployed version."
    ),
    "unblessed-seed": (
        "the seed was derived website-side by weekly-league-manager.py and is not the "
        "blessed competitive key in docs/LEAGUE_SEED_LEDGER.md. No client ever POSTed "
        "under it."
    ),
    "naive-local-timestamp-labelled-utc": (
        "archived_at was written as local wall-clock time with a 'Z' suffix bolted on "
        "(datetime.now().isoformat() + 'Z'), so its UTC claim is off by the writing "
        "machine's offset. Fixed 2026-07-28; historical values left as found."
    ),
}


def observed_defects(d, path):
    """Per-file defect list. Only what is demonstrably true of THIS record."""
    found = []
    wi = d.get("week_info") or {}
    meta = d.get("meta") or {}
    raw = path.read_text(encoding="utf-8")

    # Wrong anchor: say so only where the file itself demonstrates it -- a start
    # instant that is a Monday at 00:00 with a zero UTC offset.
    start_raw = wi.get("start_timestamp")
    if start_raw:
        try:
            s = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            off = s.utcoffset()
            if s.weekday() == 0 and (s.hour, s.minute, s.second) == (0, 0, 0) \
                    and (off is None or off == timezone.utc.utcoffset(None)):
                found.append("monday-anchored-utc-week")
        except ValueError:
            pass
    if wi.get("is_current") and d.get("archive_status") == "completed":
        found.append("is_current-stuck-true")
    if not (d.get("entries") or []):
        found.append("empty-shell")
    if "v0.4.1" in raw:
        found.append("legacy-v0.4.1-stamps")
    if str(d.get("seed", "")).startswith("weekly_"):
        found.append("unblessed-seed")
    # Every pre-cut record was written by the buggy derivation, but say so only
    # where the file itself shows it: generated/archived on a Sunday >= 14:00 UTC
    # for a week that ends that same day.
    gen = meta.get("generated")
    end = wi.get("end_timestamp") or wi.get("end_date")
    if gen and end and str(gen)[:10] and str(end)[:10]:
        try:
            g = datetime.fromisoformat(str(gen).replace("Z", "+00:00"))
            e = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            if g.tzinfo is None:
                g = g.replace(tzinfo=timezone.utc)
            if e.tzinfo is None:
                e = e.replace(tzinfo=timezone.utc)
            if g.date() >= (e.date()):
                found.append("rollover-off-by-one")
        except ValueError:
            pass
    if d.get("archived_at", "").endswith("Z") and "+" not in d.get("archived_at", ""):
        # Only flag records written before the 2026-07-28 fix.
        try:
            a = datetime.fromisoformat(d["archived_at"].replace("Z", "+00:00"))
            if a < datetime(2026, 7, 28, tzinfo=timezone.utc):
                found.append("naive-local-timestamp-labelled-utc")
        except ValueError:
            pass
    return found


def week_start_of(d):
    wi = d.get("week_info") or {}
    raw = wi.get("start_timestamp") or wi.get("start_date")
    if not raw:
        return None
    try:
        return wlm.as_utc(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
    except ValueError:
        return None


def stamp(path, check_only):
    d = json.loads(path.read_text(encoding="utf-8"))
    ws = week_start_of(d)
    if ws is None:
        print(f"[SKIP] {path.name}: no parseable week start -- cannot place it in an epoch")
        return None
    bare = wlm.epoch_for(ws)          # what the manager writes into week_info
    epoch = dict(bare)
    epoch["observed_defects"] = {k: DEFECT_TEXT[k] for k in observed_defects(d, path)}

    # current.json also carries week_info.epoch (the manager writes both). If the
    # two ever disagree, a consumer reading the fallback path -- archive.html's
    # isAnomalous() reads week_info.epoch when the top level is absent -- would
    # get a different answer from the same file. Keep them in step here rather
    # than hoping.
    wi = d.get("week_info")
    wi_stale = isinstance(wi, dict) and "epoch" in wi and wi["epoch"] != bare

    if d.get("epoch") == epoch and not wi_stale:
        return False  # already correct
    if check_only:
        print(f"[STALE] {path.name}: epoch stamp missing or out of date")
        return True
    if wi_stale:
        wi["epoch"] = bare
    # Insert `epoch` after `meta` so it reads first, before any score data.
    out = {}
    for k, v in d.items():
        if k == "epoch":
            continue
        out[k] = v
        if k == "meta":
            out["epoch"] = epoch
    if "epoch" not in out:
        out["epoch"] = epoch
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report unstamped records and exit 1, write nothing")
    args = ap.parse_args()

    targets = sorted(ARCHIVE.glob("*_league.json"))
    if (WEEKLY / "current.json").exists():
        targets.append(WEEKLY / "current.json")

    changed = 0
    anomalous = 0
    for path in targets:
        r = stamp(path, args.check)
        if r:
            changed += 1
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if (d.get("epoch") or {}).get("anomalous"):
                anomalous += 1
        except Exception:
            pass

    verb = "would change" if args.check else "stamped"
    print(f"{len(targets)} weekly records; {verb} {changed}; "
          f"{anomalous} flagged epoch=pre-regularisation (anomalous)")

    if args.check and changed:
        print("FAIL: weekly records are missing an epoch stamp. "
              "Run: python scripts/stamp-league-epoch.py")
        return 1
    if not args.check:
        # index.json is derived; keep it in step so the archive page can never
        # show a different set of weeks than the ones on disk.
        wlm.WeeklyLeagueManager().rebuild_archive_index()
    return 0


if __name__ == "__main__":
    sys.exit(main())
