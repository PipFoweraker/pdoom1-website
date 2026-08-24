#!/usr/bin/env python3
"""Assert that a SUSTAINED "cannot tell" escalates, and that a single one does not.

    python scripts/test-board-liveness-escalation.py     (exit 0 = pass)

WHY THIS EXISTS
---------------
On 2026-08-17 the DreamCompute instance serving api.pdoom1.com was stopped. The
board-liveness workflow ran every six hours for five days -- roughly twenty runs
-- and reported SUCCESS every time. The probe was not wrong: it correctly wrote
`verdict: "unreachable"` and exited 2, and board-liveness.json in the repo still
carries that verdict from the 18:31 run on 2026-08-21. The workflow's own comment
explains the decision:

    Only NEW loss is red. `epoch-unknown` and `unreachable` are genuine unknowns
    and stay green

That is right for ONE run, and this test does not change it -- an unknown a human
cannot clear must not go red, or people learn to ignore red. What was missing is
an upper bound. CLAUDE.md states the rule that was violated:

    Refusing to act is itself a silent-failure mode. A script that correctly
    declines every run is externally identical to one that is broken. Anything
    that can refuse needs a staleness escalation, not just a warning in a job
    summary.

So: the verdict and its exit code are unchanged and still pinned by
test-board-liveness-verdicts.py. What is new is `unknown_streak` / `escalate` in
the observation file, and the workflow gates on `escalate`. One unknown is an
admission. Four in a row -- about 24 hours at the 6-hourly cron -- is an incident.

WHAT WOULD MAKE THIS TEST WORTHLESS
-----------------------------------
Watching the streak only in its zero state. Every case below drives the counter
somewhere and asserts where it landed, and case 3 forces the escalation itself.
"""

import importlib.util
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

# Reuse the sandbox from the verdict tests rather than building a second one.
# Two harnesses drifting apart is how a test ends up exercising a world the
# production code no longer lives in.
_spec = importlib.util.spec_from_file_location(
    "liveness_verdicts", ROOT / "scripts" / "test-board-liveness-verdicts.py")
_h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h)

liveness = _h.liveness
Sandbox = _h.Sandbox

FAILURES = []
CHECKS = [0]


def check(cond, msg):
    CHECKS[0] += 1
    print("  %s  %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        FAILURES.append(msg)


PUBLISHED = {"seed": "weekly-2026-w33", "ladder_epoch": "L5"}
LIVE_BOARD = {("weekly-2026-w33", "L5"): [
    {"player_name": "tester", "game_mode": "v0.14.2", "date": "2026-08-22"}]}


def main():
    print("board liveness: a sustained 'cannot tell' has to escalate\n")

    # -- 1. a reachable run has no streak at all ----------------------------
    print("1. a run that reaches a real answer carries no streak")
    with Sandbox(PUBLISHED, "L5", LIVE_BOARD):
        code, out = _h.run()
        rec = _h.record()
        check(rec["verdict"] not in liveness.UNKNOWN_VERDICTS,
              "verdict is a real answer (%s)" % rec["verdict"])
        check(rec["unknown_streak"] == 0, "unknown_streak == 0")
        check(rec["escalate"] is False, "escalate is False")
        check(rec["unknown_since"] is None, "unknown_since is None")

    # -- 2. ONE outage is an admission, not an incident ---------------------
    print("\n2. one unreachable run reports the streak but does NOT escalate")
    with Sandbox(PUBLISHED, "L5", LIVE_BOARD, all_unreachable=True):
        code, out = _h.run()
        rec = _h.record()
        check(rec["verdict"] == "unreachable", "verdict is unreachable")
        check(code == 2, "exit 2 -- unchanged, still an admission (got %d)" % code)
        check(rec["unknown_streak"] == 1, "unknown_streak == 1")
        check(rec["escalate"] is False,
              "escalate is False -- a single unknown must not go red")
        check(rec["unknown_since"] is not None, "unknown_since is stamped")
        check("Not escalated yet" in out, "and it says so on stdout")

    # -- 3. FORCED FAILURE: the outage that actually happened ---------------
    print("\n3. FORCED: %d consecutive unreachable runs, the shape of 2026-08-17"
          % liveness.UNKNOWN_STREAK_ESCALATE)
    with Sandbox(PUBLISHED, "L5", LIVE_BOARD, all_unreachable=True) as _sb:
        streaks, escalated_at = [], None
        for run_number in range(1, liveness.UNKNOWN_STREAK_ESCALATE + 2):
            code, out = _h.run()
            rec = _h.record()
            streaks.append(rec["unknown_streak"])
            if rec["escalate"] and escalated_at is None:
                escalated_at = run_number
            first_since = first_since if run_number > 1 else rec["unknown_since"]
        check(streaks == list(range(1, len(streaks) + 1)),
              "the streak counts up one per run: %s" % streaks)
        check(escalated_at == liveness.UNKNOWN_STREAK_ESCALATE,
              "escalate flips exactly at run %d (flipped at %s)"
              % (liveness.UNKNOWN_STREAK_ESCALATE, escalated_at))
        check(rec["escalate"] is True, "and stays True once past the threshold")
        check(rec["unknown_since"] == first_since,
              "unknown_since pins the FIRST run of the streak, not the latest")
        check(code == 2, "the exit code is STILL 2 -- the workflow gates on the "
                         "field, the verdict keeps its meaning (got %d)" % code)
        check("ESCALATED" in out, "and it says ESCALATED on stdout")

    # -- 4. recovery clears it ----------------------------------------------
    print("\n4. one good run clears the streak completely")
    with Sandbox(PUBLISHED, "L5", LIVE_BOARD, all_unreachable=True):
        for _ in range(liveness.UNKNOWN_STREAK_ESCALATE + 1):
            _h.run()
        check(_h.record()["escalate"] is True, "escalated after the outage")
        # Same sandbox, network restored: the observation file persists, which is
        # the only memory this stateless job has.
        liveness.probe_board = _sb_probe_ok()
        code, out = _h.run()
        rec = _h.record()
        check(rec["unknown_streak"] == 0, "streak reset to 0 on recovery")
        check(rec["escalate"] is False, "escalate cleared")
        check(rec["unknown_since"] is None, "unknown_since cleared")

    # -- 5. no memory must not read as no problem ---------------------------
    print("\n5. a missing observation file is a streak of ONE, never zero")
    with Sandbox(PUBLISHED, "L5", LIVE_BOARD, all_unreachable=True):
        check(not liveness.OUT_JSON.exists(), "no prior observation exists")
        _h.run()
        rec = _h.record()
        check(rec["unknown_streak"] == 1,
              "first-ever run with no history counts as 1, not 0 -- "
              "'I have no memory' must not read as 'all is well'")

    print("\n%d checks, %d failed" % (CHECKS[0], len(FAILURES)))
    if FAILURES:
        for f in FAILURES:
            print("  FAILED: %s" % f)
        return 1
    print("OK: one unknown is an admission; a sustained one escalates and says so.")
    return 0


def _sb_probe_ok():
    """A probe that succeeds, for the recovery case."""
    def probe(seed, version):
        rows = LIVE_BOARD.get((seed, version)) or []
        return {"seed": seed, "version": version,
                "key_shape": liveness.key_shape(version),
                "entries": len(rows),
                "players": len({r["player_name"] for r in rows}),
                "player_names": sorted({r["player_name"] for r in rows}),
                "builds_seen": sorted({r["game_mode"] for r in rows}),
                "first_entry": rows[0]["date"] if rows else None,
                "last_entry": rows[-1]["date"] if rows else None}
    return probe


if __name__ == "__main__":
    sys.exit(main())
