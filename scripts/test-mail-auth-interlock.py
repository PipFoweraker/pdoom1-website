#!/usr/bin/env python
"""M5 forced red -- an INDEPENDENT second reading of the mail-auth interlock.

Why this file exists, and why it is not `scripts/test-check-mail-auth.py`:

    `.github/workflows/feedback-intake.yml` runs both. The guard
    (`scripts/check-mail-auth.py`) and its own test were written by one author
    from one reading of `docs/decisions/FEEDBACK_INTAKE_CONTRACT.md` section 5.
    If that reading is wrong, the guard and its test are wrong TOGETHER and both
    stay green -- a test can only be as right as its author's reading of the
    spec. This file is the second opinion. Every expectation below is derived
    from the CONTRACT prose, quoted inline next to the assertion it produced,
    and NOT from the guard's source.

    Deliberate constraint on this file: it observes only the guard's PUBLIC
    surface -- the process exit code, and the `check`/`state` fields of
    `--json`. It asserts no internal constant, no finding-key string, and no
    state name beyond "PASS means the check holds". Where the contract is
    ambiguous, the assertion states what the CONTRACT says; a disagreement with
    the guard is a finding to report, not a number to tune.

What section 5 requires, restated:

    | M1 | SPF record exists and is syntactically one record |
    | M2 | SPF covers both sending IPs |
    | M3 | DMARC exists |
    | M4 | DKIM selector `google._domainkey` resolves |
    | M5 | `p` > `none` ONLY IF every PHP mailer passes an aligned envelope
           sender |

    "M5 is the load-bearing one: it reads the PHP source for `mail()`'s 5th
    parameter and refuses a DMARC tightening while any mailer would fail
    alignment. Without this interlock, raising the policy silently kills the
    intake form -- the precise outcome the binding directive forbids."

    Binding directive (contract preamble): "If I ever lose a message silently,
    that's now the worst thing my website can do." Tradeoffs resolve toward
    "admitting a failure over absorbing it" -- which is where every fail-closed
    expectation below comes from.

Run:  python scripts/test-mail-auth-interlock.py
No network, no secrets, no `php` binary. Every fixture is built in a temp dir;
nothing committed is read for its content or written to.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

GUARD = Path(__file__).resolve().parent / "check-mail-auth.py"

# A fixed date so the observation clock and any acknowledgement expiry are
# forced rather than waited for. --as-of exists for exactly this.
AS_OF = "2026-08-17"
DOMAIN = "pdoom1.com"

# Contract section 5, "Records to publish". These are the two senders it names:
# "Two senders must be covered -- Google Workspace, and DreamHost shared ...
# which falls inside netblocks.dreamhost.com". DreamHost is the one that runs
# the PHP.
SPF_GOOGLE = "include:_spf.google.com"
SPF_DREAMHOST = "include:netblocks.dreamhost.com"

PASSES = []
FAILS = []
NOTES = []


# --------------------------------------------------------------------------
# fixtures -- everything below is synthesised, never copied from a committed
# file, so a test run cannot depend on (or disturb) real repo state.
# --------------------------------------------------------------------------

def spf_record(cover_dreamhost=True):
    parts = ["v=spf1", SPF_GOOGLE]
    if cover_dreamhost:
        parts.append(SPF_DREAMHOST)
    parts.append("~all")
    return " ".join(parts)


def make_spec(intended_p, published_p, cover_dreamhost=True, dkim=True,
              mailers=("public/mailer.php",)):
    """A mail-auth spec in the published schema, built from scratch.

    `intended_p` is the policy this repo INTENDS to publish; `published_p` is
    the policy DNS was last observed to actually carry. Section 5 distinguishes
    them: the "Records to publish" block is intent, and the measurement note
    ("Measured 2026-08-15 against ns1.dreamhost.com ... none of the three
    exist") is observation. Either can sit above the ceiling.
    """
    spf = spf_record(cover_dreamhost)
    return {
        "note": "SYNTHETIC fixture built by scripts/test-mail-auth-interlock.py. Not real DNS.",
        "schema": "pdoom-mail-auth/v1",
        "domain": DOMAIN,
        "max_observation_age_days": 30,
        "max_observation_age_source": "Fixture value; mirrors the real spec so the freshness check is not what fails.",
        "senders": [
            {
                "id": "google-workspace",
                "what": "Google Workspace (fixture).",
                "ip": None,
                "spf_mechanism": SPF_GOOGLE,
                "runs_php": False,
                "source": "Fixture.",
            },
            {
                "id": "dreamhost-shared",
                "what": "DreamHost shared hosting -- the sender that runs the PHP (fixture).",
                "ip": "208.113.156.243",
                "spf_mechanism": SPF_DREAMHOST,
                "covering_netblock": "208.113.128.0/17",
                "runs_php": True,
                "source": "Fixture.",
            },
        ],
        "intended": {
            "spf": spf,
            "dmarc": "v=DMARC1; p=%s; rua=mailto:team@%s" % (intended_p, DOMAIN),
            "dkim_selector": "google._domainkey",
            "source": "Fixture derived from contract section 5 'Records to publish'.",
        },
        "php_mailers_expected": list(mailers),
        "php_mailers_expected_source": "Fixture; the anti-vacuous control for M5.",
        "observation": {
            "observed_on": AS_OF,
            "resolver": "fixture (no network)",
            "method": "Synthesised by the test; no resolver was contacted.",
            "observed_by": "scripts/test-mail-auth-interlock.py",
            "records": {
                "spf": [spf],
                "dmarc": ["v=DMARC1; p=%s; rua=mailto:team@%s" % (published_p, DOMAIN)],
                "dkim": {
                    "google._domainkey": (
                        ["v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AFIXTURE"]
                        if dkim else []
                    )
                },
            },
            "mx": ["SMTP.GOOGLE.com"],
            "source": "Fixture.",
        },
    }


EMPTY_LEDGER = {
    "note": "SYNTHETIC empty acknowledgement ledger built by scripts/test-mail-auth-interlock.py.",
    "schema": "pdoom-acknowledgements/v1",
    "how_to_add_an_entry": "Not used; this fixture waives nothing on purpose, so every finding must show as a finding.",
    "policy": {"warn_within_days": 14, "source": "Fixture."},
    "checks": {
        "check-mail-auth": "scripts/check-mail-auth.py (fixture ledger, waives nothing).",
    },
    "acknowledgements": [],
}


# The 5th parameter of mail() is the envelope sender. Section 5: "it reads the
# PHP source for mail()'s 5th parameter".
MAILER_UNALIGNED = """<?php
// No 5th parameter at all -- the state section 5 describes for bug-submit.php.
mail($to, $subject, $body, $headers);
"""

MAILER_ALIGNED = """<?php
mail($to, $subject, $body, $headers, "-f team@%s");
""" % DOMAIN

MAILER_FOREIGN = """<?php
// Syntactically a 5th parameter, but the domain is not ours -- so it is not
// "aligned" in the DMARC sense the contract is using.
mail($to, $subject, $body, $headers, "-f noreply@example.net");
"""

MAILER_VARIABLE = """<?php
$envelope = getenv('PDOOM_ENVELOPE');
mail($to, $subject, $body, $headers, $envelope);
"""

MAILER_CONCAT = """<?php
mail($to, $subject, $body, $headers, "-f " . $sender_local . "@" . $sender_domain);
"""

MAILER_CALL = """<?php
mail($to, $subject, $body, $headers, envelope_for($to));
"""


def run_guard(spec, php_sources):
    """Invoke the guard against a throwaway tree. Returns (exit_code, verdict).

    php_sources: {repo-relative path: file body}. Observation surface is the
    exit code plus --json; nothing else is inspected.
    """
    tmp = Path(tempfile.mkdtemp(prefix="mailauth-interlock-"))
    try:
        repo = tmp / "repo"
        repo.mkdir()
        for rel, body in php_sources.items():
            dest = repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with io.open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)

        spec_path = tmp / "spec.json"
        with io.open(spec_path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh, indent=2)
        ledger_path = tmp / "ledger.json"
        with io.open(ledger_path, "w", encoding="utf-8") as fh:
            json.dump(EMPTY_LEDGER, fh, indent=2)

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, str(GUARD), "--check", "--json",
             "--as-of", AS_OF,
             "--spec", str(spec_path),
             "--ledger", str(ledger_path),
             "--repo-root", str(repo)],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        try:
            verdict = json.loads(proc.stdout)
        except ValueError:
            verdict = {"_unparseable_stdout": proc.stdout, "_stderr": proc.stderr}
        return proc.returncode, verdict
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# assertion helpers
# --------------------------------------------------------------------------

def check(name, ok, expectation, observed, contract):
    line = "PASS" if ok else "FAIL"
    print("[%s] %s" % (line, name))
    print("       contract : %s" % contract)
    print("       expected : %s" % expectation)
    print("       observed : %s" % observed)
    (PASSES if ok else FAILS).append(name)


def state_of(verdict, check_id):
    for row in verdict.get("results", []):
        if row.get("check") == check_id:
            return row.get("state")
    return None


def describe(code, verdict, check_ids=("M2", "M5")):
    bits = ["exit=%s" % code]
    for cid in check_ids:
        bits.append("%s=%s" % (cid, state_of(verdict, cid)))
    if "_unparseable_stdout" in verdict:
        bits.append("stdout was not JSON: %r" % verdict["_unparseable_stdout"][:200])
    return ", ".join(bits)


def build_fails(code):
    """Section 5: the guard 'asserts, and fails the build on' each row.

    Exit 0 is the only 'the build passed' code, so anything else is a refusal.
    """
    return code != 0


# --------------------------------------------------------------------------
# the assertions
# --------------------------------------------------------------------------

def main():
    print("test-mail-auth-interlock -- M5 read independently from")
    print("docs/decisions/FEEDBACK_INTAKE_CONTRACT.md section 5")
    print("guard under test: %s" % GUARD)
    print("")

    if not GUARD.exists():
        print("[FAIL] the guard named by the contract does not exist: %s" % GUARD)
        print("SUMMARY: 0 passed, 1 failed, 1 assertion attempted")
        return 1

    # -- A0: the fixture is a positive control -------------------------------
    # Section 11.1's rule, applied to this test itself: "a happy-path
    # submission must produce a sink line, or F1/F5 report unobservable-FAIL
    # rather than passing on an absence." If my healthy fixture does not go
    # green, every red below could be an artefact of the fixture and would
    # prove nothing about M5.
    code, verdict = run_guard(
        make_spec("none", "none"),
        {"public/mailer.php": MAILER_UNALIGNED},
    )
    check(
        "A0 positive control: a healthy fixture at p=none is green, so a red below means something",
        not build_fails(code),
        "exit 0",
        describe(code, verdict, ("M1", "M2", "M3", "M4", "M5")),
        "s5 records-to-publish: SPF+DMARC(p=none)+DKIM all present, both senders covered",
    )

    # -- A1: THE FORCED RED, the reason this file exists ---------------------
    code, verdict = run_guard(
        make_spec("quarantine", "none"),
        {"public/mailer.php": MAILER_UNALIGNED},
    )
    check(
        "A1 unaligned mailer (no 5th param) + intended p=quarantine -> build FAILS",
        build_fails(code),
        "exit != 0",
        describe(code, verdict),
        "s5 M5: 'p > none ONLY IF every PHP mailer passes an aligned envelope sender'; "
        "'refuses a DMARC tightening while any mailer would fail alignment'",
    )
    check(
        "A1b ...and M5 itself is the check that does not hold (the refusal is attributable)",
        state_of(verdict, "M5") not in (None, "PASS"),
        "M5 is not PASS",
        describe(code, verdict, ("M5",)),
        "s5 M5 is the row whose condition is violated; a build that failed for some other "
        "reason would leave the interlock unproven",
    )

    # A1c: p=reject is further above none than p=quarantine, so if quarantine
    # is refused, reject must be too. Section 5 says "> none", not "== reject".
    code, verdict = run_guard(
        make_spec("reject", "none"),
        {"public/mailer.php": MAILER_UNALIGNED},
    )
    check(
        "A1c unaligned mailer + intended p=reject -> build FAILS (the rule is 'p > none', not 'p == reject')",
        build_fails(code) and state_of(verdict, "M5") not in (None, "PASS"),
        "exit != 0 and M5 not PASS",
        describe(code, verdict, ("M5",)),
        "s5 M5: 'p > none ONLY IF ...'",
    )

    # A1d: the state that actually kills mail is the PUBLISHED one. A1/A1c
    # catch the intent before it ships; this catches it after.
    code, verdict = run_guard(
        make_spec("quarantine", "quarantine"),
        {"public/mailer.php": MAILER_UNALIGNED},
    )
    check(
        "A1d unaligned mailer with p=quarantine ALREADY published in DNS -> build FAILS",
        build_fails(code) and state_of(verdict, "M5") not in (None, "PASS"),
        "exit != 0 and M5 not PASS",
        describe(code, verdict, ("M5",)),
        "s5: 'raising the policy silently kills the intake form -- the precise outcome the "
        "binding directive forbids'; a policy already live is that outcome, not a risk of it",
    )

    # -- A2: the constraint binds only ABOVE none ----------------------------
    code, verdict = run_guard(
        make_spec("none", "none"),
        {"public/mailer.php": MAILER_UNALIGNED},
    )
    check(
        "A2 same unaligned mailer at p=none -> M5 does NOT fail (today's state is legal)",
        state_of(verdict, "M5") == "PASS" and not build_fails(code),
        "M5 PASS and exit 0",
        describe(code, verdict, ("M5",)),
        "s5: 'bug-submit.php:178 currently passes no 5th param, so today M5 pins the policy "
        "at p=none' -- pinned, not failed",
    )

    # -- A3: satisfying the ONLY IF is a permission --------------------------
    code, verdict = run_guard(
        make_spec("quarantine", "quarantine", cover_dreamhost=True),
        {"public/mailer.php": MAILER_ALIGNED},
    )
    check(
        "A3 aligned mailer + SPF covering the PHP sender + p=quarantine -> permitted",
        not build_fails(code),
        "exit 0",
        describe(code, verdict, ("M1", "M2", "M3", "M4", "M5")),
        "s5 M5 is a conditional permission: once every mailer passes an aligned envelope "
        "sender and both senders are covered, the tightening is allowed",
    )

    # A3b: the anti-confound control for A1. A1 raises the INTENDED policy
    # while DNS still says p=none; if the guard red-flagged any intent/DNS gap
    # on its own, A1's red would prove nothing about alignment. This fixture
    # holds that gap fixed and flips only the alignment, so the two reds in A1
    # and A1c are attributable to the mailer and nothing else.
    code, verdict = run_guard(
        make_spec("quarantine", "none"),
        {"public/mailer.php": MAILER_ALIGNED},
    )
    check(
        "A3b control: aligned mailer, intent raised to quarantine, DNS still at none -> permitted",
        not build_fails(code),
        "exit 0",
        describe(code, verdict, ("M5",)),
        "s5 M5 constrains the POLICY against the alignment ceiling; an intent that has not "
        "yet been published is not itself a violation",
    )

    # -- A4: alignment alone is not sufficient; M2 is coupled in -------------
    # DMARC passes on (SPF pass AND SPF alignment) or (DKIM pass AND DKIM
    # alignment). An aligned envelope sender supplies only the alignment half;
    # SPF must still authorise the IP, and section 5 is explicit that "Two
    # senders must be covered". Raising p while the PHP sender is unauthorised
    # is exactly "raising the policy silently kills the intake form".
    code, verdict = run_guard(
        make_spec("quarantine", "none", cover_dreamhost=False),
        {"public/mailer.php": MAILER_ALIGNED},
    )
    check(
        "A4 aligned mailer but SPF does NOT cover the PHP-running sender + p=quarantine -> build FAILS",
        build_fails(code),
        "exit != 0",
        describe(code, verdict),
        "s5 M2 'SPF covers both sending IPs' + s5 rationale 'raising the policy silently "
        "kills the intake form'",
    )
    a4b_ok = state_of(verdict, "M5") not in (None, "PASS")
    check(
        "A4b ...and the verdict does not present the tightening as PERMITTED while that sender is unauthorised",
        a4b_ok,
        "M5 is not PASS",
        describe(code, verdict, ("M2", "M5")),
        "s5 M5's stated purpose is that the policy may not rise while mail would fail; a "
        "clean M5 PASS here reads as 'the tightening is fine' when it is not",
    )
    if not a4b_ok:
        NOTES.append(
            "A4b: the guard reports M5 as PASS when SPF does not cover the PHP-running "
            "sender. The build still fails (M2 catches it), so no tightening can ship "
            "unnoticed -- but M5 alone is a NARROWER reading of the interlock than section "
            "5's prose supports: M5 answers 'is the envelope sender aligned?' and not 'would "
            "mail survive this policy?'. Whether that split is right is a contract question, "
            "not a bug this test may tune away."
        )

    # -- A5: an unresolvable 5th parameter must count as UNALIGNED ----------
    # The contract gives no rule for a 5th parameter that is not a literal, so
    # the binding directive decides: "duplicate over loss", "admitting a
    # failure over absorbing it". A false 'aligned' permits a tightening that
    # silently kills the form -- the one outcome forbidden outright. Fail
    # closed.
    for label, body in (
        ("a bare variable", MAILER_VARIABLE),
        ("a concatenation of unknowns", MAILER_CONCAT),
        ("a function call", MAILER_CALL),
    ):
        code, verdict = run_guard(
            make_spec("quarantine", "none"),
            {"public/mailer.php": body},
        )
        check(
            "A5 5th param the parser cannot resolve to a literal (%s) -> counts as UNALIGNED, build FAILS" % label,
            build_fails(code) and state_of(verdict, "M5") not in (None, "PASS"),
            "exit != 0 and M5 not PASS",
            describe(code, verdict, ("M5",)),
            "binding directive: 'admitting a failure over absorbing it'; a guessed 'aligned' "
            "buys a silent loss, which the directive forbids outright",
        )

    # -- A6: a PUBLISHED policy above the ceiling, not merely an intended one -
    # Section 5's observation is of DNS, and DNS is edited in the DreamHost
    # panel -- outside this repo entirely. A guard that read only its own
    # intent would be blind to the exact edit that does the damage.
    code, verdict = run_guard(
        make_spec("none", "reject"),
        {"public/mailer.php": MAILER_UNALIGNED},
    )
    check(
        "A6 intended p=none but DNS is OBSERVED at p=reject with an unaligned mailer -> build FAILS",
        build_fails(code) and state_of(verdict, "M5") not in (None, "PASS"),
        "exit != 0 and M5 not PASS",
        describe(code, verdict, ("M5",)),
        "s5 'Records to publish (DreamHost panel ...)' + the measured-observation note: the "
        "policy that matters is the one in DNS, and nothing in this repo edits it",
    )

    # -- A7: 'aligned' is relative to THIS domain ---------------------------
    code, verdict = run_guard(
        make_spec("quarantine", "none"),
        {"public/mailer.php": MAILER_FOREIGN},
    )
    check(
        "A7 5th param present but for a foreign domain -> not aligned, build FAILS",
        build_fails(code) and state_of(verdict, "M5") not in (None, "PASS"),
        "exit != 0 and M5 not PASS",
        describe(code, verdict, ("M5",)),
        "s5 M5 says 'an ALIGNED envelope sender'; DMARC alignment is relative to the domain "
        "the policy belongs to, which section 5 fixes as pdoom1.com",
    )

    # -- A8: 'EVERY PHP mailer' is a universal quantifier -------------------
    # A scanner that stops at the first aligned call, or that only reads the
    # first file it finds, passes this fixture wrongly.
    code, verdict = run_guard(
        make_spec("quarantine", "none", mailers=("public/mailer.php", "public/second.php")),
        {"public/mailer.php": MAILER_ALIGNED, "public/second.php": MAILER_UNALIGNED},
    )
    check(
        "A8 one aligned mailer AND one unaligned mailer at p=quarantine -> build FAILS (the quantifier is EVERY)",
        build_fails(code) and state_of(verdict, "M5") not in (None, "PASS"),
        "exit != 0 and M5 not PASS",
        describe(code, verdict, ("M5",)),
        "s5 M5: 'ONLY IF EVERY PHP mailer passes an aligned envelope sender'",
    )

    # A8b: the same two files with BOTH aligned must be permitted, or A8 would
    # be passing for the wrong reason (any two-file tree failing).
    code, verdict = run_guard(
        make_spec("quarantine", "quarantine", mailers=("public/mailer.php", "public/second.php")),
        {"public/mailer.php": MAILER_ALIGNED, "public/second.php": MAILER_ALIGNED},
    )
    check(
        "A8b control: the same two files, both aligned, at p=quarantine -> permitted",
        not build_fails(code),
        "exit 0",
        describe(code, verdict, ("M5",)),
        "s5 M5's condition is satisfied when every mailer is aligned; without this control "
        "A8 could be passing merely because two files are present",
    )

    # -- A9: M4 is its own fail-the-build row -------------------------------
    # Also proves the DKIM leg of every fixture above is load-bearing rather
    # than decorative: with DKIM absent this fixture goes red, so its presence
    # elsewhere is what kept M4 out of the way.
    code, verdict = run_guard(
        make_spec("none", "none", dkim=False),
        {"public/mailer.php": MAILER_UNALIGNED},
    )
    check(
        "A9 DKIM selector does not resolve, nothing acknowledged -> build FAILS",
        build_fails(code) and state_of(verdict, "M4") not in (None, "PASS"),
        "exit != 0 and M4 not PASS",
        describe(code, verdict, ("M4",)),
        "s5 M4: 'DKIM selector google._domainkey resolves' is listed among the checks the "
        "guard 'asserts, and fails the build on'",
    )

    # -- A10: M5 must not pass VACUOUSLY ------------------------------------
    # Section 5 says M5 "reads the PHP source". If it reads nothing -- the
    # declared mailer is missing from the tree -- then "every PHP mailer is
    # aligned" is vacuously true and the tightening would be waved through on
    # an ABSENCE. Section 11.1 rules on this exact shape: a positive control is
    # required, "or F1/F5 report unobservable-FAIL rather than passing on an
    # absence", and CLAUDE.md names it the count_emails() trap.
    code, verdict = run_guard(
        make_spec("quarantine", "none"),
        {"public/not-a-mailer.txt": "no php here\n"},
    )
    check(
        "A10 the declared mailer is absent from the tree at p=quarantine -> build FAILS, never a vacuous permit",
        build_fails(code),
        "exit != 0",
        describe(code, verdict, ("M5",)),
        "s5 'it reads the PHP source for mail()'s 5th parameter' + s11.1 'rather than "
        "passing on an absence'",
    )
    if state_of(verdict, "M5") == "PASS":
        NOTES.append(
            "A10: with no mailer on disk the guard's M5 row reads PASS -- 'every PHP mailer "
            "is aligned' is vacuously true of an empty set. The build still fails, so no "
            "tightening can ship on an absence, but the refusal comes from the scan-integrity "
            "check and NOT from M5. Anyone reading the M5 row alone would draw the wrong "
            "conclusion; anyone reading the exit code would not."
        )

    # -- A11: M1 is a fail-the-build row too --------------------------------
    # Two TXT records both beginning v=spf1 is a permerror at the receiver, and
    # a permerror is not an SPF pass, so it collapses the same ceiling M5
    # depends on.
    spec = make_spec("none", "none")
    spec["observation"]["records"]["spf"] = [
        spf_record(True),
        "v=spf1 include:example.net ~all",
    ]
    code, verdict = run_guard(spec, {"public/mailer.php": MAILER_UNALIGNED})
    check(
        "A11 two SPF records published -> build FAILS",
        build_fails(code) and state_of(verdict, "M1") not in (None, "PASS"),
        "exit != 0 and M1 not PASS",
        describe(code, verdict, ("M1",)),
        "s5 M1: 'SPF record exists and is syntactically ONE record'",
    )

    # -- report --------------------------------------------------------------
    total = len(PASSES) + len(FAILS)
    print("")
    for note in NOTES:
        print("NOTE: %s" % note)
    if NOTES:
        print("")
    print("SUMMARY: %d passed, %d failed, %d assertions attempted "
          "(independent M5 reading, contract section 5)" % (len(PASSES), len(FAILS), total))
    if FAILS:
        print("FAILED: %s" % "; ".join(FAILS))
        print("A failure here is a DISAGREEMENT between the contract and the guard. "
              "Adjudicate it against section 5 -- do not edit this test until it matches.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
