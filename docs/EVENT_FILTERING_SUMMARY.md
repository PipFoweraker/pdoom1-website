# Event Filtering & Reaction Provenance - Summary

**Created**: 2025-11-24
**Status**: Ready to implement

---

## What We've Built

### 1. **Newsletter Event Filtering** (51 events)

**Problem**: Alignment Newsletter editions are imported as individual events, but they're collections/digests, not occurrences.

**Solution**: Tag them with `event_status: "newsletter_archive"` and filter them out from the website.

**Implementation**:
- ✅ Created `scripts/metadata/tag_newsletters.py` - tags all newsletter events
- ✅ Updated `scripts/sync/sync-events.py` - filters events based on `event_status`
- ✅ Documented in `docs/EVENT_METADATA_SPECIFICATION.md`

---

### 2. **Reaction Provenance Tracking**

**Problem**: Can't tell which reactions are:
- Real quotes from LessWrong/blogs
- Human-written summaries
- Generic placeholders

**Solution**: Add `reaction_provenance` metadata to track source quality.

**Current State**:
- **Custom events (28)**: Reactions are human summaries (not real quotes)
- **Alignment research events (949)**: Generic placeholders like "Critical insights for the field"
- **Newsletter events (51)**: Not applicable (being filtered out)

**Metadata Structure**:
```json
{
  "reaction_provenance": {
    "safety_researcher_reaction": {
      "type": "real_quote",
      "source": "https://lesswrong.com/posts/...",
      "author": "Eliezer Yudkowsky",
      "date": "2022-11-15"
    },
    "media_reaction": {
      "type": "human_summary",
      "sources": ["https://fortune.com/..."],
      "notes": "Summary of 5+ articles"
    }
  }
}
```

---

### 3. **Game-Ready Tracking**

**Problem**: Need to know which events have complete, verified metadata.

**Solution**: Add `game_ready` boolean flag.

**Criteria for `game_ready: true`**:
- ✅ Category and rarity assigned
- ✅ Meaningful game impacts
- ✅ Sources verified
- ✅ Reactions are NOT placeholders
- ✅ Description is event-specific

---

## Current Event Breakdown

| Category | Count | Status | Action Needed |
|----------|-------|--------|---------------|
| Newsletter events | 51 | Excluded | None (filtered out automatically) |
| Custom events | 28 | Included | Tag reactions as "human_summary" |
| Alignment research | 949 | Review needed | Community review via website |
| **Total** | **1028** | - | - |

---

## Next Steps (In Order)

### Step 1: Tag Newsletter Events (5 minutes)

```bash
cd "g:\Documents\Organising Life\Code\pdoom1-website"
python scripts/metadata/tag_newsletters.py
```

**What it does**:
- Creates backup of `all_events.json`
- Tags 51 newsletter events with:
  - `event_status: "newsletter_archive"`
  - `reaction_provenance: "not_applicable"`
  - `game_ready: false`

**Result**: Newsletter events marked for exclusion

---

### Step 2: Re-sync Website (2 minutes)

```bash
npm run events:sync-data-only
```

**What it does**:
- Filters out newsletter events (reduces from 1028 → 977 events)
- Generates HTML pages for included events only
- Updates `events-sync-summary.json` with breakdown

**Result**: Website shows 977 events instead of 1028

---

### Step 3: Commit to pdoom-data (5 minutes)

```bash
cd "../pdoom-data"
git status
git add data/serveable/api/timeline_events/all_events.json
git commit -m "Add event_status metadata to filter newsletter events"
git push
```

**Result**: Newsletter tagging saved to source repository

---

### Step 4: Commit to pdoom1-website (5 minutes)

```bash
cd "../pdoom1-website"
git add scripts/metadata/ scripts/sync/sync-events.py docs/
git commit -m "Add event filtering and reaction provenance tracking"
git push
```

**Result**: Filtering logic deployed to production

---

## Future Enhancements (Community-Driven)

### Phase 1: Audit Custom Events (Week 1)
- Review all 28 custom events
- Verify reactions are appropriate
- Mark provenance as `human_summary`
- Identify candidates for real quote replacement

### Phase 2: Community Review (Ongoing)
- Users filter by `review_needed` status
- Bulk select events to exclude/improve
- Suggest better metadata via website
- Mark events `game_ready: true` after review

### Phase 3: Real Quote Integration (Ongoing)
- Search LessWrong/EA Forum/Twitter for reactions
- Find actual quotes from researchers
- Update `reaction_provenance` with sources
- Track author, date, context

---

## Safety Guarantees

✅ **Non-destructive**: Only ADDING fields, not removing data
✅ **Backed up**: Timestamped backups before modification
✅ **Reversible**: Can remove new fields anytime
✅ **Git-tracked**: All changes in version control
✅ **Source preserved**: Original data in pdoom-data unchanged

---

## Files Created/Modified

### New Files:
- `docs/EVENT_METADATA_SPECIFICATION.md` - Full specification
- `docs/EVENT_FILTERING_SUMMARY.md` - This file
- `docs/QUOTE_DATABASE_SCHEMA.md` - Quote sourcing infrastructure
- `scripts/metadata/tag_newsletters.py` - Tagging script
- `public/events/suggest-quote.html` - Quote suggestion form

### Modified Files:
- `scripts/sync/sync-events.py` - Added filtering logic + placeholder badges
- (Soon) `pdoom-data/data/.../all_events.json` - Tagged newsletters

---

## Questions Answered

**Q: Are reactions real or placeholders?**
A: Mixed. Custom events (28) have human summaries. Alignment research events (949) have placeholders. We're tracking this now with `reaction_provenance`.

**Q: What about newsletter events?**
A: 51 newsletter events tagged with `event_status: "newsletter_archive"` and automatically filtered out.

**Q: Is this destructive?**
A: No! We're only adding metadata fields. Originals backed up. Changes reversible.

**Q: Can we track real quotes from LessWrong?**
A: Yes! Use `reaction_provenance` with `type: "real_quote"` and include source, author, date.

---

---

## Placeholder Quote Infrastructure (NEW - 2025-11-24)

### Visual Indicators Added

All event detail pages now show **provenance badges** next to reactions:

- 🟠 **Orange badge**: `⚠️ Placeholder - Needs Real Quote` (placeholder)
- 🔵 **Blue badge**: `ℹ️ Summary (Not Direct Quote)` (human_summary)
- 🟢 **Green badge**: `✓ Verified Quote` (real_quote with source link)
- 🔘 **Gray badge**: `N/A` (not_applicable)

### Quote Suggestion System

Added **"💡 Found a Real Quote? Suggest it here"** button to every event page:

1. Opens `/events/suggest-quote.html` form
2. Pre-populated with event ID
3. Captures: Quote text, author, source URL, date, platform
4. Generates GitHub issue with structured metadata
5. Ready for maintainer review and integration

### Quote Database Schema

Created `docs/QUOTE_DATABASE_SCHEMA.md` documenting:

- Full `reaction_provenance` metadata structure
- Quote selection criteria (relevance, authority, engagement)
- Future multi-quote database for events with multiple reactions
- Integration plan for game (event cards, timeline, character commentary)
- Migration phases: Infrastructure → Curation → Community → Automation

### Current State (All Events)

- **1028 events** regenerated with placeholder badges
- **~949 events** showing orange "Placeholder" badges (alignment research)
- **~28 events** showing orange badges (custom events - will be upgraded to blue "Summary" badges)
- **0 events** with real quotes yet (ready to start sourcing!)

**Next Action**: Begin mining LessWrong, EA Forum, Twitter for real quotes on high-impact events like FTX collapse, GPT-4 release, OpenAI leadership crisis.

---

**Status**: ✅ Ready to Execute + Quote Infrastructure Complete
**Estimated Time**: 20 minutes total (filtering) + Ongoing (quote sourcing)
**Impact**: Cleaner event list, better tracking, foundation for community curation + Real quote integration system

