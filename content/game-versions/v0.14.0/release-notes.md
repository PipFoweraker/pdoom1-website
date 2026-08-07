---
title: "Manual Sync: v0.14.0"
version: "0.14.0"
release_date: "2026-08-07T12:53:17Z"
type: "game-release"
status: "stable"
download_url: "https://github.com/PipFoweraker/pdoom1/releases/tag/v0.14.0"
---

# Manual Sync: v0.14.0

**Version:** v0.14.0
**Release Date:** 2026-08-07T12:53:17Z
**Status:** Stable Release

## Download

- [Download Game](https://github.com/PipFoweraker/pdoom1/releases/tag/v0.14.0)
- [View Source Code](https://github.com/PipFoweraker/pdoom1/tree/v0.14.0)
- [Full Changelog](https://github.com/PipFoweraker/pdoom1/blob/main/CHANGELOG.md)

## Release Notes

Ladder epoch **L3 -> L4** -- this is a FORKING release. The historical event deck
was retimed to one-turn-one-month and the ruled promotions were applied (#1137),
which changes which events fire on a given seed, so scores are not comparable
with L3 boards. L3 entries stay valid and visible under L3; new runs land on L4.
Featured league seed rolls to `weekly-2026-w32`.

Every entry below is tied to a commit merged between `v0.13.2` and this release.

### Added
- **Pick the music from the pause menu** (#802, #1146) -- track selection while
  you play, not only in Settings.
- **A credits screen you can actually reach** (#1161).
- **Month review shows what CHANGED**, and SPACE opens it (#1100).
- **Settings rebuilt as a front card plus an operations board** (#1096, #1103).
- **One-time "claim a name" prompt before your first upload**, plus a lab-name
  generator (#957, #1063, #1133) -- a public board of identical
  "Researcher -- AI Safety Lab" rows is one nobody can find themselves on.
- **Epoch-aware update check** reads `release_manifest.json`; the manifest now
  carries the ladder epoch and sha256 anchors (#1110).

### Changed
- **Historical event deck retimed to one turn = one month**, with a timing dial
  and the ruled promotions applied (#1111, #1125, #1137). *This is the change
  that forks the ladder.*
- **Difficulty lock enforced where the value is CONSUMED**, not on one screen,
  and Alpha Tools now set a sticky unranked flag (#1058, #1060, #1084, #1104).
- **One table for choice keys, one door per panel** -- keyboard and navigation
  unified (#565, #567, #575, #602, #1120).
- **The last player-facing "AP" is gone**, and one number format is ruled across
  the UI (#1073, #1087, #1116).
- **Copy stops teaching a different game** -- the guide, the win condition and
  the cold open now describe what the game actually does (#1136).
- **Turn-1 hand fits above the fold; Fundraising is tile 1** (#1130).
- **The debug event-trigger is deleted, not guarded** (#1134, #1143).
- **A third-party endpoint and its unreachable fetch path were removed** (#1101,
  #1105).
- **Contact addresses redacted from the bundled historical events** (#1106).
- **The pause menu grows into its text, not into padding** (#1155).

### Fixed
- **The achievement toast rendered as a giant purple rectangle** in v0.13.2
  (#1083).
- **The office cat was a magenta checkerboard in every shipped build** -- not one
  flaky JPG (#796, #1080).
- **The server rack painted over the feed and the staff were oversized** (#793,
  #1081).
- **The public build wore a stale, clipped "DEV BUILD" banner** (#1067, #1079).
- **A failed global leaderboard fetch is now VISIBLE**, and players are warned
  about SmartScreen (#1126, #1127).
- **Music was too loud and the wrong track; Graphics Settings was an empty
  header** (#1095).
- **Percent tie direction pinned**, so doom reads the same on every platform.
- **Release export filename derives from the preset**, and the Linux alias is
  published (#1068, #1072, #1099).
- **The backslash dev key returns in release builds** (dev gates split) (#1129).

### Dev / tooling (no player-visible change)
- CI exports now route through `build_release.py`'s freshness proof (#1069,
  #1114); the GDScript syntax gate COMPILES every `.gd` rather than only what
  boot reaches (#1082, #1119).
- New instruments: `find_dead_code.py` (#1117, #1124), an action-taxonomy checker
  (#798, #1139), a generated `docs/TOOLS.md` (#1123), a generated
  `decisions/README.md` (#1108).
- Dead paths retired; what remains is LOUD (#1115, #1118).
- Art pipeline: promotion map unblocks 605 then all 327 remaining approved assets
  (#1093, #1107, #1122); 2,713 human verdicts made durable; the 2026-08-07 art
  night fired 652 images (#1158); art-review gallery keyboard repaired (#1162).
- Issue triage across all 201 open issues plus a 7-fix drive-by batch (#1144),
  and a pre-close mining pass (#1153).
- ADR-0019 (the pack is a function of declared demand), a phase-critical state
  audit (#1145), and a claims audit of the project's own output (#1160).