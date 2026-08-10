#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check-epoch-drift.py -- does the board key this site declares still match the one
the game publishes?

WHY THIS EXISTS
---------------
On 2026-08-07 pdoom1 published v0.14.0, a FORKING release: the ladder moved L3 ->
L4 and the featured seed rolled to weekly-2026-w32. pdoom1.com went on publishing
the CLOSED epoch's board for two days while 9 real scores landed on the live one,
invisible. Every workflow was green throughout and every green square was telling
the truth about itself. Nobody was told, because nothing was watching.

The value that went stale was `current_ladder_epoch` in board-probe-targets.json:
a string typed by a human in July, sourced to two issue comments. That file
PREDICTED this exact failure in writing --

    "if pdoom1 forks again and this is not updated, the site will confidently
     publish the WRONG board."

-- and the prediction did nothing, because a note saying "this will be wrong if X"
is documentation and only a check that fails when X is a trigger. This script is
that trigger.

WHAT MAKES IT POSSIBLE NOW
--------------------------
pdoom1's release_manifest.json carries BOTH halves of the board key as STRUCTURED
fields (`ladder_version`, `league_seed`) as of #1175 / v0.14.1, published as a
release asset at a stable latest-release URL. Before that the seed existed only in
prose inside `highlights`, and no honest comparison was possible.

    https://github.com/PipFoweraker/pdoom1/releases/latest/download/release_manifest.json

PULL, NOT PUSH, AND THAT IS DELIBERATE
--------------------------------------
pdoom1 already POSTs `repository_dispatch: game_version_sync` at every release.
Nothing in this repo listens, the curl carries no --fail, and the step has gone
green every time (see #290). `event=repository_dispatch` has a total_count of 0 on
this repository -- the channel has never once fired. A push whose failure is
invisible to the sender manufactures confidence; a pull fails on OUR side, where
we can see it. So this polls.

THE FAILURE MODE PREDICTED FOR THIS SCRIPT, IN ADVANCE
------------------------------------------------------
Stated in the Workshop 2 bet before a line was written: the way this becomes just
another green-and-wrong check is if a MISSING field reads as agreement. If pdoom1
renames `ladder_version`, or the asset 404s, the tempting behaviour is to shrug and
exit 0.

    ABSENCE IS NEVER AGREEMENT. A field we cannot read is `unknown`, exit 2.

OBSERVATION OUTRANKS STORED STATE
---------------------------------
If the manifest cannot be fetched we have observed nothing, and every verdict
below is about comparing two things -- so an unreachable manifest can NEVER report
drift or agreement. It reports `unreachable`. This is the precedence rule from
coordination#20: a verdict composed only from local files must not outrank one
derived from looking, because its remedy ("update the declaration") may be exactly
wrong when the real problem is that the source moved.

EXIT CODES
  0  the declared board key matches the published one
  1  DRIFT -- they disagree. The site is publishing, or about to publish, a board
     the shipped client does not post to
  2  cannot tell -- manifest unreachable, a field absent, or the site declares
     nothing. Never "fine"

RUN
    python scripts/check-epoch-drift.py
    python scripts/check-epoch-drift.py --manifest path/to/fixture.json   # offline
    python scripts/check-epoch-drift.py --json                            # machine
"""

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# CLAUDE.md: the Windows console is cp1252 and dies on the FIRST non-ASCII print,
# before doing any work. Reconfigure before anything else can print.
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
TARGETS_JSON = ROOT / "public" / "leaderboard" / "data" / "board-probe-targets.json"

# The one URL this script trusts. Not a literal board key -- a POINTER to whoever
# publishes one. It always resolves to the newest release, so it needs no edit when
# the version moves. Verified 200 unauthenticated 2026-08-09.
MANIFEST_URL = ("https://github.com/PipFoweraker/pdoom1/releases/latest/download/"
                "release_manifest.json")

# Field names are a cross-repo contract (coordination#48). If either moves, this
# script must go UNKNOWN and loudly, not quietly agree.
FIELD_EPOCH = "ladder_version"
FIELD_SEED = "league_seed"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def fetch_manifest(url, timeout=20):
    """GET only. Returns (data, error_string). Never raises."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %s" % e.code
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def normalise_epoch(raw):
    """The manifest publishes the NUMBER ("4"); the board key uses "L4".

    Kept explicit rather than clever: the client's own rule is
    GameConfig.get_board_version() -> "L" + LADDER_VERSION, so this mirrors one
    documented transformation and refuses anything that does not look like one.
    Returns (epoch_string, error_or_None).
    """
    if raw is None:
        return None, "absent"
    s = str(raw).strip()
    if not s:
        return None, "empty"
    if s.upper().startswith("L") and s[1:].isdigit():
        return "L" + s[1:], None          # already epoch-shaped
    if s.isdigit():
        return "L" + s, None              # the documented shape
    return None, "unrecognised shape %r" % s


def site_declaration(targets):
    """What this site currently claims. Returns (epoch, seeds, notes)."""
    notes = []
    cur = (targets or {}).get("current_ladder_epoch") or {}
    epoch = cur.get("value")
    if not epoch:
        notes.append("board-probe-targets.json declares no current_ladder_epoch")
    seeds = []
    for item in ((targets or {}).get("extra_seeds") or []):
        if isinstance(item, dict) and item.get("value"):
            # Same rule the probe applies: a pinned value with no source is a
            # hardcoded literal wearing a costume, and is not a declaration.
            if item.get("source"):
                seeds.append(item["value"])
            else:
                notes.append("ignored pinned seed %r: no source recorded"
                             % item.get("value"))
    return epoch, seeds, notes


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", help="read a local manifest instead of fetching "
                                       "(for tests; never used in CI)")
    ap.add_argument("--url", default=MANIFEST_URL, help="override the manifest URL")
    ap.add_argument("--targets", default=str(TARGETS_JSON))
    ap.add_argument("--json", action="store_true", help="emit a machine-readable result")
    args = ap.parse_args()

    targets = load_json(args.targets, {}) or {}
    site_epoch, site_seeds, site_notes = site_declaration(targets)

    if args.manifest:
        manifest, err = load_json(args.manifest), None
        if manifest is None:
            manifest, err = None, "could not read %s" % args.manifest
        source = args.manifest
    else:
        manifest, err = fetch_manifest(args.url)
        source = args.url

    result = {
        "checked_at": now_iso(),
        "manifest_source": source,
        "site_epoch": site_epoch,
        "site_seeds": site_seeds,
        "published_epoch": None,
        "published_seed": None,
        "notes": list(site_notes),
    }

    print("Epoch drift check -- %s" % now_iso())
    print("=" * 74)
    print("  site declares epoch   %s" % (site_epoch or "NOTHING"))
    print("  site pins seed(s)     %s" % (", ".join(site_seeds) or "none"))
    print("  manifest              %s" % source)
    for n in site_notes:
        print("  note: %s" % n)

    # ---- unreachable FIRST. Observation outranks stored state. ---------------
    if err or not isinstance(manifest, dict):
        result["verdict"], code = "unreachable", 2
        print()
        print("  CANNOT TELL: the published manifest could not be read (%s)." % err)
        print("  This is NOT evidence that the declaration is correct, and NOT")
        print("  evidence of drift. Nothing was observed, so nothing is claimed.")
        print("  The site's declaration is untouched.")
        _emit(result, args)
        return code

    pub_epoch_raw = manifest.get(FIELD_EPOCH)
    pub_seed = manifest.get(FIELD_SEED)
    pub_epoch, epoch_err = normalise_epoch(pub_epoch_raw)
    result["published_epoch"] = pub_epoch
    result["published_seed"] = pub_seed
    result["manifest_version"] = manifest.get("version")

    print("  manifest version      %s" % (manifest.get("version") or "unknown"))
    print("  published epoch       %s" % (pub_epoch or "UNREADABLE"))
    print("  published seed        %s" % (pub_seed or "ABSENT"))
    print("-" * 74)

    # ---- absence is never agreement -----------------------------------------
    missing = []
    if pub_epoch is None:
        missing.append("%s (%s)" % (FIELD_EPOCH, epoch_err))
    if not pub_seed:
        missing.append("%s (absent)" % FIELD_SEED)
    if missing:
        result["verdict"], code = "unknown", 2
        result["missing"] = missing
        print()
        print("  CANNOT TELL: the manifest does not carry %s." % " and ".join(missing))
        print("  These field names are a cross-repo contract (coordination#48).")
        print("  A field this script cannot read is UNKNOWN -- it is never treated")
        print("  as agreement, because that is precisely how this check would")
        print("  become the thing it exists to catch.")
        print("  If pdoom1 renamed or moved a field, that is a breaking change and")
        print("  wants an issue, not a silent pass.")
        _emit(result, args)
        return code

    if not site_epoch:
        result["verdict"], code = "site-undeclared", 2
        print()
        print("  CANNOT TELL: this site declares no current ladder epoch, so there")
        print("  is nothing to compare the published one against.")
        print("  Populate current_ladder_epoch in board-probe-targets.json WITH A")
        print("  SOURCE. The published value is %s / %s." % (pub_epoch, pub_seed))
        _emit(result, args)
        return code

    # ---- the comparison ------------------------------------------------------
    epoch_ok = (site_epoch == pub_epoch)
    seed_ok = (pub_seed in site_seeds)
    result["epoch_agrees"] = epoch_ok
    result["seed_pinned"] = seed_ok

    if epoch_ok and seed_ok:
        result["verdict"], code = "in-step", 0
        print()
        print("  OK: the site declares (%s) and pins %s; the shipped client posts to"
              % (site_epoch, pub_seed))
        print("  (%s, %s). They agree." % (pub_seed, pub_epoch))
        _emit(result, args)
        return code

    result["verdict"], code = "drift", 1
    print()
    print("  !! DRIFT. The board key this site publishes does not match the one the")
    print("     shipped client posts to. Scores are landing where nobody reads them,")
    print("     or will as soon as a player updates.")
    print()
    if not epoch_ok:
        print("     epoch: site says %s, release %s says %s"
              % (site_epoch, manifest.get("version") or "?", pub_epoch))
    if not seed_ok:
        print("     seed : %s is not pinned by this site (pinned: %s)"
              % (pub_seed, ", ".join(site_seeds) or "none"))
    print()
    print("     FIX, in this order:")
    print("       1. add the seed to extra_seeds in board-probe-targets.json, WITH")
    print("          a source -- the probe cannot discover a seed it has never seen")
    print("       2. set current_ladder_epoch.value, with a source and declared_on")
    print("       3. ARCHIVE the outgoing board before the epoch flips, or a live")
    print("          board becomes an unarchived orphan and the page tells visitors")
    print("          their scores are hidden")
    print("       4. get Pip's blessing on the seed -- docs/LEAGUE_SEED_LEDGER.md;")
    print("          a website-derived seed once stranded 23 submissions")
    _emit(result, args)
    return code


def _emit(result, args):
    if args.json:
        print()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
