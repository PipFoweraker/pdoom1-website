#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Derive the deterministic league seed for a month (ADR-0016 monthly cadence).

    python tools/derive_league_seed.py 2026-07        # -> league_2026-07_7d6ced29 (L2)
    python tools/derive_league_seed.py 2026-08 L2

Deriving is not blessing. The output is a PROPOSAL until Pip signs off and it is
recorded in docs/LEAGUE_SEED_LEDGER.md. See that file for the rule.
"""
import sys
import hashlib
import re

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def derive(month: str, ladder: str = "L2") -> str:
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError(f"month must be YYYY-MM, got {month!r}")
    base = f"pdoom1_league_{month}_{ladder}"
    return f"league_{month}_{hashlib.sha256(base.encode()).hexdigest()[:8]}"


def main(argv):
    if not (2 <= len(argv) <= 3):
        print(__doc__)
        return 2
    month = argv[1]
    ladder = argv[2] if len(argv) == 3 else "L2"
    seed = derive(month, ladder)
    print(seed)
    print(f"  board file: board_{seed}__{ladder}.json", file=sys.stderr)
    print("  (proposal until blessed + recorded in docs/LEAGUE_SEED_LEDGER.md)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
