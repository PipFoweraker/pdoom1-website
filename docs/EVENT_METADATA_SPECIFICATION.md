# Event Metadata Specification

**Purpose**: Define metadata standards for event curation, exclusion, and reaction sourcing.

**Last Updated**: 2025-11-24

---

## Overview

This document establishes conventions for metadata fields used to manage the event catalog, particularly for filtering out non-game-worthy events and tracking the provenance of reactions/quotes.

---

## Metadata Fields

### 1. `event_status` (NEW)

**Purpose**: Mark events for inclusion/exclusion from the game.

**Values**:
- `included` (default) - Event is included in game
- `excluded` - Event is permanently excluded
- `review_needed` - Event needs manual review before inclusion
- `newsletter_archive` - Alignment Newsletter editions (excluded by default)

**Usage**:
```json
{
  "id": "alignmentforum_555121ab60501803",
  "title": "[AN #79]: Recursive reward modeling...",
  "event_status": "newsletter_archive",
  ...
}
```

**Filtering Rules**:
- Website should filter out events where `event_status` is `excluded` or `newsletter_archive`
- Events with `review_needed` shown with warning badge
- If field is missing, treat as `included`

---

### 2. `reaction_provenance` (NEW)

**Purpose**: Track the source and quality of `safety_researcher_reaction` and `media_reaction` fields.

**Values**:
- `real_quote` - Direct quote from a real person/publication with source
- `human_summary` - Human-written summary of the event's reception
- `placeholder` - Generic placeholder text (needs replacement)
- `not_applicable` - Event doesn't warrant reactions (e.g., newsletters)

**Structure**:
```json
{
  "reaction_provenance": {
    "safety_researcher_reaction": {
      "type": "real_quote",
      "source": "https://lesswrong.com/posts/...",
      "author": "Eliezer Yudkowsky",
      "date": "2022-11-15",
      "context": "Comment on LessWrong thread about FTX collapse"
    },
    "media_reaction": {
      "type": "human_summary",
      "sources": [
        "https://fortune.com/...",
        "https://www.coindesk.com/..."
      ],
      "summarized_by": "manual_curation",
      "notes": "Summary of 5+ media articles"
    }
  }
}
```

**Simple Version** (for quick tagging):
```json
{
  "reaction_provenance": {
    "safety_researcher_reaction": "placeholder",
    "media_reaction": "human_summary"
  }
}
```

---

### 3. `game_ready` (NEW)

**Purpose**: Flag whether event has complete, game-ready metadata.

**Values**:
- `true` - Event has verified metadata, appropriate impacts, and sourced reactions
- `false` - Event missing critical data or has placeholder content

**Criteria for `game_ready: true`**:
- ✅ Category and rarity assigned
- ✅ Meaningful game impacts defined
- ✅ Sources verified and accessible
- ✅ Reactions are either `real_quote` or `human_summary` (not `placeholder`)
- ✅ Description is event-specific (not generic newsletter boilerplate)

**Usage**:
```json
{
  "id": "ftx_future_fund_collapse_2022",
  "game_ready": true,
  ...
}
```

---

## Current State Assessment

### Newsletter Events (51 total)

**Issue**: Alignment Newsletter editions imported as events - these are collections/digests, not individual occurrences.

**Action**:
```json
{
  "event_status": "newsletter_archive",
  "reaction_provenance": {
    "safety_researcher_reaction": "not_applicable",
    "media_reaction": "not_applicable"
  },
  "game_ready": false
}
```

**Count**: 51 events tagged with `newsletters` tag

---

### Custom Events (28 total)

**Current State**:
- ✅ Well-defined impacts
- ✅ Real sources
- ⚠️  Reactions are **human summaries**, not real quotes
- ✅ Most are game-ready

**Action Needed**:
```json
{
  "event_status": "included",
  "reaction_provenance": {
    "safety_researcher_reaction": "human_summary",
    "media_reaction": "human_summary"
  },
  "game_ready": true
}
```

**Future Enhancement**: Replace summaries with real quotes from LessWrong, EA Forum, Twitter, blog comments where possible.

---

### Alignment Research Events (949 remaining)

**Current State**:
- ⚠️  Many have generic placeholder reactions like "Critical insights for the field"
- ⚠️  Impacts may be generic (research +10, vibey_doom +5)
- ⚠️  Need manual review for game suitability

**Action Needed**:
```json
{
  "event_status": "review_needed",
  "reaction_provenance": {
    "safety_researcher_reaction": "placeholder",
    "media_reaction": "placeholder"
  },
  "game_ready": false
}
```

---

## Implementation Plan

### Phase 1: Tag Newsletter Events (Immediate)

Create script to auto-tag all events with `newsletters` tag:

```python
# scripts/metadata/tag_newsletters.py
for event in all_events:
    if 'newsletters' in event.get('tags', []):
        event['event_status'] = 'newsletter_archive'
        event['game_ready'] = False
```

### Phase 2: Audit Custom Events (Week 1)

Manually review all 28 custom events:
1. Verify reactions are appropriate summaries
2. Mark provenance as `human_summary`
3. Identify candidates for real quote replacement
4. Add LessWrong/EA Forum links where reactions were sourced

### Phase 3: Review Alignment Research Events (Ongoing)

Community-driven review via website:
1. Filter by `review_needed` status
2. Bulk select events that should be excluded
3. Suggest better impacts, reactions, categories
4. Mark `game_ready: true` after review

### Phase 4: Real Quote Integration (Ongoing)

For high-impact events:
1. Search LessWrong, EA Forum, Twitter for reactions
2. Find actual quotes from researchers
3. Update `reaction_provenance` with source links
4. Track author, date, context

---

## Website Integration

### Filtering Events

Update `sync-events.py` to respect `event_status`:

```python
def should_include_event(event):
    """Filter events for website display"""
    status = event.get('event_status', 'included')

    # Exclude newsletters and explicitly excluded events
    if status in ['newsletter_archive', 'excluded']:
        return False

    # Include all others (included, review_needed)
    return True
```

### Visual Indicators

Events with `review_needed` get a badge:

```html
<span class="review-badge">⚠️ Needs Review</span>
```

Events without `game_ready: true` show warning in detail page:

```html
<div class="metadata-warning">
  This event has placeholder content that needs community review.
  <a href="/events/suggest-metadata.html?event=${event_id}">Help improve it</a>
</div>
```

---

## Statistics Tracking

Track metadata quality in `events-sync-summary.json`:

```json
{
  "sync_timestamp": "2025-11-24T14:27:21",
  "total_events": 1028,
  "included_events": 977,
  "excluded_events": 51,
  "review_needed": 949,
  "game_ready": 28,
  "reaction_quality": {
    "real_quotes": 0,
    "human_summaries": 28,
    "placeholders": 949,
    "not_applicable": 51
  }
}
```

---

## Future Enhancements

### Real Quote Database

Create separate JSON file to track sourced reactions:

```json
{
  "ftx_future_fund_collapse_2022": {
    "researcher_reactions": [
      {
        "author": "Scott Alexander",
        "source": "https://astralcodexten.substack.com/p/...",
        "quote": "This is the worst funding crisis in EA history",
        "date": "2022-11-16",
        "platform": "substack"
      },
      {
        "author": "Rob Miles",
        "source": "https://twitter.com/robertskmiles/status/...",
        "quote": "Losing $32M overnight is catastrophic for alignment research",
        "date": "2022-11-11",
        "platform": "twitter"
      }
    ],
    "media_coverage": [
      {
        "outlet": "Fortune",
        "headline": "FTX collapse takes down AI safety research",
        "url": "https://fortune.com/...",
        "date": "2022-11-15"
      }
    ]
  }
}
```

### Community Sourcing Workflow

1. User finds real quote on LessWrong/Twitter
2. Submits via form with source link
3. Moderator verifies quote is real
4. Quote added to event with provenance
5. Event marked `game_ready: true`

---

## Related Documentation

- [Event Schema v1](https://github.com/PipFoweraker/pdoom-data/blob/main/config/schemas/event_v1.json)
- [Events System Documentation](./EVENTS_SYSTEM.md)
- [Metadata Suggestion Workflow](../public/events/suggest-metadata.html)

---

**Status**: 📋 Specification Draft
**Next Steps**:
1. Create `scripts/metadata/tag_newsletters.py`
2. Update `sync-events.py` filtering logic
3. Add metadata quality badges to website
4. Begin community review campaign
