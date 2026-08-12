# ADR-0002 — Designing guards that can actually fail

**Status:** proposed
**Date:** 2026-08-11
**Author:** `pdoom1-website` seat
**Context:** distilled from the 2026-08-07/11 incident, Workshop 2
(`coordination#47`), and five guards written in its aftermath. Progresses #214,
which asks for `docs/decisions/` to become a real ADR set.

---

## Context

On 2026-08-07 pdoom1 published a forking release. pdoom1.com served the **closed**
epoch's board for two days while real scores landed on the live one, invisible.
**Every workflow was green throughout, and every green square was telling the
truth about itself.**

A four-seat workshop then found the defect was not one generator but **eight
classes**, and — this is the part that matters — three seats reached that
conclusion independently from disjoint evidence. The remedies differ per class, so
"add more checks" was never the answer. What follows is the design doctrine that
came out of building five guards under those constraints.

**This is not a style guide. Every rule below is here because something broke.**

---

## Decision

### P1 — The red must be closeable by the person who hits it

A check that goes red on a condition **nobody is permitted to clear** becomes a
red nobody reads, and it takes every other red with it.

The acknowledgement clock (#295) exists for this: an acknowledgement is a state
with a clock, and **the thing that expires is the acceptance, not the finding.**
Versions where the red was about the *finding* all collapsed back into red-forever,
because the person who hits it cannot close it.

**Corollary:** if the only fix is an act only one human may perform — filling a
ledger row that records who blessed a seed and when — the check is **advisory
until that act is possible**, and the promotion condition is written next to the
check rather than remembered.

### P2 — Absence is never agreement. `unknown` is a third state.

A field that cannot be read, a manifest that 404s, a file that will not parse:
these are `unknown`, and they exit **2**, never 0.

This was the failure predicted *in advance and in public* for the epoch-drift
check, before a line of it was written, and it is the way that check would have
become another green-and-wrong one.

### P3 — Observation outranks stored state, but never silence it

When two findings are both true, the one derived from **looking** outranks the one
derived from **files**. The stored-state finding is still **printed** — never
suppressed — but it does not become the headline, and **its remedy is not offered**
when nothing was observed.

The test when writing a check: *if this fires while the thing it is about could
not be observed, is the advice it prints still executable?* If not, it is
outranked. `superseded-publication` says "run the publisher"; the publisher needs
the API that is down.

**This rule was violated inside the fix for the bug that produced it.** Assume you
will get it wrong.

### P4 — Force the state; never watch it pass

Green is equally consistent with *"the condition is safe"* and *"the check never
fires"*. A guard seen only in its passing state has not been shown to work.

Workshop 2 hardened this into a scoring standard: **no guard counts as installed
until a RED run of it has been observed and its run ID recorded.**

**And the test must reproduce the incident's real values**, not a representative
one. Fixtures using `seed-a` and `L1` pass while the real shapes fail.

### P5 — Encode roles, not copies

Four artefacts recording one blessing are **not four copies of one fact**. One is
the human record, one is the machine-read field, one is derived and must never
lead, and one is an **observation** whose `blessed: false` is *correct* and must
never be "fixed".

Write the roles into the checker. A future reader will otherwise normalise them
into agreement and destroy the distinction that makes disagreement detectable.

### P6 — Measure before describing

CLAUDE.md said tokens.json is read by ~8 pages "and the other ~2,190 hardcode
their colours". True, and it hid the shape: **28,821 declarations already carry
the correct value** and the divergence is 91 pages of stale literals.

An hour of measurement replaced a paragraph that had steered work for weeks.
**Prefer a number you can re-derive to a sentence you once believed.**

---

## Antipatterns — each observed, each cost real time

**A1 — A note predicting your own failure is documentation, not a trigger.**
`board-probe-targets.json` contained the sentence *"if pdoom1 forks again and this
is not updated, the site will confidently publish the WRONG board."* It was
exactly right and it did nothing.

**A2 — A default classification silently mislabels what you understand least.**
The Jira exporter refuses to emit when any issue lacks an explicit tier, because a
default would have been quietly applied to precisely the issues a human most needs
flagged.

**A3 — Never read a file your own next step rewrites.** The board probe took its
notion of "the site's board" from a file the publisher rewrote seconds later, and
committed both, two seconds apart, disagreeing (#293).

**A4 — Never compose a fact from two sources of different vintages.** An old seed
from one file and a new epoch from another produced `(weekly-2026-w31, L4)` — a
board key that has never existed in any system.

**A5 — An index is not the record.** A ledger's human-readable table said *NOT YET
BLESSED* while the machine-read field said `blessed`. Reading the table and
reporting it as the record led this seat to tell Pip his epoch was unblessed when
he was right.

**A6 — A metric measures its own proposition, not yours.**
`check-runs --jq .total_count` returns *"check runs attached to this SHA"*, not
*"CI covered this commit"*. Four commits were called defective on that reading;
two were correct behaviour.

**A7 — An alarming guard is not self-evidently correct.** All of the above aim at
guards that pass when they should fail. The mirror exists: a guard that fails when
it should pass, whose findings look plausible because most of them are true
(#303). **The tell is that satisfying it requires making the data worse.**

---

## Consequences

- Guards land **advisory-and-labelled** when their fix is not yet available to the
  person who will hit them, with the promotion condition written beside the check.
- Every guard ships with forced-state tests using the incident's real values.
- `unknown` is a first-class verdict with its own exit code, everywhere.
- **A6 and A7 mean this ADR is not a checklist to run against others' work.** Five
  of the antipatterns above were committed by the seat that wrote them, four
  within seventy-two hours, and two while arguing that others needed better
  evidence.

## Status of the doctrine itself

**Proposed, not settled.** It is distilled from one incident and five guards. The
honest review trigger is the same one Pip applied to the art rules: **revisit after
the next fork**, promote what demonstrably caught something, and delete what only
narrowed the work.
