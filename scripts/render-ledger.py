#!/usr/bin/env python
"""Render docs/LEAGUE_SEED_LEDGER.md to /ledger/ for players.

WHY THIS PAGE EXISTS
The ledger is the record of which seed governs which league epoch, when it
was blessed and by whom. It is written for maintainers, but it is the most
player-relevant document in the repo: it explains why a board closes, why a
score set under old rules is not comparable to a new one, and -- in its own
words -- why a wrong key means "submitted scores land in a board nobody
displays, a silent failure with no error shown to the player."

Showing that record is worth more than summarising it. A summary is a claim;
the ledger is evidence, including the parts where a gate was HELD and
nothing happened for three days.

BUILD TIME, NOT RUNTIME, and the difference from /development-rhythm/ is
deliberate. Release data moves whenever the game ships, so a generated page
about it would go stale on a schedule nobody controls. The ledger only
changes when a human performs a ceremony, so a --check that fails on drift
is a real signal rather than a permanent red.

NOTHING IS REWRITTEN, ONLY WITHHELD. The renderer refuses to publish rather
than quietly altering the record: assert_clean() raises if a withheld
pattern survives into the body. A ledger that said something different in
public from what it says in the repo would be worse than not publishing it.

The markdown renderer, the page shell and assert_clean are IMPORTED from
sync-design-notes.py, not reimplemented. This repo has been bitten by
parallel implementations of one rule (five escapers, three coverages); a
second markdown subset that drifts from the first is the same mistake in a
new place.
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "LEAGUE_SEED_LEDGER.md"
OUT = ROOT / "public" / "ledger" / "index.html"


def _design_notes():
    """Import the ADR renderer. Its markdown subset is the one measured against
    real documents in this repo, and it already handles the tables the ledger
    is mostly made of."""
    path = ROOT / "scripts" / "sync" / "sync-design-notes.py"
    spec = importlib.util.spec_from_file_location("sync_design_notes", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DN = _design_notes()

# ---------------------------------------------------------------- withholding
# INFRASTRUCTURE PROBE DETAIL. The L5 row records that api.pdoom1.com was down
# by naming the protocols and ports that timed out. That is the right level of
# detail for the person deciding whether to open a board, and the wrong level
# for a public page: it tells a reader nothing about the league and tells a
# scanner which services to look at. The FACT -- the host was unreachable, so
# the gate was held -- is what matters and is kept.
#
# Withheld by REPLACEMENT with a visible marker, never by deletion. A silent cut
# would make the public ledger quietly disagree with the repo's, and this
# document's whole value is that it is the record rather than an account of it.
WITHHOLD = [
    (re.compile(r"ICMP,\s*:\d+(?:,\s*:\d+)*\s*and\s*:\d+\s*all\s*TIME\s*OUT", re.I),
     "every service probed timed out"),
    # A bare port list anywhere else in the document, e.g. a future hold note.
    (re.compile(r"\bports?\s*:?\s*\d{2,5}(?:\s*,\s*\d{2,5})+"), "several ports"),
]

# After withholding, none of these may survive into the published body. This is
# the assert_clean half: if a pattern below still matches, the page is NOT
# written and the run fails.
FORBIDDEN = [
    (re.compile(r":22\b(?!\d)(?![:.]\d)"), "an SSH port reference"),
    (re.compile(r"\bICMP\b", re.I), "a raw protocol probe detail"),
]


def withhold(text):
    """Apply every withholding rule. Returns (text, [what was withheld])."""
    applied = []
    for pattern, replacement in WITHHOLD:
        text, n = pattern.subn(replacement, text)
        if n:
            applied.append(f"{n}x -> {replacement!r}")
    return text, applied


def assert_publishable(body):
    """Refuse to publish if a forbidden pattern survived. Mirrors
    sync-design-notes.assert_clean(): the generator declines rather than
    shipping something it cannot vouch for."""
    problems = []
    for pattern, label in FORBIDDEN:
        for m in pattern.finditer(body):
            start = max(0, m.start() - 50)
            problems.append(f"{label}: ...{body[start:m.end() + 50]}...")
    if problems:
        raise AssertionError(
            "REFUSING TO WRITE /ledger/: content that should have been withheld "
            "survived into the rendered body.\n  " + "\n  ".join(problems)
            + "\nFix the WITHHOLD patterns in this script. Do NOT relax FORBIDDEN "
              "to make this pass; that is the guard, not the obstacle.")


LEDE = (
    "The record of which seed governs which league epoch, when it was blessed, "
    "and by whom. This is the working document, not a summary of it — "
    "including the entries where a gate was held and nothing happened for days."
)


def build(check_only=False):
    if not SOURCE.exists():
        print(f"FAIL: {SOURCE} does not exist.")
        return 2
    raw = SOURCE.read_text(encoding="utf-8")

    text, applied = withhold(raw)
    # Drop the H1: the page supplies its own title, and a duplicated heading
    # reads as a rendering bug.
    text = re.sub(r"^#\s+.*$", "", text, count=1, flags=re.M)

    # scrub() returns (clean_text, n_removed) -- it strips HTML comments and the
    # ADRs' internal process markers. Both apply here: the ledger carries the same
    # kind of maintainer asides.
    clean, n_scrubbed = DN.scrub(text)
    body = DN.render(clean)
    assert_publishable(body)

    intro = (
        '<p class="lede">' + LEDE + '</p>'
        '<p class="sub">Rendered from <code>docs/LEAGUE_SEED_LEDGER.md</code> in the '
        'website repository. Infrastructure detail from outage notes is withheld and '
        'marked where that happens; nothing else is altered. '
        'See also <a href="/development-rhythm/">how irregular the pace has been</a> '
        'and <a href="/leaderboard/">the current board</a>.</p>'
    )

    html_out = DN.page(
        "League Ledger",
        "The record of which seed governs which p(Doom)1 league epoch, when it was "
        "blessed and by whom - the working document, not a summary.",
        "https://pdoom1.com/ledger/",
        intro + body,
    )

    if check_only:
        if not OUT.exists():
            print(f"STALE: {OUT} does not exist yet. Run without --check.")
            return 1
        if OUT.read_text(encoding="utf-8") != html_out:
            print(f"STALE: {OUT} no longer matches what {SOURCE.name} produces.")
            print("  The ledger has changed -- read the diff, then regenerate:")
            print("    python scripts/render-ledger.py")
            return 1
        print("OK: /ledger/ is in step with the ledger document.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_out, encoding="utf-8", newline="")
    for a in applied:
        print(f"  withheld: {a}")
    if n_scrubbed:
        print(f"  scrubbed {n_scrubbed} internal line(s)/comment(s)")
    print(f"Wrote {OUT} ({len(html_out)} bytes)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="fail if the page is out of step, write nothing")
    args = ap.parse_args(argv)
    try:
        return build(check_only=args.check)
    except AssertionError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
