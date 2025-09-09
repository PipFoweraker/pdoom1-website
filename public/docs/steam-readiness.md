# Steam Readiness (Website Frontend)

## Checklist
- Press kit page (`/press/`): logo, screenshots, trailer link, factsheet
- Store badges and CTA: Steam badge + link to store page
- Legal/Policy references: EULA, Privacy Policy, Support contact
- Age rating info (if applicable) and regional compliance notes
- Changelog and versioning surfaced (mapped to Steam releases)
- Social links and community (Discord) present and consistent
- Analytics configured (privacy-preserving)
- Accessibility pass (A11y): ARIA, contrast, keyboard nav
- SEO: sitemap.xml, robots.txt, OpenGraph/Twitter cards

## Source of Truth
- Game code, assets, and canonical docs live in `PipFoweraker/pdoom1`.
- This site links to Steam for downloads once live; until then, link to the main repo releases.

## Future architecture
- Keep design tokens in main repo; sync into this site on release tags.
- Optional: auto-generate press kit from main repo metadata (images + factsheet JSON).
