# DRAFT -- funding breakdown page

**Status: DRAFT, not published, not posted, not approved.** Drafted 2026-08-15 by the
pdoom-data seat. Intended destination is a public page on pdoom1.com linked from the
Manifund project; nothing here has been put in `public/`.

**This file is NOT covered by the campaign-facts gate.**
`scripts/check-campaign-facts.py` globs `content/campaigns/*.json`, so a `.md` draft is
invisible to it. The block below is written in the campaign shape deliberately: when this
copy is promoted to a real page, move the block into the accompanying JSON so the guards
become live. Until then they are guards a person has to honour, which is weaker, and
saying so is the point.

**When this becomes a page.** `content/` has no build into `public/`; the public pages are
hand-written `index.html` files, one per directory. So this copy would become
`public/funding/index.html`, following `docs/HTML_PAGE_TEMPLATE.md` and the shape of
`public/press/index.html`: canonical link, 150-160 char meta description, the Plausible
script in `<head>`, `og:image` pinned to `/assets/og-card.jpg`, an empty `<header></header>`
with `navigation.js` at the end of `<body>`, and no footer. Four things carry over from
the house rules and change the markup, not the words:

- Hand-written pages use the `.factsheet` / `.factsheet-item` label-value pattern rather
  than `<table>`. The line-item table below is the one place I would argue for a real
  `<table>` anyway -- `public/league/` and `public/metabolism/` already use them, and a
  four-column budget with a provenance column is genuinely tabular. Flagging it rather
  than deciding it.
- Write `&mdash;`, `&ldquo;`, `&rdquo;` as entities, not literal characters. The `--` in
  this draft is markdown convention and must be converted, not pasted.
- **No UTM parameters on on-site links.** UTMs are a campaign and social convention for
  inbound traffic; the approved outbound pattern in `2026-08-14-art-cull.json` puts no UTM
  on the Manifund link at all.
- This would be **the first reader-visible mention of Manifund anywhere on the site.**
  There is currently exactly one occurrence in `public/`, inside an HTML comment. Adding
  it to `navigation.js` is a separate decision.

```json
{
  "_facts_this_copy_must_not_break": [
    {
      "id": "manifund-figures-move",
      "constraint": "Do not type the raised total or the days remaining into copy. Both move daily and a stale number is worse than none. Link the page and let it resolve, or say 'the minimum' without a figure.",
      "verify": "durable",
      "why_durable": "An editorial rule about what not to write. It asserts nothing about the world.",
      "note": "The deadline 2026-09-09 and the $14,500 minimum and $48,000 goal are stable and MAY be typed. The raised figure and the day count may not. Inherited verbatim from 2026-08-14-art-cull.json; if it is edited there, edit it here."
    },
    {
      "id": "nobody-has-been-engaged",
      "constraint": "Do NOT say any artist, illustrator, developer or contractor has been hired, commissioned, approached, quoted or engaged. None has. Every figure describes what the money WOULD pay for. The correct tense is conditional throughout; a single slip into the past tense turns this page into a misrepresentation.",
      "verify": "human",
      "why_not_machine": "A claim about commercial arrangements that do not exist. The absence of a contract is not recorded anywhere, and no machine can check that a thing has not happened.",
      "source": "https://manifund.org/projects/fund-development-of-pdoom1 -- the funding-use section lists human artists as an INTENDED use; the round has not closed and the minimum has not been met.",
      "human_verified": {
        "by": "pdoom-data seat, drafting this page",
        "on": "2026-08-15",
        "review_by": "2026-09-16",
        "note": "Widened from the art-cull file's 'no-promise-of-human-artists-yet' to cover the developer line too, because this page prices a developer as well. Review date is a week after the 2026-09-09 close, because that is the event that makes this guard either obsolete or permanent. If the round funds, rewrite this constraint rather than deleting it."
      }
    },
    {
      "id": "no-invented-rates",
      "constraint": "Every dollar figure on this page must either (a) trace to the line-item derivation published in pdoom1 docs/copy/MANIFUND_SUBMITTED_2026-07-29.md, or (b) trace to a measured receipt cited inline, or (c) be marked 'needs a quote' with the thing that would settle it named. No fourth category. Do not replace a 'needs a quote' with a plausible number to make the table look finished.",
      "verify": "durable",
      "why_durable": "A rule about the provenance of the page's own numbers. It asserts nothing about the world that could change.",
      "note": "The whole conversion argument here is legibility. A confident fabricated rate destroys more credibility than an admitted gap, because a funder who has commissioned illustration before will know the fabricated one on sight."
    },
    {
      "id": "the-art-counts",
      "constraint": "470 assets, 23 minutes, 274 discarded. Quote 470 as 'about 470'; the verdict counts are exact as verified. Do not round any of them upward for effect.",
      "verify": "human",
      "why_not_machine": "The evidence lives in a DIFFERENT REPO. pdoom1 tools/art_review/review_log.jsonl is not vendored here and this site is a read-only consumer of pdoom1's outputs. Vendoring a copy makes it a variant on the next append (coordination#15).",
      "source": "pdoom1 tools/art_review/review_log.jsonl, session 2026-08-14T12:01:55Z to 12:25:00Z; corroborated by pdoom1 docs/art/audit_2026-08-13/SESSION_2026-08-14_first-mass-review.md.",
      "human_verified": {
        "by": "pdoom-data seat",
        "on": "2026-08-15",
        "review_by": "2026-09-09",
        "note": "SHORT CLOCK, AND IT HAS ALREADY EXPIRED ONCE. The art-cull campaign verified 274 discard / 197 keep over 472 assets at commit 63c9d637. A fresh recount at today's working tree gives 275 discard / 199 keep / 1 remix / 1 shelf over 476 assets, excluding two self-test rows. The log is append-only, so it moved by four assets in a day. This page therefore quotes the 2026-08-14 SESSION as a closed event -- 470 judged, 274 discarded, 23 minutes -- and does not quote a running total. Recount before publication. Also note: 'notes written' is NOT quoted anywhere on this page, because the art-cull file says 320 and the pdoom1 session record says 62 in his own words plus 246 auto-generated, which is 308. Two sources disagree, so the number is omitted rather than picked."
      }
    },
    {
      "id": "slots-not-discards",
      "constraint": "274 discards is NOT 274 things that need drawing, and this page must never let a reader think it is. The session was a selection sweep: multiple versions of one slot competed and the losers were discarded. The 476 judged assets resolve to 206 distinct slots, of which 199 came out with a surviving pick and 5 came out with nothing. Price a human art pass against slots, not against discards.",
      "verify": "human",
      "why_not_machine": "Same cross-repo boundary as the-art-counts; and the slot decomposition depends on the asset-id convention 'gen:<block>:<slot>:v<N>' holding, which is a pdoom1 tooling convention, not a fact this site can assert.",
      "source": "pdoom1 tools/art_review/review_log.jsonl. Recompute with: strip the trailing ':v<N>' from each asset id carrying a final verdict, count distinct remainders, then count those with no 'keep' among their versions. Version-per-slot histogram at recount: 22 slots x1, 127 x2, 28 x3, 29 x4.",
      "human_verified": {
        "by": "pdoom-data seat",
        "on": "2026-08-15",
        "review_by": "2026-09-09",
        "note": "This is the correction that changes the budget argument, and it was found the way CLAUDE.md says these things get found: by cross-checking two numbers that should have agreed. 199 slots have at least one keep and there are exactly 199 keeps, i.e. precisely one survivor per surviving slot -- which is the signature of a best-of-N selection sweep, exactly as pdoom1 docs/art/ART_PRODUCTION_PLAN.md briefed it. A page that had quoted '274 assets to replace' would have overstated the art bill by roughly 1.3x and been wrong in a way an art director would spot immediately."
      }
    },
    {
      "id": "kept-is-not-final",
      "constraint": "A 'keep' means survived this batch, not approved as final art. Do not describe the kept assets as the finished look, and do not imply the game's art is settled at either funding tier.",
      "verify": "human",
      "why_not_machine": "The distinction between 'survived this batch' and 'approved as final' lives in the review vocabulary's intent, not in the data; both render as the string 'keep'.",
      "source": "pdoom1 tools/art_review/ review vocabulary: keep / discard / remix / shelf. Verdicts were reversed mid-session on 15 assets, which is what makes keep a survival verdict rather than a sign-off.",
      "human_verified": {
        "by": "pdoom-data seat",
        "on": "2026-08-15",
        "review_by": "2026-10-31",
        "note": "Inherited from 2026-08-14-art-cull.json. Load-bearing here in a way it was not there: this page argues that generated art is a placeholder, and that argument collapses if the copy elsewhere treats the survivors as final."
      }
    },
    {
      "id": "dataset-counts-move",
      "constraint": "The served dataset counts are a snapshot with a date attached, and must be written as one. Say 'as at 2026-08-15' or say 'about'. Do not present them as a standing figure.",
      "verify": "human",
      "why_not_machine": "The collections live in pdoom-data/data/serveable/api/ and are not vendored here.",
      "source": "pdoom-data data/serveable/api/. Counted 2026-08-15: 1,194 timeline events (1,132 carrying an arXiv source, 989 with a description under 60 characters, 801 whose description begins with the literal section heading 'Introduction'); 3,434 candidates; 518 reviewed rows; 46 frontier labs.",
      "human_verified": {
        "by": "pdoom-data seat",
        "on": "2026-08-15",
        "review_by": "2026-11-15",
        "note": "Counted directly from the served files, not taken from pdoom-data/CLAUDE.md, which is stale: it states 140 reviewed rows where the file now holds 518. That is the same stale-copy failure this page's own guard block is designed against, and it was caught by counting rather than by reading."
      }
    },
    {
      "id": "quoting-austin",
      "constraint": "Do not quote or name the project's first backer, and do not identify him by description ('the first person to back this', 'my only donor'), without asking him first. The body copy is written to reference the criticism WITHOUT referencing the person; a stronger variant that does reference him is held in _optional_lines_pip_should_rule_on and is blocked on the ask.",
      "verify": "human",
      "why_not_machine": "Whether a courtesy has been extended to a named person is a fact about a conversation. It exists in an inbox, not in any repo.",
      "source": "https://manifund.org/projects/fund-development-of-pdoom1 comment thread. Inherited from 2026-08-14-art-cull.json, which records the same guard as live and blocking on its A-variant.",
      "human_verified": {
        "by": "pdoom-data seat",
        "on": "2026-08-15",
        "review_by": "2026-09-09",
        "note": "STILL NOT ASKED as at this drafting, per the art-cull file. Widened here to cover identification by description, because an earlier draft of this page said 'the first person to back this project told me it looks a little too AI-generated' -- which names nobody but identifies one specific person to anyone who has read the comment thread, and so trips the guard in substance while passing it on a word search. Body copy now says only that the criticism was made, not who made it. His comment is public, so quoting is permissible once asked; asking costs one message and buys goodwill from the only donor this project has."
      }
    },
    {
      "id": "the-game-stays-free",
      "constraint": "Do not imply that funding buys a commercial product, a paid release, a storefront listing or early access. The site already publishes 'Free, source-available, non-commercial' in three places, and a funding page that reads as pre-selling something would contradict them.",
      "verify": "human",
      "why_not_machine": "It is a consistency constraint across hand-written prose on other pages, which no verifier here reads; the closest mechanism is scripts/snapshot-copy.py --check, which is advisory rather than a gate.",
      "source": "public/press/index.html factsheet 'Price: Free, source-available, non-commercial' and lines stating 'the game is free, so you already have a copy'; public/about/index.html 'Free to play' and 'Free, source-available, early alpha'.",
      "human_verified": {
        "by": "pdoom-data seat",
        "on": "2026-08-15",
        "review_by": "2026-11-15",
        "note": "Checked against public/press/index.html and public/about/index.html on 2026-08-15. The draft now states the free position positively rather than merely avoiding the contradiction, because a funder reading a budget will otherwise assume the money is buying a product to sell."
      }
    },
    {
      "id": "the-min-column-does-not-sum-to-the-minimum",
      "constraint": "The published minimum-tier line items sum to $14,000, and the published minimum is $14,500. Do not close that $500 gap by inventing or inflating a line item. Say it out loud instead.",
      "verify": "durable",
      "why_durable": "An instruction about how to handle a discrepancy in an already-published document. The discrepancy is fixed in the historical record and cannot change.",
      "source": "pdoom1 docs/copy/MANIFUND_SUBMITTED_2026-07-29.md section 3, line-item derivation table: totals given as '~$14,000' min and '~$48,000' max against published figures of $14,500 and $48,000.",
      "note": "Naming the gap is worth more than hiding it. A reader who adds the column up and finds it short by $500 with no acknowledgement concludes the whole table was reverse-engineered from the ask; a reader who finds the gap already flagged concludes the opposite."
    }
  ],
  "_optional_lines_pip_should_rule_on": [
    "OPEN: whether to publish the state of the open dataset this frankly -- that 989 of 1,194 event descriptions are under 60 characters and 801 of them literally begin 'Introduction', because they came in as a bulk arXiv import and were never parsed. It is the single most concrete thing on the page and it is self-criticism on a fundraising page. The argument for keeping it: it converts 'dataset maintenance' from a category into a job with a visible size. The argument against: it invites 'so what am I funding, a broken dataset'. Draft keeps it.",
    "OPEN: whether to publish the fact that the human-artist line sits entirely above the minimum, i.e. that at $14,500 nothing is commissioned. It is true, it is the honest answer to the only public criticism the project has had, and it is also the strongest possible argument for funding above the floor. Draft keeps it and leads the second tier with it.",
    "OPEN: the priority order proposed for money between $14,500 and $48,000 -- art pass first, then developer, then community -- is the drafter's proposal, not Pip's ruling. It reverses the order the published derivation implies by size (developer $20,000 vs art $6,000). Rationale: the art is the criticism on record. Pip to rule before publication.",
    "BLOCKED ON ASKING AUSTIN: the stronger version of the second-tier paragraph replaces 'the only public criticism this project has had is that the art looks too AI-generated' with 'the first person to back this project also told me it looks a little too AI-generated'. It is materially stronger -- it makes the criticism specific, sourced and generous rather than abstract -- and it is the same trade the art-cull file's linkedin_variant_A makes. Do not use it until he has been asked; the ask covers both files at once.",
    "OPEN: whether to ask Manifund what the platform takes, and whether to publish the answer. The min column already lands $500 under the minimum; if there is a fee on top, the gap is larger and a funder will find it before Pip does.",
    "RESOLVED IN DRAFT: no artist day rate, no developer day rate and no hosting figure was invented. FOUR of the seven line items are marked 'needs a quote' with the settling artefact named -- hosting and infrastructure, the part-time developer, the directed art pass, and community support (which needs a definition before it can need a quote). A fifth unknown sits outside the table: whether Manifund takes a platform cut. Of the remaining three lines, one is backed by receipts and two are Pip's own labour at his own rate."
  ]
}
```

---

# What the money is for

p(Doom)1 is asking for a minimum of $14,500 on Manifund, and the round closes on
9 September. It is all-or-nothing: if the minimum is not reached, every pledge is
returned and nobody is out of pocket, including anyone who has already pledged.
That structure is why this page exists. A pledge costs nothing unless the thing works,
so the only sensible thing I can offer in return for one is a clear account of what
the money would buy; and the honest version of that account has gaps in it, which I
have left in rather than filled.

The current live figures -- what has been raised, how many days are left -- are on the
[Manifund page](https://manifund.org/projects/fund-development-of-pdoom1). They are
deliberately not typed here, because a number that moves daily on a page that does not
is worse than no number at all.

## The two numbers, and what each one changes

There are two thresholds and they buy genuinely different things; the difference is
not scale, it is who does the work. Neither buys a product to sell you; the game is free
and source-available and stays that way, so a pledge funds the work, not a licence.

**At $14,500, the project does not stop.** That is the whole of it, and I would rather
say so plainly than dress it up. The minimum covers twelve months of hosting and
infrastructure, the generation and tooling budget, keeping the open historical dataset
current, and partial recovery of roughly one focused day a week of my own time for a
year. Nobody else is paid anything. The game keeps shipping monthly on the cadence it
is already on; the dataset stays maintained rather than drifting; and the art continues
to improve the way it improved on 14 August, which is to say by generating a great deal
of it, throwing most of it away, and writing down why. That is a real answer to the art
problem but it is not the answer people mean when they ask about it -- it is one person
with a mouse applying taste to a generator, faster and more ruthlessly than before.

**At $48,000, somebody other than me draws it.** The goal adds a part-time gameplay
developer for around six months, a directed art pass by a human illustrator working
from a written brief, community support, and dataset maintenance on a schedule instead
of in the gaps. The important thing to be straight about is where the line falls: **the
human-artist money sits entirely above the minimum.** At $14,500 nothing is commissioned
and nobody is engaged. I could have spread that line across both columns to make the
floor look better and I have not, because the only public criticism this project has had
is that the art looks too AI-generated, and answering that with a budget that quietly
defers the answer would be worse than not answering at all.

Between the two, every dollar is real -- this is a range, not a switch. My proposal for
the order in which money above the floor gets spent is: the directed art pass first,
because it is the criticism actually on record; then developer time; then community
support. That ordering is a proposal and not yet a ruling, and it deliberately puts the
smaller line ahead of the larger one.

## The line items, and how each number is known

This is the derivation the ask was built from, published on 29 July, with a column added
saying how far I can defend each figure. There are seven lines. Exactly one of them is
backed by receipts; four are marked "needs a quote", with the thing that would settle
each one named; and two are my own labour priced at my own rate, which is a decision I
made rather than a price anybody quoted me.

| Line item | Minimum | Goal | How the number is known |
|---|---|---|---|
| Hosting and infrastructure, 12 months | $900 | $1,500 | **Needs a quote.** No first-party invoice exists in any repo I keep. The only written figures are Plausible cloud analytics at $9/month and an archived note reading "DreamHost $5-15/month". Settled by: twelve months of DreamHost and domain-registrar invoices plus the current analytics plan. |
| Asset generation and tooling | $1,100 | $2,500 | **Measured, and the only fully defensible line.** Image generation runs $0.06 to $0.36 per image depending on size and quality; July 2026 came to $15.78 across 62 logged images. The sprite pipeline is a subscription carrying a 2,000-generation monthly pool at about $12/month -- that last figure read off third-party pricing rather than an invoice, so treat it as the softest number in this row -- which works out near $0.006 a generation. Dollars are not the constraint here; review time is. |
| Open dataset maintenance, 12 months | $3,000 | $4,000 | Derived from my own day rate below, not from a quote. It is my labour priced as my labour. |
| My time, partial recovery | $9,000 | $12,000 | One focused day a week for twelve months. $9,000 across that prices the day at about $170, which is well under what the operations and governance work I do commands. That is deliberate and I would rather a funder notice it than not. |
| Part-time gameplay developer, ~6 months | -- | $20,000 | **Needs a quote.** No developer has been engaged and no rate has been agreed. $20,000 over six months is a placeholder I wrote to size the ask. Settled by: two or three actual rate conversations with people who would plausibly do the work. |
| Directed art pass, human illustrator | -- | $6,000 | **Needs a quote.** No illustrator has been engaged and no rate card obtained. Settled by: quotes taken against the written brief and the slot count in the next section. See the division I do below, because I do not think this number survives contact with a real rate. |
| Community support | -- | $2,000 | **Needs a definition before it needs a quote.** Chat and forum hosting for a project this size is close to free, so this line is either moderation time, events, or nothing. I have not decided which, and pricing it before deciding would be inventing a number. |
| **Total** | **$14,000** | **$48,000** | |

The minimum column sums to $14,000 and the published minimum is $14,500. That $500 is
rounding from the evening I set the figure, not a hidden line item, and I would rather
flag it than retrofit something to close it. There is also a question I have not asked
yet and should: whether the platform takes a cut, because if it does then the gap is
larger than $500 and it is better that I find that out than that a funder does.

## The size of the art problem, measured rather than gestured at

On 14 August I sat down with the generated art and judged about 470 assets in 23
minutes -- one decision roughly every three seconds -- and discarded 274 of them. That
is the measurement the art line should be priced against, but it needs one correction
before it can be, and the correction cuts the number down rather than up.

**274 discards is not 274 things that need drawing.** The session was a selection
sweep: several versions of the same slot competed against each other and the losers were
discarded, which is what the process is supposed to do. Decomposed properly, those
judgements resolve to **206 distinct art slots**; 199 of them came out with a surviving
pick and **5 came out with nothing worth keeping at all**. Most slots had two candidates,
a good number had three or four, and exactly one survivor emerged per surviving slot.
Anyone pricing a human art pass should price 206 slots, not 274 discards, and I would
rather publish that correction than quote the bigger number that flatters the ask.

The slots break down into roughly 84 interface and action icons, about 53 hero banners,
key art and screen backgrounds, 12 researcher portraits, and a tail of smaller sets.
The hero surfaces are the ones a stranger sees first and they are also where the sweep
was harshest: 73 hero candidates were judged and 19 kept. Beyond the reviewed slice
there is a much larger unjudged estate -- 2,099 distinct image families, roughly 7.8 GB
of image variants, of which about two-thirds now carry a verdict and 708 do not.

Now the division, which is the part I would want to see if I were reading somebody
else's budget. $6,000 across 206 slots is about $29 a slot; I do not believe that is a
real rate for commissioned illustration and I am not going to pretend otherwise. The
shape I think the money actually buys is narrower and more useful: a style bible and a
directed pass over the surfaces that set the tone -- call it the 53 hero and background
slots, which works out nearer $113 each -- with the icon set regenerated against that
direction rather than drawn by hand. That is a hypothesis about what an illustrator
would say, not a plan an illustrator has agreed to, and it is precisely what a quote
would settle.

## What an artist would actually be handed

The thing that makes this a proposal rather than a wish is that the brief already
exists, and it was not written for a funding page. While judging, I typed direction as
I went, uncorrected, at about three seconds an asset:

> "one red team one blue team, combat, not chess, can be engineers facing each other off"

> "Not a lock. try a more symbolic reprsentation in the abstract. Consider an alien
> culture's represetion of safe from boba principles."

> "this si danerously close to a mtg symbol. think about better repersentaiton for
> emotinal burnout"

> "silhouette too boviously male, too obviously signalling Operator"

That last one I wrote four separate times, against four versions of the same founder
banner, and one of the four I kept anyway. That is not a rendering fault a better model
fixes; it is a design problem the generator had no way of knowing it had. An illustrator
would be handed those notes, a locked style already validated over two rounds, a palette,
and a numbered list of slots -- not a vague instruction to make it look less
AI-generated. Generated art is a fast way to find out what you actually want, and the
finding-out is done by throwing most of it away and being able to say why. The taste is
the part that does not come out of a model; the money is for handing that taste to
somebody who can draw.

## What dataset maintenance means, concretely

The open historical dataset is the part of this project most likely to outlive the game,
and it is also the part where I can be most specific about what is wrong with it. As at
15 August it serves 1,194 timeline events, 3,434 candidate records, 518 human-reviewed
rows and 46 frontier labs, all with sources attached and all free for anyone to use.

It is also, in one specific respect, not finished. Of those 1,194 events, 1,132 carry an
arXiv source and came in through a bulk import whose descriptions were never parsed into
anything a person would recognise as a description: 989 of the 1,194
have a description under sixty characters, and 801 of them begin with the literal
section heading "Introduction". They are real papers with real sources and real dates;
what they do not have is a sentence a human wrote saying why the paper matters. Turning
1,132 rows of unparsed heading text into described, dated, sourced events is a
well-defined job of known size, and it is what the dataset line pays for. I would rather
show you the defect than the collection count.

## Nobody has been hired

No artist, illustrator, developer or contractor has been engaged, commissioned or
contracted for this project, and no rate has been quoted or agreed with anyone. Every
figure on this page describes what the money would pay for if the round closes. I have
put a fair amount of my own time and a few thousand dollars of my own savings into this
over the past year, and nothing else has been spent on it.

## If it does not fund

Then the pledges return, nobody loses anything, and I keep going at the rate I have been
going at -- which is one to two focused days a week, a release most months, and an art
process that consists of generating a lot and discarding most of it. The game does not
stop; it just stays a thing done in the gaps, and the dataset stays a thing maintained
in the gaps, and somebody other than me does not get to draw it. That is a real outcome
and not a catastrophic one, and I would rather say so than manufacture an emergency.

The round closes 9 September and it is all-or-nothing at $14,500. A pledge costs nothing
unless it works.

[Back it on Manifund](https://manifund.org/projects/fund-development-of-pdoom1) --
[play it](https://pdoom1.com/)
