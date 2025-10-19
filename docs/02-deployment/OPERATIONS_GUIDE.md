# Operations Guide

## Overview

This guide covers day-to-day operations, maintenance, and troubleshooting for the p(Doom)1 website and weekly league system.

## Daily Operations

### Monitoring Dashboard

Check these daily (morning AEST):

1. **GitHub Actions**:
   - Go to: Repository → Actions
   - Check for failed workflows
   - Review any automated alerts

2. **League Status**:
   ```bash
   npm run league:status
   ```
   - Verify correct week is active
   - Check participant count
   - Confirm seed is correct

3. **API Health** (if deployed):
   ```bash
   curl https://your-api-domain.com/api/health
   ```
   - Should return `"status": "healthy"`

4. **Website Accessibility**:
   - Visit https://pdoom1.com
   - Check leaderboard page loads
   - Verify no console errors

### Quick Health Check

```bash
# Run comprehensive health checks
python scripts/health-check.py

# Check deployment status
python scripts/prepare-weekly-deployment.py --check-only

# Verify league system
python scripts/weekly-league-manager.py --status
```

## Weekly Operations

### Monday: New League Week

**Automated** (00:00 AEST / Sunday 14:00 UTC)

The system automatically:
1. Archives previous week
2. Generates new seed
3. Starts new league
4. Commits changes

**Manual Verification** (00:30 AEST):

```bash
# Check league reset succeeded
npm run league:status

# Verify new week started
# Should show: CURRENT_WEEK: 2025_W[current_week]

# Check standings are empty
npm run league:standings

# Verify archive was created
ls -la public/leaderboard/data/weekly/archive/
```

**If Reset Failed**:

```bash
# Check workflow logs
gh run list --workflow=weekly-league-reset.yml --limit 3

# Manual reset if needed
npm run league:archive
npm run league:new-week
npm run game:weekly-sync

# Commit manually
git add -A
git commit -m "Manual league reset - Week [CURRENT_WEEK]"
git push
```

### Friday: Weekly Deployment

**Automated** (16:00 AEST / 06:00 UTC)

The system automatically:
1. Runs pre-deployment checks
2. Syncs game data
3. Deploys to production
4. Runs post-deployment verification

**Manual Verification** (16:30 AEST):

```bash
# Check deployment succeeded
gh run list --workflow=weekly-deployment.yml --limit 3

# Verify site is live
curl https://pdoom1.com

# Check API health (if deployed)
curl https://your-api-domain.com/api/health

# Run local verification
npm run test:all
```

**If Deployment Failed**:

1. Check workflow logs
2. Fix identified issues
3. Re-trigger deployment:
   ```bash
   gh workflow run weekly-deployment.yml
   ```

### Regular Maintenance Tasks

| Task | Frequency | Command |
|------|-----------|---------|
| Health checks | Every 6 hours | Automatic |
| League resets | Weekly (Monday) | Automatic |
| Deployments | Weekly (Friday) | Automatic |
| Backup verification | Monthly | Manual (see below) |
| Security updates | Monthly | Manual |
| Performance review | Quarterly | Manual |

## Monthly Operations

### Backup Verification

**First Monday of Month**:

```bash
# Verify archives exist
ls -la public/leaderboard/data/weekly/archive/

# Count archived weeks
ls -1 public/leaderboard/data/weekly/archive/*.json | wc -l

# Test restore procedure (in temp dir)
mkdir -p /tmp/restore-test
cd /tmp/restore-test
cp ~/pdoom1-website/public/leaderboard/data/weekly/archive/latest.json .
python -m json.tool latest.json > /dev/null && echo "✓ Archive valid"
cd ~/pdoom1-website
rm -rf /tmp/restore-test
```

### Alert Review

**First Week of Month**:

1. Review all alerts from past month:
   ```bash
   gh issue list --label automated-alert --state all
   ```

2. Check for patterns:
   - Repeated failures?
   - False positives?
   - New issues?

3. Update alert thresholds if needed

4. Document improvements in issue tracker

### Performance Review

**First Week of Month**:

1. Check workflow execution times:
   - Go to: Actions → Workflows → Click workflow
   - Review "Duration" column
   - Note any degradation

2. Review health check success rates:
   ```bash
   # Check recent health check results
   python -m json.tool public/data/health-check-results.json
   ```

3. API performance (if deployed):
   - Check response times
   - Review error rates
   - Monitor resource usage

4. Document findings in monthly report

## Quarterly Operations

### Security Updates

**First Monday of Quarter**:

1. Update Python (if self-hosted):
   ```bash
   python --version
   # Check for updates: python.org
   ```

2. Review GitHub Actions versions:
   - actions/checkout
   - actions/setup-python
   - actions/setup-node

3. Check dependencies:
   ```bash
   # We use stdlib only, but verify
   pip list --outdated
   ```

4. Review CORS configuration:
   ```bash
   cat config/production.json | grep cors_origins
   # Verify domains are correct
   ```

### Capacity Planning

**First Monday of Quarter**:

1. Review participant growth:
   - Check archived weeks for trends
   - Estimate future capacity needs

2. Storage usage:
   ```bash
   du -sh public/leaderboard/data/
   # Current: ~3MB, grows ~50KB/week
   ```

3. API load (if deployed):
   - Check request volumes
   - Review rate limiting needs
   - Plan for scale

4. Update infrastructure if needed

## Troubleshooting

### Common Issues

#### Issue: League didn't reset on Monday

**Symptoms**: Still showing previous week

**Resolution**:
```bash
# 1. Check workflow status
gh run list --workflow=weekly-league-reset.yml --limit 3

# 2. If failed, check logs
gh run view [run-id]

# 3. Manual reset
npm run league:archive
npm run league:new-week

# 4. Verify
npm run league:status

# 5. Commit
git add -A
git commit -m "Manual league reset"
git push
```

#### Issue: Deployment failed

**Symptoms**: Workflow failed, site not updated

**Resolution**:
```bash
# 1. Check logs
gh run view [run-id]

# 2. Common causes:
# - SSH key expired: Update DH_SSH_KEY secret
# - Network issue: Re-run workflow
# - Merge conflict: Pull and resolve

# 3. Re-trigger
gh workflow run weekly-deployment.yml

# 4. Manual deploy if needed
rsync -avz public/ user@host:/path/
```

#### Issue: Health checks failing

**Symptoms**: Automated issues being created

**Resolution**:
```bash
# 1. Run locally
npm run test:health

# 2. Check output
cat public/data/health-check-results.json

# 3. Fix specific failures
# - Missing files: Restore from backup
# - Invalid JSON: Fix syntax
# - Script errors: Check Python version

# 4. Re-run
npm run test:health

# 5. Commit fixes
git add -A
git commit -m "Fix: Health check issues"
git push
```

#### Issue: API not responding

**Symptoms**: Health endpoint times out

**Resolution**:
```bash
# 1. Check service status
# Railway: Check dashboard
# Self-hosted: systemctl status pdoom1-api

# 2. View logs
# Railway: railway logs
# Self-hosted: journalctl -u pdoom1-api -n 100

# 3. Restart if needed
# Railway: Restart via dashboard
# Self-hosted: systemctl restart pdoom1-api

# 4. Test locally
python scripts/api-server.py --production --port 8080

# 5. Redeploy if needed
git push  # Railway/Render auto-deploy
```

### Emergency Procedures

#### Complete Site Failure

1. **Assess scope**: What's not working?
2. **Check status page**: GitHub, Railway, DreamHost
3. **Roll back if needed**: Re-run last successful deployment
4. **Restore from backup**: See BACKUP_RECOVERY.md
5. **Notify users**: Post to Discord/social media
6. **Document incident**: Create post-mortem issue

#### Data Corruption

1. **Stop automated processes**: Disable workflows temporarily
2. **Assess damage**: What data is corrupted?
3. **Restore from archive**: Find last good backup
4. **Verify integrity**: Run health checks
5. **Resume operations**: Re-enable workflows
6. **Root cause analysis**: Prevent recurrence

#### Security Incident

1. **Assess threat**: What was compromised?
2. **Rotate credentials**: All affected secrets
3. **Review logs**: Find attack vector
4. **Patch vulnerability**: Fix and deploy
5. **Monitor closely**: Watch for repeat attempts
6. **Document**: Security incident report

## Automation Health

### Monitoring Automated Workflows

Check these weekly:

1. **Weekly League Reset**:
   ```bash
   gh run list --workflow=weekly-league-reset.yml --limit 10
   ```
   - Should show "success" for recent runs
   - Check execution time (should be ~2-5 minutes)

2. **Weekly Deployment**:
   ```bash
   gh run list --workflow=weekly-deployment.yml --limit 10
   ```
   - Should show "success" for recent runs
   - Check execution time (should be ~3-8 minutes)

3. **Health Checks**:
   ```bash
   gh run list --workflow=health-checks.yml --limit 20
   ```
   - Should have high success rate (>95%)
   - Check for patterns in failures

### Workflow Maintenance

**Monthly**:
- Review workflow execution times
- Update action versions
- Optimize slow steps
- Remove deprecated features

**Quarterly**:
- Review entire workflow structure
- Consider new automation opportunities
- Update documentation
- Test disaster recovery

## Key Metrics

Track these metrics for operational health:

### Reliability
- League reset success rate: Target 100%
- Deployment success rate: Target 100%
- Health check pass rate: Target >98%
- API uptime: Target >99.9%

### Performance
- League reset time: Target <5 minutes
- Deployment time: Target <10 minutes
- API response time: Target <500ms
- Page load time: Target <2 seconds

### Engagement
- Weekly active players: Track growth
- Average scores per week: Monitor trends
- Archive growth: ~50KB/week expected

## Support and Escalation

### Issue Priority Levels

**P0 - Critical** (respond immediately):
- Site completely down
- Data loss or corruption
- Security breach
- League reset failed on Monday

**P1 - High** (respond within 2 hours):
- Deployment failed
- API not responding
- Health checks failing
- Monitoring alerts

**P2 - Medium** (respond within 24 hours):
- Performance degradation
- Minor bugs
- Documentation updates
- Feature requests

**P3 - Low** (respond within 1 week):
- Cosmetic issues
- Enhancement ideas
- General questions
- Future planning

### Getting Help

1. **Documentation**: Check `/docs/` first
2. **Workflow logs**: Review GitHub Actions logs
3. **Health checks**: Run local diagnostics
4. **Create issue**: Use appropriate labels
5. **Community**: Discord channel (if available)

## Best Practices

### Daily
- ✅ Check for failed workflows
- ✅ Monitor league status
- ✅ Review automated alerts
- ✅ Quick health check

### Weekly
- ✅ Verify Monday league reset
- ✅ Verify Friday deployment
- ✅ Review new issues
- ✅ Check resource usage

### Monthly
- ✅ Backup verification
- ✅ Alert review
- ✅ Performance review
- ✅ Documentation updates

### Quarterly
- ✅ Security updates
- ✅ Capacity planning
- ✅ Process improvements
- ✅ Infrastructure review

## Operational Calendar

| Day | Task | Time | Type |
|-----|------|------|------|
| Sunday 14:00 UTC | League reset | Monday 00:00 AEST | Auto |
| Monday | Verify reset | 00:30 AEST | Manual |
| Friday 06:00 UTC | Deployment | 16:00 AEST | Auto |
| Friday | Verify deploy | 16:30 AEST | Manual |
| Friday | Twitch stream | 16:30 AEST | Manual |
| Every 6 hours | Health checks | Various | Auto |
| First Monday | Monthly backup check | 09:00 AEST | Manual |
| First Monday (Quarter) | Security updates | 09:00 AEST | Manual |

## Useful Commands

```bash
# Quick status check
npm run league:status && npm run test:health

# View recent workflows
gh run list --limit 10

# Check specific workflow
gh run list --workflow=weekly-league-reset.yml --limit 5

# View workflow details
gh run view [run-id]

# Manual league operations
npm run league:status
npm run league:standings
npm run league:archive
npm run league:new-week

# Deployment operations
npm run deploy:check
npm run deploy:prep-weekly
npm run test:all

# Troubleshooting
npm run test:health
npm run league:status
git status
git log --oneline -10
```

## Contact Information

For operational support:
- **Repository**: https://github.com/PipFoweraker/pdoom1-website
- **Issues**: Create with appropriate priority label
- **Documentation**: `/docs/02-deployment/`
- **Health Status**: Check GitHub Actions

## Change Log

Track operational changes:
- 2025-10-19: Added production deployment configs
- 2025-10-19: Added comprehensive monitoring guides
- 2025-10-19: Added backup and recovery procedures
- [Add new changes here]
