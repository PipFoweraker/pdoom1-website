# NodeBB Ansible Deployment

Automated deployment of NodeBB forum software for P(Doom)1.

## Overview

This Ansible playbook automates the installation and configuration of:
- Node.js 20 LTS
- MongoDB 7.0
- NodeBB v3.x
- Nginx reverse proxy
- PM2 process manager
- SSL/TLS (Let's Encrypt) setup

## Prerequisites

### On Your Local Machine

1. **Ansible installed** (version 2.9+)
   ```bash
   # macOS
   brew install ansible

   # Ubuntu/Debian
   sudo apt update && sudo apt install ansible

   # Windows (via WSL or use Windows Package Manager)
   pip install ansible
   ```

2. **SSH access to target server**
   - SSH key must be configured (`~/.ssh/pdoom-website-instance.pem`)
   - Server IP: 208.113.200.215
   - User: ubuntu

3. **DNS configured**
   - `forum.pdoom1.com` must point to your server IP
   - Wait for DNS propagation before running playbook

### On Target Server

- Ubuntu 24.04 LTS (or 22.04)
- Minimum 512MB RAM (1GB+ recommended)
- 20GB disk space
- Sudo access

## Quick Start

### 1. Configure Inventory

Edit `ansible/inventories/production.ini` if needed:

```ini
[nodebb_servers]
forum.pdoom1.com ansible_host=208.113.200.215 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/pdoom-website-instance.pem
```

### 2. Customize Variables (Optional)

Edit `ansible/roles/nodebb/vars/main.yml` to customize:
- Domain name
- Port numbers
- Database settings
- Email configuration

### 3. Run the Playbook

```bash
cd ansible
ansible-playbook -i inventories/production.ini deploy-nodebb.yml
```

### 4. Complete NodeBB Setup

After the playbook completes, SSH into the server:

```bash
ssh -i ~/.ssh/pdoom-website-instance.pem ubuntu@208.113.200.215
```

Then run NodeBB setup:

```bash
cd /opt/nodebb
sudo -u nodebb ./nodebb setup
```

You'll be prompted for:
- **URL**: `https://forum.pdoom1.com`
- **Port**: `4567`
- **Database**: `mongo`
- **MongoDB host**: `127.0.0.1`
- **MongoDB port**: `27017`
- **MongoDB database**: `nodebb`
- **Admin username**: Your choice (e.g., `admin`)
- **Admin email**: Your email
- **Admin password**: Choose a strong password (save this!)

### 5. Start NodeBB with PM2

```bash
cd /opt/nodebb
sudo -u nodebb pm2 start ./nodebb -- start
sudo -u nodebb pm2 save
```

### 6. Configure SSL

```bash
sudo certbot --nginx -d forum.pdoom1.com
```

Follow the prompts:
- Enter your email
- Agree to Terms of Service
- Choose to redirect HTTP to HTTPS (recommended)

### 7. Verify Deployment

Visit `https://forum.pdoom1.com` and verify:
- [ ] Forum loads correctly
- [ ] SSL certificate is valid (green padlock)
- [ ] Can login with admin credentials
- [ ] Admin panel accessible at `/admin`

## Project Structure

```
ansible/
├── deploy-nodebb.yml              # Main playbook
├── inventories/
│   └── production.ini             # Server inventory
├── roles/
│   └── nodebb/
│       ├── handlers/
│       │   └── main.yml           # Service restart handlers
│       ├── tasks/
│       │   └── main.yml           # Installation tasks
│       ├── templates/
│       │   ├── config.json.j2     # NodeBB configuration
│       │   └── nginx-nodebb.conf.j2  # Nginx config
│       └── vars/
│           └── main.yml           # Configuration variables
└── README.md                      # This file
```

## Configuration Details

### Variables (`roles/nodebb/vars/main.yml`)

| Variable | Default | Description |
|----------|---------|-------------|
| `nodebb_domain` | `forum.pdoom1.com` | Forum domain name |
| `nodebb_url` | `https://forum.pdoom1.com` | Full forum URL |
| `nodebb_port` | `4567` | NodeBB listening port |
| `nodebb_install_dir` | `/opt/nodebb` | Installation directory |
| `nodejs_version` | `20` | Node.js major version |
| `mongodb_database` | `nodebb` | MongoDB database name |

### Inventory (`inventories/production.ini`)

Defines target servers and connection details. Can be expanded to include multiple servers for staging/production environments.

## Maintenance

### Updating NodeBB

```bash
ssh ubuntu@208.113.200.215
cd /opt/nodebb
sudo -u nodebb git pull
sudo -u nodebb ./nodebb upgrade
sudo -u nodebb pm2 restart nodebb
```

### Viewing Logs

```bash
# PM2 logs
sudo -u nodebb pm2 logs nodebb

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# MongoDB logs
sudo journalctl -u mongod -f
```

### Backup

```bash
# Backup MongoDB
mongodump --db nodebb --out ~/backup/mongo-$(date +%Y-%m-%d)

# Backup NodeBB uploads and config
tar -czf ~/backup/nodebb-files-$(date +%Y-%m-%d).tar.gz /opt/nodebb/public/uploads /opt/nodebb/config.json
```

### Restore

```bash
# Restore MongoDB
mongorestore --db nodebb ~/backup/mongo-YYYY-MM-DD/nodebb

# Restore files
tar -xzf ~/backup/nodebb-files-YYYY-MM-DD.tar.gz -C /
```

## Troubleshooting

### Ansible Connection Issues

```bash
# Test connectivity
ansible -i inventories/production.ini nodebb_servers -m ping

# Run playbook with verbose output
ansible-playbook -i inventories/production.ini deploy-nodebb.yml -vvv
```

### NodeBB Won't Start

```bash
# Check logs
cd /opt/nodebb
sudo -u nodebb ./nodebb log

# Check if port is in use
sudo lsof -i :4567

# Restart manually
sudo -u nodebb ./nodebb restart
```

### Nginx 502 Bad Gateway

```bash
# Check if NodeBB is running
sudo -u nodebb pm2 status

# Restart NodeBB
sudo -u nodebb pm2 restart nodebb

# Check nginx configuration
sudo nginx -t
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Renew certificate
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

## Scaling for Future Developers

### Adding Staging Environment

1. Create `inventories/staging.ini`:
   ```ini
   [nodebb_servers]
   staging.forum.pdoom1.com ansible_host=X.X.X.X ansible_user=ubuntu
   ```

2. Run against staging:
   ```bash
   ansible-playbook -i inventories/staging.ini deploy-nodebb.yml
   ```

### Multi-Server Deployment

Add multiple servers to inventory:

```ini
[nodebb_servers]
forum1.pdoom1.com ansible_host=X.X.X.X
forum2.pdoom1.com ansible_host=Y.Y.Y.Y

[nodebb_servers:vars]
ansible_user=ubuntu
```

### Custom Roles

Create additional roles for:
- Monitoring (Prometheus, Grafana)
- Backup automation
- Security hardening
- Load balancing (HAProxy)

## Security Considerations

- SSH keys only (no password authentication)
- Firewall configured via security groups
- Nginx serves as reverse proxy (NodeBB not directly exposed)
- SSL/TLS encryption via Let's Encrypt
- MongoDB only accessible from localhost
- Regular security updates via `unattended-upgrades`

## Support

For issues or questions:
1. Check logs (see Maintenance section)
2. Review official NodeBB docs: https://docs.nodebb.org
3. Create issue in pdoom1-website repo

## License

Same as main project (see repository LICENSE file)

---

**Last updated**: 2025-11-08
**Ansible version**: 2.9+
**Tested on**: Ubuntu 24.04 LTS
