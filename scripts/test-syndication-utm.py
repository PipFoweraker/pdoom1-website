#!/usr/bin/env python
"""Assert that nothing can be posted with an untagged link.

    python scripts/test-syndication-utm.py     (exit 0 = pass)

WHY THIS EXISTS
---------------
content/campaigns/README.md states the rule and the reason:

    Plausible groups traffic by utm_source / utm_medium / utm_campaign, and
    public/index.html (attributionProps()) copies them onto the Download event
    -- the download button leaves for github.com, so that click is the *only*
    place a download can ever be joined to the channel that produced it.

    Post a link without UTMs and that attribution is gone permanently. There is
    no way to reconstruct it afterwards.

Until 2026-08-22 prepare-syndication.py emitted a BARE url into every platform's
copy, so every draft in the queue violated that rule. Nothing had been posted --
all four drafts sat at approved:false and posted_at:null -- so nothing was
actually lost. The first post out of this pipeline would have been the loss, and
it would have been silent and unrecoverable.

That is the shape this file exists to stop: a defect whose only symptom appears
after the irreversible act.

WHAT IS CHECKED, AND WHY EACH
-----------------------------
1. The generator tags every platform it can generate for. Checked against the
   live UTM_SOURCE table, not a copy of it, so adding a platform without a
   source value fails here rather than posting an untagged link.
2. utm_source spellings are the ones the campaign table already agreed. The
   README's warning is specific: "Never reuse a utm_source value with different
   spelling (twitter vs x vs Twitter become three separate rows that never
   re-merge)."
3. Campaign slugs are unique per post. Five dates in the blog index carry two or
   three posts each, so a date-only slug would report two campaigns as one.
4. Slugs never truncate mid-word and stay within the cap.
5. Every draft ON DISK is tagged and within its platform limit -- because a
   correct generator does not help if a stale untagged draft is still sitting in
   the queue waiting to be approved.
6. The canonical `url` field stays UNTAGGED. It is the address of the post, not
   a channel-specific link, and tagging it would put a bluesky source on a link
   nobody clicked from bluesky.
"""

import importlib.util
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content" / "syndication"
BLOG_INDEX = ROOT / "public" / "blog" / "index.json"

_spec = importlib.util.spec_from_file_location(
    "prep", ROOT / "scripts" / "prepare-syndication.py")
prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prep)

FAILURES = []
CHECKS = [0]


def check(cond, msg):
    CHECKS[0] += 1
    print("  %s  %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        FAILURES.append(msg)


def main():
    print("syndication: no link leaves untagged\n")
    posts = json.loads(BLOG_INDEX.read_text(encoding="utf-8"))["posts"]

    # -- 1. the generator tags every platform it knows about ----------------
    print("1. every platform the generator can emit gets a tagged link")
    sample = posts[0]
    for platform in prep.LIMITS:
        text = prep.draft_copy(sample, platform)
        check("utm_source=" in text, "%s: copy carries utm_source" % platform)
        check("utm_medium=social" in text, "%s: copy carries utm_medium" % platform)
        check("utm_campaign=" in text, "%s: copy carries utm_campaign" % platform)

    # -- 2. FORCED: an untagged url is what the old code produced -----------
    print("\n2. FORCED: the untagged form is still reachable, and is not what ships")
    bare = prep.post_url(sample["filename"])
    check("utm_" not in bare,
          "post_url() with no platform returns a bare url (the pre-fix behaviour)")
    tagged = prep.post_url(sample["filename"], "bluesky")
    check(tagged != bare and "utm_source=bluesky" in tagged,
          "post_url(..., 'bluesky') differs and carries the source")

    # -- 3. agreed spellings, never a new one -------------------------------
    print("\n3. utm_source values are the ones the campaign table agreed")
    agreed = {"bluesky", "twitter", "linkedin", "discord", "facebook", "instagram"}
    for platform, source in prep.UTM_SOURCE.items():
        check(source in agreed,
              "%s -> %r is an agreed spelling" % (platform, source))
        check(source == source.lower() and " " not in source,
              "%s -> %r is lowercase and space-free" % (platform, source))
    missing = set(prep.LIMITS) - set(prep.UTM_SOURCE)
    check(not missing,
          "every platform with a length limit has a utm_source (missing: %s)"
          % (sorted(missing) or "none"))

    # -- 4. slugs identify a post, not a day --------------------------------
    print("\n4. campaign slugs are unique per post and word-clean")
    slugs = [prep.campaign_slug(p["filename"]) for p in posts]
    check(len(set(slugs)) == len(slugs),
          "unique across all %d posts (%d distinct)" % (len(posts), len(set(slugs))))
    check(max(len(s) for s in slugs) <= prep.CAMPAIGN_SLUG_MAX,
          "none exceeds the %d-char cap" % prep.CAMPAIGN_SLUG_MAX)
    long_stem = "2026-08-15-1313-tests-passed-and-the-game-had-no-buttons.md"
    slug = prep.campaign_slug(long_stem)
    check(all(w in long_stem.replace(".md", "").split("-") or w == "blog"
              for w in slug.split("-")),
          "a long title truncates on a word boundary, never mid-word: %r" % slug)

    # -- 5. the QUEUE, not just the generator -------------------------------
    print("\n5. every draft on disk is tagged and within its limit")
    drafts = sorted(QUEUE.glob("*.json"))
    check(bool(drafts), "there is at least one draft to check")
    for f in drafts:
        d = json.loads(f.read_text(encoding="utf-8"))
        for platform, text in (d.get("copy") or {}).items():
            check("utm_source=%s" % prep.UTM_SOURCE.get(platform, "?") in text,
                  "%s / %s: tagged with the right source" % (f.stem[:34], platform))
            limit = prep.LIMITS.get(platform)
            check(limit is None or len(text) <= limit,
                  "%s / %s: %d chars within %s" % (f.stem[:34], platform, len(text), limit))

    # -- 6. the canonical url stays clean -----------------------------------
    print("\n6. the draft's canonical url field is NOT tagged")
    for f in drafts:
        d = json.loads(f.read_text(encoding="utf-8"))
        check("utm_" not in (d.get("url") or ""),
              "%s: url field is the plain address" % f.stem[:40])

    print("\n%d checks, %d failed" % (CHECKS[0], len(FAILURES)))
    if FAILURES:
        for f in FAILURES:
            print("  FAILED: %s" % f)
        return 1
    print("OK: nothing in the queue can be posted with an untagged link.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
