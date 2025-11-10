# pdoom-data Analytics Integration Guide

**Issue**: #66
**Created**: 2025-11-10
**Status**: Ready for Implementation

---

## Overview

This guide covers integrating the pdoom-data analytics pipeline with the production PostgreSQL database on the DreamHost VPS.

### Repositories
- **pdoom-data**: https://github.com/PipFoweraker/pdoom-data (analytics pipeline)
- **pdoom-data-public**: (to be created) - Public analytics exports
- **pdoom-dashboard**: https://github.com/PipFoweraker/pdoom-dashboard (visualization)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  pdoom-data (Analytics Pipeline)                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  SSH Tunnel                                          │    │
│  │  localhost:5432 → 208.113.200.215:5432              │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Read-Only Database Connection                       │    │
│  │  User: pdoom_readonly                                │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Data Processing & Aggregation                       │    │
│  │  - Player statistics                                 │    │
│  │  - Event analytics                                   │    │
│  │  - Leaderboard archives                              │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Export to pdoom-data-public (GitHub)                │    │
│  │  - JSON exports for dashboard                        │    │
│  │  - Anonymized datasets                               │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  pdoom-dashboard (Visualization)                             │
│  - Fetches data from pdoom-data-public                      │
│  - Displays charts, graphs, insights                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### On Your Local Machine (pdoom-data environment)

- [ ] Python 3.11+
- [ ] SSH client (OpenSSH or similar)
- [ ] Private SSH key for DreamHost VPS
- [ ] Git access to pdoom-data repository

### On Production Server (DreamHost VPS)

- [ ] PostgreSQL database running (✅ Already configured)
- [ ] SSH access enabled (✅ Already configured)
- [ ] Read-only database user created (⚠️ **TODO**)

---

## Step 1: Create Read-Only Database User

This prevents the analytics pipeline from accidentally modifying production data.

### SSH into Production Server

```bash
ssh -i path/to/pdoom-website-instance.pem ubuntu@208.113.200.215
```

### Create Read-Only User

```bash
sudo -u postgres psql pdoom1
```

```sql
-- Create read-only user
CREATE USER pdoom_readonly WITH ENCRYPTED PASSWORD 'GENERATE_STRONG_PASSWORD_HERE';

-- Grant connect permission
GRANT CONNECT ON DATABASE pdoom1 TO pdoom_readonly;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO pdoom_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pdoom_readonly;

-- Grant SELECT on future tables (important for new migrations)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pdoom_readonly;

-- Grant SELECT on sequences (for reading serial IDs, but not modifying)
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO pdoom_readonly;

-- Verify permissions
\du pdoom_readonly

-- Test connection
\c pdoom1 pdoom_readonly
SELECT COUNT(*) FROM game_sessions;  -- Should work
INSERT INTO users (pseudonym) VALUES ('test');  -- Should fail

\q
```

**Save the password securely!** You'll need it for the pdoom-data configuration.

Expected output:
```
GRANT
GRANT
GRANT
ALTER DEFAULT PRIVILEGES
```

---

## Step 2: Set Up SSH Tunnel

The production database is **not publicly accessible** (bound to localhost only for security). Access requires an SSH tunnel.

### Option A: Manual SSH Tunnel (For Testing)

```bash
# From your local machine (pdoom-data environment)
ssh -i path/to/pdoom-website-instance.pem \
    -L 5432:localhost:5432 \
    -N \
    ubuntu@208.113.200.215
```

**Explanation**:
- `-L 5432:localhost:5432`: Forward local port 5432 to remote localhost:5432
- `-N`: No command execution (tunnel only)
- Tunnel stays open until you press Ctrl+C

**Test the connection** (in another terminal):
```bash
# Install PostgreSQL client if needed
# Windows: Download from postgresql.org
# Mac: brew install postgresql
# Linux: sudo apt install postgresql-client

# Connect via tunnel
psql "postgresql://pdoom_readonly:PASSWORD@localhost:5432/pdoom1"

# Test query
SELECT COUNT(*) FROM users;

# Exit
\q
```

### Option B: Automated SSH Tunnel (For Production)

Create a script to manage the SSH tunnel automatically.

**File**: `pdoom-data/scripts/ssh_tunnel.sh`

```bash
#!/bin/bash
# SSH Tunnel Manager for pdoom-data Analytics Pipeline

set -e

SSH_KEY="$HOME/.ssh/pdoom-website-instance.pem"
REMOTE_HOST="208.113.200.215"
REMOTE_USER="ubuntu"
LOCAL_PORT=5432
REMOTE_PORT=5432

PID_FILE="/tmp/pdoom_ssh_tunnel.pid"
LOG_FILE="/tmp/pdoom_ssh_tunnel.log"

function start_tunnel() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Tunnel already running (PID: $PID)"
            return 0
        else
            rm "$PID_FILE"
        fi
    fi

    echo "Starting SSH tunnel..."
    ssh -i "$SSH_KEY" \
        -L ${LOCAL_PORT}:localhost:${REMOTE_PORT} \
        -N \
        -f \
        -o "ServerAliveInterval=60" \
        -o "ServerAliveCountMax=3" \
        -o "ExitOnForwardFailure=yes" \
        ${REMOTE_USER}@${REMOTE_HOST} \
        > "$LOG_FILE" 2>&1

    # Get PID of SSH process
    PID=$(pgrep -f "ssh.*${REMOTE_HOST}" | tail -1)
    echo "$PID" > "$PID_FILE"
    echo "Tunnel started (PID: $PID)"
}

function stop_tunnel() {
    if [ ! -f "$PID_FILE" ]; then
        echo "No tunnel running"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    echo "Stopping SSH tunnel (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
    rm "$PID_FILE"
    echo "Tunnel stopped"
}

function status_tunnel() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Tunnel running (PID: $PID)"
            return 0
        else
            echo "Tunnel not running (stale PID file)"
            rm "$PID_FILE"
            return 1
        fi
    else
        echo "Tunnel not running"
        return 1
    fi
}

case "${1:-start}" in
    start)
        start_tunnel
        ;;
    stop)
        stop_tunnel
        ;;
    restart)
        stop_tunnel
        start_tunnel
        ;;
    status)
        status_tunnel
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
```

**Make it executable**:
```bash
chmod +x pdoom-data/scripts/ssh_tunnel.sh
```

**Usage**:
```bash
# Start tunnel
./scripts/ssh_tunnel.sh start

# Check status
./scripts/ssh_tunnel.sh status

# Stop tunnel
./scripts/ssh_tunnel.sh stop
```

---

## Step 3: Configure pdoom-data Database Connection

### Create .env File

**File**: `pdoom-data/.env`

```env
# PostgreSQL Connection (via SSH tunnel)
DATABASE_URL=postgresql://pdoom_readonly:YOUR_PASSWORD_HERE@localhost:5432/pdoom1

# SSH Tunnel Configuration
SSH_TUNNEL_ENABLED=true
SSH_KEY_PATH=/path/to/pdoom-website-instance.pem
SSH_REMOTE_HOST=208.113.200.215
SSH_REMOTE_USER=ubuntu

# Data Export Configuration
EXPORT_PATH=../pdoom-data-public/data
EXPORT_SCHEDULE=daily  # or 'hourly', 'weekly'

# Analytics Settings
ANONYMIZE_DATA=true
RETENTION_DAYS=90
```

**⚠️ Security**: Add `.env` to `.gitignore` - never commit credentials!

### Update pdoom-data Python Code

**File**: `pdoom-data/database.py`

```python
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import subprocess
import time

load_dotenv()

class DatabaseConnection:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        self.ssh_tunnel_enabled = os.getenv('SSH_TUNNEL_ENABLED', 'false').lower() == 'true'
        self.ssh_tunnel_process = None

    def start_ssh_tunnel(self):
        """Start SSH tunnel if enabled."""
        if not self.ssh_tunnel_enabled:
            return

        print("Starting SSH tunnel...")
        result = subprocess.run(['./scripts/ssh_tunnel.sh', 'start'], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start SSH tunnel: {result.stderr.decode()}")

        # Wait for tunnel to establish
        time.sleep(2)
        print("SSH tunnel established")

    def stop_ssh_tunnel(self):
        """Stop SSH tunnel if enabled."""
        if not self.ssh_tunnel_enabled:
            return

        print("Stopping SSH tunnel...")
        subprocess.run(['./scripts/ssh_tunnel.sh', 'stop'])

    def get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.database_url)

    def execute_query(self, query, params=None):
        """Execute a read-only query."""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [dict(row) for row in results]
        finally:
            conn.close()

# Usage example
if __name__ == "__main__":
    db = DatabaseConnection()
    db.start_ssh_tunnel()

    try:
        # Test query
        results = db.execute_query("SELECT COUNT(*) as total_users FROM users")
        print(f"Total users: {results[0]['total_users']}")

        # More queries...
        game_sessions = db.execute_query("""
            SELECT COUNT(*) as total_games, AVG(final_score) as avg_score
            FROM game_sessions
            WHERE completed_at IS NOT NULL
        """)
        print(f"Total games: {game_sessions[0]['total_games']}")
        print(f"Average score: {game_sessions[0]['avg_score']:.2f}")

    finally:
        db.stop_ssh_tunnel()
```

---

## Step 4: Create Data Export Pipeline

### Export Script

**File**: `pdoom-data/export_analytics.py`

```python
"""
Export anonymized analytics data to pdoom-data-public repository.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from database import DatabaseConnection

class AnalyticsExporter:
    def __init__(self, export_path: str = '../pdoom-data-public/data'):
        self.export_path = Path(export_path)
        self.export_path.mkdir(parents=True, exist_ok=True)
        self.db = DatabaseConnection()

    def export_all(self):
        """Run all exports."""
        self.db.start_ssh_tunnel()

        try:
            print("Exporting player statistics...")
            self.export_player_stats()

            print("Exporting leaderboard summary...")
            self.export_leaderboard_summary()

            print("Exporting event analytics...")
            self.export_event_analytics()

            print("Exporting game metrics...")
            self.export_game_metrics()

            print("All exports complete!")

        finally:
            self.db.stop_ssh_tunnel()

    def export_player_stats(self):
        """Export anonymized player statistics."""
        query = """
            SELECT
                COUNT(DISTINCT user_id) as total_players,
                COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '7 days' THEN user_id END) as active_7d,
                COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '30 days' THEN user_id END) as active_30d,
                COUNT(DISTINCT CASE WHEN opt_in_leaderboard THEN user_id END) as leaderboard_opt_in,
                COUNT(DISTINCT CASE WHEN opt_in_analytics THEN user_id END) as analytics_opt_in
            FROM users
        """

        results = self.db.execute_query(query)

        data = {
            "timestamp": datetime.now().isoformat(),
            "player_stats": results[0],
            "metadata": {
                "anonymized": True,
                "retention_period": "90_days"
            }
        }

        output_file = self.export_path / 'player_stats.json'
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"  Exported to {output_file}")

    def export_leaderboard_summary(self):
        """Export leaderboard summary (top 100 scores, anonymized)."""
        query = """
            SELECT
                ROW_NUMBER() OVER (ORDER BY score DESC) as rank,
                score,
                EXTRACT(EPOCH FROM (NOW() - submitted_at)) / 3600 as hours_ago
            FROM leaderboard_entries
            WHERE verified = true
            ORDER BY score DESC
            LIMIT 100
        """

        results = self.db.execute_query(query)

        data = {
            "timestamp": datetime.now().isoformat(),
            "leaderboard": results,
            "metadata": {
                "anonymized": True,
                "note": "Player names removed for privacy"
            }
        }

        output_file = self.export_path / 'leaderboard_top100.json'
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"  Exported to {output_file}")

    def export_event_analytics(self):
        """Export game events analytics."""
        query = """
            SELECT
                event_type,
                COUNT(*) as event_count,
                AVG(difficulty) as avg_difficulty
            FROM game_events
            WHERE is_active = true
            GROUP BY event_type
            ORDER BY event_count DESC
        """

        results = self.db.execute_query(query)

        data = {
            "timestamp": datetime.now().isoformat(),
            "event_distribution": results
        }

        output_file = self.export_path / 'event_analytics.json'
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"  Exported to {output_file}")

    def export_game_metrics(self):
        """Export aggregated game metrics."""
        query = """
            SELECT
                DATE_TRUNC('day', completed_at) as date,
                COUNT(*) as games_played,
                AVG(final_score) as avg_score,
                AVG(final_turn) as avg_turns,
                AVG(duration_seconds / 60.0) as avg_duration_minutes
            FROM game_sessions
            WHERE completed_at >= NOW() - INTERVAL '30 days'
              AND completed_at IS NOT NULL
            GROUP BY DATE_TRUNC('day', completed_at)
            ORDER BY date DESC
        """

        results = self.db.execute_query(query)

        # Convert date objects to strings
        for row in results:
            row['date'] = row['date'].isoformat() if row['date'] else None
            row['avg_score'] = float(row['avg_score']) if row['avg_score'] else None
            row['avg_turns'] = float(row['avg_turns']) if row['avg_turns'] else None
            row['avg_duration_minutes'] = float(row['avg_duration_minutes']) if row['avg_duration_minutes'] else None

        data = {
            "timestamp": datetime.now().isoformat(),
            "daily_metrics": results
        }

        output_file = self.export_path / 'game_metrics_30d.json'
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"  Exported to {output_file}")

if __name__ == "__main__":
    exporter = AnalyticsExporter()
    exporter.export_all()
```

**Run the export**:
```bash
python export_analytics.py
```

---

## Step 5: Automate with GitHub Actions

**File**: `pdoom-data/.github/workflows/export-analytics.yml`

```yaml
name: Export Analytics Data

on:
  schedule:
    # Run daily at 2am UTC
    - cron: '0 2 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  export:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout pdoom-data
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Set up SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.PDOOM_SSH_KEY }}" > ~/.ssh/pdoom-website-instance.pem
          chmod 600 ~/.ssh/pdoom-website-instance.pem

      - name: Configure database connection
        env:
          DATABASE_PASSWORD: ${{ secrets.PDOOM_READONLY_PASSWORD }}
        run: |
          cat > .env <<EOF
          DATABASE_URL=postgresql://pdoom_readonly:${DATABASE_PASSWORD}@localhost:5432/pdoom1
          SSH_TUNNEL_ENABLED=true
          SSH_KEY_PATH=$HOME/.ssh/pdoom-website-instance.pem
          SSH_REMOTE_HOST=208.113.200.215
          SSH_REMOTE_USER=ubuntu
          EXPORT_PATH=./exports
          ANONYMIZE_DATA=true
          EOF

      - name: Run analytics export
        run: |
          python export_analytics.py

      - name: Checkout pdoom-data-public
        uses: actions/checkout@v4
        with:
          repository: PipFoweraker/pdoom-data-public
          path: pdoom-data-public
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Copy exports to public repo
        run: |
          cp -r exports/* pdoom-data-public/data/

      - name: Commit and push to pdoom-data-public
        run: |
          cd pdoom-data-public
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add data/
          git commit -m "Auto-update: Analytics data export $(date -u +%Y-%m-%d)" || echo "No changes"
          git push
```

**Required GitHub Secrets**:
- `PDOOM_SSH_KEY`: Contents of pdoom-website-instance.pem
- `PDOOM_READONLY_PASSWORD`: Password for pdoom_readonly database user

---

## Step 6: Create pdoom-data-public Repository

```bash
# Create new repository on GitHub
gh repo create PipFoweraker/pdoom-data-public --public --description "Public analytics data for p(Doom)1 game"

# Clone and initialize
git clone https://github.com/PipFoweraker/pdoom-data-public.git
cd pdoom-data-public

# Create structure
mkdir -p data
cat > README.md <<'EOF'
# pdoom-data-public

Public analytics data exports for the p(Doom)1 game.

## Data Files

- `player_stats.json` - Anonymized player statistics
- `leaderboard_top100.json` - Top 100 leaderboard (anonymized)
- `event_analytics.json` - Game event distribution
- `game_metrics_30d.json` - 30-day aggregated game metrics

## Privacy

All data is anonymized. No personally identifiable information (PII) is included.

## Updates

Data is automatically updated daily at 2am UTC via GitHub Actions.

## Usage

```javascript
// Fetch player stats
fetch('https://raw.githubusercontent.com/PipFoweraker/pdoom-data-public/main/data/player_stats.json')
  .then(res => res.json())
  .then(data => console.log(data));
```

## License

CC0 - Public Domain
EOF

git add .
git commit -m "Initial commit"
git push
```

---

## Security Checklist

- [ ] Read-only database user created (cannot modify data)
- [ ] Database not publicly accessible (localhost only)
- [ ] SSH key permissions set to 600
- [ ] `.env` file in `.gitignore`
- [ ] GitHub secrets configured (not hardcoded)
- [ ] All exported data anonymized (no PII)
- [ ] SSH tunnel auto-restart configured

---

## Troubleshooting

### Issue: SSH tunnel fails to connect

**Check**:
```bash
# Test SSH connection
ssh -i path/to/pdoom-website-instance.pem ubuntu@208.113.200.215 "echo 'Connection successful'"

# Check key permissions
ls -l path/to/pdoom-website-instance.pem
# Should be: -rw------- (600)

chmod 600 path/to/pdoom-website-instance.pem
```

### Issue: Database connection refused

**Check**:
1. Is SSH tunnel running? `./scripts/ssh_tunnel.sh status`
2. Is PostgreSQL running on server? `ssh ubuntu@208.113.200.215 "sudo systemctl status postgresql"`
3. Test connection: `psql "postgresql://pdoom_readonly:PASSWORD@localhost:5432/pdoom1"`

### Issue: Permission denied on SELECT

**Check database permissions**:
```sql
-- On server
sudo -u postgres psql pdoom1

-- Check permissions
\du pdoom_readonly

-- Re-grant if needed
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pdoom_readonly;
```

---

## Next Steps

- [ ] Create pdoom-data-public repository
- [ ] Set up automated exports
- [ ] Integrate with pdoom-dashboard
- [ ] Add more analytics queries
- [ ] Create data visualization dashboards

---

**Last Updated**: 2025-11-10
**Issue**: #66
**Related**:
- [Production Deployment](../deployment/DREAMHOST_VPS_DEPLOYMENT.md)
- [Security Audit](../security/SECURITY_AUDIT_2025-11-10.md)
