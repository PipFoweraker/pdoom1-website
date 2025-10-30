# GitHub Actions Workflows

## 🚀 Deployment Workflows

### Auto-Deploy on Push (`auto-deploy-on-push.yml`)
**Triggers:** Automatically on every push to `main` branch
**What it does:**
- Automatically deploys changes to DreamHost when you push to main
- Only triggers if files in `public/` or sitemap generator change
- Syncs entire `public/` directory via rsync
- No manual intervention needed - just push and it deploys!

**Requirements:**
- DreamHost SSH secrets must be configured (see below)
- Changes must be pushed to `main` branch

### Version-Aware Deploy (`version-aware-deploy.yml`)
**Triggers:** Manual only (via GitHub Actions UI)
**What it does:**
- Checks version changes and requires approval for major versions
- Runs health checks before deployment
- Generates deployment manifest
- Verifies deployment after completion

**Use for:** Major releases, critical updates, when you want extra validation

### Simple DreamHost Deploy (`deploy-dreamhost.yml`)
**Triggers:** Manual only (via GitHub Actions UI)
**What it does:**
- Quick deployment with optional dry-run mode
- Minimal checks, fast execution

**Use for:** Quick hotfixes, testing deployment

## 🤖 Automation Workflows

### Data Updates (`auto-update-data.yml`)
**Triggers:** Every 6 hours
**Updates:** Version info, game stats from GitHub API

### Leaderboard Sync (`sync-leaderboards.yml`)
**Triggers:** Daily at 2am UTC
**Syncs:** 15 seed-specific leaderboards from game repository

### Weekly League Rollover (`weekly-league-rollover.yml`)
**Triggers:** Sundays at 11pm UTC
**Does:** Archives current week, generates new week with deterministic seed

## 📊 Monitoring Workflows

### Health Checks (`health-checks.yml`)
**Triggers:** On schedule or manual
**Checks:** System health, API availability, data freshness

## 🔧 Required Secrets

For deployment workflows to work, configure these secrets in:
**Settings → Secrets and variables → Actions → Repository secrets**

| Secret | Description | Example |
|--------|-------------|---------|
| `DH_HOST` | DreamHost hostname | `ssh.example.dreamhost.com` |
| `DH_USER` | SSH username | `your_username` |
| `DH_PATH` | Remote deployment path | `~/pdoom1.com` |
| `DH_SSH_KEY` | Private SSH key | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DH_PORT` | SSH port (optional) | `22` (default) |

## 🎮 How to Use

### Automatic Deployment (Happy CI/CD Gremlin Mode 🤖)
1. Make changes to files in `public/`
2. Commit and push to `main` branch
3. Watch the magic happen in the Actions tab
4. Visit https://pdoom1.com and see your changes live!

### Manual Deployment
1. Go to **Actions** tab
2. Select workflow (version-aware or simple deploy)
3. Click **Run workflow**
4. Fill in any required inputs
5. Click **Run workflow** button

## 🔍 Monitoring Deployments

1. Go to **Actions** tab in GitHub
2. Click on the running/completed workflow
3. View logs for each step
4. Check deployment summary at the end

## 💰 Cost Considerations

- **GitHub Actions minutes:** Free tier includes 2,000 minutes/month
- **DreamHost bandwidth:** Included with hosting plan
- Each deployment takes ~1-2 minutes
- Even with frequent deployments, you're unlikely to exceed free tier

**Estimated usage:**
- Auto-deploys: ~5-10 per day = 5-20 minutes/day
- Automation jobs: 3 jobs × 2 minutes × 30 days = 180 minutes/month
- **Total:** ~300-600 minutes/month (well within free tier)

## 🎯 CI/CD Philosophy

You are now a **happy CI/CD project manager gremlin**! 🎉

- Push early, push often
- Let automation handle the boring stuff
- Monitor via Actions tab
- Enjoy the happy little pipelines doing their thing

## 🐛 Troubleshooting

**Workflow fails with "Missing secret"**
- Configure DH_* secrets in repository settings
- Make sure SSH key has no passphrase

**Deployment succeeds but site not updated**
- Check DH_PATH is correct
- Verify file permissions on DreamHost
- Check DreamHost deployment path points to web root

**Rsync permission denied**
- Verify SSH key is correct
- Check DH_USER has write permissions to DH_PATH

## 📚 Further Reading

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [DreamHost SSH Keys Guide](https://help.dreamhost.com/hc/en-us/articles/216499537-How-to-configure-passwordless-login-in-Mac-OS-X-and-Linux)
- [Rsync Documentation](https://linux.die.net/man/1/rsync)
