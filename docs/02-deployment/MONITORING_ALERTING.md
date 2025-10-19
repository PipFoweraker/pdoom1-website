# Monitoring and Alerting System

## Overview

Comprehensive monitoring and alerting for the p(Doom)1 website, API server, and weekly league system.

## Monitoring Components

### 1. Automated Health Checks

**Schedule**: Every 6 hours via GitHub Actions

**Checks Include:**
- ✅ File integrity (critical files exist)
- ✅ JSON validation (all data files valid)
- ✅ Script execution (all scripts compile)
- ✅ Version data structure
- ✅ Security checks (HTTPS usage)
- ✅ Performance metrics (file sizes)

**Configuration**: `.github/workflows/health-checks.yml`

### 2. API Server Monitoring

**Endpoints Monitored:**

```bash
GET /api/health
GET /api/status
GET /api/league/status
GET /api/league/current
```

**Metrics Collected:**
- Response time
- Error rates
- Request volume
- Active connections
- Memory usage
- Uptime

### 3. Weekly League Monitoring

**Tracked Metrics:**
- Current week ID
- Active league status
- Participant count
- Days remaining
- Seed generation status
- Archive integrity

**Access**: `npm run league:status`

### 4. Deployment Monitoring

**Pre-Deployment Checks:**
- Health status
- Data integrity
- Version consistency
- Configuration validation

**Post-Deployment Verification:**
- Site accessibility
- Health checks passing
- Data sync successful
- No errors in logs

## Alerting System

### Automated Alerts

#### Health Check Failures

**Trigger**: Any health check fails

**Action**:
1. Automatically creates GitHub issue
2. Labels: `bug`, `deployment`, `automated-alert`, `high-priority`
3. Includes workflow logs and failure details
4. Links to failed workflow run

**Example Alert**:
```
🚨 Health Check Failed - 2025-10-19

## Health Check Failure Report

**Workflow:** Health Checks and Deployment Tests
**Run ID:** 1234567890
**Commit:** abc123def
**Branch:** main
**Triggered by:** schedule

### Failed Steps
One or more health checks have failed. Please check the workflow logs.

### Next Steps
1. Review the workflow logs
2. Check which scripts are failing
3. Verify data integrity
4. Test deployment process manually if needed
```

#### Deployment Failures

**Trigger**: Deployment workflow fails

**Action**:
1. Creates GitHub issue
2. Includes deployment stage that failed
3. Links to workflow run
4. Lists manual deployment command
5. Priority: High

#### League Reset Failures

**Trigger**: Weekly league reset fails

**Action**:
1. Creates GitHub issue
2. Includes recovery commands
3. Time-sensitive alert (players expecting new league)
4. Priority: Critical

**Example Alert**:
```
❌ WEEKLY LEAGUE RESET FAILED ❌

Time: 2025-10-19 14:00 UTC

URGENT ACTION REQUIRED:
  1. Check workflow logs for errors
  2. Verify league data integrity
  3. Manual reset if needed:
     npm run league:archive
     npm run league:new-week
  4. Notify players of delay
  5. Update Discord with status

Players may already be expecting new league!
Time-sensitive - resolve ASAP
```

### Manual Alert Triggers

```bash
# Manually trigger health checks
gh workflow run health-checks.yml --ref main

# Check recent workflow failures
gh run list --status=failure --limit 10

# View specific run details
gh run view [run-id]

# Re-run failed workflow
gh run rerun [run-id]
```

## Monitoring Dashboards

### GitHub Actions Dashboard

Access via: Repository → Actions tab

**Key Views:**
- Recent workflow runs
- Success/failure rates
- Workflow timing trends
- Artifact downloads

### Health Check Results

**Location**: `public/data/health-check-results.json`

**Access**:
```bash
# View latest results
cat public/data/health-check-results.json | python -m json.tool

# Check specific test
cat public/data/health-check-results.json | jq '.results[] | select(.test=="Version Data")'
```

**Available via API**:
```bash
curl https://pdoom1.com/data/health-check-results.json
```

### League Status Dashboard

**Access**:
```bash
npm run league:status
```

**Output**:
```
WEEKLY LEAGUE STATUS:
   SEASON: 2025_Q4
   CURRENT_WEEK: 2025_W42
   PERIOD: 2025-10-13 to 2025-10-19
   TIME_REMAINING: 0 days, 11 hours
   CURRENT_SEED: weekly_2025_W42_00dbe16d
   LEAGUE_ACTIVE: True
   PARTICIPANTS: 0
   ARCHIVED_WEEKS: 1
```

## Monitoring Best Practices

### 1. Regular Review Schedule

| Frequency | Activity | Responsible |
|-----------|----------|-------------|
| Daily | Check for failed workflows | Automated + Manual |
| Weekly | Review health check trends | Manual |
| Monthly | Analyze performance metrics | Manual |
| Quarterly | Update monitoring thresholds | Manual |

### 2. Response Procedures

**High Priority Alerts** (respond within 2 hours):
- Deployment failures
- Health check failures
- League reset failures
- API server down

**Medium Priority** (respond within 24 hours):
- Performance degradation
- Configuration warnings
- Security scan findings

**Low Priority** (respond within 1 week):
- Documentation updates needed
- Performance optimization opportunities
- Feature enhancement alerts

### 3. Escalation Path

1. **Level 1**: Automated alerts via GitHub Issues
2. **Level 2**: Manual review of workflow logs
3. **Level 3**: Manual intervention/recovery procedures
4. **Level 4**: Emergency procedures (see BACKUP_RECOVERY.md)

## Performance Metrics

### Response Time Targets

| Endpoint | Target | Acceptable |
|----------|--------|------------|
| /api/health | < 100ms | < 500ms |
| /api/status | < 200ms | < 1s |
| /api/league/status | < 200ms | < 1s |
| /api/leaderboards/* | < 500ms | < 2s |

### Success Rate Targets

| Service | Target | Minimum |
|---------|--------|---------|
| API Availability | 99.9% | 99.0% |
| Health Checks | 100% | 98.0% |
| League Resets | 100% | 99.0% |
| Deployments | 100% | 95.0% |

## Alert Configuration

### GitHub Actions Alert Rules

Configured in workflow files:

```yaml
# Example: Create issue on failure
- name: Create issue on failure
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      const title = `🚨 Alert Title - ${new Date().toISOString()}`;
      const body = `Alert details...`;
      
      github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: title,
        body: body,
        labels: ['automated-alert', 'high-priority']
      });
```

### Custom Alert Scripts

Create custom monitoring scripts:

```python
#!/usr/bin/env python3
# scripts/monitoring-check.py

import json
import sys
from datetime import datetime, timedelta

def check_league_status():
    """Check if league is active and recent."""
    with open('public/leaderboard/data/weekly/current.json') as f:
        data = json.load(f)
    
    last_update = datetime.fromisoformat(data['last_updated'])
    hours_since = (datetime.now() - last_update).total_seconds() / 3600
    
    if hours_since > 24:
        print(f"⚠️  League not updated in {hours_since:.1f} hours")
        return False
    
    print(f"✓ League updated {hours_since:.1f} hours ago")
    return True

def check_api_health():
    """Check API server health."""
    import urllib.request
    try:
        response = urllib.request.urlopen('http://localhost:8080/api/health', timeout=5)
        data = json.loads(response.read())
        print(f"✓ API server healthy: {data['status']}")
        return True
    except Exception as e:
        print(f"✗ API server error: {e}")
        return False

if __name__ == '__main__':
    checks = [
        check_league_status(),
        # check_api_health(),  # Enable when API deployed
    ]
    
    if not all(checks):
        sys.exit(1)
```

## External Monitoring Services

### Recommended Services

1. **UptimeRobot** (Free tier available)
   - Monitor API endpoints
   - Email/SMS alerts
   - Status page generation

2. **Pingdom** (Free for 1 site)
   - Website uptime monitoring
   - Performance tracking
   - Real-time alerts

3. **Better Stack** (formerly Checkly)
   - API monitoring
   - Synthetic monitoring
   - Incident management

### Setup Example: UptimeRobot

1. Create account at uptimerobot.com
2. Add monitor for `https://pdoom1.com/api/health`
3. Set check interval: 5 minutes
4. Configure alert contacts
5. Create status page (optional, public)

**Monitor Configuration**:
```
Monitor Type: HTTP(s)
URL: https://pdoom1.com/api/health
Interval: 5 minutes
Timeout: 30 seconds
Alert When: Down, SSL expires, Keyword missing
Keyword: "healthy"
```

## Monitoring API Endpoints

### Health Check Endpoint

```bash
curl https://pdoom1.com/api/health

# Expected Response:
{
  "status": "healthy",
  "timestamp": "2025-10-19T12:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "filesystem": "ok",
    "memory": "ok"
  }
}
```

### Status Endpoint

```bash
curl https://pdoom1.com/api/status

# Expected Response:
{
  "status": "operational",
  "uptime": 86400,
  "version": "1.0.0",
  "environment": "production",
  "league": {
    "active": true,
    "current_week": "2025_W42"
  }
}
```

## Log Aggregation

### GitHub Actions Logs

**Access**: Repository → Actions → Workflow Run → Logs

**Retention**: 90 days

**Download**:
```bash
gh run view [run-id] --log > workflow-logs.txt
```

### API Server Logs

When deployed to production:

```bash
# Railway
railway logs

# Render
render logs -s pdoom1-api

# Self-hosted (systemd)
journalctl -u pdoom1-api -f
```

## Metrics to Monitor

### System Metrics
- [ ] API server uptime
- [ ] Response times (p50, p95, p99)
- [ ] Error rates
- [ ] Request volume
- [ ] Memory usage
- [ ] CPU usage

### Application Metrics
- [ ] League resets (success/fail)
- [ ] Deployments (success/fail)
- [ ] Health checks (pass rate)
- [ ] Active participants
- [ ] Score submissions
- [ ] Archive growth rate

### Business Metrics
- [ ] Weekly active players
- [ ] Retention rate (week-over-week)
- [ ] Average scores per week
- [ ] Peak activity times
- [ ] Geographic distribution

## Alert Fatigue Prevention

### Best Practices

1. **Set Appropriate Thresholds**: Don't alert on minor issues
2. **Aggregate Related Alerts**: Group similar failures
3. **Use Priority Levels**: Not everything is critical
4. **Include Resolution Steps**: Make alerts actionable
5. **Regular Review**: Adjust thresholds based on patterns
6. **Silence During Maintenance**: Prevent false alarms

### Alert Tuning

Review alert history monthly:
- Too many false positives? Adjust thresholds
- Missing real issues? Add new checks
- Alert fatigue? Consolidate or remove low-value alerts

## Troubleshooting Guide

### Health Check Failing

```bash
# 1. Check what's failing
npm run test:health

# 2. Review health check results
cat public/data/health-check-results.json | python -m json.tool

# 3. Fix specific issues
# - Missing files: Restore from backup
# - Invalid JSON: Fix syntax errors
# - Script errors: Check Python environment

# 4. Re-run health checks
npm run test:health
```

### API Server Not Responding

```bash
# 1. Check if server is running
curl https://pdoom1.com/api/health

# 2. Check deployment status
gh run list --workflow=deploy-dreamhost.yml --limit 5

# 3. Check server logs (if self-hosted)
journalctl -u pdoom1-api -n 100

# 4. Restart server
# Railway: Auto-restarts on failure
# Render: Manual restart via dashboard
# Self-hosted: systemctl restart pdoom1-api
```

### League Reset Didn't Run

```bash
# 1. Check workflow status
gh run list --workflow=weekly-league-reset.yml --limit 3

# 2. Check current league status
npm run league:status

# 3. Manual reset if needed
npm run league:archive
npm run league:new-week
npm run game:weekly-sync

# 4. Verify new week
npm run league:status
```

## Continuous Improvement

### Monthly Review Checklist

- [ ] Review all alerts from past month
- [ ] Identify false positives
- [ ] Check for missed incidents
- [ ] Update alert thresholds
- [ ] Test recovery procedures
- [ ] Update documentation
- [ ] Review performance trends
- [ ] Optimize monitoring scripts

### Quarterly Goals

- [ ] Improve alert response time
- [ ] Reduce false positive rate
- [ ] Increase test coverage
- [ ] Enhance monitoring dashboards
- [ ] Document new procedures
- [ ] Train team on monitoring tools
