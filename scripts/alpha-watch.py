#!/usr/bin/env python
"""Watch the two independent signals that the alpha is working.

THE IDEA
--------
Two streams, produced by completely separate systems, corroborating each other:

  STREAM A -- the website says people are arriving and downloading
              (Plausible: pageviews, and the Download custom event)
  STREAM B -- the leaderboard says people are playing
              (score submissions landing in the board JSON)

Neither is trustworthy alone. Download clicks overcount (people click twice,
people change their mind). Score submissions undercount badly (a player has to
finish a run AND not have opted out). But if downloads climb in the evening and
scores start appearing a few hours later, that lag is the shape of real people
installing and playing, and it is very hard to fake accidentally.

This deliberately does NOT try to match an individual person across the two
streams. Plausible is cookieless and anonymous; there is no shared identifier,
and manufacturing one would mean building tracking we don't want.

USAGE
-----
    python scripts/alpha-watch.py                 # both streams, current state
    python scripts/alpha-watch.py --days 3
    python scripts/alpha-watch.py annotate "posted to Bluesky" --channel bluesky

PLAUSIBLE API KEY (optional but recommended)
    Create one at https://analytics.pdoom1.com -> Settings -> API Keys, then:
        set PLAUSIBLE_API_KEY=...      (Windows, this shell only)
    Without it, Stream A is reported as UNAVAILABLE and you read it off the
    dashboard by eye instead -- everything else still works.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# CLAUDE.md: cp1252 console kills the FIRST non-ASCII print before any work happens.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD = REPO_ROOT / "public" / "leaderboard" / "data" / "leaderboard.json"
BOARD_LIVENESS = REPO_ROOT / "public" / "leaderboard" / "data" / "board-liveness.json"
WEEKLY = REPO_ROOT / "public" / "leaderboard" / "data" / "weekly" / "current.json"
ANNOTATIONS = REPO_ROOT / "public" / "data" / "analytics" / "annotations.json"
VERSION_JSON = REPO_ROOT / "public" / "data" / "version.json"

PLAUSIBLE_HOST = "https://analytics.pdoom1.com"
SITE_ID = "pdoom1.com"
GITHUB_RELEASES = "https://api.github.com/repos/PipFoweraker/pdoom1/releases"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def get_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %s" % e.code
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------- stream A
def stream_a(days):
    """Website side: are people arriving and clicking download?"""
    print("=" * 68)
    print("STREAM A -- website: arrivals and download clicks")
    print("=" * 68)

    key = os.environ.get("PLAUSIBLE_API_KEY")
    if not key:
        print("  Plausible API key not set -> UNAVAILABLE from here.")
        print("  Read it off %s by eye, or set PLAUSIBLE_API_KEY." % PLAUSIBLE_HOST)
        print()
        print("  What to look for on the dashboard:")
        print("    - Unique visitors climbing after you send links")
        print("    - Goal 'Download' firing (Settings -> Goals must define it,")
        print("      or the events are stored but never shown)")
        print("    - Top Sources / UTM campaigns, to tell channels apart")
    else:
        hdr = {"Authorization": "Bearer %s" % key}
        base = "%s/api/v1/stats/aggregate?site_id=%s&period=%dd&metrics=%s" % (
            PLAUSIBLE_HOST, urllib.parse.quote(SITE_ID), days,
            "visitors,pageviews,visits")
        data, err = get_json(base, hdr)
        if err:
            print("  Plausible query failed: %s" % err)
            print("  If this is HTTP 401 the key is wrong; if 404, the site id")
            print("  '%s' does not exist -- which would mean NOTHING has ever" % SITE_ID)
            print("  been recorded. Check that first.")
        else:
            r = data.get("results", {})
            print("  Last %d days:" % days)
            for k in ("visitors", "visits", "pageviews"):
                if k in r:
                    print("    %-12s %s" % (k, r[k].get("value")))

        goal_url = ("%s/api/v1/stats/breakdown?site_id=%s&period=%dd"
                    "&property=event:goal&metrics=visitors,events"
                    % (PLAUSIBLE_HOST, urllib.parse.quote(SITE_ID), days))
        gdata, gerr = get_json(goal_url, hdr)
        if gerr:
            print("  Goal breakdown unavailable: %s" % gerr)
        else:
            results = gdata.get("results", [])
            if not results:
                print("  No goals configured or no goal events yet.")
                print("  -> Plausible only SHOWS custom events that have a Goal defined.")
            else:
                print("  Goals:")
                for g in results:
                    print("    %-24s visitors=%-5s events=%s"
                          % (g.get("goal"), g.get("visitors"), g.get("events")))

    # GitHub asset counts are the ground truth for downloads.
    rel, err = get_json(GITHUB_RELEASES,
                        {"Accept": "application/vnd.github+json"})
    print()
    if err:
        print("  GitHub releases unreachable: %s" % err)
    elif not rel:
        print("  No releases found.")
    else:
        published = [r for r in rel if not r.get("draft")]
        drafts = [r for r in rel if r.get("draft")]
        print("  GitHub release assets (ground truth for actual downloads):")
        if not published:
            print("    !! NO PUBLISHED RELEASES -- only %d draft(s)." % len(drafts))
            print("       releases/latest excludes drafts, so the site cannot")
            print("       advertise or link a draft. Publish it.")
        for r in published[:2]:
            total = sum(a.get("download_count", 0) for a in r.get("assets", []))
            print("    %-12s assets=%-3d downloads=%d"
                  % (r.get("tag_name"), len(r.get("assets", [])), total))
            for a in r.get("assets", []):
                print("        %-38s %d" % (a.get("name", "")[:38],
                                            a.get("download_count", 0)))
            if not r.get("assets"):
                print("        (no assets attached -- nothing to download)")
        if drafts:
            print("    note: %d draft release(s) present and INVISIBLE to the site: %s"
                  % (len(drafts), ", ".join(d.get("tag_name") or "?" for d in drafts)))
    print()


def _board_liveness(max_age_hours=12):
    """The last dated observation of the live score API, refreshed if stale.

    check-board-liveness.py owns talking to the API; this just consumes its record. But
    a stale record read as current would recreate the very ambiguity this is here to
    remove, so anything older than max_age_hours triggers a re-run. Returns None if we
    genuinely do not know -- never a fabricated 'empty'.
    """
    rec = load_json(BOARD_LIVENESS)
    fresh = False
    if isinstance(rec, dict) and rec.get("checked_at"):
        try:
            ts = datetime.fromisoformat(rec["checked_at"].replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            fresh = (datetime.now(timezone.utc) - ts).total_seconds() < max_age_hours * 3600
        except Exception:
            fresh = False
    if fresh:
        return rec

    script = REPO_ROOT / "scripts" / "check-board-liveness.py"
    if not script.exists():
        return rec if isinstance(rec, dict) else None
    try:
        # Exit code 1 means "orphaned scores found" -- a successful, informative run.
        subprocess.run([sys.executable, str(script)], cwd=str(REPO_ROOT),
                       capture_output=True, text=True, timeout=180)
    except Exception as e:
        print("  (could not refresh board liveness: %s)" % e)
    return load_json(BOARD_LIVENESS) or (rec if isinstance(rec, dict) else None)


# ---------------------------------------------------------------- stream B
def stream_b():
    """Game side: are scores actually landing?"""
    print("=" * 68)
    print("STREAM B -- leaderboard: are people playing?")
    print("=" * 68)

    lb = load_json(LEADERBOARD)
    if lb is None:
        print("  %s missing or unparseable." % LEADERBOARD)
        return

    meta = lb.get("meta", {})
    entries = lb.get("entries", []) or []
    status = lb.get("data_status")
    print("  status        %s" % status)
    print("  generated     %s" % meta.get("generated"))
    print("  board version %s" % meta.get("game_version"))
    print("  entries       %d  (players: %s)"
          % (len(entries), meta.get("total_players")))

    # The deployed BUILD, printed for context only. It is NOT part of the board key:
    # GameConfig.get_board_version() returns "L" + LADDER_VERSION, so the client sends
    # "L3" (pdoom1 via issue #151, 2026-07-28). This function used to compare the board's
    # version half against version.json and shout MISMATCH -- which would have fired
    # permanently from the next ladder bump onward, on entirely correct data.
    vj = load_json(VERSION_JSON, {})
    lr = vj.get("latest_release") if isinstance(vj, dict) else None
    site_build = lr.get("version") if isinstance(lr, dict) else None
    print()
    print("  deployed build: %s   (context only -- NOT part of the board key)"
          % (site_build or "unknown"))

    wk = load_json(WEEKLY)
    site_seed = None
    if isinstance(wk, dict):
        site_seed = wk.get("seed")
        print("  weekly league seed: %s" % site_seed)

    # The board KEY is (seed, ladder_epoch). Both halves matter: a seed mismatch loses
    # scores just as completely as an epoch mismatch, and neither was ever printed here.
    live = _board_liveness()
    print()
    if live is None:
        print("  !! The live score API has NOT been checked, so nothing here is evidence")
        print("     about whether scores exist. Everything above reads only LOCAL files,")
        print("     and no local file has ever been fed by the API.")
        print("     Run: python scripts/check-board-liveness.py")
    else:
        key = live.get("board_key") or {}
        dep = live.get("deployed_board") or {}
        arch = live.get("archived_orphans") or {}
        new = live.get("new_orphans") or {}
        verdict = live.get("verdict")
        print("  LIVE SCORE API (checked %s)" % live.get("checked_at"))
        print("    board key: seed=%s  ladder epoch=%s"
              % (key.get("seed"), key.get("ladder_epoch") or "UNKNOWN"))
        if dep:
            print("    deployed board holds %s entries" % dep.get("entries"))

        if verdict in ("orphaned-scores", "unclassifiable"):
            n = new.get("entries_total") or 0
            print()
            print("  **** NEW SCORES ARE BEING LOST TO THE SITE ****")
            print("     %d entries are on live boards that nothing here publishes, and are" % n)
            print("     NOT in the anomaly archive. Real people finished real runs today.")
            for b in new.get("boards") or []:
                print("       (%s, %s): %d entries, %d player(s), %s .. %s"
                      % (b.get("seed"), b.get("version"), b.get("entries"),
                         b.get("players", 0), (b.get("first_entry") or "?")[:10],
                         (b.get("last_entry") or "?")[:10]))
            print()
            print("     This is NOT 'nobody is playing'. Do not go looking at analytics.")
            print("     The client's (seed, ladder_epoch) does not match the board this")
            print("     site publishes. Never fix it by re-stamping a version.")
        elif verdict == "epoch-unknown":
            print()
            print("  CANNOT CONFIRM: nothing tells this site which ladder epoch is current,")
            print("  so it cannot say the board it publishes is the board players submit")
            print("  to. That is an admission, not a mismatch finding.")
        elif verdict == "unreachable":
            print("    verdict: API UNREACHABLE -- board state is unknown, not empty.")
        elif verdict == "genuinely-empty":
            print("    verdict: genuinely empty. Nobody has submitted to the current board,")
            print("             and every other populated board is already acknowledged.")
        elif verdict == "live":
            print("    verdict: live -- the deployed board is the one receiving scores.")

        # Loud every run, but explicitly framed as settled history so it is never mistaken
        # for a fresh incident. Pip's ruling: these stay archived permanently.
        if (arch.get("entries_total") or 0) > 0:
            names = arch.get("player_names") or []
            print()
            print("  ARCHIVED ANOMALY (acknowledged, not a regression):")
            print("     %d entries from %d player(s): %s"
                  % (arch["entries_total"], len(names), ", ".join(names)))
            print("     Preserved at public/leaderboard/data/preserved/. Not a CI failure.")

    if not entries:
        print()
        if live and ((live.get("new_orphans") or {}).get("entries_total") or 0) > 0:
            # The old text here said "No entries yet. Expected before launch." That is a
            # lie whenever the API holds entries, and it is exactly the sentence that
            # would send an operator off to debug analytics instead of the board key.
            print("  The published board shows 0 entries, but that is a PUBLISHING failure,")
            print("  not an absence of players -- see the new orphaned boards above.")
        elif live is None or (live.get("board_key") or {}).get("epoch_known") is False:
            print("  The published board shows 0 entries. Whether that means anything is")
            print("  currently unknowable -- the current ladder epoch is not published")
            print("  anywhere this site can read.")
        else:
            print("  No entries yet, and the live API agrees. After you send links, scores")
            print("  should start appearing hours later -- that lag between Stream A and")
            print("  Stream B is the signal you are looking for.")
    print()


def cmd_annotate(args):
    ann = load_json(ANNOTATIONS, None) or {
        "_comment": "Dated record of what was published or sent, so traffic "
                    "spikes stay explainable years later. No personal data here.",
        "events": []
    }
    ann["events"].append({
        "date": now_iso(),
        "channel": args.channel,
        "note": args.note,
        "url": args.url or None,
    })
    Path(ANNOTATIONS).parent.mkdir(parents=True, exist_ok=True)
    Path(ANNOTATIONS).write_text(json.dumps(ann, indent=2) + "\n",
                                 encoding="utf-8", newline="\n")
    print("Recorded [%s] %s" % (args.channel, args.note))
    print("  -> %s (%d event(s))" % (ANNOTATIONS, len(ann["events"])))
    return 0


def cmd_watch(args):
    print("\np(Doom)1 alpha watch -- %s\n" % now_iso())
    stream_a(args.days)
    stream_b()
    ann = load_json(ANNOTATIONS, {"events": []})
    evs = ann.get("events", [])
    print("=" * 68)
    print("ANNOTATIONS -- what you did, so spikes stay explainable")
    print("=" * 68)
    if not evs:
        print("  Nothing recorded yet. Every time you post or send links, run:")
        print("    python scripts/alpha-watch.py annotate \"what you did\" --channel bluesky")
        print("  This cannot be reconstructed after the fact.")
    else:
        for e in evs[-8:]:
            print("  %s  [%-8s] %s" % (e["date"][:16], e["channel"], e["note"]))
    print()
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    ap.add_argument("--days", type=int, default=7,
                    help="window for Plausible stats (default: %(default)s)")

    n = sub.add_parser("annotate", help="record a dated publish/send event")
    n.add_argument("note")
    n.add_argument("--channel", default="other",
                   help="bluesky/twitter/email/hn/reddit/direct/other")
    n.add_argument("--url")
    n.set_defaults(func=cmd_annotate)

    args = ap.parse_args()
    if getattr(args, "func", None):
        return args.func(args)
    return cmd_watch(args)


if __name__ == "__main__":
    sys.exit(main())
