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
2b. ...and, since the 2026-08-24 review of #353, an "open" claim that the LEDGER does
   not carry. Requiring only a non-empty `opened_by` caught the incomplete fabrication
   and waved through the complete one: `opened_by: "Pip"` plus a plausible timestamp
   exited 0 while the ledger said [Gate 6] was HELD. So an opening must now quote
   docs/LEAGUE_SEED_LEDGER.md verbatim, the quote may not itself be a refusal, and a
   standing hold naming the same epoch beats the claim until the lift is recorded too.
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
import re
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


MIN_QUOTE = 40
# A quote that says the gate is HELD, or that the board is not open, is evidence of
# the opposite of an opening. Without this the verbatim-quote rule below is trivially
# satisfiable by quoting the very sentence that refuses the opening -- which is the
# text most likely to be sitting in the ledger when someone fabricates one.
_REFUSAL = ("held", "not open", "not yet open", "pending", "to be drawn")


def _norm(text: str) -> str:
    """Collapse whitespace so a markdown line-wrap cannot defeat a verbatim match."""
    return " ".join(str(text or "").split())


def _quote_is_corroborated(quote, ledger_norm: str):
    """(ok, why-not). A quote must be substantial, present verbatim, and not a refusal."""
    if not quote:
        return False, "is missing"
    q = _norm(quote)
    if len(q) < MIN_QUOTE:
        return False, ("is only %d characters; a fragment that short can match by "
                       "accident, so at least %d are required" % (len(q), MIN_QUOTE))
    if not ledger_norm:
        return False, "cannot be corroborated because the ledger could not be read"
    if q not in ledger_norm:
        return False, ("does not appear in docs/LEAGUE_SEED_LEDGER.md. The ledger is "
                       "the record an opening lives in; this file is its machine "
                       "mirror, and a mirror may not show something the record does not")
    low = q.lower()
    hit = next((w for w in _REFUSAL if w in low), None)
    if hit:
        return False, ("quotes ledger text containing %r, which is a refusal to open "
                       "rather than an opening. Quoting the sentence that HOLDS the "
                       "gate is not evidence that the gate was lifted" % hit)
    return True, ""


def check_opening_corroborated(name: str, blk: dict, ledger_text: str) -> list:
    """An OPENING must be corroborated by the ledger, the way a seed already is.

    THE HOLE THIS CLOSES (found by adversarial review of PR #353, 2026-08-24).
    The previous version enforced only against a MISSING opening record: it required
    `opened_by` and `opened_utc` to be non-empty. So a seat that typed
    `opened_by: "Pip"` with a plausible timestamp got exit 0 and the line
    "no opening is claimed that a human did not record" -- while
    docs/LEAGUE_SEED_LEDGER.md said verbatim that [Gate 6] was HELD and the board was
    not open, and /leaderboard/ rendered "Open ... Opened by Pip". The guard covered
    the shape that would never survive review and missed the one that would.

    An opening is a human act recorded in the ledger. This file may only MIRROR it, so
    the mirror has to point at the record: quote it verbatim, and do not claim an
    opening while an unresolved hold naming the same epoch is still standing.
    """
    out = []
    ledger_norm = _norm(ledger_text)

    ok, why = _quote_is_corroborated(blk.get("opening_ledger_quote"), ledger_norm)
    if not ok:
        out.append("`%s.state` is \"open\" but `opening_ledger_quote` %s. An opening is "
                   "a row in docs/LEAGUE_SEED_LEDGER.md; nothing here may assert one "
                   "the ledger does not carry." % (name, why))

    # A standing hold beats a claimed opening. `[Gate 6] ... HELD` next to this epoch
    # means the ceremony refused, and a refusal is only undone by another recorded act.
    epoch = str(blk.get("ladder_version") or "")
    seed = str(blk.get("seed") or "")
    if (epoch or seed) and ledger_text:
        # Containers, NOT a character window. A fixed +/-400 window missed the real
        # thing on 2026-08-24: the ledger's L5 row is one 828-character markdown table
        # line with "L5" at the start and "[Gate 6] HELD" 591 characters later, so the
        # two never landed in the same window and a standing hold read as absent. A
        # table row is a line and a prose hold is a paragraph, so ask both.
        lines = ledger_text.splitlines()
        paras = ledger_text.split("\n\n")
        names = [re.escape(x) for x in (epoch, seed) if x]
        who = re.compile(r"\b(?:%s)\b" % "|".join(names)) if names else None
        standing = any(
            "gate 6" in c.lower() and "HELD" in c and who and who.search(c)
            for c in lines + paras)
        if standing:
            ok2, why2 = _quote_is_corroborated(
                blk.get("hold_lifted_ledger_quote"), ledger_norm)
            if not ok2:
                out.append(
                    "`%s` claims %s is OPEN, but docs/LEAGUE_SEED_LEDGER.md still "
                    "records [Gate 6] HELD next to %s, and `hold_lifted_ledger_quote` "
                    "%s. A hold is lifted by a recorded act, not by editing this file. "
                    "Write the lift into the ledger and quote it here."
                    % (name, epoch, epoch, why2))
    return out


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
            bad.extend(check_opening_corroborated(name, blk, ledger_text))
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
    print("  OK: three questions, three states, three pieces of evidence, and any")
    print("  opening claimed here is quoted verbatim from the ledger that records it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
