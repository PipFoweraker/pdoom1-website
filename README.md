# p(Doom)1 Website v1.1.2

Professional website with auto-deployment, WCAG AA accessibility, weekly league system, real-time data loading, and comprehensive AI Safety resource integration for the p(Doom)1 game.

## 🆕 Latest Updates (v1.1.2)

- ✅ **Issues & Feedback Page**: Dedicated `/issues/` page with privacy-preserving submission form
- ✅ **Frontier Labs Page**: Comprehensive `/frontier-labs/` page covering 6 real + 1 hypothetical lab
- ✅ **AI Safety Links**: Stampy.ai and aisafety.info integrated throughout site
- ✅ **Performance**: Lazy loading images, preconnect hints, transparent loading states
- ✅ **Tabbed About Section**: Features/Screenshots/Requirements in organized tabs
- ✅ **Enhanced Footer**: 25+ links including sitemap, help resources, AI Safety links
- ✅ **Ownership**: Clear attribution to Pip Foweraker
- ✅ **35% Less Scrolling**: Compressed homepage with merged stats sections

## Features

### Weekly League System (v1.0.0)
- **Active Weekly Competitions**: Deterministic seed generation for fair play
- **Real-time Leaderboards**: 15 seed-specific leaderboards with 64+ entries
- **Professional API**: 8 REST endpoints with CORS support
- **Complete Automation**: 13 npm scripts for full workflow management
- **Production Ready**: 90.9% integration test success rate

### Core Integration
- **Game Repository Integration**: Real data sync from p(Doom)1 game
- **API Server**: Type-safe endpoints for leaderboards, stats, and health
- **Data Management**: Automated sync and archival systems
- **GitHub Actions Automation**: Scheduled updates, league rollover, data sync
- **Admin Monitoring Dashboard**: Real-time system status at `/monitoring/`
- **Documentation**: Comprehensive guides and specifications

### Privacy & Analytics (NEW)
- **Privacy-Preserving Analytics**: Plausible Analytics integration
- **No Cookies**: Zero personal data collection, GDPR compliant
- **User Controls**: Easy opt-out at `/privacy/`
- **Documentation**: Complete setup and implementation guides

### Social Media Syndication (NEW)
- **Automated Posting**: Blog/changelog updates auto-posted to social media
- **Multi-Platform**: Bluesky, Discord, Twitter/X, LinkedIn
- **Smart Formatting**: Platform-optimized content formatting
- **Documentation**: Complete setup and configuration guide

## Directory Structure

- `public/`: Static site assets and leaderboard data
- `scripts/`: Game integration and API server infrastructure
- `docs/`: Complete documentation and implementation guides
- `netlify/functions/`: Serverless functions (bug reporting)
- `.github/workflows/`: CI/CD pipeline and deployment automation

## Quick Start

### Development
```bash
# Start development server
npm start

# Set up game integration
npm run game:setup

# Export game data
npm run game:export

# Check integration status
npm run game:status
```

### Weekly League Management
```bash
# Check current league status
npm run league:status

# Start new weekly league
npm run league:new-week

# View current standings
npm run league:standings

# Archive completed week
npm run league:archive
```

### API Server
```bash
# Start API server
npm run api:server

# Test all endpoints
npm run api:test

# Run integration tests
npm run integration:test
```

## API Endpoints

**Production API**: `https://api.pdoom1.com` (deployed on DreamHost VPS)

### Core Endpoints
- `GET /api/health` - Server health check
- `GET /api/status` - Integration status
- `GET /api/stats` - Game statistics
- `GET /api/leaderboards/current` - Current leaderboard
- `GET /api/leaderboards/seed/{seed}` - Seed-specific data

### Weekly League Endpoints
- `GET /api/league/current` - Current weekly league
- `GET /api/league/status` - League system status
- `GET /api/league/standings` - Weekly standings

### Game Events Endpoints (NEW - 2025-11-10)
- `GET /api/events` - List all active events (with filtering)
  - Query params: `?type=combat`, `?difficulty_min=3&difficulty_max=7`, `?tags=boss,crisis`, `?limit=50&offset=0`
- `GET /api/events/{event_id}` - Get single event details
- `GET /api/events/random` - Get random event (with optional filters)

## Version Status

**v1.2.0 - PRODUCTION API & ANALYTICS** (Current - 2025-11-10)
- ✅ **Production API**: api.pdoom1.com LIVE with PostgreSQL database
- ✅ **Game Events API**: 3 new endpoints (/events, /events/{id}, /events/random) (#67)
- ✅ **Security Hardening**: PyJWT 2.10.1, OWASP Top 10 review, security audit (#68)
- ✅ **Analytics Extraction**: Automated DreamHost log extraction & archival (#61)
- ✅ **Comprehensive Documentation**: 3,862 lines (deployment, testing, integration guides)
- ✅ **GitHub Actions**: 7 workflows (analytics, forum webhook, health checks)
- ✅ Auto-deployment: LIVE (deploys on every push to main)
- ✅ WCAG 2.1 AA compliance: ACHIEVED (4/5 star rating)
- ✅ Enhanced Risk Dashboard: 8 UI improvements (#54)
- ✅ Dynamic Version Display: Auto-updates from pdoom1 releases
- ✅ Documentation Auto-Sync: pdoom1 repo docs sync every 6 hours + on release
- ✅ Weekly league infrastructure: COMPLETE
- ✅ Game repository integration: OPERATIONAL
- ✅ API server with 15 endpoints: FUNCTIONAL
- ✅ Monitoring & alerting: CONFIGURED
- ✅ Backup & recovery: DOCUMENTED
- ✅ Professional codebase: DEPLOYED

### Production Deployment

**✅ LIVE**: Production API deployed on DreamHost VPS at `https://api.pdoom1.com` (Nov 2025)

**Alternative Deployment Options**:
- **Railway**: One-click deployment with free tier
- **Render**: Auto-deploy from GitHub with generous free tier
- **Heroku**: Classic platform with robust tooling
- **Self-hosted**: Full control on VPS (current deployment)

See [DreamHost VPS Deployment Guide](docs/deployment/DREAMHOST_VPS_DEPLOYMENT.md) for production setup details.

## Next: Phase 2 - Forum & Community

**Target:** v1.2.0 (November-December 2025)

**Immediate Priority (Issue #60):**
- 🏗️ **NodeBB Forum**: Self-hosted at forum.pdoom1.com (replacing Discord)
- 🎨 **Custom Theming**: Dark theme matching pdoom1.com aesthetic
- 🔗 **Site Integration**: Forum links, latest posts on homepage
- 🏆 **Reward System**: In-game rewards for community contributors
- 📝 **Permanent Archive**: SEO-friendly, human-legible content

**Additional v1.2.0 Goals:**
- ✅ **Analytics Extraction**: DreamHost analytics → repository (Issue #61) - COMPLETE
- ✅ **Game Events API**: Dynamic event system with 3 endpoints (Issue #67) - COMPLETE
- ✅ **Security Hardening**: OWASP Top 10 review + fixes (Issue #68) - COMPLETE
- 🎯 **Event log streaming** from game sessions (pdoom-data)
- 🔐 **User authentication** (optional accounts, Steam OAuth)

See [Forum Implementation Plan](docs/FORUM_IMPLEMENTATION_ISSUE.md) and [pdoom-data Integration Plan](docs/03-integrations/pdoom-data-integration-plan.md) for detailed roadmaps.

## Automation

**GitHub Actions** handle routine maintenance automatically:
- **Auto-Update Data**: Every 6 hours - updates version info and game stats
- **Sync pdoom1 Docs**: Every 6 hours + on release - syncs documentation from game repo
- **Sync Leaderboards**: Daily at 2am UTC - syncs all leaderboard data
- **Weekly League Rollover**: Sundays at 11pm UTC - starts new competition week

**Monitor at:** [/monitoring/](https://pdoom1.com/monitoring/) - Admin dashboard for system health

See [Automation System Guide](docs/03-integrations/automation-system-guide.md) for details.

**Cross-Repository Automation:**
- pdoom1 releases trigger automatic doc sync (via repository_dispatch)
- Version updates propagate to website header automatically
- See [docs/workflows/TRIGGER_FROM_PDOOM1_REPO.yml](docs/workflows/TRIGGER_FROM_PDOOM1_REPO.yml) for webhook setup

## Documentation


### 🚀 Deployment & Operations ⭐ NEW
- [**Production Deployment Guide**](docs/02-deployment/PRODUCTION_DEPLOYMENT.md) - Complete production setup
- [**API Deployment Guide**](docs/02-deployment/API_DEPLOYMENT_GUIDE.md) - Railway, Render, Heroku, self-hosted
- [**Operations Guide**](docs/02-deployment/OPERATIONS_GUIDE.md) - Day-to-day operations and troubleshooting
- [**Backup & Recovery**](docs/02-deployment/BACKUP_RECOVERY.md) - Disaster recovery procedures
- [**Monitoring & Alerting**](docs/02-deployment/MONITORING_ALERTING.md) - Health checks and alerts
- [Weekly Deployment Schedule](docs/02-deployment/weekly-deployment-schedule.md)
- [Deployment Checklist](docs/02-deployment/weekly-deployment-checklist.md)

### 📊 Integration & Features
- [Automation System Guide](docs/03-integrations/automation-system-guide.md)
- [API Integration Guide](docs/03-integrations/api-integration-complete.md)
- [Weekly League Implementation](docs/03-integrations/weekly-league-phase1-complete.md)
- [Analytics Implementation](docs/ANALYTICS_IMPLEMENTATION.md)
- [Analytics Setup Guide](docs/ANALYTICS_SETUP.md)
- [Syndication Setup Guide](docs/SYNDICATION_SETUP.md)
- [**Syndication User Setup Guide**](docs/SYNDICATION_USER_SETUP_GUIDE.md) - Complete step-by-step guide

### 🌐 Community & Planning
- [**Forum Implementation Plan**](docs/FORUM_IMPLEMENTATION_ISSUE.md) ⭐ **NodeBB setup for forum.pdoom1.com** (Issue #60)
- [**Analytics Extraction**](docs/ANALYTICS_EXTRACTION_ISSUE.md) - DreamHost analytics collation (Issue #61)
- [Dashboard Improvements](docs/DASHBOARD_IMPROVEMENTS_ISSUE_54.md) - Risk dashboard UI enhancements (Issue #54)


## Automated Systems

### Weekly League Reset (Automated)

**Schedule**: Every Monday at 00:00 AEST (Sunday 14:00 UTC)

Fully automated via GitHub Actions:
1. Archives previous week's results
2. Generates new competitive seed (deterministic)
3. Starts new weekly league
4. Syncs game data
5. Commits and deploys changes

**Manual trigger** (if needed):
```bash
npm run league:archive    # Archive current week
npm run league:new-week   # Start new week
npm run game:weekly-sync  # Sync game data
```

### Weekly Deployment (Automated)

**Schedule**: Every Friday at 4:00 PM AEST (06:00 UTC)

The p(Doom)1 website follows a predictable weekly deployment rhythm:
- **Monday 00:00 AEST**: New weekly league starts automatically
- **Tuesday-Thursday**: Development, balance changes, and testing
- **Thursday 17:00 AEST**: Code freeze for Friday release
- **Friday 14:00 AEST**: Pre-deployment checks begin
- **Friday 16:00 AEST**: Production deployment
- **Friday 16:30 AEST**: Live Twitch stream showcasing updates

**Manual deployment commands**:
```bash
# Prepare for deployment
npm run deploy:prep-weekly

# Quick status check
npm run deploy:check

# Fast verification
npm run deploy:quick-check
```

### Health Checks (Automated)

**Schedule**: Every 6 hours

Automated monitoring via GitHub Actions:
- File integrity checks
- JSON validation
- Script execution tests
- Security scans
- Performance metrics

**Alerts**: Automatically creates GitHub issues on failures

For detailed schedule and procedures, see [Weekly Deployment Schedule](docs/02-deployment/weekly-deployment-schedule.md).