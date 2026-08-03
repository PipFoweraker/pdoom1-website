#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a local review page for content awaiting a human read.

WHY
---
Reviewing prose in a terminal is bad, and a plain markdown reader cannot show the
thing that actually matters: **what changed against what is already live**. A new
post needs reading; an edit to an existing page needs diffing. This renders both,
side by side, in one page.

Output goes to public/_review/content.html, which is gitignored and carries
noindex. It is a LOCAL artefact -- it must never be deployed, and it never asserts
anything about the site itself.

USAGE
  python scripts/render-content-review.py                 # the default review set
  python scripts/render-content-review.py --ref BRANCH    # add a branch's content
  python scripts/render-content-review.py --path FILE     # add one working-tree file
  python scripts/render-content-review.py --open          # print the localhost URL

Then:  python -m http.server 8080 --directory public
       http://localhost:8080/_review/content.html

DESIGN NOTES
- Markdown rendering is deliberately a SMALL subset, matching what the site's own
  blog renderer supports (links, images, inline code, bold, italic) plus headings,
  lists, blockquotes and tables so the reviewer can read comfortably. It is a
  REVIEW aid, not the publishing renderer -- if it renders something the site
  cannot, the banner at the top says so.
- Everything is escaped before formatting. This page is local, but it renders
  unreviewed content, and getting into the habit of escaping-then-formatting is
  cheaper than remembering which pages are trusted.
"""

import argparse
import html
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "_review" / "content.html"

# Content known to be awaiting a human read. Add to this rather than remembering.
DEFAULT_SET = [
    ("origin/content/anniversary-and-patch-week", "public/blog/2026-07-30-issue-1-turns-one.md"),
    ("origin/content/anniversary-and-patch-week", "public/blog/2026-07-28-this-post-has-a-shelf-life.md"),
    ("origin/content/claims-corpus", "docs/CLAIMS_AND_VOICE_CORPUS.md"),
    ("origin/content/press-kit-uplift", "docs/PRESS_STRATEGY.md"),
]


def git(*args):
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def show(ref, path):
    return git("show", f"{ref}:{path}")


# ---------------------------------------------------------------- markdown subset
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<em>[image: \1]</em>', s)

    def link(m):
        text, href = m.group(1), m.group(2)
        if not re.match(r"^(https?://|/|#)", href):
            return m.group(0)
        return f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">{text}</a>'

    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def render_md(text):
    """Small, forgiving renderer. Reviewer comfort, not publishing fidelity."""
    out, lines, i = [], text.split("\n"), 0
    in_fence = False
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            out.append("<pre><code>" if in_fence else "</code></pre>")
            i += 1
            continue
        if in_fence:
            out.append(html.escape(ln, quote=False))
            i += 1
            continue
        if ln.startswith("---") and i == 0:              # front matter
            j = i + 1
            fm = []
            while j < len(lines) and not lines[j].startswith("---"):
                fm.append(lines[j]); j += 1
            out.append('<div class="fm"><b>front matter</b><br>'
                       + "<br>".join(html.escape(f, quote=False) for f in fm) + "</div>")
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if ln.strip().startswith("|") and "|" in ln[1:]:
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i]); i += 1
            out.append(render_table(rows))
            continue
        if ln.strip().startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip("> ")); i += 1
            out.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i])); i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        if not ln.strip():
            i += 1
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|\s*[-*]\s|\||>|```)", lines[i]):
            para.append(lines[i]); i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def render_table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [c for c in cells if not all(re.match(r"^:?-+:?$", x or "-") for x in c)]
    if not cells:
        return ""
    head = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
    body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_diff(old, new):
    import difflib
    if old is None:
        return '<p class="new-file">NEW FILE — nothing to diff against. Read it as prose above.</p>'
    d = list(difflib.unified_diff(old.split("\n"), new.split("\n"),
                                  lineterm="", n=3, fromfile="live", tofile="proposed"))
    if not d:
        return '<p class="nodiff">No change against <code>main</code>.</p>'
    rows = []
    for ln in d:
        cls = ("d-add" if ln.startswith("+") and not ln.startswith("+++")
               else "d-del" if ln.startswith("-") and not ln.startswith("---")
               else "d-hunk" if ln.startswith("@@") else "d-ctx")
        rows.append(f'<div class="{cls}">{html.escape(ln, quote=False) or "&nbsp;"}</div>')
    return '<div class="diff">' + "".join(rows) + "</div>"


CSS = """
:root{--bg:#12100f;--bg2:#1c1917;--bg3:#262220;--fg:#fff;--fg2:#cfc7bb;--mut:#a79e92;
--amber:#f6a800;--teal:#2fd4c2;--red:#ff6b6b;--green:#4fb37a;--bd:#3a342e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.65 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:60rem;margin:0 auto;padding:2rem 1.25rem 6rem}
h1{color:var(--amber);margin:0 0 .3rem}
.sub{color:var(--mut);margin:0 0 2rem}
.warn{background:#2a2018;border:1px solid var(--amber);border-radius:8px;
padding:.9rem 1.1rem;margin-bottom:2rem;color:var(--fg2);font-size:.9rem}
.toc{background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:1rem 1.3rem;margin-bottom:2.5rem}
.toc a{color:var(--teal);display:block;padding:.2rem 0;text-decoration:none}
.toc a:hover{text-decoration:underline}
.item{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;margin:0 0 2.5rem;overflow:hidden}
.item>h2{margin:0;padding:.9rem 1.2rem;background:var(--bg3);border-bottom:1px solid var(--bd);
font-size:1.05rem;color:var(--amber);word-break:break-all}
.meta{padding:.5rem 1.2rem;color:var(--mut);font-size:.82rem;border-bottom:1px solid var(--bd)}
.tabs{display:flex;gap:0;border-bottom:1px solid var(--bd)}
.tabs button{flex:0 0 auto;background:transparent;border:0;border-bottom:2px solid transparent;
color:var(--mut);padding:.6rem 1.1rem;cursor:pointer;font:inherit;font-size:.9rem}
.tabs button[aria-selected=true]{color:var(--amber);border-bottom-color:var(--amber)}
.pane{padding:1.2rem 1.4rem;display:none}
.pane[data-open=true]{display:block}
.pane h1,.pane h2,.pane h3{color:var(--fg);margin:1.4rem 0 .5rem;line-height:1.3}
.pane h1{font-size:1.5rem}.pane h2{font-size:1.2rem}.pane h3{font-size:1.05rem}
.pane p{color:var(--fg2)}
.pane code{background:var(--bg3);padding:.1rem .35rem;border-radius:3px;color:var(--teal);font-size:.9em}
.pane pre{background:var(--bg);border:1px solid var(--bd);padding:.8rem;border-radius:6px;overflow-x:auto}
.pane blockquote{border-left:3px solid var(--amber);margin:1rem 0;padding:.2rem 0 .2rem 1rem;color:var(--mut)}
.pane a{color:var(--teal)}
.fm{background:var(--bg);border:1px dashed var(--bd);border-radius:6px;padding:.7rem .9rem;
color:var(--mut);font-size:.82rem;font-family:ui-monospace,Consolas,monospace;margin-bottom:1.2rem}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin:1rem 0}
th,td{border:1px solid var(--bd);padding:.45rem .6rem;text-align:left;vertical-align:top}
th{background:var(--bg3);color:var(--amber)}
.diff{font-family:ui-monospace,Consolas,monospace;font-size:.82rem;overflow-x:auto;
background:var(--bg);border:1px solid var(--bd);border-radius:6px;padding:.6rem}
.diff div{white-space:pre;padding:0 .3rem}
.d-add{background:rgba(79,179,122,.14);color:var(--green)}
.d-del{background:rgba(255,107,107,.12);color:var(--red)}
.d-hunk{color:var(--amber);margin-top:.4rem}
.d-ctx{color:var(--mut)}
.new-file{color:var(--green)}.nodiff{color:var(--mut)}
@media(max-width:640px){.wrap{padding:1rem .7rem 4rem}}
"""

JS = """
document.querySelectorAll('.item').forEach(function(item){
  var tabs=item.querySelectorAll('.tabs button');
  tabs.forEach(function(btn){
    btn.addEventListener('click',function(){
      tabs.forEach(function(b){b.setAttribute('aria-selected','false');});
      item.querySelectorAll('.pane').forEach(function(p){p.dataset.open='false';});
      btn.setAttribute('aria-selected','true');
      item.querySelector('[data-pane="'+btn.dataset.tab+'"]').dataset.open='true';
    });
  });
});
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", action="append", default=[],
                    help="extra 'branch:path' to include (repeatable)")
    ap.add_argument("--path", action="append", default=[],
                    help="extra working-tree file to include (repeatable)")
    args = ap.parse_args()

    items = list(DEFAULT_SET)
    for r in args.ref:
        if ":" in r:
            ref, path = r.split(":", 1)
            items.append((ref, path))
    for p in args.path:
        items.append((None, p))

    blocks, toc = [], []
    for n, (ref, path) in enumerate(items):
        new = show(ref, path) if ref else None
        if new is None and not ref:
            fp = ROOT / path
            new = fp.read_text(encoding="utf-8") if fp.is_file() else None
        if new is None:
            print(f"  SKIP (not found): {ref or 'worktree'}:{path}")
            continue
        old = show("origin/main", path)
        anchor = f"i{n}"
        label = Path(path).name
        origin = ref or "working tree"
        toc.append(f'<a href="#{anchor}">{html.escape(label)} '
                   f'<span style="color:var(--mut)">— {html.escape(origin)}</span></a>')
        status = ("NEW — not on main" if old is None
                  else "unchanged" if old == new else "CHANGED vs main")
        blocks.append(f"""
<section class="item" id="{anchor}">
  <h2>{html.escape(path)}</h2>
  <div class="meta">{html.escape(origin)} &nbsp;·&nbsp; {status} &nbsp;·&nbsp; {len(new.splitlines())} lines</div>
  <div class="tabs" role="tablist">
    <button data-tab="read" aria-selected="true">Read</button>
    <button data-tab="diff" aria-selected="false">Diff vs main</button>
    <button data-tab="raw" aria-selected="false">Raw</button>
  </div>
  <div class="pane" data-pane="read" data-open="true">{render_md(new)}</div>
  <div class="pane" data-pane="diff">{render_diff(old, new)}</div>
  <div class="pane" data-pane="raw"><pre><code>{html.escape(new, quote=False)}</code></pre></div>
</section>""")
        print(f"  included: {path}  ({status})")

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Content review — p(Doom)1</title>
<style>{CSS}</style></head><body>
<div class="wrap">
<h1>Content review</h1>
<p class="sub">Generated {stamp} · local only, never deployed</p>
<div class="warn">
<b>This is a review aid, not the publishing renderer.</b> The site's blog renderer
supports a much smaller markdown subset — links, images, inline code, bold, italic and
nothing else. Headings, tables, lists and fenced code render here for your comfort but
will appear as <em>raw text</em> on the live blog. If a draft leans on them, that is a
finding, not a formatting preference.
</div>
<div class="toc"><b style="color:var(--fg2)">Items</b>{''.join(toc)}</div>
{''.join(blocks)}
</div>
<script>{JS}</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print("view: http://localhost:8080/_review/content.html")
    print("      (python -m http.server 8080 --directory public)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
