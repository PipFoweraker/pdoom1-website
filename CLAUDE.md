# pdoom1-website — repo notes for Claude Code sessions

Complements the base `d:/Local_Code/CLAUDE.md` (MAIN style guide). This file is
repo-specific operational knowledge — read it before working here to skip
rediscovery. Keep it high-signal; add gotchas that cost real time.

Deeper material lives in `docs/`:
- `docs/TECH_DEBT.md` — everything known-broken, with evidence and effort
- `docs/ALPHA_LAUNCH_RUNBOOK.md` — launch sequence and what only Pip can do
- `docs/GAME_REPO_ASKS_ALPHA.md` — what the website needs FROM the game
- `docs/copy-baseline/` — frozen prose snapshot (see "Never lie" below)

## What this repo is
- **Statically pre-rendered** site: ~2,225 HTML files. Most styling is **inline
  `<style>`** per page; shared `css/site.css` is tiny.
- **The layout spine is `public/assets/js/navigation.js`** and nothing else
  (as of 2026-07-28). 21 of the 25 hand-written pages delegate to it: an empty
  `<header></header>` in the body, `<script src="/assets/js/navigation.js">` at
  the end. It ships its own styles, scoped to `header[data-nav-injected]`, so a
  page needs no `.nav-links`/`.dropdown` rules of its own — if you see any,
  they are dead. Recipe and rationale: `public/includes/README.md`.
  - `public/includes/navigation.html` was **deleted**. It was wired into zero
    pages and hardcoded a stale `v0.11.0`. Do not recreate a second copy.
  - `docs/HTML_PAGE_TEMPLATE.md` used to tell authors to **hand-copy** the nav
    into each page. That instruction is what generated the ten variants; it now
    documents the two-line recipe. Do not re-add "copy the nav" guidance.
  - Four static navs survive on purpose, all owned elsewhere: `index.html`
    (diverges deliberately — links Events, hides Press Kit; needs a product
    call), `events/index.html` (generated), `league/`, `players/`.
  - `scripts/test-header-consistency.js` enforces it (currently 15/25 overall,
    22/25 on the nav contract; the 9 remaining failures are content emoji in
    frozen prose, not nav). It validates `navigationHTML` itself, so breaking
    the single source fails every delegating page at once.
  - **Nav does not render with JS off.** `design-notes/index.html` shows the
    intended fallback: a `<nav>` in the header *without* `.nav-links`, which
    navigation.js overwrites when it runs. TECH_DEBT B1b.

## The prime directive: never lie to a visitor
Pip's stated top priority. Practically:

- **Before changing any reader-facing prose**, know that `docs/copy-baseline/`
  holds a frozen prose snapshot from 2026-07-22. Check your impact with
  `python scripts/snapshot-copy.py --check`. Every diff you produce must be
  justifiable as "this was false, now it's true" — do NOT rewrite tone, voice or
  phrasing that is merely stylistic. Pip wants to review copy changes for drift
  in tone and in promises made to players.
- `python scripts/snapshot-copy.py --ref <commit>` extracts prose from ANY past
  commit, so history deeper than the baseline is reachable.
- `python scripts/check-stale-facts.py` finds hardcoded facts that rot. Severity
  is about whether a literal is presented as **current**, not whether it is old:
  a blog post titled "v0.6.0" is correct history; a release lookup defaulting to
  `v0.4.1` is a lie waiting for an API hiccup.
- **Fallback literals are the dangerous ones.** A default value ships precisely
  when the real lookup failed. Prefer failing loudly, or preserving the last
  known-good value, over substituting a literal.

## Cascade gotcha (cost a whole session once)
- Any rule in `site.css` MUST use the dark palette. It once held light-theme
  literals (`.card{background:#fff}`, `:root{--accent-primary:#0066cc}`) which
  whited-out cards and turned event-page accents blue.
- **CORRECTED 2026-07-22:** an earlier version of this file claimed `site.css`
  loads last on ~2,203 pages. Measured across all 2,224 HTML files, it is last
  on **2** (`public/index.html`, `public/docs/index.html`). On event pages the
  `<link>` *precedes* the inline `<style>`, so site.css loses there. Keep its
  rules dark-palette-correct anyway — but don't reason from the old number.
- **Lesson:** before concluding a visual bug "needs a live browser," grep ALL
  stylesheets in cascade order — the winning rule is usually findable statically.

## Server access (SSH) — two different hosting targets, don't confuse them
- **pdoom1.com static site** = DreamHost **shared hosting** (`173.236.253.218`).
  Deployed ONLY via the Actions rsync workflows; `DH_HOST`/`DH_USER` are GitHub
  secrets and are not readable back — recover via DreamHost Panel → Users.
- **The VPS** (`208.113.200.215`, DreamCompute) serves `analytics.pdoom1.com`
  and `api.pdoom1.com`, and runs NodeBB:
  `ssh -i ~/.ssh/pdoom-website-instance.pem ubuntu@208.113.200.215`
  Source of truth: `ansible/inventories/production.ini`. (Verified 2026-07-22.)
- **Corollary that wasted 8 months of CI:** `scripts/extract_analytics.py` reads
  nginx logs from the VPS, but pdoom1.com is on *shared hosting*. Those logs
  structurally cannot contain the site's pageviews. The workflow is parked.
- `forum.pdoom1.com` has **no DNS record** despite NodeBB being live on port 80
  of that box; `api.pdoom1.com` resolves there with **no valid TLS cert**.
- The CVTas VPS is a different machine (`208.113.128.121`) — similar key names,
  different IPs.
- Pip's cross-repo server index: `coordination/SERVER_ACCESS_REFERENCE.md` in the
  local Code folder (local-only, not in any git repo).

## Deploy
- Push to `main` → **"Auto-Deploy to DreamHost on Push"** (~20s), `rsync --delete`
  from `public/`. Deleting a file from `public/` therefore removes it from
  production on the next deploy.
- **What does NOT ship is `deploy-excludes.txt`** (repo root, `--exclude-from`).
  Source material — the cat originals, the image pipeline, the full-res
  screenshot masters — lives in git but must never be served. **Four** workflows
  rsync `public/` to DreamHost; all four now read that one file, because for a
  while only `auto-deploy-on-push.yml` had excludes and dispatching any of the
  other three re-uploaded everything it had just stopped shipping.
  `scripts/check-deploy-excludes.py` enforces both halves: every deploy uses the
  shared list, and no deployed html/css/js references a file the list drops.
  **Netlify PR previews serve `public/` whole**, so a preview can never catch a
  bad exclude — run the script.
- **An exclude is not a delete.** With `--delete`, rsync *protects* excluded
  paths on the remote, so anything a previous deploy uploaded stays live and
  publicly fetchable. Unpublishing it needs a manual `rm` over SSH.
- `public/.htaccess` carries compression, cache lifetimes and security headers
  (verified live: `events.json` 1.18 MB → 165 KB gzipped). It is a dotfile, and
  the `--exclude='.git*'` pattern does **not** match it — it does deploy.
- Use branch + PR (Pip's default). Every PR gets a Netlify **deploy-preview** —
  verify there before merge. Can't render a browser in-session, so verify by
  `curl`-ing the preview/prod asset and node-testing any JS.
- **Bot commits do not trigger deploys.** GitHub Actions will not fire a workflow
  from a push made with the default `GITHUB_TOKEN`, so anything a workflow
  commits reaches the repo but not pdoom1.com until the next human push. Affects
  every committing workflow here. Fix would be a deploy key/PAT or a
  `workflow_run` trigger.
- **Never write the skip-CI marker in a commit message — not even quoting it.**
  Several bot workflows here commit with `[` + `skip ci` + `]` in the subject, so
  it is natural to name that marker when explaining what a bot commit did. GitHub
  matches the token **anywhere in the message, including the body and inside
  backticks**, and silently runs **nothing**: on 2026-08-02 a push to a PR
  produced 3 check runs (all Netlify's) and **zero** Actions runs, with no
  skipped/queued entry anywhere in `gh run list` — which reads exactly like an
  Actions outage and cost a diagnostic cycle to tell apart. Refer to it as "the
  skip-CI marker", or name the commit SHA. Symptom to recognise: Netlify checks
  appear on the SHA and Actions checks do not exist at all (not pending, not
  skipped — absent).

## Environment / tooling
- Python is **`python`** (3.11), not `python3`. **Pillow IS installed** (12.3.0,
  verified 2026-07-22 — an older note here said otherwise).
- **Windows console is cp1252.** Any script that prints emoji dies with
  `UnicodeEncodeError` on the FIRST print, before doing any work. This is not
  cosmetic: it aborted `health-check.py` for months, and the resulting traceback
  — which names the interpreter's own `encodings/cp1252.py` — was captured into
  a published JSON file and served from pdoom1.com. **Put this at the top of any
  script that prints non-ASCII:**
  ```python
  for _s in (sys.stdout, sys.stderr):
      try: _s.reconfigure(encoding="utf-8", errors="replace")
      except (AttributeError, ValueError): pass
  ```
  **Swept repo-wide 2026-07-29** and now enforced by
  `python scripts/check-encoding-safety.py` (CI: `encoding-safety.yml`). The
  preamble is duplicated per-module on purpose, not imported from a helper —
  scripts run directly from many working directories, so an import that must
  resolve is a new way for the thing-that-runs-first to fail. Three files were
  held by concurrent branches and are listed in that script's `KNOWN_UNFIXED`.
- **The quiet half of the same bug: `open(path)` with no `encoding=`.** It
  decodes as cp1252 on Windows and utf-8 on Linux, so a UTF-8 file mojibakes
  *without raising*. On 2026-07-28 a diagnostic read a file this way, mistook a
  mangled em dash for data corruption, and produced a false bug report. This is
  worse than the print crash: it yields wrong answers rather than no answer.
  Always pass `encoding="utf-8"` to `open`, `read_text`/`write_text`, and to any
  `subprocess` call using `text=True`.
- **Your agent shell may be lying to you.** Claude Code sets
  `PYTHONIOENCODING=utf-8` and code page 65001, so the print crash does NOT
  reproduce in-session even though Pip hits it in his own terminal. Reproduce it
  with `$env:PYTHONIOENCODING="cp1252"` before concluding a script is fine.
  (`locale.getpreferredencoding()` is still cp1252 there, so the *read* side
  misbehaves in-session regardless.)
- **Encoding gremlin:** shell heredocs mangle backslashes. A `python - <<'PY'`
  block containing regex like `[^\n]` or `\d` will silently corrupt. Use the
  Write tool to create a script file and run it, or use Edit — do NOT hand-type
  escapes into a heredoc. (This bit again on 2026-07-22 despite being documented.)
- `gh issue ... --json comments` returns `comments` as a **list**, not a count.

## Workflow authoring traps (each has cost real time here)
1. **`git diff` cannot see untracked files.** A workflow that writes new files
   then tests `git diff --quiet <path>` will always report "no changes" and
   commit nothing — while reporting SUCCESS. `sync-pdoom1-docs.yml` did this
   4×/day for months. **Always `git add` first, then test `git diff --cached`.**
2. **`github.event.inputs` is EMPTY on a `schedule` trigger.** So a guard like
   `if: github.event.inputs.dry_run != 'true'` is always TRUE on a cron run.
   `weekly-deployment.yml` performed a real unattended `rsync --delete` to
   production every Friday behind a guard that read as safe. Use `inputs.x`
   (which respects declared defaults) or test the event name explicitly.
3. A failure handler needs `permissions: issues: write`, or it 403s and the
   failure is invisible. Several workflows failed silently for this reason.
4. Prefer parking a broken workflow to `workflow_dispatch` with a comment
   explaining why, over deleting it. Several here are parked — **read the header
   comment before re-enabling any schedule.**
5. **Author-controlled context spliced into `run:`/`script:` is executable code,
   not data.** GitHub substitutes `${{ }}` into the shell/JS text *before* it runs,
   so a commit message, issue title, branch name, or `client_payload` field
   templated inline can execute. `auto-deploy-on-push.yml` echoed the raw commit
   message; a push whose message contained "…macOS & Linux…" ran `macOS` as a
   command → exit 127 → **that push's production deploy failed** (2026-07-26). The
   class was swept in PR #170, but that pass missed **push-event** context (commit
   messages). **Fix:** put untrusted context in an `env:` var and read it as quoted
   `"$VAR"` (bash) / `process.env` (github-script); build JSON with `jq --arg`;
   never `eval`. Trusted GitHub contexts (`github.sha`, `github.run_id`) may stay
   inline. Sweep command: `grep -rnE 'head_commit\.message|github\.event\.(issue|comment|client_payload|pull_request)|github\.head_ref|github\.ref_name' .github/workflows/`.

## Data flow & generated files (don't hand-edit blindly)
- `public/data/events.json` + `public/events/*.html` are **generated** by
  `scripts/sync/sync-events.py` from the **pdoom-data** repo, reading
  `data/serveable/api/timeline_events/all_events.json`. Fix data at the source.
- **Editing the generator's f-string template rethemes ~2,194 pages at once.**
  That is the cheap lever; the expensive part is the ~29 hand-written pages
  carrying 147 KB of inline CSS between them.
- **Chesterton's fence, a real case:** 1,000 `public/events/alignmentforum_*.html`
  pages have no entry in `all_events.json` and look like dead weight. They are
  not. pdoom-data still holds all 1,000 in a *separate* collection
  (`timeline_events/alignment_research/`), which the sync has never read. See
  `docs/TECH_DEBT.md` §E-0. **Trace generated content back to its source before
  deleting it.**
- **Event descriptions are raw PDF text, so they carry other people's PII.**
  arXiv/ACM author blocks include institutional email addresses; 75 distinct
  academics' addresses were live on 44 pages until 2026-07-29. `sync-events.py`
  now redacts them (`redact_pii()` walks the WHOLE event dict, not a field list,
  so a new upstream field cannot leak). `scripts/check-published-emails.py`
  re-verifies and imports the generator's one regex rather than copying it.
  The addresses are still in pdoom-data — scrubbing here does not fix the source.
- **Events were not the only mirror.** `public/data/issues-cache.json` is a verbatim
  copy of pdoom1's issue bodies, rendered by `/issues/`, and it was written raw. On
  2026-08-02 a `Co-Authored-By` trailer inside an issue body put a live address on the
  site and turned the BLOCKING honesty job red on main and on every open PR — nothing
  in this repo could clear it, because the only edit that fixes the literal is in
  another repo and the next sync reinstates it. `update-game-data.yml` now calls the
  same `redact_pii()` (imported from `sync-events.py`, not reimplemented) before
  committing. **When a guard is written for one mirror, check whether a second mirror
  exists** — this is the twin of the exemption lesson #239 recorded one guard over.
- `public/design/tokens.json` is fetched at runtime by ~8 pages; the other ~2,190
  hardcode their colours in an inline `:root`. It is not a design system yet.

## Analytics
- Self-hosted **Plausible at `analytics.pdoom1.com`** (NOT plausible.io cloud).
  Script tag hardcoded in each page `<head>`. Ingestion: `POST /api/event` → 202.
- **`202` means "accepted", not "stored".** Plausible returns 202 for events
  aimed at any domain and drops unregistered ones downstream. It is not proof.
- **Never inject a second tracker.** Plausible's script overwrites
  `window.plausible` on load, so two trackers race and the loser's custom events
  vanish. `public/assets/js/analytics.js` used to inject the *cloud* script,
  silently discarding ~half of all Download events. That file is now a consent
  shim only — it must never create a `<script>`.
- The opt-out flag the tracker actually reads is
  `localStorage.plausible_ignore === "true"`. Nothing else works.
- `analytics-config.json` is unused documentation.
- `scripts/alpha-watch.py` reports the two launch signals (site + leaderboard).
- **The Plausible VPS has no backups of any kind** (TECH_DEBT A1). The interim
  hedge is `snapshot-analytics.yml` → `scripts/snapshot-plausible.py`, which
  commits a daily `public/data/analytics/history/<date>.json`. There is exactly
  ONE such workflow; extend it rather than adding a second (see what two writers
  did to `version.json`).
  - The API answers `--period 30d` with the 30 days **ending yesterday**, so
    every day is captured by ~30 consecutive snapshots and one lost run costs
    nothing. The flip side: the hedge only reaches back 30 days from the first
    snapshot ever taken (2026-07-23 → 2026-06-23). **Older history exists only
    on the VPS** until someone runs `--range START:END`.
  - The script **writes nothing** on a missing key (exit 2), a failed/malformed
    fetch (3) or an all-zero response (4), so a bad run can never clobber the
    last good `latest.json`. CI passes `--require-key`: a revoked secret is a
    red run, not a green no-op. `scripts/test-snapshot-plausible.py` asserts all
    of that against a stubbed API — no key needed — plus the workflow contract.
  - Snapshots live under `public/`, so they are publicly fetchable once a human
    push deploys. Aggregate counts only; `public/data/analytics/README.md`
    already declares the retention public.

## Blog & feeds
- Posts are `.md` in `public/blog/`, listed in `public/blog/index.json` (keys:
  filename, title, date, tags, summary, commit, featured). `public/blog/post.html`
  renders client-side with a **very** limited markdown parser: links, images,
  inline code, bold, italic. **No tables, no fenced code blocks, no headings.**
  Anything else renders as raw text. Links go to `/blog/post.html?p=<file>`.
- `scripts/generate-feeds.py` emits `feed.xml` (RSS) and `atom.xml` from
  `index.json`; `generate-feeds.yml` keeps them current and verifies on PRs.
  Feeds are the **privacy-first** subscribe option — no account, no address, no
  list to leak. Prefer them to an email list.
- `index.json` has held entries pointing at files that don't exist; the feed
  generator skips and reports those rather than publishing a dead link.

## Design notes (ADRs)
- `scripts/sync/sync-design-notes.py` renders the game's ADRs to
  `/design-notes/`, scrubbing internal process markers. It **refuses to write**
  a page whose body still carries one (`assert_clean` raises). Covered by
  `scripts/test-design-notes.py`.
- The scrubber is deliberately case-sensitive and anchored: ADR-0009 legitimately
  contains the prose "…anchors this session:", which is design content, not a
  process artefact. A loose match would train everyone to ignore the guard.

## Local test suite (run these before opening a PR)

**Every line below is now also wired to CI** (PR #TBD, `ci/wire-the-guards`,
2026-08-01). Before that audit, **10 of them ran only if a human remembered** —
and this file claimed otherwise for at least one. The bracket says which workflow
runs it, so a claim here can be checked against `.github/workflows/` in one grep.
`[ADVISORY]` means it is reported into the job summary and **never blocks**.

```
python scripts/test-design-notes.py       # ADR scrubber + markdown subset   [encoding-safety]
node    scripts/test-analytics-optout.js  # opt-out, DNT, no-injection       [content-honesty]
python  scripts/test_ingest_scores.py     # leaderboard read path            [data-contract]
python  scripts/validate_data.py          # data contracts                   [data-contract]
python  scripts/check-stale-facts.py      # hardcoded facts that rot         [content-honesty ADVISORY]
python  scripts/check-stale-facts.py --min-severity HIGH  # the gate         [content-honesty]
python  scripts/check-platform-claims.py  # no page claims an unshipped OS   [content-honesty, encoding-safety]
python  scripts/test-platform-claims.py   # ...and that guard can still FAIL [content-honesty]
node    scripts/test-download-resolution.js # download buttons resolve/degrade [content-honesty]
node    scripts/test-changelog-render.js  # /game-changelog/ derives         [content-honesty]

python  scripts/check-published-emails.py # no third party's address served  [content-honesty]
python  scripts/snapshot-copy.py --check  # reader-facing prose drift        [content-honesty ADVISORY]
python  scripts/generate-feeds.py --check # feeds in step with the blog      [generate-feeds]
python  scripts/generate-metabolism.py --check # /metabolism/ in step        [metabolism-map]
python  scripts/test-snapshot-plausible.py # analytics backup fails loudly   [content-honesty, snapshot-analytics]
node    scripts/test-header-consistency.js # nav contract + emoji            [content-honesty ADVISORY]
python  scripts/test-changelog-structure.py   # changelog files + data shape [encoding-safety]
python  scripts/check-encoding-safety.py      # cp1252 preamble + encodings  [encoding-safety]

python  scripts/sync/sync-keybinds.py --check # FULL gate; needs ../pdoom1   [local only]
python  scripts/sync/sync-keybinds.py --ci    # no-typed-keys half only      [content-honesty]
python  scripts/test-weekly-league-boundary.py  # run-time -> week (A9)      [weekly-league-reset]
python  scripts/stamp-league-epoch.py --check   # weekly records carry epoch [data-contract]
node    scripts/test-board-escaping.js    # no API field reaches innerHTML   [board-liveness]
node    scripts/test-board-honesty.js     # key mismatch stays visible       [board-liveness]
python  scripts/test-publish-live-board.py # publisher refuses, never guesses [board-liveness]

node    scripts/test-escaping.js          # the SAME rule on the other 14 pages [escaping]
node    scripts/test-roadmap-render.js    # roadmap markdown subset + escaping  [escaping]
node    scripts/test-blog-render.js       # blog markdown subset               [generate-feeds]

python  scripts/check-deploy-excludes.py  # nothing deployed points at an excluded file [content-honesty]
python  scripts/make-og-card.py --check   # share card is 1200x630 and under budget [content-honesty]
```

**Severity model — the rule that decides where a check goes.** A check is
**blocking-and-true** or **advisory-and-labelled**. Never red-but-tolerated: "a
red test in the suite is worse than no test", and that applies to a permanently
red CI job with double force, because nobody can even skip it deliberately —
they just learn the red square means nothing. Three checks are advisory for
concrete reasons, not because they are unimportant:
- `check-stale-facts.py` — 213 findings, **0 HIGH**. A blog post titled "v0.6.0"
  is correct history. The blocking form is `--min-severity HIGH`; the full report
  goes to the job summary.
- `snapshot-copy.py --check` — 24 pages of prose have legitimately moved since
  the 2026-07-22 baseline. It is a **review aid** so Pip can see copy drift, not
  a gate.
- `test-header-consistency.js` — 19/27 today. Real drift, but content emoji in
  frozen prose is not a lie to a visitor, and blocking on it would freeze content
  work.

**Not wired, on purpose:**
- `check-control-characters.py` — red (28 control chars across generated
  `public/events/arxiv_*.html`). Genuine, but the fix belongs in
  `sync/sync-events.py` at the generator, and wiring it before that lands would
  create exactly the permanent red this section forbids.
- `sync-keybinds.py --check`'s **drift** and **freshness** halves — both are only
  fixable by re-running the sync against a **local pdoom1 checkout**, which no
  runner has and this repo cannot produce. Blocking on them would make an
  unrelated content PR un-mergeable until a human with the game repo intervenes.
  `--ci` runs all three and lets only no-hardcoding set the exit code, printing
  the other two as `WARN`. Same reasoning applies to anything else needing
  `$PDOOM1_REPO`.

## Testing discipline
Every line below was earned by something that actually went wrong here, mostly on
2026-07-30. They are cheap to follow and expensive to relearn.

- **A claimed safety property needs a forced failure.** If a script says it "fails
  loudly", "refuses rather than guesses" or "never overwrites good data", there must be a
  test that FORCES that path and observes it. A docstring is documentation, not evidence.
  Copy `scripts/test-board-escaping.js` or `scripts/test_ingest_scores.py`: build inputs
  in a temp dir, assert the refusal, never mutate a committed fixture.
- **A guard seen only in its passing state has not been shown to work.** Green is equally
  consistent with "the condition is safe" and "the check never fires". Make it fail on
  purpose once and keep that as the test.
- **Never assert a literal against a value that moves.** `test_ingest_scores.py` pinned a
  fixture to `v0.11.0` while the rule under test was "matches the DEPLOYED version"; it
  went red at v0.12.0 and stayed red through two more releases. Read the moving value and
  assert the *rule*.
- **A red test in the suite above is worse than no test** — it teaches everyone to skip
  the suite, so the one failure that matters is skipped with it. Fix it or delete it.
- **Refusing to act is itself a silent-failure mode.** A script that correctly declines
  every run is externally identical to one that is broken. Anything that can refuse needs
  a staleness escalation, not just a warning in a job summary.
- **Absence of a marker is never a clean bill of health.** Everything predating a marker
  is unmarked too, so a missing flag must render as *unknown*, never as *fine*.
- **Check sibling branches before writing a fix.** Two agents independently rewrote the
  same test on 2026-07-30, one better than the other. With parallel work here, duplicated
  effort is a more common waste than merge conflicts are.
- **"It is in the pre-PR suite" is not "it runs".** The 2026-08-01 audit found 10 of
  the checks listed above wired to no workflow at all, and this file asserting CI
  coverage for one that had none. A documented suite is a suite a human runs when they
  remember; CI is the only thing that runs when they do not. When adding a check, wire
  it in the same commit, and grep `.github/workflows/` before believing a claim here.
- **A guard that returns early can be green having checked nothing.** Look for the
  cheap exit before the expensive scan — `check-platform-claims.py` had one, and it
  was reached on every real run. The test for such a guard has to force the state that
  gets past the early return.
- **Anything rendering data from the score API must escape it.** That API is
  unauthenticated and validates nothing — `GET ?seed=x&version=L9` returns `ok:true` for
  a board that never existed — so every field is attacker-controlled.

## Escaping: there is exactly ONE escaper, and it is a file
`public/assets/js/escape.js` — `escapeHTML`, `safeUrl`, `safeUrlRaw`, `isSafeUrl`,
`toNumber`. Every page that renders fetched data loads it with a **plain blocking**
`<script src="/assets/js/escape.js">` in the head (not defer, not async — the inline
renderers call it). If it fails to load, `escapeHTML` is undefined, the template throws
and the page renders nothing: **fail closed**.

- **Do not write a second one.** Before 2026-08-01 there were FIVE, with three different
  coverages, and **three of them did not escape quotes while feeding attribute contexts**
  (`href="…"`, `style="background:#…"`, `alt="…"`), where a bare `"` ends the attribute
  and the next token is read as a new attribute. They could not protect their own primary
  sink. `league/archive.html` had the only complete one — applied to 9 interpolations and
  skipped on 11, which is *worse* than none because it defeats a reviewer's spot check.
- **Pick by sink, not by habit:** `escapeHTML` for element text and quoted attributes;
  `safeUrl` for an href/src inside an HTML string; `safeUrlRaw` for a JS sink like
  `window.open` (`safeUrl` would turn the query `&` into `&amp;`); `isSafeUrl` when the
  string is already escaped in place. Escaping alone can never make a URL safe —
  `javascript:alert(1)` contains no HTML metacharacter.
- **`toNumber` is an availability fix, not an escaping one.** `entry.score.toLocaleString()`
  and `(entry.final_doom || 0).toFixed(1)` both throw a `TypeError` on a string, and one
  throw inside a render loop kills the **whole** list. `|| 0` does not help: a non-empty
  string is truthy, and `String.toLocaleString` is the identity function. A single POST of
  `{"score":"x"}` was a denial of service on `/league/`, `/league/archive.html` and
  `/leaderboard/` with no injection involved.
- **`escapeHTML` is not correct in every context.** Unquoted attributes, `<script>`,
  `<style>`, and `on*` handlers need restructuring, not escaping. `/issues/` validates
  `label.color` as six hex digits instead, because a `style=` value is CSS, not HTML.
- Enforced by `scripts/test-escaping.js` + `.github/workflows/escaping.yml`. It enforces
  the **class**: interpolations are checked by declared external-data ROOT (so a new field
  is covered the day it lands) and every `fetch()` target must be declared (so a new data
  source fails until someone says where its result goes). Adding a page that renders
  fetched data means adding it to `GUARDED` in that file.

**`/metabolism/` is generated, never hand-edited.** `scripts/generate-metabolism.py`
derives every cadence on that page at build time from the thing that actually runs —
the `cron:` lines in `.github/workflows/`, `scripts/weekly-league-config.json`, the
manager's own week arithmetic, `docs/LEAGUE_SEED_LEDGER.md`, `public/data/clocks.json`
— and renders each with a clickable `file:line`. The two classes of fact it cannot
derive (pdoom1's release nomenclature, and observations with no in-repo measurement)
live in `public/data/metabolism.json` with an explicit `source` + `derived_from`, and
render as *declared*, not measured. Change a cron and `--check` fails the PR
(`metabolism-map.yml`); the fix is to re-run the generator. It refuses to build if a
workflow carries a park marker *and* a schedule, or if a citation needle has vanished.

**Keybinds are MIRRORED from the game, not derived — and a mirror rots.**
`public/data/keybinds.json` is written by `scripts/sync/sync-keybinds.py`, which
parses `godot/autoload/keybind_manager.gd` out of a **local pdoom1 checkout**
(`--game-repo`, `$PDOOM1_REPO`, or `../pdoom1`). pdoom1 publishes no keybind
artifact yet — the ask is **pdoom1#1011**. Until that lands the file is stamped
`"mirror": true` with source path, source commit and `verified_on`.
`--check` fails on three things: drift vs the game source (skipped when no
checkout is present), a mirror older than 90 days, and **any key typed as a
literal into a page**.
**CORRECTED 2026-08-01:** an earlier version of this file called that third check
"the one that runs everywhere, including CI". It ran in CI nowhere —
`grep -rn keybind .github/workflows/` returned nothing. It now genuinely does, via
`content-honesty.yml` calling the new `--ci` mode, which blocks on no-hardcoding
and demotes drift/freshness to `WARN` because their only fix is a local game
checkout. Treat any "runs in CI" claim in this file as a hypothesis until grepped.
Pages must
use `<kbd data-keybind="<action>">…</kbd>` and let the JS fill it; typing `N` into
HTML is exactly how pdoom1's own `CONTRIBUTING.md` came to say "backslash" long
after the bind moved. If the fetch fails the placeholder deliberately **stands**
rather than falling back to a remembered key — a stale key sends a player to a key
that does nothing, which reads as "the game is broken".
`BuildInfo.DEV_BUILD` is a hand-flipped `const` (nothing in the export tooling
sets it), so dev-gated keys must be described as "may or may not be in your build".

**Platform availability is a *derived* fact, not prose.** The source of truth is
`public/data/version.json` → `latest_release.platforms` ({windows,macos,linux}
booleans), which `scripts/update-version-info.py` derives from the GitHub release's
actual **assets** (a build is either attached or it is not). Pages must not hardcode
"available on Windows/Mac/Linux"; say "coming soon" for anything unshipped, or read
the field (see `about/index.html`'s `platforms-available` stat). `check-platform-claims.py`
(also wired to CI via `content-honesty.yml`) fails if a reachable page advertises a
platform that has no build.

- **Its green was vacuous until 2026-08-01.** `scan()` returns 0 *before opening a
  single page* when every platform is `true` — which is the state today — so the
  passing run said nothing whatsoever about the pages. That is CLAUDE.md's "a guard
  seen only in its passing state has not been shown to work", live in the repo.
  `scripts/test-platform-claims.py` now forces `macos: false` and asserts the guard
  rejects a page advertising it, accepts `"macOS — coming soon"`, ignores element ids
  and JS strings, and prints `SKIP` (not silence) in the disarmed no-`platforms` state.
  It also asserts every path in the live `REACHABLE` list still exists — a renamed page
  would otherwise drop out of coverage silently. Run it BEFORE the guard, not after.

- **`version.json` has TWO writers, and one of them disarms the guard.**
  `update-version-info.py` (via `auto-update-data.yml`) writes `latest_release.platforms`.
  `update-game-data.yml` has its own inline Python that rebuilds `version.json` **from
  scratch without that key**. Both run on ~6h crons, so the field blinks in and out —
  `git log -S'"platforms"' -- public/data/version.json` shows the two alternating. While
  it is absent, `check-platform-claims.py` prints `SKIP: version.json has no
  latest_release.platforms` and **exits 0**, so the honesty guard is silently inert about
  half the time. A page reading `latest_release.platforms` must therefore treat absence as
  "unrecorded", never as "nothing shipped". (Found 2026-07-28; not yet fixed.)

## Changelog surfaces — there are three, and only one is live
- **`/game-changelog/` is the player-facing one.** It is in `navigation.js` ("Updates"),
  the homepage footer ("Releases"), `/press/` and `/dashboard/`, and in
  `check-platform-claims.py`'s REACHABLE list. It renders release notes **derived at
  runtime** from `public/data/version.json` (current release) plus the pdoom1 releases API
  (history) — no version literal exists in the page. `scripts/test-changelog-render.js`
  locks that contract down, including the degradation paths.
- `/website-changelog/` is a *different audience* (site infrastructure), fed by
  hand-typed `data/website-changes.json`. Not a duplicate; also not maintained.
- `/changelog/` **301s to `/game-changelog/`** (Pip's call, 2026-07-28). It was orphaned
  and its data pipeline is dead — `sync_airtable.py`'s workflow was parked after 1,264
  consecutive failures against an Airtable base that does not exist. The redirect lives in
  `public/.htaccess`; the page itself keeps a meta-refresh + `location.replace()` fallback
  and an honest "this page has moved" message. Redirected, not deleted, because
  `rsync --delete` makes deletion a production removal. **`.htaccess` cannot be tested on
  a Netlify preview — Netlify ignores it.** Any change to it needs
  `curl -I https://pdoom1.com/<path>` against production after merge.
- `public/data/game-changes.json` is now read by nothing (it carries a `_deprecated`
  note saying so). Kept, not deleted: `rsync --delete`.

## Automation notes
- Weekly-league rollover only opens a GitHub issue **on failure**
  (`weekly-league-reset.yml`). The old workflow that spammed 35 "success" issues
  was removed 2026-07-14 — don't reintroduce success-issue creation.
- **The league week is anchored to Friday 00:00 `Australia/Hobart`** (Pip,
  2026-07-28: "Everything is going to be based off Hobart time, AEST"), matching
  the game's own "Seed — every Fri" cadence in
  `pdoom1/docs/RELEASE_NOMENCLATURE.md`. The cron is `0 14 * * 4` — **Thursday**
  14:00 UTC — which is Fri 00:00 Hobart in winter and Fri 01:00 in summer, i.e.
  always a Friday there and never *before* the week it opens.
  **`Australia/Hobart` is not a fixed offset:** +10 (AEST) in winter, +11 (AEDT)
  from October to April. The week is derived with `ZoneInfo`, never an offset, so
  DST cannot move the answer — only how far into the week the run lands. A
  hardcoded `+10` is the tempting wrong fix; `league_tz()` raises rather than
  falling back to one.
  **`zoneinfo` has no bundled tz database on Windows** — `ZoneInfo("Australia/Hobart")`
  raises until `pip install tzdata`. It is pinned in `requirements.txt`; without
  it the league scripts die locally while CI stays green.
- **The rollover off-by-one is FIXED (2026-07-28, TECH_DEBT A9).** The run-time →
  week mapping is explicit (`league_week_start()`), never derived from `now`, and
  the Friday anchor let the old look-ahead go away entirely: the cron fires inside
  the week it opens, so the week is simply the one containing the run.
  `scripts/test-weekly-league-boundary.py` (74 assertions) pins the boundary in
  **both DST states** plus the two DST-spanning weeks, and runs as the **first**
  step of the rollover workflow. **Do not "simplify" that back to
  `datetime.now()`** — `datetime.now()` without a tz is *local* time, which on
  Pip's box is AEST (+10), exactly the size of skew that crosses this boundary.
- **The league and player pages are retired-and-hidden, not deleted** (Pip,
  2026-07-28), and everything opened before the **L2 → L3 ladder fork** is
  labelled **anomalous pre-history** via a machine-readable `epoch` block in the
  data. The boundary is `2026-07-31 00:00 Australia/Hobart`
  (`2026-07-30T14:00:00Z`) and **it is not a script literal** — it lives in
  `public/data/ladder-epochs.json`, which `weekly-league-manager.py` reads. First
  regularised week is **2026_W32** (Fri 2026-07-31).
  **Do not re-derive this from `RELEASE_NOMENCLATURE.md`'s "Epoch = first Friday"
  rule** — that is how an earlier pass got 2026-08-07. The ladder forked
  *mid-month* on gameplay changes (the AP pool was removed for an attention
  economy); the shipping build is v0.13.2 on L3. **pdoom1-website#151, comment
  2026-07-28T23:13Z, is authoritative and supersedes that calendar row.**
  Week ids changed meaning at the 2026-07-30 rollover, so **compare
  `start_timestamp`, not ids**, across that switch. Before touching any weekly
  archive, seed leaderboard, or `/league/` + `/players/` page, read
  `docs/LEAGUE_EPOCH_ANOMALY.md`.
- **The board key is `(seed, ladder_version)` — literally `L3`.** NOT
  `v0.13.2`, NOT `L3.0`, and **no longer `(seed, game_version)`** (an earlier note
  here said that; pdoom1 #151 supersedes it). `GameConfig.get_board_version()`
  returns `"L" + LADDER_VERSION`. The build version never touches the board key
  again — that is the point of the build-vs-ladder split. `meta.game_version` in
  a weekly record is a **record stamp only**; keying off it is what stranded 23
  real submissions.
  **The score API has NO key validation.** A wrong seed or version returns
  `ok:true` with an empty board (verified 2026-07-29, read path) — indistinguishable
  from "nobody is playing", and **no error is shown to the player**. Proving a key
  needs a *positive* check (post a score, read it back). Suspect a key mismatch
  before suspecting analytics.
- **Never present an unblessed seed to a player.** The blessed value is
  `docs/LEAGUE_SEED_LEDGER.md` → mirrored into `public/data/ladder-epochs.json`;
  anything the website derives is a placeholder marked
  `seed_provenance.blessed: false`, and `public/leaderboard/index.html` will not
  offer it. Pip, 2026-07-29: *"Let's keep using variables and not hardcoding
  things where we can!"* — pinned values go in a data file with a `source` note,
  never a script literal.
- pdoom1 PR #679 also rules that this repo is a **read-only consumer** of one PHP
  score API and must not stand up a second score store.
