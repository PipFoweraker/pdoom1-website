# Bug Reporting API (shared by Web and Game)

Single backend endpoint that accepts JSON and dispatches to GitHub for issue creation via Actions.

Endpoint (after Netlify deploy):
- GET /api/report-bug (health)
- POST /api/report-bug

Environment (on Netlify):
- GITHUB_DISPATCH_TOKEN: token with permission to call repository_dispatch
- GITHUB_REPO: owner/repo (e.g., PipFoweraker/pdoom1-website)
- ALLOWED_ORIGIN: one or more origins allowed for CORS (comma or space separated). Wildcards supported, e.g. `https://*.netlify.app`.
- DRY_RUN: optional flag to skip creating issues for smoke tests

Request body:
```
{
  "title": "string (1-120)",
  "description": "string (1-10k)",
  "type": "bug|feature|documentation|performance",
  "email": "string?",
  "source": "web|game",
  "appVersion": "string?",
  "buildId": "string?",
  "os": "string?",
  "logs": "string?",
  "notify": true|false
}
```

Response:
- 200: { status: "queued", dedupeKey }
- 400/429/502 on validation/limit/upstream errors

Notes:
- Large fields are truncated server-side.
- A dedupeKey is computed and embedded to avoid duplicate issues.
- Do not set GITHUB_TOKEN as a repo secret; GitHub Actions injects it automatically.
 - CORS: Function returns Vary: Origin and honors ALLOWED_ORIGIN; set to your DreamHost domain for production, add a wildcard entry temporarily if testing Netlify previews.
