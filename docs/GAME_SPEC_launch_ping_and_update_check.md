# Spec: one launch call that does two jobs

**For: `PipFoweraker/pdoom1`, in tonight's build if at all possible.**
Written 2026-07-22. Self-contained — hand this straight to the build.

## Why this is the one thing worth stopping for

Two problems, one HTTP call:

1. **You cannot count players.** The only game-to-server signal today is a score
   submission, which needs the player to finish a run AND not have opted out.
   `entry_uuid` is per-entry, so it cannot even dedupe people. v0.11.0 shows 135
   asset downloads on GitHub and there is no way to tell how many were humans
   rather than scanners — an install ID is the only thing that answers that.

2. **You cannot tell an existing player that a patch exists.** The game has
   `has_unseen_patch_notes()` in `godot/autoload/game_config.gd:368`, but it
   compares `last_seen_version != CURRENT_VERSION` — **both local**. That shows
   patch notes *after* someone updates; it cannot tell someone on v0.11.0 that
   v0.12.0 shipped. There is no remote version check anywhere in the Godot
   project.

Neither can be retrofitted onto builds already in players' hands. Every cohort
that downloads without this stays uncountable and unreachable **forever**. That
is the whole argument for the 36-hour window.

---

## The call

One request on launch. Fire-and-forget, async, never blocking startup.

### Request

```
POST https://analytics.pdoom1.com/api/event
Content-Type: application/json
User-Agent: <must be set to a real UA string; Plausible drops requests without one>

{
  "name": "Game Launch",
  "domain": "pdoom1.com",
  "url": "app://pdoom1/launch",
  "props": {
    "install_id":   "<uuid-v4>",
    "version":      "0.12.0",
    "os":           "Windows",
    "first_launch": true
  }
}
```

Verified live: the endpoint is up, `/api/health` reports Postgres and ClickHouse
both `ok`, and a test event returned `202`. **No new server code is needed.**

Plausible returns `202` for essentially anything, so a `202` means "accepted",
not "stored" — do not treat it as confirmation. Fire and forget; never retry in a
loop, never block on it.

### `install_id` rules

- UUIDv4, generated **once**, persisted to `user://`.
- **Never** derived from hardware, MAC, disk serial, username or anything else
  about the machine. A random UUID regenerated on reinstall is exactly right —
  it counts installs, which is what we want, and it is not a device fingerprint.
- Regenerating on reinstall is fine and expected. Do not try to make it survive.

### Consent

Gate it behind the existing privacy opt-out (the same one
`godot/autoload/leaderboard_sync.gd:85-91` already honours for score
submission). If the player has opted out, **do not send at all** — not an
anonymised version, nothing.

Reuse the async + durable-outbox pattern already proven in `leaderboard_sync.gd`.
Do not invent a second networking path.

---

## The update check (same launch, second job)

Read the current version from the website, which already publishes it:

```
GET https://pdoom1.com/data/version.json
```

```json
{ "latest_release": { "version": "v0.12.0", "published_at": "..." } }
```

That file is live now, auto-updated by a workflow, and served as static JSON off
DreamHost — no API, no auth, no rate limit worth worrying about.

Compare `latest_release.version` against the local `CURRENT_VERSION`. If the
remote is newer, show a non-blocking notice on the welcome screen:

> **v0.12.0 is available** — you're on v0.11.0. [Get it]

pointing at `https://github.com/PipFoweraker/pdoom1/releases/latest`.

### Rules that matter

- **Never block startup or gameplay on this.** If the request fails, times out,
  or the JSON is malformed, show nothing and carry on silently. An update check
  that can break launch is worse than no update check.
- **Compare semver numerically, not as strings.** `"0.9.0" > "0.11.0"` is true
  for string comparison and would tell every v0.11.0 player they are ahead.
  Parse to integer triples.
- Tolerate the `v` prefix being present or absent on either side.
- Do not auto-download or auto-update. Show a notice and a link; the player
  decides.
- Make it dismissible, and don't re-nag every launch for the same version.

Note this is a plain static-file read with no identifiers attached — it carries
no privacy cost and does not need to sit behind the analytics opt-out. Keep the
two concerns separate in the code even though they happen at the same moment.

---

## Order of value if time is short

1. **`install_id` + launch ping** — un-retrofittable, and the only way to know
   whether those 135 downloads were people.
2. **Update check** — un-retrofittable *for this cohort*: players who install
   v0.12.0 without it can't be told about v0.13.0 either. Every release you ship
   without it extends the problem.
3. Everything else in `GAME_REPO_ASKS_ALPHA.md` (the bug-report panel's false
   "we'll create a GitHub issue soon" message, the `F8`-vs-`N` mismatch, the
   `/contributors` 404) can wait for the fast-follow.

If only one lands tonight, make it #1.

---

## What the website side already does, so you don't duplicate it

- Publishes `/data/version.json` with `latest_release.version`. Live.
- Accepts the launch ping at `analytics.pdoom1.com/api/event`. Live, returns 202.
- Counts arrivals and download clicks via Plausible. **Pip must add a `Download`
  Goal and allow the custom properties in Plausible settings before links go out
  — property allow-listing is not retroactive.**
- `scripts/alpha-watch.py` reads both streams and will start reporting install
  counts as soon as the ping exists.

Nothing on the website blocks any of this.
