# P(Doom) Dashboard — data-feed plan

The `/dashboard/` page was a contributor's side-project (a demo for a data aggregator they
were building; may not be picked back up). It hardcodes ~30 real-world AI-landscape "facts"
(model names, training FLOPS, p(doom) %, expert consensus, stock tickers, regional compute,
safety-investment $) and frames them as *live*. They have no source and silently rot.

## The finding that reframes it

I scouted **pdoom-data** and the **game** for backing data. Result:

- **pdoom-data** is an AI-safety **events** data lake — 1,194 timeline events (year, category,
  `impacts`, `rarity`, `pdoom_impact`, sources). It has **no** compute/FLOPS series, **no**
  expert-consensus dataset, **no** p(doom) time series, **no** regional-compute or lab data.
  Funding has a *schema* but only a 3-record fake placeholder. Serving is "planned static JSON",
  not built. (It's essentially the same corpus as the website's `events.json`.)
- The **game** owns "baseline runs" / the baseline p(doom) trajectory (in the game repo, synced
  into `version.json.game_stats.baseline_doom_percent` = 23% today) and, via the frozen score API,
  real run/score outcomes.

**So the dashboard's real-world framing is unbacked everywhere.** The fix is Pip's instinct:
stop pretending to be a real-world AI tracker (data nobody owns) and show **the game's own
world** (data we do own) — AI-safety events, the game's baseline p(doom), and real run/score
distributions. Same visual language, real + self-healing data.

## Source map (what's real TODAY vs later)

| Dashboard section (current) | Reframe to | Source | When |
|---|---|---|---|
| Compute-vs-risk chart (fabricated GPT FLOPS) | **AI-safety events timeline** (events/year, by category, pdoom_impact) | `events.json` (already on site, synced from pdoom-data) | **now** |
| P(doom) base / 2027 projection (hardcoded) | **Game baseline p(doom)** + trajectory | `version.json.game_stats` now; richer baseline-run export later | now / later |
| Expert consensus, stock tickers, regional compute, safety-$ | **Retire or mark "illustrative"** (no source) | — (external feeds only: Epoch AI, AI Impacts) | drop now |
| Prediction markets (Manifold) | keep — already live | Manifold API | live |
| (new) Run outcomes / score distribution | **Real player runs** (doom_integral, turns) | frozen score API (`schemas/leaderboard-api`) | when API live |
| (new) Funding by year | pdoom-data funding | `funding_data_v1` — real data TBD (placeholder today) | later |

## Phased plan

**Phase 0 — now, website-only (no game/pdoom-data changes needed):**
- Repoint the chart to `events.json`: aggregate events by year → an AI-safety-events timeline
  (count + summed `pdoom_impact` by category). This is real, on-theme, and already synced.
- Wire the p(doom) base tile to `version.json.game_stats.baseline_doom_percent` (stop hardcoding).
- **Retire the unbacked tickers** (stocks, GPT-5 FLOPS annotations, expert-consensus %, regional
  compute, 2027 projection) or move them behind an explicit "illustrative / not live" label.
  Keep Manifold (live).

**Phase 1 — game handoff (when the build's pushed):** the game exports **baseline-run telemetry**
(the baseline p(doom) trajectory + distribution of a reference run) as a small JSON to a known
location, contract defined alongside the score contract. Dashboard reads it → "the game's actual
baseline runs" (Pip's phrasing) become the centre of the page.

**Phase 2 — score API live:** add a real run-outcomes panel from the frozen score API
(distribution of `doom_integral` / turns across submitted runs).

**Phase 3 — pdoom-data public API:** when pdoom-data ships its planned static-JSON read surface,
consume events/funding directly from it instead of the website's synced copy; add funding-by-year
once real grant data exists.

## Build note

If **Fable** (or any rebuild) takes this on: this doc is the data map to build against. The rule
that keeps it from rotting again — **every number on the page must resolve to a source in the
table above (game data, pdoom-data, or a live external API), or be explicitly labelled
illustrative.** No hardcoded facts presented as live. Reconfigurable per patch, as Pip wants.

## Immediate low-regret step available now
Phase 0 is pure website work (events.json + version.json already exist). It converts the most
visible fabricated element — the compute-vs-risk chart — into a real AI-safety-events timeline,
and removes the tickers that will embarrass on any AI-landscape change. Hold for the design-coherence
pass if you'd rather reshape the whole page at once.
