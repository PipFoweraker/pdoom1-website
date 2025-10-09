# Weekly Deployment Timeline Visualization

## The Complete Week at a Glance

```
+-----------------------------------------------------------------+
|                    WEEKLY CYCLE - p(Doom)1                      |
|                    Friday to Friday Cadence                      |
+-----------------------------------------------------------------+

WEEK N                                        WEEK N+1

Monday      Tuesday     Wednesday   Thursday   |   Friday     Weekend      Monday
00:00       10:00       All Day     17:00      |   16:00      Monitor      00:00
|           |           |           |          |   |          |            |
|           |           |           |          |   |          |            |
v           v           v           v          |   v          v            v

[TROPHY]          [BALANCE]           [TEST]          [LOCKED]         |   [DEPLOY]         [WATCH]           [TROPHY]
New         Balance     Testing    Code        |   Deploy     Weekend      New
League      Changes     & QA       Freeze      |   Live       Buffer       League
Starts      Window      Phase                  |   Stream     Period       Starts

|           |           |           |          |   |          |            |
|           |           |           |          |   |          |            |
+-----------+-----------+-----------+----------+---+----------+------------+
|                                              |                            |
|         DEVELOPMENT & TESTING                |    DEPLOYMENT & MONITORING  |
|              (Mon-Thu)                       |         (Fri-Sun)          |
|                                              |                            |
+----------------------------------------------+----------------------------+

                        Code Freeze Line  -------->|<---- Active Dev Line


===========================================================================

                         FRIDAY - DEPLOYMENT DAY

14:00 --+-- Pre-Deployment Preparation
        |   - npm run deploy:prep-weekly
        |   - Check league status
        |   - Sync game data
14:30   |   - Verify all systems green
        |
15:00 --+-- Final Review & Decision
        |   - Manual verification
15:30   |   - Team sync (if needed)
        |   - Go/No-Go decision
15:45   |
        |
16:00 --+-- [DEPLOY] DEPLOYMENT TRIGGER
        |   - GitHub Actions started
16:05   |   - Files syncing to DreamHost
        |   - Health checks running
16:10   |   - Deployment complete
        |
16:15 --+-- Quick Verification
        |   - Test key pages
16:20   |   - Verify functionality
        |   - Check for errors
16:25   |
        |
16:30 --+-- [STREAM] TWITCH STREAM STARTS
        |   - Welcome & intro
16:35   |   - Show deployment
        |   - Feature showcase
16:45   |   - League preview
        |
17:00 --+-- Q&A Session
        |   - Community questions
17:15   |   - Technical discussion
        |   - Feedback collection
17:30   |
        |
17:30 --+-- Stream End & Monitoring
        |   - Post summary
17:45   |   - Check for issues
        |   - Monitor metrics
18:00   |
        |
18:00 --+-- Log Off (Automated monitoring continues)

===========================================================================

                    MONDAY - LEAGUE RESET (AUTOMATED)

Sunday
23:00 --+-- Pre-Reset Checks
        |   (Automated workflow preparing)
23:30   |
        |
23:59 --+-- Final entries for current week
        |
Monday
00:00 --+-- [TROPHY] AUTOMATIC LEAGUE RESET
        |   - Archive previous week
00:01   |   - Generate new competitive seed
        |   - Initialize new league data
00:02   |   - Commit changes to repo
        |   - Push updates
00:05   |
        |
00:05 --+-- New League Live
            - Players can start competing
            - Leaderboard resets
            - New week begins

===========================================================================

                      COMMUNICATION TIMELINE

Thursday PM:
+- Discord: "Deployment tomorrow 4pm AEST! [DEPLOY]"
+- Twitter: Preview of new features

Friday 15:45:
+- Discord: "Deployment starting in 15 minutes"
+- Team: Final go/no-go

Friday 16:00:
+- Discord: "[DEPLOY] Deployment in progress"
+- Twitter: "Going live!"

Friday 16:30:
+- Twitch: Stream starts
+- Discord: "Live on Twitch!"
+- Twitter: "Streaming now!"

Friday 18:00:
+- Discord: Deployment summary
|   - What deployed
|   - Version number  
|   - Known issues
|   - Thanks to contributors
+- Twitter: Highlight tweet

Sunday PM:
+- Discord: "New league Monday midnight!"
+- Twitter: Week preview

Monday 00:05:
+- Discord: "New league live! [TROPHY]"
|   - Week number
|   - Competitive seed
|   - Good luck message
+- Twitter: New league announcement

===========================================================================

                    RESPONSIBILITY MATRIX

+---------------------+------------------+------------------+
|     Activity        |    Primary       |     Backup       |
+---------------------+------------------+------------------+
| Mon: Monitor League | Lead Dev         | Community Mgr    |
| Tue: Balance Review | Game Designer    | Lead Dev         |
| Wed-Thu: Testing    | QA / Lead Dev    | Contributors     |
| Thu: Code Freeze    | Lead Dev         | -                |
| Fri 14:00: Pre-Dep  | Lead Dev         | DevOps           |
| Fri 16:00: Deploy   | Lead Dev         | DevOps           |
| Fri 16:30: Stream   | Lead Dev         | Community Mgr    |
| Fri-Sun: Monitor    | Automated        | On-Call Dev      |
| Sun 23:59: Archive  | Automated        | -                |
| Mon 00:00: Reset    | Automated        | On-Call Dev      |
+---------------------+------------------+------------------+

===========================================================================

                      AUTOMATION TRIGGERS

GitHub Actions Cron Schedules (UTC times):

+----------------------------+--------------------------+
| Workflow                   | Schedule (UTC)           |
+----------------------------+--------------------------+
| Weekly Deployment          | 0 6 * * 5                |
|                            | (Fri 06:00 = 16:00 AEST) |
+----------------------------+--------------------------+
| Weekly League Reset        | 0 14 * * 0               |
|                            | (Sun 14:00 = Mon 00:00)  |
+----------------------------+--------------------------+
| Health Checks              | 0 */6 * * *              |
|                            | (Every 6 hours)          |
+----------------------------+--------------------------+
| Game Status Sync           | Manual / Repository      |
|                            | Dispatch                 |
+----------------------------+--------------------------+

Note: During Australian Daylight Saving (Oct-Apr):
AEDT = UTC+11, so deployments are at 05:00 UTC
Consider updating cron to: 0 5 * * 5

===========================================================================

                        SUCCESS METRICS

Weekly Deployment Goals:
+- Deployment time: < 10 minutes
+- Rollback rate: < 5%
+- Zero critical bugs
+- Stream viewers: Track & grow
+- Community satisfaction: High

League Health Metrics:
+- Monday reset: 100% automated success
+- Participant growth: Week over week
+- Score submissions: Increasing
+- Community engagement: Active

===========================================================================

                     QUICK COMMAND REFERENCE

Pre-Deployment:
$ npm run deploy:prep-weekly      # Full preparation
$ npm run deploy:check            # Quick status
$ npm run league:status           # League check

Deployment:
Via GitHub Actions:
  -> Actions -> Weekly Scheduled Deployment -> Run workflow

Emergency:
$ git revert HEAD && git push     # Rollback
$ gh workflow run weekly-deployment.yml --force

League Management:
$ npm run league:new-week         # Start new week
$ npm run league:archive          # Archive current
$ npm run league:standings        # View standings

===========================================================================

Legend:
[TROPHY] - League Event
[BALANCE] - Balance Changes
[TEST] - Testing Phase
[LOCKED] - Code Freeze
[DEPLOY] - Deployment
[STREAM] - Live Stream
[WATCH] - Monitoring
```

## Print-Friendly Version

Save this timeline for your wall or desk!

**FRIDAY DEPLOYMENT - QUICK VIEW**

```
14:00 | Start prep
15:00 | Final review
16:00 | [DEPLOY] DEPLOY
16:30 | [STREAM] STREAM
18:00 | Log off
```

**COMMANDS TO REMEMBER**

```
npm run deploy:prep-weekly    # Before deployment
npm run deploy:check          # Quick status
npm run league:status         # League check
```

**EMERGENCY ROLLBACK**

```
git revert HEAD
git push
# Then re-run deployment
```

**THIS WEEK'S DEPLOYMENT**

```
Date: _______________
Version: ____________
Features: ___________
         ___________
         ___________
```
