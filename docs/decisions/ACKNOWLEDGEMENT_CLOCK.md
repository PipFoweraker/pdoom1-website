# The acknowledgement clock — an answer to "class 5, the knowing allowlist"

**Status:** prototype, live in `pdoom1-website` on one check.
**Portable to:** `pdoom1`, `pdoom-data`. Written to be copied.
**Origin:** the 2026-08-09 workshop (`coordination#47`), which named eight classes
of "green and wrong" check. Class 5 defeated every remedy proposed there.

## The problem, in the workshop's own words

> A check SEES the divergence, PRINTS it, and exits 0 **by design**. It is not
> disarmed, not mis-aimed, not stale. `pdoom-data`'s `check_invariants.py` prints
> three known divergences and exits 0, and has for about eight months. **The check
> is not fooled; the reader is, by its exit code.**

The estate has been answering this ad hoc, one check at a time, by picking one of
two bad options:

- **Red forever.** Trains everyone to ignore red. Once the red square means
  nothing, the one failure that matters is skipped with the rest. `pdoom1-website`'s
  CLAUDE.md already forbids this: *"a red test in the suite is worse than no test"*.
- **Green forever.** Hides a real finding behind a true statement nobody reads.
  Exactly class 5.

Both are wrong, and neither is more wrong than the other, which is why picking
between them per check has produced an incoherent estate.

## The generator: what is actually missing?

Look at what the existing allowlists in this repo do and do not carry. All four
(`check-encoding-safety.py`'s `KNOWN_UNFIXED`, `check-platform-claims.py`'s
`ALLOWLIST`, `check-stale-facts.py`'s `SKIP_FILES` and `LINE_ALLOWLIST`) carry a
**reason** — better than most repos manage. None carries a **clock**.

That is the whole gap. A reason is a claim about the world, and claims about the
world stop being true. Without a clock a lapsed reason is indistinguishable from a
live one, and nothing ever asks.

Live proof, found while building this. All three `KNOWN_UNFIXED` entries read
*"held by the `<X>` branch (2026-07-29 sweep)"*. On 2026-08-09 two of those three
branches did not exist on the remote. The justification had been false for days;
the check went on printing `WAIVED` and exiting 0, because a reason without an
expiry cannot expire.

## The rule

> **An acknowledgement is a state with a clock, not a permanent exemption. The
> thing that expires is the ACCEPTANCE, never the finding.**

- **Before `review_by`** — the check is **GREEN**, and every acknowledged item is
  printed *and counted in the summary line*. Green carries a number, never silence.
  A green that prints nothing is indistinguishable from a check that found nothing,
  and that indistinguishability is class 5 itself.
- **After `review_by`** — the check is **RED**, on *"this acceptance expired,
  re-accept or fix"*, **not** on the underlying finding.

That distinction is load-bearing and is the part that is easy to get wrong. A red
on the *finding* cannot be closed by whoever hits it — they did not create it and
often cannot fix it — so it becomes permanent, and we are back to red-forever. A
red on an *expired acceptance* is always closeable by a human decision: fix it and
delete the entry, or write down that you still accept it, your name, and until
when. Both are decisions. Neither is a shrug. That is why this red cannot rot into
a permanent one.

Two further states, both reported, neither blocking:

- **STALE** — an acknowledgement whose key no longer fires. Dead weight, and a
  loaded gun: if the key returns it is pre-forgiven by a decision nobody is making
  any more. *Not* blocking, because deleting a dead exemption is housekeeping, not
  an honesty risk today — and its own `review_by` forces the question on a date
  regardless. Adding a second blocking mode here would be a new knob, and ad-hoc
  knobs are the disease.
- **EXPIRING** — inside `policy.warn_within_days` of `review_by`. Without this, an
  expiry lands as a surprise red on a stranger's unrelated PR, and the rational
  response is a bulk re-accept — which is the same as having no clock at all.

## The data format

One ledger per repo, at the **repo root** (not under any deployed directory), every
value carrying a `source`. Required fields, all mandatory and non-blank:

| field | why it is required |
|---|---|
| `check` | which check this suppresses; must appear in the ledger's `checks` map |
| `key` | the stable key the check reports — how the entry is matched |
| `what` | the finding, in the check's own words |
| `why` | why it is tolerated — **the part that can stop being true** |
| `accepted_by` | a person, or an honest statement that nobody is recorded |
| `accepted_on` | strict ISO date |
| `review_by` | strict ISO date; the acceptance dies here |
| `on_expiry` | what the next human should DO — this is what makes the red actionable |
| `source` | the issue, PR, comment or ruling it rests on |

## What is refused, and why refusal beats skipping

Loading raises and the check exits **2** (not 0, not 1) on: a missing or
unparseable ledger; any missing or blank required field; a non-ISO date;
`review_by <= accepted_on`; a `check` name not declared in `checks`; a duplicate
`(check, key)`; a `policy` value with no `source`.

A malformed entry is **not** treated as absent. "Absent" means "not acknowledged"
means the check fails on the *finding* instead — which reads as a real, fresh bug
and sends someone hunting something nobody introduced. Refusing the whole ledger
says the true thing: *you cannot currently know what this check is tolerating.*

The `checks` map exists for one specific hole: a typo in an entry's `check` field
would otherwise suppress nothing while reading, to every human, as an exemption.
A silent no-op is precisely the failure mode this whole mechanism is about.

## Testability is a design constraint, not an afterthought

`today` is **injected**, never read from the clock inside the logic, and both the
module and the wired check take `--as-of`. Otherwise the expired state — the entire
point of the design — could only be observed by waiting for it to fire on someone
else. CLAUDE.md: *"a guard seen only in its passing state has not been shown to
work."* The live ledger sits in exactly one of five states, so a run against real
data exercises a fifth of the mechanism.

## Reference implementation

- `scripts/acknowledgements.py` — the module (no repo-specific logic; the ledger
  path is the only thing to change when porting).
- `data/acknowledgements.json` — the ledger.
- `scripts/check-encoding-safety.py` — the one wired check.
- `scripts/test-acknowledgements.py` — 75 assertions, every state forced.
- `.github/workflows/encoding-safety.yml` — the test runs *before* the sweep, on
  both ubuntu and a cp1252 Windows console.

**Why `check-encoding-safety.py` was chosen** over the other three candidates:

- Its allowlist is small (3 entries) and its keys are stable file paths, so the
  match is unambiguous and the diff is reviewable.
- It is genuinely **blocking-and-true** already, wired to a real workflow — so the
  clock is being added to a gate that means something, not to an advisory nobody
  reads.
- Its allowlist was a **dict literal in the script**, which CLAUDE.md's data-file
  rule forbids outright, so the migration was owed anyway.
- Its waiver reasons had *already lapsed*, so the mechanism had something true to
  say on day one rather than being a hypothetical.

Rejected for now, with reasons: `check-stale-facts.py` (213 findings; its problem
is a severity gate that is already reasoned, and its `SKIP_FILES` entries are
permanent structural facts about file *kinds*, which is a different thing from a
dated acceptance); `snapshot-copy.py --check` (a review aid by design, not a gate —
Pip reads it for drift; putting a clock on prose drift would be a product decision,
not an engineering one); `test-header-consistency.js` (JS, so porting the module is
a second implementation, and its 8 failures are content emoji, i.e. a real backlog
rather than a set of decisions).

## Porting checklist

1. Copy `scripts/acknowledgements.py`; change `LEDGER_PATH`.
2. Create the ledger with `policy`, `checks` and an empty `acknowledgements` list.
3. In the target check: `load_ledger(name)` **before** scanning; let
   `AcknowledgementError` exit 2; `assess(fired_keys, today)`; suppress
   `report.acknowledged_keys`; `report.print_to(...)`; return 1 if
   `unwaived or report.blocking`.
4. Copy `scripts/test-acknowledgements.py`, retarget the wiring tests (11–14).
5. Wire the test in the **same commit**, *before* the guard in the workflow.

For `pdoom-data`'s `check_invariants.py` specifically: its three divergences become
three entries with three *different* `review_by` dates. Do not give them one shared
date — a thundering herd of expiries on one day is answered by a bulk re-accept,
which is a clock in name only.

## Known weaknesses — read before adopting

1. **Bulk re-accept is still available.** Nothing stops a human bumping every
   `review_by` by ninety days without thinking. The design makes that *visible*
   (a dated, named, sourced diff in a reviewed file) rather than *impossible*.
   Making it impossible is not achievable by a checker; it is a review norm.
2. **The red lands on whoever pushes next**, not on the accepter. Mitigated by
   `EXPIRING SOON` and by printing `accepted_by` so the red is routable, but not
   solved. A scheduled job that opens an issue at `review_by - warn_within_days`
   would solve it properly, and is the obvious next increment.
3. **Key stability is assumed.** If a check's key format changes (a renamed file,
   a reworded finding), every acknowledgement silently becomes `STALE` — visible,
   but as the wrong diagnosis. The `checks` map catches a renamed *check*; nothing
   yet catches a renamed *key*.
4. **The window value is not derived from anything.** `warn_within_days: 14` is a
   judgement call with a `source` note saying so. It is not measured, and it should
   move if warnings start being ignored.
5. **It does not fix the finding.** By construction. This mechanism makes an
   accepted divergence a dated decision instead of a silent one; it never makes it
   go away. If a repo's answer to every expiry is another acceptance, the ledger
   becomes an accurate record of an unaddressed backlog — which is still an
   improvement on nothing, but should be read as the signal it is.
