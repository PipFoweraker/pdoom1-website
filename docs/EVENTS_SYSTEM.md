# Events System Documentation

**Project**: pdoom1-website
**Purpose**: Public-facing documentation wiki for in-game events
**Last Updated**: 2025-11-24

---

## Overview

The Events System provides a public-facing, community-editable documentation wiki for all timeline events in p(Doom)1. Events are sourced from the [pdoom-data repository](https://github.com/PipFoweraker/pdoom-data), transformed for gameplay, and displayed on the website with full filtering, search, and contribution capabilities.

### Key Features

- ✅ **1000+ Events**: Comprehensive catalog of 1028 alignment research and AI safety events
- ✅ **Automated Sync**: Daily sync from pdoom-data repository via GitHub Actions
- ✅ **Filterable Interface**: Search, filter by category, rarity, year
- ✅ **Bulk Selection**: Multi-select events and suggest metadata changes for multiple events at once
- ✅ **Individual Event Pages**: Detailed pages for each event with sources and game impacts
- ✅ **Community Contributions**: Direct links to suggest changes in pdoom-data
- ✅ **Game Icons**: Automatically synced from pdoom1 repository
- ✅ **SEO Optimized**: Each event has its own canonical URL and meta tags

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    pdoom-data Repository                     │
│  (Source of Truth for Event Data)                           │
│                                                              │
│  data/serveable/api/timeline_events/all_events.json         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Daily Sync via GitHub Actions
                       │ (.github/workflows/sync-events.yml)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               pdoom1-website Repository                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ scripts/sync/sync-events.py                            │ │
│  │   - Reads all_events.json                              │ │
│  │   - Generates individual event HTML pages              │ │
│  │   - Creates public/data/events.json index              │ │
│  └────────────────────────────────────────────────────────┘ │
│                       │                                      │
│                       ▼                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Generated Files:                                        │ │
│  │   - public/events/index.html (events browser)          │ │
│  │   - public/events/{event_id}.html (detail pages)       │ │
│  │   - public/data/events.json (index data)               │ │
│  │   - public/assets/icons/events/*.png (game icons)      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                       │
                       │ Deployed via Netlify
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  https://pdoom1.com/events/                  │
│                                                              │
│  Users can:                                                  │
│   - Browse all events                                        │
│   - Filter by category/rarity/year                          │
│   - Search events                                            │
│   - View detailed event pages                               │
│   - Click "Suggest Change" → Opens GitHub issue             │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Event Creation (pdoom-data)

Events are created/modified in the pdoom-data repository:

```
pdoom-data/
├── data/raw/events/
│   ├── funding_catastrophe_events.json
│   ├── historical_events.json
│   ├── institutional_decay_events.json
│   ├── organizational_crisis_events.json
│   └── technical_research_breakthrough_events.json
│
└── data/serveable/api/timeline_events/
    ├── all_events.json (master file)
    └── event_index.json
```

### 2. Automated Sync (Daily)

GitHub Actions workflow runs daily at 3 AM UTC:

```yaml
# .github/workflows/sync-events.yml
1. Checkout pdoom1-website
2. Clone pdoom-data repository
3. Clone pdoom1 repository (for icons)
4. Run sync-events.py script
5. Commit changes if event data updated
```

### 3. Manual Sync (Local Development)

```bash
# Sync events and icons
npm run events:sync

# Or sync data only (no icons)
npm run events:sync-data-only

# Or just sync icons
npm run icons:sync
```

### 4. Generated Output

The sync script generates:

```
public/
├── events/
│   ├── index.html                    # Main events browser
│   ├── ftx_future_fund_collapse_2022.html
│   ├── openai_board_crisis_2023.html
│   └── ... (one HTML file per event)
│
├── data/
│   ├── events.json                   # Event index for frontend
│   └── events-sync-summary.json      # Sync statistics
│
└── assets/icons/events/
    ├── funding_catastrophe_128.png
    └── ... (event category icons)
```

---

## Event Schema

Events follow the [pdoom-data event schema v1](https://github.com/PipFoweraker/pdoom-data/blob/main/config/schemas/event_v1.json):

```json
{
  "id": "ftx_future_fund_collapse_2022",
  "title": "FTX Future Fund Collapse",
  "year": 2022,
  "category": "funding_catastrophe",
  "description": "$32M+ in AI safety grants vanished overnight...",
  "impacts": [
    {
      "variable": "cash",
      "change": -80,
      "condition": null
    }
  ],
  "sources": [
    "https://fortune.com/..."
  ],
  "tags": ["cryptocurrency", "effective_altruism"],
  "rarity": "rare",
  "pdoom_impact": null,
  "safety_researcher_reaction": "Devastating blow...",
  "media_reaction": "Crypto collapse takes down AI safety..."
}
```

### Event Categories

- `funding_catastrophe` 💸 - Financial disasters affecting AI safety orgs
- `organizational_crisis` 🏢 - Internal organizational problems
- `technical_research_breakthrough` 🔬 - Research discoveries
- `institutional_decay` ⚠️ - Degradation of institutions
- `policy_development` 📜 - Policy/regulatory changes
- `public_awareness` 📢 - Public perception shifts
- `capability_advance` 🚀 - AI capability breakthroughs
- `alignment_breakthrough` 🎯 - Alignment research wins
- `governance_milestone` ⚖️ - Governance achievements

### Rarity Levels

- `common` ⚪ - Frequently occurs in game
- `rare` 🔵 - Occasionally occurs
- `legendary` ✨ - Very rare, high-impact events

---

## File Structure

```
pdoom1-website/
├── public/
│   └── events/
│       └── index.html                 # Main events browser (hand-coded)
│
├── scripts/
│   └── sync/
│       ├── sync-events.py            # Main sync script
│       └── sync-game-icons.py        # Icon sync script
│
├── .github/workflows/
│   └── sync-events.yml               # Automated sync workflow
│
├── docs/
│   ├── EVENTS_SYSTEM.md              # This file
│   └── DOWNLOAD_LINKS_SPECIFICATION.md
│
└── package.json                       # Added npm scripts
```

---

## Usage

### For Developers

#### Initial Setup

```bash
# Ensure sibling repos are cloned
cd "g:\Documents\Organising Life\Code"
git clone https://github.com/PipFoweraker/pdoom-data.git
git clone https://github.com/PipFoweraker/pdoom1.git
git clone https://github.com/PipFoweraker/pdoom1-website.git

cd pdoom1-website

# First sync (includes icons)
npm run events:sync
```

#### Daily Development

```bash
# Sync latest events from pdoom-data
npm run events:sync-data-only

# View locally
npm start
# Visit http://localhost:5173/events/
```

#### Testing Changes

```bash
# Make changes to public/events/index.html
# Test filters, search, UI changes

# Events data is in public/data/events.json
# Individual event pages in public/events/{event_id}.html
```

### For Content Contributors

#### Suggesting Event Changes

1. **Visit Event Page**: Browse to https://pdoom1.com/events/
2. **Find Event**: Use filters/search to locate event
3. **Click Event Card**: Opens detail page
4. **Click "Report Event Data Issue"**: Opens GitHub issue in pdoom-data
5. **Describe Change**: What's wrong, what should it be, sources

#### Adding New Events

1. Visit [pdoom-data repository](https://github.com/PipFoweraker/pdoom-data)
2. Navigate to `data/raw/events/`
3. Add event to appropriate category file
4. Submit pull request
5. Once merged, sync runs automatically within 24 hours

---

## Sync Script Details

### `sync-events.py`

**Purpose**: Main sync script that pulls event data and generates HTML pages

**Arguments**:
- `--pdoom-data-path PATH` - Path to pdoom-data repo (default: `../pdoom-data`)
- `--pdoom1-path PATH` - Path to pdoom1 repo (default: `../pdoom1`)
- `--sync-icons` - Also sync game icons

**What it does**:
1. Loads `all_events.json` from pdoom-data
2. Generates individual HTML detail page for each event
3. Creates `events.json` index file
4. Optionally copies game icons (128px) from pdoom1
5. Creates sync summary report

**Example**:
```bash
python scripts/sync/sync-events.py --sync-icons
```

**Output**:
```
[2025-11-24 10:30:00] [INFO] Ensured directories exist
[2025-11-24 10:30:01] [INFO] Loaded 42 events from pdoom-data
[2025-11-24 10:30:02] [INFO] Generated 42 event detail pages
[2025-11-24 10:30:02] [INFO] Wrote events index to public/data/events.json
[2025-11-24 10:30:03] [INFO] Synced 15 event icons from pdoom1
[2025-11-24 10:30:03] [INFO] ✅ Sync complete! 42 events processed
```

### `sync-game-icons.py`

**Purpose**: Sync game icons from pdoom1 to website

**Arguments**:
- `--pdoom1-path PATH` - Path to pdoom1 repo
- `--size 128` - Icon size to sync (64, 128, 256, 512, 1024)

**Example**:
```bash
python scripts/sync/sync-game-icons.py --size 128
```

---

## GitHub Actions Workflow

### `sync-events.yml`

**Trigger**:
- Daily at 3 AM UTC (cron schedule)
- Manual via GitHub Actions UI
- Repository dispatch from pdoom-data (when events updated)

**Process**:
1. Checkout website repo
2. Clone pdoom-data and pdoom1 repos
3. Run sync-events.py with --sync-icons
4. Check for file changes
5. If changed, commit and push
6. Generate summary report

**Viewing Runs**:
https://github.com/PipFoweraker/pdoom1-website/actions/workflows/sync-events.yml

---

## Frontend Features

### Events Index Page (`/events/`)

**Features**:
- Grid layout with event cards (1028 events)
- Live statistics (total events, categories, legendary count)
- Filter by category, rarity, year range
- Real-time search by title, description, tags
- **Bulk selection**: Checkboxes on each event card for multi-select
- **Bulk metadata suggestions**: Select multiple events and suggest changes in one GitHub issue
- Select all/clear all functionality
- Visual feedback for selected events (orange outline)
- Responsive design
- Contribution banner linking to GitHub

**Bulk Selection Workflow**:
1. User clicks checkboxes on event cards (or "Select All")
2. Bulk toolbar appears showing selection count
3. Click "Suggest Metadata for Selected" button
4. Opens GitHub issue with all selected events listed
5. Pre-filled template for bulk metadata changes (category, rarity, tags, impacts)

**Tech Stack**:
- Vanilla JavaScript (no framework)
- Fetch API for loading events.json
- CSS Grid for responsive layout
- Event delegation for filter buttons
- Set() for efficient selection tracking

### Event Detail Pages (`/events/{event_id}.html`)

**Features**:
- Full event description
- Game impacts table with color-coded changes
- Safety researcher and media reactions (quotes)
- Source links (clickable, verified)
- Tags for categorization
- Contribution links (GitHub issues)
- Breadcrumb navigation

**Generated Per Event**: Yes (one .html file per event)

---

## Maintenance

### Adding New Event Categories

1. **Update Schema** (pdoom-data):
   ```json
   // config/schemas/event_v1.json
   "category": {
     "enum": [
       "existing_category",
       "new_category"  // Add here
     ]
   }
   ```

2. **Update Website Icons**:
   ```javascript
   // public/events/index.html
   const categoryIcons = {
     'new_category': '🆕',
   };
   ```

3. **Add Filter Button**:
   ```html
   <button class="filter-btn" data-filter="new_category">🆕 New Category</button>
   ```

### Updating Event Data

**Direct Method** (Fast):
1. Edit event in pdoom-data repo
2. Commit and push to main
3. Manually trigger sync workflow OR wait for daily sync

**Local Testing** (Recommended):
1. Edit event in local pdoom-data clone
2. Run `npm run events:sync` in website repo
3. Test at http://localhost:5173/events/
4. Once verified, commit to pdoom-data
5. Re-sync website

### Troubleshooting

**Problem**: Events not loading on website
**Solution**: Check `public/data/events.json` exists and is valid JSON

**Problem**: Sync script fails
**Solution**:
```bash
# Check pdoom-data location
ls ../pdoom-data/data/serveable/api/timeline_events/all_events.json

# Run sync with verbose output
python scripts/sync/sync-events.py --sync-icons 2>&1 | tee sync.log
```

**Problem**: Event page shows 404
**Solution**: Event ID mismatch. Verify:
- Event ID in all_events.json matches filename
- Event ID is snake_case (lowercase, underscores only)

---

## Performance Considerations

### Page Load

- Events index: ~30KB HTML + ~50KB events.json
- Individual event pages: ~15KB each (static HTML)
- Icons: 128px PNGs (~10-20KB each)

**Total bandwidth per visit**:
- First visit (index): ~80KB + icons
- Event detail page: ~15KB (cached CSS)

### Build Time

- Sync script runtime: ~5-10 seconds for 50 events
- GitHub Actions job: ~2-3 minutes (includes repo cloning)

### Caching

- Netlify CDN caches all static files
- events.json cached with 1-hour TTL
- Event detail pages cached indefinitely (immutable URLs)

---

## Future Enhancements

### Planned Features

- [ ] **Event Timeline View**: Visual timeline with year markers
- [ ] **Impact Calculator**: Show cumulative impact of multiple events
- [ ] **Event Comparison**: Side-by-side comparison of 2+ events
- [ ] **RSS Feed**: Subscribe to new event additions
- [ ] **JSON API Endpoint**: `/api/events.json` for external use
- [ ] **Event Tags Page**: Browse events by tag
- [ ] **Related Events**: Show similar/related events on detail pages

### Community Requests

- [ ] Export events as CSV
- [ ] Print-friendly event pages
- [ ] Dark/light mode toggle
- [ ] Event of the Day feature
- [ ] Integration with game leaderboards (show events from player's game)

---

## Related Documentation

- [pdoom-data Event Schema](https://github.com/PipFoweraker/pdoom-data/blob/main/config/schemas/event_v1.json)
- [pdoom-data README](https://github.com/PipFoweraker/pdoom-data/blob/main/README.md)
- [Download Links Specification](./DOWNLOAD_LINKS_SPECIFICATION.md)
- [Deployment Instructions](../DEPLOYMENT_INSTRUCTIONS.md)

---

## Contributing

### Reporting Bugs

Found a bug in the events system? [Open an issue](https://github.com/PipFoweraker/pdoom1-website/issues/new?labels=events&title=[Events]%20)

### Suggesting Event Changes

Want to improve event data? [Submit to pdoom-data](https://github.com/PipFoweraker/pdoom-data/issues/new)

### Code Contributions

1. Fork pdoom1-website
2. Create feature branch: `git checkout -b feature/events-enhancement`
3. Make changes to `public/events/index.html` or `scripts/sync/sync-events.py`
4. Test locally: `npm run events:sync && npm start`
5. Submit pull request

---

**Status**: ✅ Implemented and Documented
**Last Sync**: Run `npm run events:sync` to check
**Website**: https://pdoom1.com/events/
**Maintainer**: See GitHub repository
