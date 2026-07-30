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
