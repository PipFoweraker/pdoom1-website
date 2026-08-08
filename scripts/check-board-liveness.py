#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check-board-liveness.py -- READ-ONLY live probe of the PHP score API.

WHY THIS EXISTS
---------------
A leaderboard board is keyed by (seed, board_version). When a submitting client's key
does not match the board anyone reads, the score lands on a board nobody looks at and
the player is shown no error. From the outside that is indistinguishable from "nobody
is playing".

Nothing in this repo had ever read the score API, so "0 entries" on the site was never
evidence about the API one way or the other. This script closes that gap: it asks the
API directly and records what it found, with a timestamp.

THE BOARD VERSION IS THE LADDER EPOCH, NOT THE BUILD
----------------------------------------------------
Authoritative (pdoom1, via pdoom1-website issue #151, comment 2026-07-28T23:13):
`GameConfig.get_board_version()` returns "L" + LADDER_VERSION. The client sends `L3`,
not `v0.13.2`. The build version no longer touches the board key at all -- that is the
build-vs-ladder split, and it means a cosmetic patch bump will never again fork a board.

So comparing a board's version half against `version.json` is WRONG, and worse than
wrong: after the next ladder bump the two are SUPPOSED to differ, and a check built that
way would scream "mismatch" forever on correct data. A permanently-firing alarm is how a
team learns to ignore alarms.

Two key shapes coexist live and NEITHER is an error:
  * epoch-shaped  `L2`       -- current. What the game sends today.
  * build-shaped  `v0.11.0`  -- historical, from before the split. Frozen evidence.
Entries on an epoch board carry their build in `game_mode`, so one board spans builds.

WHAT WE STILL CANNOT DO
-----------------------
The website has NO artifact telling it which ladder epoch is current. That is a real gap
(see the artifact request in PR #190), not something to paper over. While the epoch is
unknown this script reports `epoch-unknown` and every surface says "cannot confirm".
It never asserts a mismatch it cannot demonstrate.

NOTHING IS HARDCODED
--------------------
Probe targets are DERIVED (Pip's standing rule: "keep using variables and not hardcoding
things where we can"). Seeds come from the preserved captures, weekly/current.json and
leaderboard.json. Epochs come from the epoch-shaped keys already seen, plus a forward
window relative to the highest one -- so a ladder bump is picked up without anyone
editing a literal. Anything that genuinely must be pinned goes in
public/leaderboard/data/board-probe-targets.json WITH A SOURCE, never in this file.

CONTRACT (do not break)
-----------------------
pdoom1 PR #679 makes this repo a READ-ONLY consumer of ONE score API. GETs only. Never
POSTs, never writes to the API, never re-stamps a version (that fabricates history). It
writes one local file, board-liveness.json, which is an OBSERVATION, not a score store.

NEVER COMPOSE A BOARD KEY FROM TWO FILES
----------------------------------------
The seed half comes from published-board.json (what the site actually served) and the
epoch half used to come from board-probe-targets.json (what the ladder is on NOW). Those
are two files of two different vintages, and pairing them asserts a key that may never
have existed. On 2026-08-08 it produced `(weekly-2026-w31, L4)` -- an old seed from one
file, a new epoch from the other -- and then correctly reported the 9 real scores on
`(weekly-2026-w32, L4)` as orphaned. See issue #293.

So the published epoch is read from published-board.json ALONGSIDE the seed, and the
comparison is against that pair. When the two files disagree about the epoch the honest
answer is a named state -- `superseded-publication` -- not a fabricated key. The ordinary
weekly seed roll has the same defect with no tell: the composite resolves to LAST week's
real board and nothing in the output looks invented (#229).

EXIT CODES
  0  consistent, OR every orphaned board is already acknowledged in the anomaly archive
  1  a NEW, unacknowledged orphaned board holds entries -- scores are being lost NOW
  2  the epoch is unknown, the published board is from a superseded epoch, or the API
     could not be read (all of these are "we cannot tell", never "empty")

RUN
    python scripts/check-board-liveness.py
    python scripts/check-board-liveness.py --seed some-seed --version L4
    python scripts/check-board-liveness.py --check      # no file write
"""

import argparse
import io
import json
import re
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
PUBLISHED_JSON = LB_DIR / "published-board.json"
SNAPSHOT_JSON = LB_DIR / "leaderboard.json"
PRESERVED_DIR = LB_DIR / "preserved"
TARGETS_JSON = LB_DIR / "board-probe-targets.json"
OUT_JSON = LB_DIR / "board-liveness.json"

SCORE_API = "https://api.pdoom1.com/score_api.php"

# Shape tests, not value lists. These classify a key; they never supply one.
EPOCH_RE = re.compile(r"^L(\d+)$")
BUILD_RE = re.compile(r"^v?\d+\.\d+\.\d+$")

# How far past the highest KNOWN epoch to probe. Relative, so it tracks the ladder
# instead of naming one. 2 covers a bump landing between two runs of this script.
EPOCH_LOOKAHEAD = 2

# Preserved captures are named "<seed>__<boardversion>.json" -- the filename IS the
# board key, which is what makes the archive a derivation source rather than a dump.
CAPTURE_RE = re.compile(r"^(?P<seed>.+)__(?P<version>[^_]+)\.json$")


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


def key_shape(version):
    """'epoch' | 'build' | 'unknown'. The first two are both legitimate."""
    if not version:
        return "unknown"
    if EPOCH_RE.match(str(version)):
        return "epoch"
    if BUILD_RE.match(str(version)):
        return "build"
    return "unknown"


# ---------------------------------------------------------------- derivation
def archived_keys():
    """Every (seed, version) the anomaly archive holds, from the capture FILENAMES.

    Doubles as the acknowledgement register: an orphaned board that appears here is
    known history (Pip's ruling -- these stay archived permanently), whereas one that
    does not is a live incident. That distinction is what lets the guard be loud about
    the archive every run without ever going red for it.
    """
    keys = []
    if not PRESERVED_DIR.is_dir():
        return keys
    for f in sorted(PRESERVED_DIR.rglob("*.json")):
        m = CAPTURE_RE.match(f.name)
        if m:
            keys.append((m.group("seed"), m.group("version")))
    return keys


def derive_targets(extra_seeds, extra_versions):
    """Build the probe set from what the repo already knows.

    Deliberately not a literal list anywhere: every seed and every epoch here comes from
    a data file, a capture filename, or arithmetic on one of those.
    """
    notes = []
    targets = load_json(TARGETS_JSON, {}) or {}
    seeds, versions = [], []

    def add(bucket, value):
        if value and value not in bucket:
            bucket.append(value)

    # 1. What the site currently publishes -- the board it believes in.
    add(seeds, (load_json(WEEKLY_JSON, {}) or {}).get("seed"))
    add(seeds, (load_json(PUBLISHED_JSON, {}) or {}).get("seed"))
    snap_seed = (load_json(SNAPSHOT_JSON, {}) or {}).get("seed")
    if snap_seed not in ("-", "—", "aggregate", "no-data"):
        add(seeds, snap_seed)

    # 2. Every board the archive has seen. This is how the CLIENT's own seed format --
    #    which the website does not generate and could not otherwise guess -- stays in
    #    the probe set without being typed into a script.
    arch = archived_keys()
    for s, v in arch:
        add(seeds, s)
        add(versions, v)
    if arch:
        notes.append("%d board key(s) derived from the anomaly archive" % len(arch))
    else:
        notes.append("anomaly archive absent -- probe set is narrower than it should be, "
                     "and orphans cannot be classified as known vs new")

    # 3. Whatever the last run saw, so the set grows as the ladder moves.
    for b in ((load_json(OUT_JSON, {}) or {}).get("boards") or []):
        add(seeds, b.get("seed"))
        add(versions, b.get("version"))

    # 4. Pinned values -- only from the data file, and only with a source. A pinned value
    #    with no source is a hardcoded literal wearing a costume, so it is refused.
    for key, bucket in (("extra_seeds", seeds), ("extra_versions", versions)):
        for item in (targets.get(key) or []):
            if isinstance(item, dict):
                if not item.get("source"):
                    notes.append("ignored pinned %s %r: no source recorded"
                                 % (key, item.get("value")))
                    continue
                add(bucket, item.get("value"))
            else:
                notes.append("ignored bare %s %r: pinned values must carry a source"
                             % (key, item))

    # 5. CLI overrides, for a human who has just been told a new value.
    for s in extra_seeds:
        add(seeds, s)
    for v in extra_versions:
        add(versions, v)

    # 6. Epoch forward window, derived from the highest epoch actually seen. A ladder
    #    bump is therefore caught with no edit here. If none has been seen we start at
    #    L1: the sequence is defined by its own shape, not by a remembered value.
    epochs = [int(m.group(1)) for m in (EPOCH_RE.match(str(v)) for v in versions) if m]
    highest = max(epochs) if epochs else 0
    for n in range(1, highest + EPOCH_LOOKAHEAD + 1):
        add(versions, "L%d" % n)
    notes.append("epoch window L1..L%d (highest seen L%d, +%d lookahead)"
                 % (highest + EPOCH_LOOKAHEAD, highest, EPOCH_LOOKAHEAD))

    return seeds, versions, notes


def current_epoch(targets):
    """The ladder epoch the game is on RIGHT NOW, or (None, None).

    There is no artifact for this yet. None means 'cannot confirm' and must never be
    quietly replaced by a guess -- answering confidently without knowing is the exact
    failure mode this script exists to end.
    """
    ce = (targets or {}).get("current_ladder_epoch") or {}
    val, src = ce.get("value"), ce.get("source")
    if val and key_shape(val) == "epoch" and src:
        return val, src
    return None, None


# ---------------------------------------------------------------- probing
def probe_board(seed, version):
    q = urllib.parse.urlencode({"seed": seed, "version": version})
    data, err = get_json("%s?%s" % (SCORE_API, q))
    base = {"seed": seed, "version": version, "key_shape": key_shape(version)}
    if err:
        base.update({"error": err, "entries": None})
        return base
    if not isinstance(data, dict) or not data.get("ok"):
        base.update({"error": "unexpected payload: %s" % json.dumps(data)[:120],
                     "entries": None})
        return base
    entries = data.get("entries") or []
    players = sorted({e.get("player_name") for e in entries if e.get("player_name")})
    dates = sorted(e.get("date") for e in entries if e.get("date"))
    # An epoch board spans builds, so record which builds appear. That is the evidence
    # the split is working, and it is the only place a build version belongs.
    base.update({
        "entries": len(entries),
        "players": len(players),
        "player_names": players,
        "builds_seen": sorted({e.get("game_mode") for e in entries if e.get("game_mode")}),
        "first_entry": dates[0] if dates else None,
        "last_entry": dates[-1] if dates else None,
    })
    return base


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="append", default=[], help="extra seed (repeatable)")
    ap.add_argument("--version", action="append", default=[],
                    help="extra board version / ladder epoch (repeatable)")
    ap.add_argument("--check", action="store_true", help="exit code only, no file write")
    args = ap.parse_args()

    targets = load_json(TARGETS_JSON, {}) or {}
    epoch, epoch_source = current_epoch(targets)
    # What the SITE publishes. Prefer published-board.json, the artifact
    # publish-live-board.py writes to record the board key it actually served. Fall back
    # to weekly/current.json, which weekly-league-manager.py owns and which historically
    # carried a website-DERIVED placeholder seed no client ever posted to -- comparing
    # against that is what made every real board look like an orphan.
    published = load_json(PUBLISHED_JSON, {}) or {}
    site_seed = published.get("seed") or (load_json(WEEKLY_JSON, {}) or {}).get("seed")
    site_seed_source = "published-board.json" if published.get("seed") else "weekly/current.json"
    # The epoch half of the SAME key, from the SAME file. Reading the seed here and the
    # epoch from board-probe-targets.json is what composed a key that never existed
    # (#293). When published-board.json predates the field, `site_epoch` falls back to
    # the current epoch and the record says so -- `epoch_composed: true` -- rather than
    # presenting the fallback pair as an observation.
    published_epoch = published.get("ladder_epoch")
    site_epoch = published_epoch or epoch
    epoch_composed = published_epoch is None
    site_epoch_source = ("published-board.json" if published_epoch
                         else "COMPOSED: seed from %s, epoch from board-probe-targets.json "
                              "(published-board.json records no ladder_epoch)" % site_seed_source)
    # None, not False: the two files can only be compared when both name an epoch.
    # Absence is unknown, never agreement.
    epochs_agree = None if (published_epoch is None or epoch is None) else published_epoch == epoch
    superseded = epochs_agree is False
    # Read only to REPORT. The build plays no part in any board comparison -- see the
    # module docstring on the build-vs-ladder split.
    build = ((load_json(VERSION_JSON, {}) or {}).get("latest_release") or {}).get("version")

    seeds, versions, notes = derive_targets(args.seed, args.version)
    archive = set(archived_keys())

    print("Board liveness probe -- %s" % now_iso())
    print("=" * 74)
    print("  site seed (published)   %s   [from %s]" % (site_seed or "UNKNOWN", site_seed_source))
    print("  published ladder epoch  %s   [from %s]"
          % (published_epoch or "not recorded", site_epoch_source))
    print("  current ladder epoch    %s" % (epoch or "UNKNOWN -- no artifact publishes it"))
    print("  deployed build          %s   (NOT part of the board key)" % (build or "unknown"))
    print("  anomaly archive         %d acknowledged board key(s)" % len(archive))
    for n in notes:
        print("  note: %s" % n)
    print()

    results, errors = [], 0
    for s in seeds:
        for v in versions:
            r = probe_board(s, v)
            if r.get("error"):
                errors += 1
            results.append(r)

    populated = [r for r in results if (r.get("entries") or 0) > 0]

    def is_deployed(r):
        # Against the pair the SITE PUBLISHED -- (site_seed, site_epoch) -- not against a
        # seed from one file paired with an epoch from another (#293).
        return bool(site_epoch) and r["seed"] == site_seed and r["version"] == site_epoch

    deployed_board = next((r for r in results if is_deployed(r)), None)
    orphaned = [r for r in populated if not is_deployed(r)]
    known = [r for r in orphaned if (r["seed"], r["version"]) in archive]
    unknown = [r for r in orphaned if (r["seed"], r["version"]) not in archive]

    # When publication is a whole epoch behind, EVERY board on the new epoch fails the
    # is_deployed test -- including the board players are correctly scoring on. Calling
    # those orphans is a false alarm about a real cause: the publisher has not run yet.
    # They are set aside under `pending_publication` so the alarm keeps meaning what it
    # says, and so the workflow's "N new orphaned entries" line does not report a number
    # that is about to be zero.
    pending_publication = []
    if superseded:
        pending_publication, unknown = unknown, []

    print("  probed %d board(s): %d seed(s) x %d version(s); %d unreadable"
          % (len(results), len(seeds), len(versions), errors))
    print("-" * 74)
    for r in sorted(populated, key=lambda x: -(x["entries"] or 0)):
        tag = "DEPLOYED" if is_deployed(r) else \
              ("archived" if (r["seed"], r["version"]) in archive else "NEW ORPHAN")
        print("  [%4d] %-26s %-6s %-6s %-10s %s"
              % (r["entries"], r["seed"][:26], r["version"], r["key_shape"], tag,
                 ("builds " + ",".join(r["builds_seen"])) if r.get("builds_seen") else ""))
    if not populated:
        print("  (no probed board holds any entry)")
    print("-" * 74)

    total_known = sum(r["entries"] for r in known)
    total_unknown = sum(r["entries"] for r in unknown)
    archive_absent = not archive

    # ---- verdict ------------------------------------------------------------
    # SUPERSEDED FIRST, deliberately. When the published board is a whole epoch behind,
    # every board on the current epoch looks orphaned, so the orphan branch would fire a
    # loud, exit-1 alarm about a condition whose real cause is "the publisher has not run
    # yet". Exit 2, like epoch-unknown: this is an admission, not an incident.
    if superseded:
        verdict, exit_code = "superseded-publication", 2
        print()
        print("  SUPERSEDED PUBLICATION. The board this site published is from an epoch")
        print("  that is no longer current, so no comparison here can say whether players")
        print("  are being lost.")
        print("    published board : (%s, %s)   [published-board.json]"
              % (site_seed, published_epoch))
        print("    current epoch   : %s   [board-probe-targets.json -> current_ladder_epoch]"
              % epoch)
        print("    epoch source    : %s" % (epoch_source or "unrecorded"))
        print()
        print("  These two halves come from two different files of two different vintages.")
        print("  Pairing them would assert a board key that has never existed, so this run")
        print("  does not: it names the disagreement instead (issue #293).")
        if pending_publication:
            print()
            print("  %d populated board(s) on the current epoch are NOT being reported as"
                  % len(pending_publication))
            print("  orphans, because publication catching up is what resolves them:")
            for r in pending_publication:
                print("       - (%s, %s): %d entries, %d player(s)"
                      % (r["seed"], r["version"], r["entries"], r["players"]))
        print()
        print("  FIX: run scripts/publish-live-board.py, which observes the live board and")
        print("  rewrites published-board.json. Do NOT re-stamp published-board.json by")
        print("  hand and do NOT edit the epoch to match -- either one fabricates a")
        print("  publication that did not happen.")
    elif unknown and not archive_absent:
        verdict, exit_code = "orphaned-scores", 1
        print()
        print("  !! NEW ORPHANED BOARD(S): %d entr%s on %d board(s) NOT in the anomaly"
              % (total_unknown, "y" if total_unknown == 1 else "ies", len(unknown)))
        print("     archive. These are being lost RIGHT NOW.")
        for r in unknown:
            print("       - (%s, %s) [%s]: %d entries, %d player(s), %s .. %s"
                  % (r["seed"], r["version"], r["key_shape"], r["entries"], r["players"],
                     (r["first_entry"] or "?")[:10], (r["last_entry"] or "?")[:10]))
        print()
        print("     The board key is (seed, ladder_epoch). These entries did not fail to")
        print("     save -- they saved to a key nothing reads. Do NOT re-stamp anything:")
        print("     that fabricates history.")
    elif unknown and archive_absent:
        # Losing the archive must not manufacture an emergency. Same principle as
        # everywhere else here: absence is unknown, never a confident claim.
        verdict, exit_code = "unclassifiable", 2
        print()
        print("  CANNOT CLASSIFY. %d populated orphan board(s) found, but the anomaly"
              % len(unknown))
        print("  archive is missing, so there is no way to tell known history from a new")
        print("  incident. Restore public/leaderboard/data/preserved/ and re-run.")
    elif not epoch:
        # The honest state today: we can see the boards, we cannot say which is current.
        verdict, exit_code = "epoch-unknown", 2
        print()
        print("  CANNOT CONFIRM. No artifact tells this site which ladder epoch is")
        print("  current, so it cannot say whether the board it publishes is the board")
        print("  players submit to. This is NOT a mismatch claim -- it is an admission.")
        print("  To resolve: pdoom1 publishes the current ladder epoch, and it lands in")
        print("  board-probe-targets.json -> current_ladder_epoch (with a source).")
    elif deployed_board and deployed_board.get("entries"):
        verdict, exit_code = "live", 0
        print()
        print("  OK: deployed board (%s, %s) holds %d entries."
              % (site_seed, site_epoch, deployed_board["entries"]))
    elif errors == len(results):
        verdict, exit_code = "unreachable", 2
        print()
        print("  UNKNOWN: every probe failed. NOT evidence that the board is empty --")
        print("  evidence that we cannot tell.")
    else:
        verdict, exit_code = "genuinely-empty", 0
        print()
        print("  Deployed board (%s, %s) holds 0 entries, and every other populated board"
              % (site_seed, site_epoch))
        print("  is already acknowledged. Nobody has submitted to the current board yet.")

    if known:
        # Loud every run, green every run. Pip's ruling: these stay archived permanently,
        # so failing on them would leave the guard red forever and train everyone to
        # ignore red -- the exact failure mode this repo keeps getting bitten by.
        names = sorted({n for r in known for n in (r.get("player_names") or [])})
        print()
        print("  ARCHIVED ANOMALY (acknowledged history, not a regression):")
        print("    %d entr%s across %d board(s), %d distinct player name(s)."
              % (total_known, "y" if total_known == 1 else "ies", len(known), len(names)))
        print("    players: %s" % ", ".join(names))
        print("    see %s" % PRESERVED_DIR.relative_to(PUBLIC))

    record = {
        "_comment": "Read-only observation of the live score API. Not a score store. "
                    "Written by scripts/check-board-liveness.py. The board key is "
                    "(seed, ladder_epoch); the build version is NOT part of it.",
        "checked_at": now_iso(),
        "api": SCORE_API,
        "verdict": verdict,
        # THE BOARD KEY THE SITE PUBLISHED -- both halves from published-board.json, never
        # one half from each of two files (#293). The current epoch is carried alongside as
        # a separate, separately-sourced fact, and `epochs_agree` says whether they match.
        "board_key": {
            "seed": site_seed,
            "seed_source": site_seed_source,
            "ladder_epoch": site_epoch,
            "ladder_epoch_source": site_epoch_source,
            "published_ladder_epoch": published_epoch,
            "current_ladder_epoch": epoch,
            "current_ladder_epoch_source": epoch_source,
            # true / false / null. null means one of the two is absent, which is UNKNOWN
            # agreement -- never treat it as agreement.
            "epochs_agree": epochs_agree,
            # true means `ladder_epoch` above is NOT the epoch published-board.json
            # recorded (it records none), so the pair is a fallback and not an observation.
            "epoch_composed": epoch_composed,
            "epoch_known": bool(epoch),
            "note": "epoch_known=false means this site cannot confirm which board is "
                    "current. It is NOT a mismatch finding. epochs_agree=false means the "
                    "published board is from a superseded epoch: the fix is to run "
                    "scripts/publish-live-board.py, not to re-stamp anything. "
                    "epoch_composed=true means ladder_epoch is a fallback to the current "
                    "epoch because published-board.json predates the field -- the pair is "
                    "composed, not observed.",
        },
        "deployed_build": build,
        "deployed_board": deployed_board,
        "probe": {"seeds": seeds, "versions": versions, "boards_probed": len(results),
                  "unreachable": errors, "notes": notes},
        "archived_orphans": {
            "acknowledged": True,
            "boards": known,
            "entries_total": total_known,
            "player_names": sorted({n for r in known for n in (r.get("player_names") or [])}),
            "note": "Pre-epoch anomaly archive. Permanent by Pip's ruling -- reported "
                    "every run, never a CI failure.",
        },
        "new_orphans": {
            "boards": unknown,
            "entries_total": total_unknown,
            "note": ("Orphan classification is SUSPENDED this run: the published board is "
                     "from a superseded epoch, so every board on the current epoch would "
                     "score as an orphan. See pending_publication." if superseded else
                     "Populated boards this site does not publish and the anomaly archive "
                     "does not acknowledge."),
        },
        # Populated boards on the CURRENT epoch that publication has not caught up with.
        # Named rather than counted as orphans, because running the publisher resolves
        # them and an alarm that self-heals teaches people to ignore alarms.
        "pending_publication": {
            "boards": pending_publication,
            "entries_total": sum(r["entries"] for r in pending_publication),
            "note": "Not orphans. The publisher has not yet republished onto the current "
                    "epoch; scripts/publish-live-board.py is the fix.",
        },
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
