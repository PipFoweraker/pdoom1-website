#!/usr/bin/env python
"""Pull Plausible stats into a git-committed snapshot, so the traffic history
survives losing the analytics VPS -- and so a viral spike is captured forever.

WHY
---
Analytics live on a single self-hosted Plausible instance with no backups. The
history Pip most wants -- the shape of a growth spike, its sources, its timing --
is exactly the thing that is unrecoverable if that box dies. It is also most at
risk precisely when it matters most: a spike is when the VPS is under the most
load and most likely to fall over.

This makes a second copy that lives in git. Each run appends a dated snapshot,
so the record accretes commit by commit and survives the origin being lost. It
is not a substitute for a real database backup, but it is a cheap hedge that
also happens to be the raw material for the eventual growth histogram.

It reads the Plausible Stats API read-only. It never posts, never deletes, and
does nothing at all without an API key -- an unconfigured run is a dry run.

SETUP (one-time, Pip)
    Create a key at https://analytics.pdoom1.com -> Settings -> API Keys, then
    set PLAUSIBLE_API_KEY (locally: `set PLAUSIBLE_API_KEY=...`; in CI: a repo
    secret). That is the only thing standing between this and running.

USAGE
    python scripts/snapshot-plausible.py            # snapshot the last 30 days
    python scripts/snapshot-plausible.py --period 7d
    python scripts/snapshot-plausible.py --dry-run  # show what it would fetch
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "public" / "data" / "analytics" / "history"
LATEST = REPO_ROOT / "public" / "data" / "analytics" / "latest.json"

HOST = "https://analytics.pdoom1.com"
SITE_ID = "pdoom1.com"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def api(path, params, key):
    url = "%s/api/v1/stats/%s?%s" % (HOST, path, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer %s" % key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def gather(key, period):
    """Everything worth keeping for one snapshot. Each call is defensive: a
    single failing breakdown must not lose the whole snapshot."""
    common = {"site_id": SITE_ID, "period": period}
    out = {"site": SITE_ID, "period": period, "sections": {}, "errors": {}}

    def grab(name, path, extra):
        try:
            out["sections"][name] = api(path, dict(common, **extra), key)
        except urllib.error.HTTPError as e:
            out["errors"][name] = "HTTP %s %s" % (e.code, e.read().decode("utf-8")[:120])
        except Exception as e:
            out["errors"][name] = str(e)

    grab("aggregate", "aggregate",
         {"metrics": "visitors,visits,pageviews,bounce_rate,visit_duration"})
    grab("timeseries", "timeseries", {"metrics": "visitors,pageviews"})
    grab("sources", "breakdown",
         {"property": "visit:source", "metrics": "visitors", "limit": "50"})
    grab("pages", "breakdown",
         {"property": "event:page", "metrics": "visitors,pageviews", "limit": "50"})
    grab("countries", "breakdown",
         {"property": "visit:country", "metrics": "visitors", "limit": "50"})
    grab("utm_campaign", "breakdown",
         {"property": "visit:utm_campaign", "metrics": "visitors", "limit": "50"})
    grab("goals", "breakdown",
         {"property": "event:goal", "metrics": "visitors,events", "limit": "50"})
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", default="30d",
                    help="Plausible period, e.g. 7d/30d/6mo/12mo (default: %(default)s)")
    ap.add_argument("--date", help="snapshot date label YYYY-MM-DD "
                    "(default: from --period end; pass explicitly in CI)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("PLAUSIBLE_API_KEY", "").strip()

    if not key or args.dry_run:
        print("DRY RUN -- no snapshot written." if args.dry_run
              else "PLAUSIBLE_API_KEY not set -- nothing to do (this is a dry run).")
        print("Would fetch from %s for site %s, period %s:" % (HOST, SITE_ID, args.period))
        for s in ("aggregate", "timeseries", "sources", "pages", "countries",
                  "utm_campaign", "goals"):
            print("  - %s" % s)
        if not key:
            print("\nSet PLAUSIBLE_API_KEY (Settings -> API Keys on the dashboard) to enable.")
        return 0

    # A snapshot must be stamped, but Date.now()-style calls are avoided in this
    # repo's generators; require the label so CI passes a deterministic date.
    label = args.date
    if not label:
        try:
            snap = gather(key, args.period)
            ts = snap["sections"].get("timeseries", {}).get("results", [])
            label = ts[-1]["date"] if ts else None
        except Exception:
            label = None
        if not label:
            print("ERROR: could not derive a date; pass --date YYYY-MM-DD.",
                  file=sys.stderr)
            return 2
    else:
        snap = gather(key, args.period)

    snap["snapshot_date"] = label
    if snap["errors"]:
        print("Completed with %d section error(s): %s"
              % (len(snap["errors"]), ", ".join(snap["errors"])))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = OUT_DIR / ("%s.json" % label)
    content = json.dumps(snap, indent=2, ensure_ascii=False) + "\n"
    dated.write_text(content, encoding="utf-8", newline="\n")
    LATEST.write_text(content, encoding="utf-8", newline="\n")

    agg = snap["sections"].get("aggregate", {}).get("results", {})
    print("Wrote %s" % dated.relative_to(REPO_ROOT))
    if agg:
        print("  visitors=%s pageviews=%s"
              % (agg.get("visitors", {}).get("value"),
                 agg.get("pageviews", {}).get("value")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
