#!/usr/bin/env python
"""Render the pdoom1 game's Architecture Decision Records as player-facing pages.

Source of truth is the GAME repo: docs/game-design/decisions/ADR-*.md.
This script never edits that source -- it reads, scrubs internal-only content,
renders a markdown subset to HTML in the site's terminal palette, and writes
public/design-notes/.

Why a build-time renderer rather than the client-side one in public/blog/post.html:
that parser supports only links, images, inline code, bold and italic. The ADRs
use tables (10 rows), numbered lists, blockquotes and headings, all of which it
would emit as raw text. Rendering here also keeps the pages static, which is what
the other ~2,200 generated pages already are.

Usage:
    python scripts/sync/sync-design-notes.py                  # uses ../pdoom1
    python scripts/sync/sync-design-notes.py --source PATH
    python scripts/sync/sync-design-notes.py --check          # exit 1 if stale

The markdown subset implemented here is exactly what the ADRs use, measured
rather than guessed: headings, bullets, numbered lists, bold, inline code,
links, tables, blockquotes, horizontal rules.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT.parent / "pdoom1"
ADR_SUBPATH = Path("docs") / "game-design" / "decisions"
OUT_DIR = REPO_ROOT / "public" / "design-notes"

PLAUSIBLE = (
    '<script defer data-domain="pdoom1.com" '
    'src="https://analytics.pdoom1.com/js/'
    'script.file-downloads.outbound-links.pageview-props.tagged-events.js"></script>'
)

# Kept byte-identical to scripts/sync/sync-events.py so design-notes pages sit in
# the same cascade as the ~2,200 generated event pages. If you change one, change
# both -- see CLAUDE.md on public/css/site.css loading LAST and winning.
PALETTE = """		:root {
			--bg-primary: #12100f;
			--bg-secondary: #1c1917;
			--bg-tertiary: #262220;
			--text-primary: #ffffff;
			--text-secondary: #cfc7bb;
			--text-muted: #a79e92;
			--accent-primary: #f6a800;
			--accent-secondary: #2fd4c2;
			--accent-danger: #ff4444;
			--border-color: #3a342e;
			--success-color: #4fb37a;
			--radius-md: 6px;
		}"""

# ---------------------------------------------------------------------------
# Scrubbing: what must never reach a player-facing page.
# ---------------------------------------------------------------------------

# Whole lines dropped when they match. These are process artefacts, not design.
SCRUB_LINE_PATTERNS = [
    re.compile(r"^\s*-\s*\*\*Session:\*\*", re.I),   # "- **Session:** pre-workshop framing (Opus)"
    re.compile(r"^\s*(TODO|FIXME|XXX)\b", re.I),
    re.compile(r"^\s*-\s*(TODO|FIXME)\b", re.I),
]

# HTML comments are authoring notes ("To fill from the workshop: ...").
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def scrub(text):
    """Remove internal-only content. Returns (clean_text, n_removed)."""
    removed = len(HTML_COMMENT.findall(text))
    text = HTML_COMMENT.sub("", text)
    out = []
    for line in text.split("\n"):
        if any(p.search(line) for p in SCRUB_LINE_PATTERNS):
            removed += 1
            continue
        out.append(line)
    # Collapse the blank runs that scrubbing leaves behind.
    joined = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return joined.strip() + "\n", removed


# ---------------------------------------------------------------------------
# Markdown subset -> HTML
# ---------------------------------------------------------------------------

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITALIC = re.compile(r"(?<![\*\w])\*([^*\n]+)\*(?!\*)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def inline(text):
    """Escape, then apply inline markup. Order matters: escape first so that
    source angle brackets can never become tags."""
    text = html.escape(text, quote=False)
    # Code first -- its contents must not be re-processed for bold/italic.
    placeholders = []

    def stash_code(m):
        placeholders.append(m.group(1))
        return "\x00%d\x00" % (len(placeholders) - 1)

    text = INLINE_CODE.sub(stash_code, text)
    text = LINK.sub(r'<a href="\2">\1</a>', text)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = ITALIC.sub(r"<em>\1</em>", text)
    for i, code in enumerate(placeholders):
        text = text.replace("\x00%d\x00" % i, "<code>%s</code>" % code)
    return text


def split_row(line):
    """Split a markdown table row, dropping the leading/trailing empty cells."""
    cells = line.strip().split("|")
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip() for c in cells]


IS_DIVIDER = re.compile(r"^[\s|:-]+$")


def render(md):
    """Render the measured ADR markdown subset. Returns HTML."""
    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Horizontal rule (before heading check: '---' is not a heading).
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            out.append("<hr>")
            i += 1
            continue

        # Table: a pipe row followed by a |---|---| divider.
        if stripped.startswith("|") and i + 1 < n and IS_DIVIDER.match(lines[i + 1].strip()) \
                and "|" in lines[i + 1]:
            header = split_row(stripped)
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(split_row(lines[i].strip()))
                i += 1
            out.append('<div class="table-scroll"><table>')
            out.append("<thead><tr>" + "".join(
                "<th>%s</th>" % inline(c) for c in header) + "</tr></thead>")
            out.append("<tbody>")
            for row in body:
                out.append("<tr>" + "".join(
                    "<td>%s</td>" % inline(c) for c in row) + "</tr>")
            out.append("</tbody></table></div>")
            continue

        # Heading.
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (level, inline(m.group(2)), level))
            i += 1
            continue

        # Blockquote (consecutive lines).
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % inline(" ".join(buf)))
            continue

        # Lists. Nesting is by leading whitespace; ADRs nest at most one level.
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            out.extend(render_list(lines, i))
            i = list_end(lines, i)
            continue

        # Paragraph: consume until a blank line or a block-level construct.
        buf = []
        while i < n and lines[i].strip() and not re.match(
                r"^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|\|)", lines[i]) and not re.match(
                r"^(-{3,}|\*{3,}|_{3,})$", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append("<p>%s</p>" % inline(" ".join(buf)))
        else:
            i += 1

    return "\n".join(out)


def list_end(lines, start):
    i = start
    while i < len(lines):
        if re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
            i += 1
        elif lines[i].strip() and lines[i].startswith((" ", "\t")):
            i += 1  # continuation of the previous item
        else:
            break
    return i


def render_list(lines, start):
    """Render one list block, handling a single level of nesting."""
    end = list_end(lines, start)
    block = lines[start:end]
    base_indent = len(block[0]) - len(block[0].lstrip())
    ordered = bool(re.match(r"^\s*\d+\.", block[0]))
    out = ["<ol>" if ordered else "<ul>"]
    item = []
    nested = []

    def flush():
        if not item:
            return
        content = inline(" ".join(item))
        if nested:
            content += "\n" + "\n".join(render_list(nested, 0))
        out.append("<li>%s</li>" % content)
        item.clear()
        nested.clear()

    for line in block:
        indent = len(line) - len(line.lstrip())
        m = re.match(r"^\s*([-*+]|\d+\.)\s+(.*)$", line)
        if m and indent <= base_indent:
            flush()
            item.append(m.group(2))
        elif m:
            nested.append(line[base_indent:])
        elif line.strip():
            item.append(line.strip())
    flush()
    out.append("</ol>" if ordered else "</ul>")
    return out


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

PAGE_CSS = """
		body { font-family: 'Courier New', monospace; background: var(--bg-primary);
			color: var(--text-primary); line-height: 1.6; margin: 0; padding: 0; }
		header { background: rgba(45, 45, 45, 0.95);
			border-bottom: 2px solid var(--accent-primary); padding: 1rem 0; }
		nav { max-width: 1200px; margin: 0 auto; padding: 0 1rem;
			display: flex; justify-content: space-between; align-items: center;
			flex-wrap: wrap; gap: 0.5rem; }
		nav a { color: var(--accent-primary); text-decoration: none; }
		nav a:hover { text-decoration: underline; }
		main { max-width: 860px; margin: 2rem auto 4rem; padding: 0 1rem; }
		h1 { color: var(--accent-primary); line-height: 1.3; }
		h2 { color: var(--accent-primary); margin-top: 2.5rem;
			border-bottom: 1px solid var(--border-color); padding-bottom: 0.3rem; }
		h3 { color: var(--accent-secondary); margin-top: 1.8rem; }
		a { color: var(--accent-primary); }
		code { background: var(--bg-tertiary); padding: 0.1rem 0.35rem;
			border-radius: 3px; font-size: 0.92em; }
		blockquote { border-left: 3px solid var(--accent-secondary);
			margin: 1.2rem 0; padding: 0.4rem 1rem; color: var(--text-secondary);
			background: var(--bg-secondary); }
		hr { border: 0; border-top: 1px solid var(--border-color); margin: 2rem 0; }
		/* Wide content must scroll in its own box, never the page body. */
		.table-scroll { overflow-x: auto; margin: 1.2rem 0; }
		table { border-collapse: collapse; width: 100%; min-width: 480px; }
		th, td { border: 1px solid var(--border-color); padding: 0.5rem 0.7rem;
			text-align: left; vertical-align: top; }
		th { background: var(--bg-secondary); color: var(--accent-primary); }
		.meta { color: var(--text-muted); font-size: 0.9rem;
			border: 1px solid var(--border-color); border-radius: var(--radius-md);
			padding: 0.8rem 1rem; margin-bottom: 2rem; background: var(--bg-secondary); }
		.meta strong { color: var(--text-secondary); }
		.notice { border: 1px solid var(--accent-secondary); border-radius: var(--radius-md);
			padding: 0.9rem 1rem; margin-bottom: 2rem; color: var(--text-secondary);
			background: rgba(47, 212, 194, 0.08); font-size: 0.92rem; }
		.card-list { list-style: none; padding: 0; }
		.card-list li { border: 1px solid var(--border-color);
			border-radius: var(--radius-md); padding: 1rem 1.2rem; margin-bottom: 0.8rem;
			background: var(--bg-secondary); }
		.card-list a { text-decoration: none; font-weight: 700; }
		.card-list p { margin: 0.4rem 0 0; color: var(--text-secondary);
			font-size: 0.92rem; }
		footer { border-top: 1px solid var(--border-color); margin-top: 3rem;
			padding: 1.5rem 1rem; text-align: center; color: var(--text-muted);
			font-size: 0.85rem; }
"""


def page(title, description, canonical, body):
    return """<!DOCTYPE html>
<html lang="en-AU">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>%s</title>
	<link rel="canonical" href="%s" />
	<meta name="description" content="%s" />
	<meta property="og:title" content="%s" />
	<meta property="og:description" content="%s" />
	<meta property="og:type" content="article" />
	<meta property="og:url" content="%s" />

	<!-- Plausible Analytics -->
	%s

	<link rel="stylesheet" href="/css/site.css">
	<style>
%s
%s	</style>
</head>
<body>
	<header>
		<!-- Progressive enhancement, deliberately. navigation.js (loaded at the
		     end of body) replaces the contents of <header> UNLESS it finds a
		     <nav> containing .nav-links. This fallback has no .nav-links class,
		     so the script overwrites it with the full site nav -- but if the
		     script is blocked or fails, these links still render, and they
		     render on first paint rather than after it.

		     Do NOT hand-copy the full nav here. The site already carries ten
		     divergent hand-copied nav variants across its top-level pages;
		     navigation.js is the de-facto single source (7 pages use it) and
		     these pages should inherit its fixes automatically. -->
		<nav>
			<a href="/">p(Doom)1</a>
			<span><a href="/design-notes/">Design Notes</a> &middot; <a href="/leaderboard/">Leaderboard</a> &middot; <a href="/bug-report/">Report a Bug</a></span>
		</nav>
	</header>
	<main>
%s
	</main>
	<footer>
		Design notes are generated from the game repository's decision records.
		Source: <a href="https://github.com/PipFoweraker/pdoom1">PipFoweraker/pdoom1</a>
	</footer>
	<script src="/assets/js/navigation.js"></script>
</body>
</html>
""" % (html.escape(title), canonical, html.escape(description), html.escape(title),
       html.escape(description), canonical, PLAUSIBLE, PALETTE, PAGE_CSS, body)


# Patterns that must never survive into rendered ADR content. Checked against
# the generated <main> body only -- the page template legitimately contains HTML
# comments (the Plausible label, the nav-fallback rationale), so scanning the
# whole document would flag the scaffolding rather than the content.
LEAK_PATTERNS = [
    (re.compile(r"<!--"), "HTML comment (authoring note)"),
    (re.compile(r"<strong>Session:</strong>"), "session attribution"),
    (re.compile(r"\bTODO\b|\bFIXME\b"), "TODO/FIXME marker"),
    (re.compile(r"To fill from the workshop"), "authoring placeholder"),
]


class LeakError(RuntimeError):
    """Raised when scrubbed output still contains internal-only content."""


def assert_clean(body, source_id):
    """Refuse to write a page whose body still carries internal content.

    Deliberately fails the build rather than warning: the whole point of this
    pipeline is that the game's private design process cannot leak by accident,
    and a warning in CI output is something everyone learns to scroll past.
    """
    for pattern, label in LEAK_PATTERNS:
        m = pattern.search(body)
        if m:
            raise LeakError(
                "%s: %s survived scrubbing near %r"
                % (source_id, label, body[max(0, m.start() - 60):m.start() + 60])
            )


NOTICE = (
    '<div class="notice">These are the actual decision records the game is built '
    'from, published unedited except for internal process notes. They describe '
    '<em>why</em> the game works the way it does. They are not a strategy guide, '
    'and some of them argue with each other.</div>'
)


def parse_adr(path):
    """Return a record for one ADR file, or None if it should be skipped."""
    raw = path.read_text(encoding="utf-8")
    clean, n_removed = scrub(raw)

    title_m = re.search(r"^#\s+(.*)$", clean, re.M)
    title = title_m.group(1).strip() if title_m else path.stem
    status_m = re.search(r"^-\s*\*\*Status:\*\*\s*(.*)$", clean, re.M)
    status = status_m.group(1).strip() if status_m else "unknown"
    date_m = re.search(r"^-\s*\*\*Date:\*\*\s*(.*)$", clean, re.M)
    date = date_m.group(1).strip() if date_m else ""

    # First real paragraph after "## Context" is the summary for the index.
    ctx_m = re.search(r"^##\s+Context\s*$\n+(.+?)(?=\n\n|\n#)", clean, re.M | re.S)
    summary = re.sub(r"\s+", " ", ctx_m.group(1)).strip() if ctx_m else ""
    summary = re.sub(r"\*\*|`|\*", "", summary)

    num_m = re.match(r"ADR-(\d+)", path.stem)
    return {
        "id": path.stem,
        "number": int(num_m.group(1)) if num_m else 9999,
        "slug": path.stem.lower(),
        "title": title,
        "status": status,
        "date": date,
        "summary": summary,
        "scrubbed_items": n_removed,
        "markdown": clean,
    }


def build(source, check_only=False):
    adr_dir = Path(source) / ADR_SUBPATH
    if not adr_dir.is_dir():
        print("ERROR: no ADR directory at %s" % adr_dir, file=sys.stderr)
        return 2

    files = sorted(p for p in adr_dir.glob("ADR-0*.md") if "TEMPLATE" not in p.name)
    if not files:
        print("ERROR: no ADR files found in %s" % adr_dir, file=sys.stderr)
        return 2

    records = [parse_adr(p) for p in files]
    records.sort(key=lambda r: r["number"])

    pages = {}
    for rec in records:
        # Drop the H1 -- the page template supplies the title heading itself.
        body_md = re.sub(r"^#\s+.*$", "", rec["markdown"], count=1, flags=re.M)
        # Status/date carry their own markup (e.g. "build **third**, straight
        # after ..."), so they go through inline() rather than bare escaping.
        meta = '\t\t<div class="meta"><strong>Status:</strong> %s' % inline(rec["status"])
        if rec["date"]:
            meta += ' &middot; <strong>Decided:</strong> %s' % inline(rec["date"])
        meta += "</div>"
        body = "\t\t<h1>%s</h1>\n%s\n%s\n%s" % (
            html.escape(rec["title"]), meta, NOTICE, render(body_md))
        assert_clean(body, rec["id"])
        pages["%s.html" % rec["slug"]] = page(
            "%s | p(Doom)1 Design Notes" % rec["title"],
            rec["summary"][:155] or rec["title"],
            "https://pdoom1.com/design-notes/%s.html" % rec["slug"],
            body,
        )

    # Index.
    items = []
    for rec in records:
        items.append(
            '\t\t\t<li><a href="/design-notes/%s.html">%s</a>'
            '<p>%s</p></li>' % (
                rec["slug"], html.escape(rec["title"]),
                html.escape(rec["summary"][:220] + ("..." if len(rec["summary"]) > 220 else "")))
        )
    index_body = (
        "\t\t<h1>Design Notes</h1>\n%s\n"
        "\t\t<p>Every significant design decision in p(Doom)1 is written down before "
        "it is built. %d of those records are published here.</p>\n"
        '\t\t<ul class="card-list">\n%s\n\t\t</ul>' % (
            NOTICE, len(records), "\n".join(items))
    )
    pages["index.html"] = page(
        "Design Notes | p(Doom)1",
        "The architecture decision records p(Doom)1 is built from - why the game "
        "works the way it does.",
        "https://pdoom1.com/design-notes/",
        index_body,
    )

    manifest = {
        "generated_by": "scripts/sync/sync-design-notes.py",
        "source_repo": "PipFoweraker/pdoom1",
        "source_path": str(ADR_SUBPATH).replace("\\", "/"),
        "count": len(records),
        "records": [
            {k: r[k] for k in ("id", "slug", "title", "status", "date", "scrubbed_items")}
            for r in records
        ],
    }
    pages["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if check_only:
        stale = [name for name, content in pages.items()
                 if not (OUT_DIR / name).exists()
                 or (OUT_DIR / name).read_text(encoding="utf-8") != content]
        if stale:
            print("STALE: %d file(s) would change: %s" % (len(stale), ", ".join(sorted(stale)[:5])))
            return 1
        print("OK: design-notes up to date (%d ADRs)" % len(records))
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Remove pages for ADRs that no longer exist upstream.
    for existing in OUT_DIR.glob("*.html"):
        if existing.name not in pages:
            existing.unlink()
            print("removed stale page: %s" % existing.name)

    for name, content in sorted(pages.items()):
        (OUT_DIR / name).write_text(content, encoding="utf-8", newline="\n")

    total_scrubbed = sum(r["scrubbed_items"] for r in records)
    print("Wrote %d pages to %s" % (len(pages), OUT_DIR))
    print("Scrubbed %d internal-only item(s) across %d ADRs" % (total_scrubbed, len(records)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(DEFAULT_SOURCE),
                    help="path to the pdoom1 game repo (default: %(default)s)")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed output is stale; write nothing")
    args = ap.parse_args()
    return build(args.source, check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
