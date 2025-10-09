# CLI Deployment Commands

Quick reference for managing p(Doom)1 website deployments from command line.

## Prerequisites

Install GitHub CLI: `winget install GitHub.cli` (or from https://cli.github.com/)

## Deployment Commands

### 1. Deploy to DreamHost
```bash
# Standard deployment
gh workflow run "Deploy to DreamHost (manual)" --ref main

# Dry run (preview changes without deploying)
gh workflow run "Deploy to DreamHost (manual)" --ref main -f dry_run=true

# Deploy different branch
gh workflow run "Deploy to DreamHost (manual)" --ref feature-branch
```

### 2. Update Game Status
```bash
# Update with specific version and phase
gh workflow run "Update Game Status" --ref main \
  -f version="v0.4.2" \
  -f phase="Steam preparation phase" \
  -f progress="85% complete"

# Change game status to beta
gh workflow run "Update Game Status" --ref main \
  -f status="beta" \
  -f warning="Beta version - mostly stable but may have bugs"

# Auto-fetch latest release from GitHub
gh workflow run "Update Game Status" --ref main \
  -f fetch_release=true
```

### 3. Check Deployment Status
```bash
# List recent deployments
gh run list --workflow="Deploy to DreamHost (manual)" --limit 5

# Watch current deployment live
gh run watch $(gh run list --workflow="Deploy to DreamHost (manual)" --limit 1 --json databaseId --jq '.[0].databaseId')

# Get logs from latest deployment
gh run view --log $(gh run list --workflow="Deploy to DreamHost (manual)" --limit 1 --json databaseId --jq '.[0].databaseId')
```

### 4. Repository Management
```bash
# Quick status check
git status && git log --oneline -3

# Commit and deploy in one go
git add -A
git commit -m "Update content"
git push origin main
gh workflow run "Deploy to DreamHost (manual)" --ref main

# Check if deployment is needed
git fetch origin
git log HEAD..origin/main --oneline
```

## Advanced Workflows

### Deploy with Status Update
```bash
# Update game status and deploy automatically
gh workflow run "Update Game Status" --ref main \
  -f version="v0.4.3" \
  -f phase="Bug fixes and polish" \
  -f progress="Ready for testing"

# If AUTO_DEPLOY_ON_STATUS_UPDATE is enabled, it will deploy automatically
# Otherwise, trigger deployment manually:
gh workflow run "Deploy to DreamHost (manual)" --ref main
```

### Development Workflow
```bash
# 1. Make changes locally
# 2. Test locally: python -m http.server 8000
# 3. Commit changes
git add -A && git commit -m "Feature: whatever you changed"

# 4. Push and deploy
git push origin main
gh workflow run "Deploy to DreamHost (manual)" --ref main

# 5. Watch deployment
gh run watch $(gh run list --workflow="Deploy to DreamHost (manual)" --limit 1 --json databaseId --jq '.[0].databaseId')
```

### Batch Operations
```bash
# Update multiple things at once
gh workflow run "Update Game Status" --ref main \
  -f version="v0.5.0" \
  -f status="beta" \
  -f warning="Beta release - please report bugs" \
  -f phase="Beta testing phase" \
  -f progress="Feature complete, testing in progress" \
  -f fetch_release=true

# Then deploy
sleep 30  # Wait for status update to complete
gh workflow run "Deploy to DreamHost (manual)" --ref main
```

## Useful Aliases

Add these to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
# Quick deploy
alias pdeploy='gh workflow run "Deploy to DreamHost (manual)" --ref main'

# Deploy with dry run
alias pdeploy-test='gh workflow run "Deploy to DreamHost (manual)" --ref main -f dry_run=true'

# Check deployment status
alias pstatus='gh run list --workflow="Deploy to DreamHost (manual)" --limit 3'

# Watch latest deployment
alias pwatch='gh run watch $(gh run list --workflow="Deploy to DreamHost (manual)" --limit 1 --json databaseId --jq ".[0].databaseId")'

# Update game status with current version
alias pupdate='gh workflow run "Update Game Status" --ref main -f fetch_release=true'

# Full update and deploy
alias pfull='git add -A && git commit -m "Auto update" && git push origin main && sleep 5 && pdeploy'
```

## Error Handling

```bash
# Check if deployment failed
gh run list --workflow="Deploy to DreamHost (manual)" --limit 1 --json conclusion --jq '.[0].conclusion'

# Get error logs
gh run view --log $(gh run list --workflow="Deploy to DreamHost (manual)" --limit 1 --json databaseId --jq '.[0].databaseId') | grep -i error

# Re-run failed deployment
gh run rerun $(gh run list --workflow="Deploy to DreamHost (manual)" --limit 1 --json databaseId --jq '.[0].databaseId')
```

## Integration with Main Game Repo

From your main pdoom1 game repository, you can trigger website updates:

```bash
# Trigger website update from game repo
gh workflow run "Update Website Status" --ref main \
  -f status="alpha" \
  -f phase="Major refactoring in progress" \
  -f progress="60% complete"
```

This will automatically update the website without you needing to switch repositories!
