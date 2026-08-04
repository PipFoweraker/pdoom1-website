# Insights ledger

Ideas worth keeping, captured at the moment they were said rather than reconstructed
later. Blog fodder, argument-fodder, and occasionally the seed of a design decision.

**Rules of the ledger.** Date everything. Record who said it. Keep the original wording —
a paraphrase loses the thing that made it worth capturing. Note the context, because an
insight without its situation is a slogan. If one turns out to be wrong, **strike it
through rather than deleting it**; being wrong in public on a dated record is the same
discipline the blog posts follow.

---

## 2026-07-31 — WIP going up can be the right trade

**Claude, in conversation with Pip during league-week prep.** Pip had asked earlier that
morning to *"keep our WIP small"*, then over the next few hours approved a large audit
that opened many more items than it closed. He noted the tension himself, cheerfully.
The reply:

> WIP going up was the right trade this morning, for what it's worth — most of today's
> growth is things that were already broken and are now merely **visible**.

**Why it is worth keeping.** The usual WIP heuristic treats open items as *cost* —
things you have taken on. That is right for work you chose to start and wrong for work
you merely *discovered*. An audit does not create defects; it converts unknown defects
into known ones. The ticket count rises and the actual risk falls, and the two moving in
opposite directions is exactly what you want on the day you find out.

The failure mode this guards against is the one that punishes looking: if a rising WIP
count always reads as a problem, then the cheapest way to keep it down is not to audit,
and the second-cheapest is to audit and not write things down. Both leave the defects in
place and remove your ability to see them. **A backlog that grows when you look at it is
working. A backlog that only ever grows when you type is not being looked at.**

The honest caveat: this only holds if the new items are *findings* rather than *ambitions*.
Twelve newly-discovered broken things and twelve newly-imagined features look identical in
a ticket count and are opposite in meaning. That distinction is worth marking in the
tracker, because without it "WIP went up, that's fine, it's an audit" becomes an excuse
rather than a reason.

**Where it came from.** A day that started with a plan to do UI polish and instead found:
a live XSS sink, a deploy path that meant bot-committed data never reached the site, a
test fixture that had been rotting for three releases, a CI guard that had never once
passed, and a page that could be killed entirely by a missing WebGL context. None of
those were created that morning. All of them were **years old and silent**.

**Possible post angles:** the audit-versus-WIP tension; why a backlog that grows when you
look at it is healthy; the difference between discovered and chosen work; how to count
tickets so that looking is not punished. Pairs naturally with the *"red but tolerated"*
piece — see the entry below when written, and the testing-discipline section in
`CLAUDE.md`.

**Related:** Pip's own observation the same week that he had *trained himself to ignore
red tests* because the redness never forced him to slow down. Same family: both are about
what a signal costs to attend to, and what happens to signals nobody can afford to read.
