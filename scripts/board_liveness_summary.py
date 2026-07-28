#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emit board-liveness.json's headline numbers as shell-sourceable assignments.

Exists so board-liveness.yml does not have to nest a heredoc inside a command
substitution to get three integers out of a JSON file. That construction is a
documented time sink in this repo (CLAUDE.md, "Encoding gremlin"), and it fails in
ways that look like a passing workflow.

Values are quoted and the verdict is restricted to a safe character set, because the
output is `.`-sourced by the workflow -- anything from a data file that reaches a shell
must not be able to become a command.

Usage:  python scripts/board_liveness_summary.py > summary.env && . ./summary.env
"""

import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REC = Path(__file__).resolve().parents[1] / "public" / "leaderboard" / "data" / "board-liveness.json"
SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def main():
    try:
        d = json.loads(REC.read_text(encoding="utf-8"))
    except Exception as e:
        # Never emit a plausible-looking zero for a file we could not read: the workflow
        # would report "0 new orphans" as though that were an observation.
        print("verdict=unreadable")
        print("newn=-1")
        print("archn=-1")
        print("# %s" % str(e).replace("\n", " ")[:160])
        return 0

    verdict = SAFE.sub("_", str(d.get("verdict", "unknown")))[:64] or "unknown"
    newn = int((d.get("new_orphans") or {}).get("entries_total") or 0)
    archn = int((d.get("archived_orphans") or {}).get("entries_total") or 0)
    print("verdict=%s" % verdict)
    print("newn=%d" % newn)
    print("archn=%d" % archn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
