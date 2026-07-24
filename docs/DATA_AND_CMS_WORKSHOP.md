# Data & CMS workshop — prep + parking lot

**Scheduled:** the week of 2026-08-03, once v0.13 and the game's technical
patching have settled. **Parked until then** — this doc holds the seed thinking so
the workshop starts from something, not a blank page. Do not build any of this
before the workshop; the point is to decide, then build once.

Linked from: `docs/privacy/PROCESSING_RECORD.md` (the data this would manage),
`content/campaigns/feedback-intake.md` (feedback that will accumulate).

---

## The question

You'll accumulate *content-shaped data*: bug/feature reports, contributor names,
cats (#159), feedback from campaigns. At some point a mailbox + markdown files
stops scaling and you want a CMS. The question is **what to build now** so that
"eventually migrate to a real CMS" is an export, not a rewrite.

## The trap to avoid

**Building a CMS.** The failure mode is scope-creep: you set out to "log
submissions" and end up hand-rolling an admin UI, auth, roles, a WYSIWYG editor —
reinventing Directus/Strapi/Ghost badly, then still having to migrate. A homebrew
*store* is cheap and right at your scale; a homebrew *CMS* is a tar pit.

## The seed proposal (to sharpen or reject at the workshop)

**Don't build a CMS. Build a ledger.** An append-mostly structured store whose
schema *is* the processing record — every row carries what/when/purpose/basis/
retention-due. That single move buys three things at once:

1. **Compliance for free** — the store and the Art. 30 / APP record are the same
   artifact; retention purging is a `DELETE WHERE retention_due < today`.
2. **Searchability** — "every report about the ledger UI", "all contributors who
   opted into credit" become queries, not inbox archaeology.
3. **A clean migration** — standard schema + boring formats (SQLite / JSONL) means
   moving to a real CMS later is an export/import, not a data-archaeology project.

**Candidate shape:** SQLite (one file, no server, trivially backed up, queryable,
and every real CMS can import from it) with ~3 tables — `submissions`,
`contributors`, `cats` — plus a 30-line read-only HTML view that reads an export.
No write-UI, no auth, no admin app. You add rows by a small ingest script the bug
form's mail path (or a future POST endpoint) calls.

**The migration trigger — name it now so "I'll notice when it's annoying" becomes
a rule, not a vibe:** migrate to a real CMS when *either* (a) more than one person
needs to edit content, or (b) you're spending >30 min/week hand-managing the
ledger. Until a trigger trips, the homebrew ledger is correct, not a compromise.

## Workshop agenda (½ day)

1. **Decide store vs CMS-now.** Confirm or reject "ledger, not CMS."
2. **Schema.** The 3 tables + the processing-record columns. One hour, done.
3. **Ingest path.** How a bug report becomes a row (extend `bug-submit.php`? a
   nightly mailbox sweep? a real POST endpoint tied to the game's api.pdoom1.com
   Tier-2 work in #800?). This is the one genuinely architectural choice.
4. **Retention automation.** The purge job + how it logs what it purged.
5. **The migration trigger** — write it into `docs/SHIP_DISCIPLINE.md` as a real
   checkpoint, not a feeling.
6. **Explicitly out of scope for v1:** write-UI, auth, multi-user, rich editing.

## Pre-reading

- `docs/privacy/PROCESSING_RECORD.md` — the schema is basically already here.
- pdoom1 #800 Tier-2 (POST to api.pdoom1.com) — if that lands, the game and the
  website want *one* ingest contract, not two. Coordinate.
