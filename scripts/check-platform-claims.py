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

TWO CATEGORIES, DECLARED IN THE MARKUP (new rule, 2026-08-24)
------------------------------------------------------------
The heuristic above cannot tell an availability CLAIM from an EXPLANATION that
happens to name an OS. On 2026-08-24 it flagged this line on the homepage:

    certificate (Windows) or an Apple Developer identity plus notarization (macOS).

That is a true statement about what code-signing costs. It would be equally true
if p(Doom)1 never shipped a Mac build at all -- it asserts no build exists. But it
names two operating systems on one line, so `is_list` fired. No amount of regex
tuning fixes that: the difference is authorial intent, which is not in the text.

So the intent is now written down, in the markup, where a reviewer sees it in the
diff and this script can read it:

  data-platform-claim="explanatory"
      A subtree that names operating systems to EXPLAIN how they behave --
      Gatekeeper, SmartScreen, notarization, chmod. It asserts no build exists.
      EXEMPT from the scan, and every exempted line is PRINTED, so the exemption
      cannot grow in silence the way an ALLOWLIST quietly can.

  data-platform-claim="rendered"
      A subtree whose text is written at runtime from version.json by
      renderPlatformClaims(). NOT exempt, and deliberately so: what ships in the
      HTML is a placeholder that a visitor with JS off, or a visitor served
      before the fetch resolves, actually reads. If that placeholder names an
      unshipped platform in an availability context it is exactly as false as
      typed prose, and it is flagged exactly the same. The attribute is a claim
      about WHO WRITES the text, not a licence to say anything.

Any other value is a typo and FAILS -- an unrecognised value must never silently
degrade into "not exempt but looks handled".

Why "rendered" is worth marking at all, given it changes nothing here: it is the
hook the JS tests assert against (scripts/test-platform-render.js checks that every
slot declared in the markup is one renderPlatformClaims() actually writes, and that
every shipped placeholder names no OS), and it tells the next person that editing
that text by hand accomplishes nothing.

Limits (stated, not hidden): it reads raw HTML lines, so a claim split across lines
can slip through, and it only scans the curated reachable set below. It is a
regression net for the specific failure mode above, not a proof of total honesty.
The em-dash entry in SOFT_QUALIFIER is a known hole -- ANY em dash on a line
disarms the check for that whole line, which is how "Windows is the tested build;
macOS and Linux are new and largely untested" sat on the homepage unflagged
through a release that shipped no macOS build. Narrowing it is a separate change;
it would need every genuine "macOS -- coming soon" re-checked first.

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


# --- the declared-category machinery (2026-08-24) --------------------------------
# See the module docstring for WHY this cannot be a regex refinement.

VALID_CLAIM_VALUES = {"explanatory", "rendered"}

CLAIM_ATTR = re.compile(r"data-platform-claim\s*=\s*[\"']([^\"']*)[\"']", re.I)

# Attribute soup, quote-aware so a `>` inside an attribute value does not end the tag.
_ATTRS = r"(?:[^>\"']|\"[^\"]*\"|'[^']*')*"
OPEN_TAG = re.compile(r"<([a-zA-Z][\w:-]*)(" + _ATTRS + r")>")

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


def _line_of(html, offset):
    return html.count("\n", 0, offset) + 1


def _matching_close(html, tag, pos):
    """End offset of the close tag matching an open `tag` at `pos`, or None.

    Counts opens/closes of THIS TAG NAME ONLY. Deliberately not a real parser: HTML
    in the wild leaves <p> and <li> unclosed, and a general depth counter would
    desynchronise and hand back a span running to end of file -- which, for an
    exemption, means silently exempting the whole page. Same-name counting is immune
    to that. An unclosed tag returns None and is reported as an error rather than
    guessed at, for the same reason.
    """
    rx = re.compile(r"<(/?)" + re.escape(tag) + r"(?=[\s/>])(" + _ATTRS + r")>", re.I)
    depth = 1
    for m in rx.finditer(html, pos):
        if m.group(1):
            depth -= 1
            if depth == 0:
                return m.end()
        elif not m.group(2).rstrip().endswith("/"):
            depth += 1
    return None


def declared_categories(html):
    """(exempt_lines, rendered_count, errors) for one page's raw HTML.

    exempt_lines is the set of 1-based line numbers covered by a
    data-platform-claim="explanatory" subtree. `rendered` subtrees are counted and
    NOT exempted -- what ships in the HTML is what a JS-off reader reads.
    """
    exempt, rendered, errors = set(), 0, []
    for m in OPEN_TAG.finditer(html):
        tag, attrs = m.group(1), m.group(2)
        cm = CLAIM_ATTR.search(attrs)
        if not cm:
            continue
        value = cm.group(1).strip().lower()
        if value not in VALID_CLAIM_VALUES:
            errors.append((_line_of(html, m.start()),
                           "unknown data-platform-claim value %r (expected one of %s)"
                           % (cm.group(1), ", ".join(sorted(VALID_CLAIM_VALUES)))))
            continue
        if value == "rendered":
            rendered += 1
            continue
        # explanatory: exempt its whole subtree
        if tag.lower() in VOID_TAGS or attrs.rstrip().endswith("/"):
            end = m.end()
        else:
            end = _matching_close(html, tag, m.end())
        if end is None:
            errors.append((_line_of(html, m.start()),
                           'data-platform-claim="explanatory" on an unclosed <%s> -- '
                           "refusing to guess how far the exemption reaches" % tag))
            continue
        for n in range(_line_of(html, m.start()), _line_of(html, end) + 1):
            exempt.add(n)
    return exempt, rendered, errors


def load_available_platforms():
    with open(VERSION_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    platforms = (data.get("latest_release") or {}).get("platforms")
    if not isinstance(platforms, dict):
        return None
    return platforms


# How far from a platform name a qualifier has to be to still be about it.
# One clause, roughly -- long enough for "macOS -- coming soon" and
# "macOS: not in this release", short enough that a dash at the far end of a
# long sentence is not read as hedging a claim near the start.
QUALIFIER_WINDOW = 60


def hedged_near(line, platform):
    """Is this platform's mention softened by a qualifier CLOSE TO IT?

    This used to be a whole-line test -- `if SOFT_QUALIFIER.search(line): continue`
    -- and an em dash counts as a qualifier, so ANY line containing one anywhere
    was skipped entirely, claim and all.

    TWO LIVE FALSE CLAIMS SURVIVED THAT, both found by reading pdoom1.com rather
    than by running this script, on the day four sibling claims were fixed and it
    reported OK:

      "Windows, macOS and Linux are all available &mdash; Windows is the tested one"
      "...from the buttons above &mdash; no installation... macOS and Linux are new"

    In the first the dash follows the claim; in the second it precedes an unrelated
    clause. Neither hedges anything, and both made the line invisible.

    Scoping the search to a window around each platform mention keeps every genuine
    "macOS -- coming soon" passing while making the claim before or after an
    unrelated dash visible again. Checked per PLATFORM rather than per line, so one
    hedged platform no longer excuses an unhedged one beside it.
    """
    rx = PLATFORM_NAMES.get(platform)
    if not rx:
        return False
    for m in rx.finditer(line):
        lo = max(0, m.start() - QUALIFIER_WINDOW)
        hi = min(len(line), m.end() + QUALIFIER_WINDOW)
        if not SOFT_QUALIFIER.search(line[lo:hi]):
            return False       # at least one mention of this platform is unhedged
    return True


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
    errors = []
    exempted = []   # (file, line, text) -- printed, so the exemption cannot grow quietly
    rendered_total = 0
    for rel in REACHABLE:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            print(f"  note: {rel} not found, skipped")
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        exempt_lines, rendered, page_errors = declared_categories(html)
        rendered_total += rendered
        for n, msg in page_errors:
            errors.append((rel, n, msg))
        visible = strip_to_visible_text(html)
        for n, raw in enumerate(visible.split("\n"), 1):
                line = raw.rstrip("\n")
                names_hit = [p for p, rx in PLATFORM_NAMES.items() if rx.search(line)]
                unavail_hit = [p for p in names_hit
                               if p in unavailable and not hedged_near(line, p)]
                if not unavail_hit:
                    continue
                is_list = len(names_hit) >= 2
                is_verb = bool(AVAILABILITY_VERB.search(line))
                if not (is_list or is_verb) or allowlisted(rel, line):
                    continue
                # The category is declared in the markup, not inferred. Explanation
                # about an OS is not a claim that a build for it exists.
                if n in exempt_lines:
                    exempted.append((rel, n, line.strip()[:160]))
                    continue
                findings.append((rel, n, unavail_hit, line.strip()[:160]))

    print(f"declared categories: {rendered_total} rendered element(s) "
          f"(scanned like any other -- the shipped placeholder is what a JS-off "
          f"reader reads), {len(exempted)} line(s) exempted as explanatory")
    for rel, n, text in exempted:
        print(f"  exempt (explanatory)  {rel}:{n}")
        print(f"      {text}")

    if errors:
        print(f"\nFAIL: {len(errors)} malformed data-platform-claim declaration(s):\n")
        for rel, n, msg in errors:
            print(f"  {rel}:{n}  {msg}")
        return 1

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
