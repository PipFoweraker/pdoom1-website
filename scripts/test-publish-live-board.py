#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Destructive tests for scripts/publish-live-board.py.

WHY THIS EXISTS
---------------
publish-live-board.py was written and shipped on 2026-07-30 with ZERO tests, and it is
what stands between players and a visible league board. Its docstring claims these safety
properties:

  1. refuses and writes nothing when the ladder epoch is unknown
  2. refuses and writes nothing when the score API cannot be read
  3. never overwrites a board with an empty one on the SAME key -- but DOES publish an
     empty board on a NEW key, because an epoch fork opens a real board with no rows
  4. never publishes a board from a different epoch
  5. never guesses which empty board is real: with zero rows every wrong key looks
     exactly like the right one, so an undecidable choice is refused, not made

Those were assertions in prose. CLAUDE.md's testing discipline says a claimed safety
property needs a FORCED failure, because a docstring is documentation and not evidence.
Every test below forces the failure rather than exercising the happy path.

The property that matters most is (3). A crash is survivable and loud. Silently replacing
a board that holds real player scores with an empty one -- on a transient network blip --
destroys the record and looks exactly like "nobody is playing", which is the original bug
this whole subsystem exists to prevent.

**Property 3 changed shape on 2026-08-08 and this docstring changed with it.** It used to
read "NEVER overwrites a good board with an empty one", full stop, and test 3 asserted
exactly that. The L3 -> L4 ladder fork showed the blanket rule was itself a way to lie: the
old board closes, the new board opens with nothing on it, and refusing to publish the empty
new board leaves the site serving a CLOSED epoch's standings as if they were this week's.
The distinction that carries the safety property is the KEY, not the row count -- so the
one test became two, and the "same key" half is still the one that must never regress.

HOW IT ISOLATES
---------------
The module is imported and its path constants are redirected into a temp dir, so no test
can touch real data. The network is never used: liveness.probe_board and liveness.get_json
are replaced with stubs. Nothing here issues a single HTTP request, so it is safe to run
offline and in CI, and it cannot POST to the score API even by accident.

Run:  python scripts/test-publish-live-board.py     (exit 0 = pass)
"""

import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "publish_live_board", ROOT / "scripts" / "publish-live-board.py")
pub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pub)

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


# --------------------------------------------------------------------------- harness
GOOD_BOARD = {
    "meta": {"board_key": {"seed": "weekly-2026-w30", "ladder_epoch": "L3"},
             "total_entries": 3},
    "data_status": "live",
    "seed": "weekly-2026-w30",
    "entries": [{"score": 153, "player_name": "Applied AI Safety"},
                {"score": 109, "player_name": "Applied AI Safety"},
                {"score": 65, "player_name": "Intelligent Agents Studies"}],
}


class Sandbox:
    """Redirect the module's writes into a temp dir and stub the network."""

    def __init__(self, epoch="L3", boards=None, api_readable=True, seed_board=True,
                 pinned=()):
        self.epoch, self.boards, self.api_readable = epoch, boards or {}, api_readable
        self.seed_board = seed_board
        # Seeds pinned WITH a source in board-probe-targets.json. The module reads these
        # only to narrow an otherwise undecidable choice between empty boards.
        self.pinned = list(pinned)

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = {k: getattr(pub, k) for k in
                       ("BOARD_JSON", "PUBLISHED_JSON", "TARGETS_JSON", "ROOT")}
        self._saved_probe = pub.liveness.probe_board
        self._saved_get = pub.liveness.get_json
        self._saved_derive = pub.liveness.derive_targets

        pub.ROOT = self.tmp
        pub.BOARD_JSON = self.tmp / "leaderboard.json"
        pub.PUBLISHED_JSON = self.tmp / "published-board.json"
        pub.TARGETS_JSON = self.tmp / "board-probe-targets.json"

        if self.seed_board:
            pub.BOARD_JSON.write_text(json.dumps(GOOD_BOARD), encoding="utf-8")
        pub.TARGETS_JSON.write_text(json.dumps({
            "current_ladder_epoch": (
                {"value": self.epoch, "source": "test"} if self.epoch
                else {"value": None, "source": None}),
            "extra_seeds": [{"value": s, "source": "test"} for s in self.pinned],
        }), encoding="utf-8")

        boards, readable = self.boards, self.api_readable

        def probe(seed, version):
            if not readable:
                return {"seed": seed, "version": version, "key_shape": "epoch",
                        "error": "HTTP 503", "entries": None}
            b = boards.get((seed, version))
            if not b:
                return {"seed": seed, "version": version, "key_shape": "epoch",
                        "entries": 0, "players": 0, "player_names": [],
                        "builds_seen": [], "first_entry": None, "last_entry": None}
            return dict(b, seed=seed, version=version, key_shape="epoch",
                        entries=len(b["rows"]), players=1,
                        player_names=["p"], builds_seen=["v0.13.2"])

        def get_json(url, headers=None, timeout=20):
            if not readable:
                return None, "HTTP 503"
            import urllib.parse as up
            q = up.parse_qs(up.urlparse(url).query)
            key = (q["seed"][0], q["version"][0])
            b = boards.get(key)
            if not b:
                return {"ok": True, "entries": []}, None
            return {"ok": True, "entries": b["rows"]}, None

        pub.liveness.probe_board = probe
        pub.liveness.get_json = get_json
        pub.liveness.derive_targets = lambda a, b: (
            sorted({s for s, _ in boards} | {"weekly-2026-w30"}), [self.epoch or "L3"], [])
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            setattr(pub, k, v)
        pub.liveness.probe_board = self._saved_probe
        pub.liveness.get_json = self._saved_get
        pub.liveness.derive_targets = self._saved_derive
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


def run(argv=()):
    sys.argv = ["publish-live-board.py", *argv]
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = pub.main()
    return code, buf.getvalue()


def board_on_disk():
    try:
        return json.loads(pub.BOARD_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


ROWS = [{"score": 10, "player_name": "A", "date": "2026-07-30T09:00:00", "game_mode": "v0.13.2"}]

print("\n1. Unknown epoch -> refuses, exit 2, writes NOTHING")
with Sandbox(epoch=None, boards={("weekly-2026-w30", "L3"): {"rows": ROWS, "last_entry": "x"}}):
    code, out = run()
    check(code == 2, f"exit 2 on unknown epoch (got {code})")
    check(board_on_disk() == GOOD_BOARD, "existing good board left byte-identical")
    check(not pub.PUBLISHED_JSON.exists(), "no published-board.json written")
    check("REFUSING" in out, "says plainly that it is refusing")

print("\n2. API unreadable -> refuses, does NOT erase the good board")
with Sandbox(boards={("weekly-2026-w30", "L3"): {"rows": ROWS, "last_entry": "x"}},
             api_readable=False):
    code, _ = run()
    check(code == 3, f"exit 3 when the API cannot be read (got {code})")
    check(board_on_disk() == GOOD_BOARD,
          "THE BIG ONE: a transient outage does not replace real scores with nothing")

print("\n3a. Empty board on the SAME key -> REFUSES (this is the API losing rows)")
# The published board is (weekly-2026-w30, L3) with 3 real entries. The epoch has not
# moved and the API now says that exact key is empty. Nothing about the league changed,
# so the only honest reading is that the data went missing -- publish it and the record
# is gone. This is the half of old-test-3 that must never regress.
with Sandbox(epoch="L3", boards={}):
    code, out = run()
    check(code == 1, f"exit 1, not 3 -- 'nothing publishable' is not 'cannot read' (got {code})")
    check(board_on_disk() == GOOD_BOARD,
          "THE OTHER BIG ONE: real scores are not replaced by an empty board on the same key")
    check("SAME key" in out or "same key" in out.lower(), "names the same-key refusal")
    check(not pub.PUBLISHED_JSON.exists(), "wrote no published-board.json")

print("\n3b. Empty board on a NEW key -> PUBLISHES it, as live-empty")
# The L3 -> L4 fork. The published board (weekly-2026-w30, L3) is now closed history; the
# board players reach is on L4 and nobody has finished a run on it. Continuing to serve
# the L3 standings would present a closed epoch's results as this week's league.
with Sandbox(epoch="L4", boards={}):
    code, out = run()
    d = board_on_disk()
    check(code == 0, f"exit 0 -- an empty board on a new key IS publishable (got {code})")
    check(d["meta"]["board_key"]["ladder_epoch"] == "L4", "published the NEW epoch")
    check(d["entries"] == [], "published board is empty, as observed")
    check(d["data_status"] == "live-empty",
          f"status is live-empty, never 'live' with 0 rows (got {d['data_status']!r})")
    check(d["meta"]["total_entries"] == 0 and d["meta"]["total_players"] == 0,
          "counts say zero rather than carrying the old board's numbers forward")
    p = json.loads(pub.PUBLISHED_JSON.read_text(encoding="utf-8"))
    check(p["entries_at_publish"] == 0 and p["ladder_epoch"] == "L4",
          "published-board.json records the fork key and an honest zero")

print("\n3c. Several empty boards on the new epoch -> refuses to GUESS which is real")
# With zero rows the API is no evidence at all: every wrong key answers ok:true+empty.
# Choosing between them would be a guess wearing an observation's clothes.
FORK_EMPTIES = {("weekly-2026-w32", "L4"): {"rows": [], "last_entry": None},
                ("weekly-2026-w33", "L4"): {"rows": [], "last_entry": None}}
with Sandbox(epoch="L4", boards=FORK_EMPTIES):
    code, out = run()
    check(code == 1, f"refuses when nothing distinguishes the empty boards (got {code})")
    check(board_on_disk() == GOOD_BOARD, "good board untouched while the choice is undecidable")
    check("REFUSING" in out, "says plainly that it is refusing")
    check("weekly-2026-w32" in out and "weekly-2026-w33" in out,
          "names the candidates so a human can pin the right one")

# ...and a seed DECLARED with a source in board-probe-targets.json resolves it. The pin is
# the human channel; it narrows the choice and never widens it.
with Sandbox(epoch="L4", boards=FORK_EMPTIES, pinned=["weekly-2026-w32"]):
    code, _ = run()
    d = board_on_disk()
    check(code == 0 and d["seed"] == "weekly-2026-w32",
          "a sourced pin picks the fork board; an unsourced one could not (see derive_targets)")

print("\n4. Cross-epoch: a BUSIER old-epoch board must never be published")
with Sandbox(epoch="L3", boards={
        ("weekly-2026-w30", "L2"): {"rows": ROWS * 50, "last_entry": "2026-07-29T23:59:59"},
        ("weekly-fixture-later", "L3"): {"rows": ROWS * 2, "last_entry": "2026-07-30T10:00:00"}}):
    code, _ = run()
    d = board_on_disk()
    check(code == 0, "publishes the current-epoch board")
    check(d["meta"]["board_key"]["ladder_epoch"] == "L3", "published epoch is L3")
    check(d["meta"]["board_key"]["seed"] == "weekly-fixture-later",
          "chose the L3 board, NOT the 50-entry L2 one -- epochs are never merged")
    check(len(d["entries"]) == 2, f"published 2 entries, not 50 (got {len(d['entries'])})")

print("\n5. Several live boards on the epoch -> most recently active wins")
with Sandbox(epoch="L3", boards={
        ("weekly-2026-w30", "L3"): {"rows": ROWS * 9, "last_entry": "2026-07-30T08:00:00"},
        ("weekly-fixture-later", "L3"): {"rows": ROWS * 1, "last_entry": "2026-07-30T11:00:00"}}):
    code, _ = run()
    d = board_on_disk()
    check(d["seed"] == "weekly-fixture-later",
          "recency beats volume -- a fresh league board outranks a busy stale one")

print("\n6. Happy path -> both artifacts, honest metadata, no invented fields")
with Sandbox(epoch="L3", boards={
        ("weekly-2026-w30", "L3"): {"rows": ROWS * 3, "last_entry": "2026-07-30T09:36:29"}}):
    code, _ = run()
    d, p = board_on_disk(), json.loads(pub.PUBLISHED_JSON.read_text(encoding="utf-8"))
    check(code == 0, "exit 0")
    check(d["data_status"] == "live", "data_status=live only because rows were fetched")
    check(d["legacy"] is False, "not flagged legacy")
    check(isinstance(d.get("exclusions"), dict), "carries an exclusions block")
    check(d["exclusions"]["version_mismatched_files"] == 0, "withholds nothing")
    check(p["seed_provenance"]["blessed"] is False,
          "published seed is explicitly NOT a blessing -- it is an observation")
    check(p["ladder_epoch"] == "L3" and p["seed"] == "weekly-2026-w30", "records the key it served")
    check(d["entries"][0]["score"] >= d["entries"][-1]["score"], "entries ranked by score")

print("\n7. --check reports staleness instead of silently writing")
with Sandbox(epoch="L3", boards={
        ("weekly-2026-w30", "L3"): {"rows": ROWS * 7, "last_entry": "2026-07-30T09:36:29"}}):
    code, out = run(["--check"])
    check(code == 1, f"--check flags a stale published board (got {code})")
    check(board_on_disk() == GOOD_BOARD, "--check wrote nothing")
    check("STALE" in out, "names the staleness explicitly")

print("\n8. --dry-run never writes")
with Sandbox(epoch="L3", boards={
        ("weekly-2026-w30", "L3"): {"rows": ROWS, "last_entry": "x"}}):
    code, out = run(["--dry-run"])
    check(code == 0 and board_on_disk() == GOOD_BOARD, "--dry-run left the board alone")
    check(not pub.PUBLISHED_JSON.exists(), "--dry-run wrote no published-board.json")

print("\n9. No fallback literals: a refusal must not invent a board key")
with Sandbox(epoch=None, boards={}):
    run()
    check(not pub.PUBLISHED_JSON.exists(),
          "no default seed/epoch is ever written when the real value is unknown")

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: publish-live-board refuses rather than guesses, and never replaces real "
      "scores with an empty board.")
