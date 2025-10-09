# Design Token Sync - Quick Reference Card

## 🚀 Quick Start

### Manual Sync (Immediate Use)
1. Go to: **Actions** → **Sync Design Tokens from pdoom1**
2. Click **Run workflow**
3. Enter ref: `main` (or any branch/tag/SHA from pdoom1 repo)
4. Click **Run workflow**

### View the Workflow
- File: `.github/workflows/sync-design-tokens.yml`
- Triggers: `workflow_dispatch` (manual), `repository_dispatch` (automatic)
- Status: ✅ Ready to use

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `docs/03-integrations/design-token-sync-strategy.md` | Complete strategy guide |
| `docs/03-integrations/pdoom1-token-sync-workflow-sample.md` | Workflow for main repo |
| `docs/01-development/style-guide.md` | Updated integration section |
| `DESIGN_TOKEN_SYNC_IMPLEMENTATION.md` | Implementation summary |

## 🔧 Setup for Automatic Sync

### In Main pdoom1 Repo:

1. **Create/move tokens.json**
   - Recommended: `public/design/tokens.json`
   - Alternatives: `design/tokens.json` or `tokens.json`

2. **Add workflow file**
   - Copy from: `docs/03-integrations/pdoom1-token-sync-workflow-sample.md`
   - Save to: `.github/workflows/sync-tokens-to-website.yml`

3. **Create secret**
   - Name: `WEBSITE_SYNC_TOKEN`
   - Generate PAT with `repo` scope
   - Add to repository secrets

4. **Test**
   - Push a test tag: `git tag v1.0.0-test && git push origin v1.0.0-test`
   - Or trigger manually via Actions UI

## 🎯 What This Solves

✅ Single source of truth for design tokens (main pdoom1 repo)  
✅ Automatic sync on releases/tags  
✅ Manual sync option for testing  
✅ No breaking changes to existing functionality  
✅ Fully documented with examples  

## 🔄 Data Flow

```
pdoom1 repo          website repo           browser
tokens.json    →     tokens.json      →     CSS vars
(canonical)          (synced copy)          (applied)
```

## 📝 Token Structure

```json
{
  "version": 1,
  "updated": "2025-09-09T00:00:00Z",
  "colors": { ... },
  "shape": { ... },
  "motion": { ... }
}
```

## ⚠️ Important Notes

- Existing tokens.json in website repo is preserved
- Workflow only commits if tokens change
- Supports any git ref (branch, tag, commit SHA)
- Multiple location fallbacks for token discovery
- Safe: won't break if tokens.json not found in main repo

## 🧪 Testing

```bash
# Via GitHub CLI
gh workflow run sync-design-tokens.yml -f ref=main

# Via GitHub UI
Actions → Sync Design Tokens from pdoom1 → Run workflow
```

## 📞 Support

- Check workflow runs in Actions tab
- Review logs for sync issues
- Verify tokens.json exists in expected location
- Ensure token format is valid JSON

---

**Status**: ✅ Implementation Complete  
**Version**: 1.0  
**Last Updated**: October 9, 2025
