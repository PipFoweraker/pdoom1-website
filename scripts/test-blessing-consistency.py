#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-state tests for scripts/check-blessing-consistency.py.

Every case builds a whole fixture tree in a temp dir and runs the real script
against it with --root. Nothing reads or writes the repo's own artefacts, so the
tests keep passing after Pip fills the ledger rows -- a test that only passes
while the repo is broken is worse than no test.

THE CASE THAT MATTERS MOST is test 2: the 2026-08-09 defect reproduced with its
real values. ladder-epochs.json says blessed, the ledger row says NOT YET BLESSED,
and weekly/current.json claims blessed:true while citing the ledger. That is the
state that made this seat tell Pip his epoch was unblessed when it was not.

Run:  python scripts/test-blessing-consistency.py     (exit 0 = pass)
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        try:
            if _s is sys.stdout:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-blessing-consistency.py"
failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


LEDGER_HEAD = (
    "# League seed ledger\n\n"
    "| epoch | seed | ladder | board file | blessed (UTC) | by | notes |\n"
    "|---|---|---|---|---|---|---|\n"
)


def build(tmp, epoch, ledger_rows, ladder, weekly, published):
    r = Path(tmp)
    (r / "public" / "data").mkdir(parents=True, exist_ok=True)
    (r / "public" / "leaderboard" / "data" / "weekly").mkdir(parents=True, exist_ok=True)
    (r / "docs").mkdir(parents=True, exist_ok=True)
    (r / "public" / "data" / "ladder-epochs.json").write_text(
        json.dumps(ladder), encoding="utf-8")
    (r / "public" / "leaderboard" / "data" / "weekly" / "current.json").write_text(
        json.dumps(weekly), encoding="utf-8")
    (r / "public" / "leaderboard" / "data" / "published-board.json").write_text(
        json.dumps(published), encoding="utf-8")
    (r / "public" / "leaderboard" / "data" / "board-probe-targets.json").write_text(
        json.dumps({"current_ladder_epoch": {"value": epoch, "source": "fixture"}}),
        encoding="utf-8")
    (r / "docs" / "LEAGUE_SEED_LEDGER.md").write_text(
        LEDGER_HEAD + "".join(ledger_rows), encoding="utf-8")
    return r


def run(root):
    p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def blessed_row(epoch, seed, date="2026-08-08", by="Pip"):
    return ("| %s | `%s` | %s | `board_%s__%s.json` | %s | %s | notes |\n"
            % (epoch, seed, epoch, seed, epoch, date, by))


def unfilled_row(epoch):
    return ("| **%s** | NOT YET BLESSED | %s | `board_<seed>__%s.json` | "
            "- | - | PENDING -- a human must fill this row. |\n" % (epoch, epoch, epoch))


def ladder_of(epoch, seed, status="blessed", epochs=None):
    return {"regularised_from": {"seed": seed, "seed_status": status,
                                 "ladder_version": epoch},
            "epochs": epochs if epochs is not None
                      else [{"ladder_version": epoch, "status": "current", "seed": seed}]}


def weekly_of(epoch, seed, blessed):
    return {"seed": seed, "seed_provenance": {"blessed": blessed},
            "meta": {"ladder_version": epoch}}


def pub_of(epoch, seed):
    # blessed:false is CORRECT here and every fixture keeps it that way.
    return {"seed": seed, "ladder_epoch": epoch,
            "seed_provenance": {"blessed": False}}


tmp = Path(tempfile.mkdtemp())

print("\n1. All four agree -> exit 0")
r = build(tmp / "a", "L4", [blessed_row("L4", "weekly-2026-w32")],
          ladder_of("L4", "weekly-2026-w32"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
code, out = run(r)
check(code == 0, "exit 0 when they agree (got %s)" % code)
check("OK:" in out, "says so plainly")
check("blessed:false is CORRECT" in out,
      "states that the observation's blessed:false is correct, so nobody 'fixes' it")

print("\n2. THE 2026-08-09 DEFECT, real values: machine says blessed, document does not")
r = build(tmp / "b", "L3", [unfilled_row("L3")],
          ladder_of("L3", "weekly-2026-w31"),
          weekly_of("L3", "weekly-2026-w31", True),
          pub_of("L3", "weekly-2026-w31"))
code, out = run(r)
check(code == 1, "exit 1 (got %s)" % code)
check("BLESSED-STATUS SPLIT" in out, "names the split explicitly")
check("the machine knew and the document lied" in out,
      "uses the words that make the failure recognisable next time")
check("cites the ledger as its authority while" in out,
      "catches weekly/current.json citing a document it contradicts")

print("\n3. A file that disagrees WITH ITSELF is caught")
r = build(tmp / "c", "L3", [blessed_row("L3", "weekly-2026-w31")],
          ladder_of("L3", "weekly-2026-w31",
                    epochs=[{"ladder_version": "L3", "status": "opening", "seed": None}]),
          weekly_of("L3", "weekly-2026-w31", True),
          pub_of("L3", "weekly-2026-w31"))
code, out = run(r)
check(code == 1, "exit 1 (got %s)" % code)
check(out.count("CONTRADICTS ITSELF") >= 2,
      "catches BOTH internal contradictions -- the seed and the status")

print("\n4. No ledger row at all for the current epoch")
r = build(tmp / "d", "L4", [blessed_row("L3", "weekly-2026-w31")],
          ladder_of("L4", "weekly-2026-w32"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
code, out = run(r)
check(code == 1, "exit 1 (got %s)" % code)
check("NO ROW for L4" in out, "says which epoch is unrecorded")

print("\n5. Seed disagreement between the human record and the machine field")
r = build(tmp / "e", "L4", [blessed_row("L4", "weekly-2026-w32")],
          ladder_of("L4", "weekly-2026-w99"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
code, out = run(r)
check(code == 1, "exit 1 (got %s)" % code)
check("SEED DISAGREEMENT" in out, "names it and lists each source's value")

print("\n6. published-board.json's blessed:false is NEVER counted as disagreement")
r = build(tmp / "f", "L4", [blessed_row("L4", "weekly-2026-w32")],
          ladder_of("L4", "weekly-2026-w32"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
code, out = run(r)
check(code == 0,
      "an observation that correctly records blessed:false does not fail the check")

print("\n7. A missing artefact is UNKNOWN, never agreement")
r = build(tmp / "g", "L4", [blessed_row("L4", "weekly-2026-w32")],
          ladder_of("L4", "weekly-2026-w32"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
(r / "public" / "data" / "ladder-epochs.json").unlink()
code, out = run(r)
check(code == 2, "exit 2, not 0 and not 1 (got %s)" % code)
check("never agreement" in out, "says absence is not agreement")

print("\n8. No declared epoch -> cannot tell, and it is not a disagreement")
r = build(tmp / "h", None, [blessed_row("L4", "weekly-2026-w32")],
          ladder_of("L4", "weekly-2026-w32"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
code, out = run(r)
check(code == 2, "exit 2 (got %s)" % code)
check("no current epoch" in out, "explains there is nothing to compare about")

print("\n10. THE SWEEP BUG: an empty seed cell must not adopt a backtick from the notes")
# 2026-08-11 sweep, probe 2. This row's seed cell is EMPTY and its NOTES carry a
# backticked documentation path. The old parser took "the first backticked value in
# the row that is not a filename" and would present docs/THING.md as a league seed.
r = build(tmp / "j", "L9",
          ["| L9 |  | L9 |  | - | - | see `docs/THING.md` for the seed |\n"],
          ladder_of("L9", "weekly-2026-w99"),
          weekly_of("L9", "weekly-2026-w99", True),
          pub_of("L9", "weekly-2026-w99"))
code, out = run(r)
check("docs/THING.md" not in out,
      "a documentation path from the NOTES column is never read as a seed")
check(code == 1, "and the row still reports a disagreement rather than passing quietly")

print("\n11. A pipe inside a later cell must not move the seed")
# The row parser splits on '|', so a pipe in the notes shifts every later cell.
# The seed must still come from its own cell rather than from a shifted position.
r = build(tmp / "k", "L4",
          ["| L4 | `weekly-2026-w32` | L4 | `b.json` | 2026-08-08 | Pip | uses `a|b` |\n"],
          ladder_of("L4", "weekly-2026-w32"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
code, out = run(r)
check(code == 0,
      "a pipe in a notes cell shifts later cells but must not move the seed (got %s)" % code)

print("\n9. It never claims to be able to fix the ledger")
r = build(tmp / "i", "L4", [unfilled_row("L4")],
          ladder_of("L4", "weekly-2026-w32"),
          weekly_of("L4", "weekly-2026-w32", True),
          pub_of("L4", "weekly-2026-w32"))
code, out = run(r)
check("WILL NOT FILL A LEDGER ROW" in out,
      "says out loud that filling the row is a human's act, not a seat's")

shutil.rmtree(tmp, ignore_errors=True)

print()
if failures:
    print("%d FAILURE(S)" % len(failures))
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: agreement passes, every disagreement shape is caught, an observation's "
      "blessed:false is not a defect, and absence is unknown.")
