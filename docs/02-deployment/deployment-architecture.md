# Weekly Deployment Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     WEEKLY DEPLOYMENT SYSTEM                     │
│                         p(Doom)1 Website                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          WEEKLY CYCLE                            │
└─────────────────────────────────────────────────────────────────┘

  Monday 00:00 AEST           Tuesday-Thursday          Thursday 17:00
  ─────────────────           ────────────────          ──────────────
  🏆 League Starts             💻 Development            🔒 Code Freeze
       │                           │                          │
       │                           │                          │
       v                           v                          v
  ┌──────────┐              ┌──────────┐              ┌──────────┐
  │ Auto     │              │ Balance  │              │ Testing  │
  │ Reset    │──────────────│ Changes  │──────────────│ Complete │
  │ League   │              │ & Fixes  │              │          │
  └──────────┘              └──────────┘              └──────────┘


  Friday 14:00-16:00                    Friday 16:00
  ──────────────────                    ────────────
  ✅ Pre-Deployment                      🚀 DEPLOY
       │                                      │
       v                                      v
  ┌──────────────┐                     ┌──────────┐
  │ Preparation  │                     │ GitHub   │
  │ Script Runs  │────────────────────▶│ Actions  │
  │ All Checks   │                     │ Deploy   │
  └──────────────┘                     └──────────┘
                                             │
                                             v
  Friday 16:30-18:00                   DreamHost
  ──────────────────                   Production
  📺 Twitch Stream
```

## Data Flow

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   pdoom1     │         │   Website    │         │  DreamHost   │
│ Game Repo    │────────▶│  Repository  │────────▶│  Production  │
│              │  Sync   │              │  Deploy │              │
└──────────────┘         └──────────────┘         └──────────────┘
      │                        │                         │
      │ Leaderboard           │ Weekly                  │ Live
      │ Data Export           │ Deployment              │ Website
      │                        │                         │
      v                        v                         v
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ Game Data    │         │   Build &    │         │   Users      │
│ Files        │         │   Validate   │         │   Access     │
└──────────────┘         └──────────────┘         └──────────────┘
```

## Automation Components

### 1. GitHub Actions Workflows

```
.github/workflows/
├── weekly-deployment.yml       ← Friday 16:00 AEST (06:00 UTC)
│   ├── Pre-deployment checks
│   ├── Game data sync
│   ├── Deploy to DreamHost
│   └── Post-deployment verification
│
├── weekly-league-reset.yml     ← Monday 00:00 AEST (Sunday 14:00 UTC)
│   ├── Archive previous week
│   ├── Generate new seed
│   ├── Start new league
│   └── Commit changes
│
├── version-aware-deploy.yml    ← Manual deployment option
│   ├── Version validation
│   ├── Approval gates
│   └── Deployment
│
└── health-checks.yml           ← Every 6 hours
    └── Site monitoring
```

### 2. Deployment Scripts

```
scripts/
├── prepare-weekly-deployment.py    ← Pre-deployment validation
│   ├── Git status check
│   ├── Version validation
│   ├── League system check
│   ├── Game integration check
│   ├── Health checks
│   └── Generate readiness report
│
├── weekly-league-manager.py        ← League management
│   ├── --status        → Show current league
│   ├── --new-week      → Start new league
│   ├── --archive-week  → Archive completed week
│   ├── --standings     → Show standings
│   └── --generate-seed → Create competitive seed
│
├── game-integration.py             ← Game data sync
│   ├── --sync-leaderboards → Sync all leaderboard data
│   ├── --weekly-sync      → Sync weekly league data
│   └── --status           → Show integration status
│
└── verify-deployment.py            ← Post-deployment checks
    ├── File integrity
    ├── JSON validation
    ├── Content verification
    └── Health checks
```

### 3. NPM Commands

```
Package.json Scripts:
├── deploy:prep-weekly   → Full preparation with checks
├── deploy:check         → Status check (no changes)
├── deploy:quick-check   → Fast verification
│
├── league:status        → Show league status
├── league:new-week      → Start new week
├── league:archive       → Archive current week
├── league:standings     → View standings
│
├── game:sync-all        → Sync all game data
├── game:weekly-sync     → Sync weekly data
└── game:status          → Integration status
```

## Deployment Timeline

```
Friday Deployment Day (AEST)
────────────────────────────────────────────────────────────────

14:00 │ ┌─────────────────────────┐
      │ │ Pre-Deployment Prep     │
      │ │ • Run prepare script    │
14:30 │ │ • Check league status   │
      │ │ • Sync game data        │
15:00 │ │ • Verify all systems    │
      │ └─────────────────────────┘
      │         │
15:30 │         v
      │ ┌─────────────────────────┐
      │ │ Final Review            │
15:45 │ │ • Manual verification   │
      │ │ • Go/No-Go decision     │
      │ └─────────────────────────┘
      │         │
16:00 │         v
      │ ┌─────────────────────────┐
      │ │ 🚀 DEPLOYMENT           │
      │ │ • Trigger workflow      │
16:05 │ │ • Deploy to DreamHost   │
      │ │ • Run health checks     │
16:10 │ └─────────────────────────┘
      │         │
      │         v
16:15 │ ┌─────────────────────────┐
      │ │ Verification            │
16:20 │ │ • Manual site check     │
      │ │ • Test key features     │
      │ └─────────────────────────┘
      │         │
16:30 │         v
      │ ┌─────────────────────────┐
      │ │ 📺 Twitch Stream        │
      │ │ • Show new features     │
17:00 │ │ • Community Q&A         │
      │ │ • Demo gameplay         │
17:30 │ └─────────────────────────┘
      │         │
      │         v
18:00 │ ┌─────────────────────────┐
      │ │ Post-Stream Monitoring  │
      │ │ • Review feedback       │
      │ │ • Monitor stability     │
      │ └─────────────────────────┘
```

## Monitoring & Alerting

```
┌─────────────────────────────────────────────┐
│            MONITORING LAYERS                 │
└─────────────────────────────────────────────┘

Layer 1: GitHub Actions
├── Workflow success/failure
├── Job step monitoring
└── Automated email alerts

Layer 2: Health Checks (Every 6 hours)
├── Site accessibility
├── API endpoints
├── Leaderboard data freshness
└── Weekly league status

Layer 3: Manual Monitoring
├── Friday 16:00-18:00 (Active)
├── Weekend (Automated + On-call)
└── Monday morning (Pre-league check)

Layer 4: Community Feedback
├── Discord reports
├── Twitter mentions
└── Twitch stream chat
```

## Rollback Strategy

```
┌────────────────────────────────────────────────────┐
│              ROLLBACK DECISION TREE                 │
└────────────────────────────────────────────────────┘

    Issue Detected
         │
         ├─── Site Down? ─────────▶ IMMEDIATE ROLLBACK
         │                          (< 5 minutes)
         │
         ├─── Data Loss? ─────────▶ IMMEDIATE ROLLBACK
         │                          + Data recovery
         │
         ├─── Critical Bug? ──────▶ Quick Assessment
         │                          │
         │                          ├─ Affects all users? → Rollback
         │                          └─ Workaround exists? → Monitor
         │
         └─── Minor Issue? ───────▶ Continue Monitoring
                                     Fix in next deployment

Rollback Commands:
1. git revert HEAD
2. git push
3. Re-run deployment workflow
4. Verify rollback successful
5. Communicate to community
```

## Communication Flow

```
                        ┌──────────────┐
                        │  Developer   │
                        └──────┬───────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            v                  v                  v
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │   Discord    │   │    Twitter   │   │    Twitch    │
    │  Community   │   │   Followers  │   │   Viewers    │
    └──────────────┘   └──────────────┘   └──────────────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
                               v
                        ┌──────────────┐
                        │    Users     │
                        │   Playing    │
                        └──────────────┘
```

## Success Metrics

```
Weekly Deployment KPIs:
─────────────────────────────────────────

Reliability:
├── Deployment success rate    → Target: 100%
├── Rollback rate              → Target: <5%
└── Downtime per deployment    → Target: <1 min

Performance:
├── Deployment duration        → Target: <10 min
├── Time to detect issues      → Target: <5 min
└── Time to rollback           → Target: <5 min

Engagement:
├── Stream viewership          → Track weekly
├── Community feedback         → Positive ratio
└── Feature adoption           → Track usage

Quality:
├── Critical bugs              → Target: 0
├── User-reported issues       → Track & trend
└── Pre-deployment checks      → Target: 100% pass
```

## Documentation Map

```
docs/02-deployment/
│
├── weekly-deployment-schedule.md     ← Complete schedule & procedures
│   ├── Weekly timeline (Mon-Sun)
│   ├── Deployment workflow
│   ├── Rollback procedures
│   └── Responsibility matrix
│
├── weekly-deployment-checklist.md    ← Step-by-step checklist
│   ├── Pre-deployment tasks
│   ├── Deployment execution
│   ├── Post-deployment verification
│   └── Emergency procedures
│
├── deployment-quick-reference.md     ← Quick reference card
│   ├── Command cheat sheet
│   ├── Timeline at a glance
│   ├── Emergency contacts
│   └── Common scenarios
│
└── deployment-architecture.md        ← This document
    ├── System overview
    ├── Data flow diagrams
    ├── Automation components
    └── Success metrics
```

## Key Decisions & Rationale

### Why Friday 16:00 AEST?
- ✅ Before weekend, time for monitoring
- ✅ After work hours for live stream
- ✅ Monday league start gives users weekend to play
- ✅ Developer available for immediate response
- ✅ Community engagement via Twitch

### Why Automated League Reset?
- ✅ Ensures Monday 00:00 start is reliable
- ✅ No manual intervention required
- ✅ Archives previous week automatically
- ✅ Generates new competitive seed
- ✅ Commits changes to repository

### Why Pre-Deployment Script?
- ✅ Catches issues before deployment
- ✅ Validates all systems operational
- ✅ Syncs latest game data
- ✅ Provides clear go/no-go status
- ✅ Generates audit trail

### Why Twitch Stream?
- ✅ Community engagement
- ✅ Live demonstration of features
- ✅ Immediate feedback loop
- ✅ Transparency in process
- ✅ Educational content

## Next Steps

### Immediate (This Week)
- [ ] Test weekly-deployment.yml in production
- [ ] Verify timezone calculations during DST
- [ ] Create Twitch stream template
- [ ] Set up monitoring alerts

### Short-term (Next Month)
- [ ] Collect metrics on first deployments
- [ ] Refine based on lessons learned
- [ ] Add deployment dashboard
- [ ] Automate more pre-checks

### Long-term (Next Quarter)
- [ ] Integration with game CI/CD
- [ ] Blue-green deployment strategy
- [ ] A/B testing capabilities
- [ ] Advanced monitoring & analytics

---

**Last Updated**: 2025-10-09  
**Version**: 1.0  
**Status**: ✅ Implemented and documented
