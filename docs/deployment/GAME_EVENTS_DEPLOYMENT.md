# Game Events API Deployment Guide

**Feature**: Game Events Table + API Endpoints
**Issue**: #67
**Created**: 2025-11-10
**Status**: Ready for Deployment

---

## Overview

This deployment adds a new `game_events` table to the database and implements 3 new API endpoints for serving dynamic game content.

### New Endpoints:
1. `GET /api/events` - List events with filtering
2. `GET /api/events/{event_id}` - Get single event
3. `GET /api/events/random` - Get random event

---

## Pre-Deployment Checklist

- [ ] Production database backup completed
- [ ] API server v2 code updated (scripts/api-server-v2.py)
- [ ] Migration file ready (scripts/db_migrations/002_add_game_events.sql)
- [ ] Dependencies up to date (PyJWT 2.10.1+, psycopg2-binary 2.9.10)
- [ ] SSH access to production server verified

---

## Deployment Steps

### Step 1: Backup Production Database

```bash
# SSH into production server
ssh -i pdoom-website-instance.pem ubuntu@208.113.200.215

# Create backup
sudo -u postgres pg_dump pdoom1 > ~/backups/pdoom1_before_events_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh ~/backups/
```

### Step 2: Update Python Dependencies

```bash
# Navigate to application directory
cd /var/www/pdoom1-api

# Activate virtual environment
source venv/bin/activate

# Update dependencies
pip install --upgrade PyJWT==2.10.1 psycopg2-binary==2.9.10

# Verify installations
pip list | grep -E "PyJWT|psycopg2"
```

Expected output:
```
psycopg2-binary    2.9.10
PyJWT              2.10.1
```

### Step 3: Pull Latest Code

```bash
# From application directory
git fetch origin
git pull origin main

# Verify new files exist
ls -l scripts/db_migrations/002_add_game_events.sql
ls -l scripts/api-server-v2.py
```

### Step 4: Run Database Migration

```bash
# Connect to PostgreSQL as pdoom_api user
psql "postgresql://pdoom_api:YOUR_PASSWORD@localhost:5432/pdoom1"
```

In the PostgreSQL prompt:
```sql
-- Run the migration
\i scripts/db_migrations/002_add_game_events.sql

-- Verify table was created
\dt game_events

-- Check sample data
SELECT COUNT(*) FROM game_events;
SELECT event_type, COUNT(*) FROM game_events GROUP BY event_type;

-- Verify indexes
\di idx_game_events*

-- Exit
\q
```

Expected results:
- Table `game_events` created
- 5 sample events inserted
- 6 indexes created
- 2 functions created (get_random_event, get_events_by_type)

### Step 5: Restart API Server

```bash
# Restart the systemd service
sudo systemctl restart pdoom-api

# Check status
sudo systemctl status pdoom-api

# View logs
sudo journalctl -u pdoom-api -n 50 --no-pager

# Look for this line:
# "✅ JWT authentication initialized"
```

### Step 6: Verify API Endpoints

```bash
# Test health check
curl https://api.pdoom1.com/api/health

# Test events list (should return 5 sample events)
curl https://api.pdoom1.com/api/events

# Test events by type
curl "https://api.pdoom1.com/api/events?type=combat"

# Test random event
curl "https://api.pdoom1.com/api/events/random?difficulty_min=5&difficulty_max=8"

# Test single event (replace UUID with actual event_id from previous call)
curl https://api.pdoom1.com/api/events/YOUR_EVENT_ID_HERE
```

Expected responses:
- HTTP 200 OK
- JSON with `"status": "success"`
- Event data with all fields populated

---

## API Endpoint Specifications

### GET /api/events

**Description**: List all active events with optional filtering

**Query Parameters**:
- `type` (string): Filter by event_type (`combat`, `economic`, `narrative`, `research`, `political`)
- `difficulty` (integer): Exact difficulty (1-10)
- `difficulty_min` (integer): Minimum difficulty
- `difficulty_max` (integer): Maximum difficulty
- `tags` (string): Comma-separated tags (e.g., `boss,crisis`)
- `category` (string): Filter by category
- `limit` (integer): Max results (default: 50, max: 200)
- `offset` (integer): Pagination offset (default: 0)

**Example**:
```bash
curl "https://api.pdoom1.com/api/events?type=combat&difficulty_min=7&limit=10"
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "events": [
      {
        "event_id": "uuid-here",
        "name": "Rogue AI Incident",
        "description": "An experimental AI system...",
        "event_type": "combat",
        "category": "ai_safety",
        "difficulty": 8,
        "impact_pdoom": 0.15,
        "impact_funding": -0.10,
        "parameters": {...},
        "tags": ["crisis", "high-stakes"],
        "created_at": "2025-11-10T...",
        "updated_at": "2025-11-10T..."
      }
    ],
    "pagination": {
      "total": 1,
      "limit": 10,
      "offset": 0,
      "returned": 1
    }
  },
  "timestamp": "2025-11-10T..."
}
```

### GET /api/events/{event_id}

**Description**: Get a single event by UUID

**Example**:
```bash
curl https://api.pdoom1.com/api/events/550e8400-e29b-41d4-a716-446655440000
```

**Response**: Same event structure as above, but single object instead of array

### GET /api/events/random

**Description**: Get a random event matching optional criteria

**Query Parameters**:
- `type` (string): Filter by event_type
- `difficulty_min` (integer): Minimum difficulty
- `difficulty_max` (integer): Maximum difficulty
- `tags` (string): Comma-separated tags

**Example**:
```bash
curl "https://api.pdoom1.com/api/events/random?type=combat&difficulty_max=5"
```

**Response**: Single event object

---

## Rollback Plan

If deployment fails, rollback using these steps:

### Rollback Step 1: Revert Code

```bash
cd /var/www/pdoom1-api
git log --oneline -10  # Find previous commit
git checkout PREVIOUS_COMMIT_HASH

# Restart service
sudo systemctl restart pdoom-api
```

### Rollback Step 2: Drop game_events Table

```bash
psql "postgresql://pdoom_api:YOUR_PASSWORD@localhost:5432/pdoom1"
```

```sql
-- Drop table and related objects
DROP TABLE IF EXISTS game_events CASCADE;
DROP FUNCTION IF EXISTS get_random_event CASCADE;
DROP FUNCTION IF EXISTS get_events_by_type CASCADE;
DROP FUNCTION IF EXISTS update_game_events_updated_at CASCADE;

-- Verify cleanup
\dt game_events
```

### Rollback Step 3: Restore from Backup (if needed)

```bash
# Only if database corruption occurred
sudo -u postgres psql pdoom1 < ~/backups/pdoom1_before_events_TIMESTAMP.sql
```

---

## Post-Deployment

### Update Documentation

- [x] README.md updated with new endpoints
- [ ] Update API documentation (if separate docs exist)
- [ ] Notify game client team about new endpoints

### Monitor Performance

```bash
# Watch API logs for errors
sudo journalctl -u pdoom-api -f

# Check database performance
psql "postgresql://pdoom_api:YOUR_PASSWORD@localhost:5432/pdoom1"
```

```sql
-- Check query performance
EXPLAIN ANALYZE
SELECT * FROM game_events
WHERE event_type = 'combat' AND difficulty >= 5
ORDER BY difficulty ASC
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'game_events'
ORDER BY idx_scan DESC;
```

### Next Steps (Issue #67 Follow-up)

- [ ] Import real event data from pdoom-data (Issue #20)
- [ ] Integrate with pdoom1 game client (Issue #64)
- [ ] Add event analytics tracking
- [ ] Create admin endpoints for event management

---

## Troubleshooting

### Issue: Migration fails with "relation already exists"

**Solution**:
```sql
-- Check if table exists
\dt game_events

-- If it exists but is empty/corrupted, drop and recreate
DROP TABLE game_events CASCADE;
\i scripts/db_migrations/002_add_game_events.sql
```

### Issue: API returns 500 error for /api/events

**Check**:
1. Verify table exists: `\dt game_events`
2. Check API logs: `sudo journalctl -u pdoom-api -n 100`
3. Test database connection: `psql "postgresql://pdoom_api:PASSWORD@localhost:5432/pdoom1"`

### Issue: No events returned (empty array)

**Check**:
```sql
-- Verify sample data was inserted
SELECT COUNT(*) FROM game_events WHERE is_active = TRUE;

-- If empty, re-run sample data section of migration
-- (lines 196-234 in 002_add_game_events.sql)
```

---

## Security Notes

- ✅ All SQL queries use parameterized statements (no injection risk)
- ✅ Endpoints are public (no authentication required) - events are non-sensitive
- ✅ Rate limiting should be applied at Nginx level
- ✅ Maximum limit of 200 events per request prevents abuse

---

## Database Schema Summary

**Table**: `game_events`

**Columns**:
- `event_id` (UUID, primary key)
- `name` (VARCHAR, required)
- `description` (TEXT)
- `event_type` (VARCHAR): combat, economic, narrative, research, political, random, special
- `category` (VARCHAR)
- `difficulty` (INTEGER, 1-10)
- `impact_pdoom` (FLOAT, -1.0 to 1.0)
- `impact_funding` (FLOAT, -1.0 to 1.0)
- `parameters` (JSONB): flexible event configuration
- `tags` (TEXT[]): searchable tags
- `source` (VARCHAR): data source identifier
- `created_at`, `updated_at` (TIMESTAMP)
- `is_active` (BOOLEAN): whether event can be served

**Indexes**: 6 indexes for fast filtering (type, difficulty, tags, category, composite)

**Functions**: 2 helper functions (get_random_event, get_events_by_type)

---

## Contact

**Deployed by**: Claude Code
**Date**: 2025-11-10
**Related Issue**: #67
**Next Review**: After production testing

For issues or questions, refer to the security audit: [docs/security/SECURITY_AUDIT_2025-11-10.md](../security/SECURITY_AUDIT_2025-11-10.md)
