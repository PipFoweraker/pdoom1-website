# Self-Hosted Plausible Analytics Setup

**Goal**: Deploy Plausible Analytics on our existing DreamHost VPS (208.113.200.215)
**Cost**: $0 (using existing server)
**Privacy**: 100% data ownership, GDPR compliant
**Access**: analytics.pdoom1.com

---

## Why Self-Host?

✅ **Free** - No $9/month subscription
✅ **Full data ownership** - All analytics on our server
✅ **No limits** - Unlimited pageviews, sites, team members
✅ **Same DreamHost VPS** - Already running the API server
✅ **Privacy** - Data never leaves our infrastructure

---

## Prerequisites

- ✅ DreamHost VPS at 208.113.200.215 (already have)
- ✅ Docker installed on VPS
- ✅ Domain: analytics.pdoom1.com (needs DNS setup)
- ✅ SSH access (already configured)

---

## Architecture

```
DreamHost VPS (208.113.200.215)
├── PostgreSQL (port 5432) - Already running for API
├── Nginx (port 80/443) - Already configured
├── API Server (port 8080) - api.pdoom1.com
└── Plausible (Docker)
    ├── Plausible Web (port 8001) → analytics.pdoom1.com
    ├── ClickHouse (internal) - Analytics database
    └── Uses existing PostgreSQL
```

**Traffic Flow**:
```
pdoom1.com → Sends analytics → analytics.pdoom1.com → Plausible
                                                      ↓
                                                  PostgreSQL
```

---

## Installation Steps

### Step 1: SSH into VPS

```bash
ssh -i path/to/pdoom-website-instance.pem ubuntu@208.113.200.215
```

### Step 2: Install Docker (if not already installed)

```bash
# Check if Docker is installed
docker --version

# If not installed:
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (avoid sudo)
sudo usermod -aG docker $USER

# Install docker-compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker-compose --version
```

### Step 3: Clone Plausible Hosting Repository

```bash
# Create directory for Plausible
sudo mkdir -p /opt/plausible
sudo chown $USER:$USER /opt/plausible
cd /opt/plausible

# Clone official self-hosting repository
git clone https://github.com/plausible/hosting.git .
```

### Step 4: Configure Plausible

```bash
# Copy example config
cp plausible-conf.env.example plausible-conf.env

# Edit configuration
nano plausible-conf.env
```

**Update these values**:

```env
# Required: Generate secret key
# Run: openssl rand -base64 64
SECRET_KEY_BASE=YOUR_GENERATED_SECRET_HERE

# Base URL (your analytics subdomain)
BASE_URL=https://analytics.pdoom1.com

# Database configuration (use existing PostgreSQL)
# Create new database: plausible_db
DATABASE_URL=postgres://plausible_user:PLAUSIBLE_PASSWORD@localhost:5432/plausible_db

# ClickHouse database (Plausible's analytics DB - runs in Docker)
CLICKHOUSE_DATABASE_URL=http://plausible_events_db:8123/plausible_events_db

# Disable registration after you create your account
DISABLE_REGISTRATION=true

# Email (optional - for password reset)
# SMTP_HOST_ADDR=smtp.gmail.com
# SMTP_HOST_PORT=465
# SMTP_USER_NAME=your-email@gmail.com
# SMTP_USER_PWD=your-app-password
# SMTP_HOST_SSL_ENABLED=true
# MAILER_EMAIL=analytics@pdoom1.com
```

### Step 5: Create PostgreSQL Database for Plausible

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE plausible_db;
CREATE USER plausible_user WITH ENCRYPTED PASSWORD 'GENERATE_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE plausible_db TO plausible_user;

# PostgreSQL 15+ permissions
\c plausible_db
GRANT ALL ON SCHEMA public TO plausible_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO plausible_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO plausible_user;

\q
```

### Step 6: Update Docker Compose (Optional - Change Port)

The default docker-compose.yml exposes Plausible on port 8000. Since we're using 8080 for the API, let's use 8001:

```bash
nano docker-compose.yml
```

Find the `plausible:` service and update the ports:

```yaml
plausible:
  # ... other config ...
  ports:
    - 8001:8000  # Change from 8000:8000 to 8001:8000
```

### Step 7: Start Plausible

```bash
cd /opt/plausible

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Wait for services to be ready (may take 1-2 minutes)
# Look for: "Listening on http://0.0.0.0:8000"

# Verify running
docker-compose ps
```

### Step 8: Configure Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/analytics.pdoom1.com
```

**Add this configuration**:

```nginx
server {
    listen 80;
    server_name analytics.pdoom1.com;

    # Redirect to HTTPS (after SSL setup)
    # For now, proxy to test
    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable the site**:

```bash
sudo ln -s /etc/nginx/sites-available/analytics.pdoom1.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 9: DNS Configuration

**In your domain registrar (where pdoom1.com is registered)**:

Add an A record:
```
Type: A
Name: analytics
Value: 208.113.200.215
TTL: 3600
```

**Wait 5-10 minutes for DNS propagation**, then test:
```bash
nslookup analytics.pdoom1.com
# Should return: 208.113.200.215
```

### Step 10: Set Up SSL (Let's Encrypt)

```bash
# Install certbot if not already installed
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d analytics.pdoom1.com

# Follow prompts:
# - Enter email: team@pdoom1.com
# - Agree to terms: Yes
# - Redirect HTTP to HTTPS: Yes (option 2)

# Verify auto-renewal
sudo certbot renew --dry-run
```

**Certbot will automatically update your Nginx config to use HTTPS.**

### Step 11: Create Admin Account

```bash
# Visit: https://analytics.pdoom1.com/register
# Create your admin account

# Then, disable registration to prevent others from signing up
cd /opt/plausible
nano plausible-conf.env
```

Update:
```env
DISABLE_REGISTRATION=true
```

```bash
# Restart Plausible
docker-compose down
docker-compose up -d
```

---

## Step 12: Add pdoom1.com to Plausible

1. **Log in**: https://analytics.pdoom1.com
2. **Add website**: Click "Add a website"
3. **Domain**: `pdoom1.com`
4. **Timezone**: Your timezone
5. **Copy tracking code** (shown after creation)

---

## Step 13: Integrate Tracking Script

### Update Website HTML

Add this to the `<head>` section of all pages:

```html
<!-- Privacy-preserving analytics -->
<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>
```

**Files to update**:
- `public/index.html`
- `public/about/index.html`
- `public/leaderboard/index.html`
- `public/game-stats/index.html`
- (All HTML files with `<head>` section)

**Or create a snippet** to include in all pages:

**File**: `public/includes/analytics.html`
```html
<!-- Plausible Analytics - Privacy-preserving, self-hosted -->
<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>
```

Then in each HTML file, add where the `<head>` is:
```html
<head>
  <!-- ... other meta tags ... -->

  <!-- Analytics -->
  <script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>
</head>
```

---

## Step 14: Track Game Downloads (Custom Events)

To track which game version is downloaded:

```html
<a href="/downloads/pdoom1-v1.0.0-windows.zip"
   onclick="plausible('Download', {props: {version: '1.0.0', platform: 'windows'}})">
   Download v1.0.0 for Windows
</a>
```

**In Plausible dashboard**:
- Settings → Goals → Add Goal
- Goal: "Download"
- Enable custom properties

---

## Maintenance

### Start/Stop Plausible

```bash
cd /opt/plausible

# Stop
docker-compose down

# Start
docker-compose up -d

# Restart
docker-compose restart

# View logs
docker-compose logs -f
```

### Update Plausible

```bash
cd /opt/plausible

# Pull latest changes
git pull

# Pull latest Docker images
docker-compose pull

# Restart
docker-compose down
docker-compose up -d
```

### Backup Database

```bash
# PostgreSQL backup (plausible metadata)
sudo -u postgres pg_dump plausible_db > ~/backups/plausible_$(date +%Y%m%d).sql

# ClickHouse backup (analytics data)
docker-compose exec plausible_events_db clickhouse-client --query "BACKUP DATABASE plausible_events_db TO Disk('backups', 'backup.zip')"
```

### Check Disk Usage

```bash
# ClickHouse can grow large with lots of traffic
docker exec plausible-clickhouse-1 du -sh /var/lib/clickhouse

# If needed, set data retention in Plausible UI:
# Settings → General → Data Retention (default: forever)
```

---

## Troubleshooting

### Issue: Can't access analytics.pdoom1.com

**Check**:
```bash
# DNS resolution
nslookup analytics.pdoom1.com

# Nginx running
sudo systemctl status nginx

# Plausible running
docker-compose ps

# Port listening
sudo netstat -tlnp | grep 8001
```

### Issue: Plausible shows "Database connection error"

**Check PostgreSQL**:
```bash
# Test database connection
psql "postgresql://plausible_user:PASSWORD@localhost:5432/plausible_db"

# Check logs
docker-compose logs plausible
```

### Issue: No analytics data showing

**Check**:
1. Visit pdoom1.com and open browser console
2. Look for network request to `analytics.pdoom1.com/api/event`
3. Check Plausible dashboard: Real-time → Should see yourself

**Common issues**:
- Ad blocker blocking script
- CORS misconfiguration
- Script not loaded (check browser console)

---

## Resource Usage

**Expected on DreamHost VPS**:

| Service | CPU | RAM | Disk |
|---------|-----|-----|------|
| Plausible | 5-10% | 200MB | Minimal |
| ClickHouse | 10-20% | 512MB | 1-5GB/year* |
| **Total** | **~20%** | **~700MB** | **~5GB/year** |

*Depends on traffic. For 10k pageviews/month: ~100MB/month

**Your VPS can easily handle this** alongside the existing API server.

---

## Cost Analysis

| Option | Setup Time | Monthly Cost | Data Ownership |
|--------|------------|--------------|----------------|
| **Self-Hosted** | 1 hour | $0 | ✅ 100% yours |
| Plausible Cloud | 5 minutes | $9/month | ⚠️ On their servers |

**Self-hosting saves $108/year** and you own all your data.

---

## Security Notes

- ✅ SSL enabled via Let's Encrypt
- ✅ Registration disabled (only you have access)
- ✅ Database on localhost (not publicly exposed)
- ✅ Analytics data stays on your server
- ✅ GDPR compliant (no cookies, no personal data)

---

## What You Get

**Dashboard Access**: https://analytics.pdoom1.com

**Metrics**:
- Real-time visitors
- Page views per page
- Referral sources (where visitors come from)
- Countries (approximate, privacy-preserving)
- Devices (desktop vs mobile)
- Browsers & OS
- **Custom events**: Game downloads by version

**Retention**: Forever (or set custom retention period)

---

## Next Steps

After setup:
1. ✅ Monitor analytics dashboard
2. ✅ Set up custom events for downloads
3. ✅ Create monthly backup script
4. ✅ Share dashboard (Settings → Visibility → Make public or Add team member)

---

## Example: Download Tracking

**HTML**:
```html
<!-- Download buttons with tracking -->
<h2>Download p(Doom)1</h2>

<a href="/downloads/pdoom1-v1.0.0-windows.zip"
   class="download-btn"
   onclick="plausible('Download', {props: {version: '1.0.0', platform: 'Windows'}}); return true;">
   <strong>Windows</strong> (v1.0.0)
</a>

<a href="/downloads/pdoom1-v1.0.0-macos.zip"
   class="download-btn"
   onclick="plausible('Download', {props: {version: '1.0.0', platform: 'macOS'}}); return true;">
   <strong>macOS</strong> (v1.0.0)
</a>

<a href="/downloads/pdoom1-v1.0.0-linux.tar.gz"
   class="download-btn"
   onclick="plausible('Download', {props: {version: '1.0.0', platform: 'Linux'}}); return true;">
   <strong>Linux</strong> (v1.0.0)
</a>
```

**Then in Plausible dashboard**:
- Goals → Custom Events → "Download"
- View breakdown by version and platform

---

## Resources

- **Official Guide**: https://plausible.io/docs/self-hosting
- **GitHub**: https://github.com/plausible/analytics
- **Community**: https://plausible.io/blog/community-edition

---

**Estimated Total Setup Time**: 45-60 minutes

**Status**: Ready to deploy
**Cost**: $0/month
**Privacy**: 100% data ownership

Let's own our analytics! 📊
