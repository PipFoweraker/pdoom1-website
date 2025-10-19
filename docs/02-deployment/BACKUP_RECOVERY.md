# Backup and Recovery Procedures

## Overview

This document outlines backup strategies, retention policies, and recovery procedures for the p(Doom)1 website and weekly league system.

## Backup Strategy

### What Gets Backed Up

1. **Weekly League Data** (Critical)
   - Current week data: `public/leaderboard/data/weekly/current.json`
   - Historical archives: `public/leaderboard/data/weekly/archive/*.json`
   - League configuration: `scripts/weekly-league-config.json`

2. **Leaderboard Data** (Important)
   - All leaderboard files: `public/leaderboard/data/*.json`
   - Player statistics and rankings

3. **Configuration Files** (Important)
   - Environment configs: `config/*.json`
   - Deployment configs: `.github/workflows/*.yml`
   - API server configs

4. **Content and Documentation** (Standard)
   - Public website files: `public/**/*`
   - Documentation: `docs/**/*.md`

### Backup Schedule

| Data Type | Frequency | Retention | Method |
|-----------|-----------|-----------|--------|
| Weekly League | Automatic on reset | Unlimited | Git commit |
| Leaderboard Data | Daily | 30 days | Git commit |
| Full Site | Weekly | 90 days | Artifact upload |
| Configuration | On change | Unlimited | Git version control |

## Automated Backup System

### Weekly League Archive (Automatic)

The weekly league reset workflow automatically archives data:

```bash
# Triggered every Monday 00:00 UTC via GitHub Actions
# See .github/workflows/weekly-league-reset.yml

Steps:
1. Archive previous week to archive directory
2. Generate new competitive seed
3. Start new league
4. Commit archived data to git
5. Push to GitHub (automatic backup)
```

**Archive Location:**
```
public/leaderboard/data/weekly/archive/
├── 2025_W40.json
├── 2025_W41.json  
├── 2025_W42.json
└── [future weeks...]
```

### Deployment Data Sync (Automatic)

Weekly deployment syncs and backs up data:

```bash
# Triggered every Friday 06:00 UTC via GitHub Actions
# See .github/workflows/weekly-deployment.yml

Steps:
1. Sync game data from pdoom1 repository
2. Update leaderboards and stats
3. Commit changes to git
4. Deploy to production
5. Upload artifacts (retained 30 days)
```

### GitHub Actions Artifacts

Workflow runs automatically upload artifacts:

- **Health Check Results**: Retained 30 days
- **Deployment Logs**: Retained 90 days
- **Test Results**: Retained 30 days

Access via: GitHub → Actions → Workflow Run → Artifacts section

## Manual Backup Procedures

### Full Site Backup

```bash
# Create timestamped backup of entire site
cd /home/runner/work/pdoom1-website/pdoom1-website
tar -czf "backup-pdoom1-$(date +%Y%m%d-%H%M%S).tar.gz" \
  public/ \
  scripts/ \
  config/ \
  docs/ \
  .github/

# Move to safe location
mv backup-pdoom1-*.tar.gz ~/backups/
```

### League Data Only Backup

```bash
# Backup just the league data
tar -czf "league-backup-$(date +%Y%m%d).tar.gz" \
  public/leaderboard/data/weekly/ \
  scripts/weekly-league-config.json

# Verify backup
tar -tzf league-backup-*.tar.gz | head -20
```

### Configuration Backup

```bash
# Export all configuration files
mkdir -p ~/config-backup
cp config/*.json ~/config-backup/
cp scripts/weekly-league-config.json ~/config-backup/
cp .env.example ~/config-backup/
```

### Database Export (Future)

When migrating to database:

```bash
# PostgreSQL backup
pg_dump pdoom1_db > "pdoom1-db-$(date +%Y%m%d).sql"

# SQLite backup
sqlite3 pdoom1.db ".backup 'pdoom1-backup.db'"
```

## Retention Policies

### Weekly League Archives

**Policy:** Keep indefinitely (unlimited retention)

**Rationale:** 
- Historical competition data is valuable
- Small file size (~10-50KB per week)
- ~2.6MB per year at current size
- Important for statistics and player history

**Cleanup:** Manual review annually, keep all by default

### Deployment Artifacts

**Policy:** 30-90 days depending on type

| Artifact Type | Retention |
|---------------|-----------|
| Health checks | 30 days |
| Deployment logs | 90 days |
| Test results | 30 days |
| Build artifacts | 7 days |

**Cleanup:** Automatic via GitHub Actions configuration

### Configuration History

**Policy:** Unlimited (version controlled via Git)

**Rationale:**
- Critical for rollback capabilities
- No storage cost (text files)
- Full history aids debugging

### Leaderboard Data

**Policy:** Keep all unique seeds indefinitely

**Rationale:**
- Each seed represents unique competitive data
- Players may reference historical scores
- Enables long-term statistics

**Cleanup:** Remove duplicate or test data only

## Recovery Procedures

### Scenario 1: Weekly League Data Corruption

**Symptoms:**
- Invalid JSON in current.json
- Missing league data
- Incorrect seed information

**Recovery:**

```bash
# 1. Check if backup exists in archive
ls public/leaderboard/data/weekly/archive/

# 2. Restore from most recent archive
cp public/leaderboard/data/weekly/archive/2025_W42.json \
   public/leaderboard/data/weekly/current.json

# 3. Verify restored data
python -m json.tool public/leaderboard/data/weekly/current.json

# 4. Check league status
npm run league:status

# 5. If needed, start new week
npm run league:new-week

# 6. Commit recovery
git add public/leaderboard/data/weekly/current.json
git commit -m "Recovery: Restored league data from archive"
git push
```

### Scenario 2: Failed Deployment

**Symptoms:**
- Deployment workflow failed
- Site not responding
- Data not updated

**Recovery:**

```bash
# 1. Check workflow logs
gh run list --limit 5
gh run view [run-id]

# 2. Identify failed step
# 3. Fix issue (check SSH keys, secrets, etc.)

# 4. Manually trigger deployment
gh workflow run weekly-deployment.yml

# OR use previous successful deployment
# 5. Find last successful run
gh run list --workflow=weekly-deployment.yml --status=success --limit 1

# 6. Re-run that workflow
gh run rerun [run-id]
```

### Scenario 3: Complete Site Loss

**Symptoms:**
- Repository deleted/corrupted
- All data lost
- Need full restore

**Recovery:**

```bash
# 1. Clone from GitHub (if repository intact)
git clone https://github.com/PipFoweraker/pdoom1-website.git
cd pdoom1-website

# 2. Verify data integrity
python scripts/health-check.py

# 3. If repository lost, restore from latest backup
tar -xzf backup-pdoom1-YYYYMMDD-HHMMSS.tar.gz

# 4. Re-initialize repository
git init
git remote add origin https://github.com/PipFoweraker/pdoom1-website.git

# 5. Restore configuration
cp ~/config-backup/*.json config/
cp ~/config-backup/weekly-league-config.json scripts/

# 6. Verify and push
python scripts/verify-deployment.py
git add -A
git commit -m "Recovery: Full site restore from backup"
git push -u origin main
```

### Scenario 4: League Reset Failed

**Symptoms:**
- Monday reset didn't trigger
- Still showing old week
- No new seed generated

**Recovery:**

```bash
# 1. Check workflow status
gh run list --workflow=weekly-league-reset.yml --limit 3

# 2. Check current league status
npm run league:status

# 3. Manual reset process
npm run league:archive     # Archive old week
npm run league:new-week    # Start new week
npm run game:weekly-sync   # Sync game data

# 4. Verify new week started
npm run league:status
npm run league:standings

# 5. Commit changes
git add public/leaderboard/data/weekly/
git commit -m "Manual league reset - recovered from automation failure"
git push

# 6. Notify players of delay
# (Manual step - post to Discord/social media)
```

### Scenario 5: Configuration Loss

**Symptoms:**
- Missing config files
- Default settings applied
- Wrong environment settings

**Recovery:**

```bash
# 1. Restore from git history
git checkout HEAD~1 -- config/
git checkout HEAD~1 -- scripts/weekly-league-config.json

# 2. Or restore from backup
cp ~/config-backup/*.json config/
cp ~/config-backup/weekly-league-config.json scripts/

# 3. Verify configuration
cat config/production.json
cat scripts/weekly-league-config.json

# 4. Test with health check
npm run test:health

# 5. Commit restoration
git add config/ scripts/weekly-league-config.json
git commit -m "Recovery: Restored configuration files"
git push
```

## External Backup Storage

### Recommended External Backup Locations

1. **GitHub Repository** (Primary)
   - Automatic via git commits
   - Free unlimited history
   - Best for code and configuration

2. **Cloud Storage** (Secondary)
   - AWS S3, Google Cloud Storage, or Backblaze B2
   - For large data files and archives
   - Automated sync via scripts

3. **Local Backup** (Tertiary)
   - External drive or NAS
   - Manual periodic backups
   - Offline disaster recovery

### Setting Up External Sync

```bash
# Example: Sync to AWS S3 (requires AWS CLI)
aws s3 sync public/leaderboard/data/weekly/archive/ \
  s3://pdoom1-backups/weekly-archive/ \
  --storage-class STANDARD_IA

# Example: Sync to Backblaze B2 (requires rclone)
rclone sync public/leaderboard/data/weekly/archive/ \
  b2:pdoom1-backups/weekly-archive/
```

### Automated External Backup Script

Create `.github/workflows/external-backup.yml`:

```yaml
name: External Backup

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Backup to S3
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws s3 sync public/leaderboard/data/ \
            s3://pdoom1-backups/leaderboard-data/ \
            --exclude "*" --include "weekly/*"
```

## Backup Verification

### Regular Verification Schedule

- **Weekly**: Verify league archives are created
- **Monthly**: Test restoration procedure
- **Quarterly**: Full backup/restore drill

### Verification Commands

```bash
# Verify archive integrity
for file in public/leaderboard/data/weekly/archive/*.json; do
  echo "Checking: $file"
  python -m json.tool "$file" > /dev/null && echo "✓ Valid" || echo "✗ Invalid"
done

# Verify backup file integrity
tar -tzf backup-pdoom1-*.tar.gz > /dev/null && echo "✓ Backup valid"

# Test restoration in temp directory
mkdir -p /tmp/restore-test
tar -xzf backup-pdoom1-*.tar.gz -C /tmp/restore-test
ls -la /tmp/restore-test
rm -rf /tmp/restore-test
```

## Disaster Recovery Checklist

When disaster strikes, follow this checklist:

- [ ] Assess scope of data loss
- [ ] Identify most recent good backup
- [ ] Stop any running automated processes
- [ ] Restore from backup (see scenarios above)
- [ ] Verify data integrity
- [ ] Run health checks
- [ ] Test critical functionality
- [ ] Resume automated processes
- [ ] Document incident and recovery steps
- [ ] Update recovery procedures if needed
- [ ] Notify stakeholders of resolution

## Contact and Escalation

For backup/recovery assistance:

1. **Check documentation first**: This file and other docs
2. **Review workflow logs**: GitHub Actions logs
3. **Check health checks**: Recent health check results
4. **Create recovery issue**: Use `recovery` label
5. **Document recovery process**: Update this guide with lessons learned

## Monitoring Backup Health

Add to monitoring dashboard:

- Last successful league archive timestamp
- Number of archived weeks
- Backup file sizes and growth
- Git repository size
- Deployment artifact retention status

Access via: GitHub → Insights → Network or Actions tabs
