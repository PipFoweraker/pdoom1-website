# Ship discipline — guardrails against future-me shipping hasty

Pip's own framing: a standing tension between the **build-and-push urge** and the
**ship-with-quality urge**. This file exists so the quality side has *mechanisms*,
not just good intentions — because good intentions are exactly what erode under
launch pressure and momentum.

## The design principle for the guardrails themselves

**Prompt and fail-loud; don't hard-block, and never train reflexive dismissal.**

A hard block on a solo founder's own repo gets disabled the first time it's
inconvenient. A guardrail that makes you mash Enter to continue trains you to mash
Enter *without reading* — it actively manufactures the sloppiness it claims to
prevent. So:

- **Checklists** that are visible and quick (a PR template) — nudge, don't gate.
- **CI checks** that fail *loudly and legibly* (you can read exactly what's wrong
  in 5 seconds) — these can gate, because they're objective and fast to satisfy.
- **No "press Enter to continue" prompts.** They're theatre. (The current
  `.husky/pre-commit` has one — see "Known anti-pattern" below.)

## The disciplines (what "shipped with quality" means here)

1. **Never lie to a visitor.** Every reader-facing prose change is justifiable as
   "this was false, now it's true." Run `python scripts/snapshot-copy.py --check`
   and eyeball the diff before merging copy.
2. **Fallback literals are lies waiting to happen.** A default value ships exactly
   when the real lookup failed. Prefer failing loud or 'unknown' over a plausible
   literal (see the download version-stamp fix, 2026-07-24).
3. **New personal-data field ⇒ a row in `docs/privacy/PROCESSING_RECORD.md` in the
   same change.** A form field with no processing-record row is silent collection
   nobody decided on.
4. **Trace generated content to its source before deleting** (Chesterton's fence —
   the alignmentforum pages, the orphaned league trio).
5. **Run the local suite before opening a PR** (the list in `CLAUDE.md`).
6. **Verify on the Netlify preview, not just locally**, before merge.

## Mechanisms (status)

| mechanism | what it does | gate or nudge | status |
|---|---|---|---|
| `.github/pull_request_template.md` | the checklist above, in front of you at PR time | nudge | **shipping now** |
| local test suite (`CLAUDE.md` list) | correctness/regression | nudge (you run it) | exists |
| `snapshot-copy.py --check` | reader-facing copy drift | nudge | exists |
| CI: tests on PR (health-check, version-check) | objective pass/fail | gate | exists |
| **CI: personal-data guardrail** | fail a PR that adds a form `<input>` without touching PROCESSING_RECORD.md | gate | **proposed — see below** |
| **CI: copy-drift comment** | post the `snapshot-copy` diff as a PR comment so drift is seen, not skipped | nudge | proposed |

## Proposed: personal-data CI guardrail

A tiny workflow that, on any PR touching a form page, checks whether
`docs/privacy/PROCESSING_RECORD.md` was also touched — and fails with a legible
message if not:

> "This PR changes a form but not the processing record. If you added or changed a
> field that collects personal data, add/adjust its row. If not, say so in the PR
> and re-run."

Objective, 5-second-legible, satisfiable by one honest line — so it can gate
without becoming friction you'll want to disable. **Not built yet; decide at the
data workshop whether it's worth the wire.**

## Known anti-pattern to fix

`.husky/pre-commit` currently ends with "Press Enter to continue or Ctrl+C to
cancel" on every `feat:`/`fix:` commit. That is the reflexive-dismissal trainer
described above — it teaches you to mash Enter past a reminder you've stopped
reading. **Recommend:** replace the interactive pause with a non-blocking printed
reminder (it says its piece and lets the commit through), or drop it in favour of
the PR template. Left as-is pending your call, since it touches your commit flow.
