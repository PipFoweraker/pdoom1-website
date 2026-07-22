# Tech debt register — pdoom1-website

Captured 2026-07-22 from five parallel audits (analytics, technical correctness,
ambition debt, design system, feedback channels) and the fix agents that
followed. Each item has evidence, not a vibe.

**Status key:** `OPEN` · `PARKED` (deliberate, revisit trigger noted) ·
`NEEDS-PIP` (only he can do it — credentials, DNS, a product call).

Ordered by "what does a visitor or player actually suffer", not by how annoying
it is to a developer.

---

## A. Actively wrong to a visitor or player

| # | Item | Evidence | Effort | Status |
|---|---|---|---|---|
| A1 | **No Plausible backups.** Single DreamCompute VPS, no snapshots, no `pg_dump`, no ClickHouse `BACKUP DATABASE`, nothing offsite. The multi-year history Pip wants to animate is one incident from permanent loss. | `grep -rn "pg_dump\|BACKUP DATABASE" scripts/ ansible/ .github/` → only config lines. `docs/analytics/SELF_HOSTED_PLAUSIBLE.md:509` lists "create monthly backup script" as never done. | 3-5h + a restore drill | **NEEDS-PIP** |
| A2 | **`api.pdoom1.com` has no valid TLS cert** — resolves to the forum VPS (`208.113.200.215`), `curl` returns `000`. If score submission targets it, submissions fail outright. | DNS lookup + curl. pdoom1 PR #679 nominates this host for the score API. | ~1h (DNS + certbot) | **NEEDS-PIP** |
| A3 | **DNT is honoured on 4 pages out of 2,226.** `analytics.js` is only included by `index`, `about`, `press`, `privacy`. A visitor arriving on a deep-linked event page is counted before the ignore flag is ever set. | `grep -rl "assets/js/analytics.js" public --include=*.html` → 4 files. | 1h — add to the event generator template and re-emit | OPEN |
| A4 | **`generate_game_aware_sample_data()` drops `data_status`.** If that fallback fires it overwrites `leaderboard.json`; `applyDataStatus` defaults absent → `'live'`, so the "pre-launch" honesty banner silently disappears and an empty board reads as a real one. | `scripts/game-integration.py`, `public/leaderboard/index.html`. | 0.5h | OPEN |
| A5 | **3.78 MB cat PNG** on `/dashboard/`, in the initial desktop viewport. `loading="lazy"` added but barely helps there. No downscaled variant exists (`small-doom-cat.png` is a different cat). | `public/assets/pdoom1-office-cat-default.png` | 0.5h | OPEN |
| A6 | **Corrected dashboard prose is invisible.** `loadEventLog()` replaces all of `#narrativeBox` with the last 3 changelog entries on load, so the re-dated "Situation Analysis" shows for a moment and is gone. | `public/dashboard/index.html` | 0.5h | OPEN |
| A7 | **No favicon anywhere.** 5 pages request `/favicon.svg` which 404s; the other 2,239 declare none, so browsers fall back to `/favicon.ico` → also 404. Top-ranked missing target in the whole link graph. | `ls public/*.svg public/favicon*` → nothing. | 0.5h | OPEN |
| A8 | **`robots.txt` blocks `/data/`, `/design/`, `/stats/`** — but the homepage fetches `/data/version.json` and `design/tokens.json` at runtime. Googlebot obeys robots.txt for subresources, so it renders the hardcoded fallbacks and `/stats/` is de-indexed entirely. | `public/robots.txt` vs `public/index.html:1504,1531,1776,787` | 0.25h | OPEN |
| A9 | **Weekly-league rollover is off by one week.** Cron fires Sunday 14:00 UTC; `get_current_week_info()` derives the week from `now`, so it creates the week that *ends* 10 hours later. `validate_data.py` confirms: "week 2026_W29 is marked is_current but ended 2.4 days ago". 10 weeks of green checkmarks, all wrong. This is the #126 false positive, proven. | `scripts/weekly-league-manager.py:73`, `weekly-league-reset.yml` | 0.5h | OPEN |

---

## B. Structural — cheap now, expensive later

| # | Item | Evidence | Effort | Status |
|---|---|---|---|---|
| B1 | **Nav drift: ten distinct variants.** `test-header-consistency.js` reports **0/23 files passed, 184 errors**. Three regimes: 7 pages runtime-inject via `navigation.js`, 7 hand-copy divergent navs, 8 have only "← Back to Home", 1 (dashboard) had none until today. `public/includes/navigation.html` is wired into **zero** pages. | `node scripts/test-header-consistency.js` | 8-20h | OPEN |
| B2 | **29 hand-written pages not tokenised.** 147 KB of inline CSS across them, median 5.3 KB, max 16.6 KB (`index.html`). The 2,197 generated pages move with one template edit; this long tail does not. | design audit | ~15h | OPEN |
| B3 | **Sitemap covers 15 URLs of 2,244.** `generate-sitemap.js` uses a hardcoded `routes` array; all 2,197 event pages — the entire long-tail indexable content — are absent. | `scripts/generate-sitemap.js:12-29` | 1h | OPEN |
| B4 | **OpenGraph coverage ~1.5%.** 34 of 2,244 pages have `og:title`, 17 have `og:image`. Every share of an event page renders as a bare URL. Fix in the event template, regenerate. | link-graph sweep | 1h | OPEN |
| B5 | **`og:image` is 2.49 MB** (`pdoom1_logo_1.png`), above Twitter's practical fetch budget — so shares may render with no image at all. | `public/index.html:16` et al. | 0.5h | OPEN |
| B6 | **~26 MB of dead assets are rsynced to production** every deploy: `assets/dump/` (~11 MB, referenced by zero HTML), `assets/image-processing-systems/dump/` (~5 MB), un-downscaled `screenshots/*.png` originals (~10 MB), `8-bit-effect.gif` (1.58 MB, unreferenced). | file sweep | 0.5h (rsync `--exclude`) | OPEN |
| B7 | **`data/events.json` is 1.18 MB, uncompressed**, fetched on every visit to `/events/`. DreamHost won't gzip JSON without an `.htaccess` directive. | `public/events/index.html` | 0.5h | OPEN |
| B8 | **Nav links to a raw `.md` file** (`/docs/roadmap.md`). DreamHost serves markdown as a download, so clicking "Roadmap" downloads a file instead of showing a page. Same for 5 `.md` routes in the sitemap. | `public/assets/js/navigation.js:39` | 1h | OPEN |
| B9 | **Duplicate DOM id on the leaderboard.** `id="cards-view"` on both a button (`:746`) and a div (`:774`); `getElementById` returns the button, so card rendering targets the wrong node. | `public/leaderboard/index.html` | 0.25h | OPEN |
| B10 | **123 markdown files in `docs/`** — five on syndication, five on analytics, five session summaries from one day. They describe the *intended* system, so every new agent rediscovers the same gaps. This is the mechanism that generates ambition debt. | `docs/` | 2-4h prune | OPEN |
| B11 | **`deploy.yml` and `update-stats.yml` are self-declared no-ops** created by the (now deleted) `bootstrap.sh`. Both fail on every run. | their own `run:` lines | 0.1h | OPEN |

---

## C. Security / privacy

| # | Item | Evidence | Effort | Status |
|---|---|---|---|---|
| C1 | **Committed credentials** in `docker-compose.yml`: `POSTGRES_PASSWORD: nodebb123`, `ADMIN_PASSWORD: ChangeThisPassword123!`, a 64-hex `SECRET` — for a box that is genuinely running and reachable. In git history, so rotation is the only fix. | `docker-compose.yml` | 1h | **NEEDS-PIP** |
| C2 | **Score-API token ships in the public build** (`godot/data/leaderboard_config.json`), acknowledged in its own `_comment`. Accepted for a friends-and-family alpha; needs server-side rate limiting and a rotation plan before wider release. | game repo | — | **PARKED** until wider release |
| C3 | **"GDPR Compliant / fully compliant by design"** on `/privacy/`. With retention now honestly stated as indefinite, this leans entirely on the data being anonymous rather than pseudonymous. Defensible for Plausible's daily-rotated-salt model, but it is a legal claim. Recommend softening to a factual statement ("no cookies, no consent banner required"). | `public/privacy/index.html` | 0.25h | **NEEDS-PIP** (product call) |
| C4 | **Country-level geolocation claim is unverified.** Disclosed on the privacy page erring toward over-disclosure, on the strength of the repo's own docs listing "Countries" as a dashboard metric. If geolocation is actually off on that instance, the bullet should go. | `docs/analytics/SELF_HOSTED_PLAUSIBLE.md:496` | 0.1h | **NEEDS-PIP** (dashboard login) |
| C5 | **`/issues/` form still emails a free-text contact field** to `team@pdoom1.com` via `mailto:`. Less bad than the bug form was (that pasted addresses into public GitHub issues, now removed), but still uncovered by the "we never collect PII" framing. | `public/issues/index.html:380,676` | 0.5h | OPEN |

---

## D. Wanted features (not debt, but captured here so they aren't lost)

| # | Item | Notes |
|---|---|---|
| D1 | **Privacy-first opt-in subscribe** — dev-blog updates, playtest invites. Pip's explicit want. The homepage newsletter form is currently `mailto:`-only and captures nothing. Constraint: privacy first, so favour a self-hosted list or a plain RSS feed over a third-party marketing platform. **Cheapest honest first step: publish an RSS feed for the dev blog** — zero personal data, zero infrastructure, works forever. Then an opt-in email list only if RSS proves insufficient. See D2. |
| D2 | **RSS/Atom feed for `public/blog/`.** `index.json` already holds every field a feed needs (filename, title, date, tags, summary). ~1h, no privacy cost, and it directly serves "let people follow updates". |
| D3 | **In-game update check** — filed as pdoom1#799. The actual answer to "how do I reach players who have an old build". No personal data required. |
| D4 | **Plausible Stats API → committed JSON snapshots** in `public/data/analytics/`. Partially hedges A1 by giving a git-versioned second copy of the history that survives losing the VPS. Needs the API key. |
| D5 | **ADR + DQ practice for this repo.** Pip wants the same decision-record discipline the game repo has (17 ADRs, 38 DQs, a generated index with a pre-commit staleness check). The game's `scripts/generate_dq_index.py` is a working model to copy. |

---

## E-0. TAGGED FOR PIP / pdoom-data uplift — do NOT delete

### The 1,000 "orphaned" alignmentforum event pages are not orphans

Initially scoped for deletion as dead weight. **Tracing them to source reversed
that conclusion.** Recorded here in full because the wrong call would have
destroyed the only published surface for a live dataset.

What is actually true:

| fact | evidence |
|---|---|
| 1,000 pages under `public/events/alignmentforum_*.html`, 15.8 MB | file count |
| **All 1,000 exist in pdoom-data**, with full content | `pdoom-data/data/serveable/api/timeline_events/alignment_research/alignment_research_events.json` — 1,000 entries, 1.2 MB, each with title, description, impacts, sources, tags, rarity, pdoom_impact, and both reaction fields |
| **None of them appear in `all_events.json`** | that file holds 1,194 events: 1,129 `arxiv`, 37 `distill`, and a handful of others. Zero `alignmentforum` |
| The sync only ever reads `all_events.json` | `scripts/sync/sync-events.py:61` |
| Nothing on the site links them | sampled 20, no inbound references; the sitemap contains no event pages at all |

So pdoom-data maintains **two** event collections and the website sync knows
about one. The 1,000 pages are the only place the alignment_research dataset is
published, and they are no longer regenerated or updated by anything.

**This is a decision, not a cleanup.** Either:

- **(a)** extend `sync-events.py` to also ingest
  `alignment_research/alignment_research_events.json`, bringing the 1,000 pages
  back under management (they would then be regenerated, rethemed and validated
  like every other event page); or
- **(b)** deliberately retire the dataset from the website and delete the pages
  as a conscious editorial choice.

Deleting them *without* making that choice would silently drop 1,000 pages of
curated content whose source is alive and well. Pip is uplifting pdoom-data next
week; this belongs to that work.

**Also flagged upstream:** `pdoom-data/.../timeline_events/manifest.json` claims
`"total_events": 28`, which matches neither the 1,194 in `all_events.json` nor
the 1,000 in `alignment_research`. That manifest is stale and should not be
trusted by anything.

---

## E. Known-and-deliberate (do not "fix" without reading the reason)

- **`public/css/site.css` loads LAST on ~2,203 pages** and wins the cascade. Every rule in it must be dark-palette-correct. It has caused a sitewide whiteout once. The file carries a comment explaining this; keep it.
- **41 weekly archive files and 15 seed leaderboards still stamped `v0.4.1`** (~159 occurrences). Left deliberately: the archives are empty shells, and the seed files contain 66 real dev-session entries from a v0.4.x pygame client. Restamping would fabricate history. `ingest_scores.py:88-95` already excludes anything whose version ≠ deployed, so none of it can reach the live board.
- **`seed_leaderboard_*.json` `meta.game_version: "1.0.0"`** is the *export tool's* version, not the game's. Mislabelled upstream; flagged, not rewritten.
- **`sync-pdoom1-docs.yml`, `extract-analytics.yml`, `sync-airtable.yml`, `post-issue-to-forum.yml`, `weekly-deployment.yml`** are all parked to manual dispatch with the reason recorded in each file's header. Read the header before re-enabling any schedule.
- **Forum (`forum.pdoom1.com` has no DNS record despite NodeBB being live on port 80)** — deprioritised by Pip: GitHub Discussions is the plan until a forum emerges naturally. Not debt; a decision.
- **`check-stale-facts.py` still reports the 4 dashboard share prices** as MEDIUM ASSERTED. They are now individually date-tagged in the markup; the detector has no "is it dated?" suppression yet. Improving that is itself a small piece of debt.
