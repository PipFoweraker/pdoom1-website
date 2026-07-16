#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_data.py -- contract + integrity validation for the p(Doom)1 data seams.

Validates the data files the website consumes against the JSON Schemas in schemas/
(the enforced contracts), then layers on semantic checks that schemas cannot express:
encoding corruption, freshness, cross-repo version drift, and referential integrity.

Severity model (the whole point -- conserve a solo dev's attention):
  FAIL  = unambiguous bug. Breaks CI, warrants ONE actionable alert. (schema
          violations, mojibake, self-contradictory data)
  WARN  = drift/staleness worth a human glance, shown on the health dashboard but
          NEVER alerted. (version lag, a 'current' week that has ended)
  OK    = fine, stay silent.

Emits public/data/integration-health.json for the /monitoring/ dashboard, and exits
non-zero iff any FAIL -- so CI goes red on real breakage, quiet on drift.

Run:  python scripts/validate_data.py            (full run, writes health json)
      python scripts/validate_data.py --check    (exit-code only, no file write)
"""

import glob
import io
import json
import re
import sys
from datetime import datetime, timezone, date
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SCHEMAS = ROOT / "schemas"

FAIL, WARN, OK = "FAIL", "WARN", "OK"
checks = []  # list of {name, status, detail}


def add(name, status, detail=""):
    checks.append({"name": name, "status": status, "detail": detail})


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---- schema validation (jsonschema preferred; degrade gracefully) --------------
def validate_schema(name, data_path, schema_name):
    try:
        import jsonschema
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
    except Exception:
        # Fallback: jsonschema present but no referencing (older), or absent.
        try:
            import jsonschema  # noqa
        except Exception:
            add(f"schema:{name}", WARN, "jsonschema not installed -- schema check skipped (pip install jsonschema)")
            return
    try:
        data = load_json(data_path)
    except FileNotFoundError:
        add(f"schema:{name}", WARN, f"{data_path} not found -- skipped")
        return
    except Exception as e:
        add(f"schema:{name}", FAIL, f"{data_path} is not valid JSON: {e}")
        return

    schema = load_json(SCHEMAS / schema_name)
    try:
        import jsonschema
        # Resolve cross-file $refs (weekly -> seed) by loading all schemas into a store.
        store = {}
        for sf in SCHEMAS.glob("*.schema.json"):
            s = load_json(sf)
            store[sf.name] = s
            if "$id" in s:
                store[s["$id"]] = s
        resolver = jsonschema.RefResolver(base_uri="", referrer=schema, store=store)
        validator = jsonschema.Draft7Validator(schema, resolver=resolver)
        errs = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if not errs:
            add(f"schema:{name}", OK, "valid")
        else:
            e = errs[0]
            loc = "/".join(str(p) for p in e.path) or "(root)"
            add(f"schema:{name}", FAIL, f"{len(errs)} violation(s); first at {loc}: {e.message[:160]}")
    except Exception as e:
        add(f"schema:{name}", WARN, f"schema check errored: {e}")


# ---- encoding corruption (the mojibake class) ----------------------------------
MOJIBAKE = [chr(0x00E2) + chr(0x2020) + chr(0x2019),  # -> double-encoded
            chr(0x00E2) + chr(0x20AC) + chr(0x2122),  # ' curly
            chr(0x00E2) + chr(0x20AC) + chr(0x201D)]  # -- em dash


def check_encoding(name, path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    hits = {m: text.count(m) for m in MOJIBAKE if m in text}
    if hits:
        add(f"encoding:{name}", FAIL, f"mojibake found: {hits} (double-encoded chars in source)")
    else:
        add(f"encoding:{name}", OK, "no mojibake")


# ---- leaderboard freshness / version / integrity -------------------------------
def parse_dt(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # assume UTC for naive timestamps so arithmetic with now(utc) works
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def check_weekly_league():
    path = PUBLIC / "leaderboard" / "data" / "weekly" / "current.json"
    try:
        d = load_json(path)
    except FileNotFoundError:
        add("league:present", FAIL, "weekly/current.json missing")
        return
    now = datetime.now(timezone.utc)

    # freshness
    gen = parse_dt((d.get("meta") or {}).get("generated"))
    if gen:
        age_days = (now - gen).total_seconds() / 86400
        if age_days > 9:
            add("league:freshness", FAIL, f"current.json is {age_days:.1f} days old -- weekly rollover likely stalled")
        elif age_days > 7:
            add("league:freshness", WARN, f"current.json is {age_days:.1f} days old (rollover due)")
        else:
            add("league:freshness", OK, f"generated {age_days:.1f} days ago")
    else:
        add("league:freshness", WARN, "no parseable meta.generated")

    # current week actually current?
    wi = d.get("week_info") or {}
    end = None
    for k in ("end_timestamp", "end_date"):
        end = end or parse_dt(wi.get(k))
    if wi.get("is_current") and end:
        past = (now - end).total_seconds() / 86400
        if past > 2:
            add("league:current_week", WARN,
                f"week {wi.get('week_id')} is marked is_current but ended {past:.1f} days ago -- rollover cadence off")
        else:
            add("league:current_week", OK, f"week {wi.get('week_id')} current")

    # version drift vs deployed game version
    try:
        ver = load_json(PUBLIC / "data" / "version.json")
        deployed = (ver.get("latest_release") or {}).get("version")
        lb_ver = (d.get("meta") or {}).get("game_version")
        if deployed and lb_ver and deployed != lb_ver:
            add("league:version_drift", WARN,
                f"leaderboard game_version={lb_ver} but deployed game={deployed} -- export stamping stale version")
        elif deployed and lb_ver:
            add("league:version_drift", OK, f"game_version {lb_ver} matches deployed")
    except Exception:
        pass

    # referential integrity: stats vs entries
    entries = d.get("entries") or []
    stats = d.get("statistics") or {}
    uniq = len({(e.get("player_name") or "").strip() for e in entries if e.get("player_name")})
    if "unique_players" in stats and stats["unique_players"] != uniq:
        add("league:integrity", FAIL,
            f"statistics.unique_players={stats['unique_players']} but entries contain {uniq} unique players")
    else:
        add("league:integrity", OK, f"{len(entries)} entries, {uniq} unique players consistent")


def check_seed_leaderboards():
    files = sorted(glob.glob(str(PUBLIC / "leaderboard" / "data" / "seed_leaderboard_*.json")))
    if not files:
        add("seed_leaderboards:present", WARN, "no seed leaderboard files found")
        return
    bad = 0
    for f in files:
        try:
            load_json(f)
        except Exception:
            bad += 1
    add("seed_leaderboards:parse", FAIL if bad else OK,
        f"{bad}/{len(files)} unparseable" if bad else f"{len(files)} files parse OK")


# ---- main ----------------------------------------------------------------------
def main():
    check_only = "--check" in sys.argv

    validate_schema("events", PUBLIC / "data" / "events.json", "events.schema.json")
    validate_schema("league_weekly", PUBLIC / "leaderboard" / "data" / "weekly" / "current.json", "leaderboard-weekly.schema.json")
    # validate one representative seed file against the seed schema
    seeds = sorted(glob.glob(str(PUBLIC / "leaderboard" / "data" / "seed_leaderboard_*.json")))
    if seeds:
        validate_schema("league_seed", seeds[-1], "leaderboard-seed.schema.json")

    check_encoding("events", PUBLIC / "data" / "events.json")
    check_encoding("league_weekly", PUBLIC / "leaderboard" / "data" / "weekly" / "current.json")

    check_weekly_league()
    check_seed_leaderboards()

    n_fail = sum(1 for c in checks if c["status"] == FAIL)
    n_warn = sum(1 for c in checks if c["status"] == WARN)
    overall = FAIL if n_fail else (WARN if n_warn else OK)

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "summary": {"fail": n_fail, "warn": n_warn, "ok": sum(1 for c in checks if c["status"] == OK)},
        "checks": checks,
    }

    # console
    icon = {OK: "OK  ", WARN: "WARN", FAIL: "FAIL"}
    print(f"Data contract & integrity validation -- overall: {overall}")
    print("-" * 72)
    for c in checks:
        print(f"[{icon[c['status']]}] {c['name']}: {c['detail']}")
    print("-" * 72)
    print(f"{n_fail} fail, {n_warn} warn, {report['summary']['ok']} ok")

    if not check_only:
        out = PUBLIC / "data" / "integration-health.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
