# Website roadmap

This roadmap is a living document. It summarizes major goals for the **website** and feeds the GitHub Issues backlog for execution. It is organized by status rather than version number to avoid confusion.

> **Versioning note:** The *game* (`PipFoweraker/pdoom1`) is the source of truth for gameplay and releases — its current release is **v0.11.0**. This site tracks that release automatically via `public/data/version.json`. The milestones below describe *website* work and are independent of the game's version.

## Shipped
- **Weekly League system** — deterministic seeding, standings UI, archives, and automated weekly rollover.
- **Auto-deployment & monitoring** — pushes to `main` deploy to production (DreamHost) via GitHub Actions; scheduled health checks and status data.
- **Accessibility** — WCAG AA pass (ARIA, contrast, keyboard navigation).
- **AI Safety resource integration** — auto-generated timeline/event pages sourced from the `pdoom-data` repository.
- **Press kit** — factsheet, assets, and legal attribution page.
- **Core SEO scaffolding** — `sitemap.xml`, `robots.txt`, OpenGraph tags.

## In progress
- **Game ↔ API score submission** — automatic score submission from the game client to the production API, and standing up that API/database ([#64](https://github.com/PipFoweraker/pdoom1-website/issues/64), [#65](https://github.com/PipFoweraker/pdoom1-website/issues/65), [#66](https://github.com/PipFoweraker/pdoom1-website/issues/66)). *API and database are coded but not yet deployed; the website still reads static JSON.*
- **Community forum** — self-hosted forum ([#60](https://github.com/PipFoweraker/pdoom1-website/issues/60)) plus GitHub→forum posting ([#63](https://github.com/PipFoweraker/pdoom1-website/issues/63)). *Running, but forum links are hidden on the site until it has a proper HTTPS domain (`forum.pdoom1.com`).*
- **Analytics extraction** — privacy-preserving server-log analytics pipeline ([#61](https://github.com/PipFoweraker/pdoom1-website/issues/61)).

## Planned
- **Grant-readiness content** — donor landing ([#78](https://github.com/PipFoweraker/pdoom1-website/issues/78)), budget ([#84](https://github.com/PipFoweraker/pdoom1-website/issues/84)), team & hiring ([#83](https://github.com/PipFoweraker/pdoom1-website/issues/83)), public roadmap page ([#81](https://github.com/PipFoweraker/pdoom1-website/issues/81)), safety & responsibility statement ([#82](https://github.com/PipFoweraker/pdoom1-website/issues/82)), metrics ([#85](https://github.com/PipFoweraker/pdoom1-website/issues/85)), testimonials ([#86](https://github.com/PipFoweraker/pdoom1-website/issues/86)).
- **Steam launch** — swap the "Coming to Steam" placeholders to the live store link and update OpenGraph/CTAs when the store page is live ([#17](https://github.com/PipFoweraker/pdoom1-website/issues/17)).

## Later
- Newsletter opt-in (double opt-in).
- Localization scaffolding.

## Notes
- The source of truth for game code and the design system is the `PipFoweraker/pdoom1` repo. This site links there for downloads until the Steam launch.

- Forward cadence note (2026-07-21): league/content operations move to a MONTHLY cycle; weekly output is limited to generated challenge seeds. See the game roadmap.
