# Feedback intake contract

Status: **DRAFT — awaiting Pip's mark.** Written 2026-08-15.

Binding directive (Pip, 2026-08-15): *"If I ever lose a message silently, that's
now the worst thing my website can do and it would be better the entire website
doesn't exist."*

Every mechanism below is derived from that one sentence. Where a tradeoff exists,
it resolves toward **duplicate over loss**, and toward **admitting a failure over
absorbing it**.

This document is the single source that Wave 1 agents build against. Test authors
work from this file and **must not read the implementation**.

---

## 0. Invariant

> **INV-1 — No success state is ever shown to a visitor without a durable write
> having completed.**

Every test in §6 exists to attack INV-1. Nothing in this system may be green
while INV-1 is unproven.

Corollaries, each of which is separately testable:

| id | corollary |
|---|---|
| INV-1a | `mail()` returning true is **not** a durable write. Mail is a derived notification. |
| INV-1b | A client-side queue entry is removed **only** on a `200` carrying a matching `rid`. |
| INV-1c | The store may never live where `rsync --delete` can reach it. |
| INV-1d | When the store is unwritable the endpoint returns 5xx. It never degrades to mail-only. |
| INV-1e | Duplicates are acceptable. Rejecting a write to prevent a duplicate is not. |

---

## 1. Receipt ID

Generated **client-side, before the network call**. This is what makes loss
measurable rather than merely unlikely: it is the join key across client outbox,
server store, and mail notification.

```
rid      = UUIDv4            (crypto.randomUUID(); 128 bit)
receipt  = "F-" + base32(first 30 bits of rid), uppercase, 6 chars
```

- `rid` is stored and transmitted. `receipt` is what the visitor sees.
- `receipt` is display-only and **may collide**; never key on it.
- The client generates `rid` before the first send attempt and reuses it across
  every retry. That is what makes retries idempotent.

---

## 2. Wire format

### Request — `POST /ingest.php`, `Content-Type: application/json`

```jsonc
{
  "rid":        "uuid-v4",        // required
  "kind":       "thumb|comment|bug|feature|question|feedback",  // required, allowlist
  "page":       "/blog/post.html?p=x",  // required, origin-relative, <=512
  "value":      1,                 // thumb only: 1 | -1
  "text":       "free text",       // <=5000, optional for thumb
  "contact":    "free text",       // <=200, optional, MAY be an email
  "credit":     "free text",       // <=80,  optional
  "client_ts":  1755230000,        // client clock, advisory only
  "elapsed_ms": 8400,              // time-on-form, for the bot signal
  "hp":         "",                // honeypot; non-empty FLAGS, never drops
  "attempt":    1                  // retry counter, advisory
}
```

Unknown keys are **dropped, not rejected** — a newer client must not fail against
an older server.

### Response

| code | body | `retryable` | client action |
|---|---|---|---|
| 200 | `{ok:true, rid, receipt, stored_at}` | — | remove from outbox, show receipt |
| 400 | `{ok:false, error, retryable:false}` | no | **keep in outbox**, surface to user |
| 413 | `{ok:false, error, retryable:false}` | no | keep, surface, offer GitHub fallback |
| 429 | `{ok:false, error, retryable:true, retry_after}` | yes | keep, back off |
| 507 | `{ok:false, error, retryable:true}` | yes | keep, back off, **alarms us** |
| 5xx | `{ok:false, error, retryable:true}` | yes | keep, back off |

`retryable` is explicit in the payload so the client never infers it from the
status code. A body that omits `retryable` is treated as `true`.

**A `400` does not authorise dropping the message.** Malformed-by-our-own-parser
is our bug, not the visitor's, and their words are still in the outbox.

---

## 3. Storage

### Location

```
<store_root>/YYYY-MM.jsonl        # append-only, monthly rotation
<store_root>/.probe               # writability canary, checked per request
```

`store_root` MUST resolve **above the deployed docroot**.

- **Why:** `rsync --delete` from `public/` runs ~4x/day (INV-1c), and the payload
  carries reporter PII, which under `public/` is publicly fetchable. Either
  reason alone is sufficient.
- Resolution order: `PDOOM_FEEDBACK_STORE` env → `dirname(docroot)/feedback-store`.
- If `store_root` resolves to a path **inside** the docroot, the endpoint refuses
  to start and returns 507. It never "helpfully" falls back.

> **UNVERIFIED — needs Pip or an SSH check.** The DreamHost shared-hosting home
> layout (whether `dirname(docroot)` is writable by the PHP user) has not been
> confirmed from this session. Wave 1 must verify before merge; if it is not
> writable, this is the one decision that changes.

### Record

```jsonc
{
  "rid": "...", "receipt": "F-XXXXXX",
  "kind": "...", "page": "...", "value": 1,
  "text": "...", "contact": "...", "credit": "...",
  "flags": ["honeypot", "too-fast"],   // tags, never a reason to drop
  "server_ts": 1755230001,
  "client_ts": 1755230000,
  "ip_hash": "sha256(ip + daily_salt)",  // never the raw IP
  "ua": "...",
  "schema": 1
}
```

### Append discipline

```php
$line = json_encode($rec, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES) . "\n";
$fh = fopen($path, 'ab');
flock($fh, LOCK_EX);          // two simultaneous POSTs on shared hosting is not hypothetical
fwrite($fh, $line);
fflush($fh);
fsync($fh);                   // durability, not just visibility
flock($fh, LOCK_UN);
fclose($fh);
// ONLY NOW may a 200 be composed.
```

### Deduplication

**Dedup happens at READ time, never at write time** (INV-1e). The writer never
consults an index and never rejects a `rid` it has seen. Rationale: an index
lookup is a new failure mode standing between a visitor and a durable write, and
its failure mode is *dropping a real message* to prevent a cheap duplicate.

Readers collapse on `rid`, keeping the earliest `server_ts`.

---

## 4. Client state machine

```
composing ──submit──> queued ──> sending ──200(rid match)──> acked
                        ^            │
                        └─────────────┘  any other outcome
```

| state | localStorage | what the visitor is told |
|---|---|---|
| `queued` | written **before** fetch | "Saved on this device. Sending…" |
| `sending` | present | "Sending…" |
| `acked` | **removed** | "Saved as F-XXXXXX" |
| `retrying` | present | "Not sent yet — saved on this device, will retry." |

Rules:

1. The outbox entry is written **before** the first `fetch`, never after.
2. An entry leaves the outbox **only** on `200` with a matching `rid` (INV-1b).
3. `retrying` MUST NOT render any success affordance — no checkmark, no green,
   no "thanks". This is the exact failure `bug-submit.php` shipped and TECH_DEBT
   C5 half-fixed.
4. Replay runs on `DOMContentLoaded` and on `online`. Backoff: 0s, 5s, 30s, 5m,
   then once per page load.
5. **Outbox capacity is a loss channel.** On quota exhaustion the widget refuses
   the *new* submission with an explicit message and offers the GitHub/mail
   fallback. It never evicts an older entry to make room.
6. If the endpoint is unreachable entirely, the fallback is a prefilled GitHub
   issue — offered **after** telling the truth about what happened, never instead
   of it.

---

## 5. Mail auth

Mail is a **notification derived from a completed write**, never the record.

### Records to publish (DreamHost panel → Manage Domains → DNS)

```
TXT  @        v=spf1 include:_spf.google.com include:netblocks.dreamhost.com ~all
TXT  _dmarc   v=DMARC1; p=none; rua=mailto:team@pdoom1.com
TXT  google._domainkey   <generated in Google Admin, not the DreamHost panel>
```

Measured 2026-08-15 against `ns1.dreamhost.com` (authoritative): **none of the
three exist.** MX is `SMTP.GOOGLE.com`. Two senders must be covered — Google
Workspace, and DreamHost shared `173.236.253.218`, which falls inside
`netblocks.dreamhost.com`'s `ip4:173.236.128.0/17`.

### The interlock

`scripts/check-mail-auth.py` asserts, and **fails the build** on:

| check | condition |
|---|---|
| M1 | SPF record exists and is syntactically one record |
| M2 | SPF covers both sending IPs |
| M3 | DMARC exists |
| M4 | DKIM selector `google._domainkey` resolves |
| M5 | **`p` > `none` ONLY IF every PHP mailer passes an aligned envelope sender** |

M5 is the load-bearing one: it reads the PHP source for `mail()`'s 5th parameter
and **refuses a DMARC tightening** while any mailer would fail alignment.
`bug-submit.php:178` currently passes no 5th param, so today M5 pins the policy at
`p=none`. Without this interlock, raising the policy silently kills the intake
form — the precise outcome the binding directive forbids.

Delete `bug-submit.php:22`'s comment `// same domain -> passes SPF on DreamHost`.
It is false: SPF authorises sending IPs, not matching domain names, and with no
record published the result is `none`, never `pass`.

---

## 6. Failure taxonomy — every row is a test

Fault is **injected**, not simulated by assertion. Each test observes the failure
happening. Repo rule: a guard seen only in its passing state has not been shown
to work.

| # | fault injected | expected observable | asserts |
|---|---|---|---|
| F1 | store dir unwritable (chmod 000) | 507, `retryable:true`, **no mail sent**, outbox retains | INV-1, INV-1d |
| F2 | disk full mid-append | 507, no partial line in store | INV-1 |
| F3 | fatal after write, before response | client retries same `rid`; read-time dedup collapses | INV-1e |
| F4 | two concurrent POSTs | both lines intact, neither interleaved | §3 |
| F5 | `mail()` returns false | **200 still returned** (write succeeded), failure recorded | INV-1a |
| F6 | MTA accepts then discards | store still authoritative; reconciler flags divergence | INV-1a |
| F7 | POST never leaves client | entry stays `queued`, no success UI, replays next load | INV-1b |
| F8 | response lost after server write | retry with same `rid`, no double-count | §1 |
| F9 | throttle trip | 429 `retryable:true`, outbox retains, honest message | §4.3 |
| F10 | honeypot filled | record **stored and flagged**, never dropped | INV-1e |
| F11 | malformed JSON | 400 `retryable:false`, outbox **retains**, user told | §2 |
| F12 | payload over cap | 413, user told which field, text preserved locally | §2 |
| F13 | `rsync --delete` dry-run over docroot | store path **not** in the deletion set | INV-1c |
| F14 | store_root resolves inside docroot | endpoint refuses, 507 | §3 |
| F15 | UTF-8 free text, `PYTHONIOENCODING=cp1252` | round-trips byte-identical | encoding lesson |
| F16 | localStorage quota exhausted | new submission **refused explicitly**, nothing evicted | §4.5 |
| F17 | `<script>`/quote payload in every field | escaped at every sink; no attribute break | escaping rule |

Test files (Wave 1, agent A3, written before implementation exists):

```
scripts/test-ingest-destructive.py     # F1-F6, F9-F15
scripts/test-feedback-outbox.js        # F7, F8, F16
scripts/test-mail-auth-interlock.py    # M5 forced red
```

**Gate 2:** these run against a stub and are observed **RED** before A1/A2 write
a line. A test that has never failed has not been shown to be a test.

---

## 7. Honesty coupling

`public/privacy/index.html` currently promises we collect no *"names, emails, IP
addresses or cross-session identifiers"* (`:578`) and claims GDPR/CCPA/PECR are
satisfied *"by collecting no personal data"* (`:547`).

This system collects a free-text contact field that may be an email, a credit
name, and a salted IP hash. **The privacy page must move in the same PR as the
widget** — not the next one. Shipping the widget first makes the site lie on the
exact axis the prime directive protects.

`python scripts/snapshot-copy.py --check` will flag the prose change. That is the
mechanism working, not an obstacle.

### 7.1 The coupling is BIDIRECTIONAL — found 2026-08-16 by agent B1

This section originally said only that the privacy page must not lag the widget.
**The corollary was never written down: it must not LEAD it either.**

B1 rewrote the page to be true of a system that does not yet run, and in doing so
created a fresh falsehood pointing the other way — the page now says *"Some pages
carry a feedback widget"* when `grep -rln "feedback.js" public/ --include=*.html`
returns nothing, and describes 90/180/30-day clocks that only
`scripts/purge-feedback.py` makes real, which no workflow schedules. Both verified
independently, 2026-08-16.

A promise about a mechanism that does not run is the same class of lie as a
mechanism that runs unpromised. "We delete your contact details after 90 days" is
**false** until something deletes them, and it is more damaging than silence
because a visitor may hand over an address on the strength of it.

> **RULE: reader-facing prose and the mechanism it describes ship in the SAME
> deploy, in BOTH directions.** Neither may lead. The prose is a claim about the
> present tense, and `auto-deploy-on-push.yml` fires ~4x/day gated on nothing, so
> "it will be true by the time anyone reads it" is not available as a defence.

**Merge preconditions for the privacy prose** — all three, or the corresponding
sentences come back out:

1. at least one page mounts the widget;
2. `purge-feedback.py` is on a schedule, or the 90/180/30 sentences are removed;
3. `generate-feedback-stats.py` output is published, or the public-tally
   paragraph is removed.

This is the same failure the repo already records for `game-changes.json` —
someone migrated one consumer, verified that one page, and generalised. Here the
generalisation ran ahead of the code instead of behind it. **Same defect, mirrored.**

---

## 8. Decisions — SETTLED 2026-08-15 (Pip)

| # | decision | ruling |
|---|---|---|
| D-1 | comment visibility | **Private to Pip.** Acknowledge on send. Public **aggregate counters** on the main site. |
| D-2 | store | **JSONL on DreamHost as the record**, scheduled reconcile into GitHub |
| D-3 | notification | **digest for thumbs, per-item for prose** |
| D-4 | retention | **per-field clocks, §10** |

---

## 9. Public aggregate counter (D-1)

Pip's shape: *"220 comments / 13 death threats with bad grammar / 3 injection
attacks"*.

Derived artifact, never a second store. Cron job reads the private JSONL, writes
`public/data/feedback-stats.json` — **counts only**. Direct precedent:
`events-sync-summary.json` publishes counts precisely because naming the items
would republish what was redacted.

```jsonc
{
  "generated": "2026-08-15T00:00:00Z",
  "window": "all-time",
  "counts": { "comment": 220, "thumb_up": 1904, "thumb_down": 311,
              "abusive": 13, "injection_attempt": 3 },
  "untriaged": 47,
  "suppressed_categories": 2,
  "schema": 1
}
```

### Hazard 9a — a public classification is a public claim about a person

`abusive` is a **judgment about a real human's words**, displayed publicly. An
automated classifier will be wrong, and being wrong here means publicly
mislabelling someone's earnest angry feedback as a death threat. That is a lie to
a visitor, aimed at the visitor who tried hardest to talk to us.

> **Mechanism:** the public counter counts **human-confirmed tags only.**
> Untriaged records are counted as `untriaged`, never guessed at. No regex ever
> writes a category that reaches the public file.

### Hazard 9b — small counts re-identify

A category at count 1, on a specific page, is legible to the person who submitted
it and inferable by others.

> **Mechanism:** k-anonymity threshold `k=5`. Any category below `k` is withheld
> and folded into `suppressed_categories: N`. Never rounded, never zeroed —
> withheld and *declared as withheld*, because a silently-dropped category is the
> same lie in a smaller font.

### Property 9c — `untriaged` is a self-imposed accountability clock

Publishing the untriaged backlog attacks the **received-and-never-read** failure
mode, which is silent loss wearing a different hat and the one the binding
directive does not yet name. If Pip stops reading, the number climbs in public.
This is a feature and must not be quietly capped or hidden when it gets
embarrassing.

---

## 10. Retention (D-4)

**Retention is per-field, not per-record**, because the fields have different
purposes and therefore different clocks. Stating one number for the whole record
would over-retain the PII and under-retain the product.

| field | purpose | clock | rationale |
|---|---|---|---|
| `text`, `page`, `kind`, `value`, timestamps | the product | **indefinite** | a bug report is useful until fixed; design feedback for years; and a genuine threat is *evidence* |
| `contact` | replying to this person | **90 days** from last reply | long enough for real back-and-forth; short enough that a breach exposes little |
| `credit` | the person asked to be named | **indefinite** | publication is the consented purpose |
| `ua` | reproducing a bug | **180 days** | useless once the build has moved on |
| `ip_hash` | throttle / abuse only | **daily salt rotation**, row dropped at 30d | rotation makes it unlinkable after 24h without deleting anything |

### The erasure path — and the receipt's third job

The visitor holds `F-XXXXXX`. We store no identity, so **the receipt is the only
key by which a person can ask us to erase them.** It already earns its place twice
(idempotency §1, loss measurement §1); this is the third.

```
visitor mails team@ with F-XXXXXX
  -> python scripts/purge-feedback.py --receipt F-XXXXXX
  -> row rewritten with text/contact/credit/ua nulled, tombstone kept
  -> tombstone preserves rid + timestamps so counts stay honest
```

A tombstone rather than a deletion, so the aggregate counter cannot silently
disagree with history.

### The mechanism that makes retention real

> **A retention policy without a cron job is prose.**

`scripts/purge-feedback.py`, scheduled, rewrites the JSONL with expired fields
nulled and **reports what it purged as counts**. `--check` mode fails CI if any
field is retained past its clock. Forced-failure test: plant an over-age
`contact`, assert the check goes red, assert the purge nulls exactly that field
and touches nothing else.

Privacy-page wording this obliges us to (B1's input, must be true when published):

> *Free-text feedback is kept indefinitely. Anything you type into the contact
> field is deleted within 90 days. We never store your IP address — only a hash
> that is re-salted daily.*

---

## 11. Adjudications (2026-08-16, after A3's Gate 2 run)

A3 wrote the suite from §1–§10 and hit nine under-specifications. These are the
rulings. They are binding on A1/A2.

### 11.1 Mail observability seam — ACCEPTED

`PDOOM_MAIL_SINK` (path; endpoint appends one JSON line per notification,
`{rid, ok, ...}`, instead of calling `mail()`) and `PDOOM_MAIL_FAIL=1` (forces
`ok:false`). Test-only, inert when unset. **A1 must honour both**, or F1/F5 are
untestable — which is not the same as passing.

Positive control required: a happy-path submission must produce a sink line, or
F1/F5 report *unobservable-FAIL* rather than passing on an absence. This is the
`count_emails()` trap from CLAUDE.md — a check that reports what it matched will
happily print success on a run where nothing happened.

### 11.2 Client API — ACCEPTED

```js
createFeedbackClient({storage, fetch, uuid, now, render, endpoint})
  -> {submit, replay, outbox}
```

CommonJS-exported like `escape.js`. `render(html)` receives the exact string the
widget would assign to `innerHTML` — that is F17's sink. Outbox key
`pdoom_feedback_outbox`. **A2 must export this or an adapter.**

### 11.3 Throttle rates — NAMED (the contract was silent; this is the fix)

The binding directive and "low friction" resolve together here, because the
outbox makes throttling a **pacing device, not a rejection device**: a 429 is
`retryable`, the entry stays in the outbox, and it goes out later. Throttling
therefore **delays a message, never drops one**.

| kind | per IP | burst |
|---|---|---|
| `thumb` | 120 / hour | 20 |
| prose (`comment`, `bug`, `feature`, `question`, `feedback`) | 10 / hour | 5 |

The existing `bug-submit.php` value — one per 30s across everything — is hostile
to the thumbs case (three pages in a minute trips it) and is **not** carried
forward. `PDOOM_THROTTLE_BURST` overrides for tests.

### 11.4 A 413 must name the offending field — ACCEPTED

`error` identifies which cap was exceeded. The visitor cannot fix it otherwise,
and an unfixable rejection is a loss with extra steps. Silent
truncate-and-store is forbidden: it stores something the visitor did not say.

### 11.5 `http_response_code()` under PHP CLI SAPI — A1'S FIRST TASK

Assumed to work as getter/setter; **unverified, no `php` binary on the dev box**.
If it does not, every status assertion in the Python suite is wrong and the suite
moves to `php -S`. **Verify before writing anything else.**

### 11.6 Readers that A3's tests require to exist

F3 (read-time dedup) and F6 (mail divergence) inject their fault correctly and
then find nothing that can observe it — which is the silent-loss condition
itself, so they FAIL rather than skip. A1 owns:

- `scripts/read-feedback.py` — collapses duplicate `rid`, earliest `server_ts` wins
- `scripts/reconcile-feedback.py --store --mail-log --json` — reports divergence
  between what was stored and what was notified

### 11.7 Still unverified, and A1 must fail loudly on it

`store_root` writability on DreamHost shared hosting (§3). If
`dirname(docroot)` is not writable by the PHP user, the endpoint returns 507 and
**never** falls back to a path inside the docroot (INV-1c, F14).
