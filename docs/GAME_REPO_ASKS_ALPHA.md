# Game-repo asks for the friends & family alpha

**Window: 36 hours from 2026-07-22 19:02 AEST (closes ~2026-07-24 07:00 AEST).**
**Fast-follow patch: +48h from now.**

Everything here needs a change in `PipFoweraker/pdoom1`. Website-side work is
tracked separately and does not block these.

The ordering principle: **item 1 cannot be retrofitted.** Builds that ship
without an install ID stay uncountable forever — no later patch recovers the
players who downloaded in between. Items 2-4 are cheap correctness fixes that
can slip to the fast-follow without permanent loss.

---

## 1. Anonymous install ID + launch ping — DO THIS ONE

**Why it can't wait:** the website can currently count *clicks on a GitHub
link*. It cannot count installs, launches, retention, or distinct players. The
only game-to-server signal that exists is a score submission
(`godot/autoload/leaderboard_sync.gd`), which requires the player to finish a
run AND not have opted out — a heavily filtered subset. `entry_uuid` is
per-entry, not per-install, so it cannot dedupe players even in principle.

Without this, "I went from 5 downloads to N players" is unanswerable for every
build shipped before it lands.

**Minimum viable shape:**

- A persistent anonymous `install_id` (UUIDv4), generated once into `user://`,
  never derived from hardware. Regenerating on reinstall is fine and expected.
- A one-shot, fire-and-forget launch ping carrying
  `{install_id, game_version, os, first_launch: bool}`.
- Behind the existing privacy opt-out. Must never block or delay startup.
- Reuse the async + durable-outbox pattern already proven in
  `godot/autoload/leaderboard_sync.gd` — do not invent a second one.

**Cheapest destination — needs no new server code.** POST to the Plausible
endpoint that is already live and already returns `202`:

```
POST https://analytics.pdoom1.com/api/event
Content-Type: application/json

{
  "name": "Game Launch",
  "domain": "pdoom1.com",
  "url": "app://pdoom1/launch",
  "props": {
    "install_id": "<uuid>",
    "version": "0.12.0",
    "os": "Windows",
    "first_launch": true
  }
}
```

Verified working: the endpoint is up, Postgres and ClickHouse both report `ok`
on `/api/health`, and a test event returned `202`.

**Optional but valuable if it's nearly free:** a `source` / `campaign` string
read from a file next to the executable or a CLI flag, so per-channel builds
(the link you DM a friend vs. the one you post publicly) can be told apart.

**Website side is ready** — no coordination needed beyond the payload shape.

---

## 2. The bug-report panel tells the player something untrue

`godot/.../bug_report_panel.gd:182` currently says:

> "Thank you! Your report has been saved. We'll create a GitHub issue soon."

No it doesn't. `bug_reporter.gd:124 save_report_locally()` writes JSON + PNG to
`user://bug_reports` and stops. There is **no `HTTPRequest` in
`bug_reporter.gd`**; `format_for_github()` at `:178` is dead code with zero call
sites. The harvesting tool `tools/process_bug_reports.py:54` looks for project
name `"pdoom1"` while `godot/project.godot:14` is `config/name="P(Doom)"`, so it
reads a directory that never exists — and it only ever reads the *local*
machine's folder, so it could never see a player's reports regardless.

Net effect: every bug report a friends-and-family tester files goes nowhere, and
they are told it worked.

**Smallest honest fix (~1-2h, no networking):**

1. Replace the message with the truth plus an action: *"Saved to `<path>`. Click
   below to file it on the website."*
2. Add a button calling `OS.shell_open("https://pdoom1.com/bug-report/")`, and
   put the report text on the clipboard via `DisplayServer.clipboard_set()` so
   the player only has to paste.

**Deliberately NOT recommended:** baking a live POST endpoint into the build. A
hardcoded URL you cannot change without a rebuild is exactly the failure mode
you don't want mid-alpha. `OS.shell_open` to a stable website URL keeps the
endpoint swappable server-side — the website form can be upgraded from
"prefilled GitHub link" to "real API" without another game build.

---

## 3. Wrong key advertised for the bug reporter

The code binds **N** (`main_ui.gd:466`, `keybind_manager.gd:43`). These say F8:

- `scenes/settings_menu.tscn:376-379` — `[F8]  Bug report`
- `bug_report_panel.gd:7`
- `docs/PRIVACY.md:44`
- `.github/ISSUE_TEMPLATE/bug_report.yml` — "Press F8 in-game"

`docs/PLAYERGUIDE.md:104,182` correctly says N. Pick one and make the other four
agree — testers who press F8 and get nothing will assume the feature is broken.

---

## 4. Two dead links shown inside the game

`bug_report_panel.gd:49-50`:

- `https://pdoom1.com/privacy` → 301s to `/privacy/`. Works, but fix the link.
- `https://pdoom1.com/contributors` → **404.** Either drop it or tell me and
  I'll publish the page website-side before the alpha.

---

## 5. `blank_issues_enabled: false` breaks the website's bug-report fallback

`.github/ISSUE_TEMPLATE/config.yml:1` sets `blank_issues_enabled: false`. The
website's bug-report form falls back to a **blank-issue** URL
(`/issues/new?title=...&body=...`). With blank issues disabled, GitHub redirects
to `/issues/new/choose` and — by widespread report — **drops the prefilled title
and body**, so the player retypes everything.

*Confidence ~75%; I could not confirm directly, anonymous requests redirect to
login.* [verify: log in and click the fallback link]

Two ways out, either is fine — **pick one and tell me which**:

- **Game repo:** set `blank_issues_enabled: true`.
- **Website (I'll do it):** switch the fallback to the template form,
  `?template=bug_report.yml&title=...`, which definitely survives. Issue Forms
  prefill by field `id`, so `description=` / `steps=` / `version=` map onto
  `bug_report.yml`'s ids.

I'd rather do it website-side — it's my bug to fix and it needs no game change.
Flagging it here only because the two repos have to agree.

---

## Not blocking, but decide before the ladder opens

**The score-API token ships in the public build.**
`godot/data/leaderboard_config.json` carries a shared token in a build anyone
can unzip; the file's own `_comment` acknowledges this. Accepted risk for a
friends-and-family alpha. Before any wider release: server-side rate limiting on
`score_api.php`, and a rotation plan.

**Board key is `(seed, game_version)`.** The website's weekly league data is
still stamped `v0.4.1` (161 of 163 version stamps under
`public/leaderboard/data/`). A v0.12.0 client's submissions cannot land on a
v0.4.1 board. **This is a website-side fix and I'll do it** — noted here so the
version you stamp on the game side and the one I stamp agree. You mentioned the
fast-follow will break the first ladder; that's the moment this matters.

**Design tokens.** Separately, the game has five partially-disagreeing colour
definitions and no `design/tokens.json`, which the website's sync workflow has
been looking for (and failing to find) since it was written. Not alpha-blocking
— details in the design-system notes.
