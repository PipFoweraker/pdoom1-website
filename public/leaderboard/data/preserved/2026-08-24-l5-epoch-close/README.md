# L5 epoch close — `(weekly-2026-w33, L5)`, zero entries

**Captured 2026-08-24 from `api.pdoom1.com/score_api.php`, unmodified, immediately before
publication moved to `(weekly-2026-w35, L6)`.**

**Nobody ever scored on it.** That is the whole record and it is worth writing down rather
than letting the absence speak, because an empty capture and a missing capture look identical
six months from now.

## Why an empty board still gets archived

`derive_targets()` in `check-board-liveness.py` builds its probe set from preserved capture
**filenames**, `weekly/current.json`, `leaderboard.json` and `published-board.json`. This key
was reachable only because it sat in `published-board.json` — and publishing L6 evicts it.

Without this file the probe simply stops asking about `(weekly-2026-w33, L5)`. It holds no
scores today, so nothing would be lost today; but a board the probe cannot see is a board
that can acquire a late submission nobody ever notices. **Capture, then unpin, then publish**
is the order, and it is the same order that protected eleven real scores when L4 closed
earlier the same day.

## Why it is empty, which is the interesting part

L5 was blessed at `[Gate 5]` on 2026-08-21 and `[Gate 6]` was **HELD** that night because
`api.pdoom1.com` was unreachable. The board did not open until 2026-08-24 ~14:40 AEST.

**It was open for roughly five hours.** v0.14.3 published at 04:37Z the same day carrying
`ladder_version: 6` / `league_seed: weekly-2026-w35`, which forked the key again 34 minutes
after the L5 board was first published. So L5 existed as a published board for one afternoon,
on a client that had already been superseded, and no run ever reached it.

That is not a failure of the board. It is what a three-day hold followed by a same-day fork
produces, and it is recorded here rather than smoothed over.

## What did not happen

No score was migrated, re-stamped or reassigned. **L5 and L6 are different rule sets and a
score is only comparable to others set under the same one** — which is the entire reason the
ladder version is half the board key. An empty board stays empty.
