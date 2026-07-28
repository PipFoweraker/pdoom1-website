# Review index — `integration/2026-07-29-review`

A combined preview of **nine** branches merged on top of `origin/main` @ `73afa39b`,
so the whole site can be eyeballed in one pass before the PRs are approved
individually. **This branch is not a merge proposal.** Nothing here should be
merged to `main`; approve the underlying PRs.

Start the server:

```
python -m http.server 8080 --directory public
```

Then work down this file. It is ordered **highest-risk first**, not by site
structure. Stop the server with Ctrl-C when done.

**Two things localhost cannot show you**, because `python -m http.server`
ignores `.htaccess`:

- the `/changelog/` → `/game-changelog/` **301** (#183). Locally you get the
  fallback meta-refresh + JS redirect instead. Same destination, different
  mechanism.
- `AddType text/plain .md` (#184), which is what stops `/docs/roadmap.md`
  downloading instead of rendering. Locally `.md` links **will** download. That
  is expected here and is not a bug in the branch.

Not included: **`league/epoch-boundary` (#187)** was deliberately left out — a
parallel agent is reworking it against new rulings. Nothing below reflects it.

---

## 1. Highest risk — the nav split-brain

The nav work (#184) moved 21 hand-written pages onto the shared
`assets/js/navigation.js`. The homepage was **deliberately not converted**
(TECH_DEBT B1a: it needs a product call), so the front door now carries a
different nav from everything behind it. Check these two back to back.

| URL | PR | What visibly changed | What to look for |
|---|---|---|---|
| http://localhost:8080/ | #180 | Roadmap card + "View full roadmap →" now point at `/docs/roadmap/` instead of `/docs/roadmap.md`. Nav **unchanged**. | Open this and then any page in §2 and compare the header directly. The homepage nav has **Events** (~2,197 pages) which the shared nav lacks, and has **Press Kit commented out** which the shared nav shows. That divergence is now visible to a visitor moving between pages. This is the decision #184 is asking you for, not a defect. |
| http://localhost:8080/press/ | #184 | 60 lines of hand-written nav deleted, replaced by the injected shared nav + a `designer-credit` line ("Pip Foweraker's"). | The most link-dense conversion. Old nav: Home, Leaderboard, Blog, **Game Changelog**, Docs, Press. The shared nav carries all of those, but **"Game Changelog" is now labelled "Updates" and lives one level down, inside the Community ▾ dropdown**. The URL is intact; the wording and the depth are not. Decide whether that is acceptable for the press page specifically. |
| http://localhost:8080/bug-report/ | #184 | 73 lines of hand-written nav deleted — the largest single deletion. | **One link is genuinely gone with no replacement: "Contact" (`/#contact`).** The anchor still exists on the homepage; nothing in the shared nav points at it any more. Also: the old nav's "Stats" went to `/stats/`, the shared nav's "Stats" goes to `/game-stats/`. Both pages exist and both are titled "Game Statistics" — a pre-existing duplicate this change makes visible. |
| http://localhost:8080/privacy/ | #184 | 71 lines of hand-written nav deleted. | Old links (About, Blog, Leaderboard, Docs) all have shared-nav equivalents — verified. Watch instead for the **page's own tone**: this is the page that makes the analytics promise, and it now shows a nav it did not author. |

**Known wrinkle you should decide on** — the shared nav's **Roadmap** item still
points at `/docs/roadmap.md` (raw markdown), while #180 created a properly
rendered `/docs/roadmap/` page and moved every *in-page* link to it. On this
merged tree the nav and the page body disagree about where the roadmap lives.
`navigation.js` belongs to #184, the new page belongs to #180, so neither PR is
wrong on its own — it is a seam only visible once they are combined. Left
unfixed on purpose.

---

## 2. Nav conversions with little else going on

Same change on each: a `← Back to Home` link (or a small hand-copied nav)
replaced by the injected shared nav plus the `designer-credit` line. Sampling two
or three is probably enough; they share one mechanism.

| URL | PR | What visibly changed | What to look for |
|---|---|---|---|
| http://localhost:8080/frontier-labs/ | #184 | `← Back to Home` → full shared nav. | Does the injected header sit correctly above this page's own hero//layout, or does it collide with a top margin the old back-link did not need? |
| http://localhost:8080/resources/ | #184 | `← Back to Home` → full shared nav. | Same. Also this page is now linked *from* the nav ("AI Safety Resources" under Info ▾) — check the active/`aria-current` state highlights correctly. |
| http://localhost:8080/dev-notes/ | #184 | Back-link → shared nav. | This page carries `<meta name="robots" content="noindex">` and is meant to stay unlisted; confirm the nav does not make it look like a published section. |
| http://localhost:8080/website-changelog/ | #184 | Back-link → shared nav. | Three changelog-ish URLs now exist (`/website-changelog/`, `/game-changelog/`, `/changelog/`→redirect). Check this page says clearly which one it is. |
| http://localhost:8080/docs/ | #184, #180 | Shared nav, **and** two "Roadmap"/"Development Roadmap" links repointed to `/docs/roadmap/`. | Click both roadmap links — they should land on the rendered page, **not** download a `.md`. |

**Every one of these 21 pages renders no nav at all with JavaScript disabled**
(TECH_DEBT B1b, filed by #184 rather than fixed). `/design-notes/` shows the
intended fix. Worth knowing before you approve, not necessarily before you merge.

---

## 3. Changelog surface (#183)

| URL | PR | What visibly changed | What to look for |
|---|---|---|---|
| http://localhost:8080/game-changelog/ | #183 | The substantial rewrite: 358 lines. Now renders "Current release" and "Earlier releases" from release data, with "Downloads and files for this release on GitHub →" links and a "How this stays honest:" note. | The honesty path. Force the failure case if you can (it should say **"Failed to load changelog."** / **"No changes yet."** rather than showing a confident-looking empty panel — `scripts/test-changelog-render.js` asserts this, but read the wording yourself). Check the "pre-release" label appears only where it should. |
| http://localhost:8080/changelog/ | #183, #184 | Became a redirect stub — it bounces to `/game-changelog/`. #184 additionally added the shared-nav `<header>`. | You will almost certainly never see this page; it `location.replace()`s immediately. **But it has a real defect I chose to leave in rather than silently drop a hunk:** the stub's `body` is `display:flex; align-items:center; justify-content:center`, so the newly added `<header>` and the `<main>` become **side-by-side flex siblings**. Visible only with JS disabled. A one-line `flex-direction:column` fixes it; it belongs to whichever PR you approve second. |

---

## 4. New page (#180)

| URL | PR | What visibly changed | What to look for |
|---|---|---|---|
| http://localhost:8080/docs/roadmap/ | #180 | **Brand new page** — a rendered HTML roadmap replacing the raw `/docs/roadmap.md` as the link target. | This is the one page with no "before" to compare against, so read it as prose. `scripts/test-roadmap-render.js` asserts no future row claims to be committed — but the test cannot judge *tone*, and this is exactly the page where a projection can read as a promise. Also check it against `/docs/roadmap.md` (the source file is still there and still linked from the nav) for anything that drifted between the two. |

---

## 5. Correctness fixes you can verify by clicking (#185, #186)

| URL | PR | What visibly changed | What to look for |
|---|---|---|---|
| http://localhost:8080/leaderboard/ | #185 | Duplicate DOM id fixed: the view toggles are now `view-btn-table` / `view-btn-cards`, the containers keep theirs. | **Click "🃏 Cards", then click back to "Table View".** Previously `getElementById('cards-view')` returned the *button*, so cards rendered inside the button and `setViewMode('table')` hid the Cards toggle itself. Both toggles must survive a full round trip. |
| http://localhost:8080/dashboard/ | #185, #186 | The dev log now renders into its own `#devLog` below the Situation Analysis instead of replacing it. Cat image is now a 55 KB `.webp` (was a 3.78 MB PNG). | **The calibrated "Situation Analysis" prose must still be on screen after the page settles** — it used to flash and vanish. Also confirm the cat actually appears (the file changed format, not just size). |
| http://localhost:8080/monitoring/ | #185 | Added a 48-hour staleness cutoff on the integration-health snapshot. | This page previously showed a green "OK" forever if the snapshot froze. Check the stale note reads as *honest doubt*, not as an error — the snapshot is committed by a bot, and bot commits do not trigger deploys, so mild staleness is normal here. |

---

## 6. Blog drafts — proofread rendered, not as markdown

Both drafts render through `/blog/post.html`'s client-side parser. I checked
both against what that parser actually supports: headings, fenced code,
blockquotes, lists, `hr`, links, images, inline code, bold, italic — **but not
tables**. Neither draft uses a table, so both should render fully. (Note: the
"no headings / no fenced code" warning in `CLAUDE.md` is **stale** — the parser
on `main` handles them.)

| URL | PR | What visibly changed | What to look for |
|---|---|---|---|
| http://localhost:8080/blog/post.html?p=2026-07-30-issue-1-turns-one.md | blog | New post, "Issue #1 turns one". Three blockquotes (the issue title, the one-sentence pitch, the HypnoDrone note), a four-item list of audit findings. | **The date is 2026-07-30 — tomorrow.** It is already in `index.json`, `feed.xml` and `atom.xml`, and the feed generator reports it as the newest post. If this branch's content shipped today, a subscriber would receive a post dated in the future. That is a scheduling decision, not a bug — but it is the kind of thing this site's prime directive cares about. Also: the post asserts "roughly 140 such promises", "six purchasable upgrades", "two core actions" — those are checkable claims about the game repo, and you are the only one who can confirm them. |
| http://localhost:8080/blog/post.html?p=2026-07-28-this-post-has-a-shelf-life.md | blog | New post, "This post has a shelf life". Short, one heading, no lists. | Deliberately built as a dated observation rather than a promise — check that framing survived rendering intact, especially the "On Monday 2026-07-27, a cadence ruling was recorded" sentence, which is the whole point of the post. It names **v0.13.1** as the newest tagged release; confirm that is still true when it publishes, because that sentence is exactly the kind of literal that rots. |

Both posts also carry visible `**Date**:` / `**Tags**:` lines below the title.
That matches the existing house style (see `2026-07-15-ui-before-snapshot.md`),
so it is intentional duplication of the frontmatter, not a parser leak.

---

## 7. Event pages — **nothing to look at**

#182 changed **1,194** event pages. I verified programmatically that **every one
of those diffs is strictly inside `<head>`** — zero bytes changed below
`</head>` on any of the 1,194. There is no point opening them.

What changed there, for the record:

- `og:*` / `twitter:*` share-card tags added (they previously pasted as bare URLs).
- The analytics **consent shim** (`assets/js/analytics.js`) added above the
  deferred tracker, so a deep-linked visitor's Do-Not-Track preference is honoured
  before the pageview fires. This closes TECH_DEBT A3 (DNT was honoured on 4
  pages out of 2,226).
- A genuine content fix worth knowing about: **11 event pages had a multi-line
  `<meta name="description">`** leaking raw scraped text — author names,
  affiliations, even CSS (`padding: 1em;`, `.comment-info`) — straight into the
  head. Those are now collapsed and truncated to a single escaped line.

If you want to spot-check exactly one, the richest is
http://localhost:8080/events/openai_board_crisis_2023.html — and expect it to
look **identical** to production.

---

## 8. Non-visual, but worth a glance

| File | PR | Note |
|---|---|---|
| `public/robots.txt` | #181 | `/data/` and `/design/` are now **deliberately crawlable** — the homepage and `/state-of-doom/` fetch runtime JSON from them, and Googlebot obeys robots.txt for subresources, so disallowing them made the crawler render our hardcoded fallbacks. `/changelog/` is now crawlable too, so the 301 is reachable. The file explains all of this inline; read it, because the comments are the guard against someone re-adding the Disallow lines. |
| `public/sitemap.xml` | #181 (regenerated) | **2,250 URLs**, up from 15. I regenerated it after all nine merges — #181 built its copy against a base that predated `/docs/roadmap/`, the two blog posts and the changelog redirect. `/changelog/` is correctly absent (skipped as a meta-refresh redirect). |
| `public/.htaccess` | #183 + #184 | Carries **both** additive hunks: the `/changelog/` 301 and `AddType text/plain .md`. Neither can be verified on localhost. |
| `public/blog/feed.xml`, `atom.xml`, `index.json` | blog | Re-ran `generate-feeds.py` after merging; already in step, 16 posts. |

---

## Test results — `main` vs this branch

| Test | on `main` | on this branch | |
|---|---|---|---|
| `python scripts/test-design-notes.py` | PASS (26/26) | PASS (26/26) | — |
| `node scripts/test-analytics-optout.js` | PASS (17/17) | PASS (17/17) | — |
| `python scripts/test_ingest_scores.py` | **FAIL** | **PASS** | fixed by #185, as predicted |
| `python scripts/validate_data.py` | PASS (0 fail, 0 warn, 10 ok) | PASS (0 fail, 0 warn, 10 ok) | — |
| `python scripts/check-stale-facts.py` | FAIL (174 findings) | FAIL (174 findings) | unchanged — none of the nine PRs targeted it |
| `python scripts/check-platform-claims.py` | PASS | PASS | — |
| `node scripts/test-download-resolution.js` | PASS | PASS | — |
| `python scripts/snapshot-copy.py --check` | FAIL (16 pages drift) | FAIL (21 pages drift, +1 removed) | expected — the removed page is `public/includes/navigation.html`, deleted by #184; it was wired into zero pages |
| `python scripts/generate-feeds.py --check` | PASS (14 posts) | PASS (16 posts) | +2 blog drafts |
| `node scripts/test-header-consistency.js` | **FAIL 0/25**, 210 errors | **FAIL 16/26**, 25 errors | #184's improvement, close to the predicted ~15/25 |

New tests contributed by these branches, all passing on the merged tree:

```
node   scripts/test-changelog-render.js      PASS   (#183)
python scripts/test-changelog-structure.py   PASS   (#183)
node   scripts/test-roadmap-render.js        PASS   (#180)
python scripts/check-deploy-excludes.py      PASS   (#186) - 2,250 files scanned
python scripts/make-og-card.py --check       PASS   (#186) - 1200x630, 93,595 B
```

---

## Broken-reference sweep

I parsed all **2,248** HTML/CSS files under `public/` for local `src`/`href`/
`poster`/`url()` targets and checked each against disk, plus against
`deploy-excludes.txt`.

**Zero deployed page references a deploy-excluded file.** (Independently
confirmed by `check-deploy-excludes.py`.)

**One genuinely missing target, and it is pre-existing — not caused by any of
these nine PRs:**

- `public/assets/steam-badge-template.html` → `/assets/steam-coming-soon-badge.png`
  does not exist. Both the template and the missing image are already like that
  on `main`. The template is referenced by **zero** pages, so no visitor can
  reach it. Worth deleting or fixing at some point; not this branch's problem.

Three other hits were parser false positives, checked by hand and dismissed:
`test.webp` in `index.html` is inside a CSS `@supports not
(background-image: url('test.webp'))` feature query and is never fetched; `$2`
and `${issue.html_url}` are JS template/replacement strings, not URLs.
