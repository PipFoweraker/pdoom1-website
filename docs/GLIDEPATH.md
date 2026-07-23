# Glidepath — from here to a proud Friday go-live

Living plan. Folds in game issue #151 (the v0.13 ladder-epoch cut), the open-issue
triage, and the launch questions. Written 2026-07-23 (Thu evening); target **Fri
2026-07-24, build deployed ≤3pm AEST, announce ~4pm**.

The organising idea you asked for: treat a release like a data pipeline — a
**patch-to-serve** flow with stages and time budgets, where bigger builds buy more
scan time.

---

## 1. The patch-to-serve pipeline (the stage gates)

```
  PATCH ──▶ SCAN ──▶ PUBLISH ──▶ RESOLVE ──▶ SERVE ──▶ OBSERVE
 (build)  (QA/AV/   (GitHub    (site auto-  (live)   (analytics +
          size)     release)   points)               downloads)
```

| stage | who | what "green" means | time budget (Fri) |
|---|---|---|---|
| **Patch** | game | v0.13 build cut, versioned | — |
| **Scan** | game | QA pass + size/AV sanity; **scaled to build size** (below) | build-size dependent |
| **Publish** | game / you | GitHub release, **non-draft**, clean asset names, upload done | **by ~3:00pm** (upload buffer) |
| **Resolve** | website (auto) | `releases/latest` → buttons point at v0.13; version display updates | ~5 min after publish |
| **Serve** | website | site merged, leaderboard on the L2 board, smoke-tests pass | **by ~3:45pm** |
| **Observe** | you | Plausible + GitHub download counts + snapshot-to-git | ongoing |
| **Announce** | you | LinkedIn post once Serve is verified | **~4:00pm** |

**Scan-time-by-size heuristic** (your "larger builds need more thorough scans"):
- **< 50 MB** — quick QA + launch smoke. ~15 min.
- **50–150 MB** (v0.12 was ~90 MB, v0.13 likely similar/larger) — full QA pass + AV
  scan of the zip + confirm it launches clean on a fresh machine. ~30–45 min.
- **> 150 MB** — the above + a second reviewer / deeper AV, because a big binary is
  a bigger trust ask and a slower upload. ~1 hr+.

**Logging it (the data-lake-lite bit):** we can record, per release, `version`,
`build_size`, and timestamps for patch → publish → serve, into a committed
`public/data/releases/log.json`, and render a simple HTML timeline of
"time-from-patch-to-serve." **Doable in a session — but not Friday-critical.**
Roadmapped as issue-worthy unless you want the minimal version now.

---

## 2. Friday critical path (the must-dos)

Only three things genuinely gate a proud 4pm, and one is external:

1. **[GAME] Publish v0.13 non-draft with assets, by ~3pm.** Everything downstream
   waits on this. Buttons degrade to the releases page until then.
2. **[WEBSITE] The #151 ladder-epoch cutover.** Board key moves `(seed,v0.12)` →
   `(new-seed, L2)`. Website must:
   - point the leaderboard/featured display at the **L2** board,
   - optionally show **L1** as "legacy",
   - and the L1 board file gets preserved (`cp` on the VPS DATA_DIR — game/VPS side).
   **Blocked on Pip's follow-up comment** with the exact board-key strings + seed
   (coming later tonight / tomorrow AM). **Prep now:** parameterise the board key so
   plugging in the real values is a one-line change, not a scramble.
3. **[YOU] Plausible `Download` goal** (2 min) so the day's downloads are visible.

Everything else below is *not* Friday-blocking.

---

## 3. Open-issue triage (37 open)

### Friday-relevant
| # | verdict |
|---|---|
| **#151** v0.13 epoch cut | **CRITICAL.** Website: L2 display + L1 legacy. Prep the board-key parameter now; wire exact values when Pip posts them. |
| **#147** downloads → current build | **Largely auto.** `releases/latest` points at newest non-draft, so publishing v0.13 handles it. To-do: confirm no page hardcodes v0.11/v0.12, and the game deletes/marks the crashing v0.11 ghost. |
| **#149** data-contract fail | **Stale/green now.** `validate_data.py` = 0 fail locally; the FAIL was the version-drift already fixed. Rolling issue self-updates next run. |
| **#139** version single-source | **Partly done** (dangerous fallbacks fixed). Remaining hardcodes are low-risk; finish post-launch. |

### Soon (this week — quality for the audience, not blocking)
- **#141** player-facing changelog/release-notes page — nice to have for a launch.
- **#80** 90-sec clip + curated screenshots — ties to the *fresher-assets* gap (§6).
- **#16** proper 1200×630 OG image — I shipped a 235 KB same-shape card; the true
  landscape card is the finish.
- **#126 / #133** leaderboard handoff validation — largely superseded by #151's
  cleaner epoch model.
- **#85** public metrics page — the private growth dashboard exists; public version
  reads the git snapshots when you want it.

### Later (roadmap — post-launch)
- **Grant-readiness cluster** (#78 donor, #79 press kit, #81 roadmap, #82 safety,
  #83 team, #84 budget, #86 testimonials, #87 cadence) — content-heavy, your voice.
- **#17** Steam CTA (when store live), **#14** Search Console/Bing (quick SEO win),
  **#36** v1.1.0 docs, **#144** social auto-post (syndication is built + gated;
  needs Bluesky creds + the facet fix), **#68** security review.

### Close candidates (done / superseded / vapourware)
- **#61** DreamHost log extraction → **superseded** by the git-snapshot pipeline.
- **#64/#65/#67** API integration → **superseded** by pdoom1 #679 (read-only model).
- **#66** pdoom-data prod DB → later, and reframed by #679.
- **#6** press kit → **dup of #79** (press page exists).
- **#52** TOR/i2P hosting → vapourware, no code. **#59** origin/master → trivial.
- **#70** Airtable CRM → the workflow is neutered; no Airtable base exists.
- **Forum #60/#63/#71** → deprioritised; GitHub Discussions for now.

Recommend closing the six "close candidates" with notes to cut the open count
~37 → ~31 and stop them implying unfinished work. (Your call — I can do it.)

---

## 4. Cost & bandwidth — will a success blow you out?

**No. Comfortably no.** The three surfaces:

- **The game download is hosted by GitHub Releases, not you.** 40 downloads of a
  ~90 MB build = ~3.6 GB — **all on GitHub's dime**, free, effectively uncapped at
  this scale. Mac/Linux builds add more GitHub-hosted bytes; **still not your cost.**
  Bigger builds don't hurt your wallet — they only cost *you* a one-time upload.
- **The website is on DreamHost shared hosting** — tiny pages, now gzipped +
  cached. A LinkedIn trickle (tens–hundreds) is nothing; even a real spike is fine
  for static files. DreamHost shared is "unlimited" (fair-use); you're nowhere near.
- **Netlify ($9/mo you noticed):** production is **DreamHost, not Netlify** — Netlify
  only serves PR deploy-previews (which only you/reviewers hit). **A traffic success
  cannot blow out Netlify**, because public traffic never touches it. You could very
  likely **drop to Netlify's free tier** — previews work on free. Worth checking your
  Netlify billing; the $9 may be buying nothing you use.

**Upload time (your real cost):** ~90 MB × (Win + Mac + Linux) ≈ 270 MB one-time to
GitHub. At a typical home upload of 10–50 Mbps that's ~1–4 min per platform, call it
**10–20 min total** with overhead. **Plan 30 min** to be safe → hence "publish by
3pm for a 4pm announce."

---

## 5. Go-live mechanism, monitoring & fail-modes

**Go-live sequence (the checklist):**
1. Game: upload + **publish** v0.13 (non-draft).
2. `python scripts/alpha-watch.py` → confirms the release is non-draft and shows
   asset download counts. (It *warns* if only a draft exists.)
3. Merge any pending website PRs → auto-deploys in ~20s.
4. Wire the #151 L2 board values; verify the leaderboard shows the new epoch.
5. **Smoke-test** downloads (click each button → correct v0.13 asset) + feedback
   (submit one test report → lands in team@) — see §7.
6. Only then: post to LinkedIn.

**What we can see from simple HTML today:**
- `/monitoring/` — health-check status (now honest about staleness).
- The private growth dashboard artifact — traffic + downloads.
- `alpha-watch.py` (CLI) — the two-stream launch view (site + leaderboard).
- Gap: there's no single "launch status board." A small `/status` HTML reading
  the snapshot + health JSON is a good, cheap build if you want one glance. Roadmap.

**Fail-silent vs fail-noisy (honest inventory):**
| system | on failure | on success |
|---|---|---|
| Deploy (push→DreamHost) | **noisy** (Actions failure email) | silent (just deploys) |
| Analytics snapshot | **noisy** (Actions failure) | silent (commits daily — by design) |
| Weekly-league rollover | **noisy** (opens a GitHub issue) | silent |
| Data-contract validation | **noisy** (rolling issue #149) | silent |
| **Feedback (PHP mail)** | **fail-graceful for the user** (falls back to GitHub) but **fail-SILENT for you** — if `mail()` quietly fails, you won't know a report was lost | user sees "sent" |
| Download resolve | silent both ways (buttons keep a working baseline) | silent |

**The one gap worth noting:** the feedback path is silent-to-you on a mail
failure. Mitigation for launch: the smoke-test (§7) proves it works on the day; a
belt-and-braces later would be a copy-to-a-log or a Discord ping on receipt.

---

## 6. Fresher assets — the honest answer to "do we have the right banners?"

**No — the site is a version behind on art.** The game now has newer banner/hero
art the website doesn't use:
- `godot/assets/icons/decorative_headers/ui_header_banner_1024.png`
- `art_source/pixellab_2026-07-16/09-V9-heroic-fullcolor_*.png` (heroic hero art)
- `art_generated/scene_art_wave2/v1/*` (28 event scenes) — these feed the *event
  pages*, but the **homepage hero** still uses older gameplay **screenshots**
  (`assets/screenshots/hero-bg-*`, `gameplay-office-*`).

So: the amber palette now matches the game; the **hero imagery does not**. Uplifting
it needs your art-direction call (which banner, how it's framed) + processing the
source art to web sizes. **~1–2 hrs once you point at the assets.** Not
Friday-blocking, but it's the biggest "looks current" lever after the palette, and
it pairs with #80 (curated screenshots). Hand me the chosen art and I'll wire it.

---

## 7. Feedback smoke-test (step by step)

After the feedback PR is live (it's merged now) and deployed:
1. Open **`https://pdoom1.com/bug-report/`**.
2. Fill Title + Description (put "smoke test — ignore" so you know it's you).
   Optionally add your email in the new optional field.
3. Click **Submit**. Expected: the button flips to "**[OK] Report Submitted!**"
   (green success) — that means the PHP path emailed team@ successfully.
4. Check the **team@pdoom1.com** inbox — a plain-text mail titled
   "p(Doom)1 bug: smoke test — ignore" should arrive within a minute.
5. **If instead** it opens a GitHub issue tab ("Continue on GitHub →"), the PHP
   path failed and fell back — tell me and I'll check the DreamHost mail/PHP.
6. Bonus: submit a second one immediately → you should get a "please wait a moment"
   (the 30s throttle working).

---

## 8. Growth goals — a realistic frame

The 2014 long-form-essay playbook still works, but the distribution changed. For a
small, volunteer, non-commercial game project, honest targets:

- **Minimal / healthy (very achievable):** a *general upward trend* — from ~2–3
  visitors/day to a steady 10–30/day as you deepen and cross-link the static pages,
  with occasional post-driven spikes. **This is the right goal**, and it's the one
  you named. Depth + internal links = SEO compounding; it's slow and durable.
- **Substantial (needs a hit):** a reviewer, a HN/Reddit front page, or a Bluesky/LI
  post that catches — hundreds-to-thousands in a day, then settling to a new, higher
  baseline. Un-plannable; you prepare for it (the spike premortem) and capture it.

**What social pushing yields, roughly:** LinkedIn art-a-day is a *slow-compounding
brand* play — most posts do little, a few land, and it keeps you top-of-mind with a
professional network (good for grants/hiring, weak for raw traffic). A single well-
placed post in the *right* community (an AI-safety forum, a gamedev subreddit) can
out-traffic a month of LinkedIn. The honest model: **consistency builds the floor;
the right single placement raises the ceiling.** Your instinct — deepen the pages,
lateral-link, trend upward — is exactly right, and the analytics now *prove* the
effort lands. Post the art; watch the floor rise.

---

## Immediate next actions
- **You:** add the Plausible `Download` goal; check the Netlify $9; post #151's exact
  board keys when ready.
- **Me (on your word):** prep the parameterised L2 board key; close the six stale
  issues; build the release-log/status page or the fresher-hero uplift when you point
  me at the art.
