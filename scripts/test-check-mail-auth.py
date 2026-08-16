#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-failure tests for scripts/check-mail-auth.py.

WHY THIS EXISTS
---------------
check-mail-auth.py makes two claims that are worthless unless somebody has seen
them fail:

  1. "Absence of a record renders as a named finding, never as fine."
  2. "M5 refuses to let the DMARC policy rise above p=none while any PHP mailer
     would fail alignment."

Claim 2 is load-bearing and, on the live repo today, UNTESTABLE by observation:
the intended policy IS p=none, so M5 passes, and a passing M5 is equally
consistent with "the interlock works" and "the interlock never fires". CLAUDE.md:
"A guard seen only in its passing state has not been shown to work. Make it fail
on purpose once and keep that as the test."

So every case below FORCES a state the live repo is not in.

NO NETWORK. DNS is stubbed by construction rather than by monkeypatching a
socket: the checker's offline path reads an OBSERVATION out of the spec file, so
a fixture spec IS a stubbed resolver. Nothing here resolves a name, opens a
socket, or reads the real data/mail-auth.json except test group 9, which asserts
that the live spec's declared mailer paths still exist -- a renamed file would
otherwise shrink the guard's coverage to nothing, silently, which is the failure
test-platform-claims.py test 9 exists to catch in its own guard.

The live-DNS path (`--live`) is deliberately NOT exercised here. A test that
resolves DNS is a test that goes red when a runner's resolver hiccups, and a
flaky red teaches everyone to ignore red.

Run:  python scripts/test-check-mail-auth.py     (exit 0 = pass)
"""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import datetime as dt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-mail-auth.py"

_spec = importlib.util.spec_from_file_location("check_mail_auth", SCRIPT)
cma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cma)

TODAY = dt.date(2026, 8, 15)

failures = []
group = [""]


def section(name):
    group[0] = name
    print(f"\n{name}")


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(f"{group[0]}: {msg}")


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

GOOD_SPF = "v=spf1 include:_spf.google.com include:netblocks.dreamhost.com ~all"

# The mailer as it exists today: four arguments, no envelope sender.
PHP_UNALIGNED = """<?php
const RECIPIENT = 'team@pdoom1.com';
const FROM      = 'team@pdoom1.com';
$sent = @mail(RECIPIENT, $subject, $body, $headers);
"""

# The mailer as it must look before the ceiling may rise.
PHP_ALIGNED = """<?php
const RECIPIENT = 'team@pdoom1.com';
const FROM      = 'team@pdoom1.com';
$sent = @mail(RECIPIENT, $subject, $body, $headers, '-f ' . FROM);
"""


def base_spec(**over):
    spec = {
        "domain": "pdoom1.com",
        "max_observation_age_days": 30,
        "senders": [
            {"id": "google-workspace", "what": "Workspace", "ip": None,
             "spf_mechanism": "include:_spf.google.com", "runs_php": False,
             "source": "fixture"},
            {"id": "dreamhost-shared", "what": "shared host",
             "ip": "173.236.253.218",
             "spf_mechanism": "include:netblocks.dreamhost.com",
             "runs_php": True, "source": "fixture"},
        ],
        "intended": {
            "spf": GOOD_SPF,
            "dmarc": "v=DMARC1; p=none; rua=mailto:team@pdoom1.com",
            "dkim_selector": "google._domainkey",
            "source": "fixture",
        },
        "php_mailers_expected": ["public/bug-submit.php"],
        "observation": {
            "observed_on": "2026-08-15",
            "resolver": "ns1.dreamhost.com",
            "observed_by": "fixture",
            "source": "fixture",
            "records": {"spf": [], "dmarc": [],
                        "dkim": {"google._domainkey": []}},
        },
    }
    spec.update(copy.deepcopy(over))
    return spec


# A sentinel, because `None` is a MEANINGFUL value here -- it is the "nobody
# queried this" state, and the whole point of test group 1 is that it must not
# collapse into "queried and empty". Defaulting on `is None` would have silently
# turned every UNMEASURED case into an ABSENT one and the test would have passed
# while asserting nothing.
_UNSET = object()


def with_records(spf=_UNSET, dmarc=_UNSET, dkim=_UNSET, **over):
    spec = base_spec(**over)
    spec["observation"]["records"] = {
        "spf": [] if spf is _UNSET else spf,
        "dmarc": [] if dmarc is _UNSET else dmarc,
        "dkim": {"google._domainkey": []} if dkim is _UNSET else dkim,
    }
    return spec


def run_eval(spec, php=None, today=TODAY):
    """Evaluate against a throwaway tree. Returns {check id: Result}."""
    php = {"public/bug-submit.php": PHP_UNALIGNED} if php is None else php
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for rel, body in php.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        results, files, calls, aligned, unaligned, ceiling = cma.evaluate(
            spec, root, today)
    out = {r.cid: r for r in results}
    out["_ceiling"] = ceiling
    out["_unaligned"] = unaligned
    out["_calls"] = calls
    return out


def state(spec, cid="M1", php=None, today=TODAY):
    return run_eval(spec, php, today)[cid].state


def key(spec, cid="M1", php=None, today=TODAY):
    r = run_eval(spec, php, today)[cid]
    return r.key(spec["domain"])


# --------------------------------------------------------------------------
section("1. M1 -- the three states are kept apart, and absence is a FINDING")
# --------------------------------------------------------------------------

check(state(with_records(spf=[])) == cma.STATE_ABSENT,
      "queried and empty -> ABSENT (this is the live world today)")
check(key(with_records(spf=[]), "M1") == "pdoom1.com/M1/absent",
      "ABSENT carries the stable key pdoom1.com/M1/absent")
check(state(with_records(spf=None)) == cma.STATE_UNMEASURED,
      "null (nobody looked) -> UNMEASURED, NOT the same as absent, NOT fine")
check(key(with_records(spf=None), "M1") == "pdoom1.com/M1/unmeasured",
      "UNMEASURED gets its OWN key, so an acceptance of 'absent' cannot forgive it")
check(state(with_records(spf=[GOOD_SPF])) == cma.STATE_PASS,
      "one good record -> PASS")
check(state(with_records(spf=[GOOD_SPF, "v=spf1 -all"])) == cma.STATE_WRONG,
      "TWO v=spf1 records -> WRONG (RFC 7208 permerror, worse than none)")
check(state(with_records(spf=["v=spf1 include:_spf.google.com"])) == cma.STATE_WRONG,
      "record with no `all` mechanism -> WRONG (never reaches a verdict)")
check(state(with_records(spf=["v=DMARC1; p=none"])) == cma.STATE_ABSENT,
      "a TXT record that is not SPF does not count as an SPF record")

# --------------------------------------------------------------------------
section("2. M2 -- coverage is DERIVED (ip4 containment), not string-matched")
# --------------------------------------------------------------------------

check(state(with_records(spf=[GOOD_SPF]), "M2") == cma.STATE_PASS,
      "both include: mechanisms present -> PASS")
check(state(with_records(spf=["v=spf1 include:_spf.google.com ~all"]), "M2")
      == cma.STATE_WRONG,
      "Google only -> WRONG: the DreamHost box that runs the mailer is uncovered")
check(state(with_records(spf=["v=spf1 include:_spf.google.com "
                              "ip4:173.236.128.0/17 ~all"]), "M2")
      == cma.STATE_PASS,
      "ip4:173.236.128.0/17 CONTAINS 173.236.253.218 -> PASS by computation")
check(state(with_records(spf=["v=spf1 include:_spf.google.com "
                              "ip4:173.236.128.0/24 ~all"]), "M2")
      == cma.STATE_WRONG,
      "a /24 that does NOT contain the address -> WRONG (not fooled by a prefix)")
check(state(with_records(spf=[]), "M2") == cma.STATE_UNEVALUABLE,
      "no SPF record -> UNEVALUABLE, which is a finding, never a pass")
check(key(with_records(spf=[]), "M2") == "pdoom1.com/M2/unevaluable-no-spf",
      "UNEVALUABLE carries its own key, so it needs its own acknowledgement")

# --------------------------------------------------------------------------
section("3. M3 / M4 -- present-but-wrong is not present-and-correct")
# --------------------------------------------------------------------------

check(state(with_records(dmarc=[]), "M3") == cma.STATE_ABSENT,
      "no DMARC -> ABSENT")
check(state(with_records(dmarc=None), "M3") == cma.STATE_UNMEASURED,
      "DMARC not queried -> UNMEASURED")
check(state(with_records(dmarc=["v=DMARC1; rua=mailto:x@pdoom1.com"]), "M3")
      == cma.STATE_WRONG,
      "DMARC with no p= tag -> WRONG")
check(state(with_records(dmarc=["v=DMARC1; p=maybe"]), "M3") == cma.STATE_WRONG,
      "p=maybe is not a DMARC policy -> WRONG")
check(state(with_records(dmarc=["v=DMARC1; p=none", "v=DMARC1; p=reject"]), "M3")
      == cma.STATE_WRONG,
      "two DMARC records -> WRONG (receivers ignore the lot)")
check(state(with_records(dmarc=["v=DMARC1; p=none; rua=mailto:t@pdoom1.com"]), "M3")
      == cma.STATE_PASS,
      "one well-formed record -> PASS")

check(state(with_records(dkim={"google._domainkey": []}), "M4") == cma.STATE_ABSENT,
      "selector queried, NXDOMAIN -> ABSENT")
check(state(with_records(dkim=None), "M4") == cma.STATE_UNMEASURED,
      "dkim block null -> UNMEASURED")
check(state(with_records(dkim={"other._domainkey": ["v=DKIM1; p=AAA"]}), "M4")
      == cma.STATE_UNMEASURED,
      "a DIFFERENT selector was measured -> UNMEASURED for the intended one, "
      "never a pass by proxy")
check(state(with_records(dkim={"google._domainkey": ["hello world"]}), "M4")
      == cma.STATE_WRONG,
      "a TXT that is not a DKIM key -> WRONG")
check(state(with_records(dkim={"google._domainkey": ["v=DKIM1; k=rsa; p=AAA"]}), "M4")
      == cma.STATE_PASS,
      "a real key -> PASS")

# --------------------------------------------------------------------------
section("4. M5 -- THE INTERLOCK, forced red (the reason this file exists)")
# --------------------------------------------------------------------------

# The live world plus one edit: somebody tightens the policy while the mailer
# still passes no 5th parameter. This is the outcome the binding directive
# forbids -- every intake mail silently discarded, no bounce, no error.
tighten = with_records(spf=[GOOD_SPF], dmarc=[])
tighten["intended"]["dmarc"] = "v=DMARC1; p=quarantine; rua=mailto:t@pdoom1.com"
r = run_eval(tighten)
check(r["M5"].state == cma.STATE_WRONG,
      "intended p=quarantine + unaligned mailer -> M5 WRONG (build fails)")
check(r["M5"].key("pdoom1.com") == "pdoom1.com/M5/policy-above-ceiling",
      "...with the key pdoom1.com/M5/policy-above-ceiling")
check("bug-submit.php" in "".join(f"{c.path}" for c, _ in r["_unaligned"]),
      "...and it names the file that holds the ceiling down")

tighten["intended"]["dmarc"] = "v=DMARC1; p=reject"
check(state(tighten, "M5") == cma.STATE_WRONG,
      "p=reject is refused for the same reason, harder")

# The other direction: the policy is fine, but DNS has been tightened behind our
# back. The interlock must read the PUBLISHED policy too, not only our intent.
published = with_records(spf=[GOOD_SPF], dmarc=["v=DMARC1; p=quarantine"])
check(state(published, "M5") == cma.STATE_WRONG,
      "PUBLISHED p=quarantine + unaligned mailer -> WRONG even though intended is none")

sp_only = with_records(spf=[GOOD_SPF], dmarc=["v=DMARC1; p=none; sp=reject"])
check(state(sp_only, "M5") == cma.STATE_WRONG,
      "sp=reject is a policy too -- the subdomain tag does not slip past")

# The ceiling is the AND of two things. Aligning the mailer is not enough on its
# own, because SPF still has to authorise the IP the mailer sends from.
aligned_no_spf = with_records(spf=["v=spf1 include:_spf.google.com ~all"])
aligned_no_spf["intended"]["dmarc"] = "v=DMARC1; p=quarantine"
check(state(aligned_no_spf, "M5",
            php={"public/bug-submit.php": PHP_ALIGNED}) == cma.STATE_WRONG,
      "aligned -f but SPF does not cover the PHP box -> still WRONG (M2 coupling)")

both = with_records(spf=[GOOD_SPF])
both["intended"]["dmarc"] = "v=DMARC1; p=reject"
r = run_eval(both, php={"public/bug-submit.php": PHP_ALIGNED})
check(r["M5"].state == cma.STATE_PASS,
      "aligned -f AND SPF covering the box -> ceiling lifts, p=reject allowed")
check(r["_ceiling"] == "reject", "...and the printed ceiling says so")

# And the state the live repo is in: p=none is permitted while unaligned.
check(state(with_records(spf=[GOOD_SPF]), "M5") == cma.STATE_PASS,
      "p=none with an unaligned mailer -> PASS (the pin, not a failure)")
check(run_eval(with_records(spf=[GOOD_SPF]))["_ceiling"] == "none",
      "...and the ceiling is reported as p=none, printed on the green run")

# --------------------------------------------------------------------------
section("5. P2 -- the guard cannot return 0 having checked nothing")
# --------------------------------------------------------------------------

# The trap this repo has already been bitten by: check-platform-claims.py's
# scan() returned 0 BEFORE opening a single page. M5's equivalent is a repo with
# no PHP mailer in it -- nothing to constrain, so nothing to fail on.
check(state(base_spec(), "P2", php={"public/index.html": "<p>hi</p>"})
      == cma.STATE_WRONG,
      "declared mailer missing from disk -> P2 WRONG, not a quiet green")
check(state(base_spec(), "P2",
            php={"public/bug-submit.php": "<?php echo 'no mailer here';"})
      == cma.STATE_WRONG,
      "declared mailer on disk but the scanner finds no mail() -> P2 WRONG")
check(key(base_spec(), "P2", php={"public/index.html": "x"})
      == "pdoom1.com/P2/mailer-scan-broken",
      "...with a key of its own, so it cannot be hidden under an M-check waiver")
check(state(base_spec(), "P2") == cma.STATE_PASS,
      "the real shape -> P2 PASS")

# --------------------------------------------------------------------------
section("6. P1 -- the observation is a MIRROR, and a mirror rots")
# --------------------------------------------------------------------------

check(state(base_spec(), "P1", today=dt.date(2026, 10, 1)) == cma.STATE_WRONG,
      "observation 47 days old against a 30-day cap -> P1 WRONG")
check(key(base_spec(), "P1", today=dt.date(2026, 10, 1))
      == "pdoom1.com/P1/observation-stale",
      "...keyed as observation-stale")
check(state(base_spec(), "P1", today=dt.date(2026, 8, 1)) == cma.STATE_WRONG,
      "an observation dated in the FUTURE is a wrong clock, not evidence")
check(state(base_spec(), "P1", today=dt.date(2026, 9, 13)) == cma.STATE_PASS,
      "29 days old, cap 30 -> still PASS")

# --------------------------------------------------------------------------
section("7. The PHP scanner -- conservative, and fails CLOSED")
# --------------------------------------------------------------------------


def align(src, domain="pdoom1.com"):
    calls = cma.find_mail_calls(src, "t.php")
    if not calls:
        return None
    return calls[0].alignment(domain)[0]


check(cma.find_mail_calls("<?php // $x = mail($a,$b,$c,$d,$e);\n", "t") == [],
      "mail() inside a // comment is not a call")
check(cma.find_mail_calls("<?php /* mail($a,$b,$c,$d,$e); */\n", "t") == [],
      "mail() inside a /* */ comment is not a call")
check(cma.find_mail_calls("<?php $s = 'call mail($a,$b,$c,$d,$e) here';\n", "t") == [],
      "mail() inside a string literal is not a call")
check(cma.find_mail_calls("<?php wp_mail($a,$b,$c);\n", "t") == [],
      "wp_mail() is not mail()")
check(cma.find_mail_calls("<?php $m->mail($a,$b,$c);\n", "t") == [],
      "$obj->mail() is not mail()")
check(cma.find_mail_calls("<?php Mailer::mail($a,$b,$c);\n", "t") == [],
      "Klass::mail() is not mail()")
check(len(cma.find_mail_calls("<?php @mail($a,$b,$c,$d);\n", "t")) == 1,
      "@mail() IS mail() -- the error-suppressed form is the one in the repo")

check(align("<?php mail($a,$b,$c,$d);") is False,
      "four arguments -> unaligned")
check(align("<?php mail($a,$b,$c,$d,'-f team@pdoom1.com');") is True,
      "a literal -f on the domain -> aligned")
check(align("<?php const F='team@pdoom1.com'; mail($a,$b,$c,$d,'-f ' . F);") is True,
      "'-f ' . CONST resolves through the constant table -> aligned")
check(align("<?php mail($a,$b,$c,$d,$params);") is False,
      "a VARIABLE 5th parameter is unresolvable -> unaligned (fail closed)")
check(align("<?php mail($a,$b,$c,$d,build_params());") is False,
      "a function call is unresolvable -> unaligned (fail closed)")
check(align("<?php mail($a,$b,$c,$d,'-f bounce@example.com');") is False,
      "an -f on ANOTHER domain -> unaligned; alignment is a domain match")
check(align("<?php mail($a,$b,$c,$d,'-O DeliveryMode=b');") is False,
      "a 5th parameter that sets no -f at all -> unaligned")
check(align("<?php mail($a,$b,$c,$d,'-f nobody');") is False,
      "an -f with no @domain -> unaligned")
check(align("<?php mail('a@b.c, d@e.f', 'Subj, with comma', $b, $h);") is False,
      "commas INSIDE string arguments do not fake a 5th parameter")

# --------------------------------------------------------------------------
section("8. The CLI -- exit codes, refusals, and the acknowledgement clock")
# --------------------------------------------------------------------------

LEDGER_OK = {
    "schema": "pdoom-acknowledgements/v1",
    "policy": {"warn_within_days": 14, "source": "fixture"},
    "checks": {"check-mail-auth": "fixture"},
    "acknowledgements": [],
}


def ack(key_, review_by="2026-09-30"):
    return {
        "check": "check-mail-auth", "key": key_, "what": "fixture",
        "why": "fixture", "accepted_by": "fixture",
        "accepted_on": "2026-08-15", "review_by": review_by,
        "on_expiry": "fixture", "source": "fixture",
    }


def run_cli(spec, ledger, php=None, extra=(), as_of="2026-08-15"):
    php = {"public/bug-submit.php": PHP_UNALIGNED} if php is None else php
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for rel, body in php.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        sp = root / "spec.json"
        lp = root / "ledger.json"
        sp.write_text(json.dumps(spec), encoding="utf-8") if isinstance(spec, dict) \
            else sp.write_text(spec, encoding="utf-8")
        lp.write_text(json.dumps(ledger), encoding="utf-8") if isinstance(ledger, dict) \
            else lp.write_text(ledger, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--spec", str(sp), "--ledger", str(lp),
             "--repo-root", str(root), "--as-of", as_of, *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc


ALL_FOUR = ["pdoom1.com/M1/absent", "pdoom1.com/M2/unevaluable-no-spf",
            "pdoom1.com/M3/absent", "pdoom1.com/M4/absent"]

p = run_cli(base_spec(), LEDGER_OK)
check(p.returncode == 1, "the live world with an EMPTY ledger -> exit 1 (red)")
check("pdoom1.com/M1/absent" in p.stdout, "...naming the key to acknowledge")

led = copy.deepcopy(LEDGER_OK)
led["acknowledgements"] = [ack(k) for k in ALL_FOUR]
p = run_cli(base_spec(), led)
check(p.returncode == 0, "all four acknowledged and unexpired -> exit 0 (green)")
check("ACKNOWLEDGED FINDINGS (4)" in p.stdout,
      "...and the green run PRINTS the four findings; green carries a number")

p = run_cli(base_spec(), led, as_of="2026-10-01")
check(p.returncode == 1, "past review_by -> exit 1")
check("EXPIRED ACCEPTANCE" in p.stdout,
      "...red on the EXPIRED ACCEPTANCE, which a human can close by deciding")

# An acknowledgement of "absent" must not forgive "present but wrong".
led_absent_only = copy.deepcopy(LEDGER_OK)
led_absent_only["acknowledgements"] = [ack(k) for k in ALL_FOUR]
wrong_spf = with_records(spf=[GOOD_SPF, "v=spf1 -all"])
p = run_cli(wrong_spf, led_absent_only)
check(p.returncode == 1,
      "SPF becomes present-but-broken -> the 'absent' acceptance does NOT cover it")
check("multiple-records" in p.stdout, "...the new key is reported by name")
check("STALE" in p.stdout,
      "...and the now-unfiring acceptance is reported STALE, not silently kept")

p = run_cli("{not json", LEDGER_OK)
check(p.returncode == 2, "unparseable spec -> exit 2 REFUSED, never 0")
p = run_cli(base_spec(), "{not json")
check(p.returncode == 2, "unparseable ledger -> exit 2 REFUSED, never 0")

no_spf_key = base_spec()
del no_spf_key["observation"]["records"]["spf"]
p = run_cli(no_spf_key, LEDGER_OK)
check(p.returncode == 2,
      "a MISSING records.spf key -> exit 2: [] and null are different facts and "
      "the checker refuses to guess which was meant")

bad_ledger = copy.deepcopy(LEDGER_OK)
bad_ledger["acknowledgements"] = [dict(ack("pdoom1.com/M1/absent"), why="")]
p = run_cli(base_spec(), bad_ledger)
check(p.returncode == 2,
      "an acknowledgement with a blank `why` -> the WHOLE ledger is refused")

p = run_cli(base_spec(), led, extra=("--json",))
check(p.returncode == 0, "--json still sets the exit code")
try:
    doc = json.loads(p.stdout)
    check(doc["ceiling"] == "none", "--json reports the ceiling")
    check(sorted(doc["acknowledged"]) == sorted(ALL_FOUR),
          "--json lists what it is tolerating")
    check(doc["mail_calls"][0]["aligned"] is False,
          "--json reports the mailer as unaligned")
except (ValueError, KeyError, IndexError) as exc:
    check(False, f"--json output did not parse as expected: {exc}")

# --------------------------------------------------------------------------
section("9. The LIVE spec still describes the real repo")
# --------------------------------------------------------------------------

# A renamed or deleted mailer would shrink M5's coverage to nothing while every
# check stayed green. P2 catches that at runtime; this catches it here, before
# the guard runs, which is the order content-honesty.yml already uses.
try:
    live = cma.load_spec()
    check(True, "data/mail-auth.json loads and validates")
    missing = [m for m in live["php_mailers_expected"] if not (ROOT / m).exists()]
    check(not missing, f"every declared PHP mailer exists on disk (missing: {missing})")
    check(any(s["runs_php"] for s in live["senders"]),
          "at least one sender is marked runs_php -- otherwise M5's ceiling has "
          "no SPF requirement to couple to and M2 could pass vacuously")
    files, calls = cma.scan_mailers(ROOT)
    check(len(calls) >= 1, f"the scanner finds a real mail() call in the repo "
                           f"({files} PHP files, {len(calls)} calls)")
    # 2026-08-17: this asserted the OPPOSITE -- "every real mailer is currently
    # UNALIGNED" -- and it went red the moment bug-submit.php gained its 5th
    # parameter. That red was the assertion doing its job: it is a state snapshot
    # whose whole purpose is to fail when the state moves, so that a human has to
    # come and say which way it moved and why. Recorded here rather than deleted,
    # because the direction matters.
    #
    # What flipped it, in order: SPF and DMARC were published for pdoom1.com on
    # 2026-08-17; a real message through the live form then came back
    # `spf=pass ... dmarc=fail`, proving the alignment gap at a real receiver; the
    # mailer gained `-f team@pdoom1.com`. Both mailers are now aligned and the
    # ceiling stands at p=reject. The regression this now catches is somebody
    # dropping the 5th parameter back out -- which would silently return the
    # site's own feedback mail to a Gmail warning banner.
    unaligned = [f"{c.path}:{c.line}" for c in calls
                 if not c.alignment(live["domain"])[0]]
    check(not unaligned,
          f"every real mailer passes an aligned envelope sender (unaligned: "
          f"{unaligned or 'none'}) -- if this flips, the DMARC ceiling drops back "
          f"to p=none and this assertion is the place that records it did")
except cma.SpecError as exc:
    check(False, f"the live spec does not load: {exc}")

# --------------------------------------------------------------------------
print()
if failures:
    print(f"FAIL: {len(failures)} assertion(s)")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
print("OK: every mail-auth check was forced into its failing state and observed.")
sys.exit(0)
