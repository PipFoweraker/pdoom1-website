# Website Development Process

## Overview
This document outlines the processes for maintaining and updating the pdoom1-website project.

## Version Management

### Semantic Versioning
- **Major (X.0.0)**: Breaking changes, major redesigns, significant feature additions
- **Minor (0.X.0)**: New features, UI improvements, content additions
- **Patch (0.0.X)**: Bug fixes, minor tweaks, content updates

### Current Status
- **Current Version**: 0.2.0 (after Phase 1-3 development sprint)
- **Package.json**: Source of truth for version number
- **Status.json**: Auto-updated from package.json during deployment

## Blog Entry Process

### For Website Development Updates
1. **Create Blog Post**: Add new `.md` file in `/public/blog/` with format: `YYYY-MM-DD-title-slug.md`
2. **Update Blog Index**: Add entry to `/public/blog/index.json` with proper metadata
3. **Tag Categories**: Use appropriate tags:
   - `website`: General website updates
   - `ui`: UI/UX improvements  
   - `infrastructure`: Deployment, CI/CD changes
   - `milestone`: Major version releases
   - `hotfix`: Bug fixes and patches

### Blog Post Format
```markdown
# Title

**Date**: YYYY-MM-DD  
**Tags**: [website, ui, milestone]  
**Commit**: [git-hash]

## Summary
Brief overview for the blog index

## Content
Full blog post content...
```

## Changelog Management

### Website Changelog (`/public/website-changelog/`)
- Records website infrastructure changes
- UI/UX improvements  
- Deployment updates
- Process improvements

### Game Changelog (`/public/game-changelog/`)
- Game releases only
- Pulled from pdoom1 repository
- Player-facing changes

## Version Update Process

### When to Increment
1. **Major Website Changes**: New design, major features → Minor version bump
2. **Infrastructure Updates**: CI/CD, deployment changes → Minor version bump  
3. **Content Updates**: Blog posts, minor fixes → Patch version bump

### Steps
1. **Update package.json**: Increment version number
2. **Update status.json**: Sync website.version with package.json
3. **Create blog entry**: Document what changed
4. **Update website changelog**: Add entry to website-changes.json
5. **Commit with version tag**: Use `git tag vX.Y.Z`

## File Locations

### Version Files
- `/package.json` - Source of truth
- `/public/data/status.json` - Displayed version
- `/public/data/website-changes.json` - Website changelog data

### Blog Files
- `/public/blog/index.json` - Blog post metadata
- `/public/blog/YYYY-MM-DD-title.md` - Individual posts

### Documentation
- `/docs/WEBSITE_DEVELOPMENT_PROCESS.md` - This file
- `/docs/deployment-guide.md` - Deployment instructions
- `/docs/style-guide.md` - Design guidelines

## Automation Scripts

### Available Commands
- `npm run update:version` - Sync version across files
- `npm run sync:all` - Update all data files  
- `npm run deploy:prepare` - Pre-deployment validation
- `npm run test:all` - Run all health checks

### Manual Updates Required
- Blog post creation (manual)
- Blog index.json updates (manual)
- Version increments (manual)

## Current Development Sprint Status

### Completed Phases
- **Phase 1**: Foundation & Game Assets Integration ✅
- **Phase 2**: Developer Blog Revolution & Content Overhaul ✅  
- **Phase 3**: UI Polish & Navigation Enhancement ✅

### Next Steps
1. Create blog entry for development sprint
2. Update version to 0.2.0
3. Update all changelog files
4. Deploy and verify

## Best Practices

1. **Always document major changes** in blog posts
2. **Test locally** before committing  
3. **Update version numbers** for significant changes
4. **Use semantic commit messages** for clear history
5. **Sync all version files** before deployment