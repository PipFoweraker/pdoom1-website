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
- Weekly league infrastructure: COMPLETE
- Game repository integration: OPERATIONAL
- API server with 8 endpoints: FUNCTIONAL
- Automated management system: READY
- Professional codebase: DEPLOYED

## Next: Phase 2

See issues for upcoming features:
- Real-time score submission from game
- Production automation and hosting
- Enhanced frontend dashboard

## Documentation

Complete documentation available in `docs/`:
- [API Integration Guide](docs/03-integrations/api-integration-complete.md)
- [Weekly League Implementation](docs/03-integrations/weekly-league-phase1-complete.md)
- [Deployment Guide](docs/03-integrations/v1-deployment-ready.md)