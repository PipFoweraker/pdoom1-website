#!/usr/bin/env python3
"""Force the states stamp-league-epoch.py's defect texts claim to describe.

Why this exists
---------------
`stamp-league-epoch.py`'s docstring promises that `observed_defects` records "the
specific, individually verified ways THAT file misdescribes reality ... Derived
per-file, never asserted blanket-wise."

The `empty-shell` defect broke that promise. Its trigger was the purely structural
`if not entries`, but its text asserted a causal fact the trigger cannot verify:
*"No shipped client ever submitted to this board key, so the week ran with no
participants."*

On 2026-08-07 that produced a demonstrable falsehood. `current.json` for week
2026_W33 -- seven hours old, six days to run, keyed to the BLESSED seed
`weekly-2026-w31` -- carried the flag, while `board-liveness.json` recorded the live
board under that exact key holding 6 entries from 5 players. Both halves of the
sentence were false: clients had submitted, and the week had not "ran".

Nothing rendered it that day, because `public/league/archive.html` reads archive
records rather than `current.json`. It would have become visitor-facing at the next
rollover, when W33 archives.

CLAUDE.md: "A guard seen only in its passing state has not been shown to work." So
each assertion below FORCES the state rather than observing the committed tree.

Run:  python scripts/test-stamp-league-epoch.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = Path(__file__).parent
_spec = importlib.util.spec_from_file_location(
    "stamp_league_epoch", _HERE / "stamp-league-epoch.py")
sle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sle)

FAILURES = []


def check(label, condition, detail=""):
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}{(' -- ' + detail) if detail else ''}")
        FAILURES.append(label)


def defects_for(tmp, name, record):
    """Write `record` to a real file and return its observed-defect list."""
    p = Path(tmp) / name
    p.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return sle.observed_defects(record, p)


BLESSED_RUNNING = {
    "meta": {"week_id": "2026_W33", "generated": "2026-08-06T14:47:00Z"},
    "week_info": {
        "start_timestamp": "2026-08-07T00:00:00+10:00",
        "end_timestamp": "2026-08-13T23:59:59+10:00",
    },
    "seed": "weekly-2026-w31",
    "entries": [],
}

BLESSED_ARCHIVED = dict(BLESSED_RUNNING, archive_status="completed")

MINTED_ARCHIVED = dict(
    BLESSED_ARCHIVED, seed="weekly_2026_W32_5685561a")


def main():
    print("stamp-league-epoch: forced defect states\n")
    with tempfile.TemporaryDirectory() as tmp:

        print("A running week is not an empty shell")
        d = defects_for(tmp, "current.json", BLESSED_RUNNING)
        check("running week with 0 entries does NOT get empty-shell",
              "empty-shell" not in d, f"got {d}")

        print("\nA completed week with no entries still is one")
        d = defects_for(tmp, "2026_W33_league.json", BLESSED_ARCHIVED)
        check("archived week with 0 entries DOES get empty-shell",
              "empty-shell" in d, f"got {d}")

        print("\nThe text says only what the trigger demonstrates")
        text = sle.DEFECT_TEXT["empty-shell"]
        for claim in ("No shipped client ever submitted",
                      "the week ran with no participants"):
            check(f"empty-shell text no longer asserts {claim!r}",
                  claim not in text)
        check("empty-shell text scopes itself to THIS FILE",
              "THIS FILE" in text, text)

        print("\nThe causal claim survives where it IS demonstrable")
        d = defects_for(tmp, "2026_W32_league.json", MINTED_ARCHIVED)
        check("website-minted seed still raises unblessed-seed",
              "unblessed-seed" in d, f"got {d}")
        check("unblessed-seed is where 'No client ever POSTed' lives",
              "No client ever POSTed" in sle.DEFECT_TEXT["unblessed-seed"])
        d = defects_for(tmp, "2026_W33_league.json", BLESSED_ARCHIVED)
        check("blessed seed does NOT raise unblessed-seed",
              "unblessed-seed" not in d, f"got {d}")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} assertion(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("All assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
