#!/usr/bin/env python3
"""
Guard: no reachable page may claim a platform is available that has no shipped build.

The rot this prevents (it bit us on 2026-07-25): the site said "Windows, macOS,
Linux" while only a Windows build existed. The single source of truth for "which
platforms shipped" is public/data/version.json -> latest_release.platforms, which
update-version-info.py derives from the release's actual assets (a build is either
attached or it is not -- un-fakeable). This script cross-checks the reader-facing
pages against that source.

HEURISTIC, and deliberately biased toward flagging. For each platform the source
marks UNavailable, it flags a reachable-page line that mentions that platform in an
availability context -- i.e. the line lists two or more OS names together, OR uses
an availability verb (download/available/supported/...) -- UNLESS the line also
carries a soft qualifier (coming soon / this week / in progress / later / a dash).
A qualified line ("macOS -- coming soon") is honest and passes; a bare list
("Windows, macOS, Linux") is not and fails.

Limits (stated, not hidden): it reads raw HTML lines, so a claim split across lines
can slip through, and it only scans the curated reachable set below. It is a
regression net for the specific failure mode above, not a proof of total honesty.

Exit 1 on any finding (so CI blocks it). Genuine false positives go in ALLOWLIST
with a reason, never by loosening the heuristic.
"""

import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.join(os.path.dirname(__file__), "..")
VERSION_JSON = os.path.join(ROOT, "public", "data", "version.json")

# Pages a visitor can actually walk to (the navigation.js menu + the download flow
# and the forms reached from it). Deliberately NOT the ~2,200 generated event pages.
REACHABLE = [
    "public/index.html",
    "public/press/index.html",
    "public/about/index.html",
    "public/game-stats/index.html",
    "public/leaderboard/index.html",
    "public/bug-report/index.html",
    "public/privacy/index.html",
    "public/cats/index.html",
    "public/issues/index.html",
    "public/game-changelog/index.html",
    # In navigation.js ("Risk Dashboard") and in the homepage footer, so a visitor
    # walks to it. Added 2026-08-03: it was missing, which meant every
    # reachability-scoped guard was structurally unable to see the page -- and the
    # page was carrying a release log frozen ~324 days in the past.
    "public/dashboard/index.html",
    "public/docs/index.html",
    "public/blog/index.html",
    "public/resources/index.html",
    # /metrics/ names platforms nowhere today, which is exactly why it belongs
    # here: the cheap moment to add a page to a reachability-scoped guard is
    # before someone writes "downloads on Windows, macOS and Linux" into it.
    "public/metrics/index.html",
]

# Word-boundary name matchers per platform key in version.json.
PLATFORM_NAMES = {
    "windows": re.compile(r"\bwindows\b", re.I),
    "macos": re.compile(r"\bmac\s?os\b|\bmacos\b|\bos\s?x\b|\bosx\b", re.I),
    "linux": re.compile(r"\blinux\b", re.I),
}

# A line that says one of these near a platform is asserting availability.
AVAILABILITY_VERB = re.compile(
    r"\b(download|available|supported|exported to|runs? on|native on|"
    r"get it on|play on|ships? on|grab the)\b",
    re.I,
)

# ...unless it is softened into a promise, not a claim of the present.
SOFT_QUALIFIER = re.compile(
    r"coming soon|coming|\bsoon\b|this week|in progress|\bplanned\b|not yet|"
    r"\blater\b|roadmap|\bfuture\b|work in progress|\bwip\b|"
    r"—|&mdash;|--",  # an em dash, as in "macOS -- coming soon"
    re.I,
)

# (file substring, line substring) pairs that are known-honest despite tripping the
# heuristic. Add with a comment saying WHY; do not weaken the rules to clear one.
ALLOWLIST = [
    # (file substring, line substring, and the reason must be readable here)
    #
    # 2026-08-24. The first-run note explains WHY unsigned builds trigger an OS
    # warning, and names the two things that would stop it: a code-signing
    # certificate on Windows, an Apple Developer identity plus notarization on
    # macOS. That is a sentence about code signing, not a claim that a macOS
    # build is available -- and it stays true whether or not one exists, which is
    # the test for whether an allowlist entry is honest or a silencer.
    #
    # The guard cannot tell an availability claim from an explanatory mention,
    # and it should not try: loosening the heuristic to exclude "notarization"
    # would blind it to a real claim in a sentence that happened to use the word.
    # Naming the exception is cheaper and leaves the finding visible.
    #
    # THIS ENTRY EXPIRES WITH ITS SENTENCE. If the first-run note is rewritten,
    # re-read it before assuming this still applies.
    ("public/index.html",
     "Apple Developer identity plus notarization"),
]


def strip_to_visible_text(html):
    """Reduce HTML to what a visitor actually reads: drop <script>/<style>/comment
    blocks and all tags (so element ids like `download-macos` and JS regexes can't
    masquerade as prose), while preserving line numbers by replacing each removed
    span with as many newlines as it contained."""
    def blank(m):
        return "\n" * m.group(0).count("\n")
    html = re.sub(r"<script\b[^>]*>.*?</script>", blank, html, flags=re.I | re.S)
    html = re.sub(r"<style\b[^>]*>.*?</style>", blank, html, flags=re.I | re.S)
    html = re.sub(r"<!--.*?-->", blank, html, flags=re.S)
    html = re.sub(r"<[^>]+>", blank, html)  # remaining tags (attrs live here) -> gone
    return html


def load_available_platforms():
    with open(VERSION_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    platforms = (data.get("latest_release") or {}).get("platforms")
    if not isinstance(platforms, dict):
        return None
    return platforms


def allowlisted(path, line):
    for f_sub, l_sub in ALLOWLIST:
        if f_sub in path and l_sub in line:
            return True
    return False


def scan():
    platforms = load_available_platforms()
    if platforms is None:
        print("SKIP: version.json has no latest_release.platforms; nothing to check.")
        print("      (An older version.json predates the platforms field.)")
        return 0

    unavailable = [p for p, ok in platforms.items() if not ok]
    available = [p for p, ok in platforms.items() if ok]
    print(f"version.json platforms -> available: {available or '(none)'} | "
          f"unavailable: {unavailable or '(none)'}")
    if not unavailable:
        print("No unavailable platforms to guard against. OK.")
        return 0

    findings = []
    for rel in REACHABLE:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            print(f"  note: {rel} not found, skipped")
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            visible = strip_to_visible_text(f.read())
        for n, raw in enumerate(visible.split("\n"), 1):
                line = raw.rstrip("\n")
                if SOFT_QUALIFIER.search(line):
                    continue  # a softened promise, not a present-tense claim
                names_hit = [p for p, rx in PLATFORM_NAMES.items() if rx.search(line)]
                unavail_hit = [p for p in names_hit if p in unavailable]
                if not unavail_hit:
                    continue
                is_list = len(names_hit) >= 2
                is_verb = bool(AVAILABILITY_VERB.search(line))
                if (is_list or is_verb) and not allowlisted(rel, line):
                    findings.append((rel, n, unavail_hit, line.strip()[:160]))

    if not findings:
        print(f"OK: no reachable page claims {unavailable} as available.")
        return 0

    print(f"\nFAIL: {len(findings)} line(s) claim an unshipped platform as available:\n")
    for rel, n, hit, text in findings:
        print(f"  {rel}:{n}  (claims: {', '.join(hit)})")
        print(f"      {text}")
    print("\nFix: add a soft qualifier (\"coming soon\") or remove the platform, or")
    print("if the release now ships it, update version.json/its assets. Genuine false")
    print("positives go in ALLOWLIST with a reason.")
    return 1


if __name__ == "__main__":
    sys.exit(scan())
