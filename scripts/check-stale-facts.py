#!/usr/bin/env python
"""Find hardcoded facts that will rot: versions, dates, and asserted numbers.

The site makes factual claims to players. Any claim baked into a file instead of
read from a source of truth will eventually be wrong, and nobody notices, because
being wrong looks exactly like being right until someone checks.

This finds three classes of rot:

  VERSION   A literal vX.Y.Z that disagrees with the current game version.
            The nastiest instances are FALLBACKS -- a script whose
            release lookup defaults to an ancient literal will stamp that
            ancient version onto the live site the moment the API hiccups.
            A fallback is a claim you make when you are least able to check it.

  DATE      A date literal older than the threshold sitting in a page,
            especially next to words like "as of" / "current" / "latest".

  ASSERTED  Prose stating a fact as current with no source and no date --
            share prices, model names, "expert consensus" figures.

Usage:
    python scripts/check-stale-facts.py                 # report everything
    python scripts/check-stale-facts.py --json          # machine-readable
    python scripts/check-stale-facts.py --max-age 120   # date staleness threshold
    python scripts/check-stale-facts.py --min-severity HIGH   # the CI gate

SEVERITY IS THE GATE, NOT THE FINDING COUNT
-------------------------------------------
Most of what this reports is correct history, not rot: a blog post titled
"v0.6.0" is a true statement about the past, a comment naming the version it
was written against is documentation. Those are LOW. On 2026-08-01 the full
report was 214 findings, of which 2 were HIGH -- so gating on "any finding"
would have meant a check that is red on every PR forever, which CLAUDE.md's
testing discipline calls worse than no check at all ("a red test in the suite
teaches everyone to skip the suite").

So the exit code is severity-gated:

    --min-severity LOW     (default) exit 1 on any finding    -- the full report
    --min-severity MEDIUM  exit 1 on MEDIUM or HIGH
    --min-severity HIGH    exit 1 only on HIGH                -- what CI blocks on

HIGH means the literal is presented as CURRENT: a fallback that ships when the
real lookup failed, or a date sitting next to "as of"/"latest". That is the
class that actually lies to a visitor. Everything printed below the gate is
still printed -- demoting a severity is not the same as hiding it.
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]

# Source of truth for the game version.
VERSION_JSON = REPO_ROOT / "public" / "data" / "version.json"

SCAN_GLOBS = ["public/**/*.html", "public/**/*.json", "public/**/*.js",
              "scripts/**/*.py", "scripts/**/*.js", ".github/workflows/*.yml"]

SKIP_PARTS = {"node_modules", ".git", "copy-baseline", "events", "backups",
              "archive", "__pycache__",
              # A dated capture archive. Old version literals in there are the POINT --
              # they are frozen evidence, never presented as current, and re-stamping
              # them would fabricate history. Flagging them forever is pure noise.
              "preserved"}

# Files whose CONTENT is a record of other versions. Flagging these is a guaranteed
# false positive that recurs on every regeneration, and a permanent block of known-noise
# findings is how a report teaches people to stop reading it.
SKIP_FILES = {
    # A dated observation of which score-API boards exist, per game version. Listing
    # non-current versions is its entire purpose -- none is presented as current.
    "board-liveness.json",
    # The published live board. Every entry carries the build the player ran, in
    # `game_mode`, and a board is keyed by (seed, LADDER EPOCH) precisely so that ONE
    # board legitimately spans several builds. So a correct board routinely holds build
    # strings that are not the current release -- including, right before a cut, the
    # NEXT one, because whoever proved the build scored on it. Those are observations of
    # what a player ran, not claims about what is current, and re-stamping them would
    # fabricate a score's provenance. Written by scripts/publish-live-board.py.
    "leaderboard.json",
    "published-board.json",
    # Board keys and epoch provenance, every value carrying a `source`. It cites the
    # versions that bracket a ladder fork by design.
    "board-probe-targets.json",
}

# Line-level false positives: (file substring, line substring, reason). Same contract as
# check-platform-claims.py's ALLOWLIST -- an entry needs a REASON, and the fix for a
# recurring false positive is an entry here, never a loosened heuristic. Matched as plain
# substrings against the repo-relative path and the raw line.
LINE_ALLOWLIST = [
    (".github/workflows/health-checks.yml",
     "while the page presented it as current health",
     "Past-tense narrative: the date is WHEN the published file was frozen, and the "
     "word 'current' belongs to the bug being described, not to a claim being made. "
     "Re-stamping it would erase the evidence for why the step exists."),
]


def line_allowlisted(rel_path, line):
    return any(f in rel_path and l in line for f, l, _ in LINE_ALLOWLIST)

SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)

VERSION_RE = re.compile(r"\bv?(\d+)\.(\d+)\.(\d+)\b")

# An IPv4 literal looks exactly like a version with a fourth octet. Matching
# "208.113.200" out of 208.113.200.215 produced pure noise on the first run.
IPV4_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")

DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")

# A literal in a default/fallback position is worse than one in prose: it is the
# value that ships precisely when the real lookup failed.
FALLBACK_HINT = re.compile(
    r"(fallback|default|\|\|\s*['\"]v?\d|\.get\([^)]*,\s*['\"]v?\d|or\s+['\"]v?\d)",
    re.I)

# Require a currency amount that looks like money, not a regex backreference.
CURRENCY_CLAIM = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\b")

CURRENTNESS_WORD = re.compile(
    r"\b(as of|currently|current|latest|today|now|this year|up to date)\b", re.I)

# Dependency pins and action refs are legitimately versioned.
PIN_CONTEXT = re.compile(r"(==|>=|<=|~=|\^|@|python-|node-|actions/)\s*$")

# Historical records SHOULD name old versions -- a blog post titled
# "Deterministic RNG System v0.6.0" is correct, not rot. Only a version
# presented as the CURRENT one can be a lie. These files are archives by nature.
HISTORICAL_FILES = re.compile(
    r"(blog/|changelog|/data/(changes|blog)\.json|release|patch-notes)", re.I)

# Third-party versions are not the game's version.
OTHER_PRODUCT = re.compile(
    r"\b(godot|python|node|ubuntu|nodebb|plausible|postgres|clickhouse|php)\b", re.I)


def current_version():
    """The version the site should be claiming, from its own data file."""
    try:
        d = json.loads(VERSION_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None
    for key in ("version", "game_version", "latest_version"):
        if isinstance(d.get(key), str):
            return d[key].lstrip("v")
    for parent, child in (("latest_release", "version"),
                          ("game", "latestRelease")):
        node = d.get(parent)
        if isinstance(node, dict):
            val = node.get(child)
            if isinstance(val, str):
                return val.lstrip("v")
            if isinstance(val, dict) and isinstance(val.get("version"), str):
                return val["version"].lstrip("v")
    return None


def iter_files():
    seen = set()
    self_name = Path(__file__).name
    for pattern in SCAN_GLOBS:
        for p in REPO_ROOT.glob(pattern):
            if not p.is_file() or p in seen:
                continue
            if SKIP_PARTS & set(p.relative_to(REPO_ROOT).parts):
                continue
            if p.name == self_name:
                continue          # this file documents the patterns it hunts
            if p.name in SKIP_FILES:
                continue
            seen.add(p)
            yield p


def blank_scripts(text):
    """Replace script/style bodies with spaces, preserving line numbering."""
    def repl(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    return SCRIPT_OR_STYLE.sub(repl, text)


def scan(max_age_days):
    cur = current_version()
    today = dt.date.today()
    findings = []

    for path in iter_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Prose-only view: client-side markdown parsers are full of regex
        # replacement templates that read as dollar amounts otherwise.
        prose_lines = blank_scripts(text).splitlines()
        lines = text.splitlines()

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if len(stripped) > 400:
                continue
            if line_allowlisted(rel, line):
                continue

            # --- VERSION ---------------------------------------------------
            ip_spans = [mm.span() for mm in IPV4_RE.finditer(line)]
            for m in VERSION_RE.finditer(line):
                if any(a <= m.start() < b for a, b in ip_spans):
                    continue
                if PIN_CONTEXT.search(line[:m.start()][-12:]):
                    continue
                found = "%s.%s.%s" % m.groups()
                if cur and found == cur:
                    continue
                if found.startswith("0.0"):
                    continue
                if OTHER_PRODUCT.search(line):
                    continue          # "built with Godot 4.5.1" is not our version
                is_fallback = bool(FALLBACK_HINT.search(line))
                claims_current = bool(CURRENTNESS_WORD.search(line))
                historical = bool(HISTORICAL_FILES.search(rel))
                if historical and not (is_fallback or claims_current):
                    continue          # an archive naming an old version is correct
                if is_fallback:
                    sev = "HIGH"
                elif claims_current:
                    sev = "MEDIUM"
                else:
                    sev = "LOW"
                findings.append({
                    "kind": "VERSION",
                    "severity": sev,
                    "file": rel, "line": i,
                    "found": found, "expected": cur,
                    "fallback": is_fallback,
                    "text": stripped[:150],
                })

            # --- DATE ------------------------------------------------------
            for m in DATE_RE.finditer(line):
                try:
                    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    continue
                age = (today - d).days
                if age < max_age_days or age < 0:
                    continue
                findings.append({
                    "kind": "DATE",
                    "severity": "HIGH" if CURRENTNESS_WORD.search(line) else "LOW",
                    "file": rel, "line": i,
                    "found": m.group(0), "age_days": age,
                    "text": stripped[:150],
                })

            # --- ASSERTED (prose only) -------------------------------------
            if not rel.endswith(".html"):
                continue
            pline = prose_lines[i - 1] if i - 1 < len(prose_lines) else ""
            cm = CURRENCY_CLAIM.search(pline)
            if cm and not re.search(r"(free|\$0\b|donat|fund|budget|cost|price of)",
                                    pline, re.I):
                findings.append({
                    "kind": "ASSERTED",
                    "severity": "MEDIUM",
                    "file": rel, "line": i,
                    "found": cm.group(0).strip(),
                    "text": pline.strip()[:150],
                })

    return cur, findings


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-age", type=int, default=180,
                    help="flag date literals older than N days (default: %(default)s)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--min-severity", choices=("HIGH", "MEDIUM", "LOW"), default="LOW",
                    help="lowest severity that makes the exit code non-zero "
                         "(default: %(default)s -- i.e. any finding). Findings below "
                         "the gate are still reported.")
    args = ap.parse_args()

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    gate = order[args.min_severity]

    cur, findings = scan(args.max_age)
    gating = [f for f in findings if order[f["severity"]] <= gate]

    if args.json:
        print(json.dumps({"current_version": cur,
                          "min_severity": args.min_severity,
                          "gating_count": len(gating),
                          "findings": findings}, indent=2))
        return 1 if gating else 0

    print("Current game version (from public/data/version.json): %s"
          % (cur or "UNKNOWN"))
    print("Gate: --min-severity %s (findings below this are reported, not failed on)"
          % args.min_severity)
    if not findings:
        print("No stale hardcoded facts found.")
        return 0

    findings.sort(key=lambda f: (order[f["severity"]], f["kind"], f["file"], f["line"]))

    groups = {}
    for f in findings:
        groups.setdefault((f["severity"], f["kind"]), []).append(f)

    for (sev, kind), group in sorted(groups.items(), key=lambda kv: order[kv[0][0]]):
        note = ""
        if kind == "VERSION" and sev == "HIGH":
            note = "   <- FALLBACKS: these ship when the real lookup fails"
        print("\n%s %s (%d)%s" % (sev, kind, len(group), note))
        print("-" * 72)
        for f in group:
            extra = ""
            if kind == "VERSION":
                extra = " (expected %s)" % f["expected"]
            elif kind == "DATE":
                extra = " (%d days old)" % f["age_days"]
            print("  %s:%s  %s%s" % (f["file"], f["line"], f["found"], extra))
            print("      %s" % f["text"])

    print("\n%d finding(s); %d at or above the %s gate."
          % (len(findings), len(gating), args.min_severity))
    if not gating:
        print("PASS: nothing at or above %s. The rest is reported, not failed on --"
              " re-run without --min-severity to gate on everything."
              % args.min_severity)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
