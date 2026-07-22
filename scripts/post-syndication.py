#!/usr/bin/env python
"""Post approved syndication drafts. Posts nothing that a human has not approved.

This is the OUTBOUND half of the gate. It never composes copy -- it sends
exactly the text in content/syndication/<slug>.json, which a person wrote or
edited and explicitly marked approved.

Refuses to act when:
  - approved is not literally true
  - posted_at is already set (prevents double-posting on a re-run)
  - the copy fails the same length/URL validation used at draft time
  - SYNDICATION_TOKEN is missing (the endpoints would 401 anyway)

Set DRY_RUN=false to actually post. Anything else, including unset, is a dry run
-- an accidental invocation must not put words into the world.

Env:
    SYNDICATION_TOKEN   shared secret; must match the Netlify site env
    NETLIFY_SITE_URL    e.g. https://pdoom1-website-app.netlify.app
    DRY_RUN             "false" to post; otherwise dry run
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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

        considered += 1
        print("%s: approved, posting to %d platform(s)"
              % (name, len(draft.get("copy") or {})))
        results = {}
        all_ok = True
        for platform in list(draft.get("copy") or {}):
            ok, detail = post_one(base, token, platform, draft, dry_run)
            results[platform] = detail
            print("    %-9s %s  %s" % (platform, "OK " if ok else "FAIL", detail))
            if not ok:
                all_ok = False

        if all_ok and not dry_run:
            draft["posted_at"] = datetime.now(timezone.utc).replace(
                microsecond=0).isoformat()
            draft["post_results"] = results
            path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
            posted_any = True
        elif not all_ok:
            failures += 1

    if considered == 0 and not failures:
        print("\nNothing approved and unposted.")
    elif dry_run and considered:
        print("\n%d draft(s) would be posted. Re-run the workflow with "
              "publish=true to send them." % considered)
    elif posted_any:
        print("\nPosted %d draft(s)." % considered)
    if failures:
        print("\n%d draft(s) failed." % failures, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
