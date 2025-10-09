# Analytics Setup Guide

This guide explains how to set up and configure the privacy-preserving analytics for the p(Doom)1 website.

## Quick Overview

The website now includes **Plausible Analytics** integration, which is:
- ✅ Privacy-first (no cookies, no personal data)
- ✅ GDPR compliant by default
- ✅ Lightweight (<1KB script)
- ✅ Can be self-hosted or cloud-hosted

## Configuration Options

### Option 1: Cloud Hosting (Easiest)

1. **Sign up for Plausible**
   - Go to https://plausible.io/register
   - Choose your plan (free trial available)

2. **Add your domain**
   - In Plausible dashboard: Settings → Add Website
   - Enter `pdoom1.com`
   - Copy your tracking code

3. **Verify Integration**
   - The script is already integrated into the website
   - Visit https://pdoom1.com after deployment
   - Check Plausible dashboard for visitor data

**Cost**: Starting at $9/month for 10k pageviews

### Option 2: Self-Hosting (Full Control)

1. **Deploy Plausible**
   ```bash
   # Clone Plausible hosting repository
   git clone https://github.com/plausible/hosting
   cd hosting
   
   # Configure environment
   cp plausible-conf.env.example plausible-conf.env
   # Edit plausible-conf.env with your settings
   
   # Start with Docker
   docker-compose up -d
   ```

2. **Update Configuration**
   Edit `/public/assets/js/analytics.js`:
   ```javascript
   const ANALYTICS_CONFIG = {
     enabled: true,
     dataDomain: 'pdoom1.com',
     scriptUrl: 'https://your-plausible-domain.com/js/script.js', // Update this
     optOutKey: 'pdoom1_analytics_optout'
   };
   ```

3. **Deploy Changes**
   - Commit the configuration change
   - Push to your hosting platform (Netlify/Vercel)

**Cost**: Free (hosting costs only)

### Option 3: Alternative Providers

#### Umami Analytics
- Self-hosted, similar to Plausible
- Setup: https://umami.is/docs/install
- Update `scriptUrl` in analytics.js

#### Simple Analytics
- Privacy-focused, carbon-conscious
- Setup: https://www.simpleanalytics.com/
- Update `scriptUrl` in analytics.js

## Testing the Integration

### 1. Test Locally
```bash
# Start local server
npm start

# Visit http://localhost:5173
# Open browser console, look for:
# "[Analytics] Privacy-preserving analytics initialized"
```

### 2. Test Opt-Out
- Visit http://localhost:5173/privacy/
- Click "Opt Out of Analytics"
- Refresh page, check console for:
  `[Analytics] User has opted out - analytics disabled`

### 3. Test Production
After deployment:
- Visit https://pdoom1.com
- Check Plausible dashboard for real-time visitors
- Test opt-out on production site

## Privacy Features

### Automatic Privacy Protections
- ✅ No cookies used
- ✅ IP addresses anonymized immediately
- ✅ Do Not Track respected
- ✅ Easy opt-out mechanism
- ✅ Data deleted after 90 days

### User Controls
Users can opt out at any time:
1. Visit `/privacy/` page
2. Click "Opt Out of Analytics"
3. Or enable "Do Not Track" in browser

## File Structure

```
public/
├── assets/
│   └── js/
│       └── analytics.js          # Main analytics script
├── privacy/
│   └── index.html                 # Privacy policy & opt-out page
├── analytics-config.json          # Configuration file
└── index.html, about/, press/     # Pages with analytics integrated
```

## Maintenance

### Regular Tasks
- [ ] Monitor analytics dashboard weekly
- [ ] Review privacy policy quarterly
- [ ] Check for Plausible updates monthly
- [ ] Verify opt-out functionality works

### Troubleshooting

**Analytics not loading?**
1. Check browser console for errors
2. Verify domain in Plausible dashboard
3. Check ad blocker isn't blocking script
4. Test scriptUrl is accessible

**High opt-out rate?**
1. Review privacy messaging
2. Check if opt-out is too prominent
3. Survey users about concerns

## Monitoring & Insights

### Plausible Dashboard
Access at: https://plausible.io/pdoom1.com

**Key Metrics:**
- Real-time visitors
- Page views & unique visitors
- Top pages and referrers
- Browser, OS, device breakdown
- Geographic data (country-level)

### Custom Events
The analytics script tracks:
- Download clicks (press page)
- External link clicks (about page)

Add more custom events in HTML:
```javascript
window.pdoom1Analytics.trackEvent('Event Name', { 
  property: 'value' 
});
```

## Next Steps

1. ✅ Analytics integration complete
2. ⏳ Choose hosting option (cloud or self-hosted)
3. ⏳ Configure Plausible account
4. ⏳ Verify integration in production
5. ⏳ Monitor analytics for 1 week
6. ⏳ Review and adjust as needed

## Support & Resources

- **Plausible Docs**: https://plausible.io/docs
- **Self-Hosting Guide**: https://plausible.io/docs/self-hosting
- **Privacy Policy Template**: https://plausible.io/privacy
- **GitHub Issues**: https://github.com/PipFoweraker/pdoom1-website/issues

## Questions?

If you have questions about the analytics setup:
1. Review the documentation in `/docs/ANALYTICS_IMPLEMENTATION.md`
2. Check Plausible's documentation
3. Open an issue on GitHub

---

**Implementation Date**: 2025-01-XX
**Version**: 1.0.0
**Maintainer**: p(Doom)1 Team
