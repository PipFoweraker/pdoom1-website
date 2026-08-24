#!/usr/bin/env python
"""Forced-failure test: a partly-failed syndication run must never re-post.

WHY THIS FILE EXISTS
--------------------
post-syndication.py's docstring claimed "posted_at is already set (prevents
double-posting on a re-run)". That was true only of a run in which nothing went
wrong. `posted_at` was written under `if all_ok`, and a draft lists four
platforms, so the realistic first live run -- one credential configured, three
endpoints returning 500 -- posted to Bluesky, recorded nothing, and would have
posted to Bluesky again on the next run. The claimed property and the code
disagreed, and no test asked.

CLAUDE.md: "A claimed safety property needs a forced failure." So this drives
the real main() with a stubbed transport that succeeds for one platform and
fails for another, and asserts what is on disk afterwards. Nothing here touches
content/syndication/ -- every draft is built in a temp directory.

Run: python scripts/test-post-syndication.py
"""

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "postsyn", REPO_ROOT / "scripts" / "post-syndication.py")
postsyn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(postsyn)

PASS = 0
FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" -> " + str(detail)) if detail else ""))


URL = "https://pdoom1.com/blog/post.html?p=x.md"


def make_draft(queue, name="draft.json", approved=True, platforms=("bluesky", "x")):
    draft = {
        "title": "a post",
        "url": URL,
        "approved": approved,
        "copy": {p: "words about doom %s" % URL for p in platforms},
    }
    path = queue / name
    path.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
    return path


def run(queue, ok_platforms, monkeypatch_env=True):
    """Drive the real main() with a stubbed post_one. Returns (exit_code, calls)."""
    calls = []

    def stub_post_one(base_url, token, platform, draft, dry_run):
        calls.append(platform)
        if platform in ok_platforms:
            return True, "200 {\"success\":true}"
        return False, "HTTP 500 Bluesky credentials not configured"

    real_post_one, real_queue = postsyn.post_one, postsyn.QUEUE
    postsyn.post_one = stub_post_one
    postsyn.QUEUE = queue
    if monkeypatch_env:
        import os
        os.environ["DRY_RUN"] = "false"
        os.environ["SYNDICATION_TOKEN"] = "test-token"
        os.environ["NETLIFY_SITE_URL"] = "https://example.invalid"
    try:
        code = postsyn.main()
    finally:
        postsyn.post_one, postsyn.QUEUE = real_post_one, real_queue
    return code, calls


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


tmp = Path(tempfile.mkdtemp(prefix="syndication-test-"))
try:
    # ------------------------------------------------------------------
    print("a partial failure records the half that worked")
    q = tmp / "partial"
    q.mkdir()
    path = make_draft(q)

    code, calls = run(q, ok_platforms={"bluesky"})
    d = load(path)

    ok("both platforms were attempted", sorted(calls) == ["bluesky", "x"], calls)
    ok("the run reports failure", code == 1, "exit %s" % code)
    ok("bluesky is in the ledger", "bluesky" in (d.get("posted") or {}),
       d.get("posted"))
    ok("x is NOT in the ledger", "x" not in (d.get("posted") or {}),
       d.get("posted"))
    ok("posted_at is NOT set while a platform is outstanding",
       not d.get("posted_at"), d.get("posted_at"))
    ok("the ledger records a hash of what was sent",
       (d["posted"]["bluesky"].get("copy_sha256_12") or "") ==
       postsyn.copy_digest(d["copy"]["bluesky"]))

    # ------------------------------------------------------------------
    # THE ASSERTION THIS FILE EXISTS FOR.
    print("re-running does not post to bluesky a second time")
    code2, calls2 = run(q, ok_platforms={"bluesky"})
    ok("bluesky was NOT re-attempted", "bluesky" not in calls2, calls2)
    ok("x WAS retried", calls2 == ["x"], calls2)
    ok("still reports failure", code2 == 1, "exit %s" % code2)
    ok("the ledger still holds exactly one platform",
       list((load(path).get("posted") or {}).keys()) == ["bluesky"])

    # ------------------------------------------------------------------
    print("once the last platform succeeds the draft closes out")
    code3, calls3 = run(q, ok_platforms={"bluesky", "x"})
    d3 = load(path)
    ok("only the outstanding platform was called", calls3 == ["x"], calls3)
    ok("both platforms are now in the ledger",
       sorted((d3.get("posted") or {}).keys()) == ["bluesky", "x"])
    ok("posted_at is set", bool(d3.get("posted_at")), d3.get("posted_at"))
    ok("the run reports success", code3 == 0, "exit %s" % code3)

    # ------------------------------------------------------------------
    print("a completed draft is inert")
    code4, calls4 = run(q, ok_platforms={"bluesky", "x"})
    ok("nothing was posted at all", calls4 == [], calls4)
    ok("exit 0", code4 == 0, "exit %s" % code4)

    # ------------------------------------------------------------------
    print("an interrupted-but-complete draft closes out without re-posting")
    q2 = tmp / "orphan"
    q2.mkdir()
    p2 = make_draft(q2)
    d2 = load(p2)
    # Simulate: every platform posted, then the process died before the stamp.
    d2["posted"] = {p: {"at": "2026-08-24T00:00:00+00:00", "detail": "200",
                        "copy_sha256_12": postsyn.copy_digest(d2["copy"][p])}
                    for p in d2["copy"]}
    p2.write_text(json.dumps(d2, indent=2) + "\n", encoding="utf-8")

    code5, calls5 = run(q2, ok_platforms={"bluesky", "x"})
    ok("nothing re-posted", calls5 == [], calls5)
    ok("posted_at was filled in", bool(load(p2).get("posted_at")))

    # ------------------------------------------------------------------
    print("approval is still the gate")
    q3 = tmp / "unapproved"
    q3.mkdir()
    p3 = make_draft(q3, approved=False)
    code6, calls6 = run(q3, ok_platforms={"bluesky", "x"})
    ok("an unapproved draft is never posted", calls6 == [], calls6)
    ok("and gains no ledger", "posted" not in load(p3), load(p3).get("posted"))

    # ------------------------------------------------------------------
    print("a dry run writes nothing")
    q4 = tmp / "dry"
    q4.mkdir()
    p4 = make_draft(q4)
    import os
    os.environ["DRY_RUN"] = "true"
    real_post_one, real_queue = postsyn.post_one, postsyn.QUEUE
    dry_calls = []

    def dry_stub(base_url, token, platform, draft, dry_run):
        dry_calls.append((platform, dry_run))
        return True, "dry-run"

    postsyn.post_one, postsyn.QUEUE = dry_stub, q4
    try:
        postsyn.main()
    finally:
        postsyn.post_one, postsyn.QUEUE = real_post_one, real_queue
    ok("the dry run was told it is a dry run",
       all(dry for _, dry in dry_calls) and len(dry_calls) == 2, dry_calls)
    ok("no ledger was written", "posted" not in load(p4), load(p4).get("posted"))
    ok("no posted_at was written", not load(p4).get("posted_at"))

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Both of these were found by an adversarial review AFTER the first version
    # of this file passed 24/24. Each reaches a real POST and then fails to
    # record it, which is the exact defect the ledger exists to prevent --
    # arriving through the one field the quickstart asks a human to hand-edit.
    print("a hand-mangled `posted` must not reach a POST at all")
    q6 = tmp / "bad-ledger"
    q6.mkdir()
    for bad, label in (([u"bluesky"], "a list"), (u"bluesky", "a string"),
                       (5, "a number")):
        p6 = make_draft(q6, name="draft.json")
        d6 = load(p6)
        d6["posted"] = bad
        p6.write_text(json.dumps(d6, indent=2) + "\n", encoding="utf-8")
        code, calls = run(q6, ok_platforms={"bluesky", "x"})
        ok("`posted` as %s: nothing was posted" % label, calls == [], calls)
        ok("`posted` as %s: run reports failure" % label, code == 1,
           "exit %s" % code)
        ok("`posted` as %s: the draft was not stamped" % label,
           not load(p6).get("posted_at"), load(p6).get("posted_at"))

    print("an approved draft with no platforms is refused, not stamped")
    q7 = tmp / "no-platforms"
    q7.mkdir()
    p7 = make_draft(q7)
    d7 = load(p7)
    d7["copy"] = {}
    p7.write_text(json.dumps(d7, indent=2) + "\n", encoding="utf-8")
    code7, calls7 = run(q7, ok_platforms={"bluesky", "x"})
    ok("nothing was posted", calls7 == [], calls7)
    ok("it was NOT marked complete", not load(p7).get("posted_at"),
       load(p7).get("posted_at"))
    ok("the run reports failure rather than success", code7 == 1,
       "exit %s" % code7)

    print("the limit of the fix, asserted rather than assumed")
    # A draft part-posted under the OLD code is on disk with no `posted` key and
    # no `posted_at` -- byte-identical to a draft that has never run. Nothing can
    # recover the difference, so the new guard CANNOT protect it: the first run
    # after this change will re-post platforms the old code already sent.
    #
    # Asserted here rather than left as a comment, because it is the one case
    # where the guard does not hold and somebody will otherwise trust it to.
    # The remedy is procedural and lives in the quickstart doc: check each
    # draft's `posted` ledger before the first live run after this change.
    q5 = tmp / "legacy-state"
    q5.mkdir()
    p5 = make_draft(q5)          # no `posted`, no `posted_at` -- the legacy shape
    code7, calls7 = run(q5, ok_platforms={"bluesky", "x"})
    ok("a legacy part-posted draft is indistinguishable from a fresh one, "
       "and IS posted again", sorted(calls7) == ["bluesky", "x"], calls7)

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("")
print("%d passed, %d failed" % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
