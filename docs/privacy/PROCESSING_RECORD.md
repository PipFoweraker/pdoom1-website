# Processing record — what personal data we hold, and why

The single source of truth for every piece of personal data the site touches.
It doubles as the "record of processing" both GDPR (Art. 30) and the Australian
Privacy Principles expect you to keep — so keeping it current *is* most of the
compliance work, not paperwork on top of it.

**The rule the whole table enforces (purpose limitation):** each item may be used
only for the purpose it was given for, and kept only while that purpose is alive.
The unit is the **(data, purpose) pair**, not the data type — which is why the
same field can be fine for one use and off-limits for another.

**Status (2026-07-24):** we do not yet have a database. Form data currently lives
in the **team@pdoom1.com mailbox** (the report path) and in **GitHub** (only if a
reporter takes the public fallback). The mailbox is a datastore — so this record
describes reality today, not a future system.

| # | data | collected where | purpose (why they gave it) | lawful basis | may we use it for… | retention | stored where (today) |
|---|---|---|---|---|---|---|---|
| 1 | **Email** | bug form (optional) | reply to the reporter about *this* report | consent-by-provision / legitimate interest in supporting a user who asked | replying about this report **only** — never marketing, never a list | life of the report thread, then clear | team@ mailbox |
| 2 | **Name for credit** | bug form (optional) | credit the reporter for the contribution | **explicit opt-in consent** (they typed it knowing it may be public) | crediting them publicly (release notes / linked issue) **only** | until they ask to remove it | team@ mailbox; published credit where used |
| 3 | **Report text** | bug/issue form | describe the bug/feature | legitimate interest in fixing the product | triage, fixing, and — if the private send fails — a **public** GitHub issue they’re warned about | life of the issue | team@ mailbox or public GitHub |
| 4 | **Email (direct)** | someone emailing team@ | whatever they wrote | consent-by-provision | replying about their message | until resolved, then housekeeping | team@ mailbox |
| 5 | **Analytics events** | every page (Plausible) | understand site usage | legitimate interest | aggregate stats only | Plausible's retention; no raw PII stored | self-hosted Plausible VM |
| — | ~~IP address~~ | — | — | — | **not stored** (anonymised at request time) | n/a | n/a |

## The two lawful bases we actually use, in plain terms

- **"You gave it to me for exactly this."** Using the email a reporter typed into
  a "your email (for a reply)" box, to reply — needs no separate checkbox; the act
  of typing it into a purpose-labelled field *is* the consent. Rows 1, 3, 4, 5.
- **A separate, affirmative opt-in** for any *secondary* purpose — publishing an
  identity (row 2), or ever emailing someone about something they didn't ask
  about (a newsletter — **we don't do this, and it's not in the table**; adding it
  would need a new row and its own unbundled, default-off opt-in).

## The design rule that keeps it consistent

**One opt-in per secondary purpose. Unbundled. Default off. Independently
revocable.** Never fuse "reply to me" + "credit me" + "email me updates" into one
tick. The primary purpose (reply using the reply-email) gets no box; every extra
purpose gets its own.

## The cheat code

**The less we keep, the less we owe.** Every field not persisted is a whole row of
obligation not incurred. Row 1's ideal end-state: email used transactionally and
never persisted beyond the report thread. Minimisation isn't a constraint here —
it's what keeps this table short and the compliance surface tiny.

## Change discipline

**Adding any new field that collects personal data means adding a row here first.**
That's the guardrail — see `docs/SHIP_DISCIPLINE.md`. A field in a form with no
row in this table is the failure mode: silent collection nobody decided on.

_Companion: `docs/privacy/PRIVACY_NOTICE_DRAFT.md` is the public-facing statement
of this same table. They must stay in step — if one changes, change the other._
