#!/usr/bin/env python
"""Every number /issues/ can render must say what it counts.

WHY THIS EXISTS
---------------
On 2026-08-24 pdoom1.com/issues/ rendered "15 open issues". The repository held
**200**. The 15 was `per_page` from the API request the cache was built with --
the page size of a query, displayed as a count of the world, wrong by more than
a factor of thirteen, and it was the one sentence a visitor took away.

Four more on the same page, same day, all measured:
  - "Last updated" printed `new Date()` -- the visitor's own clock. The real
    stamp was in the file and discarded, so a cache frozen for six months still
    looked current.
  - an empty cache rendered "No open issues! Everything is working smoothly."
  - 2 of the 15 cards were pull requests, under a heading reading "Known Issues".
  - 11 of the 15 carried no labels, so the triage icon defaulted to "normal".

None of that was caught by anything. `scripts/test-escaping.js` covers the page's
escaping and nothing covered its arithmetic.

WHAT THIS CHECKS, and it is deliberately about the CACHE rather than the page:
the page can only render what the cache carries, so a cache that cannot support
an honest sentence is the defect. Checking rendered HTML would mean parsing a
template; checking the contract the template reads is exact.

Exit 0 clean, 1 with findings, 2 when it cannot tell (missing/unreadable cache) --
2 is distinct on purpose: "I could not look" must never read as "nothing wrong".

Run: python scripts/check-issues-surface.py
"""

import json
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
CACHE = REPO_ROOT / "public" / "data" / "issues-cache.json"
PAGE = REPO_ROOT / "public" / "issues" / "index.html"

# Prose that asserts health from an absence. Each of these was live.
BANNED_PAGE_STRINGS = (
    "Everything is working smoothly",
    "No open issues!",
)


def _strip_comments(text):
    """Remove HTML comment blocks and whole-line JS `//` comments.

    Only lines whose FIRST non-whitespace is `//` are dropped -- a naive `//`
    split would eat every `https://` in the file and make the scan pass by
    deleting the page.
    """
    out = []
    depth_open = "<!--"
    depth_close = "-->"
    in_html = False
    for line in text.splitlines():
        if in_html:
            if depth_close in line:
                in_html = False
                line = line.split(depth_close, 1)[1]
            else:
                continue
        while depth_open in line:
            before, rest = line.split(depth_open, 1)
            if depth_close in rest:
                line = before + rest.split(depth_close, 1)[1]
            else:
                line = before
                in_html = True
                break
        if line.lstrip().startswith("//"):
            continue
        out.append(line)
    return "\n".join(out)


def main():
    findings = []

    if not CACHE.exists():
        print("CANNOT TELL: %s is missing. Not reporting a clean surface over a "
              "cache that is not there." % CACHE.name, file=sys.stderr)
        return 2
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print("CANNOT TELL: %s is unreadable (%s)." % (CACHE.name, exc),
              file=sys.stderr)
        return 2
    if not isinstance(cache, dict):
        print("CANNOT TELL: %s is not an object." % CACHE.name, file=sys.stderr)
        return 2

    issues = cache.get("issues")
    if not isinstance(issues, list):
        findings.append("`issues` is not a list, so nothing can be said about "
                        "what the page would render")
        issues = []

    # 1. The total must be PRESENT as a key. Its value may be null -- that means
    #    UNKNOWN and the page renders it as unknown -- but the key missing
    #    entirely means the page has no way to avoid falling back to the sample.
    if "total_open_issues" not in cache:
        findings.append(
            "no `total_open_issues` key. Without it the page has nothing to "
            "render but the sample size, which is how it came to display a "
            "per_page value as a count of open issues")
    else:
        total = cache["total_open_issues"]
        if total is not None and not isinstance(total, int):
            findings.append("`total_open_issues` is %r, neither an int nor null"
                            % (total,))
        elif isinstance(total, int) and total < len(issues):
            findings.append(
                "`total_open_issues` (%d) is smaller than the sample it is "
                "supposed to be a total of (%d)" % (total, len(issues)))

    # 2. The sample must be labelled as one.
    for key in ("sample_size", "sample_requested"):
        if key not in cache:
            findings.append("no `%s` -- the grid cannot be described as a sample "
                            "without it" % key)
    if isinstance(cache.get("sample_size"), int) and \
            cache["sample_size"] != len(issues):
        findings.append("`sample_size` (%s) disagrees with len(issues) (%d)"
                        % (cache["sample_size"], len(issues)))

    # 3. A real timestamp. The page's own clock is not one.
    if not cache.get("last_updated"):
        findings.append("no `last_updated` -- the page then has nothing to show "
                        "but the visitor's own clock, which is what it used to do")

    # 4. No pull requests in a list the page presents as issues.
    prs = [i for i in issues if isinstance(i, dict) and i.get("pull_request")]
    if prs:
        findings.append(
            "%d of %d sampled item(s) are pull requests. The /issues API returns "
            "PRs; this page renders them under a 'Known Issues' heading"
            % (len(prs), len(issues)))

    # 5. No bodies. Nothing renders them and they are third-party text on a
    #    public host -- the 2026-08-02 address leak and the 2026-08-13 severed
    #    address both arrived inside a body.
    bodied = [i for i in issues if isinstance(i, dict) and i.get("body")]
    if bodied:
        total_bytes = sum(len(i.get("body") or "") for i in bodied)
        findings.append(
            "%d sampled item(s) still carry `body` (%d bytes). The page renders "
            "none of it; it is published risk with no display value"
            % (len(bodied), total_bytes))

    # 6. The page must not assert health from an absence.
    #
    # Scanned with COMMENTS STRIPPED, and that is not a detail. The first version
    # of this check matched the whole file and fired on its own documentation --
    # the comment in index.html that quotes the removed sentence to explain why it
    # was removed. A guard that cannot tell rendered prose from prose ABOUT
    # rendered prose forces the fix to be "stop explaining the defect", which is
    # the opposite of what this repo wants. Same shape as a ledger scan tuned on
    # paragraphs failing on a table: the window was wrong, not the rule.
    if PAGE.exists():
        page = _strip_comments(PAGE.read_text(encoding="utf-8"))
        for banned in BANNED_PAGE_STRINGS:
            if banned in page:
                findings.append(
                    "%s renders %r outside a comment -- an empty cache would "
                    "publish a clean bill of health" % (PAGE.name, banned))
    else:
        findings.append("%s is missing" % PAGE.name)

    print("issues-cache.json: %d sampled, total_open_issues=%r, updated=%s"
          % (len(issues), cache.get("total_open_issues"),
             cache.get("last_updated")))

    if findings:
        print("\nFAIL: %d finding(s)" % len(findings), file=sys.stderr)
        for f in findings:
            print("  - %s" % f, file=sys.stderr)
        print("\nThe producer is .github/workflows/update-game-data.yml. Fix it "
              "there, not by hand-editing the cache -- the next run overwrites "
              "a hand edit.", file=sys.stderr)
        return 1

    print("OK: every number this page can render says what it counts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
