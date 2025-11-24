#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync events from pdoom-data repository to pdoom1-website

This script:
1. Clones/updates pdoom-data repository
2. Reads event data from data/serveable/api/timeline_events/
3. Generates individual event detail pages
4. Creates events.json for the events index page
5. Downloads game icons from pdoom1 repo (optional)

Usage:
    python scripts/sync/sync-events.py [--pdoom-data-path PATH] [--sync-icons]
"""

import json
import os
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
SCRIPT_DIR = Path(__file__).parent
WEBSITE_ROOT = SCRIPT_DIR.parent.parent
PUBLIC_DIR = WEBSITE_ROOT / "public"
EVENTS_DIR = PUBLIC_DIR / "events"
DATA_DIR = PUBLIC_DIR / "data"
ICONS_DIR = PUBLIC_DIR / "assets" / "icons" / "events"

# Default pdoom-data location (sibling directory)
DEFAULT_PDOOM_DATA = WEBSITE_ROOT.parent / "pdoom-data"
DEFAULT_PDOOM1 = WEBSITE_ROOT.parent / "pdoom1"


def log(message: str, level: str = "INFO"):
    """Simple logger"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def ensure_directories():
    """Create necessary directories if they don't exist"""
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Ensured directories exist: {EVENTS_DIR}, {DATA_DIR}, {ICONS_DIR}")


def load_events_from_pdoom_data(pdoom_data_path: Path) -> Dict[str, Any]:
    """Load all events from pdoom-data repository"""
    events_file = pdoom_data_path / "data" / "serveable" / "api" / "timeline_events" / "all_events.json"

    if not events_file.exists():
        log(f"Events file not found: {events_file}", "ERROR")
        log(f"Make sure pdoom-data is cloned at: {pdoom_data_path}", "ERROR")
        sys.exit(1)

    with open(events_file, 'r', encoding='utf-8') as f:
        events = json.load(f)

    log(f"Loaded {len(events)} events from pdoom-data")
    return events


def should_include_event(event: Dict[str, Any]) -> bool:
    """Filter events for website display based on event_status metadata"""
    status = event.get('event_status', 'included')

    # Exclude newsletters and explicitly excluded events
    if status in ['newsletter_archive', 'excluded']:
        return False

    # Include all others (included, review_needed)
    return True


def filter_events(events: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out excluded events"""
    filtered = {
        event_id: event
        for event_id, event in events.items()
        if should_include_event(event)
    }

    excluded_count = len(events) - len(filtered)
    if excluded_count > 0:
        log(f"Filtered out {excluded_count} excluded/newsletter events")

    return filtered


def generate_event_detail_page(event_id: str, event: Dict[str, Any]) -> str:
    """Generate HTML for individual event detail page"""

    # Category icons
    category_icons = {
        'funding_catastrophe': '💸',
        'organizational_crisis': '🏢',
        'technical_research_breakthrough': '🔬',
        'institutional_decay': '⚠️',
        'policy_development': '📜',
        'public_awareness': '📢',
        'capability_advance': '🚀',
        'alignment_breakthrough': '🎯',
        'governance_milestone': '⚖️'
    }

    rarity_emoji = {
        'common': '⚪ Common',
        'rare': '🔵 Rare',
        'legendary': '✨ Legendary'
    }

    icon = category_icons.get(event['category'], '📌')
    rarity = rarity_emoji.get(event['rarity'], event['rarity'])

    # Generate impacts table
    impacts_html = ""
    for impact in event['impacts']:
        sign = '+' if impact['change'] > 0 else ''
        color_class = 'positive' if impact['change'] > 0 else 'negative'
        condition_text = f" (if {impact['condition']})" if impact.get('condition') else ""

        impacts_html += f"""
				<tr>
					<td>{impact['variable'].replace('_', ' ').title()}</td>
					<td class="impact-{color_class}">{sign}{impact['change']}</td>
					<td>{condition_text or 'Always'}</td>
				</tr>
		"""

    # Generate sources list
    sources_html = ""
    for i, source in enumerate(event['sources'], 1):
        sources_html += f'<li><a href="{source}" target="_blank" rel="noopener">[{i}] {source}</a></li>\n\t\t\t\t'

    # Generate tags
    tags_html = " ".join([f'<span class="tag">#{tag}</span>' for tag in event['tags']])

    # Generate metadata suggestion URLs
    from urllib.parse import quote

    category_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events&title=Metadata%3A%20Change%20category%20for%20{quote(event_id)}&body=Event%3A%20{quote(event['title'])}%0A%0ACurrent%20category%3A%20{quote(event['category'])}%0A%0ASuggested%20category%3A%20%0A%0AReason%3A%20"

    rarity_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events&title=Metadata%3A%20Change%20rarity%20for%20{quote(event_id)}&body=Event%3A%20{quote(event['title'])}%0A%0ACurrent%20rarity%3A%20{quote(event['rarity'])}%0A%0ASuggested%20rarity%3A%20%0A%0AReason%3A%20"

    tags_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events&title=Metadata%3A%20Change%20tags%20for%20{quote(event_id)}&body=Event%3A%20{quote(event['title'])}%0A%0ACurrent%20tags%3A%20{quote(', '.join(event['tags']))}%0A%0ASuggested%20tags%3A%20%0A%0AReason%3A%20"

    impacts_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events,game-balance&title=Metadata%3A%20Change%20impacts%20for%20{quote(event_id)}&body=Event%3A%20{quote(event['title'])}%0A%0ACurrent%20impacts%3A%20{len(event['impacts'])}%20game%20variable%20changes%0A%0ASuggested%20changes%3A%20%0A-%20Variable%3A%20%0A-%20Change%3A%20%0A%0AReason%3A%20"

    pdoom_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events,game-balance&title=Metadata%3A%20Change%20p(doom)%20impact%20for%20{quote(event_id)}&body=Event%3A%20{quote(event['title'])}%0A%0ACurrent%20p(doom)%20impact%3A%20{event.get('pdoom_impact', 'null')}%0A%0ASuggested%20p(doom)%20impact%3A%20%0A%0AReason%3A%20"

    # Build reaction provenance badges and source info
    def build_reaction_html(reaction_text: str, reaction_key: str) -> str:
        """Build HTML for a reaction with provenance badge and source link"""
        provenance = event.get('reaction_provenance', {})
        reaction_prov = provenance.get(reaction_key, 'placeholder')

        # Handle simple string format
        if isinstance(reaction_prov, str):
            prov_type = reaction_prov
            prov_data = {}
        else:
            prov_type = reaction_prov.get('type', 'placeholder')
            prov_data = reaction_prov

        # Build badge HTML
        badge_html = ""
        source_html = ""

        if prov_type == "placeholder":
            badge_html = '<span class="provenance-badge provenance-placeholder">⚠️ Placeholder - Needs Real Quote</span>'
        elif prov_type == "human_summary":
            badge_html = '<span class="provenance-badge provenance-summary">ℹ️ Summary (Not Direct Quote)</span>'
            if prov_data.get('sources'):
                sources = prov_data['sources'] if isinstance(prov_data['sources'], list) else [prov_data['sources']]
                source_links = ', '.join([f'<a href="{s}" target="_blank" rel="noopener">source</a>' for s in sources])
                source_html = f'<span class="quote-source">Summarized from: {source_links}</span>'
        elif prov_type == "real_quote":
            badge_html = '<span class="provenance-badge provenance-real">✓ Verified Quote</span>'
            if prov_data.get('source'):
                author = prov_data.get('author', 'Unknown')
                date = prov_data.get('date', '')
                date_text = f" ({date})" if date else ""
                source_html = f'<span class="quote-source">— {author}{date_text} (<a href="{prov_data["source"]}" target="_blank" rel="noopener">source</a>)</span>'
        elif prov_type == "not_applicable":
            badge_html = '<span class="provenance-badge" style="opacity: 0.5;">N/A</span>'

        return badge_html, source_html

    safety_badge, safety_source = build_reaction_html(event['safety_researcher_reaction'], 'safety_researcher_reaction')
    media_badge, media_source = build_reaction_html(event['media_reaction'], 'media_reaction')

    html_content = f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>{event['title']} | p(Doom)1 Events</title>
	<link rel="canonical" href="https://pdoom1.com/events/{event_id}.html" />
	<meta name="description" content="{event['description'][:155]}" />

	<!-- Plausible Analytics -->
	<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.file-downloads.outbound-links.pageview-props.tagged-events.js"></script>

	<link rel="stylesheet" href="/css/site.css">
	<style>
		:root {{
			--bg-primary: #1a1a1a;
			--bg-secondary: #2d2d2d;
			--bg-tertiary: #3d3d3d;
			--text-primary: #ffffff;
			--text-secondary: #cccccc;
			--text-muted: #aaaaaa;
			--accent-primary: #00ff41;
			--accent-secondary: #ff6b35;
			--accent-danger: #ff4444;
			--border-color: #444444;
			--success-color: #4caf50;
			--radius-md: 6px;
		}}

		body {{
			font-family: 'Courier New', monospace;
			background: var(--bg-primary);
			color: var(--text-primary);
			line-height: 1.6;
			margin: 0;
			padding: 0;
		}}

		header {{
			background: rgba(45, 45, 45, 0.95);
			border-bottom: 2px solid var(--accent-primary);
			padding: 1rem 0;
		}}

		nav {{
			max-width: 1200px;
			margin: 0 auto;
			padding: 0 1rem;
			display: flex;
			justify-content: space-between;
			align-items: center;
		}}

		.breadcrumb {{
			color: var(--text-muted);
			font-size: 0.9rem;
		}}

		.breadcrumb a {{
			color: var(--accent-primary);
			text-decoration: none;
		}}

		main {{
			max-width: 900px;
			margin: 2rem auto;
			padding: 0 1rem;
		}}

		.event-header {{
			background: linear-gradient(135deg, var(--bg-secondary), var(--bg-tertiary));
			border: 1px solid var(--border-color);
			border-radius: var(--radius-md);
			padding: 2rem;
			margin-bottom: 2rem;
		}}

		.event-icon {{
			font-size: 4rem;
			margin-bottom: 1rem;
		}}

		.event-title {{
			font-size: 2.5rem;
			color: var(--accent-primary);
			margin-bottom: 1rem;
		}}

		.event-meta {{
			display: flex;
			gap: 1.5rem;
			flex-wrap: wrap;
			margin-bottom: 1.5rem;
			font-size: 0.95rem;
		}}

		.meta-item {{
			display: flex;
			align-items: center;
			gap: 0.5rem;
		}}

		.category-badge {{
			background: var(--accent-secondary);
			color: var(--bg-primary);
			padding: 0.3rem 0.8rem;
			border-radius: 4px;
			font-weight: bold;
			text-transform: uppercase;
			font-size: 0.85rem;
		}}

		.rarity-badge {{
			background: var(--bg-tertiary);
			color: var(--text-primary);
			padding: 0.3rem 0.8rem;
			border-radius: 4px;
			border: 1px solid var(--border-color);
		}}

		.section {{
			background: var(--bg-secondary);
			border: 1px solid var(--border-color);
			border-radius: var(--radius-md);
			padding: 1.5rem;
			margin-bottom: 1.5rem;
		}}

		.section h2 {{
			color: var(--accent-secondary);
			margin-bottom: 1rem;
			font-size: 1.5rem;
		}}

		.description {{
			font-size: 1.1rem;
			line-height: 1.8;
			color: var(--text-secondary);
		}}

		.impacts-table {{
			width: 100%;
			border-collapse: collapse;
		}}

		.impacts-table th {{
			background: var(--bg-tertiary);
			padding: 0.8rem;
			text-align: left;
			color: var(--accent-primary);
			border-bottom: 2px solid var(--border-color);
		}}

		.impacts-table td {{
			padding: 0.8rem;
			border-bottom: 1px solid var(--border-color);
		}}

		.impact-positive {{
			color: var(--success-color);
			font-weight: bold;
		}}

		.impact-negative {{
			color: var(--accent-danger);
			font-weight: bold;
		}}

		.quote {{
			background: var(--bg-tertiary);
			border-left: 4px solid var(--accent-primary);
			padding: 1rem 1.5rem;
			margin: 1.5rem 0;
			font-style: italic;
		}}

		.quote-label {{
			font-weight: bold;
			color: var(--accent-primary);
			font-style: normal;
			display: block;
			margin-bottom: 0.5rem;
		}}

		.sources {{
			list-style: none;
			padding: 0;
		}}

		.sources li {{
			margin-bottom: 0.8rem;
		}}

		.sources a {{
			color: var(--accent-primary);
			text-decoration: none;
			word-break: break-all;
		}}

		.sources a:hover {{
			text-decoration: underline;
		}}

		.tags {{
			display: flex;
			gap: 0.5rem;
			flex-wrap: wrap;
		}}

		.tag {{
			background: var(--bg-primary);
			padding: 0.4rem 0.8rem;
			border-radius: 4px;
			font-size: 0.9rem;
			color: var(--text-muted);
		}}

		.metadata-section {{
			background: var(--bg-secondary);
			border: 1px solid var(--border-color);
			border-radius: var(--radius-md);
			padding: 1.5rem;
			margin-bottom: 1.5rem;
		}}

		.metadata-grid {{
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
			gap: 1rem;
			margin-top: 1rem;
		}}

		.metadata-item {{
			background: var(--bg-tertiary);
			padding: 1rem;
			border-radius: 4px;
			border: 1px solid var(--border-color);
		}}

		.metadata-label {{
			font-weight: bold;
			color: var(--accent-primary);
			font-size: 0.85rem;
			display: block;
			margin-bottom: 0.5rem;
		}}

		.metadata-value {{
			color: var(--text-secondary);
			font-size: 0.95rem;
		}}

		.suggest-link {{
			display: inline-block;
			margin-top: 0.5rem;
			color: var(--accent-secondary);
			text-decoration: none;
			font-size: 0.85rem;
			transition: color 0.3s;
		}}

		.suggest-link:hover {{
			color: var(--accent-primary);
			text-decoration: underline;
		}}

		.provenance-badge {{
			display: inline-block;
			padding: 0.25rem 0.6rem;
			border-radius: 4px;
			font-size: 0.75rem;
			font-weight: bold;
			margin-left: 0.5rem;
			vertical-align: middle;
		}}

		.provenance-placeholder {{
			background: rgba(255, 152, 0, 0.2);
			border: 1px solid #ff9800;
			color: #ff9800;
		}}

		.provenance-summary {{
			background: rgba(33, 150, 243, 0.2);
			border: 1px solid #2196f3;
			color: #2196f3;
		}}

		.provenance-real {{
			background: rgba(76, 175, 80, 0.2);
			border: 1px solid #4caf50;
			color: #4caf50;
		}}

		.quote-source {{
			display: block;
			margin-top: 0.5rem;
			font-size: 0.85rem;
			color: var(--text-muted);
		}}

		.quote-source a {{
			color: var(--accent-secondary);
			text-decoration: none;
		}}

		.quote-source a:hover {{
			text-decoration: underline;
		}}

		.suggest-quote-button {{
			display: inline-block;
			margin-top: 0.75rem;
			padding: 0.5rem 1rem;
			background: rgba(255, 107, 53, 0.1);
			border: 1px solid var(--accent-secondary);
			border-radius: 4px;
			color: var(--accent-secondary);
			text-decoration: none;
			font-size: 0.85rem;
			transition: all 0.3s;
		}}

		.suggest-quote-button:hover {{
			background: var(--accent-secondary);
			color: var(--bg-primary);
			transform: translateY(-2px);
		}}

		.contribute-section {{
			background: linear-gradient(135deg, var(--bg-secondary), rgba(255, 107, 53, 0.1));
			border: 1px solid var(--accent-secondary);
			border-radius: var(--radius-md);
			padding: 1.5rem;
			text-align: center;
		}}

		.cta-button {{
			display: inline-block;
			background: var(--accent-secondary);
			color: var(--bg-primary);
			padding: 0.8rem 1.5rem;
			text-decoration: none;
			border-radius: 4px;
			font-weight: bold;
			margin: 0.5rem;
			transition: transform 0.3s;
		}}

		.cta-button:hover {{
			transform: translateY(-2px);
		}}

		footer {{
			background: var(--bg-secondary);
			border-top: 2px solid var(--accent-primary);
			text-align: center;
			padding: 2rem 1rem;
			margin-top: 4rem;
			color: var(--text-muted);
		}}
	</style>
</head>
<body>
	<header>
		<nav>
			<div class="breadcrumb">
				<a href="/">Home</a> / <a href="/events/">Events</a> / {event['title']}
			</div>
		</nav>
	</header>

	<main>
		<div class="event-header">
			<div class="event-icon">{icon}</div>
			<h1 class="event-title">{event['title']}</h1>

			<div class="event-meta">
				<div class="meta-item">
					<span>📅</span>
					<span><strong>{event['year']}</strong></span>
				</div>
				<div class="meta-item">
					<span class="category-badge">{event['category'].replace('_', ' ')}</span>
				</div>
				<div class="meta-item">
					<span class="rarity-badge">{rarity}</span>
				</div>
			</div>

			<div class="tags">
				{tags_html}
			</div>
		</div>

		<div class="section">
			<h2>📖 Description</h2>
			<p class="description">{event['description']}</p>
		</div>

		<div class="section">
			<h2>📊 Game Impacts</h2>
			<table class="impacts-table">
				<thead>
					<tr>
						<th>Variable</th>
						<th>Change</th>
						<th>Condition</th>
					</tr>
				</thead>
				<tbody>
					{impacts_html}
				</tbody>
			</table>
		</div>

		<div class="section">
			<h2>💭 Reactions</h2>

			<div class="quote">
				<span class="quote-label">🔬 Safety Researcher Reaction:</span>
				{safety_badge}
				<br>
				"{event['safety_researcher_reaction']}"
				{safety_source}
			</div>

			<div class="quote">
				<span class="quote-label">📰 Media Reaction:</span>
				{media_badge}
				<br>
				"{event['media_reaction']}"
				{media_source}
			</div>

			<a href="/events/suggest-quote.html?event={event_id}" class="suggest-quote-button">
				💡 Found a Real Quote? Suggest it here
			</a>
		</div>

		<div class="section">
			<h2>🔗 Sources</h2>
			<ul class="sources">
				{sources_html}
			</ul>
		</div>

		<div class="metadata-section">
			<h2>🏷️ Event Metadata</h2>
			<p style="color: var(--text-muted); margin-bottom: 1rem;">
				Think this event's metadata could be improved? Suggest changes to category, rarity, tags, game impacts, or p(doom) effects.
			</p>

			<div class="metadata-grid">
				<div class="metadata-item">
					<span class="metadata-label">📁 Category</span>
					<span class="metadata-value">{event['category'].replace('_', ' ').title()}</span>
					<a href="{category_suggestion_url}" class="suggest-link" target="_blank">→ Suggest different category</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">⭐ Rarity</span>
					<span class="metadata-value">{rarity}</span>
					<a href="{rarity_suggestion_url}" class="suggest-link" target="_blank">→ Suggest different rarity</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">🏷️ Tags ({len(event['tags'])})</span>
					<span class="metadata-value">{', '.join(event['tags'])}</span>
					<a href="{tags_suggestion_url}" class="suggest-link" target="_blank">→ Suggest tag changes</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">📊 Game Impacts ({len(event['impacts'])})</span>
					<span class="metadata-value">{len(event['impacts'])} variable changes</span>
					<a href="{impacts_suggestion_url}" class="suggest-link" target="_blank">→ Suggest impact changes</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">☢️ p(Doom) Impact</span>
					<span class="metadata-value">{event.get('pdoom_impact') if event.get('pdoom_impact') is not None else 'No direct impact'}</span>
					<a href="{pdoom_suggestion_url}" class="suggest-link" target="_blank">→ Suggest p(doom) change</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">📝 General Metadata</span>
					<span class="metadata-value">Year, description, reactions</span>
					<a href="/events/suggest-metadata.html?event={event_id}" class="suggest-link">→ Comprehensive review</a>
				</div>
			</div>
		</div>

		<div class="contribute-section">
			<h2>🤝 Found an Issue?</h2>
			<p>This event data is sourced from the pdoom-data repository. If you notice errors or want to suggest improvements:</p>
			<a href="https://github.com/PipFoweraker/pdoom-data/issues/new?title=Event%20Issue:%20{event_id}" class="cta-button" target="_blank">GitHub Issue (Preferred)</a>
			<a href="mailto:team@pdoom1.com?subject=Event%20Data%20Issue:%20{event_id}&body=Event:%20{quote(event['title'])}%0A%0AWhat's wrong:%20%0A%0ASuggested fix:%20" class="cta-button">📧 Email (No GitHub)</a>
		</div>

		<div style="text-align: center; margin-top: 2rem;">
			<a href="/events/" style="color: var(--accent-primary); text-decoration: none;">← Back to All Events</a>
		</div>
	</main>

	<footer>
		<p>&copy; 2025 p(Doom)1 | <a href="https://github.com/PipFoweraker/pdoom1" style="color: var(--accent-primary);">GitHub</a></p>
		<p style="margin-top: 0.5rem; font-size: 0.9rem;">Event data from <a href="https://github.com/PipFoweraker/pdoom-data" target="_blank" style="color: var(--accent-secondary);">pdoom-data</a></p>
	</footer>
</body>
</html>
"""

    return html_content


def write_events_json(events: Dict[str, Any]):
    """Write events.json for the events index page"""
    output_file = DATA_DIR / "events.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2)

    log(f"Wrote events index to {output_file}")


def sync_icons(pdoom1_path: Path):
    """Sync game icons from pdoom1 repository"""
    icons_source = pdoom1_path / "art_generated" / "game_icons" / "v1"

    if not icons_source.exists():
        log(f"Icons directory not found: {icons_source}", "WARN")
        log("Skipping icon sync", "WARN")
        return

    # Copy 128px versions of event-related icons
    icon_patterns = [
        "*funding*_128.png",
        "*crisis*_128.png",
        "*research*_128.png",
        "*breakthrough*_128.png",
    ]

    copied = 0
    for pattern in icon_patterns:
        for icon_file in icons_source.glob(pattern):
            dest = ICONS_DIR / icon_file.name
            shutil.copy2(icon_file, dest)
            copied += 1

    log(f"Synced {copied} event icons from pdoom1")


def main():
    parser = argparse.ArgumentParser(description="Sync events from pdoom-data to pdoom1-website")
    parser.add_argument(
        "--pdoom-data-path",
        type=Path,
        default=DEFAULT_PDOOM_DATA,
        help=f"Path to pdoom-data repository (default: {DEFAULT_PDOOM_DATA})"
    )
    parser.add_argument(
        "--pdoom1-path",
        type=Path,
        default=DEFAULT_PDOOM1,
        help=f"Path to pdoom1 repository (default: {DEFAULT_PDOOM1})"
    )
    parser.add_argument(
        "--sync-icons",
        action="store_true",
        help="Also sync game icons from pdoom1 repository"
    )

    args = parser.parse_args()

    log("=" * 60)
    log("Starting events sync from pdoom-data")
    log("=" * 60)

    # Ensure directories exist
    ensure_directories()

    # Load events
    all_events = load_events_from_pdoom_data(args.pdoom_data_path)

    # Filter events (exclude newsletters and explicitly excluded)
    events = filter_events(all_events)

    # Generate individual event detail pages
    log("Generating event detail pages...")
    for event_id, event in events.items():
        html_content = generate_event_detail_page(event_id, event)
        output_file = EVENTS_DIR / f"{event_id}.html"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

    log(f"Generated {len(events)} event detail pages")

    # Write events.json for index page
    write_events_json(events)

    # Optionally sync icons
    if args.sync_icons:
        log("Syncing game icons...")
        sync_icons(args.pdoom1_path)

    log("=" * 60)
    log(f"✅ Sync complete! {len(events)} events processed")
    log("=" * 60)
    log(f"Events index: {EVENTS_DIR / 'index.html'}")
    log(f"Events data: {DATA_DIR / 'events.json'}")
    log(f"Event pages: {EVENTS_DIR}/*.html")

    # Analyze quote quality
    def get_provenance_type(event: Dict[str, Any], reaction_key: str) -> str:
        """Get the provenance type for a reaction"""
        prov = event.get('reaction_provenance', {}).get(reaction_key, 'placeholder')
        if isinstance(prov, str):
            return prov
        return prov.get('type', 'placeholder')

    quote_stats = {
        'real_quotes': 0,
        'human_summaries': 0,
        'placeholders': 0,
        'not_applicable': 0
    }

    for event in events.values():
        safety_type = get_provenance_type(event, 'safety_researcher_reaction')
        media_type = get_provenance_type(event, 'media_reaction')

        # Count based on "best" provenance type for the event
        if safety_type == 'real_quote' or media_type == 'real_quote':
            quote_stats['real_quotes'] += 1
        elif safety_type == 'human_summary' or media_type == 'human_summary':
            quote_stats['human_summaries'] += 1
        elif safety_type == 'not_applicable' and media_type == 'not_applicable':
            quote_stats['not_applicable'] += 1
        else:
            quote_stats['placeholders'] += 1

    # Create summary report
    summary = {
        "sync_timestamp": datetime.now().isoformat(),
        "total_events_in_source": len(all_events),
        "included_events": len(events),
        "excluded_events": len(all_events) - len(events),
        "categories": len(set(e['category'] for e in events.values())),
        "events_by_rarity": {
            rarity: len([e for e in events.values() if e['rarity'] == rarity])
            for rarity in ['common', 'rare', 'legendary']
        },
        "year_range": [
            min(e['year'] for e in events.values()),
            max(e['year'] for e in events.values())
        ],
        "event_status_breakdown": {
            "newsletter_archive": len([e for e in all_events.values() if e.get('event_status') == 'newsletter_archive']),
            "excluded": len([e for e in all_events.values() if e.get('event_status') == 'excluded']),
            "review_needed": len([e for e in events.values() if e.get('event_status') == 'review_needed']),
            "included": len([e for e in events.values() if e.get('event_status', 'included') == 'included'])
        },
        "quote_quality_stats": {
            "events_with_real_quotes": quote_stats['real_quotes'],
            "events_with_summaries": quote_stats['human_summaries'],
            "events_with_placeholders": quote_stats['placeholders'],
            "events_not_applicable": quote_stats['not_applicable'],
            "completion_percentage": round((quote_stats['real_quotes'] / len(events)) * 100, 1) if len(events) > 0 else 0.0,
            "goal_q1_2025": 50,
            "goal_q2_2025": 100,
            "goal_end_2025": 300
        }
    }

    summary_file = DATA_DIR / "events-sync-summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    log(f"Summary report: {summary_file}")


if __name__ == "__main__":
    main()
