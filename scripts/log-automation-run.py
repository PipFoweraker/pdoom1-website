#!/usr/bin/env python3
"""
Automation Run Logger for Admin Monitoring Dashboard

This script logs GitHub Actions automation runs to make them visible
in the /monitoring/ admin dashboard. This is separate from the game
dashboard and is for infrastructure monitoring only.

Usage:
    python scripts/log-automation-run.py --job <job-name> --trigger <trigger> [--<key> <value> ...]
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class AutomationLogger:
    """Logs automation run data for the admin monitoring dashboard."""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.monitoring_dir = self.base_dir / "public" / "monitoring" / "data"
        self.monitoring_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.monitoring_dir / "automation-runs.json"
        self.status_file = self.monitoring_dir / "automation-status.json"

    def load_runs(self) -> List[Dict[str, Any]]:
        """Load existing automation run history."""
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load existing runs: {e}")
        return []

    def save_runs(self, runs: List[Dict[str, Any]]):
        """Save automation run history."""
        # Keep only last 100 runs
        runs = runs[-100:]

        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(runs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save runs: {e}")

    def load_status(self) -> Dict[str, Any]:
        """Load current automation status."""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load status: {e}")

        return {
            "last_updated": None,
            "jobs": {}
        }

    def save_status(self, status: Dict[str, Any]):
        """Save current automation status."""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save status: {e}")

    def log_run(self, job_name: str, trigger: str, details: Dict[str, str]):
        """Log an automation run."""
        timestamp = datetime.utcnow().isoformat() + 'Z'

        # Determine overall status from details
        status = "success"
        if any(v == "failure" for v in details.values()):
            status = "failure"
        elif any(v == "skipped" for v in details.values()):
            status = "partial"

        # Create run entry
        run_entry = {
            "job": job_name,
            "trigger": trigger,
            "timestamp": timestamp,
            "status": status,
            "details": details
        }

        # Add to run history
        runs = self.load_runs()
        runs.append(run_entry)
        self.save_runs(runs)

        # Update status
        status_data = self.load_status()
        status_data["last_updated"] = timestamp

        if job_name not in status_data["jobs"]:
            status_data["jobs"][job_name] = {
                "last_run": None,
                "last_success": None,
                "last_failure": None,
                "total_runs": 0,
                "success_count": 0,
                "failure_count": 0
            }

        job_status = status_data["jobs"][job_name]
        job_status["last_run"] = timestamp
        job_status["total_runs"] += 1

        if status == "success":
            job_status["last_success"] = timestamp
            job_status["success_count"] += 1
        elif status == "failure":
            job_status["last_failure"] = timestamp
            job_status["failure_count"] += 1

        self.save_status(status_data)

        print(f"✓ Logged automation run: {job_name} ({status})")
        print(f"  Timestamp: {timestamp}")
        print(f"  Trigger: {trigger}")
        print(f"  Details: {details}")


def main():
    parser = argparse.ArgumentParser(
        description='Log automation run for monitoring dashboard'
    )
    parser.add_argument('--job', required=True, help='Job name')
    parser.add_argument('--trigger', required=True, help='Trigger type (schedule, workflow_dispatch, etc)')

    # All other arguments are treated as status details
    args, unknown = parser.parse_known_args()

    # Parse remaining args as key-value pairs
    details = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith('--'):
            key = unknown[i][2:]  # Remove --
            if i + 1 < len(unknown) and not unknown[i + 1].startswith('--'):
                value = unknown[i + 1]
                details[key] = value
                i += 2
            else:
                details[key] = "true"
                i += 1
        else:
            i += 1

    logger = AutomationLogger()
    logger.log_run(args.job, args.trigger, details)


if __name__ == '__main__':
    main()
