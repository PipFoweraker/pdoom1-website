#!/usr/bin/env python3
"""One-off migration: re-route the event-page metadata suggestion links.

WHY THIS EXISTS AS A SCRIPT AND NOT JUST A GENERATOR CHANGE
-----------------------------------------------------------
`scripts/sync/sync-events.py` renders the five "suggest a different X" links on
every event page. Fixing the generator fixes the ~1,194 pages `sync-events.yml`
regenerates nightly. It does NOT fix the ~1,000 `alignmentforum_*` pages, which
that workflow's own comment describes as "orphaned ... no generator owns" -- no
scheduled job will ever rewrite them, so they would have kept the wrong routing
indefinitely. Roughly 46% of the event surface is frozen (pdoom1-website#248,
and the missing all_events.json producer, pdoom-data#52).

WHAT IT CHANGES
---------------
A suggest-link is this site letting a stranger author a value in another repo's
vocabulary, so it must land in the repo that OWNS the field. Per the ruling of
2026-08-02 (pdoom-data#51, restated in coordination#30), the direction of
authority for game-mechanical fields runs pdoom1 -> pdoom-data.

    category, tags                      -> pdoom-data   (describe the real event)
    rarity, impacts, p(doom) impact     -> pdoom1       (game-mechanical)

Before this ran, all five pointed at pdoom-data, i.e. the site was publicly
inviting game-balance changes into the repo that is forbidden to decide them.

Labels are the TARGET repo's: pdoom1 has no `metadata` or `game-balance` label,
so carrying pdoom-data's across would produce silently unlabelled issues.

NOT A RULING. coordination#30 item A1 may keep, split or null `rarity`. If it is
nulled, the rarity link is deleted rather than re-pointed -- along with the
browse index's rarity sort tiebreaker and filter facet.

KNOWN DIVERGENCE, deliberate: the generator also adds a body line ("This is a
game-mechanical field owned by pdoom1.") to the three re-routed links. This
script does not backfill that into the frozen pages -- it changes routing only,
so the diff stays reviewable. The orphans will differ from regenerated pages by
that one sentence.

Idempotent. Safe to re-run; reports 0 changed on a second pass.

Usage:
    python scripts/fix-suggest-link-routing.py [--check]

    --check  report what would change, write nothing (exit 1 if any page is
             still mis-routed -- suitable for CI)
"""

import sys
from pathlib import Path

EVENTS_DIR = Path(__file__).resolve().parent.parent / "public" / "events"

DATA_NEW = "https://github.com/PipFoweraker/pdoom-data/issues/new"
GAME_NEW = "https://github.com/PipFoweraker/pdoom1/issues/new"
GAME_LABELS = "game-mechanics,event-system,community"

# (description, old fragment, new fragment). Matched as literal substrings against
# the raw HTML, so a page that has already been migrated simply matches nothing.
REROUTES = [
    (
        "rarity",
        f"{DATA_NEW}?labels=metadata,events&title=Metadata%3A%20Change%20rarity%20for%20",
        f"{GAME_NEW}?labels={GAME_LABELS}&title=Event%20metadata%3A%20Change%20rarity%20for%20",
    ),
    (
        "impacts",
        f"{DATA_NEW}?labels=metadata,events,game-balance&title=Metadata%3A%20Change%20impacts%20for%20",
        f"{GAME_NEW}?labels={GAME_LABELS}&title=Event%20metadata%3A%20Change%20impacts%20for%20",
    ),
    (
        "pdoom_impact",
        f"{DATA_NEW}?labels=metadata,events,game-balance&title=Metadata%3A%20Change%20p(doom)%20impact%20for%20",
        f"{GAME_NEW}?labels={GAME_LABELS}&title=Event%20metadata%3A%20Change%20p(doom)%20impact%20for%20",
    ),
]

OLD_PROSE = (
    "Think this event's metadata could be improved? Suggest changes to category, "
    "rarity, tags, game impacts, or p(doom) effects."
)

NEW_PROSE = (
    "Think this event's metadata could be improved? Category and tags describe the "
    'real-world event and are maintained in <a href="https://github.com/PipFoweraker/pdoom-data" '
    'target="_blank" rel="noopener">pdoom-data</a>. Rarity, game impacts and p(doom) '
    'effects are game-mechanical values owned by <a href="https://github.com/PipFoweraker/pdoom1" '
    'target="_blank" rel="noopener">pdoom1</a>. Each link below goes to the repository '
    "that decides that field."
)


def migrate(check_only: bool = False) -> int:
    """Rewrite every event page in place. Returns the number of pages changed."""
    if not EVENTS_DIR.is_dir():
        print(f"ERROR: {EVENTS_DIR} not found", file=sys.stderr)
        raise SystemExit(2)

    pages = sorted(EVENTS_DIR.glob("*.html"))
    changed = 0
    per_field = {name: 0 for name, _, _ in REROUTES}
    prose_fixed = 0

    for page in pages:
        original = page.read_text(encoding="utf-8")
        text = original

        for name, old, new in REROUTES:
            if old in text:
                per_field[name] += text.count(old)
                text = text.replace(old, new)

        if OLD_PROSE in text:
            prose_fixed += 1
            text = text.replace(OLD_PROSE, NEW_PROSE)

        if text != original:
            changed += 1
            if not check_only:
                page.write_text(text, encoding="utf-8")

    verb = "would change" if check_only else "changed"
    print(f"Scanned {len(pages)} pages under {EVENTS_DIR}")
    print(f"  {verb}: {changed}")
    for name, count in per_field.items():
        print(f"    {name:14s} links re-routed to pdoom1: {count}")
    print(f"    explanatory prose updated: {prose_fixed}")

    return changed


if __name__ == "__main__":
    check = "--check" in sys.argv
    n = migrate(check_only=check)
    if check and n:
        print(
            "\nFAIL: pages still route game-mechanical suggestions to pdoom-data.",
            file=sys.stderr,
        )
        raise SystemExit(1)
