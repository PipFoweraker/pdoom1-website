---
title: "Manual Sync: v0.13.2"
version: "0.13.2"
release_date: "2026-07-31T07:53:59Z"
type: "game-release"
status: "stable"
download_url: "https://github.com/PipFoweraker/pdoom1/releases/tag/v0.13.2"
---

# Manual Sync: v0.13.2

**Version:** v0.13.2
**Release Date:** 2026-07-31T07:53:59Z
**Status:** Stable Release

## Download

- [Download Game](https://github.com/PipFoweraker/pdoom1/releases/tag/v0.13.2)
- [View Source Code](https://github.com/PipFoweraker/pdoom1/tree/v0.13.2)
- [Full Changelog](https://github.com/PipFoweraker/pdoom1/blob/main/CHANGELOG.md)

## Release Notes

League build. Ladder epoch **L3** -- this is a forking release: the effort
economy was rebuilt, so scores are not comparable with L2 boards.

### 2026-07-27 build day (rides the next version bump)

#### Added
- **The early game has a real first fifteen minutes** (#791, #811, #982): you
  start in a free bedroom/basement (2-hire cap), then choose one of three
  first offices -- a cheap-in/cheap-out co-working corner, a balanced
  second-floor walk-up, or a bigger university annex sublet -- each with its
  own deposit, monthly rent, desk count, lease term, and break fee. You're
  locked into the pick mechanically for now (moving costs are architected but
  not live yet). New scouting actions let you find your next hire, including
  a deliberately loud strategic-shitposting option.
- **Conference trips are a real commit, not a menu skip** (#468, #979): the
  Travel submenu can now send you to one of 3 shell conferences. Going costs
  real travel cash and drains all your remaining Attention for the trip; the
  world keeps running while you're away (events and developments still
  fire), and you come home to a single "while you were away" digest instead
  of a stack of missed-turn popups.
- **Publishing and safety-research actions now genuinely move the doom
  engine** (#971, #974): `publish_paper`'s alarm bump and `safety_research`'s
  absorption effect were silently wired to 0.0 since the doom-stream
  migration -- they read as working in the UI but did nothing. They're
  priced now and actually fire, along with `audit_safety`'s scrutiny effect
  and the lobbying/rival/opensource doom streams.
- **Four new office workers, with mood states** (#947, #969): a Black man
  with idle/working/stressed mood art plus a full 8-direction walk cycle, and
  three more fully-walking hires (wheelchair-accessible, glasses-and-badge,
  and hijab-wearing) join the office rotation.
- **Office floor groundwork**: a first-class render-layer grid replaces the
  sandbox's old string-keyed hack (#977) -- render-only, purely cosmetic for
  now; and dev-build performance logging gained mark/gauge instrumentation
  across save/load, scene transitions, and office-roster rebuilds (#973), in
  preparation for surfacing real load-time and scaling data later.

#### Fixed
- **Hire candidates could silently vanish** (#952, #960): if your cash
  dropped between queuing a hire and it executing later the same turn, the
  candidate was removed from the pool but never actually hired -- gone for
  good, with no message. Stranded hires now return to the pool (or a
  walk-away line if the pool had refilled), including self-healing existing
  saves.

#### Dev / data (no visible gameplay change yet)
- Typed reputation dimensions -- org / operator / employee -- landed
  additively behind `rep_for()`/`rep_dims()`; the legacy scalar
  `GameState.reputation` stays authoritative and is still what every
  existing write site touches (#975). Ships alongside a first governance-body
  roster (`godot/data/bodies.json`).
- Workstream substrate core -- the object model, backlog, per-person
  assignment, and topic-tagged effort accrual that the Attention-economy
  migration builds on -- landed with a `reported` vs `actual` progress seam
  for self-directed researchers (deterministic per-person optimism, no new
  RNG); nothing consumes `reported` yet (#981).
- Balance-key coverage guard test so a doom-stream key silently falling back
  to a call-site default can't ship unnoticed again (#974).
- ~500 art files (worker round 2, cat west-walk variants, prop re-base, tier-6
  diagonals) made durable from the day's generation runs, plus shared
  bulk-select/mass-tag triage tooling across the art review sheets (#965,
  #966, #972, #978).
- `ladder_version` bumped 2 -> 3 for the day's core/ changes.
- ADR-0018 drafted: render-only office doctrine (no spatial fact becomes a
  gameplay input) (#968).

---

### Added
- **Research Quality System** (#500): Rushed / Standard / Thorough quality toggle for research
  - **Rushed**: faster research, but accumulates technical debt and raises risk
  - **Standard**: baseline speed, neutral
  - **Thorough**: slower research, reduces doom/risk (safety-focused builds)
  - Feeds the hidden Risk Pool system (research integrity, capability overhang, financial exposure)
  - New `research_quality_selector.gd` UI; defaults to Standard and remembers last selection
  - Unit tests: `test_research_quality.gd`, `test_risk_system.gd`
- **Game-design documentation** (#500): `godot/docs/design/` -- `TWO_ACT_STRUCTURE.md`, `INTRO_CINEMATIC.md`, `TONE_AND_ART.md`
- **Scenario/Mod Hook System** (#483): Custom scenarios without code changes
  - Drop JSON files into `godot/data/scenarios/` to add new scenarios
  - Scenario selection dropdown in Custom Game setup screen
  - Support for overriding starting resources (money, compute, research, reputation, doom, etc.)
  - Support for custom events with trigger conditions and player choices
  - Support for custom start dates (year, month, day)
  - Three sample scenarios included:
    - **Bootstrap Mode**: Extra resources for learning ($500k, 200 compute)
    - **Crisis Mode**: Challenging start (2020, $150k, 65 doom)
    - **Sandbox Mode**: Unlimited resources for experimentation ($10M)
  - User scenarios supported in `user://scenarios/` directory
  - Complete documentation in `docs/SCENARIOS.md`

### Fixed
- **CI/CD pipeline restored** (#527, #530, #535): the daily Enhanced CI/CD pipeline had been failing for 10+ days and two workflows (`data-validation`, `dev-blog-automation`) failed at startup for months
  - Repaired PEP 701 nested-quote f-strings that broke on the Python 3.11 runner (valid only on 3.12+)
  - Added missing `pyyaml` dependency to the sync/cleanup stages
  - Fixed invalid workflow YAML (column-0 lines terminating `run:` block scalars -> 0s startup failures)
  - Fixed schema-validation check failing under AJV strict mode on `format: "uri"` (added `ajv-formats`)

### Technical
- **Python 3.11 baseline** (#527): authoritative `pyproject.toml` + CI syntax gate so modern-only syntax can't silently break CI; standardized workflow Python pins
- **Repo cleanup**: archived ~35 pygame-era debris files to `archive/legacy-pygame/`; removed duplicates; pruned 9 stale remote branches and 6 orphaned worktrees
- New files: `scenario_loader.gd`, `docs/SCENARIOS.md`, `godot/data/scenarios/*.json`
- Modified: `game_config.gd`, `game_manager.gd`, `pregame_setup.gd`, `pregame_setup.tscn`, `events.gd`

---