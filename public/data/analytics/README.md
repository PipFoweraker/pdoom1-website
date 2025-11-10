# Analytics Data

This directory contains extracted analytics data from various sources for the pdoom1 website.

## Directory Structure

```
analytics/
├── dreamhost/          # DreamHost VPS web server logs
│   ├── 2025-11.json    # Monthly extracts
│   ├── 2025-12.json
│   ├── last_30_days.json  # Rolling 30-day window
│   └── summary.json    # All-time summary
├── github/             # GitHub repository statistics (future)
└── combined/           # Merged analytics (future)
```

## Data Sources

### DreamHost (Primary)

**Source**: Nginx access logs from production server
**Extraction**: Automated monthly via GitHub Actions
**Privacy**: IP addresses hashed (SHA-256), no PII
**Documentation**: [docs/analytics/DREAMHOST_ANALYTICS_EXTRACTION.md](../../../docs/analytics/DREAMHOST_ANALYTICS_EXTRACTION.md)

**Data Included**:
- Daily unique visitors (anonymized)
- Page views
- Top pages
- Top referrers
- Hourly traffic distribution
- Status code distribution
- Bandwidth usage

### GitHub (Future)

**Source**: GitHub API (repository stats)
**Data**: Stars, forks, issues, releases
**Current Location**: `public/data/version.json`

### Combined (Future)

**Purpose**: Merge all analytics sources
**Use Case**: Correlate traffic with releases, features, events

## Privacy & GDPR Compliance

✅ **No Personal Information**:
- IP addresses are hashed (one-way, cannot reverse)
- No cookies or tracking identifiers
- No geographic data beyond referrer domain
- Bot traffic filtered out

✅ **Data Minimization**:
- Only aggregate statistics stored
- No individual user tracking
- Retention: Historical data in git (public)

## Usage

### Load Analytics Data

```javascript
// Fetch latest summary
fetch('data/analytics/dreamhost/summary.json')
  .then(res => res.json())
  .then(data => {
    console.log(`Total visitors: ${data.totals.total_unique_visitors}`);
    console.log(`Total page views: ${data.totals.total_page_views}`);
  });
```

```python
# Python analysis
import json

with open('public/data/analytics/dreamhost/2025-11.json') as f:
    analytics = json.load(f)

print(f"Visitors: {analytics['summary']['total_unique_visitors']}")
print(f"Top page: {analytics['top_pages'][0]['path']}")
```

### Generate Reports

See [extract_analytics.py](../../../scripts/extract_analytics.py) for automated report generation.

## Automated Updates

**Schedule**: Monthly on the 1st at 3am UTC
**Workflow**: [.github/workflows/extract-analytics.yml](../../../.github/workflows/extract-analytics.yml)

**Manual extraction**:
```bash
python scripts/extract_analytics.py --ssh-key path/to/key.pem --month 2025-11
```

## Data Format

See full documentation: [DREAMHOST_ANALYTICS_EXTRACTION.md](../../../docs/analytics/DREAMHOST_ANALYTICS_EXTRACTION.md)

**Example JSON structure**:
```json
{
  "metadata": {
    "generated_at": "2025-11-10T12:00:00",
    "period_start": "2025-11-01",
    "period_end": "2025-11-30",
    "total_requests": 28450,
    "privacy": "No PII collected"
  },
  "summary": {
    "total_unique_visitors": 642,
    "total_page_views": 2580,
    "total_bandwidth_mb": 890.5
  },
  "daily": { ... },
  "top_pages": [ ... ],
  "top_referrers": [ ... ]
}
```

## Contact

**Questions**: Create an issue at https://github.com/PipFoweraker/pdoom1-website/issues
**Privacy Concerns**: team@pdoom1.com

---

**Last Updated**: 2025-11-10
**Maintained by**: Automated GitHub Actions
