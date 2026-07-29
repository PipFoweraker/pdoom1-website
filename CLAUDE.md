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
- **No shared layout spine.** `public/includes/navigation.html` is wired into
  ZERO pages. `public/assets/js/navigation.js` is the de-facto single source
  (used by ~8 pages) and is what new pages should adopt — put an empty
  `<header></header>` in the body and load the script at the end.
  `scripts/test-header-consistency.js` reports the drift (currently 0/23 pass).

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
- Use branch + PR (Pip's default). Every PR gets a Netlify **deploy-preview** —
  verify there before merge. Can't render a browser in-session, so verify by
  `curl`-ing the preview/prod asset and node-testing any JS.
- **Bot commits do not trigger deploys.** GitHub Actions will not fire a workflow
  from a push made with the default `GITHUB_TOKEN`, so anything a workflow
  commits reaches the repo but not pdoom1.com until the next human push. Affects
  every committing workflow here. Fix would be a deploy key/PAT or a
  `workflow_run` trigger.

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
```
python scripts/test-design-notes.py       # ADR scrubber + markdown subset
node    scripts/test-analytics-optout.js  # opt-out, DNT, no-injection regression
python  scripts/test_ingest_scores.py     # leaderboard read path
python  scripts/validate_data.py          # data contracts
python  scripts/check-stale-facts.py      # hardcoded facts that rot
python  scripts/check-platform-claims.py  # no reachable page claims an unshipped OS
node    scripts/test-download-resolution.js # download buttons resolve/degrade right
python  scripts/snapshot-copy.py --check  # reader-facing prose drift
python  scripts/generate-feeds.py --check # feeds in step with the blog
node    scripts/test-header-consistency.js
python  scripts/test-weekly-league-boundary.py  # rollover run-time -> week mapping (A9)
python  scripts/stamp-league-epoch.py --check   # every weekly record carries its epoch
```

**Platform availability is a *derived* fact, not prose.** The source of truth is
`public/data/version.json` → `latest_release.platforms` ({windows,macos,linux}
booleans), which `scripts/update-version-info.py` derives from the GitHub release's
actual **assets** (a build is either attached or it is not). Pages must not hardcode
"available on Windows/Mac/Linux"; say "coming soon" for anything unshipped, or read
the field (see `about/index.html`'s `platforms-available` stat). `check-platform-claims.py`
(also wired to CI via `content-honesty.yml`) fails if a reachable page advertises a
platform that has no build.

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
