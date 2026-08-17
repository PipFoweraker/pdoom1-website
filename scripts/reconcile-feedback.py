#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reconcile what the feedback store HOLDS against what was NOTIFIED.

    python scripts/reconcile-feedback.py --store <dir> --mail-log <path>
    python scripts/reconcile-feedback.py --store <dir> --mail-log <path> --json

WHAT FAULT THIS EXISTS FOR
--------------------------
docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §6 row F6: "MTA accepts then
discards". An SMTP server answers 250, so `mail()` returns true, so every log we
keep says the notification went out -- and the mail is dropped downstream. From
our side that is indistinguishable from success, which makes it exactly the
failure the binding directive names: *"If I ever lose a message silently, that's
now the worst thing my website can do."*

The store is the record (INV-1a: mail is a derived notification, never the
record), so nothing is LOST when this happens. What is lost is Pip READING it --
"received-and-never-read is silent loss wearing a different hat" (§9c). This
script is the only thing in the system that can see that gap, and it is why a
`200` is safe to return before anyone has read a word.

WHAT IT COMPARES
----------------
  store side   scripts/read-feedback.py's collapsed view, so a retried `rid`
               counts once. Duplicates are normal by design (§3) and must not
               read as three unnotified messages.
  notify side  one JSON object per line: {"rid": ..., "ok": true|false,
               "deferred": true|false}. public/ingest.php writes this to
               <store_root>/notifications/YYYY-MM.log in production, and to
               $PDOOM_MAIL_SINK under test (contract §11.1).

FOUR OUTCOMES, KEPT APART
-------------------------
  ok            stored, and a notification reports ok:true
  divergent     STORED BUT NEVER NOTIFIED -- no log line at all, or every line
                for it says ok:false. This is the row F6 fault.
  deferred      stored, and logged as handed to the thumbs digest (D-3). Counted
                as accounted-for by default; --strict-deferred moves it into
                `divergent`, which is what you want if you suspect the digest
                job itself has stopped.
  notified_not_stored
                a notification exists for a `rid` with no record. WORSE than
                divergent: somebody was told about a message that is not
                durable. Always a divergence, never suppressible.

A MISSING LOG IS NOT A CLEAN RUN
--------------------------------
If --mail-log points at nothing, every stored record is divergent and the exit
code is 1. It is never "no divergences found": absence of a marker is never a
clean bill of health, and a reconciler that returns 0 because it could not find
the file is the same green as a check that never ran.

EXIT CODES  (0 is the ONLY green; a schedule that ignores this is decoration)
    0  every stored record is accounted for
    1  at least one divergence
    2  the store or the log could not be read
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

# read-feedback.py has a hyphen in its name, so a plain import is impossible.
# Loaded rather than reimplemented on purpose: if the collapse rule ever changes,
# a private copy here would disagree with it and invent divergences that are
# really just duplicates.
import importlib.util  # noqa: E402


def _load_reader():
    path = Path(__file__).resolve().parent / "read-feedback.py"
    if not path.exists():
        raise RuntimeError(
            "%s is missing. This script reports divergence against the reader's "
            "collapsed view and will not substitute its own -- two collapse "
            "rules would disagree and the disagreement would look like data "
            "loss." % path)
    spec = importlib.util.spec_from_file_location("pdoom_read_feedback", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_notifications(path):
    """[{rid, ok, deferred, raw_line}] for every parseable line.

    Lines that do not parse, or carry no `rid`, are counted separately. They are
    not evidence that anything was notified, so they can never clear a record.
    """
    p = Path(path)
    if not p.exists():
        return [], 0, False
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RuntimeError("cannot read notification log %s: %s" % (p, exc))
    entries = []
    unusable = 0
    for line in raw.split("\n"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            unusable += 1
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("rid"), str):
            unusable += 1
            continue
        entries.append(obj)
    return entries, unusable, True


def reconcile(store, mail_log, strict_deferred=False):
    reader = _load_reader()
    doc = reader.load(store)
    stored = doc["records"]

    entries, unusable, log_present = load_notifications(mail_log)

    by_rid = {}
    for e in entries:
        by_rid.setdefault(e["rid"], []).append(e)

    ok_rids, deferred_rids, divergent, attempted_and_failed = [], [], [], []
    for rec in stored:
        rid = rec.get("rid")
        if not isinstance(rid, str) or not rid.strip():
            # No join key, so no notification can ever be matched to it. That is
            # a divergence by construction, not a pass.
            divergent.append(rec.get("receipt") or "(record with no rid)")
            continue
        lines = by_rid.get(rid, [])
        succeeded = [e for e in lines if e.get("ok") is True]
        deferred = [e for e in succeeded if e.get("deferred") is True]
        if not succeeded:
            divergent.append(rid)
            if lines:
                attempted_and_failed.append(rid)
        elif deferred and len(deferred) == len(succeeded):
            if strict_deferred:
                divergent.append(rid)
            else:
                deferred_rids.append(rid)
        else:
            ok_rids.append(rid)

    stored_rids = {r.get("rid") for r in stored if isinstance(r.get("rid"), str)}
    notified_not_stored = sorted(set(by_rid) - stored_rids)

    return {
        "store": str(store),
        "mail_log": str(mail_log),
        "mail_log_present": log_present,
        "stored": len(stored),
        "notified": len(entries),
        "notifications_unusable": unusable,
        "ok": len(ok_rids),
        "deferred": sorted(deferred_rids),
        "divergent": sorted(divergent),
        "attempted_and_failed": sorted(attempted_and_failed),
        "notified_not_stored": notified_not_stored,
        "duplicates_collapsed": doc["duplicates_collapsed"],
        "unparseable_store_lines": len(doc["unparseable_lines"]),
        "strict_deferred": bool(strict_deferred),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": 1,
    }


def human(doc):
    out = []
    out.append("store:    %s  (%d record(s), %d duplicate write(s) collapsed)"
               % (doc["store"], doc["stored"], doc["duplicates_collapsed"]))
    out.append("mail log: %s  (%s, %d entr(ies))"
               % (doc["mail_log"],
                  "present" if doc["mail_log_present"] else "MISSING",
                  doc["notified"]))
    if not doc["mail_log_present"]:
        out.append("  The log does not exist. Every stored record is therefore "
                   "unaccounted for -- this is not the same as 'nothing to do'.")
    if doc["notifications_unusable"]:
        out.append("  %d log line(s) unusable (unparseable, or carrying no rid). "
                   "They clear nothing." % doc["notifications_unusable"])
    if doc["unparseable_store_lines"]:
        out.append("  %d unparseable STORE line(s) -- run read-feedback.py; each "
                   "is a candidate lost message." % doc["unparseable_store_lines"])
    out.append("accounted for: %d notified, %d deferred to the digest"
               % (doc["ok"], len(doc["deferred"])))
    if doc["divergent"]:
        out.append("")
        out.append("DIVERGENT -- %d stored record(s) with no successful "
                   "notification:" % len(doc["divergent"]))
        for rid in doc["divergent"]:
            tail = " (a notification was attempted and reported failure)" \
                if rid in doc["attempted_and_failed"] else " (no notification line at all)"
            out.append("  %s%s" % (rid, tail))
        out.append("The records are safe -- the store is the record. What is at "
                   "risk is nobody READING them.")
    if doc["notified_not_stored"]:
        out.append("")
        out.append("NOTIFIED BUT NOT STORED -- %d rid(s). Somebody was told about "
                   "a message that is not durable:" % len(doc["notified_not_stored"]))
        for rid in doc["notified_not_stored"]:
            out.append("  %s" % rid)
    if not doc["divergent"] and not doc["notified_not_stored"]:
        out.append("")
        out.append("No divergence: every stored record has a notification and "
                   "every notification has a record.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description="Report divergence between the feedback store and the "
                    "notification log (contract §6 row F6).")
    ap.add_argument("--store", required=True, help="store root, or a .jsonl file")
    ap.add_argument("--mail-log", required=True,
                    help="notification log: one JSON object per line")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON on stdout and nothing else")
    ap.add_argument("--strict-deferred", action="store_true",
                    help="count digest-deferred records as divergent")
    args = ap.parse_args()

    try:
        doc = reconcile(args.store, args.mail_log,
                        strict_deferred=args.strict_deferred)
    except Exception as exc:
        print("reconcile-feedback: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(doc, ensure_ascii=False))
    else:
        print(human(doc))

    if doc["divergent"] or doc["notified_not_stored"] or not doc["mail_log_present"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
