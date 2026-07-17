# Game → website score uplift: scouting findings + plan

> **SETTLED (2026-07-17) by pdoom1 PR #679** — `docs/strategy/BACKEND_AND_DATA_ARCHITECTURE.md`.
> The fragmentation this doc flagged is resolved: **one PHP score API behind a frozen v1 HTTP
> contract; no parallel score paths.** What that means for *this* repo:
> - **We are a READ-ONLY consumer.** Read scores via the API's `GET` (CORS-enabled) or the
>   `board_<seed>__<version>.json` files. **Do not stand up a second score store** — our
>   `ingest_scores.py` is a read *cache/snapshot* publisher, not authoritative.
> - **The contract is frozen** and mirrored in `schemas/leaderboard-seed.schema.json` (`$defs.entry`)
>   + `schemas/leaderboard-api.schema.json` (GET/board/POST shapes). Entry = `score, doom_integral,
>   player_name, date, level_reached, game_mode, duration_seconds, entry_uuid, baseline_*`. Sort:
>   score DESC, doom_integral DESC (ADR-0002). `final_*` are legacy-only.
> - **Deploy collision RESOLVED:** the API lives on a separate subdomain (`api.pdoom1.com`), not under
>   the static site's `rsync --delete` root (`pdoom1.com` → `$DH_PATH`) — different dirs, no clobber.
>   Read path is config-driven via `config.json.scoreApi` (empty until the host is finalized).
> - **Open (for Pip + agents):** final host/subdomain; whether we read `board_*.json` off-disk
>   (needs co-location) or via `GET` (CORS, host-agnostic — the likely default for a static site).
>
> The historical scouting below stands as the record of *why* the uplift was broken.

Scouted `pdoom1` @ `origin/main` (abbe277, 2026-07-16) in a read-only worktree, 2026-07-16.

## Finding: there is no working uplift today

The game→website score path is **broken**, not merely stale:

- **Godot leaderboard is local-only.** `godot/scripts/leaderboard.gd` ("Local leaderboard
  system... JSON-based storage, ported from pygame") writes to
  `user://leaderboards/leaderboard_<seed>__<version>.json` on the *player's* machine.
  It contains **no HTTP / upload / API / website code** whatsoever.
- **The Python export is orphaned.** `scripts/export_leaderboards.py` (the old
  `--copy-to-website` uplift) imports `scripts.lib.scores.enhanced_leaderboard` and
  `scripts.lib.services.version` — **neither module exists** anymore (deleted in the
  Godot migration). It would crash on run. `tools/web_export/api_format.py` has the same
  dead `scripts.lib.services.version` import.
- **Consequence:** the website's leaderboard files (`seed_leaderboard_*.json`,
  `weekly/current.json`) are **frozen legacy data from the v0.4.1 Python era** — which is
  exactly why `validate_data.py` flags `game_version=v0.4.1` vs deployed `v0.11.0`, and why
  the weekly league has 0 participants.

Version-of-truth is also fragmented: `version.txt` = `0.11.0` (real), but the export path
hardcodes `Bootstrap_v0.4.1` (`api_format.py` x5) and `website-version-api.py` hardcodes
`0.6.0`. Three numbers, none reading `version.txt`.

## Good news

The **contract is already right**: the website's `schemas/leaderboard-seed.schema.json`
matches the fields the (old) export produced and that Godot stores locally
(`score, player_name, date, level_reached, game_mode, duration_seconds, entry_uuid,
final_*`). So whatever we build to move data, the shape is already specified and validated.

## The decision that gates everything

**Are player scores meant to reach the website automatically, or is the leaderboard
curated by you?** The game is a downloadable Godot app on players' machines, and the site
is static (DreamHost) — so "real player leaderboards" needs an ingestion backend that
accepts writes. Three architectures:

### Option A — In-game HTTP submission (the "real" multiplayer leaderboard)
Godot POSTs each game-over score to a website ingestion endpoint.
- **Needs:** (1) an ingestion API that can *write* (netlify function + a datastore, or the
  existing `scripts/api-server.py` promoted to a real host; the static site can't take
  writes directly); (2) Godot `HTTPRequest` on game-over; (3) the score-submission contract
  (already have it: the `entry` schema); (4) anti-cheat (server-side seed/score sanity,
  rate-limit, since a downloadable client is trivially spoofable).
- **Where the work lives:** ingestion API + validation → **website/pdoom-data** (safe, we
  control). HTTP submit + read `version.txt` → **game** (handoff).
- **Effort:** high. This is the actual weekly-league feature.

### Option B — Curated / batch export (rebuild the bridge for Godot)  ← recommended first step
A small script reads Godot's leaderboard JSON (from a dev/known `user://` export, or a
committed fixtures dir) and writes conformant `seed_leaderboard_*.json` into the website,
stamped from `version.txt`. This is the old Python export, **rebuilt Godot-aware and
version-correct**, runnable manually or in game-CI on release.
- **Where:** a new `scripts/export_leaderboards.py` in the **game** (reads Godot output +
  `version.txt`), validated against the copied schema before it writes (see
  `schemas/README.md`). Website side unchanged (it already consumes + validates).
- **Effort:** low–medium. Unblocks the drift immediately, no backend.

### Option C — Do nothing yet, but stop lying
Mark the current website leaderboard as **legacy/seed data** (a banner + a `"legacy": true`
flag) so `v0.4.1` isn't presented as live, and let `validate_data.py` keep the drift
visible. Zero code in the game.
- **Effort:** trivial. Buys honesty until A or B is chosen.

## Recommendation

1. **Now (website, safe):** Option C — stop presenting stale data as live; the validator
   already surfaces the drift. (~30 min, this repo.)
2. **Next (game handoff):** Option B — rebuild `export_leaderboards.py` Godot-aware +
   `version.txt`-stamped, validating against the contract before writing. Refreshes real
   seed leaderboards with correct versions. This is the "give the push-out mechanism love"
   you predicted — except it needs a *rebuild*, not a tweak, because the migration deleted it.
3. **Later (project):** Option A — the real ingestion API + in-game submission, when the
   weekly league is meant to have live players. Design the datastore first (netlify+KV/DB,
   or promote `api-server.py`).

The version-of-truth fix (everything reads `version.txt`; delete the hardcoded
`Bootstrap_v0.4.1` / `0.6.0`) is a prerequisite for B and A and is a clean, isolated
game-side change — good first handoff task.

## Built on the website side (2026-07-16) — the connection point is ready

Everything that doesn't touch the game is done, so the game handoff is a small last step:

- **`scripts/ingest_scores.py`** — the website-side receiver/publisher. Given
  contract-conforming `seed_leaderboard_*.json`, it validates every entry, aggregates
  into the `leaderboard.json` the page needs (which didn't exist → page was broken),
  and **stamps the real deployed version** from `version.json` (fixing the drift at
  publish time). It only publishes entries whose `game_version` matches the deployed
  version — so it's **self-healing**: the day the game exports real v0.11.0 scores, the
  board goes live automatically, no code change. Proven by `scripts/test_ingest_scores.py`.
- **Honesty (Option C) — shipped.** Leaderboard + league pages now show a banner and an
  honest "pre-launch" state instead of presenting synthetic/legacy data as live (and the
  league no longer shows an ended week as "🔴 LIVE"). Driven by `data_status`, so it
  self-clears when real data lands. `leaderboard.json` is published in the pre-launch state.

So the game's remaining job shrinks to: **deliver `entry`-conforming scores** (via an
export file or an ingestion endpoint) stamped with `version.txt`. Our side validates +
publishes. The delivery target format is `schemas/leaderboard-seed.schema.json`.

## Immediate handoff tasks for the game repo (when your build is pushed)
- [ ] Make the score export read `version.txt` for `game_version`; delete hardcoded
      `Bootstrap_v0.4.1` (api_format.py) and `0.6.0` (website-version-api.py).
- [ ] Decide A vs B for how Godot scores leave the machine.
- [ ] If B: rebuild `export_leaderboards.py` against Godot's `user://leaderboards/*.json`,
      validate against `schemas/leaderboard-seed.schema.json` before writing.
