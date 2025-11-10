# DreamHost Analytics Extraction Guide

**Issue**: #61
**Created**: 2025-11-10
**Status**: ✅ Ready for Use

---

## Overview

This guide covers extracting website analytics from DreamHost VPS server logs and storing them in the repository for historical analysis and data ownership.

### Why This Matters

**Current Problems:**
- Analytics data locked in server logs
- No historical backup or export
- Limited analysis capabilities
- Risk of data loss on server rotation

**Our Solution:**
- ✅ Own our data (stored in git repository)
- ✅ Historical archive (never lose traffic insights)
- ✅ Privacy-respecting (IP addresses hashed, no PII)
- ✅ Custom analysis (query/visualize as needed)
- ✅ Automated extraction (monthly via GitHub Actions)

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│  DreamHost VPS (208.113.200.215)                          │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Nginx Access Logs                                   │  │
│  │  /var/log/nginx/access.log                          │  │
│  │  /var/log/nginx/access.log.1                        │  │
│  │  /var/log/nginx/access.log.2.gz (older)             │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
                         ↓ SSH
┌───────────────────────────────────────────────────────────┐
│  extract_analytics.py                                      │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  1. Fetch logs via SSH                              │  │
│  │  2. Parse Nginx combined log format                 │  │
│  │  3. Anonymize IP addresses (SHA-256 hash)           │  │
│  │  4. Aggregate statistics                            │  │
│  │  5. Generate daily/summary reports                  │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
                         ↓
┌───────────────────────────────────────────────────────────┐
│  public/data/analytics/dreamhost/                         │
│  ├── 2025-11.json                                         │
│  ├── 2025-12.json                                         │
│  ├── last_30_days.json                                    │
│  └── summary.json (all-time totals)                       │
└───────────────────────────────────────────────────────────┘
```

---

## Installation

### Prerequisites

- Python 3.11+
- SSH access to DreamHost VPS
- SSH private key file (`pdoom-website-instance.pem`)

### Local Setup

```bash
# No additional dependencies needed - uses Python stdlib only!
# (subprocess, json, re, collections, pathlib, datetime, urllib)

# Verify Python version
python3 --version  # Should be 3.11 or higher

# Test SSH access
ssh -i path/to/pdoom-website-instance.pem ubuntu@208.113.200.215 "echo 'Connection successful'"
```

---

## Usage

### Basic Extraction (Last 30 Days)

```bash
python scripts/extract_analytics.py --ssh-key path/to/pdoom-website-instance.pem
```

**Output**:
- File: `public/data/analytics/dreamhost/last_30_days.json`
- Console: Human-readable report

### Extract Specific Month

```bash
# Extract November 2025
python scripts/extract_analytics.py \
  --ssh-key path/to/pdoom-website-instance.pem \
  --month 2025-11
```

**Output**: `public/data/analytics/dreamhost/2025-11.json`

### Extract Custom Date Range

```bash
# Last 7 days
python scripts/extract_analytics.py \
  --ssh-key path/to/pdoom-website-instance.pem \
  --days 7
```

### Custom Output Filename

```bash
python scripts/extract_analytics.py \
  --ssh-key path/to/pdoom-website-instance.pem \
  --month 2025-11 \
  --output november_traffic.json
```

---

## Output Format

### JSON Structure

```json
{
  "metadata": {
    "generated_at": "2025-11-10T12:00:00",
    "period_start": "2025-11-01",
    "period_end": "2025-11-10",
    "total_requests": 15420,
    "anonymization": "IP addresses hashed (SHA-256)",
    "privacy": "No PII collected"
  },
  "summary": {
    "total_unique_visitors": 342,
    "total_page_views": 1250,
    "total_bandwidth_mb": 450.5,
    "avg_daily_visitors": 38.0,
    "avg_daily_page_views": 138.9
  },
  "daily": {
    "2025-11-01": {
      "requests": 520,
      "unique_visitors": 45,
      "page_views": 120,
      "bandwidth_mb": 42.3
    }
    // ... more days
  },
  "top_pages": [
    {"path": "/", "views": 420},
    {"path": "/index.html", "views": 380},
    {"path": "/about/", "views": 125}
  ],
  "top_referrers": [
    {"domain": "google.com", "count": 85},
    {"domain": "github.com", "count": 42}
  ],
  "status_codes": {
    "200": 14500,
    "304": 650,
    "404": 180,
    "500": 90
  },
  "hourly_distribution": {
    "0": 120,
    "1": 95,
    // ... hours 0-23
    "23": 140
  }
}
```

### Human-Readable Report

```
============================================================
  DreamHost Analytics Report
============================================================

Period: 2025-11-01 to 2025-11-10
Generated: 2025-11-10T12:00:00
Total Requests: 15,420

SUMMARY STATISTICS
------------------------------------------------------------
  Total Unique Visitors: 342
  Total Page Views: 1,250
  Total Bandwidth: 450.5 MB
  Avg Daily Visitors: 38.0
  Avg Daily Page Views: 138.9

TOP PAGES
------------------------------------------------------------
   1. /                                       420 views
   2. /index.html                             380 views
   3. /about/                                 125 views
   4. /leaderboard/                           98 views
   5. /game-stats/                            87 views

TOP REFERRERS
------------------------------------------------------------
   1. google.com                              85 hits
   2. github.com                              42 hits
   3. reddit.com                              28 hits

DAILY TRAFFIC
------------------------------------------------------------
  2025-11-10  |   45 visitors  |   142 views  |   48.2 MB
  2025-11-09  |   38 visitors  |   125 views  |   42.5 MB
  2025-11-08  |   42 visitors  |   138 views  |   45.1 MB
  ...

============================================================
Privacy: IP addresses hashed (SHA-256)
============================================================
```

---

## Privacy & Security

### GDPR Compliance ✅

**Data Collected**:
- ✅ Anonymized visitor IDs (IP hash, not original IP)
- ✅ Page paths (URLs visited)
- ✅ Referrer domains (where visitors came from)
- ✅ Timestamps (when pages were visited)
- ✅ User agent strings (browser/OS info)

**Data NOT Collected**:
- ❌ Original IP addresses (hashed immediately)
- ❌ Personal information
- ❌ Cookies or tracking identifiers
- ❌ Geographic location (beyond what referrer provides)

### Anonymization

IP addresses are hashed using SHA-256 before storage:

```python
def anonymize_ip(ip: str) -> str:
    """IP: 192.168.1.1 → Hash: a1b2c3d4e5f6g7h8"""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]
```

**Properties**:
- One-way function (cannot reverse)
- Consistent (same IP = same hash within session)
- Privacy-preserving (cannot identify individual)

### Bot Filtering

Bots are detected and excluded from visitor counts:

```python
bot_indicators = ['bot', 'crawler', 'spider', 'scraper', 'curl', 'wget']
is_bot = any(bot in user_agent.lower() for bot in bot_indicators)
```

**Legitimate bots excluded**:
- Search engine crawlers (Googlebot, Bingbot)
- Monitoring services
- wget/curl automated requests

---

## Automated Extraction

### GitHub Actions Workflow

**Schedule**: Monthly on the 1st at 3am UTC

**What it does**:
1. SSH into DreamHost VPS
2. Fetch last month's logs
3. Parse and anonymize data
4. Generate JSON analytics file
5. Create summary of all analytics files
6. Commit and push to repository

**Manual Trigger**:
1. Go to [Actions tab](../../actions)
2. Select "Extract DreamHost Analytics"
3. Click "Run workflow"
4. Optional: Specify `days` or `month`

### Configuration

**Required GitHub Secrets**:
- `PDOOM_SSH_KEY`: Contents of `pdoom-website-instance.pem`

**To add secret**:
```bash
# In GitHub repo settings → Secrets and variables → Actions
# Create new secret: PDOOM_SSH_KEY
# Paste contents of: cat pdoom-website-instance.pem
```

---

## Data Analysis

### Query Analytics Data

```python
import json
from pathlib import Path

# Load analytics file
analytics_file = Path("public/data/analytics/dreamhost/2025-11.json")
with open(analytics_file) as f:
    data = json.load(f)

# Print summary
print(f"Total visitors: {data['summary']['total_unique_visitors']}")
print(f"Total page views: {data['summary']['total_page_views']}")

# Find busiest day
busiest_day = max(data['daily'].items(), key=lambda x: x[1]['unique_visitors'])
print(f"Busiest day: {busiest_day[0]} ({busiest_day[1]['unique_visitors']} visitors)")

# Top 5 pages
for i, page in enumerate(data['top_pages'][:5], 1):
    print(f"{i}. {page['path']} - {page['views']} views")
```

### Correlation with Releases

```python
# Compare traffic to game releases
import json
from datetime import datetime

# Load analytics
with open("public/data/analytics/dreamhost/2025-11.json") as f:
    analytics = json.load(f)

# Load version data
with open("public/data/version.json") as f:
    version = json.load(f)

# Find traffic spike after release
release_date = version['published_at'][:10]  # YYYY-MM-DD
if release_date in analytics['daily']:
    traffic = analytics['daily'][release_date]
    print(f"Traffic on release day ({release_date}):")
    print(f"  Visitors: {traffic['unique_visitors']}")
    print(f"  Page views: {traffic['page_views']}")
```

### Generate Visualization (Optional)

```python
import json
import matplotlib.pyplot as plt

# Load analytics
with open("public/data/analytics/dreamhost/2025-11.json") as f:
    data = json.load(f)

# Plot daily visitors
dates = list(data['daily'].keys())
visitors = [data['daily'][d]['unique_visitors'] for d in dates]

plt.figure(figsize=(12, 6))
plt.plot(dates, visitors, marker='o')
plt.title('Daily Unique Visitors - November 2025')
plt.xlabel('Date')
plt.ylabel('Unique Visitors')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('traffic_chart.png')
print("Chart saved to traffic_chart.png")
```

---

## Troubleshooting

### Issue: SSH connection fails

**Check**:
```bash
# Verify SSH key permissions
ls -l path/to/pdoom-website-instance.pem
# Should be: -rw------- (600)

chmod 600 path/to/pdoom-website-instance.pem

# Test connection
ssh -i path/to/pdoom-website-instance.pem ubuntu@208.113.200.215 "echo 'Success'"
```

### Issue: No log files found

**Check on server**:
```bash
ssh -i path/to/pdoom-website-instance.pem ubuntu@208.113.200.215

# List available log files
ls -lh /var/log/nginx/

# Check if logs are being written
sudo tail /var/log/nginx/access.log
```

If logs don't exist, Nginx may not be logging or logs are in a different location.

### Issue: Parsing fails

**Check log format**:
```bash
# View first few lines of log
ssh -i path/to/pdoom-website-instance.pem ubuntu@208.113.200.215 "head -5 /var/log/nginx/access.log"
```

Expected format (Combined Log Format):
```
192.168.1.1 - - [10/Nov/2025:14:30:00 +0000] "GET /index.html HTTP/1.1" 200 1234 "https://google.com" "Mozilla/5.0..."
```

If format differs, update regex in `extract_analytics.py:self.log_pattern`

### Issue: Empty analytics output

**Possible causes**:
1. Date range doesn't match log data
2. All entries are bots (filtered out)
3. Log parsing regex doesn't match format

**Debug**:
```bash
# Run with verbose output
python scripts/extract_analytics.py \
  --ssh-key path/to/pdoom-website-instance.pem \
  --days 7 \
  --report

# Check what was parsed
cat public/data/analytics/dreamhost/last_7_days.json | python -m json.tool
```

---

## Maintenance

### Monthly Routine

1. **Automated** (via GitHub Actions):
   - Extract previous month's data
   - Commit to repository

2. **Manual review** (recommended):
   - Check analytics summary
   - Identify traffic trends
   - Correlate with releases/events

### Yearly Archive

Create annual summaries:

```bash
# Extract all of 2025
for month in {01..12}; do
  python scripts/extract_analytics.py \
    --ssh-key path/to/pdoom-website-instance.pem \
    --month 2025-$month
done

# Creates: 2025-01.json, 2025-02.json, ..., 2025-12.json
```

### Log Rotation

DreamHost typically rotates logs:
- `access.log` - Current
- `access.log.1` - Yesterday
- `access.log.2.gz` - 2 days ago (compressed)
- Older logs are deleted after ~30 days

**Recommendation**: Extract monthly to capture all data before deletion.

---

## Integration with pdoom-dashboard

```javascript
// Fetch analytics data for dashboard
async function loadAnalytics() {
  const response = await fetch('data/analytics/dreamhost/summary.json');
  const data = await response.json();

  // Display totals
  document.getElementById('total-visitors').textContent =
    data.totals.total_unique_visitors.toLocaleString();
  document.getElementById('total-views').textContent =
    data.totals.total_page_views.toLocaleString();

  // List recent months
  data.files.forEach(file => {
    console.log(`${file.filename}: ${file.unique_visitors} visitors`);
  });
}
```

---

## Comparison with Other Analytics

### vs. Google Analytics

| Feature | DreamHost Extraction | Google Analytics |
|---------|---------------------|------------------|
| Privacy | ✅ IP hashed, no PII | ❌ Tracks users extensively |
| Data Ownership | ✅ In our repo | ❌ Google's servers |
| Historical Access | ✅ Forever in git | ⚠️ 14 months free tier |
| Cost | ✅ Free | ✅ Free (limited) |
| Real-time | ❌ Delayed | ✅ Yes |
| Geographic Detail | ❌ Limited | ✅ Detailed |
| Setup Complexity | ⚠️ Manual extraction | ✅ Easy (JS snippet) |

### vs. Plausible Analytics

| Feature | DreamHost Extraction | Plausible |
|---------|---------------------|-----------|
| Privacy | ✅ IP hashed | ✅ Privacy-first |
| Data Ownership | ✅ Our repo | ⚠️ Their servers |
| Cost | ✅ Free | ❌ $9/month |
| Real-time | ❌ Delayed | ✅ Yes |
| Setup | ⚠️ Manual | ✅ Easy |

**Our Approach**: Best for data ownership, privacy, and historical archiving. Consider adding Plausible for real-time insights.

---

## Future Enhancements

### Planned (v1.3.0)

- [ ] Geographic data from referrers
- [ ] Conversion tracking (downloads, signups)
- [ ] Traffic source categorization (search, social, direct)
- [ ] Comparison reports (month-over-month)
- [ ] Dashboard integration (visualizations)

### Possible

- [ ] Real-time analytics (stream logs)
- [ ] Alert on traffic spikes/drops
- [ ] A/B testing support
- [ ] Integration with pdoom-data repository

---

## Example Output

### November 2025 Analytics

```json
{
  "metadata": {
    "generated_at": "2025-12-01T03:00:00",
    "period_start": "2025-11-01",
    "period_end": "2025-11-30",
    "total_requests": 28450,
    "anonymization": "IP addresses hashed (SHA-256)",
    "privacy": "No PII collected"
  },
  "summary": {
    "total_unique_visitors": 642,
    "total_page_views": 2580,
    "total_bandwidth_mb": 890.5,
    "avg_daily_visitors": 21.4,
    "avg_daily_page_views": 86.0
  }
}
```

---

## Resources

**Scripts**:
- [extract_analytics.py](../../scripts/extract_analytics.py) - Main extraction script
- [.github/workflows/extract-analytics.yml](../../.github/workflows/extract-analytics.yml) - Automated workflow

**Documentation**:
- [Nginx Log Format](https://nginx.org/en/docs/http/ngx_http_log_module.html#log_format)
- [GDPR Compliance](https://gdpr.eu/)
- [Privacy-First Analytics](https://plausible.io/data-policy)

**Related**:
- [Issue #61](https://github.com/PipFoweraker/pdoom1-website/issues/61) - Original request
- [pdoom-data Integration](../integrations/PDOOM_DATA_INTEGRATION.md)

---

**Last Updated**: 2025-11-10
**Issue**: #61
**Status**: ✅ Ready for Production
**Maintainer**: Pip Foweraker

---

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/PipFoweraker/pdoom1-website.git
cd pdoom1-website

# 2. Extract analytics (last 30 days)
python scripts/extract_analytics.py \
  --ssh-key /path/to/pdoom-website-instance.pem

# 3. View report
cat public/data/analytics/dreamhost/last_30_days.json | python -m json.tool

# 4. Commit to repository
git add public/data/analytics/
git commit -m "chore: Add analytics data"
git push
```

**Done!** Your analytics are now safely stored in the repository. 🎉
