#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Adapter that lets a destructive test POST at the feedback intake endpoint
without a web server, a network, or a secret.

WHY THIS EXISTS
---------------
docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §6 requires every failure row to be
INJECTED and OBSERVED. Injection needs a process boundary: "the store is
unwritable", "the endpoint dies after the write" and "two POSTs race" are not
things you can assert about a function you imported. So each request runs the
endpoint as a child process, and this module is the only place that knows how.

WHICH SUBJECT IS UNDER TEST (printed by every run -- never inferred silently)
----------------------------------------------------------------------------
  1. $PDOOM_INGEST_ENDPOINT, if set. Explicit beats everything.
  2. public/ingest.php, if it exists  -> the real thing, run through php_cli_shim.php.
  3. scripts/fixtures/stub_ingest.py  -> the deliberately naive stub (Gate 2).

Rule 2 has a hard edge on purpose: if public/ingest.php exists but no `php` binary
is on PATH, this module RAISES. It does not fall back to the stub. Falling back
would report the stub's behaviour under the endpoint's name -- a green or red that
describes something nobody shipped. CLAUDE.md's rule is that a silent skip is the
failure mode this repo cares most about; a silent *substitution* is worse.

THE CALLING SEAM (test-only; see the report accompanying this branch)
--------------------------------------------------------------------
The contract specifies the wire format and `PDOOM_FEEDBACK_STORE`, but says
nothing about how a test observes "no mail was sent" (F1) or forces `mail()` to
return false (F5). Those rows are unobservable without a seam, so this harness
declares two, and the implementation must honour them:

  PDOOM_MAIL_SINK   path. When set, the endpoint MUST NOT call mail(); it appends
                    one JSON line per notification it would have sent, carrying at
                    least {"rid": ..., "ok": true|false}.
  PDOOM_MAIL_FAIL   "1" forces that notification to fail, exactly as mail()
                    returning false would.

Both are test-only and inert in production (unset). F1 and F5 begin with a POSITIVE
CONTROL: a happy-path prose submission must put a line in the sink. If it does not,
the seam is not honoured and those rows report UNOBSERVABLE-FAIL rather than
passing on an absence -- "absence of a marker is never a clean bill of health".

Two more env names are set on every child. They are not new seams: they are how a
CLI process is told what a web SAPI would have put in $_SERVER.

  PDOOM_DOCROOT           becomes $_SERVER['DOCUMENT_ROOT']
  PDOOM_REMOTE_ADDR       becomes $_SERVER['REMOTE_ADDR']
  PDOOM_HTTP_USER_AGENT   becomes $_SERVER['HTTP_USER_AGENT']

WIRE
----
child stdin  : the raw request body, bytes, exactly as POSTed
child stdout : ONE JSON envelope {"status": int, "headers": {...}, "body": str}
Anything else -- a traceback, a PHP fatal, an empty stdout -- is reported as
`crashed=True` with status 500, which is what a visitor's browser would see.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent
STUB = FIXTURES / "stub_ingest.py"
PHP_SHIM = FIXTURES / "php_cli_shim.php"
REAL_PHP = REPO_ROOT / "public" / "ingest.php"


class HarnessError(RuntimeError):
    pass


class Response(object):
    __slots__ = ("status", "body", "json", "headers", "crashed", "stderr", "duration")

    def __init__(self, status, body, js, headers, crashed, stderr, duration):
        self.status = status
        self.body = body
        self.json = js
        self.headers = headers
        self.crashed = crashed
        self.stderr = stderr
        self.duration = duration

    def field(self, name, default=None):
        if isinstance(self.json, dict):
            return self.json.get(name, default)
        return default

    def __repr__(self):
        tail = (self.body or "")[:120].replace("\n", " ")
        return "<Response %s crashed=%s %s>" % (self.status, self.crashed, tail)


def resolve_subject():
    """Return (kind, argv_prefix, label). Raises rather than substituting."""
    explicit = os.environ.get("PDOOM_INGEST_ENDPOINT", "").strip()
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise HarnessError("PDOOM_INGEST_ENDPOINT=%s does not exist" % explicit)
        if path.suffix == ".php":
            return _php_subject(path)
        return ("python", [sys.executable, str(path)], "explicit: %s" % path)

    if REAL_PHP.exists():
        return _php_subject(REAL_PHP)

    return ("stub", [sys.executable, str(STUB)],
            "STUB (scripts/fixtures/stub_ingest.py) -- public/ingest.php does not exist yet")


def _php_subject(path):
    php = shutil.which("php")
    if not php:
        raise HarnessError(
            "%s exists but no `php` binary is on PATH.\n"
            "REFUSING to fall back to the stub: that would report the stub's behaviour\n"
            "under the endpoint's name. Install PHP, or run this suite where PHP lives."
            % path
        )
    if not PHP_SHIM.exists():
        raise HarnessError("missing %s" % PHP_SHIM)
    return ("php", [php, "-d", "display_errors=stderr", str(PHP_SHIM), str(path)],
            "PHP: %s (via %s)" % (path, PHP_SHIM.name))


_SUBJECT = None


def subject():
    global _SUBJECT
    if _SUBJECT is None:
        _SUBJECT = resolve_subject()
    return _SUBJECT


def subject_label():
    return subject()[2]


def is_stub():
    return subject()[0] == "stub"


def build_env(store=None, docroot=None, mail_sink=None, mail_fail=False,
              remote_addr="203.0.113.7", user_agent="pdoom-destructive-suite/1",
              extra=None):
    env = dict(os.environ)
    env.pop("PDOOM_FEEDBACK_STORE", None)
    env.pop("PDOOM_MAIL_SINK", None)
    env.pop("PDOOM_MAIL_FAIL", None)
    if store is not None:
        env["PDOOM_FEEDBACK_STORE"] = str(store)
    if docroot is not None:
        env["PDOOM_DOCROOT"] = str(docroot)
    if mail_sink is not None:
        env["PDOOM_MAIL_SINK"] = str(mail_sink)
    if mail_fail:
        env["PDOOM_MAIL_FAIL"] = "1"
    env["PDOOM_REMOTE_ADDR"] = remote_addr
    env["PDOOM_HTTP_USER_AGENT"] = user_agent
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    return env


def _parse(stdout_bytes, stderr_text, duration):
    raw = stdout_bytes.decode("utf-8", errors="replace")
    try:
        env = json.loads(raw)
        status = int(env["status"])
        body = env.get("body")
        headers = env.get("headers") or {}
    except Exception:
        # No envelope at all: a crash, a fatal, a die() before the shim, or an
        # empty response. This is exactly what a browser reports as a 500.
        return Response(500, raw, None, {}, True, stderr_text, duration)
    if not isinstance(body, str):
        body = "" if body is None else json.dumps(body)
    try:
        js = json.loads(body)
    except Exception:
        js = None
    return Response(status, body, js, headers, False, stderr_text, duration)


def post(payload=None, *, raw_body=None, timeout=30, preexec=None, **envkw):
    """POST one request. `payload` is a dict (JSON-encoded here); `raw_body` is a
    str or bytes sent verbatim, which is how malformed JSON gets injected.

    `preexec` runs in the child between fork and exec (POSIX only) and is how F2
    imposes RLIMIT_FSIZE to cut an append in half. It is ignored on Windows,
    where the caller is expected to report the row's second half as SKIPPED."""
    if raw_body is None:
        raw_body = json.dumps(payload if payload is not None else {}, ensure_ascii=False)
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")

    _, argv, _label = subject()
    started = time.time()
    proc = subprocess.Popen(
        argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=build_env(**envkw), cwd=str(REPO_ROOT),
        preexec_fn=(preexec if (preexec and os.name == "posix") else None),
    )
    try:
        out, err = proc.communicate(raw_body, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return Response(504, "", None, {}, True,
                        "TIMEOUT after %ss\n%s" % (timeout, err.decode("utf-8", "replace")),
                        time.time() - started)
    return _parse(out, err.decode("utf-8", errors="replace"), time.time() - started)


def spawn(payload, **envkw):
    """Start a request WITHOUT waiting -- used to race requests (F4) and to kill
    the endpoint mid-flight (F3). Returns the Popen; feed it yourself."""
    _, argv, _label = subject()
    proc = subprocess.Popen(
        argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=build_env(**envkw), cwd=str(REPO_ROOT),
    )
    proc.stdin.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    proc.stdin.flush()
    proc.stdin.close()
    return proc


def collect(proc, timeout=30):
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    return _parse(out, err.decode("utf-8", errors="replace"), 0.0)


# ---------------------------------------------------------------------------
# Reading what was (or was not) durably written.
# ---------------------------------------------------------------------------

def store_files(root):
    root = Path(root)
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*.jsonl"))


def store_raw(root):
    """Every byte of every store file, decoded as UTF-8 with replacement. Reading
    with `errors="replace"` is deliberate: a record written in the wrong encoding
    must show up as damage, not as a decode exception that hides the row."""
    out = []
    for p in store_files(root):
        out.append(p.read_text(encoding="utf-8", errors="replace"))
    return "".join(out)


def store_lines(root):
    """Non-empty physical lines, as text. Includes malformed ones on purpose --
    'no partial line in the store' is only checkable if partials are visible."""
    return [ln for ln in store_raw(root).split("\n") if ln.strip()]


def store_records(root):
    """Only the lines that parse. Callers compare len() against store_lines() to
    detect a torn or interleaved append."""
    recs = []
    for ln in store_lines(root):
        try:
            recs.append(json.loads(ln))
        except Exception:
            pass
    return recs


def mail_lines(sink):
    p = Path(sink)
    if not p.exists():
        return []
    return [ln for ln in p.read_text(encoding="utf-8", errors="replace").split("\n") if ln.strip()]


if __name__ == "__main__":
    print("subject: %s" % subject_label())
