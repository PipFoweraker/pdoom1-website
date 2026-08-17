#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read the feedback JSONL store, collapsing duplicate receipt ids.

    python scripts/read-feedback.py --store <dir-or-file>
    python scripts/read-feedback.py --store <dir> --json
    python scripts/read-feedback.py --store <dir> --kind bug --since 2026-08-01

WHY DEDUP LIVES HERE AND NOT IN THE WRITER
------------------------------------------
docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §3: "Dedup happens at READ time,
never at write time" (INV-1e). public/ingest.php never consults an index and
never rejects a `rid` it has seen before, because an index lookup would be a new
failure mode standing between a visitor and a durable write -- and its failure
mode is *dropping a real message* to prevent a cheap duplicate.

The consequence is that duplicates are NORMAL in the store. A retry after a lost
response writes the same `rid` twice by design (contract §6 row F3, §1). This
script is the other half of that bargain: without it, "duplicates are acceptable"
is just an excuse for a store nobody can count.

Collapse rule: records sharing a `rid` become ONE record, and the one that
survives is the EARLIEST `server_ts`. Earliest, not latest, because the first
successful write is the one the visitor was answered about; a later duplicate is
the client retrying, not the visitor speaking again.

WHAT THIS SCRIPT WILL NOT DO
----------------------------
It never rewrites the store. Reading is not a licence to edit, and a reader that
"cleans up" is a reader that can lose. Purging is a separate, scheduled,
per-field job (contract §10, scripts/purge-feedback.py -- not this file).

It never silently skips a line it cannot parse. An unparseable line is a
candidate lost message: it is COUNTED, its line number is reported, and the exit
code goes non-zero unless --tolerate-damage is passed. "Absence of a marker is
never a clean bill of health" -- a reader that quietly dropped three corrupt
lines and printed a tidy total is the silent-loss failure wearing a report's
clothes.

EXIT CODES
    0  read cleanly
    2  the store could not be read at all (bad path, no permission)
    3  the store contains unparseable lines (suppress with --tolerate-damage)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


class StoreError(RuntimeError):
    pass


def store_files(root):
    """Every record file under the store root, oldest name first.

    Only `*.jsonl` counts as a record file. The endpoint deliberately keeps its
    canary (`.probe`), its daily salts (`.salt/`), its throttle buckets
    (`.throttle/`) and its notification log (`notifications/*.log`) out of that
    glob, so this pattern means "records" and nothing else.
    """
    root = Path(root)
    if not root.exists():
        raise StoreError("store does not exist: %s" % root)
    if root.is_file():
        return [root]
    files = sorted(p for p in root.rglob("*.jsonl") if p.is_file())
    return files


def read_lines(files):
    """Yield (path, lineno, text) for every non-blank physical line."""
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise StoreError("cannot read %s: %s" % (path, exc))
        for lineno, line in enumerate(raw.split("\n"), start=1):
            if line.strip():
                yield path, lineno, line


def _sort_key(rec):
    """Earliest first. A record with no server_ts sorts LAST, never first.

    A missing timestamp is unknown, not zero. Treating it as zero would let a
    damaged record win the collapse and silently replace a good one.
    """
    ts = rec.get("server_ts")
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return (1, 0)
    return (0, ts)


def collapse(records):
    """Collapse on `rid`, earliest `server_ts` wins.

    Records with no usable `rid` are NEVER merged with each other -- there is no
    join key, so treating them as one message would be an invention. They are
    kept individually and counted separately so the number is visible.
    """
    by_rid = {}
    order = []
    keyless = []
    duplicates = 0
    for rec in records:
        rid = rec.get("rid")
        if not isinstance(rid, str) or not rid.strip():
            keyless.append(rec)
            continue
        if rid not in by_rid:
            by_rid[rid] = [rec]
            order.append(rid)
        else:
            by_rid[rid].append(rec)
            duplicates += 1

    out = []
    for rid in order:
        group = sorted(by_rid[rid], key=_sort_key)
        winner = dict(group[0])
        if len(group) > 1:
            # Reported, not hidden: a rid seen five times means five delivery
            # attempts, which is a signal about the network, not noise.
            winner["_duplicate_writes"] = len(group)
            winner["_duplicate_server_ts"] = [
                r.get("server_ts") for r in group[1:]
            ]
        out.append(winner)
    out.extend(keyless)
    out.sort(key=_sort_key)
    return out, duplicates, len(keyless)


def parse_since(value):
    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        return int(text)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(text, fmt)
                       .replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    raise StoreError("--since %r is neither an epoch nor YYYY-MM-DD[THH:MM:SS]"
                     % value)


def load(store, kind=None, since=None):
    files = store_files(store)
    records = []
    damaged = []
    lines = 0
    for path, lineno, line in read_lines(files):
        lines += 1
        try:
            rec = json.loads(line)
        except ValueError:
            damaged.append({"file": str(path), "line": lineno,
                            "bytes": len(line.encode("utf-8"))})
            continue
        if not isinstance(rec, dict):
            damaged.append({"file": str(path), "line": lineno,
                            "bytes": len(line.encode("utf-8")),
                            "why": "line is valid JSON but not an object"})
            continue
        records.append(rec)

    collapsed, duplicates, keyless = collapse(records)

    if kind:
        wanted = {k.strip() for k in kind.split(",") if k.strip()}
        collapsed = [r for r in collapsed if r.get("kind") in wanted]
    if since is not None:
        collapsed = [r for r in collapsed
                     if isinstance(r.get("server_ts"), (int, float))
                     and not isinstance(r.get("server_ts"), bool)
                     and r["server_ts"] >= since]

    return {
        "store": str(Path(store)),
        "files": [str(p) for p in files],
        "lines_read": lines,
        "records_parsed": len(records),
        "records": collapsed,
        "record_count": len(collapsed),
        "duplicates_collapsed": duplicates,
        "records_without_rid": keyless,
        "unparseable_lines": damaged,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": 1,
    }


def human(doc, limit):
    out = []
    out.append("store: %s" % doc["store"])
    out.append("%d file(s), %d line(s), %d record(s) parsed, %d duplicate write(s) "
               "collapsed, %d record(s) after filters"
               % (len(doc["files"]), doc["lines_read"], doc["records_parsed"],
                  doc["duplicates_collapsed"], doc["record_count"]))
    if doc["records_without_rid"]:
        out.append("%d record(s) carry no rid and could not be collapsed"
                   % doc["records_without_rid"])
    if doc["unparseable_lines"]:
        out.append("DAMAGE: %d unparseable line(s) -- each one is a candidate "
                   "lost message:" % len(doc["unparseable_lines"]))
        for d in doc["unparseable_lines"][:20]:
            out.append("  %s:%d (%d bytes)%s"
                       % (d["file"], d["line"], d["bytes"],
                          "  " + d["why"] if d.get("why") else ""))
    shown = doc["records"] if limit <= 0 else doc["records"][:limit]
    for rec in shown:
        ts = rec.get("server_ts")
        when = (datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
                if isinstance(ts, (int, float)) and not isinstance(ts, bool)
                else "(no server_ts)")
        flags = rec.get("flags") or []
        out.append("")
        out.append("%s  %s  %s  %s%s"
                   % (rec.get("receipt") or "F-??????", when,
                      rec.get("kind") or "?", rec.get("page") or "?",
                      ("  flags=" + ",".join(str(f) for f in flags)) if flags else ""))
        text = (rec.get("text") or "").replace("\n", "\n    ")
        if text:
            out.append("    " + text)
        if rec.get("contact"):
            out.append("    contact: %s" % rec["contact"])
        if rec.get("credit"):
            out.append("    credit: %s (opted in to public credit)" % rec["credit"])
        if rec.get("_duplicate_writes"):
            out.append("    (%d duplicate write(s) collapsed; earliest kept)"
                       % rec["_duplicate_writes"])
    if limit > 0 and len(doc["records"]) > limit:
        out.append("")
        out.append("... %d more (raise --limit or pass --limit 0)"
                   % (len(doc["records"]) - limit))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description="Read the feedback store, collapsing duplicate rids "
                    "(contract §3, INV-1e).")
    ap.add_argument("--store", required=True,
                    help="store root directory, or a single .jsonl file")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON on stdout and nothing else")
    ap.add_argument("--kind", default="",
                    help="comma-separated kinds to keep, e.g. bug,feature")
    ap.add_argument("--since", default="",
                    help="epoch seconds or YYYY-MM-DD[THH:MM:SS] (UTC)")
    ap.add_argument("--limit", type=int, default=50,
                    help="records to print in human mode; 0 for all")
    ap.add_argument("--tolerate-damage", action="store_true",
                    help="report unparseable lines but still exit 0")
    args = ap.parse_args()

    try:
        doc = load(args.store, kind=args.kind, since=parse_since(args.since))
    except StoreError as exc:
        # Never on stdout: --json promises stdout is JSON or nothing.
        print("read-feedback: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(doc, ensure_ascii=False))
    else:
        print(human(doc, args.limit))

    if doc["unparseable_lines"]:
        print("read-feedback: %d unparseable line(s) in the store; each is a "
              "candidate lost message. Do not delete them -- they are the only "
              "copy." % len(doc["unparseable_lines"]), file=sys.stderr)
        if not args.tolerate_damage:
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
