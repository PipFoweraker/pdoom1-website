# Deploying to DreamHost (manual)

This repo includes a manual GitHub Actions workflow to deploy the static site in `public/` to DreamHost via rsync over SSH, while keeping the bug-report API on Netlify.

## One-time setup

1. Create or reuse an SSH key that DreamHost accepts (no passphrase or use a PATTERN with ssh-agent). Copy the private key contents.
2. Add repository secrets in GitHub (Settings → Secrets and variables → Actions → New repository secret):
   - `DH_HOST`: your DreamHost domain or host (e.g. `example.dreamhost.com` or `yourdomain.com`).
   - `DH_USER`: your shell user on DreamHost.
   - `DH_PATH`: absolute or home-relative path to the web root for the site (e.g. `/home/youruser/yourdomain.com`).
   - `DH_SSH_KEY`: the private key contents (BEGIN/END blocks included).

3. If you’ll use Netlify for the API only (recommended):
    - Create a Netlify site from this repo.
    - Build settings: Publish `public`, Functions `netlify/functions`.
    - Set Environment variables:
       - `GITHUB_DISPATCH_TOKEN`: token with repo dispatch rights
       - `GITHUB_REPO`: `PipFoweraker/pdoom1-website`
       - `ALLOWED_ORIGIN`: your DreamHost site URL, e.g. `https://yourdomain.com`
    - Deploy once to get the Netlify site URL, then leave hosting on DreamHost if you prefer.
    - In `public/config.json`, set `apiBase` to your Netlify site origin, e.g. `https://your-netlify-site.netlify.app`.

Optionally, restrict environment protection rules for the `production` environment.

## Running a deploy

1. Go to Actions → "Deploy to DreamHost (manual)".
2. Click "Run workflow" → choose branch `main` and optionally enable `dry_run` for a preview.
3. Run. The job uses `rsync -avz --delete` to mirror `public/` to `${DH_PATH}`.
4. Ensure `config.json` contains the correct `apiBase` for the Netlify function host.

Notes:
- `--delete` removes files on the server that are no longer present locally. Remove it if you prefer additive deploys.
- For subdomain folders, ensure `DH_PATH` points to the correct document root.
- If the host key check fails, the workflow already disables strict checking for CI convenience. For tighter security, pre-populate `known_hosts` in a secret and write it to `~/.ssh/known_hosts` instead.

## Security best practices

- Secrets
   - Store Netlify tokens in Netlify env vars; do not commit secrets.
   - Store DreamHost SSH key as `DH_SSH_KEY` secret; scope it to the deploy user only.
- CORS/Origin
   - Set `ALLOWED_ORIGIN` in Netlify to your DreamHost URL to prevent cross-site abuse.
- Spam/abuse
   - If spam appears, add an hCaptcha to the bug form and validate token in the Netlify function.
- Hardening
   - Optional `.htaccess` is provided in `public/` to disable indexes and dotfile access.
   - Consider removing `--delete` in rsync if you want safer deploys.
- Principle of least privilege
   - The GitHub token for dispatch should only have repo:public_repo (or repo if this repo is private).
   - Long-term, prefer a GitHub App for repository_dispatch.

## Local quick preview

From the repo root you can do a minimal preview without Node:

```bash
python -m http.server 5173
```

Open http://localhost:5173/public/.
