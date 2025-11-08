# P(Doom)1 API Server Documentation

## Overview

The P(Doom)1 ecosystem uses a two-stage API architecture:

1. **API Server v1 (Bridge)**: File-based development server (`scripts/api-server.py`)
2. **API Server v2 (Production)**: PostgreSQL-backed production server (`scripts/api-server-v2.py`)

## Quick Start

### Local Development (Bridge Server)

```bash
# No dependencies required - uses Python stdlib only
python scripts/api-server.py
```

This starts the bridge server on `http://localhost:8080` with mock/file-based data.

### Production Server (Local Testing)

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and set:
# - DATABASE_URL=postgresql://user:pass@localhost:5432/pdoom1
# - JWT_SECRET=(generate with: python -c 'import secrets; print(secrets.token_hex(32))')

# Run database migrations
psql $DATABASE_URL < scripts/db_migrations/001_initial_schema.sql

# Start production server
python scripts/api-server-v2.py
```

## API Endpoints

### Public Endpoints (No Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/status` | Integration status |
| POST | `/api/auth/register` | Create user account |
| POST | `/api/auth/login` | Authenticate user |

### Protected Endpoints (Requires JWT Token)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/users/profile` | Get user profile | ✅ |
| POST | `/api/scores/submit` | Submit game score | ✅ |
| GET | `/api/leaderboards/current` | Current leaderboard | Optional |
| GET | `/api/leaderboards/seed/{seed}` | Seed-specific leaderboard | Optional |
| GET | `/api/stats` | Aggregated game statistics | Optional |

## Authentication Flow

### 1. Register a New User

```bash
POST /api/auth/register
Content-Type: application/json

{
  "pseudonym": "YourGamertag",
  "opt_in_leaderboard": true,
  "opt_in_analytics": false
}
```

Response:
```json
{
  "status": "success",
  "data": {
    "user_id": "uuid-here",
    "pseudonym": "YourGamertag",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "created_at": "2025-11-08T10:00:00Z"
  }
}
```

### 2. Login (Existing User)

```bash
POST /api/auth/login
Content-Type: application/json

{
  "pseudonym": "YourGamertag"
}
```

Response:
```json
{
  "status": "success",
  "data": {
    "user_id": "uuid-here",
    "pseudonym": "YourGamertag",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 3. Use Token for Authenticated Requests

```bash
POST /api/scores/submit
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{
  "seed": "competitive-2025-W45",
  "score": 1250,
  "verification_hash": "sha256-hash-here",
  "timestamp": "2025-11-08T10:30:00Z",
  "final_metrics": {
    "final_doom": 15.2,
    "final_money": 500000,
    "final_staff": 25,
    "final_reputation": 85.5
  }
}
```

## Architecture Comparison

### Bridge Server (v1)
- **File Storage**: JSON files in `public/leaderboard/data/`
- **No Authentication**: Open endpoints
- **Dependencies**: None (Python stdlib only)
- **Use Case**: Local development, testing
- **Deployment**: Simple HTTP server

### Production Server (v2)
- **Database**: PostgreSQL with connection pooling
- **Authentication**: JWT tokens with 24-hour expiry
- **Dependencies**: psycopg2, PyJWT, python-dotenv
- **Use Case**: Production deployment
- **Deployment**: Railway, Render, or self-hosted

## Environment Variables

### Bridge Server (v1)
```env
PORT=8080
CORS_ORIGINS=*
```

### Production Server (v2)
```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
JWT_SECRET=your-secret-key-here
PORT=8080
CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com
API_MODE=production
```

## Database Schema

See [`scripts/db_migrations/001_initial_schema.sql`](../scripts/db_migrations/001_initial_schema.sql) for complete schema.

### Key Tables
- **users**: User accounts with privacy settings
- **game_sessions**: Individual game playthroughs
- **leaderboard_entries**: Competitive scores
- **weekly_challenges**: Weekly competitive events
- **blog_entries**: Content synced from game repository
- **analytics_events**: Privacy-respecting analytics (90-day retention)

## Deployment

### Option 1: Railway (Recommended)

See [Railway Deployment Guide](deployment/RAILWAY_DEPLOYMENT.md) for step-by-step instructions.

**Pros**:
- Managed PostgreSQL included
- Auto-scaling and HTTPS
- Free tier available
- Simple GitHub integration

**Estimated Cost**: $10-20/month production

### Option 2: DreamHost (Static Website Only)

DreamHost is used for static website hosting, not for the API server.

See [DreamHost Deployment Guide](02-deployment/deploy-dreamhost.md).

### Option 3: Self-Hosted

Requirements:
- VPS with PostgreSQL
- Nginx reverse proxy
- SSL certificate (Let's Encrypt)
- systemd service management

See [Self-Hosted Guide](deployment/SELF_HOSTED.md) (TODO).

## Security Features

### API Server v2
- ✅ JWT authentication with expiring tokens
- ✅ CORS restrictions in production mode
- ✅ SQL injection prevention (parameterized queries)
- ✅ Input validation and sanitization
- ✅ Header injection prevention
- ✅ Password-less authentication (pseudonym only)
- ✅ Privacy-first design (no emails required)
- ✅ GDPR-compliant data retention

### Database
- ✅ UUID primary keys
- ✅ Foreign key constraints
- ✅ Automatic analytics expiration (90 days)
- ✅ Indexed queries for performance
- ✅ User data cascade deletion

## Testing

### Health Check

```bash
curl http://localhost:8080/api/health
```

Expected:
```json
{
  "status": "success",
  "data": {
    "status": "healthy",
    "services": {
      "api_server": "running",
      "database": "connected"
    }
  }
}
```

### Integration Status

```bash
curl http://localhost:8080/api/status
```

### Load Testing

```bash
# Install Apache Bench
apt-get install apache2-utils

# Test 1000 requests, 10 concurrent
ab -n 1000 -c 10 http://localhost:8080/api/health
```

## Monitoring

### Logs

```bash
# Bridge server (stdout)
python scripts/api-server.py

# Production server (Railway)
railway logs
```

### Metrics to Monitor
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx errors)
- Database connection pool usage
- JWT token generation rate
- Failed authentication attempts

## Common Issues

### Database Connection Failed

**Symptoms**: 500 errors, "database disconnected" in health check

**Solutions**:
1. Verify `DATABASE_URL` is correct
2. Check PostgreSQL is running
3. Verify network access to database
4. Check connection pool isn't exhausted

### JWT Token Invalid

**Symptoms**: 401 Unauthorized errors

**Solutions**:
1. Token may have expired (24-hour lifetime)
2. JWT_SECRET mismatch between environments
3. Malformed Authorization header
4. Check token format: `Bearer {token}`

### CORS Errors

**Symptoms**: Browser blocks requests from website

**Solutions**:
1. Add website domain to `CORS_ORIGINS`
2. Ensure protocol matches (https:// vs http://)
3. Check for wildcards in origin
4. Verify API server is in production mode

## Performance Optimization

### Current Optimizations
- Connection pooling (2-10 connections)
- Database indexes on hot paths
- Prepared statement caching
- JSON response streaming

### Future Enhancements
- Redis caching layer
- Read replicas for leaderboards
- CDN for static responses
- Rate limiting per user
- Response compression

## API Versioning

Current version: **v2.0.0**

API URLs include version in path:
- `/api/v1/*` - Bridge server endpoints
- `/api/*` - Current production endpoints (v2)

Breaking changes will increment major version.

## Migration Path

### From v1 (Bridge) to v2 (Production)

1. Export existing leaderboard data:
   ```bash
   python scripts/export_leaderboard_to_db.py
   ```

2. Run database migrations
3. Import exported data
4. Update website config to point to new API
5. Test authentication flow
6. Switch DNS to production API

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.

### Adding New Endpoints

1. Add route in `ProductionAPIHandler.do_GET()` or `do_POST()`
2. Implement handler method `_handle_your_endpoint()`
3. Add to API documentation
4. Write tests
5. Update CHANGELOG

## Support

- **Issues**: https://github.com/PipFoweraker/pdoom1-website/issues
- **Discussions**: https://github.com/PipFoweraker/pdoom1-website/discussions
- **Email**: pip@pdoom1.com

## License

MIT License - See [LICENSE](../LICENSE) for details.

## Changelog

### v2.0.0 (2025-11-08)
- ✨ Production API server with PostgreSQL
- ✨ JWT authentication system
- ✨ User registration and login
- ✨ Remote score submission
- ✨ Privacy-first user management
- 📝 Complete deployment documentation

### v1.0.0 (2024)
- ✨ Bridge API server with file storage
- ✨ Local leaderboard endpoints
- ✨ Game statistics aggregation
- ✨ Weekly league support
