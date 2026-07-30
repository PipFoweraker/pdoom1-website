# Preserved: orphaned score boards, captured 2026-07-29

**23 real player submissions that the website never published.** Captured live
from `https://api.pdoom1.com/score_api.php` before any remediation, so that
fixing the key mismatch cannot destroy the evidence of it.

Pip's ruling, 2026-07-29: these belong in the **anomaly archive** (they predate
the 2026-08-07 epoch boundary — see `docs/LEAGUE_EPOCH_ANOMALY.md`), and he will
advise the affected players directly that their ladders will start working.

## What is here

| file | board key | entries |
|---|---|---|
| `weekly-2026-w0__v0.11.0.json` | `(weekly-2026-w0, v0.11.0)` | **20** |
| `weekly-2026-w0__v0.12.0.json` | `(weekly-2026-w0, v0.12.0)` | **3** |
| `weekly-2026-w0__v0.13.0.json` | `(weekly-2026-w0, v0.13.0)` | 0 |
| `weekly-2026-w0__v0.13.1.json` | `(weekly-2026-w0, v0.13.1)` | 0 |
| `weekly_2026_W30_18a08709__v0.13.1.json` | what the site publishes | 0 |

- **4 distinct `player_name` values:** `AI Safety Lab`, `CogDerp`,
  `Cognitive Development`, `Laboratory of Autonomous Systems`
- **Date range:** 2026-07-19T19:40:08 → 2026-07-22T23:36:37

## Why they were invisible

**Two independent mismatches, not one.** Fixing either alone still loses every
score:

1. **Seed.** The client submits `weekly-2026-w0`. The website derives
   `weekly_2026_W30_18a08709`. Three incompatible seed generators exist in this
   repo and nothing compared them.
2. **Version.** Submissions landed on `v0.11.0` and `v0.12.0` boards; the site
   publishes the `v0.13.1` board.

Compounding it, `applyDataStatus()` — the "this board is not live yet" honesty
banner — was only ever called from a function nothing invoked, so it had **never
rendered in production**. A visitor saw an empty table with no explanation, which
is indistinguishable from nobody playing. That is the failure mode CLAUDE.md
warns about, observed in the wild.

## Schema note that drove a design change

Entries carry a single `player_name` field, and it is doing two jobs: it holds a
personal handle for one player (`CogDerp`) and an organisation name for others
(`Laboratory of Autonomous Systems`). Pip's ruling: the ladder uplift must carry
**player name separately from lab name**, so that two players who accept the same
auto-generated default lab name remain distinguishable. Lodged upstream — see
the pdoom1 issue referenced in the PR.

## Rules for this directory

- **Never edit these files.** They are a dated observation, not live data.
- **Never restamp their versions.** CLAUDE.md: restamping fabricates history.
  `ingest_scores.py` already excludes anything whose version differs from the
  deployed one, so nothing here can reach the live board by accident.
- Regenerating the capture is not possible once the boards are rewritten. This
  is the only copy.
