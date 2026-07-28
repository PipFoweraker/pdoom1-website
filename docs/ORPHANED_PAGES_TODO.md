# Orphaned pages — cleanup TODO

Hidden on **2026-07-24** (launch day) rather than fixed, because launch time was
better spent on pages visitors could actually reach. **Hidden ≠ deleted** — each
carries `<meta name="robots" content="noindex, nofollow">` and a `robots.txt`
`Disallow`. Nothing was removed from `public/`.

Deleting a file from `public/` removes it from production on the next
`rsync --delete`, and Chesterton's fence applies: these are wired to real data
pipelines someone may intend to revive. **Decide before deleting.**

## What was hidden, and what's actually wrong with each

| page | inbound links | the problem |
|---|---|---|
| `public/league/index.html` | 0 (nav, homepage, sitemap all absent) | Presents a **live** weekly competition: a running countdown (`DAYS HOURS MINUTES SECONDS`) for a week that **ended 5 days ago**, plus visible "Failed to load standings." |
| `public/league/archive.html` | 0 | Reads `leaderboard/data/weekly/archive/index.json`, whose `last_updated` is **2025-10-31** — nine months stale. Shows "Failed to load archive data." |
| `public/players/index.html` | 0 | Player profile with all-zero stats and "Failed to load player profile." |
| `public/changelog/index.html` | 0 | 7 words of visible copy; its `data/changes.json` holds a single entry. **Its data pipeline is structurally dead** (audited 2026-07-28) — the only writer of `changes.json` is `scripts/sync_airtable.py`, whose workflow was parked after 1,264 consecutive failures because the Airtable base it reads does not exist. "Revive" is therefore not a cheap option for this one. See the note below. |
| `public/dev-notes/index.html` | 0 | 11 words of visible copy; renders `docs/DEV_NOTES.md` client-side. |

One human path in survives and is intentionally unbroken: `stats/competition.html`
links to `/league/`. `noindex` stops search engines using these as entry points; it
does not break that link.

## The decision to make (per page)

For each, pick one:

1. **Revive** — fix the data source, then remove the `noindex` **and** the
   `robots.txt` `Disallow`, and add it back to `navigation.js`/`sitemap.xml`.
   The league trio is only worth reviving once scores actually flow (pdoom1 #735)
   and the rollover cadence is fixed (TECH_DEBT A9) — otherwise it will go stale
   again the same way.
2. **Retire** — delete from `public/` (accepting the production removal) and drop
   the `robots.txt` entries. Check nothing links in first.
3. **Keep hidden** — fine as a holding state, but revisit; a permanently hidden
   page is dead weight that still ships in the deploy.

## `/changelog/` specifically — one extra decision, from the #141 audit

The site has **three** changelog-ish URLs. Audited 2026-07-28 while building the
player-facing release notes for issue #141:

| URL | data | who writes the data | reachable? |
|---|---|---|---|
| `/game-changelog/` | now derived at runtime from `data/version.json` + the pdoom1 releases API | `update-version-info.py` (every 6h) | **yes** — nav "Updates", homepage footer "Releases", `/press/` ×2, `/dashboard/` |
| `/website-changelog/` | `data/website-changes.json` | nobody; hand-typed, newest entry 2025-10-09 | yes — homepage footer "Changelog", `/press/` ×1 |
| `/changelog/` | `data/changes.json` | `sync_airtable.py` — **dead** (see above) | no — `noindex` + `Disallow`, 0 inbound links |

`/game-changelog/` is the live player-facing one and is where #141 was built.
`/website-changelog/` is a different audience (site infrastructure), so it is not a
duplicate. That leaves `/changelog/` as the only genuinely redundant URL, and its
disposition is an **owner call**, sharpened by one fact from #141: the game's
in-game "What's New" fallback now tells players *"Visit pdoom1.com for the latest
updates."* If that text is ever made a specific link, `/changelog/` is the URL a
person would guess — and today it serves a near-empty page. Options:

1. **Redirect** `/changelog/` → `/game-changelog/` (a meta-refresh + canonical; no
   deletion, reversible). Turns the most guessable URL into the right page.
2. **Retire** it — delete from `public/`, drop the `robots.txt` entry.
3. **Leave it** — fine, but then don't let anything ever link players to `/changelog`.

Note that `public/sitemap.xml` currently lists `/changelog/` (which is `Disallow`ed
and `noindex`) and does **not** list `/game-changelog/` (which is the live one).
That is backwards whichever option is picked; fixing it means a change in
`scripts/generate-sitemap.js`.

## Related

- The league trio's staleness is **downstream of the weekly rollover off-by-one**
  (cron fires Sunday 14:00 UTC and derives the week from `now`, so it republishes
  the week that ends hours later — TECH_DEBT A9). Fixing that is a precondition
  for reviving them honestly.
- `docs/L2_CUTOVER_RUNBOOK.md` covers the epoch move that will change what a
  revived league page should read from.
