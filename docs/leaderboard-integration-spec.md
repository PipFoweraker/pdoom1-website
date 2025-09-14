# Leaderboard Integration Specification

**Version**: 1.0  
**Date**: September 15, 2025  
**Purpose**: Define proper integration between p(Doom)1 game leaderboard system and website display

## Current Implementation Analysis

Based on analysis of the main p(Doom)1 repository, the leaderboard system is **fully implemented and active** as of v0.4.1. Here's what we found:

### Game Repository Status ✅
- **EnhancedLeaderboardManager**: Complete system with seed-specific tracking
- **LocalLeaderboard**: JSON persistence with versioned schema  
- **ScoreEntry**: Comprehensive metadata including economic model data
- **GameSession**: Full session tracking with bootstrap economic metrics
- **UI Integration**: High score screen displays actual leaderboard data

## Data Structure Specification

### ScoreEntry Format
The game uses this structure for individual leaderboard entries:

```python
class ScoreEntry:
    score: int                    # Primary ranking metric (turns survived)
    player_name: str             # Lab name (e.g. "Acme Safety Labs")
    date: datetime               # When score was achieved
    level_reached: int           # Final turn number (same as score)
    game_mode: str              # Economic model ("Bootstrap_v0.4.1")
    duration_seconds: float     # Game session length
    entry_uuid: str             # Unique identifier
```

### GameSession Extended Metadata
For enhanced leaderboard features, the game tracks:

```python
class GameSession:
    # Core identifiers
    seed: str                           # Game seed for seed-specific boards
    final_turn: int                     # Score (turns survived)
    final_score: int                   # Same as final_turn
    game_version: str                  # "v0.4.1"
    economic_model: str               # "Bootstrap_v0.4.1"
    
    # Session metadata
    start_time: datetime
    end_time: datetime  
    duration_minutes: float
    player_name: str                  # Display name
    lab_name: str                     # AI safety lab name
    
    # Final game state
    final_money: float
    final_staff: int
    final_reputation: float
    final_doom: float                 # Risk level at end
    final_compute: float
    
    # Economic model metrics (v0.4.1+)
    total_staff_maintenance_paid: float
    total_research_spending: float
    total_fundraising_gained: float
    moore_law_savings: float
    
    # Performance analytics
    actions_taken: int
    average_ap_per_turn: float
    research_papers_published: int
    technical_debt_accumulated: int
```

## Leaderboard Storage Architecture

### File Organization
```
leaderboards/
├── seed_[HASH]_Bootstrap_v0.4.1.json     # Seed-specific boards
├── seed_[HASH]_Legacy.json                # Migration data
└── sessions/
    └── [UUID].json                        # Session metadata
```

### JSON Schema Example
```json
{
    "version": "1.0.0",
    "max_entries": 100,
    "seed": "example_seed_123",
    "economic_model": "Bootstrap_v0.4.1",
    "config_hash": "abc123def456",
    "entries": [
        {
            "score": 85,
            "player_name": "Anthropic Safety Labs",
            "date": "2025-09-15T14:30:00",
            "level_reached": 85,
            "game_mode": "Bootstrap_v0.4.1",
            "duration_seconds": 1245.5,
            "entry_uuid": "uuid-here"
        }
    ]
}
```

## Integration Requirements

### Phase 1: Basic Display (Current Website)
**Status**: ❌ Mismatch - Using mock data structure

**Current Website Issues**:
- Mock data uses different field names (`name` vs `player_name`)
- Missing seed-specific separation 
- Incorrect achievement/badge system
- No economic model tracking

**Required Changes**:
1. Update `public/leaderboard/data/leaderboard.json` to match game format
2. Modify leaderboard rendering to use correct field names
3. Add seed filtering/selection UI
4. Replace mock achievements with actual game metrics

### Phase 2: Live Data Integration 
**Target**: Connect website to actual game data

**Options**:
1. **File Export**: Game exports leaderboard JSON to shared location
2. **GitHub Integration**: Game commits leaderboard data to repository  
3. **API Bridge**: Website polls for leaderboard updates
4. **Manual Sync**: Players submit screenshots/data

### Phase 3: Enhanced Features
- Player profile pages with session history
- Seed-specific leaderboard browsing
- Economic model performance analytics
- Strategic analysis display (research vs safety focused)

## Recommended Implementation Plan

### Immediate Actions (Dev Branch)
1. **Fix Data Structure**: Update website leaderboard to match game format
   ```javascript
   // Change from:
   { name: "Player", score: 1000, achievements: [...] }
   // To:
   { player_name: "Lab Name", score: 85, game_mode: "Bootstrap_v0.4.1", ... }
   ```

2. **Add Seed Support**: Implement seed-specific leaderboard display
   ```html
   <select id="seed-selector">
       <option value="all">All Seeds</option>
       <option value="seed_123">Seed: example_123</option>
   </select>
   ```

3. **Economic Model Display**: Show bootstrap economic metrics
   ```javascript
   // Display: final_money, final_staff, final_doom, technical_debt, etc.
   ```

### Required Game Repository Changes
**For p(Doom)1 main repository**:

1. **Export Functionality**: Add leaderboard export command
   ```python
   # Suggested: Add to enhanced_leaderboard.py
   def export_leaderboards_for_web(output_path: Path) -> None:
       """Export all leaderboards in web-compatible format."""
   ```

2. **Web API Endpoints**: Consider adding REST API for live data
   ```python
   # Optional: Flask/FastAPI endpoints for real-time access
   GET /api/leaderboards/{seed}
   GET /api/leaderboards/stats
   ```

3. **Privacy Controls**: Respect player privacy settings
   ```python
   # Honor privacy_manager settings for web export
   if not privacy_manager.web_leaderboard_enabled():
       return anonymized_data()
   ```

## Data Requests for Main Repository

### Missing Web Export Features
To properly integrate the website, we need these additions to the main p(Doom)1 repository:

1. **Web Export Command**:
   ```bash
   python -m pdoom1.leaderboard export --format web --output ./web_export/
   ```

2. **API-Compatible JSON Format**:
   ```json
   {
       "meta": {
           "generated": "2025-09-15T14:30:00Z",
           "total_seeds": 15,
           "total_players": 42,
           "game_version": "v0.4.1"
       },
       "leaderboards": {
           "seed_123": { ... },
           "global_stats": { ... }
       }
   }
   ```

3. **Privacy-Compliant Export**: Anonymous/pseudonymous options

### Folder Structure Request
Please create in main p(Doom)1 repository:
```
tools/
└── web_export/
    ├── export_leaderboards.py    # Web export script
    ├── api_format.py            # JSON formatting for website
    └── privacy_filter.py        # Privacy-compliant data filtering
```

## Testing Plan

### Website Leaderboard Testing
1. **Data Structure Validation**: Ensure website handles real game data format
2. **Seed Filtering**: Test seed-specific leaderboard display  
3. **Performance**: Large leaderboard rendering (100+ entries)
4. **Mobile Responsive**: Economic metrics display on mobile

### Integration Testing  
1. **Export Process**: Game → Website data flow
2. **Update Frequency**: How often website refreshes leaderboard data
3. **Error Handling**: Missing data, corrupted JSON, etc.

## Success Criteria

### Phase 1 Complete When:
- [x] Website leaderboard matches game data structure
- [ ] Seed-specific filtering functional
- [ ] Economic model metrics displayed
- [ ] Real game data (not mock) displayed

### Phase 2 Complete When:
- [ ] Live data integration working
- [ ] Automatic updates (daily/weekly)
- [ ] Privacy controls respected
- [ ] Performance acceptable (<2s load time)

### Phase 3 Complete When:
- [ ] Player profiles functional
- [ ] Strategic analysis display
- [ ] Community features (comments, comparisons)
- [ ] Mobile-optimized experience

---

## Next Steps

1. **Immediate**: Fix website data structure to match game format
2. **Contact Main Repo**: Request web export functionality implementation  
3. **Test Integration**: Use actual game leaderboard files for testing
4. **Deploy Updates**: Push corrected website leaderboard to production

**Priority**: High - Current website leaderboard is displaying incorrect/mock data structure that doesn't match the actual implemented game system.
