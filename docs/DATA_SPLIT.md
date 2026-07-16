# Event data: pure history vs game adaptation — ownership decision

`pdoom-data/DATA_ARCHITECTURE.md` proposes splitting event data into **pure history**
(pdoom-data, scholarly facts) and **game adaptations** (game fields: `impacts`, `rarity`,
`pdoom_impact`). This note records the *operative* decision for the website so the two
don't drift with ambiguous ownership (the classic solo-dev trap).

## Current reality (2026-07-16)
- `public/data/events.json` (1,194 events) **carries game fields** (`impacts`, `rarity`,
  `pdoom_impact`) — i.e. it is the *game-adapted* copy, not pure history.
- It is **generated** from pdoom-data via `scripts/sync/sync-events.py`.
- Data-quality signal from `validate_data.py`: **1,174 / 1,194** events are
  `technical_research_breakthrough` and **1,076** are `rarity: rare` — the bulk
  alignmentforum import defaulted these. The game-adaptation layer is barely differentiated.

## Decision
**pdoom-data = source of truth for historical facts. The website consumes a game-adapted
projection. The website never hand-edits `events.json`** (edits belong upstream + re-sync).

Ownership of each field is now explicit and enforced:
- **History fields** (owned by pdoom-data): `id`, `title`, `year`, `category`,
  `description`, `sources`, `tags`, reactions.
- **Game-adaptation fields** (owned by the game/adapter): `impacts`, `rarity`,
  `pdoom_impact`. Marked as such in `schemas/events.schema.json`.

The website's job is to **validate** the projection it receives (`scripts/validate_data.py`
+ `schemas/events.schema.json`) and display it — not to author it.

## Open items (not blocking)
1. The game-adaptation layer is undifferentiated (see the 1,174/1,076 skew). If rarity/
   category are meant to affect gameplay, they need real per-event values — currently they
   look like import defaults. Decide in the game repo.
2. If pdoom-data ever strips game fields to become "pure" (its stated plan), the adapter
   that re-adds them must live in ONE place (game repo's `historical_adapter.py`), and the
   website schema's "game-adaptation" fields become required-from-adapter, not from source.
