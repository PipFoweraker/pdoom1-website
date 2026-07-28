#!/usr/bin/env python3
"""Pin the weekly-league rollover boundary. TECH_DEBT A9 must not come back.

What this guards
----------------
The rollover cron fires **Sunday 14:00 UTC**. The week it opens must be the
week that is *starting* (the following Monday 00:00 UTC), not the week that is
about to end ~10 hours later.

The shipped bug derived everything from `now`: on 2026-07-26T14:28Z the
rollover wrote `2026_W30` (2026-07-20 -> 2026-07-26) as the brand-new current
week. Ten weeks of green checkmarks, every one of them a week late.

This test is deliberately over-specific about the boundary -- exactly
14:00:00, and one minute either side -- because that is the only place the
mapping can silently slip, and it is about to become load-bearing (first
"good" rollover: Sunday 2026-08-02 14:00 UTC).

Run: python scripts/test-weekly-league-boundary.py
"""

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# The module name has hyphens, so it cannot be `import`ed normally.
_MODULE_PATH = Path(__file__).parent / "weekly-league-manager.py"
_spec = importlib.util.spec_from_file_location("weekly_league_manager", _MODULE_PATH)
wlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wlm)

UTC = timezone.utc
FAILURES = []
CHECKS = 0


def check(label, got, want):
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n      got:  {got!r}\n      want: {want!r}")
        print(f"[FAIL] {label}: got {got!r}, want {want!r}")
    else:
        print(f"[ok  ] {label}: {got!r}")


def week_of(ts):
    """week_id the manager would open for a run at `ts` (no disk writes)."""
    return wlm.WeeklyLeagueManager.get_current_week_info(
        _MANAGER, datetime.fromisoformat(ts.replace("Z", "+00:00"))
    )


_MANAGER = wlm.WeeklyLeagueManager()


# --------------------------------------------------------------------------
# 1. THE BOUNDARY. Sunday 2026-08-02 is the last day of ISO week 2026-W31;
#    2026-W32 runs Mon 2026-08-03 -> Sun 2026-08-09.
# --------------------------------------------------------------------------
print("\n-- boundary: Sunday 2026-08-02 14:00 UTC (the first 'good' rollover) --")

before = week_of("2026-08-02T13:59:00Z")
check("13:59 UTC (one minute BEFORE rollover) -> week still running",
      before["week_id"], "2026_W31")
check("13:59 UTC -> week starts Monday 2026-07-27", before["start_date"], "2026-07-27")
check("13:59 UTC -> week ends Sunday 2026-08-02", before["end_date"], "2026-08-02")
check("13:59 UTC -> status", before["status"], "running")

at = week_of("2026-08-02T14:00:00Z")
check("14:00:00 UTC (exactly the rollover) -> opens the week that STARTS",
      at["week_id"], "2026_W32")
check("14:00 UTC -> week starts Monday 2026-08-03", at["start_date"], "2026-08-03")
check("14:00 UTC -> week ends Sunday 2026-08-09", at["end_date"], "2026-08-09")
check("14:00 UTC -> status is upcoming (week begins in 10h)", at["status"], "upcoming")

after = week_of("2026-08-02T14:01:00Z")
check("14:01 UTC (one minute AFTER rollover) -> same week as 14:00",
      after["week_id"], "2026_W32")
check("14:01 UTC -> start_date matches 14:00", after["start_date"], at["start_date"])

# --------------------------------------------------------------------------
# 2. THE ACTUAL REGRESSION. The 2026-07-26T14:28Z run shipped 2026_W30.
# --------------------------------------------------------------------------
print("\n-- regression: the run that produced the wrong current.json --")
check("2026-07-26T14:28Z run must open W31, NOT the shipped W30",
      week_of("2026-07-26T14:28:04Z")["week_id"], "2026_W31")

# --------------------------------------------------------------------------
# 3. Non-rollover instants map to the week that contains them.
# --------------------------------------------------------------------------
print("\n-- ordinary instants --")
check("Mon 2026-08-03T00:00Z (week just began)", week_of("2026-08-03T00:00:00Z")["week_id"], "2026_W32")
check("Tue 2026-07-28T09:00Z", week_of("2026-07-28T09:00:00Z")["week_id"], "2026_W31")
check("Sun 2026-08-02T00:00Z (Sunday, pre-rollover hour)", week_of("2026-08-02T00:00:00Z")["week_id"], "2026_W31")
check("Sun 2026-08-02T23:59Z (Sunday, post-rollover)", week_of("2026-08-02T23:59:59Z")["week_id"], "2026_W32")
check("Sat 2026-08-01T14:00Z (14:00 but NOT Sunday -> no shift)",
      week_of("2026-08-01T14:00:00Z")["week_id"], "2026_W31")

# --------------------------------------------------------------------------
# 4. ISO-year straddle. 2026 has 53 ISO weeks; the week_id year must be the
#    ISO year of the WEEK START, not the calendar year of `now`.
# --------------------------------------------------------------------------
print("\n-- ISO year/week straddle --")
check("Sun 2026-12-27T14:00Z -> 2026_W53 (Mon 2026-12-28)",
      week_of("2026-12-27T14:00:00Z")["week_id"], "2026_W53")
check("Sun 2027-01-03T14:00Z -> 2027_W01 (Mon 2027-01-04)",
      week_of("2027-01-03T14:00:00Z")["week_id"], "2027_W01")
check("Sun 2027-01-03T13:59Z -> 2026_W53 (week not over yet)",
      week_of("2027-01-03T13:59:00Z")["week_id"], "2026_W53")

# --------------------------------------------------------------------------
# 5. Timezone handling. A naive datetime must be read as UTC, not local --
#    Pip's box is AEST (+10), which is exactly the size of the skew that would
#    push a Sunday-14:00 run across the boundary.
# --------------------------------------------------------------------------
print("\n-- timezone handling --")
naive = _MANAGER.get_current_week_info(datetime(2026, 8, 2, 14, 0, 0))
check("naive 2026-08-02 14:00 treated as UTC", naive["week_id"], "2026_W32")
aest = _MANAGER.get_current_week_info(
    datetime(2026, 8, 3, 0, 0, 0, tzinfo=timezone(timedelta(hours=10))))
check("2026-08-03 00:00 AEST == 2026-08-02 14:00 UTC", aest["week_id"], "2026_W32")

# --------------------------------------------------------------------------
# 6. Internal consistency: end is always 6d23h59m59s after start, and the
#    week_id agrees with its own start_date.
# --------------------------------------------------------------------------
print("\n-- invariants across a year of Sunday rollovers --")
bad_span = bad_id = bad_weekday = 0
t = datetime(2026, 1, 4, 14, 0, tzinfo=UTC)   # a Sunday
for _ in range(60):
    wi = _MANAGER.get_current_week_info(t)
    start = datetime.fromisoformat(wi["start_timestamp"])
    end = datetime.fromisoformat(wi["end_timestamp"])
    if end - start != timedelta(days=6, hours=23, minutes=59, seconds=59):
        bad_span += 1
    if start.weekday() != 0:
        bad_weekday += 1
    y, w, _d = start.isocalendar()
    if wi["week_id"] != f"{y}_W{w:02d}":
        bad_id += 1
    t += timedelta(days=7)
check("every week starts on a Monday", bad_weekday, 0)
check("every week spans 6d23h59m59s", bad_span, 0)
check("week_id always agrees with start_date's ISO week", bad_id, 0)

# --------------------------------------------------------------------------
# 7. Epoch stamping (Task 2). Boundary = 2026-07-31; a week is anomalous iff
#    it STARTS before it, so W31 straddles-and-is-anomalous, W32 is clean.
# --------------------------------------------------------------------------
print("\n-- ladder epoch stamp --")
check("W31 (starts 2026-07-27, straddles the cut) is anomalous",
      week_of("2026-08-02T13:59:00Z")["epoch"]["anomalous"], True)
check("W31 epoch id", week_of("2026-08-02T13:59:00Z")["epoch"]["id"], "pre-regularisation")
check("W32 (starts 2026-08-03) is NOT anomalous",
      week_of("2026-08-02T14:00:00Z")["epoch"]["anomalous"], False)
check("W32 epoch id", week_of("2026-08-02T14:00:00Z")["epoch"]["id"], "regularised")
check("epoch stamp points at the archivist doc",
      week_of("2026-08-02T14:00:00Z")["epoch"]["see"], "docs/LEAGUE_EPOCH_ANOMALY.md")

# --------------------------------------------------------------------------
# 8. The cron in the workflow must still match ROLLOVER_HOUR_UTC. If someone
#    moves the schedule without moving the constant, this whole file is
#    testing a fiction.
# --------------------------------------------------------------------------
print("\n-- cron agrees with ROLLOVER_HOUR_UTC --")
wf = (Path(__file__).parent.parent / ".github" / "workflows" / "weekly-league-reset.yml").read_text(encoding="utf-8")
crons = [ln.split("'")[1] for ln in wf.splitlines() if "- cron:" in ln and "'" in ln]
check("exactly one cron in weekly-league-reset.yml", len(crons), 1)
if crons:
    minute, hour, _dom, _mon, dow = crons[0].split()
    check("cron hour matches ROLLOVER_HOUR_UTC", int(hour), wlm.ROLLOVER_HOUR_UTC)
    check("cron minute is 0", int(minute), 0)
    # cron day-of-week 0 == Sunday; datetime.weekday() Sunday == 6
    check("cron day-of-week is Sunday", int(dow), 0)
    check("ROLLOVER_WEEKDAY is Sunday", wlm.ROLLOVER_WEEKDAY, 6)

# --------------------------------------------------------------------------
print("\n" + "-" * 72)
if FAILURES:
    print(f"FAILED: {len(FAILURES)}/{CHECKS} checks failed")
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print(f"PASSED: {CHECKS}/{CHECKS} checks")
sys.exit(0)
