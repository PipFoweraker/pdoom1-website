# L4 epoch close — `(weekly-2026-w32, L4)`, 11 entries

**Captured 2026-08-24 from `api.pdoom1.com/score_api.php`, unmodified**, immediately before
the site moved publication to `(weekly-2026-w33, L5)` on Pip's `[Gate 6]` ruling.

Five players, 11 entries, all set under **L4** on client v0.14.0 / v0.14.1. This is the
board pdoom1.com published from 2026-08-07 until today.

## Why the capture had to happen before the publish, and not after

`derive_targets()` in `check-board-liveness.py` builds its probe set from what the repo
already knows: preserved capture **filenames**, `weekly/current.json`, `leaderboard.json`,
and `published-board.json`. `weekly-2026-w32` was reachable only because it sat in
`published-board.json`.

**The moment publication moved to w33, w32 would have dropped out of derivation entirely** —
and with its pin in `board-probe-targets.json` also removed, the probe would simply have
stopped asking about a board holding eleven real player scores. Not deleted; invisible,
which for a guard is the same thing.

So the order is load-bearing: **capture, then unpin, then publish.** Doing it in any other
order silently narrows what the probe can see.

## What this is not

It is **not** an anomaly archive entry. These scores are not anomalous — they are an epoch's
complete and correct history, closed because v0.14.2 forked the ladder L4 → L5, not because
anything went wrong. `archived_keys()` reads filenames here and will now report this key as
known history, which is the intended effect; the distinction between "closed epoch" and
"anomaly" lives in this README and in the ledger, not in the mechanism.

The scores do not migrate to L5. L4 and L5 are different rule sets and a score is only
comparable to others set under the same one — which is the entire reason the ladder version
is half the board key.

## Two data defects preserved as-found

The capture is byte-faithful, including two upstream problems that were live at close:

- **One entry has an empty `player_name`.**
- **One reads `GRIM (Global Risk Intervention Mechanism`** — truncated mid-word at 40 bytes,
  with the closing bracket eaten.

Both are the server-side truncation defect the game side is fixing (pdoom1#1272 — a
byte-versus-codepoint cut, plus an ordering bug where truncation happens before the encode
success check, so one bad name can empty a whole board). **They are not repaired here.** A
capture is a record of what the API served; correcting it would make this file a claim about
what should have happened rather than evidence of what did.
