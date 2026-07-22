#!/usr/bin/env python
"""Draft social copy for a blog post, for a human to edit and approve.

THE PRINCIPLE THIS IMPLEMENTS
-----------------------------
Inbound automation, outbound human gate. Syncing content INTO the site can be
fully automatic; publishing words OUT into the world is a decision a person
makes. The system gets it ready; Pip owns every word that points outward, and
therefore owns the tone, the framing, and any mistakes.

So this does NOT post anything. It writes a draft file that a human edits and
explicitly approves. Posting is a separate, deliberate act.

THE FLOW
--------
  1. A post lands in public/blog/       -> CI runs this and commits a draft
  2. content/syndication/<slug>.json    -> you edit the copy, set approved: true
  3. Manual workflow dispatch           -> posts exactly what the file says
  4. posted_at is written back          -> so nothing can be posted twice

Because the draft is a committed file, git history is the audit trail of exactly
what went out, when, and who approved it.

Usage:
    python scripts/prepare-syndication.py --post 2026-07-15-ui-before-snapshot.md
    python scripts/prepare-syndication.py --latest
    python scripts/prepare-syndication.py --list
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BLOG_INDEX = REPO_ROOT / "public" / "blog" / "index.json"
QUEUE = REPO_ROOT / "content" / "syndication"
SITE = "https://pdoom1.com"

# Hard platform limits. Copy longer than this is rejected at approval time
# rather than silently truncated -- truncation used to eat the trailing URL,
# which is the one part of the post that has to survive.
LIMITS = {
    "bluesky": 300,
    "x": 280,
    "linkedin": 3000,
    "discord": 2000,
}


def post_url(filename):
    return "%s/blog/post.html?p=%s" % (SITE, filename)


def load_posts():
    data = json.loads(BLOG_INDEX.read_text(encoding="utf-8"))
    return data["posts"] if isinstance(data, dict) else data


def draft_copy(post, platform):
    """A starting point, not a finished post. Deliberately plain: the human is
    expected to rewrite this, and bland copy invites editing more than clever
    copy does."""
    title = post["title"]
    summary = post.get("summary", "").strip()
    url = post_url(post["filename"])
    tags = post.get("tags") or []

    if platform in ("bluesky", "x"):
        limit = LIMITS[platform]
        # Reserve room for the URL and the separating newlines, so the link can
        # never be the thing that gets cut.
        room = limit - len(url) - 2
        body = title if len(title) <= room else title[:room - 1].rstrip() + "…"
        if summary and len(body) + 2 + len(summary) <= room:
            body = "%s\n\n%s" % (body, summary)
        return "%s\n\n%s" % (body, url)

    if platform == "linkedin":
        hashtags = " ".join("#" + str(t).replace("-", "") for t in tags[:5])
        parts = [title]
        if summary:
            parts.append(summary)
        parts.append(url)
        if hashtags:
            parts.append(hashtags)
        return "\n\n".join(parts)

    # discord
    parts = ["**%s**" % title]
    if summary:
        parts.append(summary)
    parts.append(url)
    return "\n\n".join(parts)


def build_draft(post):
    return {
        "_README": (
            "Edit the copy below, then set approved to true and commit. "
            "Nothing is posted until you do. Delete a platform's entry to skip it."
        ),
        "post": post["filename"],
        "title": post["title"],
        "url": post_url(post["filename"]),
        "approved": False,
        "posted_at": None,
        "copy": {p: draft_copy(post, p) for p in ("bluesky", "x", "linkedin", "discord")},
    }


def validate(draft):
    """Return a list of problems. Called here and again before posting."""
    problems = []
    for platform, text in (draft.get("copy") or {}).items():
        limit = LIMITS.get(platform)
        if limit is None:
            problems.append("unknown platform %r" % platform)
            continue
        if not str(text).strip():
            problems.append("%s: copy is empty" % platform)
            continue
        if len(text) > limit:
            problems.append("%s: %d chars, limit %d (over by %d)"
                            % (platform, len(text), limit, len(text) - limit))
        if draft.get("url") and draft["url"] not in text:
            problems.append("%s: the post URL is missing from the copy" % platform)
    return problems


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--post", help="blog post filename")
    g.add_argument("--latest", action="store_true", help="most recent post")
    g.add_argument("--list", action="store_true", help="show the queue")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing draft (loses your edits)")
    args = ap.parse_args()

    if args.list:
        if not QUEUE.exists():
            print("No syndication drafts yet.")
            return 0
        rows = []
        for f in sorted(QUEUE.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            state = ("POSTED %s" % d["posted_at"][:10]) if d.get("posted_at") \
                else ("APPROVED - not yet posted" if d.get("approved")
                      else "draft, awaiting your approval")
            rows.append((f.name, state))
        print("%-52s %s" % ("draft", "state"))
        print("-" * 90)
        for name, state in rows:
            print("%-52s %s" % (name, state))
        return 0

    posts = load_posts()
    if args.latest:
        post = posts[0]
    else:
        matches = [p for p in posts if p["filename"] == args.post]
        if not matches:
            print("ERROR: %r is not in the blog index. Publishable posts:"
                  % args.post, file=sys.stderr)
            for p in posts[:5]:
                print("  %s" % p["filename"], file=sys.stderr)
            return 2
        post = matches[0]

    QUEUE.mkdir(parents=True, exist_ok=True)
    out = QUEUE / (post["filename"].replace(".md", "") + ".json")

    if out.exists() and not args.force:
        existing = json.loads(out.read_text(encoding="utf-8"))
        if existing.get("posted_at"):
            print("Already posted on %s - not regenerating." % existing["posted_at"])
        else:
            print("Draft already exists (with your edits): %s"
                  % out.relative_to(REPO_ROOT))
            print("Pass --force to discard it and regenerate.")
        return 0

    draft = build_draft(post)
    out.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")

    print("Drafted %s" % out.relative_to(REPO_ROOT))
    print()
    for platform, text in draft["copy"].items():
        print("--- %s (%d/%d chars) ---" % (platform, len(text), LIMITS[platform]))
        print(text)
        print()
    problems = validate(draft)
    if problems:
        print("Problems to fix before approving:")
        for p in problems:
            print("  - %s" % p)
    print("Next: edit the copy, set \"approved\": true, commit. "
          "Nothing posts until you do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
