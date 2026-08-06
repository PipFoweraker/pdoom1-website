#!/usr/bin/env python
"""Derive public/data/analytics/history/index.json from the committed snapshots.

WHY THIS FILE EXISTS
--------------------
snapshot-analytics.yml commits one dated JSON per day into
public/data/analytics/history/. A static host serves no directory listing, so a
browser has no way to discover which of those files exist. /metrics/ needs to
know, and it must not guess: probing dates and treating a 404 as "no data" makes
a fetch failure indistinguishable from a day with no traffic.

It also solves a second problem. Each snapshot is a 30-day window ending the day
BEFORE its snapshot_date, so consecutive files overlap almost entirely. The
daily series a reader wants spans every day any snapshot has ever reported --
today 43 days, from before the first snapshot was taken -- which no single file
contains. Deriving that in the browser would mean fetching every snapshot, a
number that grows by one per day forever. It is derived here once instead, and
committed, so the page makes exactly two requests no matter how long the archive
gets.

WHAT IT REFUSES TO DO
---------------------
  - It never sums across snapshots. `visitors` is a DEDUPLICATED count over a
    window; one person visiting on two days is 1 visitor in a 30-day total and 2
    in a sum of dailies. Only per-day values are carried across, never totals.
  - It never interpolates. A date inside the span that no snapshot reports comes
    out in `gap_dates`, not as a zero. A recorded zero and a missing day are
    different facts and stay different all the way to the page.
  - It never silently resolves a disagreement. If two snapshots report different
    numbers for the same date, that date lands in `conflict_dates` with both
    values and its series entry carries nulls -- a disputed value is not a known
    value. (Measured 2026-08-06: 0 conflicts across 43 days and 14 snapshots.
    This exists for the day that stops being true.)
  - It never records absence as health. The 8 snapshots written before schema 2
    carry no `coverage` block at all, so their missing-day accounting is
    UNKNOWN, not empty. They get `"coverage": null` and the page renders that
    as unrecorded.

DETERMINISM
-----------
The output contains no wall clock. A generation timestamp would make --check
fail on every run and the guard would be discarded within a week. Same inputs,
same bytes.

USAGE
    python scripts/generate-analytics-index.py            # write the index
    python scripts/generate-analytics-index.py --check    # fail if out of date
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = REPO_ROOT / "public" / "data" / "analytics" / "history"
INDEX_PATH = HISTORY_DIR / "index.json"

SCHEMA = 1

NOTE = (
    "Derived from every snapshot in this directory by "
    "scripts/generate-analytics-index.py. Snapshots overlap heavily -- each is a "
    "30-day window ending the day before its snapshot_date -- so daily values are "
    "carried across, never summed. A date no snapshot reports is listed in "
    "gap_dates rather than written as a zero; a recorded zero and a missing day "
    "are different facts. Where snapshots disagree the date is listed in "
    "conflict_dates and its series values are null."
)


def _iso_days(start: str, end: str):
    """Every ISO date from start to end inclusive."""
    d = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while d <= last:
        yield d.isoformat()
        d += timedelta(days=1)


def _load_snapshots():
    """Read every dated snapshot. Returns (records, load_errors)."""
    records, load_errors = [], []
    for path in sorted(HISTORY_DIR.glob("*.json")):
        if path.name == INDEX_PATH.name:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # A corrupt snapshot is reported, never skipped silently -- silence
            # here would shorten the series with no trace of why.
            load_errors.append({"file": path.name, "error": str(exc)})
            continue
        if not isinstance(data, dict):
            load_errors.append({"file": path.name, "error": "top level is not an object"})
            continue
        records.append((path, data))
    return records, load_errors


def _timeseries(data):
    """The timeseries rows of a snapshot, tolerating a missing section."""
    section = (data.get("sections") or {}).get("timeseries") or {}
    results = section.get("results")
    return results if isinstance(results, list) else []


def _coverage_for(data):
    """The snapshot's coverage block, or None when it did not record one.

    None means UNRECORDED. It must never be normalised into an empty dict: an
    empty missing_dates list asserts "no days were omitted", which the schema-1
    snapshots never claimed.
    """
    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        return None
    return {
        "days_returned": coverage.get("days_returned"),
        "first_date": coverage.get("first_date"),
        "last_date": coverage.get("last_date"),
        "missing_dates": coverage.get("missing_dates") or [],
        "zero_dates": coverage.get("zero_dates") or [],
        "note": coverage.get("note"),
    }


def build_index():
    records, load_errors = _load_snapshots()

    snapshots = []
    # date -> {(pageviews, visitors): [snapshot_date, ...]}
    observed = {}
    reported_missing = set()

    for path, data in records:
        snapshot_date = data.get("snapshot_date") or path.stem
        coverage = _coverage_for(data)
        if coverage:
            for d in coverage["missing_dates"]:
                reported_missing.add(d)

        errors = data.get("errors")
        error_sections = sorted(errors.keys()) if isinstance(errors, dict) else []

        rows = _timeseries(data)
        for row in rows:
            if not isinstance(row, dict):
                continue
            day = row.get("date")
            if not isinstance(day, str) or not day:
                continue
            pv = row.get("pageviews")
            vis = row.get("visitors")
            key = (pv, vis)
            observed.setdefault(day, {}).setdefault(key, []).append(snapshot_date)

        snapshots.append({
            "snapshot_date": snapshot_date,
            "file": path.name,
            # None for the 8 pre-schema-2 files. The page prints "not recorded".
            "snapshot_schema": data.get("schema"),
            "captured_at_utc": data.get("captured_at_utc"),
            "period": data.get("period"),
            "days_in_timeseries": len(rows),
            "coverage": coverage,
            "error_sections": error_sections,
        })

    snapshots.sort(key=lambda s: s["snapshot_date"])

    days, gap_dates, conflict_dates = [], [], []
    first_date = last_date = None

    if observed:
        first_date = min(observed)
        last_date = max(observed)
        for day in _iso_days(first_date, last_date):
            variants = observed.get(day)
            if not variants:
                gap_dates.append(day)
                continue
            if len(variants) > 1:
                # Two snapshots disagree. Neither value is published; the day is
                # rendered as disputed, which is the honest reading of "we hold
                # two different records and cannot tell you which is right".
                conflict_dates.append({
                    "date": day,
                    "values": [
                        {"pageviews": pv, "visitors": vis, "snapshots": sorted(srcs)}
                        for (pv, vis), srcs in sorted(
                            variants.items(), key=lambda kv: str(kv[0])
                        )
                    ],
                })
                days.append({
                    "date": day, "pageviews": None, "visitors": None,
                    "snapshots": sum(len(s) for s in variants.values()),
                    "conflict": True,
                })
                continue
            (pv, vis), srcs = next(iter(variants.items()))
            days.append({
                "date": day, "pageviews": pv, "visitors": vis,
                "snapshots": len(srcs), "conflict": False,
            })

    return {
        "schema": SCHEMA,
        "generated_by": "scripts/generate-analytics-index.py",
        "note": NOTE,
        "snapshot_count": len(snapshots),
        "latest_snapshot": snapshots[-1]["snapshot_date"] if snapshots else None,
        "unreadable_files": load_errors,
        "snapshots": snapshots,
        "series": {
            "first_date": first_date,
            "last_date": last_date,
            "days": days,
            "gap_dates": gap_dates,
            "conflict_dates": conflict_dates,
            # Days a snapshot's own coverage block flagged as omitted by the API.
            # Some may since have been filled by a later snapshot; that is why
            # this is kept separate from gap_dates rather than merged into it.
            "reported_missing_dates": sorted(reported_missing),
        },
    }


def render(index):
    return json.dumps(index, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the committed index is not what this would write")
    args = parser.parse_args()

    if not HISTORY_DIR.is_dir():
        print(f"FAIL: no snapshot directory at {HISTORY_DIR}")
        return 2

    index = build_index()
    text = render(index)

    if index["unreadable_files"]:
        for bad in index["unreadable_files"]:
            print(f"WARN: unreadable snapshot {bad['file']}: {bad['error']}")

    if args.check:
        if not INDEX_PATH.exists():
            print(f"FAIL: {INDEX_PATH.relative_to(REPO_ROOT)} does not exist.")
            print("      Run: python scripts/generate-analytics-index.py")
            return 1
        current = INDEX_PATH.read_text(encoding="utf-8")
        if current != text:
            print(f"FAIL: {INDEX_PATH.relative_to(REPO_ROOT)} is out of step with the snapshots.")
            print("      Run: python scripts/generate-analytics-index.py")
            return 1
        series = index["series"]
        print(f"OK: index covers {index['snapshot_count']} snapshot(s), "
              f"{len(series['days'])} day(s) {series['first_date']}..{series['last_date']}, "
              f"{len(series['gap_dates'])} gap(s), {len(series['conflict_dates'])} conflict(s).")
        return 0

    INDEX_PATH.write_text(text, encoding="utf-8")
    series = index["series"]
    print(f"Wrote {INDEX_PATH.relative_to(REPO_ROOT)}")
    print(f"  snapshots : {index['snapshot_count']} (latest {index['latest_snapshot']})")
    print(f"  series    : {len(series['days'])} day(s) "
          f"{series['first_date']}..{series['last_date']}")
    print(f"  gaps      : {len(series['gap_dates'])}")
    print(f"  conflicts : {len(series['conflict_dates'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
