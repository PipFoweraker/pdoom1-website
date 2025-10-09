# Weekly League System Implementation

## Phase 1: Score Submission Infrastructure (Next Priority)

### Game Repository Changes Needed

#### 1. Score Submission Module
```python
# Add to game repository: src/web_integration/score_submitter.py

class ScoreSubmitter:
    def __init__(self, api_endpoint="https://pdoom1.com/api"):
        self.api_endpoint = api_endpoint
        self.player_uuid = self.get_or_create_player_id()
    
    def submit_score(self, game_session):
        """Submit completed game session to global leaderboard"""
        score_data = {
            "player_uuid": self.player_uuid,
            "player_name": game_session.lab_name,
            "seed": game_session.seed,
            "score": game_session.turns_survived,
            "final_metrics": {
                "doom_risk": game_session.final_doom,
                "money": game_session.final_money,
                "staff": game_session.final_staff,
                "reputation": game_session.final_reputation,
                "compute": game_session.final_compute,
                "papers": game_session.research_papers_published,
                "tech_debt": game_session.technical_debt
            },
            "game_version": "v0.4.1",
            "timestamp": datetime.now().isoformat(),
            "verification_hash": self.calculate_verification_hash(game_session)
        }
        
        return self.post_score(score_data)
```

#### 2. Privacy Controls
```python
# Add to game settings/preferences
LEADERBOARD_SETTINGS = {
    "submit_scores": True,  # Player opt-in
    "public_name": True,    # Show lab name publicly
    "share_metrics": True,  # Share detailed game metrics
    "weekly_leagues": True  # Participate in weekly competitions
}
```

### Website API Enhancements Needed

#### 1. Score Submission Endpoint
```python
# Add to scripts/api-server.py
@app.route('/api/scores/submit', methods=['POST'])
def submit_score():
    """Accept score submissions from game clients"""
    data = request.get_json()
    
    # Validate submission
    if not validate_score_submission(data):
        return jsonify({"error": "Invalid submission"}), 400
    
    # Anti-cheat verification
    if not verify_score_authenticity(data):
        return jsonify({"error": "Score verification failed"}), 403
    
    # Store in appropriate leaderboard
    leaderboard = get_or_create_leaderboard(data['seed'])
    leaderboard.add_entry(data)
    
    return jsonify({"status": "success", "rank": calculate_rank(data)})
```

#### 2. Weekly League Management
```python
# Add weekly league system
class WeeklyLeague:
    def __init__(self):
        self.current_week = self.get_current_week()
        self.seed = self.generate_weekly_seed()
    
    def generate_weekly_seed(self):
        """Generate new competitive seed every Monday"""
        week_start = self.get_week_start()
        return f"weekly_{week_start.strftime('%Y_W%U')}"
    
    def get_leaderboard(self):
        """Get current week's leaderboard"""
        return load_leaderboard(self.seed)
    
    def archive_week(self):
        """Archive completed week and start new one"""
        # Move current week to archives
        # Generate new seed for new week
        # Reset active leaderboard
```

## Phase 2: Database & Persistence

### Current State (File-Based)
```
public/leaderboard/data/
├── leaderboard.json          # Current/demo data
├── weekly/                   # Weekly league archives
│   ├── 2025_W41.json        # Week 41 results
│   ├── 2025_W42.json        # Week 42 results
│   └── current.json         # Active week
└── global/                   # All-time rankings
    ├── global_rankings.json  # Cross-seed leaderboard
    └── player_profiles.json  # Player statistics
```

### Recommended: Database Migration
```sql
-- Scores table for persistent storage
CREATE TABLE scores (
    id SERIAL PRIMARY KEY,
    player_uuid VARCHAR(36) NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    seed VARCHAR(50) NOT NULL,
    score INTEGER NOT NULL,
    final_metrics JSONB,
    game_version VARCHAR(10),
    submitted_at TIMESTAMP DEFAULT NOW(),
    verification_hash VARCHAR(64),
    week_number INTEGER,
    league_season VARCHAR(20)
);

-- Weekly leagues table
CREATE TABLE weekly_leagues (
    week_number INTEGER PRIMARY KEY,
    seed VARCHAR(50) UNIQUE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'active'
);
```

## Phase 3: Anti-Cheat & Verification

### Score Verification System
```python
def verify_score_authenticity(score_data):
    """Multi-layer score verification"""
    
    # 1. Hash verification
    expected_hash = calculate_verification_hash(score_data)
    if score_data['verification_hash'] != expected_hash:
        return False
    
    # 2. Physics validation
    if not validate_game_physics(score_data):
        return False
    
    # 3. Anomaly detection
    if is_statistical_outlier(score_data):
        flag_for_manual_review(score_data)
    
    return True

def calculate_verification_hash(game_session):
    """Generate tamper-proof hash of game session"""
    verification_string = f"{game_session.seed}:{game_session.turns_survived}:{game_session.final_doom}:{GAME_VERSION_HASH}"
    return hashlib.sha256(verification_string.encode()).hexdigest()
```

## Phase 4: Deployment Architecture

### Current Setup (File-Based)
```
Website (Static Files)
├── JSON Leaderboards
├── Python API Scripts
└── Manual Data Export

Game (Local)
├── Local Leaderboard Storage
├── Export Scripts
└── Manual Sync Process
```

### Target Setup (Live System)
```
Game Client
├── Automatic Score Submission
├── Privacy Controls
└── Weekly League Participation
    ↓ HTTPS API
Website/Server
├── Score Validation API
├── Database Storage
├── Weekly League Management
├── Anti-Cheat System
└── Public Leaderboard Display
```

## Implementation Timeline

### Week 1-2: Core Infrastructure
- [ ] Add score submission API endpoint to website
- [ ] Create score validation and storage system
- [ ] Implement basic weekly league structure
- [ ] Set up database/persistent storage

### Week 3-4: Game Integration
- [ ] Add score submission module to game
- [ ] Implement privacy controls and player preferences
- [ ] Create verification hash system
- [ ] Test end-to-end score submission

### Week 5-6: Weekly Leagues
- [ ] Automated weekly seed generation
- [ ] League archive system
- [ ] Player ranking and statistics
- [ ] Weekly reset automation

### Week 7-8: Polish & Launch
- [ ] Anti-cheat system implementation
- [ ] Public documentation and guides
- [ ] Beta testing with select players
- [ ] Official weekly league launch

## Next Immediate Steps

1. **Set up score submission API** in website
2. **Add HTTP client** to game for score submission
3. **Implement player UUID system** for consistent identity
4. **Create weekly seed generation** system
5. **Build verification hash** into game sessions

This creates a complete competitive ecosystem where players can automatically submit scores, participate in weekly leagues, and compete on global leaderboards!