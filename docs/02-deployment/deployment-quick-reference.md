# Weekly Deployment Quick Reference

## [CAL] Schedule at a Glance

| Day | Time (AEST) | Event |
|-----|-------------|-------|
| **Monday** | 00:00 | [TROPHY] New league starts (automated) |
| Tuesday | 10:00 | [BALANCE] Balance changes window |
| Wed-Thu | All day | [TEST] Testing & QA |
| **Thursday** | 17:00 | [LOCKED] Code freeze |
| **Friday** | 14:00 | [OK] Pre-deployment checks |
| **Friday** | 16:00 | [DEPLOY] **DEPLOYMENT** |
| **Friday** | 16:30 | [STREAM] Twitch stream |

## [ZAP] Quick Commands

### Pre-Deployment (Friday 14:00)
```bash
npm run deploy:prep-weekly    # Full preparation with all checks
npm run deploy:check           # Quick status check (no changes)
npm run league:status          # Verify league is ready
```

### Deployment (Friday 16:00)
**Via GitHub Actions:**
1. Go to: https://github.com/PipFoweraker/pdoom1-website/actions
2. Click: "Weekly Scheduled Deployment"
3. Click: "Run workflow"
4. Click: "Run workflow" (confirm)

**Manual Emergency Deployment:**
```bash
# If GitHub Actions fails
gh workflow run weekly-deployment.yml
# Or use legacy method
gh workflow run deploy-dreamhost.yml
```

### Post-Deployment (Friday 16:10)
```bash
# Verify deployment
curl https://pdoom1.com
curl https://pdoom1.com/leaderboard/data/weekly/current.json

# Check site health
npm run test:health
```

## [LIST] Friday Deployment Checklist

### Pre-Flight (14:00-15:45)
- [ ] Run `npm run deploy:prep-weekly`
- [ ] All checks green [OK]
- [ ] Game data synced (< 24h old)
- [ ] League seed generated for current week
- [ ] No critical bugs reported

### Launch (16:00)
- [ ] Trigger GitHub Actions workflow
- [ ] Monitor deployment logs
- [ ] Wait for completion (~5 minutes)

### Verify (16:10-16:20)
- [ ] Visit https://pdoom1.com
- [ ] Check version in footer
- [ ] Test leaderboard page
- [ ] Verify weekly league current week
- [ ] No console errors

### Stream (16:30-17:30)
- [ ] Start Twitch stream
- [ ] Show new features
- [ ] Answer community questions
- [ ] Preview upcoming week

## [ALERT] Emergency Procedures

### If Deployment Fails
1. Check GitHub Actions logs
2. Verify DreamHost connection
3. Try manual deployment:
   ```bash
   gh workflow run deploy-dreamhost.yml
   ```
4. If still fails, contact team

### If Site is Down After Deployment
1. **Quick rollback** (< 5 min):
   ```bash
   git revert HEAD
   git push
   # Re-run deployment workflow
   ```

2. **Check logs**:
   - GitHub Actions logs
   - DreamHost error logs (via SSH)

3. **Communicate**:
   - Post in Discord: "Investigating deployment issue"
   - Update stream viewers

### If Critical Bug Found
**During stream (16:30-18:00):**
- Note bug, continue stream, fix later unless site-breaking
- If site-breaking: Pause stream, rollback, resume

**After stream:**
- Create hotfix branch
- Test thoroughly
- Deploy Monday with force_deploy flag

## [LINK] Important Links

- **GitHub Actions**: https://github.com/PipFoweraker/pdoom1-website/actions
- **Live Site**: https://pdoom1.com
- **Leaderboard**: https://pdoom1.com/leaderboard/
- **Weekly League Data**: https://pdoom1.com/leaderboard/data/weekly/current.json
- **Full Documentation**: [Weekly Deployment Schedule](./weekly-deployment-schedule.md)
- **Detailed Checklist**: [Deployment Checklist](./weekly-deployment-checklist.md)

## [PHONE] Contact & Escalation

| Role | Availability | Contact |
|------|-------------|---------|
| **Deployer** | Fri 14:00-18:00 | On Twitch stream |
| **Backup** | Fri 14:00-18:00 | Discord DM |
| **On-Call** | Sat-Sun | Discord (emergencies only) |

## [TIME] Timezone Reference

**AEST** (Australian Eastern Standard Time) = UTC+10  
**AEDT** (Australian Eastern Daylight Time) = UTC+11 (Oct-Apr)

Hobart observes daylight saving, so:
- **Oct-Apr**: Use AEDT (UTC+11)
- **Apr-Oct**: Use AEST (UTC+10)

**Deployment Time Conversions:**
- 16:00 AEDT = 05:00 UTC
- 16:00 AEST = 06:00 UTC

GitHub Actions cron uses UTC:
- Friday deployment: `0 6 * * 5` (06:00 UTC = 16:00 AEST)
- Monday league reset: `0 14 * * 0` (14:00 UTC Sunday = 00:00 AEST Monday)

*Note: During daylight saving, manually adjust if needed or update cron to `0 5 * * 5`*

## [TARGET] Success Metrics

Track these after each deployment:
- [OK] Deployment completed in < 10 minutes
- [OK] No rollback needed
- [OK] Zero critical bugs reported
- [OK] Stream had viewers
- [OK] Positive community feedback

## [NOTE] Notes Space

**This Week** (Week of ___________):
- Version deploying: v_______
- Special considerations: ________________
- New features: ________________
- Known issues: ________________

---

[TIP] **Tip**: Print this page and keep it handy during Friday deployments!
