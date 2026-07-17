#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEPRECATED -- do not use. Kept as a no-op stub for CLI back-compat only.

This used to FABRICATE synthetic leaderboard data (15 fake entries stamped v0.4.1)
"until game export is implemented". That's the source of the stale fake data the site
was showing. It is superseded by:

  - scripts/ingest_scores.py   -- validates + publishes leaderboard.json (honest states)
  - the frozen v1 score contract (pdoom1 PR #679): the game POSTs to the PHP score API;
    the website is a READ-ONLY consumer (GET the API or read board_*.json). No fake data,
    no second score store.

This stub accepts the old flags and exits 0 so any lingering caller doesn't break, but
it NEVER writes data. Delete once no workflow/test references it.
"""

import argparse
import sys


def main():
    ap = argparse.ArgumentParser(description="DEPRECATED -- superseded by ingest_scores.py")
    ap.add_argument("--seed", type=str)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--all-seeds", action="store_true")
    ap.parse_args()
    print("export-leaderboard-bridge.py is DEPRECATED and no longer generates data.")
    print("Use scripts/ingest_scores.py (real, validated) instead. See docs/GAME_UPLIFT_PLAN.md.")
    sys.exit(0)


if __name__ == "__main__":
    main()
