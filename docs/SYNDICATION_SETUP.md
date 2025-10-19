# Social Media Syndication Setup Guide

This document describes how the automated social media syndication system works for the p(Doom)1 website.

## Overview

The syndication system automatically posts blog and changelog updates to:
- **Bluesky** (@pdoom1)
- **Discord** (alpha channel)
- **Twitter/X**
- **LinkedIn** (company page: https://www.linkedin.com/company/108743037)

## How It Works

### Trigger
The syndication workflow is triggered when:
1. A new blog post or changelog is pushed to the `main` branch
2. Paths monitored:
   - `public/blog/**/*.md`
   - `public/changelog/**/*.md`
   - `public/game-changelog/**/*.md`
   - `public/website-changelog/**/*.md`
3. Manual trigger via GitHub Actions UI (for testing)

### Content Processing
1. The workflow detects changed markdown files
2. Extracts metadata (title, summary, date) from the markdown
3. Generates appropriate URL for the content
4. Formats messages for each platform
5. Posts concurrently to all platforms

## Platform Configuration

### Bluesky

**API**: AT Protocol (https://bsky.social)
**Authentication**: App Password

**Required Secrets**:
- `BLUESKY_HANDLE`: Your Bluesky handle (e.g., "pdoom1.bsky.social" or "pdoom1")
- `BLUESKY_APP_PASSWORD`: App-specific password generated from Bluesky settings

**Setup Steps**:
1. Log into Bluesky
2. Go to Settings → App Passwords
3. Create a new app password named "pdoom1-website-syndication"
4. Add to GitHub Secrets

**Character Limit**: 300 characters

### Discord

**API**: Webhook
**Authentication**: Webhook URL

**Required Secrets**:
- `DISCORD_WEBHOOK_URL`: Full webhook URL for the alpha channel

**Setup Steps**:
1. Go to Discord server settings
2. Navigate to Integrations → Webhooks
3. Create webhook for alpha channel
4. Name it "p(Doom)1 Updates"
5. Copy webhook URL
6. Add to GitHub Secrets

**Format**: Rich embeds with title, description, and link

### Twitter/X

**API**: Twitter API v2
**Authentication**: OAuth 1.0a

**Required Secrets**:
- `TWITTER_API_KEY`: API Key (Consumer Key)
- `TWITTER_API_SECRET`: API Secret (Consumer Secret)
- `TWITTER_ACCESS_TOKEN`: Access Token
- `TWITTER_ACCESS_SECRET`: Access Token Secret

**Setup Steps**:
1. Go to https://developer.twitter.com/
2. Create a new app or use existing
3. Enable OAuth 1.0a authentication
4. Request "Read and Write" permissions
5. Generate access tokens
6. Add all credentials to GitHub Secrets

**Character Limit**: 280 characters

**Alternative**: Consider using Zapier or IFTTT as mentioned in the issue for easier setup

### LinkedIn

**API**: UGC Post API (User Generated Content)
**Authentication**: OAuth 2.0 Access Token

**Required Secrets**:
- `LINKEDIN_ACCESS_TOKEN`: OAuth 2.0 access token with `w_member_social` scope
- `LINKEDIN_ORG_ID`: Organization ID (108743037) or URN (urn:li:organization:108743037)

**Setup Steps**:
1. Go to https://www.linkedin.com/developers/
2. Create a new app or use existing
3. Request access to "Share on LinkedIn" product
4. Add company page (108743037) to the app
5. Generate access token with `w_organization_social` scope
6. Add credentials to GitHub Secrets

**Note**: LinkedIn access tokens expire. You may need to refresh periodically.

**Character Limit**: ~3000 characters (we use ~500 for formatting)

## GitHub Secrets Configuration

Add the following secrets to your GitHub repository:
1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add each secret listed above

**Additional Secret**:
- `NETLIFY_SITE_URL`: Your Netlify site URL (e.g., "https://pdoom1.netlify.app")

## Netlify Functions

The syndication functions are deployed as Netlify Functions:

### Function Endpoints
- `/.netlify/functions/syndicate-bluesky`
- `/.netlify/functions/syndicate-discord`
- `/.netlify/functions/syndicate-x`
- `/.netlify/functions/syndicate-linkedin`

### Function Environment Variables
Configure these in Netlify site settings (not GitHub):
- All platform credentials listed above
- These should match the GitHub secrets for consistency

## Testing

### Manual Trigger
1. Go to Actions → Content Syndication workflow
2. Click "Run workflow"
3. Enter path to content file
4. Check "Dry run" to test without posting
5. Click "Run workflow"

### Dry Run Mode
When enabled, the workflow:
- Extracts content metadata
- Formats messages for each platform
- Shows what would be posted
- Does NOT actually post to any platform

### Test Content
Use an existing blog post for testing:
```
public/blog/2025-10-09-website-development-sprint-complete-v0-2-0.md
```

## Content Formatting

### Bluesky Format
```
🎮 [Title]

[Summary (truncated to fit)]

🔗 [URL]
```

### Twitter Format
```
🎮 [Title]

[Summary (truncated to fit)]

[URL]
```

### LinkedIn Format
```
[Title]

[Summary]

Read more: [URL]

#gamedev #indiegame #python
```

### Discord Format
Rich embed with:
- Title (linked)
- Description (summary)
- Tags as fields
- Timestamp
- p(Doom)1 branding

## Rate Limiting

Each platform has its own rate limits:
- **Bluesky**: ~100 posts/hour (generous)
- **Discord**: 30 requests/minute per webhook
- **Twitter**: 300 tweets/3 hours for user context
- **LinkedIn**: Varies by app/user

The current implementation does not include retry logic or rate limit handling. If needed, these can be added to the Netlify functions.

## Error Handling

The workflow continues even if individual platforms fail:
- Each platform step is independent
- Failures are logged but don't stop the workflow
- Check GitHub Actions logs for details

## Monitoring

Monitor syndication results:
1. Check GitHub Actions workflow runs
2. Verify posts appear on each platform
3. Check Netlify function logs for errors
4. Monitor Discord channel for notifications

## Troubleshooting

### "Credentials not configured" error
- Verify secrets are set in both GitHub and Netlify
- Check secret names match exactly
- Ensure NETLIFY_SITE_URL is correct

### Posts not appearing
- Check platform API credentials are valid
- Verify access tokens haven't expired (especially LinkedIn)
- Check rate limits haven't been exceeded
- Review Netlify function logs

### LinkedIn token expired
LinkedIn tokens expire regularly:
1. Generate new access token
2. Update `LINKEDIN_ACCESS_TOKEN` in GitHub and Netlify
3. Rerun failed workflow

### Twitter OAuth errors
- Verify app has "Read and Write" permissions
- Confirm access tokens were generated after permission change
- Check API v2 access is enabled

## Future Enhancements

Potential improvements:
1. **Retry Logic**: Automatically retry failed posts
2. **Rate Limit Handling**: Queue posts if rate limited
3. **Token Refresh**: Automatic token refresh for LinkedIn
4. **Image Support**: Include featured images in posts
5. **Scheduling**: Delay syndication to optimize engagement
6. **Analytics**: Track clicks and engagement
7. **Platform Selection**: Choose which platforms to post to
8. **Zapier Integration**: Alternative approach for Twitter as mentioned in issue

## Cost Considerations

As mentioned in the issue, Netlify credits are limited on personal plan:
- Each function invocation uses credits
- Monitor usage in Netlify dashboard
- Consider batch syndication (post to all platforms at once)
- Current implementation: 4 function calls per syndication event

## Support

For issues or questions:
- Check GitHub Actions logs first
- Review Netlify function logs
- Verify API credentials and permissions
- Test with dry run mode before live posting

## References

- [Bluesky AT Protocol Docs](https://atproto.com/)
- [Discord Webhook Guide](https://discord.com/developers/docs/resources/webhook)
- [Twitter API v2 Docs](https://developer.twitter.com/en/docs/twitter-api)
- [LinkedIn UGC Post API](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/ugc-post-api)
