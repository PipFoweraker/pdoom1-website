#!/usr/bin/env python
"""Prove the analytics-to-git hedge fails LOUDLY, without needing the API key.

The key (PLAUSIBLE_API_KEY) is a repository secret and cannot be read back out,
so the only place the real path runs is CI. That makes the failure behaviour
untestable by hand -- which is exactly how a backup ends up green for months
while writing nothing. This stubs the Stats API and asserts each exit code.

It also asserts two things about .github/workflows/snapshot-analytics.yml that
no unit test of the script could catch, both of which have burned this repo:

  TRAP 1  `git diff` cannot see untracked files, so a workflow that writes a
          NEW dated file and then tests `git diff --quiet` reports "nothing to
          commit" and SUCCEEDS while committing nothing. A daily snapshot
          writes a new file every single run, so this trap is not hypothetical
          here. The test demonstrates the difference in a throwaway git repo,
          then asserts the workflow does the add-first ordering.
  TRAP 3  A failure handler without `permissions: issues: write` 403s, and the
          failure becomes invisible -- worse than no handler, because someone
          believes it is watching.

    python scripts/test-snapshot-plausible.py
"""

import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "snapshot-plausible.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "snapshot-analytics.yml"

FAILURES = []
PASSES = []


def check(name, condition, detail=""):
    if condition:
        PASSES.append(name)
        print("  PASS  %s" % name)
    else:
        FAILURES.append("%s%s" % (name, (" -- " + detail) if detail else ""))
        print("  FAIL  %s%s" % (name, (" -- " + detail) if detail else ""))


def load_module():
    spec = importlib.util.spec_from_file_location("snapshot_plausible", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------- fake API
def ts_rows(dates, visitors=3, pageviews=4):
    return [{"date": d, "visitors": visitors, "pageviews": pageviews} for d in dates]


def good_payloads(dates=None, visitors=90, pageviews=108, daily=3):
    dates = dates or ["2026-07-2%d" % i for i in range(1, 8)]
    return {
        "aggregate": {"results": {
            "visitors": {"value": visitors},
            "visits": {"value": visitors},
            "pageviews": {"value": pageviews},
            "bounce_rate": {"value": 88},
            "visit_duration": {"value": 12},
        }},
        "timeseries": {"results": ts_rows(dates, daily, daily)},
        "breakdown": {"results": [{"source": "Direct / None", "visitors": 40}]},
    }


def make_api(payloads, fail=(), http_status=500):
    """Return a stand-in for module.api(). `fail` names the SECTIONS to break;
    breakdown sections are told apart by their `property` param."""
    section_of = {
        "visit:source": "sources",
        "event:page": "pages",
        "visit:country": "countries",
        "visit:utm_campaign": "utm_campaign",
        "event:goal": "goals",
    }

    def _api(path, params, key):
        section = path if path != "breakdown" else section_of.get(params.get("property"), "breakdown")
        if section in fail:
            raise urllib.error.HTTPError(
                "https://analytics.pdoom1.com", http_status, "boom", {},
                io.BytesIO(b'{"error":"stubbed failure"}'))
        return payloads.get(path if path != "breakdown" else "breakdown", {})

    return _api


def run_main(mod, argv, tmp, key="stub-key", api=None):
    """Run main() with output captured and writes redirected into tmp."""
    out_dir = Path(tmp) / "history"
    latest = Path(tmp) / "latest.json"
    mod.OUT_DIR = out_dir
    mod.LATEST = latest
    if api is not None:
        mod.api = api
    if key is None:
        os.environ.pop("PLAUSIBLE_API_KEY", None)
    else:
        os.environ["PLAUSIBLE_API_KEY"] = key
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        code = mod.main(argv)
    return code, buf.getvalue() + err.getvalue(), out_dir, latest


# ------------------------------------------------------------- script tests
def test_script():
    print("\nsnapshot-plausible.py exit codes")
    mod = load_module()

    # 1. Missing key in CI must be a FAILURE, not a friendly no-op. Before this,
    #    a revoked secret produced a green run that committed nothing, forever.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, out_dir, latest = run_main(mod, ["--require-key"], tmp, key=None)
        check("no key + --require-key exits EXIT_CONFIG", code == mod.EXIT_CONFIG,
              "got %s" % code)
        check("no key + --require-key writes nothing", not out_dir.exists())
        check("no key + --require-key names the secret", "PLAUSIBLE_API_KEY" in out)

    # 2. Without --require-key the local ergonomics are preserved: a dev with no
    #    key gets a dry run, not a traceback.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, out_dir, _ = run_main(mod, [], tmp, key=None)
        check("no key, no flag stays a dry run", code == mod.EXIT_OK, "got %s" % code)
        check("dry run writes nothing", not out_dir.exists())

    # 3. An invalid/revoked key 401s every section. Nothing may be written --
    #    least of all latest.json, whose last good copy is the thing being
    #    protected.
    with tempfile.TemporaryDirectory() as tmp:
        latest = Path(tmp) / "latest.json"
        latest.write_text('{"known":"good"}', encoding="utf-8")
        code, out, out_dir, latest = run_main(
            mod, ["--date", "2026-07-29"], tmp,
            api=make_api(good_payloads(), fail=("aggregate", "timeseries"),
                         http_status=401))
        check("all sections 401 exits EXIT_FETCH", code == mod.EXIT_FETCH,
              "got %s" % code)
        check("failed fetch writes no dated file", not out_dir.exists())
        check("failed fetch leaves latest.json untouched",
              json.loads(latest.read_text(encoding="utf-8")) == {"known": "good"})

    # 4. A 200 that is structurally wrong is just as fatal as a 500.
    with tempfile.TemporaryDirectory() as tmp:
        payloads = good_payloads()
        payloads["aggregate"] = {"results": {}}
        code, out, out_dir, _ = run_main(mod, ["--date", "2026-07-29"], tmp,
                                         api=make_api(payloads))
        check("empty aggregate results exits EXIT_FETCH", code == mod.EXIT_FETCH,
              "got %s" % code)
        check("empty aggregate writes nothing", not out_dir.exists())

    with tempfile.TemporaryDirectory() as tmp:
        payloads = good_payloads()
        payloads["timeseries"] = {"results": []}
        code, out, out_dir, _ = run_main(mod, ["--date", "2026-07-29"], tmp,
                                         api=make_api(payloads))
        check("empty timeseries exits EXIT_FETCH", code == mod.EXIT_FETCH,
              "got %s" % code)

    # 5. All-zero is the quiet killer: ingestion breaks, the API answers 200
    #    with zeros, and a chart later animates a confident lie.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, out_dir, _ = run_main(
            mod, ["--date", "2026-07-29"], tmp,
            api=make_api(good_payloads(visitors=0, pageviews=0, daily=0)))
        check("all-zero response exits EXIT_EMPTY", code == mod.EXIT_EMPTY,
              "got %s" % code)
        check("all-zero writes nothing", not out_dir.exists())
        check("all-zero explains what to check", "site id" in out)

    # 6. ...but a real zero is data, and the operator has an explicit override.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, out_dir, _ = run_main(
            mod, ["--date", "2026-07-29", "--allow-zero"], tmp,
            api=make_api(good_payloads(visitors=0, pageviews=0, daily=0)))
        check("--allow-zero records a genuine zero", code == mod.EXIT_OK,
              "got %s" % code)
        check("--allow-zero wrote the file",
              (out_dir / "2026-07-29.json").exists())

    # 7. The happy path, and the coverage block.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, out_dir, latest = run_main(
            mod, ["--date", "2026-07-29"], tmp, api=make_api(good_payloads()))
        check("good response exits 0", code == mod.EXIT_OK, "got %s" % code)
        dated = out_dir / "2026-07-29.json"
        check("good response writes the dated file", dated.exists())
        check("good response updates latest.json", latest.exists())
        if dated.exists():
            snap = json.loads(dated.read_text(encoding="utf-8"))
            check("dated file and latest.json agree",
                  latest.read_text(encoding="utf-8") == dated.read_text(encoding="utf-8"))
            cov = snap.get("coverage", {})
            check("coverage reports the observed span",
                  cov.get("first_date") == "2026-07-21"
                  and cov.get("last_date") == "2026-07-27",
                  json.dumps(cov)[:160])
            check("coverage counts only days the API returned",
                  cov.get("days_returned") == 7, str(cov.get("days_returned")))
            check("no gaps invented for a contiguous span",
                  cov.get("missing_dates") == [], str(cov.get("missing_dates")))
            check("snapshot records its provenance",
                  snap.get("source") == mod.HOST and snap.get("captured_at_utc"))

    # 8. A hole in the API's own response is RECORDED, never filled in. The
    #    timeseries must still contain exactly the rows the API returned.
    with tempfile.TemporaryDirectory() as tmp:
        dates = ["2026-07-21", "2026-07-22", "2026-07-25", "2026-07-26"]
        code, out, out_dir, _ = run_main(
            mod, ["--date", "2026-07-29"], tmp,
            api=make_api(good_payloads(dates=dates)))
        snap = json.loads((out_dir / "2026-07-29.json").read_text(encoding="utf-8"))
        cov = snap["coverage"]
        check("a gap inside the span is recorded",
              cov["missing_dates"] == ["2026-07-23", "2026-07-24"],
              str(cov["missing_dates"]))
        check("the gap is NOT interpolated into the timeseries",
              len(snap["sections"]["timeseries"]["results"]) == 4)
        check("a missing day is warned about", "omitted" in out)

    # 9. Genuine zero days inside an otherwise busy window are recorded as data.
    with tempfile.TemporaryDirectory() as tmp:
        payloads = good_payloads()
        payloads["timeseries"]["results"][2] = {
            "date": "2026-07-23", "visitors": 0, "pageviews": 0}
        code, out, out_dir, _ = run_main(mod, ["--date", "2026-07-29"], tmp,
                                         api=make_api(payloads))
        snap = json.loads((out_dir / "2026-07-29.json").read_text(encoding="utf-8"))
        check("a real zero day is listed, not dropped",
              snap["coverage"]["zero_dates"] == ["2026-07-23"],
              str(snap["coverage"]["zero_dates"]))

    # 10. One flaky breakdown must not cost the day's backup -- but it must be
    #     announced, not swallowed.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, out_dir, _ = run_main(
            mod, ["--date", "2026-07-29"], tmp,
            api=make_api(good_payloads(), fail=("goals",)))
        check("an optional section failing still saves the snapshot",
              code == mod.EXIT_OK and (out_dir / "2026-07-29.json").exists(),
              "got %s" % code)
        check("a degraded section is reported", "degraded" in out and "goals" in out)

    # 11. Backfill mode writes its own file and never disturbs latest.json,
    #     which must always describe the most recent day.
    with tempfile.TemporaryDirectory() as tmp:
        latest = Path(tmp) / "latest.json"
        latest.write_text('{"known":"good"}', encoding="utf-8")
        code, out, out_dir, latest = run_main(
            mod, ["--range", "2026-06-01:2026-06-30"], tmp,
            api=make_api(good_payloads()))
        check("--range writes range-scoped file", code == mod.EXIT_OK
              and (out_dir / "range-2026-06-01_2026-06-30.json").exists(),
              "got %s" % code)
        check("--range leaves latest.json alone",
              json.loads(latest.read_text(encoding="utf-8")) == {"known": "good"})

    with tempfile.TemporaryDirectory() as tmp:
        code, out, out_dir, _ = run_main(mod, ["--range", "nonsense"], tmp,
                                         api=make_api(good_payloads()))
        check("a malformed --range is rejected", code == mod.EXIT_CONFIG,
              "got %s" % code)


# ------------------------------------------------- trap 1, demonstrated
def _rm(path):
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def test_git_add_ordering():
    """Show, in a throwaway repo, that the ordering is load-bearing: the naive
    guard cannot see a brand-new file, and the add-first guard can."""
    print("\ntrap 1: git diff cannot see an untracked file")
    tmp = tempfile.mkdtemp()
    try:
        def git(*args):
            return subprocess.run(["git", "-C", tmp] + list(args),
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")

        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        Path(tmp, "seed.txt").write_text("seed\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "seed")

        # Exactly what a daily snapshot does: create a NEW dated file.
        target = Path(tmp, "history")
        target.mkdir()
        (target / "2026-07-29.json").write_text("{}\n", encoding="utf-8")

        naive = git("diff", "--quiet", "--", "history")
        check("naive `git diff --quiet` reports NO change for a new file",
              naive.returncode == 0,
              "returncode %s -- if this ever changes, the trap note in "
              "CLAUDE.md needs revisiting" % naive.returncode)

        git("add", "-A", "history")
        staged = git("diff", "--cached", "--quiet", "--", "history")
        check("`git add` then `git diff --cached --quiet` DOES detect it",
              staged.returncode != 0, "returncode %s" % staged.returncode)
    finally:
        _rm(tmp)


# ------------------------------------------------- workflow contract
def test_workflow():
    print("\nsnapshot-analytics.yml contract")
    if not WORKFLOW.exists():
        check("workflow exists", False, str(WORKFLOW))
        return
    text = WORKFLOW.read_text(encoding="utf-8")

    add_at = text.find("git add")
    cached_at = text.find("git diff --cached")
    check("commit step stages before it tests for changes (trap 1)",
          add_at != -1 and cached_at != -1 and add_at < cached_at,
          "add@%s cached@%s" % (add_at, cached_at))
    check("no bare `git diff --quiet` guard survives (trap 1)",
          "git diff --quiet" not in text)

    check("the failure handler can actually open an issue (trap 3)",
          "issues: write" in text)
    check("there is a failure handler at all",
          "if: failure()" in text or "if: ${{ failure() }}" in text)

    check("CI runs the snapshot with --require-key",
          "--require-key" in text)

    # Trap 5: dispatch inputs are author-controlled text. Templated straight
    # into `run:` they are shell, not data. Comment lines are exempt -- the
    # header explains the trap by name and should keep being allowed to.
    live = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    check("no github.event.inputs in live YAML (traps 2 and 5)",
          not any("github.event.inputs" in ln for ln in live),
          next((ln.strip() for ln in live if "github.event.inputs" in ln), ""))
    check("the period input reaches the shell through env (trap 5)",
          "PERIOD:" in text and '"$PERIOD"' in text)

    check("the deploy asymmetry is documented in the header",
          "deploy" in text.lower() and "backup" in text.lower())


def main():
    print("Testing the analytics-to-git hedge (no API key required)")
    test_script()
    test_git_add_ordering()
    test_workflow()

    print("\n%d passed, %d failed" % (len(PASSES), len(FAILURES)))
    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
