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
