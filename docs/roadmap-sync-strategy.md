# Roadmap Synchronization with pdoom1 Repository

This document explains how the roadmap is kept in sync with the main game repository and GitHub milestones.

## Overview

The roadmap on this website is automatically synchronized with GitHub milestones from the main game repository (`PipFoweraker/pdoom1`). This ensures that the roadmap reflects the actual development planning and progress.

## Architecture

```
PipFoweraker/pdoom1 (Game Repo)
├── GitHub Milestones (source of truth)
├── Issues assigned to milestones
└── Development planning

        ↓ (automated sync)

PipFoweraker/pdoom1-website (Website Repo)
├── docs/roadmap.md (generated)
├── scripts/generate_roadmap_from_milestones.js
└── Navigation links to roadmap
```

## Sync Process

### Automatic Generation
The roadmap is generated using the script `scripts/generate_roadmap_from_milestones.js` which:

1. **Fetches milestones** from the main game repository via GitHub API
2. **Gets associated issues** for each milestone to show progress
3. **Generates markdown** with milestone information, progress, and remaining tasks
4. **Maintains backup** of the previous roadmap version
5. **Falls back gracefully** when GitHub API is unavailable

### Manual Update Process

To update the roadmap manually:

```bash
# From the website repository root
npm run generate:roadmap
```

Or directly:
```bash
node scripts/generate_roadmap_from_milestones.js
```

### GitHub Actions (Recommended)

For automated updates, add a GitHub Action that runs the script periodically:

```yaml
name: Update Roadmap
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC
  workflow_dispatch:       # Manual trigger

jobs:
  update-roadmap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Update roadmap
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: npm run generate:roadmap
      - name: Commit changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add docs/roadmap.md
          git diff --staged --quiet || git commit -m "Auto-update roadmap from milestones"
          git push
```

## Cross-Repository Relationship

### Source Repository (PipFoweraker/pdoom1)
- **Primary development** happens here
- **Milestones** define roadmap structure
- **Issues** provide detailed tasks and progress tracking
- **Releases** mark completion of milestone goals

### Website Repository (PipFoweraker/pdoom1-website)
- **Mirrors roadmap** from game repository milestones
- **Provides user-friendly presentation** of development plans
- **Links back to source** for detailed information
- **Maintains documentation** about the relationship

## Milestone Management Guidelines

### For Game Repository Maintainers

When creating milestones in the game repository:

1. **Use clear titles** that work as roadmap section headers
2. **Add descriptions** that explain the milestone goals
3. **Set due dates** when possible for timeline planning
4. **Assign issues** to milestones for progress tracking
5. **Use consistent naming** (e.g., "v0.1.0 - Website Polish")

### Recommended Milestone Structure

```
v0.0.x (Alpha) - Current Development
├── Description: Current alpha phase goals
├── Due Date: Ongoing
└── Issues: Current sprint tasks

v0.1.0 - Website Polish
├── Description: Improve website accessibility and SEO
├── Due Date: Target date
└── Issues: Website-related improvements

v0.2.0 - Steam Readiness
├── Description: Prepare game for Steam release
├── Due Date: Target date
└── Issues: Steam integration tasks
```

## Fallback Strategy

The system includes multiple fallback mechanisms:

1. **GitHub API available** → Generate from live milestones
2. **GitHub API unavailable** → Use static fallback roadmap
3. **Script fails** → Restore from backup file
4. **No backup available** → Keep existing roadmap unchanged

## Maintenance

### Regular Tasks
- **Monitor GitHub API rate limits** if running frequent updates
- **Review milestone descriptions** for clarity and user-friendliness
- **Update fallback roadmap** when major changes occur
- **Test the sync process** after repository changes

### Troubleshooting

**Script fails with authentication error:**
- Ensure `GH_TOKEN` environment variable is set
- Verify GitHub CLI is authenticated: `gh auth status`

**Generated roadmap is empty:**
- Check if milestones exist in the source repository
- Verify repository name is correct in the script
- Confirm API access permissions

**Formatting issues:**
- Review milestone descriptions for markdown conflicts
- Check for special characters in milestone titles
- Verify issue labels are properly formatted

## Benefits

### For Users
- **Transparent development** progress visible on website
- **Up-to-date information** without manual maintenance
- **Direct links** to detailed GitHub issues
- **Clear timeline** with milestone due dates

### For Developers
- **Single source of truth** for roadmap planning
- **Automatic synchronization** reduces manual work
- **Consistent presentation** across platforms
- **Easy maintenance** through existing GitHub workflow

## Implementation Notes

This synchronization strategy implements the broader cross-repository documentation pattern described in `CROSS_REPOSITORY_DOCUMENTATION_STRATEGY.md`, specifically for roadmap content.

The approach maintains the website as a presentation layer while keeping the source repository as the authoritative source for development planning and progress tracking.