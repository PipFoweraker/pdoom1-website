# NodeBB Forum Deployment - Complete

**Date**: 2025-11-08
**Issue**: #60 (Self-Hosted Forum Implementation: Replace Discord with NodeBB)
**Status**: ✅ DEPLOYED
**Forum URL**: http://208.113.200.215
**Server**: DreamCompute (208.113.200.215)

---

## 🎯 What Was Accomplished

### 1. **Forum Infrastructure** ✅
- **Platform**: NodeBB v3.x (Docker)
- **Database**: PostgreSQL 16
- **Reverse Proxy**: Nginx (port 80 → 4567)
- **Containerization**: Docker Compose with persistent volumes
- **Deployment Method**: Docker (bypassed webpack build issues)
- **Instance Size**: subsonic (2GB RAM) - resized from 512MB to resolve 503 errors

### 2. **Integration with Main Site** ✅
- Added "Forum" link to main site navigation ([public/index.html:779](../public/index.html#L779))
- Forum accessible from pdoom1.com homepage
- Ready for traffic immediately

### 3. **Theme & Branding** ✅
- Custom CSS created matching main site color scheme (#0066cc primary)
- PowerShell automation script for theme sync
- Documentation for applying theme in admin panel

### 4. **Documentation Created** ✅
- **[FORUM-SETUP.md](../../FORUM-SETUP.md)** - Complete setup and management guide
- **[ansible/README.md](../../ansible/README.md)** - Full Ansible automation (320+ lines)
- **[docker-compose.yml](../../docker-compose.yml)** - Container orchestration
- **[forum-theme.css](../../forum-theme.css)** - Custom theme
- **[scripts/sync-forum-theme.ps1](../../scripts/sync-forum-theme.ps1)** - Theme sync automation

---

## 📂 Files Created

```
pdoom1-website/
├── FORUM-SETUP.md                    # Quick reference guide
├── docker-compose.yml                # NodeBB + PostgreSQL containers
├── forum-theme.css                   # Custom theme CSS
├── scripts/
│   └── sync-forum-theme.ps1          # Theme sync automation
├── ansible/
│   ├── README.md                     # Comprehensive Ansible docs
│   ├── deploy-nodebb.yml             # Main playbook
│   ├── inventories/
│   │   ├── localhost.ini             # Local deployment
│   │   └── production.ini            # Production template
│   └── roles/nodebb/
│       ├── tasks/main.yml            # Installation tasks
│       ├── templates/
│       │   ├── config.json.j2        # NodeBB config template
│       │   └── nginx-nodebb.conf.j2  # Nginx template
│       ├── handlers/main.yml         # Service handlers
│       └── vars/main.yml             # Variables
└── public/index.html                 # Updated with forum link
```

---

## 🔧 Technical Decisions

### Why Docker Over Manual Install?
**Problem**: NodeBB v3.x had webpack build failures with dynamic require() statements
**Solution**: Official Docker image with pre-built assets
**Benefit**: Reproducible, scalable, easy handoff to team

### Why PostgreSQL Over MongoDB?
**Problem**: MongoDB 7.0 not available for Ubuntu 24.04
**Solution**: PostgreSQL 16 (fully supported)
**Benefit**: Better long-term support, easier backups

### Why Nginx Reverse Proxy?
**Problem**: Port 4567 blocked by DreamCompute firewall
**Solution**: Nginx on port 80 forwarding to container
**Benefit**: Standard HTTPS-ready setup, WebSocket support

---

## 🚀 Deployment Architecture

```
Internet
    ↓
http://208.113.200.215
    ↓
Nginx (port 80) ← /etc/nginx/sites-available/nodebb
    ↓
Docker Bridge Network
    ↓
NodeBB Container (port 4567)
    ↓
PostgreSQL Container (port 5432)
    ↓
Docker Volumes (persistent data)
```

---

## 📋 Next Steps (Future Enhancements)

### Immediate (When Time Allows)
1. **Apply Custom Theme**
   - Visit http://208.113.200.215/admin/appearance/customise
   - Paste contents of [forum-theme.css](../../forum-theme.css)
   - Click "Save"

2. **DNS Setup** (See [FORUM-SETUP.md](../../FORUM-SETUP.md))
   ```
   Type: A
   Name: forum
   Value: 208.113.200.215
   TTL: 300
   ```

3. **SSL Certificate** (After DNS)
   ```bash
   ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215
   sudo certbot --nginx -d forum.pdoom1.com
   ```

### Future Improvements
- Configure email notifications (SMTP)
- Set up automated backups
- Enable WebSocket for real-time updates
- Create category structure
- Configure user permissions and roles
- Set up spam protection/moderation tools

---

## 🛠️ Management Commands

### View Logs
```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "sudo docker logs nodebb --tail 100"
```

### Restart Forum
```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "cd /home/ubuntu && sudo docker-compose restart"
```

### Check Status
```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "sudo docker-compose -f /home/ubuntu/docker-compose.yml ps"
```

### Update Forum
```bash
ssh -i "C:\Users\gday\.ssh\pdoom-website-instance.pem" ubuntu@208.113.200.215 "cd /home/ubuntu && sudo docker-compose pull && sudo docker-compose up -d"
```

---

## 🎓 Lessons Learned

1. **Always check OS compatibility** before choosing dependencies (MongoDB issue)
2. **Docker bypasses build complexities** - valuable for rapid deployment
3. **Nginx reverse proxy** solves firewall issues without opening additional ports
4. **Document as you go** - [FORUM-SETUP.md](../../FORUM-SETUP.md) created during deployment
5. **Automation-first mindset** - Ansible playbooks created for future scaling
6. **Right-size your instances** - Initially deployed on 512MB instance, causing 503 errors due to memory pressure. Resized to 2GB (subsonic) which resolved issues immediately. NodeBB + PostgreSQL requires minimum 1-2GB RAM for stable operation

---

## 📚 Related Documentation

- [FORUM-SETUP.md](../../FORUM-SETUP.md) - Quick reference for daily operations
- [ansible/README.md](../../ansible/README.md) - Full Ansible deployment guide
- [NODEBB_INSTALLATION_RUNBOOK.md](../NODEBB_INSTALLATION_RUNBOOK.md) - Original planning doc (now superseded)

---

## ✅ Success Criteria Met

- [x] Forum accessible from main site navigation
- [x] Docker-based deployment for easy scaling
- [x] PostgreSQL database with persistent storage
- [x] Nginx reverse proxy configured
- [x] Custom theme CSS created
- [x] Comprehensive documentation for team handoff
- [x] Ansible automation for reproducible deploys
- [x] All changes committed to git
- [x] Ready for traffic immediately

---

**Deployed by**: Claude Code
**Commit**: `feat: Add NodeBB forum integration`
**Repository**: https://github.com/PipFoweraker/pdoom1-website
