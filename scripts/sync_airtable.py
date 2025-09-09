#!/usr/bin/env python3
"""
Sync blog posts and changelog entries from Airtable into static JSON files in public/data/.
- Reads environment variables: AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_BLOG_TABLE, AIRTABLE_CHANGELOG_TABLE
- Writes: public/data/blog.json, public/data/changes.json
Usage: python scripts/sync_airtable.py
"""
import json, os, sys, time
from urllib.request import Request, urlopen
from urllib.parse import urlencode

API_KEY = os.getenv('AIRTABLE_API_KEY')
BASE_ID = os.getenv('AIRTABLE_BASE_ID')
BLOG_TABLE = os.getenv('AIRTABLE_BLOG_TABLE', 'Blog')
CHANGELOG_TABLE = os.getenv('AIRTABLE_CHANGELOG_TABLE', 'Changelog')

if not (API_KEY and BASE_ID):
    print('Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID', file=sys.stderr)
    sys.exit(1)

API_ROOT = f"https://api.airtable.com/v0/{BASE_ID}"
HEADERS = { 'Authorization': f'Bearer {API_KEY}' }


def fetch_table(table_name: str, view: str = None):
    records = []
    offset = None
    params = { 'pageSize': 100 }
    if view:
        params['view'] = view
    while True:
        if offset:
            params['offset'] = offset
        url = f"{API_ROOT}/{table_name}?{urlencode(params)}"
        req = Request(url, headers=HEADERS)
        with urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        records.extend(data.get('records', []))
        offset = data.get('offset')
        if not offset:
            break
        time.sleep(0.2)  # be polite
    return records


def map_blog(records):
    out = []
    for r in records:
        f = r.get('fields', {})
        out.append({
            'id': f.get('slug') or r.get('id'),
            'title': f.get('title'),
            'excerpt': f.get('excerpt'),
            'published_at': f.get('published_at'),
            'tags': f.get('tags') or [],
            'published': bool(f.get('published', True)),
        })
    # newest first
    out.sort(key=lambda x: (x.get('published_at') or ''), reverse=True)
    return { 'posts': out }


def map_changes(records):
    out = []
    for r in records:
        f = r.get('fields', {})
        items = f.get('items') or []
        # Airtable multi-line text split to bullets if needed
        if isinstance(items, str):
            items = [x.strip('- ')] if '\n' not in items else [i.strip('- ') for i in items.splitlines() if i.strip()]
        out.append({
            'version': f.get('version'),
            'date': f.get('date'),
            'channel': f.get('channel'),
            'summary': f.get('summary'),
            'items': items,
        })
    # newest first by date
    out.sort(key=lambda x: (x.get('date') or ''), reverse=True)
    return { 'entries': out }


def main():
    blog_records = fetch_table(BLOG_TABLE)
    change_records = fetch_table(CHANGELOG_TABLE)

    blog = map_blog(blog_records)
    changes = map_changes(change_records)

    os.makedirs('public/data', exist_ok=True)
    with open('public/data/blog.json', 'w', encoding='utf-8') as f:
        json.dump(blog, f, indent=2, ensure_ascii=False)
    with open('public/data/changes.json', 'w', encoding='utf-8') as f:
        json.dump(changes, f, indent=2, ensure_ascii=False)
    print('Wrote public/data/blog.json and public/data/changes.json')

if __name__ == '__main__':
    main()
