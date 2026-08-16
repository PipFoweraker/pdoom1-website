# Feedback intake — session state at shutdown

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
| `python scripts/test-ingest-destructive.py` | **not measured** — run exceeded 120s and was stopped at shutdown | A3 reports 13 rows failing; **unverified by me** |
| `python scripts/test-check-mail-auth.py` | **0** | every mail-auth check forced into its failing state and observed |
| `python scripts/check-mail-auth.py` | **0** | 3 passing, 4 acknowledged, **`DMARC ceiling p=none`** — M5 interlock live |
| `python scripts/check-encoding-safety.py` | **0** | 83/83 modules, new files included |

A3's headline was 16 FAIL / 1 PASS. **I verified the 4 JS rows and the exit
code; I did not verify the 13 Python rows** — the suite was still running when
shutdown was called. Treat A3's Python numbers as a report, not a measurement.

**A3 flagged F4 (concurrent append) as too weak**, and it is right: its lock
probe is POSIX-only and skips on Windows, so the local PASS means "nothing
collided on this run", not "a lock exists". It runs for real on the Linux CI
runner.

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
