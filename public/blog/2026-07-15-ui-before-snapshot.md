---
title: "Where the site stands, before the refresh"
date: "2026-07-15"
tags: ["website", "ui", "design", "dev-notes"]
summary: "A deliberate 'before' snapshot of pdoom1.com at the start of a UI refresh - what's working (the Risk Dashboard), what reads as dated (blanket monospace, no shared layout spine), and the correctness bugs fixed the same day."
commit: "426e7b6"
---
# Where the site stands, before the refresh

**Date**: 2026-07-15
**Tags**: [website, ui, design, dev-notes]

Keeping a deliberate "before" snapshot of pdoom1.com, because a UI refresh is starting and it helps to be able to point back at the starting line. This is an honest look at what's working, what isn't, and why.

## The pages as they are today

The homepage — hero, live stats, and the feature cards:

![p(Doom)1 homepage: hero, download buttons, live game stats and about section](/assets/blog/2026-07-15-ui-snapshot/homepage-hero-stats-web.webp)

The events timeline — 1,194 real AI-safety events driving the game:

![Game Events Timeline with search, filters and event table](/assets/blog/2026-07-15-ui-snapshot/events-timeline-web.webp)

Game statistics and the expanded navigation:

![Game Statistics cards and expanded site navigation](/assets/blog/2026-07-15-ui-snapshot/homepage-stats-nav-web.webp)

And the Risk Dashboard — live p(doom) modelling:

![P(Doom) Dashboard: compute-vs-risk chart, simulation controls, prediction markets](/assets/blog/2026-07-15-ui-snapshot/risk-dashboard-web.webp)

## What's genuinely working

The **Risk Dashboard** is the strongest thing here. Dense, live, and the terminal aesthetic earns its keep because the content actually *is* a data terminal — compute curves, simulation sliders, prediction-market pulls. When the theme matches the content, it works.

The **hero background** does its job too — it sets a tone the rest of the site can grow into.

## What reads as dated, and why

Being blunt about the starting line:

- **Blanket monospace.** The terminal font is on everything — headings, prose, buttons — with no typographic hierarchy. It works on the dashboard; it flattens everything else.
- **No shared layout spine.** Each page carries its own inline styling, and the navigation quietly drifts between pages. A shared header/nav component exists in the codebase but isn't wired in yet — so the pages don't agree with each other.
- **Broken states that had shipped.** Three "Loading…" cards frozen forever, a `NaN%` on the dashboard, and a mangled arrow (`→` rendered as mojibake) in two event pages. These read as *unfinished* more than *dated* — and they're fixed as of today.

## Fixed alongside this snapshot

The correctness bugs above went out today: the mojibake is repaired at the data source, the dashboard guards against missing market data, and the stuck status cards now resolve to real values instead of hanging. The issue tracker also got a cleanup — 35 auto-generated "rollover complete" log entries closed out so the real backlog is visible again.

The aesthetic work — type hierarchy, a real shared layout, retiring a couple of vanity metrics — is the next stretch. This snapshot is the baseline to measure it against.
