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

## 4) End-to-end bug submit test
- With `DRY_RUN=true` on Netlify, submit the bug form from your DreamHost site. Expect a 200 response.
- Remove `DRY_RUN` in Netlify envs and redeploy.
- Submit again → confirm a GitHub Issue is created.

## 5) Optional hardening and polish
- Add hCaptcha on the form if spam appears; validate token in `netlify/functions/report-bug.js`.
- Restrict `ALLOWED_ORIGIN` to only your production domain (remove wildcards after testing).
- Rotate the GitHub PAT periodically; consider a GitHub App for repository_dispatch.
- Keep `public/design/tokens.json` as the game-driven style surface; automate updates from the game pipeline.

## Troubleshooting
- CORS 403/blocked: ensure `ALLOWED_ORIGIN` exactly matches your DreamHost domain (scheme + host). For previews, temporarily include `https://*.netlify.app`.
- 502 from function: check Netlify logs; verify `GITHUB_DISPATCH_TOKEN` and `GITHUB_REPO`.
- Form doesn’t hit API: confirm `public/config.json` `apiBase` points to your Netlify site and that DreamHost deployed the latest files.
