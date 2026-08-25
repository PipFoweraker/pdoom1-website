#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Force the events sync to refuse, and watch it write nothing.

WHY THIS EXISTS
---------------
scripts/sync/sync-events.py claims it "refuses to write ANY page if the rendered
output carries a disallowed address". CLAUDE.md's rule: a claimed safety property
needs a FORCED FAILURE. A docstring is documentation, not evidence, and a guard
seen only in its passing state has not been shown to work -- green is equally
consistent with "the condition is safe" and "the check never fires".

So this drives the real main() against a fixture pdoom-data corpus in a temp
directory, with output redirected to a temp public/ tree, and:

  * simulates a REDACTION REGRESSION (redact_pii narrowed to a no-op, which is
    exactly what a future refactor to a named field list would look like) and
    asserts the sync exits non-zero, creates no page, and leaves an existing
    events.json byte-identical;
  * asserts the same for an address in a field that reaches events.json but not
    the HTML template, so the gate is shown to cover BOTH artefacts;
  * asserts the healthy path still publishes, carrying the cross-repo redaction
    marker and no raw address;
  * asserts the marker is the string pdoom-data uses, so the two repos cannot
    drift apart again;
  * asserts the deliberately-published address (team@pdoom1.com, in every page
    footer) does NOT trip the gate -- a guard that fires on our own contact
    address would be turned off within a week;
  * asserts the obfuscated-contact advisory counts without blocking.

Nothing here touches the repo's own public/ tree.

Usage:
    python scripts/test-sync-events-pii.py
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

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNC_PATH = REPO_ROOT / "scripts" / "sync" / "sync-events.py"

FAILURES = []
CHECKS = 0

# A plausible harvested address. Kept obviously fake so nobody's real address
# lives in this repo's test fixtures.
PLANTED = "a.researcher@example-university.edu"
PLANTED_OBFUSCATED = "b.researcher [at] example-university.edu"


def check(label, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        FAILURES.append(label)


# Every stream object the module under test creates, kept alive forever.
#
# On win32 sync-events.py rebinds sys.stdout to io.TextIOWrapper(sys.stdout.buffer)
# at IMPORT time. Two consequences, both observed while writing this test:
#   * dropping the previous wrapper's last reference runs TextIOWrapper.__del__,
#     which CLOSES the underlying buffer -- the next print dies with "I/O
#     operation on closed file";
#   * several live wrappers over one buffer each hold their own buffered text,
#     so this suite's output came out shredded, with whole sections missing.
# So: hold a reference (no close) AND restore the original stream (one writer).
_KEEPALIVE = []


def load_sync_module(path: Path = SYNC_PATH, name: str = "sync_events_under_test"):
    """Import sync-events.py by path (the module name has a hyphen).

    Must be called BEFORE any redirect_stdout: the module's own preamble reads
    sys.stdout.buffer, and a StringIO has no .buffer.
    """
    orig_out, orig_err = sys.stdout, sys.stderr
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _KEEPALIVE.extend([sys.stdout, sys.stderr])
    sys.stdout, sys.stderr = orig_out, orig_err
    return module


def fixture_event(description, extra=None):
    """One event with every field generate_event_detail_page() reads."""
    event = {
        "title": "A Paper With An Author Block",
        "description": description,
        "year": 2025,
        "category": "technical_research_breakthrough",
        "rarity": "common",
        "tags": ["alignment", "test"],
        "impacts": [{"variable": "doom_level", "change": -1, "condition": None}],
        "sources": ["https://arxiv.org/abs/0000.00000"],
        "safety_researcher_reaction": "No comment.",
        "media_reaction": "No comment.",
        "reaction_provenance": {
            "safety_researcher_reaction": "placeholder",
            "media_reaction": "placeholder",
        },
        "pdoom_impact": None,
        "event_status": "included",
    }
    if extra:
        event.update(extra)
    return event


def build_corpus(root: Path, events: dict) -> Path:
    """Write a fixture all_events.json where the sync expects to find one."""
    data_dir = root / "pdoom-data" / "data" / "serveable" / "api" / "timeline_events"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "all_events.json").write_text(
        json.dumps(events, indent=2), encoding="utf-8"
    )
    return root / "pdoom-data"


def point_module_at(module, root: Path):
    """Redirect every output path the sync writes into a temp tree."""
    public = root / "public"
    module.PUBLIC_DIR = public
    module.EVENTS_DIR = public / "events"
    module.DATA_DIR = public / "data"
    module.ICONS_DIR = public / "assets" / "icons" / "events"
    return public


def run_sync(module, corpus: Path):
    """Call the real main(). Returns (exit_code, captured_stdout).

    THE CORPUS FLOOR IS SCOPED HERE, NOT WEAKENED THERE. sync-events.py refuses
    a corpus below MIN_EVENTS (D6, pdoom1-website#384) and has no override flag,
    because an override is a disarm switch. The fixtures in this file are one or
    two events on purpose -- they exist to force a PII regression, not to be a
    realistic corpus -- so the constant is patched on the imported module for the
    duration of the call and restored unconditionally. Nothing in production can
    reach this. scripts/test-sync-events.py owns the assertions about the floor
    itself, against its real value.
    """
    buf = io.StringIO()
    argv = sys.argv
    before_floor = module.MIN_EVENTS
    module.MIN_EVENTS = 1
    sys.argv = ["sync-events.py", "--pdoom-data-path", str(corpus)]
    code = 0
    try:
        with redirect_stdout(buf):
            module.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.argv = argv
        module.MIN_EVENTS = before_floor
    return code, buf.getvalue()


# ---------------------------------------------------------------------------

def test_marker_matches_pdoom_data():
    print("\n[1] The redaction marker is the cross-repo agreed string")
    module = load_sync_module()
    check(
        "REDACTION_MARKER == '[email address redacted]'",
        module.REDACTION_MARKER == "[email address redacted]",
        f"got {module.REDACTION_MARKER!r}; pdoom-data#50 writes "
        f"'[email address redacted]' at source and Pip ruled both repos match",
    )


def test_healthy_path_publishes_redacted():
    print("\n[2] Healthy path: publishes, redacted, marker visible")
    module = load_sync_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus = build_corpus(root, {
            "evt_healthy": fixture_event(
                f"Author One, MIT, {PLANTED}. We study alignment."
            )
        })
        public = point_module_at(module, root)
        code, out = run_sync(module, corpus)

        page = public / "events" / "evt_healthy.html"
        check("sync exited 0", code == 0, out[-1500:])
        check("page was written", page.exists())
        if page.exists():
            html = page.read_text(encoding="utf-8")
            check("raw address absent from page", PLANTED not in html)
            check("redaction marker visible on page",
                  module.REDACTION_MARKER in html)
            # The gate must not fire on the address we publish on purpose --
            # every generated page carries mailto:team@pdoom1.com in its footer.
            check("our own contact address survives on the page",
                  "team@pdoom1.com" in html)

        events_json = public / "data" / "events.json"
        check("events.json was written", events_json.exists())
        if events_json.exists():
            text = events_json.read_text(encoding="utf-8")
            check("raw address absent from events.json", PLANTED not in text)
            check("redaction marker present in events.json",
                  module.REDACTION_MARKER in text)


def test_forced_failure_redaction_regression():
    print("\n[3] FORCED FAILURE: redaction regresses -> refuses, writes nothing")
    module = load_sync_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus = build_corpus(root, {
            "evt_leak": fixture_event(
                f"Author One, MIT, {PLANTED}. We study alignment."
            )
        })
        public = point_module_at(module, root)

        # Pre-seed the outputs a real run would overwrite, so "wrote nothing"
        # is observed rather than assumed. A refusal that clobbers the last
        # good events.json would be a worse bug than the one being guarded.
        (public / "data").mkdir(parents=True, exist_ok=True)
        (public / "events").mkdir(parents=True, exist_ok=True)
        sentinel_json = public / "data" / "events.json"
        sentinel_json.write_text('{"previous": "good data"}', encoding="utf-8")
        sentinel_page = public / "events" / "evt_previously_published.html"
        sentinel_page.write_text("<html>untouched</html>", encoding="utf-8")
        before_json = sentinel_json.read_bytes()
        before_page = sentinel_page.read_bytes()

        # THE REGRESSION. This is what narrowing redact_pii() back to a named
        # field list, or forgetting to call it, looks like from the gate's side.
        module.redact_pii = lambda value: value

        code, out = run_sync(module, corpus)

        print("        --- captured sync output (tail) ---")
        for line in out.strip().splitlines()[-12:]:
            print(f"        {line}")
        print("        --- end ---")

        check("sync exited non-zero", code != 0, f"exit code was {code}")
        check("log says it is refusing to write", "REFUSING TO WRITE" in out)
        check("no page was written for the leaking event",
              not (public / "events" / "evt_leak.html").exists())
        check("existing events.json is byte-identical",
              sentinel_json.read_bytes() == before_json)
        check("previously published page is byte-identical",
              sentinel_page.read_bytes() == before_page)
        check("the address itself is not echoed into the log",
              PLANTED not in out,
              "CI logs are public; printing the address would republish it")


def test_forced_failure_json_only_field():
    print("\n[4] FORCED FAILURE: address in a field only events.json carries")
    module = load_sync_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 'corresponding_author' is not read by the HTML template, but
        # write_events_json() serialises the whole event. If the gate only
        # scanned pages, this would ship.
        corpus = build_corpus(root, {
            "evt_json_leak": fixture_event(
                "A clean description.",
                extra={"corresponding_author": PLANTED},
            )
        })
        public = point_module_at(module, root)
        module.redact_pii = lambda value: value

        code, out = run_sync(module, corpus)

        check("sync exited non-zero", code != 0, f"exit code was {code}")
        check("events.json named as the leaking artefact",
              "public/data/events.json" in out, out[-1500:])
        check("no events.json was written",
              not (public / "data" / "events.json").exists())
        check("no page was written",
              not (public / "events" / "evt_json_leak.html").exists())


def test_missing_allowlist_refuses():
    print("\n[5] The gate cannot disarm itself if the checker goes missing")
    module = load_sync_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Copy the generator next to NO checker, so load_allowlist() cannot
        # resolve scripts/check-published-emails.py.
        scripts = root / "scripts" / "sync"
        scripts.mkdir(parents=True)
        shutil.copy2(SYNC_PATH, scripts / "sync-events.py")
        orphan = load_sync_module(scripts / "sync-events.py",
                                  "sync_events_no_checker")

        corpus = build_corpus(root, {"evt_x": fixture_event("Clean text.")})
        public = point_module_at(orphan, root)
        code, out = run_sync(orphan, corpus)

        check("sync exited non-zero", code != 0, f"exit code was {code}")
        check("log names the missing checker",
              "check-published-emails.py is missing" in out or
              "Cannot verify published emails" in out, out[-800:])
        check("no page was written",
              not (public / "events" / "evt_x.html").exists())


def test_obfuscated_contact_is_advisory_not_blocking():
    print("\n[6] Obfuscated contact strings are counted, and do NOT block")
    module = load_sync_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus = build_corpus(root, {
            "evt_obf": fixture_event(
                f"Contact the author at {PLANTED_OBFUSCATED} for the dataset."
            )
        })
        public = point_module_at(module, root)
        code, out = run_sync(module, corpus)

        check("sync still exited 0 (advisory, never blocking)", code == 0,
              out[-1200:])
        check("page was still written",
              (public / "events" / "evt_obf.html").exists())
        check("log carries the ADVISORY line", "ADVISORY" in out, out[-1200:])

        summary = public / "data" / "events-sync-summary.json"
        check("sync summary exists", summary.exists())
        if summary.exists():
            data = json.loads(summary.read_text(encoding="utf-8"))
            pii = data.get("pii", {})
            check("summary counts the suspect",
                  pii.get("obfuscated_contact_suspects", 0) >= 1, str(pii))
            check("summary publishes counts only, never the string",
                  "example-university" not in summary.read_text(encoding="utf-8"),
                  "this file is served from pdoom1.com")

    # And the narrow-by-design half: ordinary prose must not trip it.
    check("prose 'aimed at arxiv.org' is not a suspect",
          module.count_obfuscated_contacts("the work aimed at arxiv.org today") == 0)
    check("'name [at] domain.edu' is a suspect",
          module.count_obfuscated_contacts(PLANTED_OBFUSCATED) == 1)
    check("'name AT domain DOT edu' is a suspect",
          module.count_obfuscated_contacts("jane AT example DOT edu") == 1)


def main():
    print("=" * 70)
    print("sync-events.py PII gate -- forced-failure suite")
    print("=" * 70)

    test_marker_matches_pdoom_data()
    test_healthy_path_publishes_redacted()
    test_forced_failure_redaction_regression()
    test_forced_failure_json_only_field()
    test_missing_allowlist_refuses()
    test_obfuscated_contact_is_advisory_not_blocking()

    print("\n" + "=" * 70)
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} of {CHECKS} checks failed")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"PASS: all {CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
