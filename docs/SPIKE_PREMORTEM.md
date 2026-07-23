# Premortem: the day traffic suddenly spikes

Written 2026-07-23, ahead of a wider release. The scenario: someone with reach
amplifies the game, and traffic goes from a handful of friends to thousands in a
few hours — unplanned, unscheduled, and not repeatable. You get those specific
people once.

Two things make this worth preparing for even if the odds of any single spike
are low (call it 10–25%):

1. **The moment of maximum audience is the moment of maximum fragility.** Almost
   everything that can break here breaks under load, and load is exactly what a
   spike brings.
2. **It is asymmetric and one-shot.** A spike that lands on a broken or
   dead-ended site is not refundable. The same crowd does not come back to check
   whether you fixed it.

So the premortem runs in two directions, and the second is the one usually
neglected:

- **DOWNSIDE** — the spike arrives and something *breaks*.
- **UPSIDE** — the spike *works*, and we fail to *capture* it.

Each item below is framed as the two futures you asked for: what future-you is
glad we did, and what alternate-future-you regrets.

---

## DOWNSIDE — the spike breaks something

### D1. Shared hosting buckles under load
- **Glad we did:** added gzip + cache headers to `.htaccess` (this branch). On a
  static Apache site this is *the* lever — `events.json` drops ~1.18 MB → ~200 KB,
  HTML/CSS/JS compress 70–80%, and images cache for 30 days so a returning or
  multi-page visitor re-fetches almost nothing. Excluded 23 MB of source-image
  dumps from the deploy so they stop being served at all.
- **Regret if missed:** DreamHost throttling to 503s for the one hour that
  mattered, in front of the one audience that mattered.
- **Still on you (highest residual):** the two heavy *linked* images — the
  **2.6 MB OG logo** (fetched by every social crawler and link-unfurl, which in a
  viral moment is a torrent) and the **3.8 MB dashboard cat**. Compression does
  not touch PNGs. Downscaling both to < 300 KB is the biggest remaining win and
  needs a human eye on the result. Pillow is available.

### D2. The analytics VPS falls over exactly when the interesting traffic arrives
- **Glad we did:** `scripts/snapshot-plausible.py` + `snapshot-analytics.yml`
  (this branch) pull the stats into git, so the spike's *shape and sources*
  survive even if the box later dies. This is the closest thing to insurance on
  the data you care most about.
- **Regret if missed:** "I had 20,000 visitors and, because the VPS died under
  the load and there were no backups, I cannot prove it, reconstruct it, or ever
  animate it." That is the specific loss that would sting most, given why you
  track this at all.
- **Still on you:** set `PLAUSIBLE_API_KEY` **now**, not after — the hedge only
  helps for snapshots taken *before* a crash. And real DB backups
  (`pg_dump` + ClickHouse + offsite) remain a VPS-side job the website cannot do.
  (Tech debt A1.)

### D3. The download path is wrong or confusing at the worst moment
- **Glad we did:** `resolveDownloads()` degrades safely — if the GitHub API is
  slow or an asset is missing, the buttons keep a working release-page link.
- **Regret if missed:** thousands click "Download", get a 404 or last month's
  build, and bounce.
- **Still on you:** publish the release **non-draft** (the `/releases/latest` API
  excludes drafts, so a draft leaves the site advertising the old version), and
  settle the duplicate asset names (`PDoom-Windows.zip` vs
  `PDoom-Windows-v0.11.0.zip`) so the download count isn't split. `alpha-watch.py`
  warns on the draft case.

### D4. First impression reads as janky in front of exactly the wrong crowd
- **Glad we did:** the truth pass and the nav/header fixes already shipped; the
  event pages are on the coherent amber palette.
- **Regret if missed:** 27 hand-written pages still on the old neon green clash
  visibly with the amber event pages; `/dashboard/` carries a 3.8 MB image.
- **Still on you:** the palette pass on the hand-written pages — deliberately
  left for you to drive. The most-visible seam is `public/events/index.html`
  (linked from all 2,194 rethemed pages).

### D5. A flood of feedback with nowhere good to land
- **Glad we did:** the bug form falls back to a prefilled GitHub issue; the
  in-game path is being fixed (game issue filed).
- **Regret if missed:** `pdoom1.com/api/report-bug` returns **404** in production
  (the Netlify redirect doesn't apply on DreamHost), so the "nice" path is dead
  and only the fallback works. Under a flood, a smoother intake would have
  captured far more signal.
- **Still on you / next pass:** decide whether to wire the report endpoint or
  lean entirely on the GitHub fallback and say so plainly on the page.

---

## UPSIDE — the spike works, and we fail to capture it

This is the half that gets skipped, and the regrets here are quieter but larger:
a successful spike that converts almost nobody.

### U1. Thousands of curious visitors and no honest way to stay connected
- **The gap:** the only visible "subscribe" on the homepage is a **newsletter
  form that opens a `mailto:`** — it captures nothing, there is no list, and it
  quietly implies one exists. RSS now exists (this session) but is not surfaced
  as *the* follow path.
- **Glad we would have:** a clear, honest "follow along" block — the dev-blog RSS
  feed, "watch releases" / "star" on GitHub — so a curious visitor can convert
  into someone who sees the *next* release without handing over anything.
- **Regret if missed:** 20,000 people came, loved it, and left with no thread
  back. The next release ships to the same handful of friends. **This is the
  single highest-value upside item, and it is yours to word** — content, not
  infrastructure, so I did not touch it. Strong recommendation: replace or demote
  the mailto newsletter and lead with RSS + GitHub follow.

### U2. Can't tell the story of where the spike came from
- **Glad we did:** Plausible captures referrer + UTM; `snapshot-plausible.py`
  preserves the sources breakdown to git; `public/data/analytics/annotations.json`
  lets you log "posted to X on <date>" so a spike stays explainable years later.
- **Regret if missed:** a year from now, an unexplained cliff in the graph and no
  memory of what caused it.
- **Still on you:** configure the `Download` goal + custom properties in Plausible
  **before** links go out (property allow-listing is not retroactive), and log
  each amplification in `annotations.json` on the day.

### U3. People say generous things and it evaporates
- **The gap:** no place or habit for capturing praise/testimonials in the moment.
- **Glad we would have:** a running file of quotes (with source + date + link) —
  the raw material for a testimonials section and for the grant/donor story
  (issues #86, #78).
- **Regret if missed:** the warmest social proof you will ever get scrolls past
  in replies and is gone. Cheap to start: a `content/testimonials.json` you paste
  into during the event. (Not started — flagging rather than pre-building, since
  what counts as worth keeping is your call.)

### U4. A bigger outlet picks it up and the press kit isn't ready
- **Glad we did:** a press page exists (`public/press/`).
- **Regret if missed:** a journalist wants a logo, a screenshot set, and a
  factsheet in the next hour and can't self-serve.
- **Still on you:** verify the press kit is actually complete and its assets are
  reasonably sized (the 2.6 MB logo again). Issues #79 and #6 both cover this.

### U5. The spike is a fundraising / recruiting moment and the ask isn't ready
- **Regret if missed:** peak attention with no "why fund this" or "how to help"
  path to point it at. The grant-readiness cluster (#78–#87) is the place this
  lives; none of it is spike-ready.
- **Honest call:** probably fine to leave for the alpha — but if a spike looks
  plausible, a single clear "support / follow the project" destination is worth
  more than any individual page.

---

## The short version

If you do only three things before a spike is possible, in order:

1. **Set `PLAUSIBLE_API_KEY`** and confirm the `pdoom1.com` site + `Download`
   goal exist in Plausible. This makes the spike *capturable*. (10 min, only you.)
2. **Add an honest "follow along" block** to the homepage — RSS + GitHub, not the
   mailto. This makes the spike *convertible*. (Your words.)
3. **Downscale the OG logo and the dashboard cat** to < 300 KB. This makes the
   spike *survivable* on shared hosting. (Needs a human eye; Pillow is available.)

Everything on this branch (compression, caching, deploy trimming, the analytics
snapshot hedge) is the part that could be done safely without you. The three
above are the part that needs your key, your words, and your eye.
