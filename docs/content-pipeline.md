# Content pipeline: Blog + Changelog via Airtable

This site renders `public/blog/` and `public/changelog/` from static JSON in `public/data/`:
- `public/data/blog.json` → Blog list
- `public/data/changes.json` → Changelog entries

## Authoring flow (recommended)
1. Authors edit content in Airtable (predefined schema below).
2. GitHub Action `Sync Airtable to JSON` runs on schedule or manually.
3. Action writes/commits the JSON into `public/data/`.
4. DreamHost deploy workflow publishes updated static files.

## Airtable schema (suggested)
Blog table (AIRTABLE_BLOG_TABLE, default "Blog"):
- title (Single line text)
- slug (Single line text)
- excerpt (Long text)
- published_at (Date)
- tags (Multiple select)
- published (Checkbox)

Changelog table (AIRTABLE_CHANGELOG_TABLE, default "Changelog"):
- version (Single line text)
- date (Date)
- channel (Single select: alpha/beta/stable)
- summary (Long text)
- items (Long text or multiple lines)

## Setup
- Create repository secrets:
  - AIRTABLE_API_KEY
  - AIRTABLE_BASE_ID
  - (optional) AIRTABLE_BLOG_TABLE
  - (optional) AIRTABLE_CHANGELOG_TABLE
- Manually trigger the `Sync Airtable to JSON` workflow or wait for the schedule.
- Run the DreamHost deploy workflow to publish.

## Local development
You can run the sync locally:

```bash
# Set environment variables in your shell (PowerShell or bash)
# Example for bash:
export AIRTABLE_API_KEY=your_key
export AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
export AIRTABLE_BLOG_TABLE=Blog
export AIRTABLE_CHANGELOG_TABLE=Changelog
python scripts/sync_airtable.py
```

Then open http://localhost:5500/blog/ and http://localhost:5500/changelog/.
