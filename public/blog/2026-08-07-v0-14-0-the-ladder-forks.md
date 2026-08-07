# v0.14.0: the ladder forks, and your old scores stay where they are

**2026-08-07**

v0.14.0 is out. It is a *forking* release, which is a thing this project now has
a word for, so the first section is about what that means for anything you have
already scored.

## The short version

The historical event deck was retimed so that one turn is one month, and the
ruled promotions landed with it. That changes which events fire on a given seed
— so a run on the same seed is no longer the same run. Scores earned before this
release and scores earned after it are not comparable, and the game does not
pretend otherwise.

So the ladder epoch moves from **L3 to L4**.

- **Your L3 entries stay valid and stay visible, under L3.** Nothing is deleted
  and nothing is re-stamped. They are a record of a game that had different
  rules, kept as that.
- **New runs land on L4**, on a new featured seed.
- **The two are never merged.** That is the entire reason the ladder epoch is
  half of a board's identity.

If you have been on the board this week, you have not lost anything. You have
finished a chapter.

## What the split is actually for

The board a score belongs to is keyed by the seed *and* the ladder epoch — not
by which build you were running. That distinction was introduced a couple of
releases ago and this is the first time it has really earned itself: v0.14.0
changes the rules, so it forks the ladder deliberately, while an ordinary patch
can ship any day of the week without disturbing a board mid-competition.

Before that split, a version bump could quietly fork a leaderboard and strand
everyone who had already played. That happened. It is the sort of thing you only
fix once you have watched it happen to real people's scores.

## The site is a step behind, and here is where

Being straight about this rather than letting you find it: pdoom1.com reads the
board key from published game artifacts, and this release changed the key a few
minutes after the site's last scheduled read. So for a window after publication,
the league page will still be showing the L3 board while the game is posting to
L4. That is being corrected, not ignored — and until it resolves, the board you
see on the site may not be the board your run went to.

Nothing is lost either way. Both boards exist; only the display is stale.

## What else is in it

The part of the release most likely to change your first ten minutes:

- **A one-time "claim a name" prompt before your first upload**, with a lab-name
  generator behind it. A public board of identical default names is a board
  nobody can find themselves on.
- **A failed leaderboard fetch is now visible.** It used to fail silently, which
  is indistinguishable from nobody playing. If it breaks, you will now be told.
- **The month review shows what changed**, and is reachable directly rather than
  buried.
- **Settings has been rebuilt** as a front card plus an operations board, and the
  keyboard and navigation now run off one table rather than several.
- **Music track selection from the pause menu**, and a credits screen you can
  actually reach.
- **The last player-facing "AP" is gone**, and number formatting is now consistent
  across the interface.

And a set of fixes that were embarrassing in the way that only shipped software
manages: the achievement toast rendered as a large purple rectangle, the office
cat was a magenta checkerboard in *every* build we shipped, the server rack
painted over the feed, and the public build wore a stale "DEV BUILD" banner it
had no right to.

The full changelog, derived from the release itself rather than retyped here,
lives on the [updates page](/game-changelog/).

## Where to get it

The [download page](/) resolves to the right build for your platform. It reads
what is actually attached to the release, so it cannot offer you something that
was never built.

---

*p(Doom)1 is free, open source and non-commercial. If something in this release
confused you, that is the most useful thing you can tell us — the bug tracker is
the front door.*
