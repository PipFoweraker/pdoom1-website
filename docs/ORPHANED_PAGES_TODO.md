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
| ~~`public/changelog/index.html`~~ | 0 | **RESOLVED 2026-07-28 — now redirects to `/game-changelog/`.** Was 7 words of visible copy over a `data/changes.json` holding a single entry, fed by `scripts/sync_airtable.py`, whose workflow was parked after 1,264 consecutive failures against an Airtable base that does not exist. See the note below. |
| `public/dev-notes/index.html` | 0 | 11 words of visible copy; renders `docs/DEV_NOTES.md` client-side. |

~~One human path in survives and is intentionally unbroken: `stats/competition.html`
links to `/league/`.~~ **GONE 2026-08-06** — `public/stats/` was deleted (option 2,
Retire), so the league trio now has **zero** inbound paths from anywhere on the site.
`noindex` still stops search engines using them as entry points.

**`public/stats/` — RETIRED 2026-08-06 (Pip's call).** Both files deleted, the
`robots.txt` `Disallow` dropped with them, and a 301 `/stats/` → `/game-stats/`
attempted in `public/.htaccess`. This closes TECH_DEBT A8's remainder. The
decisive fact was not staleness but reachability: **DreamHost's own panel
statistics area owns `/stats/` and answers `401 Unauthorized` there**
(`WWW-Authenticate: Basic realm="Statistics Area"`, measured 2026-08-06), so
neither page was ever loadable by a visitor. `stats/index.html` was a
near-duplicate of `game-stats/index.html` — 14 differing lines out of ~310, all
canonical URL, stylesheet links and whitespace — and that duplication was being
paid for: fixes this week had to be applied twice.
**`stats/competition.html` was NOT a duplicate** and has no successor page; it is
recoverable from git history if competition stats are ever wanted again.

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
duplicate. That left `/changelog/` as the only genuinely redundant URL.

**DECIDED (Pip, 2026-07-28): `/changelog/` redirects to `/game-changelog/`.** What
sharpened it was one fact from #141 — the game's in-game "What's New" fallback now
tells players *"Visit pdoom1.com for the latest updates."* `/changelog` is the URL a
person guesses from that, and it was serving a near-empty page. Redirecting was
preferred over deleting because it is reversible and removes nothing.

How it is implemented (three layers, in order of authority):

1. **`RewriteRule ^changelog/?$ /game-changelog/ [R=301,L]` in `public/.htaccess`** —
   the real mechanism. `301` because the move is permanent; a `302` would ask
   crawlers to keep re-checking a dead page forever.
2. A **meta-refresh + canonical** in `public/changelog/index.html`, as a fallback if
   the directive does not take effect on DreamHost shared hosting.
3. A `location.replace()` in that page, so the dead URL does not enter back-button
   history.

The page keeps a real visible message ("This page has moved") and a working manual
link, so it degrades honestly with JavaScript off and meta-refresh ignored. It no
longer fetches `changes.json` — flashing that stale entry before redirecting would
show a visitor an old version as if it were current.

**Neither Netlify previews nor any local test can verify layer 1** — Netlify ignores
`.htaccess` entirely. This needs a post-merge check against production:
`curl -I https://pdoom1.com/changelog/` → expect `301` and
`Location: https://pdoom1.com/game-changelog/`. If it does not, layers 2 and 3 are
still carrying it and the visitor still arrives; the fix would be a DreamHost
`AllowOverride` question, not a code change.

Two loose ends this does **not** close:

- `public/robots.txt` still carries `Disallow: /changelog/`, which forbids crawling
  the redirect. Being removed separately in **PR #181**, which should merge before or
  with the redirect.
- `public/sitemap.xml` lists `/changelog/` and does **not** list `/game-changelog/`.
  Backwards, and now doubly so. Fixing it means a change in
  `scripts/generate-sitemap.js`.

## DECIDED 2026-07-28 — the league trio: option 3, formalised

Pip's call: `league/index.html`, `league/archive.html` and `players/index.html`
are **retired and kept hidden — not deleted, not revived**. Everything they show
that predates the **L2 → L3 ladder fork** (the week beginning Fri 2026-07-31 in
Hobart — the ladder forked mid-month on gameplay changes; see
pdoom1-website#151, 2026-07-28T23:13Z) is now labelled
**anomalous pre-history** by a machine-readable `epoch` block in the data, and
the archive page renders it in a separate, explicitly-labelled anomaly section.

This closes the "permanently hidden page is dead weight" objection above: the
pages now state what they are, so a visitor who reaches one is not misled, and
the record survives for anyone tracing the history.

Two corrections to this file, found while doing that work:

- `league/archive.html` did **not** show "Failed to load archive data". Its index
  was present and parseable — but listed **3** of the **41** archive files, with
  `last_updated` frozen at 2025-10-31, because nothing ever rewrote it. So it
  rendered 3 weeks and looked fine. The index is now derived from the directory.
- The precondition named below (TECH_DEBT A9, rollover cadence) is **fixed** as
  of 2026-07-28.

Full account: `docs/LEAGUE_EPOCH_ANOMALY.md`.

`changelog/index.html` and `dev-notes/index.html` are untouched by that decision
and still need one.

## Related

- The league trio's staleness was **downstream of the weekly rollover off-by-one**
  (the cron fired Sunday 14:00 UTC and derived the week from `now`, so it
  republished the week that ended hours later — TECH_DEBT A9). Fixed 2026-07-28;
  the anchor also moved to Friday 00:00 `Australia/Hobart` (cron `0 14 * * 4`) on
  2026-07-29 so the website's week matches the game's Seed cadence.
- `docs/L2_CUTOVER_RUNBOOK.md` covers the epoch move that will change what a
  revived league page should read from.
