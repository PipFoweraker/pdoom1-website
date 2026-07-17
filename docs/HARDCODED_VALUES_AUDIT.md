# Hardcoded player-facing values — audit & remediation (2026-07-17)

Goal (Pip): catch hardcoded game/data facts in player-facing pages and wire them to a
**source of truth**, so a game patch doesn't leave stale numbers on the site. Trigger: the
game is now **Godot-only** (Python fully removed in today's build) — so *any* Python
reference flags a page for accuracy review.

## Source-of-truth files that exist today
- `public/data/version.json` — `latest_release.version`/`.published_at`; `repository_stats.*`;
  `game_stats.{baseline_doom_percent, frontier_labs_count, strategic_possibilities}`; release
  `body` records the engine (Godot 4.5.1). Synced from GitHub releases.
- `public/data/status.json` — website/game version, dev phase, next milestone.
- `public/data/integration-health.json` — CI/data health (already flags the leaderboard version drift).

## Fixed in this pass (unambiguous — bugs & wrong facts)
| Where | Was | Now |
|---|---|---|
| `league/index.html`, `players/index.html` | `week_id.replace('2025_W','W')` — **mislabels every 2026 week** | `replace(/^\d{4}_W/,'W')` (year-agnostic) |
| `index.html` Frontier Labs fallback | `7` | `5` (matches `version.json.game_stats.frontier_labs_count`) |
| `index.html` website-version fallback | `v1.1.1` | `v0.2.1` (matches `status.json`) |
| `index.html` Requirements tab | "Python 3.8+ / pygame / `pip install` / `python main.py`" | Godot 4.5.1 native build + download guidance |
| `about/index.html` Technology section | "Python and Pygame" + Python-Powered/Pygame cards + version `0.4.1` | Godot 4.5.1 + Godot/native cards + `v0.11.0` |
| `press/index.html` | Engine: "Python/Pygame" | "Godot 4.5.1" |

## Needs wiring to an EXISTING source (A) — static literals that should be dynamic
These pages render static values that already have a source; a future pass should fetch, not hardcode:
- `about/index.html` version (`v0.11.0`) and `press/index.html` factsheet — **neither page fetches
  `version.json`**. Recommend: a tiny shared `version-badge.js` include that stamps version/date from
  `version.json` on any page (index/game-stats already do this inline — extract + reuse).
- **Engine field:** version.json only records the engine in the release *body* prose. Recommend the
  release-sync add an explicit `engine` field so "Godot 4.5.1" is wired, not hand-typed in 3 places.

## Needs a NEW source (B) — no endpoint exists yet
- **`dashboard/index.html`** — ~30 AI-landscape facts (model names, FLOPS curve, p(doom) %, expert
  consensus, stock tickers, regional compute, safety-investment $) are hardcoded and framed as *live*.
  Per Pip this page is disposable (a contributor's aggregator demo). **See `docs/DASHBOARD_DATA_PLAN.md`**
  for reconfiguring it to feed from game data and/or pdoom-data.

## Editorial / static (C) — fine to leave
Copyright years, "last updated" prose timestamps, historical timeline dates, Steam legal text.

## Pages flagged for FULL accuracy review with today's Godot build
`index.html` (Requirements tab), `about/index.html` (Technology & Approach + Project Stats),
`press/index.html` (factsheet: release status, specs). Engine facts are corrected above, but exact
system requirements, release status, and feature claims should be re-checked against the shipped
build — I did not invent specs. Tracked for the design-coherence pass.

## The durable fix (minimise patch-time debt)
1. Extract the version.json→DOM stamping (already inline in index/game-stats) into a shared include
   used by every player-facing page — one source, no per-page literals.
2. Add `engine` (+ later, system-requirements) fields to `version.json` via the release-sync so the
   game is the source of truth for its own tech facts.
3. For AI-landscape data, stand it up as a pdoom-data read API (per the settled architecture) and have
   the dashboard consume it — see the dashboard plan.
