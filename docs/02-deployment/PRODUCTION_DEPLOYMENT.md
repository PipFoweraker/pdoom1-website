# Production Deployment Guide

## Overview

This guide covers production deployment of the p(Doom)1 website and API server infrastructure.

## Architecture

### Static Website
- **Platform**: DreamHost (primary), Netlify (backup/staging)
- **Domain**: https://pdoom1.com
- **Deployment**: Automated via GitHub Actions
- **Content**: Static HTML, CSS, JS files and leaderboard data

### API Server
- **Platform**: Self-hosted or serverless (Railway/Render recommended)
- **Endpoints**: 8 REST endpoints for leaderboard and league data
- **CORS**: Configured for production domain
- **Health Checks**: Automated monitoring

## API Server Deployment Options

### Option 1: Railway (Recommended)

Railway provides simple deployment with automatic HTTPS and environment management.

**Setup:**

1. Install Railway CLI:
```bash
npm install -g @railway/cli
```

2. Login and initialize:
```bash
railway login
railway init
```

3. Create `railway.json` in project root (see configuration below)

4. Deploy:
```bash
railway up
```

**Advantages:**
- Free tier available (500 hours/month)
- Automatic HTTPS
- Easy environment variable management
- Built-in monitoring
- GitHub integration available

### Option 2: Render

Render offers similar features with generous free tier.

**Setup:**

1. Create account at render.com
2. Connect GitHub repository
3. Create new Web Service
4. Configure build and start commands
5. Set environment variables

**Advantages:**
- Generous free tier
- Automatic deploys from GitHub
- Built-in SSL
- Easy database integration

### Option 3: Self-Hosted (VPS)

For full control, deploy to a VPS (DigitalOcean, Linode, etc.)

**Requirements:**
- Python 3.11+
- Nginx (reverse proxy)
- SSL certificate (Let's Encrypt)
- Systemd service configuration

**Setup:** See `SELF_HOSTED_API_DEPLOYMENT.md` for detailed instructions.

## Environment Configuration

### Production Environment Variables

Add to Railway/Render/VPS configuration:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
API_ENV=production

# CORS Configuration
CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=true

# Weekly League
WEEKLY_LEAGUE_AUTO_RESET=true
LEAGUE_TIMEZONE=UTC

# Rate Limiting
RATE_LIMIT_ENABLED=true
MAX_REQUESTS_PER_MINUTE=60
```

### Development vs Production

The system uses environment-aware configuration:

- **Development**: `API_ENV=development` - CORS allows all origins
- **Production**: `API_ENV=production` - CORS restricted to configured domains

## Monitoring and Health Checks

### Automated Monitoring

GitHub Actions runs health checks every 6 hours:
- File integrity checks
- JSON validation
- Script execution tests
- API endpoint tests

See `.github/workflows/health-checks.yml`

### Manual Health Checks

```bash
# Local health check
npm run test:health

# API server health check
curl https://your-api-domain.com/api/health

# League status check
npm run league:status
```

### Alerting

Health check failures automatically:
1. Create GitHub issues with `automated-alert` label
2. Include workflow logs and failure details
3. Notify via configured channels

## Backup and Recovery

### Automated Backups

Weekly league data is automatically archived:

```bash
public/leaderboard/data/weekly/archive/
├── 2025_W40.json
├── 2025_W41.json
├── 2025_W42.json
└── ...
```

**Retention Policy:**
- Weekly archives: Kept indefinitely (52+ weeks)
- Daily backups: 30 days
- Deployment artifacts: 90 days

### Manual Backup

```bash
# Backup all league data
tar -czf backup-$(date +%Y%m%d).tar.gz public/leaderboard/data/

# Backup specific week
npm run league:archive

# Sync to external storage
rsync -avz public/leaderboard/data/ user@backup-server:/backups/
```

### Recovery Procedures

**1. Restore from Archive**
```bash
# Extract backup
tar -xzf backup-YYYYMMDD.tar.gz

# Verify data integrity
python scripts/verify-deployment.py

# Sync to production
rsync -avz public/ production-server:/path/
```

**2. Emergency League Reset**
```bash
# Manual league reset if automation fails
python scripts/weekly-league-manager.py --archive-week
python scripts/weekly-league-manager.py --new-week
python scripts/game-integration.py --weekly-sync

# Commit and deploy
git add -A
git commit -m "Emergency league reset"
git push
```

**3. Rollback Deployment**

GitHub Actions provides rollback capability:
1. Navigate to failed workflow
2. Re-run successful previous deployment
3. Verify via health checks

## CI/CD Pipeline

### Automated Workflows

**Weekly League Reset** (Sunday 14:00 UTC / Monday 00:00 AEST)
- Archives previous week
- Generates new competitive seed
- Starts new league
- Syncs game data
- Commits changes

**Weekly Deployment** (Friday 06:00 UTC / Friday 16:00 AEST)
- Pre-deployment health checks
- Data synchronization
- Deploy to production
- Post-deployment verification
- Monitoring verification

**Health Checks** (Every 6 hours)
- File integrity
- JSON validation
- Script execution
- Security checks
- Performance metrics

### Manual Triggers

All workflows support manual triggering:

```bash
# Using GitHub CLI
gh workflow run weekly-league-reset.yml
gh workflow run weekly-deployment.yml
gh workflow run health-checks.yml

# Or via GitHub web interface: Actions → Select workflow → Run workflow
```

## Production Checklist

Before going live:

- [ ] API server deployed and accessible
- [ ] Environment variables configured
- [ ] CORS properly restricted to production domain
- [ ] Health checks passing
- [ ] Weekly league reset tested
- [ ] Backup system verified
- [ ] Monitoring alerts configured
- [ ] Recovery procedures documented
- [ ] DNS configured correctly
- [ ] SSL certificates valid

## Monitoring Endpoints

### Health Check
```bash
GET https://api.pdoom1.com/api/health

Response:
{
  "status": "healthy",
  "timestamp": "2025-10-19T12:00:00Z",
  "version": "1.0.0",
  "uptime": 86400
}
```

### League Status
```bash
GET https://api.pdoom1.com/api/league/status

Response:
{
  "current_week": "2025_W42",
  "seed": "weekly_2025_W42_00dbe16d",
  "active": true,
  "days_remaining": 0,
  "participants": 0
}
```

## Troubleshooting

### API Server Not Responding

1. Check service status
2. Review logs
3. Verify environment variables
4. Test health endpoint
5. Check CORS configuration

### League Reset Failed

1. Check workflow logs
2. Verify Python environment
3. Run manual reset
4. Check file permissions
5. Verify git configuration

### Deployment Failed

1. Review workflow logs
2. Check SSH connectivity (DreamHost)
3. Verify secrets are configured
4. Test manual deployment
5. Check disk space

## Support

For issues:
1. Check workflow logs in GitHub Actions
2. Review health check results
3. Check `docs/02-deployment/` for specific guides
4. Create issue with `deployment` label
