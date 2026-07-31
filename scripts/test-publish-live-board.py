#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Destructive tests for scripts/publish-live-board.py.

WHY THIS EXISTS
---------------
publish-live-board.py was written and shipped on 2026-07-30 with ZERO tests, and it is
what stands between players and a visible league board. Its docstring claims four safety
properties:

  1. refuses and writes nothing when the ladder epoch is unknown
  2. refuses and writes nothing when the score API cannot be read
  3. NEVER overwrites a good board with an empty one
  4. never publishes a board from a different epoch

Those were assertions in prose. CLAUDE.md's testing discipline says a claimed safety
property needs a FORCED failure, because a docstring is documentation and not evidence.
Every test below forces the failure rather than exercising the happy path.

The property that matters most is (3). A crash is survivable and loud. Silently replacing
a board that holds real player scores with an empty one -- on a transient network blip --
destroys the record and looks exactly like "nobody is playing", which is the original bug
this whole subsystem exists to prevent.

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

    def __init__(self, epoch="L3", boards=None, api_readable=True, seed_board=True):
        self.epoch, self.boards, self.api_readable = epoch, boards or {}, api_readable
        self.seed_board = seed_board

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
                else {"value": None, "source": None})
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

print("\n3. Epoch known but every board empty -> still does not publish an empty board")
with Sandbox(boards={}):
    code, _ = run()
    check(code != 0, f"non-zero when there is nothing to publish (got {code})")
    check(board_on_disk() == GOOD_BOARD, "good board preserved, not zeroed")

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
