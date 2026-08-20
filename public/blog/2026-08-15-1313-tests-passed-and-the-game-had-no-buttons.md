---
title: "1,313 tests passed and the game had no buttons"
date: "2026-08-15"
tags: ["playtest", "testing", "process", "dev-notes"]
summary: "On Thursday a first-time player sat down, the game drew its art and a doom percentage, and offered nothing to click. 1,313 tests were green. The cause is a per-checkout cache that CI can never see go stale, because CI always starts clean. The guard shipped Friday afternoon; the identical failure shape was back within hours - and this time it was caught."
commit: ""
---
# 1,313 tests passed and the game had no buttons

**2026-08-15**

On Thursday evening a friend sat down in front of p(Doom)1 for a playtest —
a first-time player, at the machine, with me narrating over their shoulder.

The game launched. It drew the background art, including the cat. The doom
readout said 58.5%. The research-quality selector worked — rushed, standard,
thorough, all clickable. And that was the whole game. No action icons. No
upgrades. No music. No way to commit a month. The phase label said *starting
up* and never said anything else.

No crash. No dialog. No red text anywhere. From my own narration on the
capture, as it happened:

> "all my icons have disappeared. And all my upgrades have disappeared, and I
> can't commit the month, and the music track seems not to be working, and
> also, there's no active game, so I don't think the game's actually
> initialized"

It looked exactly like a game that had not finished loading. Anyone would
wait. We waited. That is the trap: enough of the screen survives that the
screen stays plausible.

Meanwhile, 1,313 tests were passing.

## What broke

Godot resolves every `class_name` through a cache file that is generated,
gitignored, and belongs to one checkout. A refactor earlier in the week added
a new class, `Capacity`. The agent that wrote it worked in a separate
worktree, which built its own fresh cache and saw all 1,313 tests pass —
honestly. The shared checkout only *pulled*, so its cache predated the new
file, and every script that referenced `Capacity` failed to compile,
cascading through the autoloads that build the UI and start the game.
Reconstructing that exact cache afterwards on a scratch copy: 30 parse
errors, 17 dependent-script failures. The windowed run swallowed all of it;
the errors only surfaced in a headless run.

The fix is one command and takes seconds. Diagnosis took the evening. The
full symptom record is
[pdoom1#1215](https://github.com/PipFoweraker/pdoom1/issues/1215).

## The interesting part is not the bug

The interesting part is that CI structurally cannot catch it. CI clones fresh
every run, so it always generates a correct cache. Only a long-lived working
copy can hold a stale one. This is a whole class of failure that is invisible
to every check that starts clean — and most checks start clean. Green CI here
was not lying; it was answering a question nobody was asking.

So the guard that came out of this
([pdoom1#1216](https://github.com/PipFoweraker/pdoom1/pull/1216)) does not
live in CI. It lives on the launch path: a ~30ms check, before the game
starts, that every declared class actually resolves in *this* checkout's
cache, with the repair built in. The only job CI has is proving the detector
itself still detects — there is a test that reconstructs Thursday's exact
cache and asserts the check goes red on it.

## The sting in the tail

The guard merged on Friday at 16:53.

At 18:22 the same day — about ninety minutes later — a different piece of
work merged
([pdoom1#1222](https://github.com/PipFoweraker/pdoom1/pull/1222)), written in
its own worktree, tests green. It adds a new class: `class_name Refusal`. The
identical shape.

Dated observation, per house rules: on Saturday morning I ran the guard on
the shared checkout and it said

```
STALE CLASS CACHE -- this checkout will run the WRONG code, silently.
    MISSING   Refusal    res://scripts/core/refusal.gd
```

exit code 1. The failure that cost Thursday's playtest came back within
hours of the guard shipping, and this time it costs one command before the
next launch instead of an evening. I do not think I have ever had a guard
pay for itself faster.

## The rest of the week, briefly

**The board moved.** The public leaderboard shows the same lab name at 44 on
Monday and 87 on Wednesday — and in between, fixes landed on the first five
minutes of play (a legible first screen, and rejections that actually reach
the player instead of a hidden feed). Honest caveats: a lab name is typed,
not an identity, so this is not established to be the same person, and it is
not a controlled comparison. It is evidence of headroom, and I will take it.
Monday's 44 has a distinction the number does not show: a run submitted by
someone who is not me, accepted by the live board — the first external
evidence the whole pipeline works end to end, which is worth more than any
check I can run against my own API.

**Every refusal in the game got audited.** 144 distinct player-facing refusal
strings, each traced to the code behind it: 106 are real rules, correctly
stated. 29 refuse because the feature is unbuilt, 8 give a reason that is not
the actual reason, and 1 could not be determined from the code at all. The
game is mostly honest, and now the dishonest ones are being marked: a stub
must say it is a stub, because a stub that refuses in the voice of a rule
teaches the player a rule that does not exist.

**Playing the game found an exploit.** Nine leftover doom literals in the
runtime event options, measured at −6 doom per turn at the shipped event cap
— enough to drive doom from 50 to the 0.0 floor in about eight turns and pin
it there. In a game whose whole premise is that there is no victory
condition, only buying time, that is not a balance issue, it is a thesis
issue. Measured and written up in
[pdoom1#1232](https://github.com/PipFoweraker/pdoom1/issues/1232); the fix is
in review.

**Nine PRs merged on Friday** across the game and this site, including
everything above that says "merged".

None of this is me telling you the game is good. It is me telling you the
alpha is honest about being one — including about the evening it shipped
1,313 passing tests and no buttons.

---

*p(Doom)1 is free, source-available and non-commercial. If something in the
game confuses you, that is the most useful thing you can tell us — the bug
tracker is the front door.*
