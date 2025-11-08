# DreamHost VPS Deployment Guide

**Last Updated**: 2025-11-09
**Purpose**: Deploy pdoom1 API server with PostgreSQL on DreamHost VPS

## Prerequisites

- DreamHost VPS with Ubuntu/Debian
- SSH access to VPS
- Domain: `api.pdoom1.com` (or subdomain)
- Sudo privileges on VPS

## Overview

This guide deploys:
1. PostgreSQL 15+ database
2. Python 3.11 api-server-v2.py
3. Systemd service for auto-restart
4. Nginx reverse proxy
5. SSL certificate (Let's Encrypt)

**Total Time**: 30-45 minutes

---

## Step 1: SSH into DreamHost VPS

```bash
ssh username@your-vps-hostname.dreamhost.com
```

Check your Ubuntu version:
```bash
lsb_release -a
cat /etc/os-release
```

---

## Step 2: Install PostgreSQL

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Check version (should be 14+)
psql --version

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo systemctl status postgresql
```

### Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL prompt:
CREATE DATABASE pdoom1;
CREATE USER pdoom_api WITH ENCRYPTED PASSWORD 'GENERATE_STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON DATABASE pdoom1 TO pdoom_api;

# PostgreSQL 15+ requires additional grants
\c pdoom1
GRANT ALL ON SCHEMA public TO pdoom_api;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pdoom_api;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pdoom_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO pdoom_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO pdoom_api;

# Exit PostgreSQL
\q
```

**Save your database password securely!**

---

## Step 3: Install Python 3.11+

```bash
# Check Python version
python3 --version

# If Python < 3.11, install from deadsnakes PPA (Ubuntu)
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Install pip
sudo apt install -y python3-pip

# Verify
python3.11 --version
```

---

## Step 4: Clone and Setup Application

```bash
# Create application directory
sudo mkdir -p /var/www/pdoom1-api
sudo chown $USER:$USER /var/www/pdoom1-api
cd /var/www/pdoom1-api

# Clone repository
git clone https://github.com/PipFoweraker/pdoom1-website.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify psycopg2 installation
python3 -c "import psycopg2; print('✅ psycopg2 works')"
```

---

## Step 5: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add the following (replace values):

```env
# Database Configuration
DATABASE_URL=postgresql://pdoom_api:YOUR_PASSWORD_HERE@localhost:5432/pdoom1

# JWT Secret (generate with: python3 -c 'import secrets; print(secrets.token_hex(32))')
JWT_SECRET=GENERATE_64_CHAR_HEX_STRING_HERE

# CORS Origins
CORS_ORIGINS=https://pdoom1.com,https://www.pdoom1.com,https://api.pdoom1.com

# API Mode
API_MODE=production

# Server Configuration
PORT=8080
HOST=127.0.0.1
```

**Generate JWT Secret**:
```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Save and exit (Ctrl+O, Enter, Ctrl+X).

**Secure the .env file**:
```bash
chmod 600 .env
```

---

## Step 6: Run Database Migrations

```bash
# Activate virtual environment if not already
source /var/www/pdoom1-api/venv/bin/activate

# Run migration script
python3 scripts/run_migration.py

# Verify tables were created
PGPASSWORD='YOUR_PASSWORD' psql -h localhost -U pdoom_api -d pdoom1 -c '\dt'
```

You should see tables: `users`, `game_sessions`, `leaderboard_entries`, `weekly_challenges`, `blog_entries`, `analytics_events`, `schema_migrations`.

---

## Step 7: Test API Server Manually

```bash
# Activate venv
source /var/www/pdoom1-api/venv/bin/activate

# Test server
python3 scripts/api-server-v2.py --production --port 8080

# In another terminal, test health endpoint:
curl http://localhost:8080/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-11-09T..."
}
```

Press Ctrl+C to stop the test server.

---

## Step 8: Create Systemd Service

```bash
sudo nano /etc/systemd/system/pdoom-api.service
```

Add the following:

```ini
[Unit]
Description=P(Doom)1 Production API Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=YOUR_USERNAME_HERE
Group=YOUR_USERNAME_HERE
WorkingDirectory=/var/www/pdoom1-api
Environment="PATH=/var/www/pdoom1-api/venv/bin"
EnvironmentFile=/var/www/pdoom1-api/.env
ExecStart=/var/www/pdoom1-api/venv/bin/python3 scripts/api-server-v2.py --production --port 8080 --host 127.0.0.1
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Replace** `YOUR_USERNAME_HERE` with your actual username (check with `whoami`).

Save and exit.

### Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable pdoom-api

# Start service
sudo systemctl start pdoom-api

# Check status
sudo systemctl status pdoom-api

# View logs
sudo journalctl -u pdoom-api -f
```

---

## Step 9: Install and Configure Nginx

```bash
# Install Nginx
sudo apt install -y nginx

# Create site configuration
sudo nano /etc/nginx/sites-available/api.pdoom1.com
```

Add the following:

```nginx
server {
    listen 80;
    server_name api.pdoom1.com;

    # Redirect to HTTPS (will be configured with certbot)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.pdoom1.com;

    # SSL certificates (will be configured by certbot)
    ssl_certificate /etc/letsencrypt/live/api.pdoom1.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.pdoom1.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API proxy
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Access logs
    access_log /var/log/nginx/api.pdoom1.com.access.log;
    error_log /var/log/nginx/api.pdoom1.com.error.log;
}
```

Save and exit.

### Enable Site

```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/api.pdoom1.com /etc/nginx/sites-enabled/

# Test configuration (will fail SSL check until certbot runs)
sudo nginx -t

# Note: SSL errors are expected at this point
```

---

## Step 10: Configure DNS

In your DreamHost control panel or DNS provider:

**Add A Record**:
- **Type**: A
- **Name**: `api` (or `api.pdoom1`)
- **Value**: Your VPS IP address
- **TTL**: 300 (5 minutes)

**Get your VPS IP**:
```bash
curl ifconfig.me
# Or
hostname -I
```

Wait 5-15 minutes for DNS propagation. Test with:
```bash
dig api.pdoom1.com
nslookup api.pdoom1.com
```

---

## Step 11: Install SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Temporarily disable nginx (for initial cert)
sudo systemctl stop nginx

# Get certificate
sudo certbot certonly --standalone -d api.pdoom1.com

# Follow prompts:
# - Enter email address
# - Agree to Terms of Service (Y)
# - Share email with EFF (optional)

# Start nginx
sudo systemctl start nginx

# Test nginx configuration
sudo nginx -t

# If OK, reload nginx
sudo systemctl reload nginx

# Setup auto-renewal
sudo certbot renew --dry-run
```

### Auto-Renewal Cron Job

Certbot should auto-install a renewal timer. Verify:
```bash
sudo systemctl list-timers | grep certbot
```

---

## Step 12: Test Production Deployment

```bash
# Test health endpoint
curl https://api.pdoom1.com/api/health

# Test from external machine
curl https://api.pdoom1.com/api/health

# Test user registration
curl -X POST https://api.pdoom1.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"pseudonym": "testuser", "email_hash": "testhash123"}'
```

Expected health response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-11-09T..."
}
```

---

## Step 13: Monitoring and Logs

### View API Logs
```bash
# Follow logs in real-time
sudo journalctl -u pdoom-api -f

# View last 100 lines
sudo journalctl -u pdoom-api -n 100

# View errors only
sudo journalctl -u pdoom-api -p err
```

### View Nginx Logs
```bash
# Access logs
sudo tail -f /var/log/nginx/api.pdoom1.com.access.log

# Error logs
sudo tail -f /var/log/nginx/api.pdoom1.com.error.log
```

### Check Service Status
```bash
# API service
sudo systemctl status pdoom-api

# PostgreSQL
sudo systemctl status postgresql

# Nginx
sudo systemctl status nginx
```

---

## Maintenance Commands

### Restart API Server
```bash
sudo systemctl restart pdoom-api
```

### Update Code
```bash
cd /var/www/pdoom1-api
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart pdoom-api
```

### Database Backup
```bash
# Create backup
PGPASSWORD='YOUR_PASSWORD' pg_dump -h localhost -U pdoom_api pdoom1 > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
PGPASSWORD='YOUR_PASSWORD' psql -h localhost -U pdoom_api pdoom1 < backup_20251109_120000.sql
```

---

## Firewall Configuration (Optional but Recommended)

```bash
# Install UFW if not present
sudo apt install -y ufw

# Allow SSH (IMPORTANT - do this first!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status pdoom-api

# View detailed logs
sudo journalctl -u pdoom-api -n 50 --no-pager

# Check if port is already in use
sudo lsof -i :8080

# Test manually
cd /var/www/pdoom1-api
source venv/bin/activate
python3 scripts/api-server-v2.py --production
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
PGPASSWORD='YOUR_PASSWORD' psql -h localhost -U pdoom_api -d pdoom1 -c 'SELECT 1;'

# Check PostgreSQL is running
sudo systemctl status postgresql

# Check PostgreSQL logs
sudo journalctl -u postgresql -n 50
```

### Nginx Issues

```bash
# Test configuration
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log

# Restart nginx
sudo systemctl restart nginx
```

### SSL Certificate Issues

```bash
# Test certificate renewal
sudo certbot renew --dry-run

# Check certificate expiry
sudo certbot certificates

# Manually renew
sudo certbot renew
```

---

## Security Hardening (Recommended)

### PostgreSQL Remote Access

Ensure PostgreSQL only listens locally:

```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
```

Verify:
```
listen_addresses = 'localhost'
```

### Fail2ban (Brute Force Protection)

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Regular Updates

```bash
# Setup unattended-upgrades
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Next Steps

1. ✅ API deployed and running
2. ⏳ Update game client to use `https://api.pdoom1.com`
3. ⏳ Update website config.json with production API URL
4. ⏳ Test end-to-end: game → API → database
5. ⏳ Monitor for 24 hours to ensure stability

---

## Support Resources

- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **Nginx Docs**: https://nginx.org/en/docs/
- **Let's Encrypt**: https://letsencrypt.org/docs/
- **Systemd**: https://www.freedesktop.org/software/systemd/man/

---

**Deployment Complete!** 🎉

Your API is now running at: `https://api.pdoom1.com`
