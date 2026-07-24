# Feedback intake

One line per piece of feedback, from any channel. Append as it arrives — the
point is that nothing gets lost between five platforms that don't talk to each
other. Terse is fine. Raw quotes beat your summary of them.

**Format:** `| date | who | channel | verbatim-ish | action |`

Channels: `linkedin` `facebook` `twitter` `bluesky` `instagram` `web-form`
`direct` (text/call/in-person) `github`

Actions: `triaged #<issue>` · `needs-repro` · `wontfix` · `duplicate` · `—`

> Keep the wording people actually used. "I didn't know what to click" and
> "the UI is confusing" point at different fixes, and the second is usually
> your paraphrase of the first.

---

## 2026-07-24 — alpha launch

| date | who | channel | what they said | action |
|---|---|---|---|---|
|  |  |  |  |  |

---

## Patterns worth watching for

Not every report is what it says it is. A few known confusions for this launch:

- **"It won't open" on macOS** → almost certainly Gatekeeper refusing an
  un-notarised build, not a crash. The site now carries the right-click→Open
  workaround, but people who downloaded before reading it will report a broken
  download.
- **"I filed a bug in the game"** → it did not reach you (pdoom1 #800). Ask
  them to resend via the website form or just paste it to you directly.
- **"My score didn't show up"** → expected; remote score submission is not live
  (pdoom1 #735). Not a bug on their end, and worth saying so quickly so they
  don't think they broke something.
- **Silence from a whole platform** → check the link you posted actually
  carried its UTM and resolves. A dead or unattributed link looks exactly like
  disinterest.

## Triage, end of day

Three buckets, in this order:

1. **Blocks play** — they could not start, or could not finish a run. Fix first,
   these people are gone otherwise.
2. **Confused, kept playing** — onboarding and legibility. This is the most
   valuable category at alpha and the easiest to dismiss.
3. **Wants / opinions** — feature requests and balance takes. Log, do not act
   on yet; they need many data points before they mean anything.
