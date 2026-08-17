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

Nothing here touches the repository tree: every store is built in a fresh temp
directory outside it, which is also the only place purge-feedback will consent
to operate.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def run(*args, env_extra=None, cwd=None):
    env = dict(os.environ)
    env.pop("PDOOM_FEEDBACK_STORE", None)
    env.pop("PDOOM_PURGE_CRASH_AFTER", None)
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(PURGE)] + [str(a) for a in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(cwd or REPO_ROOT))
    return proc.returncode, proc.stdout, proc.stderr


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

        # Fresh: green again, and still counted rather than passed over silently.
        fresh = salt / "today"
        fresh.write_text("x", encoding="utf-8")
        code, out, _err = run("--store", root, "--check")
        check("fresh salt: --check is green", code == 0,
              "exit %s\n%s" % (code, out))
        check("fresh salt: green still carries the number",
              "salt rotation OK" in out, out)
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
               t14_record_glob_agrees_with_the_reader, t15_salt_rotation):
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
