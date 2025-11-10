# Game Client Integration Testing Checklist

**Issue**: #64
**Production API**: `https://api.pdoom1.com`
**Created**: 2025-11-10
**Status**: Ready for Testing

---

## Overview

This checklist covers integration testing for the pdoom1 Unity game client with the production API at `https://api.pdoom1.com`.

---

## Pre-Integration Setup

### Development Environment

- [ ] Unity project is up to date (latest commit from pdoom1 repo)
- [ ] API base URL updated to `https://api.pdoom1.com` in game configuration
- [ ] Test user accounts created on production API
- [ ] Network connectivity to api.pdoom1.com verified

### API Verification

Test that the production API is accessible:

```bash
# Health check
curl https://api.pdoom1.com/api/health

# Expected: HTTP 200 with "status": "healthy"
```

---

## 1. Authentication Flow

### User Registration

- [ ] **Test**: Create new user account from game client
  - Username: `TestUser_$(date +%s)`
  - Email: `test@example.com`
  - Expected: HTTP 201, JWT token returned
  - Expected: Token stored in PlayerPrefs/SecureStorage

- [ ] **Test**: Attempt duplicate username registration
  - Expected: HTTP 409 conflict error
  - Expected: Error message displayed to user

- [ ] **Test**: Invalid username format
  - Test usernames: `ab`, `user@name`, `user name`
  - Expected: HTTP 400 validation error

**Endpoint**: `POST /api/auth/register`

**Test Code** (Unity C#):
```csharp
public class AuthenticationTests {
    [Test]
    public async Task TestUserRegistration() {
        var username = $"TestUser_{DateTime.UtcNow.Ticks}";
        var response = await APIClient.Register(username, "test@example.com");

        Assert.AreEqual(201, response.StatusCode);
        Assert.IsNotNull(response.Data.Token);
        Assert.AreEqual(username, response.Data.Pseudonym);
    }
}
```

### User Login

- [ ] **Test**: Login with existing credentials
  - Expected: HTTP 200, JWT token returned
  - Expected: User data populated

- [ ] **Test**: Login with non-existent username
  - Expected: HTTP 404 not found

- [ ] **Test**: Token expiry handling (24 hours)
  - Simulate expired token
  - Expected: Re-authentication triggered

**Endpoint**: `POST /api/auth/login`

---

## 2. Score Submission

### Valid Score Submission

- [ ] **Test**: Submit score after completing a game
  - Game session data populated
  - Final score calculated
  - Checksum generated
  - Expected: HTTP 201, score accepted

- [ ] **Test**: Verify leaderboard entry created
  - Query leaderboard for submitted score
  - Expected: Score appears in correct position

**Endpoint**: `POST /api/scores/submit`

**Required Fields**:
```json
{
  "seed": "weekly-2025-W45-abc123",
  "config_hash": "sha256-of-config",
  "game_version": "1.0.0",
  "final_score": 1500,
  "final_turn": 42,
  "victory_type": "time",
  "duration_seconds": 3600.5,
  "game_metadata": {
    "final_pdoom": 0.15,
    "final_money": 50000,
    "final_staff": 12
  }
}
```

### Score Validation

- [ ] **Test**: Submit score without authentication
  - Expected: HTTP 401 unauthorized

- [ ] **Test**: Submit negative score
  - Expected: HTTP 400 validation error

- [ ] **Test**: Submit score with invalid checksum
  - Expected: Score marked as unverified

- [ ] **Test**: Rapid score submissions (rate limiting)
  - Submit 5 scores in quick succession
  - Expected: Some requests rate-limited (HTTP 429)

---

## 3. Leaderboard Retrieval

### Current Leaderboard

- [ ] **Test**: Fetch current weekly leaderboard
  - Expected: HTTP 200, array of entries
  - Expected: Entries sorted by score descending
  - Expected: Pagination working (limit/offset)

**Endpoint**: `GET /api/leaderboards/current?limit=10&offset=0`

**Expected Response**:
```json
{
  "status": "success",
  "data": {
    "leaderboard": [
      {
        "entry_id": "uuid",
        "player_name": "TestUser",
        "score": 1500,
        "rank": 1,
        "submitted_at": "2025-11-10T12:00:00Z"
      }
    ],
    "pagination": {
      "total": 42,
      "limit": 10,
      "offset": 0
    }
  }
}
```

### Seed-Specific Leaderboard

- [ ] **Test**: Fetch leaderboard for specific seed
  - Seed: Current weekly seed
  - Expected: Only entries for that seed returned

**Endpoint**: `GET /api/leaderboards/seed/weekly-2025-W45-abc123`

### Player Rank

- [ ] **Test**: Verify player's own rank displayed correctly
  - Submit score
  - Fetch leaderboard
  - Expected: Player's entry highlighted
  - Expected: Rank calculation correct

---

## 4. Game Events API (NEW)

### List Events

- [ ] **Test**: Fetch all active events
  - Expected: HTTP 200, array of events

**Endpoint**: `GET /api/events?limit=50`

- [ ] **Test**: Filter events by type
  - Types to test: `combat`, `economic`, `narrative`, `research`, `political`
  - Expected: Only matching events returned

**Endpoint**: `GET /api/events?type=combat`

- [ ] **Test**: Filter events by difficulty
  - Difficulty range: 3-7
  - Expected: Events within range returned

**Endpoint**: `GET /api/events?difficulty_min=3&difficulty_max=7`

- [ ] **Test**: Filter events by tags
  - Tags: `boss`, `crisis`, `funding-boost`
  - Expected: Events with ANY matching tag returned

**Endpoint**: `GET /api/events?tags=boss,crisis`

### Single Event

- [ ] **Test**: Fetch specific event by ID
  - Get event_id from list response
  - Expected: Full event details returned

**Endpoint**: `GET /api/events/{event_id}`

- [ ] **Test**: Fetch non-existent event
  - Random UUID
  - Expected: HTTP 404

### Random Event

- [ ] **Test**: Get random event (no filters)
  - Expected: HTTP 200, single event returned
  - Repeat 5 times, verify different events returned

**Endpoint**: `GET /api/events/random`

- [ ] **Test**: Get random event with filters
  - Filter: `type=combat&difficulty_max=5`
  - Expected: Event matches criteria

- [ ] **Test**: Get random event with impossible criteria
  - Filter: `type=combat&difficulty_min=15`
  - Expected: HTTP 404

---

## 5. Network Error Handling

### Connectivity

- [ ] **Test**: Handle network disconnection
  - Disable network mid-request
  - Expected: Timeout error, graceful fallback

- [ ] **Test**: Handle slow connection (>5s response time)
  - Throttle network speed
  - Expected: Loading indicator shown, eventually completes or times out

### API Errors

- [ ] **Test**: Handle 500 Internal Server Error
  - Trigger server error (if test endpoint available)
  - Expected: Error message displayed, retry option offered

- [ ] **Test**: Handle 503 Service Unavailable
  - Expected: "Service temporarily down" message

### CORS

- [ ] **Test**: Verify CORS headers accepted
  - Origin: https://pdoom1.com
  - Expected: Requests succeed

- [ ] **Test**: Verify invalid origin rejected
  - (Only testable from non-game environment)

---

## 6. Data Persistence

### Local Storage

- [ ] **Test**: JWT token persists between game sessions
  - Login, close game, reopen
  - Expected: Still authenticated

- [ ] **Test**: User preferences sync
  - Update privacy settings
  - Expected: Saved to API, retrieved on next login

### Offline Mode

- [ ] **Test**: Game playable without network
  - Disable network
  - Expected: Single-player mode works
  - Expected: Scores queued for later submission

- [ ] **Test**: Score sync after reconnection
  - Submit score offline
  - Reconnect
  - Expected: Queued scores submitted automatically

---

## 7. Performance Testing

### Load Testing

- [ ] **Test**: Concurrent leaderboard requests
  - 10 simultaneous requests
  - Expected: All complete successfully within 5s

- [ ] **Test**: Large leaderboard pagination
  - Fetch offset=1000, limit=100
  - Expected: Completes within 3s

### Bandwidth

- [ ] **Test**: Measure API request sizes
  - Auth request: ~500 bytes
  - Score submission: ~1KB
  - Leaderboard fetch: ~5KB (10 entries)
  - Expected: Under 10KB for typical operations

---

## 8. Security Testing

### Authentication

- [ ] **Test**: Expired JWT token handling
  - Use token older than 24 hours
  - Expected: HTTP 401, re-authentication required

- [ ] **Test**: Invalid JWT token
  - Modify token string
  - Expected: HTTP 401

- [ ] **Test**: Token injection prevention
  - Attempt to use another user's token
  - Expected: Can only access own data

### Data Validation

- [ ] **Test**: SQL injection protection
  - Username: `'; DROP TABLE users; --`
  - Expected: Treated as literal string, no database impact

- [ ] **Test**: XSS protection
  - Username: `<script>alert('xss')</script>`
  - Expected: Escaped/rejected

---

## 9. Cross-Platform Testing

### Desktop (Windows/Mac/Linux)

- [ ] **Test**: Full integration on Windows
- [ ] **Test**: Full integration on macOS
- [ ] **Test**: Full integration on Linux

### Mobile (iOS/Android)

- [ ] **Test**: Authentication on mobile
- [ ] **Test**: Score submission on mobile
- [ ] **Test**: Leaderboard display on mobile
- [ ] **Test**: Network switching (WiFi <-> cellular)

### WebGL

- [ ] **Test**: CORS compatibility in browser
- [ ] **Test**: localStorage for token persistence

---

## 10. Edge Cases

### Unusual Inputs

- [ ] **Test**: Empty username
  - Expected: HTTP 400

- [ ] **Test**: 50-character username (max length)
  - Expected: Accepted

- [ ] **Test**: 51-character username
  - Expected: HTTP 400

- [ ] **Test**: Zero score
  - Expected: Accepted (valid score)

- [ ] **Test**: Maximum integer score (2,147,483,647)
  - Expected: Accepted

### Race Conditions

- [ ] **Test**: Rapid login/logout cycles
  - Expected: No token conflicts

- [ ] **Test**: Submit score twice with same session data
  - Expected: Second submission rejected or creates separate entry

---

## 11. Monitoring & Logging

### Client-Side Logging

- [ ] **Test**: API requests logged to console
  - Expected: URL, method, status code visible

- [ ] **Test**: Errors logged with stack traces
  - Expected: Detailed error info for debugging

### Analytics

- [ ] **Test**: API call analytics (if implemented)
  - Track: request count, latency, error rate
  - Expected: Metrics visible in game analytics dashboard

---

## 12. Regression Testing

After Each API Update:

- [ ] Re-run all authentication tests
- [ ] Re-run all score submission tests
- [ ] Re-run all leaderboard tests
- [ ] Verify backward compatibility

---

## Automated Testing

### Unity Test Framework

Create automated tests for critical paths:

```csharp
[UnityTest]
public IEnumerator TestCompleteGameFlow() {
    // 1. Register user
    var username = $"AutoTest_{DateTime.UtcNow.Ticks}";
    var registerTask = APIClient.Register(username, "test@example.com");
    yield return new WaitUntil(() => registerTask.IsCompleted);
    Assert.IsNotNull(registerTask.Result.Token);

    // 2. Submit score
    var scoreTask = APIClient.SubmitScore(new GameSession {
        Seed = "test-seed",
        FinalScore = 1000,
        // ... other fields
    });
    yield return new WaitUntil(() => scoreTask.IsCompleted);
    Assert.AreEqual(201, scoreTask.Result.StatusCode);

    // 3. Verify on leaderboard
    var leaderboardTask = APIClient.GetLeaderboard("test-seed");
    yield return new WaitUntil(() => leaderboardTask.IsCompleted);
    Assert.IsTrue(leaderboardTask.Result.Data.Leaderboard.Any(e => e.PlayerName == username));
}
```

---

## Success Criteria

### Must Pass (Blocking):
- ✅ All authentication flows work
- ✅ Score submission succeeds
- ✅ Leaderboards display correctly
- ✅ No security vulnerabilities found
- ✅ Performance within acceptable limits (<5s for any operation)

### Should Pass (Non-Blocking):
- ✅ Offline mode functions
- ✅ All platforms tested
- ✅ Edge cases handled gracefully

---

## Test Environment Details

### Production API
- **URL**: `https://api.pdoom1.com`
- **Database**: PostgreSQL 16 on DreamHost VPS
- **SSL**: Let's Encrypt (verify cert valid)
- **Rate Limiting**: 60 req/min (general), 10 req/min (auth)

### Test Accounts
Create these accounts for testing:
- `TestUser_Standard` - Normal user
- `TestUser_Admin` - Admin permissions (future)
- `TestUser_Unverified` - Unverified scores

---

## Reporting Issues

When a test fails, create a GitHub issue with:

**Template**:
```markdown
## Test Failure: [Test Name]

**Endpoint**: POST /api/scores/submit
**Expected**: HTTP 201 with score ID
**Actual**: HTTP 500 Internal Server Error

**Steps to Reproduce**:
1. Authenticate as TestUser_Standard
2. Submit score with seed "test-seed-123"
3. Observe error

**Error Response**:
\`\`\`json
{
  "status": "error",
  "message": "Database connection failed"
}
\`\`\`

**Impact**: Blocking - users cannot submit scores
**Priority**: High
```

---

## Sign-Off

### Tester Information
- **Tested by**: _____________
- **Date**: _____________
- **Game Version**: _____________
- **API Version**: v2 (2025-11-10)

### Test Results
- **Total Tests**: _____ / _____
- **Passed**: _____
- **Failed**: _____
- **Blocked**: _____

### Approval
- [ ] All blocking issues resolved
- [ ] Performance acceptable
- [ ] Security verified
- [ ] **Approved for Production**: YES / NO

**Signature**: _________________ **Date**: _____________

---

**Last Updated**: 2025-11-10
**Issue**: #64
**Related Docs**:
- [API Deployment Guide](../deployment/DREAMHOST_VPS_DEPLOYMENT.md)
- [Security Audit](../security/SECURITY_AUDIT_2025-11-10.md)
- [Game Events Deployment](../deployment/GAME_EVENTS_DEPLOYMENT.md)
