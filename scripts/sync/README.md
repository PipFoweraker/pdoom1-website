# Sync Scripts

Scripts for synchronizing external data sources into the pdoom1-website.

## Scripts

### `merge-alignment-events.py`

Merges 1000 alignment research events from pdoom-data into the master events list.

**Usage**:
```bash
python scripts/sync/merge-alignment-events.py
```

**What it does**:
1. Backs up current `all_events.json` in pdoom-data
2. Loads 1000 alignment research events from `alignment_research/alignment_research_events.json`
3. Detects potential duplicates (ID collisions, similar titles)
4. Merges events non-destructively (existing events take precedence)
5. Generates duplicate detection report

**Output**:
- `scripts/sync/backups/all_events_backup_*.json` - Backup of previous version
- `public/data/duplicate-detection-report.json` - Duplicate analysis
- Updates `all_events.json` in pdoom-data with merged events (1028 total)

**Note**: This is a one-time migration script. After initial merge, use `sync-events.py` for ongoing syncs.

### `sync-events.py`

Syncs game events from the pdoom-data repository to the website (1028 events).

**Usage**:
```bash
# Sync events and icons
python scripts/sync/sync-events.py --sync-icons

# Sync events only (no icons)
python scripts/sync/sync-events.py

# Custom paths
python scripts/sync/sync-events.py \
  --pdoom-data-path /path/to/pdoom-data \
  --pdoom1-path /path/to/pdoom1 \
  --sync-icons
```

**npm shortcuts**:
```bash
npm run events:sync              # Events + icons
npm run events:sync-data-only    # Events only
```

**What it does**:
1. Reads `all_events.json` from pdoom-data repository
2. Generates individual HTML detail pages for each event
3. Creates `public/data/events.json` index file
4. Optionally syncs game icons from pdoom1 repository
5. Creates sync summary report

**Output**:
- `public/events/{event_id}.html` - Individual event pages
- `public/data/events.json` - Event index for frontend
- `public/data/events-sync-summary.json` - Sync statistics
- `public/assets/icons/events/*.png` - Game icons (if --sync-icons)

### `sync-game-icons.py`

Syncs game icons from the pdoom1 repository.

**Usage**:
```bash
# Sync 128px icons (default, best for web)
python scripts/sync/sync-game-icons.py

# Sync different size
python scripts/sync/sync-game-icons.py --size 256

# Custom path
python scripts/sync/sync-game-icons.py --pdoom1-path /path/to/pdoom1
```

**npm shortcuts**:
```bash
npm run icons:sync    # Sync 128px icons
```

**Output**:
- `public/assets/icons/game/*.png` - Game icons

## Requirements

**Python 3.11+**

**Directory Structure** (sibling repos):
```
Code/
├── pdoom-data/          # Event data source
├── pdoom1/              # Game icons source
└── pdoom1-website/      # This repo
    └── scripts/sync/    # These scripts
```

## Automated Sync

Events are automatically synced daily via GitHub Actions:
- Workflow: `.github/workflows/sync-events.yml`
- Schedule: Daily at 3 AM UTC
- Manual trigger: GitHub Actions UI → Run workflow

## Documentation

See [docs/EVENTS_SYSTEM.md](../../docs/EVENTS_SYSTEM.md) for complete documentation.
