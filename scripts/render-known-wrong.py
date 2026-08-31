#!/usr/bin/env python
"""Render data/acknowledgements.json to /known-wrong/ for players.

WHAT THIS PUBLISHES
Every divergence this site's checks have found, that somebody decided to
tolerate, with the date that decision expires. Not a status page: a status
page says what is up. This says what is wrong, who agreed to live with it,
and when that agreement runs out.

WHY IT IS WORTH PUBLISHING
The acknowledgement clock exists because a check that SEES a divergence,
prints it and exits 0 by design is telling the truth while the exit code
lies -- "class 5, the knowing allowlist". The fix was to give every
acceptance a clock. Publishing the clock is the same move one step further
out: an expiry date nobody can see is only slightly better than no expiry
date.

THE CLOCK IS COMPUTED IN THE BROWSER, NOT BAKED IN. A page about expiry
dates that reported a stale "14 days left" would be the failure it
documents. The entries are rendered at build time; `data-review-by` is
rendered as the raw date and the days-remaining is worked out on load, so
the number is right whether the page was generated this morning or in June.

THE LEDGER IS NOT COPIED INTO public/. data/acknowledgements.json lives at
the repo root deliberately -- it is CI metadata and public/ is rsynced.
Entries are rendered INTO the HTML instead, so publishing the page adds no
new served file and no new deploy-excludes question.

WHAT IT DOES NOT DO: run the checks. Whether an entry is still FIRING, has
gone STALE, or is UNVERIFIABLE is a property of a live run, not of the
ledger, and running 76 checks at page-build time would make this the
slowest generator in the repo for a fact that changes on its own schedule.
The page says what the ledger says and links to the audit; it does not
claim to know today's answer.
"""
import argparse
import html
import importlib.util
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "acknowledgements.json"
OUT = ROOT / "public" / "known-wrong" / "index.html"

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _design_notes():
    path = ROOT / "scripts" / "sync" / "sync-design-notes.py"
    spec = importlib.util.spec_from_file_location("sync_design_notes", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DN = _design_notes()


def load():
    """Read the ledger through its own loader, so this page cannot publish a
    shape the checks would refuse. acknowledgements.py rejects the WHOLE ledger
    rather than skipping a bad entry -- a skipped entry resurfaces as a fresh
    finding and sends somebody hunting a bug nobody introduced."""
    path = ROOT / "scripts" / "acknowledgements.py"
    spec = importlib.util.spec_from_file_location("acknowledgements", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import json
    with open(LEDGER, encoding="utf-8") as f:
        raw = json.load(f)
    return raw, mod


def esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


# WHO ACCEPTED IT is the most important column and the least obvious. Some
# entries are Pip's ruling. Others say, in their own words, that they are NOT --
# that an agent could not proceed, would not act unilaterally, and left the
# question. Those are open questions wearing the same shape as decisions, and
# collapsing the two would hide the only ones that need somebody.
SEAT_MARKERS = ("not pip's ruling", "he has not been asked", "not pip's ruling --")


def is_open_question(accepted_by):
    low = (accepted_by or "").lower()
    return any(m in low for m in SEAT_MARKERS)


def entry_html(a):
    key = esc(a.get("key"))
    check = esc(a.get("check"))
    review_by = a.get("review_by") or ""
    open_q = is_open_question(a.get("accepted_by"))

    badge = ('<span class="tag t-ask">awaiting a decision</span>' if open_q
             else '<span class="tag t-agreed">accepted</span>')

    return (
        '<article class="ack">'
        '<div class="ack-head">'
        f'<code class="ack-key">{key}</code>'
        f'{badge}'
        f'<span class="clock" data-review-by="{esc(review_by)}">&hellip;</span>'
        '</div>'
        f'<p class="what">{esc(a.get("what"))}</p>'
        '<details><summary>Why it has not been fixed</summary>'
        f'<p>{esc(a.get("why"))}</p>'
        f'<p class="meta"><strong>Accepted by:</strong> {esc(a.get("accepted_by"))}</p>'
        f'<p class="meta"><strong>On {esc(review_by)} this acceptance expires, and then:</strong> '
        f'{esc(a.get("on_expiry"))}</p>'
        f'<p class="meta"><strong>Found by:</strong> <code>{check}</code>'
        f'{(" &middot; " + esc(a.get("source"))) if a.get("source") else ""}</p>'
        '</details>'
        '</article>'
    )


def build(check_only=False):
    if not LEDGER.exists():
        print(f"FAIL: {LEDGER} does not exist.")
        return 2
    raw, _mod = load()
    acks = raw.get("acknowledgements") or []

    for a in acks:
        rb = a.get("review_by")
        if not rb or not DATE.match(str(rb)):
            print(f"REFUSING TO WRITE: entry {a.get('key')!r} has no usable review_by "
                  f"({rb!r}). Every acceptance on this page carries a date; one without "
                  "would render as an open-ended excuse, which is the shape the "
                  "acknowledgement clock exists to abolish.")
            return 1

    n_ask = sum(1 for a in acks if is_open_question(a.get("accepted_by")))

    if acks:
        body = "".join(entry_html(a) for a in acks)
        count_line = (
            f'<p class="lede">{len(acks)} thing'
            f'{"" if len(acks) == 1 else "s"} this site knows are wrong right now.'
            + (f' {n_ask} of them {"is" if n_ask == 1 else "are"} not a decision at all &mdash; '
               'an automated change stopped, refused to rule on something that was not its '
               'call, and left the question.' if n_ask else '')
            + '</p>')
    else:
        # An empty ledger is a real state and must not read as an achievement:
        # the checks may simply not have found anything they were pointed at.
        body = ('<article class="ack"><p class="what">Nothing is currently acknowledged. '
                'That means no check has found a divergence somebody has decided to live '
                'with &mdash; not that nothing is wrong. The checks only see what they '
                'were built to look at.</p></article>')
        count_line = '<p class="lede">Nothing is on this list today.</p>'

    intro = (
        count_line +
        '<p class="sub">When a check here finds something wrong that cannot be fixed '
        'immediately, the finding is not silenced &mdash; it is <em>accepted on a date</em>. '
        'The finding keeps printing, and the acceptance expires. After that the build fails '
        'on <em>&ldquo;this acceptance expired, re-accept or fix&rdquo;</em>, which is a '
        'question a person can answer, rather than on the original problem, which usually '
        'they cannot.</p>'
        '<p class="sub">Full reasoning for every entry, including the ones that have since '
        'been cleared, is in <code>data/acknowledgements.json</code> in the website '
        'repository. See also <a href="/development-rhythm/">how irregular the pace has '
        'been</a> and <a href="/ledger/">the league ledger</a>.</p>'
    )

    style = """
    .ack{border:1px solid var(--hair,#3A342E);border-radius:10px;padding:1rem 1.1rem;margin:1rem 0;background:var(--panel,#1C1917)}
    .ack-head{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-bottom:.6rem}
    .ack-key{font-size:.78rem;color:var(--ink-3,#A79E92);word-break:break-all}
    .tag{display:inline-block;padding:.05rem .5rem;border-radius:99px;font-size:.72rem;border:1px solid}
    .t-ask{color:#F6A800;border-color:#F6A800}
    .t-agreed{color:#A79E92;border-color:#3A342E}
    .clock{font-size:.78rem;margin-left:auto;white-space:nowrap}
    .c-ok{color:#A79E92}.c-soon{color:#F6A800}.c-gone{color:#E2524A;font-weight:bold}
    .what{margin:.2rem 0 .6rem}
    details summary{cursor:pointer;color:#2FD4C2;font-size:.88rem}
    details p{margin:.6rem 0;font-size:.9rem;color:var(--ink-2,#CFC7BB)}
    .meta{font-size:.82rem !important;color:var(--ink-3,#A79E92) !important}
    """
    script = """
    // THE CLOCK IS WORKED OUT HERE, NOT BAKED INTO THE PAGE. A page about expiry
    // dates that shipped a stale "14 days left" would be the exact failure it
    // documents. Only the raw date is rendered; the arithmetic happens on load.
    (function(){
      var DAY=86400000, now=Date.now();
      var els=document.querySelectorAll('.clock[data-review-by]');
      for(var i=0;i<els.length;i++){
        var el=els[i], raw=el.getAttribute('data-review-by'), t=Date.parse(raw+'T00:00:00Z');
        if(!isFinite(t)){ el.textContent='review date unreadable'; el.className='clock c-gone'; continue; }
        var days=Math.ceil((t-now)/DAY);
        if(days<0){ el.textContent='expired '+Math.abs(days)+' day'+(Math.abs(days)===1?'':'s')+' ago'; el.className='clock c-gone'; }
        else if(days===0){ el.textContent='expires today'; el.className='clock c-soon'; }
        else { el.textContent=days+' day'+(days===1?'':'s')+' left'; el.className='clock '+(days<=14?'c-soon':'c-ok'); }
      }
    })();
    """

    html_out = DN.page(
        "Known Wrong",
        "Things p(Doom)1's website knows are wrong, why they have not been fixed, "
        "and the date each acceptance expires.",
        "https://pdoom1.com/known-wrong/",
        intro + body + "<style>" + style + "</style><script>" + script + "</script>",
    )

    if check_only:
        if not OUT.exists():
            print(f"STALE: {OUT} does not exist yet. Run without --check.")
            return 1
        if OUT.read_text(encoding="utf-8") != html_out:
            print(f"STALE: {OUT} no longer matches the acknowledgement ledger.")
            print("  Regenerate:  python scripts/render-known-wrong.py")
            return 1
        print("OK: /known-wrong/ is in step with the acknowledgement ledger.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_out, encoding="utf-8", newline="")
    print(f"Wrote {OUT} ({len(acks)} entr{'y' if len(acks)==1 else 'ies'}, "
          f"{n_ask} awaiting a decision)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    return build(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
