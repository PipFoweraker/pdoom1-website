#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DELIBERATELY NAIVE stub of the feedback intake endpoint.

THIS IS NOT AN IMPLEMENTATION AND MUST NEVER BECOME ONE.

docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §6 requires the destructive suite to be
observed RED before agent A1 writes a line of `public/ingest.php` (Gate 2). A test
that has never failed has not been shown to be a test -- so the suite needs
something to run against that is real enough to accept a request and wrong enough
to fail. That is this file.

Every naive behaviour below is a bug that has actually shipped somewhere, and each
one maps to a row of the §6 matrix:

  * mail is sent BEFORE the durable write, and a mail failure is reported as a
    request failure          -> violates INV-1a, INV-1d   (F1, F5)
  * the store root defaults INSIDE the docroot and is never checked
                             -> violates INV-1c           (F13, F14)
  * the record is appended in two flushed chunks with no flock()
                             -> violates §3 append discipline (F4)
  * a filled honeypot is absorbed with a cheerful 200 and no record
                             -> violates INV-1e           (F10)
  * malformed JSON raises, so the caller gets a crash rather than a 400
                             -> violates §2              (F11)
  * an over-cap `text` is silently truncated and stored, never a 413
                             -> violates §2              (F12)
  * the record is written as cp1252 with errors="replace" and ensure_ascii=False,
    so non-ASCII free text is destroyed on disk
                             -> violates the encoding lesson (F15)
  * there is no throttle at all
                             -> violates §4.3            (F9)
  * there is no fsync, so "written" means "visible", not "durable"
                             -> violates §3              (F2, F3)

DO NOT "FIX" THIS FILE. Fixing it makes the suite green against a stub, which is
the exact vacuous-green shape CLAUDE.md's testing discipline forbids. The real
endpoint is agent A1's, lives at public/ingest.php, and is selected automatically
by scripts/fixtures/ingest_harness.py as soon as it exists.

Invoked by the harness, never directly:
    stdin  = the raw request body
    stdout = one JSON envelope: {"status": int, "headers": {...}, "body": "..."}
    env    = PDOOM_FEEDBACK_STORE, PDOOM_DOCROOT, PDOOM_MAIL_SINK, PDOOM_MAIL_FAIL,
             PDOOM_REMOTE_ADDR, PDOOM_HTTP_USER_AGENT
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def emit(status, obj, content_type="application/json"):
    sys.stdout.write(json.dumps({
        "status": status,
        "headers": {"Content-Type": content_type},
        "body": json.dumps(obj),
    }))
    sys.stdout.flush()


def store_root():
    # NAIVE: env first (that part is right), then a path INSIDE the docroot, and
    # no containment check whatsoever. rsync --delete reaches this, and so does
    # any visitor with a browser.
    env = os.environ.get("PDOOM_FEEDBACK_STORE")
    if env:
        return Path(env)
    return Path(os.environ.get("PDOOM_DOCROOT", ".")) / "data" / "feedback"


def send_mail(rec):
    """NAIVE: called BEFORE the write, and its result is treated as authoritative."""
    sink = os.environ.get("PDOOM_MAIL_SINK")
    ok = os.environ.get("PDOOM_MAIL_FAIL", "") != "1"
    if sink:
        with open(sink, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "rid": rec.get("rid"),
                "kind": rec.get("kind"),
                "ok": ok,
                "ts": int(time.time()),
            }) + "\n")
    return ok


def main():
    body = sys.stdin.buffer.read().decode("utf-8", errors="replace")

    # NAIVE: no try/except. A malformed body raises, the process dies, and the
    # caller sees a crash instead of `400 {"retryable": false}`.
    payload = json.loads(body)

    rid = payload.get("rid") or ""
    receipt = "F-" + rid.replace("-", "")[:6].upper()

    rec = {
        "rid": rid,
        "receipt": receipt,
        "kind": payload.get("kind"),
        "page": payload.get("page"),
        "value": payload.get("value"),
        # NAIVE: silently truncates the visitor's words instead of returning 413.
        "text": (payload.get("text") or "")[:5000],
        "contact": payload.get("contact"),
        "credit": payload.get("credit"),
        "flags": [],
        "server_ts": int(time.time()),
        "client_ts": payload.get("client_ts"),
        "ip_hash": hashlib.sha256(
            os.environ.get("PDOOM_REMOTE_ADDR", "127.0.0.1").encode("utf-8")
        ).hexdigest(),
        "ua": os.environ.get("PDOOM_HTTP_USER_AGENT", ""),
        "schema": 1,
    }

    # NAIVE: mail first, and a mail failure fails the request. Mail is being
    # treated as the record rather than as a notification derived from one.
    if not send_mail(rec):
        emit(500, {"ok": False, "error": "could not send notification", "retryable": True})
        return

    # NAIVE: a filled honeypot is absorbed. The visitor is told it worked and
    # nothing is written -- silent loss with a smile.
    if (payload.get("hp") or "") != "":
        emit(200, {"ok": True, "rid": rid, "receipt": receipt, "stored_at": int(time.time())})
        return

    root = store_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (time.strftime("%Y-%m") + ".jsonl")

    line = json.dumps(rec, ensure_ascii=False)
    # NAIVE, and this is the shape flock() exists to prevent: two unlocked,
    # separately flushed writes. Two simultaneous POSTs interleave into a line
    # that is no longer JSON.
    # NAIVE encoding: cp1252 with errors="replace" destroys every non-ASCII
    # character the visitor typed. (The explicit encoding= keeps
    # scripts/check-encoding-safety.py honest about this file; the *value* is the
    # bug being staged.)
    with open(path, "a", encoding="cp1252", errors="replace", newline="") as fh:
        fh.write(line)
        fh.flush()
        fh.write("\n")
        fh.flush()
        # NAIVE: no fsync. "Written" here means "visible to a reader on this
        # host", not "survives the power going out".

    emit(200, {"ok": True, "rid": rid, "receipt": receipt, "stored_at": rec["server_ts"]})


if __name__ == "__main__":
    main()
