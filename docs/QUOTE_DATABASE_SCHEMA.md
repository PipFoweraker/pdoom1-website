# Quote Database Schema

**Purpose**: Define the structure for storing and managing sourced reactions/quotes for timeline events.

**Last Updated**: 2025-11-24

---

## Overview

This document establishes the schema for tracking real quotes from researchers, media, and community members about AI safety events. This infrastructure supports:

1. **Upgrading placeholder reactions** to real sourced quotes
2. **Multiple quotes per event** from different sources
3. **Full provenance tracking** (author, source, date, platform)
4. **Easy integration** into both the website and game

---

## Current State

### Reaction Types in Events

| Type | Count | Description |
|------|-------|-------------|
| `placeholder` | ~949 | Generic text like "Critical insights for the field" |
| `human_summary` | ~28 | Human-written summaries of event reception |
| `real_quote` | 0 | Verified quotes with full source attribution |
| `not_applicable` | 51 | Newsletter events (excluded) |

**Goal**: Gradually replace placeholders and summaries with real quotes from the literature.

---

## Metadata Schema

### In `all_events.json`

Each event should have a `reaction_provenance` field:

```json
{
  "id": "ftx_future_fund_collapse_2022",
  "title": "FTX Future Fund Collapse",
  "safety_researcher_reaction": "This is the worst funding crisis in EA history",
  "media_reaction": "The collapse has sent shockwaves through the AI safety community",

  "reaction_provenance": {
    "safety_researcher_reaction": {
      "type": "real_quote",
      "source": "https://astralcodexten.substack.com/p/...",
      "author": "Scott Alexander",
      "date": "2022-11-16",
      "platform": "substack",
      "context": "Blog post analyzing the FTX collapse impact"
    },
    "media_reaction": {
      "type": "real_quote",
      "source": "https://fortune.com/...",
      "author": "Fortune Magazine",
      "date": "2022-11-15",
      "platform": "news",
      "publication": "Fortune"
    }
  }
}
```

### Field Definitions

#### `type` (required)
- `"real_quote"` - Direct quote from a real person/publication
- `"human_summary"` - Human-written summary of multiple sources
- `"placeholder"` - Generic placeholder text (needs replacement)
- `"not_applicable"` - Event doesn't warrant reactions

#### `source` (required for `real_quote`)
- Full URL to the original quote
- Must be a direct link (not a redirect or shortener)
- Should be publicly accessible

#### `author` (required for `real_quote`)
- Name of person or publication
- For media: Use publication name (e.g., "Fortune Magazine")
- For individuals: Full name when available

#### `date` (required for `real_quote`)
- ISO 8601 format: `YYYY-MM-DD`
- Date the quote was published, not discovered

#### `platform` (required for `real_quote`)
- One of: `lesswrong`, `ea_forum`, `twitter`, `blog`, `news`, `academic`, `other`

#### `context` (optional)
- Brief description of where/why the quote appeared
- E.g., "Comment on LessWrong thread about FTX collapse"

#### `publication` (optional, for media quotes)
- Name of publication (Fortune, TechCrunch, etc.)

#### `sources` (for `human_summary` type)
- Array of URLs summarized
- Indicates the quote is a synthesis, not a direct quote

---

## Extended Quote Database (Future)

For events with **multiple high-quality quotes**, we can create a separate quotes database:

### `data/quotes/event_quotes.json`

```json
{
  "ftx_future_fund_collapse_2022": {
    "researcher_reactions": [
      {
        "author": "Scott Alexander",
        "source": "https://astralcodexten.substack.com/p/...",
        "quote": "This is the worst funding crisis in EA history",
        "date": "2022-11-16",
        "platform": "substack",
        "upvotes": 142,
        "selected": true
      },
      {
        "author": "Rob Miles",
        "source": "https://twitter.com/robertskmiles/status/...",
        "quote": "Losing $32M overnight is catastrophic for alignment research",
        "date": "2022-11-11",
        "platform": "twitter",
        "retweets": 87,
        "selected": false
      },
      {
        "author": "Eliezer Yudkowsky",
        "source": "https://lesswrong.com/posts/...",
        "quote": "Well, that's not optimal",
        "date": "2022-11-10",
        "platform": "lesswrong",
        "karma": 234,
        "selected": false
      }
    ],
    "media_coverage": [
      {
        "outlet": "Fortune",
        "headline": "FTX collapse takes down AI safety research",
        "url": "https://fortune.com/...",
        "excerpt": "The collapse has sent shockwaves through the AI safety community",
        "date": "2022-11-15",
        "platform": "news",
        "selected": true
      },
      {
        "outlet": "MIT Technology Review",
        "headline": "AI safety's billionaire patron just vanished",
        "url": "https://technologyreview.com/...",
        "excerpt": "Research groups are scrambling to find alternative funding",
        "date": "2022-11-14",
        "platform": "news",
        "selected": false
      }
    ]
  }
}
```

**Benefits**:
- Store multiple quotes per event
- Track engagement metrics (upvotes, karma, retweets)
- Mark which quote is "selected" for display
- Easy to rotate quotes or show multiple
- Separate concerns (events vs. quotes)

---

## Quote Selection Criteria

When choosing which quote to display:

### For Safety Researcher Reactions:
1. **Direct relevance** to the event
2. **Authority** of the speaker (known AI safety researchers)
3. **Engagement** (LessWrong karma, Twitter engagement)
4. **Clarity** and conciseness
5. **Historical significance**

### For Media Reactions:
1. **Source credibility** (major publications preferred)
2. **Timeliness** (closer to event date)
3. **Accuracy** in describing the event
4. **Public impact** (widely shared/cited)

---

## Workflow for Adding Quotes

### 1. Manual Curation (Current)
1. User finds quote on LessWrong/Twitter/blog
2. Submits via [suggest-quote.html](/events/suggest-quote.html)
3. Form creates GitHub issue with structured data
4. Maintainer reviews and adds to `all_events.json`

### 2. Automated Scraping (Future)
- Scrape LessWrong comments mentioning event titles
- Track Twitter mentions with sentiment analysis
- Monitor EA Forum discussions
- Index blog post citations

### 3. Community Voting (Future)
- Users suggest multiple quotes
- Community votes on best quote per event
- Top-voted quote becomes "selected"

---

## Website Integration

### Event Detail Pages

Current implementation (as of 2025-11-24):

```html
<div class="quote">
  <span class="quote-label">🔬 Safety Researcher Reaction:</span>
  <span class="provenance-badge provenance-real">✓ Verified Quote</span>
  <br>
  "This is the worst funding crisis in EA history"
  <span class="quote-source">
    — Scott Alexander (2022-11-16) (<a href="...">source</a>)
  </span>
</div>
```

**Visual indicators**:
- 🟢 Green badge: `✓ Verified Quote` (real_quote)
- 🔵 Blue badge: `ℹ️ Summary (Not Direct Quote)` (human_summary)
- 🟠 Orange badge: `⚠️ Placeholder - Needs Real Quote` (placeholder)
- 🔘 Gray badge: `N/A` (not_applicable)

### Quote Suggestion Button

Added to every event page:
```html
<a href="/events/suggest-quote.html?event={event_id}" class="suggest-quote-button">
  💡 Found a Real Quote? Suggest it here
</a>
```

---

## Game Integration

Quotes can be used in multiple game contexts:

### 1. Event Cards
Show the quote when an event is drawn:
```
📰 Event: FTX Future Fund Collapse (2022)

Scott Alexander: "This is the worst funding crisis in EA history"

Impacts:
- Funding: -50
- Community Morale: -20
```

### 2. Historical Timeline
Display quotes in the game's event log:
```
2022-11-10: FTX Future Fund collapses
"Well, that's not optimal" - Eliezer Yudkowsky
```

### 3. Quote Carousel
Rotate through multiple quotes for major events:
```
> "This is the worst funding crisis in EA history"
  — Scott Alexander, 2022-11-16

[Next Quote] [View All 5 Reactions]
```

### 4. Character Commentary
NPC researchers can reference real quotes:
```
Dr. Safety: "Remember when Scott Alexander said it was the worst
             funding crisis in EA history? He wasn't wrong."
```

---

## Data Quality Standards

### Required for `real_quote` Status:
- ✅ Direct URL to source (must be live and accessible)
- ✅ Exact quote (no paraphrasing)
- ✅ Verified author identity
- ✅ Date within reasonable proximity to event
- ✅ Public source (not private messages/emails)

### Disqualifying Factors:
- ❌ Paraphrased or summarized content
- ❌ Anonymous sources
- ❌ Dead links or paywalled content
- ❌ Quote taken out of context
- ❌ Unverified social media accounts

---

## Migration Plan

### Phase 1: Infrastructure (✅ Complete)
- [x] Add `reaction_provenance` metadata field
- [x] Create quote suggestion form
- [x] Add visual badges to event pages
- [x] Document quote database schema

### Phase 2: Initial Curation (In Progress)
- [ ] Audit 28 custom events for real quote opportunities
- [ ] Search LessWrong for high-impact event commentary
- [ ] Identify top 20 events that need real quotes most
- [ ] Replace at least 10 placeholder quotes with real ones

### Phase 3: Community Sourcing (Planned)
- [ ] Announce quote sourcing campaign
- [ ] Set up moderation workflow for quote submissions
- [ ] Create leaderboard for top quote contributors
- [ ] Integrate top 100 real quotes

### Phase 4: Automation (Future)
- [ ] Build LessWrong comment scraper
- [ ] Create Twitter monitoring bot
- [ ] Set up EA Forum RSS tracking
- [ ] Implement quote quality scoring

---

## Example Events to Prioritize

High-impact events that deserve real quotes:

### Top Priority
1. **FTX Future Fund Collapse** (2022) - Massive impact, well-documented
2. **OpenAI Fires Sam Altman** (2023) - Huge media coverage
3. **GPT-4 Release** (2023) - Major capability advance
4. **Anthropic's Constitutional AI** (2022) - Technical breakthrough
5. **AI Safety Camp** (multiple years) - Community building

### Good Sources to Mine
- **Scott Alexander's Substack** - ACX coverage of AI safety events
- **LessWrong** - Eliezer, Paul Christiano, Nate Soares comments
- **Rob Miles YouTube** - Video commentary on major events
- **AI Alignment Forum** - Technical researcher reactions
- **Twitter threads** - Real-time reactions from AI safety community

---

## Statistics Tracking

Add to `events-sync-summary.json`:

```json
{
  "quote_quality_stats": {
    "total_events": 977,
    "events_with_real_quotes": 0,
    "events_with_summaries": 28,
    "events_with_placeholders": 949,
    "completion_percentage": 0.0,
    "quotes_by_platform": {
      "lesswrong": 0,
      "ea_forum": 0,
      "twitter": 0,
      "blog": 0,
      "news": 0,
      "academic": 0
    }
  }
}
```

**Goal**: Reach 10% real quotes by Q2 2025 (98 events)

---

## Related Documentation

- [Event Metadata Specification](./EVENT_METADATA_SPECIFICATION.md)
- [Event Filtering Summary](./EVENT_FILTERING_SUMMARY.md)
- [Quote Suggestion Form](/events/suggest-quote.html)
- [Event Schema v1](https://github.com/PipFoweraker/pdoom-data/blob/main/config/schemas/event_v1.json)

---

**Status**: 🚀 Infrastructure Complete, Ready for Curation

**Next Steps**:
1. Test quote suggestion form with sample submission
2. Begin manual curation of top 20 high-impact events
3. Search LessWrong for existing real quotes
4. Upgrade first 10 events from placeholder → real_quote
