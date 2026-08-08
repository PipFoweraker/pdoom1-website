#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Forced-state tests for scripts/check-board-liveness.py's verdict boundaries.

WHY THIS EXISTS
---------------
On 2026-08-08 the probe composed a board key that has never existed -- the seed half from
published-board.json, the epoch half from board-probe-targets.json, two files of two
different vintages -- and then reported nine real, correctly-saved player scores as
`orphaned-scores`, exit 1, job red. Re-running the identical workflow minutes later, with
no code change and no data change, said `live`. Issue #293.

The dramatic version needs an epoch fork to make the fabricated key obvious. The ordinary
weekly seed roll has the SAME defect with no tell: the composite resolves to last week's
real board, the probe reports the previous week as deployed and the current week's scores
as orphaned, and nothing in the output looks invented (#229).

CLAUDE.md's testing discipline: a claimed safety property needs a FORCED failure, because
a guard seen only in its passing state has not been shown to work. So each case below
constructs the state rather than waiting for it, and case 4 exists specifically to prove
the orphan alarm was NOT disarmed by the change that stops it firing falsely.

HOW IT ISOLATES
---------------
The module is imported and every path constant is redirected into a temp dir, so no test
can read or write real repo data. The network is never used: liveness.probe_board and
liveness.get_json are replaced with stubs and liveness.derive_targets returns a fixed set.
Nothing here issues a single HTTP request -- safe offline, safe in CI, and it cannot POST
to the score API even by accident (this repo is a READ-ONLY consumer, pdoom1 PR #679).

Run:  python scripts/test-board-liveness-verdicts.py     (exit 0 = pass)
"""

import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

# CLAUDE.md: the Windows console is cp1252 and dies on the FIRST non-ASCII print.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_board_liveness", ROOT / "scripts" / "check-board-liveness.py")
liveness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(liveness)

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


ROW = {"score": 10, "player_name": "A", "date": "2026-08-08T09:00:00", "game_mode": "v0.14.0"}

# One acknowledged capture, so `archive_absent` is false and the `unclassifiable` branch
# stays out of the way. The filename IS the board key -- that is how the real archive
# works, so the fixture has to work the same way or it is testing a different code path.
ARCHIVED_KEY = ("legacy-seed", "v0.11.0")


class Sandbox:
    """Redirect the module's paths into a temp dir and stub the network.

    `published` is written verbatim, so a test can omit `ladder_epoch` entirely and
    exercise the legacy-file path rather than a synthesised approximation of it.
    """

    def __init__(self, published, current_epoch, boards, seeds=None, versions=None,
                 all_unreachable=False):
        self.published = published
        self.current_epoch = current_epoch
        self.boards = boards
        self.seeds = seeds
        self.versions = versions
        # Forces every probe to fail, the way a real API outage does. Needed because a
        # verdict derived only from local files must not outrank "we observed nothing".
        self.all_unreachable = all_unreachable

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = {k: getattr(liveness, k) for k in (
            "ROOT", "PUBLIC", "LB_DIR", "VERSION_JSON", "WEEKLY_JSON", "PUBLISHED_JSON",
            "SNAPSHOT_JSON", "PRESERVED_DIR", "TARGETS_JSON", "OUT_JSON")}
        self._saved_fns = {k: getattr(liveness, k) for k in
                           ("probe_board", "get_json", "derive_targets")}

        public = self.tmp / "public"
        lb = public / "leaderboard" / "data"
        lb.mkdir(parents=True)
        liveness.ROOT = self.tmp
        liveness.PUBLIC = public
        liveness.LB_DIR = lb
        liveness.VERSION_JSON = public / "data" / "version.json"
        liveness.WEEKLY_JSON = lb / "weekly" / "current.json"
        liveness.PUBLISHED_JSON = lb / "published-board.json"
        liveness.SNAPSHOT_JSON = lb / "leaderboard.json"
        liveness.PRESERVED_DIR = lb / "preserved"
        liveness.TARGETS_JSON = lb / "board-probe-targets.json"
        liveness.OUT_JSON = lb / "board-liveness.json"

        liveness.PUBLISHED_JSON.write_text(json.dumps(self.published), encoding="utf-8")
        liveness.TARGETS_JSON.write_text(json.dumps({
            "current_ladder_epoch": {"value": self.current_epoch, "source": "test fixture"}
            if self.current_epoch else {"value": None, "source": None},
        }), encoding="utf-8")
        liveness.PRESERVED_DIR.mkdir(parents=True)
        (liveness.PRESERVED_DIR / ("%s__%s.json" % ARCHIVED_KEY)).write_text(
            json.dumps({"entries": []}), encoding="utf-8")

        boards = self.boards
        seeds = self.seeds if self.seeds is not None else sorted({s for s, _ in boards})
        versions = (self.versions if self.versions is not None
                    else sorted({v for _, v in boards}))

        unreachable = self.all_unreachable

        def probe(seed, version):
            if unreachable:
                return {"seed": seed, "version": version,
                        "key_shape": liveness.key_shape(version),
                        "error": "stubbed outage", "entries": 0}
            rows = boards.get((seed, version)) or []
            return {"seed": seed, "version": version, "key_shape": liveness.key_shape(version),
                    "entries": len(rows), "players": len({r["player_name"] for r in rows}),
                    "player_names": sorted({r["player_name"] for r in rows}),
                    "builds_seen": sorted({r["game_mode"] for r in rows}),
                    "first_entry": rows[0]["date"] if rows else None,
                    "last_entry": rows[-1]["date"] if rows else None}

        def get_json(url, headers=None, timeout=20):
            raise AssertionError("a test issued a network request: %s" % url)

        liveness.probe_board = probe
        liveness.get_json = get_json
        liveness.derive_targets = lambda a, b: (list(seeds), list(versions), ["stubbed"])
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            setattr(liveness, k, v)
        for k, v in self._saved_fns.items():
            setattr(liveness, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


def run(argv=()):
    sys.argv = ["check-board-liveness.py", *argv]
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = liveness.main()
    return code, buf.getvalue()


def record():
    return json.loads(liveness.OUT_JSON.read_text(encoding="utf-8"))


def key_claims(obj):
    """Every dict anywhere in the record that ASSERTS a board key, as (seed, version).

    Walks the WHOLE structure rather than a named field list, on the same reasoning as
    redact_pii() elsewhere in this repo: a field added later must not be able to
    reintroduce the fabrication simply by living somewhere nobody thought to look.

    Two things are deliberately NOT key claims and would be false positives:
      * the raw `boards` probe log -- the probe asks the API about the cross product of
        every candidate seed and version, so (old seed, new epoch) appearing there is a
        QUESTION that was asked and answered "0 entries", not an assertion. Removing it
        would make the probe unable to notice a board it had not already seen.
      * `board_key` itself, which names the published epoch AND the current epoch on
        purpose. That object is checked field-by-field instead, which is stricter.
    """
    found = []
    if isinstance(obj, dict):
        if isinstance(obj.get("seed"), str) and isinstance(obj.get("version"), str):
            found.append((obj["seed"], obj["version"]))
        for v in obj.values():
            found += key_claims(v)
    elif isinstance(obj, list):
        for v in obj:
            found += key_claims(v)
    return found


# ---------------------------------------------------------------------------- case 1 + 2
print("\n1. Published epoch differs from the current epoch -> superseded-publication")
# Exactly the 2026-08-08 production state: published-board.json still says
# (weekly-2026-w31, L3); board-probe-targets.json has already moved to L4; nine real
# scores sit on (weekly-2026-w32, L4).
SUPERSEDED_BOARDS = {
    ("weekly-2026-w31", "L3"): [ROW] * 4,
    ("weekly-2026-w32", "L4"): [ROW] * 9,
}
with Sandbox(published={"seed": "weekly-2026-w31", "ladder_epoch": "L3"},
             current_epoch="L4", boards=SUPERSEDED_BOARDS,
             seeds=["weekly-2026-w31", "weekly-2026-w32"], versions=["L3", "L4"]):
    code, out = run()
    d = record()
    k = d["board_key"]
    check(code == 2, f"exit 2 -- an admission, not an incident (got {code})")
    check(d["verdict"] == "superseded-publication",
          f"verdict is superseded-publication (got {d['verdict']!r})")
    check(k["published_ladder_epoch"] == "L3", "carries the PUBLISHED epoch")
    check(k["current_ladder_epoch"] == "L4", "carries the CURRENT epoch, separately sourced")
    check(k["epochs_agree"] is False, "says explicitly that the two do not agree")
    check(k["epoch_composed"] is False, "the pair it reports was observed, not composed")
    check(k["seed"] == "weekly-2026-w31" and k["ladder_epoch"] == "L3",
          "board_key is the pair the SITE PUBLISHED -- both halves from one file")

    # THE DEFECT ITSELF, checked two ways.
    # (a) board_key must not offer the current epoch as the published seed's partner.
    check(k["ladder_epoch"] != k["current_ladder_epoch"],
          "board_key.ladder_epoch is NOT the current epoch -- that pairing is the fabrication")
    # (b) nothing else in the record may assert (old seed, new epoch) as a board key.
    #     The raw probe log is excluded; see key_claims' docstring for why.
    claims = key_claims({kk: vv for kk, vv in d.items() if kk != "boards"})
    check(("weekly-2026-w31", "L4") not in claims,
          f"NO COMPOSED KEY is asserted anywhere in the record (claims: {sorted(set(claims))})")
    # ...and the exclusion above is not a hole in the test: if the walk covered nothing,
    # (b) would pass vacuously. It has to be looking at real key claims.
    check(claims, "the walk actually inspected some board-key claims (not vacuously green)")

    check("superseded" in out.lower(), "the printed message names the state plainly")
    check("weekly-2026-w31" in out and "L3" in out and "L4" in out,
          "names both epochs so a human can see the disagreement")
    check("publish-live-board.py" in out,
          "says the fix is to run the publisher, not to re-stamp anything")
    check("re-stamp" in out, "says explicitly not to re-stamp")

    print("\n2. ...and the board that state creates is NOT called a new orphan")
    # The false alarm being removed. With publication a whole epoch behind, every board on
    # the current epoch fails the is_deployed test -- including the one players are
    # correctly scoring on.
    orphan_seeds = [b["seed"] for b in d["new_orphans"]["boards"]]
    check("weekly-2026-w32" not in orphan_seeds,
          f"the live w32 board is not reported as an orphan (orphans: {orphan_seeds})")
    check(d["new_orphans"]["entries_total"] == 0,
          f"new orphan count is 0, not 9 (got {d['new_orphans']['entries_total']})")
    pending = [(b["seed"], b["version"]) for b in d["pending_publication"]["boards"]]
    check(("weekly-2026-w32", "L4") in pending,
          f"it is named under pending_publication instead (got {pending})")
    check(d["pending_publication"]["entries_total"] == 9,
          "the nine entries are still counted -- suppressed from the alarm, not hidden")

# ---------------------------------------------------------------------------- case 3
print("\n3. Epochs agree and the deployed board holds entries -> live, exit 0 (unchanged)")
with Sandbox(published={"seed": "weekly-2026-w32", "ladder_epoch": "L4"},
             current_epoch="L4",
             boards={("weekly-2026-w32", "L4"): [ROW] * 9},
             seeds=["weekly-2026-w32"], versions=["L4"]):
    code, out = run()
    d = record()
    check(code == 0, f"exit 0 (got {code})")
    check(d["verdict"] == "live", f"verdict is live (got {d['verdict']!r})")
    check(d["board_key"]["epochs_agree"] is True, "records that the two files agree")
    check(d["deployed_board"]["entries"] == 9, "deployed board holds the 9 entries")
    check(d["new_orphans"]["entries_total"] == 0, "nothing orphaned")

# ---------------------------------------------------------------------------- case 4
print("\n4. A genuine orphan on a MATCHING epoch still fires -- the alarm is not disarmed")
# Same epoch on both files, so nothing is superseded. A populated board on a seed the
# site does not publish and the archive does not acknowledge is a live incident.
with Sandbox(published={"seed": "weekly-2026-w32", "ladder_epoch": "L4"},
             current_epoch="L4",
             boards={("weekly-2026-w32", "L4"): [ROW] * 2,
                     ("rogue-seed", "L4"): [ROW] * 7},
             seeds=["weekly-2026-w32", "rogue-seed"], versions=["L4"]):
    code, out = run()
    d = record()
    check(code == 1, f"exit 1 -- scores are being lost NOW (got {code})")
    check(d["verdict"] == "orphaned-scores", f"verdict is orphaned-scores (got {d['verdict']!r})")
    check([b["seed"] for b in d["new_orphans"]["boards"]] == ["rogue-seed"],
          "names the rogue board")
    check(d["new_orphans"]["entries_total"] == 7, "counts all 7 lost entries")
    check(d["pending_publication"]["entries_total"] == 0,
          "nothing is parked as pending when the epochs agree -- the escape hatch is "
          "reachable ONLY from the superseded state")

# ---------------------------------------------------------------------------- case 5
print("\n5. Legacy published-board.json with no ladder_epoch -> falls back, marks it COMPOSED")
with Sandbox(published={"seed": "weekly-2026-w32"},  # no ladder_epoch key at all
             current_epoch="L4",
             boards={("weekly-2026-w32", "L4"): [ROW] * 3},
             seeds=["weekly-2026-w32"], versions=["L4"]):
    code, out = run()
    d = record()
    k = d["board_key"]
    check(k["published_ladder_epoch"] is None, "records that the file names no epoch")
    check(k["ladder_epoch"] == "L4", "falls back to the current epoch so the probe can run")
    check(k["epoch_composed"] is True, "and marks the pair COMPOSED rather than observed")
    check(k["epochs_agree"] is None,
          f"agreement is null, never True -- absence is not agreement (got {k['epochs_agree']!r})")
    check("COMPOSED" in (k["ladder_epoch_source"] or ""),
          "the source string says the pair was composed and from which two files")
    check(d["verdict"] != "superseded-publication",
          "a missing field is not a disagreement, so it must not fire superseded")

print("\n6. Every probe fails AND the epochs disagree -> unreachable wins over superseded")
# Both statements are true, and the verdict must be the one derived from OBSERVATION.
# `superseded-publication` tells the reader to run the publisher; the publisher needs the
# same API that is down, so emitting it here hands out advice that cannot work. A verdict
# built only from local files must never outrank "we saw nothing" -- that is #293's own
# defect wearing different clothes.
with Sandbox(published={"seed": "weekly-2026-w31", "ladder_epoch": "L3"},
             current_epoch="L4",
             boards={("weekly-2026-w32", "L4"): [ROW] * 9},
             all_unreachable=True):
    code, out = run()
    d = record()
    check(d["verdict"] == "unreachable",
          f"verdict is unreachable, not superseded-publication (got {d['verdict']!r})")
    check(code == 2, f"exit 2 -- an admission, not an incident (got {code})")
    check("every probe failed" in out, "says plainly that nothing was observed")
    check("disagree" in out, "still MENTIONS the epoch disagreement rather than hiding it")
    check((d.get("new_orphans") or {}).get("entries_total", 0) == 0,
          "no orphan claim is made from a run that observed nothing")

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: the probe names an epoch disagreement instead of composing a board key, and "
      "the orphan alarm still fires on a real orphan.")
