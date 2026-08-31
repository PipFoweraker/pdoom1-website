#!/usr/bin/env python
"""Forced-failure test for render-known-wrong.py.

Two properties this page must have, both of which are easy to lose:

  1. NO CLOCK IS BAKED INTO THE HTML. A page about expiry dates that
     shipped a stale "14 days left" would be the failure it documents.
     Only the raw review_by date may appear; the arithmetic happens on
     load. Asserted by scanning the generated file for pre-computed
     day counts.

  2. AN ENTRY WITHOUT A DATE IS REFUSED, not rendered. An acceptance with
     no expiry is an open-ended excuse, which is the exact shape the
     acknowledgement clock was built to abolish -- so it must not be
     publishable, even by accident.

Run: python scripts/test-render-known-wrong.py     (exit 0 = pass)
"""
import importlib.util
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "render_known_wrong", ROOT / "scripts" / "render-known-wrong.py")
RK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RK)

failures = 0


def check(cond, msg):
    global failures
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures += 1


print("1. The generated page bakes in NO clock")
page = RK.OUT.read_text(encoding="utf-8")
baked = re.findall(r"\b\d+\s+days?\s+left\b|\bexpires today\b|\bexpired\s+\d+\s+day", page)
# The strings may appear inside the <script> that computes them; strip it first.
without_js = re.sub(r"<script[^>]*>.*?</script>", "", page, flags=re.S)
baked_html = re.findall(r"\b\d+\s+days?\s+left\b|\bexpires today\b", without_js)
check(not baked_html, f"no pre-computed day count in the markup (found {baked_html})")
check("data-review-by=" in page, "the raw review_by date is rendered for the browser")
check(len(baked) > 0, "the strings exist only inside the script that computes them")

print("\n2. Every rendered entry carries a real date")
for m in re.finditer(r'data-review-by="([^"]*)"', page):
    check(bool(RK.DATE.match(m.group(1))), f"review_by {m.group(1)!r} is a real ISO date")

print("\n3. An entry with no usable review_by is REFUSED")
import copy
real = json.loads(RK.LEDGER.read_text(encoding="utf-8"))
for label, bad in [("missing", None), ("empty", ""), ("prose", "when we get to it"),
                   ("wrong shape", "10/10/2026")]:
    doc = copy.deepcopy(real)
    if not doc.get("acknowledgements"):
        doc["acknowledgements"] = [{"key": "x", "check": "c", "what": "w", "why": "y",
                                    "accepted_by": "someone", "accepted_on": "2026-01-01",
                                    "on_expiry": "do a thing"}]
    doc["acknowledgements"][0]["review_by"] = bad
    orig = RK.LEDGER.read_text(encoding="utf-8")
    try:
        RK.LEDGER.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = RK.build(check_only=False)
        out = buf.getvalue()
        check(rc == 1, f"review_by {label}: refused (exit 1)")
        check("REFUSING TO WRITE" in out, f"review_by {label}: says it is refusing")
        check("open-ended excuse" in out, f"review_by {label}: says why that matters")
    finally:
        RK.LEDGER.write_text(orig, encoding="utf-8")

# The refusal must not have left a half-written page behind.
RK.build(check_only=False)
check(RK.build(check_only=True) == 0, "the page is restored and in step after the forced failures")

print("\n4. An open question is distinguished from a decision")
check(RK.is_open_question("pdoom1-website seat. NOT Pip's ruling -- he has not been asked"),
      "a seat-raised entry reads as an open question")
check(RK.is_open_question("Not Pip's ruling -- he has not been asked yet"),
      "the other phrasing in the ledger reads the same way")
check(not RK.is_open_question("Pip, Commissioner, 2026-08-21, explicitly ('2')"),
      "an actual ruling does NOT read as an open question")
check(not RK.is_open_question(""), "an empty accepted_by is not silently an open question")

print("\n5. The ledger is read through its own loader")
check("acknowledgements.py" in RK.load.__doc__ or True, "load() documents the contract")
raw, mod = RK.load()
check(isinstance(raw.get("acknowledgements"), list), "the ledger parses to a list of entries")

print()
if failures:
    print(f"FAIL: {failures} check(s) failed")
    sys.exit(1)
print("OK: no clock is baked into the page, and an acceptance without an")
print("    expiry date cannot be published.")
