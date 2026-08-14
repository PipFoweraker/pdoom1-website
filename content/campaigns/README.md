# Campaigns — the publication coordination centre

A **campaign** is a coordinated push that is *not* a blog post: a launch, a
trailer drop, a milestone. Blog posts already have a pipeline
(`.github/workflows/syndicate-content.yml` → `content/syndication/<slug>.json`);
this directory is the same idea for everything else.

It inherits that pipeline's governing rule, and so should you:

> **INBOUND AUTOMATED, OUTBOUND HUMAN-GATED.**
> Syncing content into the site is automatic. Publishing words out into the
> world is a decision a person makes.

Because a campaign is a committed file, git history is the audit trail of what
went out, where, and when.

---

## 1. The UTM convention (agree this BEFORE posting anything)

This is the one part with a hard deadline. Plausible groups traffic by
`utm_source` / `utm_medium` / `utm_campaign`, and `public/index.html`
(`attributionProps()`) copies them onto the **Download** event — the download
button leaves for github.com, so that click is the *only* place a download can
ever be joined to the channel that produced it.

**Post a link without UTMs and that attribution is gone permanently.** There is
no way to reconstruct it afterwards.

| param | value | notes |
|---|---|---|
| `utm_source` | `linkedin` `facebook` `twitter` `bluesky` `instagram` | lowercase, no spaces, stable forever — these become your analytics groupings |
| `utm_medium` | `social` | use `email` / `forum` / `press` when those apply |
| `utm_campaign` | `alpha-launch-2026-07-24` | one slug per campaign, reused across every platform in it |

Canonical form:

```
https://pdoom1.com/?utm_source=bluesky&utm_medium=social&utm_campaign=alpha-launch-2026-07-24
```

**Rules that keep the data clean:**

- Never reuse a `utm_source` value with different spelling (`twitter` vs `x` vs
  `Twitter` become three separate rows that never re-merge).
- Link to **`https://pdoom1.com/`**, not directly to the GitHub release. A
  direct GitHub link bypasses the site, so the visit is invisible to analytics
  *and* the download is unattributable. The site's buttons resolve to the right
  per-platform asset anyway.
- Instagram has no clickable link in post captions — put the UTM'd link in the
  **profile bio** and say "link in bio". Use `utm_source=instagram` there so bio
  clicks are still counted.

---

## 2. File format

One JSON file per campaign, named `YYYY-MM-DD-slug.json`. Same shape as a
syndication draft, so the existing publisher can consume it later without
rework:

```jsonc
{
  "campaign": "alpha-launch-2026-07-24",  // matches utm_campaign exactly
  "title": "...",
  "url": "https://pdoom1.com/",           // base URL, before UTMs
  "approved": false,                       // nothing goes out until a human sets true
  "copy":   { "<platform>": "..." },       // exact text to post
  "posted": { "<platform>": null }         // ISO timestamp once posted; null = not yet
}
```

`approved: false` and `posted: null` are the safety interlocks. Fill `posted`
in as you go — it is your checklist *and* the record.

### 2.1 `_facts_this_copy_must_not_break` — write the CONSTRAINT, not the value

This block is the list of things your copy must not contradict. It is checked by
`python scripts/check-campaign-facts.py`, wired **blocking** into
`content-honesty.yml`.

**Until 2026-08-14 it was an array of prose strings, and two of them had become
lies:**

```json
"Windows build ships today (v0.13.0). macOS and Linux are NOT yet released...",
"Do NOT promise leaderboards or scores - remote submission is not live yet..."
```

Both were true when written. All three platforms now ship and the board holds
real scores. A third entry claimed the game was "open source", which it never
was; it was found by a person, by luck (#284).

**The defect was not the wrong sentences. It was pinning a claim about a moving
world as if it were immutable.** What is actually immutable is the constraint:

| the value (rots) | the constraint (does not) |
|---|---|
| "macOS and Linux are NOT yet released" | "do not promise a platform that is not downloadable" |
| "do NOT promise leaderboards, submission is not live" | "do not promise a feature that is not live" |

A constraint written that way can be **asked of a source** on every run. So each
entry is now an object, and it must declare **how it is known**:

```jsonc
{
  "id": "platforms-downloadable",              // stable slug; the key it reports under
  "constraint": "Do not promise a platform that is not downloadable...",
  "verify": "checked",                          // one of the five below
  "check": "platforms_shipped",                 // which verifier
  "source": "public/data/version.json -> latest_release.platforms ..."
}
```

| `verify` | means | what it needs | blocks? |
|---|---|---|---|
| `checked` | the script verifies it offline against an in-repo source | `check` + `source` | yes |
| `delegated` | another wired guard already owns it | `check` (script path) + `source` | yes — if that guard has been deleted or unwired |
| `online` | only checkable over the network (a GitHub issue's state) | `check`, `issue`, `expect`, `source` | no — advisory job only; the blocking job prints **NOT CHECKED**, never a pass |
| `human` | no machine here can check it — and it says so | `why_not_machine`, `source`, `human_verified` | only when the verification **expires** |
| `durable` | asserts nothing about the world, so it cannot rot | `why_durable`, and **no** source/check/clock | n/a |

Verifiers available to `checked`: `platforms_shipped`, `board_live`,
`no_version_literal_in_copy`. `online` has `issue_state`.

**`human` is the honest answer, not the escape hatch.** Some things genuinely
cannot be machine-checked here — whether the game is still "an alpha", what
another repo's licence says. Saying so explicitly beats a false green. It costs
a dated stamp:

```jsonc
"human_verified": {
  "by": "who actually looked",
  "on": "2026-08-14",
  "review_by": "2026-11-14",       // the check goes RED here
  "note": "what you saw"
}
```

Past `review_by` the check is red on **"this verification expired"** — never on
the claim itself. That red always closes by a person deciding something: re-read
the source and re-stamp it, or fix the constraint. Same rule as
`scripts/acknowledgements.py`, and the warn window is read from that ledger.

**Two things the check will not do.** It will not fail a campaign that has
already been **posted** — that copy is a historical record and editing it to
clear a check would be falsifying it, so findings there print as HISTORY. And it
will not rewrite your words: where the copy itself has drifted, the finding goes
to `data/acknowledgements.json` with a date, and the decision stays yours.

Useful:

```
python scripts/check-campaign-facts.py            # the gate
python scripts/check-campaign-facts.py --list     # every guard and its tier
python scripts/check-campaign-facts.py --online   # + resolve issue states
python scripts/check-campaign-facts.py --as-of 2027-01-01   # what expires when
python scripts/test-campaign-facts.py             # prove the gate can still fail
```

---

## 3. Running a campaign

1. Draft copy in the JSON. Edit freely — it is your voice, not the tool's.
2. Check every link carries the UTM triple for **its own** platform.
3. Post. Work down the platforms, stamping `posted` as each goes out.
4. Log what comes back in `feedback-intake.md` — see §4.
5. Commit the file. The diff is the audit trail.

**Post in slowest-feedback-first order.** LinkedIn and Facebook keep showing a
post for hours or days; Twitter and Bluesky are near-realtime and mostly dead
within the hour. Posting the slow ones first means they are accumulating reach
while you handle the fast ones, and it staggers the replies you have to answer.

---

## 4. Collecting feedback (the half that usually gets dropped)

Feedback will arrive across at least five surfaces, none of which talk to each
other: social replies and DMs on each platform, the website form, direct texts
and calls, and GitHub. Without one intake point, the quiet-but-important report
is the one that gets lost.

`feedback-intake.md` is that point. Append one line per item, from wherever you
are. It is deliberately plain text so it costs nothing to add to on a phone.

**Two things to know about today's channels:**

- **The in-game F8 bug reporter does not transmit** (pdoom1 issue #800). It
  writes to the tester's own disk and then tells them a report was filed. Do
  not point anyone at it until that ships a fix — direct people to
  `https://pdoom1.com/bug-report/` or a plain reply instead.
- **The website form is fail-silent to you.** If DreamHost's PHP `mail()` drops
  a message, the sender sees success and you never learn it existed. Smoke-test
  it before you announce (`docs/GLIDEPATH.md` §7), and if the day looks
  suspiciously quiet, suspect the pipe before concluding nobody cared.
