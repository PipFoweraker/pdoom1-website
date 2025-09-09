# Dev Notes

Quick reference for how this site is wired and how to operate it.

## Hosting and architecture
- Static site: DreamHost (public/ served as the document root)
- Serverless API: Netlify Functions (e.g., POST /api/report-bug)
- Source: GitHub repo (main branch)

## Bug intake (web + game)
- Web form posts to Netlify function: /api/report-bug
- Function validates, rate-limits, dedupes, and dispatches a repository_dispatch to GitHub
- GitHub Action `.github/workflows/bug-report.yml` creates/labels issues, ensures dedupe by marker
- Health check: GET /api/report-bug returns 200 OK JSON when alive

### Configure Netlify env
Set these variables in your Netlify site:
- GITHUB_DISPATCH_TOKEN: a PAT with `repo` scope (ideally fine-scoped)
- GITHUB_REPO: `owner/repo` e.g., `PipFoweraker/pdoom1-website`
- ALLOWED_ORIGIN: comma-separated allowlist of origins (e.g., https://pdoom1.com,https://www.pdoom1.com,http://localhost:5500)
- DRY_RUN: `false` when ready for real dispatches

Then update `public/config.json`:
- `apiBase`: your Netlify site URL (e.g., https://<your-site>.netlify.app)
- `contactEmail`: optional mailto for fallback/contact

## Deploy to DreamHost
- Manual deploy workflow: `.github/workflows/deploy-dreamhost.yml`
- Secrets required in GitHub repo:
  - DH_HOST (e.g., shell.dreamhost.com)
  - DH_USER (your shell user)
  - DH_PATH (absolute path to web root, e.g., /home/USER/example.com)
  - DH_SSH_KEY (private key PEM, read-only)
  - DH_PORT (optional, defaults to 22)
- Run it via GitHub Actions → Workflows → “Deploy to DreamHost (manual)” → Run workflow

## Blog + Changelog via Airtable
- Data files rendered by site:
  - `public/data/blog.json`
  - `public/data/changes.json`
- Source of truth: Airtable tables (Blog, Changelog)
- Sync script: `scripts/sync_airtable.py` (uses AIRTABLE_API_KEY and AIRTABLE_BASE_ID)
- Workflow: `.github/workflows/sync-airtable.yml` runs on schedule/manual; commits JSON updates
- Edit schema/table names via env if you use custom names

### Set GitHub secrets for Airtable
- AIRTABLE_API_KEY
- AIRTABLE_BASE_ID
- Optional: BLOG_TABLE, CHANGELOG_TABLE

Run the workflow “Sync Airtable content” and commit will update JSON; then deploy to DreamHost.

## Local preview
- Serve `public/` locally (e.g., Live Server). On localhost, the bug form short-circuits to a mock success.
- Blog and Changelog read from the JSON files under `public/data/`.

## Troubleshooting
- CI noise: All workflows are manual/scheduled. If you see failure emails, check for YAML indentation or missing secrets.
- Windows reserved names: Avoid filenames like `NUL`, `CON`, etc. Already ignored in .gitignore.
- CORS: Make sure your site origins are in `ALLOWED_ORIGIN`. The function sets `Vary: Origin` and returns 204 for OPTIONS.

## Next steps
- Fill out Airtable base and set GitHub secrets
- Set Netlify `apiBase` in `public/config.json`
- Run “Sync Airtable content” → then “Deploy to DreamHost (manual)”
