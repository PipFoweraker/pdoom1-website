#!/usr/bin/env python
"""Forced-failure tests for scripts/verify-deployment.py's three verdicts.

    python scripts/test-verify-deployment.py     (exit 0 = pass)

WHY THIS FILE EXISTS
--------------------
D3 of pdoom1-website#384. verify-deployment.py printed **DEPLOYMENT APPROVED**
over freshness it could not establish: the version-data check logged a PASS with
the word WARNING in its message, warnings never reached the verdict, and
`checks_failed == 0` was the whole decision. With two outcomes, "I could not
tell" had nowhere to go except into the approving one.

It matters more here than in a lint, because this script WRITES
`public/data/deployment-verification.json` -- the file `/monitoring/` renders.
It manufactures the evidence the card displays.

A deploy gate that cannot tell must not approve. That is now a third verdict
with its own exit code, and this file forces every state that should reach it.

WHAT IS DELIBERATELY NOT ASSERTED
---------------------------------
No check here pins a file count, a version or a date. Every case drives the
verdict function or the freshness check directly against a temp tree, so nothing
depends on the real repo being in any particular state, and nothing writes to
the real public/.
"""

import sys
import os
import json
import shutil
import tempfile
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "verify-deployment.py"

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


spec = importlib.util.spec_from_file_location("verify_deployment", SCRIPT)
vd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vd)


def freshness_verdict(last_updated, missing_file=False):
    """Run ONLY the version-data check against a temp tree, and report the verdict.

    chdir is how the script itself resolves 'public/data/version.json', so the
    test drives it the same way main() does rather than reaching past it.
    """
    tmp = Path(tempfile.mkdtemp())
    cwd = os.getcwd()
    try:
        (tmp / "public" / "data").mkdir(parents=True)
        if not missing_file:
            payload = {
                "latest_release": {"version": "v1", "name": "n",
                                   "published_at": "p", "html_url": "u"},
                "repository_stats": {},
                "game_stats": {},
            }
            if last_updated is not _ABSENT:
                payload["last_updated"] = last_updated
            (tmp / "public" / "data" / "version.json").write_text(
                json.dumps(payload), encoding="utf-8")
        os.chdir(tmp)
        v = vd.DeploymentVerifier()
        v.verify_version_data_fresh()
        return v
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


_ABSENT = object()

print("=" * 62)
print("D3 -- a deploy gate that cannot tell must not approve")
print("=" * 62)

# ------------------------------------------------------------------ verdicts
print("\n1. The verdict function, enumerated")


def verdict_for(failed=0, unverifiable=()):
    v = vd.DeploymentVerifier()
    v.checks_failed = failed
    v.unverifiable = list(unverifiable)
    return v.verdict()


check(verdict_for() == vd.VERDICT_APPROVED, "nothing failed, nothing unknown -> APPROVED")
check(verdict_for(failed=1) == vd.VERDICT_REFUSED, "a failure -> REFUSED")
check(verdict_for(unverifiable=["x"]) == vd.VERDICT_CANNOT_VERIFY,
      "an unknown ALONE -> CANNOT VERIFY, never APPROVED")
check(verdict_for(failed=1, unverifiable=["x"]) == vd.VERDICT_REFUSED,
      "a real failure outranks an unknown -- say what is broken, do not hide it behind 'could not tell'")

check(vd.EXIT_BY_VERDICT[vd.VERDICT_APPROVED] == 0, "APPROVED exits 0")
check(vd.EXIT_BY_VERDICT[vd.VERDICT_REFUSED] == 1, "REFUSED exits 1")
check(vd.EXIT_BY_VERDICT[vd.VERDICT_CANNOT_VERIFY] == 2,
      "CANNOT VERIFY exits 2 -- distinct from a failure, so a caller can tell them apart")
check(all(code != 0 for verdict, code in vd.EXIT_BY_VERDICT.items()
          if verdict != vd.VERDICT_APPROVED),
      "APPROVED is the ONLY verdict that exits 0")
check(set(vd.EXIT_BY_VERDICT) == {vd.VERDICT_APPROVED, vd.VERDICT_REFUSED,
                                  vd.VERDICT_CANNOT_VERIFY},
      "every declared verdict has an exit code, so a fourth cannot default to 0")

# --------------------------------------------------------------- freshness
print("\n2. Freshness states, forced")

stale = freshness_verdict("2024-01-01T00:00:00")
check(stale.verdict() == vd.VERDICT_REFUSED,
      "a 2024 timestamp REFUSES -- the input that used to print DEPLOYMENT APPROVED")
check(stale.checks_failed > 0, "...as a real failure, because the age IS established")
check(not stale.unverifiable, "...and not as an unknown, because nothing was unknown")

for label, stamp in [("null", None), ("empty", ""),
                     ("unparseable", "not-a-timestamp")]:
    v = freshness_verdict(stamp)
    check(v.verdict() == vd.VERDICT_CANNOT_VERIFY,
          f"a {label} last_updated -> CANNOT VERIFY")
    check(v.checks_failed == 0,
          f"...and a {label} last_updated is not reported as a failure either")

# An ABSENT key is different from a present-but-useless one, and correctly so:
# last_updated is a declared required field, so its absence is a STRUCTURAL
# failure the script establishes, not something it could not determine. Pinned
# here so the distinction is deliberate rather than accidental.
absent = freshness_verdict(_ABSENT)
check(absent.verdict() == vd.VERDICT_REFUSED,
      "an ABSENT last_updated -> REFUSED (a missing required field is established, not unknown)")
check(absent.verdict() != vd.VERDICT_APPROVED,
      "...and above all, never APPROVED")

future = freshness_verdict((datetime.now() + timedelta(hours=48)).isoformat())
check(future.verdict() == vd.VERDICT_CANNOT_VERIFY,
      "a FUTURE timestamp -> CANNOT VERIFY, not the freshest possible reading")

# A timezone-aware stamp must not blow up into a generic error. version.json is
# written by more than one tool over the years and the format has moved.
aware = freshness_verdict("2024-01-01T00:00:00+00:00")
check(aware.verdict() == vd.VERDICT_REFUSED,
      "a tz-aware stale stamp is still read as stale, not as an unknown")

# NEGATIVE CONTROL. Without this, every assertion above is consistent with a
# checker that never approves -- which looks identical from outside and would be
# a worse bug than the one being fixed.
print("\n3. NEGATIVE CONTROL: fresh data still approves")
fresh = freshness_verdict(datetime.now().isoformat())
check(fresh.verdict() == vd.VERDICT_APPROVED,
      "a current timestamp APPROVES, so the refusals above are discriminating")
check(vd.EXIT_BY_VERDICT[fresh.verdict()] == 0, "...and exits 0")

# --------------------------------------------------------------- the report
print("\n4. The published report says which verdict, and the old boolean narrowed")

v = freshness_verdict("not-a-timestamp")
tmp = Path(tempfile.mkdtemp())
cwd = os.getcwd()
try:
    os.chdir(tmp)
    report = v.create_deployment_report()
finally:
    os.chdir(cwd)
    shutil.rmtree(tmp, ignore_errors=True)

check(report["verdict"] == vd.VERDICT_CANNOT_VERIFY,
      "the report carries the verdict as a string, not just a boolean")
check(report["deployment_approved"] is False,
      "deployment_approved is FALSE on CANNOT VERIFY -- under the old rule "
      "(checks_failed == 0) this exact state published true")
check(report["unverifiable"], "...and the report names what could not be established")

# The window is POLICY and must be declared, not derived from the writer it checks.
print("\n5. The staleness window is a declared ruling")
check(isinstance(vd.VERSION_DATA_MAX_AGE_HOURS, (int, float))
      and vd.VERSION_DATA_MAX_AGE_HOURS > 0,
      "VERSION_DATA_MAX_AGE_HOURS is a declared number")
src = SCRIPT.read_text(encoding="utf-8")
check("DEPLOYMENT APPROVED" in src, "the approving message still exists for the approving case")
check(src.count("VERDICT_APPROVED") >= 3,
      "...and it is reached through the verdict, not from a bare checks_failed test")

# --------------------------------------------------------------- the callers
print("\n6. No caller throws the verdict away")
for wf in ["weekly-deployment.yml", "version-aware-deploy.yml"]:
    text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
    live = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    calls = [ln for ln in live if "verify-deployment.py" in ln or "health-check.py" in ln]
    check(calls, f"{wf} still calls the gate")
    check(all("||" not in ln for ln in calls),
          f"{wf} does not mask the gate's exit code with ||")
    check(not any("non-critical" in ln for ln in live),
          f"{wf} asserts no invented severity on a gate it did not read")

# The flag that never existed. verify-deployment.py has no argument parsing at
# all, so a flag in a workflow read as a narrower mode while doing nothing.
check("argparse" not in src and "sys.argv" not in src,
      "verify-deployment.py still takes no arguments (so no caller may imply it does)")
for wf in ["weekly-deployment.yml", "version-aware-deploy.yml"]:
    text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
    live = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    check(not any("verify-deployment.py" in ln and "--" in ln.split("verify-deployment.py")[1]
                  for ln in live),
          f"{wf} passes it no flags it cannot honour")

print("\n" + "=" * 62)
if failures:
    print("%d FAILURE(S)" % len(failures))
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: three verdicts, an unknown never approves, and no caller discards the answer.")
