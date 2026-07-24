# League seed ledger

The authoritative, human-readable record of which competitive seed governs which
league epoch — when it was blessed, and by whom. A "blessing" is Pip's explicit
sign-off that a seed is the real one for an epoch.

**The seed is not a free website-side choice.** The game client is built to POST
scores under a specific `(seed, ladder_version)` key; the board MUST use exactly
that key or submitted scores land in a board nobody displays — a silent failure
with no error shown to the player. So the canonical seed is **whatever the
shipped client sends**, confirmed against the game's protocol docs, not a value
picked here.

**Authoritative source (read these, not issue comments):**
- `pdoom1/docs/game-design/BUILD_VS_LADDER_VERSION_SPLIT.md` — key/epoch nomenclature + bump rule
- `pdoom1/docs/RELEASE_AND_LEAGUE_CYCLE.html` — cadence + epoch-cut runbook

| epoch | seed | ladder | board file | blessed (UTC) | by | notes |
|---|---|---|---|---|---|---|
| L2 | `weekly-2026-w30` | L2 | `board_weekly-2026-w30__L2.json` | 2026-07-24 (pending re-confirm) | Pip | **First epoch cut.** Client sends `version="L2"`, seed `weekly-2026-w30` (pdoom1 #151, gate-green; echoed in `public/data/version.json` release notes). Legacy L1 board preserved as `board_weekly-2026-w0__L1.json`. |

## Correction note (2026-07-24)

The first blessing initially landed on `league_2026-07_7d6ced29`, a website-side
**proposal** for a monthly-derived naming scheme (`league_<YYYY-MM>_<hash>`). That
proposal was made after — and without reconciling against — the game side's
already-shipped key `weekly-2026-w30` (pdoom1 #151 comment, 01:50 UTC). The client
wins by construction (it is the thing that actually POSTs scores), so this ledger
records `weekly-2026-w30`. `league_2026-07_7d6ced29` is **superseded for this
cut** and must not appear in any board file or page.

**Pip: this needs a one-line re-bless of `weekly-2026-w30`** — the marker above
stays "pending re-confirm" until you do, because the first blessing was cast on
the wrong value in good faith.

The monthly-derivation *idea* is not dead — it is parked for the game's own
**release/league nomenclature reflective review (pdoom1 #808, on/after
2026-08-24)**, where a naming change belongs (it's a client const, cheap to
re-cut between epochs, expensive to fork mid-launch). `tools/derive_league_seed.py`
stays as a reference implementation of that *proposed* scheme, not the current one.

## Legacy / superseded

- **L1 epoch** ran on the `(seed, game_version)` weekly key through v0.12.0. Its
  live board (`board_weekly-2026-w0__v0.12.0.json` on the DreamCompute DATA_DIR)
  is preserved at the L2 cutover as `board_weekly-2026-w0__L1.json`, read-only, so
  the friends-and-family alpha scores survive as "legacy epoch L1".

## How to add a row

1. Read the seed the **shipped client** sends, from the game's protocol docs above.
2. Get Pip's explicit blessing on that value.
3. Add the row with the real UTC date. Never edit a past row's seed; a corrected
   seed is a new epoch, not a rewrite of history.
