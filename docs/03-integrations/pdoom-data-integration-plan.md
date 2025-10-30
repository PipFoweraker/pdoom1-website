# pdoom-data Integration Plan

**Created:** 2025-10-30
**Status:** Planning Phase
**Target Version:** v1.2.0

## Overview

Integration plan for connecting pdoom1-website with the pdoom-data centralized data service. This will enable event log streaming, global leaderboards, analytics collection, and user authentication.

---

## Current State (v1.1.0)

### What We Have
- ✅ Weekly league system with local JSON storage
- ✅ Seed-specific leaderboards (15 seeds, 64+ entries)
- ✅ Static data sync from pdoom1 game repository
- ✅ GitHub Actions automation for data updates
- ✅ Admin monitoring dashboard at `/monitoring/`
- ✅ API server with 8 REST endpoints (local)

### What We're Missing
- ❌ Real-time event streaming from game sessions
- ❌ Persistent user accounts and authentication
- ❌ Cross-session analytics and player tracking
- ❌ Global leaderboards (across all players, not just local)
- ❌ Long-term data storage (PostgreSQL)
- ❌ Advanced analytics and insights

---

## pdoom-data Repository Architecture

Based on ecosystem documentation, pdoom-data provides:

### Infrastructure
- **Database:** PostgreSQL for persistent storage
- **API:** RESTful endpoints for data access
- **Auth:** User authentication system
- **Analytics:** Privacy-compliant data collection
- **Monitoring:** System health and performance tracking

### Expected Endpoints (To Be Confirmed)
```
POST   /api/events              - Submit game events
GET    /api/events/{session_id} - Retrieve session events
POST   /api/leaderboards        - Submit scores
GET    /api/leaderboards/global - Global rankings
POST   /api/auth/register       - User registration
POST   /api/auth/login          - User login
GET    /api/analytics/summary   - Aggregated stats
```

---

## Integration Phases

### Phase 1: Event Log Streaming (Priority 1)

**Goal:** Stream game events from pdoom1 to pdoom-data for analysis

**Architecture:**
```
pdoom1 (Game)
  └─> Event Generator
      └─> HTTP POST to pdoom-data
          └─> PostgreSQL Event Store
              └─> Analytics Pipeline
                  └─> pdoom1-website displays insights
```

**Event Types to Capture:**
1. **Game Session Events**
   - Session start/end
   - Turn progression
   - Win/loss conditions
   - Game duration

2. **Player Action Events**
   - Research decisions
   - Policy choices
   - Resource allocation
   - Critical game moments

3. **System Events**
   - Crashes/errors
   - Performance metrics
   - Configuration changes

**Implementation Steps:**
1. Define event schema (JSON format)
2. Create event submission endpoint in pdoom-data
3. Add event logging to pdoom1 game
4. Build event viewer in pdoom1-website
5. Create analytics dashboard for event insights

**Data Schema Example:**
```json
{
  "event_id": "uuid-v4",
  "session_id": "uuid-v4",
  "user_id": "anonymous-or-authenticated",
  "timestamp": "2025-10-30T12:34:56Z",
  "event_type": "research_completed",
  "event_data": {
    "research_name": "Interpretability Research",
    "turn_number": 42,
    "doom_level": 0.15,
    "resources_spent": 1000
  },
  "game_version": "v0.1.0",
  "platform": "windows",
  "privacy_consent": true
}
```

### Phase 2: Global Leaderboards (Priority 2)

**Goal:** Replace local JSON leaderboards with centralized PostgreSQL storage

**Migration Path:**
1. Keep existing local leaderboards working
2. Add dual-write (local + remote)
3. Verify data consistency
4. Switch primary read to remote
5. Deprecate local storage (keep as backup)

**Benefits:**
- Cross-player competition
- Persistent rankings across game updates
- Advanced filtering (by version, seed, date range)
- Cheat detection and validation
- Historical trend analysis

### Phase 3: User Authentication (Priority 3)

**Goal:** Optional user accounts for enhanced features

**Features:**
- Anonymous play (default)
- Optional account creation
- OAuth integration (GitHub, Google, Discord)
- Profile customization
- Achievement tracking
- Friend leaderboards

**Privacy Considerations:**
- Anonymous mode by default
- Explicit consent for data collection
- GDPR compliance
- Data export/deletion tools
- Transparent privacy policy

### Phase 4: Advanced Analytics (Priority 4)

**Goal:** Deep insights into player behavior and game balance

**Analytics Features:**
- Win rate analysis by strategy
- Popular research paths
- Difficulty curve optimization
- A/B testing infrastructure
- Cohort analysis
- Retention metrics

**Privacy-First Approach:**
- Aggregate data only (no individual tracking)
- Differential privacy techniques
- User opt-out respected
- Data anonymization
- Clear value proposition for users

---

## Technical Specifications

### Authentication Flow
```
pdoom1 (Game)
  └─> User launches game
      └─> Check for auth token
          ├─> If authenticated:
          │   └─> Load user profile from pdoom-data
          └─> If anonymous:
              └─> Generate session ID
                  └─> Optional: prompt for login

pdoom1-website
  └─> User visits site
      └─> OAuth login flow
          └─> JWT token issued
              └─> Token stored securely
                  └─> Game reads token for API calls
```

### Event Submission Flow
```
pdoom1 Game Loop
  └─> Event occurs (e.g., research completed)
      └─> Event logger captures data
          └─> Queue event for submission
              └─> Batch events (every 30s or 10 events)
                  └─> HTTP POST to pdoom-data/api/events
                      ├─> Success: Clear queue
                      └─> Failure: Retry with exponential backoff
                                   └─> After 3 failures: Write to local log
```

### Data Synchronization
```
Weekly League System (Current)
  └─> Local JSON files in pdoom1-website
      └─> GitHub Actions sync

Future State with pdoom-data
  └─> PostgreSQL in pdoom-data
      ├─> pdoom1 writes scores directly
      ├─> pdoom1-website reads via API
      └─> GitHub Actions backup to JSON (fallback)
```

---

## API Integration Requirements

### From pdoom1-website Perspective

**Endpoints We'll Call:**
```javascript
// Event retrieval for display
GET /api/events?session_id={id}
GET /api/events?user_id={id}&limit=100

// Leaderboards
GET /api/leaderboards/global?seed={seed}&limit=100
GET /api/leaderboards/weekly?week={week_id}

// Analytics
GET /api/analytics/summary
GET /api/analytics/trends?metric=doom_level&days=30

// User profiles (if authenticated)
GET /api/users/{user_id}/profile
GET /api/users/{user_id}/stats
```

**Configuration:**
```javascript
// config/pdoom-data.js
const PDOOM_DATA_CONFIG = {
  baseUrl: process.env.PDOOM_DATA_URL || 'https://api.pdoom-data.com',
  apiVersion: 'v1',
  timeout: 5000,
  retryAttempts: 3,
  cacheTTL: 300, // 5 minutes
  fallbackToLocal: true
};
```

---

## Privacy & Compliance

### Data Collection Policy

**Collected by Default (No Consent Required):**
- Game crash reports (anonymous)
- Performance metrics (aggregated)
- Error logs (no personal data)

**Collected with Consent:**
- Gameplay events and decisions
- Win/loss patterns
- Session duration and frequency
- Device/platform information

**Never Collected:**
- Personal identifying information
- Location data
- Biometric data
- Third-party tracking cookies

### GDPR Compliance Checklist
- [ ] Privacy policy clearly displayed
- [ ] Explicit consent mechanism
- [ ] Data export functionality
- [ ] Right to deletion (account + data)
- [ ] Data retention policies defined
- [ ] Breach notification procedures
- [ ] Data processing agreement with pdoom-data
- [ ] Cookie consent (if applicable)

---

## Development Timeline

### Immediate (v1.1.1 - November 2025)
- [ ] Document current state and requirements
- [ ] Review pdoom-data repository structure
- [ ] Define event schema v1.0
- [ ] Create integration RFC for team review

### Short-term (v1.2.0 - December 2025)
- [ ] Implement event logging in pdoom1
- [ ] Build event submission endpoint in pdoom-data
- [ ] Create event viewer UI in pdoom1-website
- [ ] Add monitoring for event pipeline

### Medium-term (v1.3.0 - Q1 2026)
- [ ] Migrate leaderboards to pdoom-data
- [ ] Implement dual-write pattern
- [ ] Build admin tools for data management
- [ ] Add analytics dashboard

### Long-term (v2.0.0 - Q2 2026)
- [ ] User authentication system
- [ ] Advanced analytics features
- [ ] Mobile app integration (if planned)
- [ ] Multi-game support infrastructure

---

## Testing Strategy

### Integration Testing
1. **Local Development:**
   - Mock pdoom-data API responses
   - Test offline resilience
   - Verify fallback mechanisms

2. **Staging Environment:**
   - Full stack integration tests
   - Load testing (1000 concurrent users)
   - Failover scenario testing

3. **Production Monitoring:**
   - Real-time error tracking
   - Performance monitoring
   - Data consistency checks

### Test Scenarios
- [ ] Event submission with network failure
- [ ] Authentication token expiration
- [ ] Database unavailability fallback
- [ ] High-latency API responses
- [ ] Malformed data handling
- [ ] Rate limiting behavior
- [ ] Cache invalidation

---

## Risk Assessment

### Technical Risks

**High Priority:**
- **Network dependency:** Game requires internet for events
  - *Mitigation:* Queue events locally, sync when online
- **API versioning:** Breaking changes in pdoom-data
  - *Mitigation:* Semantic versioning, deprecation notices
- **Data consistency:** Local vs remote state divergence
  - *Mitigation:* Conflict resolution strategy, checksums

**Medium Priority:**
- **Performance impact:** Event logging slows game
  - *Mitigation:* Async batching, performance profiling
- **Storage costs:** PostgreSQL hosting fees
  - *Mitigation:* Data retention policies, archival strategy

**Low Priority:**
- **Privacy compliance:** GDPR/CCPA violations
  - *Mitigation:* Legal review, privacy-by-design
- **Security:** API endpoint abuse
  - *Mitigation:* Rate limiting, authentication, monitoring

---

## Next Steps

### Immediate Actions (This Week)
1. ✅ Create this integration plan document
2. [ ] Clone pdoom-data repository and explore codebase
3. [ ] Review existing API endpoints and documentation
4. [ ] Schedule sync meeting with pdoom-data maintainers
5. [ ] Draft event schema RFC for feedback

### Investigation Required
- [ ] What events does pdoom1 currently log locally?
- [ ] What is the current state of pdoom-data API?
- [ ] Are there existing authentication mechanisms?
- [ ] What database schema exists in pdoom-data?
- [ ] Who maintains pdoom-data and what's the deployment status?

### Documentation Needed
- [ ] pdoom-data API reference
- [ ] Authentication flow diagrams
- [ ] Database schema documentation
- [ ] Privacy policy updates
- [ ] User-facing changelog

---

## Questions for pdoom-data Team

1. **Current Status:**
   - What's the current deployment status of pdoom-data?
   - Which API endpoints are operational?
   - What's the database schema?

2. **Architecture:**
   - Preferred authentication method (JWT, OAuth, API keys)?
   - Rate limiting policies?
   - Monitoring and alerting setup?

3. **Data Model:**
   - Event schema requirements?
   - Leaderboard data structure?
   - User profile fields?

4. **Operations:**
   - Who has deployment access?
   - What's the release cycle?
   - How are database migrations handled?

5. **Privacy:**
   - GDPR compliance status?
   - Data retention policies?
   - User consent mechanisms?

---

## Resources

- [Ecosystem Overview](../00-getting-started/ECOSYSTEM_OVERVIEW.md)
- [pdoom-data Repository](https://github.com/PipFoweraker/pdoom-data)
- [Current API Documentation](../03-integrations/game-repository-integration.md)
- [Privacy Policy Draft](/privacy/)

---

## Changelog

**2025-10-30:** Initial integration plan created
