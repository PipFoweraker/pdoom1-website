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

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return
    # Decode strictly first. A file that is not valid UTF-8 is a different (worse) fault
    # than mojibake, and decoding with errors="replace" would hide it behind U+FFFD.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        add(f"encoding:{name}", FAIL, f"not valid UTF-8: {e}")
        return
    hits = {m: text.count(m) for m in MOJIBAKE if m in text}
    # U+FFFD is what a lossy decode leaves behind -- e.g. a producer that read cp1252
    # bytes as UTF-8 with errors="replace". Characters that reach a file this way are
    # gone, not recoverable, so this is a FAIL and the count is the damage estimate.
    n_repl = text.count("�")
    if hits or n_repl:
        detail = []
        if hits:
            detail.append(f"mojibake {hits} (double-encoded chars in source)")
        if n_repl:
            detail.append(f"{n_repl} U+FFFD replacement char(s) -- a lossy decode wrote this file")
        add(f"encoding:{name}", FAIL, "; ".join(detail))
    else:
        add(f"encoding:{name}", OK, "valid UTF-8, no mojibake, no U+FFFD")


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

    # Version drift vs deployed game version.
    # This block used to end in `except Exception: pass`, which meant an unreadable
    # version.json made the ENTIRE check disappear from the report -- not FAIL, not WARN,
    # absent. A check that can silently delete itself is worse than no check, because the
    # green report is read as evidence. Every path below now emits a row.
    deployed = deployed_version()
    lb_ver = (d.get("meta") or {}).get("game_version")
    if not deployed:
        add("league:version_drift", WARN,
            "cannot read latest_release.version from version.json, so weekly "
            f"game_version={lb_ver} is UNCOMPARED -- absence of a mismatch here is not "
            "evidence of a match")
    elif not lb_ver:
        add("league:version_drift", WARN,
            f"weekly/current.json has no meta.game_version, so it cannot be compared to "
            f"deployed {deployed}. An unstamped board matches nothing and receives nothing.")
    elif deployed != lb_ver:
        add("league:version_drift", WARN,
            f"weekly league game_version={lb_ver} but deployed game={deployed} -- a "
            f"{deployed} client's scores cannot land on a {lb_ver} board")
    else:
        add("league:version_drift", OK, f"game_version {lb_ver} matches deployed")

    # The seed is the OTHER half of the board key and was never validated at all.
    seed = d.get("seed")
    if not seed:
        add("league:seed", FAIL,
            "weekly/current.json has no seed -- half the board key (seed, game_version) "
            "is missing, so no submission can be matched to this board")
    else:
        add("league:seed", OK, f"weekly seed {seed}")

    # referential integrity: stats vs entries
    entries = d.get("entries") or []
    stats = d.get("statistics") or {}
    uniq = len({(e.get("player_name") or "").strip() for e in entries if e.get("player_name")})
    if "unique_players" in stats and stats["unique_players"] != uniq:
        add("league:integrity", FAIL,
            f"statistics.unique_players={stats['unique_players']} but entries contain {uniq} unique players")
    else:
        add("league:integrity", OK, f"{len(entries)} entries, {uniq} unique players consistent")


def deployed_version():
    """The deployed BUILD. Report-only -- it is not part of the board key."""
    try:
        ver = load_json(PUBLIC / "data" / "version.json")
        return (ver.get("latest_release") or {}).get("version")
    except Exception:
        return None


def load_json_or_none(path):
    try:
        return load_json(path)
    except Exception:
        return None


# Shape tests for the version half of a board key. Both shapes are legitimate: epoch is
# current ("L2"), build is frozen history from before the build-vs-ladder split.
EPOCH_RE = re.compile(r"^L\d+$")
BUILD_RE = re.compile(r"^v?\d+\.\d+\.\d+$")


def board_key_shape(v):
    if not v:
        return "missing"
    if EPOCH_RE.match(str(v)):
        return "epoch"
    if BUILD_RE.match(str(v)):
        return "build"
    return "unrecognised"


def check_published_board():
    """The board a visitor actually sees, vs the build they are actually running.

    A board is keyed by (seed, game_version) -- pdoom1 PR #679. Until now this file
    validated weekly/current.json's stamp but never leaderboard.json's, so the file the
    leaderboard page fetches could drift arbitrarily far behind the deployed game and
    nothing said a word. Every report here names BOTH versions and a count; "0 entries"
    on its own is not information.
    """
    path = PUBLIC / "leaderboard" / "data" / "leaderboard.json"
    try:
        d = load_json(path)
    except FileNotFoundError:
        add("board:present", FAIL, "leaderboard.json missing -- the leaderboard page fetches this")
        return
    except Exception as e:
        add("board:present", FAIL, f"leaderboard.json is not valid JSON: {e}")
        return

    # The board key's version half, however the writer recorded it. publish-live-board.py
    # records it as meta.board_key.ladder_epoch, which says what the value IS; older
    # snapshots from ingest_scores.py put it in meta.game_version, a field name that
    # predates the build-vs-ladder split and now misdescribes its own contents. Prefer the
    # explicit one and fall back, rather than teaching the new writer to use the wrong name.
    _meta = d.get("meta") or {}
    board_ver = ((_meta.get("board_key") or {}).get("ladder_epoch")
                 or _meta.get("game_version"))
    n_entries = len(d.get("entries") or [])
    status = d.get("data_status")

    # The board key's version half is the LADDER EPOCH ("L3"), not the build version
    # (pdoom1 via issue #151, 2026-07-28T23:13). Comparing it to version.json used to
    # look sensible and is actually wrong: after a ladder bump the two are SUPPOSED to
    # differ, so that check would have gone WARN forever on correct data. A guard that
    # always fires is a guard nobody reads.
    live = load_json_or_none(PUBLIC / "leaderboard" / "data" / "board-liveness.json")
    epoch = ((live or {}).get("board_key") or {}).get("ladder_epoch")
    shape = board_key_shape(board_ver)

    if not epoch:
        add("board:key", WARN,
            f"published board key version is {board_ver!r} ({shape}-shaped, "
            f"{n_entries} entries), but no artifact tells this site which ladder epoch is "
            f"current -- so it CANNOT confirm the board it publishes is the board players "
            f"submit to. Reported as unconfirmed, deliberately NOT as a mismatch. "
            f"Needs pdoom1 to publish the current epoch.")
    elif board_ver == epoch:
        add("board:key", OK, f"published board key matches the current ladder epoch {epoch}")
    else:
        add("board:key", WARN,
            f"published board is keyed {board_ver!r} ({shape}-shaped) but the current "
            f"ladder epoch is {epoch}; the board shows {n_entries} entries. Scores "
            f"submitted under {epoch} cannot appear on a {board_ver} board. Do not "
            f"re-stamp -- that fabricates history.")

    # What ingest_scores refused to publish, named. Older snapshots predate this block;
    # its absence is reported as unknown rather than as "nothing was excluded".
    ex = d.get("exclusions")
    if not isinstance(ex, dict):
        add("board:exclusions", WARN,
            f"leaderboard.json carries no exclusions block (written before "
            f"ingest_scores.py started reporting them) -- cannot tell how many results "
            f"were withheld; re-run scripts/ingest_scores.py")
    elif ex.get("version_mismatched_files"):
        add("board:exclusions", WARN,
            f"{ex['version_mismatched_files']} seed file(s) holding "
            f"{ex.get('version_mismatched_entries', '?')} entries excluded on version: "
            f"they are stamped {', '.join(ex.get('version_mismatched_versions') or ['?'])}, "
            f"deployed is {ex.get('deployed_version')}")
    else:
        add("board:exclusions", OK,
            f"nothing withheld on version ({ex.get('test_dev_files', 0)} test/dev files "
            f"excluded by design)")

    # Self-consistency: an empty board must not advertise itself as live.
    if status == "live" and n_entries == 0:
        add("board:status_integrity", FAIL,
            "data_status='live' but the board holds 0 entries -- the page would present "
            "an empty ranking as real competitive results")
    else:
        add("board:status_integrity", OK, f"data_status={status} consistent with {n_entries} entries")


def check_board_liveness():
    """Did anyone verify the live score API, and what did they see?

    This is the check that distinguishes 'nobody finished a run' from 'submissions are
    landing somewhere nobody reads'. Without a dated observation, an empty board is not
    evidence of anything -- so a MISSING observation is itself worth reporting.
    """
    path = PUBLIC / "leaderboard" / "data" / "board-liveness.json"
    try:
        d = load_json(path)
    except FileNotFoundError:
        add("board:liveness", WARN,
            "no board-liveness.json -- nothing has ever checked the live score API, so an "
            "empty leaderboard is not evidence that no scores exist. "
            "Run: python scripts/check-board-liveness.py")
        return
    except Exception as e:
        add("board:liveness", FAIL, f"board-liveness.json is not valid JSON: {e}")
        return

    checked = parse_dt(d.get("checked_at"))
    verdict = d.get("verdict")
    key = d.get("board_key") or {}
    arch = d.get("archived_orphans") or {}
    new = d.get("new_orphans") or {}
    n_arch = arch.get("entries_total") or 0
    n_new = new.get("entries_total") or 0

    if checked:
        age_h = (datetime.now(timezone.utc) - checked).total_seconds() / 3600
        if age_h > 48:
            add("board:liveness_freshness", WARN,
                f"last live API check was {age_h/24:.1f} days ago -- the verdict below may "
                f"be stale")
        else:
            add("board:liveness_freshness", OK, f"live API checked {age_h:.1f}h ago")
    else:
        add("board:liveness_freshness", WARN, "board-liveness.json has no parseable checked_at")

    # The archived anomaly is reported LOUDLY on every run and is never a FAIL. Pip has
    # ruled those entries stay in the anomaly archive permanently, so failing on them
    # would leave this check red forever -- and a guard that is always red teaches
    # everyone to ignore red, which is the failure mode this repo keeps repeating.
    # Only a NEW, unacknowledged orphan is an emergency.
    if n_arch:
        names = arch.get("player_names") or []
        add("board:archived_anomaly", WARN,
            f"{n_arch} score entries across {len(arch.get('boards') or [])} board(s) from "
            f"{len(names)} player(s) sit in the permanent anomaly archive "
            f"({', '.join(names)}). Acknowledged history, NOT a regression -- reported "
            f"every run so it stays visible, never failed on.")

    if verdict == "orphaned-scores":
        detail = "; ".join(f"({b.get('seed')}, {b.get('version')}): {b.get('entries')} entries"
                           for b in (new.get("boards") or []))
        add("board:liveness", FAIL,
            f"NEW orphaned board(s): {n_new} score entries on {len(new.get('boards') or [])} "
            f"board(s) that are NOT in the anomaly archive. Scores are being lost RIGHT NOW. "
            f"{detail}. The board key is (seed, ladder_epoch). Do not re-stamp.")
    elif verdict == "unclassifiable":
        add("board:liveness", FAIL,
            f"{n_new} entries on orphan board(s), but the anomaly archive is missing so "
            f"known history cannot be told from a new incident. Restore "
            f"public/leaderboard/data/preserved/ and re-run.")
    elif verdict == "epoch-unknown":
        add("board:liveness", WARN,
            "no artifact tells this site which ladder epoch is current, so it cannot "
            "confirm the board it publishes is the board players submit to. Reported as "
            "UNCONFIRMED, deliberately not as a mismatch -- asserting one here would fire "
            "permanently once the ladder and the build legitimately diverge.")
    elif verdict == "unreachable":
        add("board:liveness", WARN,
            "the score API could not be reached at the last check -- board state is UNKNOWN, "
            "not empty")
    elif verdict == "genuinely-empty":
        add("board:liveness", OK,
            f"live API checked: deployed board ({key.get('seed')}, {key.get('ladder_epoch')}) "
            f"holds 0 entries and every other populated board is acknowledged -- genuinely "
            f"empty, not misrouted")
    elif verdict == "live":
        dep = d.get("deployed_board") or {}
        add("board:liveness", OK,
            f"deployed board ({key.get('seed')}, {key.get('ladder_epoch')}) holds "
            f"{dep.get('entries')} entries")
    else:
        add("board:liveness", WARN, f"unrecognised verdict {verdict!r} in board-liveness.json")


def check_seed_leaderboards():
    files = sorted(glob.glob(str(PUBLIC / "leaderboard" / "data" / "seed_leaderboard_*.json")))
    if not files:
        add("seed_leaderboards:present", WARN, "no seed leaderboard files found")
        return
    bad = 0
    census, entries_by_ver = {}, {}
    for f in files:
        try:
            d = load_json(f)
        except Exception:
            bad += 1
            continue
        v = (d.get("meta") or {}).get("game_version") or "unstamped"
        census[v] = census.get(v, 0) + 1
        entries_by_ver[v] = entries_by_ver.get(v, 0) + len(d.get("entries") or [])
    add("seed_leaderboards:parse", FAIL if bad else OK,
        f"{bad}/{len(files)} unparseable" if bad else f"{len(files)} files parse OK")

    # Version census. "no seed files match the deployed version" is the sentence that
    # explains an empty board; a bare file count never could.
    deployed = deployed_version()
    breakdown = ", ".join(f"{v}: {n} file(s)/{entries_by_ver[v]} entries"
                          for v, n in sorted(census.items()))
    if deployed and deployed not in census:
        add("seed_leaderboards:version_census", WARN,
            f"NO stored seed file is stamped with the deployed version {deployed}, so "
            f"ingest_scores.py has nothing publishable and the board will be empty "
            f"whatever happens upstream. Present: {breakdown}")
    else:
        add("seed_leaderboards:version_census", OK, breakdown or "no versions recorded")


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
    # The published board and every seed file are player-visible text too; they were
    # never encoding-checked, which is why a question about corruption in leaderboard.json
    # could not be answered from CI.
    check_encoding("board", PUBLIC / "leaderboard" / "data" / "leaderboard.json")
    for _sf in sorted(glob.glob(str(PUBLIC / "leaderboard" / "data" / "seed_leaderboard_*.json"))):
        check_encoding("seed:" + Path(_sf).stem.replace("seed_leaderboard_", ""), _sf)

    check_weekly_league()
    check_published_board()
    check_board_liveness()
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
