# pdoom1-website -- social prep, league night

**18:20** · Fri 2026-07-31 · memo `pdoom1-website/2026-07-31/1820`
**Status:** EXTRACTED BY CLAUDE from Pip's recorded playthrough, not re-read by him.

> ## PUBLISH WINDOW: 20:00-22:00 AEST TONIGHT. NOTHING BEFORE 20:00.
>
> Pip's ruling: *"Post after this dance before the next one, so 8 to 10pm window
> after we get some data."* The point of waiting is that the posts should carry
> **real board data**, not launch-day optimism. Draft now, hold, publish in that
> window.
>
> **#222 (DRAFT anniversary + patch-week posts) must not auto-publish.** Confirm
> the hold is mechanical, not just intended.

## Source

Pip played the shipped 0.13.2 build at 18:09 and narrated it. 2:46, one complete
arc: cold open -> scouting -> first hire -> fundraising spam -> reputation
collapse -> game over -> leaderboard submit at **rank 1**.

**The audio is not publishable raw -- he swears throughout.** Cut clips or
subtitle selectively; do not post the file.

## What the run PROVES, and can be said publicly

- **The ladder works end to end, verified by a human.** He read `weekly-2026-w31`
  and `Epoch L3` off the leaderboard and submitted a real score to it.
- **The full loop holds:** launch -> play -> die -> game over -> submit -> board.
  This is the transition that segfaulted in v0.11.0. It did not.
- **Difficulty is honest.** He predicted his own death at the start -- *"I'm
  gonna spam max fundraising, and then probably die at a reputation loss"* -- and
  that is exactly how the run ended.

## The arc, for a post or a clip reel

The story writes itself in four beats:

1. **Cluelessness.** *"You don't know anything yet. Go scouting."*
2. **The high.** First successful hire -- audible delight. *"I got someone."*
3. **The turn.** *"Oh, I cooked."* Then staff loss: *"Offboarding complete. Bye
   buddy."*
4. **The collapse.** Reputation hits zero, run over, exactly as predicted.

That is the game's pitch in 2:46: you will over-extend, and it will cost you the
thing you were protecting. Better than any feature list.

## Honest caveats -- do NOT claim

- **Do not claim bug reports reach us.** They do not. `bug_reporter.gd` only
  writes to the player's local disk; there is no submission endpoint (pdoom1
  #1057). If a post invites bug reports, it **must** say where the file is and
  where to send it, or it is making a promise the software does not keep.
- **Do not use the test-seed screenshots.** The `Test Prop` seeds visible in
  Pip's recording are local dev artifacts (pdoom1 #1066, traced to
  `user://leaderboards`). No player sees them; a screenshot showing them would
  misrepresent the build.
- **The in-game player guide still says "action points"** (pdoom1 #1073), a
  currency retired in #996. Do not screenshot the guide, and do not quote it.

## Download-page items, still open and player-facing tonight

- **#199** -- macOS "right click -> Open" instructions are dead on Sequoia 15.x
- **#200** -- the site says builds are "free and open source"; they are not

Both are on the page players hit from tonight's posts. **Higher priority than
the posts themselves** -- a correct post pointing at a wrong download page is
worse than no post.

## Suggested sequencing for the 20:00-22:00 window

1. Fix #199 and #200 first. The destination before the traffic.
2. Check the board has real entries beyond Pip's. **That is the data worth
   waiting for** -- a post saying "the board is live" reads differently with
   three names on it than with one.
3. Then publish, leading with the arc above rather than the version number.
