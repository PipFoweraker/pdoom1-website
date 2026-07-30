#!/usr/bin/env python
"""Pull Plausible stats into a git-committed snapshot, so the traffic history
survives losing the analytics VPS -- and so a viral spike is captured forever.

WHY
---
Analytics live on a single self-hosted Plausible instance with no backups (see
docs/TECH_DEBT.md A1). The history Pip most wants -- the shape of a growth
spike, its sources, its timing -- is exactly the thing that is unrecoverable if
that box dies. It is also most at risk precisely when it matters most: a spike
is when the VPS is under the most load and most likely to fall over.

This makes a second copy that lives in git. Each run writes a dated snapshot,
so the record accretes commit by commit and survives the origin being lost. It
is not a substitute for a real database backup, but it is a cheap hedge that
also happens to be the raw material for the eventual growth histogram.

It reads the Plausible Stats API read-only. It never posts and never deletes.

WHAT A SNAPSHOT COVERS (and what it does not)
---------------------------------------------
The daily run asks for `--period 30d`, which the API answers with the 30 days
ENDING YESTERDAY (verified against real committed responses: the snapshot
labelled 2026-07-28 carries 2026-06-28..2026-07-27). Two consequences:

  * Every day of traffic is captured by ~30 consecutive snapshots, so a single
    lost run loses nothing. That redundancy is the point.
  * The hedge only reaches back 30 days from the FIRST snapshot ever taken
    (2026-07-23, so back to 2026-06-23). Anything older lives on the VPS alone
    until someone backfills it with `--range` (below).

FAILING LOUDLY IS THE WHOLE JOB
-------------------------------
A backup that silently stops is worse than no backup, because it manufactures
confidence. So this script refuses to write a file it cannot vouch for, and
signals which way it failed via the exit code:

    0  wrote a snapshot (or an explicit dry run)
    2  configuration error -- no API key, and --require-key was given
    3  fetch failed -- a REQUIRED section errored or came back malformed
    4  the response was structurally fine but carried no traffic at all

Codes 3 and 4 write NOTHING. In particular they do not overwrite latest.json,
because clobbering the last known-good copy with an empty one is the exact
"fallback literal" failure this repo keeps getting bitten by.

DATA HONESTY
------------
Missing days are recorded as missing, never interpolated or zero-filled. The
`coverage` block in each snapshot reports the observed date span, any dates the
API skipped inside that span, and which days were genuinely zero. A real zero
is data; a fabricated zero is a lie that would later be animated as fact.

SETUP (one-time, Pip)
    Create a key at https://analytics.pdoom1.com -> Settings -> API Keys, then
    set PLAUSIBLE_API_KEY (locally: `set PLAUSIBLE_API_KEY=...`; in CI: a repo
    secret -- already created 2026-07-23). CI runs with --require-key so a
    revoked or rotated key fails the run instead of quietly doing nothing.

USAGE
    python scripts/snapshot-plausible.py                  # last 30 days
    python scripts/snapshot-plausible.py --period 7d
    python scripts/snapshot-plausible.py --dry-run        # show what it'd fetch
    python scripts/snapshot-plausible.py --require-key --date 2026-07-29   # CI
    python scripts/snapshot-plausible.py --range YYYY-MM-DD:YYYY-MM-DD     # backfill

Covered by scripts/test-snapshot-plausible.py, which exercises every exit code
above against a stubbed API -- no key and no network required.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "public" / "data" / "analytics" / "history"
LATEST = REPO_ROOT / "public" / "data" / "analytics" / "latest.json"

HOST = "https://analytics.pdoom1.com"
SITE_ID = "pdoom1.com"

SCHEMA_VERSION = 2

# A snapshot missing either of these is not a snapshot -- it is a file that
# will look like a backup right up until someone needs it. Everything else may
# degrade individually without losing the run.
REQUIRED_SECTIONS = ("aggregate", "timeseries")

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_FETCH = 3
EXIT_EMPTY = 4

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def note(level, msg):
    """Print a message, and mirror it as a GitHub annotation when running in
    Actions, so a degraded run is visible in the run summary rather than buried
    a thousand lines into a log nobody opens."""
    print("%s: %s" % (level.upper(), msg))
    if os.environ.get("GITHUB_ACTIONS") == "true" and level in ("warning", "error"):
        print("::%s::%s" % (level, msg.replace("\n", " ")))


def api(path, params, key):
    url = "%s/api/v1/stats/%s?%s" % (HOST, path, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer %s" % key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def gather(key, period, custom_range=None):
    """Everything worth keeping for one snapshot.

    Each call is defensive so a single failing breakdown does not lose the
    whole snapshot -- but the errors are RECORDED, and validate() decides
    whether what survived is still worth committing.
    """
    common = {"site_id": SITE_ID, "period": period}
    if custom_range:
        common["date"] = "%s,%s" % custom_range
    out = {
        "schema": SCHEMA_VERSION,
        "site": SITE_ID,
        "period": period,
        "range": ("%s,%s" % custom_range) if custom_range else None,
        "source": HOST,
        "captured_at_utc": datetime.now(timezone.utc)
                           .replace(microsecond=0).isoformat(),
        "sections": {},
        "errors": {},
    }

    def grab(name, path, extra):
        try:
            out["sections"][name] = api(path, dict(common, **extra), key)
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")[:200]
            except Exception:
                detail = ""
            out["errors"][name] = "HTTP %s %s" % (e.code, detail)
        except Exception as e:
            out["errors"][name] = "%s: %s" % (type(e).__name__, e)

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


def _agg_value(snap, metric):
    """Aggregate metric as a number, or None if absent/non-numeric."""
    results = snap.get("sections", {}).get("aggregate", {}).get("results", {})
    if not isinstance(results, dict):
        return None
    entry = results.get(metric)
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    return value if isinstance(value, (int, float)) else None


def coverage(snap):
    """Describe what the timeseries actually covers, without inventing a day.

    Deliberately makes NO assumption about how Plausible defines a period: an
    expectation derived from "30d" would manufacture a phantom gap the day the
    API changed its window, and a phantom gap in a backup is a lie. Instead
    this reports the span the API itself returned plus any date missing INSIDE
    that span, which is unambiguous either way.
    """
    results = snap.get("sections", {}).get("timeseries", {}).get("results")
    if not isinstance(results, list) or not results:
        return {"days_returned": 0, "first_date": None, "last_date": None,
                "missing_dates": None, "zero_dates": None,
                "note": "no timeseries returned; nothing can be said about coverage"}

    parsed = []
    unparseable = []
    for row in results:
        raw = row.get("date") if isinstance(row, dict) else None
        try:
            parsed.append((date.fromisoformat(raw), row))
        except (TypeError, ValueError):
            unparseable.append(raw)

    if not parsed:
        return {"days_returned": len(results), "first_date": None, "last_date": None,
                "missing_dates": None, "zero_dates": None,
                "note": "timeseries rows carried no parseable date"}

    parsed.sort(key=lambda p: p[0])
    present = set(d for d, _ in parsed)
    first, last = parsed[0][0], parsed[-1][0]

    missing = []
    cursor = first
    while cursor <= last:
        if cursor not in present:
            missing.append(cursor.isoformat())
        cursor += timedelta(days=1)

    zero = [d.isoformat() for d, row in parsed
            if not row.get("visitors") and not row.get("pageviews")]

    out = {
        "days_returned": len(parsed),
        "first_date": first.isoformat(),
        "last_date": last.isoformat(),
        "missing_dates": missing,
        "zero_dates": zero,
        "note": "missing_dates are days the API omitted inside the span it "
                "returned; they are recorded, never interpolated",
    }
    if unparseable:
        out["unparseable_dates"] = unparseable
    return out


def validate(snap, allow_zero=False):
    """Decide whether this snapshot is worth committing.

    Returns (exit_code, [messages]). EXIT_OK means write it; anything else
    means write nothing, so the previous good copy survives.
    """
    problems = []

    for name in REQUIRED_SECTIONS:
        if name in snap.get("errors", {}):
            problems.append("required section '%s' failed: %s"
                            % (name, snap["errors"][name]))
        elif name not in snap.get("sections", {}):
            problems.append("required section '%s' is absent" % name)

    if problems:
        return EXIT_FETCH, problems

    agg = snap["sections"]["aggregate"].get("results")
    if not isinstance(agg, dict) or not agg:
        problems.append("aggregate carried no 'results' object")
    else:
        for metric in ("visitors", "pageviews"):
            if _agg_value(snap, metric) is None:
                problems.append("aggregate is missing a numeric '%s'" % metric)

    ts = snap["sections"]["timeseries"].get("results")
    if not isinstance(ts, list) or not ts:
        problems.append("timeseries carried no rows")

    if problems:
        return EXIT_FETCH, problems

    # Structurally sound -- but is there anything in it? All-zero across a whole
    # window is far more likely to mean broken ingestion, or a key scoped to the
    # wrong site, than a genuinely dead month. Committing it would hand a future
    # chart a confident, wrong zero.
    totals = [(_agg_value(snap, m) or 0)
              for m in ("visitors", "visits", "pageviews")]
    if not any(totals) and not allow_zero:
        return EXIT_EMPTY, [
            "every aggregate metric is zero across period '%s'" % snap.get("period"),
            "before believing that, check: is the tracker still in the page "
            "<head>? does the Plausible site id '%s' still exist? is the API key "
            "scoped to it?" % SITE_ID,
            "a 202 from the ingest endpoint means 'accepted', not 'stored', so "
            "it is not evidence that these numbers should be non-zero",
            "if the zero is real, re-run with --allow-zero to record it as data",
        ]

    return EXIT_OK, []


SECTION_NAMES = ("aggregate", "timeseries", "sources", "pages", "countries",
                 "utm_campaign", "goals")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", default="30d",
                    help="Plausible period, e.g. 7d/30d/6mo/12mo (default: %(default)s)")
    ap.add_argument("--date", help="snapshot date label YYYY-MM-DD "
                    "(default: derived from the timeseries; pass explicitly in CI)")
    ap.add_argument("--range", dest="range_",
                    help="backfill a custom window, START:END (YYYY-MM-DD:YYYY-MM-DD). "
                         "Writes history/range-START_END.json and leaves latest.json "
                         "alone. UNVERIFIED against the live API -- if Plausible "
                         "rejects the custom period this exits %d rather than "
                         "writing anything." % EXIT_FETCH)
    ap.add_argument("--require-key", action="store_true",
                    help="exit %d if PLAUSIBLE_API_KEY is unset. Use in CI, where a "
                         "missing key means the secret was revoked -- not that there "
                         "is nothing to do." % EXIT_CONFIG)
    ap.add_argument("--allow-zero", action="store_true",
                    help="permit a snapshot whose metrics are all zero")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    key = os.environ.get("PLAUSIBLE_API_KEY", "").strip()

    if not key and args.require_key:
        note("error", "PLAUSIBLE_API_KEY is unset or empty, but --require-key was "
                      "given. This is a configured backup that cannot run, so it is "
                      "a failure and not a no-op. Check the repository secret.")
        return EXIT_CONFIG

    if not key or args.dry_run:
        print("DRY RUN -- no snapshot written." if args.dry_run
              else "PLAUSIBLE_API_KEY not set -- nothing to do (this is a dry run).")
        print("Would fetch from %s for site %s, period %s:"
              % (HOST, SITE_ID, args.range_ or args.period))
        for s in SECTION_NAMES:
            print("  - %s" % s)
        if not key:
            print("\nSet PLAUSIBLE_API_KEY (Settings -> API Keys on the dashboard) "
                  "to enable, or pass --require-key to make this state fail.")
        return EXIT_OK

    custom_range = None
    if args.range_:
        parts = args.range_.split(":")
        if len(parts) != 2:
            note("error", "--range must look like START:END, "
                          "each date YYYY-MM-DD")
            return EXIT_CONFIG
        try:
            start, end = (date.fromisoformat(p.strip()) for p in parts)
        except ValueError:
            note("error", "--range dates must be YYYY-MM-DD")
            return EXIT_CONFIG
        if start > end:
            note("error", "--range START is after END")
            return EXIT_CONFIG
        custom_range = (start.isoformat(), end.isoformat())

    snap = gather(key, "custom" if custom_range else args.period, custom_range)

    code, problems = validate(snap, allow_zero=args.allow_zero)
    if code != EXIT_OK:
        note("error", "refusing to write a snapshot: " + "; ".join(problems[:2]))
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        print("\nNothing was written, so the previous snapshots and latest.json "
              "are untouched.", file=sys.stderr)
        return code

    # Optional sections may degrade without losing the run -- but never silently.
    if snap["errors"]:
        note("warning", "snapshot kept, but %d section(s) degraded: %s"
             % (len(snap["errors"]), ", ".join(sorted(snap["errors"]))))

    snap["coverage"] = coverage(snap)

    label = args.date
    if not label and not custom_range:
        ts = snap["sections"]["timeseries"]["results"]
        label = ts[-1].get("date") if isinstance(ts[-1], dict) else None
        if not label:
            note("error", "could not derive a date label; pass --date YYYY-MM-DD.")
            return EXIT_CONFIG
    snap["snapshot_date"] = label

    name = ("range-%s_%s.json" % custom_range) if custom_range else ("%s.json" % label)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = OUT_DIR / name
    content = json.dumps(snap, indent=2, ensure_ascii=False) + "\n"
    dated.write_text(content, encoding="utf-8", newline="\n")
    if not custom_range:
        # latest.json is only ever replaced by a snapshot that passed validation.
        LATEST.write_text(content, encoding="utf-8", newline="\n")

    cov = snap["coverage"]
    try:
        shown = dated.relative_to(REPO_ROOT)
    except ValueError:      # output redirected (tests); an absolute path is fine
        shown = dated
    print("Wrote %s" % shown)
    print("  visitors=%s pageviews=%s"
          % (_agg_value(snap, "visitors"), _agg_value(snap, "pageviews")))
    print("  covers %s..%s (%s days returned)"
          % (cov.get("first_date"), cov.get("last_date"), cov.get("days_returned")))
    if cov.get("missing_dates"):
        note("warning", "the API omitted %d date(s) inside the span it returned: %s"
             % (len(cov["missing_dates"]), ", ".join(cov["missing_dates"][:10])))
    if cov.get("zero_dates"):
        print("  %d day(s) recorded as a genuine zero" % len(cov["zero_dates"]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
