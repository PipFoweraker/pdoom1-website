#!/usr/bin/env python
"""Generate public/blog/index.json from the posts' own front matter, and refuse
to publish anything the site cannot actually render.

WHY
---
index.json was hand-maintained. Predictable consequences, all of which were live
at once: an entry pointing at a file that did not exist (a clickable card on the
blog leading to a 404), ten .md files on disk that no entry referenced (so
unreachable), and no check that a post only used markdown the renderer supports.

Front matter is now the single source of truth. A post carries its own metadata;
this derives the index from it. Editing index.json by hand is no longer a thing
anyone should do.

WHAT IT REFUSES TO PUBLISH
--------------------------
public/blog/post.html ships a small hand-written markdown parser. It supports
headings, paragraphs, lists, fenced code, blockquotes, hr, links, images, inline
code, bold and italic. It does NOT support tables, and it flattens nested lists.
A post using a table renders literal pipe characters at the reader. So this
fails the build rather than shipping it -- the whole point is that nobody has to
remember the parser's limits.

DRAFTS
------
`draft: true` in front matter keeps a post out of the index (and therefore out
of the feed). That is how a post exists in the repo without being published:
publishing is a deliberate act, not a side effect of adding a file.

Usage:
    python scripts/build-blog-index.py            # write index.json
    python scripts/build-blog-index.py --check    # exit 1 if stale or invalid
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. pip install --user PyYAML", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[1]
BLOG_DIR = REPO_ROOT / "public" / "blog"
INDEX = BLOG_DIR / "index.json"

REQUIRED = ("title", "date", "summary")
FM_FENCE = re.compile(r"^\s*---\s*$")

# Constructs public/blog/post.html mishandles. Keep in step with that file --
# scripts/test-blog-render.js pins the table case against the real renderer.
#
# The severity split is calibrated against the existing corpus, not guessed:
# BLOCKING means the reader sees corrupted output (literal pipe characters,
# escaped tags). WARNING means the post degrades but stays readable. Twelve of
# the twenty-one existing posts use nested lists; blocking on those would have
# made the validator unusable on day one, and a validator everyone bypasses
# protects nothing.
BLOCKING = [
    (re.compile(r"^\s*\|.*\|\s*$", re.M), "table",
     "post.html has no table support; it renders literal | characters"),
    (re.compile(r"^\s*<(?!!--)[a-zA-Z]", re.M), "raw HTML block",
     "post.html escapes raw HTML rather than rendering it"),
]

WARNING = [
    (re.compile(r"^\s{2,}[-*+]\s", re.M), "nested list",
     "post.html flattens nested lists to one level"),
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def split_front_matter(text):
    """Return (front_matter_dict_or_None, body, error_or_None)."""
    text = text.replace("﻿", "")
    lines = text.split("\n")
    if not lines or not FM_FENCE.match(lines[0]):
        return None, text, None
    for i in range(1, len(lines)):
        if FM_FENCE.match(lines[i]):
            raw = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:]).lstrip("\n")
            try:
                data = yaml.safe_load(raw) or {}
            except yaml.YAMLError as exc:
                return None, body, "invalid YAML front matter: %s" % exc
            if not isinstance(data, dict):
                return None, body, "front matter is not a mapping"
            return data, body, None
    return None, text, "front matter opened with --- but never closed"


def collect():
    posts, problems, drafts, warnings = [], [], [], []

    for path in sorted(BLOG_DIR.glob("*.md")):
        name = path.name
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body, err = split_front_matter(text)

        if err:
            problems.append((name, err))
            continue
        if fm is None:
            problems.append((name, "no front matter (needs a --- block with %s)"
                             % ", ".join(REQUIRED)))
            continue
        if fm.get("draft") is True:
            drafts.append(name)
            continue

        missing = [k for k in REQUIRED if not fm.get(k)]
        if missing:
            problems.append((name, "front matter missing: %s" % ", ".join(missing)))
            continue

        date = str(fm["date"]).strip()
        if not DATE_RE.match(date):
            problems.append((name, "date %r is not YYYY-MM-DD" % date))
            continue

        blocked = False
        for pattern, label, why in BLOCKING:
            m = pattern.search(body)
            if m:
                problems.append((name, "uses a %s -- %s (line %d)"
                                 % (label, why, body[:m.start()].count("\n") + 1)))
                blocked = True
                break
        if blocked:
            continue

        for pattern, label, why in WARNING:
            m = pattern.search(body)
            if m:
                warnings.append((name, "%s -- %s (line %d)"
                                 % (label, why, body[:m.start()].count("\n") + 1)))
                break

        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        posts.append({
            "filename": name,
            "title": str(fm["title"]).strip(),
            "date": date,
            "tags": [str(t) for t in tags],
            "summary": str(fm["summary"]).strip(),
            "commit": str(fm.get("commit", "")).strip(),
            "featured": bool(fm.get("featured", False)),
        })

    posts.sort(key=lambda p: (p["date"], p["filename"]), reverse=True)
    return posts, problems, drafts, warnings


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if index.json is stale or any post is invalid")
    args = ap.parse_args()

    posts, problems, drafts, warnings = collect()

    if drafts:
        print("Drafts (not published): %s" % ", ".join(drafts))
    for name, why in warnings:
        print("  warning: %-52s %s" % (name, why))
    if problems:
        print("\n%d post(s) cannot be published:" % len(problems), file=sys.stderr)
        for name, why in problems:
            print("  %-58s %s" % (name, why), file=sys.stderr)
        print("\nFix the front matter, or set `draft: true` to hold a post back.",
              file=sys.stderr)
        return 1

    if not posts:
        print("ERROR: no publishable posts found", file=sys.stderr)
        return 2

    content = json.dumps({"posts": posts}, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        current = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
        if current != content:
            print("STALE: index.json does not match the posts on disk.\n"
                  "Run: python scripts/build-blog-index.py", file=sys.stderr)
            return 1
        print("OK: index.json matches %d post(s) on disk" % len(posts))
        return 0

    INDEX.write_text(content, encoding="utf-8", newline="\n")
    print("Wrote %s (%d posts, newest %s)"
          % (INDEX.relative_to(REPO_ROOT), len(posts), posts[0]["date"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
