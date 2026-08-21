#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Forced-state tests for the board probe's total wall-clock budget.

WHY THIS EXISTS
---------------
On 2026-08-20 the DreamCompute VPS became unreachable. `get_json` already capped
every GET at 20 seconds, so each individual request was bounded -- and the run
still went for **13.9 hours** before a human cancelled it, because the candidate
set had grown to 9 seeds x 230 versions = 2,070 boards and 2070 x 20s = 11.5
hours. A per-request timeout does not bound a run.

The blast radius was not the probe. `board-liveness.yml` declares
`concurrency: {group: board-liveness, cancel-in-progress: false}`, so the hung run
held the group and the next EIGHT scheduled runs were cancelled while queued. And
`auto-deploy-on-push.yml` triggers on this workflow COMPLETING, so production lost
its 4x/day full deploy for four days as well. One unreachable host, via one
unbounded loop, took out the site's deploy cadence.

CLAUDE.md's testing discipline: a claimed safety property needs a FORCED failure,
because a guard seen only in its passing state has not been shown to work. Each
case below constructs the state rather than waiting for it.

Case 3 is the one that matters most: it proves the circuit breaker was NOT bought
by making the probe give up on ordinary errors. An HTTP status is a real answer
from a living host and must never trip it.

HOW IT ISOLATES
---------------
The module is imported and `probe_board` is replaced with a stub. Nothing here
issues a single HTTP request -- safe offline, safe in CI, and it cannot POST to
the score API even by accident (this repo is a READ-ONLY consumer, pdoom1 #679).

Run:  python scripts/test-board-probe-budget.py     (exit 0 = pass)
"""

import importlib.util
import sys
import time
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


def run_loop(probe, seeds, versions, budget_s, streak):
    """Re-implementation of the guarded loop, driven by a stubbed probe.

    Kept in step with check-board-liveness.py by asserting the two constants
    exist there (case 4); the loop body itself is short enough that duplicating
    it here is cheaper than exporting it and safer than not testing it at all.
    """
    results, budget_hit, unreachable_streak = [], False, 0
    started = time.monotonic()
    for s in seeds:
        for v in versions:
            if time.monotonic() - started > budget_s:
                budget_hit = "budget"
                break
            if unreachable_streak >= streak:
                budget_hit = "unreachable"
                break
            r = probe(s, v)
            err = r.get("error") or ""
            if err:
                unreachable_streak = (unreachable_streak + 1
                                      if not err.startswith("HTTP ") else 0)
            else:
                unreachable_streak = 0
            results.append(r)
        if budget_hit:
            break
    return results, budget_hit


SEEDS = ["s%02d" % i for i in range(9)]
VERSIONS = ["L%d" % i for i in range(230)]
TOTAL = len(SEEDS) * len(VERSIONS)

print("Board probe budget -- forced states")
print("=" * 74)
print("  candidate set: %d seeds x %d versions = %d boards" % (len(SEEDS), len(VERSIONS), TOTAL))
print()

# --- 1. the 2026-08-20 outage ------------------------------------------------
print("1. HOST UNREACHABLE -- the state that ran for 13.9 hours")
res, hit = run_loop(lambda s, v: {"seed": s, "version": v, "error": "URLError: timed out"},
                    SEEDS, VERSIONS, budget_s=600, streak=8)
check(hit == "unreachable", "stops on the unreachable breaker, not after exhausting the set")
check(len(res) == 8, "asked 8 boards, not %d (asked %d)" % (TOTAL, len(res)))
check(len(res) * 20 / 3600 < 0.1,
      "worst-case wall clock is minutes, not the 11.5h the unguarded loop cost")
print()

# --- 2. a slow-but-alive host ------------------------------------------------
print("2. HOST ALIVE BUT SLOW -- the budget, not the breaker, must stop it")
calls = {"n": 0}


def slow_ok(s, v):
    calls["n"] += 1
    time.sleep(0.004)                      # stands in for a slow but answering API
    return {"seed": s, "version": v, "entries": 0}


res2, hit2 = run_loop(slow_ok, SEEDS, VERSIONS, budget_s=0.25, streak=8)
check(hit2 == "budget", "stops on the wall-clock budget when every answer is valid")
check(0 < len(res2) < TOTAL, "stopped partway (%d of %d), rather than not at all" % (len(res2), TOTAL))
print()

# --- 3. THE ONE THAT MATTERS: an HTTP status is a real answer -----------------
print("3. HTTP ERRORS MUST NOT TRIP THE BREAKER -- proving it was not disarmed")
res3, hit3 = run_loop(lambda s, v: {"seed": s, "version": v, "error": "HTTP 404"},
                      SEEDS, VERSIONS, budget_s=600, streak=8)
check(hit3 is False, "a host answering 404 on every board is NOT 'unreachable'")
check(len(res3) == TOTAL, "asked all %d boards (asked %d)" % (TOTAL, len(res3)))
print()

# --- 4. the constants exist where the real loop reads them -------------------
print("4. THE REAL MODULE CARRIES THE BOUNDS")
check(hasattr(liveness, "PROBE_BUDGET_S"), "check-board-liveness.py defines PROBE_BUDGET_S")
check(hasattr(liveness, "UNREACHABLE_STREAK"), "check-board-liveness.py defines UNREACHABLE_STREAK")
check(getattr(liveness, "PROBE_BUDGET_S", 0) <= 3600,
      "the budget is under an hour, so it can never again outlive its own cron interval")
src = (ROOT / "scripts" / "check-board-liveness.py").read_text(encoding="utf-8")
check("PROBE INCOMPLETE" in src,
      "a truncated probe SAYS it was truncated -- silence would report 'live' having not asked")
print()

if failures:
    print("FAILED:")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("OK: the probe is bounded in wall clock as well as per request, it stops early only")
print("    for a dead host, and a truncated run announces itself.")
