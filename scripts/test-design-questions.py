#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-state tests for scripts/sync/sync-design-questions.py.

Builds a fake pdoom1 doc tree per case, so nothing depends on a local game
checkout and the tests keep passing when the real backlog changes.

THE CASES THAT MATTER are 2, 3 and 4. The first three attempts at this generator
all failed the same way -- **a boundary inferred from a delimiter that also appears
inside the content** -- and each failure looked fine in the output:

  * an em-dash in a TITLE was read as the title/status separator, silently
    dropping DQ-21, DQ-27 and DQ-31 from a table that still looked complete
  * an entry body ran on to the next DQ, swallowing an unrelated bullet, so a
    CLEAN question was refused for somebody else's marker
  * the summary strip ran in the wrong order, embedding the whole header in a
    summary that read plausibly

Run:  python scripts/test-design-questions.py     (exit 0 = pass)
"""

import io
import json
import re
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
SCRIPT = ROOT / "scripts" / "sync" / "sync-design-questions.py"
OUT = ROOT / "public" / "design-questions" / "index.html"
failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def make_game(tmp, backlog_lines, index_rows):
    g = Path(tmp) / "pdoom1" / "docs" / "game-design"
    g.mkdir(parents=True, exist_ok=True)
    (g / "WORKSHOP_2_BACKLOG.md").write_text("\n".join(backlog_lines), encoding="utf-8")
    head = ("# DQ index\n\n| DQ | Title | Status | Backlog line |\n|---|---|---|---|\n")
    rows = "".join("| %s | %s | %s | %d |\n" % r for r in index_rows)
    (g / "DQ_INDEX.md").write_text(head + rows, encoding="utf-8")
    return Path(tmp) / "pdoom1"


def run(game):
    p = subprocess.run([sys.executable, str(SCRIPT), "--game-repo", str(game)],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rendered():
    h = OUT.read_text(encoding="utf-8")
    rows = re.findall(r'<td class="k">(.*?)</td><td class="t">(.*?)</td>', h, re.S)
    out = {}
    for k, t in rows:
        m = re.search(r'<span class="d">(.*?)</span>', t, re.S)
        out[k] = re.sub("<[^>]+>", "", m.group(1)) if m else ""
    return h, out


backup = OUT.read_text(encoding="utf-8") if OUT.exists() else None
tmp = Path(tempfile.mkdtemp())

print("\n1. Happy path: every index row is rendered")
g = make_game(tmp / "a",
              ["- **DQ-1 · Alpha — RESOLVED** *(#1)* — first sentence here. more text.",
               "- **DQ-2 · Beta** *(#2)* — second sentence here. more."],
              [("DQ-1", "Alpha", "RESOLVED", 1), ("DQ-2", "Beta", "open", 2)])
code, out = run(g)
h, r = rendered()
check(code == 0, "exit 0 (got %s)" % code)
check(len(r) == 2, "both rows rendered (got %d)" % len(r))
check(r.get("DQ-1") == "first sentence here.", "summary is the first sentence only")

print("\n2. AN EM-DASH IN THE TITLE must not drop the row")
g = make_game(tmp / "b",
              ["- **DQ-27 · Mortality guarantee — where is it ratified?** *(#2)* — body one.",
               "- **DQ-28 · Plain** *(#3)* — body two."],
              [("DQ-27", "Mortality guarantee — where is it ratified?", "open", 1),
               ("DQ-28", "Plain", "open", 2)])
code, out = run(g)
h, r = rendered()
check("DQ-27" in r, "the em-dash-titled row SURVIVES -- this dropped 3 real DQs")
check(r.get("DQ-27") == "body one.", "and its summary is its own body")

print("\n3. AN UNRELATED BULLET AFTER AN ENTRY must not be absorbed")
g = make_game(tmp / "c",
              ["- **DQ-22 · Clean question** *(#4)* — a perfectly publishable sentence.",
               "- **Some other bullet TODO** *(#5)* — internal note that is not a DQ.",
               "- **DQ-23 · Another** *(#6)* — fine."],
              [("DQ-22", "Clean question", "open", 1), ("DQ-23", "Another", "open", 3)])
code, out = run(g)
h, r = rendered()
check("Full text withheld" not in h,
      "a CLEAN question is not refused for a marker in the bullet that follows it")
check(r.get("DQ-22") == "a perfectly publishable sentence.", "its summary is its own")

print("\n4. The summary must not contain the entry's own header")
g = make_game(tmp / "d",
              ["- **DQ-9 · Receivables — content** *(#7, ADR-0007)* — the real sentence."],
              [("DQ-9", "Receivables — content", "open", 1)])
code, out = run(g)
h, r = rendered()
s = r.get("DQ-9", "")
check("DQ-9" not in s and "Receivables" not in s,
      "header stripped -- a summary carrying its own heading reads plausibly and is wrong")
check(s == "the real sentence.", "summary is exactly the derived sentence (got %r)" % s)

print("\n5. A CAVEAT marker is PUBLISHED as a caveat, not scrubbed")
g = make_game(tmp / "e",
              ["- **DQ-25 · Lever** *(#8)* — a finding. Re-confirm numbers post-#643."],
              [("DQ-25", "Lever", "open", 1)])
code, out = run(g)
h, r = rendered()
check('class="cav"' in h, "a caveat is rendered")
check("re-confirmed" in h, "and it says what the caveat IS, in reader-facing words")
check("Full text withheld" not in h, "a caveat does not withhold the entry")

print("\n6. An UNRECOGNISED internal marker REFUSES the body (default is refuse)")
g = make_game(tmp / "f",
              ["- **DQ-30 · Thing** *(#9)* — a sentence. FIXME rip this out before ship."],
              [("DQ-30", "Thing", "open", 1)])
code, out = run(g)
h, r = rendered()
check("Full text withheld" in h, "the body is withheld rather than leaked")
check("DQ-30" in h, "but the ROW still appears -- withholding a body is not dropping a row")

print("\n7. A row with no derivable summary REFUSES TO WRITE, never publishes short")
g = make_game(tmp / "g",
              ["- **DQ-40 · Empty** *(#10)*"],
              [("DQ-40", "Empty", "open", 1)])
code, out = run(g)
check(code == 1, "exit 1 (got %s)" % code)
check("undercount" in out,
      "says why: a missing row is an undercount wearing a complete-looking table")

print("\n8. No pdoom1 checkout -> refuses, exit 2, does not invent a table")
code, out = run(tmp / "nonexistent")
check(code == 2, "exit 2 (got %s)" % code)
check("REFUSING" in out, "says plainly that it is refusing")

print("\n9. Every rendered field is HTML-escaped")
g = make_game(tmp / "h",
              ['- **DQ-50 · <script>alert(1)</script> & "quotes"** *(#11)* — a & b < c.'],
              [("DQ-50", '<script>alert(1)</script> & "quotes"', "open", 1)])
code, out = run(g)
h, _ = rendered()
check("<script>alert(1)</script>" not in h, "a title cannot inject a tag")
check("&lt;script&gt;" in h, "it is escaped instead")

if backup is not None:
    OUT.write_text(backup, encoding="utf-8")
shutil.rmtree(tmp, ignore_errors=True)

print()
if failures:
    print("%d FAILURE(S)" % len(failures))
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: every index row survives, boundaries hold at three scales, caveats publish, "
      "unknown markers refuse, and nothing is silently dropped.")
