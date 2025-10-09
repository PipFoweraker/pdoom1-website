# Weekly Deployment Checklist

## Pre-Deployment (Thursday 17:00 AEST - Code Freeze)

### Code & Content Review
- [ ] All PRs for the week merged to `main`
- [ ] Version number incremented in `package.json`
- [ ] `CHANGELOG.md` updated with changes
- [ ] Blog post created (if major/minor version)
- [ ] Documentation updated for new features
- [ ] No known critical bugs in main branch

### Testing Verification
- [ ] All automated tests passing
- [ ] Manual QA completed for new features
- [ ] Cross-browser testing done (Chrome, Firefox, Safari)
- [ ] Mobile responsiveness verified
- [ ] Leaderboard integration tested
- [ ] Weekly league functionality tested

### Data Integrity
- [ ] Game data synced from pdoom1 repository
- [ ] Leaderboard data current (< 24 hours old)
- [ ] Weekly league configuration validated
- [ ] All JSON files pass validation
- [ ] No corrupt or missing data files

## Pre-Deployment Day (Friday 14:00-16:00 AEST)

### Automated Checks
Run these commands and verify all pass:

```bash
# Full pre-deployment check
npm run deploy:prepare
```

Expected output: "Ready for deployment!"

```bash
# Verify game integration status
npm run game:status
```

Expected: Connection to game repo confirmed, data fresh

```bash
# Check weekly league status
npm run league:status
```

Expected: Current week shown, seed generated, no errors

```bash
# Run all tests
npm run test:all
```

Expected: All tests pass

### Manual Pre-Deployment Verification

#### Website Content (Local Check)
- [ ] Start local server: `npm start`
- [ ] Navigate to http://localhost:5173
- [ ] Home page loads correctly
- [ ] Navigation works on all pages
- [ ] Leaderboard page displays data
- [ ] Weekly league section shows current week
- [ ] Blog posts visible and formatted correctly
- [ ] Footer links work
- [ ] No console errors in browser

#### Data Files Review
- [ ] Check `public/data/status.json` has current game version
- [ ] Verify `public/leaderboard/data/leaderboard.json` exists
- [ ] Confirm `public/leaderboard/data/weekly/current.json` has this week's data
- [ ] Review `public/data/deployment-verification.json` shows green status

#### Game Integration
- [ ] Run: `python scripts/game-integration.py --status`
- [ ] Verify connection to game repository
- [ ] Check last sync time (should be recent)
- [ ] Confirm leaderboard export working

#### Weekly League Preparation
- [ ] Run: `python scripts/weekly-league-manager.py --status`
- [ ] Current week ID matches calendar week
- [ ] Competitive seed generated for this week
- [ ] Days remaining shows correct countdown
- [ ] No errors in league configuration

### Communication Preparation
- [ ] Draft Discord announcement
- [ ] Draft Twitter/X announcement
- [ ] Prepare Twitch stream title and description
- [ ] Notify team members of deployment time
- [ ] Set calendar reminder for 16:00 AEST

## Deployment Execution (Friday 16:00 AEST)

### Trigger Deployment

#### Option A: Automated Weekly Deployment (Recommended)
1. [ ] Go to GitHub → Actions tab
2. [ ] Select "Weekly Scheduled Deployment" workflow
3. [ ] Click "Run workflow"
4. [ ] Configure options:
   - Skip checks: ❌ (leave unchecked)
   - Reset league: ✅ (if deploying on Sunday)
   - Dry run: ❌ (uncheck for real deployment)
   - Notes: Add any relevant notes
5. [ ] Click "Run workflow" button
6. [ ] Monitor workflow progress

#### Option B: Version-Aware Deployment (Alternative)
1. [ ] Go to GitHub → Actions tab
2. [ ] Select "Version-Aware Deployment to DreamHost"
3. [ ] Click "Run workflow"
4. [ ] Configure:
   - Force deploy: ❌
   - Skip version check: ❌
   - Notes: "Weekly scheduled deployment"
5. [ ] Click "Run workflow"
6. [ ] Approve if prompted (major versions only)

### Monitor Deployment
- [ ] Watch workflow logs for errors
- [ ] Verify each job completes successfully:
  - [ ] Pre-deployment preparation ✅
  - [ ] Deploy to production ✅
  - [ ] Post-deployment tasks ✅
- [ ] Note any warnings (review but may be non-critical)
- [ ] Check total deployment time (typically 3-5 minutes)

## Post-Deployment (Friday 16:00-18:00 AEST)

### Immediate Verification (16:10-16:20)
- [ ] Visit https://pdoom1.com
- [ ] Home page loads (< 3 seconds)
- [ ] Check version in footer matches deployed version
- [ ] Test navigation - all pages load
- [ ] Leaderboard page displays correctly
- [ ] Weekly league shows current week
- [ ] No 404 errors on key pages
- [ ] Check browser console for errors
- [ ] Mobile view check (use browser dev tools)

### Deep Verification (16:20-16:30)
- [ ] Test all navigation links
- [ ] Verify external links work (Discord, Twitter, GitHub)
- [ ] Check game download links
- [ ] Test leaderboard sorting and filtering
- [ ] Verify weekly league standings (if available)
- [ ] Check blog posts display correctly
- [ ] Test search functionality (if applicable)
- [ ] Verify sitemap.xml accessible

### Automated Health Checks
Wait for automated checks to complete (~30 seconds after deployment):

- [ ] Monitor workflow for post-deployment verification
- [ ] Check GitHub Actions shows ✅ for post-deployment tasks
- [ ] Review `deployment-verification.json` results

### Live Stream Setup (16:20-16:30)
- [ ] Open OBS or streaming software
- [ ] Set stream title: "p(Doom)1 Weekly Deployment - [Date] - New Features!"
- [ ] Configure scenes:
  - Browser showing pdoom1.com
  - Editor/terminal for live debugging if needed
  - Webcam/mic check
- [ ] Start stream at 16:30 AEST
- [ ] Welcome viewers and explain what's new

### Live Stream Content (16:30-17:30)
- [ ] Show deployed website
- [ ] Demonstrate new features
- [ ] Explain any changes
- [ ] Show weekly league details
- [ ] Take questions from chat
- [ ] Test game integration live
- [ ] Preview upcoming week
- [ ] Thank contributors and viewers

## Post-Stream (17:30-18:00 AEST)

### Final Verification
- [ ] Re-check website after stream traffic
- [ ] Monitor for any error reports
- [ ] Check Discord for user feedback
- [ ] Review any questions from stream
- [ ] Verify leaderboard still functioning

### Communication
- [ ] Post deployment summary to Discord
  - What was deployed
  - Version number
  - Key changes
  - Known issues (if any)
- [ ] Tweet deployment announcement
  - Link to changelog
  - Highlight major features
  - Thank community
- [ ] Update any relevant documentation
- [ ] Respond to community questions

### Monitoring Setup
- [ ] Verify automated health checks scheduled (every 6 hours)
- [ ] Confirm on-call person aware (for weekend)
- [ ] Set up monitoring alerts if not automatic
- [ ] Check that rollback plan is accessible

### Documentation
- [ ] Log deployment time and outcome
- [ ] Note any issues encountered
- [ ] Record deployment duration
- [ ] Document any manual steps needed
- [ ] Update this checklist if process changed

## Weekend Monitoring (Saturday-Sunday)

### Saturday Morning Check (Optional)
- [ ] Quick site visit - verify still up
- [ ] Check for any error reports in Discord
- [ ] Review automated health check results
- [ ] Respond to any critical issues

### Sunday Evening Check
- [ ] Verify site stability before Monday league start
- [ ] Check weekly league will auto-reset Monday 00:00
- [ ] Confirm league data looks correct
- [ ] Review week's feedback for next deployment

## Emergency Procedures

### If Deployment Fails During Execution
1. [ ] Check workflow logs for specific error
2. [ ] Verify all secrets configured correctly
3. [ ] Test SSH connection to DreamHost manually
4. [ ] Attempt manual deployment if needed
5. [ ] Notify team and community of delay
6. [ ] Follow rollback procedure if necessary

### If Critical Bug Found After Deployment
1. [ ] Assess severity (site down vs. minor bug)
2. [ ] Decide: Hotfix immediately or wait for next week
3. [ ] If hotfix needed:
   - [ ] Create hotfix branch
   - [ ] Make minimal fix
   - [ ] Test thoroughly
   - [ ] Deploy with force_deploy flag
   - [ ] Document in incident log
4. [ ] If can wait:
   - [ ] Log issue for next deployment
   - [ ] Communicate workaround to users
   - [ ] Prioritize fix for Friday

### Rollback Procedure
If site is broken and needs immediate rollback:

1. [ ] Assess: Can we fix forward or must rollback?
2. [ ] If rollback needed:
   ```bash
   git revert HEAD  # Revert last commit
   git push
   ```
3. [ ] Re-run deployment workflow
4. [ ] Verify rolled back successfully
5. [ ] Communicate to users
6. [ ] Write incident report
7. [ ] Plan fix for next deployment

## Post-Deployment Review (Following Week)

### Metrics to Collect
- [ ] Deployment success: ✅ / ❌
- [ ] Time from trigger to live: ___ minutes
- [ ] Issues found: ___ critical, ___ minor
- [ ] Rollback needed: Yes / No
- [ ] Stream viewership: ___ peak viewers
- [ ] Community feedback: Positive / Mixed / Negative

### Improvement Questions
- [ ] What went well?
- [ ] What could be improved?
- [ ] Any checklist steps unclear?
- [ ] Any automation gaps?
- [ ] Should schedule change?
- [ ] Any communication issues?

### Action Items
- [ ] Update checklist based on learnings
- [ ] Schedule any needed improvements
- [ ] Share feedback with team
- [ ] Document any new procedures

---

## Quick Reference

**Deployment Command**: GitHub Actions → "Weekly Scheduled Deployment" → Run workflow

**Time**: Friday 16:00 AEST (06:00 UTC)

**Stream**: Twitch @ 16:30 AEST

**Emergency Contact**: [On-call developer info]

**Rollback**: `git revert HEAD && git push` then re-run deployment

**Status Check**: `npm run deploy:prepare && npm run league:status`

---

## Notes Section
Use this space for deployment-specific notes:

**This Week's Focus**:
- 
- 
- 

**Known Issues**:
- 
- 

**Special Considerations**:
- 
- 

**Team Availability**:
- Deployer: 
- Backup: 
- On-call: 
