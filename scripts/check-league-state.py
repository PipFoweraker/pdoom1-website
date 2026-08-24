#!/usr/bin/env python3
"""Invariants for `player_facing` in public/data/ladder-epochs.json.

WHY THIS EXISTS
---------------
pdoom1-website#351: the site could say what is downloadable and what is coming,
and had no way to say which league is OPEN. So a published-but-unopened board and
an open board looked identical from outside, and a visitor who submitted a score
saw a board it could never appear on with no error anywhere.

The `player_facing` block models those as three separate questions with three
separate pieces of evidence. This checker exists because the block is hand-written
and its dangerous failure is silent: a seat filling in `league_open.seed` from an
observation would publish an opening that never happened. That is
pdoom1-website#297 one gate later.

WHAT IT REFUSES
---------------
1. A state name that is not in the block's own `_states` vocabulary.
2. `league_open.state == "open"` without a named opener and a timestamp -- openness
   is a recorded human act, never an inference from a board, a 200 or a blessing.
3. Any non-open state that nevertheless carries an open league's fields.
4. A `seed` presented without `seed_blessed: true`, or a `seed_blessed: true` whose
   seed is not in docs/LEAGUE_SEED_LEDGER.md. CLAUDE.md: never present an unblessed
   seed to a player.
5. An epochs[] entry marked `published: false` that carries a `boundary_local`
   (it would relabel every later week) or claims `seed_status: blessed`.
6. `cut_ladder_version` disagreeing with `cut_ladder_version_published`.
7. `downloadable_now` naming a different epoch from the frontier the site publishes
   on -- those two must be the same fact or the page is guessing.

EXIT CODES -- three outcomes, not two.
  0  invariants hold and the verification is fresh
  1  an invariant is violated (a claim on the site is wrong)
  2  CANNOT TELL: the file is missing/unreadable, or the verification has expired.
     Not a pass. The renderer degrades the same block to `unknown`.

Run: python scripts/check-league-state.py [path-to-ladder-epochs.json]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "public" / "data" / "ladder-epochs.json"
LEDGER = ROOT / "docs" / "LEAGUE_SEED_LEDGER.md"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

OPEN_FIELDS = ("seed", "ladder_version", "opened_by", "opened_utc")
BLOCKS = ("downloadable_now", "league_open", "coming")


def _parse_stamp(raw: str):
    """ISO-8601, tolerating the trailing Z form and a minute-precision stamp."""
    if not isinstance(raw, str) or not raw:
        return None
    txt = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    ledger_path = path.parent.parent.parent / "docs" / "LEAGUE_SEED_LEDGER.md"
    if not ledger_path.exists():
        ledger_path = LEDGER

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 -- any read/parse failure is "cannot tell"
        print("CANNOT TELL: %s could not be read: %s" % (path, exc))
        print("  Absence is not agreement. Nothing here may fall back to a literal.")
        return 2

    pf = data.get("player_facing")
    if not isinstance(pf, dict):
        print("CANNOT TELL: %s has no `player_facing` block." % path)
        return 2

    bad: list[str] = []
    stale: list[str] = []

    states = pf.get("_states")
    if not isinstance(states, dict) or not states:
        bad.append("`player_facing._states` is missing or empty -- a state name with "
                   "no published meaning is a label, not a claim.")
        states = {}

    ledger_text = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    if not ledger_text:
        stale.append("docs/LEAGUE_SEED_LEDGER.md could not be read, so no "
                     "`seed_blessed: true` can be corroborated.")

    # ---- 1..4: the three blocks -------------------------------------------
    for name in BLOCKS:
        blk = pf.get(name)
        if not isinstance(blk, dict):
            bad.append("`player_facing.%s` is missing." % name)
            continue
        for req in ("question", "state", "evidence"):
            if not blk.get(req):
                bad.append("`%s.%s` is missing or empty. Every claim carries its own "
                           "evidence; a block without one is an assertion." % (name, req))
        state = blk.get("state")
        if state and state not in states:
            bad.append("`%s.state` is %r, which `_states` does not define. Add the "
                       "meaning or use `unknown`." % (name, state))

        # Openness is a recorded act, never an inference.
        if state == "open":
            for f in OPEN_FIELDS:
                if not blk.get(f):
                    bad.append("`%s.state` is \"open\" but `%s` is empty. An opening is "
                               "a named human's recorded act at [Gate 6] -- it may not "
                               "be inferred from a board, from a 200, or from a "
                               "blessing (#297)." % (name, f))
        elif name == "league_open":
            for f in OPEN_FIELDS:
                if blk.get(f):
                    bad.append("`league_open.%s` is set to %r while the state is %r. "
                               "Only an open league has those fields; a value sitting "
                               "there reads as an opening that did not happen."
                               % (f, blk.get(f), state))

        # A seed reaches a visitor only when it is blessed. A block may carry the seed
        # at the top level (league_open) or inside board_key (downloadable_now); both
        # are the same claim to a reader, so both are held to the same rule.
        seed = blk.get("seed") or (blk.get("board_key") or {}).get("seed")
        blessed = blk.get("seed_blessed")
        if seed and blessed is not True:
            bad.append("`%s.seed` is %r but `seed_blessed` is %r. CLAUDE.md: never "
                       "present an unblessed seed to a player. Record an observed "
                       "const under a differently-named field instead."
                       % (name, seed, blessed))
        if blessed is True and not seed:
            bad.append("`%s.seed_blessed` is true with no seed. A blessing of nothing "
                       "is not a blessing." % name)
        if seed and blessed is True and ledger_text and seed not in ledger_text:
            bad.append("`%s.seed` is %r and claims blessed, but that string does not "
                       "appear in docs/LEAGUE_SEED_LEDGER.md, which is the record a "
                       "blessing lives in. The ledger is the authority; this file is "
                       "its machine mirror." % (name, seed))

    # ---- 7: the downloadable epoch IS the frontier -------------------------
    reg = data.get("regularised_from") or {}
    dl = pf.get("downloadable_now") or {}
    dl_epoch = ((dl.get("board_key") or {}).get("ladder_version"))
    if dl_epoch and reg.get("ladder_version") and dl_epoch != reg["ladder_version"]:
        bad.append("`downloadable_now.board_key.ladder_version` is %r but the frontier "
                   "`regularised_from.ladder_version` is %r. The epoch a player can "
                   "reach and the epoch this site publishes on must be one fact, or "
                   "the leaderboard is guessing which board to show."
                   % (dl_epoch, reg["ladder_version"]))

    # ---- 6: the cut epoch vs the published one -----------------------------
    cut = reg.get("cut_ladder_version")
    cut_pub = reg.get("cut_ladder_version_published")
    if cut is not None:
        if cut == reg.get("ladder_version") and cut_pub is not True:
            bad.append("`cut_ladder_version` equals the frontier (%r) but "
                       "`cut_ladder_version_published` is %r. If the frontier has "
                       "moved to the cut, a build carrying it shipped."
                       % (cut, cut_pub))
        if cut != reg.get("ladder_version") and cut_pub is not False:
            bad.append("`cut_ladder_version` is %r, the frontier is %r, and "
                       "`cut_ladder_version_published` is %r. A cut the frontier has "
                       "not caught up to is by definition unpublished."
                       % (cut, reg.get("ladder_version"), cut_pub))

    # ---- 5: an unpublished epoch must not carry a boundary or a blessing ---
    for e in (data.get("epochs") or []):
        if e.get("published") is False:
            lv = e.get("ladder_version")
            if e.get("boundary_local"):
                bad.append("epochs[] %s is marked published:false but carries "
                           "boundary_local %r. ladder_version_for() resolves every "
                           "week from those boundaries, so this would relabel every "
                           "later week as an epoch no build ships."
                           % (lv, e["boundary_local"]))
            if e.get("seed_status") == "blessed":
                bad.append("epochs[] %s is marked published:false and claims "
                           "seed_status blessed. Nothing unshipped has been blessed; "
                           "a blessing is Pip's, after the ceremony (#297)." % lv)

    # ---- freshness ---------------------------------------------------------
    stamp = _parse_stamp(pf.get("verified_utc") or "")
    days = pf.get("stale_after_days")
    if stamp is None:
        stale.append("`player_facing.verified_utc` is missing or unparseable, so "
                     "nothing here can be dated. A claim with no date cannot expire.")
    elif not isinstance(days, int) or days <= 0:
        stale.append("`player_facing.stale_after_days` is %r. A verification date with "
                     "no expiry is the class-5 shape." % days)
    else:
        age = (datetime.now(timezone.utc) - stamp).total_seconds() / 86400.0
        if age > days:
            stale.append("the verification is %.1f days old and expires after %d. "
                         "Re-run the measurements each block's `evidence` names, then "
                         "re-stamp verified_utc." % (age, days))

    print("league state: %s" % path)
    print("  downloadable_now : %s" % (dl.get("state") or "?"))
    print("  league_open      : %s" % ((pf.get("league_open") or {}).get("state") or "?"))
    print("  coming           : %s" % ((pf.get("coming") or {}).get("state") or "?"))
    print("-" * 70)

    if bad:
        print("  !! %d INVARIANT VIOLATION(S) -- a claim on the site is wrong" % len(bad))
        for f in bad:
            print("     - %s" % f)
        return 1
    if stale:
        print("  CANNOT TELL -- %d reason(s). This is not a pass; the page shows"
              % len(stale))
        print("  these blocks as `unknown` rather than as still-true.")
        for f in stale:
            print("     - %s" % f)
        return 2
    print("  OK: three questions, three states, three pieces of evidence, and no")
    print("  opening is claimed that a human did not record.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
