# Versioning & Changelog Guide

**Purpose**: Ensure consistent versioning and changelog maintenance for p(Doom)1 website releases.

---

## Quick Reference

### When to Update Version

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `feat:` - New feature | **MINOR** (1.1.0 → 1.2.0) | Quote infrastructure, new events system |
| `fix:` - Bug fix | **PATCH** (1.1.0 → 1.1.1) | Fix broken links, correct typos |
| `BREAKING:` - Breaking change | **MAJOR** (1.0.0 → 2.0.0) | API changes, major restructure |
| `chore:`, `docs:`, `style:` | **NONE** | Refactoring, documentation, formatting |

### Version Bump Commands

```bash
# Patch version (bug fixes)
npm version patch

# Minor version (new features)
npm version minor

# Major version (breaking changes)
npm version major
```

---

## Step-by-Step Workflow

### For Feature/Fix Commits

1. **Make your changes**
   ```bash
   git add .
   git commit -m "feat: Add quote infrastructure"
   ```

2. **Update version** (automatically updates package.json)
   ```bash
   npm version minor  # for feat:
   # or
   npm version patch  # for fix:
   ```

3. **Update CHANGELOG.md**
   - Add new section with version number and date
   - List all changes under appropriate headings (Added, Changed, Fixed, etc.)
   - See format below

4. **Commit changelog**
   ```bash
   git add CHANGELOG.md
   git commit --amend --no-edit  # Add to version bump commit
   ```

5. **Push to main**
   ```bash
   git push origin main
   git push --tags  # Push the version tag
   ```

---

## CHANGELOG.md Format

```markdown
## [1.2.0] - 2025-11-24

### Added - Brief Summary

**Feature Category**
- **Feature Name**: Description
  - Detail 1
  - Detail 2
- **Another Feature**: Description

### Changed

**What Changed**
- **Component**: What was modified and why

### Fixed

**Bug Fixes**
- **Issue**: What was broken and how it was fixed

### Impact

- Key metric or outcome
- User-facing improvements
```

### Example Entry

```markdown
## [1.2.0] - 2025-11-24

### Added - Quote Provenance Infrastructure

**Visual Provenance System**
- **Provenance Badges**: Color-coded badges on all event pages
  - 🟠 Orange: Placeholder quotes
  - 🟢 Green: Verified quotes
- **Quote Suggestion Form**: Community contribution workflow

### Impact

- Baseline established: 1028 events with placeholder tracking
- Infrastructure ready for systematic quote mining
```

---

## Semantic Versioning Rules

We follow [Semantic Versioning 2.0.0](https://semver.org/):

**MAJOR.MINOR.PATCH**

### MAJOR (X.0.0)

**Increment when**:
- Breaking changes to public API
- Major architectural changes
- Incompatible changes requiring user action

**Examples**:
- Migrating from static site to server-rendered
- Changing event data schema (breaking existing integrations)
- Removing public endpoints

### MINOR (1.X.0)

**Increment when**:
- Adding new features (backwards compatible)
- New pages or sections
- New functionality

**Examples**:
- Adding quote infrastructure (1.1.0 → 1.2.0)
- New events system (1.2.0 → 1.3.0)
- Community contribution features

### PATCH (1.1.X)

**Increment when**:
- Bug fixes
- Small improvements
- Documentation updates (if significant)

**Examples**:
- Fixing broken links (1.1.0 → 1.1.1)
- Correcting typos in events (1.1.1 → 1.1.2)
- Accessibility contrast fixes

---

## Automation

### Pre-commit Hook

Located at `.husky/pre-commit`

**What it does**:
- Checks commit message for `feat:` or `fix:`
- Reminds you to update version and changelog
- Prompts to continue or cancel

**Skip if needed**:
```bash
git commit --no-verify -m "..."
```

### GitHub Action

Located at `.github/workflows/version-check.yml`

**What it does**:
- Runs on PRs and pushes to main
- Checks if version was bumped for feature/fix commits
- Checks if CHANGELOG.md was updated
- Fails the check if forgotten
- Comments on PR with reminder

**Bypass** (use sparingly):
- Add `[skip version-check]` to commit message

---

## Git Tags

### Creating Tags

When you run `npm version minor`, it automatically:
1. Bumps version in `package.json`
2. Creates a git commit
3. Creates a git tag (e.g., `v1.2.0`)

### Pushing Tags

```bash
# Push tags to remote
git push --tags

# Or push commit and tags together
git push origin main --follow-tags
```

### Viewing Tags

```bash
# List all tags
git tag

# Show specific tag
git show v1.2.0

# List tags with dates
git log --tags --simplify-by-decoration --pretty="format:%ai %d"
```

---

## Release Notes

### GitHub Releases

After pushing a tag, create a GitHub release:

1. Go to https://github.com/PipFoweraker/pdoom1-website/releases
2. Click "Draft a new release"
3. Select your tag (e.g., `v1.2.0`)
4. Copy relevant section from CHANGELOG.md
5. Add any additional notes
6. Publish release

### Auto-Release (Future)

Consider using GitHub Action to auto-generate releases from CHANGELOG.md:

```yaml
name: Create Release
on:
  push:
    tags:
      - 'v*'
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Create Release
        uses: actions/create-release@v1
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          body_path: CHANGELOG.md
```

---

## Common Scenarios

### Scenario 1: Multiple Features in One Release

```bash
# Work on features
git commit -m "feat: Add quote infrastructure"
git commit -m "feat: Add contribution guide"
git commit -m "feat: Add analytics tracking"

# Bump version once for all features
npm version minor

# Update CHANGELOG with all features
# Then amend the version commit
git add CHANGELOG.md
git commit --amend --no-edit

# Push
git push origin main --tags
```

### Scenario 2: Hotfix After Release

```bash
# Fix urgent bug
git commit -m "fix: Broken quote suggestion form"

# Patch version
npm version patch  # 1.2.0 → 1.2.1

# Quick changelog update
git add CHANGELOG.md
git commit --amend --no-edit

# Push immediately
git push origin main --tags
```

### Scenario 3: Pre-release Versions

```bash
# For beta/alpha releases
npm version prerelease --preid=beta
# Result: 1.2.0 → 1.2.1-beta.0

npm version prerelease
# Result: 1.2.1-beta.0 → 1.2.1-beta.1

# When ready for stable
npm version patch
# Result: 1.2.1-beta.1 → 1.2.1
```

---

## Versioning Checklist

Before committing a feature or fix:

- [ ] Commit changes with conventional commit message
- [ ] Run `npm version patch/minor/major`
- [ ] Update CHANGELOG.md with new version section
- [ ] Amend version commit to include changelog
- [ ] Push commit and tags
- [ ] (Optional) Create GitHub release
- [ ] Verify deployment completed

---

## Integration with CI/CD

### Auto-Update Version Info

The `update-version-info.py` script runs on deployment:

```bash
npm run update:version
```

**What it does**:
- Reads version from package.json
- Updates public-facing version displays
- Generates version metadata

**Triggered by**:
- GitHub Actions on push
- Manual deployment scripts

---

## Troubleshooting

### Forgot to Update Version

```bash
# If you already committed
git reset --soft HEAD~1  # Undo commit, keep changes
npm version minor
git add CHANGELOG.md
git commit -m "feat: Your feature + version bump"
```

### Wrong Version Bumped

```bash
# Delete local tag
git tag -d v1.2.0

# Re-run correct version bump
npm version patch  # Instead of minor

# If already pushed
git push --delete origin v1.2.0
```

### Merge Conflicts in CHANGELOG

```bash
# Accept both changes
git checkout --ours CHANGELOG.md    # Keep your version
git checkout --theirs CHANGELOG.md  # Keep their version

# Or manually merge, then:
git add CHANGELOG.md
git commit
```

---

## Best Practices

1. **Update CHANGELOG as you code** - Don't wait until commit time
2. **Be specific** - "Fix bug" → "Fix broken quote form validation"
3. **Group related changes** - One version bump for related features
4. **Use pre-releases for experiments** - Don't jump to 2.0.0 prematurely
5. **Tag strategically** - Tags are permanent, make them meaningful
6. **Keep changelog user-focused** - Write for users, not developers
7. **Link to issues/PRs** - Include GitHub links for context

---

## Related Documentation

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [npm version docs](https://docs.npmjs.com/cli/v9/commands/npm-version)

---

**Status**: ✅ Active
**Last Updated**: 2025-11-24
**Maintained By**: Development team
