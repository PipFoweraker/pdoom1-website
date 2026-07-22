#!/usr/bin/env python
"""Generate RSS 2.0 and Atom feeds for the dev blog.

WHY A FEED RATHER THAN AN EMAIL LIST
------------------------------------
People asked to be able to follow updates. A feed is the privacy-first answer:
it collects nothing, stores nothing, requires no account, needs no consent
banner, and cannot leak a subscriber list because there isn't one. Readers pull;
we never push. An opt-in email list can come later if feeds prove insufficient,
but it should not be the FIRST thing tried, because it is the option that
creates a database of people's contact details.

The feed is generated from public/blog/index.json, the same file the blog index
page renders from, so a post cannot appear in one and not the other.

Usage:
    python scripts/generate-feeds.py           # write the feeds
    python scripts/generate-feeds.py --check   # exit 1 if they are stale (CI)
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[1]
BLOG_DIR = REPO_ROOT / "public" / "blog"
INDEX = BLOG_DIR / "index.json"
RSS_OUT = REPO_ROOT / "public" / "blog" / "feed.xml"
ATOM_OUT = REPO_ROOT / "public" / "blog" / "atom.xml"

SITE = "https://pdoom1.com"
TITLE = "p(Doom)1 dev blog"
DESCRIPTION = ("Development notes from p(Doom)1 - a satirical strategy game "
               "about managing an AI safety lab.")
LANG = "en-AU"


def post_url(filename):
    """Posts are rendered client-side by post.html, so the canonical reader URL
    carries the filename as a query parameter."""
    return "%s/blog/post.html?p=%s" % (SITE, filename)


def parse_date(value):
    """Blog dates are plain YYYY-MM-DD. Treat them as midday UTC so that a
    timezone shift can never move a post to the previous or next day."""
    try:
        d = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        return d.replace(hour=12, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def load_posts():
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    posts = data["posts"] if isinstance(data, dict) and "posts" in data else data

    out, skipped = [], []
    for p in posts:
        fn = p.get("filename")
        if not fn:
            skipped.append((p.get("title", "?"), "no filename"))
            continue
        # A feed entry pointing at a missing post is worse than no entry --
        # subscribers get a dead link pushed at them. index.json has held a
        # dangling filename before, so this is checked rather than assumed.
        if not (BLOG_DIR / fn).exists():
            skipped.append((fn, "file missing on disk"))
            continue
        when = parse_date(p.get("date"))
        if when is None:
            skipped.append((fn, "unparseable date %r" % p.get("date")))
            continue
        out.append({
            "filename": fn,
            "title": p.get("title") or fn,
            "date": when,
            "summary": (p.get("summary") or "").strip(),
            "tags": p.get("tags") or [],
            "url": post_url(fn),
        })

    out.sort(key=lambda p: p["date"], reverse=True)
    return out, skipped


def build_rss(posts, built):
    items = []
    for p in posts:
        cats = "".join("\n      <category>%s</category>" % escape(str(t))
                       for t in p["tags"])
        items.append(
            "    <item>\n"
            "      <title>%s</title>\n"
            "      <link>%s</link>\n"
            "      <guid isPermaLink=\"false\">%s</guid>\n"
            "      <pubDate>%s</pubDate>\n"
            "      <description>%s</description>%s\n"
            "    </item>"
            % (escape(p["title"]), escape(p["url"]),
               escape("pdoom1-blog-" + p["filename"]),
               format_datetime(p["date"]), escape(p["summary"]), cats))

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '  <channel>\n'
        '    <title>%s</title>\n'
        '    <link>%s/blog/</link>\n'
        '    <description>%s</description>\n'
        '    <language>%s</language>\n'
        '    <lastBuildDate>%s</lastBuildDate>\n'
        '    <atom:link href="%s/blog/feed.xml" rel="self" type="application/rss+xml" />\n'
        '%s\n'
        '  </channel>\n'
        '</rss>\n'
        % (escape(TITLE), SITE, escape(DESCRIPTION), LANG,
           format_datetime(built), SITE, "\n".join(items)))


def build_atom(posts, built):
    entries = []
    for p in posts:
        cats = "".join("\n    <category term=\"%s\" />" % escape(str(t))
                       for t in p["tags"])
        entries.append(
            "  <entry>\n"
            "    <title>%s</title>\n"
            "    <link href=\"%s\" />\n"
            "    <id>urn:pdoom1:blog:%s</id>\n"
            "    <updated>%s</updated>\n"
            "    <summary>%s</summary>%s\n"
            "  </entry>"
            % (escape(p["title"]), escape(p["url"]),
               escape(p["filename"]),
               p["date"].strftime("%Y-%m-%dT%H:%M:%SZ"),
               escape(p["summary"]), cats))

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="%s">\n'
        '  <title>%s</title>\n'
        '  <link href="%s/blog/" />\n'
        '  <link href="%s/blog/atom.xml" rel="self" />\n'
        '  <id>urn:pdoom1:blog</id>\n'
        '  <updated>%s</updated>\n'
        '  <subtitle>%s</subtitle>\n'
        '%s\n'
        '</feed>\n'
        % (LANG, escape(TITLE), SITE, SITE,
           built.strftime("%Y-%m-%dT%H:%M:%SZ"), escape(DESCRIPTION),
           "\n".join(entries)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed feeds are stale; write nothing")
    args = ap.parse_args()

    posts, skipped = load_posts()
    if not posts:
        print("ERROR: no publishable posts found in %s" % INDEX, file=sys.stderr)
        return 2

    # lastBuildDate is derived from the newest POST, not from the wall clock.
    # Using "now" would make every run produce a different file, so --check
    # could never pass and the feed would churn the git history on each build.
    built = posts[0]["date"]

    rss, atom = build_rss(posts, built), build_atom(posts, built)

    if args.check:
        stale = [name for name, content, path in
                 (("feed.xml", rss, RSS_OUT), ("atom.xml", atom, ATOM_OUT))
                 if not path.exists()
                 or path.read_text(encoding="utf-8") != content]
        if stale:
            print("STALE: %s would change. Run: python scripts/generate-feeds.py"
                  % ", ".join(stale))
            return 1
        print("OK: feeds up to date (%d posts)" % len(posts))
        return 0

    RSS_OUT.write_text(rss, encoding="utf-8", newline="\n")
    ATOM_OUT.write_text(atom, encoding="utf-8", newline="\n")
    print("Wrote %s and %s (%d posts, newest %s)"
          % (RSS_OUT.name, ATOM_OUT.name, len(posts),
             posts[0]["date"].date()))
    for name, why in skipped:
        print("  SKIPPED %s: %s" % (name, why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
