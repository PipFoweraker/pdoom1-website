#!/usr/bin/env python
"""Guard against the cp1252 trap that keeps re-breaking this repo.

WHY THIS EXISTS
---------------
Windows consoles default to cp1252. Two separate failure modes follow, and this
repo has been bitten by both:

1. THE WRITE SIDE (loud). A `print()` of any non-ASCII character raises
   UnicodeEncodeError on the FIRST print, aborting the script before it does any
   work. `health-check.py` died this way for months, and the resulting traceback
   -- which names the interpreter's own encodings/cp1252.py -- was captured into
   public/data/test-report.json and served from pdoom1.com. A Python stack trace
   became reader-facing content.

2. THE READ SIDE (quiet, and worse). `open(path)` with no `encoding=` decodes as
   cp1252 on Windows and utf-8 on Linux. A UTF-8 file full of em dashes, curly
   quotes and arrows -- which describes nearly every data file here -- silently
   mojibakes. On 2026-07-28 a diagnostic read a file this way, misread a mangled
   em dash as data corruption, and produced a FALSE BUG REPORT that cost real
   time to disprove. The write side stops a script; the read side makes people
   believe untrue things about the data.

WHAT IT CHECKS
--------------
  W1  A module that can print needs the stdout/stderr reconfigure preamble.
      Any `print()` / `sys.stdout.write()` counts: the argument does not have to
      be a literal emoji. Filenames, JSON values, HTML prose and repr()'d
      exceptions are all routes for a non-ASCII byte to reach stdout. We assume
      a printing script can emit non-ASCII unless it does not print at all.

  R1  `open()` in a text mode with no `encoding=` argument.
  R2  `Path.read_text()` / `Path.write_text()` with no `encoding=`.
  R3  subprocess in text mode (`text=True` / `universal_newlines=True`) with no
      `encoding=`. Python decodes the child's output with the locale encoding,
      so `git log` output containing an em dash mojibakes exactly like R1.

Checks are AST-based, not regex-based, so `"open("` inside a docstring or an
HTML template string does not trip them.

USAGE
-----
    python scripts/check-encoding-safety.py            # check, exit 1 on failure
    python scripts/check-encoding-safety.py --check     # identical; CI idiom
    python scripts/check-encoding-safety.py --list      # audit table, always 0

The fix for W1 is a three-line preamble copied verbatim into the module header,
NOT a shared import. See PREAMBLE below and the note on why it is duplicated.
"""

import argparse
import ast
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acknowledgements import (  # noqa: E402  (must follow the sys.path line)
    AcknowledgementError, load_ledger)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


REPO_ROOT = Path(__file__).resolve().parent.parent

# The canonical preamble. Duplicated verbatim into every printing module rather
# than imported from a helper, deliberately:
#   - these scripts are invoked directly (`python scripts/foo.py`) from many
#     working directories and from workflow steps that `cd` elsewhere, so a
#     helper import needs sys.path surgery ABOVE it -- more lines than the
#     preamble, and able to fail;
#   - an import that raises defeats the exact purpose of the preamble, which is
#     to survive being the first thing that runs;
#   - CLAUDE.md already prescribes this literal snippet, so a divergent
#     mechanism would make the documented one wrong.
PREAMBLE = '''for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass'''

# Matches the preamble's load-bearing call in either quote style, so a
# reformatting pass does not silently turn the guard off.
PREAMBLE_RE = re.compile(r"""reconfigure\(\s*encoding\s*=\s*["']utf-8["']""")

# Paths excluded from the sweep, each with a reason. Keep this list short and
# justified -- a growing exclusion list is how a guard stops guarding.
EXCLUDED = {
    # Vendored dump of a retired image pipeline, served as static bytes under
    # public/ and never executed by this repo. Editing it would change deployed
    # file contents for no behavioural gain.
    "public/assets/image-processing-systems/dump",
}

SUBPROCESS_FUNCS = {"run", "check_output", "Popen", "call", "check_call"}

# Findings somebody has decided to tolerate for now. Reported loudly on every run
# so the waiver stays visible; the entry is deleted when the file is fixed. This
# list is not a place to park anything else -- a new offender must be fixed, not
# added here.
#
# It currently holds NOTHING, and that is the intended resting state. The three
# entries it carried were cleared on 2026-08-13: two of those files had in fact
# been protected all along by a hand-rolled `io.TextIOWrapper` swap, which W1
# cannot see, because PREAMBLE_RE matches ONE spelling of the fix rather than the
# property "stdout will not die on a non-ASCII byte". Read a W1 as "this module
# does not carry the canonical preamble", never as "this module is unprotected" --
# and note the cost of the gap: a waiver sat on sync-events.py for eleven days
# citing a crash risk it did not have.
#
# ...used to be a dict literal here. It is now data/acknowledgements.json, read
# through scripts/acknowledgements.py, for two reasons.
#
# CLAUDE.md's rule, first: "pinned values go in a data file with a `source` note,
# never a script literal."
#
# The one that actually bit, second. All three entries said "held by the <X>
# branch (2026-07-29 sweep)". On 2026-08-09 no branch of two of those names
# existed on the remote -- the reason had stopped being true, and this check went
# on printing WAIVED and exiting 0, because a reason without a clock cannot
# expire. That is "class 5, the knowing allowlist": the check was not fooled, the
# reader was, by the exit code. Each acknowledgement now carries a review_by, and
# this check goes RED when one lapses -- red on the EXPIRED ACCEPTANCE, never on
# the underlying finding, so the red is always closeable by a human decision.
ACK_CHECK_NAME = "check-encoding-safety"


class Finding:
    def __init__(self, code, path, line, detail):
        self.code = code
        self.path = path
        self.line = line
        self.detail = detail

    def __str__(self):
        return f"{self.path}:{self.line}: [{self.code}] {self.detail}"


def _kwarg(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


def _is_binary_mode(call):
    """True if this open() call is in binary mode, where encoding= is illegal."""
    mode = _kwarg(call, "mode")
    node = mode.value if mode is not None else (call.args[1] if len(call.args) > 1 else None)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "b" in node.value
    # A non-literal mode (a variable) could be either. Treat as binary so we do
    # not demand an encoding that might raise ValueError at runtime.
    return node is not None


def _truthy_kwarg(call, name):
    kw = _kwarg(call, name)
    return kw is not None and not (
        isinstance(kw.value, ast.Constant) and kw.value.value in (False, None)
    )


def _func_name(node):
    """Last component of a call target: open, run, read_text, ..."""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _is_builtin_open(node):
    """True only for the builtin open()/io.open(), never Image.open or
    webbrowser.open -- both of which live in this repo and take no encoding=."""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id == "open"
    if isinstance(f, ast.Attribute) and f.attr == "open":
        return isinstance(f.value, ast.Name) and f.value.id in ("io", "codecs")
    return False


def scan_source(source, rel):
    """Return (findings, prints, tree_ok) for one module's source text."""
    findings = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [Finding("E0", rel, exc.lineno or 0, f"could not parse: {exc.msg}")], False, False

    prints = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _func_name(node)

        if name == "print" and isinstance(node.func, ast.Name):
            prints = True
        elif name == "write" and isinstance(node.func, ast.Attribute):
            tgt = node.func.value
            if isinstance(tgt, ast.Attribute) and tgt.attr in ("stdout", "stderr"):
                prints = True

        if _is_builtin_open(node) and _kwarg(node, "encoding") is None:
            if not _is_binary_mode(node):
                findings.append(
                    Finding("R1", rel, node.lineno, "open() in text mode without encoding= "
                            "(decodes as cp1252 on Windows, utf-8 on Linux)")
                )
        elif name in ("read_text", "write_text") and _kwarg(node, "encoding") is None:
            findings.append(
                Finding("R2", rel, node.lineno, f"Path.{name}() without encoding=")
            )
        elif name in SUBPROCESS_FUNCS and _kwarg(node, "encoding") is None:
            texty = _truthy_kwarg(node, "text") or _truthy_kwarg(node, "universal_newlines")
            if texty:
                findings.append(
                    Finding("R3", rel, node.lineno, f"subprocess.{name}() in text mode "
                            "without encoding= (child output decoded with the locale codec)")
                )

    if prints and not PREAMBLE_RE.search(source):
        findings.append(
            Finding("W1", rel, 1, "module prints but has no stdout/stderr reconfigure "
                    "preamble (first non-ASCII print aborts the run on Windows)")
        )
    return findings, prints, True


def python_files():
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(rel.startswith(x) for x in EXCLUDED):
            continue
        if "/.git/" in f"/{rel}" or rel.startswith(".claude/"):
            continue
        yield path, rel


# Each case is (source, expected finding codes). A guard nobody has watched fail
# is not a guard, so these run in CI alongside the sweep: they prove the checker
# still fires when the preamble is stripped or an encoding= is dropped, and that
# it stays quiet on the shapes that are genuinely fine.
SELF_TEST_CASES = [
    ("import sys\nprint('hi')\n", ["W1"]),
    ("import sys\n" + PREAMBLE + "\nprint('hi')\n", []),
    # non-print modules are not required to carry the preamble
    ("x = 1\n", []),
    ("import sys\n" + PREAMBLE + "\nsys.stdout.write('x')\n", []),
    ("sys.stdout.write('x')\n", ["W1"]),
    # read side
    ("open('f')\n", ["R1"]),
    ("open('f', encoding='utf-8')\n", []),
    ("open('f', 'rb')\n", []),
    ("open('f', 'wb')\n", []),
    ("open('f', mode='rb')\n", []),
    ("import pathlib\npathlib.Path('f').read_text()\n", ["R2"]),
    ("import pathlib\npathlib.Path('f').write_text('x', encoding='utf-8')\n", []),
    ("import subprocess\nsubprocess.run(['x'], text=True)\n", ["R3"]),
    ("import subprocess\nsubprocess.run(['x'], text=True, encoding='utf-8')\n", []),
    ("import subprocess\nsubprocess.run(['x'], capture_output=True)\n", []),
    ("import subprocess\nsubprocess.run(['x'], text=False)\n", []),
    # things that merely LOOK like the builtin open() and take no encoding=
    ("from PIL import Image\nImage.open('f.png')\n", []),
    ("import webbrowser\nwebbrowser.open('http://x/')\n", []),
    # docstrings and string literals must not trip the AST checks
    ('"""example: open(path) with no encoding"""\nx = "open(y)"\n', []),
]


def self_test():
    failures = 0
    for i, (src, expected) in enumerate(SELF_TEST_CASES):
        findings, _, _ = scan_source(src, f"<case {i}>")
        got = sorted(f.code for f in findings)
        if got != sorted(expected):
            failures += 1
            print(f"  case {i}: expected {sorted(expected)}, got {got}\n"
                  f"    source: {src!r}")
    if failures:
        print(f"SELF-TEST FAIL: {failures}/{len(SELF_TEST_CASES)} cases")
        return 1
    print(f"self-test OK: {len(SELF_TEST_CASES)} cases")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="check mode (the default); exit 1 if any finding")
    ap.add_argument("--list", action="store_true",
                    help="print the full audit table and exit 0")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the checker still detects each violation")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="evaluate acknowledgement expiry at this date instead of "
                         "today -- shows what is about to come due, and lets the "
                         "tests force the expired state rather than wait for it")
    ap.add_argument("--ledger",
                    help="path to an alternative acknowledgement ledger (tests)")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    # Load BEFORE scanning. A malformed ledger must stop the run outright: if it
    # were tolerated, every acknowledged file would report as a fresh finding and
    # the reader would go hunting three encoding bugs that nobody introduced.
    try:
        ledger = load_ledger(ACK_CHECK_NAME, args.ledger)
    except AcknowledgementError as exc:
        print(f"REFUSED: the acknowledgement ledger cannot be trusted, so this "
              f"check cannot say what it is tolerating.\n  {exc}", file=sys.stderr)
        return 2

    today = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()

    scanned = {}
    rows = []
    for path, rel in python_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        findings, prints, ok = scan_source(source, rel)
        if findings:
            scanned[rel] = findings
        rows.append((rel, prints, PREAMBLE_RE.search(source) is not None,
                     [f.code for f in findings]))

    report = ledger.assess(fired_keys=scanned.keys(), today=today)
    suppressed = report.acknowledged_keys
    waived = [f for rel, fs in scanned.items() if rel in suppressed for f in fs]
    all_findings = [f for rel, fs in scanned.items() if rel not in suppressed
                    for f in fs]

    if args.list:
        print(f"{'file':<52} {'prints':<7} {'preamble':<9} findings")
        print("-" * 92)
        for rel, prints, pre, codes in rows:
            print(f"{rel:<52} {'yes' if prints else '-':<7} "
                  f"{'yes' if pre else '-':<9} {','.join(codes) or '-'}")
        print(f"\n{len(rows)} modules scanned, "
              f"{len(all_findings)} findings, {len(waived)} waived")
        report.print_to(sys.stdout)
        return 0

    # Acknowledged findings are printed in full first -- the ledger prints the
    # decision, this prints the thing decided about. Green with a number, never
    # green with silence.
    if waived:
        print(f"WAIVED: {len(waived)} known finding(s) in "
              f"{len(suppressed & set(scanned))} file(s) not fixed yet")
        for f in sorted(waived, key=lambda f: (f.path, f.line)):
            print(f"  {f}")
        print()

    report.print_to(sys.stdout)
    print()

    if all_findings:
        print(f"FAIL: {len(all_findings)} encoding-safety finding(s) "
              f"across {len(rows)} Python modules\n")
        for f in sorted(all_findings, key=lambda f: (f.path, f.line)):
            print(f"  {f}")
        print("\nW1 -> copy the preamble from scripts/check-encoding-safety.py "
              "(PREAMBLE) into the module, just below its imports.")
        print("R1/R2/R3 -> pass encoding='utf-8' explicitly. On the read side add "
              "errors='replace' only where mojibake is preferable to a crash.")
        return 1

    if report.blocking:
        # NOT a finding failure. The scan is clean apart from things somebody
        # chose to tolerate, and the choice ran out. This red closes by deciding,
        # which is why it can never become the permanent red CLAUDE.md forbids.
        print(f"FAIL: {len(report.expired)} acknowledgement(s) expired. Every "
              f"encoding finding is either fixed or acknowledged -- what is red "
              f"is the ACCEPTANCE, listed above with what to do about it.")
        return 1

    n_waived_files = len(suppressed & set(scanned))
    clean = len(rows) - n_waived_files
    print(f"OK: {clean} of {len(rows)} Python modules are encoding-safe"
          + (f" ({n_waived_files} acknowledged, listed above)" if waived else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
