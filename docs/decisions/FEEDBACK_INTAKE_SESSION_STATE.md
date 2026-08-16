# Feedback intake — session state at shutdown

> ## SUPERSEDED IN PART — stamped 2026-08-16T23:35Z = 2026-08-17 09:35 AEST
>
> **Mail auth is DONE and DEPLOYED.** Sections 1 and 2 below described a world
> where SPF, DKIM and DMARC were all absent. Two of those changed on 2026-08-17.
> Read this box before believing anything below it.
>
> **What Pip published** (DreamHost panel, ~08:53 AEST, verified on all three
> DreamHost nameservers plus 8.8.8.8, 1.1.1.1 and 9.9.9.9):
>
> ```
> pdoom1.com          TXT  v=spf1 include:_spf.google.com include:netblocks.dreamhost.com ~all
> _dmarc.pdoom1.com   TXT  v=DMARC1; p=none; rua=mailto:team@pdoom1.com
> ```
>
> **What that changed**
>
> | | before | now |
> |---|---|---|
> | M1 / M2 / M3 | ABSENT / UNEVALUABLE / ABSENT | **PASS** — the three 08-22 acknowledgements are DELETED, not expired |
> | M4 (DKIM) | ABSENT | still ABSENT, acknowledgement stands, `review_by 2026-08-29` |
> | DMARC ceiling | `p=none` | **`p=reject` permitted**; published policy deliberately still `p=none` |
> | form mail | `dmarc=fail`, Gmail spoof banner | **`dmarc=pass`**, no banner |
>
> **Merged to main and live: `06416bf2`** — `bug-submit.php`'s `mail()` gained
> `-f team@pdoom1.com` (PR #325). Verified end-to-end by sending through the live
> form and reading the received headers: `Return-Path: <team@pdoom1.com>`,
> `spf=pass ... designates 208.113.156.243`, `dmarc=pass`.
>
> **Three claims this repo held that real headers disproved:**
> 1. `data/mail-auth.json` named `173.236.253.218` as the sender. That is the WEB
>    IP and sends nothing. PHP runs on `173.236.245.76`; the SMTP client Google
>    authenticates is the relay `208.113.156.243`. Corrected in `01893664`.
> 2. The M4 acknowledgement said "nothing the domain sends is DKIM-signed".
>    Workspace mail IS signed — `d=pdoom1-com.20251104.gappssmtp.com` — but that
>    does not ALIGN, so DMARC can't use it. Workspace `dmarc=pass` rests on SPF
>    alone, and SPF alignment is what forwarding breaks. That is the real argument
>    for doing M4. Corrected in `01893664`.
> 3. `bug-submit.php`'s own comment (`b2a6d422`, written 08:25) asserted with
>    today's date that no SPF record existed. True when written, false 28 minutes
>    later. Corrected in `06416bf2`.
>
> **Open, in priority order:**
> - **`bug-submit.php` WILL CONFLICT** when this branch merges: `main` has
>   `b2a6d422` + `06416bf2`, this branch has `72cb1b3c` + `01893664`, both editing
>   the same region. Reconcile before merging.
> - Revert the mailto mitigation `50227fc0` — safe now, the form's mail
>   authenticates.
> - **Do NOT raise the DMARC policy** past `p=none` until the `rua` reports have
>   been watched for ~2 weeks. Permission is not a reason.
> - Check whether `rua` reports actually arrive within 48h. If nothing lands, the
>   tag is decoration.
> - DKIM (M4) in Google Admin — a different console. Clock: 2026-08-29.
> - **Unresolved: were pre-fix submissions lost?** Google Admin's Email Log Search
>   showed nothing. That is NOT evidence of loss — it caps at ~30 days, the
>   server-side `submission_log()` only exists from `b2a6d422` onward, and Email
>   Log Search can only show what reached Google at all. Pip's hypothesis is that
>   Postfix never handed them off; checking DreamHost's own mail logs is the next
>   step and was deferred. Note that "nobody used the form" is an equally good
>   explanation of the same null and has not been ruled out.
> - `scripts/check-mail-auth.py --live` resolves against `ns1.dreamhost.com`,
>   which is **Cloudflare anycast** — it can record a stale PoP's answer as a
>   measurement. Unfixed. Require agreement across all three nameservers.

**Stamped 2026-08-16T07:53Z** (2026-08-16 17:53 Australia/Hobart, UTC+10).
Session ran 2026-08-15 into 2026-08-16. Branch `feedback/intake-contract`,
forked from `main` at `04004298`. **Nothing merged, nothing deployed.**

---

## 1. Clocks — the dated things, in expiry order

| date | what expires | who can clear it | if nobody does |
|---|---|---|---|
| **2026-08-22** | acknowledgements `pdoom1.com/M1/absent`, `M2/unevaluable-no-spf`, `M3/absent` | **Pip only** — DreamHost panel, one visit | `check-mail-auth.py` goes red on "acceptance expired" |
| **2026-08-29** | acknowledgement `pdoom1.com/M4/absent` (DKIM) | **Pip only** — Google Admin, a *different* console | same |
| n/a | contract §10 retention clocks | not yet implemented | `purge-feedback.py` does not exist yet |

Audit at any time: `python scripts/acknowledgements.py --audit`

The three 2026-08-22 entries are cleared by a **single act** — publishing SPF and
DMARC. They are carried as three entries rather than one so the check cannot go
green on a partial fix.

---

## 2. Measured state of the world (2026-08-15/16, authoritative vs `ns1.dreamhost.com`)

| fact | value |
|---|---|
| MX | `SMTP.GOOGLE.com` pref 0 |
| SPF | **absent** |
| DKIM `google._domainkey` | **absent** (NXDOMAIN) |
| DMARC | **absent** |
| apex A / www | `173.236.253.218` (DreamHost shared) |
| `api.` / `analytics.` | `208.113.200.215`, **both valid LE certs** (exp 2026-10-06 / 2026-10-08) |
| `forum.pdoom1.com` | still NXDOMAIN |
| `navigation.js` coverage | **45 of 2263** HTML files |
| generated event pages | load **neither** `navigation.js` **nor** `escape.js` |

Records to publish (contract §5):

```
TXT  @        v=spf1 include:_spf.google.com include:netblocks.dreamhost.com ~all
TXT  _dmarc   v=DMARC1; p=none; rua=mailto:team@pdoom1.com
TXT  google._domainkey   <generated in Google Admin, NOT the DreamHost panel>
```

---

## 3. Gate 2 evidence — verified by me, not taken on report

| suite | real exit | meaning |
|---|---|---|
| `node scripts/test-feedback-outbox.js` | **1** | F7, F8, F16, F17 all fail against the stub |
| `python scripts/test-ingest-destructive.py` | **1** — reverified 2026-08-16, full run | 12 of 13 fail; subject line confirms `STUB`, not a half-written endpoint |
| `python scripts/test-check-mail-auth.py` | **0** | every mail-auth check forced into its failing state and observed |
| `python scripts/check-mail-auth.py` | **0** | 3 passing, 4 acknowledged, **`DMARC ceiling p=none`** — M5 interlock live |
| `python scripts/check-encoding-safety.py` | **0** | 83/83 modules, new files included |

A3's headline was 16 FAIL / 1 PASS. **Reverified 2026-08-16: it is exactly
right.** Python rows F1, F2, F3, F5, F6, F9-F15 fail; F4 passes. JS rows F7, F8,
F16, F17 fail against the stub and pass against A2's real module.

**A3 flagged F4 (concurrent append) as too weak**, and it is right: its lock
probe is POSIX-only and skips on Windows, so the local PASS means "nothing
collided on this run", not "a lock exists". It runs for real on the Linux CI
runner.

### 3.1 Where the suite can and cannot run — a constraint, not a bug

Once `public/ingest.php` exists, `test-ingest-destructive.py` **cannot run on a
Windows box at all**: there is no `php` binary, and the harness RAISES rather
than falling back to the stub, because a fallback would report the stub's
behaviour under the endpoint's name. That is the correct design and it means
**CI is the only place those 13 rows will ever execute.**

Three consequences, none yet closed:
- `.github/workflows/feedback-intake.yml` has **no explicit `setup-php` step**.
  `ubuntu-latest` ships PHP, so it should work by default — but that is an
  implicit dependency on a runner image. Pin it. Failure mode is loud (the
  harness raises), so this is robustness, not correctness.
- **CI has never run on this branch.** The workflow triggers on `pull_request`
  and `push: main`; no PR exists. Every green recorded here is local-only.
- The POSIX-only halves — F2's torn write, F4's lock probe, F13's rsync dry-run
  — have therefore **never executed anywhere**.

---

## 4. Committed this session

- `docs/decisions/FEEDBACK_INTAKE_CONTRACT.md` — the contract (§8 decisions
  settled with Pip: private comments + public aggregate counters, JSONL record,
  digest-for-thumbs, per-field retention)
- `scripts/test-ingest-destructive.py`, `scripts/test-feedback-outbox.js`,
  `scripts/fixtures/**` — A3
- `scripts/check-mail-auth.py`, `scripts/test-check-mail-auth.py`,
  `data/mail-auth.json`, `data/acknowledgements.json` (+4 entries),
  `.github/workflows/feedback-intake.yml` — A4

**No implementation exists.** `public/ingest.php` and
`public/assets/js/feedback.js` are unwritten by design — Gate 2 requires the
tests to be observed red first, which they now are.

---

## 5. Open, blocking Wave 1b

A3 surfaced **9 contract under-specifications** it had to decide unilaterally.
These are now de-facto contract, encoded in tests that A1/A2 must satisfy, and
**they have not been adjudicated by me or Pip**. The load-bearing ones:

1. **Mail observability seam** — `PDOOM_MAIL_SINK` / `PDOOM_MAIL_FAIL`. A1 must
   honour these or F1/F5 are untestable.
2. **Client API shape** — `createFeedbackClient({storage, fetch, uuid, now,
   render, endpoint})`. A2 must export this or an adapter, or F7/F8/F16 are
   untestable. *Untestable is not the same as passing.*
3. **Throttle rate is unnamed in the contract.** F9 defaults to a burst of 60.
   **The contract should name a number.**
4. **413 must name the offending field**, else the visitor cannot fix it.
5. **`http_response_code()` under PHP CLI SAPI is assumed to work as a
   getter/setter and is UNVERIFIED** — no `php` binary on this box. If it does
   not, every status assertion in the Python suite is wrong and the suite must
   move to `php -S`. **A1 should check this first.**

Also unresolved: **`store_root` writability.** Contract §3 requires the store
above the deployed docroot; whether `dirname(docroot)` is writable by the PHP
user on DreamHost shared hosting is **still unverified**. It is the one premise
that would change the storage decision.

---

## 6. Lost context

Agent A4 was **stopped mid-report** at shutdown. Its closing line — *"Live
resolution confirms the measurement independently — and surfaced one detail
worth recording"* — was truncated, and **that detail is not recorded anywhere in
this document**. Its full transcript survives at:

```
C:\Users\gday\AppData\Local\Temp\claude\D--Local-Code-pdoom1-website\
  cbe33dd9-dad0-442c-819b-7ebfb968de0c\tasks\a55d03360eed41922.output
```

Scratchpad paths are session-scoped and may be cleaned. If that detail matters,
recover it before the next session starts.
