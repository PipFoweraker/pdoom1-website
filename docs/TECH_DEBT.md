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
| A5 | ~~**3.78 MB cat PNG** on `/dashboard/`, in the initial desktop viewport.~~ Fixed in `faa3ff7e` before this row was re-read: the PNG became `pdoom1-office-cat-default.webp`, 960x900, **55,840 bytes** (-98.5%), and `dashboard/index.html:987` points at it. Live: `curl -sI pdoom1.com/assets/pdoom1-office-cat-default.webp` returns 200 / 55,840. `small-doom-cat.png` remains a different cat and was not substituted. | `public/assets/pdoom1-office-cat-default.webp` | done | **DONE** |
| A6 | **Corrected dashboard prose is invisible.** `loadEventLog()` replaced all of `#narrativeBox` with the last 3 changelog entries on load, so the re-dated "Situation Analysis" showed for a moment and was gone. | `public/dashboard/index.html` | 0.5h | **FIXED** — the dev log now renders into its own `#devLog` child appended below the analysis; a failed/empty fetch leaves both the analysis and `#devLog` untouched. No prose changed. |
| A7 | ~~**No favicon anywhere.**~~ **RESOLVED — this row was stale.** Both `public/favicon.ico` and `public/favicon.svg` now exist. Re-verified 2026-07-28. Only **6 of 2,245** pages *declare* a `rel="…icon"` link — but that no longer matters to a visitor, because browsers fall back to `/favicon.ico` at the root and that file now exists, so every page resolves an icon. The declaration gap is now cosmetic (2,239 pages get the 192-byte `.ico` rather than the `.svg`). Not worth 0.5h; fold into the event-template work if ever. | `ls public/favicon*` → `.ico` (192 B) + `.svg` (350 B); `grep -rl 'rel="[^"]*icon' public --include=*.html` → 6 | — | **CLOSED 2026-07-28** |
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
| B5 | ~~**`og:image` is 2.49 MB**~~ Two passes. `3aa21ba6` moved all 17 `og:image` tags off the 2,611,379-byte `pdoom_logo_1.png` onto `og-card.jpg` (235,016 B) — but kept the source's **1024x1536 portrait** shape, and every page declares `twitter:card=summary_large_image` (~1.91:1), so scrapers centre-cropped to the cat's chest and cut the laser eyes out of frame. `og-card.jpg` is now a deliberate **1200x630** crop, **93,595 bytes**, regenerated by `scripts/make-og-card.py` (`--check` asserts shape + a 300 KB budget). Same filename, so no page needed editing and no third variant exists. Closes #16. `pdoom_logo_1.png` stays: `/press/` links it as the press-kit logo download. | `scripts/make-og-card.py` | done | **DONE** |
| B6 | **~34 MB of source material is rsynced to production.** Now excluded by `deploy-excludes.txt`, shared by all four workflows that rsync `public/` to DreamHost — previously only `auto-deploy-on-push.yml` had excludes, so dispatching any of the other three re-uploaded everything. Measured: `assets/dump` 11,152,471 B (12 files), `assets/image-processing-systems` 11,615,856 B (132), `assets/screenshots/*.png` 9,184,720 B (4 masters, every on-site screenshot is a derived `-web.jpg`/`.webp`/`hero-bg-*` variant), `8-bit-effect.gif` 1,656,220 B. All verified referenced by zero deployed html/css/js. `scripts/check-deploy-excludes.py` re-verifies both invariants on demand. **Caveat: `--delete` PROTECTS excluded paths, so the copies already on the server stay fetchable** (`curl -so/dev/null -w '%{size_download}' pdoom1.com/assets/8-bit-effect.gif` → 1656220 as of 2026-07-28). Reclaiming those needs one manual `rm` — command is in the workflow comment. | `deploy-excludes.txt` | done (+1 manual `rm`) | **NEEDS-PIP** (the one-off `rm`) |
| B7 | ~~**`data/events.json` is 1.18 MB, uncompressed**~~ `public/.htaccess` (landed `43c41b4c`) carries `AddOutputFilterByType DEFLATE application/json`. Verified live 2026-07-28: `Content-Encoding: gzip`, **1,198,304 → 164,755 bytes on the wire (-86.2%)**, plus `Cache-Control: max-age=300` from the `mod_expires` block and the three security headers. | `public/.htaccess` | done | **DONE** |
| B8 | **Nav links to a raw `.md` file** (`/docs/roadmap.md`). DreamHost serves markdown as a download, so clicking "Roadmap" downloads a file instead of showing a page. Same for 5 `.md` routes in the sitemap. | `public/assets/js/navigation.js:39` | 1h | OPEN |
| B9 | **Duplicate DOM id on the leaderboard.** `cards-view` was on both a button (`:746`) and a div (`:774`); `getElementById` returned the button, so card rendering targeted the wrong node — and `setViewMode('table')` set `display:none` on the Cards button itself, hiding the toggle. | `public/leaderboard/index.html` | 0.25h | **FIXED** — toggles renamed `view-btn-table` / `view-btn-cards`; the containers keep their ids. Page now has zero duplicate ids. |
| B10 | **123 markdown files in `docs/`** — five on syndication, five on analytics, five session summaries from one day. They describe the *intended* system, so every new agent rediscovers the same gaps. This is the mechanism that generates ambition debt. | `docs/` | 2-4h prune | OPEN |
| B11 | **`deploy.yml` and `update-stats.yml` were self-declared no-ops** created by the (now deleted) `bootstrap.sh` (`f602822f`). The "fail on every run" note was itself stale: `bootstrap.sh` emitted them with literal `\n` instead of newlines (`deploy.yml` was one unparseable line; `update-stats.yml` was empty), so both failed in 0s on every push until `7026e814` rewrote them as valid `workflow_dispatch`-only no-ops. Neither has run since **2025-09-09**. | their own `run:` lines | 0.1h | **FIXED (deleted)** — see note below |

### B11 note — why these two were deleted rather than parked

CLAUDE.md's workflow trap #4 says *prefer parking a broken workflow to
`workflow_dispatch` over deleting it*. That rule protects **real work that is
temporarily broken**. These two held none, and were already parked:

- `deploy.yml`'s entire body was `echo 'Add your deploy steps here'`. It is **not**
  the deploy. The real one is `auto-deploy-on-push.yml` ("Auto-Deploy to DreamHost
  on Push"), with `version-aware-deploy.yml` and `deploy-dreamhost.yml` as the two
  manual variants — the three documented in `.github/workflows/README.md`, which
  never mentioned `deploy.yml`. A workflow literally named `deploy` sitting beside
  them is a decoy: it is the first thing anyone hunting "the deploy" clicks, and it
  says deploys are a no-op. (`docs/archive/IMPLEMENTATION_SUMMARY.md:281` already
  mis-cites it as the deployment trigger, for a GitHub Pages setup this repo has
  never used — the site is on DreamHost shared hosting.)
- `update-stats.yml`'s body was `echo "Stats updater disabled."`. The real stats
  updater, `scripts/calculate-game-stats.py`, is already run by
  `auto-update-data.yml` (6-hourly) and `health-checks.yml`.

Parking preserves knowledge; there was none to preserve, and `git show f602822f`
still has both bodies. Nothing else in the repo references either file.

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

## Spike readiness

See `docs/SPIKE_PREMORTEM.md` for the full two-sided premortem (spike breaks us /
spike succeeds and we fail to capture it). The three items only Pip can do:
set `PLAUSIBLE_API_KEY`, add an honest homepage "follow along" block (RSS+GitHub,
not the mailto newsletter), and downscale the 2.6 MB OG logo + 3.8 MB dashboard
cat. Compression, caching, deploy-trimming and the analytics-to-git hedge are
done (branch `feat/spike-readiness`, merged — `43c41b4c` is on `main`).

**Updated 2026-07-28.** Both image items are now done too (A5, B5), and the
deploy trim was finished and made enforceable: see B6. The payload work leaves
exactly one thing only Pip can do — a single manual `rm` on the DreamHost box to
unpublish the ~34 MB of source material that earlier deploys already uploaded.
An rsync `--exclude` cannot do it, because with `--delete` an exclude *protects*
the remote copy rather than removing it.

## Flaky / stateful tests

- **`scripts/test_ingest_scores.py`** — **FIXED.** It was state-dependent, but the
  diagnosis recorded here was only half right, so both halves are worth keeping:

  1. *What was actually failing.* Case 1 ran against the checked-in fixture
     `scripts/fixtures/leaderboard/seed_leaderboard_fixture_live.json`, whose
     `meta.game_version` was the hardcoded literal `"v0.11.0"`. `ingest_scores.py`
     only publishes a seed as `live` when its stamp equals the **deployed** version
     from `public/data/version.json`. The moment that advanced to `v0.13.1` the
     fixture stopped matching, so the test reported `pre-launch`/0 entries and went
     red — caused by a routine release, not by any code change. That is the same
     "fallback literal" class CLAUDE.md warns about, wearing a test's clothes.
  2. *The state dependency that had not bitten yet.* Case 2 called `ingest_scores`
     with **no** `--input`, defaulting to the live `public/leaderboard/data/`, and
     asserted the result was `pre-launch` with 0 entries. Verified by planting one
     correctly-version-stamped seed there: `ingest_scores` immediately reported
     `status=live`, 1 entry. So the first real score to land would have failed the
     test — the leaderboard going live would have looked like a broken build.

  Fix: every fixture is now built in a temp dir by the test itself. The only repo
  read left is `version.json`, and the deployed version is *read from it and stamped
  into the fixture*, so the test tracks releases instead of rotting against them.
  Coverage was widened while the file was open: ADR-0002 sort **and** tiebreak,
  test-seed-filename exclusion (plus `--include-tests`), `--include-legacy`
  publishing as `legacy` with the producer's stamp overridden by the deployed one,
  and the empty-input case. The now-unreferenced fixture file was deleted.

## Fail-silent monitoring surfaces

- **`/monitoring/` showed `integration-health.json` with no staleness rule.**
  `updateIntegrationHealth()` printed `overall_status` in the same green treatment
  regardless of the snapshot's age; the only clue was a raw absolute timestamp the
  reader had to diff by eye. If `data-contract-validation.yml` ever stopped
  running, the page would have gone on announcing "Overall: OK · 0 fail · 0 warn"
  indefinitely. The page already had the right idiom — `HEALTH_STALE_AFTER_HOURS`
  + a `STALE`/`CURRENT` badge, used by `updateRecentChecks()` — it just was not
  applied here. **FIXED:** added `INTEGRATION_STALE_AFTER_HOURS = 48` (two missed
  daily runs), a STALE banner, a spelled-out age, and dimming of the check rows.

  The reason this needs a *wider* threshold than the cron interval: the workflow
  commits the artefact as `github-actions[bot]`, and **bot commits do not trigger
  the deploy**. So the copy the page fetches is refreshed not when the workflow
  runs but on the next *human* push. Repo-fresh and site-fresh are different
  things here, and only the second is what a visitor sees.

  Not fixed, and worth a decision: the general form of this is that every
  bot-committed artefact under `public/` is served at human-push cadence. A deploy
  key / PAT or a `workflow_run` trigger (CLAUDE.md "Deploy") would close it for all
  of them at once.

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
