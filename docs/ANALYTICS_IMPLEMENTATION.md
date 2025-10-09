# Privacy-Preserving Analytics Implementation

## Overview

This document describes the privacy-preserving analytics implementation for the p(Doom)1 website. We use **Plausible Analytics**, a privacy-first, cookie-free analytics solution that is GDPR-compliant by design.

## Features

### Privacy-First Design
- **No Cookies**: No cookies or persistent identifiers are used
- **No Personal Data**: No personally identifiable information is collected
- **GDPR Compliant**: Fully compliant with privacy regulations by default
- **Respects Do Not Track**: Honors browser DNT settings
- **Easy Opt-Out**: Users can opt out with a single click

### What We Collect
- **Page views**: Anonymous aggregate page visit counts
- **Referrers**: Where visitors come from (search engines, social media)
- **Browser & OS**: General browser and operating system information
- **Device type**: Desktop, mobile, or tablet classification

### What We DON'T Collect
- ❌ IP addresses (anonymized immediately)
- ❌ Cookies or local storage (except opt-out preference)
- ❌ Personal information (names, emails, etc.)
- ❌ Cross-site tracking data
- ❌ Device fingerprinting data

## Implementation

### Files Created

1. **`/public/assets/js/analytics.js`**
   - Main analytics integration script
   - Handles initialization, opt-out, and event tracking
   - Respects DNT and user preferences

2. **`/public/analytics-config.json`**
   - Configuration file for analytics settings
   - Includes provider information and privacy features

3. **`/public/privacy/index.html`**
   - Privacy policy and analytics information page
   - Interactive opt-out/opt-in controls
   - Detailed explanation of data collection practices

### Integration Points

Analytics are integrated into the following pages:
- `/public/index.html` - Main landing page
- `/public/about/index.html` - About page with external link tracking
- `/public/press/index.html` - Press page with download tracking

Each page includes:
```html
<!-- Privacy-preserving analytics -->
<script src="/assets/js/analytics.js"></script>
```

## Analytics Provider

### Plausible Analytics

We chose Plausible Analytics for the following reasons:
- **Open Source**: Fully auditable and transparent
- **Lightweight**: < 1KB script size, minimal performance impact
- **Privacy-First**: No cookies, no personal data collection
- **GDPR Compliant**: Designed for privacy regulations
- **Self-Hostable**: Can be self-hosted for complete data ownership

### Alternative Providers Considered

- **Umami**: Self-hosted, similar privacy features
- **Simple Analytics**: Privacy-focused with carbon-conscious hosting

All three options are privacy-preserving and GDPR-compliant. Plausible was selected for its simplicity and excellent documentation.

## Configuration

### Cloud Hosting (Default)

The default configuration uses Plausible's cloud service:

```javascript
{
  "provider": "plausible",
  "enabled": true,
  "dataDomain": "pdoom1.com",
  "scriptUrl": "https://plausible.io/js/script.js"
}
```

### Self-Hosting Option

To self-host Plausible Analytics:

1. Follow [Plausible self-hosting guide](https://plausible.io/docs/self-hosting)
2. Update `analytics-config.json`:
   ```json
   {
     "scriptUrl": "https://your-domain.com/js/script.js"
   }
   ```
3. Update `ANALYTICS_CONFIG.scriptUrl` in `/public/assets/js/analytics.js`

## User Controls

### Opt-Out Mechanism

Users can opt out of analytics in three ways:

1. **Privacy Page**: Visit `/privacy/` and click "Opt Out of Analytics"
2. **Browser DNT**: Enable Do Not Track in browser settings
3. **JavaScript Console**: Execute `window.pdoom1Analytics.optOut()`

Opt-out preference is stored in `localStorage` and persists across visits.

### Opt-In

Users who have opted out can opt back in:

1. **Privacy Page**: Visit `/privacy/` and click "Opt Back In"
2. **JavaScript Console**: Execute `window.pdoom1Analytics.optIn()`

## Custom Event Tracking

The analytics script provides a simple API for tracking custom events:

```javascript
// Track a custom event
window.pdoom1Analytics.trackEvent('Event Name', { 
  property: 'value' 
});

// Example: Track download clicks
window.pdoom1Analytics.trackEvent('Download', { 
  item: 'Press Kit' 
});

// Example: Track external link clicks
window.pdoom1Analytics.trackEvent('External Link', { 
  url: 'https://github.com/...' 
});
```

Events are only tracked if:
- Analytics is enabled
- User has not opted out
- Do Not Track is not enabled

## Data Retention

- **Analytics data**: Automatically deleted after 90 days
- **Opt-out preference**: Stored indefinitely in browser localStorage
- **No long-term tracking**: No user profiles or historical data

## Compliance

### GDPR Compliance

- ✅ Data minimization: Only essential data collected
- ✅ Pseudonymization: No identifiable information
- ✅ Opt-in/Opt-out: User control over data collection
- ✅ Right to erasure: Opt-out removes all tracking
- ✅ Transparency: Clear privacy policy and documentation

### Legal Basis

The legal basis for analytics data processing is:
- **Legitimate Interest**: Understanding website usage for improvement
- **Consent**: Users can opt out at any time
- **Privacy by Design**: Minimal data collection by default

## Testing

### Manual Testing

1. **Verify Analytics Loading**:
   ```
   Open browser console → Check for "[Analytics] Privacy-preserving analytics initialized"
   ```

2. **Test Opt-Out**:
   ```
   Visit /privacy/ → Click "Opt Out" → Verify status changes
   ```

3. **Test DNT Respect**:
   ```
   Enable DNT in browser → Reload page → Check console for DNT message
   ```

4. **Test Custom Events**:
   ```javascript
   window.pdoom1Analytics.trackEvent('Test Event', { test: true });
   ```

### Automated Testing

Add to test suite:

```javascript
// Test analytics initialization
test('Analytics script loads without errors', async () => {
  // Test implementation
});

// Test opt-out functionality
test('Opt-out persists in localStorage', async () => {
  // Test implementation
});

// Test DNT respect
test('Analytics disabled when DNT enabled', async () => {
  // Test implementation
});
```

## Monitoring

### Analytics Dashboard

Access the Plausible dashboard at:
- Cloud: `https://plausible.io/pdoom1.com`
- Self-hosted: `https://your-domain.com/pdoom1.com`

Dashboard shows:
- Real-time visitor count
- Page views and unique visitors
- Top pages and referrers
- Browser, OS, and device breakdown
- Geographic location (country-level only)

### Privacy Dashboard

The `/privacy/` page provides users with:
- Current analytics status
- Opt-out/opt-in controls
- Detailed privacy information
- Analytics provider information

## Deployment

### Production Checklist

- [x] Analytics script created and tested
- [x] Privacy page created with opt-out controls
- [x] Analytics integrated into main pages
- [x] Sitemap updated with privacy page
- [x] Configuration files updated
- [ ] Plausible account configured (cloud or self-hosted)
- [ ] Domain verified in Plausible dashboard
- [ ] Test analytics in production environment

### Netlify Deployment

No special configuration needed for Netlify. The static files will be served automatically.

### Self-Hosting Plausible

If self-hosting Plausible:

1. Deploy Plausible instance (Docker recommended)
2. Update `scriptUrl` in analytics configuration
3. Configure CORS headers if needed
4. Test analytics loading from production domain

## Troubleshooting

### Analytics Not Loading

1. Check browser console for errors
2. Verify script URL is accessible
3. Check if ad blockers are interfering
4. Verify domain configuration in Plausible

### Opt-Out Not Working

1. Check if localStorage is enabled
2. Verify browser allows local storage
3. Check browser console for errors

### Custom Events Not Tracking

1. Verify Plausible script has loaded (`typeof window.plausible !== 'undefined'`)
2. Check if user has opted out
3. Verify event name and properties format

## Future Improvements

- [ ] Add more custom event tracking (form submissions, video plays)
- [ ] Implement server-side analytics for better ad-blocker resilience
- [ ] Add analytics dashboard integration in admin panel
- [ ] Create automated privacy reports
- [ ] Add A/B testing capabilities (privacy-preserving)

## Resources

- [Plausible Documentation](https://plausible.io/docs)
- [Plausible Self-Hosting Guide](https://plausible.io/docs/self-hosting)
- [GDPR Compliance Guide](https://plausible.io/data-policy)
- [Privacy Policy Template](https://plausible.io/privacy)

## Contact

For questions about analytics implementation:
- GitHub Issues: https://github.com/PipFoweraker/pdoom1-website/issues
- Documentation: `/docs/`

---

**Last Updated**: 2025-01-XX
**Version**: 1.0.0
**Maintainer**: p(Doom)1 Team
