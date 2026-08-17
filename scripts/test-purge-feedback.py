#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Force every safety property purge-feedback.py claims, and observe it fail.

    python scripts/test-purge-feedback.py

CLAUDE.md, testing discipline: "A claimed safety property needs a forced
failure... A guard seen only in its passing state has not been shown to work."
purge-feedback.py is the ONLY script in the feedback system that writes to the
store, so every claim it makes is a claim about not losing a visitor's message.
Each block below injects the fault rather than asserting about it:

  T1  a HARD KILL mid-rewrite (os._exit, no unwinding) -- the original file must
      survive byte-for-byte, and a later normal run must still find every record
  T2  an over-age `contact` -- --check must go RED, and go green after a purge
  T3  erasure nulls text/contact/credit/ua and NOTHING else, and leaves every
      other record's line byte-identical
  T4  a colliding receipt -- must REFUSE and write nothing (contract §1 says the
      receipt may collide; erasing on it would erase a stranger)
  T5  an unmatched receipt -- must REFUSE, not silently "succeed"
  T6  clock boundaries for ua (180d) and ip_hash (30d), forced on both sides
  T7  the contact clock runs from the LAST REPLY, not from server_ts
  T8  a store path inside the repo, and one under a docroot -- both refused
  T9  an unparseable line -- preserved byte-for-byte, run reports UNKNOWN
  T10 no store configured -- UNKNOWN (exit 2), never a vacuous green
  T11 idempotency: a second run rewrites nothing at all
  T12 U+2028 inside a record, which str.splitlines() would tear in half
  T13 UTF-8 content under PYTHONIOENCODING=cp1252 (CLAUDE.md's cp1252 trap)
  T14 purge and read-feedback agree on what a record file is
  T15 §10's other half -- a salt that stopped rotating is RED, and a salt this
      script cannot find is UNVERIFIED out loud rather than silently fine
  T16 A1: contention on <store>/.write-lock -- the lock is HELD by this process
      and the purge must wait and then refuse, never replace
  T17 A1, the defect itself: a record appended DURING a purge, under the lock,
      exactly as ingest.php appends it. It must survive the os.replace()
  T18 A2: a store inside a docroot that carries none of the heuristic's names --
      the real DreamHost layout, which the old guard waved through
  T19 A3: the salts and throttle buckets the purge never touched, and the
      linkage a retained salt keeps alive

Nothing here touches the repository tree: every store is built in a fresh temp
directory outside it, which is also the only place purge-feedback will consent
to operate.

WHY EVERY RUN GETS A DOCROOT (changed 2026-08-17)
------------------------------------------------
purge-feedback.py now REFUSES without --docroot / PDOOM_DOCROOT, so run() below
injects a throwaway one that contains no store. T18 is the block that takes it
away again and observes the refusal -- if the default were silently absent here,
every other block would be exercising the refusal path instead of the thing it
means to test, and would still look green.
"""

import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
PURGE = SCRIPTS / "purge-feedback.py"
READER = SCRIPTS / "read-feedback.py"

DAY = 86400
NOW = 1800000000          # a fixed "now"; every age below is relative to it

FAILURES = []
CHECKS = 0


def check(label, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if condition:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s%s" % (label, ("\n       " + detail) if detail else ""))
        FAILURES.append(label)


# A docroot that exists and contains none of the stores below, so the INV-1c
# containment test has something real to compare against without ever matching.
# Created once; the interpreter's temp dir is cleaned by the OS.
DEFAULT_DOCROOT = tempfile.mkdtemp(prefix="pdoom-test-docroot-")


def _env(env_extra=None):
    env = dict(os.environ)
    env.pop("PDOOM_FEEDBACK_STORE", None)
    env.pop("PDOOM_PURGE_CRASH_AFTER", None)
    env.pop("PDOOM_DOCROOT", None)
    env.pop("PDOOM_PURGE_LOCK_TIMEOUT", None)
    # Short by default so a genuinely stuck lock fails the suite in seconds
    # instead of hanging it; T16 sets its own.
    env["PDOOM_PURGE_LOCK_TIMEOUT"] = "5"
    env["PDOOM_DOCROOT"] = DEFAULT_DOCROOT
    # env_extra wins, INCLUDING an empty string -- that is how T18 takes the
    # docroot away and observes the refusal.
    env.update(env_extra or {})
    return env


def run(*args, env_extra=None, cwd=None):
    proc = subprocess.run(
        [sys.executable, str(PURGE)] + [str(a) for a in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_env(env_extra), cwd=str(cwd or REPO_ROOT))
    return proc.returncode, proc.stdout, proc.stderr


def spawn(*args, env_extra=None):
    """Same invocation as run(), but the caller drives the process.

    T17 needs the purge to be RUNNING and blocked while this process holds the
    lock and appends a record. subprocess.run() cannot express that.
    """
    return subprocess.Popen(
        [sys.executable, str(PURGE)] + [str(a) for a in args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
        env=_env(env_extra), cwd=str(REPO_ROOT))


def record(rid, **over):
    rec = {
        "rid": rid,
        "receipt": "F-" + rid[:6].upper(),
        "kind": "comment",
        "page": "/blog/post.html?p=x",
        "value": None,
        "text": "the visitor said something",
        "contact": "someone@example.org",
        "credit": "Someone",
        "flags": [],
        "server_ts": NOW,
        "client_ts": NOW - 2,
        "ip_hash": "a" * 64,
        "ua": "Mozilla/5.0",
        "schema": 1,
    }
    rec.update(over)
    return rec


def store_with(records, triage=None, name="2026-08.jsonl"):
    root = Path(tempfile.mkdtemp(prefix="pdoom-feedback-"))
    lines = []
    for rec in records:
        lines.append(rec if isinstance(rec, str)
                     else json.dumps(rec, ensure_ascii=False,
                                     separators=(",", ":")))
    (root / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if triage is not None:
        (root / "triage.log").write_text(
            "\n".join(t if isinstance(t, str)
                      else json.dumps(t, ensure_ascii=False)
                      for t in triage) + "\n", encoding="utf-8")
    return root


def read_records(root, name="2026-08.jsonl"):
    out = []
    for line in (root / name).read_text(encoding="utf-8").split("\n"):
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append(None)
    return out


def raw_bytes(root, name="2026-08.jsonl"):
    return (root / name).read_bytes()


# --------------------------------------------------------------------------
def t1_crash_mid_rewrite():
    print("\nT1  hard kill mid-rewrite -- the fault is injected, not simulated")
    # Every record is over every clock, so a purge MUST rewrite the file.
    old = NOW - 400 * DAY
    root = store_with([record("rid-%d" % i, server_ts=old) for i in range(4)])
    try:
        before = raw_bytes(root)
        for crash_at in (0, 1, 3, 9):
            code, _out, _err = run("--store", root, "--now", NOW,
                                   env_extra={"PDOOM_PURGE_CRASH_AFTER":
                                              str(crash_at)})
            check("crash_after=%d killed the process (exit 70)" % crash_at,
                  code == 70, "exit was %s" % code)
            check("crash_after=%d left the store byte-identical" % crash_at,
                  raw_bytes(root) == before,
                  "store changed under a crash; a half-written purge shipped")
        # ...and the store is still readable, with every message in it.
        recs = read_records(root)
        check("all 4 records survived every crash",
              len(recs) == 4 and all(r for r in recs),
              "got %d record(s)" % len(recs))
        # The temp file may survive a kill -- it cannot be mistaken for a record
        # file by anything that reads the store, which is the point of the name.
        strays = [p.name for p in root.iterdir() if p.suffix == ".jsonl"]
        check("no stray *.jsonl left by the crash", strays == ["2026-08.jsonl"],
              "found %s" % strays)
        # And a clean run afterwards still works and loses nothing.
        code, out, _err = run("--store", root, "--now", NOW)
        recs = read_records(root)
        check("a normal run after the crashes succeeds", code == 0,
              "exit %s" % code)
        check("normal run kept all 4 records", len(recs) == 4)
        check("normal run nulled contact/ua/ip_hash",
              bool(recs) and all(r and r["contact"] is None and r["ua"] is None
                                 and r["ip_hash"] is None for r in recs),
              json.dumps(recs[:1]))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t2_over_age_contact_is_red():
    print("\nT2  an over-age contact must make --check RED")
    root = store_with([
        record("fresh", server_ts=NOW - 10 * DAY),
        record("stale", server_ts=NOW - 91 * DAY, ua=None, ip_hash=None),
    ])
    try:
        code, out, _err = run("--store", root, "--check", "--now", NOW)
        check("--check exits 1 on a 91-day-old contact", code == 1,
              "exit %s\n%s" % (code, out))
        check("--check names the field and the record",
              "contact" in out and "stale" in out, out)
        check("--check wrote nothing",
              read_records(root)[1]["contact"] == "someone@example.org")

        run("--store", root, "--now", NOW)
        code, out, _err = run("--store", root, "--check", "--now", NOW)
        check("--check is green after the purge", code == 0,
              "exit %s\n%s" % (code, out))
        recs = read_records(root)
        check("the fresh record's contact was NOT touched",
              recs[0]["contact"] == "someone@example.org")
        check("the stale record's contact is null", recs[1]["contact"] is None)
        check("the stale record's text survived (indefinite, §10)",
              recs[1]["text"] == "the visitor said something")
        check("the purge stamped what it did",
              recs[1].get("purged", {}).get("contact", "").endswith("Z"),
              json.dumps(recs[1].get("purged")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t3_erasure_touches_exactly_four_fields():
    print("\nT3  erasure nulls exactly text/contact/credit/ua, nothing else")
    target = record("erase-me")
    bystander = record("bystander")
    root = store_with([target, bystander])
    try:
        before_lines = (root / "2026-08.jsonl").read_text(
            encoding="utf-8").split("\n")
        code, out, err = run("--store", root, "--receipt", target["receipt"],
                             "--now", NOW)
        check("erasure by receipt succeeds", code == 0, "%s%s" % (out, err))
        recs = read_records(root)
        erased, other = recs[0], recs[1]

        for field in ("text", "contact", "credit", "ua"):
            check("erasure nulled %s" % field, erased[field] is None,
                  repr(erased[field]))
        for field in ("rid", "receipt", "kind", "page", "value", "flags",
                      "server_ts", "client_ts", "ip_hash", "schema"):
            check("erasure preserved %s (tombstone, §10)" % field,
                  erased[field] == target[field],
                  "%r != %r" % (erased[field], target[field]))
        check("a tombstone marker was written",
              erased.get("erased", {}).get("via") == "receipt",
              json.dumps(erased.get("erased")))

        after_lines = (root / "2026-08.jsonl").read_text(
            encoding="utf-8").split("\n")
        check("the bystander's line is byte-identical",
              after_lines[1] == before_lines[1],
              "%r\n       %r" % (before_lines[1], after_lines[1]))
        check("the bystander's contact is untouched",
              other["contact"] == "someone@example.org")

        # Idempotent: a second request must not report failure at a person.
        code, _out, _err = run("--store", root, "--receipt", target["receipt"],
                               "--now", NOW)
        check("a repeated erasure request still succeeds", code == 0)

        # --dry-run + an erasure would have erased for real, because the erasure
        # branch runs first. A flag that means the opposite of what it says is
        # worse than a missing flag.
        code, _out, err = run("--store", root, "--rid", "bystander",
                              "--dry-run", "--now", NOW)
        check("--dry-run with an erasure is REFUSED, not silently honoured",
              code == 3, "exit %s\n%s" % (code, err))
        check("the bystander was not erased by the rehearsal",
              read_records(root)[1]["text"] == "the visitor said something")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t4_colliding_receipt_refuses():
    print("\nT4  a receipt matching two different rids must REFUSE")
    a = record("alpha")
    b = record("beta")
    b["receipt"] = a["receipt"]          # contract §1: receipts may collide
    root = store_with([a, b])
    try:
        before = raw_bytes(root)
        code, out, err = run("--store", root, "--receipt", a["receipt"],
                             "--now", NOW)
        check("exit is REFUSED (3)", code == 3, "exit %s\n%s%s" % (code, out, err))
        check("the refusal says why and offers --rid",
              "--rid" in err and "collide" in err, err)
        check("nothing was written", raw_bytes(root) == before)

        # --rid is the unambiguous form, and it must work.
        code, _out, _err = run("--store", root, "--rid", "alpha", "--now", NOW)
        recs = read_records(root)
        check("--rid erases the right one", code == 0 and recs[0]["text"] is None)
        check("--rid left the collider alone",
              recs[1]["text"] == "the visitor said something")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t5_unknown_receipt_refuses():
    print("\nT5  an unmatched receipt must REFUSE, never quietly succeed")
    root = store_with([record("only")])
    try:
        before = raw_bytes(root)
        code, out, err = run("--store", root, "--receipt", "F-ZZZZZZ",
                             "--now", NOW)
        check("exit is REFUSED (3)", code == 3, "exit %s\n%s%s" % (code, out, err))
        check("nothing was written", raw_bytes(root) == before)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t6_clock_boundaries():
    print("\nT6  ua=180d and ip_hash=30d, forced on both sides of the boundary")
    for days, ua_gone, ip_gone in ((29, False, False),
                                   (31, False, True),
                                   (179, False, True),
                                   (181, True, True)):
        root = store_with([record("r", server_ts=NOW - days * DAY,
                                  contact=None)])
        try:
            code, out, _err = run("--store", root, "--check", "--now", NOW)
            expect_red = ua_gone or ip_gone
            check("age=%dd: --check is %s" % (days, "red" if expect_red else "green"),
                  (code == 1) == expect_red, "exit %s\n%s" % (code, out))
            run("--store", root, "--now", NOW)
            rec = read_records(root)[0]
            check("age=%dd: ua %s" % (days, "purged" if ua_gone else "kept"),
                  (rec["ua"] is None) == ua_gone, repr(rec["ua"]))
            check("age=%dd: ip_hash %s" % (days, "purged" if ip_gone else "kept"),
                  (rec["ip_hash"] is None) == ip_gone, repr(rec["ip_hash"]))
        finally:
            shutil.rmtree(root, ignore_errors=True)


def t7_contact_clock_runs_from_last_reply():
    print("\nT7  contact's 90 days run from the last reply, not from server_ts")
    old = NOW - 300 * DAY
    for reply_days, expect_red in ((10, False), (100, True)):
        root = store_with(
            [record("conv", server_ts=old, ua=None, ip_hash=None)],
            triage=[{"rid": "conv", "last_reply_ts": NOW - reply_days * DAY}])
        try:
            code, out, _err = run("--store", root, "--check", "--now", NOW)
            check("record 300d old, replied %dd ago: --check %s"
                  % (reply_days, "red" if expect_red else "green"),
                  (code == 1) == expect_red, "exit %s\n%s" % (code, out))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    print("     ...and an unreadable sidecar makes the contact clock UNKNOWN")
    root = store_with([record("conv", server_ts=old)],
                      triage=["{this is not json"])
    try:
        code, out, _err = run("--store", root, "--now", NOW)
        rec = read_records(root)[0]
        check("purge exits UNKNOWN (2) on a damaged sidecar", code == 2,
              "exit %s\n%s" % (code, out))
        check("contact was NOT purged on an uncomputable clock",
              rec["contact"] == "someone@example.org", repr(rec["contact"]))
        check("ua and ip_hash were still purged normally",
              rec["ua"] is None and rec["ip_hash"] is None)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t8_bad_store_locations_refused():
    print("\nT8  a store inside the repo, or under a docroot, must be REFUSED")
    inside = REPO_ROOT / "public" / "data" / "feedback-store"
    code, _out, err = run("--store", inside, "--check")
    check("a path inside the git checkout is refused", code == 3,
          "exit %s\n%s" % (code, err))
    check("the refusal cites the reason (INV-1c / PII)",
          "INV-1c" in err or "PII" in err, err)
    check("the refusal created nothing", not inside.exists())

    outside = Path(tempfile.mkdtemp(prefix="pdoom-docroot-")) / "public" / "store"
    try:
        code, _out, err = run("--store", outside, "--check")
        check("a path with a `public` component is refused", code == 3,
              "exit %s\n%s" % (code, err))
    finally:
        shutil.rmtree(outside.parents[1], ignore_errors=True)


def t9_unparseable_line_preserved():
    print("\nT9  an unparseable line is preserved byte-for-byte and reported")
    garbage = '{"rid":"torn","text":"half a mess'
    root = store_with([record("good", server_ts=NOW - 400 * DAY), garbage])
    try:
        code, out, _err = run("--store", root, "--now", NOW)
        text = (root / "2026-08.jsonl").read_text(encoding="utf-8")
        check("purge exits UNKNOWN (2) when a line cannot be parsed", code == 2,
              "exit %s\n%s" % (code, out))
        check("the damaged line survived byte-for-byte", garbage in text, text)
        check("the good record was still purged",
              read_records(root)[0]["ua"] is None)
        code, out, _err = run("--store", root, "--check", "--now", NOW)
        check("--check reports UNKNOWN (2), not OK", code == 2,
              "exit %s\n%s" % (code, out))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t10_no_store_is_unknown_not_green():
    print("\nT10 no store configured must be UNKNOWN, never a vacuous green")
    code, _out, err = run("--check")
    check("exit is 2, not 0", code == 2, "exit %s\n%s" % (code, err))
    check("it says why silence is not success", "vacuous" in err, err)

    missing = Path(tempfile.mkdtemp(prefix="pdoom-missing-")) / "nope"
    try:
        code, _out, err = run("--store", missing, "--check")
        check("a store path that does not exist is UNKNOWN too", code == 2,
              "exit %s\n%s" % (code, err))
    finally:
        shutil.rmtree(missing.parent, ignore_errors=True)

    # The documented env fallback, exercised rather than assumed. Every other
    # block passes --store, so without this the PDOOM_FEEDBACK_STORE path -- the
    # one a cron job on the server will actually use -- would ship untested.
    root = store_with([record("env", server_ts=NOW - 400 * DAY)])
    try:
        code, out, err = run("--check", "--now", NOW,
                             env_extra={"PDOOM_FEEDBACK_STORE": str(root)})
        check("PDOOM_FEEDBACK_STORE resolves the store", code == 1,
              "exit %s\n%s%s" % (code, out, err))
        check("...and it is the right store", "ua" in out and "env" in out, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t11_second_run_rewrites_nothing():
    print("\nT11 a second run must not rewrite a single byte")
    root = store_with([record("a", server_ts=NOW - 400 * DAY),
                       record("b", server_ts=NOW - 10 * DAY)])
    try:
        run("--store", root, "--now", NOW)
        after_first = raw_bytes(root)
        code, out, _err = run("--store", root, "--now", NOW)
        check("second run succeeds", code == 0, out)
        check("second run left the file byte-identical",
              raw_bytes(root) == after_first)
        check("second run reports nothing purged",
              "purged" in out and "none" in out, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t12_u2028_does_not_tear_a_record():
    print("\nT12 U+2028 inside a record must not be split into two lines")
    # PHP's JSON_UNESCAPED_UNICODE emits U+2028 raw, and str.splitlines() treats
    # it as a line break. A splitlines()-based reader tears this record in half.
    payload = "line one" + " " + "line two"
    root = store_with([record("sep", text=payload,
                              server_ts=NOW - 400 * DAY),
                       record("next", server_ts=NOW - 400 * DAY)])
    try:
        code, out, _err = run("--store", root, "--now", NOW)
        check("purge succeeded", code == 0, out)
        recs = read_records(root)
        check("still exactly 2 records", len(recs) == 2,
              "got %d" % len(recs))
        check("the U+2028 text round-tripped intact",
              recs[0]["text"] == payload, repr(recs[0]["text"]))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t13_utf8_under_cp1252():
    print("\nT13 UTF-8 content with PYTHONIOENCODING=cp1252 (CLAUDE.md's trap)")
    payload = "emoji \U0001f600 em dash — curly “quote”"
    root = store_with([record("utf", text=payload, server_ts=NOW - 400 * DAY)])
    try:
        code, out, err = run("--store", root, "--now", NOW,
                             env_extra={"PYTHONIOENCODING": "cp1252"})
        check("the run did not die on the first print", code == 0,
              "exit %s\n%s%s" % (code, out, err))
        check("no UnicodeEncodeError anywhere",
              "UnicodeEncodeError" not in err, err)
        check("the visitor's text round-tripped byte-identical",
              read_records(root)[0]["text"] == payload)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t14_record_glob_agrees_with_the_reader():
    print("\nT14 purge and read-feedback must mean the same thing by 'record file'")
    if not READER.exists():
        check("read-feedback.py exists to compare against", False,
              "%s is missing" % READER)
        return
    purge = _import(PURGE, "purge_under_test")
    reader = _import(READER, "reader_under_test")
    root = Path(tempfile.mkdtemp(prefix="pdoom-glob-"))
    try:
        (root / "2026-07.jsonl").write_text("{}\n", encoding="utf-8")
        (root / "2026-08.jsonl").write_text("{}\n", encoding="utf-8")
        (root / "triage.log").write_text("{}\n", encoding="utf-8")
        (root / ".probe").write_text("", encoding="utf-8")
        mine = sorted(p.name for p in purge.record_files(root))
        theirs = sorted(p.name for p in reader.store_files(root))
        check("the two file lists are identical", mine == theirs,
              "purge=%s reader=%s" % (mine, theirs))
        check("the triage sidecar is NOT read as visitor records",
              "triage.log" not in theirs, str(theirs))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t15_salt_rotation():
    print("\nT15 §10's other half: the ip_hash salt must be seen to rotate")
    import time

    # Absent: UNVERIFIED, said out loud, and NOT allowed to look like approval --
    # but it does not set the exit code, because "I could not find the salt" is
    # not the same finding as "the salt is stale".
    root = store_with([record("r", contact=None, ua=None, ip_hash=None)])
    try:
        code, out, _err = run("--store", root, "--check", "--now", NOW)
        check("absent salt: exit stays 0", code == 0, "exit %s\n%s" % (code, out))
        check("absent salt: printed as UNVERIFIED, not silence",
              "UNVERIFIED" in out, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Stale: this one it can prove, so this one is red.
    root = store_with([record("r", contact=None, ua=None, ip_hash=None)])
    try:
        salt = root / ".salt"
        salt.mkdir()
        old = salt / "2026-06-01"
        old.write_text("x", encoding="utf-8")
        three_days = time.time() - 3 * 86400
        os.utime(old, (three_days, three_days))
        code, out, _err = run("--store", root, "--check")
        check("stale salt: --check goes RED", code == 1, "exit %s\n%s" % (code, out))
        check("stale salt: the message says why it matters",
              "linkable" in out, out)

        # A fresh salt clears the ROTATION finding -- and must NOT clear the
        # RETENTION one, which is A3's whole point: the salt is rotating and
        # every historical salt is still on disk, so a 30-day-old ip_hash is
        # still reversible. Two different findings about the same directory.
        fresh = salt / "today"
        fresh.write_text("x", encoding="utf-8")
        code, out, _err = run("--store", root, "--check")
        check("fresh salt + a retained old one: still RED", code == 1,
              "exit %s\n%s" % (code, out))
        check("...and now for RETENTION, not rotation",
              "salt rotation OK" in out and "ip-derived file" in out, out)

        # Green only once the old salt is actually gone.
        old.unlink()
        code, out, _err = run("--store", root, "--check")
        check("fresh salt, no retained salt: --check is green", code == 0,
              "exit %s\n%s" % (code, out))
        check("fresh salt: green still carries the number",
              "salt rotation OK" in out, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t16_write_lock_is_observed():
    print("\nT16 A1: hold <store>/.write-lock and watch the purge refuse to replace")
    purge = _import(PURGE, "purge_lock_probe")
    root = store_with([record("held", server_ts=NOW - 400 * DAY)])
    try:
        before = raw_bytes(root)

        # The fault: a real exclusive lock, taken by THIS process on the very
        # file ingest.php locks. Not a stub, not a flag -- the same primitive.
        with purge.store_write_lock(root, 5.0) as lock_path:
            check("the lockfile is not a record file",
                  lock_path.name == ".write-lock"
                  and not lock_path.name.endswith(".jsonl"),
                  str(lock_path))
            started = time.monotonic()
            code, _out, err = run("--store", root, "--now", NOW,
                                  "--lock-timeout", "1")
            waited = time.monotonic() - started
            check("a purge that cannot take the lock REFUSES (3)", code == 3,
                  "exit %s\n%s" % (code, err))
            check("...and it WAITED for the lock rather than skipping it",
                  waited >= 0.9, "returned after %.2fs" % waited)
            check("...and the store is byte-identical", raw_bytes(root) == before)
            check("...and the refusal names the lockfile",
                  ".write-lock" in err, err)

            # --check has a different right answer: it wrote nothing either way,
            # so the honest report is "certified nothing", not "refused".
            code, _out, err = run("--store", root, "--check", "--now", NOW,
                                  "--lock-timeout", "1")
            check("--check under contention is UNKNOWN (2), never a green",
                  code == 2, "exit %s\n%s" % (code, err))
            check("...and says why silence is not success",
                  "certified nothing" in err, err)

        # POSITIVE CONTROL. Without this, every assertion above is equally
        # consistent with a purge that is simply broken -- CLAUDE.md's
        # count_emails() trap, which reports success on a run where nothing
        # happened.
        code, out, _err = run("--store", root, "--now", NOW, "--lock-timeout", "1")
        check("positive control: the same run succeeds once the lock is free",
              code == 0, "exit %s\n%s" % (code, out))
        check("positive control: it really did rewrite the store",
              raw_bytes(root) != before)
        check("positive control: the record survived the rewrite",
              read_records(root)[0]["text"] == "the visitor said something")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t17_a_submission_during_a_purge_survives():
    print("\nT17 A1, the defect itself: a POST that lands mid-purge must survive")
    # This is the failing sequence from the review, executed rather than
    # described: purge starts, ingest.php appends and answers 200, purge calls
    # os.replace(). Before the shared lock the appended record ended up in an
    # orphaned inode and NOTHING recorded the loss.
    # The two processes are real and so is the contention. PDOOM_PURGE_STALL_MS
    # only widens the read -> os.replace() window from sub-millisecond to
    # seconds; it does not change who holds what. Without it the race is real
    # but unobservable, and an unobservable property is one a test can only
    # assert about.
    purge = _import(PURGE, "purge_race_probe")
    root = store_with([record("old-%d" % i, server_ts=NOW - 400 * DAY)
                       for i in range(3)])
    proc = None
    holder = None
    try:
        proc = spawn("--store", root, "--now", NOW, "--lock-timeout", "60",
                     env_extra={"PDOOM_PURGE_STALL_MS": "3000"})
        time.sleep(1.0)
        check("the purge is mid-run (it has read the store, not yet replaced it)",
              proc.poll() is None, "it exited %s already" % proc.poll())

        # Now do exactly what public/ingest.php does on a POST: take the store
        # write lock, append one line, fsync, release. The 200 with the
        # visitor's receipt goes out at the instant of that fsync.
        started = time.monotonic()
        holder = purge.store_write_lock(root, 30.0)
        holder.__enter__()
        waited = time.monotonic() - started
        check("the appender BLOCKED on the lock the purge is holding",
              waited >= 1.0,
              "acquired in %.2fs -- the purge is not holding the lock across "
              "its read, so a record written now is in an inode about to be "
              "replaced" % waited)

        late = record("late-arrival", server_ts=NOW)
        with open(root / "2026-08.jsonl", "a", encoding="utf-8",
                  newline="") as fh:
            fh.write(json.dumps(late, ensure_ascii=False,
                                separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        holder.__exit__(None, None, None)
        holder = None

        out, err = proc.communicate(timeout=60)
        check("the purge completed", proc.returncode == 0,
              "exit %s\n%s%s" % (proc.returncode, out, err))

        recs = read_records(root)
        rids = [r["rid"] for r in recs if r]
        check("THE ONE THAT MATTERS: the record appended mid-purge survived",
              "late-arrival" in rids,
              "the visitor holds a receipt for a message that is gone; rids=%s"
              % rids)
        check("...and no earlier record was lost", len(recs) == 4,
              "got %d record(s): %s" % (len(recs), rids))
        check("...and the purge still did its job on the old records",
              all(r["ip_hash"] is None for r in recs if r["rid"] != "late-arrival"),
              json.dumps(recs))
        # Indexed defensively: when the record HAS been swallowed this list is
        # empty, and a raised IndexError would take the summary line with it.
        survivors = [r for r in recs if r["rid"] == "late-arrival"]
        check("...and the fresh record was left alone",
              bool(survivors) and survivors[0]["ip_hash"] == "a" * 64,
              "no surviving late-arrival to inspect" if not survivors
              else repr(survivors[0]["ip_hash"]))
    finally:
        if holder is not None:
            holder.__exit__(None, None, None)
        if proc is not None and proc.poll() is None:
            proc.kill()
        shutil.rmtree(root, ignore_errors=True)


def t18_a_store_inside_the_real_docroot_is_refused():
    print("\nT18 A2: the DreamHost layout -- a docroot with no `public` in its name")
    purge = _import(PURGE, "purge_docroot_probe")
    home = Path(tempfile.mkdtemp(prefix="pdoom-home-"))
    docroot = home / "pdoom1.com"          # DreamHost's actual docroot shape
    store = docroot / "feedback-store"
    store.mkdir(parents=True)
    (store / "2026-08.jsonl").write_text(
        json.dumps(record("in-docroot"), ensure_ascii=False,
                   separators=(",", ":")) + "\n", encoding="utf-8")
    try:
        # First: prove the OLD guard would have passed this. Without this the
        # block only shows the new check firing, and says nothing about whether
        # it was needed.
        parts = Path(os.path.realpath(str(store))).parts
        hits = [p for p in parts if p.lower() in purge.DOCROOT_PARTS]
        check("the name heuristic ALONE does not see this path (the defect)",
              hits == [], "heuristic matched %s" % hits)

        code, _out, err = run("--store", store, "--check", "--now", NOW,
                              env_extra={"PDOOM_DOCROOT": str(docroot)})
        check("containment against the declared docroot refuses it", code == 3,
              "exit %s\n%s" % (code, err))
        check("the refusal cites INV-1c and names the docroot",
              "INV-1c" in err and "pdoom1.com" in err, err)
        check("the refusal points at ingest.php's matching guard",
              "ingest.php" in err, err)

        # A refusal that only applied to --check would leave the dangerous mode
        # unguarded, which is the shape of every early-return defect in this repo.
        code, _out, err = run("--store", store, "--now", NOW,
                              env_extra={"PDOOM_DOCROOT": str(docroot)})
        check("a real purge is refused too, not only --check", code == 3,
              "exit %s\n%s" % (code, err))
        check("the refused run created no lockfile inside the docroot store",
              not (store / ".write-lock").exists())

        # The --docroot FLAG must work, not just the env var.
        code, _out, err = run("--store", store, "--check", "--now", NOW,
                              "--docroot", str(docroot),
                              env_extra={"PDOOM_DOCROOT": ""})
        check("--docroot as a flag refuses it as well", code == 3,
              "exit %s\n%s" % (code, err))

        # The sibling that merely LOOKS contained must NOT be refused, or an
        # operator learns to reach for a bypass.
        sibling = home / "pdoom1.com-feedback-store"
        sibling.mkdir()
        (sibling / "2026-08.jsonl").write_text(
            json.dumps(record("outside"), ensure_ascii=False,
                       separators=(",", ":")) + "\n", encoding="utf-8")
        code, out, err = run("--store", sibling, "--check", "--now", NOW,
                             env_extra={"PDOOM_DOCROOT": str(docroot)})
        check("a sibling sharing the docroot's PREFIX is not refused",
              code != 3, "exit %s\n%s%s" % (code, out, err))

        # No docroot at all: REFUSE, never fall back to the heuristic.
        code, _out, err = run("--store", sibling, "--check", "--now", NOW,
                              env_extra={"PDOOM_DOCROOT": ""})
        check("with no docroot supplied it REFUSES rather than falling back",
              code == 3, "exit %s\n%s" % (code, err))
        check("...and says exactly what to pass",
              "--docroot" in err and "PDOOM_DOCROOT" in err, err)
        check("...and explains why there is no default",
              "DreamHost" in err or "no fallback" in err.lower(), err)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def t19_salts_and_throttle_buckets_are_swept():
    print("\nT19 A3: the ip_hash clock is not only a field")
    day = dt.datetime.fromtimestamp(NOW, dt.timezone.utc)
    today = day.strftime("%Y-%m-%d")
    ten_days_ago = (day - dt.timedelta(days=10)).strftime("%Y-%m-%d")

    ip = "203.0.113.7"
    old_salt_value = "s" * 64
    linkable = hashlib.sha256((ip + old_salt_value).encode("utf-8")).hexdigest()

    # A record whose ip_hash is still INSIDE its 30-day window, so the field is
    # legitimately retained. The finding is entirely about the files.
    root = store_with([record("recent", server_ts=NOW - 5 * DAY,
                              contact=None, ua=None, ip_hash=linkable)])
    try:
        salt = root / ".salt"
        salt.mkdir()
        throttle = root / ".throttle"
        throttle.mkdir()

        fresh_salt = salt / today
        fresh_salt.write_text("f" * 64, encoding="utf-8")
        old_salt = salt / ten_days_ago
        old_salt.write_text(old_salt_value, encoding="utf-8")
        # ingest.php's lost-rename leftover, which carries salt material and
        # which nothing in this system has ever removed.
        stray = salt / "legacy-salt-no-date"
        stray.write_text("l" * 64, encoding="utf-8")
        # mtimes are set against the INJECTED clock so salt_state() reports
        # rotation as healthy -- otherwise the run goes red for staleness and
        # this block would be observing the wrong finding.
        for path, when in ((fresh_salt, NOW - 3600),
                           (old_salt, NOW - 10 * DAY),
                           (stray, NOW - 400 * DAY)):
            os.utime(path, (when, when))

        fresh_bucket = throttle / ("a" * 32 + ".json")
        fresh_bucket.write_text('{"prose":{"tokens":4}}', encoding="utf-8")
        old_bucket = throttle / (linkable[:32] + ".json")
        old_bucket.write_text('{"prose":{"tokens":5}}', encoding="utf-8")
        os.utime(fresh_bucket, (NOW - DAY, NOW - DAY))
        os.utime(old_bucket, (NOW - 40 * DAY, NOW - 40 * DAY))

        # The linkage is real, not rhetorical: with the retained salt in hand,
        # the stored ip_hash resolves back to an address.
        check("a retained salt makes a stored ip_hash reversible (the harm)",
              hashlib.sha256(
                  (ip + old_salt.read_text(encoding="utf-8")).encode("utf-8")
              ).hexdigest() == linkable)
        check("the throttle bucket is NAMED after that same ip_hash",
              old_bucket.stem == linkable[:32])

        code, out, _err = run("--store", root, "--check", "--now", NOW)
        check("--check goes RED on retained ip-derived files", code == 1,
              "exit %s\n%s" % (code, out))
        check("--check counts them", "ip_derived_files_over_clock" in out, out)
        check("--check names the salt and the bucket",
              ten_days_ago in out and old_bucket.name in out, out)
        check("--check is red for RETENTION, not rotation",
              "salt rotation OK" in out, out)
        check("--check deleted nothing", old_salt.exists() and old_bucket.exists())

        code, out, _err = run("--store", root, "--now", NOW)
        check("the purge succeeded", code == 0, "exit %s\n%s" % (code, out))
        check("the over-age salt is GONE", not old_salt.exists())
        check("the undated leftover is gone too (mtime fallback)",
              not stray.exists())
        check("the over-age throttle bucket is GONE", not old_bucket.exists())
        check("today's salt survived -- sweeping it would re-hash every visitor",
              fresh_salt.exists())
        check("the in-window throttle bucket survived", fresh_bucket.exists())
        check("the purge reported what it swept", "swept" in out, out)
        check("the visitor's record was not touched by any of this",
              read_records(root)[0]["text"] == "the visitor said something")
        check("...and its in-window ip_hash is still there",
              read_records(root)[0]["ip_hash"] == linkable)

        code, out, _err = run("--store", root, "--check", "--now", NOW)
        check("--check is green after the sweep", code == 0,
              "exit %s\n%s" % (code, out))

        # "Never counted as a record" is a claim; this is the observation.
        purge = _import(PURGE, "purge_glob_probe")
        names = [str(p) for p in purge.record_files(root)]
        check("no salt, bucket or lockfile is read as a record file",
              names == [str(root / "2026-08.jsonl")], str(names))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _import(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    print("Forcing the failures purge-feedback.py claims to survive.")
    if not PURGE.exists():
        print("FAIL: %s does not exist" % PURGE)
        return 1
    for fn in (t1_crash_mid_rewrite, t2_over_age_contact_is_red,
               t3_erasure_touches_exactly_four_fields,
               t4_colliding_receipt_refuses, t5_unknown_receipt_refuses,
               t6_clock_boundaries, t7_contact_clock_runs_from_last_reply,
               t8_bad_store_locations_refused, t9_unparseable_line_preserved,
               t10_no_store_is_unknown_not_green, t11_second_run_rewrites_nothing,
               t12_u2028_does_not_tear_a_record, t13_utf8_under_cp1252,
               t14_record_glob_agrees_with_the_reader, t15_salt_rotation,
               t16_write_lock_is_observed,
               t17_a_submission_during_a_purge_survives,
               t18_a_store_inside_the_real_docroot_is_refused,
               t19_salts_and_throttle_buckets_are_swept):
        # A block that dies takes its own findings with it AND every block after
        # it, which turns a precise report into "something went wrong". Observed
        # while mutation-testing this file: the crash-mid-rewrite defect failed
        # four checks correctly and then raised, losing the summary line.
        try:
            fn()
        except Exception as exc:                       # noqa: BLE001
            import traceback
            check("%s ran to completion" % fn.__name__, False,
                  "%s: %s\n%s" % (type(exc).__name__, exc,
                                  traceback.format_exc()))
    print("\n%d check(s), %d failure(s)" % (CHECKS, len(FAILURES)))
    if FAILURES:
        for name in FAILURES:
            print("  FAILED: %s" % name)
        return 1
    print("OK: every claimed property was forced into its failing state and held.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
