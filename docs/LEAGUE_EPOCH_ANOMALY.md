# The league epoch anomaly — pre-history before ladder epoch L3

**Status:** deliberate. Nothing described here is a bug awaiting a fix.
**Written:** 2026-07-28. **Revised twice on 2026-07-29** — see
[Revision history](#revision-history). Every count and path below was measured,
not recalled.

Pip's ruling (2026-07-28): the weekly league and player pages are **retired and
kept hidden, not deleted**, and everything opened before the ladder fork becomes
deliberately-labelled **anomalous pre-history** — visible in the archive as an
explicit anomaly section, not silently buried. In his words, kept so "the ultra
archivists can track it down".

This file is that record. If you are the archivist: start at
[Where every piece lives](#where-every-piece-lives).

---

## The epoch boundary

```
EPOCH_BOUNDARY = 2026-07-31 00:00:00 Australia/Hobart
               = 2026-07-30T14:00:00Z
```

**It is not a literal in any script.** It lives in
`public/data/ladder-epochs.json` with its source cited, and
`scripts/weekly-league-manager.py` reads it (`ladder_contract()`,
`epoch_boundary()`). It has moved twice in two days, and Pip's standing rule
(2026-07-29) is *"Let's keep using variables and not hardcoding things where we
can!"*.

### Why here: the ladder forked, mid-month

The boundary is the **L2 → L3 ladder fork**, not a calendar rule.
`ladder_version.txt` moved 2 → 3 **mid-month**, on gameplay changes:

- the **action-point pool was removed entirely**, in favour of an attention
  economy;
- office lease and lock-in;
- four-way founder hours;
- six previously-inert upgrades wired up;
- quirk rebalance.

The build shipping Friday 2026-07-31 is **v0.13.2 on L3**. Nothing has ever been
published on L3 — the current public build, v0.13.1, is L2.

A score set under the old rules and a score set under the new ones are not
measuring the same game. That non-comparability *is* the reason `ladder_version`
is half the board key. It is a far stronger justification than "before this
date", and it is sourced.

> **Source precedence.** `pdoom1/docs/RELEASE_NOMENCLATURE.md` describes the
> cadence *pattern* (Seed weekly on Fridays; Epoch monthly on the first Friday)
> and that pattern still holds — but its calendar row
> `Jul 31 | Fri | Weekly Seed | Seed | -- / L2` is **stale**, because the ladder
> forked off-cadence. **pdoom1 on pdoom1-website#151, comment 2026-07-28T23:13Z
> is authoritative for this cut.** Anywhere this repo cites either, it says which.

### Midnight, not 1700 — and why the difference is recorded rather than hidden

The board itself opens **~1700 AEST on Friday 2026-07-31** (the seed is drawn and
spoken at a ceremony ~1645), which is ~17 hours *into* the first L3 week. The
boundary is nevertheless the **Hobart-midnight anchor of that week**, for one
reason:

- The unit being flagged is a **whole league week**. Cutting at 1700 would put
  the boundary inside the first L3 week, so that week would start before its own
  boundary and be labelled pre-L3 — the first good week flagged as bad.
- Worse, a week that is half under L2 rules and half under L3 is exactly the
  cross-epoch blend the ladder split exists to prevent. Weeks do not get to be
  half-comparable.

So the open time is carried **separately** — `epoch.board_opens_local` in every
regularised record, `epochs.board_opens_local` in the archive index, and a
sentence on the archive page — flagged `board_opens_confirmed: false` because
"~1700" is approximate until the game side confirms it. Nothing anywhere claims
the board was accepting scores from midnight. A player who played Friday morning
was on v0.13.1/L2 and submitted to the **L2** board, which is preserved and
labelled; a player who played Friday evening was on v0.13.2/L3. Both are
described correctly.

### The rule

A week is **anomalous** iff its own start instant is **before** the boundary.
The rule is one line, in one place, and every consumer reads the flag rather
than re-deriving the date:

- `public/data/ladder-epochs.json` → the boundary, ladder version, board-key
  shape, seed blessing state and both reason strings
- `scripts/weekly-league-manager.py` → `ladder_contract()`, `epoch_boundary()`,
  `board_opens()`, `epoch_for()`
- stamped into the data as an `epoch` object (below)
- read by `public/league/archive.html` → `isAnomalous()`

| week | starts | ends | epoch |
|---|---|---|---|
| … 2025_W41 … 2026_W30 | 2025-10-06 … 2026-07-20 | … 2026-07-26 | `pre-regularisation` (anomalous) — Monday-anchored UTC weeks |
| **2026_W31** | 2026-07-27 | 2026-08-02 | `pre-regularisation` (anomalous) — the last Monday-anchored week; archived by the Thu 2026-07-30 rollover |
| **2026_W32** | Fri 2026-07-31 | Thu 2026-08-06 | `regularised`, `ladder_version: L3` — **the first good week**, and the first Friday/Hobart week. Opened by the Thu 2026-07-30 14:00 UTC rollover; board opens ~1700 that day. |

There is no straddle any more: the anchor change and the fork land on the same
instant, `2026-07-30T14:00:00Z`. That is a coincidence worth stating rather than
relying on — the test asserts the two agree
(`the boundary IS the rollover instant`), so if either moves independently the
rollover fails instead of publishing a week under the wrong epoch.

### The week itself moved: Friday 00:00 Australia/Hobart

Pip, 2026-07-28: *"Everything is going to be based off Hobart time, AEST. The
rest of the world can deal with it. I might adjust that in 6 months."*

The league week now runs **Friday 00:00:00 → Thursday 23:59:59 in
Australia/Hobart**, matching the game's own "every Fri" Seed cadence. The
website had run Monday→Sunday UTC for its whole life — two days out of phase
with the spec — and fixing the off-by-one inside the wrong anchor would only
have hardened the phase error.

**Hobart is not a fixed offset.** Tasmania observes daylight saving: UTC+10
(AEST) in winter, UTC+11 (AEDT) from the first Sunday in October to the first
Sunday in April. GitHub Actions cron is UTC-only and has no DST awareness, so
the design separates trigger from truth:

| | cron instant | in Hobart |
|---|---|---|
| winter (AEST) | Thu 2026-07-30 **14:00 UTC** | Fri 2026-07-31 **00:00 +10:00** — exactly the boundary |
| summer (AEDT) | Thu 2026-11-26 **14:00 UTC** | Fri 2026-11-27 **01:00 +11:00** — one hour into the week |

Always a Friday in Hobart, in both halves of the year, and **never earlier** than
the week it opens (cron can run late, which is harmless; it cannot run early).
The week itself is derived with `ZoneInfo("Australia/Hobart")` in
`league_week_start()`, never from an offset — so a DST change moves *how far into
the week the run happens*, not *which week it is*.

Consequences that are easy to miss:

- A Hobart league week is 7 days ± 1 hour in **elapsed** time across the two DST
  transitions. Its **wall-clock** span is always exactly one week minus a second.
  `scripts/test-weekly-league-boundary.py` asserts both spans explicitly rather
  than pretending a week is always 604 799 seconds.
- `week_id` comes from the ISO week of the league week's own **Thursday** — ISO
  8601's own rule for numbering a week. A Fri→Thu week contains exactly one
  Thursday, so labels stay unique and strictly increasing, including across the
  2026-W53 → 2027-W01 straddle.
- The old Monday geometry used the same label space shifted two days, so the
  Friday week of 2026-07-24 would also have been called `2026_W31`. That week is
  never materialised (the switch happens at the 2026-07-30 rollover, which opens
  `2026_W32`), but the overlap is real: **do not compare archives across the
  switch by id alone.**

### `tzdata` is a hard dependency, especially on Windows

`zoneinfo` reads the *system* tz database. Linux and macOS have one; **Windows
does not**, so `ZoneInfo("Australia/Hobart")` raises `No time zone found with key
Australia/Hobart` until `pip install tzdata`. That is the worst failure
asymmetry available — green on `ubuntu-latest`, dead on Pip's box — so:

- `tzdata` is pinned in `requirements.txt` with the reason written next to it,
  and installed explicitly by `weekly-league-reset.yml`.
- `league_tz()` **raises** with the fix in the message. It deliberately does
  **not** fall back to a hardcoded `+10:00`: that would silently move every
  rollover by an hour for half of every year, which is precisely the bug class
  this work exists to remove.

---

## What the `epoch` stamp looks like in the data

Every weekly record carries a top-level `epoch` object, written directly after
`meta` so it reads before any score data:

```json
"epoch": {
  "id": "pre-regularisation",
  "anomalous": true,
  "ladder_version": null,
  "boundary_ladder_version": "L3",
  "boundary_local": "2026-07-31T00:00:00+10:00",
  "boundary_tz": "Australia/Hobart",
  "boundary_utc": "2026-07-30T14:00:00Z",
  "reason": "Opened before the L2 -> L3 ladder fork. L3 removed the action-point pool entirely in favour of an attention economy, added office lease and lock-in, four-way founder hours, six previously-inert upgrades and a quirk rebalance. Scores set under the earlier rules are not comparable ...",
  "see": "docs/LEAGUE_EPOCH_ANOMALY.md",
  "source": "pdoom1 on pdoom1-website#151, comment 2026-07-28T23:13Z",
  "observed_defects": {
    "monday-anchored-utc-week": "...",
    "rollover-off-by-one": "...",
    "empty-shell": "..."
  }
}
```

The boundary is carried in **both clocks plus the zone name**, so a reader never
has to know which one a bare timestamp meant. A **regularised** record adds
`ladder_version: "L3"` and `board_opens_local` / `board_opens_confirmed`; a
pre-fork record carries `ladder_version: null` (it belongs to no current epoch)
and no board-open time, because none applies to it.

### The board key is `(seed, L<n>)` — literally `L3`

Not `v0.13.2`. Not `L3.0`. **The build version never touches the board key
again**; that is the entire point of the build-vs-ladder split, and it means a
cosmetic patch bump can no longer fork a board. From the game side:
`GameConfig.get_board_version()` returns `"L" + LADDER_VERSION`; the local board
file is `leaderboard_<seed>__L3.json`; the remote POST body field and the remote
GET query parameter are both `version=L3`.

Every new weekly record therefore carries an explicit `board_key` object
(`seed`, `ladder_version`, `shape`, `blessed`) so no consumer has to reassemble
the key and get its shape wrong. `meta.game_version` is still written, but it is
a **record stamp** — which build produced the file — and is commented as such in
`weekly-league-manager.py`. Under the old `(seed, game_version)` keying a patch
bump *did* fork the board; that is how 23 of the 27 preserved submissions below
were stranded.

### The seed is deliberately absent

`public/data/ladder-epochs.json` → `regularised_from.seed` is **`null`**, with
`seed_status: "unblessed"`. The L3 seed is drawn at the ceremony ~1645 AEST on
2026-07-31 and posted by the game side; pdoom1 asked explicitly that nothing
hardcode it beforehand, and this repo has been wrong about a seed before
(`league_2026-07_7d6ced29`). Until a human blesses it:

- `seed_for_week()` falls back to the website's derived placeholder and marks it
  `blessed: false`;
- `public/leaderboard/index.html` **refuses to offer an unblessed seed to a
  player** — previously it would have advertised the placeholder, sending people
  to a board that can only ever be empty;
- `scripts/test-weekly-league-boundary.py` greps `scripts/*.py` and
  `public/data/*.json` and fails if the probable value appears anywhere.

`observed_defects` is derived **per file**, never asserted blanket-wise: each
key is present only if that specific file demonstrates it. Frequencies across
the 42 archived weeks (re-measured 2026-07-29):

| defect key | files | what it means |
|---|---:|---|
| `monday-anchored-utc-week` | 42 / 42 | the week runs Mon 00:00 → Sun 23:59:59 **UTC**, two days out of phase with the game's Friday Seed cadence. Detected from the file's own `start_timestamp` (a Monday, at 00:00, at offset zero). |
| `empty-shell` | 42 / 42 | zero entries. No shipped client ever submitted to these board keys. |
| `unblessed-seed` | 42 / 42 | seed derived website-side, not the blessed competitive key. |
| `rollover-off-by-one` | 42 / 42 | the record was generated on or after the day its own week ended. |
| `is_current-stuck-true` | 41 / 42 | `week_info.is_current` still `true` on an archived week. |
| `naive-local-timestamp-labelled-utc` | 41 / 42 | `archived_at` written as local wall-clock with a `Z` bolted on. |
| `legacy-v0.4.1-stamps` | 40 / 42 | `meta.game_version: "v0.4.1"` and `economic_model: "Bootstrap_v0.4.1"`. |

`monday-anchored-utc-week` and `rollover-off-by-one` are **independent** faults
that happened to coexist: the first is a phase error against the spec, the second
a derivation error against the calendar. Fixing either alone would have left a
wrong answer, which is why they are recorded separately per file.

The one file missing four of those is `2026_W30_league.json`, archived on
2026-07-28 by the **fixed** code — so it has a real UTC `archived_at`,
`is_current: false`, and a `v0.13.1` stamp. Its `rollover-off-by-one` and
`empty-shell` flags are still true, because the *content* came from the broken
rollover on 2026-07-26.

---

## The five things that are actually wrong with the pre-history

### 0. The week was anchored to the wrong day, in the wrong clock

Every pre-cut record describes a **Monday 00:00 → Sunday 23:59:59 UTC** week.
`pdoom1/docs/RELEASE_NOMENCLATURE.md` has always said a Seed roll is "every
Fri". So the website's weeks were two days out of phase with the competition
they claimed to describe, independently of the off-by-one below — and the
`14:00 UTC` cron hour was an undocumented attempt to mean "midnight where Pip
lives", which is a *Hobart* clock that a fixed offset cannot express.

**Fixed 2026-07-30 onward**: Friday 00:00 `Australia/Hobart`, derived from the
zone, cron moved to Thursday 14:00 UTC. See
[The week itself moved](#the-week-itself-moved-friday-0000-australiahobart).

### 1. The rollover was one week behind (TECH_DEBT A9 — now fixed)

`.github/workflows/weekly-league-reset.yml` fires `cron: '0 14 * * 0'` —
**Sunday 14:00 UTC**. The old `get_current_week_info()` derived the week from
`now`, so the run opened the week that was *ending* about ten hours later.

The proof is in the data, not in an argument. `2026_W30_league.json`:

```
meta.generated       2026-07-26T14:28:04Z     <- the rollover run
week_info.start_date 2026-07-20
week_info.end_date   2026-07-26               <- ends 9.5h after it was "started"
week_info.is_current true
```

Ten weeks of green checkmarks, every one of them a week late. `validate_data.py`
was the only thing that ever noticed, and only intermittently: its check fires
at `>2 days past end`, so it was silent for the first two days of each wrong
week — which is exactly when a human would have looked.

**Fixed 2026-07-28** by making the run-time → week mapping explicit
(`league_week_start()`), and pinned by `scripts/test-weekly-league-boundary.py`.
The Friday/Hobart anchor then made the fix *simpler*: because the cron now fires
at or just after the Hobart Friday midnight, the week a run operates on is simply
the week that contains the run. The old code's look-ahead ("if it is rollover
o'clock, jump forward a week") is gone entirely — and with it the thing that went
wrong. The test asserts the boundary at exactly the rollover instant and one
second / one minute either side, **in both DST states**, and runs as the first
step of the rollover workflow, so a regression fails the rollover instead of
publishing a wrong week quietly.

### 2. Every week is empty, and always was

All 42 archived weeks have `entries: []`. That is not data loss. Scores are
submitted under a `(seed, ladder)` board key held by the **score API on the
DreamCompute VPS**, and this repo is a read-only consumer of it (pdoom1 PR #679).
Nothing has ever written player entries into `public/leaderboard/data/weekly/`.

So these files were always containers. Reading a 0 as "nobody played that week"
is the wrong inference — the correct one is "this file was never where scores
lived".

### 3. The seeds are website-side inventions

`docs/LEAGUE_SEED_LEDGER.md` is explicit: *"The seed is not a free website-side
choice."* The canonical key is whatever the shipped client POSTs — currently
seed `weekly-2026-w30`, ladder `L2`, blessed by Pip on 2026-07-25.

`weekly-league-manager.py` derives its own `weekly_<week_id>_<sha256[:8]>`
values. **None of them has ever matched a blessed seed**, and no client has ever
POSTed under one. This is the same class of error as the superseded
`league_2026-07_7d6ced29` blessing recorded in the ledger's correction note.

Newly-written records now carry a `seed_provenance` block saying so in the file
itself, so the value cannot be mistaken for a competitive seed downstream:

```json
"seed_provenance": { "blessed": false, "canonical_source": "the shipped game client, recorded in docs/LEAGUE_SEED_LEDGER.md", ... }
```

### 4. The `v0.4.1` stamps are correct history — do NOT restamp

`docs/TECH_DEBT.md` §E already rules on this, and the ruling stands: restamping
would fabricate history. Recorded precisely, because §E's phrasing is loose in
two ways worth correcting (see [Corrections](#corrections-to-existing-docs)):

- **In the 41 pre-existing weekly archives:** `v0.4.1` appears **80 times** — as
  `meta.game_version: "v0.4.1"` and `economic_model: "Bootstrap_v0.4.1"` in 40 of
  them. (`2026_W29_league.json` is `v0.11.0` / `"unknown"`.)
- **In the 15 seed leaderboards:** `v0.4.1` appears **79 times**, and *never* as a
  version field. It is `economic_model: "Bootstrap_v0.4.1"` (15×, one per file)
  and `game_mode: "Bootstrap_v0.4.1"` (64×, one per entry). Their
  `meta.game_version` is **`"1.0.0"`** — the *export tool's* version, mislabelled
  upstream.
- 80 + 79 = **159**, matching §E's "~159 occurrences".

None of it can reach the live board. `scripts/ingest_scores.py` applies two
independent filters, in this order:

1. `gather_seed_files()` drops the 10 test/party/demo-named seed files outright.
2. `is_publishable()` keeps a file only if its `meta.game_version` equals the
   deployed version (`public/data/version.json` → `latest_release.version`,
   currently `v0.13.1`).

The remaining 5 seed files are stamped `1.0.0`, and `1.0.0 != v0.13.1`, so the
version gate alone excludes every one of them. The weekly archives are not read
by this path at all. Neither filter depends on the `v0.4.1` strings.

---

## Where every piece lives

All paths relative to the repo root. Counts verified 2026-07-28.

### Weekly league records — 43 files, ~122 KB

| path | count | notes |
|---|---:|---|
| `public/leaderboard/data/weekly/archive/*_league.json` | **42** | `2025_W41` … `2026_W30`, contiguous, no gaps. All `epoch.anomalous: true`. Total 121,508 bytes. |
| `public/leaderboard/data/weekly/archive/index.json` | 1 | **Derived**, rebuilt from the directory by `weekly-league-manager.py --rebuild-archive-index`. Carries a per-week `epoch` plus an `epochs` summary block. |
| `public/leaderboard/data/weekly/current.json` | 1 | Currently `2026_W31` (the last Monday-anchored week), `epoch.anomalous: true`. Archived and replaced by `2026_W32` — the first L3 week — at the **Thu 2026-07-30 14:00 UTC** rollover. |

**Deliberately not pre-rolled.** `current.json` was left holding the
Monday-anchored `2026_W31` rather than being regenerated under the new geometry.
Regenerating it by hand would fabricate a rollover that never ran, and — because
the Friday week of 2026-07-24 would also be labelled `2026_W31` — it would have
overwritten the archive of the week it was archiving. The geometry change takes
effect at the next real rollover, which is the honest place for it.

**Merge timing is now tight.** The boundary and the anchor land on the same
instant, **Thu 2026-07-30 14:00 UTC**, and that single run both switches the
geometry and opens the first L3 week. If this merges after it, the first L3 week
gets no record until the following Thursday while the board is live —
`validate_data.py` would WARN about a stale current week from 2026-08-04, and the
archive page would show no L3 week at all. The #191 scope line also closes on
2026-07-30: no board-key handling changes after that without a heads-up.

`2026_W30_league.json` is **new in this change**: it is the stale `current.json`
(week 2026_W30, generated 2026-07-26) archived where it belongs, so the live
file could hold the truthful running week.

> **index.json was badly stale.** Before this change it listed **3** archives
> (`2025_W41`, `W42`, `W44`) with `last_updated: 2025-10-31`, while **41** files
> sat beside it. Nothing ever rewrote it — `archive_current_week()` never touched
> it. Since `public/league/archive.html` reads *only* the index, **38 weeks of
> pre-history were invisible on the page**. It is now derived on every archive and
> every new week.

### Preserved orphaned boards — 27 real submissions the site never showed

`public/leaderboard/data/preserved/2026-07-29-orphaned-boards/` (arrives with
branch `data/preserve-orphaned-boards`). Captured live from
`https://api.pdoom1.com/score_api.php` **before** any remediation, so repairing
the fault could not destroy the evidence of it.

Measured from the capture on 2026-07-29 — **27 entries, 6 distinct
`player_name` values, 2026-07-19T19:40:08 → 2026-07-26T18:30:47**:

| board key | key kind | entries |
|---|---|---:|
| `(weekly-2026-w0, v0.11.0)` | build-version — pre-split keying | **20** |
| `(weekly-2026-w0, v0.12.0)` | build-version — pre-split keying | **3** |
| `(weekly-2026-w30, L2)` | ladder | **4** |
| four other captured boards | mixed | 0 |

Players: `AI Safety Lab`, `CogDerp`, `Cognitive Development`,
`Division of Intelligent Agents`, `Hamthropic`,
`Laboratory of Autonomous Systems`.

**Why they were invisible — two independent mismatches**, either of which alone
lost every score: the client submitted seed `weekly-2026-w0` while the site
derived `weekly_2026_W30_18a08709`, **and** the versions differed. Compounding
it, the score API has **no key validation at all** — a wrong seed or version
returns `ok:true` with an empty board (verified 2026-07-29 on the read path), so
nothing on either side could tell "the key is wrong" from "nobody has played".
23 of the 27 sat on `(seed, game_version)` boards forked by patch bumps, which is
precisely what the build-vs-ladder split now prevents.

**How they surface.** `rebuild_archive_index()` scans the preserved directory and
writes a `preserved_boards` summary into `archive/index.json`; the archive page
renders a **[PRESERVED] Real scores the site never showed** block from it, listing
each board key and its actual entries. It is derived from the directory, so:

- while the capture is on its own branch, the array is `[]` and the block does
  not render — the page claims nothing;
- **the moment `data/preserve-orphaned-boards` merges, someone must run
  `python scripts/weekly-league-manager.py --rebuild-archive-index`** (or wait
  for the next rollover, which does it) for the block to appear.

**They are never merged forward.** Pip's ruling 2026-07-29, echoing pdoom1:
merging scores earned under different rules is the exact lie the ladder split
exists to prevent. `scan_preserved_boards()` only ever *summarises* — it has no
path that copies an entry into a league record. Pip is contacting the six players
directly.

> **The capture's own README is one revision behind this file.** It says "23 real
> player submissions", "4 distinct `player_name` values" and a range ending
> 2026-07-22 — true of the five files it tabulates, but the directory also holds
> `weekly-2026-w30__L2.json` (4 entries, to 2026-07-26). It also cites the
> superseded `2026-08-07` boundary. Both are that branch's to correct; the counts
> above were measured against the files, not copied from the README.

### Seed leaderboards — 15 files, ~39 KB, the only real entries anywhere

`public/leaderboard/data/seed_leaderboard_*.json`

- **64 entries** across the 15 files, **64 distinct `entry_uuid`s**, **13
  distinct `player_name`s** (`Anonymous`, `Apex Intelligence`, `Catalyst Labs`,
  `Demo Labs`, `Epic AI Labs`, `Infinitas Research`, `Nexus Computing`,
  `Pulsar AI`, `Quantum Leap`, `Rain Research`, `Silver Stream AI`,
  `Test Systems`, `Zenith Dynamics`).
- Entry dates span **2025-09-13T10:36:25** → **2025-09-29T20:35:30** — a
  ~17-day dev-session window, exported 2025-10-09.
- 10 of the 15 filenames match `ingest_scores.py`'s `TEST_SEED_RE`
  (`test|party|demo|final-verification|natural-game-over`) and are dropped by
  `gather_seed_files()` before anything else looks at them. The 5 that survive
  that filter are:
  `seed_leaderboard_202537_c53217a3.json`, `seed_leaderboard_202538_21062d2e.json`,
  `seed_leaderboard_202538_747962e3.json`, `seed_leaderboard_202539_25079545.json`,
  `seed_leaderboard_202540_8fb1684c.json`.
- **These files are NOT epoch-stamped.** They are a different seam (per-seed
  export, not weekly rollover) and are read by `ingest_scores.py`, whose
  behaviour is covered by another owner's tests. They are pre-history, and this
  document is their record; the data was deliberately left byte-identical.

### Pages (retired, hidden, not deleted)

| path | what it does now |
|---|---|
| `public/league/index.html` | Static retirement notice added above the (still non-functional) live-league UI. `noindex, nofollow`. |
| `public/league/archive.html` | Splits archives on `epoch.anomalous`. Regularised weeks in the main grid; pre-history in a separate, labelled **anomaly section** with per-week defect lists. `noindex, nofollow`. |
| `public/players/index.html` | Static retirement notice. **Has no data store of its own** — it computes every figure in-browser from `weekly/current.json` + the archive index, so its zeroes are downstream of the same anomaly. `noindex, nofollow`. |

There is **no player database in this repo**: `find public -ipath "*player*"
-name "*.json"` returns nothing. Any future "player data" claim should start
from that fact.

### Code

| path | role |
|---|---|
| `public/data/ladder-epochs.json` | **The contract.** Boundary, ladder version, board-key shape, board-open time, seed blessing state, both reason strings, and the source citation for each. Edit the boundary here, nowhere else. |
| `scripts/weekly-league-manager.py` | The producer. `league_tz()`, `league_week_start()`, `league_week_end()`, `week_id_for()`, `ladder_contract()`, `epoch_boundary()`, `board_opens()`, `epoch_for()`, `seed_for_week()`, `scan_preserved_boards()`, `rebuild_archive_index()`. |
| `scripts/test-weekly-league-boundary.py` | 93 assertions: the zone resolves at all (the tzdata trap), the boundary in **winter and summer**, the two DST-spanning weeks, the A9 regression instant, the ISO-year straddle, input timezone handling, 60 rollovers of invariants, the epoch rule, board-open vs boundary, the contract's board-key shape, that the unblessed seed is hardcoded nowhere, that a wrong offset in the contract is rejected, and that the workflow's cron still matches `ROLLOVER_HOUR_UTC` / `ROLLOVER_CRON_DOW` **and still lands on a Friday in Hobart in both DST states**. |
| `requirements.txt` | Pins `tzdata`. Without it the anchor cannot be resolved on Windows and every league script fails loudly. |
| `scripts/stamp-league-epoch.py` | Idempotent backfill. `--check` exits 1 if any weekly record is unstamped. |
| `.github/workflows/weekly-league-reset.yml` | Runs the boundary test **before** mutating anything, then stamps epochs after opening the week. |

---

## How a future archivist reads this

1. **Trust the flag, not the date.** Every record says whether it is anomalous.
   Filter on `epoch.anomalous`, never on a date you re-derive yourself.
2. **`0` means "never wired up", not "nobody played".** Scores lived on the VPS
   score API, never in these files.
3. **Ignore the seed strings.** Cross-reference `docs/LEAGUE_SEED_LEDGER.md` for
   the seed that was actually competitive in any period.
4. **A `v0.4.1` or `1.0.0` stamp is evidence, not an error.** It dates the
   producing tool. Restamping destroys the only provenance these files have.
5. **Nothing before 2026_W32 is comparable to anything after it.** Not the week
   numbering, not the seeds, not the version stamps, not the participant counts —
   and above all not the scores, because L3 changed the rules that produced them.
   The week numbering in particular changed meaning at the 2026-07-30 rollover
   (Monday-anchored UTC → Friday-anchored Hobart), so two records can share an
   id and describe different spans. Compare `start_timestamp`, never ids.
7. **A board is `(seed, L<n>)`.** If you find yourself keying anything off
   `meta.game_version`, stop: that is a record stamp, and treating it as a key is
   what stranded 23 real submissions.
6. **To reproduce any claim here**, run:
   ```
   python scripts/stamp-league-epoch.py --check      # every record stamped?
   python scripts/test-weekly-league-boundary.py     # boundary still pinned?
   python scripts/validate_data.py                   # contracts + cadence
   ```

---

## Corrections to existing docs

Found while verifying counts for this file. Recorded rather than silently
patched, because each is someone else's page to change.

1. **`docs/TECH_DEBT.md` §E says the seed files hold "66 real dev-session
   entries".** The measured count is **64** (64 distinct `entry_uuid`s across the
   15 files). The rest of the §E ruling — do not restamp — is unaffected and
   stands.
2. **§E's phrase "15 seed leaderboards still stamped `v0.4.1`" is imprecise.**
   No seed file has a `v0.4.1` *version* stamp; their `meta.game_version` is
   `"1.0.0"`. The `v0.4.1` strings are `economic_model` / `game_mode` values.
   §E's own next bullet already notes the `1.0.0` mislabelling, so the two
   bullets describe the same 15 files from different angles.
3. **`docs/ORPHANED_PAGES_TODO.md` says `league/archive.html` "Shows 'Failed to
   load archive data.'"** The index it reads was present and parseable, so the
   real failure mode was quieter: it rendered **3 of 41** weeks. The stale index
   was the bug, not a fetch error.
4. ~~**`public/robots.txt` claims the orphaned block's pages "also carry
   `<meta name="robots" content="noindex">`".** True for 5 of the 7 disallowed
   paths. **`public/stats/index.html` and `public/stats/competition.html` carry
   no robots meta tag at all** — verified by grep.~~ **MOOT 2026-08-06:** both
   files were deleted, `Disallow: /stats/` was dropped with them, and the
   robots.txt claim is now true for every path it covers. The noindex gap could
   not be closed by adding a tag, because adding one would have pre-empted the
   retire-or-keep decision (TECH_DEBT A8); Pip took that decision and chose
   retire. Root cause of the whole row: the entire `/stats/` path answered
   `401 Unauthorized` from DreamHost's own panel statistics area, so no crawler
   could read a meta tag there either.

---

## Revision history

Three rulings landed after the first version of this file was written. Recorded
rather than quietly overwritten, because "the boundary moved twice" is itself
part of the provenance — and it is the reason the boundary now lives in a data
file instead of a script.

| | v1 (2026-07-28) | v2 (2026-07-29 AM) | v3 (2026-07-29 PM, current) |
|---|---|---|---|
| week anchor | Monday 00:00 **UTC** | Friday 00:00 **Australia/Hobart** | unchanged |
| rollover cron | `0 14 * * 0` (Sun 14:00 UTC) | `0 14 * * 4` (Thu 14:00 UTC) | unchanged |
| epoch boundary | `2026-07-31T00:00:00Z` | `2026-08-07 00:00 Hobart` | **`2026-07-31 00:00 Hobart`** (`2026-07-30T14:00:00Z`) |
| justification | "patch-cycle regularisation" (a date) | "first Friday Epoch, `0.13→0.14` / `L2→L3`" (a calendar rule) | **the L2 → L3 ladder fork itself** (a rules change), sourced to #151 |
| first regularised week | `2026_W32` (Mon 2026-08-03) | `2026_W33` (Fri 2026-08-07) | **`2026_W32`** (Fri 2026-07-31) |
| where the boundary lives | script literal | script literal | **`public/data/ladder-epochs.json`** |
| board key | `(seed, game_version)` | not addressed | **`(seed, L<n>)`**, literally `L3` |
| new dependency | — | `tzdata` in `requirements.txt` | unchanged |

**Why v2 was wrong.** It derived 7 August from `RELEASE_NOMENCLATURE.md`'s
"Epoch = first Friday" rule. The rule still describes the pattern, but the ladder
**forked early** — `ladder_version.txt` moved 2 → 3 mid-month on gameplay
changes, and the build shipping 2026-07-31 is v0.13.2 on L3. So that document's
row `Jul 31 | Fri | Weekly Seed | Seed | -- / L2` is stale, and
pdoom1-website#151 (2026-07-28T23:13Z) wins. Deriving a boundary from a cadence
rule instead of from the thing the boundary is *about* is the mistake worth
remembering.

**The anomalous window therefore shrank by one week between v2 and v3.** The 43
records on disk were anomalous under all three boundaries and remain so. The week
that moved is `2026_W32` (Fri 2026-07-31 → Thu 2026-08-06): v2 called it
pre-history, v3 correctly calls it the **first L3 week**.

The A9 diagnosis and fix have **not** been revisited across any of this: the
off-by-one, and the `datetime.now()`-is-local half of it, are independent of
which day the anchor sits on and of which epoch the boundary marks.

---

## When this file stops being needed

Never, entirely — it is the provenance record. But the *anomaly section* on the
archive page disappears on its own the moment there are no `epoch.anomalous`
records to render, because it is driven by the data rather than by a hardcoded
date. If the pre-history is ever deleted (a decision, not a cleanup — see
`docs/ORPHANED_PAGES_TODO.md`), this document is what should survive it.
