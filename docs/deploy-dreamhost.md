# Deploying to DreamHost (manual)

This repo includes a manual GitHub Actions workflow to deploy the static site in `public/` to DreamHost via rsync over SSH.

## One-time setup

1. Create or reuse an SSH key that DreamHost accepts (no passphrase or use a PATTERN with ssh-agent). Copy the private key contents.
2. Add repository secrets in GitHub (Settings → Secrets and variables → Actions → New repository secret):
   - `DH_HOST`: your DreamHost domain or host (e.g. `example.dreamhost.com` or `yourdomain.com`).
   - `DH_USER`: your shell user on DreamHost.
   - `DH_PATH`: absolute or home-relative path to the web root for the site (e.g. `/home/youruser/yourdomain.com`).
   - `DH_SSH_KEY`: the private key contents (BEGIN/END blocks included).

Optionally, restrict environment protection rules for the `production` environment.

## Running a deploy

1. Go to Actions → "Deploy to DreamHost (manual)".
2. Click "Run workflow" → choose branch `main` and optionally enable `dry_run` for a preview.
3. Run. The job uses `rsync -avz --delete` to mirror `public/` to `${DH_PATH}`.

Notes:
- `--delete` removes files on the server that are no longer present locally. Remove it if you prefer additive deploys.
- For subdomain folders, ensure `DH_PATH` points to the correct document root.
- If the host key check fails, the workflow already disables strict checking for CI convenience. For tighter security, pre-populate `known_hosts` in a secret and write it to `~/.ssh/known_hosts` instead.

## Local quick preview

From the repo root you can do a minimal preview without Node:

```bash
python -m http.server 5173
```

Open http://localhost:5173/public/.
