# How p(Doom)1 Leaderboards Work

## Overview

The p(Doom)1 leaderboard system tracks player performance across different game seeds and economic models, providing a competitive platform for AI safety strategy gaming.

## Current System (v1.0.0)

### How Scores Are Recorded
- **Local Game Data**: Scores are saved locally in your game installation
- **Export Integration**: Real leaderboard data from `leaderboards/` folder in game repository
- **Website Display**: Exported data appears on the website leaderboard
- **Seed-Specific Tracking**: Each game seed has its own leaderboard

### Leaderboard Structure
```
📊 Current Leaderboards:
├── Seed-Specific Boards (e.g., "demo-competitive-seed")
├── Economic Model Tracking (Bootstrap_v0.4.1, Legacy, etc.)
└── Player Performance Metrics
    ├── Turns Survived (Primary Score)
    ├── Final Doom Risk Percentage
    ├── Economic Metrics (Money, Staff, Reputation)
    ├── Research Papers Published
    └── Technical Debt Accumulated
```

### Viewing Leaderboards
- **Website**: Visit [pdoom1-website/leaderboard/](https://yoursite.com/leaderboard/)
- **Filtering**: Sort by score, risk level, date, research output
- **Search**: Find specific players or game modes
- **Real-Time**: Data updates when game exports new scores

## Score Metrics Explained

### Primary Score: Turns Survived
The main competitive metric - how many turns you lasted before the game ended.

### Risk Management
- **Safe Play**: ≤30% doom risk (conservative strategy)
- **Risky Play**: 30-50% doom risk (balanced approach)  
- **Dangerous Play**: >50% doom risk (high-risk, high-reward)

### Economic Performance
- **Final Money**: Total financial resources at game end
- **Staff Count**: Number of team members recruited
- **Reputation**: Public perception and influence level
- **Compute Resources**: AI development infrastructure

### Research Impact
- **Papers Published**: Academic contributions to AI safety
- **Technical Debt**: Accumulated shortcuts and risks

## Planned Features (Coming Soon)

### Weekly Leagues (Q4 2025)
- **Reset Schedule**: New competitive seeds every Monday
- **League Tables**: Weekly, monthly, and seasonal rankings
- **Prize Categories**: Best newcomer, most improved, risk management expert

### Global Leaderboard Integration
- **Cross-Seed Rankings**: Compare performance across different scenarios
- **Player Profiles**: Track individual progress and achievements
- **Team Competition**: Lab vs lab competitive play

### Score Submission System
- **Automatic Upload**: Seamless score transmission from game to website
- **Verification**: Anti-cheat measures and score validation
- **Privacy Controls**: Choose what data to share publicly

## For Developers

### API Endpoints
```bash
GET /api/leaderboards/current?limit=10    # Current top players
GET /api/leaderboards/seed/{seed}         # Seed-specific board
GET /api/stats                            # Overall statistics
GET /api/health                           # System status
```

### Data Format
All leaderboard data follows a standardized JSON schema with game metadata, player information, and performance metrics.

### Integration Commands
```bash
# Export game data to website
python scripts/game-integration.py --export

# Ingest published board JSON into the site's leaderboard data
python scripts/ingest_scores.py

# Test integration
python scripts/test-integration.py --quick
```

> The website does not run its own score API. Scores live behind one PHP
> endpoint owned by the game side (`score_api.php`), and this site is a
> read-only consumer of it -- either via its GET contract or by reading the
> published `board_<seed>__<version>.json` files directly.

## Privacy & Fair Play

### Data Privacy
- Only performance metrics are shared, not personal data
- Players control what information appears publicly
- Local game data remains on your machine unless explicitly shared

### Anti-Cheat Measures
- Score validation against game physics
- Seed verification for competitive play
- Anomaly detection for suspicious patterns

### Community Guidelines
- Respectful competition encouraged
- No exploiting game bugs for leaderboard advantage
- Report suspected cheating through GitHub issues

---

**Ready to compete?** Download the game, play a few rounds, and see your scores appear on the leaderboard!