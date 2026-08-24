# League cycle handbook

**Read this instead of asking.** Written 2026-07-31 because the same three
questions kept needing re-explaining: what a board key is, when to *bless* versus
*roll* a seed, and where the website fits in the game's gate ceremony.

This is the *why*. For the record of which seed governs which epoch, see
[`LEAGUE_SEED_LEDGER.md`](LEAGUE_SEED_LEDGER.md). For the mechanics of publishing,
see [`SURFACE_REGISTER.md`](SURFACE_REGISTER.md) §2.

---

## 1. The board key, in one page

A **board** is one leaderboard table. Every score the game submits carries a key
saying which table it belongs on. The key has two halves:

```
(seed, ladder_epoch)
 │      └── which RULES the score was earned under.  "L3".  Ticks when rules change.
 └───────── which SCENARIO everyone is competing on. "weekly-2026-w31".
```

**Two scores are comparable only if both halves match.** Same puzzle, same rules.
That is the whole idea.

**The build version is NOT part of the key.** `v0.13.2` is not `L3`. A cosmetic
patch must never fork a board — that was the entire point of the build-vs-ladder
split. One board legitimately spans several builds, and seeing
`builds_seen: ["v0.13.1", "v0.13.2"]` on a single board is the split working, not
a bug.

**Why this matters more than it sounds.** The score API returns `ok: true` with an
empty list for a board that has never existed. There is no validation and no
error. So a wrong key is **indistinguishable from nobody playing** — from the
player's side *and* from ours. That is not hypothetical: 27 real submissions from
6 players were stranded exactly this way, and nobody noticed for a week. They are
now in the permanent anomaly archive and must never be re-stamped.

---

## 2. Bless vs roll — the decision that keeps coming up

Both words are about the **seed** half of the key. Neither touches the epoch.

| | **Bless in place** | **Roll** |
|---|---|---|
| What happens | Keep the seed the client already sends; record it as canonical | Change the client's seed const, then bless the new one |
| Board opens | With whatever is already on it | Empty |
| Cost | None — no re-cut | A re-cut, and a const change |
| Use when | The existing board's contents are legitimate competition | Something on the board should not be in the competition |

### The rule that decides it

**Ask one question: is everything currently on that board something you are happy
for players to compete against?**

- **Yes → bless in place.** Cheaper, no re-cut, no risk.
- **No → roll.**

There is no third option, because **the website does not filter a live board.**
Removing entries is editing standings, and a board that can be edited is no longer
a record of what happened. If something must not be on the opening board, the
league has to open on a *different key*.

And since the epoch only moves when the *rules* change, the only half that can
move for this purpose is the seed. **"Get those runs off the board" and "roll the
seed" are the same sentence.**

### Worked example — 2026-07-31

The Gate 4 proving runs (three of Pip's own, Thursday morning) were sitting on
`(weekly-2026-w30, L3)`. Pip ruled they should not open the league. The rules had
not changed again, so `L3` stays. Therefore: roll the seed to `weekly-2026-w31`,
bless that, open empty.

### The trap in rolling

The ledger's discipline is *bless what the client actually sends, verified*. But
after a roll you **cannot verify by submitting a score** — that puts a run on the
opening board, which is the thing you just ruled out.

**Verify from the built artifact instead**: read the seed const out of the zip.
That is the source of truth for what the client will send, needs no submission,
and is stronger evidence than a round trip anyway.

**Never verify by "the GET returned ok:true".** Every wrong key returns that too.

### After the freeze, a const change is a re-cut

Changing the seed after [Gate 2: THE FREEZE] means a re-cut, not a patch. A seed
const is not gameplay-shaped, so the Commissioner may rule the full Gate 4
sequence is not needed — but **record that ruling**. A silent exception is how the
rule dies.

---

## 3. Where the website sits in the gate rail

pdoom1 runs release weeks on six named gates. The website appears in exactly one
of them, and it is worth knowing which.

| Gate | Website involvement |
|---|---|
| 1 LAST POUR | none |
| 2 THE FREEZE | none |
| 3 PACK BLESSED | none |
| 4 PROVEN BUILD | none |
| **5 SEED BLESSING** | **"board-key fork verified clean" — the one gate line that spans both repos** |
| 6 BOARD OPENS | display points at the live board |

Gate 5 cannot be honestly spoken from the game side alone. The playbook's rule is
*"saying a line you have not verified is the cardinal sin of the ceremony"*, so a
website-side unknown is enough to fail it.

**What the website has to be able to say at Gate 5:**

1. The API accepts the epoch key. *(Proven by observation 2026-07-30 — real rows
   exist on an `L3` key the API auto-created. Does not need re-proving unless the
   epoch changes.)*
2. The site publishes whatever board the client posts to. *(Structural — see §4.)*
3. Earlier epochs stay preserved and read-only, never merged forward.

---

## 4. Why the website needs no code change on ceremony day

`scripts/publish-live-board.py` **observes** the board key rather than being told
it. It reuses the liveness probe's derivation, finds whichever board on the
current epoch has the most recent activity, and publishes that.

So: draw the seed, the client posts to it, the next probe publishes it. **No edit,
no deploy race against the release.**

This is deliberate and worth protecting. The failure it prevents is a
website-derived seed that no client ever sends — which is exactly what happened
before (`weekly_2026_W31_f148a5b6`, a hash the site invented and published while
players posted somewhere else entirely).

**Corollary: never hardcode a seed anywhere in `scripts/` or `public/data/`.**
`test-weekly-league-boundary.py` fails if you do, and it gates the unattended
rollover.

---

## 5. The one thing that is still a human channel

The **current ladder epoch** reaches this repo by a person reading a GitHub
comment and typing a value into `public/leaderboard/data/board-probe-targets.json`.
pdoom1 publishes no machine-readable epoch artifact yet.

Nothing in CI can notice pdoom1 forking L3 → L4. A wrong epoch returns `ok:true`
with an empty board, so the site would keep reporting "live" against a board that
had gone quiet.

**So: at every epoch fork, update that file.** It carries a `supersede_when` field
naming the artifact that would retire the human step. Standing ask on PR #190.

---

## 5b. Published is not open, and the site now says so separately

Added 2026-08-24, pdoom1-website#351.

`GameConfig.FEATURED_SEED_OVERRIDE` is a **compiled-in constant**, so both halves
of the board key `(seed, ladder_epoch)` ship inside the binary. A build can
therefore be posting scores to a board that no ceremony ever opened. Until this
change the site had no way to say that: "what is downloadable" and "which league
is open" were the same field, so a published-but-unopened board and an open board
looked identical from outside.

**Three questions, three answers, three pieces of evidence.** They live in
`public/data/ladder-epochs.json` under `player_facing`, and `/leaderboard/`
renders them with `buildLeagueStateHTML()`:

| question | field | today |
|---|---|---|
| what is downloadable now | `downloadable_now` | v0.14.2, board `(weekly-2026-w33, L5)` |
| which league is OPEN | `league_open` | **none-open** |
| what is coming | `coming` | ladder epoch L6, cut in the game repo, no build carries it |

**The state vocabulary is in the file itself** (`player_facing._states`), and a
state name it does not define is a hard failure. The two that matter:
`published-not-open` (a build posts to this key and nobody opened a league on it)
and `open` (a named human performed [Gate 6] and it is recorded).

### The rules this cannot be talked out of

- **Nothing may infer an opening, and an opening must QUOTE THE LEDGER.**
  `league_open.state: "open"` requires `opened_by`, `opened_utc`, and an
  `opening_ledger_quote` that appears **verbatim** in
  `docs/LEAGUE_SEED_LEDGER.md`. `/leaderboard/` will not print the word "Open"
  without that quote either, and it shows the quote to the visitor.
  **Why the quote and not just a named opener.** The first version of this guard
  required only a non-empty `opened_by`, and adversarial review on 2026-08-24 walked
  through it: `opened_by: "Pip"` with a plausible timestamp exited 0 and printed
  *"no opening is claimed that a human did not record"*, while the ledger said
  verbatim that [Gate 6] was HELD and the page rendered *"Open ... Opened by Pip"*.
  It covered the fabrication no review would pass and missed the one that would.
  Two rules follow: the quote may not itself be a refusal (quoting the sentence that
  HOLDS the gate is not evidence the gate was lifted), and a standing
  `[Gate 6] ... HELD` naming the same epoch beats the claim until
  `hold_lifted_ledger_quote` records the lift as well.
  A seat inferring a blessing is #297; inferring an *opening* is that error one gate
  later.
- **The page says ONE thing about a key mismatch, from one source.** Both boxes on
  `/leaderboard/` call `boardMechanismHTML()`. They previously disagreed, adjacent,
  about the same key: one promised a run would appear *"until this page catches
  up"*, the other that it could *"never"* appear. **Both were wrong.**
  `publish-live-board.py` reads its epoch from `board-probe-targets.json` and its
  derived seed list already contains the shipped client's seed, so that key is
  publishable by the existing 6-hourly job -- "never" is false. And "until this page
  catches up" is an *unearned* promise: conditional on catching up before the next
  fork, a condition that has already failed twice this month. State the mechanism,
  promise no timing.
- **An empty board is not evidence of anything.** The score API has no key
  validation: `seed=NOTASEED-zzz9&version=L99` returns `ok:true` with an empty
  entries array (measured 2026-08-24), exactly like a real board nobody has
  played. Never argue "not open" -- or "open" -- from a count.
- **The API answering 200 is not an open league.** Reachability is a fact about a
  host; openness is a decision. Those two were fused in `ladder-epochs.json` until
  2026-08-24 and the fused sentence outlived the fact it rested on.
- **`check-blessing-consistency.py` passing proves nothing about consistency.** It
  compares only the current epoch and is advisory in CI, so a disagreement about a
  closed epoch neither fails nor blocks.
- **Unknown is first-class, and an expired acceptance is RED.**
  `player_facing.verified_utc` expires after `stale_after_days` (14 -- two league
  weeks); past that the page renders **every** line as unknown, the mismatch warning
  on row 4 included. Dropping that warning while keeping the bare board key was a
  defect found in the same review: a true-looking fact with its safety notice
  deleted reads as reassurance.
  CI **fails** on expiry rather than warning. The first wiring turned exit 2 into a
  green annotation, which would have gone permanently green-with-a-note from
  2026-08-31 while the page showed Unknown -- manufactured confidence inside the
  guard written to prevent it. Close it by re-running the commands under each
  block's `evidence` and re-stamping; raising `stale_after_days` with a recorded
  reason is also a legitimate close. Re-stamping without re-measuring is not.

### The frontier and the cut are different fields now

`regularised_from.ladder_version` is **the frontier the site publishes on**, and
it moves when a build carrying a fork is **published** -- not when the fork is cut.
`regularised_from.cut_ladder_version` records the latest fork cut in the game repo
regardless. Same split, same reason, as `boundary_ladder_version` on 2026-08-13.

Moving the frontier to an epoch no build ships would open weeks on a board no
player can reach, and would make `/leaderboard/` tell a visitor their run is
recorded on an epoch their client never posts to. It is also load-bearing:
`test-weekly-league-boundary.py` pins the frontier equal to
`board-probe-targets.json -> current_ladder_epoch.value`, so the two must move in
one commit.

### Operator step: opening a league on a new epoch

Deliberately NOT automated, and deliberately not done by a seat.

1. pdoom1 publishes a release whose `release_manifest.json` carries the new
   `ladder_version` and `league_seed`. **Until that release exists, nothing below
   may run** -- publishing a board for a client nobody has is the same class of
   error as showing a board nobody's score can reach.
2. Pip performs [Gate 5] (bless the seed) and writes the ledger row in
   `docs/LEAGUE_SEED_LEDGER.md`, reading the value **from the release artifact**.
3. Pip performs [Gate 6] (open the board), and the ledger row records who and when.
4. Only then, by hand, in one commit:
   - `public/leaderboard/data/board-probe-targets.json` -> `current_ladder_epoch.value`
   - `public/data/ladder-epochs.json` -> `regularised_from.ladder_version`,
     `regularised_from.seed`/`seed_status`, the `epochs[]` entry (which now gains
     `boundary_local` and `first_build`), and `player_facing.downloadable_now` /
     `league_open` / `coming`, re-stamping `player_facing.verified_utc`.
5. `python scripts/publish-live-board.py` to publish the board itself.
6. `python scripts/check-league-state.py` (expect 0) and
   `python scripts/test-weekly-league-boundary.py` (expect all green).

---

## 6. Quick reference

**A board is empty on opening night.** Correct, not a fault, when the seed rolled.

**Scores from before a fork do not migrate.** Different rules produced them.
Merging them is the specific lie the ladder split exists to prevent.

**The anomaly archive is immutable.** `public/leaderboard/data/preserved/`. Never
edit, never re-stamp. It is the only surviving copy — the boards it was captured
from have since been rewritten.

**If the board looks wrong, suspect the key before suspecting the players.**
`python scripts/check-board-liveness.py` prints every board it can find and
whether each is DEPLOYED, archived, or a NEW ORPHAN.
