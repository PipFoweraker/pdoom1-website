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
| L2 | `weekly-2026-w30` | L2 | `board_weekly-2026-w30__L2.json` | 2026-07-25 | Pip | **First epoch cut.** Client sends `version="L2"`, seed `weekly-2026-w30` (pdoom1 #151, gate-green; echoed in `public/data/version.json` release notes). Legacy L1 board preserved as `board_weekly-2026-w0__L1.json`. |
| **L3** | ⏳ **NOT YET BLESSED** | L3 | `board_<seed>__L3.json` | — | — | **PENDING — a human must fill this row.** See below. |

### ⏳ L3 — pending blessing (do not fill this in from memory)

**Nothing here may be guessed.** The L3 seed is **drawn and spoken at the
ceremony ~1645 AEST Fri 2026-07-31**, and the game side posts the confirmed
string on pdoom1-website#151. pdoom1's words: *"Please do not hardcode it
anywhere before then."* This repo has already blessed the wrong value once
(`league_2026-07_7d6ced29`, superseded the same day) — that is why this row is
empty rather than optimistic.

What is already known and sourced (pdoom1 on #151, 2026-07-28T23:13Z):

- The ladder moved **2 → 3 mid-month**, on gameplay changes — the action-point
  pool was removed entirely in favour of an attention economy, plus office
  lease/lock-in, four-way founder hours, six previously-inert upgrades and a
  quirk rebalance.
- The build shipping Fri 2026-07-31 is **v0.13.2**, running on **L3**. Nothing
  has ever been published on L3; the current public build v0.13.1 is L2.
- The board key is `(seed, L3)` — **literally `L3`**, not `v0.13.2` and not
  `L3.0`. `GameConfig.get_board_version()` returns `"L" + LADDER_VERSION`. Local
  file `leaderboard_<seed>__L3.json`; remote POST body `version=L3`; remote GET
  `?version=L3`. **The build version never touches the board key again.**
- The board opens **~1700 AEST Fri 2026-07-31** (approximate until confirmed).
- The read path is confirmed clear: `GET ?seed=…&version=L3` returns
  `ok:true` with an empty board — **and so does every wrong key**, including
  `version=L99` and `version=NOTAVERSION`. The API has no validation, so a typo
  produces a valid-looking empty board rather than an error. Proving the key
  needs a **positive** check, not an absence of errors.
- **UPDATE 2026-07-31 — the positive check now exists, and it passed.** The
  board `(weekly-2026-w30, L3)` holds **3 real entries** posted by the shipped
  client on 2026-07-30 (08:32, 09:10, 09:36 AEST), spanning builds `v0.13.1` and
  `v0.13.2`. So **POST auto-creation on an `L3` key is verified by observation,
  not inferred**: the API accepted a key that had never existed and stored real
  rows under it. Item 1 of pdoom1-website#151 — *"the one item that would
  actually break Friday"* — is **closed**. What remains unverified is only which
  seed string the shipped client sends; see the roll decision below.

### Roll, not bless-in-place — ruled 2026-07-31

**Decision (Pip, 2026-07-31 morning): the league opens on a NEW seed, and the
Gate 4 proving runs do not carry over.**

Why this follows rather than being a preference: the board
`(weekly-2026-w30, L3)` already holds three runs — the Thursday proving runs that
passed [Gate 4: PROVEN BUILD]. Pip ruled those should not be on the opening
board. **The website does not filter a live board** — removing entries is editing
standings, and a board that can be edited is no longer a record of what happened.
So the only honest way to exclude them is for the league to open on a *different
board key*.

The epoch half cannot move: the rules have not changed again, so it stays `L3`.
**The only half that can move is the seed.** Hence the roll.

Consequence to accept knowingly: **the board opens empty** and stays empty until
the first real player finishes a run. That is correct, not a fault. The
leaderboard says so honestly rather than showing a live-looking empty table.

**The verification wrinkle.** This ledger's discipline is *bless what the client
actually sends, verified*. But the new seed **must not** be verified by
submitting a score — that would put a run on the opening board, which is the
thing being ruled out. So:

- **Verify from the artifact**: read the seed const out of the built v0.13.2 zip.
  That is the source of truth for what the client will send, needs no submission,
  and is stronger evidence than a round trip.
- **Do not** verify by POST. **Do not** verify by GET-returns-`ok:true` — every
  wrong key does that too.
- The API's acceptance of an `L3` key is already proven (above) and does not need
  re-proving.

**Re-cut, not patch.** Changing the seed const after [Gate 2: THE FREEZE] means a
re-cut by the standing rule. A seed const is not gameplay-shaped, so the
Commissioner may rule that the full [Gate 4] sequence is not required — but that
must be an **explicit ruling recorded here**, not a silent exception. "We patched
instead of re-cutting, just this once" is how the rule dies.

**Website work required: none.** `publish-live-board.py` observes whichever board
the client posts to and publishes that. No code change, no deploy race.

**Checklist for whoever blesses it (a human, on the day):**

- [ ] Copy the confirmed seed string from pdoom1's #151 comment — not from any
      website-derived value, and not from this document. **The probable value is
      `weekly-2026-w31`; treat that as UNCONFIRMED until the ceremony.**
- [ ] **Roll-specific:** confirm the seed const in the *built artifact* matches
      the string being blessed. Artifact beats intention.
- [ ] **Roll-specific:** record the Commissioner's ruling on whether the re-cut
      re-ran [Gate 4], and if not, why not.
- [ ] Fill the L3 row above: seed, board file, blessed date, by.
- [ ] Set `regularised_from.seed` in `public/data/ladder-epochs.json` and change
      `seed_status` to `blessed`. That is the *only* place a script reads it;
      `weekly-league-manager.py` picks it up automatically and stamps
      `seed_provenance.blessed: true`.
- [ ] Confirm `regularised_from.board_opens_local` against what actually
      happened and set `board_opens_confirmed: true`.
- [ ] Re-run `python scripts/weekly-league-manager.py --rebuild-archive-index`
      and `python scripts/test-weekly-league-boundary.py`.

Until that is done, the website **derives a placeholder seed and refuses to show
it to players**: `public/leaderboard/index.html` only offers a seed whose record
says `seed_provenance.blessed === true`, and the boundary test fails if the
probable string is hardcoded anywhere in `scripts/` or `public/data/`.

## Blessings log

The ceremony, for the record — including the one that missed, because the log is
history, not a tidy final answer.

| # | when (AEST) | seed | rite | outcome |
|---|---|---|---|---|
| 1 | 2026-07-24 ~08:00 | `league_2026-07_7d6ced29` | *waves doom staff* | **Superseded.** Blessed in good faith, but conflicted with the already-shipped client key. Corrected same day. |
| 2 | 2026-07-25 ~09:20 | `weekly-2026-w30` | *waves doom staff* | **Canonical.** Matches the shipped v0.13 client. This is the seed the L2 board uses. |
| 3 | 2026-07-31 ~16:45 | ⏳ *to be drawn* | *waves doom staff* | **PENDING.** Roll ruled 2026-07-31 so the Gate 4 proving runs do not open the board. Fill from pdoom1's confirmed string, not from memory. |

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
