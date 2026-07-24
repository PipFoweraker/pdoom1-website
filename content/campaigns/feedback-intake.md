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
| 2026-07-24 03:03 UTC | Helpful Stranger (pip.f.temp@) | web-form | Smoke test. Confirms the form → team@pdoom1.com path **works**. | — (channel verified) |
| 2026-07-24 03:03 UTC | Helpful Stranger | web-form | "this event system probably needs some love and at least one human eyeball involved in the system that reviews and promotes it, just like the system that y'all have for doing art assets in game. Pip would love to spend a month manually reviewing AI papers" | needs-issue — see below |
| 2026-07-24 03:03 UTC | (surfaced by above) | web-form | Reporter attached `Screenshot 2026-07-15 161002.png` (201,249 bytes). The file was **not forwarded** — only its name reached us, and the reporter was shown "Report Submitted!" with no indication. | fixed on `launch/2026-07-24-alpha` |

### On the event-curation point

Read past the joke and it lands on a real gap. The events pipeline
(pdoom-data → `sync-events.py` → ~2,194 generated pages) has **no human review or
promotion stage**. The art asset pipeline does. ADR-0016 assumes one — its monthly
cycle is *"collect real-world events, suggestions on papers etc → author a
world-update pack"* — and "author" is the step that does not exist as tooling.

The sarcasm carries the actual argument: nobody will hand-review a month of AI
papers, so an unreviewed firehose is the default outcome unless something makes
curation cheap. Worth an issue against the monthly world-update cadence, not a
launch-day fix.

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
