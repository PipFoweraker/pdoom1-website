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
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD = REPO_ROOT / "public" / "leaderboard" / "data" / "leaderboard.json"
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

    # The failure mode that looks exactly like "nobody is playing".
    site_version = None
    vj = load_json(VERSION_JSON, {})
    lr = vj.get("latest_release") if isinstance(vj, dict) else None
    if isinstance(lr, dict):
        site_version = lr.get("version")

    board_version = meta.get("game_version")
    print()
    if board_version and site_version and board_version != site_version:
        print("  !! MISMATCH: board is %s but the current release is %s."
              % (board_version, site_version))
        print("     The board key is (seed, game_version) per pdoom1 PR #679, so a")
        print("     %s client's scores CANNOT land on a %s board. Players would"
              % (site_version, board_version))
        print("     submit and see nothing, with no error. If Stream A shows")
        print("     downloads and Stream B stays empty, suspect THIS before you")
        print("     suspect analytics.")
    elif board_version:
        print("  Board version matches the current release (%s)." % board_version)

    wk = load_json(WEEKLY)
    if isinstance(wk, dict):
        wv = wk.get("game_version")
        print("  weekly league version: %s%s"
              % (wv, "   <-- STALE" if (wv and site_version and wv != site_version)
                 else ""))

    if not entries:
        print()
        print("  No entries yet. Expected before launch. After you send links,")
        print("  scores should start appearing hours later -- that lag between")
        print("  Stream A and Stream B is the signal you are looking for.")
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
