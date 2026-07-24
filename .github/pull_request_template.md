<!-- Ship discipline (docs/SHIP_DISCIPLINE.md). Tick what applies; delete the rest.
     This is a nudge, not a gate. Its job is to make future-you pause on the
     things that erode under momentum, not to slow an honest change. -->

## What & why

<!-- One or two sentences. What changed, and what was wrong before. -->

## Ship checklist

- [ ] **Reader-facing prose:** every copy change is "this was false, now it's true" (not tone drift). Ran `python scripts/snapshot-copy.py --check` and read the diff.
- [ ] **No new fallback literal** presented as current (version, price, date). Failures fail loud or read 'unknown', not a plausible-but-stale value.
- [ ] **Personal data:** if this adds/changes a form field that collects personal data, `docs/privacy/PROCESSING_RECORD.md` has a matching row. (N/A? say so.)
- [ ] **Generated content:** didn't delete generated/orphaned files without tracing them to source (Chesterton's fence).
- [ ] **Tests:** ran the local suite (see `CLAUDE.md`); relevant ones pass.
- [ ] **Preview:** verified on the Netlify deploy-preview, not only locally.

## Notes for review

<!-- Anything the reviewer (you) should look at hardest. Copy wording? A promise
     made to players? A data-handling boundary? Name it. -->
