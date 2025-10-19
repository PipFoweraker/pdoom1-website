# Future Enhancements: Weekly League UI

## Overview

This document tracks future enhancements for the Weekly League UI that were identified as out-of-scope during the initial implementation.

**Related PR:** Add Frontend UI for Weekly League Standings and Competition Dashboard  
**Status:** Planned / Technical Debt  
**Created:** 2025-10-19

## Background

The core Weekly League UI was implemented with:
- Weekly League Dashboard (`/league/index.html`)
- Competition Statistics Page (`/stats/competition.html`)
- Enhanced Leaderboard with seed/week filtering (`/leaderboard/index.html`)

However, several features were deferred to keep the initial implementation focused and manageable.

---

## 1. Interactive Performance Charts

**Priority:** HIGH  
**Estimated Effort:** Medium (2-3 days)

### Description
Replace chart placeholders with actual visualizations using a lightweight charting library.

### Features Needed
- Performance trends over time (line chart)
- Score distribution (histogram)
- Player engagement trends (area chart)
- Weekly participation comparison (bar chart)

### Suggested Implementation
- **Library:** Chart.js (lightweight, ~60KB, no dependencies)
- **Alternative:** D3.js (more powerful, steeper learning curve)
- Lazy load charts for better initial page load
- Use responsive chart configurations
- Maintain dark theme color scheme

### Files to Modify
- `/public/stats/competition.html` - Add chart rendering
- `/public/league/index.html` - Optional: mini-charts for quick stats

### Technical Considerations
- Charts should load after page render (progressive enhancement)
- Use cached data to avoid excessive API calls
- Ensure charts are accessible (provide data tables as fallback)
- Test performance on mobile devices

---

## 2. Historical Archive Browser

**Priority:** MEDIUM  
**Estimated Effort:** Medium (3-4 days)

### Description
Week-by-week navigation interface for browsing historical competition data.

### Features Needed
- Browse past weeks with prev/next navigation
- Filter by season (2025_Q4, 2026_Q1, etc.)
- Search by week number or date range
- View historical standings for any week
- Compare performance across weeks

### Data Structure
Archive data already exists at `/leaderboard/data/weekly/archive/`
- Format: `2025_W{week_number}.json`
- Contains: standings, statistics, seed info

### Suggested Implementation
```javascript
// Archive structure
{
  "archives": [
    {
      "week_id": "2025_W40",
      "season": "2025_Q4",
      "start_date": "2025-09-30",
      "end_date": "2025-10-06",
      "winner": "Player Name",
      "high_score": 1234,
      "participants": 15
    }
  ]
}
```

### Files to Create/Modify
- `/public/league/archive.html` - New archive browser page
- `/public/league/index.html` - Add "View Archives" button
- JavaScript module for archive data loading

### UI Components
- Calendar view or list view toggle
- Season filter dropdown
- Week detail modal/page
- Pagination for large datasets

---

## 3. Detailed Player Profile Pages

**Priority:** MEDIUM  
**Estimated Effort:** Large (5-7 days)

### Description
Individual player statistics and performance history pages.

### Features Needed
- Personal best scores across all seeds
- Rank history and improvement trends
- Week-by-week participation record
- Average performance metrics (score, doom risk, turns)
- Head-to-head comparison with other players (optional)

### URL Structure
- `/players/{player_name}/` or `/players/{player_uuid}/`
- Example: `/players/Catalyst_Labs/`

### Data Requirements
Aggregate data from:
- Current week leaderboard
- Historical archives
- Seed-specific leaderboards

### Suggested Implementation
- Static page generation or dynamic rendering
- Profile data JSON structure:
```javascript
{
  "player_name": "Catalyst Labs",
  "uuid": "...",
  "total_games": 47,
  "best_score": 1234,
  "average_score": 856.5,
  "best_rank": 1,
  "weeks_participated": 8,
  "current_streak": 3,
  "achievements": [...],
  "history": [...]
}
```

### Privacy Considerations
- Consider allowing players to opt-out of public profiles
- Anonymize UUID if privacy is a concern
- Only show aggregate stats, not individual game details

### Files to Create
- `/public/players/index.html` - Player directory (optional)
- `/public/players/[player].html` - Dynamic or static profile pages
- JavaScript for profile data aggregation

---

## 4. Achievement System Integration

**Priority:** LOW  
**Estimated Effort:** Medium (3-4 days)

### Description
Visual badge system for player milestones and achievements.

### Achievement Types

#### Competition-Based
- 🥇 **First Place** - Top rank in any week
- 🥈 **Silver Medal** - 2nd place finish
- 🥉 **Bronze Medal** - 3rd place finish
- 🏆 **Perfect Week** - Win with 0% doom risk
- 🎯 **High Scorer** - Score > 1000

#### Participation-Based
- 🔥 **Hot Streak** - 3+ consecutive weeks
- ⚡ **Lightning Fast** - Submit score in first hour
- 📅 **Early Bird** - First submission of the week
- 🎪 **Regular** - Participate in 10+ weeks
- 💎 **Veteran** - Participate in 25+ weeks

#### Performance-Based
- 🛡️ **Safety First** - Average doom < 20%
- 🚀 **Risk Taker** - Win with doom > 50%
- 📈 **Improver** - 5+ rank improvement in a week
- 🎓 **Scholar** - 100+ research papers published
- 💰 **Wealthy** - End game with $1M+ money

### Technical Implementation
- Backend system for achievement tracking (may require API changes)
- Badge SVG icons or emoji
- Achievement data structure:
```javascript
{
  "achievement_id": "first_place",
  "name": "First Place",
  "description": "Achieved top rank in a weekly competition",
  "icon": "🥇",
  "rarity": "rare",
  "earned_date": "2025-10-01",
  "week": "2025_W40"
}
```

### Files to Modify
- `/public/league/index.html` - Show achievements in standings
- `/public/players/[player].html` - Achievement showcase
- `/public/leaderboard/index.html` - Badge icons next to names

---

## 5. Real-time Score Notifications

**Priority:** LOW  
**Estimated Effort:** Large (4-6 days, includes backend)

### Description
Live notifications when new scores are submitted during active competitions.

### Features Needed
- Toast notification for new score submissions
- Notification badge with count
- "New scores available" indicator
- Option to enable/disable notifications

### Technical Approaches

#### Option A: Server-Sent Events (SSE)
- Lightweight, one-way communication
- Easy to implement
- Good browser support
```javascript
const eventSource = new EventSource('/api/league/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  showNotification(data);
};
```

#### Option B: WebSocket
- Full duplex communication
- More complex setup
- Useful if we need two-way communication

#### Option C: Polling Enhancement
- Fall back to smarter polling
- Exponential backoff
- Only poll during active competitions

### UI Components
- Toast notification component
- Notification permission request
- Settings toggle for notifications
- Visual indicator of new submissions

### Backend Requirements
- Streaming endpoint or WebSocket server
- Event publishing when scores submitted
- Rate limiting to prevent spam

### Files to Create/Modify
- `/public/league/index.html` - Add notification UI
- `/public/assets/js/notifications.js` - Notification module
- Backend: New streaming endpoint (requires backend work)

---

## Implementation Priority

### Phase 1 (Next Sprint)
**Goal:** Improve data visualization
- ✅ Interactive performance charts
- Estimated: 2-3 days
- High user impact

### Phase 2 (Q4 2025)
**Goal:** Historical data access
- ✅ Historical archive browser
- ✅ Player profile pages
- Estimated: 8-11 days total
- Medium user impact

### Phase 3 (Q1 2026)
**Goal:** Engagement features
- ✅ Achievement system
- Estimated: 3-4 days
- Low-medium impact

### Phase 4 (Future/Optional)
**Goal:** Real-time features
- ✅ Real-time notifications
- Estimated: 4-6 days + backend
- Requires infrastructure investment

---

## Technical Guidelines

### Must Maintain
- ✅ Pure JavaScript (no framework dependencies)
- ✅ Mobile-first responsive design
- ✅ Dark theme aesthetic
- ✅ WCAG 2.1 accessibility compliance
- ✅ Progressive enhancement
- ✅ Performance optimization

### Performance Targets
- Page load: < 2s on 3G
- Time to interactive: < 3s
- Chart rendering: < 500ms
- Archive loading: < 1s

### Browser Support
- Chrome/Edge (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Mobile browsers (iOS Safari, Chrome Mobile)

---

## Success Metrics

### User Engagement
- Track page views for new features
- Monitor time spent on archive pages
- Measure player profile view counts
- Track achievement unlock rates

### Performance
- Monitor page load times
- Track API response times
- Measure chart rendering performance
- Monitor mobile performance metrics

### User Feedback
- Collect feedback on new features
- Monitor bug reports
- Track feature requests
- Measure user satisfaction

---

## Resources

### Charting Libraries
- [Chart.js](https://www.chartjs.org/) - Recommended, lightweight
- [D3.js](https://d3js.org/) - More powerful, complex
- [ApexCharts](https://apexcharts.com/) - Good alternative

### Testing Tools
- Lighthouse for performance
- axe DevTools for accessibility
- BrowserStack for cross-browser testing

### Design References
- Current Weekly League Dashboard
- Existing leaderboard patterns
- Competition statistics page

---

## Notes

- All enhancements should be backwards compatible
- Consider API rate limits when implementing real-time features
- Document all new features in user-facing documentation
- Update screenshots and demos after implementation
- Consider internationalization for future expansion

---

**Last Updated:** 2025-10-19  
**Maintainer:** Development Team  
**Review Schedule:** Quarterly
