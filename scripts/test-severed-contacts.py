#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Force the mode-(d) advisory to fire, on the text that actually leaked.

WHY THIS EXISTS
---------------
On 2026-08-13 public/data/issues-cache.json served a real person's email address
for roughly twelve hours, and every scanner in this repo reported it clean the
whole time.

The address was truncation-severed -- "leimeister@un", cut mid-domain by
pdoom-data's 1,000-character description cap, so it has no dot and no TLD.
EMAIL_PATTERN requires a TLD, so redact_pii() could not see it. That is not a
bug in EMAIL_PATTERN; it is a shape outside the pattern's contract.

It reached the published cache because pdoom1#1212 -- THE PULL REQUEST THAT
CLOSED THE ORIGINAL EXPOSURE -- quoted the fragment verbatim to explain the
defect, and update-game-data.yml harvests open issue and PR bodies into that
file. The remediation republished the thing it was remediating.

CLAUDE.md's rule is that a claimed safety property needs a FORCED FAILURE, and
that a guard seen only in its passing state has not been shown to work. So this
runs the advisory against the REAL historical inputs and a control corpus:

  * the exact line from #1212's body, which must fire;
  * every false-positive family measured in this corpus -- pass@k, Acc@100,
    lx@paragraphsign, @realDonaldTrump, ACDC@LungHP, "@ 2.20GHz", BibTeX
    @article{ -- each tested bare AND hard-cut with the truncation marker
    appended, which must all stay silent;
  * team@pdoom1.com, our own deliberately-published contact address, which must
    stay silent -- a guard that fires on it gets turned off within a week;
  * the advisory must COUNT and never mutate: this is not a redaction.

Run: python scripts/test-severed-contacts.py
"""
import importlib.util
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_SYNC = os.path.join(_HERE, "sync", "sync-events.py")

# Imported, never reimplemented: this repo keeps exactly ONE definition of each
# address shape, the same way check-published-emails.py imports EMAIL_PATTERN.
_spec = importlib.util.spec_from_file_location("sync_events", _SYNC)
sync_events = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_events)

count_severed = sync_events.count_severed_contacts
count_emails = sync_events.count_emails
MARKER = sync_events.REDACTION_MARKER

# The real thing, byte-for-byte as it stood in #1212's body.
LEAKED_LINE = '    "...St.Gallen, Switzerland  \\nleimeister@un..."'

MUST_FIRE = [
    ("the #1212 body line, verbatim", LEAKED_LINE),
    ("bare severed address", "leimeister@un..."),
    ("severed inside the TLD", "j.smith@uni-kassel.d..."),
    ("unicode ellipsis truncation marker", "leimeister@un…"),
    ("short local part carrying a separator", "jan.marco@un..."),
    ("severed address inside a longer body", "prose before\nleimeister@un...\nprose after"),
]

# Every one of these is measured in this corpus, not imagined. Each is tested
# as-is and hard-cut with the marker appended, because the marker is the only
# thing the rule anchors on and appending it is the adversarial case.
FALSE_POSITIVE_FAMILIES = [
    ("pass@k metric notation", "we report pass@k"),
    ("Acc@100 metric notation", "Acc@100"),
    ("lx@paragraphsign LaTeX internal", "lx@paragraphsign"),
    ("@realDonaldTrump handle", "@realDonaldTrump"),
    ("ACDC@LungHP dataset name", "ACDC@LungHP"),
    ("clock speed with a spaced @", "8 CPU cores @ 2.20GHz"),
    ("BibTeX entry key", "BIB: @article{Giuseppi2020, doi = {10.1109/lcsys}"),
    ("math@ short bare token", "math@"),
    ("prose containing a domain", "and so on, aimed at arxiv.org"),
    ("a docker/node version pin", "node@18"),
]

MUST_NOT_FIRE = [
    ("our own published contact address", "team@pdoom1.com"),
    ("our contact address, hard-cut", "team@pdoom1.com..."),
    ("an already-redacted marker", MARKER + "..."),
    ("a severed shape with no truncation marker", "leimeister@un"),
    ("empty string", ""),
]
for _name, _s in FALSE_POSITIVE_FAMILIES:
    MUST_NOT_FIRE.append((_name + ", as-is", _s))
    MUST_NOT_FIRE.append((_name + ", hard-cut with marker", _s + "..."))


def main() -> int:
    failures = []

    print("MUST FIRE -- the advisory has to see these:")
    for name, text in MUST_FIRE:
        n = count_severed(text)
        ok = n >= 1
        if not ok:
            failures.append(f"MUST FIRE but did not (n={n}): {name}")
        print(f"  [{'PASS' if ok else 'FAIL'}] n={n:<2} {name}")

    print("\nMUST NOT FIRE -- silence on every measured false-positive family:")
    for name, text in MUST_NOT_FIRE:
        n = count_severed(text)
        ok = n == 0
        if not ok:
            failures.append(f"MUST NOT FIRE but did (n={n}): {name}")
        print(f"  [{'PASS' if ok else 'FAIL'}] n={n:<2} {name}")

    # The regression that made this necessary: the OLD scanner scored the
    # leaking text as clean. Assert that gap explicitly, so nobody "simplifies"
    # the advisory away on the grounds that redact_pii() already covers it.
    print("\nTHE GAP THIS CLOSES -- old scanner vs new, on the leaked text:")
    old = count_emails(LEAKED_LINE)
    new = count_severed(LEAKED_LINE)
    ok = old == 0 and new == 1
    if not ok:
        failures.append(
            f"expected EMAIL_PATTERN blind (0) and advisory seeing (1), got {old}/{new}")
    print(f"  [{'PASS' if ok else 'FAIL'}] EMAIL_PATTERN={old} (blind), "
          f"severed advisory={new} (sees it)")

    # It is an ADVISORY. It must not rewrite anything.
    print("\nADVISORY, NOT A REDACTION -- redact_pii must leave the shape alone:")
    unchanged = sync_events.redact_pii(LEAKED_LINE) == LEAKED_LINE
    if not unchanged:
        failures.append("redact_pii() mutated the severed shape; this is advisory only")
    print(f"  [{'PASS' if unchanged else 'FAIL'}] redact_pii() left it byte-identical")

    # Structure walking, same contract as the other counters.
    print("\nWALKS NESTED STRUCTURES -- a new API field cannot hide one:")
    nested = {"issues": [{"body": LEAKED_LINE, "user": {"login": "someone"}}]}
    n = count_severed(nested)
    ok = n == 1
    if not ok:
        failures.append(f"nested walk returned {n}, expected 1")
    print(f"  [{'PASS' if ok else 'FAIL'}] n={n} through dict -> list -> dict -> str")

    print()
    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    total = len(MUST_FIRE) + len(MUST_NOT_FIRE) + 3
    print(f"PASS: {len(MUST_FIRE)} must-fire and {len(MUST_NOT_FIRE)} "
          f"must-not-fire cases pass ({total} assertions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
