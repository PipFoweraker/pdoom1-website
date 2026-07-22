/**
 * Standard Navigation Loader for p(Doom)1 Website
 * Loads consistent navigation across all pages
 */

(function() {
	'use strict';

	const navigationHTML = `
		<nav role="navigation" aria-label="Main navigation">
			<div class="logo-container">
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
						<li role="none"><a href="/resources/" role="menuitem">AI Safety Resources</a></li>
						<li role="none"><a href="/docs/roadmap.md" role="menuitem">Roadmap</a></li>
						<li role="none"><a href="/docs/" role="menuitem">Documentation</a></li>
						<li role="none"><a href="/press/" role="menuitem">Press Kit</a></li>
					</ul>
				</li>
			</ul>
		</nav>
	`;

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

		// Replace or insert navigation
		if (existingNav) {
			existingNav.outerHTML = navigationHTML;
		} else {
			header.innerHTML = navigationHTML;
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
		updateNavVersion();
	}

	// Run when DOM is ready
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	} else {
		init();
	}
})();
