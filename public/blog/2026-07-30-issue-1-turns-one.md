---
title: "Issue #1 turns one"
date: "2026-07-30"
tags: ["anniversary", "milestone", "process", "dev-notes"]
summary: "The first issue ever filed on p(Doom)1 - 'Text overflows UI elements on several screens', 2025-07-30 - turns one. A year measured in the bug tracker rather than the trophy cabinet, ending with an audit of every promise the game's code makes."
commit: ""
---
# Issue #1 turns one

**Date**: 2026-07-30
**Tags**: [anniversary, milestone, process, dev-notes]

A year ago today — 2025-07-30, 12:09 UTC — the first issue was opened on the p(Doom)1 repository. In full:

> Text overflows UI elements on several screens

That is the founding document of a game about how civilisation might end. Not a design manifesto. Not a threat model. A label too long for its box.

Anniversaries invite a list of achievements. This one gets a different measure: what the bug tracker was about at the start, and what it turned out to be about all along.

## The sentence

On Monday, at an AI-safety coworking session, the game got its first introduction to an actual room of people. Reconstructed verbatim afterwards:

> Pdoom1 is a novel bureaucracy simulator that tries to back-trace how I get to my own personal pdoom answer and invokes time travel to make this semi-coherent.

Own read on the delivery: "surprisingly confident." Which is about the honest register a year in — still slightly surprised the thing can be said in one sentence at all.

## Issue #1, one abstraction layer down

Also on Monday, an audit ran across the game's own code hunting for one specific thing: places where the game tells the player something happened and nothing actually happens. Roughly 140 such promises were traced from message to delivery path. Findings:

- Every event message announcing a doom change fed a value the next tick overwrote. Announcements with nothing behind them.
- Six purchasable upgrades charged real in-game money for effects with zero implementing code.
- One action's "+political pressure" write was overwritten every tick *and* read by nothing anywhere. Doubly dead.
- Two core actions — publishing a paper, doing safety research — were reading balance keys that did not exist and silently falling back to `0.0`. A working UI over zero-priced no-ops.

That is issue #1 again, one layer down. Text overflowing its element is an interface failing to fit its own contents; you can see it, so somebody files it. A message announcing a doom change that reaches nothing is an interface failing to be *about* its contents. You cannot see that one at all. You find it by taking every promise the software makes and asking, one at a time, whether anything is on the other end.

A bureaucracy simulator whose internals were quietly full of unfired promises is either the worst possible outcome or extremely on-theme, and no ruling has been made on which.

## What this post is not

The fixes are on `main`. Whether they are in anything you can download depends on when you are reading this: at the time of writing, the newest tagged release was v0.13.1, and Monday's work rides the next version bump. The [releases page](https://github.com/PipFoweraker/pdoom1/releases) knows; a blog post written in advance does not. If your build predates the next tag, you are playing the code as it stood before the audit — which, given the subject of this post, at least has documentary value.

## Year two

Asked — laughing — whether there was any appetite for being interviewed about any of this:

> I'm going to try and deflect questions to lesswrong posts through the CoD death screen -- 'you died to an interpretability failure, allowing X model to escape containment, and it wasn't caught before it launched a pre-emptive HypnoDrone strike. ALL HAIL HYPNODRONE. go argue on this comment thread ->'

That feature does not exist. It is a parking-lot note, filed Monday between other parking-lot notes. It is quoted here because it is the most accurate available description of the register the game is aiming at: authority deflected to a comment thread, catastrophe with a brand name, and the interface still telling you exactly what killed you.

Year two opens with the tracker in roughly the condition year one opened in: full of things that do not fit. The difference is knowing which of them were lying. [Issue #1](https://github.com/PipFoweraker/pdoom1/issues/1) remains open to visitors, as does [the rest of the tracker](https://github.com/PipFoweraker/pdoom1/issues) — argue there, not here.
