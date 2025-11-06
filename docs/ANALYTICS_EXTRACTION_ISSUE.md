# Analytics Extraction and Data Collation

## Objective

Extract analytics data from DreamHost and collate it into the pdoom1-website repository for private traffic analysis and data ownership.

**Inspiration:** Borrow/adapt Gwen's approach to analytics data extraction and storage.

---

## Why This Matters

**Current Problems:**
- Analytics locked in DreamHost dashboard
- No historical data export/backup
- Can't correlate with GitHub stats or game data
- Limited analysis capabilities

**Benefits:**
- **Own our data** - Analytics in our repository
- **Historical archive** - Traffic patterns over time
- **Correlation** - Link traffic to releases, features, events
- **Custom analysis** - Query/visualize however we want
- **Backup** - Never lose traffic insights

---

## Data Sources

### Primary: DreamHost Analytics
- **Access:** DreamHost control panel
- **Data Available:**
  - Page views per day/month
  - Unique visitors
  - Referrers
  - Popular pages
  - Geographic distribution
  - User agents/browsers

### Secondary: GitHub Stats (already tracked)
- Repository stats in public/data/version.json
- Stars, forks, issues (updated via workflow)

### Future Integration:
- NodeBB forum analytics (once deployed)
- Game download counts (itch.io API?)
- Manifold Markets engagement

---

## Implementation Plan

### Phase 1: Research Gwen's Approach (Week 1)
**Tasks:**
- [ ] Review Gwen's analytics extraction methodology
- [ ] Document tools/scripts she uses
- [ ] Identify applicable patterns for our use case
- [ ] Determine data format (JSON, CSV, SQLite?)

**Deliverables:**
- Documentation of Gwen's approach
- Proposed data schema for pdoom1-website

---

### Phase 2: DreamHost Data Extraction (Week 1-2)
**Tasks:**
- [ ] Access DreamHost analytics dashboard
- [ ] Determine if API access exists
- [ ] If no API: Manual export process
- [ ] If API: Script automated extraction
- [ ] Define extraction frequency (daily, weekly?)
- [ ] Set up data storage location in repo

**Proposed Storage:**
```
public/data/analytics/
  dreamhost/
    2025-11/
      daily-stats.json
      summary.json
    historical/
      2025-10.json
  github/
    (already in version.json)
  combined/
    traffic-report.json
```

**Deliverables:**
- Data extraction script or manual process
- Initial historical data dump
- Storage structure created

---

### Phase 3: Automation & Scheduling (Week 2)
**Tasks:**
- [ ] Create GitHub Action for periodic extraction (if API available)
- [ ] Set up cron job or manual reminder
- [ ] Add validation/error checking
- [ ] Configure notifications for failed extractions

**Deliverables:**
- Automated workflow (or documented manual process)
- Scheduled extraction running

---

### Phase 4: Data Collation & Analysis (Week 3)
**Tasks:**
- [ ] Combine DreamHost + GitHub stats
- [ ] Create traffic report generator
- [ ] Add correlation analysis (releases vs. traffic)
- [ ] Generate visualizations (optional)
- [ ] Add summary to dashboard (optional)

**Deliverables:**
- Combined analytics dataset
- Traffic insights document

---

## Privacy & Security

**Important:**
- DO NOT commit IP addresses or PII
- Anonymize user-level data
- Aggregate statistics only
- GDPR compliance (EU visitors)
- Store in private repo section if needed

---

## Cost Analysis

**Time Investment:**
- Research Gwen's approach: 2-4 hours
- Initial extraction setup: 4-6 hours
- Automation: 2-4 hours
- Ongoing maintenance: 1 hour/month

**Hosting:**
- Storage in git repo: Free (minimal size)
- No additional infrastructure needed

---

## Success Metrics

**Phase 1 (Week 1):**
- Gwen's approach documented
- Data schema defined

**Phase 2 (Week 2):**
- Historical data extracted and committed
- Current month's data available

**Phase 3 (Month 1):**
- Automated extraction running
- No data gaps in timeline

**Phase 4 (Month 2):**
- Correlation insights generated
- Traffic patterns analyzed

---

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| No DreamHost API | Manual exports, document process |
| Data privacy concerns | Aggregate only, no PII |
| Large file sizes | Compress, use separate branch |
| Extraction failures | Alerts, fallback to manual |

---

## Resources

**Gwen's Approach:**
- (To be documented after research)

**DreamHost Analytics:**
- Control Panel: https://panel.dreamhost.com
- Documentation: (check for API docs)

**Similar Projects:**
- Plausible Analytics (privacy-friendly alternative)
- Umami (self-hosted analytics)

---

## Next Steps

1. **Immediate:** Research Gwen's analytics extraction approach
2. **This week:** Access DreamHost analytics and assess extraction options
3. **Next week:** Implement extraction and initial data dump
4. **Month 1:** Automate and schedule ongoing collection

---

**Labels:** enhancement, data
**Milestone:** v1.2.0 (or v1.3.0)
**Priority:** Medium (after NodeBB implementation)
**Estimate:** 12-16 hours over 2-3 weeks

---

**Let's own our data. Let's understand our traffic. Let's collate everything.**
