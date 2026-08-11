#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish the board the game actually posts to.

WHY THIS EXISTS
---------------
Until now nothing in this repo published live scores. `ingest_scores.py` reads seed
files from disk; `export-leaderboard-bridge.py` is a deprecated stub that used to
FABRICATE entries; `check-board-liveness.py` reads the API but only to REPORT. So the
site could observe that real scores existed and still show an empty board -- which is
exactly what happened: 27 entries from 6 players accumulated on boards pdoom1.com does
not publish (see public/leaderboard/data/preserved/2026-07-29-orphaned-boards/).

pdoom1 asked for this directly on issue #201: "Publish the (seed, L3) board. This is
the one that decides whether Friday records anything."

WHAT IT WILL NOT DO
-------------------
- **Never POST.** The website is a READ-ONLY consumer of one PHP score API; the game
  owns score truth (pdoom1 PR #679). This does GET and nothing else.
- **Never invent a seed.** The seed is OBSERVED -- whatever board the client is
  demonstrably posting to -- not chosen here and not derived from a week number. A
  website-derived seed is what routed a whole week's submissions to a board nobody
  displayed. Friday's seed is drawn at a ceremony that has not happened; this script
  needs no edit when it does, because it reads what is live rather than what is planned.
- **Never write on failure.** A fetch error, an unparseable payload or an unknown
  ladder epoch leaves the last known-good file untouched and exits non-zero. A default
  value ships precisely when the real lookup failed, so there are no defaults here.
- **Never publish across epochs.** Scores earned under different rules are not
  comparable -- that non-comparability is the entire reason the ladder epoch is half
  the board key. Boards on other epochs stay where they are, tagged legacy.
- **Never replace a board with an empty one on the SAME key.** If the key has not
  moved and the rows have vanished, the API is lying (or the network is), and
  overwriting real scores with nothing is the exact damage this whole subsystem exists
  to prevent.

EMPTY BOARDS, AND THE ONE CASE WHERE PUBLISHING ONE IS HONEST
-------------------------------------------------------------
Added 2026-08-08, for the L3 -> L4 fork. An epoch fork (or a seed roll) opens a real
board with **zero rows**, and that state is genuinely different from "the rows went
missing":

  same key + 0 rows  ->  the API is contradicting itself. REFUSE, keep the good board.
  NEW key  + 0 rows  ->  a fork. The old board is closed history; the new board is the
                         one players reach, and it is empty because nobody has finished
                         a run yet. Publishing it as `data_status: "live-empty"` is the
                         honest answer; continuing to publish the CLOSED board as if it
                         were current is not.

The published key is read from `leaderboard.json`'s own `meta.board_key`, so "new" means
"different from what this site is serving right now", not "different from what some
other file remembers".

**A guessed seed is still refused.** With zero rows the API gives no evidence at all
about which key is real -- every wrong key returns `ok:true` with an empty board -- so if
several reachable boards on the epoch are empty, this REFUSES and names them rather than
picking one. It narrows by DECLARATION where it can (a seed pinned in
board-probe-targets.json carries a `source`; a derived one does not), and never widens.
An empty board is published only when exactly one candidate survives.

WHAT IT WRITES
--------------
  public/leaderboard/data/leaderboard.json    the table the page renders
  public/leaderboard/data/published-board.json  which board key the site publishes,
                                                with provenance

The second file exists so "the board this site publishes" is an ARTIFACT rather than
something inferred from weekly/current.json -- which weekly-league-manager.py owns and
rewrites on rollover. Two writers on one file is how version.json got into trouble.
check-board-liveness.py prefers this artifact when present.

Usage:
  python scripts/publish-live-board.py            # fetch and publish
  python scripts/publish-live-board.py --check    # verify freshness, write nothing
  python scripts/publish-live-board.py --dry-run  # show what would be published

Exit codes: 0 ok / 1 nothing publishable / 2 cannot determine epoch / 3 fetch failed
"""

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows console is cp1252; a non-ASCII print dies on the FIRST print, before any work.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
LB_DIR = ROOT / "public" / "leaderboard" / "data"
BOARD_JSON = LB_DIR / "leaderboard.json"
PUBLISHED_JSON = LB_DIR / "published-board.json"
TARGETS_JSON = LB_DIR / "board-probe-targets.json"

# Reuse the probe's derivation instead of copying it. The seed/epoch derivation is
# subtle -- it reads preserved capture FILENAMES to recover the client's own seed
# format, which this repo does not generate and could not otherwise guess. A second
# copy would drift from the first, and the two disagreeing is how the board key gets
# lost again. The hyphen in the filename is why this is an importlib dance.
_spec = importlib.util.spec_from_file_location(
    "check_board_liveness", Path(__file__).resolve().parent / "check-board-liveness.py")
liveness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(liveness)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def published_key():
    """The (seed, epoch) this site is serving RIGHT NOW, from the board it serves.

    Read from leaderboard.json rather than published-board.json on purpose: the question
    being asked is "what would this write replace", and the answer is whatever the page
    fetches. A missing or unreadable file yields (None, None), which compares unequal to
    every real key -- so an absent board is treated as "nothing to protect", never as
    "matches, refuse".
    """
    cur = load_json(BOARD_JSON, {}) or {}
    k = ((cur.get("meta") or {}).get("board_key") or {})
    return k.get("seed"), k.get("ladder_epoch")


def pinned_seeds():
    """Seeds a human declared in board-probe-targets.json, WITH a source.

    Same rule check-board-liveness.py applies: a pinned value with no source is a
    hardcoded literal wearing a costume, and is ignored. Used only to NARROW an
    otherwise ambiguous empty-board choice, never to add a candidate.
    """
    targets = load_json(TARGETS_JSON, {}) or {}
    out = set()
    for item in (targets.get("extra_seeds") or []):
        if isinstance(item, dict) and item.get("source") and item.get("value"):
            out.add(item["value"])
    return out


def pick_live_board(epoch, verbose=True):
    """The board on THIS epoch that the site should publish.

    Returns (result_dict, entries_list, status) where status is one of:

      "ok"          a board was chosen; entries_list holds its rows (possibly EMPTY,
                    but only when the key differs from what is published today)
      "unreadable"  every probe failed, or the winner's re-fetch failed. Evidence of
                    nothing; the caller must not write.
      "same-key"    the only thing on offer is an empty board on the key already
                    published. The API is contradicting itself; refuse.
      "ambiguous"   several reachable boards on this epoch are empty and none is
                    distinguishable. Every wrong key answers ok:true+empty, so choosing
                    would be guessing.
      "none"        nothing reachable on this epoch at all.

    Only boards whose version half equals the current epoch are eligible -- a busier
    board on an older epoch is history, not the league, and publishing it would merge
    scores across rule sets.
    """
    seeds, versions, notes = liveness.derive_targets([], [])
    if verbose:
        for n in notes:
            print("  note: %s" % n)

    candidates, empties, errors, probed = [], [], 0, 0
    for s in seeds:
        r = liveness.probe_board(s, epoch)
        probed += 1
        if r.get("error"):
            errors += 1
            if verbose:
                print("  unreachable: (%s, %s): %s" % (s, epoch, r["error"]))
            continue
        if (r.get("entries") or 0) > 0:
            candidates.append(r)
        else:
            empties.append(r)

    # Every probe failed. NOT evidence that the boards are empty -- evidence that we
    # cannot tell. This must stay distinguishable from "nothing to publish": conflating
    # them is how a network blip would come to look like a fork.
    if probed and errors == probed:
        return None, None, "unreadable"

    if not candidates:
        winner, status = _pick_empty_fork(epoch, empties, verbose)
        if winner is None:
            return None, None, status
        # No re-fetch: there are no rows to fetch, and probe_board already established
        # that the key is reachable and answered ok:true.
        return winner, [], "ok"

    # Most recently active wins. Ties are impossible in practice (timestamps are
    # per-entry), but sorting by seed keeps the choice deterministic if they happen.
    candidates.sort(key=lambda r: (r.get("last_entry") or "", r["seed"]), reverse=True)
    winner = candidates[0]

    if verbose and len(candidates) > 1:
        print("  NOTE: %d boards are live on %s. Publishing the most recently active."
              % (len(candidates), epoch))
        for c in candidates:
            print("        (%s, %s) %d entries, last %s"
                  % (c["seed"], c["version"], c["entries"], c.get("last_entry")))

    # Re-fetch the winner to publish the ACTUAL rows. probe_board returns counts only;
    # publishing from a summary would mean publishing numbers nobody fetched.
    import urllib.parse
    q = urllib.parse.urlencode({"seed": winner["seed"], "version": epoch})
    data, err = liveness.get_json("%s?%s" % (liveness.SCORE_API, q))
    if err or not isinstance(data, dict) or not data.get("ok"):
        return None, None, "unreadable"
    return winner, (data.get("entries") or []), "ok"


def _pick_empty_fork(epoch, empties, verbose):
    """Choose an empty board to publish, or explain why nothing may be chosen.

    Returns (winner_or_None, status). See pick_live_board for the status vocabulary.
    """
    if not empties:
        return None, "none"

    cur_seed, cur_epoch = published_key()

    # An empty board on the key already published is the API contradicting itself, not
    # a fork. Refuse loudly rather than zeroing real scores.
    if any(r["seed"] == cur_seed for r in empties) and epoch == cur_epoch:
        if verbose:
            print("  REFUSING: (%s, %s) is the board this site already publishes and it "
                  "now reads EMPTY." % (cur_seed, cur_epoch))
            print("  The key has not moved, so this is not a fork -- it is the API (or "
                  "the network) losing rows.")
        return None, "same-key"

    fresh = [r for r in empties if (r["seed"], epoch) != (cur_seed, cur_epoch)]
    if not fresh:
        return None, "none"

    # Narrow by DECLARATION, never widen: a seed pinned with a source is one a human
    # vouched for. Derived seeds come from old captures and stale weekly files, and with
    # zero rows the API cannot tell them apart from the real one.
    declared = [r for r in fresh if r["seed"] in pinned_seeds()]
    pool = declared or fresh

    if len(pool) > 1:
        if verbose:
            print("  REFUSING: %d reachable boards on %s are empty and nothing "
                  "distinguishes them:" % (len(pool), epoch))
            for r in sorted(pool, key=lambda x: x["seed"]):
                print("        (%s, %s)" % (r["seed"], epoch))
            print("  Every WRONG key also answers ok:true with an empty board, so picking "
                  "one would be a guess wearing an observation's clothes. Pin the real "
                  "seed (with a source) in board-probe-targets.json, and remove any pin "
                  "whose remove_when has been met.")
        return None, "ambiguous"

    winner = pool[0]
    if verbose:
        print("  FORK: (%s, %s) is a NEW board key -- the site currently publishes "
              "(%s, %s)." % (winner["seed"], epoch, cur_seed, cur_epoch))
        print("  It holds 0 entries. That is an open board nobody has scored on yet, not "
              "a lost board: publishing it empty is honest, and continuing to publish a "
              "closed board as current is not.")
    return winner, "ok"


def build_payload(board, entries, epoch):
    players = sorted({e.get("player_name") for e in entries if e.get("player_name")})
    builds = sorted({e.get("game_mode") for e in entries if e.get("game_mode")})
    ranked = sorted(entries, key=lambda e: -(e.get("score") or 0))
    return {
        "meta": {
            "generated": now_iso(),
            "export_source": "website:publish-live-board.py",
            "total_players": len(players),
            "total_entries": len(ranked),
            "board_key": {"seed": board["seed"], "ladder_epoch": epoch},
            "builds_seen": builds,
            "note": (
                "Fetched read-only from the score API. The board key is "
                "(seed, ladder_epoch); the build version is NOT part of it, which is why "
                "one board legitimately spans several builds. Scores from other epochs "
                "are not merged in -- different rules produced them."
            ),
            "source_api": liveness.SCORE_API,
        },
        # "live" is asserted only because rows were actually fetched. With zero rows the
        # claim shrinks to "live-empty": the key is current and holds nothing yet. That
        # is a weaker statement than "live" on purpose -- validate_data.py FAILS on
        # live+0, and the leaderboard page hides the sort/filter toolbar for a board
        # that has nothing to sort.
        "data_status": "live" if ranked else "live-empty",
        "legacy": False,
        "seed": board["seed"],
        "economic_model": "unknown",
        # Same block ingest_scores.py emits, so validate_data.py can tell "nothing was
        # withheld" apart from "written before anyone reported withholding". This path
        # withholds nothing BY CONSTRUCTION: it publishes one board whole, and filtering
        # a live competitive board would be editing the standings.
        "exclusions": {
            "version_mismatched_files": 0,
            "version_mismatched_entries": 0,
            "version_mismatched_versions": [],
            "deployed_version": None,
            "test_dev_files": 0,
            "note": (
                "publish-live-board.py publishes one board key whole and excludes nothing. "
                "Build version is deliberately NOT a filter: a board spans builds by "
                "design, so excluding on it would drop real scores. Entries from OTHER "
                "epochs are not excluded here either -- they are simply not on this board."
            ),
        },
        "entries": ranked,
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify the published board is current; write nothing")
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    args = ap.parse_args()

    targets = load_json(TARGETS_JSON, {}) or {}
    epoch, epoch_source = liveness.current_epoch(targets)

    print("Publish live board -- %s" % now_iso())
    print("=" * 74)

    if not epoch:
        print("  REFUSING TO PUBLISH: no artifact says which ladder epoch is current.")
        print("  Publishing without knowing the epoch would be a guess, and a guessed")
        print("  board key is indistinguishable from a correct one until players lose")
        print("  scores. Populate current_ladder_epoch in %s"
              % TARGETS_JSON.relative_to(ROOT))
        return 2

    print("  current ladder epoch    %s" % epoch)
    print("  epoch source            %s" % epoch_source)

    board, entries, status = pick_live_board(epoch, verbose=not args.check)

    if board is None:
        # Each refusal says which one it is. "Cannot read" and "nothing to publish" were
        # once the same (None, None) return disambiguated by a sentinel, and that is the
        # kind of collapsing that lets an outage be mistaken for an empty league.
        if status == "unreadable":
            print("  the score API could not be read on %s." % epoch)
            print("  Leaving the published board untouched -- an empty file would erase")
            print("  history on a transient network failure.")
            return 3
        if status == "same-key":
            print("  the board this site publishes now reads EMPTY on the SAME key.")
            print("  Refusing: that is the API losing rows, not a fork. Nothing written.")
        elif status == "ambiguous":
            print("  several empty boards on %s and no way to tell which is real." % epoch)
            print("  Refusing rather than guessing a board key. Nothing written.")
        else:
            print("  no board on %s is reachable." % epoch)
        return 1

    print("-" * 74)
    print("  publishing (%s, %s): %d entries from %d player(s)"
          % (board["seed"], epoch, len(entries),
             len({e.get("player_name") for e in entries if e.get("player_name")})))
    print("  builds represented: %s" % (", ".join(board.get("builds_seen") or []) or "none"))

    payload = build_payload(board, entries, epoch)

    if args.check:
        cur = load_json(BOARD_JSON, {}) or {}
        cur_key = ((cur.get("meta") or {}).get("board_key") or {})
        stale = (cur_key.get("seed") != board["seed"]
                 or cur_key.get("ladder_epoch") != epoch
                 or len(cur.get("entries") or []) != len(entries))
        if stale:
            print("  STALE: published board is (%s, %s) with %d entries; live is "
                  "(%s, %s) with %d. Run without --check."
                  % (cur_key.get("seed"), cur_key.get("ladder_epoch"),
                     len(cur.get("entries") or []), board["seed"], epoch, len(entries)))
            return 1
        print("  OK: published board matches the live board.")
        return 0

    if args.dry_run:
        print("  --dry-run: nothing written.")
        return 0

    BOARD_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    PUBLISHED_JSON.write_text(json.dumps({
        "_comment": (
            "The board key this site publishes, written by publish-live-board.py. This is "
            "an OBSERVATION of what the shipped client posts to, not a choice made here. "
            "check-board-liveness.py reads it to decide whether a populated board is "
            "'deployed' or an orphan. Kept separate from weekly/current.json because "
            "weekly-league-manager.py owns that file and rewrites it on rollover."
        ),
        "seed": board["seed"],
        "ladder_epoch": epoch,
        "epoch_source": epoch_source,
        "seed_provenance": {
            "blessed": False,
            "derivation": "observed live on the score API; the board the client is posting to",
            "note": (
                "Not a blessing. Friday's competitive seed is drawn at the ceremony and "
                "recorded in docs/LEAGUE_SEED_LEDGER.md. This file records what IS, so "
                "that the site publishes the board players actually reach."
            ),
        },
        "entries_at_publish": len(entries),
        "published_at": now_iso(),
    }, indent=2) + "\n", encoding="utf-8")

    print("-" * 74)
    print("  wrote %s" % BOARD_JSON.relative_to(ROOT))
    print("  wrote %s" % PUBLISHED_JSON.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
