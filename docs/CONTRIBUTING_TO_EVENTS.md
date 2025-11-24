# Contributing to Events Data

**Welcome!** This guide explains how you can help improve the p(Doom)1 event timeline by contributing real quotes, fixing metadata, and curating event quality.

---

## Quick Overview

The p(Doom)1 timeline contains **1028 events** tracking the history of AI safety research, funding crises, technical breakthroughs, and policy developments. Many events currently have **placeholder reactions** that need to be replaced with real quotes from researchers and media.

**Your contribution matters** because:
- Real quotes make events more authentic and engaging
- Proper sourcing creates a historical record
- Better metadata improves the game experience
- Community curation ensures quality

---

## What Needs Help?

### 🟠 Placeholder Quotes (~949 events)

Most events show this badge: <span style="background: rgba(255, 152, 0, 0.2); border: 1px solid #ff9800; color: #ff9800; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">⚠️ Placeholder - Needs Real Quote</span>

**Example placeholder quote:**
> "Critical insights for the field"

**What we need:**
> Real quotes from LessWrong, EA Forum, Twitter, blogs, or news articles

### 🔵 Human Summaries (~28 events)

Some events show: <span style="background: rgba(33, 150, 243, 0.2); border: 1px solid #2196f3; color: #2196f3; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">ℹ️ Summary (Not Direct Quote)</span>

**These are better than placeholders** but could still be upgraded to real sourced quotes when available.

### 🟢 Real Quotes (0 events - we're just starting!)

Our goal: <span style="background: rgba(76, 175, 80, 0.2); border: 1px solid #4caf50; color: #4caf50; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">✓ Verified Quote</span>

**Example of what we want:**
> "This is the worst funding crisis in EA history"
> — Scott Alexander (2022-11-16) ([source](https://astralcodexten.substack.com/p/...))

---

## How to Contribute

### Option 1: Suggest a Real Quote (Easiest!)

1. **Browse the [Events Timeline](/events/)**
2. **Click on an event** you know about
3. **Look for the placeholder/summary badges** in the Reactions section
4. **Click "💡 Found a Real Quote? Suggest it here"**
5. **Fill out the form** with the quote, author, source link, and date
6. **Submit** - it creates a GitHub issue for review

**Good sources to check:**
- [LessWrong](https://lesswrong.com) - AI safety researcher discussions
- [EA Forum](https://forum.effectivealtruism.org) - Effective altruism community
- [Scott Alexander's blog](https://astralcodexten.substack.com) - ACX coverage of AI safety
- Twitter/X - Real-time reactions from researchers
- News articles - Fortune, MIT Tech Review, TechCrunch, etc.

### Option 2: Fix Event Metadata

If you notice errors in categories, tags, rarities, or game impacts:

1. **Click the event detail page**
2. **Scroll to "🏷️ Event Metadata" section**
3. **Click "→ Suggest different [category/rarity/tags]"**
4. **Opens GitHub issue** - explain what should change and why

### Option 3: Bulk Review (Advanced)

If you're familiar with the AI safety landscape:

1. **Use the [Events Browser](/events/)** table view
2. **Filter by category** (e.g., "funding_catastrophe")
3. **Select multiple events** with checkboxes
4. **Click "Bulk Suggest Metadata"**
5. **Review events systematically** by topic area

---

## Quote Quality Guidelines

### ✅ Good Quotes

**Safety Researcher Reactions:**
- Direct quotes from known AI safety researchers
- Comments on LessWrong, EA Forum with author attribution
- Blog posts analyzing the event's impact
- Conference presentations or papers citing the event

**Media Reactions:**
- Headlines from major publications (Fortune, MIT Tech Review)
- Excerpts from news articles covering the event
- Public statements from organizations
- Social media reactions from verified accounts

### ❌ Bad Quotes

**Don't submit:**
- Paraphrased or summarized content (unless it's your own summary)
- Anonymous sources or unverified accounts
- Private messages or non-public communications
- Quotes taken out of context
- Dead links or paywalled content

### 📋 Required Information

When suggesting a quote, you **must** provide:
- ✅ **Quote text** - The exact words (no paraphrasing)
- ✅ **Author** - Who said/wrote it
- ✅ **Source URL** - Direct link to the quote
- ✅ **Date** - When it was published
- ✅ **Platform** - LessWrong, Twitter, blog, news, etc.

**Optional but helpful:**
- Context (e.g., "Comment on LessWrong thread about FTX collapse")
- Your name (for credit if quote is accepted)

---

## High-Priority Events

These events have significant historical importance and would benefit most from real quotes:

### Top 10 Priority

1. **FTX Future Fund Collapse (2022)** - Massive AI safety funding loss
2. **OpenAI Fires Sam Altman (2023)** - Leadership crisis
3. **GPT-4 Release (2023)** - Major capability advance
4. **Anthropic's Constitutional AI (2022)** - Technical breakthrough
5. **AI Safety Camp Events** - Community building
6. **DeepMind's AlphaFold (2020)** - Capability demonstration
7. **EU AI Act Passage (2024)** - Policy milestone
8. **MIRI Research Program Changes** - Institutional shifts
9. **Pause Giant AI Experiments Letter (2023)** - Public awareness
10. **Superintelligence Book Release (2014)** - Field foundation

### Where to Find Quotes

**Scott Alexander (Astral Codex Ten):**
- Covers major AI safety events in blog posts
- Thoughtful analysis of funding, research, policy
- Check archives for event dates ± 2 weeks

**LessWrong:**
- Search for event title or organization name
- Check "Alignment Forum" tag for technical events
- Look at comment threads from prominent users

**Twitter/X:**
- Search for event name + "AI safety"
- Check accounts: @elonmusk, @sama, @ESYudkowsky, @DarioAmodei
- Use advanced search with date filters

**News Archives:**
- Google News search with date range
- Fortune's AI coverage
- MIT Technology Review's AI section
- TechCrunch's AI category

---

## Review Process

### After You Submit

1. **GitHub issue created** with your quote suggestion
2. **Maintainer reviews** for accuracy and quality
3. **Quote verified** - checks source is valid and quote is accurate
4. **Metadata updated** in pdoom-data repository
5. **Website regenerated** - your contribution goes live!
6. **Credit given** (if you provided your name)

### Timeline

- **Quick reviews**: 24-48 hours for straightforward quotes
- **Complex reviews**: Up to 1 week for verification
- **Batch updates**: Website regenerates daily or on-demand

---

## Technical Details (For Developers)

### Metadata Structure

Quotes are stored in `all_events.json` with this structure:

```json
{
  "id": "ftx_future_fund_collapse_2022",
  "safety_researcher_reaction": "This is the worst funding crisis in EA history",
  "media_reaction": "The collapse has sent shockwaves through the AI safety community",

  "reaction_provenance": {
    "safety_researcher_reaction": {
      "type": "real_quote",
      "source": "https://astralcodexten.substack.com/p/...",
      "author": "Scott Alexander",
      "date": "2022-11-16",
      "platform": "substack"
    },
    "media_reaction": {
      "type": "real_quote",
      "source": "https://fortune.com/...",
      "author": "Fortune Magazine",
      "date": "2022-11-15",
      "platform": "news"
    }
  }
}
```

### Provenance Types

- `"real_quote"` - Verified quote with full attribution
- `"human_summary"` - Human-written summary (not a direct quote)
- `"placeholder"` - Generic placeholder text (default if missing)
- `"not_applicable"` - Event doesn't warrant reactions

### Visual Indicators

The website automatically shows badges based on `reaction_provenance`:

```css
/* Orange - Placeholder */
.provenance-placeholder { background: rgba(255, 152, 0, 0.2); }

/* Blue - Summary */
.provenance-summary { background: rgba(33, 150, 243, 0.2); }

/* Green - Real Quote */
.provenance-real { background: rgba(76, 175, 80, 0.2); }
```

### Sync Process

1. Quotes stored in `pdoom-data/data/serveable/api/timeline_events/all_events.json`
2. Website syncs daily via GitHub Actions (`.github/workflows/sync-events.yml`)
3. Event detail pages regenerated with new badges
4. Manual sync: `npm run events:sync-data-only`

### Scripts

- **Sync events**: `scripts/sync/sync-events.py`
- **Tag newsletters**: `scripts/metadata/tag_newsletters.py`
- **Quote form**: `public/events/suggest-quote.html`

### Documentation

- [Event Metadata Specification](./EVENT_METADATA_SPECIFICATION.md)
- [Quote Database Schema](./QUOTE_DATABASE_SCHEMA.md)
- [Event Filtering Summary](./EVENT_FILTERING_SUMMARY.md)
- [Events System Overview](./EVENTS_SYSTEM.md)

---

## Statistics & Progress

### Current State (2025-11-24)

- **Total Events**: 1028
- **Events with Real Quotes**: 0
- **Events with Summaries**: ~28
- **Events with Placeholders**: ~949
- **Newsletter Events (Excluded)**: 51

### Goals

- **Q1 2025**: 50 real quotes (5% coverage)
- **Q2 2025**: 100 real quotes (10% coverage)
- **End 2025**: 300+ real quotes (30% coverage)

### Top Contributors

Coming soon! We'll track and credit the community members who contribute the most high-quality quotes.

---

## Questions?

### Why are there so many placeholders?

The 949 alignment research events were imported from a database that didn't include reaction quotes. We're now working with the community to source real reactions from the literature.

### Can I suggest multiple quotes for one event?

Yes! Major events often have multiple notable reactions. Submit them separately and we'll track them all. In the future, we may implement a quote carousel for events with multiple high-quality reactions.

### What if I find a quote but don't have a GitHub account?

You can email quotes to [team@pdoom1.com](mailto:team@pdoom1.com) with the subject "Event Quote Suggestion". Include all the required information (quote, author, source, date).

### Will my contributions appear in the game?

Yes! Real quotes will be used in:
- Event card displays when events are drawn
- Historical timeline view in the game
- Character dialogue and commentary
- Event notifications and logs

### How do I know if my quote was accepted?

Check the GitHub issue status, or search for the event on the website. Accepted quotes will show the green "✓ Verified Quote" badge with attribution.

---

## Recognition

We deeply appreciate all contributors who help build this historical record of AI safety. Quality contributions will be:

- ✅ **Credited** in the event metadata (if you provide your name)
- ✅ **Listed** on a future Contributors page
- ✅ **Tracked** in statistics and leaderboards
- ✅ **Used** to improve both the website and game

**Thank you for helping preserve the history of AI safety research!**

---

**Get started**: Browse [Events Timeline](/events/) and look for orange "Placeholder" badges

**Need help?** Open a [GitHub issue](https://github.com/PipFoweraker/pdoom1-website/issues) or email [team@pdoom1.com](mailto:team@pdoom1.com)

**Technical docs**: See [Quote Database Schema](./QUOTE_DATABASE_SCHEMA.md) for developers
