#!/usr/bin/env python
"""Forced-failure tests for the league archive step's exit-code contract.

    python scripts/test-league-archive-outcomes.py      (exit 0 = pass)

WHY THIS FILE EXISTS
--------------------
D4 of pdoom1-website#384. `.github/workflows/weekly-league-reset.yml` used to run

    python scripts/weekly-league-manager.py --archive-week \\
        || echo "Archive failed (may already be archived)"

which invents a benign cause it never checked. The fix removes the `|| echo` and
rests on a claim about the script: **exit 0 already means benign, exit 1 already
means a real fault.** A claim is not evidence, so this file forces all three
states and observes the exit code.

It also asserts the workflow itself, because the fix is only worth anything
while the masking stays removed -- and a comment explaining why is exactly the
sort of thing a later edit restores over.

Nothing here touches the real public/. Every case runs against a manager whose
directories are redirected into a temp tree.
"""

import sys
import os
import json
import shutil
import tempfile
import importlib.util
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "weekly-league-reset.yml"

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def load_manager():
    spec = importlib.util.spec_from_file_location(
        "weekly_league_manager", ROOT / "scripts" / "weekly-league-manager.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TempLeague:
    """A manager with every directory it writes redirected into a temp tree."""

    def __init__(self, mod, current=None):
        self.mod = mod
        self.current = current

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        weekly = self.tmp / "weekly"
        (weekly / "archive").mkdir(parents=True)
        self.m = self.mod.WeeklyLeagueManager()
        self.m.league_data_dir = weekly
        self.m.current_league_file = weekly / "current.json"
        self.m.archive_dir = weekly / "archive"
        if self.current is not None:
            self.m.current_league_file.write_text(
                json.dumps(self.current), encoding="utf-8")
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


A_WEEK = {
    "week_info": {"week_id": "2026_W99", "is_current": True, "status": "active"},
    "entries": [],
}


print("=" * 62)
print("D4 -- the archive step's exit code, forced")
print("=" * 62)

mod = load_manager()

# ---------------------------------------------------------------- state 1
print("\n1. Nothing to archive is BENIGN and already exits 0")
with TempLeague(mod) as t:
    # No current.json at all -- the state the deleted excuse claimed to explain.
    result = t.m.archive_current_week()
    check(result is True, "archive_current_week() returns True when there is no current league")
    check(not any(t.m.archive_dir.glob("*.json")),
          "...and writes no archive file, so it cannot invent an empty week")

# ---------------------------------------------------------------- state 2
print("\n2. A real week archives, and the current file is consumed")
with TempLeague(mod, current=dict(A_WEEK)) as t:
    result = t.m.archive_current_week()
    written = sorted(p.name for p in t.m.archive_dir.glob("*.json"))
    check(result is True, "archive_current_week() returns True on a real archive")
    check("2026_W99_league.json" in written,
          "...and writes the week's file, named from week_id")
    check(not t.m.current_league_file.exists(),
          "...and removes current.json, so a second run hits state 1 rather than duplicating")

    # The idempotence the excuse ASSERTED. Re-running now must be benign --
    # which is the whole reason "may already be archived" sounded plausible.
    again = t.m.archive_current_week()
    check(again is True, "a SECOND run is benign, exactly as the deleted excuse claimed")

# ---------------------------------------------------------------- state 3
print("\n3. A REAL failure returns False -- it never masquerades as benign")
with TempLeague(mod, current=dict(A_WEEK)) as t:
    # Replace the archive directory with a FILE, so writing into it raises.
    # This is the state the deleted message described as "may already be
    # archived", and the point is that it is distinguishable.
    shutil.rmtree(t.m.archive_dir)
    t.m.archive_dir.write_text("not a directory", encoding="utf-8")
    result = t.m.archive_current_week()
    check(result is False, "a genuine write failure returns False, NOT the benign True")
    check(t.m.current_league_file.exists(),
          "...and current.json survives, so the week is not lost with the archive")

# THE DISCRIMINATION. States 1 and 3 must not agree. Without this, everything
# above is consistent with a function that returns True always.
print("\n4. NEGATIVE CONTROL: benign and broken do not return the same thing")
with TempLeague(mod) as empty:
    benign = empty.m.archive_current_week()
with TempLeague(mod, current=dict(A_WEEK)) as broken:
    shutil.rmtree(broken.m.archive_dir)
    broken.m.archive_dir.write_text("x", encoding="utf-8")
    faulted = broken.m.archive_current_week()
check(benign != faulted,
      "nothing-to-do and write-failure return DIFFERENT values, so the exit code carries information")

# ---------------------------------------------------------------- workflow
print("\n5. The workflow no longer manufactures a cause")
wf = WORKFLOW.read_text(encoding="utf-8")

# LIVE lines only. A comment explaining a removed defect is not the defect, and
# a guard that cannot tell the difference punishes the documentation -- which is
# the failure this repo has already paid for three times, most recently in the
# first draft of this very file. The excuse is matched loosely (the two words
# that carry the speculation) rather than as a fixed string, so restoring it
# with different punctuation does not slip through.
live = [ln for ln in wf.splitlines() if not ln.strip().startswith("#")]
live_text = "\n".join(live)

check(not any("already" in ln and "archiv" in ln.lower() for ln in live),
      "no live line speculates that the week was already archived")

archive_lines = [ln for ln in live if "--archive-week" in ln]
check(archive_lines, "the archive step still runs --archive-week")
check(all("||" not in ln for ln in archive_lines),
      "...and no live --archive-week invocation is masked with ||")

# The `if:` that reads as a safety toggle. github.event.inputs is EMPTY on a
# schedule trigger, so the old spelling was unconditionally true on cron --
# CLAUDE.md workflow trap #2. The schedule is parked until 2026-09-02.
check(not any("event.inputs" in ln and "archive_previous" in ln for ln in live),
      "no live archive gate reads the dispatch-inputs context (empty on a schedule)")

# The outcome this step reports is FILED, not just printed: it is passed to
# log-automation-run.py, which writes what /monitoring/ publishes. That is the
# reason the masking mattered, so the linkage is pinned here.
check("--archive-status" in live_text and "steps.archive.outcome" in live_text,
      "steps.archive.outcome is still what gets recorded to monitoring")

print("\n" + "=" * 62)
if failures:
    print("%d FAILURE(S)" % len(failures))
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: benign and broken are distinguishable, and the workflow reports which "
      "one happened instead of guessing.")
