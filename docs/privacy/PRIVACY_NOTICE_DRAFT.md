# Privacy notice — DRAFT for Pip's review

Plain-language, in your voice. This is the *forms & contact* half of privacy —
the existing `/privacy/` page already covers analytics well, and the forms clause
there was updated 2026-07-24 to match this. This draft is the fuller version to
fold in when the tone pass (#160) runs; it is **not deployed** until you sign off.

Every line must stay true to `docs/privacy/PROCESSING_RECORD.md`. If they drift,
the record wins and this gets corrected — never the other way round.

---

## What happens to what you tell us

We keep this short because the honest version *is* short: we collect almost
nothing, and what you hand us we use only for the reason you handed it over.

**If you just visit** — we don't collect anything about you personally. No
cookies, no account, no name, no email, no IP kept. (The full analytics story is
above.)

**If you file a bug or feature report:**

- **Your email** (optional) is used for one thing: replying to you about that
  report. We keep it with the report while it's open, then clear it. It never
  goes on a mailing list, we never sell or share it, and we won't email you about
  anything you didn't raise.
- **A name for credit** (optional) is the one thing here that can be *public* — if
  you fill it in, we may credit you in release notes or a linked issue. That's the
  whole point of the field. **Leave it blank and you stay anonymous** — the report
  is just as welcome either way.
- **The report itself** comes to our team privately by email. If that send fails,
  the form offers to open a pre-filled GitHub issue instead — that one is public,
  and the form tells you so before you continue.

**If you email us** — we get what you wrote, and use it to reply. That's it.

## Your say over it

- **See it or delete it:** email <team@pdoom1.com> and ask what we hold about you,
  or to delete it. We hold very little, so this is easy for us to honour.
- **Stop the anonymous counting:** turn on Do Not Track, or use the opt-out on the
  analytics page. Nothing else is needed.

## The honest bit about who we are

We're a small, volunteer-made, non-commercial project. We'd rather show you good
mechanics than wave a compliance badge — but the substance matters, so plainly:
we process almost no personal data, keep it only as long as its purpose lasts,
store it on our own systems, and share it with no one. If there's something here
we could do better, tell us — genuinely. <team@pdoom1.com>.

---

## Notes for Pip (not for publication)

- **Deploy target:** fold into `public/privacy/index.html` under a "Forms &
  Contact" section during the tone pass (#160), gated through
  `snapshot-copy.py --check`.
- **Blog parser constraint** does not apply here (this is a real HTML page, not a
  markdown blog post) — headings/lists are fine.
- **When a database exists:** add a line on where data lives and how deletion
  works mechanically. Until then, "email us to delete" is honest — deletion is
  literally us finding the mail and removing it.
- **Do not add** language promising things we don't do (a newsletter, an account
  system) even if they're planned. Notice describes *now*, not the roadmap.
