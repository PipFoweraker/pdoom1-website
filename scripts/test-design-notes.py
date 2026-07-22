#!/usr/bin/env python
"""Tests for scripts/sync/sync-design-notes.py.

Covers the two things that would be embarrassing to get wrong: leaking the
game's internal process notes onto a public page, and mangling the markdown
subset the ADRs actually use.

Run: python scripts/test-design-notes.py
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sdn", ROOT / "scripts" / "sync" / "sync-design-notes.py")
sdn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdn)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" -> " + detail) if detail else ""))


print("scrub(): internal content removal")
raw = (
    "# ADR-0099 - Title\n\n"
    "- **Status:** ACCEPTED\n"
    "- **Session:** Fable workshop #2, beat 1 (issue #604)\n"
    "- **Date:** 2026-07-04\n\n"
    "## Context\n\n"
    "Real design content.\n\n"
    "<!-- To fill from the workshop: rejected alternatives -->\n"
    "TODO: decide the numbers\n\n"
    "More content.\n"
)
clean, removed = sdn.scrub(raw)
check("session line dropped", "Session:" not in clean)
check("html comment dropped", "<!--" not in clean)
check("TODO line dropped", "TODO" not in clean)
check("status line kept", "**Status:** ACCEPTED" in clean)
check("date line kept", "**Date:** 2026-07-04" in clean)
check("real content kept", "Real design content." in clean and "More content." in clean)
check("removal counted", removed == 3, "got %d" % removed)

print("scrub(): legitimate prose containing 'session:' must survive")
prose = "## Context\n\nPip fixed the fiction anchors this session: 2017 start.\n"
kept, _ = sdn.scrub(prose)
check("lowercase prose 'session:' kept", "this session: 2017 start" in kept)

print("assert_clean(): refuses leaky bodies")
for bad, label in [
    ("<p>note</p><!-- authoring -->", "html comment"),
    ("<p><strong>Session:</strong> workshop</p>", "session attribution"),
    ("<p>TODO: fix</p>", "todo"),
    ("<p>To fill from the workshop</p>", "placeholder"),
]:
    try:
        sdn.assert_clean(bad, "TEST")
        check("raises on %s" % label, False, "no exception")
    except sdn.LeakError:
        check("raises on %s" % label, True)
try:
    sdn.assert_clean("<p>Pip fixed anchors this session: 2017.</p>", "TEST")
    check("allows legitimate prose", True)
except sdn.LeakError as e:
    check("allows legitimate prose", False, str(e))

print("render(): markdown subset the ADRs actually use")
cases = [
    ("## Heading", "<h2>Heading</h2>", "heading"),
    ("**bold**", "<strong>bold</strong>", "bold"),
    ("`code`", "<code>code</code>", "inline code"),
    ("[text](https://x.test)", '<a href="https://x.test">text</a>', "link"),
    ("> quoted", "<blockquote>quoted</blockquote>", "blockquote"),
    ("---", "<hr>", "horizontal rule"),
]
for src, expect, label in cases:
    out = sdn.render(src)
    check(label, expect in out, "got %r" % out[:70])

out = sdn.render("- one\n- two\n")
check("bullet list", "<ul>" in out and out.count("<li>") == 2, out[:80])
out = sdn.render("1. first\n2. second\n")
check("numbered list", "<ol>" in out and out.count("<li>") == 2, out[:80])

table = "| A | B |\n|---|---|\n| 1 | 2 |\n"
out = sdn.render(table)
check("table renders", "<table>" in out and "<th>A</th>" in out and "<td>2</td>" in out,
      out[:120])
check("table scroll wrapper", 'class="table-scroll"' in out,
      "wide content must scroll in its own box, not the page body")

print("render(): safety")
out = sdn.render("<script>alert(1)</script>")
check("raw HTML escaped", "<script>" not in out and "&lt;script&gt;" in out, out[:80])
out = sdn.render("`glob/**.gd` and `autoload/**.gd`")
check("globs in code not read as bold", "<strong>" not in out, out[:100])
out = sdn.render("Plain [link](a) with **bold** and `code`.")
check("mixed inline", all(t in out for t in ("<a href=", "<strong>", "<code>")), out[:110])

print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
