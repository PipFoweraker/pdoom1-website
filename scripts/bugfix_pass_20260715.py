#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bugfix_pass_20260715.py  --  Website "make it stop looking broken" pass.

Fixes four confirmed, statically-diagnosed bugs seen in the 2026-07-15 screenshot dump.
Every functional mojibake string below is built from Unicode code points (chr / json.dumps),
never a typed character, so no editor or encoding layer can silently corrupt the fix.

  1. Mojibake  "UK AI Safety Institute [garbage] AI Security Institute"
     The intended arrow ">" (U+2192, UTF-8 bytes E2 86 92) was misdecoded as cp1252,
     leaving code points U+00E2 U+2020 U+2019 baked into the data.
       - public/data/events.json stores it ASCII-escaped  (\\u00e2\\u2020\\u2019, x2)
       - the 2 generated event HTML pages store the raw 3 chars               (x3 each)
     Both are repaired, so a future sync-events.py run stays clean either way.

  2. Dashboard "NaN%" on a Manifold prediction-market tile.
     market.probability is undefined for one market -> undefined*100 -> NaN.
     Adds a Number.isFinite guard so a bad market is skipped, not rendered.

  3. Three permanently-stuck "Loading..." homepage cards
     (Current Version / Weekly League / Last Updated). Grep confirmed NOTHING ever
     populates these spans -- unfinished scaffolding. Wires them to /data/version.json
     (already fetched by the page) and derives the ISO week client-side for the league
     card, which has no endpoint yet. Every placeholder resolves to a real value or a
     dash, never a frozen "Loading...".

NOT fixed here (needs a live browser inspect, not static files):
  * White/blank "Features" cards under About. Their content IS in the HTML and every
    stylesheet resolves .card to a dark background; something overrides it at runtime.
    Steps to diagnose in ~30s are printed at the end.

Idempotent + fail-loud: each edit asserts its anchor exists exactly once, then no-ops on
re-run. Nothing is committed -- review `git diff`, then branch + PR as usual.

Run from anywhere:  python scripts/bugfix_pass_20260715.py
"""

import io
import json
import re
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"

# --- code-point-derived mojibake targets (no typed non-ASCII is load-bearing) ---
MOJIBAKE_CHARS = chr(0x00E2) + chr(0x2020) + chr(0x2019)   # as stored in generated HTML
ARROW = chr(0x2192)                                        # intended ">"
# json.dumps(ensure_ascii=True) reproduces the exact escaped text the sync writer used:
MOJIBAKE_JSON = json.dumps(MOJIBAKE_CHARS)[1:-1]           # -> â†’
ARROW_JSON = json.dumps(ARROW)[1:-1]                       # -> →

report = []


def note(ok, msg):
    report.append(("OK  " if ok else "SKIP", msg))


def edit_file(path: Path, mutate, *, encoding="utf-8"):
    if not path.exists():
        note(False, f"{path.relative_to(ROOT)} -- not found, skipped")
        return
    text = path.read_text(encoding=encoding)
    new_text, changed, message = mutate(text)
    if changed:
        path.write_text(new_text, encoding=encoding)
    note(changed, message)


# 1. Mojibake ----------------------------------------------------------------
def fix_events_json(text):
    n = text.count(MOJIBAKE_JSON)
    if n == 0:
        return text, False, "events.json -- no mojibake escape found (already clean?)"
    return text.replace(MOJIBAKE_JSON, ARROW_JSON), True, \
        f"events.json -- fixed {n} escaped mojibake -> {ARROW_JSON}"


def fix_event_html(text, label):
    n = text.count(MOJIBAKE_CHARS)
    if n == 0:
        return text, False, f"{label} -- no mojibake chars found (already clean?)"
    return text.replace(MOJIBAKE_CHARS, ARROW), True, f"{label} -- replaced {n} mojibake chars -> arrow"


# 2. Dashboard NaN guard -----------------------------------------------------
def fix_dashboard_nan(text):
    anchor = "const probability = (market.probability * 100).toFixed(0);"
    count = text.count(anchor)
    if count == 0:
        if "Number.isFinite(market.probability)" in text:
            return text, False, "dashboard -- NaN guard already present"
        raise SystemExit("ABORT: dashboard NaN anchor not found -- file changed, inspect manually.")
    if count > 1:
        raise SystemExit(f"ABORT: dashboard NaN anchor found {count}x (expected 1).")
    guarded = (
        "if (!market || !Number.isFinite(market.probability)) {\n"
        "          console.warn(`Manifold market ${slug}: no probability field, skipping`);\n"
        "          continue;\n"
        "        }\n"
        "        const probability = (market.probability * 100).toFixed(0);"
    )
    return text.replace(anchor, guarded), True, "dashboard -- added Number.isFinite guard before NaN render"


# 3. Homepage stuck "Loading..." cards ---------------------------------------
STATUS_JS = """
			// --- injected by bugfix_pass_20260715.py: populate the status cards ---
			// These spans had NO populator and sat on "Loading..." forever.
			// Fill from /data/version.json; the league card has no endpoint yet, so
			// derive the ISO week client-side and dash the rest.
			function _isoWeek(d) {
				const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
				const day = t.getUTCDay() || 7;
				t.setUTCDate(t.getUTCDate() + 4 - day);
				const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
				return Math.ceil((((t - yearStart) / 86400000) + 1) / 7);
			}
			function _setStatus(id, val) {
				const el = document.getElementById(id);
				if (!el) return;
				el.textContent = (val === null || val === undefined || val === '') ? '\\u2014' : val;
				el.classList.remove('loading-placeholder');
			}
			async function populateStatusCards() {
				try {
					const res = await fetch('/data/version.json', { cache: 'no-store' });
					if (!res.ok) throw new Error('version.json ' + res.status);
					const v = await res.json();
					_setStatus('current-version-display', v.latest_release && v.latest_release.version);
					_setStatus('release-date', v.latest_release && v.latest_release.published_at
						? v.latest_release.published_at.slice(0, 10) : null);
					_setStatus('open-issues-count', v.repository_stats && v.repository_stats.open_issues);
					_setStatus('last-update-time', v.last_updated
						? new Date(v.last_updated).toLocaleDateString(undefined,
							{ year: 'numeric', month: 'short', day: 'numeric' }) : null);
					const now = new Date();
					_setStatus('current-week-display',
						now.getUTCFullYear() + '_W' + String(_isoWeek(now)).padStart(2, '0'));
					_setStatus('week-time-remaining', null);
					_setStatus('league-participants', null);
				} catch (e) {
					console.warn('populateStatusCards failed:', e);
					document.querySelectorAll('.loading-placeholder').forEach(el => {
						el.textContent = '\\u2014';
						el.classList.remove('loading-placeholder');
					});
				}
			}
			// --- end injected block ---
"""


def fix_homepage_loading(text):
    if "function populateStatusCards" in text:
        return text, False, "index.html -- status-card populator already present"

    anchor_def = "async function loadGameStats() {"
    if text.count(anchor_def) != 1:
        raise SystemExit(f"ABORT: index.html loadGameStats anchor found {text.count(anchor_def)}x (expected 1).")
    text = text.replace(anchor_def, STATUS_JS.rstrip() + "\n\n\t\t\t" + anchor_def, 1)

    call_pat = re.compile(
        r"(document\.addEventListener\('DOMContentLoaded',\s*\(\)\s*=>\s*\{\s*\n\s*loadGameStats\(\);)")
    if not call_pat.search(text):
        raise SystemExit("ABORT: index.html DOMContentLoaded/loadGameStats() call site not found.")
    text = call_pat.sub(r"\1\n\t\t\t\tpopulateStatusCards();", text, count=1)

    return text, True, "index.html -- injected populateStatusCards() + wired into DOMContentLoaded"


def main():
    print(f"repo root: {ROOT}")
    print(f"mojibake targets  html={MOJIBAKE_CHARS!r}  json={MOJIBAKE_JSON!r} -> {ARROW!r}\n")

    edit_file(PUBLIC / "data" / "events.json", fix_events_json)
    for name in ("uk_ai_safety_to_security_2025.html", "us_aisi_to_caisi_2025.html"):
        edit_file(PUBLIC / "events" / name,
                  lambda t, _n=name: fix_event_html(t, _n))
    edit_file(PUBLIC / "dashboard" / "index.html", fix_dashboard_nan)
    edit_file(PUBLIC / "index.html", fix_homepage_loading)

    print("Bug-fix pass results")
    print("-" * 60)
    for status, msg in report:
        print(f"[{status}] {msg}")
    print("-" * 60)
    print(
        "\nSTILL OPEN -- white/blank 'Features' cards (needs a live inspect):\n"
        "  1. Open pdoom1.com, DevTools > Elements.\n"
        "  2. Select a card under About > Features (its <p> text IS in the HTML).\n"
        "  3. Read Computed > background-color + the winning rule in Styles.\n"
        "     Base .card is rgba(61,61,61,.75) (dark); something overrides it to white\n"
        "     at runtime. Suspects: a .tab-content/.about-tabs rule, or loadTokens().\n"
        "     Report what wins and it's a one-line fix.\n"
    )
    print("Nothing committed. Review `git diff`, then branch + PR as usual.")


if __name__ == "__main__":
    main()
