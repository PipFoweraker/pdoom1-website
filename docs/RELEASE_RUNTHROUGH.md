# Release run-through checklist

Use this when the `pdoom1` game ships a new release, to confirm the website reflects it correctly. The site reads the game's **latest GitHub release** — it does not need a website deploy to pick up a new game version, but a few things are worth verifying by eye.

## How version info flows
- `scripts/update-version-info.py` (run every 6h by `.github/workflows/auto-update-data.yml`) fetches the game repo's `releases/latest` and writes `public/data/version.json`. It also syncs the release block into `public/data/status.json` (guarded against API-failure fallback).
- Client-side, pages fetch `public/data/version.json` and update their version display:
  - Homepage nav badge + footer + hero download buttons → inline scripts in `public/index.html`.
  - Homepage hero **stats** (doom %, frontier labs, strategic possibilities) → `loadGameStats()` in `public/index.html`.
  - The 7 pages using the injected nav (about, blog, cats, game-changelog, game-stats, issues, leaderboard) → `updateNavVersion()` in `public/assets/js/navigation.js`.

## When a new release lands — verify

1. **Release is actually tagged/published.** The site follows *published releases*, not commits. If the game team merged the "massive update" but hasn't cut a release, the site correctly still shows the previous release. Cut the release first.

2. **Download links resolve.** Buttons point at `github.com/PipFoweraker/pdoom1/releases/latest/download/<asset>`:
   - `PDoom-Windows.zip`
   - `PDoom.app.zip`
   - `PDoom.x86_64`
   ⚠️ If the new release renames these assets, the `latest/download/...` links will 404. Either keep the asset filenames stable, or update the three hrefs in `public/index.html` (ids `download-windows` / `download-macos` / `download-linux`).

3. **Let the auto-updater run (or trigger it).** Either wait for the 6-hourly `auto-update-data.yml`, or run it manually (`workflow_dispatch`) / locally: `python scripts/update-version-info.py`. Confirm `public/data/version.json` shows the new `latest_release.version`.

4. **Spot-check version display** on a few pages (hard-refresh to bypass cache):
   - Homepage: nav badge, footer, and the three hero stat numbers populate (not `--`).
   - One injected-nav page (e.g. `/leaderboard/`): nav badge shows the new version, not the hardcoded fallback.

5. **Changelog / release notes.** Check `public/game-changelog/` and `CHANGELOG.md` reflect the new release (these may be Airtable-synced or manual — confirm the source).

6. **CHANGELOG version-gate CI.** `version-check.yml` fails PRs with `feat:`/`fix:` commits that don't bump the CHANGELOG — expect it to be relevant for the website's own changes, not the game release.

## Known follow-ups (not blockers)
- Blog/changelog content is **Airtable-sourced** (`sync_airtable.py`); refresh at source, not by editing `public/data/*.json`.
- The website's own version scheme is muddled (`status.json` website `0.2.1` vs `CHANGELOG.md` `1.2.0`) — pick a canonical scheme when convenient.
- `public/includes/navigation.html` is an unused legacy include; the live nav is `public/assets/js/navigation.js`.
