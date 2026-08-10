#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check-token-drift.py -- which pages define a design token with a value that is not
the design token?

WHY THIS EXISTS
---------------
CLAUDE.md says public/design/tokens.json "is fetched at runtime by ~8 pages; the
other ~2,190 hardcode their colours in an inline :root. It is not a design system
yet." That framing is literally true and misleading, and this script exists to
replace the impression with a number.

A survey on 2026-08-09 found the corpus has only ~14 distinct palette signatures
and has ALREADY converged: the ~2,194 generated event pages carry the tokens.json
palette baked in as literals, and of 138 hex values sitewide the top 14 by
file-count are exactly the 14 token colours. The divergence is not a design
decision per page. It is a small number of stale values in the hand-written pages.

**This script is Step 0 of the token plan, and its job is to prove or disprove
that survey for the cost of an hour.** If it does not report roughly 44 pages on
--text-primary and 33 on --accent-danger, the plan built on that survey is wrong
and we found out cheaply.

WHAT IT DOES NOT DO
-------------------
It does not change a colour, and it must not. A restyle is Pip's call and the
copy-baseline rule means prose must not move while CSS does.

It also does not judge the SECOND DIALECT. Six newer pages define --bg / --panel /
--ink / --amber / --teal, whose values match the tokens but whose names do not.
Those are reported separately as INFORMATIONAL, because renaming a CSS variable is
a design decision and this script has no standing to make one.

NAMING
------
tokens.json uses camelCase (bgPrimary); the CSS uses kebab-case (--bg-primary).
One documented transformation, applied here explicitly rather than guessed at.

EXIT CODES
  0  every page that defines a token-named variable uses the token's value
  1  drift -- at least one page defines a token-named variable with another value
  2  cannot tell -- tokens.json missing, unreadable, or carries no colours

RUN
    python scripts/check-token-drift.py
    python scripts/check-token-drift.py --json
    python scripts/check-token-drift.py --var text-primary     # one variable
"""

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        try:
            if _s is sys.stdout:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
TOKENS = PUBLIC / "design" / "tokens.json"

DECL_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,8})\s*[;}]")
CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def kebab(name):
    """bgPrimary -> bg-primary. The one documented transformation."""
    return CAMEL_RE.sub("-", name).lower()


def norm_hex(h):
    """#abc -> #aabbcc, case-folded. #aabbccdd keeps its alpha."""
    h = h.strip().lower()
    if len(h) == 4:
        return "#" + "".join(c * 2 for c in h[1:])
    return h


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--var", help="report only this CSS variable (kebab-case, no --)")
    ap.add_argument("--list-files", action="store_true",
                    help="list every drifting file rather than a sample")
    args = ap.parse_args()

    try:
        tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("CANNOT TELL: could not read %s (%s)." % (TOKENS, e))
        print("Absence of the token file is UNKNOWN, never agreement.")
        return 2

    colors = tokens.get("colors") or {}
    if not colors:
        print("CANNOT TELL: tokens.json carries no colours, so there is nothing to")
        print("check pages against.")
        return 2

    # kebab css var -> canonical value
    want = {kebab(k): norm_hex(v) for k, v in colors.items() if isinstance(v, str)}
    if args.var:
        want = {k: v for k, v in want.items() if k == args.var.lstrip("-")}
        if not want:
            print("No such token variable: --%s" % args.var.lstrip("-"))
            return 2

    files = sorted(PUBLIC.rglob("*.html"))
    drift = defaultdict(list)      # var -> [(path, found)]
    agree = defaultdict(int)       # var -> count
    other_dialect = defaultdict(int)
    scanned = 0

    token_values = {v for v in want.values()}

    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        rel = f.relative_to(ROOT).as_posix()
        for m in DECL_RE.finditer(text):
            var, val = m.group(1)[2:], norm_hex(m.group(2))
            if var in want:
                if val == want[var]:
                    agree[var] += 1
                else:
                    drift[var].append((rel, val))
            elif val in token_values:
                # a variable nobody named after a token, holding a token value:
                # the second dialect. Informational only.
                other_dialect[var] += 1

    print("Design token drift -- %d HTML files scanned" % scanned)
    print("=" * 74)
    print("  tokens.json colours: %d" % len(want))
    total_drift_files = len({p for v in drift.values() for p, _ in v})
    print("  pages using a token-named var with the RIGHT value: %d declaration(s)"
          % sum(agree.values()))
    print("-" * 74)

    if drift:
        for var in sorted(drift, key=lambda k: -len(drift[k])):
            hits = drift[var]
            vals = sorted({v for _, v in hits})
            print("  --%-18s %4d page(s)   token %s   found %s"
                  % (var, len(hits), want[var], ", ".join(vals)))
            show = hits if args.list_files else hits[:3]
            for path, val in show:
                print("        %-58s %s" % (path[:58], val))
            if not args.list_files and len(hits) > 3:
                print("        ... and %d more (use --list-files)" % (len(hits) - 3))
    else:
        print("  no token-named variable disagrees with tokens.json")

    if other_dialect:
        print("-" * 74)
        print("  INFORMATIONAL -- variables holding a token VALUE under a non-token")
        print("  NAME (the second dialect). Renaming a CSS variable is a design")
        print("  decision and this check does not make one:")
        for var, n in sorted(other_dialect.items(), key=lambda kv: -kv[1])[:8]:
            print("        --%-16s %4d declaration(s)" % (var, n))

    result = {
        "scanned": scanned,
        "tokens": len(want),
        "agreeing_declarations": sum(agree.values()),
        "drifting_files": total_drift_files,
        "drift": {v: {"token": want[v], "pages": len(h),
                      "found": sorted({x for _, x in h})}
                  for v, h in drift.items()},
        "second_dialect": dict(sorted(other_dialect.items(), key=lambda kv: -kv[1])[:12]),
    }
    if args.json:
        print()
        print(json.dumps(result, indent=2))

    if not drift:
        print()
        print("  OK: every token-named variable in public/ carries the token's value.")
        return 0

    print("-" * 74)
    print("  DRIFT: %d file(s) define a token-named variable with a different value."
          % total_drift_files)
    print()
    print("  This is a MECHANICAL divergence, not a design decision -- the same")
    print("  variable names with stale values. It is Step 1 of the token plan.")
    print("  Do NOT hand-edit public/events/*.html: the daily sync overwrites them.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
