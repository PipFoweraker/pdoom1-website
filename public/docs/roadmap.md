# Roadmap

Where P(Doom)1 is headed, and how firm each part of it is.

This page is a projection. The source of truth is the game repo:
[docs/ROADMAP.md](https://github.com/PipFoweraker/pdoom1/blob/main/docs/ROADMAP.md)
and [docs/RELEASE_NOMENCLATURE.md](https://github.com/PipFoweraker/pdoom1/blob/main/docs/RELEASE_NOMENCLATURE.md).
Nothing on this page is a commitment the game repo has not already made; where
the two disagree, the game repo is right. Day-to-day execution lives on the
[GitHub milestones](https://github.com/PipFoweraker/pdoom1/milestones).
Website work has its own page: [Website roadmap](/docs/website-roadmap.md).

## How the game evolves

Since 25 July 2026 the game moves on a **monthly rhythm**:

- **Each month is a Theme.** One named direction -- a new mechanic, plus
  quality-of-life and balance work -- shipped on the first Friday of the month
  as a minor version bump.
- **A Theme forks the leaderboard.** Because the rules change, a new epoch
  starts and scores begin fresh. Older runs stay in the archive; they simply
  stop being comparable to new ones.
- **Every Friday brings a new seed.** A fresh board on unchanged rules -- new
  puzzle, same game, same epoch.
- **Small fixes ship any time**, as patches, and never fork the board.

Quarterly planning has been retired. It was slowing the real pace down, and a
version number now means "which month's Theme is this", not "which quarter".

Above that rhythm sit two **Big Milestones**. Each spans several monthly Themes
and completes when it is done rather than on a fixed date. They exist to make
the shape of the project legible without pretending a solo developer can
date-lock a quarter.

## The two big milestones

**First Contact** -- targeting the end of Q3 2026. Everything the game needs
before the doors open properly: first-launch help and onboarding, the share loop
(copy your result and your seed so somebody can try to beat it), the remote
leaderboard switched on and hardened, and the monthly league running for real.

**Rivals & News** -- targeting the end of Q4 2026. Rival labs stop being
background numbers and become a surface you play against: an intel panel, a
visible capability race, poaching, and a News channel that reports the world
back to you.

Both are named arcs, not release dates.

## Month by month

Theme names beyond the shipped one are **provisional** -- the game repo marks
them so, and two of the six months are not named at all yet.

| Ships | Version | Theme | What it adds | How firm |
|---|---|---|---|---|
| Jul 2026 | v0.13 | Launch epoch | hiring pipeline, narrative cold-open, office visuals, the league live, a legibility and stability pass | **Shipped** |
| 7 Aug 2026 | v0.14 | "Per-tick & People" *(provisional name)* | per-tick resolution; people and money cohere -- roles, salary, managers, payroll | Grounded in design that already exists |
| 4 Sep 2026 | v0.15 | *not yet named* | onboarding as a mechanic rather than a tutorial; public-alpha hardening -- leaderboard, install ping, bug reporter, test builds | Grounded in design that already exists |
| 2 Oct 2026 | v0.16 | "Sightings" *(provisional name)* | rivals begin to appear -- procedural presence and developments; a wider event pool drawn from the open data set | Direction to steer, not a commitment |
| 6 Nov 2026 | v0.17 | "The World Shoots Back" *(provisional name)* | the News feedline, plus rival pressure in the midgame: poaching, litigation, funding attacks | Direction to steer, not a commitment |
| 4 Dec 2026 | v0.18 | *not yet named* | rivals confront you directly; News v1; a voice pass over generic event text | Direction to steer, not a commitment |

The "how firm" column is the game repo's own confidence note, not a softening we
added: the next two months rest on design that already exists, and everything
from October onward is expected to be reshaped by design workshops before it is
built. The dates follow the first-Friday rule, so they move when a month moves.

## Further out -- wanted, not scheduled

Carried forward with no dates attached, deliberately: a player-facing Liability
Ledger; a content-pool ladder and a monthly world-update metabolism that feeds
real-world AI events into the game; a damper-economy beat; and then the beta and
Steam "coming soon" beat -- store page and wishlists, press kit, character
creation, and a full balance calibration pass.

## The release ladder

1. **Alpha -- we are here.** The game is free and you can download it from this
   site today. The game repo still calls this the *private*
   (friends-and-family) alpha, because what makes the alpha "public" is
   readiness rather than availability: onboarding that works without somebody
   sitting next to you, a hardened leaderboard, and a distribution channel
   chosen. That readiness work is the First Contact milestone.
2. **Public alpha -- free.** How it will be distributed is genuinely not
   decided: a direct download from this site, a storefront page, or a playable
   web build. That decision is owed before the public alpha ships. Anyone who
   tells you it is settled is ahead of the facts.
3. **Beta -- a Steam "coming soon" page.** Wishlists start compounding while the
   mid and late game get built in.
4. **1.0.**

This page does not restate which build is current, so that it cannot go stale --
the download buttons on the [home page](/) always point at the latest release.

## What all of this is sized to

One developer at roughly one to two focused days a week, plus agent-assisted
increments. Every date above is sized to that cadence, not to burst weeks. They
exist to be steered, and to make the shape of the work legible -- not as
marketing.
