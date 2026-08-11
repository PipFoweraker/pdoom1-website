---
title: "Manual Sync: v0.14.1"
version: "0.14.1"
release_date: "2026-08-07T16:08:56Z"
type: "game-release"
status: "stable"
download_url: "https://github.com/PipFoweraker/pdoom1/releases/tag/v0.14.1"
---

# Manual Sync: v0.14.1

**Version:** v0.14.1
**Release Date:** 2026-08-07T16:08:56Z
**Status:** Stable Release

## Download

- [Download Game](https://github.com/PipFoweraker/pdoom1/releases/tag/v0.14.1)
- [View Source Code](https://github.com/PipFoweraker/pdoom1/tree/v0.14.1)
- [Full Changelog](https://github.com/PipFoweraker/pdoom1/blob/main/CHANGELOG.md)

## Release Notes

**The board key does NOT move.** Ladder stays **L4**, featured seed stays
`weekly-2026-w32`, board key stays `(weekly-2026-w32, L4)`. Your v0.14.0 scores
are still valid and still on the same board. Nothing here touches scoring, run
outcomes, or replay determinism -- these are UI, diagnosis and tooling fixes.

Players on v0.14.0 could not see their own leaderboard. Six separate defects
made it invisible; this makes it visible. Every entry below is tied to a commit
merged between `v0.14.0` and this release.

Test provenance: the fast gate was measured locally on the tagged tree. The
simulation tier was verified **in CI** on the same tree, not locally -- the local
runner's hardcoded 900s cap is not meetable on the machine this was cut from.
No local simulation pass is claimed.

### Fixed
- **The game-over screen scrolled, and the way out was inside the scroll**
  (#1179). `> Press ENTER for Leaderboard` was line 32 of 32, 436px below the
  bottom of its own box -- the only advertised route to the board, on the one
  screen where you go looking for it. It is a **Leaderboard [ENTER]** button in
  the button row now. The screen was cut from 32 lines to 16 rather than merely
  enlarged, body text went 16pt -> 20pt, and two colours that failed WCAG AA on
  the panel ground (Compute at 2.23:1, Research at 3.61:1) were replaced. No
  scrollbar at any tested resolution from 1024x768 to 2560x1080.
- **The leaderboard screen opened on LOCAL** and only fetched the global board if
  you pressed a toggle (#1173). "Here are your four scores" reads as "there is no
  global board", which is what it was read as. It opens on global now.
- **Two different sources for one board key** (#1173). The global fetch keyed on
  `GameConfig.get_display_seed()` while the local view keyed on the board file
  being shown, and those two do diverge -- the seed dropdown changed one without
  the other. There is one source now, `_global_board_identity()`: the board on
  screen.
- **A player who never opted in, and a player who declined, both saw nothing at
  game over** (#1172, #1173). Both now get a standing readout saying where the
  score went and where to change it. It is a readout, not a prompt: no dialog,
  no re-nudge, and it does not opt anybody in.
- **A successful submission looked like nothing happening** (#1173). The
  confirmation was 12pt and appended below the button row, last line in the
  panel. It is 16pt and sits above the buttons.
- **Every remote failure claimed you were offline** (#1173). A rotated token
  (403), a moved endpoint (404) and a server fault (500) all rendered the same
  sentence, because the HTTP status was discarded. The status reaches the player
  now, and "offline" is reserved for a request that never got to a server. Every
  failure still says the score was kept locally.

### Added
- **In-game patch notes cover 0.12.0 onwards** (#1175), ending three releases
  where the What's New screen said nothing about what changed.
- **The release manifest publishes `league_seed`** from the version SSOT
  (#1175), so the website can read the board key instead of inferring it.

### Dev / tooling (no player-visible change)
- **Headless test runs were writing into live player data** (#1173). Godot
  derives `user://` from `config/name`, not the checkout path, so every worktree
  shared one profile and `run_godot_tests.py` passed no `env=`; a test run took a
  real 50-entry league board to 0. All four `subprocess.run` sites now pass an
  isolated `APPDATA` keyed by a hash of the checkout path. The property tests
  also stopped leaving ~1,300 board files behind per run.