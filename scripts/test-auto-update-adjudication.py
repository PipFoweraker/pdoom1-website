#!/usr/bin/env python3
"""Forced-failure test: Auto-Update Data must be able to go red on a data failure.

    python scripts/test-auto-update-adjudication.py     (exit 0 = pass)

WHY THIS FILE EXISTS
--------------------
.github/workflows/auto-update-data.yml grants `issues: write` and carries a
"Create issue on failure" handler gated on `if: failure()`. Its own header
comment explained why: the workflow "carries three `continue-on-error` steps, so
it can report SUCCESS while having written nothing. A workflow that can be green
while broken needs its alarm to actually reach someone."

The comment described the hazard correctly and then described a mitigation that
did not exist. Those three steps were the only things in the job that could fail,
and continue-on-error means a failed step does not fail the job; the commit step
`exit 0`s early when there is nothing to commit. So no failure of
update-version-info.py or calculate-game-stats.py could reach the handler.

Measured before the fix, over the 20 most recent runs: the red ones all failed at
"Commit changes if any" (run 32710311391 -- version, stats and log steps all
green, commit red), which is a concurrent-push race. The alarm was reachable by
exactly one path, and that path says nothing about whether the data updated.

What that costs: update-version-info.py is written to REFUSE rather than guess a
version, and raising is the loudest signal it has. That refusal rendered as a
green run and a `success` row on /monitoring/.

WHAT THIS TEST DOES
-------------------
The structural half asserts the adjudication step exists, runs on `always()`,
sits before the handler, and names only step ids that actually exist -- that last
one is the guard against the very defect the step exists to catch, because
`${{ steps.typo.outcome }}` silently expands to the empty string.

The executable half is the part that matters: it EXTRACTS the adjudication step's
shell body out of the YAML and RUNS it under bash across every outcome
combination, asserting the exit code. A structural test can only show the step is
present; this shows it discriminates. CLAUDE.md: "A guard seen only in its
passing state has not been shown to work."
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


REPO_ROOT = Path(__file__).parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "auto-update-data.yml"
ADJUDICATE = "Adjudicate step outcomes"

# The data steps whose failure MUST be able to fail the job. Named here rather
# than discovered, so adding a continue-on-error data step to the workflow
# without adjudicating it fails this test.
ADJUDICATED = ["update-version", "update-stats"]

passed = 0
failed = 0


def ok(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  PASS %s" % name)
    else:
        failed += 1
        print("  FAIL %s%s" % (name, (" -> " + detail) if detail else ""))


def load_steps():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return doc, doc["jobs"]["update-data"]["steps"]


def find_step(steps, name):
    for i, step in enumerate(steps):
        if step.get("name") == name:
            return i, step
    return None, None


# ---------------------------------------------------------------------------
# 1. Structure.
# ---------------------------------------------------------------------------
def test_structure(steps):
    print("\nWorkflow structure")

    idx, adj = find_step(steps, ADJUDICATE)
    ok("the adjudication step exists", adj is not None,
       "no step named %r" % ADJUDICATE)
    if adj is None:
        return None

    ok("it runs on always(), so a red earlier step cannot skip it",
       str(adj.get("if", "")).strip() == "always()", repr(adj.get("if")))
    ok("it is NOT continue-on-error (that would re-disarm it)",
       adj.get("continue-on-error") in (None, False),
       repr(adj.get("continue-on-error")))
    ok("its body can exit non-zero", "exit 1" in adj.get("run", ""))

    hidx, handler = find_step(steps, "Create issue on failure")
    ok("the failure handler still exists", handler is not None)
    if handler is not None:
        ok("the handler is gated on failure()",
           str(handler.get("if", "")).strip() == "failure()", repr(handler.get("if")))
        ok("adjudication comes BEFORE the handler", idx < hidx,
           "adjudicate at %r, handler at %r" % (idx, hidx))

    # The commit step publishes public/monitoring/data/, which is the record of
    # the failure. Adjudicating first would fail the job and skip that commit,
    # leaving /monitoring/ with no entry for the run that went wrong.
    cidx, _ = find_step(steps, "Commit changes if any")
    ok("adjudication comes AFTER the commit, so the evidence is published first",
       cidx is not None and cidx < idx, "commit at %r, adjudicate at %r" % (cidx, idx))

    # Every step id the adjudication reads must exist. A typo here expands to the
    # empty string -- which is exactly the failure mode being fixed, so an
    # unchecked reference would rebuild it inside the fix.
    declared_ids = {s.get("id") for s in steps if s.get("id")}
    env = adj.get("env", {}) or {}
    referenced = []
    for value in env.values():
        text = str(value)
        if "steps." in text:
            referenced.append(text.split("steps.", 1)[1].split(".")[0])
    ok("the adjudication declares its inputs as env vars, not inline ${{ }} in run",
       len(env) > 0 and "${{" not in adj.get("run", ""),
       "workflow trap #5: author-controlled context spliced into run: is code")
    for ref in referenced:
        ok("referenced step id %r actually exists" % ref, ref in declared_ids,
           "declared ids: %s" % sorted(declared_ids))

    for step_id in ADJUDICATED:
        ok("data step id %r is present in the workflow" % step_id,
           step_id in declared_ids)
        ok("...and is read by the adjudication", step_id in referenced,
           "referenced: %s" % referenced)

    return adj


# ---------------------------------------------------------------------------
# 2. Behaviour. Run the real shell body under every outcome combination.
# ---------------------------------------------------------------------------
def test_behaviour(adj):
    print("\nAdjudication behaviour (the real shell body, executed)")

    bash = shutil.which("bash")
    if not bash:
        ok("bash is available to execute the adjudication body", False,
           "no bash on PATH -- this half of the test could not run")
        return

    body = adj.get("run", "")

    cases = [
        # (name, UPDATE_VERSION, UPDATE_STATS, LOG_RUN, expected exit)
        ("both data steps succeeded -> green",
         "success", "success", "success", 0),
        ("version update FAILED -> red",
         "failure", "success", "success", 1),
        ("stats update FAILED -> red",
         "success", "failure", "success", 1),
        ("both FAILED -> red",
         "failure", "failure", "success", 1),
        # The defect this whole PR is about: a renamed or unresolved step id
        # expands to the empty string, and empty read as success is what made
        # /monitoring/ publish 1201/1201.
        ("version outcome EMPTY (unresolved step id) -> red",
         "", "success", "success", 1),
        ("stats outcome EMPTY -> red",
         "success", "", "success", 1),
        ("both outcomes EMPTY -> red",
         "", "", "success", 1),
        # Neither data step is gated by an `if:`, so these are impossible-in-
        # principle values. An unexpected value must be red, not silently fine.
        ("an ungated step reporting 'skipped' -> red",
         "skipped", "success", "success", 1),
        ("an unexpected outcome value -> red",
         "cancelled", "success", "success", 1),
        ("a garbage outcome value -> red",
         "banana", "success", "success", 1),
        # The monitoring logger is deliberately advisory: it records history, it
        # does not produce served data, and its refusal path is repaired by hand.
        ("the monitoring log step failing is a WARNING, not a failure",
         "success", "success", "failure", 0),
        ("the monitoring log step being unresolved is also only a warning",
         "success", "success", "", 0),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "adjudicate.sh"
        script.write_text(body, encoding="utf-8")

        for name, version, stats, log_run, expected in cases:
            env = dict(os.environ)
            env["UPDATE_VERSION"] = version
            env["UPDATE_STATS"] = stats
            env["LOG_RUN"] = log_run
            # `bash -e {0}` is the default shell GitHub uses for a `run:` block.
            proc = subprocess.run(
                [bash, "-e", str(script)],
                env=env, capture_output=True, text=True, encoding="utf-8",
            )
            ok(name, proc.returncode == expected,
               "expected exit %d, got %d; stdout=%r"
               % (expected, proc.returncode, proc.stdout[-300:]))

            if expected == 1:
                ok("  ...and it annotates the run with ::error::",
                   "::error::" in proc.stdout, proc.stdout[-200:])

        # The advisory path must be visible, or "not blocking" becomes "not said".
        env = dict(os.environ)
        env.update({"UPDATE_VERSION": "success", "UPDATE_STATS": "success",
                    "LOG_RUN": "failure"})
        proc = subprocess.run([bash, "-e", str(script)], env=env,
                              capture_output=True, text=True, encoding="utf-8")
        ok("a failed monitoring log still emits ::warning::",
           "::warning::" in proc.stdout, proc.stdout[-200:])


# ---------------------------------------------------------------------------
# 3. NEGATIVE CONTROL: the pre-fix workflow shape must FAIL this test.
#    Without it, a green run here is equally consistent with "the alarm works"
#    and "this test never discriminated".
# ---------------------------------------------------------------------------
def test_negative_control():
    print("\nNegative control: the pre-fix shape must not pass")

    # The workflow as it stood before this PR: same steps, no adjudication.
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["update-data"]["steps"]
    pre_fix = [s for s in steps if s.get("name") != ADJUDICATE]

    idx, adj = find_step(pre_fix, ADJUDICATE)
    ok("with the adjudication removed, the step is not found", adj is None)

    # And with it removed, nothing left in the job can fail on a data error:
    # every data step is continue-on-error, and the commit step exits 0 early.
    failable = [
        s.get("name") for s in pre_fix
        if s.get("continue-on-error") is not True
        and s.get("name") not in ("Checkout repository", "Set up Python",
                                  "Create issue on failure")
    ]
    ok("the only non-continue-on-error step left is the commit",
       failable == ["Commit changes if any"], repr(failable))

    commit = [s for s in pre_fix if s.get("name") == "Commit changes if any"][0]
    ok("...and the commit exits 0 when there is nothing to commit",
       "exit 0" in commit.get("run", ""),
       "so a clean tree could not fail the job either")

    # A weaker adjudication -- one that tolerates the empty outcome, the way
    # sync-leaderboards.yml legitimately does for its `if:`-gated steps -- must
    # not be mistaken for this one.
    weak = 'bad=0\nif [ "$UPDATE_VERSION" = "failure" ]; then bad=1; fi\n' \
           'if [ "$bad" = "1" ]; then exit 1; fi\n'
    bash = shutil.which("bash")
    if bash:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "weak.sh"
            script.write_text(weak, encoding="utf-8")
            env = dict(os.environ)
            env.update({"UPDATE_VERSION": "", "UPDATE_STATS": "success",
                        "LOG_RUN": "success"})
            proc = subprocess.run([bash, "-e", str(script)], env=env,
                                  capture_output=True, text=True, encoding="utf-8")
            ok("a failure-only adjudication would pass the EMPTY outcome (exit 0)",
               proc.returncode == 0, "rc=%d" % proc.returncode)


def main():
    print("Forced-failure test: auto-update-data.yml adjudication")
    print("=" * 60)

    if not WORKFLOW.exists():
        print("FAIL: %s does not exist" % WORKFLOW)
        return 1

    doc, steps = load_steps()
    adj = test_structure(steps)
    if adj is not None:
        test_behaviour(adj)
    test_negative_control()

    print("\n" + "=" * 60)
    print("%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
