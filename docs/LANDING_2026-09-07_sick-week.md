# Landing document -- pdoom1-website seat, sick week (from 2026-09-07)

Pip is ill from 2026-09-07. This is the ONE document to read on return from this
seat. It accumulates through the week; newest entries go at the top of each
section. Decisions are batched so they can be answered in a single sitting.

**Nothing has been landed.** A push to `main` here auto-deploys to pdoom1.com
with no test gate (CLAUDE.md, "Deploy"), so unattended landing is off for the
week. This document and the league re-park live on the branch
`docs/sick-week-landing`, pushed so they are not on one laptop only. `main` is
untouched at `6add8299` and nothing has deployed.

**Every path cited below resolves.** Each was checked against `origin/main`
after the coordination seat found a citation in its own runbook that a reader
could not paste. Bare filenames were qualified to full paths -- `sync-events.py`
lives at `scripts/sync/sync-events.py`, and the short form silently returns an
empty `git log` that reads exactly like "nothing touched this file" while hiding
18 commits. Paths in `timeline_events/` and `DECISIONS-NEEDED_2026-09-07.md`
belong to pdoom-data and coordination respectively and correctly do not resolve
here.

**Evidence standard for this file:** every claim in a heading or a bolded
sentence reduces to a command someone else can run, and the command is written
next to it. Where a thing was not measured, it says NOT MEASURED rather than a
plausible number.

**Position against origin, because a measurement without one is not a claim.**
Everything below was first measured on a working tree **31 commits behind
`origin/main`** (and 9 ahead, carrying this document). The coordination seat
caught that after finding its own pdoom-data checkout was 34 stale and that one
of its reports had come from a month-old tree. Re-checked on 2026-09-07 with
`git fetch` and `git show origin/main:<path>`, without pulling, because pulling
under a running agent with work in flight is its own hazard:

- Of the paths these findings rest on, **only `public/data/version.json` moved**
  in those 31 commits -- six `Auto-update: version info and game stats` runs.
  `public/events/`, `scripts/sync/sync-events.py`, `public/index.html`,
  `deploy-excludes.txt` and `public/data/events.json` are all unchanged, so every
  D2 measurement stands as written.
- Both D1 facts re-verify on `origin/main`: `latest_release.platforms` is still
  `{windows: true, macos: true, linux: true}` at v0.14.4, and the false FAQ
  literal is still present, once.

Re-run any of it against the ref rather than the tree:
`git fetch && git show origin/main:public/index.html | grep -c 'no build in the current release'`

---

## 1. Decisions needed

Answer these in one sitting. Nothing here has been decided by an agent.

### D1. The homepage tells a Mac visitor two contradictory things

**Context.** `public/index.html:1038` renders the macOS download button from data
(`data-platform-claim="rendered"`), and `public/data/version.json` reports
`platforms.macos: true` for v0.14.4 because `PDoom-macOS-v0.14.4.zip` is attached
to the release. Meanwhile `public/index.html:1602`, in the FAQ prose, is a typed
literal reading *"macOS -- no build in the current release; it broke and a fix is
written"*. Both are on the same page. One of them is now false.

Separately, `public/about/index.html:503` says *"Windows is the tested one, Mac
and Linux are fresh and largely untested"*, which is accurate and should not be
contradicted by whatever replaces the FAQ line.

**Verify with:**
```
grep -n 'no build in the current release' public/index.html
python -c "import json;print(json.load(open('public/data/version.json',encoding='utf-8'))['latest_release']['platforms'])"
```

**Why an agent did not just fix it.** The one-sentence fix is reader-facing prose
making a promise about platform support, which CLAUDE.md records as copy you
review. More decisively, the comment block at `public/index.html:1013-1037`
documents this same button being disarmed, restored, re-disarmed and re-armed on
2026-08-10, 2026-08-24 and 2026-08-28, each on a judgement call. A fifth
unattended flip while you are ill is the move that history argues against.

**The precise ask.** Which of these should the FAQ line say?
- (a) "macOS -- a build ships, but nobody has confirmed it launches yet."
- (b) "macOS -- available; Windows is the tested one." (matches /about/)
- (c) Delete the platform sentence from the FAQ entirely and let the rendered
  buttons and /about/ carry it, so there is one source instead of two.

Claude's recommendation is **(c)**, because the defect is that a typed literal
exists at all next to derived data -- (a) and (b) both leave a second literal to
rot. NOT MEASURED and it would change the wording: whether the v0.14.4 Mac zip
actually launches.

**If unanswered:** the contradiction stays live. Low harm while traffic is small;
it becomes consequential the moment merch points strangers at the site.

### D2. The fabricated-quote pipeline into this site is armed, and its only guard counts rather than refuses

**CORRECTED 2026-09-07, same day, before anyone acted on it.** This card first
said "nothing fabricated is live right now", on the evidence that 0 of 1194
records in `public/data/events.json` carry a reaction. That measured the DATA
FILE and asserted about the SITE. They disagree.

**1,000 published pages carry fabricated quotes right now.** Scanning the
rendered HTML rather than its source data: 2,388 reaction blocks render the
clean `Not recorded` state, and **2,000 blocks across exactly 1,000 files render
an invented sentence in literal quotation marks**, two per page (a safety
reaction and a media reaction). Every one of the 1,000 is an
`alignmentforum_*` page. Zero `arxiv_*` pages are affected.

Sample, from `alignmentforum_00671cab97bcd7dc.html`:

> Safety Researcher Reaction: [Placeholder - Needs Real Quote]
> "Important work advancing our understanding of AI safety"

**Do not merge this with pdoom1's version of the problem.** They share a pool of
33 boilerplate strings and nothing else. In the GAME corpus, 1,132 of 1,194
records are arXiv-keyed, so an invented reaction sits against a real paper by
real, NAMED authors. In this repo's 1,000 orphan pages, the sources are Alignment
Forum, there are zero arXiv links, and the attribution is a generic "safety
researcher". The game's is the more serious of the two. Stating them as one
finding overstates this one and understates that one.

**Settled 2026-09-07: the quotation marks are real, and they are added here.**
The coordination and pdoom1 seats both recorded this as NOT MEASURED, because at
the data layer these are bare phrases with no quote characters. On the rendered
page they are not: **2,000 of 2,000 placeholder blocks are wrapped in literal
`"` characters**, added by this repo's template. So "a fabricated sentence in
quotation marks" is an accurate description of what pdoom1.com serves, and "a
boilerplate phrase in a data field" is an accurate description of what pdoom1
stores. Both seats were right about their own layer.

**All 1,000 pages pair the invented quote with a real source link** (Alignment
Forum; zero arXiv links in this corpus, unlike the synced one). The genuine
citation sits beside the invented reaction and lends it credibility -- which is
the sharper form of the honesty problem than fabrication alone.

**Two things make this less bad than it sounds, and one makes it worse.**
Less bad: the quote carries a visible provenance badge reading *Placeholder -
Needs Real Quote*, so it is disclosed rather than passed off; and it is attributed
to a generic "safety researcher", not to a named person. Worse: **these are
exactly the 1,000 orphan pages that no generator can reach.** Per
`docs/TECH_DEBT.md` E-0, they have no entry in `all_events.json`; pdoom-data
holds them in a separate collection (`timeline_events/alignment_research/`) the
sync has never read. So a gate in `scripts/sync/sync-events.py` protects against future
arrivals and **does nothing for the 1,000 already published.** Cleaning them is a
scripted one-off rewrite, the same shape as the two orphan pages that had to be
hand-fixed for the email marker.

**But the machinery is fully wired.** The event schema carries
`safety_researcher_reaction` and `media_reaction`; `scripts/sync/sync-events.py:1633` renders
a reaction as a labelled quote (`Safety Researcher Reaction:`) on the public
event page; and event pages are built from real arXiv papers by real, named
authors. pdoom1 PR #1339 proposes **1,194 fabricated researcher quotes** -- the
same count as this site's event corpus, which is consistent with both deriving
from the same pdoom-data collection.

**The provenance system is a counter, not a gate.** `get_provenance_type()`
(`scripts/sync/sync-events.py:2045`) classifies each reaction as `real_quote`,
`human_summary`, `placeholder` or `not_applicable`, and feeds `quote_stats` into
`events-sync-summary.json`. Nothing consults it before rendering. An unlabelled
reaction defaults to `placeholder` -- and a placeholder is **still published**.
So if fabricated reactions reach `all_events.json` without a
`reaction_provenance` block, this site renders invented sentences in quotation
marks, labelled as a safety researcher's reaction, attached to named people's
papers, on up to 1,194 public pages, and the only consequence is a number in a
summary file nobody reads.

This is the defect class in `docs/TECH_DEBT.md` and issue #384: a guard that
reports a value it never enforces.

**Verify with:**
```
python -c "import json;d=json.load(open('public/data/events.json',encoding='utf-8'));e=d if isinstance(d,list) else d.get('events',d);e=list(e.values()) if isinstance(e,dict) else e;print(sum(1 for x in e if x.get('safety_researcher_reaction')),'of',len(e))"
grep -n 'def get_provenance_type' -A 10 scripts/sync/sync-events.py
```

**The precise ask.** Should `scripts/sync/sync-events.py` refuse to render a reaction whose
provenance is not `real_quote` or `human_summary` -- the same fail-closed shape
`redact_pii()` already uses, where the generator declines to write rather than
publishing something it cannot vouch for?

Claude's recommendation is **yes, and before #1339 is decided upstream**, because
the gate belongs on the consuming side regardless of what the game does: this
repo is a read-only consumer of pdoom-data and cannot control what arrives. Not
done unattended because it changes what a visitor-facing page would show, and
because the honest wording of a refusal ("no reaction recorded" vs. rendering
nothing at all) is a presentation call that is yours.

**If unanswered:** the 1,000 orphan pages keep serving invented quotes, badge and
all. No sync will change that either way, so waiting costs nothing new -- but
nothing improves either, and the gate question stays open for the corpus that
IS synced.

**Second ask, separable from the first.** Should the 1,000 orphan pages be
rewritten to the `Not recorded` state now? That is a scripted edit to published
HTML with no generator behind it, so it needs a human to say yes. Claude's
recommendation is yes: the badge is honest, but an invented sentence in quotation
marks beside real research is a poor thing to serve when the alternative is two
words.

**MEASURED 2026-09-07 by the coordination seat, which has pdoom-data checked out:
there is no real reaction to substitute, anywhere.**
`timeline_events/alignment_research/alignment_research_events.json` holds exactly
1,000 records -- a 1:1 match with the 1,000 orphan pages -- with 1,000 non-null
`safety_researcher_reaction` values across **9 distinct strings**, 1,000 non-null
`media_reaction` values across **1 distinct string** (one sentence repeated a
thousand times), zero `reaction_provenance`, and zero arXiv sources. Upstream of
that, `data/raw/alignment_research/` is HuggingFace extraction metadata and
`data/enrichment/` is a quality-score table. No commentary at any layer.

That kills the substitute fix. Teaching the sync to read the real collection
cannot fix the quotes and close TECH_DEBT E-0 together, **because there is no
real collection.**

**RECOMMENDATION REVISED 2026-09-07, and the revision is better than what it
replaces.** This card first recommended SUPPRESS -- delete the two fields. That
was wrong, and verifying a peer's retraction is what turned it up.

The pages already carry an honest disclosure and a **working** correction
channel:

- `Placeholder - Needs Real Quote` renders as visible body text, not as a CSS
  class. It names the deficiency rather than euphemising it.
- Every page carries `<a href="/events/suggest-quote.html?event=<id>">`. That
  page exists (12.5 KB), is **not** in `deploy-excludes.txt` so it ships, holds a
  real form, and submits by opening a prefilled GitHub issue against
  **pdoom-data** with labels `quote-suggestion,metadata,events` -- which is the
  correct repo, since that is where the data lives.

So suppressing the fields would delete a working disclosure and the mechanism
built to retire it. **The invented sentence is the only defective part.**

**Recommended instead: keep the badge, keep the suggest link, drop the invented
sentence** -- render the 1,000 orphans into the same state the 1,194 synced pages
are already in. The template puts the badge, a `<br>` and the quote in separate
elements, so removing only the quote is a clean edit.

**Settled: the sync does not clean anything, so nothing will ever fix these
pages on its own.** It was worth asking whether `scripts/sync/sync-events.py` already drops
fabricated reactions for the main corpus, which would have narrowed this to a
code path. It does not. The only reaction handling is a URL sanitiser guarded by
`is not None` (`scripts/sync/sync-events.py:953-955`), and the comment above it states why the
synced corpus is clean: *"pdoom-data now serves null for a reaction nobody has
been asked for, and the key STAYS PRESENT so consumers indexing on it keep
working. See pdoom-data#96."*

So the 1,194 pages are clean **because pdoom-data cleaned them at source**, not
because anything here filtered them. pdoom-data nulled the main collection and
did not null `alignment_research`. Combined with the orphans having no generator
that regenerates them, the consequence is that **the 1,000 pages are frozen: no
sync, no upstream fix, and no future release changes them.** Only a human running
a script moves them, which is why this is a decision and not a backlog item.

**The strongest evidence for the shape of the fix is that the end state already
ships.** The
suggest link is on all 2,194 event pages, including the 1,194 that render
`Not recorded` and carry no quote at all. Those pages demonstrate the badge-plus-
hook-without-fabrication state working in production today. The ask is therefore
not "design something" but "make the 1,000 look like the 1,194".

Its "zero arXiv, all Alignment Forum" independently reproduces the same result
Claude measured from the rendered pages, which is a real cross-check: two seats
measuring different artifacts of one pipeline and agreeing.

**This second ask does NOT depend on the source-marking question.** The
coordination seat is right that a gate for the synced corpus should wait for
pdoom-data to mark fabrications at source, because a gate that infers which
strings are invented is a heuristic and every consumer's heuristic is wrong
differently. That argument does not reach the 1,000 orphans: their pages already
carry an explicit `provenance-placeholder` class on every one of the 2,000
blocks, so a cleanup keys on a marker that is already present and guesses at
nothing. The two asks can be answered independently and in either order.

**How the error above happened, because the mechanism recurs.** The check ran
against `events.json` and the conclusion was stated about the website. The data
file is one input to the site, not a picture of it -- and for the orphan corpus
it is not even an input. `scripts/check-published-emails.py` exists in this repo for
exactly this reason: it walks what is committed under `public/`, not what the
generator was handed. **When asking "what does the site show", scan `public/`.**

### D3. The blessing record disagrees with itself, and only you can settle it

**Found by running the suite, not by reading about it.**
`python scripts/check-blessing-consistency.py` exits **1** today. It is wired as
ADVISORY in `content-honesty.yml`, so CI is green and nothing surfaced it.

    current epoch (declared)   L6
    ledger row                 seed=weekly-2026-w35  blessed=True  by=Pip on 2026-08-24
    ladder-epochs.json         seed=weekly-2026-w35  status=blessed  epoch=L6
    weekly/current.json        seed=weekly_2026_W35_a97e68ae  blessed=False  epoch=L4
    published-board.json       seed=weekly-2026-w35  epoch=L6

Two findings: `weekly/current.json` is stamped **L4 while the declared epoch is
L6**, and it carries a **different seed form** (`weekly_2026_W35_a97e68ae` vs
`weekly-2026-w35`).

**Severity, measured rather than assumed.** `/league/` is **not** reachable --
zero `href="/league` references in `navigation.js` or the homepage, consistent
with retired-and-hidden. But `/leaderboard/` **is** in the nav, and it reads
`weekly/current.json`. It also guards correctly: `public/leaderboard/index.html:1714`
tests `weekData.seed_provenance?.blessed === true` before offering a seed, so a
`blessed: false` record means the page **offers nothing rather than offering the
wrong thing**. So no visitor is lied to. A visitor may simply be shown less than
they should be, and nobody would know why.

**Why an agent did not fix it.** The script refuses to fill a ledger row on
purpose, and says why: that row records **who** blessed and **when**, and a seat
inferring it is how #297 started. The same applies to restamping the epoch. This
is one decision written by hand to four places, and the decision is yours.

**The precise ask.** Is `weekly_2026_W35_a97e68ae` at L4 a stale artefact that
should be restamped to L6 with the canonical seed form, or is it a real L4-era
record that should be preserved and excluded from the current-epoch comparison?
The `preserved/2026-08-24-l4-epoch-close/` directory suggests the project already
has a convention for the second answer.

**If unanswered:** the leaderboard keeps failing closed, which is the safe
direction, and the advisory keeps exiting 1 where nobody looks.

### D4-D6. Merch blockers -- held in coordination, not duplicated here

`DECISIONS-NEEDED_2026-09-07.md` in the coordination repo carries, as entries
3, 4 and 5: the unresolved wordmark blocking any print run; the absent fact gate
on merch copy; and whether the "nothing may read as a launch" ruling still holds.
Answer them there. They are recorded here only so this document is a complete
index of what is waiting on you.

---

## 2. Work that needs a human, not an agent

**Verify the macOS build launches.** pdoom1 issue #1071 states no macOS build has
ever been verified to run. No agent can establish this; it needs a Mac and five
minutes. It gates D1's wording and it gates whether stranger-legible merch can
safely point at the site at all. Staff are in Monday and Tuesday -- this is the
highest-value five minutes available to a human this week.

**Share the Shirt Inspection Sheet.** Published private at
`https://claude.ai/code/artifact/f09930eb-00ee-471b-9d41-03cd2ce7781f`. It needs
sharing from the page's share menu before anyone can open it. All social is RED
this week on your own call, so no agent posts it.

---

## 3. Verified findings

Each of these was run, not inferred.

**The league rollover cron was parked five days past its own expiry, and is now
re-parked to 2026-09-21.** Committed by the coordination seat as `54cb0e2a` in
this repo, local and unpushed. `PARKED-UNTIL: 2026-09-21` at
`.github/workflows/weekly-league-reset.yml:23`, with the `schedule:`/`cron:`
lines still commented at 76-77 -- both halves are required or
`scripts/generate-metabolism.py` exits 2 on "one of the two is a lie".
Verify: `python scripts/test-weekly-league-boundary.py` gives `PASSED: 108/108`;
`python scripts/generate-metabolism.py --check` gives rc=0.
**Unconfirmed input:** the re-park rests on an instruction reported as "league
disable for week", which did not come through this seat. Conservative in either
direction, but it holds the league off for two more weeks.

**A repo comment claims the game is stable, and the shipped build contradicts
it.** `public/index.html:869` reads "Alpha warning banner removed as game is now
stable". pdoom1 #1341 -- the pause menu did not pause -- was found by you on the
shipped v0.14.4 and is fixed on pdoom1 `main` (2026-08-30) but is in no release.
Latest release is still v0.14.4, tagged 2026-08-28; the v0.15 train was due
2026-09-04 and slipped. Comment only, no visitor sees it. Recorded so nobody
reasons from it.
Verify: `grep -n 'game is now stable' public/index.html`

**CI is clean and the local checkout was 25 days stale.** Zero non-success
conclusions across the last 100 workflow runs. Local `main` was 611 commits
behind at session start and was fast-forwarded on 2026-09-05.
Verify: `gh run list --limit 100 --json conclusion`

**Issue #388 ("Health checks failing") is stale.** Open since 2026-08-26 with
zero comments, while `public/data/health-check.json` reads
`overall_status: PASS` and every Health Checks run since is green. It is an
auto-alert with no closer -- the shape #376 is about.
Verify: `python -c "import json;print(json.load(open('public/data/health-check.json',encoding='utf-8'))['overall_status'])"`

---

## 4. Not measured

Stated so nothing here reads as more settled than it is.

- Whether the v0.14.4 macOS artifact launches. Needs a Mac.
- Whether `temp_windows_build/` (untracked, ~836 MB per the pdoom1 seat, two
  files above GitHub's 100 MB limit) is still wanted on disk. Left alone.
- Whether the "league disable for week" instruction was said as reported.
- Jason's response to either shirt. The sheet is built and unshared.

---

## 5. Whether the cross-seat traffic earned its keep

Four seats messaging each other reads as overhead by default, so here is the
evidence either way rather than an assurance.

**Two findings existed only in the comparison.** Neither was visible from one
repo:

- **The quotation marks are added at the template, not stored in the data.** The
  game seat asserted the quotes ship "in quotation marks" from a PR description;
  coordination challenged it as possibly a rendering assumption and filed it NOT
  MEASURED; this seat settled it by scanning rendered HTML -- 2,000 of 2,000
  wrapped, and `scripts/sync/sync-events.py` is what wraps them. Each seat was right about its
  own layer and wrong about the other's.
- **pdoom-data holds no real reactions to substitute.** This seat proposed
  teaching the sync to read the upstream collection, which would have fixed the
  quotes and closed E-0 together. Coordination has pdoom-data checked out, and
  measured that the collection is itself the fabrication -- 9 distinct strings,
  and one media string repeated a thousand times. The hoped-for fix did not
  exist, and no amount of work inside this repo could have discovered that.

**It also caught four wrong claims, two of them this seat's.** The game seat
classified the macOS fix as safe-to-automate when the same button had been
flipped three times on human judgement; coordination told this seat to push work
stacked on top of its own parked commit, which would have deployed to production;
coordination retracted a claim that the league cron had fired unattended, whose
source was a document describing a risk rather than a measurement of it; and this
seat asserted "nothing fabricated is live" from the data file while 1,000 pages
were serving it.

**The honest summary is that the traffic was worth it and the error rate was
high.** Every one of those four was caught by someone re-measuring rather than by
someone objecting, which is the part worth keeping.
