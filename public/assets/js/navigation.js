/**
 * Standard Navigation Loader for p(Doom)1 Website
 * Loads consistent navigation across all pages
 */

(function() {
	'use strict';

	// ---- The funding campaign window ---------------------------------------
	//
	// p(Doom)1 is raising money on Manifund and the campaign CLOSES 2026-09-09.
	// Source: pdoom1/docs/copy/budget.json `published` ({"closes": "2026-09-09"}),
	// which manifund.org's own project page agrees with -- it renders
	// "Closes September 9th, 2026".
	//
	// After that date a "fund the game" call to action is an invitation to a
	// thing that has stopped happening, which is worse than no link at all. The
	// obvious fix -- write the link in and remember to take it out -- is the one
	// that fails, because nobody remembers. pdoom1-website#194 sat unread for 25
	// days; a deletion scheduled for one specific Wednesday will do no better.
	//
	// So the link is not markup somebody has to remove. It EXPIRES:
	//   * the nav entry below is injected ONLY while campaignIsOpen() is true;
	//   * any element on any page carrying `data-campaign-window` is REMOVED
	//     from the DOM once campaignIsOpen() is false.
	// Removed, not hidden: `display:none` still answers Ctrl-F, still reaches a
	// screen reader, and still shows up in a "view source". A dead campaign
	// should be gone, not quiet.
	//
	// WHY THE CUTOFF ERRS LATE. CAMPAIGN_CLOSES is the END of 2026-09-09 in UTC.
	// Manifund's close is recorded as a bare date with no timezone, so the exact
	// closing instant is UNKNOWN to this file. Of the two available mistakes --
	// the link outliving the campaign by some hours, or the link vanishing while
	// people can still pledge -- the second costs money and the first does not,
	// so this picks the first deliberately. Visitor clock skew moves this by
	// minutes, not days, and a visitor with a badly wrong clock is not a case
	// worth a network call to fix.
	//
	// TO END IT EARLY, OR AFTER: set CAMPAIGN_CLOSES to a past date. That alone
	// takes down every campaign link on every page that loads this script. To
	// remove it for good, delete this block, the CAMPAIGN_SLOT line in
	// navigationHTML, the .nav-fund rules in navigationCSS, and grep the repo
	// for `data-campaign-window`.
	const CAMPAIGN_URL = 'https://manifund.org/projects/fund-development-of-pdoom1';
	const CAMPAIGN_CLOSES = Date.UTC(2026, 8, 10, 0, 0, 0);  // month is 0-based: 8 = September

	function campaignIsOpen() {
		return Date.now() < CAMPAIGN_CLOSES;
	}

	// utm_medium distinguishes the nav link from the homepage band, so Manifund's
	// referrer data can say WHICH of the two a backer actually used. Kept on the
	// site side rather than baked into CAMPAIGN_URL because the band tags itself.
	const campaignNavItem =
		'<li role="none" data-campaign-window>' +
		'<a class="nav-fund" href="' + CAMPAIGN_URL +
		'?utm_source=pdoom1.com&amp;utm_medium=nav&amp;utm_campaign=manifund-2026-09"' +
		' role="menuitem" target="_blank" rel="noopener">Fund the game</a></li>';

	// Runs on EVERY page that loads this script, whether or not the nav is
	// injected -- a page with its own hand-written nav still gets its
	// data-campaign-window elements cleaned up. Defensive about parentNode
	// because this also runs under the DOM stub in scripts/test-navigation.js.
	function applyCampaignWindow() {
		if (campaignIsOpen()) return;
		const stale = document.querySelectorAll('[data-campaign-window]');
		for (let i = 0; i < stale.length; i++) {
			if (stale[i] && stale[i].parentNode) {
				stale[i].parentNode.removeChild(stale[i]);
			}
		}
	}

	const navigationHTML = `
		<nav role="navigation" aria-label="Main navigation">
			<div class="logo-container">
				<!-- The site byline, same wording as the homepage's own nav
				     (public/index.html) and the other hand-written navs that
				     still carry it. This markup was missing while the CSS rule
				     for it below was already here -- an accidental drop, not a
				     decision, so the injected nav rendered without the credit
				     that every static nav shows. -->
				<div class="designer-credit">Pip Foweraker's</div>
				<a href="/" class="logo" aria-label="p(Doom)1 home">p(Doom)1</a>
				<!-- Deliberately empty: updateNavVersion() fills these from
				     /data/version.json. A hardcoded version/date here would keep
				     asserting a stale release whenever that fetch fails. -->
				<span class="version-badge" id="versionBadge" hidden style="display:none">
					<span class="version-number" id="versionNumber"></span>
					<span id="versionDate"></span>
				</span>
			</div>
			<ul class="nav-links" role="menubar">
				<li role="none"><a href="/" role="menuitem">Game</a></li>
				<li role="none"><a href="/leaderboard/" role="menuitem">Leaderboard</a></li>
				<li role="none"><a href="/game-stats/" role="menuitem">Stats</a></li>
				<li role="none"><a href="/dashboard/" role="menuitem">Risk Dashboard</a></li>
				<!-- Forum link hidden until forum.pdoom1.com (DNS + HTTPS) is live -->
				<li role="none" class="dropdown">
					<a href="#" role="menuitem" aria-haspopup="true" aria-expanded="false" class="dropdown-toggle">Community ▾</a>
					<ul class="dropdown-menu" role="menu">
						<!-- /bug-report/ is the ONLY zero-account path on the site that
						     actually delivers: it POSTs to bug-submit.php, which emails
						     team@pdoom1.com. It was linked from nowhere in the nav until
						     2026-08-11, so the one working contact route was unreachable
						     unless you already knew the URL. Labelled for a general
						     visitor, not "Report a Bug" -- most first-stranger contact is
						     not a bug report, and a bug-only label turns them away. -->
						<li role="none"><a href="/bug-report/" role="menuitem">Contact / Feedback</a></li>
						<li role="none"><a href="/issues/" role="menuitem">Issues & Feedback</a></li>
						<li role="none"><a href="/blog/" role="menuitem">Dev Blog</a></li>
						<li role="none"><a href="/game-changelog/" role="menuitem">Updates</a></li>
						<li role="none"><a href="/cats/" role="menuitem">Cat Custodians</a></li>
						<li role="none"><a href="https://github.com/PipFoweraker/pdoom1" role="menuitem" target="_blank" rel="noopener">GitHub</a></li>
					</ul>
				</li>
				<li role="none" class="dropdown">
					<a href="#" role="menuitem" aria-haspopup="true" aria-expanded="false" class="dropdown-toggle">Info ▾</a>
					<ul class="dropdown-menu" role="menu">
						<li role="none"><a href="/about/" role="menuitem">About</a></li>
						<!--
							"Site Metrics", not "Metrics": the main bar already has "Stats",
							which is /game-stats/ and is about the GAME. This one is the
							website's own traffic. Two links both called some form of
							"stats" a few pixels apart is how a reader ends up on the wrong
							page and concludes the numbers are wrong.
						-->
						<li role="none"><a href="/metrics/" role="menuitem">Site Metrics</a></li>
						<li role="none"><a href="/resources/" role="menuitem">AI Safety Resources</a></li>
						<li role="none"><a href="/events/" role="menuitem">AI Safety Timeline</a></li>
						<li role="none"><a href="/docs/roadmap/" role="menuitem">Roadmap</a></li>
						<li role="none"><a href="/docs/" role="menuitem">Documentation</a></li>
						<li role="none"><a href="/press/" role="menuitem">Press Kit</a></li>
					</ul>
				</li>
				<!--CAMPAIGN_SLOT-->
			</ul>
		</nav>
	`;

	// Styles for the injected nav.
	//
	// This script used to inject markup only, and relied on each host page
	// having its own .nav-links / .logo-container / .dropdown rules. Pages that
	// did not (the blog, for one) rendered the nav as an unstyled block stack --
	// a tall column of links in the top-left corner taking up most of the fold.
	//
	// Shipping the styles here makes the component self-contained, so ANY page
	// can adopt it by adding an empty <header></header> and this script. That is
	// the migration path off the ten divergent hand-copied navs.
	//
	// Scoped under [data-nav-injected] so it can never restyle a page that has
	// its own nav, and every colour goes through a var() with a fallback so it
	// works on pages that define no design tokens at all.
	const navigationCSS = `
		header[data-nav-injected] {
			background: var(--bg-secondary, #1C1917);
			border-bottom: 2px solid var(--accent-primary, #F6A800);
			padding: 0.4rem 0;
		}
		header[data-nav-injected] nav {
			max-width: 1200px; margin: 0 auto; padding: 0 1rem;
			display: flex; justify-content: space-between; align-items: center;
			gap: 0.5rem; flex-wrap: wrap;
		}
		header[data-nav-injected] .logo-container {
			display: flex; flex-direction: row; align-items: center;
			gap: 0.4rem; flex-shrink: 0;
		}
		header[data-nav-injected] .designer-credit {
			font-size: 0.75rem; color: var(--text-muted, #A79E92);
			letter-spacing: 0.3px; white-space: nowrap;
		}
		header[data-nav-injected] .logo {
			font-size: 1.3rem; font-weight: bold;
			color: var(--accent-primary, #F6A800);
			text-decoration: none; white-space: nowrap;
		}
		header[data-nav-injected] .nav-links {
			display: flex; gap: 0.6rem; list-style: none;
			flex-wrap: wrap; align-items: center; margin: 0; padding: 0;
		}
		header[data-nav-injected] .nav-links > li { margin: 0; }
		header[data-nav-injected] .nav-links a {
			color: var(--text-secondary, #CFC7BB); text-decoration: none;
			padding: 0.3rem 0.6rem; border: 1px solid transparent;
			border-radius: 4px; white-space: nowrap; display: inline-block;
		}
		header[data-nav-injected] .nav-links a:hover {
			color: var(--accent-primary, #F6A800);
			border-color: var(--accent-primary, #F6A800);
		}
		/* The one nav item that is a call to action rather than a destination.
		   Filled rather than outlined so it reads as the CTA at a glance, and
		   scoped like every other rule here so it cannot leak onto a page that
		   supplies its own nav. Injected only while the campaign is open --
		   see campaignIsOpen() above -- so these rules match nothing after
		   2026-09-09 and are harmless if left behind. */
		header[data-nav-injected] .nav-links a.nav-fund {
			color: var(--bg-primary, #12100E);
			background: var(--accent-primary, #F6A800);
			border-color: var(--accent-primary, #F6A800);
			font-weight: bold;
		}
		header[data-nav-injected] .nav-links a.nav-fund:hover {
			color: var(--bg-primary, #12100E);
			background: var(--accent-secondary, #E08A00);
			border-color: var(--accent-secondary, #E08A00);
		}
		header[data-nav-injected] .dropdown { position: relative; }
		header[data-nav-injected] .dropdown-toggle { cursor: pointer; }
		header[data-nav-injected] .dropdown-menu {
			position: absolute; top: 100%; right: 0; min-width: 190px;
			background: var(--bg-secondary, #1C1917);
			border: 1px solid var(--border-color, #3A342E);
			border-radius: 6px; list-style: none; margin: 0; padding: 0.3rem 0;
			opacity: 0; visibility: hidden; transition: opacity 150ms ease;
			z-index: 200;
		}
		header[data-nav-injected] .dropdown:hover .dropdown-menu,
		header[data-nav-injected] .dropdown.open .dropdown-menu {
			opacity: 1; visibility: visible;
		}
		header[data-nav-injected] .dropdown-menu a {
			display: block; padding: 0.45rem 1rem; border: none; border-radius: 0;
		}
		header[data-nav-injected] .version-badge {
			font-size: 0.7rem; color: var(--text-muted, #A79E92);
			white-space: nowrap;
		}
		/* 768px, NOT 760. Every page in this repo breaks at 768; the nav broke at 760,
		   so between 761 and 768 the page was in mobile layout while the nav it carries
		   was still in desktop layout. An 8-pixel band of disagreement is exactly the
		   kind of defect that reproduces on one device and not another. */
		@media (max-width: 768px) {
			header[data-nav-injected] nav {
				flex-direction: column; align-items: flex-start; gap: 0.5rem;
			}
			header[data-nav-injected] .nav-links { justify-content: flex-start; }
			/* COLLAPSED, not expanded. This rule set position/opacity/visibility and
			   never set 'display', so both dropdowns dropped into flow FULLY OPEN and
			   stayed there: 6 top-level links + 6 Community children + 7 Info children
			   + Fund the game = 20 visible links in a sticky header, above the content,
			   on every page that takes the injected nav.

			   The homepage looked like only three lines because it still carries a
			   pre-migration '.dropdown-menu { display: none }' of its own -- an
			   ACCIDENT that was holding the front page together. CLAUDE.md says of
			   those leftover rules "if you see any, they are dead"; they are not, they
			   match the injected nav because the class names are identical, and
			   deleting index.html's would have broken the page that looked fine.
			   That paragraph is corrected in this commit.

			   So the fix is here, additive, and the leftovers can then go separately. */
			header[data-nav-injected] .dropdown-menu {
				position: static; opacity: 1; visibility: visible;
				display: none;
			}
			header[data-nav-injected] .dropdown-toggle[aria-expanded="true"] + .dropdown-menu,
			header[data-nav-injected] .dropdown.open .dropdown-menu { display: block; }
		}
	`;

	function injectStyles() {
		if (document.getElementById('pdoom1-nav-styles')) return;
		const el = document.createElement('style');
		el.id = 'pdoom1-nav-styles';
		el.textContent = navigationCSS;
		document.head.appendChild(el);
	}

	// Initialize navigation when DOM is ready
	function initNavigation() {
		const header = document.querySelector('header');
		if (!header) {
			console.warn('No header element found');
			return;
		}

		// Check if nav already exists
		const existingNav = header.querySelector('nav');
		if (existingNav && existingNav.querySelector('.nav-links')) {
			// Already has proper navigation, don't replace
			return;
		}

		// Styles first, then mark the header, so the nav is never painted
		// unstyled for a frame.
		injectStyles();
		header.setAttribute('data-nav-injected', '');

		// Replace or insert navigation. The campaign slot is filled HERE rather
		// than in the navigationHTML literal so the decision is made at render
		// time against the visitor's clock, not at file-parse time.
		const html = navigationHTML.replace('<!--CAMPAIGN_SLOT-->',
			campaignIsOpen() ? campaignNavItem : '');

		if (existingNav) {
			existingNav.outerHTML = html;
		} else {
			header.innerHTML = html;
		}

		// Initialize dropdown functionality
		initDropdowns();

		// Highlight current page
		highlightCurrentPage();
	}

	// Initialize dropdown menus
	function initDropdowns() {
		const dropdownToggles = document.querySelectorAll('.dropdown-toggle');

		dropdownToggles.forEach(toggle => {
			toggle.addEventListener('click', function(e) {
				e.preventDefault();
				const dropdown = this.closest('.dropdown');
				const isOpen = dropdown.classList.contains('open');

				// Close all dropdowns
				document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('open'));

				// Toggle current dropdown
				if (!isOpen) {
					dropdown.classList.add('open');
					this.setAttribute('aria-expanded', 'true');
				} else {
					this.setAttribute('aria-expanded', 'false');
				}
			});
		});

		// Close dropdowns when clicking outside
		document.addEventListener('click', function(e) {
			if (!e.target.closest('.dropdown')) {
				document.querySelectorAll('.dropdown').forEach(d => {
					d.classList.remove('open');
					const toggle = d.querySelector('.dropdown-toggle');
					if (toggle) toggle.setAttribute('aria-expanded', 'false');
				});
			}
		});
	}

	// Highlight current page in navigation
	function highlightCurrentPage() {
		const currentPath = window.location.pathname;
		const navLinks = document.querySelectorAll('.nav-links a');

		navLinks.forEach(link => {
			const linkPath = new URL(link.href, window.location.origin).pathname;
			if (linkPath === currentPath || (currentPath !== '/' && linkPath !== '/' && currentPath.startsWith(linkPath))) {
				link.classList.add('active');
				link.setAttribute('aria-current', 'page');
			}
		});
	}

	// Update the nav version badge from the canonical version.json so every page
	// using this injected nav reflects the current game release. The badge markup
	// ships empty and hidden, so a failed fetch shows nothing rather than a stale
	// version -- silence beats a confident wrong number.
	async function updateNavVersion() {
		const badgeEl = document.getElementById('versionBadge');
		const numberEl = document.getElementById('versionNumber');
		const dateEl = document.getElementById('versionDate');
		if (!numberEl && !dateEl) return;
		try {
			const response = await fetch('/data/version.json', { cache: 'no-store' });
			if (!response.ok) return;
			const data = await response.json();
			const release = data.latest_release || {};
			if (numberEl && release.version) {
				numberEl.textContent = release.version;
			}
			if (dateEl && release.published_at) {
				dateEl.textContent = release.published_at.split('T')[0];
			}
			if (badgeEl && release.version) {
				badgeEl.removeAttribute('hidden');
				badgeEl.style.display = '';
			}
		} catch (e) {
			// Leave the badge hidden and empty on any failure.
		}
	}

	function init() {
		initNavigation();
		// After initNavigation, so a page whose own nav was left in place still
		// has its campaign markup swept. Before updateNavVersion, which is async
		// and must not be able to delay the removal of an expired campaign.
		applyCampaignWindow();
		updateNavVersion();
	}

	// Run when DOM is ready
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	} else {
		init();
	}
})();
