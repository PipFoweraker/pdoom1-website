# Bug Reporting API (shared by Web and Game)

Single backend endpoint that accepts JSON and dispatches to GitHub for issue creation via Actions.

Endpoint (after Netlify deploy):
- POST /api/report-bug

Environment (on Netlify):
- GITHUB_DISPATCH_TOKEN: token with permission to call repository_dispatch
- GITHUB_REPO: owner/repo (e.g., PipFoweraker/pdoom1-website)
- ALLOWED_ORIGIN: your website origin (optional)

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
