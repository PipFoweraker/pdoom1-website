#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tag newsletter events with exclusion metadata

This script marks all Alignment Newsletter events with appropriate metadata
so they can be filtered out from the game event list.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Paths
SCRIPT_DIR = Path(__file__).parent
WEBSITE_ROOT = SCRIPT_DIR.parent.parent
PDOOM_DATA_PATH = WEBSITE_ROOT.parent / "pdoom-data"

EVENTS_FILE = PDOOM_DATA_PATH / "data/serveable/api/timeline_events/all_events.json"
BACKUP_DIR = WEBSITE_ROOT / "scripts/sync/backups"

def log(msg):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def create_backup():
    """Create timestamped backup"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"all_events_before_newsletter_tagging_{timestamp}.json"

    log(f"Creating backup: {backup_file.name}")
    with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log(f"✓ Backup saved: {backup_file}")
    return backup_file

def tag_newsletter_events():
    """Tag all newsletter events with exclusion metadata"""
    log("Loading events...")
    with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
        events = json.load(f)

    log(f"Total events: {len(events)}")

    # Find newsletter events
    newsletter_events = []
    for event_id, event in events.items():
        tags = event.get('tags', [])
        if 'newsletters' in tags:
            newsletter_events.append(event_id)

    log(f"Found {len(newsletter_events)} newsletter events")

    # Tag them
    tagged_count = 0
    for event_id in newsletter_events:
        event = events[event_id]

        # Add event_status
        event['event_status'] = 'newsletter_archive'

        # Add reaction_provenance
        event['reaction_provenance'] = {
            'safety_researcher_reaction': 'not_applicable',
            'media_reaction': 'not_applicable'
        }

        # Mark as not game ready
        event['game_ready'] = False

        tagged_count += 1

    log(f"✓ Tagged {tagged_count} events")

    # Save updated events
    log("Saving updated events...")
    with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

    log(f"✓ Saved to {EVENTS_FILE}")

    return {
        'total_events': len(events),
        'newsletter_events': len(newsletter_events),
        'tagged': tagged_count
    }

def print_summary(stats, backup_file):
    """Print summary of tagging operation"""
    print("\n" + "="*80)
    print("NEWSLETTER TAGGING SUMMARY")
    print("="*80)
    print(f"✓ Backup created: {backup_file.name}")
    print(f"✓ Total events: {stats['total_events']}")
    print(f"✓ Newsletter events found: {stats['newsletter_events']}")
    print(f"✓ Events tagged: {stats['tagged']}")
    print()
    print("Tagged events with:")
    print("  - event_status: 'newsletter_archive'")
    print("  - reaction_provenance: 'not_applicable'")
    print("  - game_ready: false")
    print()
    print("Next steps:")
    print("1. Run sync to regenerate website: npm run events:sync-data-only")
    print("2. Verify newsletter events are filtered out")
    print("3. Commit changes to pdoom-data repository")
    print("="*80 + "\n")

def main():
    """Main execution"""
    print("\n" + "="*80)
    print("TAG NEWSLETTER EVENTS")
    print("="*80 + "\n")

    try:
        # Create backup
        backup_file = create_backup()

        # Tag newsletter events
        stats = tag_newsletter_events()

        # Print summary
        print_summary(stats, backup_file)

        log("✅ Tagging complete!")
        return 0

    except Exception as e:
        log(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
