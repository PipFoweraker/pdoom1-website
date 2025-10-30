# Changelog - pdoom1-website

All notable changes to the pdoom1 website will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.1] - 2025-10-30

### Added - CI/CD & Accessibility

**Auto-Deployment Infrastructure**
- **auto-deploy-on-push.yml**: Automatic deployment to DreamHost on every push to main
  - Triggers only when `public/` files or sitemap generator changes
  - Full rsync deployment with detailed logging
  - Error handling and secret validation
  - Estimated 2-3 minute deployment time
- **Workflows README**: Comprehensive guide to all deployment and automation workflows
  - Documents all 4 deployment methods (auto, version-aware, simple, manual)
  - Setup instructions for DreamHost secrets
  - Cost analysis (well within GitHub free tier)
  - Troubleshooting guide

**Accessibility Improvements (WCAG 2.1 AA Compliance)**
- **Accessibility Audit Document**: Comprehensive 200+ line audit (`docs/01-development/ACCESSIBILITY_AUDIT.md`)
  - Full WCAG 2.1 AA compliance checklist
  - Color contrast analysis for all theme colors
  - Testing recommendations (axe, WAVE, Lighthouse, pa11y)
  - Action items prioritized by impact
  - Overall rating: 4/5 stars
- **Fixed text-muted contrast**: Changed from #888888 (3.9:1 - FAILS) to #aaaaaa (5.6:1 - PASSES AA)
  - Improves readability for vision-impaired users
  - Maintains design aesthetic while meeting standards

**Existing Accessibility Features Verified**
- ✅ Skip-to-content link with proper focus handling
- ✅ Comprehensive ARIA labels and semantic HTML
- ✅ Enhanced focus indicators (2px outline + offset)
- ✅ `prefers-reduced-motion` support (disables animations)
- ✅ `prefers-contrast: high` mode (increased contrast colors)
- ✅ Keyboard navigation throughout site
- ✅ Form validation with aria-invalid states

**Planning & Documentation**
- **pdoom-data Integration Plan**: 400+ line comprehensive integration roadmap
  - Event log streaming architecture
  - Global leaderboards migration strategy
  - User authentication system design
  - Privacy & GDPR compliance framework
  - 4-phase implementation timeline
  - Risk assessment and mitigation strategies

### Changed

**UI Improvements**
- Removed "Home" breadcrumb from navigation (cleaner header)
- Reduced padding by 20% across all major layout elements:
  - Header, nav, main, hero, sections, cards, grids, forms, footer
  - Inline padding styles in dynamic sections
  - Creates denser, more professional layout
  - Improves mobile-friendliness with tighter spacing

**Documentation Updates**
- Updated README to v1.1.1 with current features
- Added "Next: Phase 2 - pdoom-data Integration" section
- Documented auto-deployment setup
- Listed all accessibility achievements

### Infrastructure

**Continuous Deployment**
```
Developer pushes to main
  → GitHub Actions detects public/ changes
    → Runs auto-deploy-on-push.yml
      → Generates sitemap
        → rsync to DreamHost
          → Site live at https://pdoom1.com
```

**Cost Analysis**
- GitHub Actions: ~5-10 deployments/day × 2 min = 300-600 min/month
- Well within free tier (2,000 minutes/month)
- DreamHost bandwidth: Included with hosting
- Total cost: $0 for automation infrastructure

### Accessibility

**WCAG 2.1 AA Compliance Status**

Perceivable:
- ✅ 1.1.1 Non-text Content (Alt text)
- ✅ 1.3.1 Info and Relationships (Semantic HTML, ARIA)
- ✅ 1.4.3 Contrast (Minimum) - Now passes with 5.6:1
- ✅ 1.4.4 Resize Text (200% zoom works)
- ✅ 1.4.10 Reflow (Responsive design)

Operable:
- ✅ 2.1.1 Keyboard (Full keyboard access)
- ✅ 2.1.2 No Keyboard Trap
- ✅ 2.4.1 Bypass Blocks (Skip link)
- ✅ 2.4.2 Page Titled
- ✅ 2.4.7 Focus Visible

Understandable:
- ✅ 3.1.1 Language of Page
- ✅ 3.3.1 Error Identification
- ✅ 3.3.2 Labels or Instructions

Robust:
- ✅ 4.1.2 Name, Role, Value
- ✅ 4.1.3 Status Messages

---

## [1.1.0] - 2025-10-30

### Added - Automation & Dynamic Front Page

**GitHub Actions Automation System**
- **auto-update-data.yml**: Automatically updates version info and game stats every 6 hours
- **sync-leaderboards.yml**: Daily leaderboard data sync from game repository (2am UTC)
- **weekly-league-rollover.yml**: Automatic weekly league management (Sundays 11pm UTC)
- **log-automation-run.py**: Centralized logging system for all automation runs
- Automation status tracking via `/monitoring/data/automation-status.json` and `automation-runs.json`

**Enhanced Monitoring Dashboard** (`/monitoring/`)
- New "Automation Status" section showing GitHub Actions job success rates
- New "Weekly League Management" section with current week info and manual controls
- Real-time data loading from automation logs
- Clear labeling as "Admin & Operations Dashboard"

**Dynamic Front Page**
- **Live Game Status Section**: New prominent section showing real-time game state
  - Current version with release date and open issues count
  - Weekly league status with time remaining and participant count
  - Last updated timestamp showing data freshness
- **Loading States**: Shimmer animations while data loads (no more stale hardcoded values)
- **Dynamic Stats**: All three main stats (Baseline Doom, Frontier Labs, Strategic Possibilities) load from live data
- **Smart Download Buttons**: Automatically update with latest version number and link
- **Auto-refresh**: All data fetched fresh on every page load
- Error handling with graceful fallbacks

**Documentation**
- `docs/03-integrations/automation-system-guide.md`: 400+ line comprehensive automation guide
- `docs/03-integrations/2025-10-30-automation-deployment.md`: Deployment record and handoff doc
- Updated README with automation info and monitoring dashboard link

### Changed

**Front Page Improvements**
- Replaced hardcoded version numbers ("0.1.0") with dynamic loading
- Replaced static stats with live data from `/data/version.json`
- Added weekly league data loading from `/leaderboard/data/weekly/current.json`
- Improved UX with loading placeholders and animations

**Monitoring Dashboard**
- Enhanced with two new major sections for automation and league management
- Added subtitle: "Admin & Operations Dashboard - Infrastructure monitoring and automation status"
- Integrated automation log display

**README.md**
- Added "Automation" section explaining GitHub Actions workflows
- Added link to `/monitoring/` dashboard
- Added reference to automation system guide

### Infrastructure

**Three-Tier Automation Philosophy**
- **Tier 1 (Fully Automatic)**: Routine maintenance, issue on failure only
- **Tier 2 (Auto-execute with Notification)**: Important events, always creates issue
- **Tier 3 (Manual Approval)**: Critical operations requiring human judgment

**Monitoring & Observability**
- All automation runs logged to `/monitoring/data/`
- GitHub issues created for failures and important events
- Success rates tracked per job
- Dashboard provides real-time status visibility

**Data Flow**
```
GitHub Actions (scheduled)
  → Python scripts (version, stats, leaderboards, league)
    → JSON data files (public/data/, public/leaderboard/data/)
      → Auto-commit to repo
        → Front page loads fresh data
          → Users see live info
```

### Technical Details

**New Files**
- `.github/workflows/auto-update-data.yml`
- `.github/workflows/sync-leaderboards.yml`
- `.github/workflows/weekly-league-rollover.yml`
- `scripts/log-automation-run.py`
- `public/monitoring/data/automation-status.json`
- `public/monitoring/data/automation-runs.json`
- `docs/03-integrations/automation-system-guide.md`
- `docs/03-integrations/2025-10-30-automation-deployment.md`
- `CHANGELOG.md` (this file)

**Modified Files**
- `public/index.html` (dynamic loading, Live Status section)
- `public/monitoring/index.html` (automation sections)
- `README.md` (automation documentation)
- `package.json` (version bump to 1.1.0)

### Developer Notes

**Manual Operations Still Available**
- All npm scripts still work for manual execution
- `npm run league:archive` / `npm run league:new-week`
- `npm run game:sync-all`
- `npm run update:version` / `npm run update:stats`

**Monitoring**
- Check `/monitoring/` for automation health
- GitHub Issues with label `automation` for notifications
- Success target: >95% for all jobs

---

## [1.0.0] - 2025-10-09

### Added - Weekly League System (Production Release)

**Weekly League Infrastructure**
- Deterministic seed generation for fair competition
- Automatic archival system for completed weeks
- Season management (quarters: Q1, Q2, Q3, Q4)
- 15 seed-specific leaderboards with 64+ entries
- Complete npm script workflow (13 scripts)

**API Server**
- 8 REST endpoints (5 core + 3 league-specific)
- `/api/league/current` - Current weekly competition
- `/api/league/status` - League system status
- `/api/league/standings` - Competition standings
- CORS support for cross-origin requests
- Type-safe implementations with comprehensive annotations

**Game Integration**
- Real data sync from p(Doom)1 game repository
- Bulk leaderboard sync capability
- Weekly league synchronization
- Integration testing suite (90.9% success rate)

**Documentation**
- API Integration Guide
- Weekly League Implementation docs
- Deployment ready documentation
- Professional codebase with type annotations

### Changed
- Enhanced `game-integration.py` with `--sync-leaderboards` and `--weekly-sync`
- Updated all Python scripts with production-grade error handling
- Cleaned all Unicode characters for cross-platform compatibility

---

## [0.2.1] - 2025-09-30

### Fixed
- Version-aware deployment system validation
- Test patch deployment improvements
- Documentation reorganization for clarity

---

## [0.2.0] - 2025-09-15

### Added
- Multi-repository integration complete
- UI monolith breakdown
- Hotfix batch deployment system
- Cross-repository documentation strategy

---

## [0.1.0] - 2025-09-09

### Added - Initial Website Launch
- Static site with game information
- Basic leaderboard display
- AI Safety resources section
- Development blog
- Game statistics page
- About and press kit pages

---

**Version Numbering**
- **Major (X.0.0)**: Breaking changes, major feature additions
- **Minor (0.X.0)**: New features, backwards compatible
- **Patch (0.0.X)**: Bug fixes, minor improvements
