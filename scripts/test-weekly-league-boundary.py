#!/usr/bin/env python3
"""Pin the weekly-league rollover boundary. TECH_DEBT A9 must not come back.

What this guards
----------------
The league week runs **Friday 00:00:00 -> Thursday 23:59:59 in Australia/Hobart**
(Pip's ruling 2026-07-28; pdoom1/docs/RELEASE_NOMENCLATURE.md: a Seed roll is
"every Fri"). The rollover cron fires **Thursday 14:00 UTC**, which lands on a
Friday in Hobart in both halves of the year:

    winter (AEST, UTC+10)   Thu 14:00Z -> Fri 00:00 +10:00   exactly the boundary
    summer (AEDT, UTC+11)   Thu 14:00Z -> Fri 01:00 +11:00   one hour into the week

Two failure modes are pinned here, and they are different:

1. **The A9 off-by-one.** The old code derived the week from `now`, so the
   rollover opened the week that was *ending*: on 2026-07-26T14:28Z it wrote
   `2026_W30` (2026-07-20 -> 2026-07-26) as the brand-new current week. Ten weeks
   of green checkmarks, every one of them a week late.
2. **The DST trap.** GitHub cron is UTC-only with no DST awareness, and Tasmania
   observes daylight saving. A hardcoded `+10:00` would silently move the
   boundary by an hour from early October to early April every year. The tests in
   section 2 fail if anyone replaces ZoneInfo with a fixed offset.

Requires `tzdata` on Windows (`pip install tzdata`, pinned in requirements.txt);
zoneinfo has no bundled database there. That asymmetry -- green in CI, dead on
Pip's box -- is exactly why section 0 checks the zone first and says so loudly.

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
AEST = timezone(timedelta(hours=10))   # what a hardcoded offset would look like
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
    """week_info the manager would open for a run at `ts` (no disk writes)."""
    return _MANAGER.get_current_week_info(
        datetime.fromisoformat(ts.replace("Z", "+00:00")))


_MANAGER = wlm.WeeklyLeagueManager()


# --------------------------------------------------------------------------
# 0. THE ZONE ITSELF. If this fails, nothing below means anything -- and the
#    message must name the fix, because on Windows this is the first thing to
#    break and the last thing anyone suspects.
# --------------------------------------------------------------------------
print("\n-- the league timezone resolves (needs tzdata on Windows) --")
try:
    _TZ = wlm.league_tz()
    print(f"[ok  ] league_tz() resolved: {_TZ}")
    CHECKS += 1
except RuntimeError as e:
    print(f"[FAIL] league_tz() could not resolve {wlm.LEAGUE_TZ_NAME}:\n{e}")
    sys.exit(1)

check("the anchor zone is the IANA zone, not an offset", str(_TZ), "Australia/Hobart")
check("anchor weekday is Friday (datetime.weekday(): Mon=0)", wlm.ANCHOR_WEEKDAY, 4)

# ZoneInfo really is doing the DST work -- both offsets must be observed.
_winter = datetime(2026, 7, 31, 0, 0, tzinfo=_TZ)
_summer = datetime(2026, 11, 27, 0, 0, tzinfo=_TZ)
check("Hobart offset on 2026-07-31 (AEST)", _winter.utcoffset(), timedelta(hours=10))
check("Hobart offset on 2026-11-27 (AEDT)", _summer.utcoffset(), timedelta(hours=11))


# --------------------------------------------------------------------------
# 1. THE BOUNDARY IN WINTER. Thu 2026-08-06 14:00 UTC == Fri 2026-08-07
#    00:00:00 +10:00 exactly -- and that Friday is the epoch fork, so this is
#    the single most load-bearing instant in the whole system.
# --------------------------------------------------------------------------
print("\n-- boundary, winter: Thu 2026-08-06 14:00 UTC == Fri 2026-08-07 00:00 Hobart --")

before = week_of("2026-08-06T13:59:00Z")
check("13:59 UTC (one minute BEFORE) -> previous week", before["week_id"], "2026_W32")
check("13:59 UTC -> week started Fri 2026-07-31", before["start_date"], "2026-07-31")
check("13:59 UTC -> week ends Thu 2026-08-06", before["end_date"], "2026-08-06")
check("13:59 UTC -> status", before["status"], "running")

check("13:59:59 UTC is still the outgoing week",
      week_of("2026-08-06T13:59:59Z")["week_id"], "2026_W32")

at = week_of("2026-08-06T14:00:00Z")
check("14:00:00 UTC (exactly the rollover) -> the week that STARTS",
      at["week_id"], "2026_W33")
check("14:00 UTC -> week starts Fri 2026-08-07", at["start_date"], "2026-08-07")
check("14:00 UTC -> week ends Thu 2026-08-13", at["end_date"], "2026-08-13")
check("14:00 UTC -> start_timestamp is Hobart-local with its offset",
      at["start_timestamp"], "2026-08-07T00:00:00+10:00")
check("14:00 UTC -> end_timestamp", at["end_timestamp"], "2026-08-13T23:59:59+10:00")
check("14:00 UTC -> start_timestamp_utc", at["start_timestamp_utc"], "2026-08-06T14:00:00Z")
check("14:00 UTC -> the week is already running, not upcoming", at["status"], "running")
check("14:00 UTC -> week_info names the zone", at["timezone"], "Australia/Hobart")

after = week_of("2026-08-06T14:01:00Z")
check("14:01 UTC (one minute AFTER) -> same week as 14:00",
      after["week_id"], "2026_W33")
check("14:01 UTC -> start_date matches 14:00", after["start_date"], at["start_date"])

# --------------------------------------------------------------------------
# 2. THE BOUNDARY IN SUMMER (AEDT). This is the DST case, and it is the one a
#    hardcoded offset gets wrong. Fri 2026-11-27 00:00 +11:00 == Thu
#    2026-11-26 13:00 UTC, an hour EARLIER in UTC than the winter boundary.
# --------------------------------------------------------------------------
print("\n-- boundary, summer: Fri 2026-11-27 00:00 Hobart == Thu 2026-11-26 13:00 UTC --")

check("Thu 12:59:59 UTC -> still the outgoing week",
      week_of("2026-11-26T12:59:59Z")["week_id"], "2026_W48")
check("Thu 13:00:00 UTC -> the new week has begun (DST-shifted boundary)",
      week_of("2026-11-26T13:00:00Z")["week_id"], "2026_W49")
check("Thu 13:00 UTC -> week starts Fri 2026-11-27",
      week_of("2026-11-26T13:00:00Z")["start_date"], "2026-11-27")
check("Thu 13:00 UTC -> start_timestamp carries +11:00, not +10:00",
      week_of("2026-11-26T13:00:00Z")["start_timestamp"], "2026-11-27T00:00:00+11:00")

cron_summer = week_of("2026-11-26T14:00:00Z")
check("the cron (Thu 14:00 UTC) lands INSIDE the summer week it opens",
      cron_summer["week_id"], "2026_W49")
check("summer cron -> same start as the 13:00 boundary",
      cron_summer["start_date"], "2026-11-27")
check("summer cron -> status is running (one hour in), never upcoming",
      cron_summer["status"], "running")

# The regression this section exists for: with a hardcoded +10:00, the summer
# boundary would be computed as Thu 14:00 UTC instead of Thu 13:00 UTC, so
# 13:30 UTC would still report the OLD week. Assert the zone-aware answer
# differs from the fixed-offset answer at that instant.
_probe = datetime(2026, 11, 26, 13, 30, tzinfo=UTC)
_zone_day = _probe.astimezone(_TZ).date()
_fixed_day = _probe.astimezone(AEST).date()
check("a fixed +10:00 offset would disagree with the zone in summer",
      (_zone_day.isoformat(), _fixed_day.isoformat()),
      ("2026-11-27", "2026-11-26"))
check("and the zone-aware answer is the one the manager uses",
      week_of("2026-11-26T13:30:00Z")["start_date"], "2026-11-27")

# --------------------------------------------------------------------------
# 3. WEEKS THAT CONTAIN A DST TRANSITION. Hobart springs forward 02:00 -> 03:00
#    on Sun 2026-10-04 and falls back on Sun 2027-04-04, so those league weeks
#    are 7 days MINUS an hour and 7 days PLUS an hour in elapsed time. The
#    wall-clock week is still Fri 00:00 -> Thu 23:59:59.
# --------------------------------------------------------------------------
print("\n-- weeks spanning a Hobart DST transition --")

spring = week_of("2026-10-02T14:00:00Z")     # Fri 2026-10-02 (AEST) -> Thu 2026-10-08 (AEDT)
check("spring-forward week starts Fri 2026-10-02", spring["start_date"], "2026-10-02")
check("spring-forward week ends Thu 2026-10-08", spring["end_date"], "2026-10-08")
check("spring-forward week starts at +10:00", spring["start_timestamp"][-6:], "+10:00")
check("spring-forward week ends at +11:00", spring["end_timestamp"][-6:], "+11:00")
_ss = datetime.fromisoformat(spring["start_timestamp"])
_se = datetime.fromisoformat(spring["end_timestamp"])
check("spring-forward week is 7 days minus an hour minus a second, in real time",
      _se - _ss, timedelta(days=7) - timedelta(hours=1) - timedelta(seconds=1))

autumn = week_of("2027-04-02T13:00:00Z")     # Fri 2027-04-02 (AEDT) -> Thu 2027-04-08 (AEST)
check("fall-back week starts Fri 2027-04-02", autumn["start_date"], "2027-04-02")
check("fall-back week ends Thu 2027-04-08", autumn["end_date"], "2027-04-08")
check("fall-back week starts at +11:00", autumn["start_timestamp"][-6:], "+11:00")
check("fall-back week ends at +10:00", autumn["end_timestamp"][-6:], "+10:00")
_as = datetime.fromisoformat(autumn["start_timestamp"])
_ae = datetime.fromisoformat(autumn["end_timestamp"])
check("fall-back week is 7 days plus an hour minus a second, in real time",
      _ae - _as, timedelta(days=7) + timedelta(hours=1) - timedelta(seconds=1))

# --------------------------------------------------------------------------
# 4. THE ACTUAL REGRESSION. The 2026-07-26T14:28Z run shipped 2026_W30.
#    Under the Friday anchor that instant is Mon 2026-07-27 00:28 Hobart, which
#    sits in the week that opened Fri 2026-07-24 -- still labelled 2026_W31, so
#    the original A9 assertion survives the anchor change unchanged.
# --------------------------------------------------------------------------
print("\n-- regression: the run that produced the wrong current.json --")
check("2026-07-26T14:28Z run must NOT open the shipped 2026_W30",
      week_of("2026-07-26T14:28:04Z")["week_id"], "2026_W31")

# The old Sunday anchor must be gone: nothing special may happen at Sun 14:00Z.
print("\n-- the old Sunday 14:00 UTC anchor is gone --")
check("Sun 2026-08-02 13:59Z and 14:00Z are the same league week",
      (week_of("2026-08-02T13:59:00Z")["week_id"],
       week_of("2026-08-02T14:00:00Z")["week_id"]),
      ("2026_W32", "2026_W32"))
check("...and the same start date",
      week_of("2026-08-02T14:00:00Z")["start_date"], "2026-07-31")

# --------------------------------------------------------------------------
# 5. Ordinary instants map to the week that contains them.
# --------------------------------------------------------------------------
print("\n-- ordinary instants --")
check("Sat 2026-08-08 (Hobart) is in the week that opened Fri 2026-08-07",
      week_of("2026-08-08T02:00:00Z")["week_id"], "2026_W33")
check("Wed 2026-07-29 09:00Z -> the week that opened Fri 2026-07-24",
      week_of("2026-07-29T09:00:00Z")["week_id"], "2026_W31")
check("Thu 2026-08-06 03:00Z (Thursday, pre-rollover) -> outgoing week",
      week_of("2026-08-06T03:00:00Z")["week_id"], "2026_W32")
check("Fri 2026-08-07 14:00Z (14:00 but NOT Thursday -> no shift)",
      week_of("2026-08-07T14:00:00Z")["week_id"], "2026_W33")

# --------------------------------------------------------------------------
# 6. ISO-year straddle. 2026 has 53 ISO weeks. The label comes from the league
#    week's own Thursday (ISO 8601's own rule), so consecutive Fridays get
#    consecutive labels across the year boundary.
# --------------------------------------------------------------------------
print("\n-- ISO year/week straddle --")
check("Fri 2026-12-25 (Thu 13:00Z trigger) -> 2026_W53",
      week_of("2026-12-24T13:00:00Z")["week_id"], "2026_W53")
check("Fri 2027-01-01 -> 2027_W01",
      week_of("2026-12-31T13:00:00Z")["week_id"], "2027_W01")
check("Thu 2026-12-31 12:59Z -> still 2026_W53 (week not over yet)",
      week_of("2026-12-31T12:59:00Z")["week_id"], "2026_W53")

# --------------------------------------------------------------------------
# 7. Timezone handling of the INPUT. A naive datetime must be read as UTC, not
#    as the local clock of whatever machine is running -- `datetime.now()`
#    unqualified on Pip's box is AEST, and `.isoformat() + "Z"` used to bolt a
#    UTC suffix onto it.
# --------------------------------------------------------------------------
print("\n-- timezone handling of the input instant --")
naive = _MANAGER.get_current_week_info(datetime(2026, 8, 6, 14, 0, 0))
check("naive 2026-08-06 14:00 treated as UTC", naive["week_id"], "2026_W33")
tagged = _MANAGER.get_current_week_info(datetime(2026, 8, 7, 0, 0, 0, tzinfo=AEST))
check("2026-08-07 00:00 +10:00 == 2026-08-06 14:00 UTC", tagged["week_id"], "2026_W33")
check("a naive local-looking instant does NOT silently become the next week",
      _MANAGER.get_current_week_info(datetime(2026, 8, 6, 13, 0, 0))["week_id"],
      "2026_W32")

# --------------------------------------------------------------------------
# 8. Invariants across a year of rollovers, ACROSS both DST transitions.
# --------------------------------------------------------------------------
print("\n-- invariants across 60 consecutive rollovers (spans both DST changes) --")
bad_weekday = bad_end = bad_id = bad_span = 0
prev_id = None
non_monotonic = 0
t = datetime(2026, 8, 6, 14, 0, tzinfo=UTC)   # a Thursday rollover
for _ in range(60):
    wi = _MANAGER.get_current_week_info(t)
    start = datetime.fromisoformat(wi["start_timestamp"])
    end = datetime.fromisoformat(wi["end_timestamp"])
    if start.weekday() != 4 or (start.hour, start.minute, start.second) != (0, 0, 0):
        bad_weekday += 1
    # end is one second before the NEXT anchor, in wall-clock terms
    if (end.year, end.month, end.day) != tuple(
            (start.date() + timedelta(days=6)).timetuple()[:3]):
        bad_end += 1
    if (end.hour, end.minute, end.second) != (23, 59, 59):
        bad_span += 1
    if wi["week_id"] != wlm.week_id_for(start):
        bad_id += 1
    if prev_id is not None and wi["week_id"] <= prev_id and not wi["week_id"].startswith("2027"):
        non_monotonic += 1
    prev_id = wi["week_id"]
    t += timedelta(days=7)
check("every week starts Friday 00:00:00 local", bad_weekday, 0)
check("every week ends on its own Thursday", bad_end, 0)
check("every week ends at 23:59:59 local wall-clock", bad_span, 0)
check("week_id always agrees with its own start", bad_id, 0)
check("week_id increases week over week", non_monotonic, 0)

# --------------------------------------------------------------------------
# 9. The epoch fork. Boundary = Fri 2026-08-07 00:00 Hobart (2026-08-06T14:00Z):
#    the first Friday of August, where 0.13 -> 0.14 and L2 -> L3. A week is
#    anomalous iff it STARTS before the fork, so the week beginning Fri
#    2026-07-31 -- a Seed roll on unchanged rules -- is still pre-history.
# --------------------------------------------------------------------------
print("\n-- ladder epoch stamp --")
check("epoch boundary in UTC", wlm.as_utc(wlm.epoch_boundary()).isoformat(),
      "2026-08-06T14:00:00+00:00")
check("epoch boundary in Hobart terms", wlm.epoch_boundary().isoformat(),
      "2026-08-07T00:00:00+10:00")
pre = week_of("2026-08-06T13:59:00Z")
post = week_of("2026-08-06T14:00:00Z")
check("2026_W32 (starts Fri 2026-07-31, a Seed roll) is anomalous",
      pre["epoch"]["anomalous"], True)
check("2026_W32 epoch id", pre["epoch"]["id"], "pre-regularisation")
check("2026_W33 (starts Fri 2026-08-07, the fork) is NOT anomalous",
      post["epoch"]["anomalous"], False)
check("2026_W33 epoch id", post["epoch"]["id"], "regularised")
check("the stamp carries the boundary in both clocks",
      (post["epoch"]["boundary_utc"], post["epoch"]["boundary_local"],
       post["epoch"]["boundary_tz"]),
      ("2026-08-06T14:00:00Z", "2026-08-07T00:00:00+10:00", "Australia/Hobart"))
check("epoch stamp points at the archivist doc",
      post["epoch"]["see"], "docs/LEAGUE_EPOCH_ANOMALY.md")
check("the stated reason names the fork, not just a date",
      all(s in post["epoch"]["reason"] for s in ("2026-08-07", "L2 -> L3")), True)

# --------------------------------------------------------------------------
# 10. The cron in the workflow must still match the constants -- AND still land
#     on a Friday in Hobart in both halves of the year. The numeric check
#     catches a typo; the semantic check catches someone "fixing" DST by moving
#     the cron hour, which is the tempting wrong answer.
# --------------------------------------------------------------------------
print("\n-- cron agrees with the anchor, in both DST states --")
wf = (Path(__file__).parent.parent / ".github" / "workflows" / "weekly-league-reset.yml").read_text(encoding="utf-8")
crons = [ln.split("'")[1] for ln in wf.splitlines() if "- cron:" in ln and "'" in ln]
check("exactly one cron in weekly-league-reset.yml", len(crons), 1)
if crons:
    minute, hour, _dom, _mon, dow = crons[0].split()
    check("cron hour matches ROLLOVER_HOUR_UTC", int(hour), wlm.ROLLOVER_HOUR_UTC)
    check("cron minute is 0", int(minute), 0)
    # cron day-of-week 0 == Sunday, so Thursday == 4.
    check("cron day-of-week matches ROLLOVER_CRON_DOW", int(dow), wlm.ROLLOVER_CRON_DOW)
    check("ROLLOVER_CRON_DOW is Thursday", wlm.ROLLOVER_CRON_DOW, 4)

    # Semantic: build real UTC instants from the cron fields, one in each DST
    # state, and assert both are Fridays in Hobart AND are inside (never before)
    # the week they open.
    cron_weekday_py = (int(dow) - 1) % 7          # cron 0=Sun -> weekday() Sun=6
    bad_day = bad_order = 0
    probes = []
    for base in (datetime(2026, 7, 30, tzinfo=UTC),      # winter, AEST
                 datetime(2026, 11, 26, tzinfo=UTC)):    # summer, AEDT
        assert base.weekday() == cron_weekday_py, "probe is not on the cron's weekday"
        fire = base.replace(hour=int(hour), minute=int(minute))
        local = fire.astimezone(_TZ)
        if local.weekday() != wlm.ANCHOR_WEEKDAY:
            bad_day += 1
        start = wlm.league_week_start(fire)
        if wlm.as_utc(start) > wlm.as_utc(fire):
            bad_order += 1
        probes.append(local.isoformat())
    check("the cron instant is a Friday in Hobart in both DST states", bad_day, 0)
    check("the cron never fires BEFORE the week it opens", bad_order, 0)
    check("the two probe instants in Hobart terms", probes,
          ["2026-07-31T00:00:00+10:00", "2026-11-27T01:00:00+11:00"])

# --------------------------------------------------------------------------
print("\n" + "-" * 72)
if FAILURES:
    print(f"FAILED: {len(FAILURES)}/{CHECKS} checks failed")
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print(f"PASSED: {CHECKS}/{CHECKS} checks")
sys.exit(0)
