# Style & Design Guide (website)

Purpose: document the website's design tokens and how they map to the main game's design system.

## Tokens
- Source: `public/design/tokens.json` at runtime
- Applied via inline script in `public/index.html` (loadTokens)
- Token groups:
  - colors: bgPrimary, textPrimary, accentPrimary, etc.
  - shape: radii, borderWidth, shadowButton
  - motion: durationFast, durationBase, easing

## Integration with `pdoom1` main repo
- Preferred source: keep a canonical token JSON in the main repo
- Options to sync:
  1) Manual copy during releases
  2) GitHub Action in main repo commits tokens to this repo
  3) Fetch tokens.json at build time (Netlify build hook) and write to `public/design/tokens.json`

## Components
- Pure HTML/CSS with small inline JS; monospace aesthetic
- Cards, grids, CTA buttons, form controls

## Accessibility
- Ensure semantic headings and labels
- Focus states with visible outlines
- Contrast ratio >= 4.5:1

## Content surfaces
- Blog at `/blog/` from `public/data/blog.json`
- Changelog at `/changelog/` from `public/data/changes.json`

## Next
- Document color usage and states
- Map tokens to game UI atoms for consistency
