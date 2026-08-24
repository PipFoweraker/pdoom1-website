#!/usr/bin/env python3
"""
Automation Run Logger for Admin Monitoring Dashboard

This script logs GitHub Actions automation runs to make them visible
in the /monitoring/ admin dashboard. This is separate from the game
dashboard and is for infrastructure monitoring only.

Usage:
    python scripts/log-automation-run.py --job <job-name> --trigger <trigger> [--<key>-status <outcome> ...]

WHY THE STATUS RULES LOOK LIKE THIS
-----------------------------------
Until 2026-08-25 this script opened with `status = "success"` and downgraded only
if some detail value read "failure" or "skipped". So a run with NO observations
at all logged `success` and incremented `success_count`. Measured on a sandbox
copy before the change:

    log-automation-run.py --job demo --trigger schedule
        -> "Logged automation run: demo (success)", success_count 1, from {} details

    log-automation-run.py --job demo2 --trigger schedule
        --version-status "" --stats-status ""
        -> "success" again, from two empty strings

That second shape is not hypothetical. Every caller interpolates
`${{ steps.<id>.outcome }}`, which expands to the EMPTY STRING when the step id
is renamed, is skipped by an `if:`, or never ran. The workflow keeps working, the
logger keeps saying success, and /monitoring/ publishes the result. On
2026-08-24 that page showed auto-update-data at 1201/1201 = 100%.

The rule now is CLAUDE.md's: "Absence of a marker is never a clean bill of
health." Zero observations renders as UNKNOWN, which increments no success
counter. Only outcomes this script recognises, all of them saying "success", can
produce a success.

WHY IT NOW EXITS NON-ZERO
-------------------------
Two silent-failure paths were also measured:
  * a failed WRITE printed "Warning: Could not save runs" and exited 0, so a
    caller could not tell a recorded run from an unrecorded one;
  * a CORRUPT automation-runs.json was caught, returned as [], and then
    OVERWRITTEN with a single entry -- the run counter silently restarted and up
    to 100 prior records were destroyed.
Both now refuse: nothing is written and the exit code says so. CLAUDE.md,
"Fallback literals are the dangerous ones ... Prefer failing loudly, or
preserving the last known-good value, over substituting a literal."

Exit codes:
    0  the run was recorded (whatever status it was recorded WITH)
    2  bad invocation
    3  could not write -- nothing was recorded
    4  existing log/status file is unreadable -- refused to overwrite it
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import sys

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# A detail key ending in this suffix carries a GitHub step OUTCOME and is the
# only kind of detail that may influence the recorded status. Every real caller
# uses it (--version-status, --stats-status, --sync-all-status, --verify-status,
# --archive-status, --new-week-status). Keys that are not outcomes must not be
# read as outcomes -- weekly-league-reset.yml passes --new-week-id, which is a
# week identifier, and the previous code would have read "2026_W32" as a status.
OUTCOME_SUFFIX = "-status"

# The complete set of values GitHub Actions can put in `steps.<id>.outcome`.
# ANYTHING ELSE -- including the empty string -- is an observation we cannot
# interpret, and is therefore not evidence of success.
KNOWN_OUTCOMES = frozenset({"success", "failure", "cancelled", "skipped"})

STATUS_SUCCESS = "success"
STATUS_FAILURE = "failure"
STATUS_PARTIAL = "partial"
STATUS_UNKNOWN = "unknown"

# Counter key per status. `partial` and `unknown` are counted too, so total_runs
# reconciles against the sum instead of quietly exceeding it.
COUNTER_KEYS = {
    STATUS_SUCCESS: "success_count",
    STATUS_FAILURE: "failure_count",
    STATUS_PARTIAL: "partial_count",
    STATUS_UNKNOWN: "unknown_count",
}


class LogUnreadableError(Exception):
    """An existing monitoring file could not be parsed, so it must not be overwritten."""


class LogUnwritableError(Exception):
    """A monitoring file could not be written, so the run was NOT recorded."""


def derive_status(details: Dict[str, str]) -> Tuple[str, str]:
    """Derive the recorded status from the outcome-bearing details.

    Returns (status, reason). The reason is printed and stored, because a bare
    "unknown" on a dashboard sends the reader to the code to find out why.

    Precedence, strongest evidence first:
      failure  -- an outcome of "failure" was actually OBSERVED. Decisive even
                  alongside uninterpretable outcomes: a seen failure is a fact.
      unknown  -- no outcome keys at all, or any outcome value this script
                  cannot interpret (empty string, typo), or "cancelled" -- a
                  cancelled step never ran to completion, so whether it would
                  have succeeded is genuinely unobserved.
      partial  -- everything readable, but something was skipped.
      success  -- at least one outcome, and every one of them says "success".
    """
    observations = {
        key: value for key, value in details.items() if key.endswith(OUTCOME_SUFFIX)
    }

    if not observations:
        return (
            STATUS_UNKNOWN,
            "no %s detail was supplied, so nothing about this run was observed"
            % OUTCOME_SUFFIX,
        )

    failed = sorted(k for k, v in observations.items() if v == "failure")
    if failed:
        return STATUS_FAILURE, "observed failure in: %s" % ", ".join(failed)

    uninterpretable = sorted(
        "%s=%r" % (k, v) for k, v in observations.items() if v not in KNOWN_OUTCOMES
    )
    if uninterpretable:
        return (
            STATUS_UNKNOWN,
            "outcome not interpretable (an empty value means the step id did not "
            "resolve): %s" % ", ".join(uninterpretable),
        )

    cancelled = sorted(k for k, v in observations.items() if v == "cancelled")
    if cancelled:
        return (
            STATUS_UNKNOWN,
            "cancelled, so the result was never observed: %s" % ", ".join(cancelled),
        )

    skipped = sorted(k for k, v in observations.items() if v == "skipped")
    if skipped:
        return STATUS_PARTIAL, "skipped: %s" % ", ".join(skipped)

    return (
        STATUS_SUCCESS,
        "all %d observed outcomes reported success" % len(observations),
    )


class AutomationLogger:
    """Logs automation run data for the admin monitoring dashboard."""

    def __init__(self, monitoring_dir: Optional[Path] = None):
        self.base_dir = Path(__file__).parent.parent
        if monitoring_dir is None:
            monitoring_dir = self.base_dir / "public" / "monitoring" / "data"
        self.monitoring_dir = Path(monitoring_dir)
        self.monitoring_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.monitoring_dir / "automation-runs.json"
        self.status_file = self.monitoring_dir / "automation-status.json"

    def load_runs(self) -> List[Dict[str, Any]]:
        """Load existing automation run history.

        Refuses on a corrupt file. Returning [] here is what silently restarted
        the run counter and discarded up to 100 records on the next save.
        """
        if not self.log_file.exists():
            return []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except Exception as e:
            raise LogUnreadableError(
                "%s could not be parsed (%s). Refusing to overwrite it -- the "
                "existing run history would be destroyed. Repair or move the "
                "file, then re-run." % (self.log_file, e)
            )
        if not isinstance(loaded, list):
            raise LogUnreadableError(
                "%s parsed as %s, expected a list of run entries. Refusing to "
                "overwrite it." % (self.log_file, type(loaded).__name__)
            )
        return loaded

    def save_runs(self, runs: List[Dict[str, Any]]):
        """Save automation run history."""
        # Keep only last 100 runs
        runs = runs[-100:]

        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(runs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise LogUnwritableError("could not write %s: %s" % (self.log_file, e))

    def load_status(self) -> Dict[str, Any]:
        """Load current automation status. Refuses on a corrupt file, as above."""
        if not self.status_file.exists():
            return {"last_updated": None, "jobs": {}}
        try:
            with open(self.status_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except Exception as e:
            raise LogUnreadableError(
                "%s could not be parsed (%s). Refusing to overwrite it -- every "
                "job's run totals would reset to zero. Repair or move the file, "
                "then re-run." % (self.status_file, e)
            )
        if not isinstance(loaded, dict):
            raise LogUnreadableError(
                "%s parsed as %s, expected an object. Refusing to overwrite it."
                % (self.status_file, type(loaded).__name__)
            )
        loaded.setdefault("last_updated", None)
        loaded.setdefault("jobs", {})
        if not isinstance(loaded["jobs"], dict):
            raise LogUnreadableError(
                "%s has a non-object 'jobs'. Refusing to overwrite it."
                % self.status_file
            )
        return loaded

    def save_status(self, status: Dict[str, Any]):
        """Save current automation status."""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise LogUnwritableError("could not write %s: %s" % (self.status_file, e))

    def log_run(self, job_name: str, trigger: str, details: Dict[str, str]) -> str:
        """Log an automation run. Returns the status it was recorded with."""
        timestamp = datetime.utcnow().isoformat() + 'Z'

        status, reason = derive_status(details)

        # Read BOTH files before writing EITHER. If the status file is corrupt we
        # must not already have rewritten the run log -- a half-applied record is
        # a third state nobody reading /monitoring/ could diagnose.
        runs = self.load_runs()
        status_data = self.load_status()

        run_entry = {
            "job": job_name,
            "trigger": trigger,
            "timestamp": timestamp,
            "status": status,
            "status_reason": reason,
            "details": details
        }
        runs.append(run_entry)

        status_data["last_updated"] = timestamp

        job_status = status_data["jobs"].setdefault(job_name, {})
        # setdefault per key, not a whole-dict default: entries written by older
        # versions of this script have no partial_count/unknown_count and must
        # keep their existing totals rather than being reset to a fresh block.
        job_status.setdefault("last_run", None)
        job_status.setdefault("last_success", None)
        job_status.setdefault("last_failure", None)
        for key in ("total_runs",) + tuple(COUNTER_KEYS.values()):
            job_status.setdefault(key, 0)

        job_status["last_run"] = timestamp
        job_status["total_runs"] += 1
        job_status[COUNTER_KEYS[status]] += 1

        # last_success / last_failure are CLAIMS about the world, so only an
        # observed success or an observed failure may move them. unknown and
        # partial move neither -- that is the whole point of the two states.
        if status == STATUS_SUCCESS:
            job_status["last_success"] = timestamp
        elif status == STATUS_FAILURE:
            job_status["last_failure"] = timestamp

        self.save_runs(runs)
        self.save_status(status_data)

        marker = "!" if status in (STATUS_FAILURE, STATUS_UNKNOWN) else "-"
        print("%s Logged automation run: %s (%s)" % (marker, job_name, status))
        print("  Why: %s" % reason)
        print("  Timestamp: %s" % timestamp)
        print("  Trigger: %s" % trigger)
        print("  Details: %s" % details)
        if status == STATUS_UNKNOWN:
            # Visible in an Actions log even when the step is continue-on-error.
            print("::warning::automation run for %r recorded as UNKNOWN: %s"
                  % (job_name, reason))
        return status


def parse_details(unknown: List[str]) -> Dict[str, str]:
    """Parse the trailing --key value pairs into a details dict."""
    details: Dict[str, str] = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith('--'):
            key = unknown[i][2:]  # Remove --
            if i + 1 < len(unknown) and not unknown[i + 1].startswith('--'):
                details[key] = unknown[i + 1]
                i += 2
            else:
                # A bare flag. Recorded as "true", which is deliberately NOT a
                # member of KNOWN_OUTCOMES: if it lands on a -status key, the run
                # is unknown rather than quietly successful.
                details[key] = "true"
                i += 1
        else:
            i += 1
    return details


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Log automation run for monitoring dashboard'
    )
    parser.add_argument('--job', required=True, help='Job name')
    parser.add_argument('--trigger', required=True, help='Trigger type (schedule, workflow_dispatch, etc)')
    parser.add_argument('--monitoring-dir', default=None,
                        help='Override the output directory (tests only; defaults '
                             'to public/monitoring/data)')

    # All other arguments are treated as status details
    args, unknown = parser.parse_known_args()

    details = parse_details(unknown)

    try:
        logger = AutomationLogger(monitoring_dir=args.monitoring_dir)
        logger.log_run(args.job, args.trigger, details)
    except LogUnreadableError as e:
        print("REFUSED: %s" % e, file=sys.stderr)
        print("::error::automation log unreadable, run NOT recorded", file=sys.stderr)
        return 4
    except LogUnwritableError as e:
        print("REFUSED: %s" % e, file=sys.stderr)
        print("::error::automation log unwritable, run NOT recorded", file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
