# Press strategy — draft for Pip's review

Status: **draft, 2026-07-29.** Written to Pip's brief ("consider slowly uploading
assets, hero and poster art, etc to bluesky and twitter as Press Strategy #1 —
please also have a crack at the rest of this"). Nothing here has been executed.
Lives in `docs/`, which does not deploy, so no reader sees it.

This document does **not** invent new machinery. It sits on top of what already
exists: `content/campaigns/` (the coordination centre), its UTM convention, and
the rule those inherit — **INBOUND AUTOMATED, OUTBOUND HUMAN-GATED** (ADR-0001).
Nothing goes out until a human sets `approved: true` in a campaign file.

---

## 0. The audience model this is built on

Two different mechanisms, and conflating them is how indie marketing goes wrong.

- **Consistency builds the floor.** Regular, low-effort, in-character posting
  accumulates a small number of people who recognise the project on sight. The
  floor is what you have on a bad week. It compounds slowly and it does not
  spike.
- **One well-placed post in the right community raises the ceiling.** A single
  post read by the *right* few hundred people — an AI-safety forum, an
  indie-strategy subreddit, a Godot channel — produces more than a month of
  broadcast. The ceiling is lumpy, unpredictable, and mostly a function of
  *venue fit*, not post quality.

The practical consequence: **run the floor on autopilot cadence, and spend
deliberate effort on venue selection for the ceiling.** Do not spend ceiling
effort on floor posts, and do not expect floor cadence to produce ceiling
results.

The audience we are building the floor for is small on purpose. Pip's framing —
*"I'm building this game for about 80 people on the planet"* — is the strategy,
not a joke about it. A campaign that would work by reaching a hundred thousand
indifferent people is the wrong campaign. Reaching eighty of the right ones is
the win condition, and it makes almost every conventional growth tactic
irrelevant to us.

---

## Strategy #1 — the slow asset drip (Bluesky + X)

**The idea.** We have hero art, poster art, cat art, pixel-processed screenshots
and a logo that nobody outside the repo has seen. Releasing them all at once
produces one post. Releasing them one at a time produces a *cadence* — and
cadence is the floor.

**Shape.**

| | |
|---|---|
| Platforms | Bluesky and X first (image-native, low-friction, our people are on Bluesky) |
| Rhythm | one asset per week, same day, no more |
| Campaign slug | one slug for the whole drip, e.g. `art-drip-2026-08` — **not** one per post |
| Copy | one or two lines about *what the thing is or why it exists*, not a pitch |
| Link | most posts carry **no link at all**; roughly every third carries the UTM'd `https://pdoom1.com/` |
| Gate | one campaign JSON per month, `approved: false` until Pip flips it |

**Why "no link at all" on most posts.** Two reasons, one of them ours and one of
them the platforms'. Ours: a link in every post reads as an ad, and the drip's
job is recognition, not conversion. Theirs: link-bearing posts have historically
been shown to fewer people on X. Neither claim is measured *by us* — the second
is widely reported and not something we can verify from here. [verify?]

**Why the assets are the right raw material.** Because they are true. A
screenshot is not a promise; it is the thing. The drip never has to claim the
game is finished, and it never risks the site's prime directive.

**The queue** (draft — Pip reorders freely; check each file actually exists and
is not on `deploy-excludes.txt` before scheduling):

1. Hero background art — the widest, most immediately legible image we have.
2. Office gameplay screenshot 1 — "this is what the game actually looks like".
3. The office cat. It is the most human thing in the project and it costs
   nothing to lead with charm.
4. Logo / poster treatment.
5. Office gameplay screenshot 2 — the bureaucracy visible: budgets, staff cards.
6. A UI detail shot with one line about *why* it works that way.

Six posts is roughly six weeks. That is a whole quarter's floor for about an
hour of total work, which is the point.

**One rule that makes this safe.** Every image posted must already be committed
in this repo and deployable — never a private mock-up or an unshipped feature.
If it is not in `public/`, it does not go out. That keeps the drip inside the
same honesty boundary as the site.

---

## 2. The rest of the press strategy

### 2.1 What we are actually pitching

Not "a game about AI safety". That description recruits people who want a
lecture and repels people who want a game.

The pitch is the one already written in the alpha-launch campaign copy, and it
is correct: **the bureaucracy is the game.** You run an AI safety lab. Hiring,
funding, compute, and a heroic amount of paperwork between you and saving the
world. The satire and the sincerity are load-bearing at the same time, and
that combination is the thing that is genuinely rare.

Second-order framing, for outlets that need a hook: a solo developer built an
institutional-management game about the risk he works on professionally, and
published the model's assumptions on the website so you can argue with them.
That is a story about *epistemics in public*, which is a different and better
story than "indie dev ships game".

### 2.2 Venue tiers (ceiling work)

Ordered by fit, not by size. Fit is the whole variable.

**Tier A — communities that already care about the subject.** The AI-safety
adjacent web: LessWrong / EA Forum (post as a person, not a marketer, and expect
to be argued with — that is the value), AI-safety Discords and local chapters,
PauseAI's community spaces. These readers will not be impressed by polish and
will be impressed by an honest model. **Highest ceiling, requires the most care.**

**Tier B — communities that care about the form.** r/gamedev, r/godot, the Godot
community showcase, indie-strategy and management-sim communities,
bureaucracy-sim adjacent spaces (the Papers Please / Democracy / Plague Inc
audience). These reward screenshots and mechanics, not themes.

**Tier C — press proper.** Small outlets and individual writers who cover
political/management sims and unusual indies, before anyone large. A solo dev
alpha is not a story for a big outlet yet; it is a good story for someone who
writes about strange strategy games.

**Tier D — aggregators and calendars.** itch.io, IndieDB, Godot showcase lists,
"games about X" roundups. Low effort, small and persistent return, and they keep
paying out for years.

**Deliberately not doing:** paid promotion, key-drop mailouts, influencer
outreach, or a mailing list. The first three do not work at this scale and the
fourth is a personal-data liability we have explicitly chosen against — the RSS
and Atom feeds are the privacy-first subscribe option and cost us nothing to
keep honest.

### 2.3 Sequencing

The order matters more than the content.

1. **Fix the front door first.** Every Tier-A/B post sends people to
   `pdoom1.com`. Anything false or broken on the way in wastes a ceiling event
   that cannot be re-run. The press kit, the gallery and the download path are
   prerequisites, not follow-ups.
2. **Run the drip (Strategy #1) for a few weeks.** It costs almost nothing and
   it means a curious visitor from a later post finds an account with a history
   rather than a cold start.
3. **Then one Tier-A post**, chosen carefully, timed near something real — a
   release, a league epoch, the doom-clock page shipping. One at a time, with a
   fortnight between, so each one's result is legible.
4. **Tier B and D opportunistically**, whenever there is a genuine artefact.
5. **Tier C last**, and only with a working press kit to point at.

### 2.4 Timing to the metabolism

The project already has a monthly rhythm (Epoch Friday; website issue #165's
Hop B is the monthly publication leg). Press should ride it rather than invent
its own calendar: the monthly "world turned over" post is the natural anchor for
one deliberate outbound push per month, with the weekly drip filling the gaps.
That gives twelve real moments a year without manufacturing any.

---

## 3. Mechanics that are non-negotiable

### 3.1 UTMs

Read `content/campaigns/README.md` §1 and follow it exactly. The short version:

`public/index.html`'s `attributionProps()` copies UTM params onto the Plausible
`Download` event. The download button leaves for github.com, so **that click is
the only place a download can ever be joined to the channel that produced it.**
A link posted without UTMs is unattributable permanently — there is no
reconstruction after the fact.

Always link to `https://pdoom1.com/`, never straight to the GitHub release: a
direct link bypasses the site, so the visit is invisible *and* the download is
unattributable. The site's buttons resolve the right per-platform asset anyway.

### 3.2 Character budgets — and the asymmetry nobody warns you about

X and Bluesky do **not** cost the same, because they treat the URL differently.

- **X:** 280 characters, and every link is wrapped by `t.co` to a flat 23
  characters regardless of its real length. UTM parameters are therefore free.
- **Bluesky:** 300 graphemes, and there is **no shortener** — the full URL text
  counts. Our canonical UTM'd link is 93 characters, which is **31% of a
  Bluesky post spent on tracking**.

Measured against the existing launch drafts in
`content/campaigns/2026-07-24-alpha-launch.json`:

| platform | draft length | effective | limit | headroom |
|---|---|---|---|---|
| X | 349 raw | 279 after t.co wrapping | 280 | **1 character** |
| Bluesky | 273 (URL counted in full) | 273 | 300 | 27 characters |

That X draft is one character from being rejected, and it only fits *because*
t.co shortens. Anyone editing it without knowing that will break it.

Two practical rules follow:

- **Keep campaign slugs short.** `art-drip-2026-08` instead of
  `alpha-launch-2026-07-24` recovers 7 Bluesky characters; dropping to
  `artdrip` recovers 16. On X it makes no difference at all. Slugs are still
  forever-stable analytics keys, so pick short *and* permanent.
- **Draft for Bluesky first, then relax for X.** The tighter budget is the real
  constraint. Going the other way produces posts that need re-cutting.

### 3.3 The campaign file is the audit trail

One JSON per campaign in `content/campaigns/`, `approved: false` until a human
says otherwise, `posted[platform]` stamped with an ISO timestamp as each goes
out, then committed. The git diff is the permanent record of what was said,
where, and when. For the drip, one file per month with the six posts inside is
easier to live with than six files.

Post in **slowest-feedback-first** order (LinkedIn and Facebook keep showing a
post for days; X and Bluesky are mostly dead within the hour), so the slow ones
accumulate reach while you handle the fast ones.

### 3.4 Feedback intake

Log everything that comes back in `content/campaigns/feedback-intake.md`, from
wherever you are. Two live caveats that predate this document and still apply:
the in-game F8 bug reporter **does not transmit** (pdoom1 #800), so do not point
anyone at it; and the website form is **fail-silent to us**, so a quiet day may
be a broken pipe rather than an indifferent audience. Suspect the pipe first.

---

## 4. What counts as working

Deliberately modest, because at this scale most metrics are noise.

- **Floor:** the drip ran on schedule without becoming a chore. That is the
  whole success criterion for Strategy #1. Follower count is not a target.
- **Ceiling:** for each Tier-A/B post, did Plausible show a distinguishable
  `utm_source` cohort that reached the download button? One legible cohort per
  post is the entire measurement. If the UTMs were right, this is free; if they
  were wrong, no amount of analysis recovers it.
- **The real signal:** did anyone email `team@pdoom1.com`, file an issue, or say
  something specific about a mechanic? Eighty of the right people is the goal,
  and eighty of the right people show up as *conversations*, not as a chart.

---

## 5. Open questions for Pip

1. **Which handles exist?** This document assumes Bluesky and X accounts for the
   project. If they are personal rather than project accounts, that changes the
   voice and probably the whole plan. Not verified from here.
2. **Tier A is a values call, not a marketing one.** Posting the game into
   AI-safety spaces means presenting a *satire* of that world to that world.
   Worth deciding deliberately before the first post, not in the replies.
3. **Slug convention.** Adopting short slugs (§3.2) means the existing
   `alpha-launch-2026-07-24` becomes an inconsistent precedent. Keep it and
   start short from the next campaign, or accept the inconsistency permanently?
4. **Does the drip need a poster?** "Poster art" was in the brief; the repo has
   hero art and screenshots, and whether a dedicated poster exists is not
   something this document verified.
