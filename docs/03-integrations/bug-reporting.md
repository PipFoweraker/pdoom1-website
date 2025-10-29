# Bug Reporting API (shared by Web and Game)

Single backend endpoint that accepts JSON and dispatches to GitHub for issue creation via Actions.

Endpoint (after Netlify deploy):
- GET /api/report-bug (health)
- POST /api/report-bug

Environment (on Netlify):
- GITHUB_DISPATCH_TOKEN: token with permission to call repository_dispatch and create gists
- GITHUB_REPO: owner/repo (e.g., PipFoweraker/pdoom1-website)
- ALLOWED_ORIGIN: one or more origins allowed for CORS (comma or space separated). Wildcards supported, e.g. `https://*.netlify.app`.
- DRY_RUN: optional flag to skip creating issues for smoke tests
- HCAPTCHA_SITEKEY: optional hCaptcha site key. If set, enables hCaptcha validation.
- HCAPTCHA_SECRET: optional hCaptcha secret key. Required if HCAPTCHA_SITEKEY is set.

## hCaptcha Setup (Optional)

To enable spam protection with hCaptcha:

1. **Get hCaptcha credentials**:
   - Sign up at https://hcaptcha.com
   - Create a new site
   - Copy the Site Key and Secret Key

2. **Configure Netlify environment**:
   - In Netlify dashboard, go to Site Settings → Environment Variables
   - Add `HCAPTCHA_SITEKEY` with your site key
   - Add `HCAPTCHA_SECRET` with your secret key

3. **Update frontend form**:
   - Add hCaptcha widget to your bug report form
   - Include the hCaptcha token in the POST request body as `hcaptchaToken`

4. **Behavior**:
   - If `HCAPTCHA_SITEKEY` is NOT set: hCaptcha validation is disabled (backward compatible)
   - If `HCAPTCHA_SITEKEY` IS set: hCaptcha validation is required, requests without a valid token will return 400

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
  "hcaptchaToken": "string? (required if HCAPTCHA_SITEKEY is configured)",
  "attachment": {
    "filename": "string",
    "content": "base64 encoded string",
    "size": "number (bytes, max 500KB)",
    "type": "string (MIME type)"
  }?,
  "notify": true|false
}
```

Response:
- 200: { status: "queued", dedupeKey }
- 400/429/502 on validation/limit/upstream errors

Notes:
- Large fields are truncated server-side.
- A dedupeKey is computed and embedded to avoid duplicate issues.
- Attachments are uploaded to GitHub Gists and linked in the issue.
- Maximum attachment size: 500 KB.
- Supported file types: .txt, .log, .json, .zip, .png, .jpg, .jpeg
- Do not set GITHUB_TOKEN as a repo secret; GitHub Actions injects it automatically.
 - CORS: Function returns Vary: Origin and honors ALLOWED_ORIGIN; set to your DreamHost domain for production, add a wildcard entry temporarily if testing Netlify previews.
