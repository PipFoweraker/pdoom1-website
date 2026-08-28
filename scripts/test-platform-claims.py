#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Forced-failure tests for scripts/check-platform-claims.py.

WHY THIS EXISTS
---------------
check-platform-claims.py is the guard that stops pdoom1.com telling a player a build
exists when it does not. It has been green in CI since it was wired to
content-honesty.yml -- and that green has carried NO information.

Read its scan():

    unavailable = [p for p, ok in platforms.items() if not ok]
    ...
    if not unavailable:
        print("No unavailable platforms to guard against. OK.")
        return 0        # <-- BEFORE OPENING A SINGLE PAGE

Every platform in version.json is currently true, so the guard returns 0 having read
zero bytes of HTML. A page could say "Download for BeOS, Plan 9 and macOS" and the run
would still be green. Test 1 below asserts exactly that, so the vacuity is a recorded
fact rather than a surprise -- and so that anyone who later "fixes" the early return
finds out here.

CLAUDE.md, Testing discipline: "A guard seen only in its passing state has not been
shown to work. Green is equally consistent with 'the condition is safe' and 'the check
never fires'. Make it fail on purpose once and keep that as the test."

Every case below FORCES a state the live repo is not in: a platform marked false, a
missing platforms key, a page that lies. Nothing here reads or writes real repo data
except test 9, which asserts the real REACHABLE list still points at files that exist
(a renamed page would otherwise silently shrink the guard's coverage to nothing, which
is the same failure in slower motion).

Follows the isolation pattern of test-publish-live-board.py: import the module, redirect
its path constants into a temp dir, restore them afterwards. No network, no secrets.

Run:  python scripts/test-platform-claims.py     (exit 0 = pass)
"""

import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_platform_claims", ROOT / "scripts" / "check-platform-claims.py")
cpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpc)

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


class Sandbox:
    """Point the guard at a temp tree with a forced version.json and forced pages.

    `platforms=None` omits latest_release.platforms entirely, which is the state
    update-game-data.yml leaves version.json in roughly half the time (CLAUDE.md:
    "version.json has TWO writers, and one of them disarms the guard").
    """

    def __init__(self, platforms, pages, allowlist=None):
        self.platforms, self.pages, self.allowlist = platforms, pages, allowlist

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = {k: getattr(cpc, k)
                       for k in ("ROOT", "VERSION_JSON", "REACHABLE", "ALLOWLIST")}

        release = {"tag_name": "v9.9.9"}
        if self.platforms is not None:
            release["platforms"] = self.platforms
        vj = self.tmp / "public" / "data" / "version.json"
        vj.parent.mkdir(parents=True, exist_ok=True)
        vj.write_text(json.dumps({"latest_release": release}), encoding="utf-8")

        for rel, body in self.pages.items():
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

        cpc.ROOT = str(self.tmp)
        cpc.VERSION_JSON = str(vj)
        cpc.REACHABLE = list(self.pages.keys())
        if self.allowlist is not None:
            cpc.ALLOWLIST = self.allowlist
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            setattr(cpc, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


def run():
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cpc.scan()
    return code, buf.getvalue()


ALL_SHIPPED = {"windows": True, "macos": True, "linux": True}
NO_MAC = {"windows": True, "macos": False, "linux": True}

# Deliberately carries NO soft qualifier and no em dash: an em dash anywhere on the
# line reads as "macOS -- coming soon" to the heuristic and would legitimately pass,
# which is the bug the first draft of this file had.
BLATANT_LIE = ("<html><body>\n"
               "<p>Download for macOS. Grab the build now.</p>\n"
               "<p>Windows, macOS and Linux builds are available today.</p>\n"
               "</body></html>")

print("\n1. THE VACUOUS GREEN: all platforms true -> returns 0 without reading a page")
with Sandbox(ALL_SHIPPED, {"public/lies.html": BLATANT_LIE}) as sb:
    code, out = run()
    check(code == 0, "exits 0, as it does in production today")
    check("No unavailable platforms" in out,
          "and says WHY it is green: there was nothing to guard against")
    check("lies.html" not in out,
          "the blatantly lying page was never opened -- this green proves nothing "
          "about the pages, only about version.json")

print("\n2. FORCED FAILURE: macos=false + a page advertising macOS -> rejected")
with Sandbox(NO_MAC, {"public/index.html":
                      "<html><body>\n<p>Download for macOS today.</p>\n</body></html>"}):
    code, out = run()
    check(code == 1, f"exit 1 -- the guard fires when there is something to fire on "
                     f"(got {code})")
    check("public/index.html:2" in out, "names the file AND the line to fix")
    check("macos" in out, "names the platform being falsely advertised")
    check("FAIL" in out, "says plainly that it failed")

print("\n3. Bare OS list with no availability verb is still a claim -> rejected")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n<p>Windows, macOS, Linux</p>\n</body></html>"}):
    code, out = run()
    check(code == 1, "two OS names on one line read as an availability list")

print("\n4. An honest promise passes: 'macOS -- coming soon' is not a lie")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n<p>Download for macOS &mdash; coming soon</p>\n"
                      "</body></html>"}):
    code, out = run()
    check(code == 0, "a softened, future-tense line is honest and must not be flagged")
    check("OK:" in out, "reports OK rather than staying silent")

print("\n5. Only what a VISITOR reads counts: markup is not prose")
with Sandbox(NO_MAC, {"public/p.html":
                      '<html><head><style>#download-macos{display:none}</style>'
                      '<script>var m="download for macOS available";</script></head>'
                      '<body>\n<a id="download-macos" data-platform-label="macOS">'
                      "Get the game</a>\n</body></html>"}):
    code, out = run()
    check(code == 0,
          "an element id, a JS string and a CSS selector are not claims to a reader")

print("\n6. THE DISARMED STATE: no platforms key -> SKIP, and it must SAY so")
with Sandbox(None, {"public/p.html": BLATANT_LIE}):
    code, out = run()
    check(code == 0, "exits 0 -- it cannot check what it cannot read")
    check("SKIP" in out,
          "prints SKIP. Absence of the key must render as UNKNOWN, never as 'fine': "
          "update-game-data.yml rebuilds version.json without it on a ~6h cron, so "
          "this state is reached in production, not just in a test")

print("\n7. ALLOWLIST suppresses one line, and only by exact substring")
with Sandbox(NO_MAC,
             {"public/p.html":
              "<html><body>\n<p>Download for macOS today.</p>\n</body></html>"},
             allowlist=[("public/p.html", "Download for macOS today.")]):
    code, _ = run()
    check(code == 0, "an allowlisted line is not a finding")
with Sandbox(NO_MAC,
             {"public/p.html":
              "<html><body>\n<p>Download for macOS today.</p>\n</body></html>"},
             allowlist=[("public/other.html", "Download for macOS today.")]):
    code, _ = run()
    check(code == 1, "an allowlist entry for a DIFFERENT file does not suppress it")

print("\n8. A missing reachable page is reported, not silently counted as clean")
with Sandbox(NO_MAC, {"public/p.html": "<html><body>fine</body></html>"}) as sb:
    cpc.REACHABLE = ["public/p.html", "public/gone.html"]
    code, out = run()
    check("gone.html" in out and "not found" in out,
          "names the page it could not read instead of passing over it in silence")

print("\n9. The REAL reachable list still points at files that exist")
missing = [rel for rel in cpc.REACHABLE if not (ROOT / rel).is_file()]
check(not missing,
      "every page in the live REACHABLE list is on disk"
      + (f" -- MISSING: {missing}" if missing else "")
      + ". A renamed page would silently drop out of the guard's coverage.")
check(len(cpc.REACHABLE) >= 10,
      f"the live REACHABLE list still covers the download surfaces "
      f"({len(cpc.REACHABLE)} pages)")

print("\n10. Regression net: the guard must not early-return once a platform is false")
with Sandbox(NO_MAC, {"public/p.html": BLATANT_LIE}):
    code, out = run()
    check(code == 1 and "p.html" in out,
          "with an unavailable platform present, pages ARE opened and scanned")

# ---------------------------------------------------------------------------
# THE DECLARED CATEGORIES (added 2026-08-24). The heuristic cannot separate a claim
# that a build exists from an explanation of how an OS behaves; the markup now says
# which is which. Both answers are forced below -- an exemption seen only in its
# passing state is indistinguishable from a disabled guard.
# ---------------------------------------------------------------------------

# The real sentence that tripped the guard on 2026-08-24. It names two OSes, so
# is_list fires, and it is true whether or not any Mac build exists.
NOTARIZATION = ("certificate (Windows) or an Apple Developer identity plus "
                "notarization (macOS).")

print('\n11. data-platform-claim="explanatory" exempts a subtree -- and SAYS it did')
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n"
                      '<div data-platform-claim="explanatory">\n'
                      "<p>" + NOTARIZATION + "</p>\n"
                      "</div>\n"
                      "</body></html>"}):
    code, out = run()
    check(code == 0, "explanation about an OS is not a claim that a build exists")
    check("exempt (explanatory)" in out and "notarization" in out,
          "the exempted line is PRINTED, so the exemption cannot grow in silence")

print("\n12. THE SAME SENTENCE, UNDECLARED, still fails -- the attribute does the work")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n<div>\n<p>" + NOTARIZATION + "</p>\n"
                      "</div>\n</body></html>"}):
    code, out = run()
    check(code == 1,
          "without the declaration it is flagged exactly as before -- so test 11's "
          "green is the attribute, not a loosened heuristic")

print("\n13. The exemption stops at the closing tag; a claim AFTER it still fails")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n"
                      '<div data-platform-claim="explanatory">\n'
                      "<p>" + NOTARIZATION + "</p>\n"
                      "</div>\n"
                      "<p>Download for macOS today.</p>\n"
                      "</body></html>"}):
    code, out = run()
    check(code == 1, "a real claim outside the exempt subtree is still caught")
    check("public/p.html:5" in out,
          "and the line named is line 5, the one after </div>, not the exempt one")

print("\n14. Nested same-name tags do not end the exemption early")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n"
                      '<div data-platform-claim="explanatory">\n'
                      "<div><p>inner</p></div>\n"
                      "<p>" + NOTARIZATION + "</p>\n"
                      "</div>\n"
                      "</body></html>"}):
    code, out = run()
    check(code == 0,
          "the inner </div> does not close the exemption -- depth is counted, and a "
          "miscount would have left the notarization line flagged")

print('\n15. data-platform-claim="rendered" is NOT exempt: the shipped text is read')
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n"
                      '<span data-platform-claim="rendered" data-platform-slot="x">'
                      "Download for macOS</span>\n"
                      "</body></html>"}):
    code, out = run()
    check(code == 1,
          "a rendered slot whose SHIPPED text claims macOS is flagged like any other "
          "-- a JS-off reader reads the placeholder, and 'a script will fix it' is "
          "not a defence")
    check("rendered element" in out, "the count of rendered elements is reported")

print("\n16. An honest rendered placeholder passes")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n"
                      '<span data-platform-claim="rendered" data-platform-slot="x">'
                      "Platform availability loads from the current release</span>\n"
                      "</body></html>"}):
    code, out = run()
    check(code == 0, "a placeholder that names no OS claims nothing and passes")

print("\n17. An unrecognised category value FAILS rather than degrading silently")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n"
                      '<div data-platform-claim="explanitory">\n'   # typo, on purpose
                      "<p>" + NOTARIZATION + "</p>\n</div>\n</body></html>"}):
    code, out = run()
    check(code == 1, "a typo in the value is an error, not an accidental exemption")
    check("unknown data-platform-claim value" in out and "explanitory" in out,
          "and it names the bad value and its line")

print("\n18. An UNCLOSED explanatory tag is refused, not guessed at")
with Sandbox(NO_MAC, {"public/p.html":
                      "<html><body>\n"
                      '<div data-platform-claim="explanatory">\n'
                      "<p>" + NOTARIZATION + "</p>\n"
                      "<p>Download for macOS today.</p>\n"
                      "</body></html>"}):
    code, out = run()
    check(code == 1,
          "an unclosed subtree would otherwise exempt everything to end of file -- "
          "silently disarming the guard for the rest of the page")
    check("unclosed" in out, "and it says the tag was unclosed")

print("\n19. The LIVE homepage carries the declarations this rule assumes")
live = (ROOT / "public" / "index.html").read_text(encoding="utf-8", errors="replace")
check('data-platform-claim="explanatory"' in live,
      "index.html declares its explanatory subtree")
_exempt, _rendered, _errs = cpc.declared_categories(live)
check(not _errs, f"the live page has no malformed declarations ({_errs})")
check(_rendered == 7,
      f"declared_categories() sees all 7 rendered slots on index.html (got {_rendered})")
_lines = live.count("\n") + 1
check(len(_exempt) < _lines // 4,
      f"the explanatory exemption covers {len(_exempt)} lines of a {_lines}-line page "
      f"-- a narrow subtree, not a blanket over the page")

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: check-platform-claims rejects a page advertising an unshipped platform, "
      "accepts an honest 'coming soon', and its all-shipped green is documented as "
      "vacuous rather than mistaken for evidence.")
