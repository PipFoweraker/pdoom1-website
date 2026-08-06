# Surface register — pdoom1-website

**Built 2026-07-30/31.** A map of every surface in this repo: what exists, what it can
break, and what is actually wrong with it right now.

**Why it exists.** Three load-bearing defects were found today *by accident*, while
looking for something else: a live XSS sink on the leaderboard, a deploy trap that meant
bot-committed data never reached the site, and a test fixture that had been rotting for
three releases. Finding things by luck does not scale to 2,247 files. This is the map
that makes them findable on purpose.

**How to read it.** Sections 1–2 are a plain-English tour — read those first, they are
the architecture. Section 3 is the inventory. Section 4 is what is broken, ranked.
Section 5 is the burn-down board: finite, countable, drivable to zero.

**Confidence marking.** Everything here was produced by five parallel audits and then
spot-checked. Claims I personally re-verified against the code are marked **[verified]**.
Claims taken from an audit and *not* independently checked are marked **[reported]** —
treat those as leads, not facts. One audit finding was checked and found **wrong**; it is
recorded in §4.9 rather than deleted, because a register that hides its own errors is
the thing it is supposed to prevent.

---

## 1. The shape of the thing

This site is **statically pre-rendered and machine-fed**. Almost nothing is authored by
hand at request time; almost everything is a file that some script wrote, that some
workflow committed, that some rsync copied to a shared host. Understanding it means
understanding four layers and the seams between them.

**Layer 1 — the pages.** 2,247 HTML files, but only **28 are hand-written**. The other
2,214 are two generated classes: 2,197 event pages and 17 design-note pages, each class
sharing one template. This matters enormously for effort: editing one f-string in
`sync-events.py` rethemes 2,197 pages, while the 28 hand-written pages carry ~147 KB of
inline CSS between them and must be touched individually. The generated pages are also,
security-wise, the **cleanest** thing on the site: zero JavaScript, zero `fetch`, zero
`innerHTML`. All the risk lives in the 28.

**Layer 2 — the data files.** Roughly 40 JSON files under `public/`. Every page that
shows a number fetches one of these at runtime. This is the honesty layer: if a number
on the site is wrong, it is almost always because a data file is wrong or stale, not
because someone typed a lie into HTML. The critical property of a data file is **who
writes it** — and the recurring bug in this repo is *more than one writer*.

**Layer 3 — the scripts.** 83 of them. They fall into three natural groups: **generators**
that produce pages or data, **guards** that check something and exit non-zero, and
**one-shots** that were run once and never removed.

**CORRECTED 2026-08-06 — "about a third are orphaned" was wrong, and the count it rested
on was stale.** Every file under `scripts/` was checked against every workflow,
`package.json`, CLAUDE.md's documented suite, and every other script: **69 of 83 were
wired**. Of the 14 that were not, three were genuinely dead and were deleted
(`update-version-info.js`, `test-header-consistency.sh`, `add_analytics.sh`), two were
green guards that had simply never been wired and now are
(`test-navigation.js`, `test-syndication-auth.js`), and **nine are unwired on purpose** —
Pip's hand-run tooling (`ab-preview.py`, `print-doc.ps1`, `render-content-review.py`,
`apply-review-print-css.py`, `test-review-print.py`), a VPS provisioning recipe
(`deploy_plausible.sh`), the unexercised option for an open decision
(`sync/merge-alignment-events.py`), a one-shot whose defect is still live
(`bugfix_pass_20260715.py`), and one referred back to Pip (`sync-forum-theme.ps1`).

**The lesson, which is the generalisable part: "nothing invokes it" is a fact about the
repo, not a verdict about the script.** A third of the apparent orphans exist precisely to
be run by a human, and one of them is the only rebuild recipe for a VPS with no backups.
Counting callers finds candidates; only reading each one produces a verdict.

**Layer 4 — the workflows.** 28 files, of which 11 carry a cron. **183 scheduled runs per
week.** They are the metabolism: they fetch from upstream repos, run the generators,
commit the results, and occasionally deploy. Most bugs that reach a visitor pass through
here, because a workflow that fails silently produces stale data that looks fresh.

### The seams — where things actually break

Four seams carry nearly all the risk, and they are worth holding in your head:

1. **Upstream → data file.** Anything crossing from `pdoom1` or `pdoom-data`. Failure
   mode: the sync fails quietly and yesterday's data keeps serving as though current.
2. **Data file → page.** Failure mode: the page renders a fallback literal instead of
   admitting it does not know, which is how invented numbers reach readers.
3. **Bot commit → production.** Failure mode: the commit lands in git and never deploys,
   so the repo and the live site disagree indefinitely.
4. **External input → `innerHTML`.** Failure mode: XSS. The score API is unauthenticated
   and validates nothing, so every field it returns is attacker-controlled.

---

## 2. The score/leaderboard model, in plain English

Worth its own section because it is the most subtle thing here and the most expensive to
get wrong.

A **board** is one leaderboard table. Every score the game submits carries a *key* saying
which table it belongs on, and the key has two halves: **which seed** (which randomised
scenario everyone is competing on) and **which ladder epoch** (which version of the
*rules* the score was earned under). Two scores are comparable only if both halves match —
same puzzle, same rules.

The ladder epoch is a plain counter, currently `L3`. It ticks only when the **rules**
change. The build version (`v0.13.2`) ticks whenever anything ships, including a typo fix.

**They used to be the same thing, and that is what lost 27 scores.** When the key used the
build version, a cosmetic patch created a brand-new empty table: players who updated
posted to one board, players who had not posted to another, and nobody's score sat next
to anybody else's. The score API returns `ok: true` with an empty list for a board that
has never existed, so **no error was ever shown to a player**, and from the outside it
looked exactly like "nobody is playing."

Splitting build from ladder fixes it. The live board legitimately spans two builds right
now — that is the split working as designed.

**The anomaly archive** (`public/leaderboard/data/preserved/`) holds nine captures pulled
off the live API on 2026-07-29, containing those 27 real submissions from six real
players. The temptation, once the key was fixed, is to relabel them so they "count".
**That would be fabricating history**: they were played under different rules, on a
different seed, in a game that has since forked the ladder twice. They stay archived, the
players get told directly, and the tooling encodes the ruling — the liveness check reports
them every run but **never fails on them**, going red only for *new* loss. A job that is
red forever is a job nobody reads.

---

## 3. Inventory

Full per-item tables live in the audit outputs; this is the shape and the counts.

| Surface | Count | Notes |
|---|---|---|
| Hand-written pages | 28 | all the risk |
| Generated pages | 2,214 | 2,197 events + 17 ADRs; static, JS-free, safest thing here |
| Data files under `public/` | ~40 | ~12 hand-edited, several dead |
| Scripts | 83 | **9** wired to nothing, all deliberate — see below |
| Workflows | 28 | 11 scheduled → **183 runs/week** |
| Guards / tests | 24 | **12 not wired to CI** |

### The automation calendar (AEST; add an hour Oct–Apr)

| Time | What fires |
|---|---|
| 04:00 / 10:00 / 16:00 / 22:00 | `auto-update-data` + `health-checks` + `update-game-data` — **three at once, two writing the same file** |
| 04:17 / 10:17 / 16:17 / 22:17 | `board-liveness` + `pull-pdoom1-issues` |
| 05:00 / 17:00 | `sync-design-notes` |
| 11:30 | `snapshot-analytics` |
| 12:00 | `sync-leaderboards` |
| 13:00 | `sync-events` — rewrites ~2,197 pages |
| 16:00 | peak: 4 workflows, 3 pushing to `main` |
| Fri 00:00 | `weekly-league-reset` |

Only **one** of the 14 workflows that commit reader-facing files can make the site
actually update. See §4.3.

---

## 4. What is broken, ranked

### 4.1 `version.json` has three writers, and the loser deletes a safety field **[verified]**

`update-version-info.py`, `calculate-game-stats.py` and an inline block in
`update-game-data.yml` all write `public/data/version.json`. Two run on the *same cron
minute*. Verified by walking the git log — the alternation is perfect:

```
fc79374e  Auto-update: version info and game stats   -> has platforms
91f34d01  chore: Update cached game data [skip ci]   -> NO platforms
a61c08c7  Auto-update: version info and game stats   -> has platforms
1eb996f9  chore: Update cached game data [skip ci]   -> NO platforms
```

`update-game-data.yml` rebuilds the file from scratch with no `platforms` key, so every
six hours the field is deleted. And `check-platform-claims.py` — the CI guard that stops
the site advertising an OS with no build — does this when the field is absent:

```python
print("SKIP: version.json has no latest_release.platforms; nothing to check.")
return 0
```

**So the honesty gate has been passing without checking anything, every second commit.**
This is *"absence of a marker is never a clean bill of health"* running live on a
six-hour cycle. Same block also re-asserts the invented game stats.

**Fix:** one writer for `version.json`; make the guard FAIL rather than SKIP.
*(Partly fixed on branch `fix/nuke-stat-placeholders` — PR #206.)*

### 4.2 Invented numbers presented as measurements **[verified]**

`baseline_doom_percent: 23` and `strategic_possibilities: 10000` were hardcoded in **three
places** and rendered on the homepage, `/stats/` and `/game-stats/` under confident
labels, with a homepage aria-label announcing *"This week's baseline doom percentage"* —
a weekly calculation that has never run. Nobody measured either number.

`frontier_labs_count` is subtler and arguably worse: it counts how many lab names from a
hardcoded list appear **in this website's own homepage**, then floors the result at 5.
The tile labelled "Frontier Labs" is the site counting mentions of itself.

**Fix:** PR #206 nulls them and renders "not yet measured". The floor and the `return 7`
fallback are addressed by PR #196.

### 4.3 One of fourteen committing workflows can actually update the site **[verified]**

A push made by a workflow using the default `GITHUB_TOKEN` does not trigger another
workflow. Fourteen workflows commit files under `public/`; **only `board-liveness` has a
`workflow_run` deploy hook** (added yesterday). Everything else — feeds, events, design
notes, issues, health data — lands in git and stops there until a human pushes.

The RSS feed is the sharpest case: `generate-feeds.yml`'s own header says *"A feed that
silently stops updating is worse than no feed"*, and the regenerated feed cannot reach
pdoom1.com without a human.

### 4.4 XSS beyond the leaderboard **[reported, spot-checked]**

The leaderboard is now fully escaped (PRs #202, #208 — 29 interpolations, 0 raw). The
sweep found more:

- **`/dashboard/`** interpolates `market.question` from `api.manifold.markets` into
  `innerHTML` and hands `market.url` to `window.open`. Genuinely third-party-controlled
  text on a **top-level nav page**. Worst remaining instance.
- **`/issues/`** escapes one of five GitHub fields; `label.color` lands in a `style=`
  attribute.
- **`/league/`, `/league/archive.html`, `/players/`, `/monitoring/`** render score and
  league data with **no escaper defined at all**.
- **Three markdown renderers, three different holes**; `/dev-notes/` has none.

There are now **three differently-named escapers** on the site with different coverage,
and two do not escape `"` or `'` — which matters because several sinks are attribute
contexts. Consolidate to one.

### 4.5 A workflow file that is invalid, and reds every push **[reported]**

`post-issue-to-forum.yml` fails at workflow-creation on **every push to every branch** —
zero jobs, just a red X. It is parked and does nothing. This is the single largest
manufacturer of alert fatigue in the repo, and it is plausibly *why* red stopped meaning
anything. Reproduce with `actionlint`.

### 4.6 Failure handlers that cannot fire **[reported]**

`version-check.yml` has **no `permissions:` block** (repo default is read-only) *and*
calls `context.repo.name`, which does not exist — the property is `context.repo.repo`.
Two independent faults in one 12-line step, invisible because the handler only runs on
failure. `auto-update-data.yml` declares only `contents: write` but calls the issues API,
so its alerting has **never** worked — on a job that runs 4×/day.

### 4.7 Stale prose presented as current **[reported]**

`docs/CONTRIBUTING_TO_EVENTS.html` states an event count of 1,028 (actual 1,194), claims
~28 events have summaries (actual 0), sets three delivery goals that expired 7–19 months
ago, advertises a **24–48 hour review turnaround**, and offers as its model of a *sourced*
quote a line attributed to a named real person with `href="#"`.

`status.json` still says `v0.11.0 / 2025-12-07` and renders on the homepage **next to**
the derived `v0.13.1`. A visitor sees both, eight months apart, on one screen.

`/cats/` has nine links to `/about/#contributors` — an anchor that does not exist.

### 4.8 Silently discarded bug reports **[reported]**

`bug-report/index.html` decides it is running locally with, among other tests,
`window.location.href.includes('localhost')` — which examines the **whole URL**. Any
production URL containing that substring anywhere (a UTM value, a fragment, a referral
parameter) takes the mock branch: the report is **discarded** and the button says
*"Report Submitted!"*. Also trivially weaponisable as a link that eats reports.

### 4.9 A finding that was wrong — recorded on purpose

One audit reported that `game-integration.py` would overwrite the live leaderboard with an
empty board every night, because CI has no game repo checkout. **I checked, and it is
false.** Both code paths (`sync_all_leaderboards()` and `export_game_data()`) begin with
`if not self.game_repo_path: return False`, and no committed config supplies that path, so
in CI they refuse and write nothing.

It is kept here because it is the most important methodological point in this document:
**an audit finding is a lead, not a fact.** This one was specific, well-argued, cited real
line numbers, and was wrong. Anything marked **[reported]** above deserves the same
treatment before anyone acts on it.

### 4.10 The guards are thinner than the docs claim **[verified]**

Of the 17 checks CLAUDE.md lists as the pre-PR suite, **12 are not wired to CI at all**.
They run only if a human remembers. That includes `check-published-emails.py` — the guard
added after 75 academics' addresses were served from 44 pages — and, until today,
`test-board-escaping.js`.

CLAUDE.md is also **wrong** about one: it says `sync-keybinds.py --check` "runs
everywhere, including CI". `grep -rn keybind .github/workflows/` returns nothing.

Three checks **crash before asserting anything**, all on the documented cp1252 trap:
`test-changelog-structure.py`, `test-integration.py`, `test-orchestrator.py`. Those three
are the *only* references to five reader-facing writers, so a naive cross-reference
counts those writers as "covered" when nothing covers them. *(PR #198 fixes the class.)*

One test **cannot fail**: `test-syndication.js` has no failure counter and no non-zero
exit path. It prints success unconditionally.

And the one that stings: **`test-board-escaping.js` — the guard I wrote today — could
never run on Windows.** `core.autocrlf=true`, so a checkout writes CRLF, and the
extractors anchor on `;
`. Under CRLF the byte after `;` is ``, so extraction died
before a single assertion. It passed for me only because I had written the file from
Python with LF preserved. It failed on the only platform CLAUDE.md tells you to run it on,
while passing in a CI that does not run it either. *(Fixed in PR #208.)*

### 4.11 Guards that pass vacuously **[verified]**

`check-platform-claims.py` currently prints `No unavailable platforms to guard against.
OK.` and returns **before scanning a single page** — because all three platforms are
currently `true`. It has never been observed rejecting anything, and there is no test that
forces a platform to `false`. Green here carries no information at all.

Combined with §4.1 — where the field is deleted every six hours and the guard then prints
`SKIP` — this check has two independent ways of passing without checking, and no way
anyone would notice.

Eight guards in total have only ever been observed passing, with nothing proving they can
fail. Only five meet the "forced failure" bar: `test-snapshot-plausible.py` (the strongest
in the repo, ~20 forced-failure constructs), `test-design-notes.py`, `test_ingest_scores.py`,
`test-analytics-optout.js`, and `test-publish-live-board.py`.

### 4.12 `validate_data.py` is green while reporting the board cannot work **[verified]**

Exit logic is `sys.exit(1 if n_fail else 0)` — a WARN can never turn the daily cron red.
The current WARN reads: *"NO stored seed file is stamped with the deployed version, so
ingest_scores.py has nothing publishable and the board will be empty whatever happens
upstream."* That is a description of the exact silent failure this repo exists to prevent,
delivered at a severity nothing acts on.

### 4.13 A guard that greps its own siblings, gating an unattended job **[reported]**

`test-weekly-league-boundary.py` asserts that the unblessed seed is hardcoded nowhere, by
globbing **every** `scripts/*.py` for the literal. During this audit it went red because a
*sibling agent's test fixture* legitimately contained that string. That test is the first
step of `weekly-league-reset.yml` and explicitly gates the unattended Friday rollover — so
a test file containing a seed string could abort a live league rollover. It needs a
test-file exclusion.


---

## 5. The burn-down board

The point of counting is that these are **finite**. Each row is a number that can be
driven to zero, and the number moving is the signal — not the redness.

| # | Population | Now | Target |
|---|---|---|---|
| 1 | Data files with more than one writer | 5 | 0 |
| 2 | Reader-facing generators with no test | 22 | 0 |
| 3 | Documented-suite checks not wired to CI | 12 of 17 | 0 |
| 4 | Orphaned scripts | ~22 | 0 (delete or stub) |
| 5 | Pages rendering external data unescaped | 6 | 0 |
| 6 | Escapers on the site | 3 | 1 |
| 7 | Fallback literals that ship on failure | 15+ | 0 |
| 8 | Mirrors with no freshness stamp | 7 | 0 |
| 9 | `check-stale-facts` findings | 213 (1 HIGH, 212 LOW) | triage, then hold |
| 10 | Committing workflows that cannot deploy | 13 | 0 or documented |
| 11 | Guards with no forced-failure test | 8 | 0 |
| 12 | Checks that crash before asserting | 3 | 0 |

**Rule for this board, from your own data-quality practice:** a big number is fine. A
number with no owner and no trajectory is not. Record the count each month; new entries
are loud precisely because the known population is quiet.

---

## 6. What is genuinely good

Worth recording, because these are the patterns to copy rather than re-invent:

- **`board_liveness_summary.py`** emits deliberately impossible sentinels
  (`newn=-1`) when it cannot read a file — *"never emit a plausible-looking zero for a
  file we could not read."*
- **`sync-keybinds.py`** is the only cross-repo mirror whose staleness is a **test
  failure** rather than a comment: 90-day expiry, required `verified_on`, and it fails if
  any key is typed literally into a page. Every other mirror should be measured against it.
- **`snapshot-plausible.py`** exits 2/3/4 writing nothing, so a bad run can never clobber
  the last good file — and has a test that forces each of those paths.
- **`publish-live-board.py`** probes and publishes in one workflow run so two derivations
  of the board key cannot disagree, and refuses rather than guessing.
- **`/metabolism/`** derives every cadence from the real crons with clickable `file:line`
  provenance, and is the only page on the site that publishes its own failures. Where it
  contradicts a sibling page, it is the one that is right.
- **The generated event pages** — 2,197 files with no JavaScript at all. Boring, static,
  and the safest surface here.
