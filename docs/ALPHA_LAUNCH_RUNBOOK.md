# Alpha launch runbook — two streams, corroborating

Written 2026-07-22 for the friends & family baseline going out tonight.

**Goal:** see people arriving and downloading on the website, then see scores
appearing hours later on the leaderboard. Two independent systems telling the
same story is the evidence that it's working. No per-person tracking — that
would mean building surveillance we don't want, and it isn't needed.

| | stream A — website | stream B — leaderboard |
|---|---|---|
| says | people arrived and clicked download | people are actually playing |
| source | Plausible + GitHub asset counts | score submissions in the board JSON |
| bias | **overcounts** (double clicks, changed minds) | **undercounts** badly (must finish a run AND not opt out) |

Neither is trustworthy alone. The lag between them — downloads in the evening,
scores a few hours later — is the shape of real people installing and playing,
and it's hard to fake by accident.

Check both at once:

```
python scripts/alpha-watch.py
```

---

## Where you're starting from (not zero)

**v0.11.0 already has 135 asset downloads.** So you have a real baseline to
measure the alpha against, not a standing start.

Worth knowing: the release carries two competing Windows asset names —
`PDoom-Windows.zip` (54 downloads) and `PDoom-Windows-v0.11.0.zip` (6). Same for
macOS. If tonight's release keeps both, your download counts stay split across
two names. Pick one convention.

---

## Do these in order

### 1. Publish the release — NOT as a draft  *(blocks everything, 2 min)*

`api.github.com/.../releases/latest` **excludes drafts.** Until v0.12.0 is
*published with build assets attached*, the site keeps advertising v0.11.0 and
`resolveDownloads()` keeps the buttons on the releases page.

Nothing else here matters if this isn't done. `alpha-watch.py` will warn you
loudly if only drafts exist.

The buttons degrade safely (`public/index.html:1568`) — if the API fails or an
asset is missing, they keep a working `releases/latest` link. A partial release
is embarrassing, not broken.

### 2. Merge PR #145 — the download-tracking fix  *(5 min, highest technical value)*

Until this lands, **roughly half of all Download and Outbound-Link events go to
plausible.io — the cloud service, where pdoom1.com is not a registered site —
and are silently discarded.** `analytics.js` was injecting a second tracker, and
Plausible's script overwrites `window.plausible` on load, so whichever landed
last won.

Pageviews were never affected, which is exactly why this looked fine. Stream A's
download signal is unreliable until this merges. Merging auto-deploys in ~20s.

### 3. Configure Plausible — only you can do this  *(10 min, needs your login)*

At `https://analytics.pdoom1.com`:

- **Confirm a site named exactly `pdoom1.com` exists.** This is the one thing
  the audit could not verify from outside, and everything rests on it: Plausible
  returns `202` for events aimed at *any* domain and drops unregistered ones
  downstream. If it's missing, every pageview so far has been discarded. Check
  this first.
- **Settings → Goals →** add `Download`, `Outbound Link: Click`, `File Download`.
  Plausible only *shows* custom events that have a Goal defined — without this,
  download clicks arrive and stay invisible.
- **Settings → Custom Properties →** allow `source`, `campaign`, `version`,
  `platform`, `file`. Goals match retroactively; **property allow-listing does
  not**, so do this before the links go out.
- **Settings → API Keys →** create one, then `set PLAUSIBLE_API_KEY=...` and
  `alpha-watch.py` reports Stream A directly instead of telling you to go look.

Then load `https://pdoom1.com/?utm_source=selftest` in a normal browser and watch
Realtime. If it doesn't show, stop and fix that before sending anyone anything.

### 4. Verify Stream B can actually receive scores  *(the silent killer)*

If downloads climb and scores never appear, **suspect this before you suspect
analytics.**

The board key is `(seed, game_version)` per pdoom1 PR #679. A v0.12.0 client's
submissions cannot land on a v0.11.0 or v0.4.1 board — the player submits, sees
nothing, and gets no error. `alpha-watch.py` compares the board version against
the current release and shouts if they diverge.

Two known problems here:
- The **weekly league** data is stamped `v0.4.1` (being fixed on
  `feat/copy-baseline-and-truth-fixes` — verify before opening the ladder).
- **`api.pdoom1.com` resolves to the forum VPS with no valid TLS cert** — `curl`
  returns `000`. If submissions are meant to go there, they will fail outright.
  One DNS record plus certbot.

The main `leaderboard.json` is currently healthy: `data_status: pre-launch`,
board version v0.11.0, ingest pipeline validated.

### 5. Write down what you did, on the day  *(30 seconds, cannot be redone later)*

```
python scripts/alpha-watch.py annotate "DMed the first five" --channel direct
python scripts/alpha-watch.py annotate "posted to Bluesky" --channel bluesky --url <url>
```

Writes `public/data/analytics/annotations.json`. A spike is unexplainable a year
from now if nobody recorded what happened that day, and it **cannot be
reconstructed after the fact**. This is the cheapest high-value habit here.

If you want to tell channels apart, append `?utm_source=bluesky` (or `email`,
`signal`, …) to the link you post. Plausible groups by that automatically — no
per-person codes needed.

### 6. The game-side ask  *(only if the build isn't cut yet)*

An anonymous install ID plus a one-shot launch ping is the only item in
`GAME_REPO_ASKS_ALPHA.md` that **cannot be added later for the people who
download tonight**. It would close the gap between "clicked download" and
"actually ran it" — currently you only learn someone played if they submit a
score. Needs no new server code: `POST https://analytics.pdoom1.com/api/event`
already accepts it and returns `202`.

If the build is already cut, let it go and put it in the fast-follow.

### 7. Back up Plausible — this week, not tonight

There are **no backups**. Single VPS, no snapshots, no `pg_dump`, no ClickHouse
backup, nothing offsite. The multi-year history you want to animate later is one
incident from being permanently gone.

Cheap partial hedge you can automate: pull daily aggregates from the Stats API
(needs the key from step 3) and commit the JSON to `public/data/analytics/` — a
git-versioned second copy that survives losing the box.

---

## Reading it afterwards

Downloads climbing while the leaderboard stays empty means either nobody
finished a run yet (plausible in the first hours), or submissions are being
rejected — check step 4.

Scores appearing without a matching download bump means someone already had the
game, or Stream A's Download goal isn't configured (step 3).

Both moving together, with a few hours' lag, is the thing you're looking for.
