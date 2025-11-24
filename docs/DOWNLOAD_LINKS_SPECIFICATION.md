# Download Links Specification

**Project**: pdoom1-website
**Purpose**: Specify required download file formats and hosting strategy
**Last Updated**: 2025-11-24

---

## Overview

The pdoom1.com website provides download links for the PDoom game across three platforms: Windows, macOS, and Linux. This document specifies the required file formats and hosting configuration.

## Hosting Strategy

**Method**: GitHub Releases (CDN hosting)
**Rationale**:
- ✅ No bandwidth costs to pdoom1.com (saves Netlify quota)
- ✅ GitHub CDN provides fast, reliable downloads globally
- ✅ Automatic versioning with `/latest/download/` URLs
- ✅ Download tracking works via Plausible Analytics (configured in index.html)

## Required Release Files

When creating a new release in the [pdoom1 game repository](https://github.com/PipFoweraker/pdoom1), the following files must be uploaded as release assets:

### Windows
- **Filename**: `PDoom-Windows.zip`
- **Format**: ZIP archive containing:
  - `PDoom.exe` (executable)
  - All required DLL files
  - Any data/asset folders needed for gameplay
- **Reason**: ZIP format ensures players get all necessary files (exe + dependencies) for a working installation
- **Download URL**: `https://github.com/PipFoweraker/pdoom1/releases/latest/download/PDoom-Windows.zip`

### macOS
- **Filename**: `PDoom.app.zip`
- **Format**: ZIP archive containing the `.app` bundle
- **Download URL**: `https://github.com/PipFoweraker/pdoom1/releases/latest/download/PDoom.app.zip`

### Linux
- **Filename**: `PDoom.x86_64`
- **Format**: Single executable binary (AppImage or standalone)
- **Download URL**: `https://github.com/PipFoweraker/pdoom1/releases/latest/download/PDoom.x86_64`

## Download Tracking

Download clicks are automatically tracked using Plausible Analytics with the following custom event properties:

```javascript
plausible('Download', {
  props: {
    version: currentVersion,  // e.g., "v0.10.5"
    platform: 'Windows',       // or 'macOS', 'Linux'
    file: 'PDoom-Windows.zip'  // actual filename
  }
});
```

This tracking is configured in `public/index.html` (lines 1524-1585) and uses the Plausible script with file-downloads extension (line 27).

## Implementation Details

### index.html Download Buttons

Located in `public/index.html` (lines 884-892):

```html
<!-- Windows -->
<a id="download-windows"
   href="https://github.com/PipFoweraker/pdoom1/releases/latest/download/PDoom-Windows.zip"
   class="cta-button">
  Download for Windows
</a>

<!-- macOS -->
<a id="download-macos"
   href="https://github.com/PipFoweraker/pdoom1/releases/latest/download/PDoom.app.zip"
   class="cta-button">
  Download for macOS
</a>

<!-- Linux -->
<a id="download-linux"
   href="https://github.com/PipFoweraker/pdoom1/releases/latest/download/PDoom.x86_64"
   class="cta-button">
  Download for Linux
</a>
```

### Plausible Analytics Configuration

Located in `public/index.html` (line 27):

```html
<script defer
  data-domain="pdoom1.com"
  src="https://analytics.pdoom1.com/js/script.file-downloads.outbound-links.pageview-props.tagged-events.js">
</script>
```

The `file-downloads` extension automatically tracks clicks on download links.

## Build Process Requirements (pdoom1 Game Repo)

The pdoom1 game repository's GitHub Actions workflow or manual release process **must**:

1. **Build Windows artifacts**:
   - Create executable + dependencies
   - Package into `PDoom-Windows.zip`
   - Upload to GitHub release

2. **Build macOS artifacts**:
   - Create `.app` bundle
   - Package into `PDoom.app.zip`
   - Upload to GitHub release

3. **Build Linux artifacts**:
   - Create standalone executable
   - Name as `PDoom.x86_64`
   - Upload to GitHub release

4. **Use consistent naming**:
   - Filenames must match exactly (case-sensitive)
   - Use `/latest/download/` links (not version-specific)

## Verification Checklist

Before releasing a new game version:

- [ ] Windows: `PDoom-Windows.zip` exists in release assets
- [ ] macOS: `PDoom.app.zip` exists in release assets
- [ ] Linux: `PDoom.x86_64` exists in release assets
- [ ] All files downloadable from `/releases/latest/download/`
- [ ] Test download links on pdoom1.com
- [ ] Verify Plausible Analytics tracks downloads (check dashboard)

## Troubleshooting

### Download Link Returns 404

**Cause**: Release asset filename doesn't match expected name
**Solution**: Re-upload release asset with correct filename, or update `index.html` links

### Downloads Not Tracked in Analytics

**Cause**: Plausible script not loaded or event not firing
**Solution**:
1. Check browser console for JavaScript errors
2. Verify Plausible script loads (Network tab)
3. Check `setupDownloadTracking()` function is called

### Windows Users Report Missing Files

**Cause**: Distributed `.exe` only without dependencies
**Solution**: Ensure Windows release is packaged as `.zip` with all required files

## Related Files

- `public/index.html` - Download button HTML and tracking JavaScript
- `.github/workflows/update-game-data.yml` - Fetches release metadata (not binaries)
- `DEPLOYMENT_INSTRUCTIONS.md` - Website deployment process

## Future Considerations

### Alternative: Self-Hosted Downloads

If GitHub hosting becomes problematic, we could self-host downloads:

1. Create `public/downloads/` directory
2. Add GitHub Action to sync releases:
   ```yaml
   - name: Download latest releases
     run: |
       wget https://github.com/PipFoweraker/pdoom1/releases/latest/download/PDoom-Windows.zip
       mv PDoom-Windows.zip public/downloads/
   ```
3. Update links to `/downloads/PDoom-Windows.zip`

**Pros**: Full control, faster tracking
**Cons**: Uses Netlify bandwidth (100GB/month free tier), requires sync workflow

### Bandwidth Estimation

Average file sizes (estimated):
- Windows ZIP: ~50MB
- macOS ZIP: ~60MB
- Linux executable: ~45MB

Netlify free tier: 100GB/month
Max downloads/month: ~1,500-2,000 (if self-hosted)

Current GitHub hosting: **Unlimited** (within GitHub's fair use policy)

---

**Status**: ✅ Implemented
**Updated**: 2025-11-24
**Contact**: See [GitHub Issues](https://github.com/PipFoweraker/pdoom1-website/issues)
