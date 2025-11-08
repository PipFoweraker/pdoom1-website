# P(Doom)1 Forum Setup Guide

## Quick Reference

**Forum URL (current)**: http://208.113.200.215
**Admin Panel**: http://208.113.200.215/admin
**Server IP**: 208.113.200.215
**SSH Key**: `C:\Users\gday\.ssh\pdoom-website-instance.pem`

---

## Theme Customization

### Apply Custom Theme (Now)

1. **Copy the theme CSS**:
   - Open [forum-theme.css](forum-theme.css)
   - Copy entire contents

2. **Go to NodeBB Admin**:
   - Visit http://208.113.200.215/admin/appearance/customise
   - Scroll to "Custom CSS" section
   - Paste the CSS
   - Click "Save"

3. **View changes**:
   - Visit http://208.113.200.215
   - Colors should match main site (#0066cc blue, etc.)

### Update Theme (When Main Site Colors Change)

Run this PowerShell script:
```powershell
.\scripts\sync-forum-theme.ps1
```

Or manually:
1. Update colors in [forum-theme.css](forum-theme.css)
2. Copy & paste into Admin Panel → Appearance → Customise → Custom CSS

---

## DNS Setup (forum.pdoom1.com)

### Step 1: Add DNS Record

In your domain registrar (wherever you bought pdoom1.com):

```
Type: A
Name: forum
Value: 208.113.200.215
TTL: 300
```

### Step 2: Wait for DNS Propagation

Test with:
```powershell
nslookup forum.pdoom1.com
```

Should show: `208.113.200.215`

### Step 3: Update NodeBB Configuration

Once DNS works, update the URL:

1. **Edit docker-compose.yml** on server:
   ```yaml
   URL: https://forum.pdoom1.com
   ```

2. **Restart containers**:
   ```bash
   ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215
   cd /home/ubuntu
   sudo docker-compose down
   sudo docker-compose up -d
   ```

3. **Update nginx** for the new domain (see SSL Setup section)

---

## SSL Setup (https://forum.pdoom1.com)

**After DNS is configured**, set up free SSL certificate:

```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215

# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d forum.pdoom1.com

# Follow prompts:
# - Enter email
# - Agree to ToS
# - Choose: Redirect HTTP to HTTPS (recommended)
```

Certbot will auto-renew. Test renewal:
```bash
sudo certbot renew --dry-run
```

---

## Link from Main Site

Add this to your main site navigation:

```html
<a href="https://forum.pdoom1.com">Forum</a>
```

Or wherever your nav is defined.

---

## Management Commands

### View Logs
```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "sudo docker logs nodebb --tail 100"
```

### Restart Forum
```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "cd /home/ubuntu && sudo docker-compose restart"
```

### Stop/Start
```bash
# Stop
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "cd /home/ubuntu && sudo docker-compose down"

# Start
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "cd /home/ubuntu && sudo docker-compose up -d"
```

### Check Status
```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "sudo docker-compose -f /home/ubuntu/docker-compose.yml ps"
```

---

## File Locations

| File | Purpose |
|------|---------|
| [forum-theme.css](forum-theme.css) | Custom CSS matching main site colors |
| [scripts/sync-forum-theme.ps1](scripts/sync-forum-theme.ps1) | Auto-sync theme from main site |
| [docker-compose.yml](docker-compose.yml) | Docker container configuration |
| [ansible/README.md](ansible/README.md) | Full deployment documentation |

---

## For Your Team

When handing off to developers:

1. Share this document
2. Share SSH key location
3. Share admin credentials (separately/securely)
4. Point them to [ansible/README.md](ansible/README.md) for full infrastructure docs

---

## Troubleshooting

### Forum not loading
```bash
# Check if containers are running
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "sudo docker-compose ps"

# Check logs
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "sudo docker logs nodebb --tail 50"
```

### Database issues
```bash
# Check PostgreSQL
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "sudo docker logs nodebb-postgres --tail 50"
```

### Theme not applying
- Clear browser cache
- Check Admin Panel → Appearance → Customise → Custom CSS
- Make sure you clicked "Save"

---

**Created**: 2025-11-08
**Last Updated**: 2025-11-08
