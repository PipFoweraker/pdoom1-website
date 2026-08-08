# L3 epoch close — `(weekly-2026-w31, L3)`

Captured 2026-08-08 from the live score API, read-only, **before** the site was
switched to publish the L4 board.

## What this is, and why it is not a loss

The six entries below are the whole of the **L3 league week** — the board that opened
Fri 2026-07-31 on seed `weekly-2026-w31` and ran until pdoom1 **v0.14.0 forked the
ladder L3 → L4 on 2026-08-07**. They are real player scores, played under L3's rules,
and they are now **closed history**: an L3 score and an L4 score were produced by
different rule sets, which is the entire reason the ladder epoch is half the board key.

**These are orphaned by the epoch cut, not by a mistake.** Nothing failed, nothing was
lost, and no player is affected. But `scripts/check-board-liveness.py` cannot tell
"closed by an epoch fork" from "lost by accident" — it can only tell "published" from
"not published". The moment `published-board.json` moves to `(weekly-2026-w32, L4)`,
this board becomes a populated board the site does not publish, i.e. a **NEW ORPHAN**,
and the liveness guard goes red hourly about a situation everyone already agreed on.

Placing the capture here is how the epoch close gets recorded in a form the tooling
reads: the archive is the **acknowledgement register**, and a board that appears here
is known history rather than a live incident. Same mechanism, and same reasoning, as
the `2026-08-01-gate4-proving-runs/` capture next door.

## The entries

| score | player | build | date (UTC) |
|---|---|---|---|
| 65 | AI Safety Lab | v0.13.2 | 2026-08-05T14:01:39 |
| 47 | Notkilleveryone Inc | v0.13.2 | 2026-07-31T18:11:23 |
| 44 | Division of Machine Learning | v0.13.2 | 2026-08-05T20:54:42 |
| 20 | Cognitive Systems Studies II | v0.13.2 | 2026-07-31T10:36:28 |
| 12 | AI Safety Lab | v0.13.2 | 2026-08-06T13:02:18 |
| 8 | Cognitive Systems Studies | v0.13.2 | 2026-07-31T10:35:08 |

Lab names are player-editable inputs pre-filled with a game-generated suggestion, so a
name here means "the player submitted it", not "the game produced it" — see the
correction note in `../2026-08-01-gate4-proving-runs/README.md`, which is the same
point and was got wrong once already.

All six are on build `v0.13.2`. A board legitimately spans builds; this one happened
not to, because no other build shipped inside the L3 week.

## Rules

**Never edit these files. Never re-stamp their version or seed.** They are a dated
observation of what the API held. Re-stamping them onto `L4` would assert that these
runs were played under rules that did not exist when they were played — the specific
lie the ladder split exists to prevent.

The board is still live on the API and will keep answering `GET ?seed=weekly-2026-w31
&version=L3`. Archiving here does not delete anything upstream; the website is a
read-only consumer (pdoom1 PR #679).

## Provenance

- Source: `GET https://api.pdoom1.com/score_api.php?seed=weekly-2026-w31&version=L3`
- Captured: 2026-08-08 (read-only GET; nothing was POSTed)
- Filename is the board key (`<seed>__<version>.json`), which is what
  `check-board-liveness.py` reads to build its acknowledgement register.
- Epoch fork authority: pdoom1 **v0.14.0** git tag message — *"Ladder L4. Featured seed
  weekly-2026-w32. Board key (weekly-2026-w32, L4)."* — and `release_manifest.json`
  `"ladder_version": "4"`.
- The successor board `(weekly-2026-w32, L4)` was **positively verified** at capture
  time: it held 9 entries from clients stamped `v0.14.0` and `v0.14.1`. That is a
  positive check, not an absence-of-error one — every wrong key also returns
  `ok:true` with an empty board.
