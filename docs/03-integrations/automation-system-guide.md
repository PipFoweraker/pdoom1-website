# Automation System Guide

**Version:** 1.0.0
**Last Updated:** 2025-10-30
**Purpose:** Admin & operations automation for pdoom1-website infrastructure

---

## Overview

This guide documents the automation system for the pdoom1-website infrastructure. This is **separate from the game dashboard** - it handles background maintenance tasks, data updates, and weekly league management.

### Key Principle

**Automate execution, surface results, approve when needed.**

The system runs routine maintenance automatically via GitHub Actions, logs all activity to the `/monitoring/` admin dashboard, and creates GitHub issues for failures or significant events.

---

## Architecture

### Three-Tier Automation

**Tier 1: Fully Automatic (No approval needed)**
- Runs on schedule
- Commits changes automatically
- Creates issue only on failure

Examples:
- Update version info (every 6 hours)
- Calculate game stats (every 6 hours)
- Sync leaderboard data (daily at 2am UTC)

**Tier 2: Auto-execute with Notification (Runs automatically, always notifies)**
- Runs on schedule
- Commits changes automatically
- Creates issue on both success AND failure

Examples:
- Weekly league rollover (Sundays at 23:00 UTC)
- Health checks (every 6 hours)

**Tier 3: Manual Approval (Waits for human trigger)**
- Only runs via workflow_dispatch
- Requires explicit approval

Examples:
- Deploy to production
- Major data migrations

---

## GitHub Actions Workflows

### 1. Auto-Update Data (`auto-update-data.yml`)

**Schedule:** Every 6 hours
**Tier:** 1 (Fully Automatic)
**Purpose:** Keep version and game statistics current

**What it does:**
1. Runs `scripts/update-version-info.py`
2. Runs `scripts/calculate-game-stats.py`
3. Logs to monitoring dashboard
4. Commits changes if data updated
5. Creates issue only if failure

**Manual trigger:**
```bash
# Via GitHub CLI
gh workflow run "Auto-Update Data"

# Or via GitHub web UI
Actions > Auto-Update Data > Run workflow
```

**Monitoring:**
- Status visible at: `/monitoring/` (Automation Status section)
- Log file: `public/monitoring/data/automation-runs.json`
- Current status: `public/monitoring/data/automation-status.json`

---

### 2. Weekly League Rollover (`weekly-league-rollover.yml`)

**Schedule:** Sundays at 23:00 UTC
**Tier:** 2 (Auto-execute with notification)
**Purpose:** Automatically manage weekly competition lifecycle

**What it does:**
1. Archives current week's league data
2. Generates new week with deterministic seed
3. Resets participant counts
4. Logs to monitoring dashboard
5. Creates GitHub issue (success or failure)

**Manual trigger:**
```bash
# Via npm (local)
npm run league:archive
npm run league:new-week

# Via GitHub Actions
gh workflow run "Weekly League Rollover"
```

**Important Notes:**
- Runs 1 hour before week officially ends (safety buffer)
- Archives preserved in `public/leaderboard/data/weekly/archive/`
- New seed is deterministic (same week = same seed)
- Issue created for audit trail

**Monitoring:**
- Current week: `/monitoring/` (Weekly League Management section)
- Current data: `public/leaderboard/data/weekly/current.json`
- Archive: `public/leaderboard/data/weekly/archive/`

---

### 3. Sync Leaderboards (`sync-leaderboards.yml`)

**Schedule:** Daily at 2:00 AM UTC
**Tier:** 1 (Fully Automatic)
**Purpose:** Keep leaderboard data synchronized with game repository

**What it does:**
1. Checks game repository connection
2. Syncs all seed-specific leaderboards
3. Syncs weekly league data
4. Verifies data integrity
5. Commits changes if data updated

**Manual trigger:**
```bash
# Via npm (local)
npm run game:sync-all
npm run game:weekly-sync

# Via GitHub Actions
gh workflow run "Sync Leaderboards" --field sync_type=all
```

**Sync Types:**
- `all` - Full sync of all leaderboards + weekly
- `weekly` - Only weekly league data
- `full` - Complete export including bridge

**Monitoring:**
- Integration status: Check via `npm run game:status`
- Data freshness: `/monitoring/` (Data Freshness card)

---

## Monitoring Dashboard

**Location:** `/monitoring/` (Admin & Operations Dashboard)

**Important:** This is NOT the game dashboard. This is for infrastructure monitoring only.

### Dashboard Sections

1. **Website Status** - Response time, uptime
2. **Deployment Status** - Last deploy, version, health score
3. **Data Freshness** - Version/stats age, next update time
4. **GitHub Integration** - API status, issues, releases
5. **🤖 Automation Status** - GitHub Actions job runs and success rates
6. **🏆 Weekly League Management** - Current week, seed, participants
7. **Recent Health Checks** - Script execution results

### Automation Status Display

For each automated job:
- **Job name** (human-readable)
- **Last run** timestamp
- **Success rate** percentage
- **Status** indicator (OK/ISSUE)

Example display:
```
auto update data
Last run: 2h ago | Success rate: 95% (19/20)
[OK]

weekly league rollover
Last run: 3d ago | Success rate: 100% (4/4)
[OK]
```

### Weekly League Display

Shows:
- Current week ID and date range
- Days remaining in week
- Weekly seed (deterministic)
- Participant count
- Submission count

---

## Logging System

### Scripts

**`log-automation-run.py`**

Purpose: Logs GitHub Actions runs to monitoring dashboard

Usage:
```bash
python scripts/log-automation-run.py \
  --job "job-name" \
  --trigger "schedule|workflow_dispatch" \
  --step1-status "success" \
  --step2-status "failure"
```

Called automatically by workflows.

### Data Files

**`public/monitoring/data/automation-runs.json`**

Contains last 100 automation runs:
```json
[
  {
    "job": "auto-update-data",
    "trigger": "schedule",
    "timestamp": "2025-10-30T14:00:00Z",
    "status": "success",
    "details": {
      "version-status": "success",
      "stats-status": "success"
    }
  }
]
```

**`public/monitoring/data/automation-status.json`**

Current status of all jobs:
```json
{
  "last_updated": "2025-10-30T14:00:00Z",
  "jobs": {
    "auto-update-data": {
      "last_run": "2025-10-30T14:00:00Z",
      "last_success": "2025-10-30T14:00:00Z",
      "last_failure": "2025-10-29T02:00:00Z",
      "total_runs": 20,
      "success_count": 19,
      "failure_count": 1
    }
  }
}
```

---

## Notification System

### GitHub Issues

Automation creates issues for:

**Success notifications** (Tier 2 only):
- Labels: `automation`, `[job-type]`, `success`, `auto-created`
- Purpose: Audit trail for important events
- Example: Weekly league rollover completion

**Failure alerts** (All tiers):
- Labels: `automation`, `[job-type]`, `bug`, `auto-created`
- Priority: `high-priority` if critical
- Purpose: Immediate attention to broken automation

### Issue Content

All automated issues include:
- Workflow run ID (link to logs)
- Timestamp
- Status of each step
- Required actions / next steps
- Priority level

---

## Manual Operations

### Weekly League Management

**Check status:**
```bash
npm run league:status
```

**Manual rollover:**
```bash
# 1. Archive current week
npm run league:archive

# 2. Start new week
npm run league:new-week

# 3. Verify
npm run league:status
npm run league:standings
```

**Generate seed manually:**
```bash
npm run league:seed
```

### Data Sync

**Check integration:**
```bash
npm run game:status
```

**Sync all data:**
```bash
npm run game:sync-all
```

**Sync weekly only:**
```bash
npm run game:weekly-sync
```

### Health Checks

**Run all tests:**
```bash
npm run test:all
```

**Integration tests:**
```bash
npm run integration:test
```

**Health check:**
```bash
npm run test:health
```

---

## Troubleshooting

### Automation Job Failed

1. Check `/monitoring/` dashboard for error status
2. Find the GitHub issue (labeled `auto-created`)
3. Click workflow run link in issue
4. Review logs for specific error
5. Fix issue and either:
   - Wait for next scheduled run, OR
   - Manually trigger workflow, OR
   - Run script locally via npm

### Weekly League Stuck

**Symptoms:** League showing old week, days remaining negative

**Fix:**
```bash
npm run league:status           # Check current state
npm run league:archive          # Archive old week
npm run league:new-week         # Start fresh week
npm run league:status           # Verify
```

### Leaderboard Data Stale

**Symptoms:** Data Freshness showing old age in `/monitoring/`

**Fix:**
```bash
npm run game:status             # Check connection
npm run game:sync-all           # Force sync
npm run update:version          # Update version data
npm run update:stats            # Update game stats
```

### GitHub Actions Not Running

**Check:**
1. Go to GitHub repository > Actions tab
2. Check if workflows are enabled
3. Look for failed runs
4. Check repository permissions

**Fix:**
- Enable workflows if disabled
- Check secrets are configured
- Verify `GITHUB_TOKEN` has write permissions

---

## Development Workflow

### Adding New Automation

1. Create workflow file in `.github/workflows/`
2. Add logging call to `log-automation-run.py`
3. Update `/monitoring/` dashboard if needed
4. Document in this guide
5. Test via workflow_dispatch first
6. Enable schedule after validation

### Testing Automation Locally

```bash
# Test scripts individually
npm run update:version
npm run update:stats
npm run league:status

# Test integration
npm run integration:test

# Simulate automation run
python scripts/log-automation-run.py \
  --job "test-job" \
  --trigger "manual" \
  --test-status "success"
```

### Monitoring Best Practices

1. Check `/monitoring/` dashboard daily
2. Review automation issues weekly
3. Close successful rollover issues monthly
4. Investigate any <80% success rates
5. Keep automation logs under 100 entries

---

## Nomenclature & Separation of Concerns

### Admin/Monitoring Dashboard (`/monitoring/`)

**Purpose:** Infrastructure operations and automation monitoring
**Audience:** Repository maintainers, developers
**Content:** System health, automation status, deployment metrics
**Visibility:** Low-profile, linked from footer

### Game Dashboard (TBD - separate implementation)

**Purpose:** Player-facing game statistics and visualizations
**Audience:** Players, community
**Content:** Doom-flavored UI, game stats, player achievements
**Visibility:** High-profile, featured prominently

**These are separate systems** - do not conflate them. The automation/monitoring is backend infrastructure that players don't need to see.

---

## NPM Scripts Reference

### Automation-Related Commands

```json
{
  "update:version": "python scripts/update-version-info.py",
  "update:stats": "python scripts/calculate-game-stats.py",
  "sync:all": "npm run update:version && npm run update:stats",

  "game:status": "python scripts/game-integration.py --status",
  "game:sync-all": "python scripts/game-integration.py --sync-leaderboards",
  "game:weekly-sync": "python scripts/game-integration.py --weekly-sync",

  "league:status": "python scripts/weekly-league-manager.py --status",
  "league:new-week": "python scripts/weekly-league-manager.py --new-week",
  "league:archive": "python scripts/weekly-league-manager.py --archive-week",
  "league:standings": "python scripts/weekly-league-manager.py --standings",

  "test:all": "python scripts/health-check.py && python scripts/verify-deployment.py",
  "integration:test": "python scripts/test-integration.py --quick"
}
```

---

## Future Enhancements

Potential improvements:

1. **Slack/Discord notifications** - Real-time alerts
2. **Metrics dashboard** - Historical trends
3. **Auto-recovery** - Retry failed jobs automatically
4. **Rate limiting** - Prevent API throttling
5. **Cross-repo triggers** - Game repo pushes trigger website updates

---

## Support & Questions

- **Issues:** Create GitHub issue with label `automation`
- **Logs:** Check `/monitoring/` dashboard first
- **Status:** All automation visible at `/monitoring/`
- **Emergency:** Run scripts manually via npm

---

**End of Automation System Guide**
