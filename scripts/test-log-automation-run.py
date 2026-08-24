#!/usr/bin/env python3
"""Forced-failure test: the automation logger must never record unearned success.

    python scripts/test-log-automation-run.py     (exit 0 = pass)

WHY THIS FILE EXISTS
--------------------
log-automation-run.py writes public/monitoring/data/automation-status.json, which
/monitoring/ renders as a success rate. Until 2026-08-25 the script began with

    status = "success"

and downgraded only if some detail value read "failure" or "skipped". Measured
against a sandbox copy of the pre-fix script, before any edit:

    --job demo --trigger schedule                      -> success, from {} details
    --job demo2 --trigger schedule --version-status ""
                                  --stats-status ""    -> success, from two empty strings

Both callers in .github/workflows/ interpolate `${{ steps.<id>.outcome }}`, which
expands to the EMPTY STRING whenever the step id does not resolve -- a renamed
step, an `if:`-gated step, a step that never ran. So the second shape is the
realistic one, and on 2026-08-24 the live status file recorded auto-update-data
at 1201 runs / 1201 successes / 0 failures.

CLAUDE.md: "A guard seen only in its passing state has not been shown to work"
and "Absence of a marker is never a clean bill of health." So this file does
three things, and the third is the one that matters:

  1. asserts the new rules on every outcome shape a real caller can produce;
  2. FORCES the two silent-failure paths (corrupt existing log, failed write)
     and asserts the script refuses and says so in its exit code;
  3. re-runs the OLD rule on the same inputs and asserts it DISAGREES. Without
     that, this file could be green because the defect is gone or because the
     assertions never discriminated, and those two look identical from outside.

Nothing here touches public/monitoring/ -- every case runs against a temp
directory via the --monitoring-dir override.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


SCRIPT = Path(__file__).parent / "log-automation-run.py"
REPO_MONITORING = Path(__file__).parent.parent / "public" / "monitoring" / "data"

passed = 0
failed = 0


def ok(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  PASS %s" % name)
    else:
        failed += 1
        print("  FAIL %s%s" % (name, (" -> " + detail) if detail else ""))


def load_module():
    """Import log-automation-run.py by path (its name is not a legal identifier)."""
    spec = importlib.util.spec_from_file_location("log_automation_run", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_cli(tmpdir, *args):
    """Invoke the script as a subprocess, the way a workflow does."""
    cmd = [sys.executable, str(SCRIPT), "--monitoring-dir", str(tmpdir)] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return proc


def read(tmpdir, name):
    p = Path(tmpdir) / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Status derivation, on every shape a real caller can produce.
# ---------------------------------------------------------------------------
def test_status_rules(mod):
    print("\nStatus derivation")

    cases = [
        # (name, details, expected status)
        ("no details at all is UNKNOWN, not success",
         {}, "unknown"),
        ("empty outcome strings are UNKNOWN (the renamed-step shape)",
         {"version-status": "", "stats-status": ""}, "unknown"),
        ("one empty outcome among successes is UNKNOWN",
         {"version-status": "success", "stats-status": ""}, "unknown"),
        ("every outcome success is success",
         {"version-status": "success", "stats-status": "success"}, "success"),
        ("an observed failure is decisive",
         {"version-status": "failure", "stats-status": "success"}, "failure"),
        ("an observed failure beats an unreadable sibling",
         {"version-status": "failure", "stats-status": ""}, "failure"),
        ("skipped is partial",
         {"version-status": "success", "stats-status": "skipped"}, "partial"),
        ("cancelled never completed, so it is UNKNOWN",
         {"version-status": "cancelled", "stats-status": "success"}, "unknown"),
        ("an unrecognised outcome value is UNKNOWN",
         {"version-status": "SUCCESS"}, "unknown"),
        # weekly-league-reset.yml passes --new-week-id. A non-outcome key must
        # not be read as an outcome in either direction.
        ("a non-outcome key alone leaves the run UNOBSERVED",
         {"new-week-id": "2026_W32"}, "unknown"),
        ("a non-outcome key does not spoil a real success",
         {"archive-status": "success", "new-week-id": "2026_W32"}, "success"),
        ("a bare flag on a status key is UNKNOWN, not success",
         {"version-status": "true"}, "unknown"),
    ]

    for name, details, expected in cases:
        got, reason = mod.derive_status(details)
        ok(name, got == expected, "expected %r, got %r (%s)" % (expected, got, reason))
        ok("  ...and %s carries a reason" % expected, bool(reason and reason.strip()))


# ---------------------------------------------------------------------------
# 2. Counters. The success counter is the number published as a success RATE.
# ---------------------------------------------------------------------------
def test_counters():
    print("\nCounters written to disk")

    with tempfile.TemporaryDirectory() as tmp:
        proc = run_cli(tmp, "--job", "demo", "--trigger", "schedule")
        ok("a zero-observation run still exits 0 (it WAS recorded)",
           proc.returncode == 0, "rc=%d %s" % (proc.returncode, proc.stderr))

        status = read(tmp, "automation-status.json")
        job = status["jobs"]["demo"]
        ok("zero observations increment NO success counter",
           job["success_count"] == 0, "success_count=%r" % job["success_count"])
        ok("zero observations increment unknown_count",
           job["unknown_count"] == 1, "unknown_count=%r" % job["unknown_count"])
        ok("zero observations leave last_success null",
           job["last_success"] is None, "last_success=%r" % job["last_success"])
        ok("the run is still counted in total_runs",
           job["total_runs"] == 1)
        ok("the unknown is announced as a workflow warning",
           "::warning::" in proc.stdout, proc.stdout[-200:])

        runs = read(tmp, "automation-runs.json")
        ok("the run entry records status unknown", runs[-1]["status"] == "unknown")
        ok("the run entry records WHY", bool(runs[-1].get("status_reason")))

    with tempfile.TemporaryDirectory() as tmp:
        run_cli(tmp, "--job", "demo", "--trigger", "schedule",
                "--version-status", "success", "--stats-status", "success")
        job = read(tmp, "automation-status.json")["jobs"]["demo"]
        ok("two observed successes DO increment success_count",
           job["success_count"] == 1)
        ok("...and set last_success", job["last_success"] is not None)

    with tempfile.TemporaryDirectory() as tmp:
        run_cli(tmp, "--job", "demo", "--trigger", "schedule",
                "--version-status", "failure", "--stats-status", "success")
        job = read(tmp, "automation-status.json")["jobs"]["demo"]
        ok("an observed failure increments failure_count", job["failure_count"] == 1)
        ok("...and never success_count", job["success_count"] == 0)

    # Totals must reconcile, or /monitoring/ divides by a number that means
    # something different from the numerator.
    with tempfile.TemporaryDirectory() as tmp:
        run_cli(tmp, "--job", "j", "--trigger", "t", "--a-status", "success")
        run_cli(tmp, "--job", "j", "--trigger", "t", "--a-status", "failure")
        run_cli(tmp, "--job", "j", "--trigger", "t", "--a-status", "skipped")
        run_cli(tmp, "--job", "j", "--trigger", "t", "--a-status", "")
        job = read(tmp, "automation-status.json")["jobs"]["j"]
        total = (job["success_count"] + job["failure_count"]
                 + job["partial_count"] + job["unknown_count"])
        ok("total_runs reconciles with the sum of the four counters",
           total == job["total_runs"] == 4,
           "total_runs=%r sum=%r" % (job["total_runs"], total))


# ---------------------------------------------------------------------------
# 3. Back-compat: a status file written by the OLD script has no partial_count
#    or unknown_count. Those totals are real history and must not be reset.
# ---------------------------------------------------------------------------
def test_legacy_entry_preserved():
    print("\nLegacy status entries")

    with tempfile.TemporaryDirectory() as tmp:
        legacy = {
            "last_updated": "2026-08-24T18:11:32.707541Z",
            "jobs": {
                "auto-update-data": {
                    "last_run": "2026-08-24T18:11:32.707541Z",
                    "last_success": "2026-08-24T18:11:32.707541Z",
                    "last_failure": None,
                    "total_runs": 1201,
                    "success_count": 1201,
                    "failure_count": 0,
                }
            },
            "system_info": {"automation_version": "1.0.0"},
        }
        (Path(tmp) / "automation-status.json").write_text(
            json.dumps(legacy), encoding="utf-8")

        run_cli(tmp, "--job", "auto-update-data", "--trigger", "schedule",
                "--version-status", "", "--stats-status", "")
        job = read(tmp, "automation-status.json")["jobs"]["auto-update-data"]
        ok("legacy total_runs is carried forward, not reset",
           job["total_runs"] == 1202, "total_runs=%r" % job["total_runs"])
        ok("legacy success_count is untouched by an unknown run",
           job["success_count"] == 1201, "success_count=%r" % job["success_count"])
        ok("the new counter starts at 1", job["unknown_count"] == 1)
        ok("unrelated top-level keys survive",
           read(tmp, "automation-status.json").get("system_info") is not None)


# ---------------------------------------------------------------------------
# 4. FORCED FAILURE: a corrupt existing log must never be overwritten.
# ---------------------------------------------------------------------------
def test_refuses_corrupt_log():
    print("\nForced failure: corrupt existing files")

    with tempfile.TemporaryDirectory() as tmp:
        runs_path = Path(tmp) / "automation-runs.json"
        corrupt = "NOT JSON {{{"
        runs_path.write_text(corrupt, encoding="utf-8")

        proc = run_cli(tmp, "--job", "demo", "--trigger", "schedule",
                       "--version-status", "success")
        ok("a corrupt run log exits 4, not 0",
           proc.returncode == 4, "rc=%d" % proc.returncode)
        ok("...and the corrupt file is left EXACTLY as found (no data destroyed)",
           runs_path.read_text(encoding="utf-8") == corrupt)
        ok("...and no status file is invented",
           not (Path(tmp) / "automation-status.json").exists())
        ok("...and it says REFUSED on stderr",
           "REFUSED" in proc.stderr, proc.stderr[-200:])

    # The status file is read SECOND. If the script wrote the run log before
    # reading it, a corrupt status file would leave a half-applied record.
    with tempfile.TemporaryDirectory() as tmp:
        runs_path = Path(tmp) / "automation-runs.json"
        good_runs = json.dumps([{"job": "demo", "status": "success"}])
        runs_path.write_text(good_runs, encoding="utf-8")
        (Path(tmp) / "automation-status.json").write_text("{{{", encoding="utf-8")

        proc = run_cli(tmp, "--job", "demo", "--trigger", "schedule",
                       "--version-status", "success")
        ok("a corrupt status file exits 4", proc.returncode == 4,
           "rc=%d" % proc.returncode)
        ok("...and the GOOD run log is byte-identical afterwards",
           runs_path.read_text(encoding="utf-8") == good_runs)

    # A JSON file of the wrong SHAPE parses fine and is still not a run history.
    with tempfile.TemporaryDirectory() as tmp:
        runs_path = Path(tmp) / "automation-runs.json"
        runs_path.write_text('{"not": "a list"}', encoding="utf-8")
        proc = run_cli(tmp, "--job", "demo", "--trigger", "schedule",
                       "--version-status", "success")
        ok("a run log that parses but is not a list exits 4",
           proc.returncode == 4, "rc=%d" % proc.returncode)


# ---------------------------------------------------------------------------
# 5. FORCED FAILURE: a failed WRITE must not be reported as a recorded run.
#    Forced in-process by shadowing the module's `open` for write mode only --
#    a module global resolves before the builtin, so the substitution is total
#    and contained to this interpreter.
# ---------------------------------------------------------------------------
def test_refuses_failed_write(mod):
    print("\nForced failure: unwritable destination")

    real_open = open

    def failing_open(file, mode="r", *a, **kw):
        if "w" in mode:
            raise OSError(28, "simulated: no space left on device")
        return real_open(file, mode, *a, **kw)

    with tempfile.TemporaryDirectory() as tmp:
        runs_path = Path(tmp) / "automation-runs.json"
        good_runs = json.dumps([{"job": "demo", "status": "success"}])
        runs_path.write_text(good_runs, encoding="utf-8")

        mod.open = failing_open
        try:
            argv = sys.argv
            sys.argv = ["log-automation-run.py", "--job", "demo",
                        "--trigger", "schedule", "--version-status", "success",
                        "--monitoring-dir", tmp]
            try:
                rc = mod.main()
            finally:
                sys.argv = argv
        finally:
            del mod.open

        ok("a failed write exits 3, not 0", rc == 3, "rc=%r" % rc)
        ok("...and the previous good log survives untouched",
           runs_path.read_text(encoding="utf-8") == good_runs)


# ---------------------------------------------------------------------------
# 6. NEGATIVE CONTROL: the OLD rule, re-run on the same inputs, must disagree.
#    Without this the file above could be green because the defect is fixed or
#    because the assertions never discriminated.
# ---------------------------------------------------------------------------
def old_rule(details):
    """The pre-2026-08-25 derivation, reproduced verbatim from git history."""
    status = "success"
    if any(v == "failure" for v in details.values()):
        status = "failure"
    elif any(v == "skipped" for v in details.values()):
        status = "partial"
    return status


def test_negative_control(mod):
    print("\nNegative control: the old rule must disagree")

    unearned = [
        ("no details at all", {}),
        ("two empty outcomes", {"version-status": "", "stats-status": ""}),
        ("one empty outcome", {"version-status": "success", "stats-status": ""}),
        ("a cancelled step", {"version-status": "cancelled"}),
        ("a non-outcome key only", {"new-week-id": "2026_W32"}),
    ]
    for name, details in unearned:
        old = old_rule(details)
        new, _ = mod.derive_status(details)
        ok("old rule said success for %s" % name, old == "success",
           "old=%r" % old)
        ok("...and the new rule does not", new != "success", "new=%r" % new)

    # ...but the rules must still AGREE wherever the old one was right, or this
    # is not a fix, it is a different bug.
    for name, details, expected in [
        ("real success", {"a-status": "success"}, "success"),
        ("real failure", {"a-status": "failure"}, "failure"),
        ("real skip", {"a-status": "success", "b-status": "skipped"}, "partial"),
    ]:
        old = old_rule(details)
        new, _ = mod.derive_status(details)
        ok("old and new agree on %s" % name, old == new == expected,
           "old=%r new=%r" % (old, new))


# ---------------------------------------------------------------------------
# 7. This test must never write into the repository's real monitoring data.
# ---------------------------------------------------------------------------
def test_leaves_repo_alone(before):
    print("\nThe test itself")
    after = snapshot_repo_monitoring()
    ok("public/monitoring/data/ is byte-identical before and after this run",
       before == after,
       "the test wrote into the real monitoring directory")


def snapshot_repo_monitoring():
    if not REPO_MONITORING.exists():
        return None
    out = {}
    for p in sorted(REPO_MONITORING.iterdir()):
        if p.is_file():
            out[p.name] = p.read_bytes()
    return out


def main():
    print("Forced-failure test: log-automation-run.py")
    print("=" * 60)

    before = snapshot_repo_monitoring()
    mod = load_module()

    test_status_rules(mod)
    test_counters()
    test_legacy_entry_preserved()
    test_refuses_corrupt_log()
    test_refuses_failed_write(mod)
    test_negative_control(mod)
    test_leaves_repo_alone(before)

    print("\n" + "=" * 60)
    print("%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
