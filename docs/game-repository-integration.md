# Game Repository Integration

This document explains how to integrate the main p(Doom)1 game repository with the website for automatic status updates.

## For the Main Game Repository

### 1. Add Website Update Workflow

Create `.github/workflows/update-website-status.yml` in the main game repository:

```yaml
name: Update Website Status

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      status:
        description: 'Game status'
        required: true
        default: 'alpha'
        type: choice
        options:
          - alpha
          - beta
          - release
      warning:
        description: 'Warning message for users'
        required: false
        default: 'SUPER BUGGY ALPHA - Download at your own risk'
        type: string
      phase:
        description: 'Current development phase'
        required: false
        type: string
      progress:
        description: 'Development progress'
        required: false
        type: string

jobs:
  update-website:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger website status update
        uses: peter-evans/repository-dispatch@v2
        with:
          token: ${{ secrets.WEBSITE_UPDATE_TOKEN }}
          repository: PipFoweraker/pdoom1-website
          event-type: update-game-status
          client-payload: |
            {
              "version": "${{ github.event.release.tag_name || github.event.inputs.version }}",
              "status": "${{ github.event.inputs.status || 'alpha' }}",
              "warning": "${{ github.event.inputs.warning || 'SUPER BUGGY ALPHA - Download at your own risk' }}",
              "phase": "${{ github.event.inputs.phase }}",
              "progress": "${{ github.event.inputs.progress }}",
              "fetch_release": true
            }
```

### 2. Setup Required Secrets

In the main game repository, add this secret:

- **`WEBSITE_UPDATE_TOKEN`**: GitHub personal access token with `repo` permissions for the website repository

### 3. Usage Examples

**Automatic on Release:**
- When you publish a GitHub release in the main game repo, the website automatically updates

**Manual Updates:**
- Go to Actions → "Update Website Status" 
- Run workflow with current development info
- Website will update within minutes

**From Terminal:**
```bash
# Update development phase
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/PipFoweraker/pdoom1-website/dispatches \
  -d '{
    "event_type": "update-game-status",
    "client_payload": {
      "phase": "Bug fixing sprint",
      "progress": "75% complete",
      "status": "alpha"
    }
  }'
```

## Website Status Management

### Manual Updates (Website Repository)

You can also update status directly from the website repository:

1. **GitHub Actions**: Go to Actions → "Update Game Status" → Run workflow
2. **Command Line**: 
   ```bash
   cd scripts
   node update-game-status.js --version v0.4.2 --phase "Steam preparation"
   ```
3. **Direct Edit**: Modify `public/data/status.json` and commit

### Status File Structure

```json
{
  "website": {
    "version": "1.0.0",
    "lastUpdated": "2025-09-14T23:30:00Z"
  },
  "game": {
    "status": "alpha|beta|release",
    "warning": "User warning message",
    "repository": "https://github.com/PipFoweraker/pdoom1",
    "latestRelease": {
      "version": "v0.4.1",
      "date": "2025-09-13",
      "downloadUrl": "https://github.com/PipFoweraker/pdoom1/releases/latest",
      "changelog": "Brief description"
    },
    "development": {
      "phase": "Current development focus",
      "progress": "Percentage or description",
      "nextMilestone": "Upcoming milestone"
    }
  }
}
```

### Automated Deployment

Set `AUTO_DEPLOY_ON_STATUS_UPDATE=true` in repository variables to automatically deploy to DreamHost when status updates.

## Integration Benefits

1. **Synchronized Information**: Game releases automatically update website
2. **Real-time Status**: Development progress visible to users immediately  
3. **User Safety**: Alpha warnings and disclaimers update automatically
4. **Minimal Maintenance**: Set up once, works automatically
5. **Version Consistency**: No manual sync required between repositories

## Troubleshooting

- **Updates not appearing**: Check GitHub Actions logs in both repositories
- **Permission denied**: Verify `WEBSITE_UPDATE_TOKEN` has correct permissions
- **Website not deploying**: Check DreamHost deployment secrets are configured
- **Status not loading**: Verify `data/status.json` exists and is valid JSON
