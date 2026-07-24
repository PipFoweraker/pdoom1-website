# L2 ladder-epoch cutover — runbook

Executable steps for moving the league from the L1 epoch (`(seed, v0.12.0)`
weekly board) to the L2 epoch, per issue #151. Written on launch day
(2026-07-24) so the cutover is a checklist, not a scramble at 3pm.

**Board key (from the shipped v0.13 client — pdoom1 #151, gate-green):**
`(weekly-2026-w30, L2)` → `board_weekly-2026-w30__L2.json`
**Legacy L1 board file:** `board_weekly-2026-w0__L1.json`

> The seed is `weekly-2026-w30`, NOT the earlier website-side proposal
> `league_2026-07_7d6ced29` — see the correction note in
> `docs/LEAGUE_SEED_LEDGER.md`. The client POSTs to `weekly-2026-w30`; the board
> must match it or scores vanish silently.

---

## Status of each step

| # | step | side | state |
|---|---|---|---|
| 1 | Preserve L1 board as legacy | VPS (Pip) | **ready** — command below |
| 2 | Confirm score API accepts `(weekly-2026-w30, L2)` | VPS/API | **ready** — key now known; check below |
| 3 | Point website display at the L2 board | website | **contingent on #735** — does v0.13 submit remotely |
| 4 | Verify | website | **ready** — checks below |

The values that were blocked are now known (client is built). Step 3 remains
contingent only on whether v0.13 actually submits scores remotely (issue #735) —
if it does not, there is nothing to display yet and the honest pre-launch banner
is correct as-is.

---

## Step 1 — preserve the L1 board (VPS, run as Pip)

The live v0.12.0 board holds tonight's real friends-and-family tester scores.
Copy it to the legacy key BEFORE any v0.13 client posts, so those scores survive
as "legacy epoch L1". This runs on DreamCompute, not from this repo:

```bash
ssh -i ~/.ssh/pdoom-website-instance.pem ubuntu@208.113.200.215
# on the VPS, in the score API DATA_DIR (confirm the path):
cp -n board_weekly-2026-w0__v0.12.0.json board_weekly-2026-w0__L1.json
ls -la board_weekly-2026-w0__*.json    # confirm both exist, same size
```

`-n` (no-clobber) so re-running never overwrites the legacy copy. The original
keeps its seed string so the provenance of those scores stays legible.

## Step 2 — confirm the API accepts `(weekly-2026-w30, L2)`

The board key is client-supplied and the store is flat-file, so it should
auto-create on first POST — but confirm no version allowlist rejects the new
`L2` epoch form (the game flagged this against #149). Read of the (empty) new
board is the cheap check:

```bash
# fill <API_BASE>:
curl -s "<API_BASE>/board?seed=weekly-2026-w30&ladder=L2" -o /dev/null -w "%{http_code}\n"
# 200 (empty board) or a clean 404-that-will-autocreate = OK; a 4xx rejecting
# the key = a version allowlist to widen for L<n> before the cutover.
```

## Step 3 — point the website display at L2  [contingent on #735]

How the L2 board reaches the site depends on the answer to #735:

- **If v0.13 submits scores remotely:** the site must ingest the L2 board. Today
  `scripts/ingest_scores.py` aggregates local seed files into
  `public/leaderboard/data/leaderboard.json` and stamps `meta.game_version` from
  `public/data/version.json`, self-healing `data_status` to `"live"` once real
  deployed-version scores appear. Wiring the L2 remote board into that ingest is
  the work; it is **not built yet** (see `docs/GAME_UPLIFT_PLAN.md`).
- **If v0.13 does NOT yet submit remotely:** nothing to point at. The leaderboard
  stays on the honest pre-launch banner shipped in PR #155 (no scores recorded
  yet), which is correct and needs no change. Leave the board out of the launch
  posts.

Either way the site is already honest; this step only adds real data when there
is real data. **Do not stand up a second score store** (pdoom1 #679: the website
is a read-only consumer of the one PHP score API).

## Step 4 — verify

```bash
# the shipped seed is referenced in the release notes (sanity anchor):
grep -o "weekly-2026-w30" public/data/version.json    # 1 hit

# leaderboard page is honest right now (pre-launch banner, empty toolbar hidden):
curl -s https://pdoom1.com/leaderboard/ | grep -c "No scores recorded yet"   # >=1

# if/when a live board publishes, validate it before trusting it:
python scripts/validate_data.py
```

---

## Straggler note (from #151)

Old v0.12.0 clients keep posting to the L1 board after the copy. Pip is fine
treating them as legacy — they stay on L1; the v0.13 build posts to L2. No action
needed unless a cleaner cutover is wanted.
