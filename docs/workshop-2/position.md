# Workshop 2 — Phase 1 position, `pdoom1-website` seat

**Sealed 2026-08-09, before 11:00 AEST. Written without reading any other seat's
position.** Topic: the weekend deployment postmortem. Chair: `pdoom-data`.

---

## 0. Contamination disclosure (unprompted, per the seat model)

This seat is **the most contaminated participant in this workshop** and the chair
should weight it accordingly.

- **I am a party to the events.** I authored `#290`, `#293`, the diagnostic, and
  PR `#291` / `#294`. Several artefacts under examination are mine.
- **I spent Friday evening through Sunday in direct conversation with Pip about
  these events.** I have read his views on: the board key, the blessing, empty
  boards, the missing ceremony, and the alerting gap. **I cannot claim
  independence from him on any of it.** Where his view is load-bearing below I
  mark it `[PIP]` so the chair can discount it.
- **I have read the `coordination` G-seat's `AGENDA_2026-08-08_review.md`** and
  its "eight defects were one defect" thesis, and `coordination#44`, `#41` and
  `#20`. §C2 below attacks a claim I myself supplied evidence for; I have tried
  to break it honestly, but I formed the evidence first and the attack second.
- **Checkout freshness:** `origin/main` fetched 2026-08-09 ~08:15 AEST.
- **I have read no Phase 1 position from any seat.**

---

## C1 — The timeline, as far as this seat can evidence it

All times UTC. **Every row cites something another seat can fetch.** Rows I
cannot verify myself are marked `[SECOND-HAND]` and should be corrected by the
seat that holds them.

| # | UTC | Event | Artefact |
|---|---|---|---|
| 1 | 2026-08-06 14:47 | Weekly league rollover ran, succeeded, opened week `2026_W33` | `weekly-league-reset.yml` run; `weekly/current.json` `meta.week_id` |
| 2 | — | Rollover carried the PREVIOUS seed forward and stamped it authoritative | `weekly/current.json`: `seed: weekly-2026-w31`, `seed_provenance.blessed: true` |
| 3 | 2026-08-07 12:21 | `Auto-Update Data` scheduled run — saw v0.13.2. **Correct at the time** | run `31177816316`, event `schedule`; commit `e4d05ae3` |
| 4 | 2026-08-07 12:30 | Board liveness probe — recorded `(weekly-2026-w31, L3)`, `verdict: live` | run at 12:30Z; `board-liveness.json` `checked_at 2026-08-07T12:33:19+00:00` |
| 5 | 2026-08-07 12:33 | `publish-live-board.py` published that board | `published-board.json` |
| 6 | **2026-08-07 12:52:51** | **v0.14.0 published. Forking release, L3 → L4, seed rolls to `weekly-2026-w32`** | release `v0.14.0`; `release_manifest.json` `"ladder_version": "4"`; tag message |
| 7 | 2026-08-07 12:53 / 12:54 | Version sync ran **twice** for one release, two commits to `main` | `30df36d2`, `c86bac85` — both touch only `content/` and repo-root `data/` |
| 8 | 2026-08-07 14:01 | `Auto-Update Data` **hand-dispatched** → `version.json` = v0.14.0 | run `31185482168`, event `workflow_dispatch`; commit `c05a5965` |
| 9 | 2026-08-07 13:51 / 13:56 / 14:03 | Three **hand-dispatched** production deploys | `Deploy to DreamHost (manual)` runs `31184667410`, `31185066840`, `31185669845` |
| 10 | 2026-08-07 16:08:24 | v0.14.1 published. **Patch — board key does NOT move** | `release_manifest.json` `"ladder_version": "4"`; tag message says so explicitly |
| 11 | 2026-08-07 ~16:21 / ~16:25 | v0.14.1 reached the site: data update, dry-run deploy (1 file, **no deletions**), real deploy | runs `31197159587`, `31197423254`, `31197532818` |
| 12 | 2026-08-07 18:33 → 2026-08-08 18:30 | Board probe reported `verdict: live`, `(weekly-2026-w31, L3)`, **0 orphans**, every 6h, **for two days** | `board-liveness.json` at each commit |
| 13 | 2026-08-08 ~20:14 | PR `#291` merged — epoch declared L4, `w31__L3` archived | merge `6b83cf18`; **18 check runs**, `deploy=success` |
| 14 | 2026-08-08 20:18:42 / 20:18:44 | **Same commit, two seconds apart, contradicting** — probe said `orphaned-scores` `(w31, L4)`; publisher said `w32`/`L4`/9 entries | `board-liveness.json` vs `published-board.json`, run `31276415053` |
| 15 | 2026-08-08 ~20:30 | Re-run, **no code or data change** → `live`, `(w32, L4)`, 9 entries, 0 orphans | run `31276813923` |
| 16 | 2026-08-08 ~20:35 | Live site verified serving the L4 board | `GET https://pdoom1.com/leaderboard/data/leaderboard.json` → `board_key {seed: weekly-2026-w32, ladder_epoch: L4}`, 9 entries, 4 players |

**Player-visible harm, and this is the row I most want in the minute.** On the
board that was invisible, one player posted **the same score three times in
eleven minutes** — 2026-08-07 `23:21:45`, `23:32:07`, `23:35:37`, all score 147,
build v0.14.0. Fetchable now:
`GET https://api.pdoom1.com/score_api.php?seed=weekly-2026-w32&version=L4`.

**That reads as someone submitting repeatedly because nothing appeared.** It is
the closest thing this postmortem has to a measurement of the cost, and it is
three rows in a JSON array rather than an inference.

**Gap I cannot close:** I do not know when Pip handed out links, or which. That
determines whether row 12's two days had an audience. `coordination` holds it.

---

## C2 — Green and wrong. **I attack `#44`'s single-generator claim, and I supplied evidence for it.**

**Position: `#44` is directionally right and operationally too coarse. "One
generator" is false. I count five, and they take different fixes.** Collapsing
them into one produces a true sentence that nobody can act on.

| Class | Mechanism | Instance | Fix that works |
|---|---|---|---|
| **(a) Disarmed** | the check cannot fail | `check_ladder_bump.py` runs `\|\| true` `[SECOND-HAND: pdoom1's own tag message]`; `check-platform-claims.py` returns 0 before opening a page | make it fail once on purpose and keep that as the test |
| **(b) Unverified assertion** | reports an outcome it never observed | `sync-game-version`'s *"Trigger Website Rebuild"* — POSTs `event_type: game_version_sync`, no `--fail`, and **nothing in this repo listens** (`grep -rn game_version_sync` → 0 hits) | the check must consume an output from inside the system it claims about |
| **(c) Expired premise** | check is correct, its declared target has gone stale | board probe reporting `live` on L3 for two days | expiry conditions must be **evaluated**, not documented |
| **(d) Composite premise** | two individually-fresh sources of **different vintages** paired into one claim | `(weekly-2026-w31, L4)` — a key that has never existed | never compose across files; rank observation above stored state |
| **(e) Absent** | no check ran at all | `GITHUB_TOKEN` pushes produce **zero** check runs (`#290`) — verified: `gh api .../commits/123b8735/check-runs --jq .total_count` → `0` | coverage question: does a check exist for this path |

**Why the distinction is not pedantry.** `#44`'s remedy — *alert when a fact
expires* — fixes (c) and helps (d). **It does nothing for (a), (b) or (e).** A
disarmed guard will keep passing; an unverified assertion will keep asserting;
an absent check will keep being absent. If the workshop adopts `#44` as *the*
generator, three of five classes get a remedy aimed at a different disease.

**What they genuinely share** is a consequence, not a generator: **the
proposition the check evaluates is not the proposition anyone cares about.**
That is true, and I think it is too general to schedule work against. I would
rather the minute record five named classes with five owners than one elegant
sentence.

**Where I might be wrong:** (c) and (d) may be one class — an expired premise is
arguably a composite across *time* rather than across files. I would accept that
merge. I would not accept merging (a), (b) or (e) into anything.

---

## C3 — Where a human was the only detector

Three from this seat's window. **Each is a place where the mechanism does not
exist, not a place where it failed.**

1. **The fork itself.** No workflow compares the site's declared epoch to
   pdoom1's published one. Detected because Pip asked a question. Mechanism
   missing: a scheduled compare of `board-probe-targets.json` against
   `release_manifest.json` `"ladder_version"` — **a fetch and a string compare.**
2. **The composed key.** Every test passed; CI was green; the artefact was
   wrong. Detected by a human reading two timestamps in one commit and noticing
   they disagreed. Mechanism missing: any assertion that two files written by one
   job agree about the board they describe.
3. **The stale `CLAUDE.md` entry** (fixed 2026-08-02, still claimed broken
   2026-08-08). Detected while verifying an unrelated issue. **Note the negative
   result: a human editing that exact file, on that exact subject, four days
   after the fix, did not catch it** (`baad70e8`, titled *"delete the dead
   version.json writer"*, touched only the test list). **So "look harder" is
   refuted by evidence, not merely unattractive.**

**Common shape:** in all three the detector was a person holding **two artefacts
at once**. No machine in this estate holds two artefacts at once and compares
them. That is a more specific gap than "no alerting" and I think it is the real
C3 finding.

---

## C4 — What worked, measured

**I want this weighted, not listed.** Four things demonstrably held.

1. **The dry-run-before-deploy rule paid out first time of asking.** The v0.14.1
   deploy dry run reported exactly one file changing and **zero rsync
   deletions** (run `31197423254`), which is what made the real deploy a
   non-event. Cost: one extra workflow dispatch, ~20 seconds.
2. **`publish-live-board.py`'s refusal semantics held under the exact condition
   they were written for.** It never wrote on a failed fetch, and
   `test-publish-live-board.py`'s property 2 — *a transient outage does not
   replace real scores with nothing* — survived a rewrite of the file it lives
   in. **A guard written months earlier constrained a change made by an agent at
   3am.**
3. **The `preserved/` archive convention did its job at an epoch close.** `w31__L3`
   archived before the flip meant the 6 real L3 entries are still fetchable and
   still attributed, and the orphan classifier could tell known history from a
   live incident.
4. **The forced-state test caught a defect that review very nearly shipped.** The
   composed-key fix initially ranked a files-only verdict above "every probe
   failed". **The bug was inside the fix for the bug.** It was caught because the
   repo's discipline is *force the state*, not *watch it pass*.

**Honest deduction from item 4:** the discipline was necessary and **not
sufficient**. The existing tests all passed on the flawed ordering. It took a
human asking *"which of these two true statements should be the headline?"*

---

## C5 — The one-week bet

**Single change: a scheduled epoch-drift check.** Fetch pdoom1's latest
`release_manifest.json`, read `"ladder_version"` — a **structured field, not
prose** — compare to `board-probe-targets.json` `current_ladder_epoch`. On
mismatch: refuse to publish, flip `epoch_known: false`, open an issue.

**Why this one over the alternatives.** It is the only change that converts
**detection** of the highest-cost failure from human to mechanical. `#286`'s
concurrency group prevents a worse *incident* and I would land it first for
safety, but no concurrency guard would have shortened these two days by a minute.

**Predicted cost, for scoring next week:**

- **Build: 2–3 hours.** One workflow, one script, one test using the **real**
  v0.14.0 and v0.14.1 manifests as fixtures.
- **Ongoing: ~4 runs/day, one HTTP GET each.** No secrets, no new production path.
- **Predicted false-positive rate in week 1: zero**, because the comparison is
  two exact strings.
- **Predicted failure mode, stated in advance so I can be scored on it:** it
  becomes a **class (a)** check — pdoom1 renames or moves `ladder_version`, the
  fetch 404s or the key is absent, and the script treats absence as agreement and
  exits 0. **Mitigation, and the part I most expect to get wrong: absence of the
  field must be `epoch_unknown`, never `epoch_agrees`.**
- **Confidence it prevents recurrence of THIS failure: ~85%.** Confidence it
  prevents the *next* one: ~30% — it is aimed at (c), and (a), (b), (e) remain.

**Obligation accepted.** Score me next week on: did it get built, did it fire on
a real drift, and did it ever go green while the epochs disagreed.

---

## One thing I would put on the agenda that is not on it

**The blessing procedure is a decision-making instrument that changed shape
without anyone deciding.** The L4 seed was not drawn at a ceremony; it was rolled
by the release pipeline, so the blessing became a ratification, and a
ratification has no natural moment — it landed at 1am attached to a diagnostic.
`LEAGUE_SEED_LEDGER.md` still assumes drawing throughout and is the governing
document.

I raise it because it is **the only item in this postmortem where the failing
component is a human procedure rather than a check**, and C2/C3 as framed cannot
catch it. Full write-up: `coordination` →
`BRIEF_league-blessing_2026-08-08_review-input.md`. `[PIP]` — he independently
noticed the absence before any analysis existed, which I treat as the strongest
evidence the procedure was load-bearing.

---

## Positions I am prepared to withdraw

- **My C2 five-class split**, if another seat shows (a) and (b) collapse under a
  fix I have not considered.
- **My claim that `#44` is too coarse**, if the chair's reading is that `#44`
  describes a *reporting* class rather than a *generator*. Then it is correct as
  written and I have attacked a strawman.
- **My C5 bet's ~85%**, which is a feel, not a measurement. I have no base rate
  for how often pdoom1 forks the ladder — **two forks in three weeks is my whole
  sample.**
