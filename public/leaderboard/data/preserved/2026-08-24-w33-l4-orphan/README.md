# `(weekly-2026-w33, L4)` — one score, archived by ruling

**Captured 2026-08-24 from `api.pdoom1.com/score_api.php`, unmodified.** One entry, scored
2026-08-14 on client v0.14.1, by Pip.

## Why this board exists at all

It is an **intermediate key**: the featured-seed constant rolled from `weekly-2026-w32` to
`weekly-2026-w33` on 2026-08-13 (pdoom1#1214) while the ladder was still **L4**. The L4→L5
fork did not land until v0.14.2 on 2026-08-21. So for eight days the shipped client posted
to a seed/epoch pair that no ceremony ever blessed and no page ever published.

Nothing was broken. The API accepted the score, stored it, and still returns it. What was
missing was a board on the site that could ever show it.

## The ruling

**Pip, 2026-08-24: this score goes to the anomaly archive.**

That places it with the 36 pre-epoch entries already preserved here — acknowledged history,
reported by `check-board-liveness.py` on **every** run so it stays visible, and never a CI
failure. It is not deleted, not re-stamped onto a live board, and not quietly dropped.

**Re-stamping it forward was never on the table.** Moving a score from the epoch it was
played under to a later one is the cross-epoch blend the ladder version exists to prevent —
L4 and L5 are different rule sets, and a score is only comparable to others set under the
same one.

## What archiving it mechanically does

`archived_keys()` in `scripts/check-board-liveness.py` reads capture **filenames** under
this directory, so the presence of `weekly-2026-w33__L4.json` is what registers the key as
known history. Before this, the probe classified it as `pending_publication` and the data
contract could not go green while it sat unresolved.

**The filename is the register.** Renaming this file un-archives the board.

## The honest part

This score is Pip's own, which is the only reason the ruling was cheap. The next one may not
be, and the precedent set here is: **an intermediate key produced by a constant moving
without a ceremony is archived where it was played, not migrated.** If that ever costs a
real player a place on a board, the fix is upstream — bless the seed before the constant
moves — not to start re-stamping history.
