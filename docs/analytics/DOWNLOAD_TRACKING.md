# Download Tracking with Plausible Analytics

This document explains how game download tracking is implemented on pdoom1.com using Plausible Analytics custom events.

## Implementation

### Download Buttons

Each download button has a unique ID for tracking:

```html
<a id="download-windows" href="...">Download for Windows</a>
<a id="download-macos" href="...">Download for macOS</a>
<a id="download-linux" href="...">Download for Linux</a>
```

### Tracking Code

When a user clicks a download button, a custom event is sent to Plausible:

```javascript
plausible('Download', {
    props: {
        version: 'v0.10.2',    // Current game version
        platform: 'Windows',    // OS platform
        file: 'PDoom.exe'       // Specific file downloaded
    }
});
```

### Event Properties

Each download event includes:
- **version**: Game version (e.g., `v0.10.2`)
- **platform**: Operating system (`Windows`, `macOS`, `Linux`)
- **file**: Specific filename being downloaded

## Setting Up Custom Event Goals in Plausible

To view download statistics in your Plausible dashboard:

1. **Log in to Plausible Analytics**:
   - Visit: https://analytics.pdoom1.com
   - Navigate to your site (pdoom1.com)

2. **Add Custom Event Goal**:
   - Click **Settings** → **Goals**
   - Click **+ Add Goal**
   - Choose **Custom Event**
   - Enter event name: `Download`
   - Click **Add Goal**

3. **View Download Statistics**:
   - Go back to your main dashboard
   - The "Download" event will now appear in the **Goal Conversions** section
   - Click on "Download" to see breakdown by properties (version, platform, file)

## Viewing Download Data

### Dashboard View

Once the goal is configured, you'll see:
- **Total downloads**: Overall count
- **Downloads by platform**: Windows vs macOS vs Linux breakdown
- **Downloads by version**: Which versions are most popular
- **Download trends**: Downloads over time

### Example Queries

In the Plausible dashboard, you can filter by:
- **Platform**: Show only Windows downloads
- **Version**: Show downloads for specific versions
- **Date range**: Downloads in last 7 days, 30 days, etc.

### API Access (Optional)

You can also query download data via Plausible's Stats API:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://analytics.pdoom1.com/api/v1/stats/breakdown?site_id=pdoom1.com&period=30d&property=event:goal&filters=event:goal==Download"
```

## Testing Download Tracking

### Manual Testing

1. **Open browser console** (F12)
2. **Visit** https://pdoom1.com
3. **Click a download button**
4. **Check console** for: `Download tracked: Windows v0.10.2`
5. **Check Plausible dashboard** for real-time event (may take 1-2 seconds)

### Verification Script

```javascript
// Test if Plausible is loaded
console.log('Plausible loaded:', typeof plausible !== 'undefined');

// Manually trigger a test event
if (window.plausible) {
    plausible('Download', {
        props: {
            version: 'test',
            platform: 'Test',
            file: 'test.exe'
        }
    });
    console.log('Test event sent');
}
```

## Privacy Considerations

- Download tracking is **anonymous** - no user identification
- Only tracks: version, platform, file name
- No personal data collected
- Respects "Do Not Track" browser settings
- GDPR compliant

## Data Retention

- Plausible stores analytics data indefinitely by default
- Self-hosted instance: Configure retention in `/opt/plausible/plausible-conf.env`
- Recommended: Keep at least 2 years for trend analysis

## Common Queries

### Most Downloaded Platform

Filter by "platform" property to see Windows vs macOS vs Linux distribution.

### Version Adoption Rate

Filter by "version" property to see how quickly users adopt new versions.

### Download Conversion Rate

Compare page views to download events to calculate conversion rate:
- **Page Views**: Total visits to homepage
- **Downloads**: Total download events
- **Conversion Rate**: (Downloads / Page Views) × 100%

## Troubleshooting

### Downloads Not Appearing in Dashboard

1. **Check if custom event goal exists**:
   - Settings → Goals → Look for "Download"
   - If missing, add it (see "Setting Up Custom Event Goals" above)

2. **Check browser console**:
   - Should see: `Download tracked: [Platform] [Version]`
   - If missing, check if Plausible script loaded

3. **Check Plausible script**:
   ```html
   <!-- Should be in <head> -->
   <script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>
   ```

4. **Verify button IDs**:
   - Inspect download buttons
   - Confirm IDs: `download-windows`, `download-macos`, `download-linux`

### Console Errors

**Error**: `plausible is not defined`
- **Cause**: Plausible script not loaded or blocked by ad blocker
- **Fix**: Check network tab, whitelist analytics.pdoom1.com

**Error**: `Cannot read property 'addEventListener' of null`
- **Cause**: Button ID not found
- **Fix**: Verify button IDs match in HTML and JavaScript

## Future Enhancements

Potential improvements for download tracking:

1. **Track download completion** (requires server-side logging)
2. **A/B test download button text** (measure conversion rates)
3. **Track "View on GitHub" clicks** as separate event
4. **Geo-location data** (requires MaxMind GeoLite2 database)
5. **Referrer tracking** (where downloads came from)

## Related Documentation

- [HTML Page Template](../HTML_PAGE_TEMPLATE.md) - Standard page structure
- [Self-Hosted Plausible Setup](SELF_HOSTED_PLAUSIBLE.md) - Analytics server setup
- [Plausible Custom Events](https://plausible.io/docs/custom-event-goals) - Official documentation

---

**Last Updated**: 2025-11-10
**Author**: Development Team
**Status**: Active
