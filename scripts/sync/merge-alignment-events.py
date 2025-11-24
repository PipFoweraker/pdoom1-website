#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge alignment research events into all_events.json

This script:
1. Backs up current all_events.json
2. Loads 1000 alignment research events
3. Detects potential duplicates for manual review
4. Merges events non-destructively (existing events take precedence)
5. Generates duplicate detection report
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Paths
SCRIPT_DIR = Path(__file__).parent
WEBSITE_ROOT = SCRIPT_DIR.parent.parent
PDOOM_DATA_PATH = WEBSITE_ROOT.parent / "pdoom-data"

CURRENT_EVENTS = PDOOM_DATA_PATH / "data/serveable/api/timeline_events/all_events.json"
ALIGNMENT_EVENTS = PDOOM_DATA_PATH / "data/serveable/api/timeline_events/alignment_research/alignment_research_events.json"
BACKUP_DIR = WEBSITE_ROOT / "scripts/sync/backups"
REPORT_FILE = WEBSITE_ROOT / "public/data/duplicate-detection-report.json"

def log(msg):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def similarity_ratio(a, b):
    """Calculate similarity between two strings (0.0 to 1.0)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def load_events():
    """Load both event datasets"""
    log("Loading current events...")
    with open(CURRENT_EVENTS, 'r', encoding='utf-8') as f:
        current = json.load(f)

    log("Loading alignment research events...")
    with open(ALIGNMENT_EVENTS, 'r', encoding='utf-8') as f:
        alignment = json.load(f)

    log(f"✓ Current events: {len(current)} (dictionary)")
    log(f"✓ Alignment events: {len(alignment)} (array)")

    return current, alignment

def create_backup(current_events):
    """Create timestamped backup of current events"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"all_events_backup_{timestamp}.json"

    log(f"Creating backup: {backup_file.name}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(current_events, f, indent=2, ensure_ascii=False)

    log(f"✓ Backup saved: {backup_file}")
    return backup_file

def detect_duplicates(current_events, alignment_events):
    """Detect potential duplicates between datasets"""
    log("Detecting potential duplicates...")

    duplicates = {
        'id_collisions': [],
        'title_similar': [],
        'year_title_similar': []
    }

    # Convert current events dict to list
    current_list = list(current_events.values())
    current_ids = {e['id'] for e in current_list}

    # Check for ID collisions
    for align_event in alignment_events:
        if align_event['id'] in current_ids:
            duplicates['id_collisions'].append({
                'id': align_event['id'],
                'title': align_event['title'],
                'year': align_event['year']
            })

    # Check for similar titles (potential semantic duplicates)
    for align_event in alignment_events:
        for curr_event in current_list:
            # Skip if same ID (already caught above)
            if align_event['id'] == curr_event['id']:
                continue

            # Check title similarity
            title_sim = similarity_ratio(align_event['title'], curr_event['title'])
            if title_sim > 0.80:
                duplicates['title_similar'].append({
                    'similarity': round(title_sim, 3),
                    'current_event': {
                        'id': curr_event['id'],
                        'title': curr_event['title'],
                        'year': curr_event['year'],
                        'category': curr_event['category']
                    },
                    'alignment_event': {
                        'id': align_event['id'],
                        'title': align_event['title'],
                        'year': align_event['year'],
                        'category': align_event['category']
                    }
                })

            # Check for same year + similar title (>70%)
            if align_event['year'] == curr_event['year'] and title_sim > 0.70:
                duplicates['year_title_similar'].append({
                    'similarity': round(title_sim, 3),
                    'year': align_event['year'],
                    'current_event': {
                        'id': curr_event['id'],
                        'title': curr_event['title']
                    },
                    'alignment_event': {
                        'id': align_event['id'],
                        'title': align_event['title']
                    }
                })

    log(f"✓ ID collisions: {len(duplicates['id_collisions'])}")
    log(f"✓ Title similar (>80%): {len(duplicates['title_similar'])}")
    log(f"✓ Year + title similar (>70%): {len(duplicates['year_title_similar'])}")

    return duplicates

def merge_events(current_events, alignment_events, duplicates):
    """Merge alignment events into current events (non-destructively)"""
    log("Merging events...")

    merged = current_events.copy()
    added_count = 0
    skipped_count = 0

    # Get list of IDs to skip (existing events take precedence)
    skip_ids = {dup['id'] for dup in duplicates['id_collisions']}

    for align_event in alignment_events:
        event_id = align_event['id']

        # Skip if ID collision (preserve existing event)
        if event_id in skip_ids:
            log(f"  ⚠️  Skipping {event_id} (ID collision)")
            skipped_count += 1
            continue

        # Skip if already exists (shouldn't happen, but safety check)
        if event_id in merged:
            log(f"  ⚠️  Skipping {event_id} (already exists)")
            skipped_count += 1
            continue

        # Add event to merged dataset
        merged[event_id] = align_event
        added_count += 1

    log(f"✓ Added: {added_count} events")
    log(f"✓ Skipped: {skipped_count} events (ID collisions)")
    log(f"✓ Total events after merge: {len(merged)}")

    return merged

def save_merged_events(merged_events):
    """Save merged events to all_events.json"""
    log(f"Saving merged events to {CURRENT_EVENTS.name}...")

    with open(CURRENT_EVENTS, 'w', encoding='utf-8') as f:
        json.dump(merged_events, f, indent=2, ensure_ascii=False)

    log(f"✓ Saved {len(merged_events)} events to {CURRENT_EVENTS}")

def save_duplicate_report(duplicates, merged_count):
    """Save duplicate detection report for user review"""
    log("Generating duplicate detection report...")

    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_merged': merged_count,
            'id_collisions': len(duplicates['id_collisions']),
            'title_similar_80': len(duplicates['title_similar']),
            'year_title_similar_70': len(duplicates['year_title_similar'])
        },
        'duplicates': duplicates,
        'recommendations': []
    }

    # Add recommendations
    if duplicates['id_collisions']:
        report['recommendations'].append({
            'type': 'id_collision',
            'severity': 'high',
            'message': f"{len(duplicates['id_collisions'])} events skipped due to ID collisions. Review manually to decide which version to keep."
        })

    if duplicates['title_similar']:
        report['recommendations'].append({
            'type': 'title_similar',
            'severity': 'medium',
            'message': f"{len(duplicates['title_similar'])} events with >80% title similarity. May be semantic duplicates - review manually."
        })

    # Ensure output directory exists
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log(f"✓ Duplicate report saved: {REPORT_FILE}")
    return report

def print_summary(report, backup_file):
    """Print summary of merge operation"""
    print("\n" + "="*80)
    print("MERGE SUMMARY")
    print("="*80)
    print(f"✓ Backup created: {backup_file.name}")
    print(f"✓ Events merged: {report['summary']['total_merged']}")
    print(f"✓ ID collisions (skipped): {report['summary']['id_collisions']}")
    print(f"✓ Similar titles (>80%): {report['summary']['title_similar_80']}")
    print(f"✓ Year + similar title (>70%): {report['summary']['year_title_similar_70']}")
    print()
    print(f"📊 Duplicate report: {REPORT_FILE}")
    print()

    if report['recommendations']:
        print("⚠️  RECOMMENDATIONS:")
        for rec in report['recommendations']:
            print(f"   [{rec['severity'].upper()}] {rec['message']}")
        print()

    print("Next steps:")
    print("1. Review duplicate report: public/data/duplicate-detection-report.json")
    print("2. Manually check similar events and decide which to keep")
    print("3. Run sync to generate HTML pages: npm run events:sync")
    print("="*80 + "\n")

def main():
    """Main execution"""
    print("\n" + "="*80)
    print("MERGE ALIGNMENT RESEARCH EVENTS")
    print("="*80 + "\n")

    try:
        # Load events
        current_events, alignment_events = load_events()

        # Create backup
        backup_file = create_backup(current_events)

        # Detect duplicates
        duplicates = detect_duplicates(current_events, alignment_events)

        # Merge events
        merged_events = merge_events(current_events, alignment_events, duplicates)

        # Save merged events
        save_merged_events(merged_events)

        # Save duplicate report
        report = save_duplicate_report(duplicates, len(merged_events))

        # Print summary
        print_summary(report, backup_file)

        log("✅ Merge complete!")
        return 0

    except Exception as e:
        log(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
