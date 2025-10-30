# Manifold Markets Integration & 10 Interesting Markets

**Priority:** Medium
**Type:** Enhancement
**Components:** Website, Game Data, Community Engagement
**Estimated Effort:** 2-3 days

---

## 🎯 Objective

Integrate Manifold Markets prediction markets into the p(Doom)1 ecosystem to:
1. Create community engagement around AI Safety predictions
2. Provide real-world forecasting data for game calibration
3. Build credibility with rationalist/EA communities
4. Generate organic traffic from Manifold users

**Inspiration:** Metaculus integration with AI Alignment Forum, Polymarket's crypto prediction markets

---

## 📋 Requirements

### Phase 1: 10 Interesting Markets (Week 1)
Create 10 prediction markets on Manifold that:
- Relate to p(Doom)1 themes
- Are interesting to AI Safety community
- Have clear resolution criteria
- Drive traffic back to pdoom1.com

### Phase 2: Website Integration (Week 2)
- Display live Manifold market data on pdoom1.com
- Embed market widgets on relevant pages
- Link to markets from game stats/dashboard

### Phase 3: Game Integration (Future)
- Use Manifold probabilities to calibrate game parameters
- Display community predictions in-game
- Achievement for participating in markets

---

## 🎲 10 Proposed Manifold Markets

### Category: AI Timeline Predictions

#### 1. **"Will p(Doom)1 reach 10,000 downloads by end of 2025?"**
- **Resolution:** GitHub release download count + Steam (when available)
- **Current Baseline:** ~500 downloads
- **Why Interesting:** Tests game's virality and community growth

#### 2. **"Will any Frontier AI Lab release a model >10T parameters in 2025?"**
- **Resolution:** Public announcement from OpenAI, Anthropic, DeepMind, Meta, xAI, or Mistral
- **Current Baseline:** GPT-4 ~1.8T (rumored)
- **Why Interesting:** Tests scaling law predictions, relevant to game modeling

#### 3. **"Will Claude Code (or similar coding agent) surpass 50% of programmer productivity by end of 2026?"**
- **Resolution:** Survey data or benchmark results
- **Why Interesting:** AI capability advancement directly impacts p(Doom) calculations

---

### Category: AI Safety & Governance

#### 4. **"Will the US pass AI safety legislation requiring pre-deployment testing by end of 2026?"**
- **Resolution:** Federal law enacted
- **Why Interesting:** Central to p(Doom)1 policy mechanics

#### 5. **"Will any Frontier Lab voluntarily pause training runs >10^26 FLOPs before 2027?"**
- **Resolution:** Public announcement + 6+ month pause
- **Why Interesting:** Tests safety culture predictions, key game event

#### 6. **"Will Anthropic's Claude reach #1 in LMSYS Chatbot Arena for 30 consecutive days by end of 2025?"**
- **Resolution:** LMSYS leaderboard data
- **Why Interesting:** Safety-focused lab vs capabilities race

---

### Category: p(Doom) Meta-Predictions

#### 7. **"Will median AI researcher p(Doom) estimate increase from 2024 to 2025?"**
- **Resolution:** AI Impacts survey or similar
- **Current:** ~5-10% median (varies by survey)
- **Why Interesting:** Directly tracks the game's core mechanic

#### 8. **"Will p(Doom)1 game get featured on Hacker News front page (top 10) in 2025?"**
- **Resolution:** Hacker News ranking data
- **Why Interesting:** Community validation, traffic driver

#### 9. **"Will Eliezer Yudkowsky tweet about p(Doom)1 by end of 2025?"**
- **Resolution:** Twitter/X search
- **Why Interesting:** High-profile AI Safety figure, huge credibility boost

---

### Category: Game-Specific

#### 10. **"Will p(Doom)1 get a Steam release with 'Overwhelmingly Positive' reviews (95%+) by end of 2025?"**
- **Resolution:** Steam store page rating
- **Why Interesting:** Tests game quality and community sentiment

---

## 🔧 Technical Implementation

### Manifold API Integration

**Endpoints Needed:**
- `GET /v0/markets` - Fetch market list
- `GET /v0/market/:id` - Get specific market details
- `GET /v0/bets` - Get bet history (optional)

**Display Locations:**
1. **Homepage** - "Community Predictions" widget
   - Show 3 featured markets
   - Live probability updates
   - "View all markets →" link

2. **Dashboard** - Manifold widget in sidebar
   - Current p(Doom) meta-prediction
   - Related AI timeline markets

3. **Resources Page** - "Forecasting & Prediction Markets" section
   - Links to all p(Doom)1 markets
   - Brief explainer on Manifold

**Example Widget Code:**
```html
<div class="manifold-widget">
  <h3>Community Prediction</h3>
  <iframe src="https://manifold.markets/embed/username/market-slug"
          height="400"
          width="100%"
          frameborder="0">
  </iframe>
</div>
```

---

## 📊 Success Metrics

### Market Engagement
- **Target:** 100+ traders across all markets
- **Target:** $1,000+ mana volume across all markets
- **Target:** 500+ comments/discussion

### Traffic & Conversion
- **Target:** 1,000+ visitors from Manifold → pdoom1.com
- **Target:** 10%+ conversion to game downloads
- **Target:** 50+ new GitHub stars from Manifold community

### Community Validation
- **Target:** Markets shared on LessWrong, EA Forum
- **Target:** Positive sentiment in comments
- **Target:** Request for more markets

---

## 🚧 Implementation Plan

### Week 1: Create Markets
- [ ] Set up Manifold account for "p(Doom)1 Official"
- [ ] Create all 10 markets with clear descriptions
- [ ] Seed each market with 100-200 mana
- [ ] Post to LessWrong/EA Forum announcing markets
- [ ] Share on X/Twitter, Bluesky

### Week 2: Website Integration
- [ ] Create `/markets/` page on pdoom1.com
- [ ] Embed top 3 markets on homepage
- [ ] Add Manifold link to footer (Community section)
- [ ] Write blog post about markets
- [ ] Update sitemap.xml

### Week 3: Promotion & Monitoring
- [ ] Post in Manifold Discord
- [ ] Engage with commenters/traders
- [ ] Create follow-up markets based on community interest
- [ ] Track traffic from Manifold in analytics

---

## 💡 Market Ideas - Extended List

If initial markets succeed, create:
- "Will p(Doom)1 win an indie game award in 2025?"
- "Will OpenAI's o3 model beat humans at Codeforces (median) by 2026?"
- "Will China announce a >100B parameter model by end of 2025?"
- "Will p(Doom)1 get 1,000+ GitHub stars by end of 2025?"
- "Will Anthropic raise a Series D at >$30B valuation by 2026?"

---

## 📚 Resources

### Manifold Documentation
- API Docs: https://docs.manifold.markets/api
- Embed Guide: https://docs.manifold.markets/embed
- Creating Markets: https://docs.manifold.markets/creating-markets

### Inspiration
- Metaculus AI Predictions: https://www.metaculus.com/questions/?search=cat:ai
- Polymarket Trending: https://polymarket.com
- LessWrong Prediction Posts: https://www.lesswrong.com/tag/forecasting-and-prediction

### Community Platforms
- LessWrong: https://www.lesswrong.com
- EA Forum: https://forum.effectivealtruism.org
- Manifold Discord: https://discord.gg/manifold

---

## 🎯 Resolution Criteria Template

For each market, include:
1. **Clear yes/no condition** (or percentage for numeric markets)
2. **Specific date** for resolution
3. **Authoritative source** for data (no ambiguity)
4. **Edge cases** handled explicitly
5. **N/A conditions** if market becomes moot

**Example:**
```
Market: "Will p(Doom)1 reach 10,000 downloads by end of 2025?"

Resolution: YES if sum of:
- GitHub release downloads (all versions)
- Steam downloads (if released)
- Any other official distribution channels
>= 10,000 by 2025-12-31 23:59:59 UTC

Source: GitHub API + Steam API (or manual count from Steam dashboard if needed)

N/A: If project is abandoned or repo is deleted
```

---

## 🤝 Community Engagement Strategy

### Initial Announcement Post (LessWrong/EA Forum)

**Title:** "p(Doom)1 Prediction Markets: Bet on AI Safety & Game Success"

**Content:**
```markdown
I've created 10 Manifold Markets related to p(Doom)1, the AI Safety strategy game.

These markets cover:
- AI capability timelines
- Safety governance predictions
- Game virality forecasts
- Meta-predictions about p(Doom) itself

Why these markets matter:
1. Calibration data for game modeling
2. Community engagement with AI Safety themes
3. Real-world forecasting on tractable questions

[Link to markets]

Curious to see how the LW/EA forecasting community calibrates on these!

What other markets would you like to see?
```

---

## 💰 Budget

| Item | Cost | Notes |
|------|------|-------|
| Manifold mana (seeding) | $0-20 | Optional, can earn mana for free |
| Developer time | 16-24 hours | Market creation + integration |
| Marketing/promotion | $0 | Organic posts only |
| **Total** | **$0-20** | Extremely low cost experiment |

---

## 🚨 Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Low engagement | Medium | Medium | Seed markets with own bets, promote heavily |
| Resolution disputes | Low | Low | Use extremely clear criteria |
| Negative sentiment | Low | Low | Engage positively with critics |
| Time sink | Medium | Medium | Limit to 10 markets initially |

---

## ✅ Success Checklist

- [ ] All 10 markets created on Manifold
- [ ] Markets shared on LessWrong (>50 karma post)
- [ ] Markets shared on EA Forum
- [ ] Markets tweeted from @pdoom1 (or Pip's account)
- [ ] Homepage widget displaying markets
- [ ] `/markets/` page created
- [ ] Blog post about markets published
- [ ] Analytics tracking Manifold referrals
- [ ] First 50 trades received
- [ ] Positive community feedback

---

## 📅 Timeline

**Week 1:**
- Day 1-2: Create all markets
- Day 3: LessWrong/EA Forum posts
- Day 4-7: Monitor, respond, promote

**Week 2:**
- Day 8-10: Build website integration
- Day 11-12: Write blog post
- Day 13-14: Launch homepage widget

**Week 3:**
- Day 15-21: Promote, engage, iterate

---

## 🎉 Potential Upsides

1. **Community Validation** - Rationalists/EAs engaging = credibility
2. **Organic Traffic** - Manifold users → pdoom1.com → downloads
3. **Data Calibration** - Use probabilities to adjust game parameters
4. **Content Creation** - Markets = blog post ideas = SEO
5. **Network Effects** - Traders share markets → more visibility

---

**Next Steps:**
1. Get approval on 10 market ideas
2. Set up Manifold account
3. Create markets in one sitting (consistency)
4. Launch with coordinated social media push

---

**Questions? Feedback?**
Discuss in GitHub issue or contact team@pdoom1.com

---

*Document Version: 1.0*
*Created: 2025-10-30*
*Author: Claude Code*
*Status: ✅ Ready for Implementation*
