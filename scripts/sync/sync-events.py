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
import re
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

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

# Canonical origin, used to build absolute og:url / og:image values (the
# OpenGraph spec requires absolute URLs -- a relative path is silently ignored
# by every scraper).
SITE_ORIGIN = "https://pdoom1.com"

# The site-wide share card already referenced by index/about/press. Deliberately
# NOT a per-event image: no per-event art exists, and pointing at one that does
# not exist is worse than pointing at the generic card.
OG_IMAGE_URL = f"{SITE_ORIGIN}/assets/og-card.jpg"

# Length budget for the description reused by <meta name="description">,
# og:description and twitter:description.
META_DESCRIPTION_CHARS = 155


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


# ---------------------------------------------------------------------------
# PII redaction
#
# Many event descriptions are raw text scraped out of paper PDFs, and arXiv/ACM
# author blocks carry the authors' institutional email addresses. Republishing
# those on a public static site hands a spam harvester 75 academics' addresses
# that they never agreed to have listed here. So every string that reaches a
# generated page or events.json is swept before it is written.
#
# Two properties this pattern is built for, both from the real corpus:
#
#   * PDF extraction glues the next author's given name onto the TLD --
#     "madry@mit.eduAleksandar". A greedy [A-Za-z]{2,} TLD eats "Aleksandar"
#     too and silently deletes a name. Requiring the TLD to be one letter
#     followed by LOWERCASE letters stops the match at the capital, so the
#     redaction removes the address and leaves the name.
#   * Line breaks are extracted as a literal "\n" two-character sequence in
#     some records, which is why the corpus contains "nroman.yampolskiy@..."
#     with a leading n. The local part matches whatever precedes the @, so
#     that stray n is left behind as text -- ugly, but it is not an address,
#     and inventing a rule to strip it risks eating real initials.
REDACTION_MARKER = "[email removed]"

EMAIL_PATTERN = re.compile(
    r"(?:mailto:)?"                            # swallow a mailto: prefix too
    r"[A-Za-z0-9._%+\-]+"                      # local part
    r"@"
    r"[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*"     # domain labels
    r"\.[A-Za-z][a-z]{1,23}"                   # TLD (see note above)
)


def redact_emails_in_text(text: str) -> str:
    """Replace every email address in a string with REDACTION_MARKER.

    Marking rather than deleting: a reader who sees a gap in an author block
    should be able to tell that something was taken out deliberately, not that
    the page is broken. The site's rule is to never mislead a visitor, and a
    silent deletion is a small lie about what the source said.
    """
    return EMAIL_PATTERN.sub(REDACTION_MARKER, text)


def redact_pii(value: Any) -> Any:
    """Recursively redact email addresses in any nested str/list/dict value.

    Deliberately walks the WHOLE event rather than a named list of fields:
    write_events_json() serialises the entire event dict, so a field added
    upstream tomorrow would otherwise ship unscrubbed. Fail closed.
    """
    if isinstance(value, str):
        return redact_emails_in_text(value)
    if isinstance(value, list):
        return [redact_pii(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_pii(v) for k, v in value.items()}
    return value


def count_emails(value: Any) -> int:
    """Count email addresses in a nested structure (for the sync log)."""
    if isinstance(value, str):
        return len(EMAIL_PATTERN.findall(value))
    if isinstance(value, list):
        return sum(count_emails(v) for v in value)
    if isinstance(value, dict):
        return sum(count_emails(v) for v in value.values())
    return 0



# ---------------------------------------------------------------------------
# HTML escaping
#
# Every string below reaches a generated page through an f-string, so the page
# is built by concatenation and the data decides where the markup ends. Event
# descriptions are raw text extracted from paper PDFs -- arXiv accepts uploads
# from anyone -- so "the data is first-party" is not true of the *contents* of
# these fields, only of the pipeline that carries them.
#
# This was not hypothetical. Before this pass, in the shipped corpus:
#   * arxiv_73643a60bb86bf2f's description contains "<<number to be assigned>>",
#     which the browser parses as a tag start in <p class="description"> AND
#     inside the <meta name="description" content="..."> attribute.
#   * arxiv_aa8c44de8cf70353's description contains a double quote inside the
#     first 155 characters, which TERMINATES the meta content attribute early
#     and turns the rest of the sentence into bogus tag attributes.
# Both were live on pdoom1.com.
#
# escape_event_for_html() mirrors redact_pii(): it walks the WHOLE record rather
# than a named list of fields, so a field added upstream tomorrow is covered on
# the day it appears. Fail closed. Non-strings pass through untouched, so ints
# (year, impact deltas) still render as numbers.
def esc(value: Any) -> str:
    """HTML-escape a single value for text OR attribute context.

    Escaping the double quote is not optional: several slots are attribute values
    (content="...", href="..."), and an unescaped double quote in an attribute is
    an injection, not a typo.

    The apostrophe is deliberately NOT escaped, which is where this differs from
    html.escape(s, quote=True). Every attribute in this template is double-quoted
    (test-sync-events.py asserts that as a rule, so the exemption cannot rot), and
    inside a double-quoted attribute an apostrophe is an ordinary character. Escaping
    it anyway would rewrite ~1,194 published pages for no reader-visible change --
    prose is full of apostrophes -- and burying a real fix in a diff that large is
    how a real fix stops getting reviewed.
    """
    return (str(value).replace("&", "&amp;")
                      .replace("<", "&lt;")
                      .replace(">", "&gt;")
                      .replace('"', "&quot;"))


def escape_event_for_html(value: Any) -> Any:
    """Recursively HTML-escape every string in a nested str/list/dict value.

    Deliberately mirrors redact_pii(): whole-record, not a field list. The page
    template interpolates ~20 distinct expressions off the event dict and gains
    more over time; enumerating them is how the leaderboard shipped six escaped
    fields and thirteen unescaped ones.
    """
    if isinstance(value, str):
        return esc(value)
    if isinstance(value, list):
        return [escape_event_for_html(v) for v in value]
    if isinstance(value, dict):
        return {k: escape_event_for_html(v) for k, v in value.items()}
    return value


def meta_text(value: Any, limit: Optional[int] = None) -> str:
    """Prepare an arbitrary event string for a <meta content="..."> slot.

    Escaping alone is not enough for the meta block, which is why this exists
    alongside esc() rather than instead of it. Two extra problems, both present
    in the shipped corpus:
      * newlines and runs of whitespace -- many arXiv-derived descriptions are
        multi-line, so the raw value emitted an attribute spanning six physical
        lines and rendered as a mangled share-card snippet;
      * length -- og:description and twitter:description want a snippet, not the
        whole abstract.

    It does NOT define a second notion of escaping: the last step calls esc(),
    the single escaper this module owns. Order matters -- collapse and truncate
    FIRST, escape LAST, so the character budget counts what a reader sees and a
    cut can never land inside an entity. That means meta_text() must be handed
    the UNESCAPED value (`raw[...]`), never the pre-escaped `event[...]`, or the
    ampersands get escaped twice.
    """
    collapsed = " ".join(str(value).split())
    if limit is not None and len(collapsed) > limit:
        collapsed = collapsed[:limit].rstrip() + "…"
    return esc(collapsed)


def sanitize_urls_in_text(text: str) -> str:
    """Convert HTTP URLs to HTTPS where safe to do so"""
    import re

    # Known safe HTTP -> HTTPS conversions
    safe_conversions = {
        'http://rohinshah.com': 'https://rohinshah.com',
        'http://redwoodresearch.org': 'https://redwoodresearch.org',
        'http://aitracker.org': 'https://aitracker.org',
        'http://arxiv.org': 'https://arxiv.org',
        'http://lesswrong.com': 'https://lesswrong.com',
        'http://www.lesswrong.com': 'https://www.lesswrong.com',
        'http://forum.effectivealtruism.org': 'https://forum.effectivealtruism.org',
        'http://eepurl.com': 'https://eepurl.com',
        'http://alignment-newsletter.libsyn.com': 'https://alignment-newsletter.libsyn.com',
        'http://www.cs.umd.edu': 'https://www.cs.umd.edu',
        'http://amazon.com': 'https://amazon.com',
        'http://acritch.com': 'https://acritch.com',
        'http://proceedings.mlr.press': 'https://proceedings.mlr.press',
        'http://www.jackspencer.org': 'https://www.jackspencer.org',
    }

    result = text
    for http_url, https_url in safe_conversions.items():
        result = result.replace(http_url, https_url)

    return result


def sanitize_event_urls(event: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize URLs throughout an event object"""
    # Sanitize description
    if 'description' in event:
        event['description'] = sanitize_urls_in_text(event['description'])

    # Sanitize reactions
    for reaction_key in ['safety_researcher_reaction', 'media_reaction']:
        if reaction_key in event:
            event[reaction_key] = sanitize_urls_in_text(event[reaction_key])

    # Sanitize sources
    if 'sources' in event:
        event['sources'] = [sanitize_urls_in_text(s) for s in event['sources']]

    return event


def generate_event_detail_page(event_id: str, event: Dict[str, Any]) -> str:
    """Generate HTML for individual event detail page"""

    # Escape ONCE, at the top, for the whole record -- see escape_event_for_html().
    # `raw` keeps the unescaped values for the two contexts where escaping would be
    # wrong: urllib.parse.quote() percent-encodes for a URL (double-escaping would
    # put "%26amp%3B" in a prefilled GitHub issue title), and the meta-description
    # truncation must slice the source text BEFORE escaping or it can cut an entity
    # in half. Everything else below reads the escaped `event`.
    raw = event
    event = escape_event_for_html(event)
    event_id_esc = esc(event_id)

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

    # These read `raw`, not `event`: quote() is the escaper for a URL context, and
    # running it over already-HTML-escaped text would prefill the GitHub issue with
    # "%26amp%3B" where the source said "&". The percent-encoding quote() produces
    # contains no <, > or " , so the finished URL is safe in an href attribute.
    category_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events&title=Metadata%3A%20Change%20category%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0ACurrent%20category%3A%20{quote(raw['category'])}%0A%0ASuggested%20category%3A%20%0A%0AReason%3A%20"

    rarity_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events&title=Metadata%3A%20Change%20rarity%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0ACurrent%20rarity%3A%20{quote(raw['rarity'])}%0A%0ASuggested%20rarity%3A%20%0A%0AReason%3A%20"

    tags_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events&title=Metadata%3A%20Change%20tags%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0ACurrent%20tags%3A%20{quote(', '.join(raw['tags']))}%0A%0ASuggested%20tags%3A%20%0A%0AReason%3A%20"

    impacts_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events,game-balance&title=Metadata%3A%20Change%20impacts%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0ACurrent%20impacts%3A%20{len(event['impacts'])}%20game%20variable%20changes%0A%0ASuggested%20changes%3A%20%0A-%20Variable%3A%20%0A-%20Change%3A%20%0A%0AReason%3A%20"

    pdoom_suggestion_url = f"https://github.com/PipFoweraker/pdoom-data/issues/new?labels=metadata,events,game-balance&title=Metadata%3A%20Change%20p(doom)%20impact%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0ACurrent%20p(doom)%20impact%3A%20{quote(str(raw.get('pdoom_impact', 'null')))}%0A%0ASuggested%20p(doom)%20impact%3A%20%0A%0AReason%3A%20"

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

    # Values shared by <meta name="description"> and the OpenGraph / Twitter
    # card block. Built from `raw`, NOT from the already-escaped `event`:
    # meta_text() collapses and truncates before escaping (see its docstring),
    # so handing it a pre-escaped string would double-escape the ampersands and
    # let a cut land inside an entity. `event_id_esc` is reused rather than
    # re-derived so the canonical URL and og:url cannot drift apart.
    page_url = f"{SITE_ORIGIN}/events/{event_id_esc}.html"
    og_title = meta_text(raw['title'])
    og_description = meta_text(raw['description'], META_DESCRIPTION_CHARS)

    html_content = f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>{event['title']} | p(Doom)1 Events</title>
	<link rel="canonical" href="{page_url}" />
	<meta name="description" content="{og_description}" />

	<!-- Share cards. Without these an event link pastes as a bare URL. -->
	<meta property="og:type" content="article" />
	<meta property="og:site_name" content="p(Doom)1" />
	<meta property="og:title" content="{og_title}" />
	<meta property="og:description" content="{og_description}" />
	<meta property="og:url" content="{page_url}" />
	<meta property="og:image" content="{OG_IMAGE_URL}" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content="{og_title}" />
	<meta name="twitter:description" content="{og_description}" />
	<!-- twitter:site intentionally omitted until the handle is finalized,
	     matching public/index.html. -->

	<!-- Analytics consent shim. MUST stay above the deferred tracker below:
	     this tag is parser-blocking, so it sets localStorage.plausible_ignore
	     (from Do-Not-Track or an explicit opt-out) before the deferred script
	     runs and fires its pageview. Without it on this page, a deep-linked
	     visitor is counted before the privacy page's promise can be honoured.
	     It never injects a tracker -- see public/assets/js/analytics.js. -->
	<script src="/assets/js/analytics.js"></script>

	<!-- Plausible Analytics -->
	<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.file-downloads.outbound-links.pageview-props.tagged-events.js"></script>

	<link rel="stylesheet" href="/css/site.css">
	<style>
		:root {{
			/* Palette derived from the game's shipped art: amber-dominant CRT chrome
			   with a teal counterpoint over warm near-black. Green is demoted to
			   --phosphor (OK-state / terminal flourish only), matching
			   godot/scripts/ui/terminal_theme.gd: amber = PLAN register, green = WATCH. */
			--bg-primary: #12100F;
			--bg-secondary: #1C1917;
			--bg-tertiary: #262220;
			--text-primary: #E9F2F2;
			--text-secondary: #CFC7BB;
			--text-muted: #A79E92;
			--accent-primary: #F6A800;
			--accent-secondary: #2FD4C2;
			--accent-danger: #E2524A;
			--border-color: #3A342E;
			--success-color: #4FB37A;
			--radius-md: 6px;
			/* extended semantic tokens */
			--border-strong: #574E44;
			--accent-alt: #2FD4C2;
			--phosphor: #5BE87A;
			--warning: #E9752E;
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
			background: rgba(28, 25, 23, 0.95);
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
			/* phosphor = the demoted terminal green, kept for live OK-state readouts */
			color: var(--phosphor);
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

		/* Tint alpha is 0.12, not 0.20: the badge text sits on the *blended* tint,
		   and at 0.20 the warning variant only reaches 4.36:1 (WCAG AA fail).
		   At 0.12 the three variants measure 4.97 / 7.55 / 5.61. */
		.provenance-placeholder {{
			background: rgba(233, 117, 46, 0.12);
			border: 1px solid var(--warning);
			color: var(--warning);
		}}

		.provenance-summary {{
			background: rgba(47, 212, 194, 0.12);
			border: 1px solid var(--accent-alt);
			color: var(--accent-alt);
		}}

		.provenance-real {{
			background: rgba(79, 179, 122, 0.12);
			border: 1px solid var(--success-color);
			color: var(--success-color);
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
			background: rgba(47, 212, 194, 0.1);
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
			background: linear-gradient(135deg, var(--bg-secondary), rgba(47, 212, 194, 0.1));
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

			<a href="/events/suggest-quote.html?event={quote(event_id)}" class="suggest-quote-button">
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
					<a href="/events/suggest-metadata.html?event={quote(event_id)}" class="suggest-link">→ Comprehensive review</a>
				</div>
			</div>
		</div>

		<div class="contribute-section">
			<h2>🤝 Found an Issue?</h2>
			<p>This event data is sourced from the pdoom-data repository. If you notice errors or want to suggest improvements:</p>
			<a href="https://github.com/PipFoweraker/pdoom-data/issues/new?title=Event%20Issue:%20{quote(event_id)}" class="cta-button" target="_blank">GitHub Issue (Preferred)</a>
			<a href="mailto:team@pdoom1.com?subject=Event%20Data%20Issue:%20{quote(event_id)}&amp;body=Event:%20{quote(raw['title'])}%0A%0AWhat's wrong:%20%0A%0ASuggested fix:%20" class="cta-button">📧 Email (No GitHub)</a>
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

    with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
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

    # Sanitize HTTP URLs to HTTPS
    log("Sanitizing HTTP URLs to HTTPS...")
    url_changes = 0
    for event_id, event in events.items():
        before = json.dumps(event)
        events[event_id] = sanitize_event_urls(event)
        after = json.dumps(events[event_id])
        if before != after:
            url_changes += 1
    if url_changes > 0:
        log(f"Sanitized URLs in {url_changes} events")

    # Redact third-party email addresses harvested out of paper PDFs.
    # Runs AFTER the URL pass so the https rewrite still sees whole strings,
    # and BEFORE page generation and write_events_json() so neither surface
    # can publish one. See redact_pii() for why it walks the whole record.
    log("Redacting third-party email addresses...")
    emails_found = 0
    events_with_emails = 0
    for event_id, event in events.items():
        n = count_emails(event)
        if n:
            emails_found += n
            events_with_emails += 1
            events[event_id] = redact_pii(event)
    if emails_found:
        log(f"Redacted {emails_found} email addresses across {events_with_emails} events")
    else:
        log("No email addresses found in event data")

    # Generate individual event detail pages
    log("Generating event detail pages...")
    for event_id, event in events.items():
        html_content = generate_event_detail_page(event_id, event)
        output_file = EVENTS_DIR / f"{event_id}.html"

        # newline='\n' pins LF output. Without it, a Windows run writes CRLF;
        # git's autocrlf clean filter silently REFUSES to normalise any file
        # that already contains a lone CR (one arXiv description does), so that
        # page alone would be committed with CRLF and show up as a whole-file
        # rewrite in every future diff.
        with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
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
    with open(summary_file, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(summary, f, indent=2)

    log(f"Summary report: {summary_file}")


if __name__ == "__main__":
    main()
