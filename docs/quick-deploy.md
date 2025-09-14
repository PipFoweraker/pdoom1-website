# Quick Deployment Reference

## Deploy to DreamHost (GitHub Actions)

### One-Time Setup Checklist
- [ ] DreamHost shell user created
- [ ] SSH public key uploaded to DreamHost `~/.ssh/authorized_keys`
- [ ] GitHub secrets added: `DH_HOST`, `DH_USER`, `DH_PATH`, `DH_SSH_KEY`
- [ ] Domain pointing to correct directory

### Deploy Steps
1. Go to: `https://github.com/PipFoweraker/pdoom1-website/actions`
2. Click: "Deploy to DreamHost (manual)"
3. Click: "Run workflow"
4. Select: `main` branch
5. Choose: Dry run (test) or Live deployment
6. Click: "Run workflow"

### Quick Test
SSH test: `ssh -i /path/to/key username@domain.com "pwd"`

### Current Settings (pdoom1.com)
- **Host**: `pdoom1.com`
- **User**: `pdoom1_dot_com_shell` 
- **Path**: `/home/pdoom1_dot_com_shell/pdoom1.com`
- **Deploys**: `public/` folder contents

### Files Deployed
All contents of `public/` folder:
- `index.html` (main site)
- `assets/` (images, styles)
- `blog/` (blog posts)
- `config.json` (API configuration)
- All other static content
