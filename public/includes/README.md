# Navigation System

The site has exactly ONE navigation. It lives in
[`/public/assets/js/navigation.js`](../assets/js/navigation.js), in the
`navigationHTML` template, and it is injected at runtime.

## Why there is no HTML include here any more

This directory used to hold `navigation.html`, described in its own docs as a
"static HTML template (reference only)". It was wired into **zero** pages, and
it had gone stale in the way an unused copy always does: it hardcoded
`v0.11.0` / `2025-12-07` in the version badge, so any page that had adopted it
would have asserted a two-releases-old version forever.

Two sources of truth for one component is how this site ended up with ten
divergent navs. It was deleted on 2026-07-28. `navigation.js` is the only
source; if you want to change the nav, change it there.

`docs/HTML_PAGE_TEMPLATE.md` used to instruct authors to *copy* the nav markup
into each new page. That instruction was the drift generator and has been
replaced with the recipe below.

## Adding the nav to a page

1. Put an **empty** header in the body:

   ```html
   <header>
       <!-- Navigation loaded by navigation.js -->
   </header>
   ```

   It must stay empty. `navigation.js` overwrites the header's contents at
   runtime, so anything you leave in there is dead markup that reads as live —
   `scripts/test-header-consistency.js` fails a page for exactly this.

2. Load the script at the **end of the body**:

   ```html
   <script src="/assets/js/navigation.js"></script>
   ```

3. That is it. The script ships its own styles (scoped to
   `header[data-nav-injected]`, every colour a `var()` with a fallback), so the
   nav is self-contained and does not need the host page to define
   `.nav-links` / `.dropdown` / `.logo-container` rules. If your page already
   has such rules only for its own nav, delete them.

`/css/site.css` is optional for the nav — helpful for the rest of the page, not
required by the component.

## What the nav contains

Read `navigationHTML` in `navigation.js` for the authoritative list. As of
2026-07-28:

- **Main links:** Game, Leaderboard, Stats, Risk Dashboard
- **Community ▾:** Issues & Feedback, Dev Blog, Updates, Cat Custodians, GitHub
- **Info ▾:** About, AI Safety Resources, Roadmap, Documentation, Press Kit

The Forum link is deliberately absent until `forum.pdoom1.com` has DNS and
HTTPS. The version badge ships **empty and hidden**; `updateNavVersion()` fills
it from `/data/version.json` and leaves it hidden if that fetch fails, so a
failure shows nothing rather than a stale version.

## Known divergence

`public/index.html` still carries its own static nav. It differs on purpose in
two ways that need a product call before it can be converted:

- it links **Events** (`/events/`, ~2,197 pages) — the shared nav does not;
- it has **Press Kit commented out** — the shared nav includes it.

Converting the homepage without resolving those would silently drop the Events
link and silently add Press Kit. See `docs/TECH_DEBT.md` B1.

## Features

- Current page highlighting (`aria-current="page"`)
- Click-to-open dropdowns, closed on outside click
- Responsive: stacks under 760px, dropdowns become static
- ARIA roles throughout (`menubar` / `menuitem` / `aria-haspopup`)
- Version badge fed from `/data/version.json`, silent on failure

## Files

- `/assets/js/navigation.js` — the nav: markup, styles, behaviour (active)
- `/css/site.css` — shared site styles (does not style the nav)
- `scripts/test-header-consistency.js` — enforces the contract above
