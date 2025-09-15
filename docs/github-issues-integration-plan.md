# GitHub Issues Integration Plan

## Goal
Embed a live summary of all GitHub issues from the main p(Doom)1 repository directly into the game's website.

## Implementation Plan

### Phase 1: Basic Integration
- [ ] Create GitHub API integration to fetch issues from PipFoweraker/pdoom1
- [ ] Add new "Known Issues" or "Bug Tracker" section to website
- [ ] Display open issues with titles, labels, and status
- [ ] Auto-refresh data periodically

### Phase 2: Enhanced Display
- [ ] Categorize issues by type (bug, feature, enhancement)
- [ ] Show issue priority and affected platforms
- [ ] Link directly to GitHub issues for detailed discussion
- [ ] Display issue creation/update dates

### Phase 3: Integration with Game Status
- [ ] Connect issue status to game download warnings
- [ ] Show platform-specific known issues on download page
- [ ] Auto-update game status based on critical open issues

### Technical Implementation
- [ ] GitHub API integration (likely in JavaScript for client-side updates)
- [ ] Caching mechanism to avoid rate limits
- [ ] Responsive design for issue display
- [ ] Filter/search functionality for users

### Benefits
- Real-time transparency about game issues
- Reduces duplicate bug reports
- Shows active development/maintenance
- Helps users make informed download decisions

## Current Status
- Planning phase
- Mac TypeError bug (Issue #299) is first test case
- Will implement after fixing critical bugs

## Priority
Medium - adds transparency and reduces support overhead
