#!/usr/bin/env python
"""Render REVIEW_INDEX.md to a clickable local page.

Local review aid only. Writes to public/_review/index.html, which is
deliberately NOT committed -- see the .gitignore entry this script adds.
The point is the links: a walkthrough you can click through beats one you
copy-paste into a viewer.

    python D:\\Local_Code\\pdoom1-website\\scripts\\render-review-index.py
    -> http://localhost:8080/_review/
"""
import html
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "REVIEW_INDEX.md"
OUT = ROOT / "public" / "_review" / "index.html"


def inline(t):
    """Inline markdown -> HTML. Escape first, then re-introduce markup."""
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<em>\1</em>", t)
    # bare localhost URLs become links too
    t = re.sub(r"(?<!\")(?<!=)(https?://localhost:\d+[^\s<>\"]*)",
               r'<a href="\1">\1</a>', t)
    return t


def render(md):
    out, i = [], 0
    lines = md.split("\n")
    while i < len(lines):
        ln = lines[i]

        if ln.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            out.append("<pre><code>%s</code></pre>" % "\n".join(buf))
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)", ln)
        if m:
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl))
            i += 1
            continue

        if re.match(r"^\s*(---|\*\*\*|___)\s*$", ln):
            out.append("<hr>")
            i += 1
            continue

        # table: header row, separator, then body
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1]):
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(ln)
            i += 2
            body = []
            while i < len(lines) and lines[i].startswith("|"):
                body.append(cells(lines[i]))
                i += 1
            t = ['<div class="tw"><table><thead><tr>']
            t += ["<th>%s</th>" % inline(h) for h in head]
            t.append("</tr></thead><tbody>")
            for r in body:
                t.append('<tr><td class="chk"><input type="checkbox"></td>')
                t += ["<td>%s</td>" % inline(c) for c in r]
                t.append("</tr>")
            t.append("</tbody></table></div>")
            # header needs the extra checkbox column
            t[0] = t[0] + "<th></th>"
            out.append("".join(t))
            continue

        if re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append("<li>%s</li>" % inline(re.sub(r"^\s*[-*]\s+", "", lines[i])))
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
            continue

        if ln.strip() == "":
            i += 1
            continue

        para = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "```", "-", "*")):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
        else:
            i += 1
    return "\n".join(out)


CSS = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:#0b0d0c;color:#cdd3d0;
 font:400 16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:34px 22px 90px}
h1{font-size:30px;line-height:1.15;margin:0 0 18px;color:#fff;letter-spacing:-.02em}
h2{font-size:21px;margin:44px 0 12px;color:#ffb000;border-bottom:1px solid #242b29;padding-bottom:7px}
h3{font-size:16px;margin:28px 0 8px;color:#cdd3d0}
p{max-width:74ch}
a{color:#ffb000}
a:visited{color:#b8830f}
code{font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:13px;
 background:#161a19;border:1px solid #242b29;padding:1px 5px;border-radius:2px}
pre{background:#141817;border:1px solid #242b29;padding:13px 15px;overflow-x:auto}
pre code{background:none;border:0;padding:0;font-size:13px}
hr{border:0;border-top:1px solid #242b29;margin:34px 0}
ul{max-width:74ch}
li{margin:5px 0}
.tw{overflow-x:auto;margin:14px 0;border:1px solid #242b29}
table{border-collapse:collapse;width:100%;font-size:14px}
th{background:#161a19;text-align:left;padding:9px 11px;border-bottom:1px solid #242b29;
 font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:11px;
 letter-spacing:.11em;text-transform:uppercase;color:#79837f;white-space:nowrap}
td{padding:10px 11px;border-bottom:1px solid #1b201f;vertical-align:top}
tr:last-child td{border-bottom:0}
td.chk{width:34px;text-align:center}
input[type=checkbox]{accent-color:#ffb000;width:15px;height:15px;cursor:pointer}
tr.done{opacity:.34}
tr.done td:not(.chk){text-decoration:line-through}
.bar{position:sticky;top:0;z-index:5;background:#0b0d0c;border-bottom:1px solid #242b29;
 padding:11px 0;margin-bottom:8px}
.bar .in{max-width:1100px;margin:0 auto;padding:0 22px;display:flex;gap:16px;align-items:center;
 font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:12px;color:#79837f}
.bar b{color:#ffb000;font-variant-numeric:tabular-nums}
.bar button{font:inherit;background:transparent;border:1px solid #242b29;color:#79837f;
 padding:4px 11px;cursor:pointer}
.bar button:hover{border-color:#ffb000;color:#ffb000}
a:focus-visible,input:focus-visible,button:focus-visible{outline:2px solid #ffb000;outline-offset:2px}
"""

JS = """
(function(){
  var boxes = Array.prototype.slice.call(document.querySelectorAll('tbody input[type=checkbox]'));
  var done = document.getElementById('done'), tot = document.getElementById('tot');
  tot.textContent = boxes.length;
  var KEY = 'review-index-2026-07-29';
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){}
  function paint(){
    var n = 0;
    boxes.forEach(function(b,i){
      var row = b.closest('tr');
      if(b.checked){ n++; row.classList.add('done'); } else { row.classList.remove('done'); }
    });
    done.textContent = n;
  }
  boxes.forEach(function(b,i){
    b.checked = !!saved[i];
    b.addEventListener('change', function(){
      saved[i] = b.checked;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch(e){}
      paint();
    });
  });
  document.getElementById('reset').addEventListener('click', function(){
    boxes.forEach(function(b,i){ b.checked = false; saved[i] = false; });
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch(e){}
    paint();
  });
  paint();
})();
"""

if not SRC.exists():
    print("ERROR: %s not found. Are you on the integration branch?" % SRC)
    raise SystemExit(1)

body = render(SRC.read_text(encoding="utf-8"))
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Review index - integration/2026-07-29-review</title>
<style>%s</style></head><body>
<div class="bar"><div class="in">
  <span>REVIEW PROGRESS</span><span><b id="done">0</b> / <b id="tot">0</b> checked</span>
  <button type="button" id="reset">Reset</button>
  <span style="margin-left:auto">local review aid &middot; not deployed</span>
</div></div>
<div class="wrap">%s</div>
<script>%s</script>
</body></html>""" % (CSS, body, JS)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")

# Never let this reach production.
gi = ROOT / ".gitignore"
line = "public/_review/"
existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
if line not in existing:
    with gi.open("a", encoding="utf-8") as f:
        f.write("\n# Local review aid, rendered by scripts/render-review-index.py. Never deployed.\n%s\n" % line)
    print("added %s to .gitignore" % line)

print("wrote %s" % OUT)
print("open  http://localhost:8080/_review/")
