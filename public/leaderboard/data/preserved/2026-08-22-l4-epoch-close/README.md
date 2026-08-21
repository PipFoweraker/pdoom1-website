# L4 epoch close -- `(weekly-2026-w32, L4)`

Captured 2026-08-22 from the live score API, read-only, **before** the site was
switched to publish the L5 board.

## What this is, and why it is not a loss

The eleven entries below are the whole of the **L4 epoch** -- the board that
opened with pdoom1 **v0.14.0** on 2026-08-07 and ran until **v0.14.2 forked the
ladder L4 -> L5 on 2026-08-21**. They are real player scores, played under L4's
rules, and they are now **closed history**: an L4 score and an L5 score were
produced by different rule sets, which is the entire reason the ladder epoch is
half the board key.

The fork was forced by two changes that alter what a score MEANS on a given
seed -- pdoom1 #1233 routed runtime event options through the doom streams,
closing a sink of up to -6 doom per turn, and #1230 added 28 events, changing
which events fire. Both are Section 3.1 BUMP triggers.

**These are orphaned by the epoch cut, not by a mistake.** Nothing failed,
nothing was lost, and no player is affected. But
`scripts/check-board-liveness.py` cannot tell "closed by an epoch fork" from
"lost by accident" -- it can only tell "published" from "not published". The
moment `published-board.json` moves to `(weekly-2026-w33, L5)`, this board
becomes a populated board the site does not publish, i.e. a **NEW ORPHAN**, and
the liveness guard goes red hourly about a situation everyone already agreed on.

Placing the capture here is how the epoch close gets recorded in a form the
tooling reads: the archive is the **acknowledgement register**, and a board that
appears here is known history rather than a live incident. Same mechanism, and
same reasoning, as `2026-08-08-l3-epoch-close/` next door.

## One thing worth noting about L4

**L4 ran for two weeks without a completed blessing.** Its ledger row was
written retrospectively on 2026-08-21, alongside L3's and L5's, closing a gap
that had run since L2 on 2026-07-25. The scores below were posted by real
players to a board key nobody had formally opened. They count -- the key was
correct and the client posted to it -- but the ceremony that was supposed to
declare it never happened until after it closed. See
`docs/LEAGUE_SEED_LEDGER.md`.

## The entries

| score | player | build | date (UTC) |
|---|---|---|---|
| 147 | GRIM (Global Risk Intervention Mechanism | v0.14.0 | 2026-08-07T23:21:45 |
| 147 | GRIM | v0.14.0 | 2026-08-07T23:32:07 |
| 147 | GRIM | v0.14.0 | 2026-08-07T23:35:37 |
| 87 | Kaur, Chen & Lindqvist | v0.14.1 | 2026-08-12T14:36:57 |
| 53 | gronklabs | v0.14.0 | 2026-08-08T00:25:27 |
| 44 | Kaur, Chen & Lindqvist | v0.14.1 | 2026-08-10T17:28:17 |
| 28 | gronklabs the better | v0.14.1 | 2026-08-08T02:16:21 |
| 21 | gronklabs | v0.14.0 | 2026-08-08T01:29:40 |
| 21 |  | v0.14.0 | 2026-08-08T00:05:43 |
| 21 |  | v0.14.0 | 2026-08-08T00:22:46 |
| 12 |  | v0.14.0 | 2026-08-07T23:31:10 |

Captured with a read-only `GET`; nothing was POSTed to obtain this. Verified
against a control in the same session: the same endpoint returned 0 entries for
`(weekly-2026-w33, L5)` and 11 here, so the API was answering truthfully rather
than returning `ok:true` to everything.

## Do not

- **Do not edit these entries.** The archive is immutable; it is the only
  surviving copy once the live board rotates.
- **Do not re-stamp them onto L5.** They were played under different rules.
  That merge is the specific lie the ladder split exists to prevent.
