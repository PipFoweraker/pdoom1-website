# Syndication — setting it up, and the three traps

**Rewritten 2026-08-24.** The previous version of this file never mentioned
`SYNDICATION_TOKEN` — the one value whose absence makes every endpoint refuse
with a 503 — and described workflow inputs ("enter path", a "dry run" checkbox)
that `syndicate-content.yml` does not have. Following it end to end produced a
401 with nothing here to explain it.

`scripts/check-syndication-docs.py` now derives the required set from the code
that reads it and fails if this document omits one, or files it on the wrong
side. **If the check disagrees with this page, the check is right.**

---

## 0. The shape, in one paragraph

Inbound is automatic, outbound is human-gated. Publishing a blog post triggers
the **prepare** half, which writes a draft into `content/syndication/<slug>.json`
with `"approved": false` and posts nothing. A person edits the copy, sets
`approved` to `true`, commits. Then someone dispatches the workflow with
`publish=true`, and the **publish** half posts exactly the text in the file. The
draft is a committed file, so git history is the audit trail.

---

## 1. Where each credential goes, and why the side matters

The functions run on **Netlify**. The workflow runs on **GitHub**. A value read
by a function must be in the Netlify site environment; a value sent by the
workflow must be a GitHub secret. `SYNDICATION_TOKEN` is read by the function
*and* sent by the workflow, so it is **the same string in both places**.

**Setting only the GitHub half yields a green workflow and a 401 from every
function.** `_auth.js` fails closed — unset means refuse, never allow — so a
half-finished setup is indistinguishable from a code bug unless you know this.

### Required for any posting at all

| variable | where | notes |
|---|---|---|
| `SYNDICATION_TOKEN` | **Netlify** site env | `_auth.js` compares the `x-syndication-token` header against it |
| `SYNDICATION_TOKEN` | **GitHub** secret | the workflow sends it. **Identical string to the Netlify one** |
| `NETLIFY_SITE_URL` | **GitHub** secret | base URL of the deployed functions, e.g. `https://pdoom1-website-app.netlify.app` |

Generate the token however you like — it is a shared secret, not a credential
for anything else. `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

### Bluesky

| variable | where | notes |
|---|---|---|
| `BLUESKY_HANDLE` | **Netlify** site env | e.g. `pdoom1.bsky.social` |
| `BLUESKY_APP_PASSWORD` | **Netlify** site env | Bluesky → Settings → App Passwords. **Not the account password** |

An app password is revocable on its own and cannot change the account's email or
password. There is no reason to use the real one.

### X / Twitter

| variable | where |
|---|---|
| `TWITTER_API_KEY` | **Netlify** site env |
| `TWITTER_API_SECRET` | **Netlify** site env |
| `TWITTER_ACCESS_TOKEN` | **Netlify** site env |
| `TWITTER_ACCESS_SECRET` | **Netlify** site env |
| `TWITTER_BEARER_TOKEN` | **Netlify** site env |

### LinkedIn

| variable | where | notes |
|---|---|---|
| `LINKEDIN_ACCESS_TOKEN` | **Netlify** site env | OAuth 2.0, scope `w_organization_social` |
| `LINKEDIN_ORG_ID` | **Netlify** site env | the organisation to post as |

### Discord

| variable | where |
|---|---|
| `DISCORD_WEBHOOK_URL` | **Netlify** site env |

---

## 2. Trap 1 — do not approve a four-platform draft with one credential

Every draft `prepare-syndication.py` writes lists **four** platforms —
`bluesky`, `x`, `linkedin`, `discord` — and the poster sends to all of them.
With only Bluesky configured, the other three return
`500 credentials not configured`.

Since 2026-08-24 that is survivable: success is recorded **per platform** in the
draft's `posted` ledger, written to disk immediately, so a re-run retries only
what failed. Before that change the whole-draft `posted_at` was written only if
every platform succeeded, so a partial run recorded nothing and **the next run
posted to Bluesky a second time**.

Two things still follow from this:

- **Trim `copy` to the platforms you have configured** before setting
  `approved: true`. Otherwise every run exits 1 on three permanent failures, and
  a red run that is expected is a red run nobody reads.
- **Before the first live run after 2026-08-24, look at each draft's `posted`
  ledger.** A draft part-posted under the old code has no ledger at all, which is
  byte-identical to one that never ran. The guard cannot tell them apart and will
  post again. `scripts/test-post-syndication.py` asserts exactly this limit
  rather than leaving it to be discovered.

## 3. Trap 2 — link facets are measured in bytes (fixed, kept tested)

`syndicate-bluesky.js` used to mark the link span with a JavaScript string
index. AT Protocol wants **UTF-8 byte offsets**. The two agree only while the
text before the URL is pure ASCII, which every auto-generated draft is — so the
defect was live and invisible. One em dash before the link shifts it by two
bytes, one emoji by three, and the post publishes with the link covering the
wrong span.

Fixed 2026-08-24, along with duplicate URLs collapsing onto one span and
sentence punctuation being swallowed into the href.
`scripts/test-syndication-facets.js` pins it by round trip: cut the claimed byte
range out of the encoded post, decode it, require the URL back. It also re-runs
the old algorithm and asserts it *fails*, so the suite cannot go green by
testing nothing.

**What this means for you:** you can write em dashes, curly quotes and emoji in
hand-edited copy. That was not safe before.

## 4. Trap 3 — this document

`scripts/check-syndication-docs.py` derives the credential list from
`netlify/functions/syndicate-*.js`, `_auth.js`, `scripts/post-syndication.py`
and the workflow, and fails if one is missing here or filed on the wrong side.
Add a platform handler and this page fails until it is documented.

---

## 5. Doing it

### First-time setup

1. **Netlify** → Site configuration → Environment variables. Add
   `SYNDICATION_TOKEN`, plus the credentials for each platform you actually want.
2. **GitHub** → Settings → Secrets and variables → Actions. Add
   `SYNDICATION_TOKEN` (same string) and `NETLIFY_SITE_URL`.
3. Redeploy the Netlify site — functions read the environment at deploy time.

### Posting

1. A published blog post triggers the draft automatically. Or run
   `python scripts/prepare-syndication.py --latest` locally.
2. Edit `content/syndication/<slug>.json`. **Delete the platforms you have not
   configured** (Trap 1). Set `"approved": true`. Commit.
3. Actions → **Content Syndication** → Run workflow, leaving `publish` **false**.
   That is a dry run: it prints what it would POST and sends nothing.
4. Read the dry run. Then run it again with `publish` **true**.
5. The workflow commits the `posted` ledger and `posted_at` back to the repo.

### Checking state without posting

```
python scripts/prepare-syndication.py --list
```

### The local suite

```
node   scripts/test-syndication-auth.js      # the gate is present and fails closed
node   scripts/test-syndication-facets.js    # link spans are byte offsets
python scripts/test-post-syndication.py      # a partial failure never re-posts
python scripts/check-syndication-docs.py     # this document is complete
```

All four run in `content-honesty.yml`.

---

## 6. What is NOT set up as of 2026-08-24

Measured with `gh secret list`: the repository holds `DH_HOST`, `DH_PATH`,
`DH_PORT`, `DH_SSH_KEY`, `DH_USER` and `PLAUSIBLE_API_KEY`. **`SYNDICATION_TOKEN`
and `NETLIFY_SITE_URL` are absent**, so the publish half would refuse before
sending anything (`post-syndication.py` exits 2 rather than posting).

The Netlify side cannot be read from a checkout. Treat `BLUESKY_HANDLE`,
`BLUESKY_APP_PASSWORD` and Netlify's `SYNDICATION_TOKEN` as **unknown, not
absent**, until someone looks in the Netlify UI.

## Full documentation

- `docs/SYNDICATION_ARCHITECTURE.md` — how the two halves fit together
- `docs/SYNDICATION_SETUP.md` — per-platform credential walkthroughs
- `.github/workflows/syndicate-content.yml` — the authority on what actually runs
