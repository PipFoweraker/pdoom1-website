#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-failure tests for scripts/acknowledgements.py and its one wiring.

WHY THIS EXISTS
---------------
CLAUDE.md, Testing discipline: "A claimed safety property needs a forced
failure. If a script says it 'fails loudly', 'refuses rather than guesses' or
'never overwrites good data', there must be a test that FORCES that path and
observes it." And: "A guard seen only in its passing state has not been shown to
work."

acknowledgements.py claims four states and one refusal. Today's ledger sits in
exactly ONE of them (live, unexpired, firing), so a run against real data
exercises a quarter of the module and says nothing about the rest -- including
the expiry, which is the entire point and which nobody would otherwise observe
until the day it fired on a stranger's PR. Every case below FORCES a state the
repo is not in, using a ledger built in a temp dir and an injected `today`.

The wiring tests (11-13) go further and drive check-encoding-safety.py as a
subprocess against a synthetic ledger, because the property that matters is not
"the module computes expiry" but "the CHECK's EXIT CODE changes", and an exit
code is only observable end to end.

No network, no secrets, no mutation of any committed file.

Run:  python scripts/test-acknowledgements.py      (exit 0 = pass)
"""

import datetime as dt
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "acknowledgements", ROOT / "scripts" / "acknowledgements.py")
ack = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ack)

FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    if condition:
        PASSES.append(label)
        print(f"  ok   {label}")
    else:
        FAILURES.append(label)
        print(f"  FAIL {label}")
        if detail:
            print(f"       {detail}")


def entry(**over):
    """A valid entry. Tests mutate exactly one field, so a failure names a cause."""
    base = {
        "check": "demo-check",
        "key": "scripts/demo.py",
        "what": "W1: no preamble",
        "why": "the branch that holds it has not merged",
        "accepted_by": "Test Person",
        "accepted_on": "2026-01-01",
        "review_by": "2026-06-01",
        "on_expiry": "add the preamble and delete this entry",
        "source": "issue #1",
    }
    base.update(over)
    return {k: v for k, v in base.items() if v is not ...}


def ledger_doc(entries, **over):
    doc = {
        "note": "test fixture",
        "policy": {"warn_within_days": 14, "source": "test fixture"},
        "checks": {"demo-check": "a synthetic check used only by the tests"},
        "acknowledgements": entries,
    }
    doc.update(over)
    return doc


def write_ledger(tmp, doc):
    p = Path(tmp) / "acknowledgements.json"
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


def refuses(doc, needle, label):
    """Assert load_ledger REFUSES this document, and says why."""
    with tempfile.TemporaryDirectory() as tmp:
        p = write_ledger(tmp, doc)
        try:
            ack.load_ledger("demo-check", p)
        except ack.AcknowledgementError as exc:
            check(label, needle.lower() in str(exc).lower(),
                  f"raised, but the message did not mention {needle!r}: {exc}")
            return
        except Exception as exc:                       # noqa: BLE001
            check(label, False, f"raised {type(exc).__name__}, not "
                                f"AcknowledgementError: {exc}")
            return
    check(label, False, "load_ledger ACCEPTED a document it must refuse")


# ---------------------------------------------------------------------------
print("\n1. Unexpired acknowledgement whose key fires -> GREEN, and COUNTED")
# The design's first claim: green must carry a number, never silence. A green
# that prints nothing is indistinguishable from a check that found nothing, and
# that indistinguishability IS class 5.
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([entry()]))
    led = ack.load_ledger("demo-check", p)
    rep = led.assess({"scripts/demo.py"}, today=dt.date(2026, 3, 1))
    check("not blocking before review_by", rep.blocking is False)
    check("the key is suppressible", rep.acknowledged_keys == {"scripts/demo.py"})
    check("classified as acknowledged, not stale", len(rep.acknowledged) == 1
          and not rep.stale and not rep.expired)
    buf = io.StringIO()
    rep.print_to(buf)
    out = buf.getvalue()
    check("the item is PRINTED", "scripts/demo.py" in out, out)
    check("the summary line carries a COUNT, not silence",
          "1 live and firing" in rep.summary_line(), rep.summary_line())
    check("92 days out is not yet 'expiring soon'", not rep.expiring)

# ---------------------------------------------------------------------------
print("\n2. Past review_by -> RED, and the red is about the ACCEPTANCE")
# The load-bearing distinction. A red on the FINDING cannot be closed by whoever
# hits it, so it becomes permanent, and permanent red is what CLAUDE.md says is
# worse than no check. A red on an expired acceptance always closes by deciding.
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([entry()]))
    led = ack.load_ledger("demo-check", p)
    rep = led.assess({"scripts/demo.py"}, today=dt.date(2026, 6, 2))
    check("blocking the day AFTER review_by", rep.blocking is True)
    check("expired, and only expired", len(rep.expired) == 1 and not rep.acknowledged)
    buf = io.StringIO()
    rep.print_to(buf)
    out = buf.getvalue()
    check("names the state as an expired ACCEPTANCE", "EXPIRED ACCEPTANCE" in out, out)
    check("says the finding is not new",
          "The FINDING is not new" in out, out)
    check("carries the actionable on_expiry text",
          "add the preamble and delete this entry" in out, out)
    check("names who accepted it, so the red is routable", "Test Person" in out, out)
    check("says overdue by how long", "1 day(s) overdue" in out, out)
    # Both exits must be on offer. "Fix it" alone is a red the hitter often
    # cannot close today; "re-accept" alone is a rubber stamp. The pair is what
    # makes the red always-closeable AND always a decision.
    flat = " ".join(out.split())
    check("offers BOTH exits (fix and delete, OR re-accept with a new date)",
          "delete the entry" in flat and "set a new review_by" in flat, flat[-500:])

# review_by is inclusive: the acceptance is in force THROUGH that day. An
# off-by-one here would fire a day early on someone who is not late.
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([entry()]))
    led = ack.load_ledger("demo-check", p)
    rep = led.assess({"scripts/demo.py"}, today=dt.date(2026, 6, 1))
    check("ON review_by it is still green (inclusive boundary)",
          rep.blocking is False and len(rep.acknowledged) == 1)

# ---------------------------------------------------------------------------
print("\n3. Approaching review_by -> warned BEFORE the cliff")
# Without this, every expiry lands as a surprise red on an unrelated PR, and the
# rational response is a bulk re-accept -- which is the same as no clock at all.
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([entry()]))
    led = ack.load_ledger("demo-check", p)
    rep = led.assess({"scripts/demo.py"}, today=dt.date(2026, 5, 25))  # 7 days out
    check("still green inside the warning window", rep.blocking is False)
    check("but flagged as expiring", len(rep.expiring) == 1)
    check("the summary says so", "expiring within 14d" in rep.summary_line(),
          rep.summary_line())
    rep15 = led.assess({"scripts/demo.py"}, today=dt.date(2026, 5, 17))  # 15 days
    check("outside the window it is not flagged", not rep15.expiring)

# ---------------------------------------------------------------------------
print("\n4. Acknowledgement whose finding has VANISHED -> surfaced, not blocking")
# A stale exemption hides nothing today, so blocking on it would be a permanent
# red for housekeeping. But it is a loaded gun: if the key returns it is
# pre-forgiven by a decision nobody is making any more. So: loud, counted, green.
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([entry()]))
    led = ack.load_ledger("demo-check", p)
    rep = led.assess(set(), today=dt.date(2026, 3, 1))       # nothing fired
    check("classified stale, not acknowledged",
          len(rep.stale) == 1 and not rep.acknowledged)
    check("stale alone does not block", rep.blocking is False)
    buf = io.StringIO()
    rep.print_to(buf)
    out = buf.getvalue()
    check("STALE is printed", "STALE (1)" in out, out)
    check("explains the pre-forgiveness risk", "pre-forgiven" in out, out)
    check("counted in the summary", "1 stale" in rep.summary_line(),
          rep.summary_line())

# A stale entry still expires. Otherwise "delete this dead exemption" is a task
# with no forcing function and the ledger silts up forever.
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([entry()]))
    led = ack.load_ledger("demo-check", p)
    rep = led.assess(set(), today=dt.date(2026, 7, 1))
    check("a stale entry past review_by still blocks",
          rep.blocking is True and not rep.stale)

# ---------------------------------------------------------------------------
print("\n5. Malformed entries are REFUSED, never silently ignored")
# Skipping a bad entry would be the worst outcome available: the finding would
# resurface as if fresh and send someone hunting a bug nobody introduced.
for field in ack.REQUIRED_FIELDS:
    refuses(ledger_doc([entry(**{field: ...})]), field,
            f"a missing {field!r} refuses the whole ledger")

refuses(ledger_doc([entry(source="   ")]), "non-blank",
        "a BLANK source is refused (a sourceless acceptance is anonymous)")
refuses(ledger_doc([entry(accepted_by="")]), "non-blank",
        "a blank accepted_by is refused")
refuses(ledger_doc([entry(review_by="2026-6-1")]), "strict ISO",
        "a non-ISO review_by is refused, not guessed at")
refuses(ledger_doc([entry(review_by="not a date")]), "strict ISO",
        "unparseable review_by is refused")
refuses(ledger_doc([entry(accepted_on="2026-13-45")]), "strict ISO",
        "an impossible accepted_on is refused")
refuses(ledger_doc([entry(review_by="2026-01-01")]), "must be after",
        "review_by == accepted_on is refused (a zero-length acceptance)")
refuses(ledger_doc([entry(review_by="2025-01-01")]), "must be after",
        "review_by BEFORE accepted_on is refused")
refuses(ledger_doc([entry(check="demo-chekc")]), "not declared",
        "a TYPO in `check` is refused, not silently applied to nothing")
refuses(ledger_doc([entry(), entry()]), "duplicate",
        "two acceptances of one key are refused (which review_by is in force?)")
refuses(ledger_doc([entry()], policy={"warn_within_days": 14}), "policy.source",
        "a policy value with no source is refused (CLAUDE.md's data-file rule)")
refuses(ledger_doc([entry()], policy={"warn_within_days": -1, "source": "x"}),
        "non-negative", "a negative warning window is refused")
refuses(ledger_doc([entry()], checks={}), "non-empty",
        "an empty `checks` map is refused")
refuses(ledger_doc([entry()], acknowledgements="not a list"), "must be a list",
        "a non-list acknowledgements block is refused")
refuses(ledger_doc(["a string, not an object"]), "must be an object",
        "a non-object entry is refused")

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "acknowledgements.json"
    p.write_text("{ not json", encoding="utf-8")
    try:
        ack.load_ledger("demo-check", p)
        check("invalid JSON is refused", False, "accepted")
    except ack.AcknowledgementError as exc:
        check("invalid JSON is refused", "not valid JSON" in str(exc), str(exc))

with tempfile.TemporaryDirectory() as tmp:
    try:
        ack.load_ledger("demo-check", Path(tmp) / "nope.json")
        check("a MISSING ledger is refused, not read as 'no exemptions'",
              False, "accepted")
    except ack.AcknowledgementError as exc:
        check("a MISSING ledger is refused, not read as 'no exemptions'",
              "does not exist" in str(exc), str(exc))

# ---------------------------------------------------------------------------
print("\n6. An undeclared check name refuses, so a RENAME cannot lose exemptions")
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([entry()]))
    try:
        ack.load_ledger("check-that-nobody-declared", p)
        check("asking for an undeclared check refuses", False, "accepted")
    except ack.AcknowledgementError as exc:
        check("asking for an undeclared check refuses",
              "not declared" in str(exc), str(exc))

# ---------------------------------------------------------------------------
print("\n7. Entries for OTHER checks do not leak into this check's ledger")
with tempfile.TemporaryDirectory() as tmp:
    doc = ledger_doc([entry(), entry(check="other-check", key="scripts/x.py")],
                     checks={"demo-check": "d", "other-check": "o"})
    p = write_ledger(tmp, doc)
    led = ack.load_ledger("demo-check", p)
    check("only this check's entries are returned",
          [e.key for e in led.entries] == ["scripts/demo.py"],
          str([e.key for e in led.entries]))

# ---------------------------------------------------------------------------
print("\n8. An empty ledger still prints, rather than saying nothing")
with tempfile.TemporaryDirectory() as tmp:
    p = write_ledger(tmp, ledger_doc([]))
    led = ack.load_ledger("demo-check", p)
    rep = led.assess({"scripts/demo.py"}, today=dt.date(2026, 3, 1))
    buf = io.StringIO()
    rep.print_to(buf)
    check("says 'none on file' explicitly", "none on file" in buf.getvalue(),
          buf.getvalue())
    check("nothing suppressed", rep.acknowledged_keys == set())

# ---------------------------------------------------------------------------
print("\n9. THE REAL LEDGER loads, and every entry is honest about its clock")
led = ack.load_ledger("check-encoding-safety")
check("data/acknowledgements.json parses and validates", len(led.entries) == 3,
      str(len(led.entries)))
today = dt.date.today()
check("no entry in the real ledger is already expired (that would ship a red)",
      all(not e.is_expired(today) for e in led.entries),
      str([(e.key, str(e.review_by)) for e in led.entries]))
check("real entries do not all share one review_by (no thundering herd)",
      len({e.review_by for e in led.entries}) == len(led.entries),
      str(sorted(str(e.review_by) for e in led.entries)))
check("every real entry cites a source",
      all(len(e.source) > 20 for e in led.entries))

# ---------------------------------------------------------------------------
print("\n10. The audit CLI reports, and never gates")
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "acknowledgements.py"),
                    "--audit", "--as-of", "2030-01-01"],
                   capture_output=True, text=True, encoding="utf-8")
check("--audit exits 0 even with everything expired", r.returncode == 0,
      f"rc={r.returncode} {r.stderr[-400:]}")
check("--audit reports the expiries it found", "EXPIRED" in r.stdout,
      r.stdout[-400:])
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "acknowledgements.py"),
                    "--audit", "--check", "no-such-check"],
                   capture_output=True, text=True, encoding="utf-8")
check("--audit on an unknown check name refuses (exit 2)", r.returncode == 2,
      f"rc={r.returncode}")

# ---------------------------------------------------------------------------
print("\n11. WIRING: check-encoding-safety goes RED when an acceptance expires")
# The property that matters is the EXIT CODE of the real check, which no unit
# test of the module can observe. --as-of forces the future without editing
# any committed date.
GUARD = [sys.executable, str(ROOT / "scripts" / "check-encoding-safety.py")]

r = subprocess.run(GUARD, capture_output=True, text=True, encoding="utf-8",
                   cwd=str(ROOT))
check("today: the check is GREEN", r.returncode == 0, f"rc={r.returncode}")
check("today: green PRINTS the acknowledged findings",
      "WAIVED" in r.stdout and "ACKNOWLEDGED" in r.stdout, r.stdout[-600:])
check("today: green carries a COUNT", "on file" in r.stdout, r.stdout[-600:])

r = subprocess.run(GUARD + ["--as-of", "2027-01-01"], capture_output=True,
                   text=True, encoding="utf-8", cwd=str(ROOT))
check("future: the check is RED", r.returncode == 1, f"rc={r.returncode}")
check("future: red names the EXPIRY, not the finding, as the cause",
      "what is red is the ACCEPTANCE" in r.stdout, r.stdout[-800:])
check("future: red tells the reader what to do",
      "DO THIS" in r.stdout, r.stdout[-800:])

# ---------------------------------------------------------------------------
print("\n12. WIRING: a malformed ledger stops the check, and does NOT read as "
      "three fresh encoding bugs")
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "bad.json"
    p.write_text(json.dumps({
        "policy": {"warn_within_days": 14, "source": "x"},
        "checks": {"check-encoding-safety": "d"},
        "acknowledgements": [{"check": "check-encoding-safety",
                              "key": "scripts/ingest_scores.py"}],
    }), encoding="utf-8")
    r = subprocess.run(GUARD + ["--ledger", str(p)], capture_output=True,
                       text=True, encoding="utf-8", cwd=str(ROOT))
    check("a ledger missing required fields REFUSES (exit 2, not 0 and not 1)",
          r.returncode == 2, f"rc={r.returncode} out={r.stdout[-300:]}")
    check("it says the ledger is the problem",
          "ledger cannot be trusted" in r.stderr, r.stderr[-400:])
    check("it does NOT report the acknowledged files as fresh findings",
          "FAIL:" not in r.stdout, r.stdout[-400:])

# ---------------------------------------------------------------------------
print("\n13. WIRING: an EMPTY ledger makes the three real findings fail normally")
# Proves the suppression is doing real work -- without it, these findings are
# live and red. A guard whose allowlist could be emptied with no change in
# behaviour is a guard that was never checking anything.
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "empty.json"
    p.write_text(json.dumps({
        "policy": {"warn_within_days": 14, "source": "x"},
        "checks": {"check-encoding-safety": "d"},
        "acknowledgements": [],
    }), encoding="utf-8")
    r = subprocess.run(GUARD + ["--ledger", str(p)], capture_output=True,
                       text=True, encoding="utf-8", cwd=str(ROOT))
    check("with nothing acknowledged the check is RED on the findings",
          r.returncode == 1, f"rc={r.returncode}")
    check("and red on the FINDINGS this time, not on an expiry",
          "encoding-safety finding(s)" in r.stdout
          and "acknowledgement(s) expired" not in r.stdout, r.stdout[-500:])
    check("the three real files are the ones named",
          all(k in r.stdout for k in ("scripts/ingest_scores.py",
                                      "scripts/sync/sync-events.py",
                                      "scripts/weekly-league-manager.py")),
          r.stdout[-600:])

# ---------------------------------------------------------------------------
print("\n14. WIRING: the check's own self-test and --list still work")
for extra in (["--self-test"], ["--list"]):
    r = subprocess.run(GUARD + extra, capture_output=True, text=True,
                       encoding="utf-8", cwd=str(ROOT))
    check(f"check-encoding-safety {' '.join(extra)} exits 0",
          r.returncode == 0, f"rc={r.returncode} {r.stderr[-300:]}")

# ---------------------------------------------------------------------------
print(f"\n{len(PASSES)} passed, {len(FAILURES)} failed")
if FAILURES:
    for f in FAILURES:
        print(f"  FAILED: {f}")
    sys.exit(1)
print("All acknowledgement states forced and observed.")
sys.exit(0)
