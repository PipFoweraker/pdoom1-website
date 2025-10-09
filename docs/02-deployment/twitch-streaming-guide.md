# Twitch Streaming Guide for Weekly Deployments

## Overview

Every Friday at 16:30 AEST, host a live stream showcasing the weekly deployment and new features.

## Pre-Stream Setup (16:00-16:30)

### Technical Setup
- [ ] **OBS Configuration**
  - Open OBS Studio
  - Load "p(Doom)1 Deployment" scene collection
  - Test audio levels (mic + desktop)
  - Test camera (optional)
  
- [ ] **Browser Sources**
  - Scene 1: pdoom1.com homepage
  - Scene 2: Leaderboard page
  - Scene 3: Terminal/console (for live debugging if needed)
  - Scene 4: GitHub Actions (deployment progress)
  
- [ ] **Audio Check**
  - Microphone levels good
  - Desktop audio capturing
  - Music volume low (if using)
  - Test audio delay

### Stream Information

**Title Template:**
```
p(Doom)1 Weekly Deployment - v{VERSION} - {HIGHLIGHT FEATURE}
```

**Examples:**
- "p(Doom)1 Weekly Deployment - v1.2.0 - New Balance Changes!"
- "p(Doom)1 Weekly Deployment - v1.1.5 - League Season 2!"
- "p(Doom)1 Weekly Deployment - v1.0.8 - Performance Updates"

**Category:** Science & Technology (or) Gaming

**Tags:**
- gamedev
- webdev
- deployment
- doom
- roguelike

**Stream Description:**
```
Join us for the weekly p(Doom)1 deployment! 

[DEPLOY] Deploying v{VERSION}
[TROPHY] New league week starting Monday
[CHAT] Q&A and feature showcase

Links:
[WEB] Website: https://pdoom1.com
[GAME] Download: https://pipfoweraker.itch.io/pdoom1
[CHAT] Discord: [Your Discord link]
[BIRD] Twitter: [Your Twitter]

Schedule:
16:30 - Deployment watch
16:45 - Feature showcase  
17:00 - League preview
17:15 - Q&A
17:30 - Wrap up
```

## Stream Timeline

### 16:30 - Opening (5 minutes)

**Start Stream**

**Say:**
> "Hey everyone! Welcome to the weekly p(Doom)1 deployment stream! We're deploying version {VERSION} today. The deployment should already be running, so let's check the status."

**Show:**
- GitHub Actions page with deployment running
- Explain what's happening in each step

**Engage:**
- Welcome viewers by name
- Ask: "Any questions about the deployment process?"

### 16:35 - Deployment Watch (10 minutes)

**Monitor GitHub Actions:**
```
[OK] Pre-deployment preparation
[OK] Deploy to production
[WAIT] Post-deployment tasks
```

**Commentary:**
- Explain each step as it happens
- "Now it's syncing game data..."
- "Health checks are running..."
- "Deployment propagating to production..."

**If deployment succeeds quickly:**
- Show the deployed site
- Point out version number in footer
- Do a quick smoke test

**If deployment has issues:**
- Stay calm, debug live
- Explain what you're checking
- Show logs and problem-solving
- This is actually good content!

### 16:45 - Feature Showcase (15 minutes)

**Navigate to pdoom1.com**

**Show New Features:**
1. **What Changed**
   ```
   Show: CHANGELOG.md or release notes
   Say: "Here's what's new this week..."
   ```

2. **Visual Changes**
   - Click through affected pages
   - Show before/after if available
   - Explain the reasoning

3. **Balance Changes**
   - Discuss game balance updates
   - Show where players can see changes
   - Explain impact on gameplay

4. **League Updates**
   ```
   Show: /leaderboard page
   Point out: Current week, new seed, standings
   Say: "Monday at midnight, new league starts!"
   ```

### 17:00 - League Preview (15 minutes)

**Weekly League Focus:**

**Show Leaderboard:**
```
Navigate to: https://pdoom1.com/leaderboard/
```

**Discuss:**
- "Let's check out this week's league..."
- Current week standings (if people have played)
- Top scores and interesting runs
- Upcoming week's competitive seed

**Competitive Preview:**
```
Say: "New league starts Monday at midnight AEST"
Show: Weekly league page
Discuss: What makes this seed interesting
```

**Call to Action:**
- "Download the game if you haven't yet"
- "Join the league on Monday"
- "Share your best runs in Discord"

### 17:15 - Q&A Session (15 minutes)

**Open Floor:**

**Good Questions to Prime:**
- "How does the deployment automation work?"
- "What's coming next week?"
- "When will X feature be added?"
- "How can I contribute?"

**Show Technical Details (if asked):**
- GitHub Actions workflow
- Deployment scripts
- Weekly league manager
- Integration with game

**Code Walkthrough (if viewers interested):**
- Open VS Code
- Show relevant scripts
- Explain architecture
- Demo locally if requested

**Community Engagement:**
- Thank contributors
- Shout out bug reporters
- Highlight community suggestions
- Ask for feedback

### 17:30 - Wrap Up (5 minutes)

**Summary:**
```
Recap:
[OK] v{VERSION} deployed successfully
[OK] {Key features} now live
[OK] New league starts Monday
[OK] Thanks for joining!
```

**Next Week:**
```
Say: "Same time next Friday - 16:30 AEST"
Preview: "Working on {upcoming features}"
```

**Final Calls to Action:**
1. "Try the new features this weekend"
2. "Join the Monday league"
3. "Report bugs in Discord"
4. "Follow on Twitter for updates"
5. "Star the repo on GitHub"

**End Stream:**
```
Say: "Thanks everyone! See you Monday for the new league, 
     and next Friday for another deployment!"
```

## Scene Suggestions for OBS

### Scene 1: "Intro"
- Webcam (if using)
- Starting soon screen
- Music playing
- Chat visible

### Scene 2: "Deployment Watch"
- Full screen: GitHub Actions
- Small overlay: Chat
- Small overlay: Webcam (optional)

### Scene 3: "Website Demo"
- Full screen: Browser (pdoom1.com)
- Small overlay: Chat
- Small overlay: Webcam

### Scene 4: "Code View"
- Full screen: VS Code or Terminal
- Small overlay: Chat
- Small overlay: Webcam

### Scene 5: "BRB"
- Be Right Back screen
- Music
- Chat visible

## Stream Tips

### Do's [OK]
- **Be authentic** - Show real deployment, including hiccups
- **Explain technical** - Some viewers want to learn
- **Engage chat** - Call out names, answer questions
- **Stay on schedule** - Viewers expect ~1 hour
- **Show passion** - Enthusiasm is contagious
- **Thank contributors** - Community matters

### Don'ts [X]
- **Don't panic on errors** - Great learning opportunity
- **Don't go off-topic** - Stay focused on deployment
- **Don't ignore chat** - Engagement is key
- **Don't rush** - Take time to explain
- **Don't forget calls to action** - Help grow the community
- **Don't stream over 90 min** - Respect viewers' time

## Technical Troubleshooting During Stream

### If Deployment Fails
1. **Stay calm:** "Looks like we hit an issue, let's investigate"
2. **Check logs:** Show GitHub Actions logs
3. **Diagnose:** Explain what you're seeing
4. **Decide:** 
   - Can fix quickly? Do it live
   - Need more time? Schedule follow-up
5. **Communicate:** "We'll get this sorted and deploy Monday"

### If Site Goes Down
1. **Acknowledge:** "The site appears to be having issues"
2. **Check:** DreamHost status, DNS, etc.
3. **Rollback:** If needed, do it on stream
4. **Explain:** What happened and how you're fixing it

### If Stream Lags
1. Lower bitrate in OBS
2. Close unnecessary browser tabs
3. Switch to simplified scenes
4. Announce: "Adjusting stream quality for stability"

## Post-Stream Tasks

- [ ] Export VOD for YouTube (optional)
- [ ] Clip highlights for Twitter
- [ ] Post summary in Discord
- [ ] Note viewer count and feedback
- [ ] Save any questions for next week
- [ ] Update stream metrics in deployment report

## Stream Metrics to Track

Track these after each stream:
- Peak concurrent viewers
- Average viewers
- Total unique viewers
- Chat messages count
- New followers
- Questions asked
- Bugs reported
- Feature requests

## Content Ideas for Future Streams

- **Special Episodes:**
  - Major version releases (longer stream)
  - Season changes (extended Q&A)
  - Community highlight stream
  - "Behind the scenes" development
  
- **Variety:**
  - Live coding sessions
  - Architecture deep-dives
  - Game balance discussions
  - Community game night

## Emergency Stream Setup

**Minimal Setup (if main setup fails):**
1. Phone camera + phone streaming app
2. Screen recording software (OBS alternative)
3. Just audio (podcast style) while sharing screen
4. Pre-record and upload VOD instead

**Don't skip stream just because setup isn't perfect!**

## Stream Assets Needed

Create these assets in advance:
- [ ] Starting soon screen (1920x1080)
- [ ] Be right back screen (1920x1080)
- [ ] Stream ended screen (1920x1080)
- [ ] Lower third with name/title
- [ ] Logo overlay
- [ ] Social media graphics
- [ ] Outro with links

## Example Stream Script

```
[16:30] OPEN
"Hey everyone! Welcome to the p(Doom)1 weekly deployment stream. 
I'm [Your Name] and we're deploying version 1.2.0 today with 
some exciting new balance changes."

[16:32] DEPLOYMENT STATUS
"Let's check on the deployment... looking at GitHub Actions here...
We can see it's in the 'Deploy to Production' stage. This is where
the files are being synced to DreamHost..."

[16:35] FIRST VERIFICATION
"Okay, looks like it's done! Let's visit pdoom1.com and verify...
There it is, version 1.2.0 in the footer. Let's click around and 
make sure everything works..."

[16:40] FEATURE SHOWCASE
"Now let me show you what's new. We've updated the balance for..."
[Continue through features]

[16:55] LEAGUE PREVIEW
"Let's check out the leaderboard for this week..."
[Show current standings and discuss]

[17:10] Q&A
"Now let's open it up for questions. What do you want to know?"
[Answer questions from chat]

[17:28] WRAP UP
"That's all for this week! Thanks so much for joining. New league
starts Monday at midnight, same deployment time next Friday. See
you then!"

[17:30] END STREAM
```

## Resources

**OBS Resources:**
- https://obsproject.com/
- r/obs for help
- OBS Discord community

**Streaming Tips:**
- Harris Heller's "Stream Tips" playlist
- Alpha Gaming YouTube channel
- Streamer communities on Discord

**Screen Recording (Backup):**
- OBS (same software, just record)
- ShareX (Windows)
- QuickTime (Mac)

---

**Remember:** The stream is about **community** and **transparency**. 
Show the real process, engage with viewers, and have fun! [GAME][DEPLOY]

Good luck with your first deployment stream! [STREAM]
