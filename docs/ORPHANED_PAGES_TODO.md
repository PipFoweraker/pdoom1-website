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
| `public/changelog/index.html` | 0 | 7 words of visible copy; its `data/changes.json` holds a single entry. |
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

## DECIDED 2026-07-28 — the league trio: option 3, formalised

Pip's call: `league/index.html`, `league/archive.html` and `players/index.html`
are **retired and kept hidden — not deleted, not revived**. Everything they show
that predates the 2026-07-31 patch-cycle regularisation is now labelled
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

- The league trio's staleness is **downstream of the weekly rollover off-by-one**
  (cron fires Sunday 14:00 UTC and derives the week from `now`, so it republishes
  the week that ends hours later — TECH_DEBT A9). Fixing that is a precondition
  for reviving them honestly.
- `docs/L2_CUTOVER_RUNBOOK.md` covers the epoch move that will change what a
  revived league page should read from.
