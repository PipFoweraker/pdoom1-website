# phpBB Forum Integration Plan

**Status:** Planning Phase
**Priority:** High
**Target:** v1.3.0
**Estimated Effort:** 2-3 weeks
**Dependencies:** DreamHost access, domain configuration

---

## 🎯 Objective

Install and integrate a self-hosted phpBB forum at `forum.pdoom1.com` (or `pdoom1.com/forum/`) to create a community hub for players to discuss strategies, share stories, report bugs, and connect with the development team.

**Inspiration:** Path of Exile's forum system (pathofexile.com/forum) - keeps conversation on-site, builds community identity, and enables future Steam integration for rewards.

---

## 📋 Requirements

### Core Functionality
- [x] Self-hosted (no external dependencies)
- [x] Privacy-respecting (GDPR compliant)
- [x] Low maintenance overhead
- [x] Mobile-friendly interface
- [x] Integration with pdoom1.com design system
- [x] Single sign-on capability (future: Steam integration)

### User Experience Goals
1. **Low friction** - Easy registration and posting
2. **Engaging** - Clear categories, active moderation
3. **Rewarding** - Future: In-game cosmetics for contributors
4. **Community-driven** - Player strategies, feedback, fan content

---

## 🏗️ Technical Architecture

### Hosting Setup
- **Platform:** phpBB 3.3.x (latest stable)
- **Server:** DreamHost (existing hosting)
- **URL:** `forum.pdoom1.com` or `pdoom1.com/forum/`
- **Database:** MySQL (DreamHost provided)
- **PHP:** 7.4+ (check DreamHost compatibility)

### Why phpBB?
✅ **Mature & Stable** - 20+ years of development
✅ **Self-hosted** - Full control over data and privacy
✅ **Extensible** - Rich ecosystem of mods and themes
✅ **Low Cost** - $0/month (uses existing hosting)
✅ **Active Community** - Strong support and documentation
✅ **SEO Friendly** - Good for discoverability

**Alternatives Considered:**
- Discourse: Heavy resource requirements, costly hosting
- Reddit-style: Less forum-like, harder to theme
- Discord: Ephemeral, no SEO, not on our domain

---

## 📝 Implementation Plan

### Phase 1: Installation & Basic Setup (Week 1)

**Tasks:**
1. [ ] Create subdomain: `forum.pdoom1.com`
2. [ ] Download phpBB 3.3.x from official source
3. [ ] Upload via FTP/SFTP to DreamHost
4. [ ] Create MySQL database and user
5. [ ] Run phpBB installer
6. [ ] Configure basic settings (site name, description, email)
7. [ ] Install SSL certificate (Let's Encrypt via DreamHost)
8. [ ] Test basic functionality (register, post, moderate)

**Deliverables:**
- Working phpBB installation
- Admin access configured
- Basic security hardening complete

---

### Phase 2: Theming & Design Integration (Week 1-2)

**Tasks:**
1. [ ] Install phpBB theme framework
2. [ ] Create custom theme matching pdoom1.com design system
   - Dark theme (primary)
   - Matrix green accents (#00ff41)
   - Courier New monospace font
   - Consistent borders and styling
3. [ ] Add custom header with pdoom1 logo
4. [ ] Create navigation links to main site
5. [ ] Mobile responsive testing
6. [ ] Add custom footer with links

**Design Tokens to Match:**
```css
--bg-primary: #1a1a1a;
--bg-secondary: #2d2d2d;
--accent-primary: #00ff41;
--accent-secondary: #ff6b35;
--text-primary: #ffffff;
--border-color: #444444;
```

**Deliverables:**
- Custom phpBB theme
- Mobile-friendly layout
- Consistent branding with main site

---

### Phase 3: Forum Structure & Categories (Week 2)

**Tasks:**
1. [ ] Create forum categories:
   - **Announcements** (Dev posts, updates, releases)
   - **General Discussion** (Off-topic, introductions)
   - **Strategy & Tactics** (Gameplay discussion, tips)
   - **Bug Reports** (Technical issues, crashes)
   - **Feature Requests** (Ideas, suggestions)
   - **Fan Content** (Screenshots, stories, memes)
   - **Modding & Development** (For contributors)
2. [ ] Set up permissions per category
3. [ ] Create welcome/rules post (pinned)
4. [ ] Set up moderation tools
5. [ ] Configure anti-spam measures (CAPTCHA, email verification)

**Deliverables:**
- Organized forum structure
- Clear posting guidelines
- Anti-spam protection

---

### Phase 4: Integration & Launch (Week 2-3)

**Tasks:**
1. [ ] Add forum link to main site navigation
2. [ ] Create `/forum/` redirect from main site
3. [ ] Set up email notifications (SendGrid or SMTP)
4. [ ] Configure RSS feeds for announcements
5. [ ] Test registration flow end-to-end
6. [ ] Create admin/moderator accounts
7. [ ] Seed initial posts (welcome, guidelines, FAQ)
8. [ ] Launch announcement on main site and social media

**Integration Points:**
- Main site header: Add "Forum" nav link
- Issues page: Link to bug report forum category
- Footer: Add forum link
- Dashboard: "Latest forum discussions" widget (future)

**Deliverables:**
- Live forum at forum.pdoom1.com
- Integrated with main site
- Initial content and moderation setup

---

## 🔒 Privacy & Security

### GDPR Compliance
- [ ] Privacy policy for forum (separate from main site)
- [ ] Cookie consent (phpBB sessions only)
- [ ] Data retention policy (purge old accounts after X months inactive)
- [ ] User data export capability (phpBB has built-in tools)
- [ ] Right to be forgotten (account deletion process)

### Security Hardening
- [ ] Change default admin URL
- [ ] Disable directory listing
- [ ] Restrict file upload types
- [ ] Enable HTTPS only
- [ ] Regular phpBB updates (security patches)
- [ ] Implement rate limiting
- [ ] Block known spam IPs (Akismet or similar)

### Backup Strategy
- [ ] Daily database backups (via DreamHost)
- [ ] Weekly full backups (database + uploads)
- [ ] Store backups off-site (separate from DreamHost)
- [ ] Test restore process quarterly

---

## 🎮 Future: Steam Integration & Rewards

**Vision:** Reward forum contributors with in-game cosmetics, similar to Path of Exile's supporter packs.

### Phase 5: Steam Integration (v2.0+)

**Requirements:**
1. Steam OpenID authentication
2. Link forum accounts to Steam profiles
3. API to verify forum activity (posts, helpful answers)
4. Game integration to unlock cosmetics based on forum activity

**Reward Tiers (Ideas):**
- **Active Member** (10+ helpful posts): Forum badge, in-game title
- **Community Helper** (50+ posts, 10+ solutions): Custom player icon
- **Cat Picture Submission**: Your cat appears as NPC in game! 🐱
- **Strategy Guide Author**: Name in credits, special cosmetic
- **Bug Hunter**: Special debug-themed cosmetic

**Technical Implementation:**
1. phpBB extension for Steam OpenID
2. Database linking Steam ID ↔ Forum User ID
3. API endpoint: `/api/v1/rewards/check?steamid=XXX`
4. Game queries API at startup, unlocks rewards
5. Future: In-game "Submit Feedback" button opens forum

**Privacy Considerations:**
- Opt-in for Steam linking
- Clear disclosure of what data is shared
- Ability to unlink at any time
- No data shared with third parties

---

## 📊 Success Metrics

### Short-term (First 3 Months)
- 100+ registered users
- 500+ posts
- 10+ active daily users
- <1% spam posts (effective moderation)
- 50+ bug reports filed via forum

### Long-term (6-12 Months)
- 1,000+ registered users
- Active community-driven strategy discussions
- Player-created content (guides, videos)
- Successful Steam integration pilot
- Positive sentiment in community surveys

---

## 🛠️ Maintenance Plan

### Regular Tasks
- **Daily:** Monitor moderation queue, respond to reports
- **Weekly:** Review spam logs, update anti-spam rules
- **Monthly:** phpBB security updates, backup verification
- **Quarterly:** Review forum structure, add/remove categories as needed

### Staffing
- **Primary Admin:** Pip Foweraker
- **Moderators:** TBD (recruit from community after launch)
- **Backup Admin:** TBD (technical person with DreamHost access)

---

## 💰 Cost Analysis

### Initial Setup
- **Domain:** $0 (use subdomain of pdoom1.com)
- **Hosting:** $0 (existing DreamHost plan)
- **Software:** $0 (phpBB is free)
- **Theme:** $0 (custom built)
- **Labor:** ~20-30 hours (planning + setup)

### Ongoing Costs
- **Hosting:** $0/month (included in current plan)
- **Maintenance:** ~2-5 hours/week (moderation + updates)
- **Spam Protection:** $0-10/month (if using paid service like Akismet)

**Total:** ~$0-120/year (plus volunteer moderation time)

---

## 🚧 Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Spam overwhelms forum | High | Medium | Implement CAPTCHA, email verification, moderation tools |
| Low user engagement | Medium | Medium | Seed content, promote on main site, rewards program |
| Security breach | High | Low | Regular updates, hardening, monitoring |
| Moderation burnout | Medium | Medium | Recruit volunteer moderators, clear guidelines |
| DreamHost resource limits | Low | Low | Monitor usage, upgrade plan if needed |

---

## 📚 Resources

### Documentation
- phpBB Official Docs: https://www.phpbb.com/support/docs/
- phpBB Security Guide: https://www.phpbb.com/support/docs/en/3.3/ug/security/
- DreamHost phpBB Guide: https://help.dreamhost.com/

### Community
- phpBB Community Forums: https://www.phpbb.com/community/
- phpBB Extensions Database: https://www.phpbb.com/customise/db/

### Inspiration
- Path of Exile Forums: https://www.pathofexile.com/forum
- Factorio Forums: https://forums.factorio.com/
- Kerbal Space Program Forums: https://forum.kerbalspaceprogram.com/

---

## 📅 Timeline

```
Week 1
├─ Day 1-2: Subdomain setup, phpBB installation
├─ Day 3-4: Basic configuration, security hardening
└─ Day 5-7: Theme development begins

Week 2
├─ Day 8-10: Theme completion, mobile testing
├─ Day 11-12: Forum structure creation
└─ Day 13-14: Category setup, permissions

Week 3
├─ Day 15-16: Integration with main site
├─ Day 17-18: Testing, anti-spam configuration
├─ Day 19-20: Seed content, moderator training
└─ Day 21: Launch! 🚀
```

---

## ✅ Launch Checklist

### Pre-Launch
- [ ] phpBB installed and tested
- [ ] Theme applied and mobile-tested
- [ ] All categories created
- [ ] Rules and guidelines posted
- [ ] Anti-spam measures enabled
- [ ] Email notifications working
- [ ] Backup system tested
- [ ] Privacy policy published
- [ ] Integration with main site complete
- [ ] Admin and moderator accounts ready

### Launch Day
- [ ] Announcement post on main site
- [ ] Social media posts (if applicable)
- [ ] Email newsletter (if applicable)
- [ ] Monitor for issues first 24 hours
- [ ] Respond to first posts/questions

### Post-Launch (First Week)
- [ ] Daily monitoring for spam
- [ ] Engage with early users
- [ ] Collect feedback on UX
- [ ] Adjust moderation rules as needed
- [ ] Create FAQ based on common questions

---

## 🎉 Conclusion

A self-hosted phpBB forum will:
1. **Build Community** - Give players a home to connect
2. **Centralize Feedback** - Easier bug tracking and feature requests
3. **Enable Future Features** - Steam integration, rewards, events
4. **Increase Engagement** - Keep players invested in the game
5. **Low Cost** - $0/month using existing infrastructure

This positions p(Doom)1 as a serious indie game with a thriving community, following the model of successful games like Path of Exile.

---

**Next Steps:**
1. Review and approve this plan
2. Create GitHub issue for tracking
3. Schedule Week 1 tasks
4. Begin subdomain and database setup

---

**Questions? Feedback?**
Discuss in GitHub issue #XXX or contact team@pdoom1.com

---

*Document Version: 1.0*
*Created: 2025-10-30*
*Last Updated: 2025-10-30*
*Author: Claude Code*
*Approved by: [Pending]*
