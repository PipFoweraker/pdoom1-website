#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Destructive suite for the feedback intake endpoint -- rows F1-F6 and F9-F15 of
docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §6.

    python scripts/test-ingest-destructive.py            (exit 0 = every row green)
    python scripts/test-ingest-destructive.py --list      (row table, always exit 0)

WHICH WORKFLOW SHOULD RUN THIS (agent A4 owns the wiring; this file must not)
----------------------------------------------------------------------------
  .github/workflows/content-honesty.yml, as a BLOCKING step, in the SAME PR that
  lands public/ingest.php -- not before.

  Two conditions on that wiring, both earned by this repo:

  a) Until the endpoint exists this suite is RED by design (Gate 2), and CLAUDE.md
     is explicit that "a red test in the suite is worse than no test" because it
     teaches everyone to skip the suite. So it stays hand-run until A1 lands, then
     it goes blocking. Do not park it half-wired; do not let it sit red in CI.

  b) The producer of the data it guards is the visitor, not a bot -- but the pages
     it guards ship through `public/`, and the deploy fires ~4x/day on a
     `workflow_run` trigger that runs no tests at all. A push-path filter alone
     therefore does NOT mean "this ran before those bytes were live". Give it the
     daily `schedule` backstop that content-honesty.yml already carries.

WHAT THIS FILE IS, AND WHAT IT DELIBERATELY IS NOT
--------------------------------------------------
Written by agent A3 from the contract ALONE, before any implementation existed, so
that the tests cannot encode the implementation's bugs. Nobody who wrote a line of
the endpoint wrote a line of this file. If a row here disagrees with
public/ingest.php, the contract is the tiebreaker -- not this file and not the
endpoint.

Every row INJECTS a fault and OBSERVES the consequence. There is no row that
merely watches a guard pass: "a guard seen only in its passing state has not been
shown to work", and green is equally consistent with "the condition is safe" and
"the check never fires".

The subject under test is resolved by scripts/fixtures/ingest_harness.py and
PRINTED at the top of every run. With no endpoint present it is the deliberately
naive stub, and most rows below are expected to be RED. That is the deliverable,
not a defect.

ONE FAULT PER ROW -- AND §11.3 IS F9'S FAULT, NOBODY ELSE'S (2026-08-17)
------------------------------------------------------------------------
The first CI run against the real endpoint had F3 and F4 red, and neither had
found a defect. §11.3 throttles PER IP (prose: burst 5, refill 10/hour) and every
request the harness sends carries the same REMOTE_ADDR by default, so any row
issuing more than five prose submissions in a second was answered 429 from step 7
-- upstream of the store, the lock, and the dedup rule those rows exist to test.
F4 read `expected 16, found 5` as a broken flock(); F3 read `429 then 429` as a
write-time dedup index. Both were reading F9.

So: a row that is not about the throttle sends each request from its own client
address (see client_ip()), which is also the honest model of the fault -- sixteen
simultaneous appends are sixteen visitors. F9 keeps sending from one address,
because that is its fault, and it passes. Rule to keep: when a row goes red,
check which step of the endpoint answered it before believing what it says.

WHAT A ROW CANNOT DO IS PASS QUIETLY
------------------------------------
Verdicts are PASS / FAIL / SKIP / UNINJECTABLE, and only PASS is green. A SKIP
prints its reason and the platform fact that caused it. An UNINJECTABLE row prints
what would have to exist for it to be injectable. Neither is ever counted as
evidence that the invariant holds.
"""

import argparse
import importlib.util
import itertools
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
import ingest_harness as H  # noqa: E402  (must follow the sys.path line)

REPO_ROOT = Path(__file__).resolve().parents[1]
PURGE = REPO_ROOT / "scripts" / "purge-feedback.py"
IS_WINDOWS = os.name == "nt"

# ---------------------------------------------------------------------------
# One client address per request, where the row is not about the client
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS (measured 2026-08-17, the suite's first CI run against the real
# public/ingest.php under PHP 8.2)
# --------------------------------------------------------------------------
# §11.3 throttles PER IP: prose (comment/bug/feature/question/feedback) gets a
# burst of 5 and a refill of 10/hour, i.e. 0.0028 tokens per second. Every
# request the harness sends carries the SAME REMOTE_ADDR by default
# (ingest_harness.build_env's `remote_addr="203.0.113.7"`), so a row that issues
# more than five prose submissions in a second is one client emptying one bucket,
# and everything after the fifth is a 429 that never reaches the code the row is
# about.
#
# That is exactly what happened. F4 issues 16 prose POSTs: 5 x 200, 11 x 429,
# five records on disk, and its `expected 16, found 5` read as a broken append.
# F3 issues 3 baselines + 13 crash attempts + 2 retries: the first five wrote and
# the rest were paced, so its INV-1e retry pair came back `429 then 429` and its
# read-time-dedup check collapsed nothing because there was nothing to collapse.
# Neither row had found a defect. Both had found F9.
#
# The throttle is not the thing under test in either row -- F9 is the row that
# tests the throttle, it PASSES, and it must keep sending from one address. So
# the rows that are about the STORE send from distinct addresses, which is also
# the honest model of the fault they inject: sixteen simultaneous appends are
# sixteen visitors, and one visitor firing sixteen prose submissions in a second
# is F9's scenario by definition.
#
# No test seam was added to the endpoint for this. REMOTE_ADDR is not a seam: it
# is a real request property that a web SAPI sets and that
# scripts/fixtures/php_cli_shim.php already maps from PDOOM_REMOTE_ADDR, declared
# in the harness docstring since before the endpoint existed. Nothing here can be
# reached from a request.
#
# 198.51.100.0/24 is TEST-NET-2 (RFC 5737), reserved for documentation and
# guaranteed never to be a real client. It is a DIFFERENT block from the
# harness's own default (203.0.113.7, TEST-NET-3), so a row using this allocator
# can never collide with a row that deliberately does not.

_IP_SEQ = itertools.count(1)


def client_ip():
    """A fresh, never-reused client address.

    Raises rather than wrapping. A wrapped counter would silently hand two
    requests the same throttle bucket again, which is the confound this function
    exists to remove -- and it would do it invisibly, months later, when somebody
    added a row.
    """
    n = next(_IP_SEQ)
    if n > 254:
        raise RuntimeError(
            "the destructive suite has asked for more than 254 distinct client "
            "addresses in one run. 198.51.100.0/24 is exhausted. Widen the block "
            "here -- do NOT wrap, because a reused address silently reintroduces "
            "the per-IP throttle into a row that is not about the throttle.")
    return "198.51.100.%d" % n


# ---------------------------------------------------------------------------
# Row plumbing
# ---------------------------------------------------------------------------

ROWS = []


class Row(object):
    def __init__(self, rid, title, fault, invariants):
        self.id = rid
        self.title = title
        self.fault = fault
        self.invariants = invariants
        self.checks = []      # (ok, invariant, message)
        self.notes = []
        self.skipped = None
        self.uninjectable = None
        self.fn = None

    # An assertion that does not name the invariant it defends is a assertion
    # nobody can act on six months later, so `inv` is not optional.
    def check(self, ok, inv, message):
        self.checks.append((bool(ok), inv, message))
        return bool(ok)

    def note(self, text):
        self.notes.append(text)

    def skip(self, reason):
        self.skipped = reason

    def cannot_inject(self, reason):
        self.uninjectable = reason

    @property
    def verdict(self):
        if self.uninjectable:
            return "UNINJECTABLE"
        if self.skipped and not self.checks:
            return "SKIP"
        if not self.checks:
            return "UNINJECTABLE"
        return "PASS" if all(c[0] for c in self.checks) else "FAIL"


def row(rid, title, fault, invariants):
    def deco(fn):
        r = Row(rid, title, fault, invariants)
        r.fn = fn
        ROWS.append(r)
        return fn
    return deco


class Workspace(object):
    """A throwaway filesystem for one row. Nothing here reads or writes a
    committed fixture, `public/`, or anything the repo ships."""

    def __init__(self, tag):
        self.root = Path(tempfile.mkdtemp(prefix="pdoom-feedback-%s-" % tag))
        self.docroot = self.root / "example.com" / "public"
        self.docroot.mkdir(parents=True)
        self.store = self.root / "feedback-store"
        self.mail = self.root / "mail-sink.jsonl"

    def cleanup(self):
        # Teardown only. Nothing here is an observation, and nothing here may
        # raise: a throwaway temp dir that resists deletion must not be able to
        # score a row that has already finished asserting.
        #
        # The obvious spelling of this is wrong, and cost F1 its whole verdict on
        # the suite's first-ever run (2026-08-17). It was:
        #
        #     def _force(func, path, _exc):
        #         try:
        #             os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        #             func(path)          # <-- retry "the operation that failed"
        #         except OSError:
        #             pass
        #
        # `func` is whatever rmtree was calling, and on POSIX -- where
        # shutil._use_fd_functions is true -- rmtree walks with directory file
        # descriptors, so on a 0-mode directory it fails inside
        #     os.open(path, os.O_RDONLY | os.O_NONBLOCK, dir_fd=...)
        # and reports it as `onerror(os.open, path, exc)` (Lib/shutil.py:748).
        # Re-calling that as `func(path)` is `os.open(path)` with no `flags`:
        # TypeError, which `except OSError` does not catch. It escaped cleanup,
        # escaped f1()'s `finally`, and the runner scored the row FAIL -- after
        # all ten of its checks had already passed. _f1_chmod_000 is the only
        # injection that makes a directory unopenable, which is why F1 was the
        # only row to hit it, and why Windows never saw it (_use_fd_functions is
        # false there, and mode bits on a directory are a no-op anyway).
        #
        # So: restore the modes FIRST, top-down, and never re-invoke `func`.
        # os.walk is top-down and scandirs each directory only when it reaches
        # it, so chmodding a subdirectory here happens before the walk descends
        # into it.
        for dirpath, dirnames, filenames in os.walk(self.root):
            for name in dirnames + filenames:
                try:
                    os.chmod(os.path.join(dirpath, name), stat.S_IRWXU)
                except OSError:
                    pass

        def _relax(_func, path, _exc):
            # Last resort for anything the walk could not reach. Chmod and
            # return: rmtree retries the entry itself, and a leaked temp dir is
            # a smaller harm than a teardown that can fail a row.
            try:
                os.chmod(path, stat.S_IRWXU)
            except OSError:
                pass

        shutil.rmtree(self.root, onerror=_relax)

    def env(self, **over):
        base = dict(store=self.store, docroot=self.docroot, mail_sink=self.mail)
        base.update(over)
        return base


def payload(**over):
    p = {
        "rid": str(uuid.uuid4()),
        "kind": "bug",
        "page": "/blog/post.html?p=alpha-launch.md",
        "text": "the download button 404s on the linux build",
        "contact": "",
        "credit": "",
        "client_ts": int(time.time()),
        "elapsed_ms": 8400,
        "hp": "",
        "attempt": 1,
    }
    p.update(over)
    return p


# ---------------------------------------------------------------------------
# Positive control for the mail seam.
#
# F1 asserts NO mail was sent and F5 asserts a mail failure was recorded. Both are
# claims about the contents of PDOOM_MAIL_SINK, and an implementation that ignores
# the seam entirely produces an empty sink -- which looks exactly like "no mail was
# sent". "Absence of a marker is never a clean bill of health", so the absence is
# only admissible as evidence once the presence has been demonstrated on a
# known-good request.
# ---------------------------------------------------------------------------

MAIL_SEAM = {"ok": False, "why": "not probed"}


def probe_mail_seam():
    ws = Workspace("mailprobe")
    try:
        r = H.post(payload(kind="bug", text="positive control for the mail seam"),
                   **ws.env())
        lines = H.mail_lines(ws.mail)
        if r.status == 200 and lines:
            MAIL_SEAM["ok"] = True
            MAIL_SEAM["why"] = "happy-path prose submission wrote %d line(s) to the sink" % len(lines)
        else:
            MAIL_SEAM["ok"] = False
            MAIL_SEAM["why"] = (
                "happy-path prose submission returned %s and wrote %d sink line(s); "
                "the endpoint does not honour PDOOM_MAIL_SINK, so 'no mail was sent' "
                "is unobservable and must not be read as evidence"
                % (r.status, len(lines))
            )
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F1 -- store dir unwritable
# ---------------------------------------------------------------------------

@row("F1", "store dir unwritable",
     "the store root is replaced by something that cannot be appended to",
     "INV-1, INV-1d")
def f1(r):
    variants = [("not-a-directory", _f1_file_in_the_way)]
    if not IS_WINDOWS:
        variants.append(("chmod-000", _f1_chmod_000))
    else:
        r.note("chmod-000 variant not run: Windows ignores mode bits on directories, "
               "so os.chmod(dir, 0) is a no-op and would inject nothing. The "
               "not-a-directory variant is the portable injection.")

    for name, inject in variants:
        ws = Workspace("F1-" + name)
        try:
            inject(ws)
            resp = H.post(payload(text="store is unwritable, %s" % name), **ws.env())
            r.check(resp.status == 507, "INV-1d",
                    "[INV-1d] %s: unwritable store must return 507, got %s "
                    "(never degrade to mail-only)" % (name, resp.status))
            r.check(resp.field("retryable") is True, "INV-1",
                    "[INV-1] %s: 507 body must carry retryable:true so the client keeps "
                    "the message; got %r" % (name, resp.field("retryable")))
            r.check(resp.field("ok") is not True, "INV-1",
                    "[INV-1] %s: no success state may be shown without a durable write; "
                    "body claimed ok=%r" % (name, resp.field("ok")))
            wrote = H.store_lines(ws.store) if ws.store.is_dir() else []
            r.check(not wrote, "INV-1",
                    "[INV-1] %s: nothing may be recorded as stored when the store is "
                    "unwritable; found %d line(s)" % (name, len(wrote)))
            if MAIL_SEAM["ok"]:
                mails = H.mail_lines(ws.mail)
                r.check(not mails, "INV-1d",
                        "[INV-1d] %s: mail must NOT be sent when the durable write "
                        "failed -- that is the mail-only degradation the contract "
                        "forbids; found %d notification(s)" % (name, len(mails)))
            else:
                r.check(False, "INV-1d",
                        "[INV-1d] %s: cannot observe 'no mail sent' -- %s"
                        % (name, MAIL_SEAM["why"]))
        finally:
            ws.cleanup()


def _f1_file_in_the_way(ws):
    # A regular file where the store directory must be. Every mkdir and every
    # fopen('<store>/YYYY-MM.jsonl','ab') under it fails with ENOTDIR. Portable,
    # and closer to a real shared-hosting misconfiguration than chmod is.
    ws.store.write_text("not a directory\n", encoding="utf-8")


def _f1_chmod_000(ws):
    ws.store.mkdir(parents=True, exist_ok=True)
    os.chmod(ws.store, 0)


# ---------------------------------------------------------------------------
# F2 -- disk full mid-append
# ---------------------------------------------------------------------------

@row("F2", "disk full mid-append",
     "the append is made to fail, once outright and once by truncation",
     "INV-1")
def f2(r):
    # Part A: the month file becomes unappendable AFTER a good record is in it.
    # This is the portable half -- an append that fails outright.
    ws = Workspace("F2a")
    try:
        first = H.post(payload(text="first record, must survive"), **ws.env())
        r.check(first.status == 200, "INV-1",
                "[INV-1] setup: the first (healthy) append must succeed, got %s"
                % first.status)
        files = H.store_files(ws.store)
        r.check(len(files) == 1, "INV-1",
                "[INV-1] setup: expected exactly one store file, found %d" % len(files))
        for f in files:
            os.chmod(f, stat.S_IREAD)
        second = H.post(payload(text="second record, the append must fail"), **ws.env())
        r.check(second.status == 507, "INV-1",
                "[INV-1] a failed append must return 507, got %s" % second.status)
        r.check(second.field("ok") is not True, "INV-1",
                "[INV-1] a failed append must never compose a 200; body ok=%r"
                % second.field("ok"))
        lines = H.store_lines(ws.store)
        recs = H.store_records(ws.store)
        r.check(len(lines) == len(recs) == 1, "INV-1",
                "[INV-1] the store must hold exactly the one complete record and no "
                "partial line; %d physical line(s), %d parse" % (len(lines), len(recs)))
    finally:
        for f in H.store_files(ws.store):
            try:
                os.chmod(f, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
        ws.cleanup()

    # Part B: a genuinely torn write -- the append is cut in half by RLIMIT_FSIZE.
    if IS_WINDOWS:
        r.note("torn-write half SKIPPED: RLIMIT_FSIZE is POSIX-only and Windows has "
               "no portable way to make a write return short. Run this suite on the "
               "Linux CI runner to exercise it -- on Windows the row is proven only "
               "against an append that fails outright, which is the weaker fault.")
        return

    import resource  # noqa: E402  (POSIX-only, guarded above)

    ws = Workspace("F2b")
    try:
        ok = H.post(payload(text="A" * 2000), **ws.env())
        r.check(ok.status == 200, "INV-1",
                "[INV-1] setup: healthy 2KB append must succeed, got %s" % ok.status)
        size = sum(p.stat().st_size for p in H.store_files(ws.store))
        cap = size + 400          # enough for part of the next line, never all of it

        def _cap():
            resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))

        torn = H.post(payload(text="B" * 2000), preexec=_cap, **ws.env())
        r.check(torn.status in (507, 500) and torn.field("ok") is not True, "INV-1",
                "[INV-1] a torn append must not produce a success state; got status %s "
                "ok=%r" % (torn.status, torn.field("ok")))
        r.check(torn.status == 507, "INV-1",
                "[INV-1] a torn append must be reported as 507 (retryable storage "
                "failure), got %s" % torn.status)
        lines = H.store_lines(ws.store)
        recs = H.store_records(ws.store)
        r.check(len(lines) == len(recs), "INV-1",
                "[INV-1] no partial line may remain after a torn append: %d physical "
                "line(s) but only %d parse as JSON" % (len(lines), len(recs)))
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F3 -- fatal after write, before response
# ---------------------------------------------------------------------------

@row("F3", "fatal after write, before response",
     "the endpoint process is killed at sampled offsets across its whole lifetime",
     "INV-1, INV-1e")
def f3(r):
    # The contract's fault is "fatal AFTER the write, BEFORE the response". Nothing
    # in the contract gives a test a hook at that instant, and inventing one
    # (PDOOM_FAULT=...) would make the test depend on a branch that only exists for
    # the test -- so the kill is external and its timing is SAMPLED across the run,
    # a crash campaign rather than a single surgical kill. That is strictly
    # stronger: it covers before-write, mid-write and after-write, and the
    # invariant is the same at every offset.
    ws = Workspace("F3")
    try:
        # The window to kill in is measured from the moment the child EXISTS, not
        # from the moment the test asked for one.
        #
        # The first version of this row scaled its kill delays by the whole
        # request duration and landed 0 kills out of 12 while reporting a
        # campaign. Measured cause: subprocess creation on this Windows box costs
        # 370-1150 ms (antivirus), while the endpoint's own work costs ~50 ms --
        # so every delay derived from the total was already past the child's
        # death. The injection was failing silently and the row's other checks
        # were reading a store that nothing had crashed. Keep the two measurements
        # separate.
        #
        # Every request below comes from its OWN client address (see client_ip()).
        # This row injects a crash campaign, not a burst: 16 prose submissions
        # from one address is F9's fault, and before 2026-08-17 it was silently
        # this row's fault too -- the campaign emptied the §11.3 prose bucket by
        # its fifth request and the rest were 429ed before append_record() was
        # ever reached.
        spans = []
        for _ in range(3):
            p = H.spawn(payload(text="baseline timing probe"),
                        remote_addr=client_ip(), **ws.env())
            t0 = time.time()
            b = H.collect(p)
            spans.append(time.time() - t0)
            r.check(b.status == 200, "INV-1",
                    "[INV-1] setup: baseline request must succeed, got %s" % b.status)
        span = sorted(spans)[1]

        killed = 0
        attempts = 0
        # Half the campaign kills at sampled offsets across the child's lifetime;
        # the other half watches the store file and kills the instant it grows,
        # which is the contract's literal fault -- fatal AFTER the write, BEFORE
        # the response.
        for frac in (0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1):
            attempts += 1
            p = H.spawn(payload(text="crash campaign at %.2f x span" % frac),
                        remote_addr=client_ip(), **ws.env())
            time.sleep(span * frac)
            if p.poll() is None:
                p.kill()
                killed += 1
            H.collect(p)
        for _ in range(4):
            attempts += 1
            before = _store_size(ws.store)
            p = H.spawn(payload(text="crash campaign, kill on first byte written"),
                        remote_addr=client_ip(), **ws.env())
            deadline = time.time() + max(span * 4, 1.0)
            while time.time() < deadline:
                if _store_size(ws.store) > before and p.poll() is None:
                    p.kill()
                    killed += 1
                    break
                if p.poll() is not None:
                    break
            H.collect(p)

        r.check(killed > 0, "INV-1",
                "[INV-1] the injection must actually land -- if the endpoint is never "
                "killed mid-flight, every check below is reading an uncrashed store. "
                "%d of %d attempts landed (child lifetime %.0f ms)"
                % (killed, attempts, span * 1000))
        r.note("killed the endpoint mid-flight in %d of %d attempts "
               "(child lifetime %.0f ms, samples %s ms)"
               % (killed, attempts, span * 1000, [round(s * 1000) for s in spans]))

        lines = H.store_lines(ws.store)
        recs = H.store_records(ws.store)
        r.check(len(lines) == len(recs), "INV-1",
                "[INV-1] a fatal must never leave a partial line in the store: %d "
                "physical line(s) survived the campaign, %d parse as JSON"
                % (len(lines), len(recs)))

        # The client's response to this fault is to retry the SAME rid. The writer
        # must accept it -- rejecting a write to prevent a duplicate is the one
        # thing INV-1e forbids outright.
        #
        # BOTH halves of the retry come from ONE address, and that address is a
        # FRESH one. Both halves matter and for opposite reasons:
        #
        #   same address -- a real retry comes from the client that sent the
        #   original. Sending the two halves from two addresses would still
        #   detect a write-time dedup index (the defect INV-1e names), but it
        #   would test a request pair no visitor ever makes.
        #
        #   fresh address -- the crash campaign above has just spent this row's
        #   requests. Reusing its address would put the pair behind whatever the
        #   campaign left in the §11.3 bucket, and a 429 here says nothing about
        #   dedup. §11.3's prose burst is 5, so a full bucket covers a pair with
        #   room to spare.
        #
        # WHAT THIS DELIBERATELY DOES NOT TEST, because the contract has not
        # decided it: a retry that arrives while the client's own bucket is
        # EMPTY. INV-1e ("rejecting a write to prevent a duplicate is not
        # acceptable") and §11.3 ("a per-IP throttle returns 429") both apply to
        # that request and the contract does not say which wins. A 429 is
        # retryable and the outbox holds the message, so it is arguably not a
        # rejection at all -- but that is a reading, not a ruling, and this file
        # is not the place to make one. Written up for Pip in the report
        # accompanying branch fix/intake-throttle-vs-f3f4. Do not resolve it by
        # editing the assertion below.
        retry_ip = client_ip()
        rid = str(uuid.uuid4())
        a = H.post(payload(rid=rid, text="retry after a lost response", attempt=1),
                   remote_addr=retry_ip, **ws.env())
        b = H.post(payload(rid=rid, text="retry after a lost response", attempt=2),
                   remote_addr=retry_ip, **ws.env())
        r.check(a.status == 200 and b.status == 200, "INV-1e",
                "[INV-1e] a repeated rid must be accepted, never rejected to prevent a "
                "duplicate; got %s then %s" % (a.status, b.status))
        same = [x for x in H.store_records(ws.store) if x.get("rid") == rid]
        r.check(len(same) == 2, "INV-1e",
                "[INV-1e] duplicates are acceptable and must both be durable: expected "
                "2 records for the retried rid, found %d" % len(same))
        r.check(all(x.get("server_ts") for x in same), "INV-1e",
                "[INV-1e] each duplicate needs a server_ts so a reader can keep the "
                "earliest; got %r" % [x.get("server_ts") for x in same])

        # The other half of the row -- "read-time dedup collapses" -- needs a reader.
        reader = os.environ.get("PDOOM_FEEDBACK_READER") or str(REPO_ROOT / "scripts" / "read-feedback.py")
        if not Path(reader).exists():
            r.check(False, "INV-1e",
                    "[INV-1e] no read-time collapser exists (looked for %s, and "
                    "$PDOOM_FEEDBACK_READER is unset). §3 puts dedup at READ time, so "
                    "until that reader exists the duplicates this row just proved are "
                    "correct are also uncollapsed -- the invariant is half-built, not "
                    "satisfied" % Path(reader).name)
        else:
            out = subprocess.run(
                [sys.executable, reader, "--store", str(ws.store), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(REPO_ROOT))
            try:
                doc = json.loads(out.stdout)
                collapsed = [x for x in doc.get("records", []) if x.get("rid") == rid]
            except Exception:
                collapsed = None
            r.check(collapsed is not None and len(collapsed) == 1, "INV-1e",
                    "[INV-1e] the reader must collapse the two duplicate rids to one "
                    "record; got %r" % (None if collapsed is None else len(collapsed)))
            if collapsed:
                r.check(collapsed[0].get("server_ts") == min(x["server_ts"] for x in same),
                        "INV-1e",
                        "[INV-1e] the collapsed record must keep the EARLIEST server_ts")
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F4 -- two concurrent POSTs
# ---------------------------------------------------------------------------

@row("F4", "concurrent POSTs",
     "16 requests from 16 clients are started simultaneously, then each of the two "
     "locks the endpoint must take is held by the test in turn",
     "§3 append discipline")
def f4(r):
    ws = Workspace("F4")
    try:
        n = 16
        rids = [str(uuid.uuid4()) for _ in range(n)]
        # Near the §2 cap, so each record is thousands of bytes: a big record is
        # what turns an unlocked multi-write append into an interleaved one. Under
        # the cap on purpose -- this row is about locking, not about 413.
        #
        # SIXTEEN VISITORS, NOT ONE VISITOR SIXTEEN TIMES (fixed 2026-08-17).
        # Every POST here used to carry the harness's single default REMOTE_ADDR,
        # so §11.3's prose bucket (burst 5, refill 10/hour) admitted exactly five
        # and 429ed eleven -- and this row read `expected 16, found 5` as a
        # failure of flock(). It was not: the eleven never reached the append at
        # all. Concurrency on a public endpoint is many clients at once; one
        # client at sixteen-per-second is F9's fault, F9 injects it, and F9
        # passes. See client_ip().
        procs = [H.spawn(payload(rid=rid, text=("row-%d " % i) + ("x" * 4800)),
                         remote_addr=client_ip(), **ws.env())
                 for i, rid in enumerate(rids)]
        responses = [H.collect(p) for p in procs]

        ok = [x for x in responses if x.status == 200]
        r.check(len(ok) == n, "INV-1",
                "[INV-1] all %d concurrent POSTs must be answered honestly; %d returned "
                "200, statuses=%s" % (n, len(ok), sorted(x.status for x in responses)))
        lines = H.store_lines(ws.store)
        recs = H.store_records(ws.store)
        r.check(len(lines) == len(recs) == n, "§3",
                "[§3] flock(LOCK_EX) must keep every record on its own intact line: "
                "expected %d, found %d physical line(s) of which %d parse"
                % (n, len(lines), len(recs)))
        interleaved = [ln for ln in lines if ln.count('"rid"') > 1]
        r.check(not interleaved, "§3",
                "[§3] no line may contain two records; %d line(s) carry more than one "
                'occurrence of "rid", which is an interleaved append'
                % len(interleaved))
        got = sorted(x.get("rid") for x in recs)
        r.check(got == sorted(rids), "INV-1",
                "[INV-1] every concurrent submission must survive: %d of %d rids present"
                % (len(set(got) & set(rids)), n))
        truncated = [x for x in recs if len(x.get("text") or "") < 4800]
        r.check(not truncated, "§3",
                "[§3] no record may lose text under concurrency (a short write, not a "
                "lock); %d record(s) came back shorter than they went in"
                % len(truncated))

        # THE OUTCOME HALF ABOVE IS PROBABILISTIC AND MUST NOT BE TRUSTED ALONE.
        # The window in which two appends can collide is microseconds wide, so a
        # lock-free writer passes it most of the time. A green from those checks
        # is evidence that nothing collided on this run, NOT evidence that a lock
        # exists -- the same shape as "a guard seen only in its passing state".
        #
        # The deterministic half: hold each lock the endpoint is supposed to take
        # and watch whether it waits. A lock-free writer sails past and answers
        # immediately, which is directly observable as a duration.
        _f4_lock_probe(r, ws)
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# The lock probe. Rewritten 2026-08-17 -- the previous version could not observe
# the thing it named.
#
# WHAT IT USED TO CONCLUDE, AND WHY THAT WAS LIBEL
# ------------------------------------------------
# It held flock(LOCK_EX) on the month file, POSTed, and on a short duration
# printed "so it is not taking the exclusive lock §3 prescribes". Its POST came
# from the same address as the sixteen above, which had already emptied §11.3's
# prose bucket -- so the endpoint answered 429 in 47 ms from step 7, roughly a
# hundred lines of PHP BEFORE append_record() and its lock exist. The probe was
# not measuring a lock-free append. It was measuring a request that never
# attempted an append, and it reported that as proof of a missing lock. A verdict
# reached before the code under test runs cannot distinguish a compliant endpoint
# from a broken one, and it read as the second.
#
# THERE ARE TWO LOCKS NOW, AND THE PROBE TAKES BOTH
# -------------------------------------------------
#   A) <store>/.write-lock, the store-wide lock. Its whole purpose is that its
#      inode never changes, so a purge holding it across read -> os.replace() and
#      an ingest holding it across an append can see each other. A probe that
#      only ever locks the month file cannot observe it AT ALL: the purge swaps
#      that inode out, which is the defect the lock was added to fix.
#      This half deliberately takes the lock by calling
#      scripts/purge-feedback.py's own store_write_lock() rather than by opening
#      a path spelled out here. The property under test is that the two writers
#      agree on one object; asserting that against a literal typed into this file
#      would let both of them move and still pass.
#   B) the month file, which §3 literally prescribes (flock($fh, LOCK_EX)) and
#      which still serialises two concurrent POSTs on its own.
#
# AND IT CARRIES ITS OWN CONTROL
# ------------------------------
# "The endpoint took 1.5 s" only means "it waited" if an uncontended request does
# not. So an uncontended POST is timed first and the hold is scaled from it. If
# the box is slow enough that the two cannot be told apart, the probe says so
# rather than returning a green nobody can read.
# ---------------------------------------------------------------------------

LOCK_PROBE_MAX_HOLD = 10.0


def _f4_lock_probe(r, ws):
    if IS_WINDOWS:
        r.note("lock-hold probe SKIPPED: flock is advisory on POSIX, which is what "
               "makes the probe a clean discriminator. Windows byte-range locks are "
               "MANDATORY, so holding one blocks any writer including a compliant "
               "one, and the probe would prove nothing. On Windows this row rests on "
               "the probabilistic half alone -- treat a PASS here as WEAK and re-run "
               "the suite on the Linux CI runner before believing it.")
        return
    import fcntl  # noqa: E402  (POSIX-only, guarded above)

    files = H.store_files(ws.store)
    if not files:
        r.check(False, "§3",
                "[§3] lock probe could not run: no store file exists to lock")
        return

    # The control. A fresh address, nothing held, so this measures the endpoint's
    # own cost -- process start, parse, validate, append, fsync.
    control = H.post(payload(text="lock probe control: no lock is held"),
                     remote_addr=client_ip(), timeout=30, **ws.env())
    r.check(control.status == 200, "§3",
            "[§3] lock probe control: an UNCONTENDED append must be a 200, got %s. "
            "Without a working control the timings below discriminate nothing."
            % control.status)
    uncontended = control.duration
    hold = max(1.5, uncontended * 6.0)
    r.note("lock probe control: an uncontended append took %.0f ms, so each lock "
           "is held for %.0f ms and anything under %.0f ms counts as 'did not wait'"
           % (uncontended * 1000, hold * 1000, hold * 500))
    if hold > LOCK_PROBE_MAX_HOLD:
        # Not a lock failure and not something to paper over: on this box a
        # normal request is slow enough that "waited" and "did not wait" are the
        # same measurement, so the probe cannot answer. Say that out loud.
        r.check(False, "§3",
                "[§3] the lock probe cannot discriminate on this machine: an "
                "UNCONTENDED append took %.0f ms, so a hold long enough to be "
                "unmistakable would exceed the %.0fs ceiling. This is a statement "
                "about the runner, not about the endpoint -- do not read it as "
                "either a passing or a failing lock."
                % (uncontended * 1000, LOCK_PROBE_MAX_HOLD))
        return

    purge = _load_purge()
    if purge is None:
        r.check(False, "§3",
                "[§3] the store-wide write lock cannot be probed: %s is missing or "
                "will not import, so nothing in this suite can hold the lock the "
                "OTHER writer takes. <store>/.write-lock exists precisely so the "
                "purge and the endpoint serialise against each other, and that "
                "property is currently unobserved." % PURGE.name)
    else:
        _hold_and_post(
            r, ws,
            label="<store>/%s, taken via purge-feedback.store_write_lock()"
                  % purge.LOCK_NAME,
            cm=purge.store_write_lock(ws.store, 15.0),
            hold=hold, uncontended=uncontended,
            consequence="the purge rewrites the store while a visitor is mid-append, "
                        "and a record the endpoint has already answered 200 for is "
                        "dropped by os.replace() with nothing anywhere recording the "
                        "loss")

    _hold_and_post(
        r, ws,
        label="the month file %s, flock(LOCK_EX) as §3 prescribes" % files[0].name,
        cm=_flock_held(fcntl, files[0]),
        hold=hold, uncontended=uncontended,
        consequence="two simultaneous POSTs on shared hosting interleave and one "
                    "visitor's record is written through the middle of another's")


def _load_purge():
    """scripts/purge-feedback.py as a module, or None.

    Imported for ONE symbol -- the lock helper -- so that this suite takes the
    store-wide lock the same way the only other writer to the store does. None,
    never a substitute: a probe that quietly locked some other path would report
    a serialisation that does not exist.
    """
    if not PURGE.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("purge_for_lock_probe", PURGE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    if not hasattr(module, "store_write_lock") or not hasattr(module, "LOCK_NAME"):
        return None
    return module


class _flock_held(object):
    """Context manager: flock(LOCK_EX) on one path, released on exit."""

    def __init__(self, fcntl_mod, path):
        self._fcntl = fcntl_mod
        self._path = path
        self._fh = None

    def __enter__(self):
        self._fh = open(self._path, "ab")
        self._fcntl.flock(self._fh.fileno(), self._fcntl.LOCK_EX)
        return self._path

    def __exit__(self, *_exc):
        try:
            self._fcntl.flock(self._fh.fileno(), self._fcntl.LOCK_UN)
        except OSError:
            pass
        self._fh.close()
        return False


def _hold_and_post(r, ws, label, cm, hold, uncontended, consequence):
    """Hold one lock on a background thread, POST, and measure the wait.

    The lock is released BY THE HOLDER after `hold` seconds, not after the POST
    returns. That order is the whole reason this is a thread and not a `with`
    block around the POST: a COMPLIANT endpoint blocks, so releasing afterwards
    would deadlock the test and score correct behaviour as a hang.
    """
    import threading

    ready = threading.Event()
    release = threading.Event()
    holder_error = {}

    def _holder():
        try:
            with cm:
                ready.set()
                release.wait(hold)
        except Exception as exc:            # noqa: BLE001 -- reported, not swallowed
            holder_error["exc"] = exc
            ready.set()

    thread = threading.Thread(target=_holder, name="lock-holder", daemon=True)
    thread.start()
    try:
        if not ready.wait(30.0):
            r.check(False, "§3",
                    "[§3] the probe could not take %s within 30s, so nothing below "
                    "was measured. Something else is holding it." % label)
            return
        if "exc" in holder_error:
            r.check(False, "§3",
                    "[§3] the probe could not take %s: %r. The endpoint was not "
                    "tested against it." % (label, holder_error["exc"]))
            return

        rid = str(uuid.uuid4())
        started = time.time()
        # A fresh client address. This request must reach append_record(); a 429
        # from §11.3 would be answered before the lock is ever touched, and that
        # is exactly how this probe came to report a working lock as a missing
        # one on 2026-08-17.
        resp = H.post(payload(rid=rid,
                              text="this append must queue behind %s" % label),
                      remote_addr=client_ip(),
                      timeout=max(60.0, hold * 6),
                      **ws.env())
        waited = time.time() - started
    finally:
        release.set()
        thread.join(30.0)

    r.note("lock-hold probe [%s]: endpoint answered %s after %.0f ms (control %.0f ms, "
           "lock held %.0f ms)" % (label, resp.status, waited * 1000,
                                   uncontended * 1000, hold * 1000))

    # 429 is called out separately because it is the ONE status that means the
    # measurement is void rather than bad: the request was refused upstream of
    # the append, so it says nothing about any lock. It must not be able to hide
    # inside a generic "did not wait".
    r.check(resp.status != 429, "§3",
            "[§3] the probe request was throttled (429) while %s was held, so it "
            "never reached the append and this row measured nothing about the "
            "lock. Every probe request must come from a fresh client address."
            % label)
    r.check(resp.status == 429 or waited >= hold * 0.5 or resp.status == 507, "§3",
            "[§3] the endpoint did NOT wait for %s: it answered %s after %.0f ms "
            "while the lock was held for %.0f ms, against an uncontended control of "
            "%.0f ms. It is therefore appending without taking that lock, and %s"
            % (label, resp.status, waited * 1000, hold * 1000, uncontended * 1000,
               consequence))
    if resp.status == 200:
        # Waiting is only half of it. An endpoint that blocks correctly and then
        # loses the record has still lost the record.
        stored = {x.get("rid") for x in H.store_records(ws.store)}
        r.check(rid in stored, "INV-1",
                "[INV-1] the endpoint waited for %s, answered 200, and the record is "
                "NOT on disk. A 200 without a durable write is the one thing INV-1 "
                "forbids." % label)


# ---------------------------------------------------------------------------
# F5 -- mail() returns false
# ---------------------------------------------------------------------------

@row("F5", "mail() returns false",
     "the notification is forced to fail after a healthy durable write",
     "INV-1a")
def f5(r):
    if not MAIL_SEAM["ok"]:
        r.check(False, "INV-1a",
                "[INV-1a] cannot inject a mail failure: %s. The endpoint must honour "
                "PDOOM_MAIL_SINK / PDOOM_MAIL_FAIL=1 (test-only, inert in production) "
                "or this row is untestable and INV-1a is unproven" % MAIL_SEAM["why"])
        return
    ws = Workspace("F5")
    try:
        rid = str(uuid.uuid4())
        resp = H.post(payload(rid=rid, kind="bug", text="mail is a derived notification"),
                      mail_fail=True, **ws.env())
        r.check(resp.status == 200, "INV-1a",
                "[INV-1a] mail() returning false is NOT a durable-write failure: the "
                "write succeeded, so the response must still be 200; got %s"
                % resp.status)
        r.check(resp.field("ok") is True, "INV-1a",
                "[INV-1a] the visitor must be told it worked, because it did; body "
                "ok=%r" % resp.field("ok"))
        recs = [x for x in H.store_records(ws.store) if x.get("rid") == rid]
        r.check(len(recs) == 1, "INV-1",
                "[INV-1] the record must be durable regardless of mail; found %d"
                % len(recs))
        # "failure recorded" -- the contract does not say where. Either channel is
        # accepted; silence in both is not.
        sink_says = []
        for ln in H.mail_lines(ws.mail):
            try:
                entry = json.loads(ln)
            except Exception:
                continue
            if isinstance(entry, dict) and entry.get("ok") is False:
                sink_says.append(entry)
        flagged = bool(recs) and any("mail" in str(f).lower() for f in (recs[0].get("flags") or []))
        r.check(bool(sink_says) or flagged, "INV-1a",
                "[INV-1a] the mail failure must be RECORDED somewhere -- a flag on the "
                "record or a failed line in the notification log. Found %d failed "
                "notification line(s) and flags=%r; if both are empty, a notification "
                "that never arrived is invisible"
                % (len(sink_says), (recs[0].get("flags") if recs else None)))
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F6 -- MTA accepts then discards
# ---------------------------------------------------------------------------

@row("F6", "MTA accepts then discards",
     "the store holds 3 records while the notification log holds 2",
     "INV-1a")
def f6(r):
    reconciler = os.environ.get("PDOOM_FEEDBACK_RECONCILER") or str(
        REPO_ROOT / "scripts" / "reconcile-feedback.py")
    ws = Workspace("F6")
    try:
        rids = []
        for i in range(3):
            rid = str(uuid.uuid4())
            rids.append(rid)
            H.post(payload(rid=rid, text="reconcile me %d" % i), **ws.env())
        # Injection: the MTA said 250 and then dropped one. Simulated by deleting
        # that rid's line from the notification log, which is exactly what a
        # silently-discarded message looks like from our side.
        if MAIL_SEAM["ok"]:
            kept = [ln for ln in H.mail_lines(ws.mail) if rids[1] not in ln]
            ws.mail.write_text("\n".join(kept) + "\n", encoding="utf-8")
            r.note("injected: rid %s… delivered to the store but absent from the "
                   "notification log" % rids[1][:8])
        else:
            ws.mail.write_text(
                "\n".join(json.dumps({"rid": x, "ok": True}) for x in (rids[0], rids[2])) + "\n",
                encoding="utf-8")
            r.note("mail seam not honoured, so the notification log was synthesised; "
                   "the divergence itself is still genuine")

        if not Path(reconciler).exists():
            r.check(False, "INV-1a",
                    "[INV-1a] the divergence was injected and NOTHING can see it: no "
                    "reconciler exists (looked for scripts/reconcile-feedback.py, and "
                    "$PDOOM_FEEDBACK_RECONCILER is unset). An MTA that accepts and then "
                    "discards is precisely the silent loss the binding directive "
                    "forbids, and it is currently undetectable")
            return
        out = subprocess.run(
            [sys.executable, reconciler, "--store", str(ws.store),
             "--mail-log", str(ws.mail), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT))
        try:
            doc = json.loads(out.stdout)
        except Exception:
            doc = None
        r.check(doc is not None, "INV-1a",
                "[INV-1a] the reconciler must emit machine-readable output for "
                "--store/--mail-log/--json; got %r" % (out.stdout or out.stderr)[:160])
        if doc is not None:
            divergent = doc.get("divergent") or doc.get("missing_notifications") or []
            r.check(rids[1] in [str(x) for x in divergent], "INV-1a",
                    "[INV-1a] the reconciler must FLAG the record whose notification "
                    "never arrived; divergent=%r" % divergent)
            r.check(out.returncode != 0, "INV-1a",
                    "[INV-1a] a divergence must be a non-zero exit, or the schedule "
                    "that runs it reports success while messages are being lost")
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F9 -- throttle trip
# ---------------------------------------------------------------------------

@row("F9", "throttle trip",
     "a burst from one client, large enough that any sane limit must trip",
     "§4.3")
def f9(r):
    burst = int(os.environ.get("PDOOM_THROTTLE_BURST", "60"))
    ws = Workspace("F9")
    try:
        seen = []
        for i in range(burst):
            resp = H.post(payload(kind="thumb", value=1, text="", page="/",
                                  elapsed_ms=200 + i), **ws.env())
            seen.append(resp)
            if resp.status == 429 and len([x for x in seen if x.status == 429]) >= 3:
                break
        throttled = [x for x in seen if x.status == 429]
        r.check(bool(throttled), "§4.3",
                "[§4.3] a burst of %d requests from one client tripped no throttle at "
                "all -- the 429 branch of the response table is unreachable, so its "
                "client handling has never run" % len(seen))
        for x in throttled[:3]:
            r.check(x.field("retryable") is True, "§4.3",
                    "[§4.3] a 429 must carry retryable:true so the client backs off "
                    "rather than dropping; got %r" % x.field("retryable"))
            ra = x.field("retry_after")
            r.check(isinstance(ra, (int, float)) and ra > 0, "§4.3",
                    "[§4.3] a 429 must carry a numeric retry_after; got %r" % (ra,))
            r.check(x.field("ok") is not True, "§4.3",
                    "[§4.3] a throttled request must not report ok:true")
        # Nothing may be absorbed: every 200 needs its record on disk.
        stored = {x.get("rid") for x in H.store_records(ws.store)}
        accepted = [x for x in seen if x.status == 200]
        missing = [x for x in accepted if x.field("rid") not in stored]
        r.check(not missing, "INV-1",
                "[INV-1] every request answered 200 during the burst needs a record on "
                "disk -- a throttle that drops instead of refusing is silent loss. "
                "%d of %d accepted requests are missing" % (len(missing), len(accepted)))
        r.note("burst of %d: %d x 200, %d x 429, other=%s"
               % (len(seen), len(accepted), len(throttled),
                  sorted({x.status for x in seen} - {200, 429})))
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F10 -- honeypot filled
# ---------------------------------------------------------------------------

@row("F10", "honeypot filled",
     "hp is non-empty, and elapsed_ms is impossibly small",
     "INV-1e")
def f10(r):
    ws = Workspace("F10")
    try:
        rid = str(uuid.uuid4())
        resp = H.post(payload(rid=rid, hp="http://spam.example/", elapsed_ms=90,
                              text="i am probably a bot but i might be a person"),
                      **ws.env())
        r.check(resp.status == 200, "INV-1e",
                "[INV-1e] a filled honeypot FLAGS, it never drops: expected 200, got %s"
                % resp.status)
        recs = [x for x in H.store_records(ws.store) if x.get("rid") == rid]
        r.check(len(recs) == 1, "INV-1e",
                "[INV-1e] the flagged submission must still be STORED -- absorbing it "
                "with a cheerful 200 is silent loss wearing a spam filter's hat; found "
                "%d record(s)" % len(recs))
        if recs:
            flags = [str(f).lower() for f in (recs[0].get("flags") or [])]
            r.check("honeypot" in flags, "INV-1e",
                    "[INV-1e] the record must carry the 'honeypot' flag so a human can "
                    "triage it; flags=%r" % flags)
            r.check(recs[0].get("text"), "INV-1e",
                    "[INV-1e] the flagged submission's text must be preserved verbatim")
            r.check(any("fast" in f for f in flags), "§3",
                    "[§3] elapsed_ms=90 should also raise the 'too-fast' tag named in "
                    "the record schema; flags=%r" % flags)
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F11 -- malformed JSON
# ---------------------------------------------------------------------------

@row("F11", "malformed JSON",
     "a truncated body, a non-JSON body, and an empty body",
     "§2")
def f11(r):
    cases = [
        ("truncated", '{"rid": "0d1c", "kind": "bug", "text": "half a mes'),
        ("not-json", "kind=bug&text=hello"),
        ("empty", ""),
        ("array-not-object", '["rid","kind"]'),
    ]
    ws = Workspace("F11")
    try:
        for name, body in cases:
            resp = H.post(raw_body=body, **ws.env())
            r.check(not resp.crashed, "§2",
                    "[§2] %s: the endpoint must ANSWER a malformed body, not crash. A "
                    "fatal reaches the visitor as an unparseable 500 and the client "
                    "cannot tell retryable from not. stderr=%s"
                    % (name, (resp.stderr or "").strip().replace("\n", " ")[:140]))
            r.check(resp.status == 400, "§2",
                    "[§2] %s: expected 400, got %s" % (name, resp.status))
            r.check(resp.json is not None, "§2",
                    "[§2] %s: the 400 body must itself be JSON -- the client parses it "
                    "to read `retryable`; got %r" % (name, (resp.body or "")[:80]))
            r.check(resp.field("retryable") is False, "§2",
                    "[§2] %s: a 400 must state retryable:false EXPLICITLY. A body that "
                    "omits it is treated as retryable:true and the client backs off "
                    "forever; got %r" % (name, resp.field("retryable")))
            r.check(resp.field("error"), "§2",
                    "[§2] %s: a 400 must carry an `error` the widget can show the "
                    "visitor, because their words are still in the outbox and they are "
                    "owed an explanation" % name)
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F12 -- payload over cap
# ---------------------------------------------------------------------------

@row("F12", "payload over cap",
     "each capped field is submitted one byte over its cap",
     "§2")
def f12(r):
    caps = [("text", 5000), ("contact", 200), ("credit", 80), ("page", 512)]
    ws = Workspace("F12")
    try:
        for field, cap in caps:
            rid = str(uuid.uuid4())
            over = "z" * (cap + 1)
            kw = {"rid": rid}
            kw[field] = over if field != "page" else "/" + over
            resp = H.post(payload(**kw), **ws.env())
            r.check(resp.status == 413, "§2",
                    "[§2] %s over cap (%d+1) must return 413, got %s"
                    % (field, cap, resp.status))
            r.check(resp.field("retryable") is False, "§2",
                    "[§2] %s: a 413 is not retryable and must say so explicitly; got %r"
                    % (field, resp.field("retryable")))
            err = str(resp.field("error") or "")
            r.check(field in err.lower(), "§2",
                    "[§2] %s: the 413 must NAME the field that was too long, or the "
                    "visitor cannot fix it; error=%r" % (field, err[:120]))
            # The silent-truncation trap: storing a cut-down copy and answering 200
            # would be the endpoint editing the visitor's words without telling them.
            stored = [x for x in H.store_records(ws.store) if x.get("rid") == rid]
            mangled = [x for x in stored if len(str(x.get(field) or "")) == cap]
            r.check(not mangled, "INV-1",
                    "[INV-1] %s: an over-cap submission must be rejected, never silently "
                    "cut to exactly %d and stored -- rejecting is honest, editing the "
                    "visitor's words is not (found %d truncated record(s))"
                    % (field, cap, len(mangled)))
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F13 -- rsync --delete over the docroot
# ---------------------------------------------------------------------------

@row("F13", "rsync --delete over the docroot",
     "the store is located by the endpoint's own resolution rule, then hunted for "
     "inside the docroot",
     "INV-1c")
def f13(r):
    ws = Workspace("F13")
    try:
        # No PDOOM_FEEDBACK_STORE: force the endpoint to use its own default,
        # which §3 says is dirname(docroot)/feedback-store.
        rid = str(uuid.uuid4())
        resp = H.post(payload(rid=rid, text="where does this land?"),
                      docroot=ws.docroot, mail_sink=ws.mail)
        r.check(resp.status == 200, "INV-1",
                "[INV-1] setup: default-location submission must succeed, got %s"
                % resp.status)
        found = sorted(p for p in ws.root.rglob("*.jsonl"))
        found = [p for p in found if p != ws.mail]
        r.check(bool(found), "INV-1",
                "[INV-1] an accepted submission must leave a store file somewhere under "
                "the test root; the endpoint answered %s and wrote none, meaning it "
                "either stored nothing or stored outside the sandbox -- both worse "
                "than a 507" % resp.status)
        inside = [p for p in found if _is_within(p, ws.docroot)]
        r.check(not inside, "INV-1c",
                "[INV-1c] the store MUST resolve above the docroot. rsync --delete from "
                "public/ runs ~4x/day and the payload carries reporter PII, so a store "
                "under the docroot is both deletable and publicly fetchable. Found: %s"
                % [str(p.relative_to(ws.root)) for p in inside])
        for p in found:
            r.note("store file resolved to %s" % p.relative_to(ws.root).as_posix())

        # The literal row: a --delete dry-run. Only meaningful with real rsync.
        rsync = shutil.which("rsync")
        if not rsync:
            r.note("rsync dry-run SKIPPED: no rsync binary on PATH (this box is "
                   "Windows; the deploy runs rsync on the GitHub runner). The "
                   "containment assertion above is the load-bearing half -- a path "
                   "outside the mirror's destination cannot be in any deletion set.")
        else:
            src = ws.root / "src-public"
            src.mkdir(exist_ok=True)
            (src / "index.html").write_text("<!doctype html>", encoding="utf-8")
            out = subprocess.run(
                [rsync, "-rn", "--delete", str(src) + "/", str(ws.docroot) + "/"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            deleting = [ln for ln in out.stdout.split("\n") if ln.startswith("deleting ")]
            hit = [ln for ln in deleting
                   if any(p.name in ln for p in found)]
            r.check(not hit, "INV-1c",
                    "[INV-1c] rsync --delete would remove the store: %s" % hit[:3])
            r.note("rsync dry-run deletion set: %d path(s)" % len(deleting))
    finally:
        ws.cleanup()


def _store_size(root):
    total = 0
    for p in H.store_files(root):
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return total


def _is_within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# F14 -- store_root resolves inside the docroot
# ---------------------------------------------------------------------------

@row("F14", "store_root inside the docroot",
     "PDOOM_FEEDBACK_STORE is pointed at a path under the docroot",
     "INV-1c, §3")
def f14(r):
    ws = Workspace("F14")
    try:
        bad = ws.docroot / "data" / "feedback"
        rid = str(uuid.uuid4())
        resp = H.post(payload(rid=rid, text="this must never be written"),
                      store=bad, docroot=ws.docroot, mail_sink=ws.mail)
        r.check(resp.status == 507, "§3",
                "[§3] a store_root inside the docroot must make the endpoint REFUSE "
                "with 507 -- it never 'helpfully' falls back; got %s" % resp.status)
        r.check(resp.field("ok") is not True, "INV-1",
                "[INV-1] a refusing endpoint must not report success; body ok=%r"
                % resp.field("ok"))
        r.check(resp.field("retryable") is True, "§2",
                "[§2] 507 is retryable:true so the client keeps the message and backs "
                "off; got %r" % resp.field("retryable"))
        under = [p for p in ws.docroot.rglob("*") if p.is_file()]
        r.check(not under, "INV-1c",
                "[INV-1c] NOTHING may be written under the docroot: found %s"
                % [str(p.relative_to(ws.docroot)) for p in under[:4]])
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# F15 -- UTF-8 free text under PYTHONIOENCODING=cp1252
# ---------------------------------------------------------------------------

SAMPLE = "café 🎲 日本語 — “curly” ٱلْعَرَبِيَّة ✓ naïve nbsp"


@row("F15", "UTF-8 free text with PYTHONIOENCODING=cp1252",
     "the endpoint is run in the cp1252 console environment that has cost this "
     "repo the most",
     "encoding lesson (CLAUDE.md)")
def f15(r):
    ws = Workspace("F15")
    try:
        rid = str(uuid.uuid4())
        cp = {"PYTHONIOENCODING": "cp1252", "LC_ALL": "C", "LANG": "C"}
        resp = H.post(
            payload(rid=rid, text=SAMPLE, contact=SAMPLE[:60], credit="Pip — Hobart"),
            extra=cp, **ws.env())
        r.check(resp.status == 200, "encoding",
                "[encoding] a UTF-8 submission under a cp1252 console must succeed, not "
                "die on the first byte; got %s. stderr=%s"
                % (resp.status, (resp.stderr or "").strip().replace("\n", " ")[:160]))
        recs = [x for x in H.store_records(ws.store) if x.get("rid") == rid]
        r.check(len(recs) == 1, "INV-1",
                "[INV-1] the submission must be durable; found %d record(s)" % len(recs))
        if recs:
            got = recs[0].get("text")
            r.check(got == SAMPLE, "encoding",
                    "[encoding] free text must round-trip BYTE-IDENTICAL. Wrote %r, read "
                    "back %r" % (SAMPLE, got))
            r.check(recs[0].get("credit") == "Pip — Hobart", "encoding",
                    "[encoding] an em dash in `credit` must survive; got %r"
                    % recs[0].get("credit"))
        raw_bytes = b"".join(p.read_bytes() for p in H.store_files(ws.store))
        r.check(b"\xef\xbf\xbd" not in raw_bytes and b"?" * 3 not in raw_bytes, "encoding",
                "[encoding] the store contains replacement characters -- the record was "
                "encoded with the locale codec instead of UTF-8, which mangles WITHOUT "
                "raising and is the quiet half of this bug class")
        r.check("日本語".encode("utf-8") in raw_bytes, "§3",
                "[§3] the record must be written with JSON_UNESCAPED_UNICODE: the store "
                "should hold raw UTF-8, not \\uXXXX escapes")
        r.note("sample round-tripped: %s" % SAMPLE)
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="print the row table and exit 0")
    ap.add_argument("--only", default="", help="comma-separated row ids, e.g. F1,F11")
    args = ap.parse_args()

    if args.list:
        print("row  invariant(s)              fault injected")
        for r in ROWS:
            print("%-4s %-25s %s" % (r.id, r.invariants, r.fault))
        return 0

    print("=" * 78)
    print("FEEDBACK INTAKE -- DESTRUCTIVE SUITE (contract §6, rows F1-F6 / F9-F15)")
    try:
        print("subject under test: %s" % H.subject_label())
    except H.HarnessError as exc:
        print("HARNESS REFUSED TO RUN:\n%s" % exc)
        return 1
    print("platform: %s   python: %s" % (sys.platform, sys.version.split()[0]))
    print("=" * 78)

    probe_mail_seam()
    print("mail seam positive control: %s -- %s"
          % ("OK" if MAIL_SEAM["ok"] else "NOT HONOURED", MAIL_SEAM["why"]))

    wanted = {x.strip().upper() for x in args.only.split(",") if x.strip()}
    for r in ROWS:
        if wanted and r.id not in wanted:
            continue
        print("\n--- %s  %s" % (r.id, r.title))
        print("    inject: %s" % r.fault)
        try:
            r.fn(r)
        except Exception as exc:  # a row that explodes is a FAIL, never a skip
            r.check(False, r.invariants,
                    "[%s] the row itself raised %s: %s"
                    % (r.invariants, type(exc).__name__, exc))
        for note in r.notes:
            print("    note: %s" % note)
        for ok, _inv, msg in r.checks:
            print("    %s %s" % ("PASS " if ok else "FAIL ", msg))
        if r.skipped:
            print("    SKIP: %s" % r.skipped)
        if r.uninjectable:
            print("    UNINJECTABLE: %s" % r.uninjectable)
        print("    => %s" % r.verdict)

    ran = [r for r in ROWS if not wanted or r.id in wanted]
    print("\n" + "=" * 78)
    print("%-5s %-12s %s" % ("row", "verdict", "title"))
    for r in ran:
        print("%-5s %-12s %s" % (r.id, r.verdict, r.title))
    bad = [r for r in ran if r.verdict != "PASS"]
    print("=" * 78)
    if bad:
        print("%d of %d rows are not green: %s"
              % (len(bad), len(ran), ", ".join(r.id for r in bad)))
        print("If the subject above is the STUB, this is Gate 2 evidence and the exit "
              "code is supposed to be 1.")
        return 1
    print("all %d rows green against %s" % (len(ran), H.subject_label()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
