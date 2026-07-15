# Dashboard Deployment Instructions

**Project**: P(doom) Risk Dashboard Integration
**Date**: October 30, 2025
**Status**: 🟢 Ready for Deployment

---

## Quick Start

The dashboard integration is **complete and tested**. To deploy to production:

```bash
cd /home/laptop/Documents/Projects/ai-sandbox/pdoom1-website

# Verify commit is ready
jj log -r main --limit 1

# Push to GitHub (requires authentication)
jj git push --bookmark main

# Netlify will auto-deploy within 1-2 minutes
```

---

## What Was Done

### Files Added
1. `public/dashboard/index.html` (30KB) - Main dashboard application
2. `public/assets/pdoom1-office-cat-default.png` (3.8MB) - Primary cat image
3. `public/assets/small-doom-cat.png` (109KB) - Secondary cat image
4. `DASHBOARD_INTEGRATION_CHANGELOG.md` - Detailed change log
5. `DASHBOARD_TESTING_REPORT.md` - Comprehensive test results
6. `DEPLOYMENT_INSTRUCTIONS.md` (this file)

### Files Modified
1. `public/index.html` - Added "Risk Dashboard" link to navigation (line 733)
2. `public/resources/index.html` - Added featured dashboard callout (lines 219-228)

### Configuration Changes
1. `.jj/repo/config.toml` - Increased `snapshot.max-new-file-size = 4000000` to handle large cat images

---

## Current Status

### Commit Information
- **Hash**: `f8f51517`
- **Bookmark**: `main`
- **Message**: "Add P(doom) Risk Dashboard integration"
- **Author**: StevenGITHUBwork@proton.me
- **Timestamp**: 2025-10-30 01:13:04

### Testing Status
- ✅ 11/11 tests passed (100% pass rate)
- ✅ All endpoints return HTTP 200
- ✅ No broken links or 404 errors
- ✅ Design consistency verified
- ✅ Asset paths converted to web-relative URLs

### Documentation Status
- ✅ Changelog created (DASHBOARD_INTEGRATION_CHANGELOG.md)
- ✅ Testing report created (DASHBOARD_TESTING_REPORT.md)
- ✅ Deployment instructions created (this file)
- ✅ Integration plan created (DASHBOARD_WEBSITE_INTEGRATION_PLAN.md)

---

## Deployment Process

### Step 1: Verify Local State

```bash
cd /home/laptop/Documents/Projects/ai-sandbox/pdoom1-website

# Check jj status
jj status
# Expected: "The working copy has no changes"

# Verify commit
jj log -r main --limit 1
# Expected: f8f51517 "Add P(doom) Risk Dashboard integration"
```

### Step 2: Push to GitHub

The repository uses HTTPS authentication. You'll need to authenticate when pushing:

```bash
jj git push --bookmark main
```

**Authentication Options**:
1. **Personal Access Token (PAT)** - Generate at https://github.com/settings/tokens
2. **GitHub CLI** - Run `gh auth login` first
3. **SSH** - Configure SSH keys and change remote URL

**If authentication fails**, convert to SSH:
```bash
git remote set-url origin git@github.com:PipFoweraker/pdoom1-website.git
jj git push --bookmark main
```

### Step 3: Monitor Netlify Deployment

Once pushed to GitHub, Netlify automatically deploys:

1. Visit https://app.netlify.com/ and log in
2. Find "pdoom1-website" site
3. Check "Deploys" tab
4. Wait for "Published" status (~1-2 minutes)

**Deployment URL**: https://pdoom1.com/dashboard/

### Step 4: Verify Production Deployment

After Netlify shows "Published":

```bash
# Test production URLs
curl -I https://pdoom1.com/dashboard/
curl -I https://pdoom1.com/assets/pdoom1-office-cat-default.png
curl -I https://pdoom1.com/assets/small-doom-cat.png
```

**Expected**: All return HTTP 200 OK

### Step 5: Browser Testing

Open in browser and verify:
- [ ] Dashboard loads at https://pdoom1.com/dashboard/
- [ ] "Risk Dashboard" link appears in main navigation
- [ ] Resources page features dashboard callout
- [ ] WebGL shader renders (green/orange/red neural mesh)
- [ ] Dual-axis graph displays correctly
- [ ] Sliders update graph in real-time
- [ ] Cat images load and rotate every 5 seconds
- [ ] Expert estimates panel displays
- [ ] Stock tickers show placeholder data
- [ ] All links open correctly (Wikipedia, Yahoo Finance, etc.)
- [ ] No console errors

---

## Rollback Procedure

If critical issues arise after deployment:

```bash
cd /home/laptop/Documents/Projects/ai-sandbox/pdoom1-website

# Undo the dashboard commit
jj undo

# Force push to GitHub
jj git push --bookmark main --force

# Netlify auto-deploys previous version within 1-2 minutes
```

**Alternative**: Use Netlify Dashboard to manually roll back to previous deploy.

---

## Authentication Setup

### Option 1: Personal Access Token (Recommended)

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` (full control of private repositories)
4. Copy token and save securely
5. When pushing, use token as password:
   ```
   Username: PipFoweraker
   Password: <paste token here>
   ```

### Option 2: GitHub CLI

```bash
# Install gh (if not installed)
sudo apt install gh

# Authenticate
gh auth login

# Push using gh
jj git push --bookmark main
```

### Option 3: SSH Keys

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add to GitHub: https://github.com/settings/keys

# Change remote to SSH
git remote set-url origin git@github.com:PipFoweraker/pdoom1-website.git

# Push
jj git push --bookmark main
```

---

## Post-Deployment Checklist

### Immediate (Within 5 minutes)
- [ ] Dashboard accessible at https://pdoom1.com/dashboard/
- [ ] HTTPS/SSL working (no warnings)
- [ ] Navigation link visible on main page
- [ ] Resources page callout displays correctly
- [ ] Cat images load (check Network tab for 200 responses)

### Within 1 Hour
- [ ] Test on multiple browsers (Chrome, Firefox, Safari)
- [ ] Check browser console for JavaScript errors
- [ ] Verify Plotly.js CDN loads correctly
- [ ] Test interactive sliders
- [ ] Verify WebGL shader renders

### Within 24 Hours
- [ ] Monitor Netlify bandwidth (large cat images = 4MB/visit)
- [ ] Check Netlify analytics for traffic
- [ ] Gather initial user feedback
- [ ] Monitor error logs (if any)

### Within 1 Week
- [ ] Review analytics data (most-visited sections, time on page)
- [ ] Collect user feedback on UX/design
- [ ] Identify optimization opportunities
- [ ] Plan next iteration (mobile responsiveness, live data APIs)

---

## Troubleshooting

### Problem: Push fails with authentication error

**Solution**: See "Authentication Setup" section above. Use PAT or SSH.

### Problem: Netlify build fails

**Likely Cause**: Git push didn't complete successfully.

**Solution**:
```bash
# Check GitHub repo
gh repo view PipFoweraker/pdoom1-website

# Verify commit is on GitHub
git log origin/main --oneline -n 5

# If missing, re-push
jj git push --bookmark main
```

### Problem: Dashboard shows 404 after deployment

**Likely Cause**: Netlify serving wrong directory.

**Solution**: Check `netlify.toml` publish directory:
```toml
[build]
  publish = "public"
```

If missing, create file and re-deploy.

### Problem: Cat images don't load (404)

**Likely Cause**: Asset paths incorrect or files not pushed.

**Solution**:
```bash
# Verify files exist in repo
ls -lh public/assets/pdoom1-office-cat-default.png
ls -lh public/assets/small-doom-cat.png

# Check paths in dashboard
grep -n 'src="/assets/' public/dashboard/index.html

# If files missing, re-add and re-push
jj status
jj commit
jj git push --bookmark main
```

### Problem: WebGL shader doesn't render

**Likely Cause**: Browser doesn't support WebGL, or security policy blocks it.

**Solution**: Test in different browser (Chrome recommended). Check browser console for WebGL errors.

**Workaround**: Shader is decorative only; dashboard remains functional without it.

### Problem: Plotly.js graphs don't display

**Likely Cause**: CDN blocked, JavaScript error, or adblocker.

**Solution**:
1. Check browser console for errors
2. Verify CDN accessible: https://cdn.plot.ly/plotly-2.32.0.min.js
3. Disable adblocker and reload
4. Check Netlify logs for errors

---

## Monitoring & Maintenance

### Netlify Dashboard
- **URL**: https://app.netlify.com/
- **Site**: pdoom1-website
- **Tabs to Monitor**:
  - **Deploys**: Build status, deploy logs
  - **Analytics**: Traffic, page views
  - **Bandwidth**: Asset downloads (watch cat images!)
  - **Functions**: Serverless function logs (if any)

### Git/jj Status
```bash
# Check local repo
jj log -r 'main | main@origin' --limit 5

# Verify sync
jj git fetch
jj log -r 'main | main@origin' --limit 1
```

### Bandwidth Considerations

Dashboard assets per visit:
- HTML: 30KB
- Cat image 1: 3.8MB
- Cat image 2: 109KB
- Plotly.js CDN: ~3MB (cached by browser)

**Total first visit**: ~7MB
**Total repeat visit**: ~4MB (Plotly.js cached)

**Netlify Free Tier**: 100GB/month bandwidth
- **Max visits/month**: ~25,000 first-time visitors
- **Recommended**: Optimize cat images to WebP (~2.5MB total)

---

## Next Steps

### Immediate (After Successful Deployment)
1. Announce dashboard on:
   - Dev blog (/blog/)
   - Social media
   - AI Safety communities (LessWrong, EA Forum)
2. Monitor for user feedback
3. Watch Netlify analytics for traffic patterns

### Short-Term (1-2 Weeks)
1. Optimize cat images (PNG → WebP, ~70% size reduction)
2. Add Google Analytics or Plausible for detailed tracking
3. Create social media preview images (og:image)
4. Add "Share" button to dashboard

### Medium-Term (1-2 Months)
1. Integrate live stock data API
2. Add more AI models (Claude, Gemini, Llama)
3. Create mobile-responsive layout
4. Implement accessibility improvements

### Long-Term (3+ Months)
1. Historical P(doom) survey data visualization
2. Citation network graph
3. Scenario analysis tool (slow vs fast takeoff)
4. Risk factor breakdown (misalignment, deception, coordination)
5. Interactive tutorial/walkthrough for new users

---

## Support & Contact

**Repository**: https://github.com/PipFoweraker/pdoom1-website
**Issues**: https://github.com/PipFoweraker/pdoom1-website/issues
**Website**: https://pdoom1.com
**Dashboard**: https://pdoom1.com/dashboard/ (after deployment)

**Integration by**: Claude (Sonnet 4.5)
**Date**: October 30, 2025

---

## Files to Review

1. **DASHBOARD_INTEGRATION_CHANGELOG.md** - Complete list of changes
2. **DASHBOARD_TESTING_REPORT.md** - Test results (11/11 passed)
3. **DASHBOARD_WEBSITE_INTEGRATION_PLAN.md** - Original integration strategy
4. **public/dashboard/index.html** - Dashboard source code

---

## Summary

✅ Dashboard integrated and tested
✅ All documentation created
✅ Changes committed to jj
⏳ **Awaiting authentication to push to GitHub**
⏳ **Netlify will auto-deploy once pushed**

**Action Required**: Authenticate and push to GitHub using one of the methods in "Authentication Setup" section.

---

**Status**: 🟢 Ready for Production
**Last Updated**: October 30, 2025
