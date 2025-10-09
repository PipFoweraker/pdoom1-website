# Sample Workflow for PipFoweraker/pdoom1 Repository

This file contains a sample workflow that can be added to the main pdoom1 repository to automatically sync design tokens to the website on releases.

## File: `.github/workflows/sync-tokens-to-website.yml`

```yaml
name: Sync Tokens to Website

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
    inputs:
      force_sync:
        description: 'Force sync tokens to website'
        required: false
        default: 'false'

jobs:
  sync-tokens:
    runs-on: ubuntu-latest
    steps:
      - name: Check tokens.json exists
        uses: actions/checkout@v4
        
      - name: Verify tokens.json
        id: verify
        run: |
          if [ -f public/design/tokens.json ]; then
            echo "tokens_path=public/design/tokens.json" >> $GITHUB_OUTPUT
            echo "Tokens found at: public/design/tokens.json"
          elif [ -f design/tokens.json ]; then
            echo "tokens_path=design/tokens.json" >> $GITHUB_OUTPUT
            echo "Tokens found at: design/tokens.json"
          elif [ -f tokens.json ]; then
            echo "tokens_path=tokens.json" >> $GITHUB_OUTPUT
            echo "Tokens found at: tokens.json"
          else
            echo "::error::tokens.json not found in repository"
            exit 1
          fi
          
      - name: Trigger website token sync
        if: success()
        run: |
          echo "Triggering sync for ref: ${{ github.ref_name }}"
          
          curl -X POST \
            -H "Authorization: token ${{ secrets.WEBSITE_SYNC_TOKEN }}" \
            -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/PipFoweraker/pdoom1-website/dispatches \
            -d '{
              "event_type": "sync-tokens",
              "client_payload": {
                "ref": "${{ github.ref_name }}",
                "source": "pdoom1",
                "triggered_by": "${{ github.actor }}"
              }
            }'
            
      - name: Verify webhook sent
        if: success()
        run: |
          echo "✓ Website token sync triggered successfully"
          echo "Check progress at: https://github.com/PipFoweraker/pdoom1-website/actions/workflows/sync-design-tokens.yml"
```

## Setup Instructions

### 1. Add the Workflow File

1. In the `PipFoweraker/pdoom1` repository, create:
   - `.github/workflows/sync-tokens-to-website.yml`
2. Copy the workflow content above into this file
3. Commit and push

### 2. Create Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name: "Website Token Sync"
4. Select scopes:
   - ✓ `repo` (Full control of private repositories)
5. Click "Generate token"
6. **IMPORTANT**: Copy the token immediately (you won't see it again)

### 3. Add Secret to Main Repo

1. Go to `PipFoweraker/pdoom1` repository
2. Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `WEBSITE_SYNC_TOKEN`
5. Value: Paste the personal access token from step 2
6. Click "Add secret"

## Testing

### Test the Workflow

1. Push a test tag:
   ```bash
   git tag v1.0.0-test
   git push origin v1.0.0-test
   ```

2. Or trigger manually:
   - Go to Actions → "Sync Tokens to Website"
   - Click "Run workflow"
   - Enter "true" for force_sync
   - Click "Run workflow"

3. Verify in website repo:
   - Go to `PipFoweraker/pdoom1-website`
   - Check Actions → "Sync Design Tokens from pdoom1"
   - Should see a workflow run triggered by repository_dispatch

## Tokens Location

Ensure `tokens.json` exists in one of these locations:
- `public/design/tokens.json` (recommended)
- `design/tokens.json`
- `tokens.json` (root)

## Workflow Triggers

The workflow runs:
1. **Automatically** when pushing tags starting with `v` (e.g., `v1.0.0`, `v2.1.3`)
2. **Manually** via workflow_dispatch in GitHub Actions UI

## Troubleshooting

**"tokens.json not found" error:**
- Check tokens.json exists in expected location
- Verify path in the repository

**Webhook fails silently:**
- Check WEBSITE_SYNC_TOKEN secret exists
- Verify token has correct permissions (repo scope)
- Check token hasn't expired

**Website doesn't receive sync:**
- Check website repo Actions for workflow runs
- Verify repository_dispatch event type matches ("sync-tokens")
- Check website workflow permissions (needs `contents: write`)

## Alternative: Manual Sync

If automatic sync isn't desired, tokens can be synced manually:
1. Go to `PipFoweraker/pdoom1-website`
2. Actions → "Sync Design Tokens from pdoom1"
3. Run workflow with desired ref (tag/branch/SHA)
