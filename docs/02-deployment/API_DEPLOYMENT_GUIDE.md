# API Server Deployment Guide

## Quick Start

The p(Doom)1 API server can be deployed to multiple platforms. Choose the one that best fits your needs.

## Deployment Options

### Option 1: Railway (Recommended for Quick Start)

Railway provides the easiest deployment with automatic HTTPS and zero configuration.

**Setup:**

1. **Install Railway CLI** (optional, can also use web interface):
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. **Deploy via GitHub**:
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select `PipFoweraker/pdoom1-website`
   - Railway automatically detects `railway.json` configuration

3. **Configure Environment Variables**:
   - In Railway dashboard, go to Variables
   - Add:
     ```
     API_ENV=production
     CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com
     ```

4. **Get your URL**:
   - Railway provides: `https://your-app.railway.app`
   - Add custom domain in Settings → Domains (optional)

**Advantages:**
- ✅ Free tier: 500 hours/month
- ✅ Automatic HTTPS
- ✅ GitHub integration (auto-deploy on push)
- ✅ Built-in monitoring
- ✅ One-click rollbacks

**railway.json Configuration:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python scripts/api-server.py --production --port $PORT",
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### Option 2: Render

Render offers similar features with a generous free tier.

**Setup:**

1. **Create Account**: Go to [render.com](https://render.com)

2. **New Web Service**:
   - Connect GitHub account
   - Select repository
   - Render detects `render.yaml`

3. **Configuration** (or use render.yaml):
   - Name: `pdoom1-api`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python scripts/api-server.py --production --port $PORT`

4. **Environment Variables**:
   ```
   API_ENV=production
   CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com
   ```

**Advantages:**
- ✅ Generous free tier
- ✅ Automatic deploys from GitHub
- ✅ Built-in SSL
- ✅ Easy database integration
- ✅ Pull request previews

**render.yaml Configuration:**
```yaml
services:
  - type: web
    name: pdoom1-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt || echo "No requirements"
    startCommand: python scripts/api-server.py --production --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: API_ENV
        value: production
      - key: CORS_ORIGINS
        value: https://pdoom1.com,https://www.pdoom1.com
```

### Option 3: Heroku

Classic platform with robust tooling.

**Setup:**

1. **Install Heroku CLI**:
   ```bash
   curl https://cli-assets.heroku.com/install.sh | sh
   heroku login
   ```

2. **Create App**:
   ```bash
   heroku create pdoom1-api
   ```

3. **Deploy**:
   ```bash
   git push heroku main
   ```

4. **Configure**:
   ```bash
   heroku config:set API_ENV=production
   heroku config:set CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com
   ```

**Procfile Configuration:**
```
web: python scripts/api-server.py --production --port $PORT
```

**Advantages:**
- ✅ Mature platform
- ✅ Excellent CLI tools
- ✅ Add-on ecosystem
- ✅ Comprehensive documentation

**Note**: Heroku ended free tier in November 2022. Paid plans start at $7/month.

### Option 4: Self-Hosted (VPS)

For full control, deploy to a VPS (DigitalOcean, Linode, AWS EC2, etc.)

**Requirements:**
- Ubuntu 22.04 LTS or similar
- Python 3.11+
- Nginx (reverse proxy)
- Certbot (SSL certificates)

**Setup:**

1. **Install Dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3.11 python3-pip nginx certbot python3-certbot-nginx
   ```

2. **Clone Repository**:
   ```bash
   cd /opt
   sudo git clone https://github.com/PipFoweraker/pdoom1-website.git
   cd pdoom1-website
   ```

3. **Create Systemd Service**:
   ```bash
   sudo nano /etc/systemd/system/pdoom1-api.service
   ```

   ```ini
   [Unit]
   Description=p(Doom)1 API Server
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/opt/pdoom1-website
   ExecStart=/usr/bin/python3 scripts/api-server.py --production --port 8080 --host 127.0.0.1
   Restart=on-failure
   RestartSec=5s
   Environment="API_ENV=production"
   Environment="CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com"

   [Install]
   WantedBy=multi-user.target
   ```

4. **Configure Nginx**:
   ```bash
   sudo nano /etc/nginx/sites-available/pdoom1-api
   ```

   ```nginx
   server {
       listen 80;
       server_name api.pdoom1.com;

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /api/health {
           proxy_pass http://127.0.0.1:8080/api/health;
           access_log off;
       }
   }
   ```

5. **Enable and Start**:
   ```bash
   sudo ln -s /etc/nginx/sites-available/pdoom1-api /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   sudo systemctl enable pdoom1-api
   sudo systemctl start pdoom1-api
   ```

6. **Setup SSL**:
   ```bash
   sudo certbot --nginx -d api.pdoom1.com
   ```

7. **Verify**:
   ```bash
   curl https://api.pdoom1.com/api/health
   ```

**Advantages:**
- ✅ Full control
- ✅ No platform limitations
- ✅ Cost-effective at scale
- ✅ Custom configurations

**Disadvantages:**
- ❌ Manual maintenance
- ❌ Security responsibility
- ❌ Scaling complexity

## Environment Variables

All platforms support these environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | No | 8080 | Port to run server (auto-set by platforms) |
| `API_ENV` | No | development | Set to `production` for production mode |
| `CORS_ORIGINS` | No | * | Comma-separated allowed origins for CORS |

## Testing Your Deployment

### Health Check

```bash
curl https://your-api-domain.com/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-19T12:00:00Z",
  "version": "1.0.0"
}
```

### All Endpoints

```bash
# League status
curl https://your-api-domain.com/api/league/status

# Current leaderboard
curl https://your-api-domain.com/api/leaderboards/current?limit=10

# Stats
curl https://your-api-domain.com/api/stats
```

## Monitoring

### Built-in Health Checks

All platforms support automatic health checks via `/api/health` endpoint.

**Railway**: Configured in `railway.json`
**Render**: Configured in `render.yaml`
**Heroku**: Add via Heroku CLI or dashboard
**Self-hosted**: Use systemd or monitoring tools

### External Monitoring

Recommended services:
- **UptimeRobot** (free): Simple uptime monitoring
- **Pingdom** (free tier): Basic monitoring
- **Better Stack** (paid): Comprehensive monitoring

Example UptimeRobot configuration:
```
Monitor Type: HTTP(s)
URL: https://your-api-domain.com/api/health
Interval: 5 minutes
Alert: Email/SMS on down
```

## Updating Production

### Railway/Render/Heroku (Git-based)

Automatic deployment on git push:
```bash
git push origin main
```

### Self-Hosted

```bash
cd /opt/pdoom1-website
sudo git pull
sudo systemctl restart pdoom1-api
sudo systemctl status pdoom1-api
```

## Troubleshooting

### API Not Responding

1. **Check service status**:
   ```bash
   # Railway/Render: Check dashboard
   # Self-hosted:
   sudo systemctl status pdoom1-api
   ```

2. **View logs**:
   ```bash
   # Railway
   railway logs
   
   # Render
   render logs -s pdoom1-api
   
   # Self-hosted
   sudo journalctl -u pdoom1-api -n 100 -f
   ```

3. **Test locally**:
   ```bash
   python scripts/api-server.py --production --port 8080
   curl http://localhost:8080/api/health
   ```

### CORS Errors

1. **Check CORS_ORIGINS**:
   ```bash
   # Should match your website domain exactly
   CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com
   ```

2. **Verify production mode**:
   ```bash
   # Must be set for CORS to take effect
   API_ENV=production
   ```

3. **Test CORS**:
   ```bash
   curl -H "Origin: https://pdoom1.com" \
        -H "Access-Control-Request-Method: GET" \
        -X OPTIONS https://your-api-domain.com/api/health -v
   ```

### Memory/CPU Issues

1. **Check resource usage** (self-hosted):
   ```bash
   top -p $(pgrep -f api-server)
   ```

2. **Restart service**:
   ```bash
   # Railway/Render: Restart via dashboard
   # Self-hosted:
   sudo systemctl restart pdoom1-api
   ```

3. **Upgrade plan** (Railway/Render/Heroku):
   - Free tiers have resource limits
   - Consider paid plans for production

## Security Considerations

### Production Checklist

- [ ] HTTPS enabled (automatic on Railway/Render/Heroku)
- [ ] CORS restricted to production domains
- [ ] Health check endpoint accessible
- [ ] Monitoring configured
- [ ] Logs reviewed regularly
- [ ] API_ENV set to production
- [ ] No sensitive data in logs

### Rate Limiting

Currently not implemented. For production, consider:
- Cloudflare (free tier with rate limiting)
- API Gateway (AWS/GCP)
- Nginx rate limiting (self-hosted)

### DDoS Protection

Recommended services:
- Cloudflare (free tier)
- AWS CloudFront
- Fastly

## Cost Estimates

| Platform | Free Tier | Paid Plans Start |
|----------|-----------|------------------|
| Railway | 500 hrs/month | $5/month |
| Render | 750 hrs/month | $7/month |
| Heroku | None | $7/month |
| DigitalOcean | None | $6/month |
| AWS EC2 | 750 hrs/month (1 year) | $3.50/month |

## Next Steps

1. Choose deployment platform
2. Deploy API server
3. Configure environment variables
4. Test all endpoints
5. Set up monitoring
6. Update website to use production API
7. Monitor and maintain

## Support

- **Documentation**: `/docs/02-deployment/`
- **Issues**: GitHub Issues with `deployment` label
- **Health Status**: Check `/api/health` endpoint
