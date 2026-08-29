#!/usr/bin/env python
"""Build the p(Doom)1 greyscale clipboard field pack (30 A4 pages).

Renders pack.html -> pdoom1-clipboard-pack.pdf with WeasyPrint.
Run with:  ~/.local/share/whisper-venv/bin/python build.py

Design brief: coordination#61 (Bauhaus-era, black-and-white, printer-safe)
and coordination#66 (typography is an open decision -- this pack puts the
candidates on paper to be judged). Mono laser: Brother HL-L2460DW.

Every factual claim on these pages is sourced from pdoom1 README / LICENSE
at the version named in public/data/version.json, or from pdoom1.com. The
version and the platform list are DERIVED from that file, never typed here --
this pack once advertised a macOS build that did not exist. The licence is
SOURCE-AVAILABLE, not open
source. The game is an ALPHA. Do not edit claims without re-verifying.
"""
import math, os, subprocess, sys

# cp1252 console guard. This module prints a filename that can contain non-ASCII,
# and CLAUDE.md records that the FIRST such print aborts the whole run on a Windows
# console before any work happens. Written verbatim as check-encoding-safety.py
# expects it -- an equivalent-but-differently-spelled version reads to that sweep
# as no preamble at all.
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ------------------------------------------------------- derived release facts
# PLATFORM AVAILABILITY IS A DERIVED FACT, NOT PROSE. The website's rule
# (CLAUDE.md, check-platform-claims.py) is that no page may advertise a platform
# with no build; the source of truth is version.json -> latest_release.platforms,
# which update-version-info.py derives from the release's actual assets.
#
# This pack sat outside that guard because it lives in print/, not public/, and
# it drifted: it claimed "Windows / macOS / Linux" and "v0.14.1" while the
# shipping release was v0.14.3 with Windows and Linux assets only. A wrong claim
# on a web page can be corrected in twenty seconds; this one gets handed to a
# stranger on paper and cannot be recalled, so it is derived here instead.
#
# There is deliberately NO fallback literal. A default ships exactly when the
# real lookup failed, and the failure mode of a fallback here is printing a
# confident falsehood a few hundred times.
def _release_facts():
    import json
    path = os.path.join(REPO, "public", "data", "version.json")
    try:
        with open(path, encoding="utf-8") as f:
            rel = json.load(f)["latest_release"]
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f"REFUSING TO BUILD: cannot read {path} ({exc}).\n"
                 "The pack's version and platform claims are derived from it, and a\n"
                 "printed pack cannot be corrected after the fact.")
    version = rel.get("version")
    platforms = rel.get("platforms")
    if not version or not isinstance(platforms, dict) or not platforms:
        sys.exit(f"REFUSING TO BUILD: {path} has no usable version/platforms.\n"
                 "Absence is not permission to guess -- see CLAUDE.md on fallback literals.")
    label = {"windows": "Windows", "macos": "macOS", "linux": "Linux"}
    live = [label.get(k, k) for k, v in platforms.items() if v]
    dead = [label.get(k, k) for k, v in platforms.items() if not v]
    if not live:
        sys.exit(f"REFUSING TO BUILD: {path} reports no shipped platform at all.")
    return version, live, dead

VERSION, PLATFORMS_LIVE, PLATFORMS_DEAD = _release_facts()

def _join(xs, sep=" / "):
    return sep.join(xs)

def _prose(xs):
    return xs[0] if len(xs) == 1 else " and ".join([", ".join(xs[:-1]), xs[-1]])

PLATFORM_SLASHES = _join(PLATFORMS_LIVE)          # "Windows / Linux"
PLATFORM_PROSE = _prose(PLATFORMS_LIVE)           # "Windows and Linux"
# Named explicitly rather than left silent: a reader who owns the missing machine
# is the one person who most needs to be told, and silence reads as "supported".
UNSHIPPED_NOTE = (
    f"No {_prose(PLATFORMS_DEAD)} build is published yet." if PLATFORMS_DEAD else ""
)
print(f"derived: {VERSION}, shipped for {PLATFORM_SLASHES}"
      + (f"; unshipped: {_join(PLATFORMS_DEAD, ', ')}" if PLATFORMS_DEAD else ""))

# ---------------------------------------------------------------- geometry
def pt(cx, cy, r, deg):
    """SVG point at math-angle deg (CCW from +x, y flipped for SVG)."""
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy - r * math.sin(a))

def _fmt(x):
    return f"{x:.2f}"

def wedge(cx, cy, r1, r2, a, b, fill, stroke="#000", sw=0.5):
    """Annulus sector from math-angle a down to b (a > b)."""
    x1, y1 = pt(cx, cy, r2, a); x2, y2 = pt(cx, cy, r2, b)
    x3, y3 = pt(cx, cy, r1, b); x4, y4 = pt(cx, cy, r1, a)
    large = 1 if (a - b) > 180 else 0
    d = (f"M {_fmt(x1)} {_fmt(y1)} A {r2} {r2} 0 {large} 1 {_fmt(x2)} {_fmt(y2)} "
         f"L {_fmt(x3)} {_fmt(y3)} A {r1} {r1} 0 {large} 0 {_fmt(x4)} {_fmt(y4)} Z")
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'

BANDS = [
    ("FINE, PROBABLY",        "#ffffff", "#000"),
    ("CONCERNING",            "#e0e0e0", "#000"),
    ("ALARMING",              "#bdbdbd", "#000"),
    ("SEVERE",                "#8a8a8a", "#000"),
    ("CATASTROPHIC",          "#454545", "#fff"),
    ("YOU ARE ALREADY DEAD",  "#000000", "#fff"),
]

def dial_svg(w, r1_frac=0.36, labels=True, label_size=None, needle=None,
             pivot=False, sw=0.5, tick_pct=True, klass=""):
    """Semicircular doom dial, width w mm, height ~ w/2 + a little.

    needle: math-angle in degrees for a printed needle, or None.
    pivot: draw a punch-out pivot cross (for the moving-pointer prop).
    """
    r2 = w / 2.0
    r1 = r2 * r1_frac
    pad = max(4.0, r2 * 0.22)   # headroom so rim labels never clip
    h = r2 + 6
    cx, cy = r2, r2 + 1
    ls = label_size if label_size else max(2.6, r2 * 0.052)
    parts = [f'<svg class="{klass}" width="{w + 2*pad}mm" height="{h + pad}mm" '
             f'viewBox="{-pad} {-pad} {w + 2*pad} {h + pad}" '
             f'style="margin:{-pad}mm 0 0 {-pad}mm" '
             f'xmlns="http://www.w3.org/2000/svg">']
    for i, (name, fill, txt) in enumerate(BANDS):
        a = 180 - 30 * i
        parts.append(wedge(cx, cy, r1, r2, a, a - 30, fill, sw=sw))
    # band labels, radial like the bushfire sign
    if labels:
        for i, (name, fill, txt) in enumerate(BANDS):
            mid = 180 - 30 * i - 15
            rm = (r1 + r2) / 2.0
            x, y = pt(cx, cy, rm, mid)
            rot = (180 - mid) if mid > 90 else -mid
            parts.append(
                f'<text x="{_fmt(x)}" y="{_fmt(y)}" fill="{txt}" '
                f'font-family="Liberation Sans Narrow" font-weight="bold" '
                f'font-size="{_fmt(ls)}" text-anchor="middle" '
                f'transform="rotate({_fmt(rot)} {_fmt(x)} {_fmt(y)})" '
                f'dominant-baseline="middle">{name}</text>')
    # boundary ticks + 0 / 100 endpoints
    for i in range(7):
        a = 180 - 30 * i
        x1, y1 = pt(cx, cy, r2, a); x2, y2 = pt(cx, cy, r2 + 1.6, a)
        parts.append(f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" '
                     f'y2="{_fmt(y2)}" stroke="#000" stroke-width="{sw}"/>')
    if tick_pct:
        fs = max(2.4, r2 * 0.045)
        parts.append(f'<text x="{_fmt(cx - r2 - 1)}" y="{_fmt(cy + 4.2)}" '
                     f'font-family="Liberation Mono" font-size="{_fmt(fs)}" '
                     f'text-anchor="start">0%</text>')
        parts.append(f'<text x="{_fmt(cx + r2 + 1)}" y="{_fmt(cy + 4.2)}" '
                     f'font-family="Liberation Mono" font-size="{_fmt(fs)}" '
                     f'text-anchor="end">100%</text>')
    # needle
    if needle is not None:
        nx, ny = pt(cx, cy, r2 * 0.94, needle)
        bx1, by1 = pt(cx, cy, 3.2, needle + 90)
        bx2, by2 = pt(cx, cy, 3.2, needle - 90)
        parts.append(f'<polygon points="{_fmt(bx1)},{_fmt(by1)} {_fmt(nx)},{_fmt(ny)} '
                     f'{_fmt(bx2)},{_fmt(by2)}" fill="#000"/>')
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="3.4" fill="#000"/>')
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="1.1" fill="#fff"/>')
    if pivot:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="2.6" fill="none" '
                     f'stroke="#000" stroke-width="0.5" stroke-dasharray="1.2 1"/>')
        parts.append(f'<line x1="{_fmt(cx-1.6)}" y1="{cy}" x2="{_fmt(cx+1.6)}" y2="{cy}" '
                     f'stroke="#000" stroke-width="0.4"/>')
        parts.append(f'<line x1="{cx}" y1="{_fmt(cy-1.6)}" x2="{cx}" y2="{_fmt(cy+1.6)}" '
                     f'stroke="#000" stroke-width="0.4"/>')
    parts.append("</svg>")
    return "".join(parts)

def paren_dot_mark(w):
    """M3: 'p( . )' -- parentheses holding a filled circle. Pure geometry."""
    h = w * 0.62
    return (f'<svg width="{w}mm" height="{h}mm" viewBox="0 0 100 62" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'<text x="2" y="50" font-family="URW Gothic" font-weight="600" '
            f'font-size="58">p</text>'
            f'<path d="M 48 6 A 34 34 0 0 0 48 58" fill="none" stroke="#000" stroke-width="6"/>'
            f'<path d="M 78 6 A 34 34 0 0 1 78 58" fill="none" stroke="#000" stroke-width="6"/>'
            f'<circle cx="63" cy="32" r="11" fill="#000"/>'
            f'</svg>')

# ---------------------------------------------------------------- widgets
def tick(id_, label="", big=False):
    cls = "tickbig" if big else "tick"
    lab = f'<span class="ticklab">{label}</span>' if label else ""
    return (f'<span class="tickrow"><span class="{cls}"></span>'
            f'<span class="tickid">{id_}</span>{lab}</span>')

def sheet(body, klass="", folio=""):
    f = f'<div class="folio">{folio}</div>' if folio else ""
    return f'<section class="sheet {klass}">{body}{f}</section>'

def h(t, sub=""):
    s = f'<div class="hsub">{sub}</div>' if sub else ""
    return f'<header class="ph"><div class="hbar"></div><div class="htxt"><h1>{t}</h1>{s}</div></header>'

# ================================================================= CSS
CSS = """
@page { size: A4 portrait; margin: 8mm; }
@page land { size: A4 landscape; margin: 8mm; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Nimbus Sans"; font-size:9.5pt; color:#000; }
.sheet { width:194mm; height:281mm; position:relative; overflow:hidden;
         page-break-after:always; }
.sheet.land { page: land; width:281mm; height:194mm; }
.sheet:last-child { page-break-after:auto; }
.folio { position:absolute; bottom:0; right:0; font-family:"Liberation Mono";
         font-size:6.5pt; color:#000; }

/* header */
.ph { display:flex; align-items:stretch; margin-bottom:4mm; }
.hbar { width:7mm; background:#000; margin-right:4mm; }
.htxt h1 { font-family:"URW Gothic"; font-weight:600; font-size:17pt;
           letter-spacing:0.4mm; text-transform:uppercase; }
.hsub { font-family:"Liberation Mono"; font-size:7.5pt; margin-top:1mm; }

/* ticks (inline-block: WeasyPrint downgrades inline-flex to block) */
.tickrow { display:inline-block; white-space:nowrap; }
.tick, .tickbig { display:inline-block; border:0.7mm solid #000; background:#fff;
                  vertical-align:middle; }
.tick { width:6mm; height:6mm; }
.tickbig { width:9mm; height:9mm; }
.tickid { font-family:"Liberation Mono"; font-weight:bold; font-size:8.5pt;
          vertical-align:middle; padding-left:1.5mm; }
.ticklab { font-size:8.5pt; vertical-align:middle; padding-left:1.5mm; }

/* rules and boxes */
.rule { height:1.2mm; background:#000; margin:2mm 0; }
.box { border:0.5mm solid #000; padding:3mm; }
.boxinv { background:#000; color:#fff; padding:3mm; }
.mono { font-family:"Liberation Mono"; }
.small { font-size:7.5pt; }
.tiny { font-size:6.5pt; }
.cap { text-transform:uppercase; letter-spacing:0.3mm; }

/* legend linework */
.cutline { border-top:0.4mm solid #000; }
.foldline { border-top:0.4mm dashed #000; }
.legend-swatch { display:inline-block; width:14mm; vertical-align:middle; }

/* tone ramp */
.ramp { display:flex; height:14mm; border:0.4mm solid #000; }
.ramp div { flex:1; border-right:0.2mm solid #777; }
.hatch1 { background:repeating-linear-gradient(45deg,#000 0,#000 0.4mm,#fff 0.4mm,#fff 2.2mm); }
.hatch2 { background:repeating-linear-gradient(45deg,#000 0,#000 0.4mm,#fff 0.4mm,#fff 1.2mm); }
.hatch3 { background:repeating-linear-gradient(-45deg,#000 0,#000 0.8mm,#fff 0.8mm,#fff 1.6mm); }
.dots   { background:repeating-linear-gradient(0deg,#000 0,#000 0.5mm,#fff 0.5mm,#fff 2mm),
                     repeating-linear-gradient(90deg,#000 0,#000 0.5mm,#fff 0.5mm,#fff 2mm); }

/* wordmark candidates */
.wm { display:flex; align-items:center; justify-content:space-between;
      border:0.3mm solid #000; padding:3mm 4mm; margin-bottom:2.6mm; }
.wm .art { flex:1; }
.wm .meta { width:44mm; text-align:right; }
.wm .meta .name { font-family:"Liberation Mono"; font-size:7pt; }

/* cut sheets */
.cardgrid { position:absolute; }
.card { position:absolute; width:85mm; height:55mm; overflow:hidden; background:#fff; }
.gridline { position:absolute; background:none; }
.crop { position:absolute; background:#000; }

/* image frames */
.artframe { border:0.5mm solid #000; }
.artframe img { display:block; width:100%; }
.cap-lab { font-family:"Liberation Mono"; font-size:7pt; margin-top:1mm; }

/* survey */
.q { margin-bottom:4.5mm; }
.q .qt { font-weight:bold; margin-bottom:1.5mm; }
.writeline { border-bottom:0.35mm solid #000; height:7mm; }

/* zine panels */
.zpanel { position:absolute; width:70.25mm; height:97mm; overflow:hidden; }
.zflip { transform:rotate(180deg); }
.zin { padding:6mm 5mm; height:97mm; position:relative; }

/* tent */
.tentpanel { position:absolute; left:0; width:194mm; overflow:hidden; }
"""

PAGES = []

MONOFACTS = [
    f"alpha &middot; {VERSION} &middot; built in Godot 4.5.1",
    "source-available (not open source) &mdash; see LICENSE",
    f"{PLATFORM_SLASHES} &middot; free download",
    "pdoom1.com &middot; github.com/PipFoweraker/pdoom1",
]

ONE_LINER = "Run an underfunded AI safety lab and hold off catastrophe for as long as you can."

PREMISE = ("You run an underfunded AI safety lab while better-resourced rivals race "
           "toward AGI. There is no win screen &mdash; alignment is not a thing you finish. "
           "You hire researchers, balance their traits, handle burnout, poaching and "
           "rival-lab events, and buy time against a rising p(Doom). Every run ends in "
           "defeat; your score is the number of turns you survived, and the end screen "
           "attributes honestly what killed you.")

# ================================================================ p.1 cover
ramp = "".join(f'<div style="background:rgb({v},{v},{v})"></div>'
               for v in [255,229,204,178,153,127,102,76,51,25,0])
ramp_labels = "".join(f'<div style="flex:1;text-align:center">{p}</div>'
                      for p in ["0","10","20","30","40","50","60","70","80","90","100"])
PAGES.append(sheet(
    h("p(Doom)1 &mdash; field pack",
      "30 pages &middot; greyscale &middot; built 2026-08 &middot; clipboard + scissors edition") +
    f"""
<div class="boxinv" style="margin-bottom:4mm">
  <span class="cap" style="font-family:'URW Gothic';font-weight:600;font-size:13pt">
  How to use this pack</span><br>
  <span class="small">Show pages. Ask the question printed on each page. Get a tick or a
  circle in under ten seconds. Cut sheets live at the back &mdash; scissors welcome.
  Tally page is p.20. Every design element has an ID (W&hellip;, C&hellip;, S&hellip;) so
  a tick is enough.</span>
</div>
<table style="width:100%; border-collapse:collapse; font-size:8.5pt">
<tr>
 <td style="width:33%;vertical-align:top;padding-right:4mm">
   <div class="cap" style="font-weight:bold">Line legend</div>
   <div style="margin:2mm 0"><span class="legend-swatch cutline"></span> cut (solid)</div>
   <div style="margin:2mm 0"><span class="legend-swatch foldline"></span> fold (dashed)</div>
   <div style="margin:2mm 0">{tick('ID','tick = preference')}</div>
 </td>
 <td style="vertical-align:top" class="small">
   <div class="cap" style="font-weight:bold;font-size:8.5pt">Contents</div>
   <div class="mono tiny" style="line-height:1.65">
   2 explainer &middot; 3&ndash;4 wordmarks W1&ndash;W8 &middot; 5 casing N1&ndash;N5 &middot;
   6 taglines T1&ndash;T6 &middot; 7 body type B1&ndash;B3 &middot; 8 marks M0&ndash;M4 &middot;
   9 portraits R1&ndash;R5 &middot; 10 event art E1&ndash;E4 &middot; 11 cats K1&ndash;K4 &middot;
   12 card face-off C1&ndash;C5 &middot; 13&ndash;14 DOOM DIAL prop &middot; 15 pocket dials &middot;
   16 tent card &middot; 17 one-cut zine &middot; 18 survey &middot; 19 channels &middot;
   20 tally &middot; 21&ndash;22 posters P1&ndash;P4 &middot; 23&ndash;27 business cards &middot;
   28&ndash;30 slips S1&ndash;S3</div>
 </td>
</tr></table>
<div class="rule"></div>
<div class="cap small" style="font-weight:bold">Printer calibration &mdash; Brother HL-L2460DW, mono laser</div>
<div class="small" style="margin:1mm 0 2mm">Tone ramp (nominal % black) and pattern fills.
If steps 10&ndash;30 merge or 70&ndash;90 fill in, note it here and the Monday colour
iteration compensates.</div>
<div class="ramp">{ramp}</div>
<div style="display:flex" class="mono tiny">{ramp_labels}</div>
<div style="display:flex; gap:3mm; margin-top:3mm; height:12mm">
  <div class="hatch1" style="flex:1;border:0.4mm solid #000"></div>
  <div class="hatch2" style="flex:1;border:0.4mm solid #000"></div>
  <div class="hatch3" style="flex:1;border:0.4mm solid #000"></div>
  <div class="dots" style="flex:1;border:0.4mm solid #000"></div>
</div>
<div class="mono tiny" style="display:flex;gap:3mm;margin-top:1mm">
  <div style="flex:1">hatch 2.2mm</div><div style="flex:1">hatch 1.2mm</div>
  <div style="flex:1">hatch heavy</div><div style="flex:1">crosshatch</div>
</div>
<div style="position:absolute; bottom:14mm; left:0; right:0">
  {dial_svg(120, needle=28, klass="")}
  <div class="mono tiny" style="margin-top:2mm">Everything stated in this pack is true of
  build {VERSION} unless it is printed as a question. The licence is source-available; the
  game is an alpha; nobody is promised a win screen, because there isn't one.</div>
</div>""", folio="p(Doom)1 field pack &middot; 1/30"))

# ================================================================ p.2 explainer
facts = "".join(f'<li>{x}</li>' for x in [
    "Turn-based strategy, single player. Hire researchers from a candidate pool "
    "(Safety, Capabilities, Interpretability, Alignment); teams of up to 8 per manager.",
    "Researchers have traits &mdash; team player, media savvy, leak-prone &mdash; and can "
    "burn out or be poached by rival labs.",
    "Random events and rival-lab actions land every run. Doom rises from reckless research.",
    "<b>There is no victory condition.</b> Score = turns survived. The end screen tells you "
    "what killed you, honestly.",
    "Deterministic seeds: a given seed plays identically for everyone, so scores are "
    "comparable.",
    "Report a bug from inside the game (press <b>N</b>) &mdash; and your cat can be drawn "
    "into the game as an Office Cat, with five doom-level variants, plus a credits listing.",
])
PAGES.append(sheet(
    h("What is p(Doom)1?", "the honest one-pager &middot; hand this page to a stranger") +
    f"""
<div style="font-family:'URW Gothic';font-weight:600;font-size:15pt;margin-bottom:3mm">
{ONE_LINER}</div>
<p style="margin-bottom:3.5mm">{PREMISE}</p>
<div class="artframe"><img src="assets/screenshot.png"></div>
<div class="cap-lab">Actual alpha interface, v0.14 &mdash; the game runs dark; this is what
it looks like pushed through a mono laser.</div>
<div class="rule" style="margin-top:3.5mm"></div>
<ul style="margin:2mm 0 3mm 5mm; line-height:1.5">{facts}</ul>
<div style="display:flex; gap:4mm">
  <div class="box" style="flex:1">
    <div class="cap" style="font-weight:bold; font-size:8.5pt">Status, stated plainly</div>
    <div class="small" style="line-height:1.55; margin-top:1mm">
    <b>Alpha</b>, {VERSION}, built in Godot 4.5.1. Published for {PLATFORM_PROSE}; the
    Windows build is the most tested. {UNSHIPPED_NOTE} Builds are not yet code-signed, so
    your OS will warn you the developer is unidentified &mdash; that is expected, and the
    website walks you past it.</div>
  </div>
  <div class="box" style="flex:1">
    <div class="cap" style="font-weight:bold; font-size:8.5pt">Licence, stated plainly</div>
    <div class="small" style="line-height:1.55; margin-top:1mm">
    <b>Source-available.</b> Not open source, and we won't call it that. The source is
    public to read and contribute to; no licence is granted to redistribute or sell. A
    formal open-source licence for the engine is planned around 1.0.</div>
  </div>
</div>
<div class="boxinv mono" style="margin-top:4mm; font-size:10pt; text-align:center">
pdoom1.com &nbsp;&middot;&nbsp; github.com/PipFoweraker/pdoom1 &nbsp;&middot;&nbsp; team@pdoom1.com
</div>""", folio="2/30"))

# ================================================================ p.3 wordmarks A
WMS = [
    ("W1", "p(Doom)1", "URW Gothic", "600", "26pt", "0.2mm", "geometric &middot; Bauhaus lineage (Avant Garde)", ""),
    ("W2", "P(DOOM)1", "URW Gothic", "400", "22pt", "1.6mm", "geometric caps, letterspaced", ""),
    ("W3", "p(Doom)1", "Nimbus Sans", "bold", "26pt", "0mm", "grotesque &middot; neutral, industrial", ""),
    ("W4", "P(DOOM)1", "Liberation Sans Narrow", "bold", "28pt", "0.1mm", "condensed poster caps", ""),
    ("W5", "p(doom)1", "Liberation Mono", "bold", "22pt", "0mm", "terminal &middot; matches the game's shipping mono UI", ""),
    ("W6", "p(doom)1", "DejaVu Sans Mono", "bold", "20pt", "0mm", "terminal alt &mdash; a face the game itself falls back to", ""),
    ("W7", "p(Doom)1", "C059", "bold", "24pt", "0mm", "bookish serif &mdash; the control nobody expects", ""),
    ("W8", "p(Doom)1", "Quicksand", "bold", "24pt", "0.2mm", "rounded geometric &mdash; nearest kin of the current tile", ""),
]
wm_rows = "".join(
    f"""<div class="wm">
      <div class="art" style="font-family:'{fam}';font-weight:{wt};font-size:{sz};
           letter-spacing:{ls}">{text}</div>
      <div class="meta"><div class="name">{id_} &middot; {fam}</div>
      <div class="tiny">{note}</div>
      <div style="margin-top:1.5mm">{tick(id_)}</div></div>
    </div>"""
    for id_, text, fam, wt, sz, ls, note, _ in WMS)
PAGES.append(sheet(
    h("Wordmark, round one", "coordination#66 made physical &middot; tick any you'd stop for &middot; X any you hate") +
    wm_rows +
    '<div class="mono tiny" style="margin-top:2mm">All faces licensed/installed locally; '
    'the winner gets bought properly if it needs to be. Casing is a separate question '
    '&mdash; next page but one.</div>',
    folio="3/30"))

# ================================================================ p.4 wordmarks B (survival test)
def wm_small(fam, wt, text, sz):
    return (f'<span style="font-family:\'{fam}\';font-weight:{wt};font-size:{sz}">{text}</span>')
rows = []
for id_, text, fam, wt, _, _, note, _ in [WMS[0], WMS[3], WMS[4], WMS[2]]:
    rows.append(f"""
<div class="box" style="margin-bottom:3mm">
  <div style="display:flex; align-items:center; gap:5mm">
    <div style="width:20mm">{tick(id_)}</div>
    <div style="flex:1">
      <div>{wm_small(fam, wt, text, "8pt")} &nbsp; {wm_small(fam, wt, text, "11pt")}
           &nbsp; {wm_small(fam, wt, text, "15pt")}</div>
      <div class="boxinv" style="margin-top:2mm; text-align:center">
        {wm_small(fam, wt, text, "13pt")}</div>
    </div>
    <div style="width:58mm; border:0.3mm solid #000; padding:2mm; height:26mm">
      <div style="font-family:'{fam}';font-weight:{wt};font-size:10.5pt">{text}</div>
      <div class="tiny" style="margin-top:1mm">Pip Foweraker &middot; pdoom1.com</div>
      <div class="tiny mono" style="position:relative; top:8mm">business-card scale</div>
    </div>
  </div>
</div>""")
PAGES.append(sheet(
    h("Wordmark, survival test", "same four candidates at 8pt, reversed, and at card scale &mdash; a mark that dies small is dead") +
    "".join(rows) +
    f"""
<div class="box" style="margin-top:2mm">
  <div style="display:flex; align-items:center; gap:5mm">
    <div style="width:20mm">{tick('W0')}</div>
    <div style="flex:1"><img src="assets/wordmark_tile.png" style="width:30mm"></div>
    <div style="width:100mm" class="small">The tile that already lives in the game repo.
    It has been size-culled but never approved as a design (coordination#66). It runs as a
    candidate here like everything else &mdash; no incumbency privileges.</div>
  </div>
</div>""", folio="4/30"))

# ================================================================ p.5 casing
CASES = [
    ("N1", "p(Doom)1", "the website's usage"),
    ("N2", "P(Doom)", "the game repo's title usage"),
    ("N3", "pdoom1", "the domain and the repo slug"),
    ("N4", "P(DOOM)1", "poster caps &mdash; used nowhere yet"),
    ("N5", "p(doom)", "the lowercase term of art, as the field writes it"),
]
case_rows = "".join(
    f"""<div class="wm"><div class="art" style="font-family:'URW Gothic';font-weight:600;
        font-size:24pt">{t}</div>
        <div class="meta"><div class="name">{i}</div><div class="tiny">{n}</div>
        <div style="margin-top:1.5mm">{tick(i)}</div></div></div>"""
    for i, t, n in CASES)
PAGES.append(sheet(
    h("The casing question", "these all currently coexist in the estate &mdash; one of them should win. Circle or tick.") +
    case_rows +
    '<div class="mono tiny">True statement: the project has never decided this. '
    'Your tick is a real input.</div>', folio="5/30"))

# ================================================================ p.6 taglines
TAGS = [
    ("T1", "Run an underfunded AI safety lab. Hold off catastrophe for as long as you can."),
    ("T2", "Every run ends in defeat. Your score is how long you lasted."),
    ("T3", "Alignment is not a thing you finish. Buy time."),
    ("T4", "Made with coffee and existential dread."),
    ("T5", "The end screen tells you what killed you. Honestly."),
    ("T6", "How many turns can you buy?"),
]
tag_rows = "".join(
    f"""<div class="box" style="margin-bottom:3.5mm; display:flex; align-items:center; gap:5mm">
     <div style="width:16mm">{tick(i)}</div>
     <div style="flex:1; font-family:'Liberation Sans Narrow'; font-weight:bold;
          font-size:15pt">{t}</div></div>"""
    for i, t in TAGS)
PAGES.append(sheet(
    h("Tagline face-off", "every one of these is true of the build &mdash; which one makes you look up?") +
    tag_rows +
    """<div class="q"><div class="qt small">Got a better one? It has to be true. There is no
    win screen, it is an alpha, and it is source-available &mdash; write inside the rails:</div>
    <div class="writeline"></div><div class="writeline"></div></div>""",
    folio="6/30"))

# ================================================================ p.7 body type
BODIES = [
    ("B1", "Liberation Mono", "normal", "8.5pt", "terminal mono &mdash; what the game UI actually ships"),
    ("B2", "Nimbus Sans", "normal", "9.5pt", "grotesque &mdash; the quiet professional"),
    ("B3", "C059", "normal", "9.5pt", "book serif &mdash; reads like a rulebook"),
]
body_rows = "".join(
    f"""<div class="box" style="margin-bottom:4mm">
      <div style="display:flex; justify-content:space-between; margin-bottom:2mm">
        <span class="mono small"><b>{i}</b> &middot; {fam} &middot; {note}</span>{tick(i)}</div>
      <div style="font-family:'{fam}';font-weight:{wt};font-size:{sz};line-height:1.55;
           column-count:2; column-gap:6mm">{PREMISE}</div>
    </div>"""
    for i, fam, wt, sz, note in BODIES)
PAGES.append(sheet(
    h("Body type &mdash; which would you read a rulebook in?",
      "same paragraph, three settings &middot; tick the one your eyes forgave") +
    body_rows +
    '<div class="mono tiny">Line length, size and leading held comparable; only the face '
    'changes. This decides manuals, the website body, and slip copy.</div>',
    folio="7/30"))

# ================================================================ p.8 marks
PAGES.append(sheet(
    h("Marks &amp; emblems", "the thing that goes on a sticker, a favicon, a shirt &middot; tick any") +
    f"""
<div style="display:flex; flex-wrap:wrap; gap:4mm">
  <div class="box" style="width:92mm">
    <img src="assets/logo_emblem.png" style="width:52mm; display:block; margin:0 auto">
    <div class="cap-lab">M0 &middot; current game icon (mountain-and-graph emblem). Prints
    as a heavy toner disc; survives, at a cost.</div>
    <div style="margin-top:1mm">{tick('M0')}</div>
  </div>
  <div class="box" style="width:92mm">
    <img src="assets/wordmark_tile.png" style="width:52mm; display:block; margin:0 auto">
    <div class="cap-lab">M1 &middot; current wordmark tile (unapproved, see p.4).</div>
    <div style="margin-top:1mm">{tick('M1')}</div>
  </div>
  <div class="box" style="width:92mm">
    <div style="display:flex; justify-content:center; padding:4mm 0">{dial_svg(56, labels=False, needle=22, tick_pct=False)}</div>
    <div class="cap-lab">M2 &middot; NEW &mdash; the doom dial as a mark. Needle parked in
    the black. Pure line and tone; laughs at mono lasers.</div>
    <div style="margin-top:1mm">{tick('M2')}</div>
  </div>
  <div class="box" style="width:92mm">
    <div style="display:flex; justify-content:center; padding:2mm 0">{paren_dot_mark(50)}</div>
    <div class="cap-lab">M3 &middot; NEW &mdash; p( &bull; ): the probability that dare not
    speak its value. Geometric, Bauhaus-honest, one glyph from being a logo.</div>
    <div style="margin-top:1mm">{tick('M3')}</div>
  </div>
  <div class="box" style="width:92mm">
    <img src="assets/cat_face.png" style="width:40mm; display:block; margin:0 auto">
    <div class="cap-lab">M4 &middot; the office cat as mascot-mark (from the game's icon
    set). Dark tile; would be redrawn as linework for print.</div>
    <div style="margin-top:1mm">{tick('M4')}</div>
  </div>
  <div class="box" style="width:92mm; display:flex; flex-direction:column; justify-content:center">
    <div class="small" style="line-height:1.6">A mark must survive: 12mm on a business
    card, reversed white-on-black, one colour, and a bad photocopy. M2 and M3 were drawn
    under those rules. M0, M1 and M4 predate them.</div>
  </div>
</div>""", folio="8/30"))

# ================================================================ p.9 portraits
PORTS = [
    ("R1", "port_pessimist", "the authoritarian pessimist"),
    ("R2", "port_burnout",   "the burned-out senior"),
    ("R3", "port_optimist",  "the capabilities optimist"),
    ("R4", "port_crusader",  "the moral crusader"),
    ("R5", "port_pleaser",   "the people pleaser"),
]
port_cells = "".join(
    f"""<div style="width:60mm">
      <div class="artframe"><img src="assets/{f}.png"></div>
      <div style="display:flex; justify-content:space-between; margin-top:1mm">
        <span class="cap-lab">{i} &middot; {n}</span>{tick(i)}</div>
    </div>"""
    for i, f, n in PORTS)
PAGES.append(sheet(
    h("Which face fronts the poster?", "real in-game dossier portraits, straight off the mono laser &middot; tick up to two") +
    f'<div style="display:flex; flex-wrap:wrap; gap:4mm; justify-content:space-between">{port_cells}'
    f"""<div style="width:60mm" class="box">
     <div class="small" style="line-height:1.6">These are researcher archetypes you actually
     hire in the game. They were painted dossier-style and convert to greyscale better than
     anything else in the repo &mdash; which is why this whole pack leans on them.<br><br>
     <span class="mono tiny">Bonus question: which one is you? Write their R-number here:</span>
     <div class="writeline" style="margin-top:2mm"></div></div>
    </div></div>""",
    folio="9/30"))

# ================================================================ p.10 events
EVENTS = [
    ("E1", "ev_board",  "the board convenes", "reads well in grey"),
    ("E2", "ev_opp",    "an opportunity, maybe", "reads well in grey"),
    ("E3", "ev_crisis", "the graph does a thing", "dark &mdash; shadows lifted for print"),
    ("E4", "ev_secret", "the filing cabinet knows", "very dark &mdash; heaviest lift in the pack"),
]
ev_cells = "".join(
    f"""<div style="width:92mm">
      <div class="artframe"><img src="assets/{f}.png"></div>
      <div style="display:flex; justify-content:space-between; margin-top:1mm">
        <span class="cap-lab">{i} &middot; {n} <span class="tiny">({note})</span></span>{tick(i)}</div>
    </div>"""
    for i, f, n, note in EVENTS)
PAGES.append(sheet(
    h("Event art &mdash; which scene sells the mood?", "in-game event illustrations &middot; tick any that pull you in") +
    f'<div style="display:flex; flex-wrap:wrap; gap:4mm">{ev_cells}</div>' +
    '<div class="mono tiny" style="margin-top:2mm">Honesty note: E3 and E4 are far darker '
    'in the game than shown; their shadows were lifted so a mono laser could hold them at '
    'all. The originals would print as toner floods.</div>',
    folio="10/30"))

# ================================================================ p.11 cats
CATS = [
    ("K1", "cat_photo", "the real office cat (photograph)"),
    ("K2", "cat_lamp",  "icon-set cat, with lamp and coffee"),
    ("K3", "cat_face",  "icon-set cat, portrait tile"),
    ("K4", "cat_doom",  "icon-set cat, doom variant"),
]
cat_cells = "".join(
    f"""<div style="width:92mm">
      <div class="artframe"><img src="assets/{f}.png" style="max-height:78mm; width:auto; margin:0 auto"></div>
      <div style="display:flex; justify-content:space-between; margin-top:1mm">
        <span class="cap-lab">{i} &middot; {n}</span>{tick(i)}</div>
    </div>"""
    for i, f, n in CATS)
PAGES.append(sheet(
    h("Cat referendum", "tick exactly one. we know this is the page people will fight over") +
    f'<div style="display:flex; flex-wrap:wrap; gap:4mm">{cat_cells}</div>' +
    """<div class="boxinv small" style="margin-top:3mm">True and standing offer: report a bug
    (press N in-game) or help playtest, and your own cat can be drawn into the game as an
    Office Cat &mdash; five doom-level variants, credits listing included.</div>""",
    folio="11/30"))

# ================================================================ p.12 card face-off (uncut)
def card_c1(scale=1.0, id_lab=True):
    return f"""
<div style="width:85mm;height:55mm;position:relative;background:#fff;overflow:hidden">
  <div style="position:absolute;top:0;left:0;width:85mm;height:3mm;background:#000"></div>
  <div style="position:absolute;top:8mm;left:6mm;font-family:'URW Gothic';font-weight:600;
       font-size:20pt">p(Doom)1</div>
  <div style="position:absolute;top:19mm;left:6mm;width:44mm;height:1mm;background:#000"></div>
  <div style="position:absolute;top:23mm;left:6mm;font-size:8pt;line-height:1.5">
    AI safety strategy game<br>Pip Foweraker</div>
  <div style="position:absolute;bottom:5mm;left:6mm" class="mono tiny">
    pdoom1.com &middot; team@pdoom1.com<br>source-available alpha</div>
  <div style="position:absolute;right:-9mm;bottom:-9mm;width:26mm;height:26mm;
       border:1mm solid #000;border-radius:50%"></div>
  <div style="position:absolute;right:5mm;bottom:6mm;width:5mm;height:5mm;
       background:#000;border-radius:50%"></div>
</div>"""

def card_c2():
    return f"""
<div style="width:85mm;height:55mm;position:relative;background:#fff;overflow:hidden;
     font-family:'Liberation Mono'">
  <div style="position:absolute;top:0;left:0;right:0;height:10mm;background:#000;
       color:#fff;font-size:9pt;padding:2.5mm 4mm">p(doom)1 &mdash; {VERSION}-alpha</div>
  <div style="position:absolute;top:14mm;left:4mm;font-size:8pt;line-height:1.7">
    $ run lab --underfunded<br>
    &gt; doom is rising<br>
    &gt; there is no win state<br>
    &gt; survive more turns</div>
  <div style="position:absolute;bottom:4mm;left:4mm;font-size:8pt">
    pip foweraker &middot; pdoom1.com</div>
  <div style="position:absolute;bottom:4mm;right:4mm;font-size:8pt">[alpha]</div>
</div>"""

def card_c3():
    return f"""
<div style="width:85mm;height:55mm;position:relative;background:#fff;overflow:hidden">
  <div style="position:absolute;top:-14mm;left:-30mm;width:150mm;height:26mm;background:#000;
       transform:rotate(-12deg)"></div>
  <div style="position:absolute;top:2.5mm;left:6mm;transform:rotate(-12deg);
       font-family:'Liberation Sans Narrow';font-weight:bold;font-size:21pt;color:#fff;
       letter-spacing:0.2mm">P(DOOM)1</div>
  <div style="position:absolute;bottom:14mm;left:6mm;font-family:'Liberation Sans Narrow';
       font-weight:bold;font-size:10.5pt">EVERY RUN ENDS IN DEFEAT.<br>
       YOUR SCORE IS HOW LONG YOU LASTED.</div>
  <div style="position:absolute;bottom:5mm;left:6mm" class="mono tiny">
    pdoom1.com &middot; source-available alpha</div>
</div>"""

def card_c4():
    return f"""
<div style="width:85mm;height:55mm;position:relative;background:#fff;overflow:hidden">
  <div style="position:absolute;top:6mm;left:5mm">{dial_svg(40, labels=False, needle=20, tick_pct=False, sw=0.4)}</div>
  <div style="position:absolute;top:9mm;left:50mm;font-family:'URW Gothic';font-weight:600;
       font-size:15pt">p(Doom)1</div>
  <div style="position:absolute;top:17mm;left:50mm;font-size:7.5pt;width:32mm;line-height:1.4">
    hold off catastrophe<br>as long as you can</div>
  <div style="position:absolute;bottom:5mm;left:5mm" class="mono tiny">
    pdoom1.com &middot; Pip Foweraker &middot; alpha</div>
</div>"""

def card_c5():
    return f"""
<div style="width:85mm;height:55mm;position:relative;background:#fff;overflow:hidden">
  <img src="assets/cat_face.png" style="position:absolute;left:0;top:0;height:55mm">
  <div style="position:absolute;left:57mm;top:7mm;font-family:'URW Gothic';font-weight:600;
       font-size:13pt">p(Doom)1</div>
  <div style="position:absolute;left:57mm;top:15mm;font-size:7.5pt;width:26mm;line-height:1.45">
    the office cat requests playtesters</div>
  <div style="position:absolute;left:57mm;bottom:5mm" class="mono tiny">pdoom1.com</div>
</div>"""

CARD_DEFS = [("C1","geometric",card_c1),("C2","terminal",card_c2),
             ("C3","condensed",card_c3),("C4","dial",card_c4),("C5","cat",card_c5)]
faceoff = "".join(
    f"""<div style="width:92mm;margin-bottom:4mm">
      <div style="border:0.3mm solid #888;width:85.6mm">{fn()}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:1.5mm">
        <span class="mono small"><b>{i}</b> &middot; {name} &middot;
        <span class="tiny">cut-sheet p.{22+n+1}</span></span>{tick(i)}</div>
    </div>"""
    for n,(i,name,fn) in enumerate(CARD_DEFS))
PAGES.append(sheet(
    h("Business card face-off", "five designs at true size &middot; tick the one you'd keep in your wallet") +
    f'<div style="display:flex;flex-wrap:wrap;gap:2mm 8mm">{faceoff}'
    """<div style="width:92mm" class="box">
      <div class="small" style="line-height:1.6">Each design has its own uncut sheet of ten
      at the back of the pack (pages 23&ndash;27) &mdash; scissors turn a tick into a
      pocketful. The sampler sheet p.27 carries two of each for pocket A/B tests.</div>
    </div></div>""", folio="12/30"))

# ================================================================ p.13 THE DIAL (landscape)
big_dial = dial_svg(170, label_size=5.0, pivot=True, sw=0.8)
PAGES.append(sheet(f"""
<div style="position:absolute; top:2mm; left:0; right:0; text-align:center">
  <div style="font-family:'Liberation Sans Narrow'; font-weight:bold; font-size:34pt;
       letter-spacing:0.5mm">P(DOOM) RATING TODAY</div>
</div>
<div style="position:absolute; top:22mm; left:55mm">{big_dial}</div>
<div style="position:absolute; top:118mm; left:55mm; width:170mm" class="boxinv"
     ><div style="text-align:center; font-family:'Liberation Sans Narrow'; font-weight:bold;
     font-size:15pt; letter-spacing:0.6mm">SOURCE-AVAILABLE ALPHA &middot; PDOOM1.COM</div></div>
<div style="position:absolute; top:140mm; left:20mm; right:20mm; border-top:0.4mm solid #000"></div>
<div style="position:absolute; top:142mm; left:20mm; right:20mm" class="mono tiny">
CUT along the outer solid border of this whole panel. The dotted circle at the dial's
hinge is the pivot &mdash; assembly and pointer are on the next page. Sign modelled, with
respect and one addition, on the Australian fire danger rating sign; the addition is the
band the fire signs never needed.</div>
<div style="position:absolute; top:8mm; left:12mm; width:36mm" class="small">
  <div class="cap" style="font-weight:bold">Field prop No. 1</div>
  <div class="tiny" style="margin-top:1mm">clipboard-mounted<br>audience-adjustable<br>
  doom forecaster</div></div>
<div style="position:absolute; top:8mm; right:12mm; width:36mm; text-align:right" class="small">
  <div class="cap" style="font-weight:bold">Operating note</div>
  <div class="tiny" style="margin-top:1mm">the needle only<br>ratchets clockwise*<br>
  <span style="font-size:5.5pt">*mechanically untrue, thematically accurate</span></div></div>
<div style="position:absolute; top:0; left:0; width:281mm; height:160mm;
     border:0.6mm solid #000"></div>
""", klass="land", folio="13/30"))

# ================================================================ p.14 pointer + stand (landscape)
def pointer_svg():
    return """<svg width="120mm" height="40mm" viewBox="0 0 120 40"
     xmlns="http://www.w3.org/2000/svg">
  <path d="M 6 20 L 14 12 L 96 17 L 112 20 L 96 23 L 14 28 Z" fill="#000"/>
  <circle cx="18" cy="20" r="6.5" fill="#fff" stroke="#000" stroke-width="0.6"/>
  <circle cx="18" cy="20" r="2.6" fill="none" stroke="#000" stroke-width="0.5"
      stroke-dasharray="1.2 1"/>
  <line x1="16.4" y1="20" x2="19.6" y2="20" stroke="#000" stroke-width="0.4"/>
  <line x1="18" y1="18.4" x2="18" y2="21.6" stroke="#000" stroke-width="0.4"/>
  <text x="60" y="37" font-family="Liberation Mono" font-size="3" text-anchor="middle">
  POINTER &mdash; cut on the outline, punch the marked hole</text>
</svg>"""
PAGES.append(sheet(f"""
{h("Dial assembly", "one pointer, one stand, four steps, zero excuses")}
<div style="display:flex; gap:8mm">
<div style="width:150mm">
  <div class="box" style="margin-bottom:5mm">{pointer_svg()}</div>
  <div class="box" style="margin-bottom:5mm">{pointer_svg()}</div>
  <div class="cap-lab">Two pointers because the first one always gets bent in the bag.</div>
  <div class="box" style="margin-top:5mm; height:52mm; position:relative">
    <div style="position:absolute; top:0mm; left:46mm; bottom:0; border-left:0.4mm dashed #000"></div>
    <div style="position:absolute; top:0mm; left:92mm; bottom:0; border-left:0.4mm dashed #000"></div>
    <div style="position:absolute; top:20mm; left:8mm" class="small cap">tape<br>here</div>
    <div style="position:absolute; top:20mm; left:56mm" class="small cap">easel<br>spine</div>
    <div style="position:absolute; top:20mm; left:102mm" class="small cap">foot</div>
    <div style="position:absolute; bottom:2mm; left:8mm" class="mono tiny">
    STAND &mdash; cut out, fold on dashed lines into a Z, tape the first panel to the
    sign's back. The dial now stands on a table.</div>
  </div>
</div>
<div style="flex:1">
  <div class="cap" style="font-weight:bold; font-size:11pt">Assembly</div>
  <ol style="margin:3mm 0 0 5mm; line-height:1.9; font-size:9.5pt">
    <li>Cut out the sign (p.13) on its solid border.</li>
    <li>Cut out one pointer; punch the marked pivot holes in pointer and sign
        (hole punch, or a pen nib on a soft surface).</li>
    <li>Fasten with a split pin / brass fastener. No pin? Unbend one loop of a
        paperclip through both holes and tape the back.</li>
    <li>Fold the stand, tape it on, stand it next to the clipboard. Invite
        strangers to set today's rating. Do not reassure them.</li>
  </ol>
  <div class="boxinv small" style="margin-top:5mm">Prints better on card stock.
  Ordinary paper works if you laminate it or back it with the cereal box you were
  going to recycle anyway.</div>
  <div style="margin-top:5mm">{dial_svg(60, labels=False, needle=8, tick_pct=False)}
  <div class="cap-lab">factory setting</div></div>
</div>
</div>""", klass="land", folio="14/30"))

# ================================================================ p.15 pocket dials
mini = dial_svg(62, label_size=2.7, sw=0.4)
mini_cells = "".join(f"""
<div style="width:92mm; height:62mm; position:relative; border:0.4mm solid #000;
     margin-bottom:0; overflow:hidden">
  <div style="position:absolute; top:5mm; left:4mm">{mini}</div>
  <div style="position:absolute; top:6mm; right:4mm; width:20mm" class="tiny">
    <b>MY P(DOOM)</b><br><br>date:<div class="writeline" style="height:5mm"></div>
    initials:<div class="writeline" style="height:5mm"></div></div>
  <div style="position:absolute; bottom:2mm; left:4mm" class="mono tiny">
    draw your needle on the dial &middot; keep the card &middot; pdoom1.com</div>
</div>""" for _ in range(4))
PAGES.append(sheet(
    h("Pocket doom dials", "cut the four cards &middot; hand a pen to a stranger &middot; they draw their own needle and keep it") +
    f'<div style="display:flex; flex-wrap:wrap; gap:4mm">{mini_cells}</div>' +
    """<div class="box small" style="margin-top:4mm; line-height:1.6">Why this works: nobody
    will tell you their p(doom), but everybody will draw it. The card is a souvenir, the
    URL is on the souvenir, and the conversation has already happened. Restock from p.15
    of this pack.</div>""",
    folio="15/30"))

# ================================================================ p.16 tent card
PAGES.append(sheet(f"""
<div class="tentpanel" style="top:0; height:120mm">
  <div style="transform:rotate(180deg); transform-origin:center; width:194mm; height:120mm;
       position:relative">
    <div style="position:absolute; top:16mm; left:0; right:0; text-align:center;
         font-family:'URW Gothic'; font-weight:600; font-size:30pt">p(Doom)1</div>
    <div style="position:absolute; top:34mm; left:0; right:0; text-align:center;
         font-size:11pt">{ONE_LINER}</div>
    <div style="position:absolute; top:48mm; left:47mm">{dial_svg(100, label_size=3.2, needle=25)}</div>
    <div style="position:absolute; bottom:6mm; left:0; right:0; text-align:center"
         class="mono small">pdoom1.com &middot; source-available alpha</div>
  </div>
</div>
<div style="position:absolute; top:120mm; left:0; right:0" class="foldline"></div>
<div class="tentpanel" style="top:120mm; height:120mm">
  <div style="position:absolute; top:14mm; left:0; right:0; text-align:center;
       font-family:'Liberation Sans Narrow'; font-weight:bold; font-size:26pt">
       ASK ME ABOUT<br>THE GAME YOU CANNOT WIN</div>
  <div style="position:absolute; top:52mm; left:47mm">{dial_svg(100, label_size=3.2, needle=25)}</div>
  <div style="position:absolute; bottom:5mm; left:0; right:0; text-align:center"
       class="mono small">p(Doom)1 &middot; pdoom1.com</div>
</div>
<div style="position:absolute; top:240mm; left:0; right:0" class="foldline"></div>
<div style="position:absolute; top:240mm; left:0; right:0; height:41mm">
  <div style="padding:4mm" class="mono tiny">BASE FLAP &mdash; fold both dashed lines the
  same way, tape this flap under the first panel: triangle tent, two faces, stands on any
  table. Faces read correctly from both sides.</div>
</div>""", folio="16/30"))

# ================================================================ p.17 one-cut zine (landscape)
ZW, ZH = 70.25, 97.0
def zp(content, col, row, flip):
    x = col * ZW; y = row * ZH
    inner = f'<div class="zin{" zflip" if False else ""}">{content}</div>'
    flipcss = "transform:rotate(180deg);" if flip else ""
    return (f'<div class="zpanel" style="left:{x}mm; top:{y}mm">'
            f'<div style="width:{ZW}mm; height:{ZH}mm; {flipcss}">{inner}</div></div>')
def ztitle(t):
    return f'<div style="font-family:\'Liberation Sans Narrow\'; font-weight:bold; font-size:14pt; margin-bottom:3mm" class="cap">{t}</div>'
zbody = 'font-size:8.5pt; line-height:1.55'
ZPAGES = {
 1: f"""<div style="text-align:center; padding-top:8mm">
     <div style="font-family:'URW Gothic'; font-weight:600; font-size:19pt">p(Doom)1</div>
     <div style="margin:4mm 0">{dial_svg(50, labels=False, needle=24, tick_pct=False, sw=0.4)}</div>
     <div class="small">an eight-page briefing<br>on a game you cannot win</div>
     <div class="mono tiny" style="margin-top:6mm">fold-it-yourself edition</div></div>""",
 2: ztitle("1 &middot; the premise") + f'<div style="{zbody}">You run an underfunded AI '
    'safety lab. Better-resourced rivals are racing toward AGI. Your job is not to win '
    '&mdash; alignment is not a thing you finish. Your job is to buy time.</div>',
 3: ztitle("2 &middot; the work") + f'<div style="{zbody}">Hire researchers &mdash; Safety, '
    'Capabilities, Interpretability, Alignment. Balance their traits. Handle burnout and '
    'poaching. Respond to rival labs and to events you did not choose.</div>',
 4: ztitle("3 &middot; the catch") + f'<div style="{zbody}">There is no win screen. '
    '<b>Every run ends in defeat.</b> Your score is the number of turns you survived, and '
    'the end screen tells you honestly what killed you.</div>',
 5: ztitle("4 &middot; the fairness") + f'<div style="{zbody}">Deterministic seeds: a '
    'given seed plays out identically for everyone. Scores are comparable. Your defeat '
    'and my defeat can be measured against each other, which is its own comfort.</div>',
 6: ztitle("5 &middot; the cat") + f'<div style="{zbody}">Report a bug (press N in-game) '
    'or help playtest, and your actual cat can be drawn into the game as an Office Cat '
    'with five doom-level variants. This is a real program with credits listings.</div>'
    f'<div style="text-align:center; margin-top:3mm"><img src="assets/cat_lamp.png" style="width:26mm"></div>',
 7: ztitle("6 &middot; the status") + f'<div style="{zbody}">Alpha, {VERSION}, built in '
    f'Godot 4.5.1. {PLATFORM_SLASHES}, free download. {UNSHIPPED_NOTE} Source-available &mdash; not '
    'open source; the source is public to read, and an open-source engine licence is '
    'planned around 1.0. Builds are not yet code-signed; your OS will grumble once.</div>',
 8: f"""<div style="text-align:center; padding-top:16mm">
     <div class="mono" style="font-size:9pt; line-height:2.2">pdoom1.com<br>
     github.com/PipFoweraker/pdoom1<br>team@pdoom1.com</div>
     <div style="margin-top:8mm">{paren_dot_mark(28)}</div></div>""",
}
zine_panels = (
    zp(ZPAGES[5], 0, 0, True) + zp(ZPAGES[4], 1, 0, True) +
    zp(ZPAGES[3], 2, 0, True) + zp(ZPAGES[2], 3, 0, True) +
    zp(ZPAGES[6], 0, 1, False) + zp(ZPAGES[7], 1, 1, False) +
    zp(ZPAGES[8], 2, 1, False) + zp(ZPAGES[1], 3, 1, False))
PAGES.append(sheet(f"""
{zine_panels}
<div style="position:absolute; left:0; right:0; top:{ZH}mm" class="foldline"></div>
<div style="position:absolute; top:0; bottom:0; left:{ZW}mm" class="foldline"></div>
<div style="position:absolute; top:0; bottom:0; left:{ZW}mm; border-left:0.3mm dashed #999"></div>
<div style="position:absolute; top:0; bottom:0; left:{2*ZW}mm; border-left:0.3mm dashed #999"></div>
<div style="position:absolute; top:0; bottom:0; left:{3*ZW}mm; border-left:0.3mm dashed #999"></div>
<div style="position:absolute; left:{ZW}mm; width:{2*ZW}mm; top:{ZH}mm; border-top:1mm solid #000"></div>
<div style="position:absolute; left:{ZW+18}mm; top:{ZH-6}mm" class="mono tiny"
     >&#9986; CUT ONLY THIS HEAVY LINE</div>
<div style="position:absolute; right:2mm; bottom:1mm; width:64mm" class="mono tiny">
ONE-CUT ZINE: fold in half long-ways, cut the heavy line, fold into an 8-page A7 booklet
(fold lengthwise, push ends inward so the slit opens, wrap flat). Top row is upside down
on purpose.</div>
""", klass="land", folio="17/30"))

# ================================================================ p.18 survey
def opts(*labels):
    return " &nbsp; ".join(f'<span class="tickrow"><span class="tick"></span>'
                           f'<span class="ticklab">{l}</span></span>' for l in labels)
PAGES.append(sheet(
    h("Sixty-second survey", "clipboard page &middot; tick fast, no wrong answers, one page then flip") +
    f"""
<div class="q"><div class="qt">1. Had you heard the term &ldquo;p(doom)&rdquo; before today?</div>
{opts("yes","no","heard it, couldn't define it")}</div>
<div class="q"><div class="qt">2. A strategy game where every run ends in defeat and the
score is how long you lasted. Gut reaction?</div>
{opts("bleak, love it","bleak, hate it","roguelike players eat this daily","need to see it")}</div>
<div class="q"><div class="qt">3. Where would you play it?</div>
{opts("Windows","macOS","Linux","browser","phone","Steam Deck")}</div>
<div class="q"><div class="qt">4. Mark today's personal p(doom) on the dial:</div>
<div style="margin-top:2mm">{dial_svg(88, label_size=2.9)}</div></div>
<div class="q"><div class="qt">5. Would you playtest an alpha?</div>
{opts("yes","no","only if the cat program is real (it is)")}</div>
<div class="q"><div class="qt">6. Optional &mdash; where should the playtest invite go?
<span class="tiny">(used for that one invite, nothing else)</span></div>
<div class="writeline" style="margin-top:2mm"></div></div>
<div class="mono tiny">collected on paper by Pip Foweraker &middot; pdoom1.com</div>""",
    folio="18/30"))

# ================================================================ p.19 channels
PAGES.append(sheet(
    h("Where would you look for it?", "distribution is a decision we haven't made &mdash; your tick is data") +
    f"""
<div class="q"><div class="qt">1. You hear about an indie AI-lab strategy game. Where do
you go first?</div>
<div style="display:flex; flex-direction:column; gap:2.5mm; margin-top:2mm">
{''.join(f'<div>{opts(o)}</div>' for o in
 ["Steam", "itch.io", "the game's own website", "GitHub releases",
  "a browser version, no download", "phone app store", "I wait for a friend to make me"])}
</div></div>
<div class="q"><div class="qt">2. What would you type into a search box to find it?</div>
<div class="writeline"></div></div>
<div class="q"><div class="qt">3. Fair price for the finished 1.0, one honest tick:</div>
{opts("free forever","pay-what-you-want","$5","$10","$20","depends on hours of play")}</div>
<div class="q"><div class="qt">4. The alpha today is a free download from GitHub via
pdoom1.com. Does knowing that change your answer to Q3?</div>
{opts("no","yes, higher","yes, lower","stop asking hard questions")}</div>
<div class="rule"></div>
<div class="small" style="line-height:1.6">Everything above is a question about the future,
not a promise. Current truth: free source-available alpha, downloadable now for
{PLATFORM_PROSE}. {UNSHIPPED_NOTE}</div>""",
    folio="19/30"))

# ================================================================ p.20 tally
TALLY_IDS = ([w[0] for w in WMS] + [c[0] for c in CASES] + [t[0] for t in TAGS] +
             [b[0] for b in BODIES] + ["M0","M1","M2","M3","M4"] +
             [p[0] for p in PORTS] + [e[0] for e in EVENTS] + [k[0] for k in CATS] +
             [c[0] for c in CARD_DEFS] + ["P1","P2","P3","P4","S1","S2","S3"])
tally_cells = "".join(
    f'<div style="width:30mm; display:flex; align-items:center; gap:2mm; margin-bottom:2.6mm">'
    f'<span class="tickid" style="width:8mm">{i}</span>'
    f'<span style="flex:1; border-bottom:0.3mm solid #000; height:6mm"></span></div>'
    for i in TALLY_IDS)
PAGES.append(sheet(
    h("Tally &amp; field notes", "five-bar-gate the ticks per ID as you go, or at the cafe after") +
    f'<div style="display:flex; flex-wrap:wrap; gap:0 6mm">{tally_cells}</div>' +
    '<div class="rule"></div>' +
    '<div class="cap small" style="font-weight:bold; margin-bottom:2mm">Things people actually said</div>' +
    ''.join('<div class="writeline" style="margin-bottom:3mm"></div>' for _ in range(10)),
    folio="20/30"))

# ================================================================ p.21-22 posters
def poster_p1():
    return f"""
<div style="width:132mm; height:190mm; position:relative; background:#fff; overflow:hidden">
  <div style="position:absolute; top:0; left:0; width:132mm; height:8mm; background:#000"></div>
  <div style="position:absolute; top:18mm; left:10mm; font-family:'URW Gothic';
       font-weight:600; font-size:42pt; line-height:1.05">p(Doom)1</div>
  <div style="position:absolute; top:44mm; left:10mm; width:78mm; height:1.4mm; background:#000"></div>
  <div style="position:absolute; top:52mm; left:10mm; width:112mm;
       font-family:'Liberation Sans Narrow'; font-weight:bold; font-size:19pt">
       EVERY RUN ENDS IN DEFEAT.<br>YOUR SCORE IS HOW LONG YOU LASTED.</div>
  <div style="position:absolute; top:92mm; left:22mm">{dial_svg(88, label_size=2.9, needle=20)}</div>
  <div style="position:absolute; bottom:12mm; left:10mm; width:88mm" class="mono small">
    pdoom1.com &middot; free source-available alpha<br>{PLATFORM_SLASHES}</div>
  <div style="position:absolute; bottom:0; right:0; width:26mm; height:26mm; background:#000;
       border-radius:50% 0 0 0"></div>
</div>"""
def poster_p2():
    return f"""
<div style="width:132mm; height:190mm; position:relative; background:#fff; overflow:hidden">
  <img src="assets/port_burnout.png" style="position:absolute; top:0; left:0; width:132mm">
  <div style="position:absolute; top:134mm; left:0; right:0; background:#000; color:#fff;
       padding:5mm 8mm; font-family:'Liberation Sans Narrow'; font-weight:bold; font-size:17pt">
       YOUR SENIOR RESEARCHER IS BURNED OUT.<br>YOUR RIVALS' AREN'T.</div>
  <div style="position:absolute; bottom:8mm; left:8mm; font-family:'URW Gothic';
       font-weight:600; font-size:17pt">p(Doom)1</div>
  <div style="position:absolute; bottom:9mm; right:8mm" class="mono small">pdoom1.com</div>
</div>"""
def poster_p3():
    return f"""
<div style="width:132mm; height:190mm; position:relative; background:#fff; overflow:hidden">
  <div style="position:absolute; top:12mm; left:0; right:0; text-align:center;
       font-family:'Liberation Sans Narrow'; font-weight:bold; font-size:26pt">
       P(DOOM) RATING TODAY</div>
  <div style="position:absolute; top:34mm; left:11mm">{dial_svg(110, label_size=3.4, pivot=False)}</div>
  <div style="position:absolute; top:102mm; left:0; right:0; text-align:center" class="small">
       (mark it yourself &mdash; pen on a string optional)</div>
  <div style="position:absolute; top:118mm; left:16mm; right:16mm" class="boxinv"
       ><div style="text-align:center; font-family:'Liberation Sans Narrow'; font-weight:bold;
       font-size:13pt">THE GAME ABOUT MOVING THIS NEEDLE<br>IS CALLED p(Doom)1</div></div>
  <div style="position:absolute; bottom:10mm; left:0; right:0; text-align:center"
       class="mono small">pdoom1.com &middot; source-available alpha</div>
</div>"""
def poster_p4():
    return f"""
<div style="width:132mm; height:190mm; position:relative; background:#fff; overflow:hidden">
  <img src="assets/ev_board.png" style="position:absolute; top:0; left:-33mm; height:132mm">
  <div style="position:absolute; top:132mm; left:0; right:0; background:#000; color:#fff;
       padding:5mm 8mm; font-family:'Liberation Sans Narrow'; font-weight:bold; font-size:19pt">
       THE BOARD WILL SEE YOU NOW.</div>
  <div style="position:absolute; bottom:20mm; left:8mm; width:116mm; font-size:9.5pt">
       Rival labs act. Events land. Doom rises. You explain yourself.</div>
  <div style="position:absolute; bottom:8mm; left:8mm; font-family:'URW Gothic';
       font-weight:600; font-size:15pt">p(Doom)1</div>
  <div style="position:absolute; bottom:9.5mm; right:8mm" class="mono small">pdoom1.com</div>
</div>"""
for pair, ids, folio in [((poster_p1, poster_p2), ("P1","P2"), "21/30"),
                         ((poster_p3, poster_p4), ("P3","P4"), "22/30")]:
    a, b = pair
    PAGES.append(sheet(f"""
<div style="display:flex; gap:5mm; align-items:flex-start">
  <div>
    <div style="border:0.4mm solid #000">{a()}</div>
    <div style="display:flex; justify-content:space-between; margin-top:2mm">
      <span class="mono small"><b>{ids[0]}</b></span>{tick(ids[0])}</div>
  </div>
  <div style="width:52mm; padding-top:4mm">
    <div class="cap small" style="font-weight:bold">Poster pair {ids[0]}/{ids[1]}</div>
    <div class="tiny" style="margin-top:2mm; line-height:1.6">Two A5-ish posters per page.
    Tick the one that would stop you in a corridor. Cut on the frame if you want to pin
    one up somewhere it's welcome.</div>
  </div>
</div>
<div style="display:flex; gap:5mm; margin-top:4mm; flex-direction:row-reverse;
     justify-content:flex-end">
  <div>
    <div style="border:0.4mm solid #000; transform:scale(0.48); transform-origin:top left">
    {b()}</div>
  </div>
</div>""" if False else f"""
<div style="display:flex; gap:6mm">
  <div>
    <div style="border:0.4mm solid #000; transform:scale(0.68); transform-origin:top left;
         width:132mm; height:190mm; margin-bottom:-58mm; margin-right:-40mm">{a()}</div>
    <div style="display:flex; gap:3mm; align-items:center">{tick(ids[0])}</div>
  </div>
  <div>
    <div style="border:0.4mm solid #000; transform:scale(0.68); transform-origin:top left;
         width:132mm; height:190mm; margin-bottom:-58mm; margin-right:-40mm">{b()}</div>
    <div style="display:flex; gap:3mm; align-items:center">{tick(ids[1])}</div>
  </div>
</div>
<div class="mono tiny" style="position:absolute; bottom:4mm; left:0">
Poster pair &middot; shown at 68% &middot; tick the one that would stop you in a corridor.</div>
""", folio=folio))

# ================================================================ p.23-27 card cut sheets
def card_cut_sheet(fn, id_, name, folio, mixed=None):
    cells = []
    gx, gy = 12, 5.5  # grid origin within sheet (170x275 grid)
    for r in range(5):
        for c in range(2):
            x = gx + c * 85; y = gy + r * 55
            if mixed:
                f2 = mixed[(r * 2 + c) % len(mixed)][2]
                inner = f2()
            else:
                inner = fn()
            cells.append(f'<div class="card" style="left:{x}mm; top:{y}mm">{inner}</div>')
    # cut lines: light dashes along grid
    lines = []
    for c in range(3):
        x = gx + c * 85
        lines.append(f'<div style="position:absolute; left:{x}mm; top:{gy-3}mm; height:{275+6}mm; border-left:0.25mm dashed #666"></div>')
    for r in range(6):
        y = gy + r * 55
        lines.append(f'<div style="position:absolute; top:{y}mm; left:{gx-3}mm; width:{170+6}mm; border-top:0.25mm dashed #666"></div>')
    label = (f'<div style="position:absolute; left:{gx-3}mm; top:1mm" class="mono tiny">'
             f'{id_} &middot; {name} &middot; ten per sheet &middot; cut on dashed lines</div>')
    return sheet("".join(cells) + "".join(lines) + label, folio=folio)

PAGES.append(card_cut_sheet(card_c1, "C1", "geometric", "23/30"))
PAGES.append(card_cut_sheet(card_c2, "C2", "terminal", "24/30"))
PAGES.append(card_cut_sheet(card_c3, "C3", "condensed", "25/30"))
PAGES.append(card_cut_sheet(card_c4, "C4", "dial", "26/30"))
PAGES.append(card_cut_sheet(None, "C5", "sampler", "27/30", mixed=CARD_DEFS))

# ================================================================ p.28-30 slips
def slip_sheet(inner_fn, id_, name, folio):
    slips = []
    for r in range(3):
        y = 2 + r * 92
        slips.append(f'<div style="position:absolute; left:2mm; top:{y}mm; width:190mm; '
                     f'height:88mm; overflow:hidden">{inner_fn()}</div>')
        if r:
            slips.append(f'<div style="position:absolute; left:0; right:0; top:{y-2}mm" class="cutline"></div>')
    lab = (f'<div style="position:absolute; right:0; bottom:0" class="mono tiny">{id_} &middot; '
           f'{name} &middot; three per page, cut on solid lines</div>')
    return sheet("".join(slips) + lab, folio=folio)

def slip_s1():
    return f"""
<div style="position:relative; width:190mm; height:88mm; border:0.4mm solid #000">
  <div style="position:absolute; top:6mm; left:7mm; font-family:'URW Gothic'; font-weight:600;
       font-size:22pt">p(Doom)1</div>
  <div style="position:absolute; top:17mm; left:7mm; width:108mm; font-size:9.5pt;
       line-height:1.5">{ONE_LINER} Hire researchers, weather the events, watch the doom
       meter climb. <b>There is no win screen; your score is how long you lasted.</b></div>
  <div style="position:absolute; bottom:6mm; left:7mm" class="mono small">
    pdoom1.com &middot; github.com/PipFoweraker/pdoom1<br>
    free download &middot; {PLATFORM_SLASHES} &middot; source-available alpha {VERSION}</div>
  <div style="position:absolute; top:8mm; right:7mm">{dial_svg(58, label_size=2.5, needle=23, sw=0.4)}</div>
  <div style="position:absolute; bottom:6mm; right:7mm" class="tiny" >S1</div>
</div>"""
def slip_s2():
    return f"""
<div style="position:relative; width:190mm; height:88mm; border:0.4mm solid #000">
  <div style="position:absolute; top:0; left:0; right:0; height:14mm; background:#000;
       color:#fff; font-family:'Liberation Sans Narrow'; font-weight:bold; font-size:17pt;
       padding:3mm 7mm">BETWEEN ROUNDS? RUN AN AI LAB. LOSE SLOWER.</div>
  <div style="position:absolute; top:19mm; left:7mm; width:112mm; font-size:9.5pt;
       line-height:1.5">Turn-based lab management, single player, runs on a laptop that has
       seen things. Draft researchers, manage burnout, answer to the board. Every run ends
       in defeat &mdash; the score is turns survived, like a gauntlet you can brag about.
       Deterministic seeds mean your loss and your mate's loss are comparable.</div>
  <div style="position:absolute; bottom:6mm; left:7mm" class="mono small">
    pdoom1.com &middot; free alpha &middot; report a bug in-game (press N) and your cat can
    be drawn into the game</div>
  <div style="position:absolute; top:22mm; right:7mm"><img src="assets/cat_lamp.png"
       style="width:42mm"></div>
  <div style="position:absolute; bottom:6mm; right:7mm" class="tiny">S2</div>
</div>"""
def slip_s3():
    return f"""
<div style="position:relative; width:190mm; height:88mm; border:0.4mm solid #000">
  <div style="position:absolute; top:6mm; left:7mm; font-family:'Liberation Sans Narrow';
       font-weight:bold; font-size:16pt; width:130mm">A GAME ABOUT THE ALIGNMENT PROBLEM
       THAT REFUSES TO PRETEND YOU CAN WIN</div>
  <div style="position:absolute; top:26mm; left:7mm; width:120mm; font-size:9.5pt;
       line-height:1.5">p(Doom)1 is a strategy game: run an underfunded safety lab while
       rivals race to AGI. Alignment is not a thing you finish, so the game doesn't let
       you finish it &mdash; you buy time, and the end screen attributes your defeat
       honestly. Alpha, source-available, free. Playtesters and bug reports genuinely
       shape it &mdash; the in-game reporter is one keypress (N).</div>
  <div style="position:absolute; bottom:6mm; left:7mm" class="mono small">
    pdoom1.com &middot; team@pdoom1.com &middot; github.com/PipFoweraker/pdoom1</div>
  <div style="position:absolute; top:30mm; right:7mm">{dial_svg(52, labels=False, needle=12, tick_pct=False, sw=0.4)}
    <div class="tiny" style="text-align:center">current vibes</div></div>
  <div style="position:absolute; bottom:6mm; right:7mm" class="tiny">S3</div>
</div>"""

PAGES.append(slip_sheet(slip_s1, "S1", "general handout", "28/30"))
PAGES.append(slip_sheet(slip_s2, "S2", "tabletop-shop flavour", "29/30"))
PAGES.append(slip_sheet(slip_s3, "S3", "EAGx flavour", "30/30"))

# ================================================================= render
HTML_DOC = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>p(Doom)1 field pack</title>
<style>{CSS}</style></head>
<body>{''.join(PAGES)}</body></html>"""

if __name__ == "__main__":
    html_path = os.path.join(HERE, "pack.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(HTML_DOC)
    print(f"wrote {html_path} ({len(PAGES)} sheets)")
    from weasyprint import HTML
    pdf_path = os.path.join(HERE, "pdoom1-clipboard-pack.pdf")
    HTML(html_path, base_url=HERE).write_pdf(pdf_path)
    print(f"wrote {pdf_path}")
