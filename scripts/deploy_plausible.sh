#!/bin/bash
# Automated Plausible Analytics Deployment Script
# Run this on DreamHost VPS: bash <(curl -s https://raw.githubusercontent.com/PipFoweraker/pdoom1-website/main/scripts/deploy_plausible.sh)

set -e  # Exit on error

echo "================================================"
echo "  Plausible Analytics Self-Hosted Deployment"
echo "  For pdoom1.com"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run as root. Run as ubuntu user."
    exit 1
fi

echo "Step 1: Installing Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    print_success "Docker installed"
else
    print_success "Docker already installed"
fi

if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    print_success "Docker Compose installed"
else
    print_success "Docker Compose already installed"
fi

echo ""
echo "Step 2: Setting up Plausible directory..."
sudo mkdir -p /opt/plausible
sudo chown $USER:$USER /opt/plausible
cd /opt/plausible

if [ ! -d ".git" ]; then
    git clone https://github.com/plausible/hosting.git .
    print_success "Plausible repository cloned"
else
    print_success "Plausible repository already exists"
fi

echo ""
echo "Step 3: Generating secrets..."
SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n')
PLAUSIBLE_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')

echo ""
echo "Step 4: Creating PostgreSQL database..."
sudo -u postgres psql <<EOF
-- Create database if it doesn't exist
SELECT 'CREATE DATABASE plausible_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'plausible_db')\gexec

-- Create user if it doesn't exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'plausible_user') THEN
        CREATE USER plausible_user WITH ENCRYPTED PASSWORD '${PLAUSIBLE_PASSWORD}';
    END IF;
END
\$\$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE plausible_db TO plausible_user;
\c plausible_db
GRANT ALL ON SCHEMA public TO plausible_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO plausible_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO plausible_user;
EOF

print_success "PostgreSQL database created"

echo ""
echo "Step 5: Configuring Plausible..."
# Ensure we're in /opt/plausible directory
cd /opt/plausible
cat > plausible-conf.env <<EOF
# Plausible Analytics Configuration
# Generated: $(date)

# Base URL
BASE_URL=https://analytics.pdoom1.com

# Secret key (auto-generated)
SECRET_KEY_BASE=${SECRET_KEY}

# PostgreSQL database
DATABASE_URL=postgres://plausible_user:${PLAUSIBLE_PASSWORD}@host.docker.internal:5432/plausible_db

# ClickHouse database (analytics data)
CLICKHOUSE_DATABASE_URL=http://plausible_events_db:8123/plausible_events_db

# Disable registration after first user
DISABLE_REGISTRATION=invite_only

# Optional: Email configuration (uncomment and configure if needed)
# SMTP_HOST_ADDR=smtp.gmail.com
# SMTP_HOST_PORT=465
# SMTP_USER_NAME=your-email@gmail.com
# SMTP_USER_PWD=your-app-password
# SMTP_HOST_SSL_ENABLED=true
# MAILER_EMAIL=analytics@pdoom1.com

# Disable registration banner
DISABLE_REGISTRATION_NOTICE=true

# IP geolocation (optional - uses MaxMind free database)
# MAXMIND_LICENSE_KEY=your_key_here
# MAXMIND_EDITION=GeoLite2-City
EOF

print_success "Configuration file created"

echo ""
echo "Step 6: Updating Docker Compose configuration..."
# Ensure we're in /opt/plausible directory
cd /opt/plausible

# Verify compose.yml exists (newer Docker Compose format)
if [ ! -f "compose.yml" ]; then
    print_error "compose.yml not found. Repository may not have cloned correctly."
    exit 1
fi

# Change port from 8000 to 8001 to avoid conflict with API
sed -i 's/8000:8000/8001:8000/g' compose.yml

# Use host.docker.internal for PostgreSQL connection
# This allows Docker container to connect to host's PostgreSQL
cat >> compose.yml <<'EOF'

# Override network settings to allow host access
networks:
  default:
    driver: bridge
EOF

print_success "Docker Compose configured"

echo ""
echo "Step 7: Starting Plausible..."
# Ensure we're in /opt/plausible directory
cd /opt/plausible
docker compose pull
docker compose up -d

# Wait for services to start
echo "Waiting for services to start (30 seconds)..."
sleep 30

print_success "Plausible is starting up"

echo ""
echo "Step 8: Configuring Nginx..."
sudo tee /etc/nginx/sites-available/analytics.pdoom1.com > /dev/null <<'EOF'
server {
    listen 80;
    server_name analytics.pdoom1.com;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for real-time dashboard)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/analytics.pdoom1.com /etc/nginx/sites-enabled/

# Test and reload Nginx
if sudo nginx -t; then
    sudo systemctl reload nginx
    print_success "Nginx configured"
else
    print_error "Nginx configuration test failed"
    exit 1
fi

echo ""
echo "Step 9: Setting up SSL with Let's Encrypt..."
if command -v certbot &> /dev/null; then
    print_warning "Certbot already installed"
else
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
fi

# Check if DNS is configured
if host analytics.pdoom1.com | grep -q "208.113.200.215"; then
    print_success "DNS is configured correctly"
    echo ""
    print_warning "Ready to get SSL certificate. Run this command:"
    echo "  sudo certbot --nginx -d analytics.pdoom1.com --non-interactive --agree-tos --email team@pdoom1.com"
else
    print_warning "DNS not configured yet. Please add DNS record:"
    echo "  Type: A"
    echo "  Name: analytics"
    echo "  Value: 208.113.200.215"
    echo ""
    echo "After DNS propagates (5-10 minutes), run:"
    echo "  sudo certbot --nginx -d analytics.pdoom1.com --non-interactive --agree-tos --email team@pdoom1.com"
fi

echo ""
echo "================================================"
echo "  🎉 Plausible Installation Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Set up DNS (if not done):"
echo "   Add A record: analytics → 208.113.200.215"
echo ""
echo "2. Get SSL certificate (after DNS propagates):"
echo "   sudo certbot --nginx -d analytics.pdoom1.com --non-interactive --agree-tos --email team@pdoom1.com"
echo ""
echo "3. Create admin account:"
echo "   Visit: https://analytics.pdoom1.com/register"
echo "   (Only first user can register, then it's locked)"
echo ""
echo "4. Add pdoom1.com as a site in Plausible dashboard"
echo ""
echo "5. Add tracking script to website:"
echo '   <script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>'
echo ""
echo "Database password saved to: /opt/plausible/plausible-conf.env"
echo ""
echo "Useful commands:"
echo "  cd /opt/plausible"
echo "  docker compose logs -f    # View logs"
echo "  docker compose restart    # Restart"
echo "  docker compose down       # Stop"
echo "  docker compose up -d      # Start"
echo ""
print_success "All done! 🚀"
