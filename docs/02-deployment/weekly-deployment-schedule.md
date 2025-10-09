# Weekly Deployment Schedule for p(Doom)1

## Overview
This document establishes the weekly deployment rhythm for p(Doom)1 website and game updates, with deployments every **Friday at 4:00 PM AEST (Hobart time)** to prepare for the new league week starting Monday.

## Schedule Summary

| Event | Day | Time (AEST) | Time (UTC) | Description |
|-------|-----|-------------|------------|-------------|
| **League Start** | Monday | 00:00 | Sunday 14:00* | New weekly league begins |
| **Balance Changes** | Tuesday | 10:00 | 00:00 | Balance adjustments based on Monday data |
| **Testing Window** | Wed-Thu | All day | - | QA and integration testing |
| **Deployment Freeze** | Thursday | 17:00 | 07:00 | Code freeze for Friday release |
| **Pre-Deployment** | Friday | 14:00-15:30 | 04:00-05:30 | Final checks and preparation |
| **🚀 DEPLOYMENT** | **Friday** | **16:00** | **06:00** | Production deployment |
| **Twitch Stream** | Friday | 16:30-17:30 | 06:30-07:30 | Live deployment watch party |
| **Post-Deploy Monitor** | Friday | 16:00-18:00 | 06:00-08:00 | Active monitoring period |
| **Weekend Buffer** | Sat-Sun | All day | - | Time for emergency fixes if needed |

\* *AEST is UTC+10 (standard) or UTC+11 (daylight saving). Hobart observes daylight saving Oct-Apr.*

## Weekly Deployment Workflow

### Monday (League Start Day)
- **00:00 AEST**: New weekly league automatically starts
- **Throughout day**: Monitor league participation and initial gameplay
- **End of day**: Collect initial balance feedback

### Tuesday (Balance & Planning)
- **09:00-12:00**: Review Monday's league data and player feedback
- **10:00**: Implement balance changes if needed (game repository)
- **12:00-17:00**: Development work on features/fixes
- **17:00**: Balance changes merged and ready for testing

### Wednesday-Thursday (Testing Window)
- **Wednesday AM**: Integration testing begins
- **Wednesday PM**: Weekly league data sync testing
- **Thursday AM**: Final QA and regression testing
- **Thursday PM**: Documentation updates
- **Thursday 17:00 AEST (07:00 UTC)**: CODE FREEZE - no more changes

### Friday (Deployment Day)

#### Pre-Deployment (14:00-16:00 AEST / 04:00-06:00 UTC)
- **14:00**: Pre-deployment checks begin
  ```bash
  npm run deploy:prepare
  npm run test:all
  npm run league:status
  ```
- **14:30**: Game data sync from pdoom1 repository
  ```bash
  npm run game:sync-all
  npm run game:weekly-sync
  ```
- **15:00**: Verify deployment readiness
  ```bash
  python scripts/verify-deployment.py
  python scripts/weekly-league-manager.py --status
  ```
- **15:30**: Final smoke tests and manual review
- **15:45**: Deploy/No-Deploy decision point

#### Deployment (16:00 AEST / 06:00 UTC)
- **16:00**: Trigger automated deployment workflow
  - Via GitHub Actions: `version-aware-deploy.yml`
  - Or manual: `deploy-dreamhost.yml`
- **16:05**: Deployment propagates to DreamHost
- **16:10**: Automated health checks run
- **16:15**: Manual verification of key pages

#### Live Stream & Monitoring (16:30-18:00 AEST / 06:30-08:00 UTC)
- **16:30**: Begin Twitch stream
  - Show deployment status
  - Preview new features
  - Test game integration live
  - Answer community questions
- **17:00**: Stream league overview for upcoming week
- **17:30**: Stream ends, continue monitoring
- **18:00**: Log off for weekend (monitoring continues via automation)

### Weekend (Saturday-Sunday)
- **Automated monitoring**: Health checks every 6 hours
- **On-call**: Developer available for critical issues only
- **Community**: Players testing new features and league
- **Sunday PM**: Brief check-in before Monday league start

## Deployment Automation

### Automated Pre-Deployment Checklist
The following checks run automatically before deployment:

1. **Version Validation**
   - Check version number incremented correctly
   - Validate changelog updated
   - Verify blog post exists (for major/minor versions)

2. **Data Integrity**
   - Verify all JSON files are valid
   - Check leaderboard data is current
   - Validate weekly league configuration

3. **Integration Tests**
   - Test game data integration
   - Verify API endpoints respond
   - Check external dependencies

4. **File Integrity**
   - Ensure all critical files exist
   - Validate sitemap generation
   - Check content completeness

### Manual Deployment Process

#### Option 1: Automated (Recommended)
```bash
# Via GitHub Actions
1. Go to Actions → "Version-Aware Deployment to DreamHost"
2. Click "Run workflow"
3. Leave defaults (unless emergency)
4. Click "Run workflow"
5. Monitor progress in Actions tab
6. Approve if prompted for major version
```

#### Option 2: Manual (Emergency Only)
```bash
# Local deployment steps
npm run deploy:prepare        # Run all pre-checks
npm run sync:all              # Sync all data
npm run deploy:verify         # Final verification

# Then trigger via GitHub Actions or SSH directly to DreamHost
```

## Rollback Procedures

### Quick Rollback (< 30 minutes)
If critical issue discovered immediately after deployment:

1. **Stop the bleeding**
   ```bash
   # Via GitHub Actions
   - Revert last commit: git revert HEAD
   - Re-run deployment workflow
   ```

2. **Notify users**
   - Update status page
   - Post in Discord/community channels
   - Twitter announcement if major

3. **Investigate offline**
   - Pull logs from DreamHost
   - Review deployment verification output
   - Identify root cause

### Standard Rollback (30 min - 2 hours)
For issues discovered during stream or monitoring period:

1. **Assess impact**
   - Is site functional? (if yes, can wait)
   - Are scores being lost? (if yes, immediate rollback)
   - Is it just a visual bug? (if yes, can hotfix)

2. **Execute rollback**
   ```bash
   # Revert to previous version
   git revert <commit-sha>
   git push
   
   # Or checkout previous version
   git checkout <previous-tag>
   # Create hotfix branch and force deploy
   ```

3. **Communicate timeline**
   - Announce on stream
   - Update users on expected fix time
   - Set expectations for next deployment

### Emergency Rollback (Critical)
For site-down or data-loss scenarios:

1. **Immediate actions** (< 5 minutes)
   ```bash
   # Direct SSH to DreamHost
   ssh user@pdoom1.com
   cd ~/pdoom1.com
   
   # Quick restore from backup
   cp -r backup_YYYYMMDD/* .
   ```

2. **Use force deployment**
   - GitHub Actions with `force_deploy: true`
   - Bypasses version checks
   - Requires detailed notes in deployment_notes

3. **Post-incident**
   - Write incident report
   - Update rollback procedures
   - Add prevention checks

## Responsibility Matrix

| Task | Primary | Backup | Tools/Access Required |
|------|---------|--------|----------------------|
| **Pre-Deployment Checks** | Lead Dev | QA | Local environment, npm |
| **Game Data Sync** | Lead Dev | DevOps | Access to game repo |
| **Balance Changes** | Game Designer | Lead Dev | Game repo commit access |
| **Deployment Execution** | Lead Dev | DevOps | GitHub Actions access |
| **Live Stream** | Lead Dev | Community Manager | Twitch account, OBS |
| **Monitoring** | Automated | Lead Dev | GitHub Actions, monitoring tools |
| **Rollback Decision** | Lead Dev | Product Owner | Deployment access |
| **Emergency Response** | On-Call Dev | Lead Dev | SSH access to DreamHost |
| **Post-Deploy Comms** | Community Manager | Lead Dev | Discord, Twitter access |

## Monitoring & Health Checks

### Automated Monitoring
- **Every 6 hours**: Full health check workflow
  - Site accessibility
  - API endpoint verification
  - Leaderboard data freshness
  - Weekly league status

### Post-Deployment Monitoring (16:00-18:00 AEST)
- **16:15**: First manual check - all pages load
- **16:30**: Check during live stream - user experience
- **17:00**: API endpoint testing
- **17:30**: Leaderboard verification
- **18:00**: Final check before logging off

### Weekend Monitoring
- **Automated only**: Health checks every 6 hours
- **Alert thresholds**:
  - Site down > 5 minutes: Page on-call
  - API errors > 10/hour: Email alert
  - No leaderboard updates > 24 hours: Email alert

## Communication Plan

### Pre-Deployment
- **Thursday**: Twitter/Discord announcement
  - "Weekly deployment Friday 4pm AEST"
  - Highlight major changes
  - Link to changelog

### Deployment Day
- **Friday 15:45**: Final go/no-go in Discord
- **Friday 16:00**: "Deployment starting" announcement
- **Friday 16:30**: Start Twitch stream
  - Live deployment watch
  - Feature showcase
  - Q&A session
- **Friday 17:30**: Post-deployment summary
  - What was deployed
  - Known issues (if any)
  - Next week's focus

### Post-Deployment
- **Friday 18:00**: Summary post on Discord/Twitter
- **Monday AM**: "New league week" announcement
- **Throughout week**: Community feedback collection

## Integration with Weekly League

### League Reset Timing
- **Monday 00:00 AEST**: Automated league reset
  ```bash
  # Runs automatically via cron or GitHub Actions
  npm run league:new-week
  ```

### Seed Generation
- **Friday deployment includes**: New competitive seed for upcoming week
  ```bash
  npm run league:seed
  ```

### Archive Management
- **Sunday 23:59 AEST**: Previous week auto-archived
  ```bash
  npm run league:archive
  ```

## Emergency Scenarios

### Scenario 1: Deployment Fails During Stream
1. **Stay calm on stream**: "We're experiencing a technical issue"
2. **Switch to backup content**: Show existing features, take Q&A
3. **Debug offline**: Check GitHub Actions logs
4. **Decision point** (10 minutes):
   - Can fix quickly? Do it live (good content)
   - Need more time? Postpone and reschedule
5. **Communicate**: Set clear expectations

### Scenario 2: Critical Bug Found on Monday
1. **Assess severity**: Can it wait until Friday?
2. **If urgent**: Hotfix procedure
   ```bash
   # Create hotfix branch
   git checkout -b hotfix/critical-fix
   # Make minimal fix
   # Increment patch version
   # Deploy via force_deploy if needed
   ```
3. **If can wait**: Add to Friday deployment

### Scenario 3: Game Repository Not Ready
1. **Friday 15:00**: Check game repo status
2. **If not ready**: 
   - Deploy website updates only
   - Skip game data sync
   - Communicate to users: "Game update coming in separate deployment"
3. **When ready**: Mini-deployment (Monday-Wednesday)

## Continuous Improvement

### Post-Deployment Review
- **Every month**: Review deployment logs
- **Metrics to track**:
  - Deployment success rate
  - Time from trigger to live
  - Number of rollbacks
  - Issues found post-deployment
  - Stream viewership and engagement

### Process Updates
- **Quarterly**: Review and update this schedule
- **After incidents**: Update rollback procedures
- **Community feedback**: Adjust timing if needed

## Tools & Resources

### Required Access
- [ ] GitHub repository (write access)
- [ ] GitHub Actions (workflow trigger)
- [ ] DreamHost SSH credentials
- [ ] Twitch streaming account
- [ ] Discord admin access
- [ ] Twitter account access

### Documentation Links
- [Deployment Guide](./deployment-guide.md)
- [Version-Aware Deployment](./GITHUB_ENVIRONMENT_SETUP.md)
- [Weekly League System](../03-integrations/weekly-league-phase1-complete.md)
- [Game Integration](../03-integrations/game-repository-integration.md)

### Support Contacts
- **Primary**: Lead Developer (on Twitch during deployment)
- **Backup**: DevOps (on-call)
- **Emergency**: Product Owner (critical decisions)

---

## Quick Reference Card

**Deployment Time**: Friday 16:00 AEST (06:00 UTC)  
**Pre-Deployment Start**: Friday 14:00 AEST  
**Code Freeze**: Thursday 17:00 AEST  
**Stream**: Friday 16:30-17:30 AEST on Twitch  

**One-Command Deploy Check**:
```bash
npm run deploy:prepare && npm run league:status && echo "READY FOR DEPLOYMENT"
```

**Emergency Rollback**:
```bash
git revert HEAD && git push
# Then re-run deployment workflow
```

**Next Week's League**:
```bash
npm run league:new-week  # Monday 00:00 AEST
```
