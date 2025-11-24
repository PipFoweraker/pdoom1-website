# API Server Verification Integration Guide

**Date**: November 20, 2024
**Component**: pdoom1-website API Server v2
**Related**: pdoom1/docs/VERIFICATION_INTEGRATION_COMPLETE.md

---

## Overview

This guide shows how to integrate cumulative hash verification into the existing API server (api-server-v2.py).

**Files Created**:
- `scripts/db_migrations/003_add_verification_hashes.sql` - Database schema
- `scripts/verification_logic.py` - Verification handler module

---

## Step 1: Run Database Migration

### Prerequisites

- PostgreSQL database running
- `DATABASE_URL` environment variable set
- Existing schema from `001_initial_schema.sql` and `002_add_game_events.sql`

### Run Migration

```bash
cd pdoom1-website/scripts

# Method 1: Using psql directly
psql $DATABASE_URL -f db_migrations/003_add_verification_hashes.sql

# Method 2: Using run_migration.py (if available)
python run_migration.py --file db_migrations/003_add_verification_hashes.sql

# Method 3: Manual connection
psql -h localhost -U your_user -d pdoom1_db -f db_migrations/003_add_verification_hashes.sql
```

### Verify Migration

```sql
-- Check tables created
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('verification_hashes', 'hash_duplicates');

-- Expected output:
-- verification_hashes
-- hash_duplicates

-- Check views created
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public'
AND table_name LIKE 'v_%';

-- Expected output:
-- v_popular_strategies
-- v_rare_strategies
-- v_leaderboard_with_discoveries
```

---

## Step 2: Update API Server

### Import Verification Logic

Add to top of `api-server-v2.py`:

```python
# Add after existing imports
from verification_logic import (
    HashVerificationHandler,
    PlausibilityChecker,
    ScoreCalculator,
    VerificationError
)
```

### Update Score Submission Handler

Replace the existing `_handle_score_submission()` method in `ProductionAPIHandler` class:

```python
def _handle_score_submission(self, user_data: Dict):
    """Handle score submission with cumulative hash verification."""
    try:
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, "No data provided")
            return

        post_data = self.rfile.read(content_length)
        score_data = json.loads(post_data.decode('utf-8'))

        # Validate basic submission format
        if not self._validate_score_submission(score_data):
            self._send_error(400, "Invalid score submission")
            return

        user_id = user_data['sub']

        # Use verification handler for hash checking
        verification_handler = HashVerificationHandler(self.db_manager)

        try:
            response = verification_handler.process_submission(user_id, score_data)

            self._send_json_response(200, {
                "status": response["status"],
                "data": response["data"],
                "message": response["data"].get("message", "Score submitted successfully"),
                "timestamp": datetime.now().isoformat() + "Z"
            })

        except VerificationError as e:
            # Verification failed - reject submission
            self._send_error(400, f"Verification failed: {str(e)}")

    except json.JSONDecodeError:
        self._send_error(400, "Invalid JSON data")
    except Exception as e:
        print(f"Score submission error: {e}")
        import traceback
        traceback.print_exc()
        self._send_error(500, f"Score submission failed: {str(e)}")
```

### Update Validation Function

Update `_validate_score_submission()` to require verification hash and final_state:

```python
def _validate_score_submission(self, score_data: Dict[str, Any]) -> bool:
    """Validate score submission data."""
    required_fields = ['seed', 'score', 'verification_hash', 'timestamp', 'final_state']

    for field in required_fields:
        if field not in score_data:
            print(f"Missing required field: {field}")
            return False

    # Validate types
    if not isinstance(score_data['score'], int) or score_data['score'] < 0:
        print(f"Invalid score: {score_data['score']}")
        return False

    # Validate verification hash format
    if len(score_data['verification_hash']) != 64:
        print(f"Invalid hash length: {len(score_data['verification_hash'])}")
        return False

    # Validate final_state is dict
    if not isinstance(score_data['final_state'], dict):
        print(f"Invalid final_state type")
        return False

    return True
```

---

## Step 3: Update Score Calculation Formula

**CRITICAL**: The `ScoreCalculator.calculate_score()` function in `verification_logic.py` must match the game's exact scoring formula.

### Find Game's Scoring Formula

Check the Godot game code to find the scoring formula. Likely locations:
- `godot/scripts/game_manager.gd`
- `godot/scripts/core/game_state.gd`
- `godot/scripts/ui/game_over_screen.gd`

### Example Formula (Update as needed)

```gdscript
# In Godot (GDScript)
func calculate_final_score() -> int:
    var score = 0
    score += money * 0.1
    score += papers * 5000
    score += (100 - doom) * 1000
    score += researchers.size() * 2000
    return int(score)
```

### Update Python Formula to Match

```python
# In verification_logic.py ScoreCalculator class
@staticmethod
def calculate_score(final_state: Dict[str, Any]) -> int:
    """
    CRITICAL: Must match godot/scripts/game_manager.gd exactly!
    """
    money = final_state.get('money', 0)
    papers = final_state.get('papers', 0)
    doom = final_state.get('doom', 0)
    researchers = final_state.get('researchers', 0)

    score = 0
    score += money * 0.1
    score += papers * 5000
    score += (100 - doom) * 1000
    score += researchers * 2000

    return int(score)
```

**Verification**: Run test cases with known game states to ensure formulas match exactly.

---

## Step 4: Update Leaderboard Queries

### Query for Originals Only (Default)

```python
def _handle_seed_leaderboard(self, query_params: Dict[str, Any], seed: str):
    """Handle /api/leaderboards/seed/{seed} endpoint."""
    try:
        limit = int(query_params.get('limit', [100])[0])
        show_all = query_params.get('show_all', ['false'])[0].lower() == 'true'

        if show_all:
            # Show ALL submissions (originals + duplicates)
            query = """
                SELECT
                    le.entry_id,
                    u.pseudonym as player_name,
                    le.score,
                    le.submitted_at,
                    le.is_original_hash,
                    le.is_duplicate_hash,
                    vh.duplicate_count,
                    ROW_NUMBER() OVER (ORDER BY le.score DESC, le.submitted_at ASC) as rank
                FROM leaderboard_entries le
                JOIN users u ON le.user_id = u.user_id
                LEFT JOIN game_sessions gs ON le.session_id = gs.session_id
                LEFT JOIN verification_hashes vh ON gs.checksum = vh.verification_hash
                WHERE le.seed = %s AND u.opt_in_leaderboard = true
                ORDER BY le.score DESC, le.submitted_at ASC
                LIMIT %s
            """
        else:
            # Show ORIGINALS ONLY (default)
            query = """
                SELECT
                    le.entry_id,
                    u.pseudonym as player_name,
                    le.score,
                    le.submitted_at,
                    vh.duplicate_count,
                    ROW_NUMBER() OVER (ORDER BY le.score DESC, le.submitted_at ASC) as rank
                FROM leaderboard_entries le
                JOIN users u ON le.user_id = u.user_id
                LEFT JOIN game_sessions gs ON le.session_id = gs.session_id
                LEFT JOIN verification_hashes vh ON gs.checksum = vh.verification_hash
                WHERE le.seed = %s
                    AND u.opt_in_leaderboard = true
                    AND le.is_original_hash = TRUE
                ORDER BY le.score DESC, le.submitted_at ASC
                LIMIT %s
            """

        entries = self.db_manager.execute_query(query, (seed, limit))

        # Format for response
        formatted_entries = []
        for entry in entries:
            formatted_entries.append({
                "rank": entry['rank'],
                "player_name": entry['player_name'],
                "score": entry['score'],
                "date": entry['submitted_at'].isoformat(),
                "is_original": entry.get('is_original_hash', True),
                "duplicate_count": entry.get('duplicate_count', 0)
            })

        response = {
            "status": "success",
            "data": {
                "seed": seed,
                "entries": formatted_entries,
                "count": len(formatted_entries),
                "mode": "all" if show_all else "originals_only"
            }
        }

        self._send_json_response(200, response)

    except Exception as e:
        print(f"Leaderboard error: {e}")
        self._send_error(500, f"Failed to fetch leaderboard: {str(e)}")
```

---

## Step 5: Testing

### Manual Testing Flow

**1. Submit Original Score**

```bash
# Get auth token first
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"pseudonym": "TestPlayer1", "opt_in_leaderboard": true}'

# Login
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pseudonym": "TestPlayer1"}'

# Expected response: {"status": "success", "data": {"token": "eyJ..."}}

# Submit score (replace TOKEN)
curl -X POST http://localhost:8080/api/scores/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "seed": "test-seed-001",
    "score": 125000,
    "verification_hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
    "game_version": "0.10.2",
    "timestamp": 1732118400,
    "final_state": {
      "turn": 50,
      "money": 125000,
      "doom": 45.5,
      "papers": 5,
      "research": 120,
      "compute": 350,
      "researchers": 8
    },
    "duration_seconds": 1800
  }'

# Expected response:
# {
#   "status": "success",
#   "data": {
#     "hash_status": "original",
#     "message": "First player to achieve this strategy!",
#     "rank": 1
#   }
# }
```

**2. Submit Duplicate (Same Hash, Different Player)**

```bash
# Create second player
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"pseudonym": "TestPlayer2", "opt_in_leaderboard": true}'

# Login as Player 2
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pseudonym": "TestPlayer2"}'

# Submit SAME hash
curl -X POST http://localhost:8080/api/scores/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_PLAYER2" \
  -d '{
    "seed": "test-seed-001",
    "score": 125000,
    "verification_hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
    ...
  }'

# Expected response:
# {
#   "status": "success",
#   "data": {
#     "hash_status": "duplicate",
#     "message": "Strategy already discovered X seconds ago by another player",
#     "duplicate_count": 1
#   }
# }
```

**3. Test Plausibility Rejection**

```bash
# Submit impossible score (doom > 100)
curl -X POST http://localhost:8080/api/scores/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "final_state": {
      "doom": 150.0  # IMPOSSIBLE
    },
    ...
  }'

# Expected response:
# {
#   "status": "error",
#   "message": "Verification failed: Implausible game state: doom 150.0"
# }
```

---

## Step 6: Monitoring & Admin Tools

### Check Flagged Hashes (Admin Dashboard)

```sql
-- Get all flagged rapid duplicates
SELECT
    vh.verification_hash,
    vh.seed,
    vh.duplicate_count,
    vh.flag_reason,
    vh.flagged_at,
    u.pseudonym as first_discoverer
FROM verification_hashes vh
LEFT JOIN users u ON vh.first_submitted_by = u.user_id
WHERE vh.rapid_duplicate_flag = TRUE
ORDER BY vh.flagged_at DESC;
```

### Popular Strategies Query

```sql
-- Most reproduced strategies
SELECT * FROM v_popular_strategies
LIMIT 10;
```

### Rare Strategies Query

```sql
-- Unique strategies (zero duplicates)
SELECT * FROM v_rare_strategies
LIMIT 10;
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Database migration run successfully
- [ ] `verification_logic.py` module created
- [ ] API server updated with new handler
- [ ] Score calculation formula matches game exactly
- [ ] Manual testing completed (original, duplicate, rejection)
- [ ] Leaderboard queries updated

### Testing

- [ ] Unit tests for PlausibilityChecker
- [ ] Unit tests for ScoreCalculator
- [ ] Integration test: game → API → database
- [ ] Load test: 100+ concurrent submissions
- [ ] Cross-platform hash consistency verified

### Production

- [ ] Backup database before migration
- [ ] Run migration on production database
- [ ] Deploy updated API server
- [ ] Monitor error logs for 24 hours
- [ ] Check flagged_hashes table for anomalies
- [ ] Verify leaderboard displays correctly

---

## Rollback Procedure

If issues occur:

```sql
-- Drop new tables (WARNING: Loses verification data)
DROP TABLE IF EXISTS hash_duplicates CASCADE;
DROP TABLE IF NOT EXISTS verification_hashes CASCADE;

-- Drop new columns
ALTER TABLE leaderboard_entries DROP COLUMN IF EXISTS is_original_hash;
ALTER TABLE leaderboard_entries DROP COLUMN IF EXISTS is_duplicate_hash;
ALTER TABLE users DROP COLUMN IF EXISTS display_discoveries;
ALTER TABLE users DROP COLUMN IF EXISTS verified_external_account;

-- Restore old API server version
git checkout HEAD~1 scripts/api-server-v2.py
python scripts/api-server-v2.py --production
```

---

## Troubleshooting

### "Verification hash not found" Error

**Cause**: Hash not in database after first submission
**Fix**: Check that `_handle_original_submission()` is inserting into `verification_hashes` table

### Score Mismatch Errors

**Cause**: Client and server scoring formulas don't match
**Fix**:
1. Extract exact formula from Godot code
2. Update `ScoreCalculator.calculate_score()`
3. Test with known game states
4. Consider adding tolerance (default 100 points)

### Rapid Duplicate Flags (False Positives)

**Cause**: Popular strategy guide published, many players reproduce
**Action**:
- Check `hash_duplicates` table for patterns
- If legitimate (e.g., YouTube guide), clear flag:
  ```sql
  UPDATE verification_hashes
  SET rapid_duplicate_flag = FALSE,
      flag_reason = NULL
  WHERE hash_id = X;
  ```

### Database Connection Errors

**Cause**: Connection pool exhausted
**Fix**: Increase `max_conn` in `DatabaseManager.initialize_pool()`

---

## Next Steps

After successful deployment:

1. **Week 3**: End-to-end testing, load testing, monitoring
2. **Week 4**: Launch announcement, community feedback
3. **Post-launch**: Iterate based on real-world usage

---

**Status**: Ready for integration testing
**Updated**: November 20, 2024
**Contact**: See pdoom1/docs/VERIFICATION_INTEGRATION_COMPLETE.md
