# Self-Hosted Forum Implementation

## 🎯 Objective

**Replace Discord** with a self-hosted forum at `forum.pdoom1.com` to:
- Own our community data
- Avoid Discord's AI enshittification
- Create lasting, SEO-friendly content
- Reward community contributions directly
- Build a permanent archive of knowledge

**Inspiration:** GGG's Path of Exile forums - on-site discussion that builds community identity and enables reward integration.

---

## 🔥 Why This Matters

**Discord Problems:**
- ❌ Ephemeral (content disappears)
- ❌ No SEO (not searchable/indexable)
- ❌ AI training on our data without consent
- ❌ Platform lock-in
- ❌ Can't reward contributors with in-game items
- ❌ Not our domain, not our rules

**Self-Hosted Benefits:**
- ✅ **Permanent archive** - words on pages that last forever
- ✅ **SEO benefits** - discoverable via search engines
- ✅ **Full control** - our data, our rules
- ✅ **Direct rewards** - integrate with game for contributor perks
- ✅ **Privacy** - GDPR compliant, no third-party tracking
- ✅ **Community identity** - forum.pdoom1.com, not discord.gg/random

---

## 📊 Platform Comparison (2025 Research)

### Option 1: **NodeBB** ⭐ RECOMMENDED

**Why NodeBB:**
- ✅ Modern, real-time interactions (Node.js)
- ✅ Mobile-first design
- ✅ ActivityPub support (fediverse integration!)
- ✅ SEO-optimized out of the box
- ✅ Built-in analytics dashboard
- ✅ Real-time chat capabilities
- ✅ Lighter than Discourse, more feature-rich than Flarum
- ✅ Active development and community

**Resource Requirements:**
- RAM: 1-2GB
- Disk: 5-10GB
- Node.js 16+
- MongoDB or PostgreSQL

**Hosting Cost:** $0/month (uses existing DreamHost VPS or similar)

**Setup Time:** 1-2 hours (Docker) or 3-4 hours (manual)

---

### Option 2: Discourse

**Pros:**
- Enterprise-grade moderation
- Trust system for users
- Huge community (22k+ forums)

**Cons:**
- ❌ Heavy resource usage (2GB+ RAM required)
- ❌ Docker-only (more complex setup)
- ❌ Overkill for small-medium communities

---

### Option 3: Flarum

**Pros:**
- Lightweight and fast
- Beautiful, clean UI
- Easy PHP setup

**Cons:**
- ❌ Limited features for scaling
- ❌ Beta stability concerns
- ❌ Fewer integrations

---

### Option 4: phpBB (Original Plan)

**Pros:**
- Mature (20+ years)
- Simple PHP/MySQL
- Low resources

**Cons:**
- ❌ Dated interface
- ❌ Feels old compared to modern alternatives
- ❌ Less real-time interaction

---

## 🏗️ Implementation Plan - NodeBB

### Phase 1: Server Setup (Week 1)

**Tasks:**
- [ ] Provision subdomain: `forum.pdoom1.com`
- [ ] Set up SSL certificate (Let's Encrypt)
- [ ] Install Node.js 18+ on server
- [ ] Install MongoDB or PostgreSQL
- [ ] Configure reverse proxy (nginx)
- [ ] Set up backups

**Deliverables:**
- Working server environment
- SSL configured
- Database ready

---

### Phase 2: NodeBB Installation (Week 1)

**Tasks:**
- [ ] Download NodeBB
- [ ] Run `./nodebb setup`
- [ ] Configure database connection
- [ ] Set up admin account
- [ ] Test basic functionality
- [ ] Configure email (SMTP)
- [ ] Enable HTTPS

**Deliverables:**
- NodeBB running at forum.pdoom1.com
- Admin access configured
- Email notifications working

---

### Phase 3: Theming & Design (Week 2)

**Tasks:**
- [ ] Install theme framework
- [ ] Create custom theme matching pdoom1.com:
  - Dark theme (`#1a1a1a` background)
  - Matrix green accents (`#00ff41`)
  - Courier New monospace font
  - Consistent borders and styling
- [ ] Add pdoom1 logo to header
- [ ] Create navigation links to main site
- [ ] Mobile responsive testing
- [ ] Custom footer

**Design System:**
```css
--bg-primary: #1a1a1a;
--bg-secondary: #2d2d2d;
--accent-primary: #00ff41;
--accent-secondary: #ff6b35;
--text-primary: #ffffff;
--border-color: #444444;
```

**Deliverables:**
- Custom NodeBB theme
- Visual consistency with main site
- Mobile-friendly interface

---

### Phase 4: Forum Structure (Week 2-3)

**Categories:**
1. **🎮 Gameplay**
   - Strategies & Tips
   - Turn Reports
   - Achievement Showcase
2. **🐛 Bug Reports**
   - Game Bugs
   - Website Issues
   - Technical Support
3. **💡 Suggestions**
   - Feature Requests
   - Balance Discussion
   - Quality of Life
4. **📰 News & Updates**
   - Patch Notes
   - Dev Blog
   - Community Events
5. **🎨 Creative**
   - Fan Art
   - Stories
   - Memes
6. **🔧 Modding** (future)
   - Mod Development
   - Mod Showcase

**Deliverables:**
- Forum categories created
- Moderator guidelines
- Posting rules
- Welcome message

---

### Phase 5: Integration (Week 3-4)

**Main Site Integration:**
- [ ] Add "Forum" link to nav (replace Discord)
- [ ] Embed latest forum posts on homepage
- [ ] RSS feed integration
- [ ] Single Sign-On (future: Steam OAuth)

**Game Integration (Future):**
- [ ] API for forum post count
- [ ] Reward system: Forum posts → in-game cosmetics
- [ ] "Cat NPC" reward for top contributors
- [ ] Achievement badges sync

**Deliverables:**
- Forum linked from main site
- Latest posts visible on homepage
- Cross-promotion working

---

### Phase 6: Migration & Launch (Week 4)

**Migration from Discord:**
- [ ] Announce forum to Discord community
- [ ] Archive important Discord threads to forum
- [ ] Gradual Discord wind-down plan
- [ ] Redirect users to forum

**Launch Checklist:**
- [ ] Backup system tested
- [ ] Moderation team trained
- [ ] Community guidelines posted
- [ ] Welcome thread created
- [ ] First 10 users registered
- [ ] Announcement post on main site

**Deliverables:**
- Public launch
- Discord migration complete
- Active moderation

---

## 🔐 Security & Privacy

**Required:**
- HTTPS everywhere
- CAPTCHA for registration
- Rate limiting
- Email verification
- IP banning tools
- GDPR compliance tools

**NodeBB Features:**
- Built-in spam prevention
- Akismet integration
- IP logging for moderation
- User ban/suspension tools

---

## 💰 Cost Analysis

**Hosting:**
- NodeBB: $0/month (existing VPS)
- Domain: $0 (subdomain of pdoom1.com)
- SSL: $0 (Let's Encrypt)
- Database: $0 (included with VPS)

**Total: $0/month** (assuming VPS capacity)

**Time Investment:**
- Initial setup: 20-30 hours
- Monthly maintenance: 2-4 hours
- Moderation: Variable (community-driven)

---

## 🎮 Community Rewards System (Future Phase)

### Reward Tiers
1. **Active Member** (10 posts) → Forum badge
2. **Contributor** (50 posts) → In-game title
3. **Cat Custodian** (100 quality posts) → Cat NPC named after you
4. **Legend** (500 posts + mod approval) → Custom in-game item

### Technical Implementation
- NodeBB API → Game server webhook
- Player links Steam/GitHub to forum account
- Post count/quality tracked
- Manual approval for top-tier rewards

---

## 📈 Success Metrics

**Week 1:**
- Forum live and accessible
- 10+ registered users
- 5+ threads created

**Month 1:**
- 50+ registered users
- 100+ posts
- Daily active users: 10-20
- No major technical issues

**Month 3:**
- 200+ users
- 500+ posts
- SEO: 10+ forum pages indexed
- Discord fully replaced

---

## 🚨 Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Low adoption | Incentivize with rewards, promote heavily |
| Spam/trolling | Strong moderation, CAPTCHA, rate limits |
| Server overload | Monitor resources, upgrade VPS if needed |
| Data loss | Daily backups, test restore process |
| Downtime | Status page, quick rollback plan |

---

## 📚 Resources

**NodeBB:**
- Docs: https://docs.nodebb.org
- GitHub: https://github.com/NodeBB/NodeBB
- Community: https://community.nodebb.org
- Themes: https://community.nodebb.org/category/7/nodebb-themes

**Alternatives:**
- Discourse: https://www.discourse.org
- Flarum: https://flarum.org
- phpBB: https://www.phpbb.com

---

## 🎯 Decision Points

**Choose NodeBB if:**
- ✅ Want modern, real-time features
- ✅ Value mobile-first design
- ✅ Like ActivityPub/fediverse support
- ✅ Need good balance of features vs. resources

**Choose Discourse if:**
- Enterprise-grade moderation needed
- Have 4GB+ RAM available
- Want the "industry standard"

**Choose Flarum if:**
- Minimalist approach preferred
- Very limited resources
- Small community (<100 users)

---

## 🚀 Next Steps

1. **Immediate:** Approve this issue and platform choice (NodeBB recommended)
2. **This week:** Set up subdomain and server environment
3. **Next week:** Install NodeBB and configure
4. **Week 3-4:** Theme customization and category setup
5. **Week 4-5:** Launch and migration from Discord

---

## 💬 Discussion

**Questions to resolve:**
- Confirm NodeBB as platform choice?
- VPS specs: Do we need to upgrade hosting?
- Moderator team: Who will help moderate?
- Launch timing: Coordinate with game release?

---

**Labels:** enhancement, priority: high, community, infrastructure
**Milestone:** v1.3.0
**Estimate:** 30-40 hours (4-5 weeks calendar time)

---

**Let's own our community. Let's make content that lasts. Let's do this.** 🚀
