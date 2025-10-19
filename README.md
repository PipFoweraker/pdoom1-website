# p(Doom)1 Website v1.0.0

Professional website with weekly league competition system for the p(Doom)1 game.

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

### Core Endpoints
- `GET /api/health` - Server health check
- `GET /api/status` - Integration status
- `GET /api/stats` - Game statistics
- `GET /api/leaderboards/current` - Current leaderboard
- `GET /api/leaderboards/seed/{seed}` - Seed-specific data

### Weekly League Endpoints (NEW)
- `GET /api/league/current` - Current weekly league
- `GET /api/league/status` - League system status
- `GET /api/league/standings` - Weekly standings

## Version Status

**v1.0.0 - PRODUCTION READY**
- ✅ Weekly league infrastructure: COMPLETE
- ✅ Game repository integration: OPERATIONAL
- ✅ API server with 8 endpoints: FUNCTIONAL
- ✅ Automated management system: READY
- ✅ Production deployment configs: READY
- ✅ Monitoring & alerting: CONFIGURED
- ✅ Backup & recovery: DOCUMENTED
- ✅ Professional codebase: DEPLOYED

### Production Deployment Options
- **Railway** (recommended): One-click deployment with free tier
- **Render**: Auto-deploy from GitHub with generous free tier
- **Heroku**: Classic platform with robust tooling
- **Self-hosted**: Full control on VPS

See [API Deployment Guide](docs/02-deployment/API_DEPLOYMENT_GUIDE.md) for setup.

## Next: Phase 2

See issues for upcoming features:
- Real-time score submission from game
- Enhanced frontend dashboard
- Database migration for scale

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
- [API Integration Guide](docs/03-integrations/api-integration-complete.md)
- [Weekly League Implementation](docs/03-integrations/weekly-league-phase1-complete.md)
- [Analytics Implementation](docs/ANALYTICS_IMPLEMENTATION.md)
- [Analytics Setup Guide](docs/ANALYTICS_SETUP.md)
- [Syndication Setup Guide](docs/SYNDICATION_SETUP.md)
- [**Syndication User Setup Guide**](docs/SYNDICATION_USER_SETUP_GUIDE.md) ⭐ **START HERE** - Complete step-by-step guide


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