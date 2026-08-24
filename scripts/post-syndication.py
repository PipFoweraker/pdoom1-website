#!/usr/bin/env python
"""Post approved syndication drafts. Posts nothing that a human has not approved.

This is the OUTBOUND half of the gate. It never composes copy -- it sends
exactly the text in content/syndication/<slug>.json, which a person wrote or
edited and explicitly marked approved.

Refuses to act when:
  - approved is not literally true
  - the platform is already recorded in draft["posted"] (see below)
  - posted_at is already set (the whole draft is done)
  - the copy fails the same length/URL validation used at draft time
  - SYNDICATION_TOKEN is missing (the endpoints would 401 anyway)

WHAT "ALREADY POSTED" MEANS, AND WHY IT IS PER PLATFORM
------------------------------------------------------
This used to record `posted_at` only when EVERY platform in the draft
succeeded. One draft lists four platforms, and the realistic first live run has
exactly one credential configured, so three endpoints return 500 "credentials
not configured", the run is not all-ok, and NOTHING was written down -- while a
real post had already appeared on Bluesky. Re-running then posted it a second
time. The docstring above claimed "prevents double-posting on a re-run" the
whole time, and it was true only of a run in which nothing had gone wrong.

So success is now recorded per platform, in `draft["posted"]`, and written to
disk immediately after each one rather than at the end of the draft. A crash,
a timeout or a missing credential can therefore cost a retry but never a
duplicate. `posted_at` still marks the whole draft and is set once every
platform in `copy` is present in `posted`, so anything reading it -- the queue
listing, the workflow -- keeps its old meaning.

Each ledger entry carries a hash of the exact text that went out. If someone
edits the copy after a partial post, the record still says what was published,
rather than what the file says today.

Set DRY_RUN=false to actually post. Anything else, including unset, is a dry run
-- an accidental invocation must not put words into the world.

Env:
    SYNDICATION_TOKEN   shared secret; must match the Netlify site env
    NETLIFY_SITE_URL    e.g. https://pdoom1-website-app.netlify.app
    DRY_RUN             "false" to post; otherwise dry run
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
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
QUEUE = REPO_ROOT / "content" / "syndication"

# prepare-syndication.py has a hyphen in its name, so it cannot be imported
# normally. Reusing its validate() rather than reimplementing means the checks
# applied at approval time are byte-for-byte the ones applied at post time.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prep", REPO_ROOT / "scripts" / "prepare-syndication.py")
prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prep)


def copy_digest(text):
    """Short hash of the exact text sent, so the ledger records what went out."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def write_draft(path, draft):
    """Persist immediately. Called after EVERY successful platform, not once per
    draft -- the whole point of the ledger is that an interrupted run has already
    been written down."""
    path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def post_one(base_url, token, platform, draft, dry_run):
    url = "%s/.netlify/functions/syndicate-%s" % (base_url.rstrip("/"), platform)
    payload = {
        "title": draft["title"],
        "text": draft["copy"][platform],
        "url": draft["url"],
    }
    if dry_run:
        print("    DRY RUN -> would POST to %s" % url)
        return True, "dry-run"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-syndication-token": token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, "%s %s" % (r.status, r.read().decode("utf-8")[:120])
    except urllib.error.HTTPError as e:
        return False, "HTTP %s %s" % (e.code, e.read().decode("utf-8")[:160])
    except Exception as e:
        return False, str(e)


def main():
    dry_run = os.environ.get("DRY_RUN", "true").lower() != "false"
    token = os.environ.get("SYNDICATION_TOKEN", "")
    base = os.environ.get("NETLIFY_SITE_URL", "").strip()

    if not QUEUE.exists():
        print("No syndication queue; nothing to do.")
        return 0

    drafts = sorted(QUEUE.glob("*.json"))
    if not drafts:
        print("Queue is empty; nothing to do.")
        return 0

    if not dry_run:
        missing = [n for n, v in (("SYNDICATION_TOKEN", token),
                                  ("NETLIFY_SITE_URL", base)) if not v]
        if missing:
            print("ERROR: %s not set. Refusing to post." % ", ".join(missing),
                  file=sys.stderr)
            return 2

    print("Mode: %s\n" % ("DRY RUN (nothing will be posted)" if dry_run else "LIVE"))

    posted_any = False
    considered = 0
    failures = 0

    for path in drafts:
        draft = json.loads(path.read_text(encoding="utf-8"))
        name = path.name

        if draft.get("posted_at"):
            continue
        if draft.get("approved") is not True:
            print("%s: awaiting approval - skipped" % name)
            continue

        problems = prep.validate(draft)
        if problems:
            print("%s: APPROVED BUT INVALID - not posted" % name, file=sys.stderr)
            for p in problems:
                print("    - %s" % p, file=sys.stderr)
            failures += 1
            continue

        platforms = list(draft.get("copy") or {})

        # An approved draft with no platforms would fall straight through to the
        # "all platforms already posted" branch below and be stamped posted_at
        # having sent nothing -- a draft permanently marked as sent, which is
        # the same lie as a double-post pointing the other way. prep.validate()
        # cannot catch it: it iterates `copy`, so an empty one has no problems.
        # The quickstart tells a human to DELETE platforms from `copy` before the
        # first live run, so deleting all of them is a live path, not a theory.
        if not platforms:
            print("%s: APPROVED BUT HAS NO PLATFORMS - not posted, not stamped"
                  % name, file=sys.stderr)
            failures += 1
            continue

        ledger = draft.get("posted") or {}
        # Type, not just presence. `ledger[platform] = ...` below happens AFTER a
        # successful POST, so a hand-edited `"posted": ["bluesky"]` raised
        # TypeError with the post already sent and nothing written down -- and
        # the next run sent it again. That is precisely the defect this ledger
        # exists to prevent, reachable through the one field the quickstart asks
        # a human to go and inspect by hand.
        if not isinstance(ledger, dict):
            print("%s: `posted` is %s, not an object - refusing to touch this "
                  "draft. Fix it by hand (an object keyed by platform) or "
                  "remove it." % (name, type(ledger).__name__), file=sys.stderr)
            failures += 1
            continue

        todo = [p for p in platforms if p not in ledger]

        if not todo:
            # Every platform is already in the ledger -- a previous run finished
            # the job but was interrupted before it could stamp the draft as a
            # whole. Close it out rather than leaving a draft that looks pending
            # forever and invites somebody to "just re-run it".
            if not dry_run and not draft.get("posted_at"):
                draft["posted_at"] = datetime.now(timezone.utc).replace(
                    microsecond=0).isoformat()
                write_draft(path, draft)
                print("%s: all platforms already posted - marked complete" % name)
            else:
                print("%s: all platforms already posted - nothing to do" % name)
            continue

        considered += 1
        already = len(platforms) - len(todo)
        print("%s: approved, posting to %d platform(s)%s"
              % (name, len(todo),
                 " (%d already posted, skipped)" % already if already else ""))

        results = {}
        all_ok = True
        for platform in todo:
            ok, detail = post_one(base, token, platform, draft, dry_run)
            results[platform] = detail
            print("    %-9s %s  %s" % (platform, "OK " if ok else "FAIL", detail))
            if not ok:
                all_ok = False
                continue
            if dry_run:
                continue
            # Written to disk NOW. If the next platform hangs or the runner is
            # killed, this one is still recorded and will not be sent again.
            ledger[platform] = {
                "at": datetime.now(timezone.utc).replace(
                    microsecond=0).isoformat(),
                "detail": detail,
                "copy_sha256_12": copy_digest(draft["copy"][platform]),
            }
            draft["posted"] = ledger
            write_draft(path, draft)
            posted_any = True

        if not dry_run and all(p in ledger for p in platforms):
            draft["posted_at"] = datetime.now(timezone.utc).replace(
                microsecond=0).isoformat()
            draft["post_results"] = results
            write_draft(path, draft)
        if not all_ok:
            failures += 1

    if considered == 0 and not failures:
        print("\nNothing approved and unposted.")
    elif dry_run and considered:
        print("\n%d draft(s) would be posted. Re-run the workflow with "
              "publish=true to send them." % considered)
    elif posted_any:
        # Deliberately counts drafts ATTEMPTED, and says so, because a draft can
        # now be part-posted. "Posted 1 draft" over a run where three of four
        # platforms 500'd is the reassuring-value-instead-of-the-truth shape.
        print("\n%d draft(s) attempted; see the per-platform lines above and "
              "the `posted` ledger in each file for what actually went out."
              % considered)
    if failures:
        print("\n%d draft(s) failed." % failures, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
