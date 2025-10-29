# Go-live guide

A concise, ordered sequence to get the site live on your DreamHost domain while using Netlify for the API.

## 1) Netlify – create site and set envs
- Create a Netlify site from this GitHub repo.
- Settings → Build & deploy:
  - Publish directory: `public`
  - Functions directory: `netlify/functions`
- Settings → Environment variables (Production):
  - `GITHUB_DISPATCH_TOKEN`: GitHub PAT with repo dispatch capability (public_repo for public repos, repo for private)
  - `GITHUB_REPO`: `PipFoweraker/pdoom1-website`
  - `ALLOWED_ORIGIN`: `https://yourdomain.com` (your DreamHost site); you may append ` https://*.netlify.app` for preview testing
  - Optional: `DRY_RUN`: `true` initially
- Deploy once. Confirm health:
  - GET `https://YOUR-NETLIFY-SITE.netlify.app/api/report-bug` → `{ "status": "ok" }`

## 2) Frontend config – point to Netlify API
- Edit `public/config.json`:
  - `{ "apiBase": "https://YOUR-NETLIFY-SITE.netlify.app" }`
- Commit the change.

## 3) DreamHost – configure deploy and push site
- In GitHub → Settings → Secrets and variables → Actions → New repository secret:
  - `DH_HOST`: `yourdomain.com`
  - `DH_USER`: DreamHost shell user
  - `DH_PATH`: e.g., `/home/USER/yourdomain.com`
  - `DH_SSH_KEY`: private key contents (BEGIN/END included)
- Actions → "Deploy to DreamHost (manual)" → Run workflow (enable `dry_run` for preview). If looks good, run without `dry_run`.
- Ensure DNS points your domain to the DreamHost site (if not already).

## 4) GitHub Actions - Bug Report Workflow
The bug report intake is handled by the `bug-report.yml` workflow:
- **Trigger**: `repository_dispatch` with `event_type: bug-report`
- **Action**: Creates or deduplicates GitHub issues using `dedupeKey` from payload
- **Labels**: Automatically applies `type: bug` and `priority: medium` (configurable by issue type)
- **Maintainers**: Assigns or mentions repository maintainers (@PipFoweraker)
- **Run logs**: Generates workflow summary with issue details and links

Workflow documentation: [.github/workflows/bug-report.yml](../.github/workflows/bug-report.yml)

## 5) End-to-end bug submit test
- With `DRY_RUN=true` on Netlify, submit the bug form from your DreamHost site. Expect a 200 response.
- Remove `DRY_RUN` in Netlify envs and redeploy.
- Submit again → confirm a GitHub Issue is created via the bug-report workflow.

## 6) Optional hardening and polish
- **Add hCaptcha** for spam protection (recommended):
  1. Sign up at https://hcaptcha.com and create a new site
  2. In Netlify → Environment Variables, add:
     - `HCAPTCHA_SITEKEY`: your hCaptcha site key
     - `HCAPTCHA_SECRET`: your hCaptcha secret key
  3. Add hCaptcha widget to your bug report form (see frontend integration below)
  4. The backend will automatically validate tokens when `HCAPTCHA_SITEKEY` is set
  5. **Fallback toggle**: To disable hCaptcha validation, simply remove or unset `HCAPTCHA_SITEKEY` in Netlify
- Restrict `ALLOWED_ORIGIN` to only your production domain (remove wildcards after testing).
- Rotate the GitHub PAT periodically; consider a GitHub App for repository_dispatch.
- Keep `public/design/tokens.json` as the game-driven style surface; automate updates from the game pipeline.

### Frontend hCaptcha Integration

To add hCaptcha to the bug report form:

1. Add hCaptcha script to your HTML:
   ```html
   <script src="https://js.hcaptcha.com/1/api.js" async defer></script>
   ```

2. Add hCaptcha widget to your form:
   ```html
   <div class="h-captcha" data-sitekey="YOUR_SITEKEY_HERE"></div>
   ```

3. Include the token in your POST request:
   ```javascript
   const hcaptchaToken = document.querySelector('[name="h-captcha-response"]')?.value;
   bugData.hcaptchaToken = hcaptchaToken;
   ```

See `docs/03-integrations/bug-reporting.md` for complete API documentation.

## Troubleshooting
- CORS 403/blocked: ensure `ALLOWED_ORIGIN` exactly matches your DreamHost domain (scheme + host). For previews, temporarily include `https://*.netlify.app`.
- 502 from function: check Netlify logs; verify `GITHUB_DISPATCH_TOKEN` and `GITHUB_REPO`.
- Form doesn’t hit API: confirm `public/config.json` `apiBase` points to your Netlify site and that DreamHost deployed the latest files.
