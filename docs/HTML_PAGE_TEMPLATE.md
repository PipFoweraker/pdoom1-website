# HTML Page Template for p(Doom)1 Website

## Standard Page Structure

All HTML pages on the pdoom1.com website should follow this template to ensure consistent analytics tracking, navigation, and styling.

### Minimal Template

```html
<!DOCTYPE html>
<html lang="en-AU">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>Page Title - p(Doom)1</title>
	<link rel="canonical" href="https://pdoom1.com/page-path/" />
	<meta name="description" content="Page description for SEO" />

	<!-- Plausible Analytics - Privacy-first, self-hosted analytics -->
	<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>

	<style>
		/* Page-specific styles here */
	</style>
</head>
<body>
	<!-- Leave this EMPTY. navigation.js injects the nav and its styles. -->
	<header>
		<!-- Navigation loaded by navigation.js -->
	</header>

	<!-- Page content -->
	<main>
		<h1>Page Title</h1>
		<!-- Content here -->
	</main>

	<footer>
		<!-- Footer content -->
	</footer>

	<script src="/assets/js/navigation.js"></script>
	<script>
		// Page-specific JavaScript
	</script>
</body>
</html>
```

## Required Analytics Script

**IMPORTANT**: Every HTML page MUST include this script in the `<head>` section:

```html
<!-- Plausible Analytics - Privacy-first, self-hosted analytics -->
<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>
```

### Placement
- Add AFTER meta tags and preconnect links
- Add BEFORE `<style>` tag
- This ensures analytics loads without blocking page rendering

## Tracking Custom Events

For tracking game downloads or other custom events:

```javascript
// Track a download event
plausible('Download', {
	props: {
		version: '0.10.2',
		platform: 'Windows'
	}
});

// Track button clicks
document.getElementById('download-btn').addEventListener('click', function() {
	plausible('Download', {props: {version: 'latest', platform: 'Windows'}});
});
```

### Common Events to Track
- `Download` - Game downloads (with version/platform props)
- `Leaderboard View` - Leaderboard page visits
- `Forum Click` - Forum link clicks
- `External Link` - Outbound links to GitHub, Steam, etc.

## Navigation Component

**Do NOT copy nav markup into a page.** This section used to say "copy the
navigation from `/public/includes/navigation.html`", and that instruction is
what produced ten divergent navs across the hand-written pages (TECH_DEBT B1).
A copy cannot be kept in step; it can only drift. `navigation.html` was deleted
on 2026-07-28.

The nav is a runtime-injected component. Two lines adopt it:

```html
<header>
	<!-- Navigation loaded by navigation.js -->
</header>
...
<script src="/assets/js/navigation.js"></script>
```

The header must stay **empty** — `navigation.js` overwrites its contents, so
markup left inside is dead but reads as live. The script also ships its own
styles, so the host page does not need `.nav-links` / `.dropdown` /
`.logo-container` rules of its own.

To change the nav for the whole site, edit `navigationHTML` in
`/public/assets/js/navigation.js`. Full recipe and rationale:
`public/includes/README.md`. Enforcement:
`node scripts/test-header-consistency.js`.

## SEO Best Practices

1. **Title Format**: `Page Name - p(Doom)1`
2. **Canonical URL**: Always include `<link rel="canonical">`
3. **Meta Description**: 150-160 characters, descriptive
4. **Open Graph**: Add for social media sharing:
   ```html
   <meta property="og:title" content="Page Title" />
   <meta property="og:description" content="Description" />
   <meta property="og:url" content="https://pdoom1.com/path/" />
   <meta property="og:image" content="https://pdoom1.com/assets/pdoom_logo_1.png" />
   ```

## Privacy Considerations

- Plausible Analytics is GDPR compliant (no cookies, IP anonymization)
- No personal data collection
- No third-party trackers
- Respects Do Not Track (DNT) headers

## Development Workflow

When creating a new page:

1. Copy this template
2. Update title, meta tags, canonical URL
3. **Ensure Plausible script is present in `<head>`**
4. Add the empty `<header>` and the `navigation.js` script tag (see above)
5. Build page content
6. Test analytics:
   - Visit https://analytics.pdoom1.com
   - Check real-time dashboard
   - Verify page view is tracked

## Automated Checking

To verify all pages have analytics:

```bash
# Check for analytics script in all HTML files
grep -r "analytics.pdoom1.com" public/**/*.html

# Find pages missing analytics
find public -name "*.html" ! -path "*/includes/*" -exec grep -L "analytics.pdoom1.com" {} \;
```

## Future Automation

Consider implementing:
- Build-time injection of analytics script
- Template engine (e.g., Jinja2, Handlebars) for shared components
- Pre-commit hook to verify analytics script presence

---

**Last Updated**: 2025-11-10
**Maintained by**: Development Team
