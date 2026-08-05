# Tech debt register — pdoom1-website

Captured 2026-07-22 from five parallel audits (analytics, technical correctness,
ambition debt, design system, feedback channels) and the fix agents that
followed. Each item has evidence, not a vibe.

**Status key:** `OPEN` · `PARTLY DONE` (name which half shipped and what remains) ·
`PARKED` (deliberate, revisit trigger noted) · `NEEDS-PIP` (only he can do it —
credentials, DNS, a product call) · `DONE`/`FIXED`/`CLOSED`/`RESOLVED` (kept, not
deleted, with the command that proved it).

Ordered by "what does a visitor or player actually suffer", not by how annoying
it is to a developer.

**Truth pass 2026-08-06.** Every row below was re-verified against `origin/main`
and, where the claim is about what a visitor sees, against **production**. A
register that is wrong about its own contents is worse than none, and this one
had drifted: several rows marked `OPEN` had shipped, and several rows carried a
*correct* status resting on a *stale reason*. Both classes are corrected here,
each with the command and its output. **`PARTLY DONE` is used deliberately** —
three rows shipped for the ~1,194 generated event pages and not for the 1,000
unmanaged `alignmentforum_*` orphans (§E-0), and calling that DONE would be the
same lie in the other direction.

---

## A. Actively wrong to a visitor or player

| # | Item | Evidence | Effort | Status |
|---|---|---|---|---|
| A1 | **No Plausible backups.** Single DreamCompute VPS, no snapshots, no `pg_dump`, no ClickHouse `BACKUP DATABASE`, nothing offsite. The multi-year history Pip wants to animate is one incident from permanent loss. **The two artefacts are different things and must not be conflated:** (1) the **hedge** — `snapshot-analytics.yml` committing daily *aggregate summaries* to git — is **live and healthy**; (2) the **restorable database backup** — a `pg_dump`/`BACKUP DATABASE` that could rebuild the instance — **does not exist**. Summaries cannot be restored into Plausible; losing the VPS still loses every per-day breakdown the API was never asked for. **CORRECTED 2026-08-06: the stated target of 2026-08-05 has passed with nothing shipped.** No new target set — Pip's call. | Re-run 2026-08-06: `grep -rn "pg_dump\|BACKUP DATABASE" scripts/ ansible/ .github/` → **one hit, and it is a comment**: `.github/workflows/snapshot-analytics.yml:10` explaining that neither exists. `docs/analytics/SELF_HOSTED_PLAUSIBLE.md:509` still lists "create monthly backup script" as never done. | 3-5h + a restore drill | **NEEDS-PIP** |
| A1b | **The git hedge cannot reach history older than 2026-06-23.** Daily snapshots use `--period 30d` and the first ran 2026-07-23, so everything before that window exists only on the VPS — exactly the multi-year history Pip wants to animate. `scripts/snapshot-plausible.py --range START:END` exists to backfill it but is **unverified against the live API** (custom-period params were written from the docs, not exercised), and needs a dispatch run with the secret. **Re-verified 2026-08-06 — still OPEN, and the hedge itself is healthy:** 14 consecutive daily snapshots, `2026-07-23` → `2026-08-05`, **no gaps**, every one `period=30d`. So no backfill has ever run, and the archive's floor is still frozen at 2026-06-23. | 2026-08-06: `ls public/data/analytics/history/` → 14 files, first `2026-07-23.json`, last `2026-08-05.json`. Reading each file's `sections.timeseries.results`: first→last date ranges step forward exactly one day per file, `2026-06-23→2026-07-22` … `2026-07-06→2026-08-04`. **No file carries a custom range**, which is what a backfill run would look like. | ~0.5h (one dispatch + check the file) | OPEN |
| A2 | ~~**`api.pdoom1.com` has no valid TLS cert** — `curl` returns `000`.~~ **RESOLVED — this row was stale.** The handshake now completes against the system trust store with **no `-k`**, and the host answers deliberately. It still resolves to the same VPS (`208.113.200.215`), and it is now the **live score API host**: `GET https://api.pdoom1.com/score_api.php?seed=weekly-2026-w31&version=L3&limit=3` → **200**. The bare root `/` returns a deliberate **410 Gone** carrying its own explanation, which is a retirement notice, not a failure. | 2026-08-06, all over TLS with cert validation on: `curl -sS -o /dev/null -w '%{http_code}' https://api.pdoom1.com/` → **410** (exit 0; identical with `-k`, so the cert verifies). `curl -sv …` → `HTTP/1.1 410 Gone`, `Server: nginx/1.24.0 (Ubuntu)`. Body: `This API was retired on 2026-08-03. The score API is at /score_api.php`. `curl -sS -o /dev/null -w '%{http_code}' 'https://api.pdoom1.com/score_api.php?seed=weekly-2026-w31&version=L3&limit=3'` → **200**. `nslookup api.pdoom1.com` → `208.113.200.215`. | — | **RESOLVED 2026-08-06** |
| A3 | ~~**DNT is honoured on 4 pages out of 2,226.**~~ **PARTLY DONE — the generator half shipped, the hand-written half did not.** `assets/js/analytics.js` (the consent shim that owns `localStorage.plausible_ignore`) is now on **1,198 of 2,246** pages, up from 4. The fix went into the event template and re-emitted, exactly as this row prescribed: **1,194 of 2,197** `/events/` pages carry it. **What remains is two disjoint gaps.** (a) The **1,000 `alignmentforum_*` orphans** (§E-0) — nothing regenerates them, so no template edit can reach them; they load Plausible and no shim. (b) **45 hand-written pages** still at the original four — including `/dashboard/`, `/leaderboard/`, `/game-changelog/`, `/issues/`, `/resources/`, `/state-of-doom/`, `/blog/`, `/docs/` and all 19 `/design-notes/` pages. **The four pages that had the shim in the original finding are still the only non-event pages that have it**: `index`, `about`, `press`, `privacy`. | 2026-08-06, repo: every `*.html` under `public/` loads the Plausible tag (2,246/2,246); 1,198 also load the shim; 1,048 do not. Production confirms both sides: `curl https://pdoom1.com/events/arxiv_004aec5c84faaf31.html` → 2 hits for `assets/js/analytics.js`; `curl https://pdoom1.com/events/alignmentforum_00671cab97bcd7dc.html` → **0** hits (and that page does load the tracker). | 0.5h for the 45 hand-written pages; the 1,000 orphans are §E-0's decision | **PARTLY DONE** |
| A4 | ~~**`generate_game_aware_sample_data()` drops `data_status`.**~~ **FIXED** in `52942224` (#190). The fallback now returns `"data_status": "pre-launch"` explicitly, with the reason written beside it: *"Without this the leaderboard page had no status to read. It defaulted the absent field to 'live', so a FAILED EXPORT published itself as a real, empty competitive board."* The same commit stopped the function freezing a version literal — it reads `deployed_game_version(self.website_dir)`. | 2026-08-06: `scripts/game-integration.py:310` → `"data_status": "pre-launch"`. `git log -S'"data_status": "pre-launch"' -- scripts/game-integration.py` → `52942224 fix(leaderboard): make board-key loss loud … (#190)`. | done | **FIXED (#190)** |
| A5 | ~~**3.78 MB cat PNG** on `/dashboard/`, in the initial desktop viewport.~~ Fixed in `faa3ff7e` before this row was re-read: the PNG became `pdoom1-office-cat-default.webp`, 960x900, **55,840 bytes** (-98.5%), and `dashboard/index.html:987` points at it. Live: `curl -sI pdoom1.com/assets/pdoom1-office-cat-default.webp` returns 200 / 55,840. `small-doom-cat.png` remains a different cat and was not substituted. | `public/assets/pdoom1-office-cat-default.webp`. **Re-verified on production 2026-08-06:** `curl -sI https://pdoom1.com/assets/pdoom1-office-cat-default.webp` → `200`, `Content-Length: 55840`. | done | **DONE** |
| A6 | **Corrected dashboard prose is invisible.** `loadEventLog()` replaced all of `#narrativeBox` with the last 3 changelog entries on load, so the re-dated "Situation Analysis" showed for a moment and was gone. | `public/dashboard/index.html:926` (`#narrativeBox`), `:937-940` (the comment forbidding a write to `#narrativeBox`, plus `<div id="devLog">`). **Re-verified 2026-08-06** and the box has since been hardened well past this row: `node scripts/test-dashboard-devlog.js` → `OK: the dashboard development log derives from version.json + the releases API, refuses to present anything older than 90 days (or undated) as recent, and renders hostile upstream fields as inert text.` See CLAUDE.md "Changelog surfaces" — `/dashboard/` is the **fourth** release surface and had been rendering v0.4.1 as "Recent". | 0.5h | **FIXED** — the dev log now renders into its own `#devLog` child appended below the analysis; a failed/empty fetch leaves both the analysis and `#devLog` untouched. No prose changed. |
| A7 | ~~**No favicon anywhere.**~~ **RESOLVED — this row was stale.** Both `public/favicon.ico` and `public/favicon.svg` now exist. Re-verified 2026-07-28. Only **6 of 2,245** pages *declare* a `rel="…icon"` link — but that no longer matters to a visitor, because browsers fall back to `/favicon.ico` at the root and that file now exists, so every page resolves an icon. The declaration gap is now cosmetic (2,239 pages get the 192-byte `.ico` rather than the `.svg`). Not worth 0.5h; fold into the event-template work if ever. | `ls public/favicon*` → `.ico` (192 B) + `.svg` (350 B); `grep -rl 'rel="[^"]*icon' public --include=*.html` → 6. **Re-verified 2026-08-06: unchanged — still 6 declarations, now out of 2,246 pages, and both files are still on disk at the same sizes.** | — | **CLOSED 2026-07-28** (re-verified 2026-08-06) |
| A8 | ~~**`robots.txt` blocks `/data/`, `/design/`, `/stats/`.**~~ **PARTLY DONE — the visitor-harming two-thirds shipped; the third is a deliberate hold.** The `Disallow` lines for **`/data/` and `/design/` are gone**, and the file now carries a nine-line comment explaining *why* they must not come back (they are runtime subresources; blocking them made Googlebot render the hardcoded fallbacks). That closes the part of this row that made the crawler see a false version number. **`/stats/` is still disallowed, on purpose:** `robots.txt` records that `stats/index.html` and `stats/competition.html` carry **no** `noindex` tag, so removing the `Disallow` would expose two pages whose retire-or-keep decision is open, and adding a `noindex` would pre-empt that decision. That is Pip's call, not a fix. | 2026-08-06, **production**: `curl https://pdoom1.com/robots.txt \| grep -i '^Disallow'` → `/.netlify/`, `/api/`, `/assets/private/`, `/monitoring/`, `/league/`, `/players/`, `/dev-notes/`, `/stats/`. **No `/data/`, no `/design/`.** Matches `public/robots.txt` in the repo. | remaining: a product call on `/stats/` | **PARTLY DONE** → remainder is **NEEDS-PIP** |
| A9 | **Weekly-league rollover is off by one week** — and anchored to the wrong day. The cron fired Sunday 14:00 UTC and `get_current_week_info()` derived the week from `now`, so it created the week that *ends* 10 hours later. `validate_data.py` confirms: "week 2026_W29 is marked is_current but ended 2.4 days ago". 10 weeks of green checkmarks, all wrong; this is the #126 false positive, proven. Separately, the Monday→Sunday **UTC** week was two days out of phase with `pdoom1/docs/RELEASE_NOMENCLATURE.md` ("Seed — every Fri"). | `scripts/weekly-league-manager.py`, `weekly-league-reset.yml` | 0.5h | **FIXED 2026-07-28; anchor corrected 2026-07-29.** The week now runs **Friday 00:00 → Thursday 23:59:59 `Australia/Hobart`** (cron `0 14 * * 4`, resolved via `ZoneInfo` — never a fixed offset, because Hobart is +10/+11 across DST; `tzdata` pinned in `requirements.txt` since Windows ships no tz database). The run-time → week mapping is explicit (`league_week_start()`) and the old look-ahead is gone: the cron fires inside the week it opens. Pinned by `scripts/test-weekly-league-boundary.py` (**99** assertions as of a 2026-08-06 re-run — `PASSED: 99/99 checks`; this row said 93 and CLAUDE.md says 74, so **read the test's own output rather than either number**), covering both DST states, which runs as the **first** step of the rollover workflow so a regression fails the rollover instead of publishing a wrong week. The ten wrong weeks are kept and labelled — see `docs/LEAGUE_EPOCH_ANOMALY.md`. The epoch boundary is `public/data/ladder-epochs.json`, not a script literal. |

---

## B. Structural — cheap now, expensive later

| # | Item | Evidence | Effort | Status |
|---|---|---|---|---|
| B1 | **Nav drift: ten distinct variants.** Mostly closed 2026-07-28. 21 of 25 hand-written pages now delegate to `navigation.js`; the test went 0/25 → 15/25 overall and **22/25 on the nav contract itself**. `public/includes/navigation.html` (wired into zero pages, hardcoding a stale `v0.11.0`) was deleted, and `docs/HTML_PAGE_TEMPLATE.md` — which instructed authors to hand-copy nav markup, i.e. the mechanism that produced the ten variants — was rewritten. **CORRECTED 2026-08-06: three static navs remain, not four.** `index.html` joined the spine (see B1a) — the survivors are `events/index.html` (generated by `sync-events.py`), `league/`, `players/`, and all three are owned elsewhere. Regime split is now **delegate=22, delegate(+fallback)=2, static=3** across 27 files. | 2026-08-06: `node scripts/test-header-consistency.js` → `Nav regimes: delegate=22 delegate(+fallback)=2 static=3`; `Header/nav contract: 24/27`; `Emoji-free: 20/27`; `SUMMARY: 19/27`. The 3 static are `events\index.html`, `league\index.html`, `players\index.html`. | ~3h left | **PARTLY DONE** |
| B1a | ~~**Homepage nav divergence needs a product call before `index.html` can join the spine.**~~ **DONE — Pip ruled 2026-07-31: converge.** Landed in `160f0698` (#212). Both halves of the question were answered rather than papered over: **Events was added to the shared nav** (Info dropdown, labelled *"AI Safety Timeline"*) instead of being dropped, because `public/index.html` was the ONLY non-events page linking `/events/` and pure convergence would have orphaned ~2,197 pages; and **Press Kit now shows on the homepage** like everywhere else. The same commit moved the Roadmap link off `/docs/roadmap.md` (a download) onto `/docs/roadmap/`, and handed the version badge to `navigation.js` alone — the homepage had been writing it to `#versionInfo`, an id the injected nav does not have. | 2026-08-06: `public/index.html:855` is a bare `<header>`; `public/assets/js/navigation.js:49` → `<a href="/events/">AI Safety Timeline</a>`, `:52` → `<a href="/press/">Press Kit</a>`. `test-header-consistency.js` classifies `index.html` as `delegate(+fallback)`. | done | **DONE (#212)** |
| B1b | **The injected nav does not render with JS disabled.** **CORRECTED 2026-08-06: 2 of the 24 delegating pages now carry the fallback, not 1 — and the count of pages still exposed is 22, not 20.** `public/design-notes/index.html` was the reference pattern and `public/index.html` adopted it in #212 (the front door specifically should not be a blank header with JS off). The fix is a small `<nav>` in the `<header>` *without* `.nav-links`, which `navigation.js` overwrites when it runs. The other 22 render **nothing at all** with JS off. Adding it is a per-page prose addition, so it is still flagged rather than done. | 2026-08-06: `node scripts/test-header-consistency.js` → `delegate=22 delegate(+fallback)=2`. `public/assets/js/navigation.js`, `public/design-notes/index.html`, `public/index.html`. | 1h + copy review | OPEN |
| B2 | **Hand-written pages not tokenised.** **CORRECTED 2026-08-06 — every number in the original row is stale, and the debt has GROWN, not shrunk.** Re-measured across all non-event pages (plus `events/index.html`, which is hand-shaped): **50 pages, 243,892 bytes = 238.2 KB of inline `<style>`**, median **3,117 B**, max **16,616 B** (`index.html`, unchanged as the worst). Was "29 pages, 147 KB, median 5.3 KB". The median fell while the total rose by 91 KB, i.e. the growth is **more pages**, not fatter ones — new hand-written surfaces (`/docs/roadmap/`, `/metabolism/`, `/frontier-labs/`, `/state-of-doom/`, the 19 `/design-notes/` pages) each arrived carrying their own copy. The ~2,197 generated pages still move with one template edit; this long tail still does not. The original lesson stands and is now better supported: nav adoption (B1) clawed back a **measured 1,975 bytes** across the 9 converted pages (−1,521 B on disk once script tags and comments are counted) — a rounding error against 238 KB. Two commit messages on `infra/nav-spine` quoted larger figures (−1.4 KB, −3.2 KB) before the measurement was run; the numbers here are the measured ones. | 2026-08-06: sum of `<style>…</style>` bodies over every `public/**/*.html` except generated `events/*`. Top five: `index.html` 16,616 · `dashboard/index.html` 15,763 · `leaderboard/index.html` 14,127 · `league/archive.html` 10,934 · `league/index.html` 10,613. | ~15h+ | OPEN |
| B3 | ~~**Sitemap covers 15 URLs of 2,244.**~~ **DONE.** `generate-sitemap.js` no longer carries a hardcoded `routes` array — it enumerates the real pages under `public/`, **parses `robots.txt`** rather than duplicating it (so a sitemap can never advertise a disallowed URL), honours `<meta name="robots" content="noindex">`, excludes non-page fragments, and takes `lastmod` from git — **omitting the element rather than fabricating today's date** when git cannot supply one. All 2,197 event pages are now listed. | 2026-08-06, repo: `grep -c '<loc>' public/sitemap.xml` → **2,247**, of which **2,197** are `/events/`. **Production:** `curl https://pdoom1.com/sitemap.xml \| grep -c '<loc>'` → **2,249** (prod is one sync ahead of this branch's checkout; both far past 15). `curl -sI https://pdoom1.com/sitemap.xml` → `200`, 279,921 B. | done | **DONE** |
| B4 | ~~**OpenGraph coverage ~1.5%.**~~ **PARTLY DONE — same split as A3, same cause.** `og:title` is now on **1,229 of 2,246** pages (was 34) and `og:image` on **1,211** (was 17). The event template carries them: **1,129 of 1,129** `arxiv_*` pages have `og:title`. **What remains: the 1,000 `alignmentforum_*` orphans have ZERO** — no `og:title`, no `og:image` — because nothing regenerates them (§E-0); plus **14 of the 49 hand-written pages** still lack `og:title`. So ~45% of the site still shares as a bare URL, and the fix for the bulk of it is §E-0's decision, not a template edit. | 2026-08-06, repo: `grep -rl og:title public --include=*.html \| wc -l` → 1,229; same for `og:image` → 1,211; `grep -l og:title public/events/alignmentforum_*.html \| wc -l` → **0** of 1,000; non-event pages with `og:title` → 35 of 49. **Production:** `curl https://pdoom1.com/events/arxiv_004aec5c84faaf31.html` → 1 × `og:title`; `curl https://pdoom1.com/events/alignmentforum_00671cab97bcd7dc.html` → **0** (page returns 200). | 0.25h for the 14 hand-written; the 1,000 are §E-0 | **PARTLY DONE** |
| B5 | ~~**`og:image` is 2.49 MB**~~ Two passes. `3aa21ba6` moved all 17 `og:image` tags off the 2,611,379-byte `pdoom_logo_1.png` onto `og-card.jpg` (235,016 B) — but kept the source's **1024x1536 portrait** shape, and every page declares `twitter:card=summary_large_image` (~1.91:1), so scrapers centre-cropped to the cat's chest and cut the laser eyes out of frame. `og-card.jpg` is now a deliberate **1200x630** crop, **93,595 bytes**, regenerated by `scripts/make-og-card.py` (`--check` asserts shape + a 300 KB budget). Same filename, so no page needed editing and no third variant exists. Closes #16. `pdoom_logo_1.png` stays: `/press/` links it as the press-kit logo download. | `scripts/make-og-card.py`. **Re-verified on production 2026-08-06:** `curl -sI https://pdoom1.com/assets/og-card.jpg` → `200`, `Content-Length: 93595`. | done | **DONE** |
| B6 | **~34 MB of source material is rsynced to production.** Now excluded by `deploy-excludes.txt`, shared by all four workflows that rsync `public/` to DreamHost — previously only `auto-deploy-on-push.yml` had excludes, so dispatching any of the other three re-uploaded everything. Measured: `assets/dump` 11,152,471 B (12 files), `assets/image-processing-systems` 11,615,856 B (132), `assets/screenshots/*.png` 9,184,720 B (4 masters, every on-site screenshot is a derived `-web.jpg`/`.webp`/`hero-bg-*` variant), `8-bit-effect.gif` 1,656,220 B. All verified referenced by zero deployed html/css/js. `scripts/check-deploy-excludes.py` re-verifies both invariants on demand. **Caveat: `--delete` PROTECTS excluded paths, so the copies already on the server stay fetchable** (`curl -so/dev/null -w '%{size_download}' pdoom1.com/assets/8-bit-effect.gif` → 1656220 as of 2026-07-28). Reclaiming those needs one manual `rm` — command is in the workflow comment. **RE-VERIFIED 2026-08-06: the caveat is STILL TRUE and the `rm` has not happened.** Now also tracked as **#246**, which *upgrades* the severity: this is no longer only a payload problem. The excluded trees include **third parties' names inside publicly-fetchable filenames**, so what is still on the server is a privacy exposure, not just 34 MB of waste. Read #246 before scheduling the `rm`; do not duplicate its detail here. | `deploy-excludes.txt` (also now excludes `public/_review/`, internal decision packs that live inside the deploy root). **Production, 2026-08-06:** `curl -so /dev/null -w '%{size_download}' https://pdoom1.com/assets/8-bit-effect.gif` → **1656220** (HTTP 200) — byte-identical to the 2026-07-28 measurement, i.e. nothing has been reclaimed in nine days. | done (+1 manual `rm`) | **NEEDS-PIP** (the one-off `rm`) — tracked as **#246** |
| B7 | ~~**`data/events.json` is 1.18 MB, uncompressed**~~ `public/.htaccess` (landed `43c41b4c`) carries `AddOutputFilterByType DEFLATE application/json`. Verified live 2026-07-28: `Content-Encoding: gzip`, **1,198,304 → 164,755 bytes on the wire (-86.2%)**, plus `Cache-Control: max-age=300` from the `mod_expires` block and the three security headers. **Re-verified on production 2026-08-06: still true — 1,198,188 → 164,177 bytes (-86.3%).** | `public/.htaccess`. **Measuring trap, worth recording: bare `curl -sI` sends no `Accept-Encoding`, so it returns the uncompressed `Content-Length` and NO `Content-Encoding` header — which reads exactly like "compression is broken".** Use `curl -sI --compressed` (→ `Content-Encoding: gzip`) and `curl -sS --compressed -o /dev/null -w '%{size_download}'` (→ 164177) before concluding this row has regressed. | done | **DONE** |
| B8 | **Nav links to a raw `.md` file** (`/docs/roadmap.md`). Confirmed by measurement, not inference: `curl -I` returned `Content-Type: text/markdown`, which no browser renders, so "Roadmap" downloaded a file. All 5 `.md` routes fixed at the server on 2026-07-28 — `AddType text/plain .md` in `public/.htaccess` re-types them so they render, without touching any `.md` file or forking content into an HTML copy. **Verify after deploy:** `curl -I https://pdoom1.com/docs/roadmap.md` should say `text/plain` (Netlify previews ignore `.htaccess`, so the PR preview cannot show this). **That verification was performed 2026-08-06 and passes.** | `public/.htaccess`, `public/assets/js/navigation.js`. **Production 2026-08-06:** `curl -sI https://pdoom1.com/docs/roadmap.md` → `HTTP/1.1 200 OK`, `Content-Type: text/plain; charset=utf-8`. **Also fixed since: the nav no longer points here at all** — `navigation.js:50` links `/docs/roadmap/`, the rendered page (#212). | done | **DONE (floor)** — production-verified 2026-08-06 |
| B8a | **Four `/docs/*.md` routes still have no rendered surface** and are linked as raw markdown from `/docs/`. A reader who clicks them gets `##` and pipe tables as plain text. **CORRECTED 2026-08-06 — THE STATED REASON WAS FALSE, and the row is narrower than it was.** It claimed *"The proper fix is an HTML surface that renders markdown — which does not exist"*, and justified that with *"`/blog/post.html`'s parser handles links, images, inline code, bold and italic only (no headings, no tables, no fenced code)"*. **Both halves are now wrong.** (1) The blog parser was replaced in `cf38e315`: headings, fenced code, lists, blockquotes and `hr` had worked for months, and **pipe tables landed 2026-08-03**. See CLAUDE.md "Blog & feeds" — and prefer `scripts/test-blog-render.js` over any prose claim about that parser, in either direction. (2) A rendering surface **does** exist and is live: **`/docs/roadmap/`** fetches `/docs/roadmap.md` at runtime and renders it, deliberately holding **no copy of its own** so it cannot drift from the markdown (which is itself a projection of the game repo's `ROADMAP.md`). `scripts/test-roadmap-render.js` pins the parser against the actual file and asserts the two honesty properties — no hardcoded game version, and every forward-looking Theme row marked provisional. **What is actually left**, and why the row stays open: `roadmap.md` got a bespoke page, and the pattern was not generalised. `/docs/index.html` still links **four** `.md` files directly — `DEV_NOTES.md` (:66, :165), `pdoom1-open-issues.md` (:70, :167), `steam-readiness.md` (:78), `how-leaderboards-work.md` (:120). The remaining work is therefore *generalise the roadmap surface to a parameterised `/docs/<name>/` renderer*, not *invent a renderer*. | 2026-08-06: `public/docs/roadmap/index.html` exists (11,477 B); `curl -sI https://pdoom1.com/docs/roadmap/` → `200`, `Content-Type: text/html`. `grep -n '\.md"' public/docs/index.html` → the four routes above still linked raw. `scripts/test-roadmap-render.js`, `scripts/test-blog-render.js`. | 1-2h (was 2-4h — the renderer no longer has to be written) | OPEN |
| B9 | **Duplicate DOM id on the leaderboard.** `cards-view` was on both a button (`:746`) and a div (`:774`); `getElementById` returned the button, so card rendering targeted the wrong node — and `setViewMode('table')` set `display:none` on the Cards button itself, hiding the toggle. | `public/leaderboard/index.html`. **Re-verified 2026-08-06:** `:785` `id="view-btn-table"`, `:786` `id="view-btn-cards"`, `:814` `<div id="cards-view">` — the id appears on exactly one element, and `:1315-1316` read the buttons by their new ids. The page also carries a comment at `:782` recording why. | 0.25h | **FIXED** — toggles renamed `view-btn-table` / `view-btn-cards`; the containers keep their ids. Page now has zero duplicate ids. |
| B10 | **Markdown sprawl in `docs/`** — five files on syndication, five on analytics, five session summaries from one day. They describe the *intended* system, so every new agent rediscovers the same gaps. This is the mechanism that generates ambition debt. **CORRECTED 2026-08-06: the count is now 144, not 123** — 21 files added in fifteen days, so this row is getting worse at roughly 1.4 files/day while sitting at `OPEN`. | 2026-08-06: `find docs -name '*.md' \| wc -l` → **144** (was 123 on 2026-07-22). | 2-4h prune | OPEN |
| B11 | **`deploy.yml` and `update-stats.yml` were self-declared no-ops** created by the (now deleted) `bootstrap.sh` (`f602822f`). The "fail on every run" note was itself stale: `bootstrap.sh` emitted them with literal `\n` instead of newlines (`deploy.yml` was one unparseable line; `update-stats.yml` was empty), so both failed in 0s on every push until `7026e814` rewrote them as valid `workflow_dispatch`-only no-ops. Neither has run since **2025-09-09**. | their own `run:` lines. **Re-verified 2026-08-06:** neither `deploy.yml` nor `update-stats.yml` exists under `.github/workflows/`. | 0.1h | **FIXED (deleted)** — see note below |

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
| C1 | **Committed credentials** in `docker-compose.yml`: `POSTGRES_PASSWORD: nodebb123`, `ADMIN_PASSWORD: ChangeThisPassword123!`, a 64-hex `SECRET` — for a box that is genuinely running and reachable. In git history, so rotation is the only fix. **Re-verified 2026-08-06: unchanged, all four literals still present.** | `docker-compose.yml:11,35` (`POSTGRES_PASSWORD: nodebb123`), `:44` (`ADMIN_PASSWORD: ChangeThisPassword123!`), `:47` (64-hex `SECRET`). | 1h | **NEEDS-PIP** |
| C2 | **Score-API token ships in the public build** (`godot/data/leaderboard_config.json`), acknowledged in its own `_comment`. Accepted for a friends-and-family alpha; needs server-side rate limiting and a rotation plan before wider release. **2026-08-06: NOT re-verifiable from this repo** — the file lives in the game repo and no local `pdoom1` checkout is available here, so treat the current state as **unknown**, not as unchanged. What *is* observable from here is consistent with the row: `https://api.pdoom1.com/score_api.php` answers unauthenticated `GET`s (see A2), and CLAUDE.md records that it validates no key. | game repo | — | **PARKED** until wider release |
| C3 | ~~**"GDPR Compliant / fully compliant by design"** on `/privacy/`.~~ **DONE — softened exactly as this row recommended.** The bare legal claim is gone; the page now makes a **factual** statement about mechanism instead of a conclusion about compliance: *"Built to satisfy GDPR, CCPA and PECR by collecting no personal data and setting no cookies"*, with the reasoning spelled out below it (*"…names, emails, IP addresses or cross-session identifiers — so most of what GDPR…"*). That is a claim about what the site does, which is checkable, rather than a claim about a legal outcome, which is not. | 2026-08-06, **production**: `curl https://pdoom1.com/privacy/ \| grep -oiE 'fully compliant\|GDPR Compliant\|Built to satisfy GDPR[^<]*'` → returns **only** `Built to satisfy GDPR, CCPA and PECR by collecting no personal data and setting no cookies`. Repo-wide `grep -rn "fully compliant\|GDPR Compliant" public/` → **no matches**. | done | **DONE** |
| C4 | **Country-level geolocation claim is unverified.** Disclosed on the privacy page erring toward over-disclosure, on the strength of the repo's own docs listing "Countries" as a dashboard metric. If geolocation is actually off on that instance, the bullet should go. **Re-verified 2026-08-06: unchanged and still unverifiable from this repo** — the claim is live at `public/privacy/index.html:307` (*"Approximate location: Country level, worked out from your IP address at the moment of the request (the IP itself is never stored)"*), and confirming it still needs a Plausible dashboard login nobody here has. **Partial counter-evidence, not proof:** every committed analytics snapshot carries a `sections.countries` block, so the *API* is being asked for country data — which is consistent with geolocation being on, but does not establish that the instance resolves anything. | `docs/analytics/SELF_HOSTED_PLAUSIBLE.md:496`; `public/data/analytics/history/*.json` → `sections` keys include `countries`. | 0.1h | **NEEDS-PIP** (dashboard login) |
| C5 | **`/issues/` form still emails a free-text contact field** to `team@pdoom1.com` via `mailto:`. Less bad than the bug form was (that pasted addresses into public GitHub issues, now removed), but still uncovered by the "we never collect PII" framing. **Re-verified 2026-08-06: unchanged.** The handler still reads `contact-method` into `formData.contact`, still splices it into the mail body as `**Contact:** …` when it is not `Anonymous`, and still hands the visitor a `mailto:team@pdoom1.com?subject=…&body=…` link. The `// TODO: Replace with actual Netlify Function or backend endpoint` is still there. | `public/issues/index.html:489` (the address), `:683` (`contact: … \|\| 'Anonymous'`), `:705` (`**Contact:**` in the body), `:716` (the `mailto:`). | 0.5h | OPEN |

---

## D. Wanted features (not debt, but captured here so they aren't lost)

| # | Item | Notes |
|---|---|---|
| D1 | **Privacy-first opt-in subscribe** — dev-blog updates, playtest invites. Pip's explicit want. **The first step is DONE (2026-08-06 verification).** The `mailto:`-only homepage newsletter form — which captured nothing — has been **removed** and replaced by an honest follow-along block: `public/index.html:1248` `<h3>[Feed] Follow along</h3>`, offering `/blog/feed.xml` (RSS) and `/blog/atom.xml` (Atom), plus a `<link rel="alternate" type="application/rss+xml">` at `:10` so a reader's browser or feed client discovers it automatically. `:1482` carries the removal note: *"(newsletter mailto form removed — replaced by the honest RSS/GitHub follow-along block)"*. **Still open, and deliberately so:** no opt-in email list exists, and per this row that should only be built if RSS proves insufficient. **`mailto:team@pdoom1.com` survives at `:1301` as "Email Support"** — a support contact, not a subscribe mechanism, so it is not the thing this row objected to. |
| D2 | ~~**RSS/Atom feed for `public/blog/`.**~~ **DONE.** `scripts/generate-feeds.py` emits both from `index.json`, and `generate-feeds.yml` keeps them current and verifies them on PRs. Verified on **production** 2026-08-06: `curl -sS -o /dev/null -w '%{http_code} %{size_download}' https://pdoom1.com/blog/feed.xml` → `200 10368`. Both `public/blog/feed.xml` and `public/blog/atom.xml` are committed. **Note the path** — they are under `/blog/`, not at the site root, so `public/feed.xml` does not exist and a check that looks there will wrongly report this undone. |
| D3 | **In-game update check** — filed as pdoom1#799. The actual answer to "how do I reach players who have an old build". No personal data required. **2026-08-06: state UNKNOWN.** This lives entirely in the game repo; nothing in this repo observes it, and no local `pdoom1` checkout was available to check. Do not read the absence of an update here as "not done". |
| D4 | **Plausible Stats API → committed JSON snapshots** in `public/data/analytics/`. **DONE** — the key was created 2026-07-23 and `snapshot-analytics.yml` has committed daily since. Hardened 2026-07-29 so a missing key, a failed fetch or an all-zero response fails the run and writes nothing, instead of committing a plausible-looking empty file. **Re-verified 2026-08-06: 14 daily files, `2026-07-23` → `2026-08-05`, no gaps** (plus `latest.json`, `annotations.json`, `README.md`). Remaining gap is A1b (backfill) and A1 proper (a restorable database backup, not summaries) — **those are two different artefacts and this row is neither of them**. |
| D5 | **ADR + DQ practice for this repo.** Pip wants the same decision-record discipline the game repo has (17 ADRs, 38 DQs, a generated index with a pre-commit staleness check). The game's `scripts/generate_dq_index.py` is a working model to copy. **STARTED, not done (2026-08-06):** `docs/decisions/` now exists and holds **exactly one** record, `ADR-0001-inbound-automated-outbound-gated.md`. There is no DQ series, no generated index, and no staleness check — which is the half that makes the practice self-sustaining rather than a folder someone stopped adding to. |

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

**Updated 2026-08-06 (truth pass).** All three of the "only Pip can do" items
listed above are now resolved: `PLAUSIBLE_API_KEY` is set and has produced 14
consecutive daily snapshots (D4); the homepage newsletter `mailto:` form is gone
and replaced by an RSS + GitHub follow-along block (D1); and both images are
downscaled and production-verified (A5, B5). **The single manual `rm` is still
outstanding and is now the whole of this section** — re-measured on production
today, `assets/8-bit-effect.gif` still returns 1,656,220 bytes. It has also
grown a second, worse justification since this was written: see B6 and **#246**,
which is about third parties' names in publicly-fetchable filenames, not about
payload size.

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

  **Re-run 2026-08-06 — the fix is holding, and holding for the right reason.**
  `python scripts/test_ingest_scores.py` → `PASS: live/pre-launch/legacy paths,
  ADR-0002 sort + tiebreak, test-seed exclusion, version stamp pinned to v0.13.2
  (all fixtures built in temp dirs -- no live-data dependency)`. Note the
  **`v0.13.2`** in that line: it is *read from `version.json` at run time*, not
  typed into the test. Two releases have shipped since the fix and the test tracked
  them instead of rotting — which is exactly the property the old `v0.11.0` literal
  lacked. If that string ever stops moving with the deployed version, the literal
  has crept back in.

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

  The original reason this needed a *wider* threshold than the cron interval was
  that the workflow commits the artefact as `github-actions[bot]`, and bot commits
  did not trigger the deploy — so the copy the page fetches refreshed not when the
  workflow ran but on the next *human* push.

  **CORRECTED 2026-08-06: that reason is stale, and the fix this section called for
  has LANDED.** `auto-deploy-on-push.yml` now carries a `workflow_run` trigger on
  `workflows: ["Board liveness (score API)"]`, `types: [completed]`,
  `branches: [main]`, so a full `rsync --delete` of `public/` fires ~4×/day
  regardless of who committed. Max staleness for a bot-committed artefact under
  `public/` is ~6 hours, not "until a human pushes". The file's own comment at
  line 15 records why. **Keep the 48-hour threshold anyway** — it is now sized
  against *two missed daily runs of the producer*, which is the right thing for it
  to measure; it was only ever incidentally about deploy cadence.

  **The risk inverted rather than disappeared, and that is the open item now.**
  `types: [completed]` has **no conclusion filter**, so the deploy fires whether
  board-liveness passed or failed, and the deploy job runs no tests — content
  honesty, escaping and data-contract failures do not block it. "It will not reach
  production until someone looks" is now **false**. Worth a decision.

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
| Nothing on the site *links* them — but they are now **advertised to crawlers** | **CORRECTED 2026-08-06.** The original evidence read *"sampled 20, no inbound references; the sitemap contains no event pages at all"*. The first half still holds, exhaustively rather than by sample: `grep -rl "alignmentforum_" public --include=*.html`, excluding the pages themselves, returns **nothing**. **The second half is now FALSE and it changes the stakes.** B3 replaced the hardcoded sitemap with an enumeration of `public/`, so `public/sitemap.xml` now carries **all 1,000** `alignmentforum` URLs (`grep -c alignmentforum public/sitemap.xml` → 1000, of 2,247 `<loc>` entries). They are unlinked, unmanaged, un-redacted-by-generator — and submitted to search engines. |

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

**New in 2026-07-29 — the unmanaged pages now carry a privacy cost, not just a
staleness cost.** `sync-events.py` gained a redaction pass that strips
third-party email addresses out of PDF-scraped descriptions (75 addresses were
being published across 44 pages). That pass protects everything generated from
`all_events.json` — and by construction cannot protect these 1,000, because
nothing regenerates them. Two of them were carrying addresses
(`alignmentforum_5cf6dbe41151b29e.html`, `alignmentforum_7154aca101dbeb10.html`)
and were scrubbed in place with `scripts/check-published-emails.py --fix`. That
is a **stopgap**: an in-place edit to a generated file, which is exactly the
thing this repo warns against, tolerable only because no generator will clobber
it. Option (a) above is the real fix — it puts these pages under the redaction
pass with everything else. Until then, `check-published-emails.py` is the only
thing standing between them and the next scraped address. **Re-run 2026-08-06:
`python scripts/check-published-emails.py` → `PASS: no third-party email
addresses published under public/`.** Note what that does and does not prove:
per CLAUDE.md it checks the **output**, so a PASS only says no leak has already
shipped — `redact_pii()` is the thing that stops one, and by construction it
cannot reach these 1,000 pages.

**New in 2026-08-06 (truth pass) — the decision has got more expensive to defer,
and half of option (a) is already written.**

- **They now inherit every site-wide fix that goes through the generator, and
  therefore miss every one of them.** Three separate rows are `PARTLY DONE`
  purely because of these 1,000 pages: **A3** (they load the Plausible tag and
  not the DNT consent shim — verified on production, `alignmentforum_*` returns
  0 hits for `assets/js/analytics.js` while `arxiv_*` returns 2), and **B4**
  (0 of 1,000 carry `og:title` or `og:image`, while 1,129 of 1,129 `arxiv_*` do).
  That is the mechanism to watch: **each future template fix will fork the corpus
  a little further**, and each will look like a partial success rather than an
  unmade decision.
- **A merge script for option (a) already exists and has never been wired to
  anything.** `scripts/sync/merge-alignment-events.py` backs up `all_events.json`,
  loads the 1,000 alignment-research events, runs duplicate detection and merges
  non-destructively. `grep -rn "merge-alignment-events" .github/workflows/ scripts/`
  finds it referenced **only from `scripts/sync/README.md`** — no workflow, no
  caller. Its README describes a post-merge world of "1028 events", which matches
  neither the 1,194 in `all_events.json` today nor 1,194 + 1,000; treat that
  number as stale documentation, not as a plan. So option (a) is *cheaper than it
  looks and less finished than that script implies* — someone still has to decide,
  then reconcile the counts.

**Also flagged upstream:** `pdoom-data/.../timeline_events/manifest.json` claims
`"total_events": 28`, which matches neither the 1,194 in `all_events.json` nor
the 1,000 in `alignment_research`. That manifest is stale and should not be
trusted by anything.

---

## E. Known-and-deliberate (do not "fix" without reading the reason)

- **`public/css/site.css` must be dark-palette-correct in every rule.** It has caused a sitewide whiteout once. The file carries a comment explaining this; keep it.
  - **CORRECTED 2026-08-06: the stated reason was wrong, though the rule it supports is right.** This bullet claimed site.css *"loads LAST on ~2,203 pages and wins the cascade"*. Measured across all 2,246 HTML files: **2,222 pages link it, and it loads after the last inline `<style>` on exactly 2** — `index.html` and `docs/index.html`. On every event page the `<link>` *precedes* the inline `<style>`, so site.css **loses** there. CLAUDE.md has carried this correction since 2026-07-22; this file did not. **Keep the rule, drop the number**: the reason to keep site.css dark-correct is that it wins on the two most-visited hand-written pages and is one page-template edit away from winning everywhere — not that it currently wins on 2,203.
- **41 weekly archive files and 15 seed leaderboards still stamped `v0.4.1`** (~159 occurrences). Left deliberately: the archives are empty shells, and the seed files contain 66 real dev-session entries from a v0.4.x pygame client. Restamping would fabricate history. `ingest_scores.py:88-95` already excludes anything whose version ≠ deployed, so none of it can reach the live board.
  - **Counts re-measured 2026-07-28** — the ruling stands, two of the numbers do not. The seed files hold **64** entries (64 distinct `entry_uuid`s), not 66; and no seed file carries a `v0.4.1` *version* stamp — their `meta.game_version` is `1.0.0`, and the `v0.4.1` strings are `economic_model`/`game_mode` values. Full breakdown, with the 80/79 split of the 159 occurrences: `docs/LEAGUE_EPOCH_ANOMALY.md`.
- **`seed_leaderboard_*.json` `meta.game_version: "1.0.0"`** is the *export tool's* version, not the game's. Mislabelled upstream; flagged, not rewritten.
- **`sync-pdoom1-docs.yml`, `extract-analytics.yml`, `sync-airtable.yml`, `post-issue-to-forum.yml`, `weekly-deployment.yml`** are all parked to manual dispatch with the reason recorded in each file's header. Read the header before re-enabling any schedule.
  - **Re-verified 2026-08-06.** Four of the five still exist and **none of them carries a `schedule:` key**, so the park is real, not just documented. **One has moved on: `post-issue-to-forum.yml` is now `post-issue-to-forum.yml.disabled`** — renamed out of the `.yml` extension, so GitHub does not parse it at all. That is a stronger park than dispatch-only and should be described as such rather than listed alongside the other four.
- **Forum (`forum.pdoom1.com` has no DNS record despite NodeBB being live on port 80)** — deprioritised by Pip: GitHub Discussions is the plan until a forum emerges naturally. Not debt; a decision. **Re-verified 2026-08-06: `nslookup forum.pdoom1.com` → `Non-existent domain`.** Note the contrast with A2: the *sibling* host `api.pdoom1.com` on the same box now resolves and serves a valid cert, so "that VPS has no TLS" is no longer a shared explanation for both.
- **`check-stale-facts.py` still reports the 4 dashboard share prices** as MEDIUM ASSERTED. They are now individually date-tagged in the markup; the detector has no "is it dated?" suppression yet. Improving that is itself a small piece of debt.
  - **Re-run 2026-08-06:** `python scripts/check-stale-facts.py` → **215 findings, 215 at or above LOW**; `--min-severity HIGH` → **215 findings, 0 at or above HIGH**, `PASS`. So the advisory/blocking split described in CLAUDE.md still holds and the gate is genuinely clean. The count has drifted from the 213 recorded there — that is expected of an advisory count and is not itself a finding; **do not treat either number as a threshold**.
