#!/usr/bin/env python
"""Forced-failure test for validate_data.py's acknowledgement wiring.

A suppression mechanism is the most dangerous thing to add to a blocking
gate, because the failure mode is silence. Four states are forced here and
observed, rather than reasoned about:

  acknowledged  the finding prints, the run exits 0, and overall_status is
                NOT OK -- green with a signed note is the class-5 shape the
                clock exists to abolish
  expired       the run is RED, and the red is about the ACCEPTANCE, not the
                finding underneath it, so a person can close it by deciding
  malformed     the run REFUSES (exit 2) rather than proceeding with an
                unknown set of exemptions
  unacknowledged  THE NEGATIVE CONTROL. A FAIL nobody signed for still fails.
                Without this the other three are consistent with a mechanism
                that swallows everything.

Run: python scripts/test-validate-data-acknowledgements.py   (exit 0 = pass)
"""
import json
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "validate_data.py"
REAL = ROOT / "data" / "acknowledgements.json"

failures = 0


def check(cond, msg):
    global failures
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures += 1


def run(ledger=None, as_of=None):
    cmd = [sys.executable, str(SCRIPT), "--check"]
    if ledger:
        cmd += ["--ledger", str(ledger)]
    if as_of:
        cmd += ["--as-of", as_of]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ledger_with(entries, checks=None):
    doc = json.loads(REAL.read_text(encoding="utf-8"))
    doc["acknowledgements"] = entries
    if checks is not None:
        doc["checks"] = checks
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(doc, f, indent=2)
    f.close()
    return Path(f.name)


# SELF-CONTAINED since 2026-11-22. This used to borrow the REAL ledger's
# league:freshness entry as its fixture, so the test of the mechanism depended on
# a particular finding staying unfixed: delete the acceptance (the right thing to
# do once the finding clears) and step 2 went red with "expected a ... in the real
# ledger". The fixture is now built here, and the FAIL it acknowledges is FORCED
# by date: league:blessing_age is guaranteed red at blessed_on + fail_after + 1,
# whatever the real calendar says. Every date is DERIVED, never typed.
CONTRACT = json.loads((ROOT / "public" / "data" / "ladder-epochs.json")
                      .read_text(encoding="utf-8"))
_blessed = date.fromisoformat(CONTRACT["regularised_from"]["seed_blessed_on"])
_fail_after = CONTRACT["blessing_policy"]["fail_after_days"]
AS_OF = (_blessed + timedelta(days=_fail_after + 1)).isoformat()   # forced FAIL
DAY_AFTER = (date.fromisoformat(AS_OF) + timedelta(days=1)).isoformat()
KEY = "league:blessing_age"
SYNTHETIC = [{
    "check": "validate_data", "key": KEY,
    "what": "test fixture: a forced blessing-age FAIL",
    "why": "test fixture", "accepted_by": "test", "accepted_on": _blessed.isoformat(),
    "review_by": AS_OF, "on_expiry": "test fixture", "source": "test fixture",
}]

print(f"1. Acknowledged: the forced FAIL ({KEY} at {AS_OF}) prints, and passes")
fx = ledger_with(SYNTHETIC)
try:
    rc, out = run(ledger=fx, as_of=AS_OF)
    check(rc == 0, "exit 0 while the acceptance is live")
    check(KEY in out, "the finding still PRINTS -- it is not suppressed from view")
    check("acknowledged" in out.lower(), "the summary counts it")
    check("overall: WARN" in out or "overall: FAIL" in out,
          "overall_status is not OK while something is knowingly wrong")

    print("\n2. NEGATIVE CONTROL -- an unacknowledged FAIL still fails")
    empty = ledger_with([])
    try:
        rc, out = run(ledger=empty, as_of=AS_OF)
        check(rc == 1, "with nothing acknowledged, the run is RED again")
        check(KEY in out, "and names the finding")
        check("what is red is the ACCEPTANCE" not in out,
              "the red is about the FINDING, not about an expiry")
    finally:
        empty.unlink()

    print("\n3. An EXPIRED acceptance is red, and red about the EXPIRY")
    rc, out = run(ledger=fx, as_of=DAY_AFTER)
    check(rc == 1, f"the day after review_by ({DAY_AFTER}), the run is RED")
    check("EXPIRED" in out, "it says the acceptance expired")
    check("what is red is the ACCEPTANCE" in out,
          "and is explicit that the finding is not what is red")
    check("re-accept" in out.lower() or "what to do" in out.lower(),
          "it tells the reader the red closes by deciding")

    print("\n4. On review_by itself the acceptance is still good (boundary, not fencepost)")
    rc, out = run(ledger=fx, as_of=AS_OF)
    check(rc == 0, f"on {AS_OF} it has not expired yet")
finally:
    fx.unlink()

print("\n5. A malformed ledger REFUSES rather than guessing")
bad = Path(tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                       encoding="utf-8").name)
bad.write_text("{ not json", encoding="utf-8")
try:
    rc, out = run(ledger=bad)
    check(rc == 2, "exit 2 -- refused, distinct from both pass and fail")
    check("cannot be trusted" in out, "it says the ledger cannot be trusted")
finally:
    bad.unlink()

print("\n6. An undeclared check REFUSES -- a rename cannot silently lose exemptions")
undeclared = ledger_with(SYNTHETIC, checks={"some-other-check": "x"})
try:
    rc, out = run(ledger=undeclared)
    check(rc == 2, "exit 2 when validate_data is not declared in `checks`")
    check("not declared" in out, "and says so")
finally:
    undeclared.unlink()

print()
if failures:
    print(f"FAIL: {failures} check(s) failed")
    sys.exit(1)
print("OK: acknowledged findings print and pass, unacknowledged ones still fail,")
print("    an expired acceptance is red about the acceptance, and a ledger that")
print("    cannot be read stops the run instead of emptying it.")
