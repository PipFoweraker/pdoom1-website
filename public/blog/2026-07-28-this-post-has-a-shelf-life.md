---
title: "This post has a shelf life"
date: "2026-07-28"
tags: ["process", "honesty", "dev-notes"]
summary: "This week's development cadence, reported as a dated decision (2026-07-27) rather than a forward promise - and where to check for yourself whether it held."
commit: ""
---
# This post has a shelf life

**Date**: 2026-07-28
**Tags**: [process, honesty, dev-notes]

Statements about what a developer is *going to do* decay in a specific and unhelpful way: the promise outlives the practice. The sentence sits on the page reading as present-tense long after it has stopped being true, and the reader has no way to date it. Nobody lies on purpose; the page just stops being checked.

So, a dated observation rather than a commitment.

**On Monday 2026-07-27, a cadence ruling was recorded** in the build-day log: keep adding mechanics and accept that balance breaks while they land — the log's own words are "game can break 10 times today" — patch daily through the week, hold speed until about Wednesday, then cleanup, hotpatch and playtest on Thursday, so Friday's commitments land.

That is what was decided, on that day. Everything after it is the future, and the future is not something a blog post gets to assert.

The falsification test is public. If the cadence held, the [commit history](https://github.com/PipFoweraker/pdoom1/commits/main) shows it; if it stopped on Tuesday, the commit history shows that instead, and this post will still say exactly what it says. The [changelog](https://github.com/PipFoweraker/pdoom1/blob/main/CHANGELOG.md) is the slower, tidier version of the same check.

More relevant if you actually play: as of this post's date, the newest tagged release is v0.13.1. Work merged this week is not in any build you can download until a new tag says it is.

If something breaks this week, it was priced in. If nothing gets patched, the links above will show that too.
