# Social Media Syndication - System Architecture

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Content Update                               │
│                                                                       │
│  Developer pushes new blog post or changelog to main branch         │
│  Files: public/blog/*.md, public/*-changelog/*.md                   │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflow                           │
│              (.github/workflows/syndicate-content.yml)               │
│                                                                       │
│  1. Detect changed files (git diff)                                 │
│  2. Extract metadata (title, summary, date)                         │
│  3. Generate URL                                                     │
│  4. Format content for each platform                                │
└────────────────┬───────────┬──────────┬─────────────┬────────────────┘
                 │           │          │             │
        ┌────────┘           │          │             └────────┐
        │                    │          │                      │
        ▼                    ▼          ▼                      ▼
┌──────────────┐    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Bluesky    │    │   Discord    │   │  Twitter/X   │   │   LinkedIn   │
│   Function   │    │   Function   │   │   Function   │   │   Function   │
└──────┬───────┘    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                   │                   │                   │
       │ POST              │ POST              │ POST              │ POST
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Bluesky API │    │   Discord    │   │  Twitter API │   │ LinkedIn API │
│   AT Proto   │    │   Webhook    │   │   v2/OAuth   │   │   UGC API    │
└──────┬───────┘    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                   │                   │                   │
       └───────────────────┴───────────────────┴───────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │   Social Media       │
                        │   Posts Published    │
                        │                      │
                        │  🔗 Link to website  │
                        └──────────────────────┘
```

## Component Architecture

```
pdoom1-website/
│
├── .github/workflows/
│   └── syndicate-content.yml         ← Workflow orchestrator
│
├── netlify/functions/
│   ├── syndicate-bluesky.js          ← Bluesky integration
│   ├── syndicate-discord.js          ← Discord integration
│   ├── syndicate-x.js                ← Twitter/X integration
│   └── syndicate-linkedin.js         ← LinkedIn integration
│
├── scripts/
│   ├── syndication-helpers.js        ← Shared utilities
│   └── test-syndication.js           ← Test suite
│
├── docs/
│   ├── SYNDICATION_SETUP.md          ← Setup guide
│   ├── SYNDICATION_QUICKSTART.md     ← Quick reference
│   └── SYNDICATION_SUMMARY.md        ← Implementation summary
│
└── .env.example                       ← Environment variables
```

## Data Flow

### 1. Content Detection
```javascript
// Workflow detects changed markdown files
Changed Files: public/blog/2025-10-09-new-post.md

// Extracts metadata
Title: "Amazing New Feature"
Date: "2025-10-09"
Summary: "We've implemented an amazing new feature..."
Tags: ["feature", "update"]
```

### 2. URL Generation
```javascript
Filename: "2025-10-09-new-post.md"
      ↓
Generated URL: "https://pdoom1.com/blog/#new-post"
```

### 3. Platform-Specific Formatting

#### Bluesky (300 chars)
```
🎮 Amazing New Feature

We've implemented an amazing new feature...

🔗 https://pdoom1.com/blog/#new-post
```

#### Twitter (280 chars)
```
🎮 Amazing New Feature

We've implemented an amazing new feature...

https://pdoom1.com/blog/#new-post
```

#### LinkedIn (flexible)
```
Amazing New Feature

We've implemented an amazing new feature...

Read more: https://pdoom1.com/blog/#new-post

#feature #update
```

#### Discord (embed)
```json
{
  "embeds": [{
    "title": "Amazing New Feature",
    "description": "We've implemented...",
    "url": "https://pdoom1.com/blog/#new-post",
    "color": 65280,
    "timestamp": "2025-10-09T..."
  }]
}
```

### 4. API Calls

Each function makes platform-specific API calls:

```
Bluesky:  createSession → createRecord (post)
Discord:  POST to webhook URL
Twitter:  OAuth signature → POST /2/tweets
LinkedIn: POST /v2/ugcPosts with Bearer token
```

## Authentication Flow

### Bluesky (AT Protocol)
```
1. Create session with handle + app password
2. Receive accessJwt and DID
3. Create post record with accessJwt
```

### Discord (Webhook)
```
1. POST to webhook URL (no auth needed)
2. Discord validates webhook URL authenticity
```

### Twitter/X (OAuth 1.0a)
```
1. Generate OAuth parameters (nonce, timestamp)
2. Create signature base string
3. Sign with HMAC-SHA1 (API secret + access secret)
4. Add signature to Authorization header
5. POST to API endpoint
```

### LinkedIn (OAuth 2.0)
```
1. Use pre-generated Bearer token
2. Add to Authorization header
3. POST to UGC API with organization URN
```

## Error Handling

```
For each platform:
  Try:
    - Call Netlify function
    - Parse response
    - Log success
  Catch:
    - Log error
    - Continue to next platform
    
Result: Best-effort delivery (don't fail all if one fails)
```

## Configuration

### Required Secrets

```
GitHub Repository Secrets & Netlify Environment Variables:

NETLIFY_SITE_URL=https://pdoom1.netlify.app

# Bluesky
BLUESKY_HANDLE=pdoom1.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Twitter/X
TWITTER_API_KEY=xxxxxxxxxx
TWITTER_API_SECRET=xxxxxxxxxx
TWITTER_ACCESS_TOKEN=xxxxxxxxxx
TWITTER_ACCESS_SECRET=xxxxxxxxxx

# LinkedIn
LINKEDIN_ACCESS_TOKEN=xxxxxxxxxx
LINKEDIN_ORG_ID=108743037
```

## Testing Flow

### Unit Tests
```bash
npm run test:syndication

Tests:
  ✅ extractBlogMetadata()
  ✅ generateBlogUrl()
  ✅ formatPostContent() for all platforms
  ✅ Character limit validation
```

### Dry Run (Manual)
```
GitHub Actions → Content Syndication → Run workflow

Inputs:
  - content_path: path/to/file.md
  - dry_run: true
  
Output:
  - Shows formatted content
  - No actual posting
```

### Live Test
```
1. Create/update blog post
2. Push to main
3. Workflow triggers automatically
4. Check each platform for post
```

## Monitoring

### GitHub Actions Logs
```
- Workflow execution history
- Success/failure per platform
- Error messages
- Formatted content preview
```

### Platform Verification
```
- Bluesky: Check @pdoom1 profile
- Discord: Check alpha channel
- Twitter: Check timeline
- LinkedIn: Check company page
```

## Cost Analysis

### Netlify Function Invocations
```
Per syndication event: 4 function calls
  - syndicate-bluesky
  - syndicate-discord
  - syndicate-x
  - syndicate-linkedin

Frequency: Only on blog/changelog updates (infrequent)
Estimate: ~10-20 invocations per month
```

## Maintenance

### Regular Tasks
- [ ] Monitor Netlify function logs
- [ ] Check platform posts for formatting
- [ ] Refresh LinkedIn token (expires periodically)
- [ ] Review error rates

### As Needed
- [ ] Update character limits if platforms change
- [ ] Add new platforms
- [ ] Adjust content formatting
- [ ] Add image support

## Future Enhancements

1. **Retry Logic**: Automatic retry on failure
2. **Queueing**: Batch posts to save credits
3. **Scheduling**: Delay posts for optimal engagement
4. **Images**: Attach featured images
5. **Analytics**: Track clicks and engagement
6. **Selective Posting**: Choose platforms per post
7. **Templates**: Custom message templates

## Summary

This architecture provides:
- ✅ Automated content syndication
- ✅ Platform-agnostic design
- ✅ Error resilience
- ✅ Easy testing
- ✅ Comprehensive documentation
- ✅ Security best practices
- ✅ Cost efficiency
