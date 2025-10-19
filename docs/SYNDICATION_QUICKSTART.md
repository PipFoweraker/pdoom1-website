# Social Media Syndication - Quick Setup

## Required GitHub Secrets

Configure these in: Settings → Secrets and variables → Actions → New repository secret

### Essential Secrets
```
NETLIFY_SITE_URL=https://pdoom1.netlify.app
```

### Bluesky
```
BLUESKY_HANDLE=pdoom1.bsky.social
BLUESKY_APP_PASSWORD=<generate from Bluesky settings>
```

### Discord
```
DISCORD_WEBHOOK_URL=<webhook URL for alpha channel>
```

### Twitter/X
```
TWITTER_API_KEY=<from developer.twitter.com>
TWITTER_API_SECRET=<from developer.twitter.com>
TWITTER_ACCESS_TOKEN=<from developer.twitter.com>
TWITTER_ACCESS_SECRET=<from developer.twitter.com>
```

### LinkedIn
```
LINKEDIN_ACCESS_TOKEN=<OAuth 2.0 token with w_organization_social>
LINKEDIN_ORG_ID=108743037
```

## Netlify Environment Variables

Also configure these in Netlify site settings (Environment variables section).
They should match the GitHub secrets above.

## Testing

1. Go to Actions → Content Syndication
2. Click "Run workflow"
3. Enter path: `public/blog/2025-10-09-website-development-sprint-complete-v0-2-0.md`
4. Check "Dry run" checkbox
5. Click "Run workflow"

This will show what would be posted without actually posting.

## Full Documentation

See [docs/SYNDICATION_SETUP.md](SYNDICATION_SETUP.md) for complete setup instructions.
