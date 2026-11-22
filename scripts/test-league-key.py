#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-failure test for validate_data.py's league:key, league:blessing_age and
league:current_week rows (2026-11-22, replacing league:freshness).

Pip asked, of the new key check: "what about silent successes that are hidden
failures?" Each case below is one of those, forced:

  key        mismatch | incomplete key | matching STRING on an unblessed record |
             a record that disagrees with itself | no blessed key declared |
             contract unreadable
  age        stood still past the window (FAIL) | one missed Friday (WARN) |
             no window declared | no blessing date | a future blessing date
  end date   null WITHOUT the marker is a defect, not "open"
  control    the all-agree, fresh world is OK -- so every red above means something

Run: python scripts/test-league-key.py   (exit 0 = pass)
"""
import copy
import importlib.util
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("vd", ROOT / "scripts" / "validate_data.py")
vd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vd)

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


BLESSED_ON = date(2026, 11, 27)
CONTRACT = {
    "regularised_from": {"seed": "weekly-2099-w01", "ladder_version": "L6",
                         "seed_status": "blessed", "seed_blessed_on": BLESSED_ON.isoformat()},
    "blessing_policy": {"warn_after_days": 8, "fail_after_days": 15, "source": "test"},
}
RECORD = {
    "seed": "weekly-2099-w01",
    "seed_provenance": {"blessed": True},
    "board_key": {"seed": "weekly-2099-w01", "ladder_version": "L6", "blessed": True},
    "meta": {"ladder_version": "L6", "end_date": None, "closes": "on_next_blessing"},
}
TODAY = BLESSED_ON + timedelta(days=3)


def rows(record=None, contract=None, today=TODAY, contract_text=None):
    tmp = Path(tempfile.mkdtemp()) / "ladder-epochs.json"
    tmp.write_text(contract_text if contract_text is not None
                   else json.dumps(contract or CONTRACT), encoding="utf-8")
    vd.LADDER_EPOCHS = tmp
    vd.checks.clear()
    vd.check_league_blessing(record or RECORD, today)
    return {r["name"]: (r["status"], r["detail"]) for r in vd.checks}


def with_(base, path, value):
    d = copy.deepcopy(base)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    if value is ...:
        cur.pop(path[-1], None)
    else:
        cur[path[-1]] = value
    return d


print("0. CONTROL: the all-agree, freshly blessed world is OK")
r = rows()
check(r["league:key"][0] == "OK", f"league:key OK ({r['league:key'][0]})")
check(r["league:blessing_age"][0] == "OK", f"league:blessing_age OK ({r['league:blessing_age'][0]})")

print("\n1. league:key -- every way to agree by accident is RED")
for label, rec, con, needle in (
        ("seed mismatch", with_(with_(RECORD, ["board_key", "seed"], "weekly-2099-w00"),
                                ["seed"], "weekly-2099-w00"), None, "blessed key is"),
        ("ladder mismatch", with_(with_(RECORD, ["board_key", "ladder_version"], "L5"),
                                  ["meta", "ladder_version"], "L5"), None, "blessed key is"),
        ("incomplete key", with_(RECORD, ["board_key", "ladder_version"], ...), None,
         "incomplete"),
        ("matching STRING, record labelled unblessed",
         with_(RECORD, ["seed_provenance", "blessed"], False), None, "not labelled blessed"),
        ("record disagrees with itself", with_(RECORD, ["seed"], "weekly-2099-w00"), None,
         "disagrees with itself"),
        ("no blessed key declared", None,
         with_(CONTRACT, ["regularised_from", "seed_status"], "unblessed"),
         "declares no blessed key")):
    r = rows(rec, con)
    check(r["league:key"][0] == "FAIL" and needle in r["league:key"][1],
          f"{label}: FAIL, and says why ({r['league:key'][0]})")
r = rows(contract_text="{ not json")
check(r["league:key"][0] == "FAIL" and r["league:blessing_age"][0] == "FAIL",
      "contract unreadable: both rows FAIL -- absence is never agreement")

print("\n2. league:blessing_age -- the league standing still is a finding")
r = rows(today=BLESSED_ON + timedelta(days=16))
check(r["league:blessing_age"][0] == "FAIL", "16 days: two missed Fridays -> FAIL")
r = rows(today=BLESSED_ON + timedelta(days=15))
check(r["league:blessing_age"][0] == "WARN", "15 days: boundary is WARN, not FAIL (no fencepost)")
r = rows(today=BLESSED_ON + timedelta(days=9))
check(r["league:blessing_age"][0] == "WARN", "9 days: one missed Friday -> WARN")
r = rows(today=BLESSED_ON + timedelta(days=8))
check(r["league:blessing_age"][0] == "OK", "8 days: still OK")
r = rows(today=BLESSED_ON + timedelta(days=16))
check(r["league:key"][0] == "OK",
      "...and a stale blessing does not disguise itself as a key problem (key still OK)")
for label, con in (("no window declared", with_(CONTRACT, ["blessing_policy"], ...)),
                   ("an inverted window", with_(CONTRACT, ["blessing_policy",
                                                           "warn_after_days"], 20)),
                   ("no blessing date", with_(CONTRACT, ["regularised_from",
                                                         "seed_blessed_on"], ...)),
                   ("a future blessing date", with_(CONTRACT, ["regularised_from",
                                                               "seed_blessed_on"],
                                                    "2999-01-01"))):
    r = rows(contract=con)
    check(r["league:blessing_age"][0] == "FAIL", f"{label}: FAIL, never a pass")

print("\n3. league:current_week -- a null end needs the marker")
real = json.loads((ROOT / "public/leaderboard/data/weekly/current.json")
                  .read_text(encoding="utf-8"))
src = (ROOT / "scripts" / "validate_data.py").read_text(encoding="utf-8")
check('"league:current_week", FAIL' in src.replace("\r\n", "\n").replace("\n            ", " ")
      or "open-ended by accident is not open" in src,
      "[source] the no-marker branch is a FAIL, not a WARN or a skip")
tmp = Path(tempfile.mkdtemp())
pub = tmp / "public" / "leaderboard" / "data" / "weekly"
pub.mkdir(parents=True)
saved = vd.PUBLIC
try:
    for label, closes, want in (("with the marker", "on_next_blessing", "OK"),
                                ("WITHOUT the marker", None, "FAIL")):
        rec = copy.deepcopy(real)
        rec.setdefault("week_info", {})["end_timestamp"] = None
        rec["week_info"]["end_date"] = None
        rec["meta"]["closes"] = closes
        (pub / "current.json").write_text(json.dumps(rec), encoding="utf-8")
        vd.PUBLIC = tmp / "public"
        vd.LADDER_EPOCHS = ROOT / "public" / "data" / "ladder-epochs.json"
        vd.checks.clear()
        vd.check_weekly_league(date.today())
        got = next((r["status"] for r in vd.checks if r["name"] == "league:current_week"), None)
        check(got == want, f"null end {label}: {want} (got {got})")
finally:
    vd.PUBLIC = saved

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) failed")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("OK: the key check cannot agree by accident, a league that stands still is a "
      "finding, absence is never a pass, and an open-ended week needs its marker.")
