# NodeBB Installation Runbook

**Platform:** NodeBB v3.x
**Domain:** forum.pdoom1.com
**Target:** Live in 6 hours
**Reference:** Issue #60

---

## Pre-Flight Checklist

Before starting, verify you have:
- [ ] DreamHost VPS access (SSH credentials)
- [ ] Domain access (ability to create subdomain)
- [ ] Root/sudo access on server
- [ ] Email SMTP credentials for notifications
- [ ] 2-3 hours of focused time

**Server Requirements:**
- Node.js 18+ (preferably 20 LTS)
- MongoDB OR PostgreSQL (recommend MongoDB for simplicity)
- 1-2GB RAM minimum
- 10GB disk space
- nginx (for reverse proxy)

---

## Phase 1: Server Environment Setup (45-60 min)

### Step 1.1: SSH into Server
```bash
ssh username@your-dreamhost-server.com
```

### Step 1.2: Check Current Environment
```bash
# Check Node.js version
node --version  # Need 18+

# Check if MongoDB installed
mongod --version

# Check nginx
nginx -v

# Check available disk space
df -h

# Check RAM
free -h
```

### Step 1.3: Install Node.js 20 LTS (if needed)
```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
nvm alias default 20

# Verify
node --version  # Should be v20.x.x
npm --version
```

### Step 1.4: Install MongoDB
```bash
# Check if already installed
which mongod

# If not, install via package manager
# (DreamHost-specific commands may vary)
sudo apt-get update
sudo apt-get install -y mongodb-org

# Or use Docker (alternative)
# docker run -d -p 27017:27017 --name nodebb-mongo mongo:latest
```

### Step 1.5: Start MongoDB
```bash
# Start MongoDB service
sudo systemctl start mongod
sudo systemctl enable mongod  # Auto-start on boot

# Verify it's running
sudo systemctl status mongod

# Test connection
mongo --eval "db.version()"
```

**Checkpoint 1.5:** MongoDB running? Node.js v20+ installed?
- [ ] Yes, continue
- [ ] No, troubleshoot before proceeding

---

## Phase 2: NodeBB Installation (30-45 min)

### Step 2.1: Create Directory Structure
```bash
# Navigate to web directory (adjust for DreamHost setup)
cd ~/domains/pdoom1.com  # or wherever you host sites
mkdir -p forum.pdoom1.com
cd forum.pdoom1.com
```

### Step 2.2: Clone NodeBB
```bash
git clone -b v3.x https://github.com/NodeBB/NodeBB.git .
# Note the '.' at end - clones into current directory

# Verify
ls -la  # Should see package.json, nodebb, install/, etc.
```

### Step 2.3: Install Dependencies
```bash
npm install --production

# This takes 3-5 minutes
# If errors occur, note them for troubleshooting
```

### Step 2.4: Run Setup Wizard
```bash
./nodebb setup

# You'll be prompted for:
# - URL: https://forum.pdoom1.com
# - Port: 4567 (or any free port)
# - Database: MongoDB
# - MongoDB host: localhost (or 127.0.0.1)
# - MongoDB port: 27017
# - MongoDB database name: nodebb
# - Admin username: [choose admin username]
# - Admin email: [your email]
# - Admin password: [SECURE PASSWORD - save this!]
```

**IMPORTANT:** Save admin credentials immediately!
```
Admin Username: _______________
Admin Password: _______________
Admin Email:    _______________
```

### Step 2.5: Test Local Installation
```bash
./nodebb start

# Wait 10-20 seconds, then check
curl http://localhost:4567

# Should return HTML
# If error, check:
./nodebb log
```

**Checkpoint 2.5:** NodeBB running locally on port 4567?
- [ ] Yes, continue
- [ ] No, check logs: `./nodebb log`

---

## Phase 3: Domain & SSL Setup (30-45 min)

### Step 3.1: Create Subdomain in DreamHost Panel
1. Log into DreamHost control panel
2. Navigate to Domains > Manage Domains
3. Click "Add New Domain / Sub-Domain"
4. Subdomain: `forum`
5. Domain: `pdoom1.com`
6. Web directory: `/home/username/domains/pdoom1.com/forum.pdoom1.com`
7. HTTPS: Enable
8. Save changes

**Wait 5-15 minutes for DNS propagation**

### Step 3.2: Test Subdomain Resolution
```bash
# From your local machine
ping forum.pdoom1.com

# Should resolve to DreamHost IP
# If "unknown host", wait longer for DNS
```

### Step 3.3: Configure nginx Reverse Proxy
```bash
# On server, create nginx config
sudo nano /etc/nginx/sites-available/forum.pdoom1.com

# Paste this configuration:
```

```nginx
server {
    listen 80;
    server_name forum.pdoom1.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name forum.pdoom1.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/forum.pdoom1.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/forum.pdoom1.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to NodeBB
    location / {
        proxy_pass http://127.0.0.1:4567;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/forum.pdoom1.com /etc/nginx/sites-enabled/

# Test nginx config
sudo nginx -t

# If OK, reload nginx
sudo systemctl reload nginx
```

### Step 3.4: Obtain SSL Certificate (Let's Encrypt)
```bash
# Install certbot if not present
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d forum.pdoom1.com

# Follow prompts:
# - Email: [your email]
# - Agree to ToS: Yes
# - Redirect HTTP to HTTPS: Yes (recommended)

# Test auto-renewal
sudo certbot renew --dry-run
```

**Checkpoint 3.4:** SSL certificate obtained and nginx serving HTTPS?
- [ ] Yes, continue
- [ ] No, check certbot logs

---

## Phase 4: Configure NodeBB for Production (20-30 min)

### Step 4.1: Edit NodeBB Configuration
```bash
cd ~/domains/pdoom1.com/forum.pdoom1.com
nano config.json
```

Ensure it has:
```json
{
    "url": "https://forum.pdoom1.com",
    "secret": "[long random string - DO NOT CHANGE]",
    "database": "mongo",
    "mongo": {
        "host": "127.0.0.1",
        "port": "27017",
        "database": "nodebb"
    },
    "port": 4567,
    "bind_address": "127.0.0.1"
}
```

### Step 4.2: Set Up Process Manager (PM2)
```bash
# Install PM2 globally
npm install -g pm2

# Stop existing NodeBB
./nodebb stop

# Start NodeBB with PM2
pm2 start ./nodebb -- start

# Save PM2 configuration
pm2 save

# Enable PM2 on system startup
pm2 startup
# Follow the command it outputs (usually starts with 'sudo env...')

# Check status
pm2 status
pm2 logs nodebb  # View logs
```

### Step 4.3: Configure Email (SMTP)
```bash
# Log into NodeBB admin panel
# Navigate to: https://forum.pdoom1.com/admin
# Login with admin credentials from Step 2.4

# Go to: Settings > Email
# Configure SMTP:
# - SMTP Host: [your SMTP server]
# - SMTP Port: 587 (or 465 for SSL)
# - SMTP Username: [your email username]
# - SMTP Password: [your email password]
# - From Address: noreply@pdoom1.com

# Save and test email
```

**Checkpoint 4.3:** Can send test email successfully?
- [ ] Yes, continue
- [ ] No, verify SMTP credentials

---

## Phase 5: Initial Configuration & Theming (30-45 min)

### Step 5.1: Admin Panel Setup
Navigate to: `https://forum.pdoom1.com/admin`

**General Settings:**
- Site Title: "P(Doom)1 Community Forum"
- Site Description: "Strategic AI Safety discussions for the P(Doom)1 game"
- Terms of Use: (create or link to main site)
- Privacy Policy: Link to https://pdoom1.com/privacy/

**User Settings:**
- Allow Guest Posting: No (recommended)
- Require Email Confirmation: Yes
- Registration Type: Normal (or invite-only initially)
- Min Password Length: 12

**Security:**
- Enable CAPTCHA: Yes (Google reCAPTCHA)
- Get reCAPTCHA keys from: https://www.google.com/recaptcha/admin
- Site key: [paste here]
- Secret key: [paste here]

### Step 5.2: Create Forum Categories
Navigate to: `https://forum.pdoom1.com/admin/manage/categories`

Click "Create New Category" for each:

1. **Gameplay**
   - Name: Gameplay
   - Description: Strategies, tips, and turn reports
   - Icon: fa-gamepad
   - Background color: #00ff41

2. **Bug Reports**
   - Name: Bug Reports
   - Description: Report game bugs and technical issues
   - Icon: fa-bug
   - Background color: #ff4444

3. **Suggestions**
   - Name: Suggestions
   - Description: Feature requests and balance discussion
   - Icon: fa-lightbulb
   - Background color: #0ff

4. **News & Updates**
   - Name: News & Updates
   - Description: Patch notes and announcements
   - Icon: fa-newspaper
   - Background color: #ff9966

5. **Creative**
   - Name: Creative
   - Description: Fan art, stories, and memes
   - Icon: fa-palette
   - Background color: #f0f

### Step 5.3: Install & Configure Theme
```bash
# SSH back into server
cd ~/domains/pdoom1.com/forum.pdoom1.com

# Install Harmony theme (modern, customizable)
npm install nodebb-theme-harmony

# Restart NodeBB
pm2 restart nodebb
```

In Admin Panel:
- Navigate to: Appearance > Themes
- Activate "Harmony" theme
- Click "Customize" to match pdoom1.com:

**Color Customization:**
```
Background: #1a1a1a
Card Background: #2d2d2d
Primary Color: #00ff41
Accent Color: #ff6b35
Text Color: #ffffff
Border Color: #444444
```

Save and preview.

**Checkpoint 5.3:** Forum categories created and theme matches pdoom1.com?
- [ ] Yes, continue to Phase 6
- [ ] No, adjust colors in theme customizer

---

## Phase 6: Integration & Go-Live (30 min)

### Step 6.1: Add Forum Link to Main Site
```bash
# On your local machine (pdoom1-website repo)
cd /path/to/pdoom1-website
```

Edit `public/index.html`:
```html
<!-- In navigation section, replace Discord link -->
<a href="https://forum.pdoom1.com" target="_blank" class="nav-button">
    Forum
</a>
```

Commit and push:
```bash
git add public/index.html
git commit -m "feat: Add NodeBB forum link to navigation

Replaces Discord link with self-hosted forum at forum.pdoom1.com.

Issue #60"
git push origin main
```

### Step 6.2: Create Welcome Post
Navigate to: `https://forum.pdoom1.com/category/4/news-updates`

Create first post:
```
Title: Welcome to the P(Doom)1 Forum!

Body:
Welcome to the official P(Doom)1 community forum!

This is a self-hosted, privacy-respecting space for:
- Sharing strategies and turn reports
- Discussing game balance and features
- Reporting bugs
- Creative content (art, stories, memes)

Why we're not on Discord:
- Permanent archive of knowledge
- SEO-friendly (posts show up in Google)
- We own our data
- No AI training on community content without consent
- Direct rewards for contributors (coming soon!)

Ground rules:
1. Be respectful
2. Stay on-topic
3. No spam or self-promotion
4. Report issues responsibly

Let's build something that lasts. Words on pages, forever.

- Pip Foweraker
```

### Step 6.3: Final Checks
- [ ] Forum accessible at https://forum.pdoom1.com
- [ ] SSL certificate valid (green padlock)
- [ ] Admin panel accessible
- [ ] Email notifications working
- [ ] Guest access blocked (must register)
- [ ] All 5 categories visible
- [ ] Theme matches pdoom1.com aesthetic
- [ ] Welcome post published
- [ ] Main site links to forum
- [ ] reCAPTCHA working on registration

### Step 6.4: Announce Launch
Post to:
- [ ] Main website (news section)
- [ ] Discord (migration announcement)
- [ ] GitHub (update README)
- [ ] Social media (if applicable)

Announcement template:
```
P(Doom)1 Forum Now Live!

We've launched our self-hosted community forum at forum.pdoom1.com

Why a forum instead of Discord?
- Permanent content archive
- SEO-friendly discussions
- Full data ownership
- No invasive AI training
- Future in-game rewards for contributors

Join us: https://forum.pdoom1.com

Discord will remain active during transition, but we encourage moving discussions to the forum for lasting impact.
```

---

## Post-Launch Monitoring (First 24 Hours)

### Health Checks
```bash
# SSH into server

# Check NodeBB status
pm2 status
pm2 logs nodebb --lines 50

# Check nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Check MongoDB
mongo nodebb --eval "db.stats()"

# Check disk space
df -h

# Check memory usage
free -h
```

### Monitor for Issues
- [ ] Registration working?
- [ ] Email confirmations arriving?
- [ ] Posts visible immediately?
- [ ] Images uploading correctly?
- [ ] Mobile responsive?
- [ ] Search functioning?
- [ ] No 502/503 errors in nginx logs?

---

## Troubleshooting Common Issues

### Issue: NodeBB won't start
```bash
# Check logs
./nodebb log

# Common causes:
# 1. Port already in use
sudo lsof -i :4567
# Kill process if needed
sudo kill -9 [PID]

# 2. MongoDB not running
sudo systemctl status mongod
sudo systemctl start mongod

# 3. Missing dependencies
npm install --production
```

### Issue: 502 Bad Gateway
```bash
# Check if NodeBB running
pm2 status

# Restart NodeBB
pm2 restart nodebb

# Check nginx config
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log
```

### Issue: SSL certificate error
```bash
# Re-run certbot
sudo certbot --nginx -d forum.pdoom1.com

# Check certificate validity
sudo certbot certificates
```

### Issue: Email not sending
- Verify SMTP credentials in Admin Panel
- Check SMTP port (587 vs 465)
- Test with Gmail SMTP as fallback
- Check firewall isn't blocking outbound SMTP

### Issue: Can't login as admin
```bash
# Reset admin password
cd ~/domains/pdoom1.com/forum.pdoom1.com
./nodebb reset -u admin-username
# Follow prompts to set new password
```

---

## Backup Strategy

### Daily Backups (Automated)
```bash
# Create backup script
mkdir -p ~/backups/nodebb
nano ~/backups/backup-nodebb.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y-%m-%d)
BACKUP_DIR=~/backups/nodebb

# Backup MongoDB
mongodump --db nodebb --out $BACKUP_DIR/mongo-$DATE

# Backup uploads/config
tar -czf $BACKUP_DIR/files-$DATE.tar.gz ~/domains/pdoom1.com/forum.pdoom1.com/public/uploads
cp ~/domains/pdoom1.com/forum.pdoom1.com/config.json $BACKUP_DIR/config-$DATE.json

# Delete backups older than 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

```bash
# Make executable
chmod +x ~/backups/backup-nodebb.sh

# Add to crontab (runs daily at 2am)
crontab -e
# Add line:
0 2 * * * ~/backups/backup-nodebb.sh >> ~/backups/backup.log 2>&1
```

---

## Next Steps (Post-Launch)

Week 1:
- [ ] Monitor user registrations
- [ ] Respond to first posts
- [ ] Adjust moderation settings
- [ ] Install useful plugins (search, markdown, syntax highlighting)

Week 2:
- [ ] Embed latest forum posts on pdoom1.com homepage
- [ ] Set up RSS feed integration
- [ ] Configure backup restoration test

Week 3-4:
- [ ] Plan reward system integration
- [ ] Design "Cat Custodian" achievement
- [ ] Begin Discord migration

---

## Success Criteria

**Launch Day:**
- [ ] Forum live and accessible
- [ ] At least 5 registered users
- [ ] At least 3 posts created
- [ ] Zero downtime

**Week 1:**
- [ ] 10+ registered users
- [ ] 20+ posts
- [ ] Daily active users: 5-10
- [ ] No major technical issues

**Month 1:**
- [ ] 50+ users
- [ ] 100+ posts
- [ ] Active daily discussions
- [ ] Discord migration started

---

**Installation Target: 6 hours from start to public launch**

Breakdown:
- Phase 1 (Server Setup): 1 hour
- Phase 2 (Installation): 45 min
- Phase 3 (Domain/SSL): 45 min
- Phase 4 (Production Config): 30 min
- Phase 5 (Theming/Categories): 45 min
- Phase 6 (Integration/Launch): 30 min
- Buffer: 45 min

**Let's own our community. Let's build something permanent. Let's do this.**
