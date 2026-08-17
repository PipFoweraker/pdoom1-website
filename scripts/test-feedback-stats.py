#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Force every hazard §9 names, and observe generate-feedback-stats.py refuse.

    python scripts/test-feedback-stats.py

The public counter's whole promise is that no visitor's words and no machine's
guess can reach a file served from pdoom1.com. A promise is worth what the thing
enforcing it is worth, so every block here makes the enforcement fire:

  S1  a category below k=5 is WITHHELD and declared -- forced on both sides of
      the threshold, because a rule seen only at 5 has not been seen to suppress
  S2  a regex-derived tag gets NO ROUTE IN: the record stays untriaged, the tag
      never appears, and the machine entry is counted as ignored
  S3  a triage entry claiming source="human" with nobody named REFUSES the run,
      and the previously published file is left standing byte-for-byte
  S4  `flags` -- the endpoint's own honeypot/too-fast markers -- never become
      public categories
  S5  `untriaged` publishes at 1, exempt from k (§9c's accountability clock)
  S6  the reader dependency missing -> REFUSED, nothing written, no private
      collapser invented
  S7  a reader that LOSES a record -> REFUSED (the conservation law)
  S8  duplicate rids are counted once, by the reader's rule, not by ours
  S9  no visitor content reaches the output, checked against the finished file
  S10 a tombstoned record is still counted (§10: counts stay honest)
  S11 no record total is published -- a total would recover every suppressed
      count by subtraction
  S12 a tag with a shape that could never be a safe JSON key is refused
  S13 UTF-8 store content under PYTHONIOENCODING=cp1252

Every store and every output path is a fresh temp directory outside the repo.
The real public/data/feedback-stats.json is never written by this test.
"""

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
GEN = SCRIPTS / "generate-feedback-stats.py"
READER = SCRIPTS / "read-feedback.py"

NOW = "2026-08-16T00:00:00Z"
K = 5

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


def run(*args, env_extra=None):
    env = dict(os.environ)
    env.pop("PDOOM_FEEDBACK_STORE", None)
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(GEN)] + [str(a) for a in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(REPO_ROOT))
    return proc.returncode, proc.stdout, proc.stderr


def record(rid, kind="comment", **over):
    rec = {"rid": rid, "receipt": "F-" + rid[:6].upper(), "kind": kind,
           "page": "/blog/post.html?p=x", "value": None,
           "text": "visitor words for %s" % rid,
           "contact": "someone@example.org", "credit": "Someone",
           "flags": [], "server_ts": 1800000000, "client_ts": 1799999998,
           "ip_hash": "a" * 64, "ua": "Mozilla/5.0", "schema": 1}
    rec.update(over)
    return rec


def make_store(records, triage=None):
    root = Path(tempfile.mkdtemp(prefix="pdoom-stats-"))
    (root / "2026-08.jsonl").write_text(
        "\n".join(r if isinstance(r, str)
                  else json.dumps(r, ensure_ascii=False) for r in records)
        + "\n", encoding="utf-8")
    if triage is not None:
        (root / "triage.log").write_text(
            "\n".join(t if isinstance(t, str)
                      else json.dumps(t, ensure_ascii=False) for t in triage)
            + "\n", encoding="utf-8")
    return root


def generate(root, extra=(), env_extra=None):
    """Run the generator into a temp output file. Returns (code, doc, out, err)."""
    out_path = root / "out" / "feedback-stats.json"
    code, out, err = run("--store", root, "--out", out_path, "--now", NOW,
                         *extra, env_extra=env_extra)
    doc = None
    if out_path.exists():
        doc = json.loads(out_path.read_text(encoding="utf-8"))
    return code, doc, out, err, out_path


def human_tag(rid, *tags, by="Pip"):
    return {"rid": rid, "tags": list(tags), "source": "human",
            "confirmed_by": by, "confirmed_on": "2026-08-16"}


# --------------------------------------------------------------------------
def s1_below_k_is_withheld():
    print("\nS1  k=5: forced on BOTH sides, because suppression unseen is unproven")
    for n, published in ((K - 1, False), (K, True)):
        root = make_store([record("bug-%d" % i, kind="bug") for i in range(n)])
        try:
            code, doc, out, err, _p = generate(root)
            check("n=%d: generator succeeded" % n, code == 0, err)
            if not doc:
                continue
            check("n=%d: `bug` %s" % (n, "published" if published else "withheld"),
                  ("bug" in doc["counts"]) == published, json.dumps(doc["counts"]))
            check("n=%d: suppressed_categories=%d" % (n, 0 if published else 1),
                  doc["suppressed_categories"] == (0 if published else 1),
                  json.dumps(doc))
            check("n=%d: withheld, never zeroed or rounded" % n,
                  doc["counts"].get("bug") in ((K if published else None),),
                  json.dumps(doc["counts"]))
            check("n=%d: the withheld NAME is not in the file" % n,
                  published or "bug" not in json.dumps(doc),
                  json.dumps(doc))
        finally:
            shutil.rmtree(root, ignore_errors=True)


def s2_regex_tag_has_no_route_in():
    print("\nS2  a machine-derived tag must never reach the public file (§9a)")
    root = make_store(
        [record("m-%d" % i) for i in range(8)],
        triage=[{"rid": "m-%d" % i, "tags": ["abusive"], "source": "regex",
                 "confirmed_by": "classifier-v2", "confirmed_on": "2026-08-16"}
                for i in range(8)])
    try:
        code, doc, out, err, _p = generate(root)
        check("the run still succeeds (an auto-tagger is not an outage)",
              code == 0, err)
        if not doc:
            return
        check("`abusive` is absent from counts",
              "abusive" not in doc["counts"], json.dumps(doc["counts"]))
        check("`abusive` appears nowhere in the file at all",
              "abusive" not in json.dumps(doc), json.dumps(doc))
        check("the records stay untriaged -- the backlog does not shrink",
              doc["untriaged"] == 8, json.dumps(doc))
        check("the ignored machine tags are counted, not hidden",
              doc["unconfirmed_tags"] == 8, json.dumps(doc))
        # ...and the same records, once a HUMAN confirms them, do publish.
        (root / "triage.log").write_text(
            "\n".join(json.dumps(human_tag("m-%d" % i, "abusive"))
                      for i in range(8)) + "\n", encoding="utf-8")
        code, doc, out, err, _p = generate(root)
        check("the same tag publishes once a human confirms it",
              code == 0 and doc and doc["counts"].get("abusive") == 8,
              json.dumps(doc) if doc else err)
        check("...and untriaged drops to 0", doc and doc["untriaged"] == 0)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s3_unattributed_human_claim_refuses():
    print("\nS3  source=human with nobody named must REFUSE the whole run")
    root = make_store(
        [record("x-%d" % i) for i in range(6)],
        triage=[{"rid": "x-0", "tags": ["abusive"], "source": "human",
                 "confirmed_by": "   ", "confirmed_on": "2026-08-16"}])
    try:
        # Publish a good file first, so we can prove a refusal leaves it alone.
        (root / "triage.log").rename(root / "triage.bad")
        code, doc, _out, err, out_path = generate(root)
        check("the clean run published", code == 0 and doc is not None, err)
        before = out_path.read_bytes() if out_path.exists() else None

        (root / "triage.bad").rename(root / "triage.log")
        code, _doc, out, err, out_path = generate(root)
        check("exit is REFUSED (3)", code == 3, "exit %s\n%s%s" % (code, out, err))
        check("the refusal explains it publishes under a human's name or not "
              "at all", "confirmed_by" in err, err)
        check("the previously published file is untouched",
              before is not None
              and out_path.exists() and out_path.read_bytes() == before,
              "the baseline publish did not happen, so this proves nothing")

        for bad, why in (
            ({"rid": "x-0", "tags": ["abusive"], "source": "human",
              "confirmed_by": "Pip", "confirmed_on": "last tuesday"},
             "a confirmation date that is not a date"),
            ({"rid": "", "tags": ["abusive"], "source": "human",
              "confirmed_by": "Pip", "confirmed_on": "2026-08-16"},
             "a confirmation naming no record"),
            ({"rid": "x-0", "tags": [], "source": "human",
              "confirmed_by": "Pip", "confirmed_on": "2026-08-16"},
             "a confirmation of nothing"),
        ):
            (root / "triage.log").write_text(json.dumps(bad) + "\n",
                                             encoding="utf-8")
            code, _doc, out, err, _p = generate(root)
            check("REFUSED: %s" % why, code == 3, "exit %s\n%s" % (code, err))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s4_flags_are_not_categories():
    print("\nS4  the endpoint's own flags must never become public categories")
    root = make_store([record("f-%d" % i,
                              flags=["honeypot", "too-fast", "injection_attempt"])
                       for i in range(9)])
    try:
        code, doc, _out, err, _p = generate(root)
        check("run succeeded", code == 0, err)
        if not doc:
            return
        blob = json.dumps(doc)
        for flag in ("honeypot", "too-fast", "injection_attempt"):
            check("`%s` never reaches the file" % flag, flag not in blob, blob)
        check("those records are untriaged, not classified",
              doc["untriaged"] == 9, blob)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s5_untriaged_publishes_at_one():
    print("\nS5  untriaged is exempt from k -- it publishes at 1 (§9c)")
    root = make_store([record("lonely")])
    try:
        code, doc, _out, err, _p = generate(root)
        check("run succeeded", code == 0, err)
        check("untriaged=1 is published, not suppressed",
              doc and doc["untriaged"] == 1, json.dumps(doc) if doc else err)
        check("the record's own kind IS suppressed at 1",
              doc and "comment" not in doc["counts"],
              json.dumps(doc) if doc else "")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # §9's own example -- 1904 thumbs against untriaged 47 -- says the backlog
    # counts WORDS, not submissions. 30 bare thumbs must not read as 30 unread
    # messages, or the accountability clock is drowned by the thing it was never
    # about and Pip learns to ignore it.
    print("     ...and a bare thumb is not a reading obligation")
    root = make_store([record("v-%d" % i, kind="thumb", value=1, text=None)
                       for i in range(30)]
                      + [record("w-%d" % i, text="please read me")
                         for i in range(3)])
    try:
        code, doc, _out, err, _p = generate(root)
        check("run succeeded", code == 0, err)
        check("30 bare thumbs are counted as thumbs",
              doc and doc["counts"].get("thumb_up") == 30,
              json.dumps(doc) if doc else err)
        check("untriaged is 3 (the prose), not 33",
              doc and doc["untriaged"] == 3, json.dumps(doc) if doc else err)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("     ...but a thumb WITH a comment attached is (§2 allows both)")
    root = make_store([record("y-%d" % i, kind="thumb", value=1,
                              text="and also, the tutorial is confusing")
                       for i in range(6)])
    try:
        code, doc, _out, err, _p = generate(root)
        check("a thumb carrying text counts as untriaged prose",
              code == 0 and doc and doc["untriaged"] == 6,
              json.dumps(doc) if doc else err)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("     ...and an erased record stops being a reading obligation (§10)")
    root = make_store([record("z-%d" % i, text=None, contact=None, credit=None,
                              ua=None,
                              erased={"on": NOW, "via": "receipt",
                                      "fields": ["contact", "credit", "text",
                                                 "ua"]})
                       for i in range(6)])
    try:
        code, doc, _out, err, _p = generate(root)
        check("tombstones still count as submissions",
              code == 0 and doc and doc["counts"].get("comment") == 6,
              json.dumps(doc) if doc else err)
        check("...but not as unread words", doc and doc["untriaged"] == 0,
              json.dumps(doc) if doc else "")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _stub_reader(root, body):
    path = root / "stub-reader.py"
    path.write_text(body, encoding="utf-8")
    return path


def s6_missing_reader_refuses():
    print("\nS6  the dedup dependency missing must REFUSE, never improvise")
    root = make_store([record("a-%d" % i) for i in range(6)])
    try:
        code, doc, out, err, out_path = generate(
            root, extra=("--reader", root / "does-not-exist.py"))
        check("exit is REFUSED (3)", code == 3, "exit %s\n%s%s" % (code, out, err))
        check("the refusal names read-time dedup and the contract",
              "dedup" in err.lower() and "collapser" in err.lower(), err)
        check("nothing was written", not out_path.exists())
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("     ...and a reader with no load() is named, not worked around")
    root = make_store([record("a-%d" % i) for i in range(6)])
    try:
        stub = _stub_reader(root, "def something_else(x):\n    return x\n")
        code, _doc, out, err, out_path = generate(root, extra=("--reader", stub))
        check("exit is REFUSED (3)", code == 3, "exit %s\n%s%s" % (code, out, err))
        check("the refusal states the required surface", "load(store)" in err, err)
        check("nothing was written", not out_path.exists())
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s7_lossy_reader_refuses():
    print("\nS7  a reader that LOSES a record must take the counter offline")
    root = make_store([record("a-%d" % i) for i in range(6)])
    try:
        # Reports 6 parsed, 0 duplicates, but returns 5. The conservation law
        # (parsed - returned == duplicates) is the only thing standing between a
        # lossy reader and a public number that is quietly too small.
        stub = _stub_reader(root, (
            "import json, pathlib\n"
            "def load(store, kind=None, since=None):\n"
            "    recs = [json.loads(l) for l in\n"
            "            (pathlib.Path(store)/'2026-08.jsonl')\n"
            "            .read_text(encoding='utf-8').split('\\n') if l.strip()]\n"
            "    kept = recs[:-1]\n"
            "    return {'records': kept, 'record_count': len(kept),\n"
            "            'records_parsed': len(recs), 'duplicates_collapsed': 0,\n"
            "            'unparseable_lines': [], 'records_without_rid': []}\n"))
        code, _doc, out, err, out_path = generate(root, extra=("--reader", stub))
        check("exit is REFUSED (3)", code == 3, "exit %s\n%s%s" % (code, out, err))
        check("the refusal names the conservation law",
              "conservation" in err, err)
        check("nothing was written", not out_path.exists())

        # And a reader that returns the same rid twice is caught too.
        stub2 = _stub_reader(root, (
            "import json, pathlib\n"
            "def load(store, kind=None, since=None):\n"
            "    recs = [json.loads(l) for l in\n"
            "            (pathlib.Path(store)/'2026-08.jsonl')\n"
            "            .read_text(encoding='utf-8').split('\\n') if l.strip()]\n"
            "    out = recs + [recs[0]]\n"
            "    return {'records': out, 'record_count': len(out),\n"
            "            'records_parsed': len(out), 'duplicates_collapsed': 0,\n"
            "            'unparseable_lines': [], 'records_without_rid': []}\n"))
        code, _doc, _out, err, _p = generate(root, extra=("--reader", stub2))
        check("a reader returning a duplicate rid is REFUSED", code == 3, err)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s8_duplicates_counted_once():
    print("\nS8  duplicate writes count once -- by the reader's rule, not ours")
    if not READER.exists():
        check("read-feedback.py exists", False, "%s missing" % READER)
        return
    recs = []
    for i in range(6):
        rec = record("d-%d" % i)
        recs.append(rec)
        # A retry after a lost response: same rid, later server_ts (contract F3).
        recs.append(dict(rec, server_ts=rec["server_ts"] + 30))
    root = make_store(recs)
    try:
        code, doc, out, err, _p = generate(root)
        check("run succeeded", code == 0, err)
        check("12 lines collapsed to 6 comments",
              doc and doc["counts"].get("comment") == 6,
              json.dumps(doc) if doc else err)
        check("the collapse is reported, not hidden",
              "6 duplicate write(s) collapsed" in out, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s9_no_content_reaches_the_file():
    print("\nS9  no visitor content in the output -- checked against the file")
    secrets = ["burn it all down", "reporter@university.edu", "Ada L",
               "/blog/post.html?p=secret-draft"]
    recs = []
    for i in range(6):
        recs.append(record("c-%d" % i, text=secrets[0], contact=secrets[1],
                           credit=secrets[2], page=secrets[3]))
    root = make_store(recs, triage=[human_tag("c-%d" % i, "abusive")
                                    for i in range(6)])
    try:
        code, doc, _out, err, out_path = generate(root)
        check("run succeeded", code == 0, err)
        blob = out_path.read_text(encoding="utf-8")
        for secret in secrets:
            check("%r is not in the published file" % secret[:24],
                  secret not in blob, blob)
        check("only integers and declared constants are values",
              doc and all(isinstance(v, int) or isinstance(v, str)
                          or isinstance(v, dict) for v in doc.values()))
        check("the human-confirmed category did publish",
              doc and doc["counts"].get("abusive") == 6, blob)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s10_tombstones_still_count():
    print("\nS10 a tombstoned record is still one submission (§10)")
    recs = [record("t-%d" % i) for i in range(6)]
    for rec in recs[:3]:
        rec.update({"text": None, "contact": None, "credit": None, "ua": None,
                    "erased": {"on": NOW, "via": "receipt",
                               "fields": ["contact", "credit", "text", "ua"]}})
    root = make_store(recs)
    try:
        code, doc, _out, err, _p = generate(root)
        check("run succeeded", code == 0, err)
        check("all 6 still counted, erased or not",
              doc and doc["counts"].get("comment") == 6,
              json.dumps(doc) if doc else err)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s11_no_total_is_published():
    print("\nS11 no total may be published -- it would undo every suppression")
    # 6 comments (published) + 2 bugs (suppressed). A published total of 8 would
    # recover the withheld count by subtraction, making the withholding theatre.
    root = make_store([record("p-%d" % i) for i in range(6)]
                      + [record("q-%d" % i, kind="bug") for i in range(2)])
    try:
        code, doc, _out, err, _p = generate(root)
        check("run succeeded", code == 0, err)
        if not doc:
            return
        check("`bug` is suppressed", "bug" not in doc["counts"])
        forbidden = [k for k in doc
                     if k in ("total", "records", "record_count", "total_records",
                              "submissions", "lines")]
        check("no total-shaped key exists", not forbidden, str(forbidden))

        # RESIDUAL 9d, asserted rather than wished away. In a wholly untriaged
        # store §9c's exact `untriaged` IS the total, so differencing works and
        # the generator must SAY SO instead of quietly implying otherwise.
        check("the residual is real in the untriaged case (8 - 6 == 2)",
              doc["untriaged"] - sum(doc["counts"].values()) == 2,
              json.dumps(doc))
        source = GEN.read_text(encoding="utf-8")
        check("...and it is documented as RESIDUAL 9d, not left to be "
              "rediscovered", "RESIDUAL 9d" in source)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("     ...and it closes as soon as anything is triaged")
    root = make_store([record("p-%d" % i) for i in range(6)]
                      + [record("q-%d" % i, kind="bug") for i in range(2)],
                      triage=[human_tag("p-%d" % i, "abusive") for i in range(6)])
    try:
        code, doc, _out, err, _p = generate(root)
        check("run succeeded", code == 0, err)
        if not doc:
            return
        check("untriaged (2) no longer equals the record total (8)",
              doc["untriaged"] != 8, json.dumps(doc))
        check("...so the suppressed count is not recoverable by subtraction",
              doc["untriaged"] - sum(doc["counts"].values()) != 2,
              json.dumps(doc))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s12_unsafe_tag_shape_refused():
    print("\nS12 a tag that could never be a safe public key is REFUSED")
    for tag in ("Pip is an idiot", "<script>alert(1)</script>", "ABUSIVE",
                "a" * 40, "", "death threats / bad grammar"):
        root = make_store([record("s-%d" % i) for i in range(6)],
                          triage=[human_tag("s-0", tag)])
        try:
            code, _doc, out, err, out_path = generate(root)
            check("tag %r is refused" % tag[:28], code == 3,
                  "exit %s\n%s%s" % (code, out, err))
            check("tag %r: nothing written" % tag[:28], not out_path.exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    print("     ...and a tag colliding with a kind-derived count is refused too")
    root = make_store([record("s-%d" % i) for i in range(6)],
                      triage=[human_tag("s-0", "comment")])
    try:
        code, _doc, _out, err, _p = generate(root)
        check("tag 'comment' collides with the kind count and is refused",
              code == 3, err)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def s13_utf8_under_cp1252():
    print("\nS13 UTF-8 store content under PYTHONIOENCODING=cp1252")
    root = make_store([record("u-%d" % i, text="emoji \U0001f600 dash — quote “x”")
                       for i in range(6)])
    try:
        code, doc, out, err, _p = generate(root,
                                           env_extra={"PYTHONIOENCODING": "cp1252"})
        check("the run did not die on the first print", code == 0,
              "exit %s\n%s%s" % (code, out, err))
        check("no UnicodeEncodeError", "UnicodeEncodeError" not in err, err)
        check("counts are correct", doc and doc["counts"].get("comment") == 6,
              json.dumps(doc) if doc else err)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    print("Forcing the hazards contract §9 names.")
    if not GEN.exists():
        print("FAIL: %s does not exist" % GEN)
        return 1
    for fn in (s1_below_k_is_withheld, s2_regex_tag_has_no_route_in,
               s3_unattributed_human_claim_refuses, s4_flags_are_not_categories,
               s5_untriaged_publishes_at_one, s6_missing_reader_refuses,
               s7_lossy_reader_refuses, s8_duplicates_counted_once,
               s9_no_content_reaches_the_file, s10_tombstones_still_count,
               s11_no_total_is_published, s12_unsafe_tag_shape_refused,
               s13_utf8_under_cp1252):
        # A block that raises loses its own remaining checks and every block
        # after it. Found by mutation-testing this file: publishing a `total`
        # key failed the right checks, then crashed on a missing output file and
        # swallowed the summary.
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
    print("OK: every §9 hazard was forced and the refusal observed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
