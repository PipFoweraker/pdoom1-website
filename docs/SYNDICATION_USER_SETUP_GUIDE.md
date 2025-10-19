# Social Media Syndication - Complete User Setup Guide

This guide provides step-by-step instructions with exact terminal commands and scripts to complete the syndication setup.

## Prerequisites

- Access to GitHub repository settings
- Access to Netlify dashboard
- Git bash or terminal with git installed
- GitHub CLI (`gh`) installed (optional but recommended)

---

## Part 1: GitHub Repository Secrets Configuration

### Method 1: Using GitHub CLI (Recommended)

#### Step 1.1: Install GitHub CLI (if not already installed)

**Windows (Git Bash):**
```bash
# Download and install from https://cli.github.com/
# Or use winget:
winget install --id GitHub.cli
```

**macOS:**
```bash
brew install gh
```

**Linux:**
```bash
# Debian/Ubuntu
sudo apt install gh

# Fedora/RHEL
sudo dnf install gh
```

#### Step 1.2: Authenticate with GitHub

```bash
# Login to GitHub CLI
gh auth login

# Follow the prompts:
# - Choose: GitHub.com
# - Choose: HTTPS
# - Authenticate with your preferred method
```

#### Step 1.3: Navigate to Repository

```bash
# Clone if you haven't already
git clone https://github.com/PipFoweraker/pdoom1-website.git
cd pdoom1-website

# Or navigate to existing clone
cd /path/to/pdoom1-website
```

#### Step 1.4: Set GitHub Secrets

Create a script to set all secrets at once:

```bash
# Create a script file
cat > setup-github-secrets.sh << 'EOF'
#!/bin/bash

# GitHub Secrets Setup Script for Social Media Syndication
# This script will prompt for each secret and set it in GitHub repository

set -e  # Exit on error

REPO="PipFoweraker/pdoom1-website"

echo "========================================="
echo "GitHub Secrets Setup for Syndication"
echo "========================================="
echo ""
echo "This script will configure all required secrets for social media syndication."
echo "You will be prompted to enter each secret value."
echo ""
echo "Repository: $REPO"
echo ""

# Function to set a secret with validation
set_secret() {
    local secret_name=$1
    local secret_description=$2
    local is_optional=$3
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Setting: $secret_name"
    echo "Description: $secret_description"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ "$is_optional" = "optional" ]; then
        echo "(Optional - press Enter to skip)"
    fi
    
    read -sp "Enter value for $secret_name: " secret_value
    echo ""
    
    if [ -z "$secret_value" ]; then
        if [ "$is_optional" = "optional" ]; then
            echo "⏭️  Skipped $secret_name (optional)"
            return 0
        else
            echo "❌ Error: $secret_name is required"
            return 1
        fi
    fi
    
    # Set the secret
    echo "$secret_value" | gh secret set "$secret_name" -R "$REPO"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully set $secret_name"
    else
        echo "❌ Failed to set $secret_name"
        return 1
    fi
}

echo "Starting secret configuration..."
echo ""

# Essential - Netlify
set_secret "NETLIFY_SITE_URL" "Your Netlify site URL (e.g., https://pdoom1.netlify.app)" "required"

# Bluesky
echo ""
echo "═══════════════════════════════════════════════════"
echo "BLUESKY CONFIGURATION"
echo "═══════════════════════════════════════════════════"
set_secret "BLUESKY_HANDLE" "Your Bluesky handle (e.g., pdoom1.bsky.social or pdoom1)" "optional"
set_secret "BLUESKY_APP_PASSWORD" "Bluesky app password (generate at Settings > App Passwords)" "optional"

# Discord
echo ""
echo "═══════════════════════════════════════════════════"
echo "DISCORD CONFIGURATION"
echo "═══════════════════════════════════════════════════"
set_secret "DISCORD_WEBHOOK_URL" "Discord webhook URL for alpha channel" "optional"

# Twitter/X
echo ""
echo "═══════════════════════════════════════════════════"
echo "TWITTER/X CONFIGURATION"
echo "═══════════════════════════════════════════════════"
echo "Note: All 4 Twitter credentials are required for it to work"
set_secret "TWITTER_API_KEY" "Twitter/X API Key (Consumer Key)" "optional"
set_secret "TWITTER_API_SECRET" "Twitter/X API Secret (Consumer Secret)" "optional"
set_secret "TWITTER_ACCESS_TOKEN" "Twitter/X Access Token" "optional"
set_secret "TWITTER_ACCESS_SECRET" "Twitter/X Access Token Secret" "optional"

# LinkedIn
echo ""
echo "═══════════════════════════════════════════════════"
echo "LINKEDIN CONFIGURATION"
echo "═══════════════════════════════════════════════════"
set_secret "LINKEDIN_ACCESS_TOKEN" "LinkedIn OAuth 2.0 access token" "optional"
set_secret "LINKEDIN_ORG_ID" "LinkedIn organization ID (108743037)" "optional"

echo ""
echo "========================================="
echo "✅ Secret configuration complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Configure the same secrets in Netlify (see Part 2 of guide)"
echo "2. Test with dry-run mode (see Part 3 of guide)"
echo ""

EOF

# Make the script executable
chmod +x setup-github-secrets.sh

echo "✅ Created setup-github-secrets.sh"
echo ""
echo "Run the script with:"
echo "  ./setup-github-secrets.sh"
```

#### Step 1.5: Run the Setup Script

```bash
# Execute the script
./setup-github-secrets.sh

# Follow the prompts to enter each secret value
```

#### Step 1.6: Verify Secrets Were Set

```bash
# List all secrets (names only, not values)
gh secret list -R PipFoweraker/pdoom1-website

# Expected output should include:
# NETLIFY_SITE_URL
# BLUESKY_HANDLE
# BLUESKY_APP_PASSWORD
# DISCORD_WEBHOOK_URL
# TWITTER_API_KEY
# TWITTER_API_SECRET
# TWITTER_ACCESS_TOKEN
# TWITTER_ACCESS_SECRET
# LINKEDIN_ACCESS_TOKEN
# LINKEDIN_ORG_ID
```

---

### Method 2: Using GitHub Web UI (Alternative)

If you prefer not to use GitHub CLI:

1. Navigate to: https://github.com/PipFoweraker/pdoom1-website/settings/secrets/actions

2. Click "New repository secret" for each of the following:

   ```
   Name: NETLIFY_SITE_URL
   Value: https://pdoom1.netlify.app (or your Netlify URL)
   
   Name: BLUESKY_HANDLE
   Value: pdoom1.bsky.social
   
   Name: BLUESKY_APP_PASSWORD
   Value: [from Bluesky Settings > App Passwords]
   
   Name: DISCORD_WEBHOOK_URL
   Value: [your Discord webhook URL]
   
   Name: TWITTER_API_KEY
   Value: [from Twitter Developer Portal]
   
   Name: TWITTER_API_SECRET
   Value: [from Twitter Developer Portal]
   
   Name: TWITTER_ACCESS_TOKEN
   Value: [from Twitter Developer Portal]
   
   Name: TWITTER_ACCESS_SECRET
   Value: [from Twitter Developer Portal]
   
   Name: LINKEDIN_ACCESS_TOKEN
   Value: [from LinkedIn Developer Portal]
   
   Name: LINKEDIN_ORG_ID
   Value: 108743037
   ```

---

## Part 2: Netlify Environment Variables Configuration

### Step 2.1: Access Netlify Dashboard

```bash
# Open Netlify site settings in browser
echo "Opening Netlify dashboard..."
echo "Navigate to: https://app.netlify.com/sites/[YOUR-SITE-NAME]/settings/env"
echo ""
echo "Or manually navigate to:"
echo "1. Go to https://app.netlify.com"
echo "2. Select your site (pdoom1-website)"
echo "3. Go to Site settings > Environment variables"
```

### Step 2.2: Prepare Environment Variables Script

Create a helper script to generate the environment variable list:

```bash
# Create a script to generate Netlify env vars
cat > netlify-env-vars.sh << 'EOF'
#!/bin/bash

# Netlify Environment Variables Generator
# This script creates a reference file with all environment variables

set -e

OUTPUT_FILE="netlify-env-vars.txt"

cat > "$OUTPUT_FILE" << 'ENVEOF'
# Netlify Environment Variables for Social Media Syndication
# Copy these to Netlify Site Settings > Environment variables
# https://app.netlify.com/sites/[YOUR-SITE]/settings/env

# ============================================
# ESSENTIAL
# ============================================

NETLIFY_SITE_URL=https://pdoom1.netlify.app

# ============================================
# BLUESKY
# ============================================

BLUESKY_HANDLE=pdoom1.bsky.social
BLUESKY_APP_PASSWORD=[GET FROM BLUESKY SETTINGS]

# To get Bluesky app password:
# 1. Go to https://bsky.app/settings/app-passwords
# 2. Click "Add App Password"
# 3. Name it "pdoom1-website-syndication"
# 4. Copy the generated password

# ============================================
# DISCORD
# ============================================

DISCORD_WEBHOOK_URL=[YOUR WEBHOOK URL]

# To create Discord webhook:
# 1. Go to Discord server settings
# 2. Integrations > Webhooks
# 3. Click "New Webhook"
# 4. Name it "p(Doom)1 Updates"
# 5. Select #alpha channel
# 6. Copy webhook URL

# ============================================
# TWITTER/X
# ============================================

TWITTER_API_KEY=[FROM TWITTER DEVELOPER PORTAL]
TWITTER_API_SECRET=[FROM TWITTER DEVELOPER PORTAL]
TWITTER_ACCESS_TOKEN=[FROM TWITTER DEVELOPER PORTAL]
TWITTER_ACCESS_SECRET=[FROM TWITTER DEVELOPER PORTAL]

# To get Twitter credentials:
# 1. Go to https://developer.twitter.com/en/portal/dashboard
# 2. Select your app or create new one
# 3. Go to "Keys and tokens"
# 4. Generate/copy API Key, API Secret, Access Token, Access Secret
# 5. Ensure app has "Read and Write" permissions

# ============================================
# LINKEDIN
# ============================================

LINKEDIN_ACCESS_TOKEN=[FROM LINKEDIN DEVELOPER PORTAL]
LINKEDIN_ORG_ID=108743037

# To get LinkedIn token:
# 1. Go to https://www.linkedin.com/developers/apps
# 2. Select your app or create new one
# 3. Request "Share on LinkedIn" product
# 4. Add organization (108743037) to app
# 5. Generate OAuth 2.0 access token with w_organization_social scope
# 6. Copy the token (it will expire periodically)

# ============================================
# OPTIONAL (for bug reporting)
# ============================================

GITHUB_DISPATCH_TOKEN=[IF NOT ALREADY SET]
GITHUB_REPO=PipFoweraker/pdoom1-website
ALLOWED_ORIGIN=https://pdoom1.com,https://*.netlify.app
DRY_RUN=false

ENVEOF

echo "✅ Created $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "1. Review and fill in the values in $OUTPUT_FILE"
echo "2. Add each variable manually in Netlify dashboard:"
echo "   https://app.netlify.com/sites/[YOUR-SITE]/settings/env"
echo "3. Click 'Add a variable' for each one"
echo "4. Scope: Select 'All' or 'Production' as needed"
echo ""

EOF

chmod +x netlify-env-vars.sh

echo "✅ Created netlify-env-vars.sh"
echo ""
echo "Run with: ./netlify-env-vars.sh"
```

### Step 2.3: Generate Reference File

```bash
# Run the script
./netlify-env-vars.sh

# Review the generated file
cat netlify-env-vars.txt

# This file contains all environment variables with instructions
```

### Step 2.4: Add Variables to Netlify

**Manual Process** (Netlify doesn't have a bulk import for env vars):

1. Open your Netlify site settings: https://app.netlify.com
2. Navigate to: Site settings > Environment variables
3. Click "Add a variable" for each variable
4. Enter the key (name) and value
5. Choose scope (All deployments recommended)
6. Click "Create variable"

**Recommended order:**
1. `NETLIFY_SITE_URL` (essential)
2. Platform credentials you want to enable (Bluesky, Discord, Twitter, LinkedIn)
3. Optional credentials

---

## Part 3: Platform-Specific Setup

### 3.1: Bluesky Setup

```bash
echo "Bluesky Setup Instructions:"
echo ""
echo "1. Log in to Bluesky at https://bsky.app"
echo "2. Go to Settings > App Passwords"
echo "3. Click 'Add App Password'"
echo "4. Name: pdoom1-website-syndication"
echo "5. Copy the generated password (it looks like: xxxx-xxxx-xxxx-xxxx)"
echo "6. Use this as BLUESKY_APP_PASSWORD in secrets"
echo ""
echo "Your handle should be: pdoom1.bsky.social (or just pdoom1)"
```

### 3.2: Discord Setup

```bash
echo "Discord Webhook Setup Instructions:"
echo ""
echo "1. Go to your Discord server"
echo "2. Right-click the #alpha channel > Edit Channel"
echo "3. Go to Integrations > Webhooks"
echo "4. Click 'New Webhook' or 'Create Webhook'"
echo "5. Name: p(Doom)1 Updates"
echo "6. Avatar: (optional) upload logo"
echo "7. Click 'Copy Webhook URL'"
echo "8. Use this URL as DISCORD_WEBHOOK_URL in secrets"
echo ""
echo "The URL will look like:"
echo "https://discord.com/api/webhooks/[ID]/[TOKEN]"
```

### 3.3: Twitter/X Setup

```bash
echo "Twitter/X API Setup Instructions:"
echo ""
echo "1. Go to https://developer.twitter.com/en/portal/dashboard"
echo "2. Select your app or create a new one"
echo "3. Go to 'Settings' > ensure 'Read and Write' permissions"
echo "4. Go to 'Keys and tokens' tab"
echo "5. Under 'Consumer Keys':"
echo "   - Copy 'API Key' → TWITTER_API_KEY"
echo "   - Copy 'API Key Secret' → TWITTER_API_SECRET"
echo "6. Under 'Authentication Tokens':"
echo "   - Click 'Generate' if not already generated"
echo "   - Copy 'Access Token' → TWITTER_ACCESS_TOKEN"
echo "   - Copy 'Access Token Secret' → TWITTER_ACCESS_SECRET"
echo ""
echo "⚠️  Alternative: Use Zapier or IFTTT (mentioned in issue)"
echo "   This may save Netlify function credits"
```

### 3.4: LinkedIn Setup

```bash
echo "LinkedIn API Setup Instructions:"
echo ""
echo "1. Go to https://www.linkedin.com/developers/apps"
echo "2. Create app or select existing one"
echo "3. Products tab > Request 'Share on LinkedIn' product"
echo "4. Settings tab > Add your company page:"
echo "   Company: p(Doom)1 Website"
echo "   ID: 108743037"
echo "   URL: https://www.linkedin.com/company/108743037"
echo "5. Auth tab > OAuth 2.0 settings:"
echo "   - Add redirect URL: https://pdoom1.com/auth/callback"
echo "6. Generate access token with w_organization_social scope"
echo "7. Copy token → LINKEDIN_ACCESS_TOKEN"
echo "8. Organization ID: 108743037"
echo ""
echo "⚠️  LinkedIn tokens expire periodically"
echo "   You'll need to regenerate when posts fail"
```

---

## Part 4: Testing

### 4.1: Test Helper Functions Locally

```bash
# Navigate to repository
cd /path/to/pdoom1-website

# Run the test suite
npm run test:syndication

# Expected output: All tests should pass
# ✅ Metadata extraction
# ✅ URL generation
# ✅ Content formatting
# ✅ Character limits
```

### 4.2: Test Workflow with Dry Run

Create a test script:

```bash
# Create dry run test script
cat > test-syndication-dryrun.sh << 'EOF'
#!/bin/bash

# Test Syndication Workflow (Dry Run)
# This script triggers the workflow without actually posting

set -e

REPO="PipFoweraker/pdoom1-website"
WORKFLOW="syndicate-content.yml"
BRANCH="main"
TEST_FILE="public/blog/2025-10-09-website-development-sprint-complete-v0-2-0.md"

echo "========================================="
echo "Testing Syndication Workflow (Dry Run)"
echo "========================================="
echo ""
echo "Repository: $REPO"
echo "Workflow: $WORKFLOW"
echo "Test file: $TEST_FILE"
echo ""

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "❌ Error: GitHub CLI (gh) is not installed"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Check authentication
echo "Checking GitHub CLI authentication..."
gh auth status || {
    echo "❌ Not authenticated. Run: gh auth login"
    exit 1
}

echo "✅ Authenticated"
echo ""

# Trigger the workflow
echo "Triggering workflow with dry run mode..."
echo ""

gh workflow run "$WORKFLOW" \
  -R "$REPO" \
  -r "$BRANCH" \
  -f content_path="$TEST_FILE" \
  -f dry_run=true

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Workflow triggered successfully!"
    echo ""
    echo "To view the run:"
    echo "  gh run list -R $REPO -w \"$WORKFLOW\" -L 1"
    echo ""
    echo "To watch the run:"
    echo "  gh run watch -R $REPO"
    echo ""
    echo "Or view in browser:"
    echo "  https://github.com/$REPO/actions/workflows/$(basename $WORKFLOW)"
    echo ""
    echo "The workflow will:"
    echo "  1. Extract metadata from the blog post"
    echo "  2. Format messages for each platform"
    echo "  3. Show what WOULD be posted (but won't actually post)"
    echo ""
else
    echo "❌ Failed to trigger workflow"
    exit 1
fi

EOF

chmod +x test-syndication-dryrun.sh

echo "✅ Created test-syndication-dryrun.sh"
echo "Run with: ./test-syndication-dryrun.sh"
```

### 4.3: Run Dry Run Test

```bash
# Execute the test
./test-syndication-dryrun.sh

# Watch the workflow run
gh run watch -R PipFoweraker/pdoom1-website

# Or view in browser
echo "View workflow runs at:"
echo "https://github.com/PipFoweraker/pdoom1-website/actions/workflows/syndicate-content.yml"
```

### 4.4: Review Dry Run Results

```bash
# Get the latest run
LATEST_RUN=$(gh run list -R PipFoweraker/pdoom1-website -w "syndicate-content.yml" -L 1 --json databaseId -q '.[0].databaseId')

echo "Latest run ID: $LATEST_RUN"

# View the logs
gh run view $LATEST_RUN -R PipFoweraker/pdoom1-website --log

# Look for sections showing formatted content for each platform
```

---

## Part 5: Live Testing

### 5.1: Test with Actual Post (Once Secrets Configured)

Create a test post script:

```bash
# Create test post script
cat > test-live-post.sh << 'EOF'
#!/bin/bash

# Create a test blog post and trigger syndication

set -e

TEST_POST="public/blog/test-syndication-$(date +%Y-%m-%d).md"
DATE=$(date +%Y-%m-%d)

echo "Creating test blog post..."

cat > "$TEST_POST" << POSTEOF
# Test Syndication Post

**Date**: $DATE
**Tags**: [test, syndication]

## Summary
This is a test post to verify social media syndication is working correctly. If you see this on Bluesky, Discord, Twitter/X, or LinkedIn, the syndication is working!

## Details
Testing the automated syndication system for the p(Doom)1 website.

POSTEOF

echo "✅ Created $TEST_POST"
echo ""

# Add and commit
git add "$TEST_POST"
git commit -m "Test: Syndication post for $(date +%Y-%m-%d)"

echo ""
echo "⚠️  IMPORTANT: About to push to main branch"
echo "This will trigger LIVE posting to all configured platforms!"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled. To remove test post:"
    echo "  git reset HEAD~1"
    echo "  git checkout -- $TEST_POST"
    exit 0
fi

# Push to trigger workflow
git push origin main

echo ""
echo "✅ Pushed to main. Workflow should trigger automatically."
echo ""
echo "Check:"
echo "1. GitHub Actions: https://github.com/PipFoweraker/pdoom1-website/actions"
echo "2. Bluesky: https://bsky.app/profile/pdoom1.bsky.social"
echo "3. Discord: Check #alpha channel"
echo "4. Twitter: https://twitter.com/[your-username]"
echo "5. LinkedIn: https://www.linkedin.com/company/108743037"
echo ""

EOF

chmod +x test-live-post.sh

echo "✅ Created test-live-post.sh"
echo ""
echo "⚠️  WARNING: This will post to LIVE social media!"
echo "Only run after secrets are configured and dry run succeeds"
```

### 5.2: Clean Up Test Post (if needed)

```bash
# If test post should be removed
cat > cleanup-test-post.sh << 'EOF'
#!/bin/bash

# Remove test syndication post

set -e

echo "Searching for test posts..."
TEST_POSTS=$(find public/blog -name "test-syndication-*.md" 2>/dev/null || echo "")

if [ -z "$TEST_POSTS" ]; then
    echo "No test posts found"
    exit 0
fi

echo "Found test posts:"
echo "$TEST_POSTS"
echo ""

read -p "Delete these posts? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled"
    exit 0
fi

# Delete test posts
for post in $TEST_POSTS; do
    git rm "$post"
    echo "Deleted: $post"
done

git commit -m "Clean up: Remove test syndication posts"
git push origin main

echo "✅ Test posts removed"

EOF

chmod +x cleanup-test-post.sh
```

---

## Part 6: Monitoring and Maintenance

### 6.1: Check Workflow Status

```bash
# Create monitoring script
cat > monitor-syndication.sh << 'EOF'
#!/bin/bash

# Monitor syndication workflow runs

set -e

REPO="PipFoweraker/pdoom1-website"
WORKFLOW="syndicate-content.yml"

echo "========================================="
echo "Syndication Workflow Monitor"
echo "========================================="
echo ""

# Recent runs
echo "Recent workflow runs:"
gh run list -R "$REPO" -w "$WORKFLOW" -L 10

echo ""
echo "To view details of a run:"
echo "  gh run view [RUN_ID] -R $REPO"
echo ""
echo "To view logs:"
echo "  gh run view [RUN_ID] -R $REPO --log"
echo ""

# Check for failures
echo "Checking for failed runs..."
FAILED=$(gh run list -R "$REPO" -w "$WORKFLOW" -L 5 --json conclusion -q '[.[] | select(.conclusion=="failure")] | length')

if [ "$FAILED" -gt 0 ]; then
    echo "⚠️  Found $FAILED failed runs in last 5"
    echo ""
    echo "Failed runs:"
    gh run list -R "$REPO" -w "$WORKFLOW" -L 5 --json databaseId,conclusion,startedAt -q '.[] | select(.conclusion=="failure") | "\(.databaseId) - \(.startedAt)"'
else
    echo "✅ No failures in recent runs"
fi

EOF

chmod +x monitor-syndication.sh

echo "✅ Created monitor-syndication.sh"
```

### 6.2: Create Maintenance Checklist Script

```bash
# Create maintenance script
cat > syndication-maintenance.sh << 'EOF'
#!/bin/bash

# Syndication System Maintenance Checklist

echo "========================================="
echo "Syndication System Maintenance"
echo "========================================="
echo ""

echo "✅ Weekly Checklist:"
echo "  [ ] Check Netlify function invocations (dashboard)"
echo "  [ ] Verify posts on all platforms"
echo "  [ ] Review GitHub Actions logs for errors"
echo ""

echo "⚠️  Monthly Checklist:"
echo "  [ ] Review and refresh LinkedIn access token (expires periodically)"
echo "  [ ] Check platform API rate limits"
echo "  [ ] Review Netlify credit usage"
echo ""

echo "🔧 Troubleshooting Commands:"
echo ""
echo "Check recent runs:"
echo "  ./monitor-syndication.sh"
echo ""
echo "Test locally:"
echo "  npm run test:syndication"
echo ""
echo "Dry run test:"
echo "  ./test-syndication-dryrun.sh"
echo ""
echo "View GitHub secrets:"
echo "  gh secret list -R PipFoweraker/pdoom1-website"
echo ""
echo "View workflow runs:"
echo "  gh run list -R PipFoweraker/pdoom1-website -w syndicate-content.yml"
echo ""

echo "📚 Documentation:"
echo "  Architecture: docs/SYNDICATION_ARCHITECTURE.md"
echo "  Setup: docs/SYNDICATION_SETUP.md"
echo "  Summary: docs/SYNDICATION_SUMMARY.md"
echo "  Quickstart: docs/SYNDICATION_QUICKSTART.md"
echo ""

EOF

chmod +x syndication-maintenance.sh

echo "✅ Created syndication-maintenance.sh"
```

---

## Part 7: Troubleshooting

### 7.1: Common Issues and Solutions

#### Issue: "Credentials not configured"

```bash
# Check if secrets are set
gh secret list -R PipFoweraker/pdoom1-website

# Verify Netlify env vars
echo "Check Netlify dashboard:"
echo "https://app.netlify.com/sites/[YOUR-SITE]/settings/env"

# Re-run setup if needed
./setup-github-secrets.sh
```

#### Issue: LinkedIn posts fail

```bash
# LinkedIn tokens expire - regenerate
echo "LinkedIn token expired. Follow these steps:"
echo "1. Go to https://www.linkedin.com/developers/apps"
echo "2. Select your app"
echo "3. Generate new access token"
echo "4. Update secrets:"
echo ""
echo "GitHub:"
echo "  gh secret set LINKEDIN_ACCESS_TOKEN -R PipFoweraker/pdoom1-website"
echo ""
echo "Netlify:"
echo "  Update in dashboard"
```

#### Issue: Twitter OAuth errors

```bash
echo "Twitter OAuth troubleshooting:"
echo ""
echo "1. Verify app permissions (must be 'Read and Write'):"
echo "   https://developer.twitter.com/en/portal/dashboard"
echo ""
echo "2. Regenerate tokens if permissions changed:"
echo "   Go to Keys and tokens > Regenerate"
echo ""
echo "3. Update all 4 credentials in secrets"
```

### 7.2: View Detailed Logs

```bash
# Get latest run ID
LATEST=$(gh run list -R PipFoweraker/pdoom1-website -w syndicate-content.yml -L 1 --json databaseId -q '.[0].databaseId')

# View full logs
gh run view $LATEST -R PipFoweraker/pdoom1-website --log

# View specific job
gh run view $LATEST -R PipFoweraker/pdoom1-website --log --job [JOB_ID]
```

---

## Quick Reference Card

Save this for quick access:

```bash
# Create quick reference
cat > SYNDICATION_QUICK_REF.txt << 'EOF'
═══════════════════════════════════════════════════════════
SOCIAL MEDIA SYNDICATION - QUICK REFERENCE
═══════════════════════════════════════════════════════════

SETUP SCRIPTS
────────────────────────────────────────────────────────────
./setup-github-secrets.sh      - Configure GitHub secrets
./netlify-env-vars.sh          - Generate Netlify env vars list
./test-syndication-dryrun.sh   - Test without posting
./test-live-post.sh            - Create test post (LIVE)
./monitor-syndication.sh       - Check workflow status
./syndication-maintenance.sh   - Maintenance checklist

LOCAL TESTING
────────────────────────────────────────────────────────────
npm run test:syndication       - Run test suite

GITHUB CLI COMMANDS
────────────────────────────────────────────────────────────
gh secret list -R PipFoweraker/pdoom1-website
gh run list -R PipFoweraker/pdoom1-website -w syndicate-content.yml
gh run view [RUN_ID] -R PipFoweraker/pdoom1-website --log

URLS
────────────────────────────────────────────────────────────
GitHub Actions:  https://github.com/PipFoweraker/pdoom1-website/actions
Netlify:         https://app.netlify.com
Bluesky:         https://bsky.app/profile/pdoom1.bsky.social
LinkedIn:        https://www.linkedin.com/company/108743037
Twitter Dev:     https://developer.twitter.com/en/portal/dashboard
LinkedIn Dev:    https://www.linkedin.com/developers/apps

REQUIRED SECRETS
────────────────────────────────────────────────────────────
Essential:
  NETLIFY_SITE_URL

Optional (enable platforms you want):
  BLUESKY_HANDLE, BLUESKY_APP_PASSWORD
  DISCORD_WEBHOOK_URL
  TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
  LINKEDIN_ACCESS_TOKEN, LINKEDIN_ORG_ID

═══════════════════════════════════════════════════════════
EOF

cat SYNDICATION_QUICK_REF.txt
```

---

## Summary

All scripts created! Here's what to do now:

```bash
# 1. Setup GitHub secrets
./setup-github-secrets.sh

# 2. Setup Netlify environment variables
./netlify-env-vars.sh
# Then manually add to Netlify dashboard

# 3. Test locally
npm run test:syndication

# 4. Test workflow (dry run)
./test-syndication-dryrun.sh

# 5. Monitor results
./monitor-syndication.sh

# 6. When ready, test live
./test-live-post.sh
```

**All files created in this guide:**
- `setup-github-secrets.sh` - GitHub secrets setup
- `netlify-env-vars.sh` - Netlify env vars generator  
- `test-syndication-dryrun.sh` - Workflow dry run test
- `test-live-post.sh` - Live posting test
- `cleanup-test-post.sh` - Remove test posts
- `monitor-syndication.sh` - Monitor workflow runs
- `syndication-maintenance.sh` - Maintenance checklist
- `netlify-env-vars.txt` - Generated env vars list
- `SYNDICATION_QUICK_REF.txt` - Quick reference card

For detailed platform-specific instructions, see:
- `docs/SYNDICATION_SETUP.md`
- `docs/SYNDICATION_QUICKSTART.md`
- `docs/SYNDICATION_ARCHITECTURE.md`
