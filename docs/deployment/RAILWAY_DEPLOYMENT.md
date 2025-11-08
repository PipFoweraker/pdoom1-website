# Railway Deployment Guide for P(Doom)1 Production API

This guide walks you through deploying the production API server (v2) with PostgreSQL database to Railway.

## Why Railway?

- **Modern & Developer-Friendly**: Simple deployment from GitHub
- **PostgreSQL Included**: Managed PostgreSQL with automatic backups
- **Free Tier Available**: 500 hours/month free (enough for testing)
- **Auto-Scaling**: Horizontal scaling when needed
- **Environment Variables**: Easy configuration management
- **HTTPS Automatic**: SSL certificates handled automatically

## Prerequisites

1. GitHub account with access to `PipFoweraker/pdoom1-website`
2. Railway account (sign up at https://railway.app)
3. Local development environment for testing (optional)

## Step 1: Create Railway Project

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Authorize Railway to access your GitHub account
5. Select `PipFoweraker/pdoom1-website` repository
6. Railway will automatically detect Python and start deployment

## Step 2: Add PostgreSQL Database

1. In your Railway project, click "New Service"
2. Select "Database"
3. Choose "PostgreSQL"
4. Railway will provision a PostgreSQL instance
5. Note: Database URL will be automatically available as `DATABASE_URL` environment variable

## Step 3: Configure Environment Variables

In Railway project settings, add these environment variables:

### Required Variables

```env
# Database (automatically set by Railway)
DATABASE_URL=[automatically populated]

# JWT Secret (generate a secure random key)
JWT_SECRET=[generate with: python -c 'import secrets; print(secrets.token_hex(32))']

# Server Configuration
PORT=8080
API_MODE=production

# CORS Origins
CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com
```

### Generate JWT Secret

Run this command locally to generate a secure JWT secret:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

Copy the output and paste it as the `JWT_SECRET` value in Railway.

## Step 4: Update Railway Configuration

Railway should use the existing `railway.json` file, but verify it contains:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python scripts/api-server-v2.py --production --port $PORT",
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

**Important**: Update the start command to use `api-server-v2.py` instead of `api-server.py`.

## Step 5: Run Database Migrations

After deployment, run the initial database schema migration:

### Option A: Using Railway CLI

1. Install Railway CLI:
   ```bash
   npm install -g @railway/cli
   ```

2. Login to Railway:
   ```bash
   railway login
   ```

3. Link to your project:
   ```bash
   railway link
   ```

4. Run migration:
   ```bash
   railway run psql $DATABASE_URL < scripts/db_migrations/001_initial_schema.sql
   ```

### Option B: Using Railway Dashboard

1. Go to your PostgreSQL service in Railway dashboard
2. Click "Connect" and copy the connection command
3. Use a PostgreSQL client (TablePlus, DBeaver, pgAdmin) to connect
4. Run the SQL from `scripts/db_migrations/001_initial_schema.sql`

### Option C: Using Python Script

Create a one-time migration runner:

```python
# scripts/run_migration.py
import os
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')

with open('scripts/db_migrations/001_initial_schema.sql', 'r') as f:
    schema_sql = f.read()

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute(schema_sql)
conn.commit()
print("✅ Migration completed successfully!")
conn.close()
```

Then run via Railway:
```bash
railway run python scripts/run_migration.py
```

## Step 6: Verify Deployment

1. Check Railway logs for successful startup
2. Visit your Railway-provided URL + `/api/health`
   - Example: `https://your-project.up.railway.app/api/health`
3. You should see:
   ```json
   {
     "status": "success",
     "data": {
       "status": "healthy",
       "services": {
         "api_server": "running",
         "database": "connected"
       },
       "version": "v2.0.0-production"
     }
   }
   ```

## Step 7: Configure Custom Domain

### Add Domain to Railway

1. In Railway project settings, go to "Settings"
2. Click "Generate Domain" for a free Railway subdomain
   - Example: `pdoom1-api.up.railway.app`
3. Or add custom domain:
   - Click "Add Custom Domain"
   - Enter `api.pdoom1.com`
   - Railway will provide DNS configuration

### DNS Configuration for Custom Domain

Add these DNS records to your domain provider (DreamHost):

```
Type:  CNAME
Name:  api
Value: your-project.up.railway.app
TTL:   Auto
```

Wait for DNS propagation (5-60 minutes).

## Step 8: Update Website Configuration

Update pdoom1-website to point to production API:

```javascript
// public/config.json
{
  "apiBase": "https://api.pdoom1.com"
}
```

## Step 9: Test End-to-End Flow

### 1. Register a User

```bash
curl -X POST https://api.pdoom1.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "pseudonym": "TestPlayer123",
    "opt_in_leaderboard": true,
    "opt_in_analytics": false
  }'
```

Expected response:
```json
{
  "status": "success",
  "data": {
    "user_id": "uuid-here",
    "pseudonym": "TestPlayer123",
    "token": "jwt-token-here"
  }
}
```

### 2. Submit a Score

```bash
curl -X POST https://api.pdoom1.com/api/scores/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "seed": "test-seed",
    "score": 100,
    "verification_hash": "abc123",
    "timestamp": "2025-11-08T10:00:00Z"
  }'
```

### 3. View Leaderboard

```bash
curl https://api.pdoom1.com/api/leaderboards/current?limit=10
```

## Monitoring and Maintenance

### View Logs

```bash
railway logs
```

Or view in Railway dashboard under "Deployments" → "Logs"

### Database Backups

Railway automatically backs up PostgreSQL databases. To manually backup:

1. Go to PostgreSQL service in Railway
2. Click "Backups"
3. Create manual backup or schedule automatic backups

### Scaling

Railway automatically scales based on demand. For manual scaling:

1. Go to project settings
2. Click "Settings" → "Resources"
3. Adjust CPU/Memory allocation
4. Enable horizontal scaling if needed

## Cost Estimates

### Free Tier
- 500 hours/month of usage
- $5 credit (no credit card required)
- Perfect for development and testing

### Production Tier
- **API Server**: ~$5-10/month (depends on usage)
- **PostgreSQL**: ~$5-10/month (depends on storage)
- **Total**: ~$10-20/month for production workload

## Troubleshooting

### Database Connection Fails

1. Verify `DATABASE_URL` is set in environment variables
2. Check PostgreSQL service is running in Railway dashboard
3. View logs: `railway logs`

### API Server Won't Start

1. Check that `requirements.txt` includes all dependencies
2. Verify `railway.json` points to correct start command
3. Check environment variables are all set
4. View detailed logs in Railway dashboard

### JWT Errors

1. Ensure `JWT_SECRET` is set and is a strong random value
2. Verify token is being sent in `Authorization: Bearer {token}` header
3. Check token hasn't expired (24 hour default)

### CORS Errors

1. Verify `CORS_ORIGINS` includes your website domain
2. Ensure protocol matches (https:// not http://)
3. Check for typos in domain names

## Security Best Practices

1. **Never commit `.env` file** - Use `.env.example` as template
2. **Rotate JWT_SECRET periodically** - Every 90 days recommended
3. **Use strong DATABASE_URL password** - Railway generates secure ones
4. **Enable Railway's built-in security features**:
   - IP allowlisting (if needed)
   - Environment variable encryption (automatic)
   - HTTPS-only (automatic)

5. **Monitor logs for suspicious activity**:
   ```bash
   railway logs --filter="401\|403\|500"
   ```

## Rollback Procedure

If deployment fails:

1. Go to Railway dashboard → "Deployments"
2. Find last working deployment
3. Click "Redeploy"
4. Or use Railway CLI:
   ```bash
   railway rollback
   ```

## Next Steps

After successful deployment:

1. ✅ Update game client to use production API
2. ✅ Configure DreamHost to serve static website
3. ✅ Enable monitoring and alerts
4. ✅ Set up automated database backups
5. ✅ Implement rate limiting (future enhancement)
6. ✅ Add Redis caching (future enhancement)

## Support

- Railway Documentation: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- PostgreSQL Docs: https://www.postgresql.org/docs/

## Migration from Development to Production Checklist

- [ ] Railway project created
- [ ] PostgreSQL database provisioned
- [ ] Environment variables configured
- [ ] Database schema migrated
- [ ] API server deployed and healthy
- [ ] Custom domain configured (api.pdoom1.com)
- [ ] DNS records updated
- [ ] End-to-end testing completed
- [ ] Website config updated to use production API
- [ ] Monitoring and alerts configured
- [ ] Backup strategy verified
- [ ] Security audit completed

## Additional Resources

- [Railway.json Configuration](https://docs.railway.app/deploy/railway-json)
- [PostgreSQL Best Practices](https://railway.app/docs/databases/postgresql)
- [Environment Variables Management](https://docs.railway.app/develop/variables)
- [Custom Domains](https://docs.railway.app/deploy/domains)
