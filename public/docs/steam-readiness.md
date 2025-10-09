# Steam Readiness (Website Frontend)

## Checklist
- [x] Press kit page (`/press/`): logo, screenshots, trailer link, factsheet
- [x] Store badges and CTA: Steam badge + link to store page
- [ ] Legal/Policy references: EULA, Privacy Policy, Support contact
- [ ] Age rating info (if applicable) and regional compliance notes
- [ ] Changelog and versioning surfaced (mapped to Steam releases)
- [x] Social links and community (Discord) present and consistent
- [ ] Analytics configured (privacy-preserving)
- [ ] Accessibility pass (A11y): ARIA, contrast, keyboard nav
- [ ] SEO: sitemap.xml, robots.txt, OpenGraph/Twitter cards

## Implementation Status
- **Download CTAs**: ✅ Updated to prioritize Steam with GitHub as fallback
- **Steam badges**: ✅ Implemented with Valve-compliant legal attribution
- **Configuration**: ✅ Steam store URL added to config.json

## Source of Truth
- Game code, assets, and canonical docs live in `PipFoweraker/pdoom1`.
- This site now links to Steam for downloads; GitHub releases available as fallback option.

## Future architecture
- Keep design tokens in main repo; sync into this site on release tags.
- Optional: auto-generate press kit from main repo metadata (images + factsheet JSON).
- Update Steam store URL placeholder with actual app ID once available.
