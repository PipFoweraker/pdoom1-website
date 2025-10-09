# Design Token Synchronization Strategy

## Overview

This document describes how design tokens are synchronized from the main game repository (`PipFoweraker/pdoom1`) to the website repository (`PipFoweraker/pdoom1-website`).

## Architecture

```
PipFoweraker/pdoom1 (Game Repo)
├── tokens.json or public/design/tokens.json
└── Canonical source of design tokens

        ↓ (automated sync via GitHub Actions)

PipFoweraker/pdoom1-website (Website Repo)
├── public/design/tokens.json (synced copy)
├── .github/workflows/sync-design-tokens.yml
└── Applied at runtime via inline scripts
```

## Token Structure

The tokens.json file contains three main groups:

```json
{
  "version": 1,
  "updated": "2025-09-09T00:00:00Z",
  "colors": {
    "bgPrimary": "#1a1a1a",
    "textPrimary": "#ffffff",
    "accentPrimary": "#00ff41",
    ...
  },
  "shape": {
    "radiusSm": "4px",
    "borderWidth": "1px",
    "shadowButton": "0 10px 20px rgba(0, 255, 65, 0.3)",
    ...
  },
  "motion": {
    "durationFast": "150ms",
    "durationBase": "300ms",
    "easing": "cubic-bezier(0.2, 0.8, 0.2, 1)"
  }
}
```

## Sync Workflow

### Manual Sync

To manually sync tokens from the main repo:

1. Navigate to **Actions** → **Sync Design Tokens from pdoom1**
2. Click **Run workflow**
3. Enter the git ref (branch, tag, or commit SHA) from the main repo
4. The workflow will:
   - Check out both repositories
   - Copy tokens.json to `public/design/tokens.json`
   - Commit and push if changes are detected

### Automatic Sync on Release

The main pdoom1 repository can automatically trigger a sync when a new release/tag is created.

#### Setup in Main Repo (PipFoweraker/pdoom1)

Add this step to your release workflow:

```yaml
# .github/workflows/release.yml or tag workflow
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      # ... other release steps ...
      
      - name: Notify website to sync tokens
        if: success()
        run: |
          curl -X POST \
            -H "Authorization: token ${{ secrets.WEBSITE_SYNC_TOKEN }}" \
            -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/PipFoweraker/pdoom1-website/dispatches \
            -d '{
              "event_type": "sync-tokens",
              "client_payload": {
                "ref": "${{ github.ref_name }}"
              }
            }'
```

#### Required Secret

In the main pdoom1 repo, add a secret named `WEBSITE_SYNC_TOKEN`:
- Generate a Personal Access Token with `repo` scope
- Add it to the pdoom1 repository secrets as `WEBSITE_SYNC_TOKEN`

## Token Locations

The sync workflow checks for tokens.json in the following locations (in order):
1. `public/design/tokens.json`
2. `design/tokens.json`
3. `tokens.json` (root)

## Usage in Website

Tokens are loaded at runtime via inline scripts in HTML files:

```javascript
async function loadDesignTokens() {
  try {
    const response = await fetch('/design/tokens.json');
    const tokens = await response.json();
    const root = document.documentElement;
    
    for (const [key, value] of Object.entries(tokens)) {
      root.style.setProperty(`--${key}`, value);
    }
  } catch (error) {
    console.warn('Could not load design tokens:', error);
  }
}
loadDesignTokens();
```

CSS variables are then available throughout the site:
```css
body {
  background: var(--bg-primary);
  color: var(--text-primary);
}
```

## Benefits

1. **Single Source of Truth**: Tokens maintained in one place (main game repo)
2. **Automatic Sync**: Website tokens update automatically on releases
3. **Version Control**: Full git history of token changes
4. **Flexibility**: Can sync from any ref (tag, branch, commit)
5. **No Build Dependencies**: Tokens loaded at runtime, no build step needed

## Maintenance

### Updating Token Structure

When adding new token groups or changing structure:
1. Update tokens.json in main pdoom1 repo
2. Test locally in game
3. Create a release/tag
4. Automatic sync will update website
5. Verify tokens load correctly on website

### Troubleshooting

**Tokens not syncing:**
- Check workflow run logs in Actions tab
- Verify tokens.json exists in main repo
- Check file permissions and paths

**Tokens not applying:**
- Check browser console for loading errors
- Verify JSON structure is valid
- Clear browser cache and reload

## Related Documentation

- Main style guide: `docs/01-development/style-guide.md`
- Workflow implementation: `.github/workflows/sync-design-tokens.yml`
- Roadmap sync (similar pattern): `docs/03-integrations/roadmap-sync-strategy.md`
