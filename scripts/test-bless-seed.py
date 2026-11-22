#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-failure test for the blessing-driven league (2026-11-22, D1 (i)).

Covers scripts/bless-seed.py and the rollover changes in weekly-league-manager.py.
Every refusal is FORCED and then checked against the bytes on disk, because "it
refused" and "it refused having already written half the record" print the same
line. Everything runs in a temp copy of the real artefacts; the repo is not touched.

  bless-seed   unreachable manifest -> exit 2, nothing written
               manifest on another seed -> refused, nothing written
               manifest on another ladder (an epoch cut) -> refused, nothing written
               seed already blessed -> refused, nothing written
               future --on -> refused
               the real path -> all four contract fields move together, the
                 previous week is archived AT THIS MOMENT, the new week has no
                 end date and carries the marker, and validate_data agrees
  rollover     second run with nothing new -> NO-OP, byte-identical
               no blessed seed -> REFUSED, current.json untouched
               two blessings in one week -> both archives survive
               a failing archive -> current.json is NOT replaced

Run: python scripts/test-bless-seed.py   (exit 0 = pass)
"""
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "scripts"
failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bless = load("bless_seed", "bless-seed.py")
vd = load("validate_data_mod", "validate_data.py")

COPY = ["public/data/ladder-epochs.json", "public/data/version.json",
        "public/leaderboard/data/weekly/current.json", "scripts/weekly-league-config.json"]
REAL_CONTRACT = json.loads((ROOT / COPY[0]).read_text(encoding="utf-8"))
LADDER = REAL_CONTRACT["regularised_from"]["ladder_version"]
SEED = REAL_CONTRACT["regularised_from"]["seed"]
NEW = "weekly-2099-w01"          # a seed no real build will ever carry


def tree():
    t = Path(tempfile.mkdtemp())
    for rel in COPY:
        (t / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, t / rel)
    (t / "public/leaderboard/data/weekly/archive").mkdir(parents=True, exist_ok=True)
    return t


def manifest(t, seed=NEW, ladder=LADDER.lstrip("L")):
    p = t / "release_manifest.json"
    p.write_text(json.dumps({"league_seed": seed, "ladder_version": ladder,
                             "commit_hash": "f" * 40}), encoding="utf-8")
    return p


def snapshot(t):
    return {p.relative_to(t).as_posix(): p.read_bytes()
            for p in t.rglob("*") if p.is_file() and p.name != "release_manifest.json"}


def run_bless(t, *argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = bless.main(["--root", str(t), *argv])
    return code, out.getvalue()


def manager(t, contract=None):
    wlm = bless._load("weekly_league_manager", "weekly-league-manager.py")
    wlm._CONTRACT_CACHE[:] = [contract or json.loads(
        (t / COPY[0]).read_text(encoding="utf-8"))]
    return wlm, wlm.WeeklyLeagueManager(root=t)


def current(t):
    return json.loads((t / COPY[2]).read_text(encoding="utf-8"))


print("0. Precondition: the copied current.json is on the blessed key")
t = tree()
c = current(t)
check((c.get("board_key") or {}).get("seed") == SEED,
      f"fixture starts on ({SEED}, {LADDER}) -- otherwise the cases below prove nothing")
shutil.rmtree(t, ignore_errors=True)

print("\n1. bless-seed REFUSES, and writes nothing, whenever a check fails")
for label, kw, argv, want in (
        ("an unreachable manifest", None, ["--manifest", "https://127.0.0.1:9/nope.json"], 2),
        ("a manifest on another seed", {"seed": "weekly-2099-w02"}, [], 1),
        ("a manifest on another ladder (epoch cut)", {"ladder": "99"}, [], 1),
        ("a seed that is already blessed", {"seed": SEED}, ["--seed-override", SEED], 1),
        ("a future-dated blessing", {}, ["--on", "2999-01-01"], 1)):
    t = tree()
    before = snapshot(t)
    m = manifest(t, **(kw or {})) if kw is not None else None
    seed = NEW
    argv = list(argv)
    if "--seed-override" in argv:
        seed = argv[argv.index("--seed-override") + 1]
        argv = argv[:argv.index("--seed-override")]
    if m is not None and "--manifest" not in argv:
        argv += ["--manifest", str(m)]
    code, out = run_bless(t, "--seed", seed, *argv)
    check(code == want, f"{label}: exit {want} (got {code})")
    check(snapshot(t) == before, f"{label}: every file byte-identical afterwards")
    shutil.rmtree(t, ignore_errors=True)

print("\n2. The real path: blessing moves the record and opens the week")
t = tree()
before_week = current(t)
code, out = run_bless(t, "--seed", NEW, "--manifest", str(manifest(t)))
check(code == 0, f"exit 0 (got {code})")
contract = json.loads((t / COPY[0]).read_text(encoding="utf-8"))
cut = contract["regularised_from"]
cur_rows = [e for e in contract["epochs"]
            if e.get("ladder_version") == LADDER and e.get("status") == "current"]
check(cut["seed"] == NEW and cut["seed_status"] == "blessed" and cut["seed_blessed_on"]
      and cur_rows and cur_rows[0]["seed"] == NEW,
      "regularised_from.seed / seed_status / seed_blessed_on and the epochs[] row move together")
c = current(t)
check(c["board_key"] == {"seed": NEW, "ladder_version": LADDER, "shape": "(seed, L<n>)",
                         "blessed": True}, "current.json is on the NEW blessed key")
check(c["meta"]["end_date"] is None and c["week_info"]["end_timestamp"] is None
      and c["meta"]["closes"] == "on_next_blessing",
      "the new week has NO end date, and carries the marker that makes that legitimate")
arch = list((t / "public/leaderboard/data/weekly/archive").glob("*_league.json"))
check(len(arch) == 1, f"the previous week was archived ({len(arch)} file)")
if arch:
    a = json.loads(arch[0].read_text(encoding="utf-8"))
    check(a["seed"] == before_week["seed"] and a["week_info"]["end_timestamp"]
          and a["week_info"]["status"] == "ended",
          "the archive is the previous week, closed with a real end time")
check("LEAGUE_SEED_LEDGER.md" in out and f"`{NEW}`" in out,
      "it prints the ledger row for a human to add -- it does not write it")
vd.checks.clear()
vd.LADDER_EPOCHS = t / COPY[0]
vd.check_league_blessing(c, vd.datetime.now(vd.timezone.utc).date())
rows = {r["name"]: r["status"] for r in vd.checks}
check(rows.get("league:key") == "OK", f"validate_data agrees: league:key {rows.get('league:key')}")
check(rows.get("league:blessing_age") == "OK",
      f"...and the blessing is fresh: league:blessing_age {rows.get('league:blessing_age')}")

print("\n3. The rollover is idempotent, out loud")
before = snapshot(t)
wlm, mgr = manager(t)
buf = io.StringIO()
with redirect_stdout(buf):
    ok = mgr.start_new_week()
check(ok and "NO-OP" in buf.getvalue(), "a second rollover with nothing new says NO-OP")
check(snapshot(t) == before, "...and changes no byte")
shutil.rmtree(t, ignore_errors=True)

print("\n4. The rollover REFUSES an unblessed seed")
t = tree()
unblessed = json.loads((t / COPY[0]).read_text(encoding="utf-8"))
unblessed["regularised_from"]["seed"] = None
unblessed["regularised_from"]["seed_status"] = "unblessed"
(t / COPY[2]).unlink()            # so the no-op branch cannot be what answers
before = snapshot(t)
wlm, mgr = manager(t, unblessed)
buf = io.StringIO()
with redirect_stdout(buf):
    ok = mgr.start_new_week()
check(not ok and "REFUSED" in buf.getvalue(),
      "no blessed seed -> REFUSED (a derived placeholder is not a league week)")
check(snapshot(t) == before and not (t / COPY[2]).exists(),
      "...and no current.json was written")
shutil.rmtree(t, ignore_errors=True)

print("\n5. Two blessings in one week: both archives survive")
t = tree()
code1, _ = run_bless(t, "--seed", NEW, "--manifest", str(manifest(t)))
code2, _ = run_bless(t, "--seed", "weekly-2099-w02",
                     "--manifest", str(manifest(t, seed="weekly-2099-w02")))
arch = sorted(p.name for p in (t / "public/leaderboard/data/weekly/archive").glob("*_league.json"))
check(code1 == 0 and code2 == 0 and len(arch) == 2,
      f"two archives, neither overwritten: {arch}")
shutil.rmtree(t, ignore_errors=True)

print("\n6. A failing archive does NOT replace the live week")
t = tree()
before = current(t)
wlm, mgr = manager(t)
mgr.archive_current_week = lambda now=None: False
contract = json.loads((t / COPY[0]).read_text(encoding="utf-8"))
contract["regularised_from"]["seed"] = NEW
wlm._CONTRACT_CACHE[:] = [contract]
buf = io.StringIO()
with redirect_stdout(buf):
    ok = mgr.start_new_week()
check(not ok and current(t) == before,
      "archive failed -> rollover refused, current.json unchanged")
shutil.rmtree(t, ignore_errors=True)

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) failed")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("OK: every refusal was forced and wrote nothing; the real path moves the whole "
      "record and opens an open-ended week; the rollover is idempotent and never "
      "overwrites history.")
