#!/usr/bin/env python
"""Forced-failure test for sync-events.py's control-character strip.

A guard seen only in its passing state has not been shown to work. Every
case below that must be cleaned is fed through the real generator function
and observed changing; every case that must survive is fed through it and
observed unchanged.

THE CASE THAT MATTERS MOST is not "the character is gone". It is that a
form feed becomes a SPACE rather than nothing. 0x0c sits at a PDF page
break -- between the last word of one page and the first of the next -- so
deleting it yields a word that never existed, silently, in text a reader
may go on to quote. That is a worse outcome than the control character.

Run: python scripts/test-sync-events-control-chars.py    (exit 0 = pass)
"""
import importlib.util
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "sync_events", ROOT / "scripts" / "sync" / "sync-events.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

failures = 0


def check(cond, msg):
    global failures
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures += 1


FF = chr(0x0c)      # form feed -- a PDF page break
FS = chr(0x1c)      # file separator -- a column break
SOH = chr(0x01)
ETX = chr(0x03)
SI = chr(0x0f)
DEL = chr(0x7f)
VT = chr(0x0b)

print("1. THE ONE THAT WOULD INVENT A WORD")
joined = "large language models" + FF + "We evaluate"
out = sync.strip_control_chars(joined)
check(FF not in out, "the form feed is gone")
check("modelsWe" not in out, "and it did NOT become 'modelsWe' -- deletion would have")
check(out == "large language models We evaluate", "it became a space, so both words survive")

print("\n2. Every character the checker's class covers is stripped")
for name, ch in [("SOH 0x01", SOH), ("ETX 0x03", ETX), ("VT 0x0b", VT),
                 ("FORM FEED 0x0c", FF), ("SI 0x0f", SI),
                 ("FILE SEP 0x1c", FS), ("DEL 0x7f", DEL)]:
    out = sync.strip_control_chars(f"before{ch}after")
    check(ch not in out, f"{name} is stripped")

print("\n3. NEGATIVE CONTROL -- legitimate whitespace is NOT touched")
for name, ch in [("tab", "\t"), ("newline", "\n"), ("carriage return", "\r")]:
    text = f"a{ch}b"
    check(sync.strip_control_chars(text) == text, f"{name} survives unchanged")
check(sync.strip_control_chars("plain text") == "plain text", "ordinary text is untouched")
check(sync.strip_control_chars("unicode: é 中 \U0001f600") ==
      "unicode: é 中 \U0001f600", "non-ASCII is untouched")

print("\n4. It walks the WHOLE record, like redact_pii()")
event = {
    "title": f"Paper{FF}Title",
    "nested": {"description": f"a{SOH}b", "list": [f"x{FS}y", {"deep": f"p{ETX}q"}]},
    "untouched_int": 7,
    "untouched_none": None,
    # The field nobody has added yet. redact_pii() fails closed against exactly
    # this and so must the strip, or a new upstream key ships uncleaned.
    "field_added_upstream_tomorrow": f"z{SI}w",
}
cleaned = sync.strip_control_chars_deep(event)
flat = repr(cleaned)
check(not any(c in flat for c in (FF, SOH, FS, ETX, SI)),
      "no control character survives anywhere in the record")
check(cleaned["untouched_int"] == 7 and cleaned["untouched_none"] is None,
      "non-string leaves are passed through untouched")
check(cleaned["field_added_upstream_tomorrow"] == "z w",
      "a field nobody declared is cleaned too -- fail closed")
check(event["title"] == f"Paper{FF}Title", "the input dict is not mutated in place")

print("\n5. The counter reports what the pattern matched")
check(sync.count_control_chars(event) == 5, "counts every control char in the record")
check(sync.count_control_chars(cleaned) == 0, "and zero once cleaned")
check(sync.count_control_chars({"a": 1, "b": None}) == 0, "non-strings count nothing")

print("\n6. Generator and checker share ONE definition of the class")
spec2 = importlib.util.spec_from_file_location(
    "check_cc", ROOT / "scripts" / "check-control-characters.py")
checker = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(checker)
check(checker.CONTROL is sync.CONTROL_CHAR_PATTERN,
      "the checker uses the generator's compiled pattern object, not a copy")

print()
if failures:
    print(f"FAIL: {failures} check(s) failed")
    sys.exit(1)
print("OK: control characters are stripped from the whole record, a form feed")
print("    becomes a space rather than joining two words, and tab/LF/CR survive.")
