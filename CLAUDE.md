# pdoom1-website — repo notes for Claude Code sessions

Complements the base `d:/Local_Code/CLAUDE.md` (MAIN style guide). This file is
repo-specific operational knowledge — read it before working here to skip
rediscovery. Keep it high-signal; add gotchas that cost real time.

## What this repo is
- **Statically pre-rendered** site: ~2,225 hand/generated HTML files (one per event).
  Most styling is **inline `<style>`** per page; shared `css/site.css` is tiny.
- **No shared layout spine.** `public/includes/navigation.html` exists but is wired
  into ZERO pages — navs are hand-copied and drift. `scripts/test-header-consistency.js`
  exists because of this. Wiring it up is the big open "un-dated" refactor.

## Cascade gotcha that will bite you (cost a whole session once)
- `public/css/site.css` is loaded **LAST** on ~2,203 pages (after the inline `<style>`
  and the two `/assets/css/*.css`). Same-specificity rules there **win the cascade**.
- Any rule in `site.css` MUST use the dark terminal palette. It once held light-theme
  literals (`.card{background:#fff}`, `:root{--accent-primary:#0066cc}`) which whited-out
  cards and turned ~2,200 event-page accents blue. The homepage masked it via a runtime
  token loader; event pages have none, so they showed the raw bug.
- **Lesson:** before concluding a visual bug "needs a live browser," grep ALL stylesheets
  in cascade order (`site.css` last) — the winning rule is usually findable statically.

## Deploy
- Push to `main` → **"Auto-Deploy to DreamHost on Push"** (~20s). Production = pdoom1.com.
- Use branch + PR (Pip's default). Every PR gets a Netlify **deploy-preview** — verify
  there before merge. Can't render a browser in-session, so verify by `curl`-ing the
  preview/prod asset (e.g. confirm `site.css` has the fix) and node-testing any JS.

## Environment / tooling
- Python is **`python`** (3.11), not `python3`. **Pillow is NOT installed by default**
  (add `--user` if you need `optimize-screenshots.py`); it's also missing from requirements.txt.
- **Encoding gremlin:** verifying non-ASCII byte-forms via shell heredocs mangles
  backslashes. Build target strings from code points (`chr(0x2192)`, `json.dumps(...)[1:-1]`),
  Write a script file and run it — do NOT hand-type the chars into an Edit/heredoc.
- `gh issue ... --json comments` returns `comments` as a **list**, not a count.

## Data flow & generated files (don't hand-edit blindly)
- `public/data/events.json` (+ the 2,200 `public/events/*.html`) are **generated** by
  `scripts/sync/sync-events.py` from the **pdoom-data** repo. Fix data at the source.
- Version/tokens/docs/dev-blog sync IN from the **pdoom1** game repo via workflows.
- Homepage status cards + game stats are populated client-side from `/data/version.json`.

## Analytics
- Self-hosted **Plausible at `analytics.pdoom1.com`** (NOT plausible.io cloud). Script tag
  hardcoded in each page `<head>`; on ~2,223/2,225 pages. `analytics-config.json` is unused
  documentation. Ingestion health: `POST /api/event` → 202.

## Blog
- Posts are `.md` in `public/blog/`, listed in `public/blog/index.json` (keys: filename,
  title, date, tags, summary, commit, featured). `public/blog/post.html` renders a post
  client-side (dependency-free markdown parser; no tables/raw-HTML support). Links go to
  `/blog/post.html?p=<file>`.

## Automation notes
- Weekly-league rollover logs to `/monitoring/` and only opens a GitHub issue **on
  failure** (`weekly-league-reset.yml`). The old `weekly-league-rollover.yml` that spammed
  35 "success" issues was removed 2026-07-14 — don't reintroduce success-issue creation.
- The game↔website score/leaderboard handoff is **not** end-to-end validated; rollover
  "success" has reported false positives (see the website repo's open tracking issue).
