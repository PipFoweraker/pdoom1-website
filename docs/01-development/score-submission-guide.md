# Score Submission Development Guide

## Quick Start: Adding Score Submission to p(Doom)1

### 1. Add HTTP Client to Game

Create `src/web_integration/__init__.py`:
```python
# Empty file to make it a package
```

Create `src/web_integration/score_client.py`:
```python
import requests
import hashlib
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class ScoreSubmissionClient:
    """Handle score submission to website leaderboard"""
    
    def __init__(self, api_base_url: str = "http://localhost:8081"):
        self.api_base_url = api_base_url
        self.player_config_file = Path.home() / ".pdoom1" / "player_config.json"
        self.player_uuid = self.get_or_create_player_uuid()
    
    def get_or_create_player_uuid(self) -> str:
        """Get existing player UUID or create new one"""
        if self.player_config_file.exists():
            try:
                with open(self.player_config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('player_uuid', str(uuid.uuid4()))
            except:
                pass
        
        # Create new UUID and save
        new_uuid = str(uuid.uuid4())
        self.save_player_config({'player_uuid': new_uuid})
        return new_uuid
    
    def save_player_config(self, config: Dict[str, Any]):
        """Save player configuration"""
        self.player_config_file.parent.mkdir(exist_ok=True)
        with open(self.player_config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def calculate_verification_hash(self, session_data: Dict[str, Any]) -> str:
        """Calculate tamper-proof verification hash"""
        # Include key game data in hash
        verification_string = (
            f"{session_data['seed']}:"
            f"{session_data['score']}:"
            f"{session_data['final_doom']}:"
            f"{session_data['game_version']}:"
            f"pdoom1_verification_salt"
        )
        return hashlib.sha256(verification_string.encode()).hexdigest()
    
    def submit_score(self, game_session) -> Optional[Dict[str, Any]]:
        """Submit completed game session to global leaderboard"""
        
        # Prepare score data
        score_data = {
            "player_uuid": self.player_uuid,
            "player_name": game_session.lab_name,
            "seed": getattr(game_session, 'seed', 'default_seed'),
            "score": game_session.turns_survived,
            "game_mode": getattr(game_session, 'economic_model', 'Bootstrap_v0.4.1'),
            "duration_seconds": getattr(game_session, 'duration_seconds', 0.0),
            "final_metrics": {
                "final_doom": getattr(game_session, 'final_doom', 25.0),
                "final_money": getattr(game_session, 'final_money', 100000),
                "final_staff": getattr(game_session, 'final_staff', 5),
                "final_reputation": getattr(game_session, 'final_reputation', 50.0),
                "final_compute": getattr(game_session, 'final_compute', 10000),
                "research_papers_published": getattr(game_session, 'research_papers_published', 0),
                "technical_debt_accumulated": getattr(game_session, 'technical_debt_accumulated', 0)
            },
            "game_version": "v0.4.1",
            "timestamp": datetime.now().isoformat(),
            "entry_uuid": str(uuid.uuid4())
        }
        
        # Add verification hash
        score_data["verification_hash"] = self.calculate_verification_hash(score_data)
        
        try:
            # Submit to API
            response = requests.post(
                f"{self.api_base_url}/api/scores/submit",
                json=score_data,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Score submitted successfully! Rank: {result.get('rank', 'Unknown')}")
                return result
            else:
                print(f"Score submission failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to submit score: {e}")
            return None

# Convenience function for easy integration
def submit_score_if_enabled(game_session) -> bool:
    """Submit score if player has enabled leaderboard submission"""
    
    # Check if player wants to submit scores
    config_file = Path.home() / ".pdoom1" / "player_config.json"
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                if not config.get('submit_scores', True):
                    return False
        except:
            pass  # Default to enabled if config is corrupted
    
    # Submit score
    client = ScoreSubmissionClient()
    result = client.submit_score(game_session)
    return result is not None
```

### 2. Integrate into Game End

In your main game loop (likely in `main.py` or game session management):

```python
# Add import at top
from src.web_integration.score_client import submit_score_if_enabled

# At the end of a game session (when the game ends)
def end_game_session(self):
    """Called when game ends - save scores and submit to leaderboard"""
    
    # Your existing game end logic
    self.save_local_leaderboard()
    self.calculate_final_metrics()
    
    # NEW: Submit to global leaderboard
    try:
        submit_score_if_enabled(self)
        print("Score submitted to global leaderboard!")
    except Exception as e:
        print(f"Could not submit score: {e}")
        # Game continues normally even if submission fails
```

### 3. Add Player Preferences

Create a simple settings system for leaderboard participation:

```python
# Add to your settings/preferences system
class PlayerPreferences:
    def __init__(self):
        self.config_file = Path.home() / ".pdoom1" / "player_config.json"
        self.load_preferences()
    
    def load_preferences(self):
        """Load player preferences from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except:
                self.config = self.get_default_config()
        else:
            self.config = self.get_default_config()
    
    def get_default_config(self):
        """Default leaderboard preferences"""
        return {
            "submit_scores": True,      # Participate in leaderboards
            "public_name": True,        # Show lab name publicly  
            "share_metrics": True,      # Share detailed game metrics
            "weekly_leagues": True      # Participate in weekly competitions
        }
    
    def save_preferences(self):
        """Save preferences to file"""
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
```

### 4. Test the Integration

Test that score submission works:

```python
# Test script: test_score_submission.py
from src.web_integration.score_client import ScoreSubmissionClient

# Create a mock game session for testing
class MockGameSession:
    def __init__(self):
        self.lab_name = "Test Lab"
        self.turns_survived = 42
        self.seed = "test_seed_123"
        self.final_doom = 25.5
        self.final_money = 150000
        self.final_staff = 8
        self.final_reputation = 75.0
        self.final_compute = 15000
        self.research_papers_published = 3
        self.technical_debt_accumulated = 12

# Test submission
client = ScoreSubmissionClient("http://localhost:8081")
mock_session = MockGameSession()
result = client.submit_score(mock_session)

if result:
    print(f"Test successful! Rank: {result.get('rank')}")
else:
    print("Test failed - check API server is running")
```

## Website API Changes Needed

Add this to your `scripts/api-server.py`:

```python
# Add score submission endpoint
def do_POST(self):
    """Handle POST requests for score submission"""
    if self.path == '/api/scores/submit':
        self.handle_score_submission()
    else:
        self.send_error(404, "Not Found")

def handle_score_submission(self):
    """Handle score submission from game clients"""
    try:
        # Read request data
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        score_data = json.loads(post_data.decode('utf-8'))
        
        # Validate submission
        if self.validate_score_submission(score_data):
            # Add to leaderboard
            self.add_score_to_leaderboard(score_data)
            
            # Calculate rank
            rank = self.calculate_player_rank(score_data)
            
            # Send success response
            response = {"status": "success", "rank": rank}
            self.send_json_response(response)
        else:
            self.send_error(400, "Invalid score submission")
            
    except Exception as e:
        self.send_error(500, f"Server error: {e}")

def validate_score_submission(self, score_data):
    """Validate score submission data"""
    required_fields = ['player_uuid', 'player_name', 'seed', 'score', 'verification_hash']
    return all(field in score_data for field in required_fields)
```

## Quick Implementation Checklist

- [ ] Add `src/web_integration/score_client.py` to game
- [ ] Import and call `submit_score_if_enabled()` at game end
- [ ] Add score submission endpoint to website API
- [ ] Test with mock game session
- [ ] Add player preferences for leaderboard participation
- [ ] Update website to handle incoming scores
- [ ] Test end-to-end: game → API → leaderboard display

This gives you a complete score submission system that players can opt into for competitive play!