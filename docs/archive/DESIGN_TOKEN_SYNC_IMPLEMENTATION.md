# Design Token Sync Implementation Summary

## What Was Implemented

This implementation addresses the requirement to sync design tokens from the main pdoom1 repository to the website repository, establishing the main repo as the canonical source of truth for design tokens.

## Files Created

### 1. GitHub Action Workflow
**File**: `.github/workflows/sync-design-tokens.yml`

This workflow:
- Triggers manually via `workflow_dispatch` (for testing and manual syncs)
- Triggers automatically via `repository_dispatch` when the main repo sends a sync event
- Checks out both the website and main pdoom1 repositories
- Searches for tokens.json in expected locations in the main repo
- Copies the file to `public/design/tokens.json` in the website repo
- Commits and pushes changes if tokens have been updated

**Key Features**:
- Flexible ref targeting (can sync from any branch, tag, or commit SHA)
- Multiple fallback locations for tokens.json discovery
- Clean error handling with warnings
- Automatic commit/push only when changes are detected

### 2. Comprehensive Documentation
**File**: `docs/03-integrations/design-token-sync-strategy.md`

Complete guide covering:
- Architecture overview and data flow
- Token structure and format
- Manual sync instructions
- Automatic sync setup (from main repo)
- Usage examples in the website
- Benefits of the approach
- Maintenance and troubleshooting

### 3. Sample Workflow for Main Repo
**File**: `docs/03-integrations/pdoom1-token-sync-workflow-sample.md`

Ready-to-use workflow file that can be added to the main pdoom1 repository to:
- Trigger token sync on new releases/tags
- Send repository_dispatch events to the website repo
- Include setup instructions for required secrets
- Provide testing and troubleshooting guidance

### 4. Updated Style Guide
**File**: `docs/01-development/style-guide.md`

Updated the "Integration with pdoom1 main repo" section to:
- Document the canonical source (main pdoom1 repo)
- Explain the automated sync strategy
- Provide manual and automatic sync instructions
- Include example workflow code for the main repo

### 5. Documentation Index Updates
**Files**: 
- `docs/README.md` - Added references to token sync documentation
- `public/docs/index.html` - Added link to design token sync strategy

## How It Works

### Current State
The tokens are currently maintained in `public/design/tokens.json` in the website repository.

### Future State (After Main Repo Setup)
1. **Main Repo (pdoom1)**: Maintains canonical tokens.json
2. **On Release/Tag**: Main repo workflow sends repository_dispatch event
3. **Website Repo**: Receives event, runs sync workflow
4. **Sync Process**: Copies tokens.json from main repo to website
5. **Commit**: Changes are committed and pushed automatically

### Manual Sync Option
Anytime someone needs to sync tokens:
1. Go to GitHub Actions → "Sync Design Tokens from pdoom1"
2. Click "Run workflow"
3. Enter the ref (tag, branch, or SHA) from main repo
4. Workflow runs and updates tokens if changed

## Benefits

1. **Single Source of Truth**: Tokens maintained in one place (main repo)
2. **Consistency**: Game and website use same design system
3. **Automation**: Tokens sync automatically on releases
4. **Version Control**: Full git history of token changes
5. **Flexibility**: Can sync from any ref (useful for testing)
6. **No Build Step**: Tokens loaded at runtime, no rebuild needed

## Next Steps

To fully activate this system, the main pdoom1 repository needs:

1. **Create tokens.json** in the main repo (if it doesn't exist)
   - Recommended location: `public/design/tokens.json`
   - Use existing format from website

2. **Add the sync workflow** to main repo
   - Use the sample from `docs/03-integrations/pdoom1-token-sync-workflow-sample.md`
   - Create `.github/workflows/sync-tokens-to-website.yml`

3. **Create GitHub secret** in main repo
   - Generate a Personal Access Token with `repo` scope
   - Add as secret: `WEBSITE_SYNC_TOKEN`

4. **Test the sync**
   - Push a test tag or trigger workflow manually
   - Verify tokens sync to website repo

## Testing

The workflow has been:
- ✅ Created with valid YAML syntax
- ✅ Documented comprehensively
- ✅ Integrated into documentation structure
- ⏳ Not yet tested (requires main repo setup or manual trigger)

To test:
```bash
# Option 1: Manual trigger via GitHub UI
# Go to Actions → Sync Design Tokens from pdoom1 → Run workflow

# Option 2: Using gh CLI
gh workflow run sync-design-tokens.yml -f ref=main
```

## Token Structure

Current tokens.json structure (will be maintained):
```json
{
  "version": 1,
  "updated": "2025-09-09T00:00:00Z",
  "colors": { ... },
  "shape": { ... },
  "motion": { ... }
}
```

## Documentation Links

- Main strategy doc: `docs/03-integrations/design-token-sync-strategy.md`
- Sample workflow for main repo: `docs/03-integrations/pdoom1-token-sync-workflow-sample.md`
- Style guide: `docs/01-development/style-guide.md`
- Public docs: `public/docs/index.html` (now includes token sync link)

## Maintenance

- Workflow runs automatically when triggered from main repo
- Manual syncs available anytime via GitHub Actions UI
- No scheduled runs (sync on-demand only)
- No breaking changes to existing token structure or usage
