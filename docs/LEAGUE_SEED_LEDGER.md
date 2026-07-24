# League seed ledger

The authoritative, human-readable record of which competitive seed governs which
league epoch — when it was blessed, and by whom. A "blessing" is Pip's explicit
sign-off that a seed is the real one for an epoch; nothing else makes a seed
canonical.

Per ADR-0016 (league metabolism) the cycle is **monthly**, one baseline seed per
month. The seed is derived deterministically so future months need no invention,
only a blessing:

```
seed = "league_" + <YYYY-MM> + "_" + sha256("pdoom1_league_" + <YYYY-MM> + "_" + <ladder>).hexdigest()[:8]
```

Deriving a value is not the same as blessing it. A derived-but-unblessed seed is
a proposal; only a row in this table with a blessing date is canonical.

| epoch | month | seed | ladder | blessed (UTC) | by | notes |
|---|---|---|---|---|---|---|
| L2 | 2026-07 | `league_2026-07_7d6ced29` | L2 | 2026-07-24 | Pip | **First seed blessing.** Opens the L2 ladder epoch cut (issue #151), replacing the `(seed, v0.12.0)` weekly board. Legacy L1 board preserved as `board_weekly-2026-w0__L1.json`. |

## Legacy / superseded

- **L1 epoch** ran on the `(seed, game_version)` weekly key through v0.12.0. Its
  live board (`board_weekly-2026-w0__v0.12.0.json` on the DreamCompute DATA_DIR)
  is preserved at the L2 cutover as `board_weekly-2026-w0__L1.json` so real
  tester scores from the friends-and-family alpha survive as "legacy epoch L1".
  See `docs/L2_CUTOVER_RUNBOOK.md`.

## How to add a row

1. Derive the seed for the month (`tools/derive_league_seed.py <YYYY-MM> [ladder]`).
2. Get Pip's explicit blessing — do not backfill a blessing you assumed.
3. Add the row with the real UTC date. Never edit a past row's seed; a corrected
   seed is a new epoch, not a rewrite of history.
