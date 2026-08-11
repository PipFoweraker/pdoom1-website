#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check-blessing-consistency.py -- do the four artefacts that record a league
blessing actually agree with each other?

WHY THIS EXISTS
---------------
A blessing is Pip's explicit sign-off that a seed is the real one for an epoch. It
is one decision, and it is recorded by hand into FOUR places with nothing checking
that they match. On 2026-08-09 they did not, and the failure was worse than a
stale value:

  * public/data/ladder-epochs.json -> regularised_from  said seed_status "blessed"
  * docs/LEAGUE_SEED_LEDGER.md     -> the L3 table row   said "NOT YET BLESSED"
  * weekly/current.json            said blessed: true, CITING the ledger as its
                                   authority -- while contradicting it

Five or six of the seven checklist steps had run. The one that did not was the
HUMAN-READABLE one. So the machine knew and the document lied, which is the worse
split: a seat reading for orientation reads the document, and this seat did, and
told Pip his epoch had never been blessed. He was right and it was wrong.

That is what this catches. See pdoom1-website#297 and the Workshop 2 R9 ruling.

THE FOUR ARTEFACTS AND THEIR DIFFERENT ROLES
--------------------------------------------
They are NOT four copies of one fact. Treating them as interchangeable is how the
last fix went wrong, so the roles are encoded here rather than left to memory:

  1. docs/LEAGUE_SEED_LEDGER.md      THE HUMAN RECORD. Authoritative for WHO
                                     blessed and WHEN. A row here is the blessing.
  2. public/data/ladder-epochs.json  THE MACHINE-READ FIELD. The seed ledger's own
                                     checklist calls regularised_from "the only
                                     place a script reads it". Must match (1).
  3. weekly/current.json             DERIVED by weekly-league-manager.py. Must
                                     match (1) and (2); it must never lead.
  4. published-board.json            AN OBSERVATION of what the client posts to.
                                     Its seed_provenance.blessed is FALSE BY
                                     DESIGN and that is correct -- it records what
                                     IS, not what was blessed. So it is compared
                                     on the KEY only, never on blessed-status.

  ** Do not "fix" (4) to say blessed: true. It would be a lie, and the publisher
     writes that field deliberately. **

WHAT IT WILL NOT DO
-------------------
It does not decide anything. It cannot fill a ledger row -- that row records who
blessed and when, and a seat inferring that is how #297 started. It reports
disagreement and stops.

ABSENCE IS NOT AGREEMENT. A file that cannot be read, or a row that cannot be
parsed, is `unknown` and exit 2 -- never a quiet pass.

EXIT CODES
  0  the artefacts agree about the current epoch
  1  they disagree -- a blessing is recorded in some places and not others
  2  cannot tell -- an artefact is missing, unreadable, or declares nothing

RUN
    python scripts/check-blessing-consistency.py
    python scripts/check-blessing-consistency.py --root path/to/fixture-tree
"""

import argparse
import io
import json
import re
import sys
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

REPO_ROOT = Path(__file__).resolve().parents[1]

# A ledger row: | L3 | `seed` | L3 | `board file` | blessed date | by | notes |
ROW_RE = re.compile(r"^\|\s*\**\s*(L\d+)\s*\**\s*\|(.+)$")
BACKTICKED = re.compile(r"`([^`]+)`")
# The unfilled-row marker the ledger uses. Matching the WORDS, not the emoji --
# CLAUDE.md: the Windows console is cp1252 and an emoji literal is a crash.
UNBLESSED_RE = re.compile(r"NOT\s+YET\s+BLESSED", re.I)
ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def parse_ledger(path):
    """Return {epoch: {seed, blessed, blessed_utc, by, unfilled}} from the table."""
    rows = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        epoch, rest = m.group(1), m.group(2)
        cells = [c.strip() for c in rest.split("|")]
        unfilled = bool(UNBLESSED_RE.search(rest))

        # THE SEED COMES FROM ITS OWN CELL, and from nowhere else.
        #
        # This used to take "the first backticked value in the row that is not a
        # filename", which reads sensibly and is wrong: a row whose seed cell is
        # EMPTY adopts the first backtick anywhere in the row, including a
        # documentation path in the notes column --
        #
        #   | L9 |  | L9 |  | - | - | see `docs/THING.md` for the seed |
        #        -> seed == 'docs/THING.md'
        #
        # which would present a doc path as a blessed league seed. Found by
        # attacking the parser (the 2026-08-11 sweep), not by reading it. It was
        # harmless only because the live unfilled row is flagged separately and
        # nulls the seed before this runs -- an accident, not a guard.
        #
        # Cell 0 is the seed column: ROW_RE has already consumed the epoch cell,
        # so `rest` begins at the seed. Refuse rather than guess when it is empty.
        seed_cell = cells[0] if cells else ""
        ticked = BACKTICKED.findall(seed_cell)
        seed = ticked[0] if ticked else (seed_cell or None)
        if seed and (seed.endswith(".json") or UNBLESSED_RE.search(seed)):
            seed = None
        date = None
        for c in cells:
            d = ISO_DATE.search(c)
            if d:
                date = d.group(1)
                break
        by = None
        for c in cells:
            if c and c not in ("-", "—") and len(c) < 24 and c.isalpha():
                by = c
                break
        rows[epoch] = {"seed": None if unfilled else seed, "blessed": not unfilled,
                       "blessed_utc": date, "by": by, "unfilled": unfilled}
    return rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(REPO_ROOT))
    args = ap.parse_args()
    root = Path(args.root)

    P_LADDER = root / "public" / "data" / "ladder-epochs.json"
    P_WEEKLY = root / "public" / "leaderboard" / "data" / "weekly" / "current.json"
    P_PUB = root / "public" / "leaderboard" / "data" / "published-board.json"
    P_TARGETS = root / "public" / "leaderboard" / "data" / "board-probe-targets.json"
    P_LEDGER = root / "docs" / "LEAGUE_SEED_LEDGER.md"

    print("Blessing consistency -- do the four artefacts agree?")
    print("=" * 74)

    ladder = load_json(P_LADDER)
    weekly = load_json(P_WEEKLY)
    published = load_json(P_PUB)
    targets = load_json(P_TARGETS) or {}
    ledger = parse_ledger(P_LEDGER)

    missing = [n for n, v in (("ladder-epochs.json", ladder),
                              ("weekly/current.json", weekly),
                              ("published-board.json", published),
                              ("LEAGUE_SEED_LEDGER.md", ledger)) if v is None]
    if missing:
        print("  CANNOT TELL: could not read %s." % ", ".join(missing))
        print("  A missing artefact is UNKNOWN, never agreement.")
        return 2

    # Which epoch is current? board-probe-targets.json is the site's declaration,
    # and check-epoch-drift.py separately proves it against what the game ships --
    # so this check does not need to re-derive it and must not guess it.
    epoch = ((targets.get("current_ladder_epoch") or {}).get("value"))
    if not epoch:
        print("  CANNOT TELL: board-probe-targets.json declares no current epoch,")
        print("  so there is no epoch to check agreement about.")
        return 2
    print("  current epoch (declared)   %s" % epoch)

    findings = []

    # ---- 1. the human record -------------------------------------------------
    row = (ledger or {}).get(epoch)
    if row is None:
        findings.append("LEDGER has NO ROW for %s. The blessing is not recorded "
                        "where a human would look for it." % epoch)
        led_seed, led_blessed = None, False
    else:
        led_seed, led_blessed = row["seed"], row["blessed"]
        if row["unfilled"]:
            findings.append("LEDGER row for %s reads NOT YET BLESSED." % epoch)
        elif not led_seed:
            # Surfaced by the 2026-08-11 sweep's own regression test: a row that
            # claims a blessing while naming no seed used to pass silently,
            # because the old parser filled the gap from elsewhere in the row.
            # With the seed read from its own cell the gap is now visible, and a
            # blessing of nothing is exactly what this check exists to catch.
            findings.append(
                "LEDGER row for %s records a blessing but NAMES NO SEED. A blessing "
                "is a sign-off on a specific string; without one there is nothing "
                "for the other artefacts to agree with." % epoch)
        print("  ledger row                 seed=%s blessed=%s by=%s on=%s"
              % (led_seed, led_blessed, row["by"], row["blessed_utc"]))

    # ---- 2. the machine-read field ------------------------------------------
    reg = (ladder or {}).get("regularised_from") or {}
    lad_seed = reg.get("seed")
    lad_blessed = (reg.get("seed_status") == "blessed")
    lad_epoch = reg.get("ladder_version")
    print("  ladder-epochs.json         seed=%s status=%s epoch=%s"
          % (lad_seed, reg.get("seed_status"), lad_epoch))

    # The same file's epochs[] array is a SECOND record inside ONE artefact, and
    # on 2026-08-10 it contradicted regularised_from. An artefact that disagrees
    # with itself cannot be used to check the others.
    for e in (ladder.get("epochs") or []):
        if e.get("ladder_version") == lad_epoch:
            if (e.get("seed") or None) != (lad_seed or None):
                findings.append(
                    "ladder-epochs.json CONTRADICTS ITSELF for %s: regularised_from "
                    "says seed %r, epochs[] says %r."
                    % (lad_epoch, lad_seed, e.get("seed")))
            if lad_blessed and e.get("status") == "opening":
                findings.append(
                    "ladder-epochs.json CONTRADICTS ITSELF for %s: regularised_from "
                    "says blessed, epochs[] still says status 'opening'." % lad_epoch)

    # ---- 3. the derived file -------------------------------------------------
    wk_seed = weekly.get("seed")
    wk_blessed = bool((weekly.get("seed_provenance") or {}).get("blessed"))
    wk_epoch = ((weekly.get("meta") or {}).get("ladder_version")
                or (weekly.get("epoch") or {}).get("ladder_version"))
    print("  weekly/current.json        seed=%s blessed=%s epoch=%s"
          % (wk_seed, wk_blessed, wk_epoch))

    # ---- 4. the observation (KEY ONLY -- never blessed-status) ---------------
    pub_seed = published.get("seed")
    pub_epoch = published.get("ladder_epoch")
    print("  published-board.json       seed=%s epoch=%s   (observation; its "
          "blessed:false is CORRECT)" % (pub_seed, pub_epoch))
    print("-" * 74)

    # ---- comparisons ---------------------------------------------------------
    if lad_epoch and lad_epoch != epoch:
        findings.append("ladder-epochs.json describes %s as the frontier, but the "
                        "declared current epoch is %s." % (lad_epoch, epoch))
    if wk_epoch and wk_epoch != epoch:
        findings.append("weekly/current.json is stamped %s, but the declared "
                        "current epoch is %s -- the league page derives from this."
                        % (wk_epoch, epoch))
    if pub_epoch and pub_epoch != epoch:
        findings.append("published-board.json serves %s while %s is declared "
                        "current." % (pub_epoch, epoch))

    if led_blessed != lad_blessed:
        findings.append(
            "BLESSED-STATUS SPLIT for %s: the ledger says %s, ladder-epochs.json "
            "says %s. This is the 2026-08-09 defect exactly -- the machine knew "
            "and the document lied." % (epoch, led_blessed, lad_blessed))
    if wk_blessed and not led_blessed:
        findings.append(
            "weekly/current.json claims blessed:true for a seed the ledger has not "
            "blessed -- and it cites the ledger as its authority while "
            "contradicting it.")

    seeds = {"ledger": led_seed, "ladder-epochs": lad_seed, "weekly": wk_seed}
    named = {k: v for k, v in seeds.items() if v}
    if len(set(named.values())) > 1:
        findings.append("SEED DISAGREEMENT: %s." % ", ".join(
            "%s=%s" % (k, v) for k, v in sorted(named.items())))

    if not findings:
        print()
        print("  OK: ledger, ladder-epochs.json and weekly/current.json agree about")
        print("  %s, and published-board.json serves the same key." % epoch)
        return 0

    print()
    print("  !! THE BLESSING RECORD DISAGREES WITH ITSELF -- %d finding(s)"
          % len(findings))
    for f in findings:
        print("     - %s" % f)
    print()
    print("     A blessing is ONE decision written to FOUR places by hand. Nothing")
    print("     until now checked they matched, and on 2026-08-09 they did not.")
    print()
    print("     THIS SCRIPT WILL NOT FILL A LEDGER ROW. That row records WHO")
    print("     blessed and WHEN; a seat inferring it is how #297 started.")
    print("     See docs/LEAGUE_SEED_LEDGER.md 'How to add a row' and #297.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
