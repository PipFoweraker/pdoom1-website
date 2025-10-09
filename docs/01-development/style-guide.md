# Style & Design Guide (website)

Purpose: document the website's design tokens and how they map to the main game's design system.

## Tokens
- Source: `public/design/tokens.json` at runtime
- Applied via inline script in `public/index.html` (loadTokens)
- Token groups:
  - colors: bgPrimary, textPrimary, accentPrimary, etc.
  - shape: radii, borderWidth, shadowButton
  - motion: durationFast, durationBase, easing

## Integration with `pdoom1` main repo
- **Canonical source**: `PipFoweraker/pdoom1` repository (main game repo)
- **Sync strategy**: Automated via GitHub Actions workflow
  - Workflow: `.github/workflows/sync-design-tokens.yml`
  - Trigger: Manual dispatch or repository_dispatch event from main repo
  - Process: Copies `tokens.json` from pdoom1 to `public/design/tokens.json` in this repo
  - Can sync from any ref (branch, tag, or commit SHA) in the main repo

### Syncing Tokens

**Manual Sync:**
1. Go to Actions → "Sync Design Tokens from pdoom1"
2. Click "Run workflow"
3. Specify the ref (tag, branch, or SHA) from the main repo
4. Workflow will copy tokens.json and commit if changes detected

**Automatic Sync (from main repo):**
- The main pdoom1 repo can trigger this workflow on releases/tags using `repository_dispatch`
- Event type: `sync-tokens`
- Payload: `{ "ref": "v1.2.3" }`

**Example: Triggering from main repo**
```yaml
# In PipFoweraker/pdoom1/.github/workflows/release.yml
- name: Notify website to sync tokens
  run: |
    curl -X POST \
      -H "Authorization: token ${{ secrets.WEBSITE_SYNC_TOKEN }}" \
      -H "Accept: application/vnd.github.v3+json" \
      https://api.github.com/repos/PipFoweraker/pdoom1-website/dispatches \
      -d '{"event_type":"sync-tokens","client_payload":{"ref":"${{ github.ref_name }}"}}'
```

## Components
- Pure HTML/CSS with small inline JS; monospace aesthetic
- Cards, grids, CTA buttons, form controls

## Accessibility
- Ensure semantic headings and labels
- Focus states with visible outlines
- Contrast ratio >= 4.5:1

## Content surfaces
- Blog at `/blog/` from `public/data/blog.json`
- Changelog at `/changelog/` from `public/data/changes.json`

## Next
- Document color usage and states
- Map tokens to game UI atoms for consistency
