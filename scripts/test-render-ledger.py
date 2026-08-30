#!/usr/bin/env python
"""Forced-failure test for render-ledger.py's withholding.

The page publishes a maintainer document verbatim. The only thing standing
between the repo's ledger and pdoom1.com is the withholding pass, so it is
tested the way every other refusal in this repo is: by forcing the state
that must fail and observing it fail, not by watching it pass.

THE NEGATIVE CONTROL IS THE INTERESTING HALF. The ledger is full of
timestamps like `2026-08-21T22:22Z`, and a naive "no :22 anywhere" rule
would strip the record's own dates while claiming to protect a port
number. That case is pinned below because it was hit for real while
writing this -- an ad-hoc grep flagged the timestamp and the actual guard
correctly did not.

Run: python scripts/test-render-ledger.py     (exit 0 = pass)
"""
import importlib.util
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("render_ledger", ROOT / "scripts" / "render-ledger.py")
RL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RL)

failures = 0


def check(cond, msg):
    global failures
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures += 1


print("1. The real sentence from the L5 row is withheld")
real = ("**Check 7 was UNAVAILABLE and [Gate 6] was HELD by the Commissioner on "
        "2026-08-21: `api.pdoom1.com` was unreachable** — ICMP, :22, :80 and :443 all "
        "TIME OUT rather than refuse, so the host is down.")
out, applied = RL.withhold(real)
check("ICMP" not in out, "the protocol name is gone")
check(":22" not in out and ":443" not in out, "the port list is gone")
check(len(applied) == 1, "exactly one withholding rule fired")
check("every service probed timed out" in out, "replaced with a readable statement")

print("\n2. The FACT survives -- withheld, not censored")
check("was unreachable" in out, "the host being unreachable is still stated")
check("[Gate 6] was HELD" in out, "the decision it justified is still stated")
check("api.pdoom1.com" in out, "the host name stays -- it is the public score API")
check("2026-08-21" in out, "the date stays")

print("\n3. NEGATIVE CONTROLS -- the record's own timestamps must survive")
for label, text in [
    ("a Zulu timestamp", "the host returned on 2026-08-21T22:22Z; re-measured"),
    ("a local time", "opened at approximately 14:40 AEST"),
    ("a bare count", "208 board keys probed, 0 unreachable"),
    ("a version string", "pdoom1 v0.14.2 forked L4 -> L5"),
    ("a seed", "seed `weekly-2026-w33` at ladder epoch `L5`"),
]:
    got, ap = RL.withhold(text)
    check(got == text and not ap, f"{label} is untouched")

print("\n4. assert_publishable REFUSES rather than shipping")
for label, bad in [
    ("raw ICMP", "the probe used ICMP and got nothing"),
    ("lower-case icmp", "sent an icmp echo"),
    ("a bare SSH port", "we checked :22 and it hung"),
]:
    try:
        RL.assert_publishable(bad)
        check(False, f"{label}: should have raised, did not")
    except AssertionError as exc:
        check("REFUSING TO WRITE" in str(exc), f"{label}: refused")
        check("Do NOT relax FORBIDDEN" in str(exc),
              f"{label}: and says not to loosen the guard to pass")

print("\n5. assert_publishable does NOT fire on the record's own text")
for label, ok in [
    ("a Zulu timestamp", "returned on 2026-08-21T22:22Z; re-measured 2026-08-24"),
    ("the withheld replacement", "every service probed timed out, so the host is down"),
    ("an ordinary sentence", "The board was not open."),
]:
    try:
        RL.assert_publishable(ok)
        check(True, f"{label}: allowed through")
    except AssertionError:
        check(False, f"{label}: wrongly refused")

print("\n6. The generator is wired to the real document")
check(RL.SOURCE.exists(), f"source exists: {RL.SOURCE.name}")
check(RL.OUT.exists(), f"output exists: {RL.OUT.relative_to(ROOT)}")
check(RL.build(check_only=True) == 0, "--check reports the page is in step")

print()
if failures:
    print(f"FAIL: {failures} check(s) failed")
    sys.exit(1)
print("OK: infrastructure detail is withheld, the facts it justified survive,")
print("    and the record's own timestamps are not mistaken for port numbers.")
