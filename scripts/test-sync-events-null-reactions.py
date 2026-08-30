#!/usr/bin/env python3
"""A reaction nobody has been asked for renders as an absence, not as "None".

    python scripts/test-sync-events-null-reactions.py

WHY THIS EXISTS. pdoom-data serves safety_researcher_reaction and
media_reaction as null for every record where nobody was actually asked. Those
fields previously carried invented text: 1,166 of the 1,194 events drew from a
five-element list by random.choice, so one sentence stood as what safety
researchers thought about 232 separate papers. See pdoom-data#96, #92, #76.

The key STAYS PRESENT and goes null, which is the kind detail and also the
trap. Nothing raises KeyError, so every `if key in event` guard still passes
and hands None to code typed for str. Two defects followed, both measured in
this repository before the fix:

  1. sanitize_event_urls called sanitize_urls_in_text(None), which raises
     AttributeError: 'NoneType' object has no attribute 'replace'.

  2. The detail template wrapped the value in LITERAL quotation marks, so a
     null would have published

         "None"

     under the heading "Safety Researcher Reaction". A wrong answer in
     quotation marks is worse than no answer, which is the whole reason
     pdoom-data made the field nullable in the first place.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "sync_events", ROOT / "scripts" / "sync" / "sync-events.py")
se = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(se)

failures = []
checks = [0]


def check(cond, msg):
    checks[0] += 1
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def event(safety, media, **over):
    e = {
        "title": "A Thing Happened",
        "description": "A description.",
        "year": 2024,
        "category": "research",
        "rarity": "rare",
        "tags": ["alpha"],
        "sources": ["https://example.com/a"],
        "safety_researcher_reaction": safety,
        "media_reaction": media,
        "pdoom_impact": 3,
        "impacts": [{"variable": "research", "change": 2, "condition": None}],
    }
    e.update(over)
    return e


def main():
    print("null reactions: an absence must render as an absence\n")

    print("1. the crash, gone")
    e = event(None, None)
    try:
        se.sanitize_event_urls(dict(e))
        crashed = None
    except Exception as exc:                                  # noqa: BLE001
        crashed = exc
    check(crashed is None,
          "sanitize_event_urls survives a null reaction (was AttributeError)")

    kept = se.sanitize_event_urls(dict(e))
    check("safety_researcher_reaction" in kept
          and kept["safety_researcher_reaction"] is None,
          "and the key is KEPT and still null, so consumers indexing on it work")

    print("\n2. a real reaction is untouched")
    live = se.sanitize_event_urls(event("They were alarmed.", "Wide coverage."))
    check(live["safety_researcher_reaction"] == "They were alarmed.",
          "a present reaction passes through sanitisation unchanged")

    print("\n3. THE ONE THAT MATTERS: no page may publish the word None")
    page = se.generate_event_detail_page("null_event", dict(event(None, None)))
    check('"None"' not in page,
          'the rendered page does not contain "None" in quotation marks')
    check("None" not in page.replace("noopener", "").replace("nonet", ""),
          "and does not contain a bare None anywhere in the markup")
    check('""' not in page.split("Reactions")[-1][:1200],
          "no empty pair of quotation marks is left behind either")
    check("Not recorded" in page,
          "the reader is told the reaction was not recorded")

    print("\n4. a page WITH reactions still quotes them")
    page2 = se.generate_event_detail_page(
        "live_event", dict(event("They were alarmed.", "Wide coverage.")))
    check('"They were alarmed."' in page2,
          "a real reaction is still rendered inside quotation marks")
    check('"Wide coverage."' in page2, "and so is the media reaction")

    print("\n5. one null and one present is handled per field")
    page3 = se.generate_event_detail_page(
        "half_event", dict(event(None, "Wide coverage.")))
    check('"Wide coverage."' in page3, "the present one is quoted")
    check('"None"' not in page3, "the null one is not")
    check("Not recorded" in page3, "and is labelled as not recorded")

    print("\n%d checks, %d failed" % (checks[0], len(failures)))
    if failures:
        for f in failures:
            print("  FAILED: %s" % f)
        return 1
    print("OK: a null reaction renders as an absence and never as a quotation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
