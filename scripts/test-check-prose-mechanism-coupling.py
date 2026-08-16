#!/usr/bin/env python
"""Force check-prose-mechanism-coupling.py into every failing state.

A guard seen only in its passing state has not been shown to work: green is
equally consistent with "the prose and the mechanism agree" and "the check never
fires". Every case here builds a throwaway repo in a temp dir, plants a specific
defect, and asserts the guard refuses it -- plus the mirror cases where it must
NOT fire, because a check with false positives is one people route around.

Nothing here touches the real repo or any committed fixture.
"""

import importlib
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
guard = importlib.import_module("check-prose-mechanism-coupling")

FAILURES = []
CHECKS = 0


def expect(label, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        FAILURES.append(label)


def build(root, *, prose, registry, page_script=None, cron_script=None,
          make_path=None):
    """Construct a minimal fake repo. Returns the registry path."""
    (root / "public").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)

    (root / "public" / "privacy.html").write_text(prose, encoding="utf-8")

    if page_script:
        (root / "public" / "mounted.html").write_text(
            '<script src="/%s"></script>' % page_script, encoding="utf-8")

    if cron_script:
        (root / ".github" / "workflows" / "maint.yml").write_text(
            "on:\n  schedule:\n    - cron: '0 3 * * *'\njobs:\n  j:\n    steps:\n"
            "      - run: python %s --check\n" % cron_script, encoding="utf-8")

    if make_path:
        p = root / make_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")

    reg = root / "registry.json"
    reg.write_text(json.dumps(registry), encoding="utf-8")
    return reg


def run(root, reg):
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = guard.main(["--root", str(root), "--registry", str(reg)])
    return rc, buf.getvalue() + err.getvalue()


def claim(cid, pattern, kind, value):
    return {
        "id": cid, "claim_file": "public/privacy.html", "claim_pattern": pattern,
        "requires": {"kind": kind, "value": value}, "why": "because",
    }


BASE = {"schema": 1, "claims": [
    claim("widget", "feedback widget", "page_loads_script", "assets/js/feedback.js")]}

print("=" * 78)
print("FORCED-FAILURE SUITE -- check-prose-mechanism-coupling.py")
print("=" * 78)

tmp = Path(tempfile.mkdtemp(prefix="prose_coupling_"))
try:
    # --- 1. the real 2026-08-16 defect: prose LEADS mechanism ----------------
    print("\n-- prose claims a widget that no page mounts (the actual defect)")
    r = tmp / "c1"
    reg = build(r, prose="<p>Some pages carry a feedback widget.</p>", registry=BASE)
    rc, out = run(r, reg)
    expect("unmounted widget is refused", rc == 1, "(rc=%d)" % rc)
    expect("the finding names the page", "public/privacy.html" in out)
    expect("the finding offers exactly two remedies",
           "Make the mechanism real" in out and "Take the sentence out" in out)
    expect("it forbids the third 'remedy'", "loosening the pattern" in out)

    # --- 2. same prose, mechanism now real ----------------------------------
    print("\n-- the same claim, once a page actually mounts it")
    r = tmp / "c2"
    reg = build(r, prose="<p>Some pages carry a feedback widget.</p>",
                registry=BASE, page_script="assets/js/feedback.js")
    rc, _ = run(r, reg)
    expect("mounted widget passes", rc == 0, "(rc=%d)" % rc)

    # --- 3. dormant claim: prose does not make it ----------------------------
    print("\n-- a claim the prose does not currently make owes no mechanism")
    r = tmp / "c3"
    two = {"schema": 1, "claims": [
        claim("widget", "feedback widget", "page_loads_script", "assets/js/feedback.js"),
        claim("tally", "public tally", "path_exists", "scripts/stats.py")]}
    reg = build(r, prose="<p>Some pages carry a feedback widget.</p>",
                registry=two, page_script="assets/js/feedback.js")
    rc, out = run(r, reg)
    expect("dormant claim does not fail the run", rc == 0, "(rc=%d)" % rc)
    expect("but it is COUNTED and printed, never silent", "dormant" in out,
           "-- green must carry a number")

    # --- 4. cron is required, not just an invocation -------------------------
    print("\n-- a script wired to dispatch-only does not satisfy a retention promise")
    clocks = {"schema": 1, "claims": [
        claim("clock", "90 days", "workflow_schedules", "scripts/purge.py")]}
    r = tmp / "c4a"
    reg = build(r, prose="<p>deleted within 90 days</p>", registry=clocks)
    (r / ".github" / "workflows" / "manual.yml").write_text(
        "on:\n  workflow_dispatch:\njobs:\n  j:\n    steps:\n"
        "      - run: python scripts/purge.py\n", encoding="utf-8")
    rc, _ = run(r, reg)
    expect("invoked but NOT scheduled is refused", rc == 1, "(rc=%d)" % rc)

    r = tmp / "c4b"
    reg = build(r, prose="<p>deleted within 90 days</p>", registry=clocks,
                cron_script="scripts/purge.py")
    rc, _ = run(r, reg)
    expect("invoked AND scheduled passes", rc == 0, "(rc=%d)" % rc)

    # --- 5. a vanished claim_file must fail closed ---------------------------
    print("\n-- a renamed/deleted page must not silently drop out of coverage")
    r = tmp / "c5"
    reg = build(r, prose="<p>feedback widget</p>", registry=BASE,
                page_script="assets/js/feedback.js")
    (r / "public" / "privacy.html").unlink()
    rc, out = run(r, reg)
    expect("missing claim_file is a finding, not a pass", rc != 0, "(rc=%d)" % rc)
    expect("and it says so explicitly", "does not exist" in out or "proved nothing" in out)

    # --- 6. registry validation: reject the WHOLE file -----------------------
    print("\n-- a malformed registry is rejected whole, never partially skipped")
    bad_cases = [
        ("unknown predicate kind",
         {"schema": 1, "claims": [claim("x", "p", "vibes_check", "v")]}),
        ("missing 'why'",
         {"schema": 1, "claims": [{"id": "x", "claim_file": "public/privacy.html",
                                   "claim_pattern": "p",
                                   "requires": {"kind": "path_exists", "value": "v"}}]}),
        ("blank field",
         {"schema": 1, "claims": [{"id": "", "claim_file": "public/privacy.html",
                                   "claim_pattern": "p", "why": "w",
                                   "requires": {"kind": "path_exists", "value": "v"}}]}),
        ("duplicate id", {"schema": 1, "claims": [
            claim("dup", "a", "path_exists", "v"),
            claim("dup", "b", "path_exists", "v")]}),
        ("empty claims array", {"schema": 1, "claims": []}),
        ("invalid regex",
         {"schema": 1, "claims": [claim("x", "([unclosed", "path_exists", "v")]}),
    ]
    for label, reg_obj in bad_cases:
        r = tmp / ("c6_" + label.replace(" ", "_").replace("'", ""))
        reg = build(r, prose="<p>p</p>", registry=reg_obj)
        rc, _ = run(r, reg)
        expect("registry rejected: %-24s" % label, rc == 2, "(rc=%d)" % rc)

    # --- 7. an unknown kind must never evaluate to TRUE ----------------------
    print("\n-- the dangerous direction: an unevaluable claim must not pass")
    r = tmp / "c7"
    reg = build(r, prose="<p>feedback widget</p>",
                registry={"schema": 1, "claims": [
                    claim("x", "feedback widget", "not_a_real_kind", "v")]})
    rc, _ = run(r, reg)
    expect("unknown predicate is rejected, not treated as satisfied", rc == 2,
           "(rc=%d) -- an unevaluable claim that passes is worse than no claim" % rc)

    # --- 8. never exit 0 having checked nothing ------------------------------
    print("\n-- the cheap-early-exit trap this repo already has a scar from")
    r = tmp / "c8"
    reg = build(r, prose="<p>totally unrelated copy</p>",
                registry={"schema": 1, "claims": [
                    claim("x", "feedback widget", "path_exists", "scripts/p.py")]})
    rc, out = run(r, reg)
    expect("all-dormant registry does NOT exit 0", rc == 2, "(rc=%d)" % rc)
    expect("and it says the run proved nothing", "proved nothing" in out)

    # --- 9. case insensitivity ----------------------------------------------
    print("\n-- prose case must not be a way to evade a claim")
    r = tmp / "c9"
    reg = build(r, prose="<p>Some pages carry a FEEDBACK WIDGET.</p>", registry=BASE)
    rc, _ = run(r, reg)
    expect("uppercase prose still triggers the claim", rc == 1, "(rc=%d)" % rc)

    print("")
    print("=" * 78)
    if FAILURES:
        print("FAIL: %d of %d checks failed: %s"
              % (len(FAILURES), CHECKS, ", ".join(FAILURES)))
        sys.exit(1)
    print("OK: %d checks -- every coupling failure was forced and observed refused," % CHECKS)
    print("    and every case where the guard must stay quiet was confirmed quiet.")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
