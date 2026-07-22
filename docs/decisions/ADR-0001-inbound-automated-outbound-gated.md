# ADR-0001 — Inbound automated, outbound human-gated

- **Status:** ACCEPTED (Pip, 2026-07-23)
- **Applies to:** every automated path that moves content into or out of this repo

## Context

This repo sits between several systems. Content flows **in** from the pdoom1
game repo (versions, docs, design notes, dev blog) and from pdoom-data (events),
and flows **out** to the public web and, potentially, to social platforms.

Those two directions have completely different failure costs, and the repo had
been treating them the same.

An inbound sync that goes wrong publishes something stale or malformed to a page
we control. It is embarrassing, it is visible, and it is fixable by pushing a
correction — the blast radius is a URL.

An outbound post that goes wrong is unrecoverable. It has the project's name on
it, it lands in other people's feeds, it gets screenshotted, and a deletion is
itself a visible event. The blast radius is reputation.

The previous `syndicate-content.yml` did not make this distinction: it fired on
every push to `main` touching a blog file and posted automatically. It also
re-implemented its copy formatting inline in bash rather than calling the
project's own formatter, so two divergent implementations existed and the one
that would actually have run leaked its own YAML indentation into the post body.
The endpoints it called had no authentication at all.

Pip's framing, which this record exists to preserve:

> I think I want synchs in to be automated but publishing out to be human
> decision gated — system can get it ready for me, but I need to own all words
> pointing out into the world for final edits on tone and content and to catch
> errors, or at least make them my responsibility.

The last clause is the load-bearing one. This is not only about catching
mistakes. It is about **who is answerable** for the words.

## Decision

**Inbound automation is unrestricted. Outbound publication requires an explicit,
recorded human approval.**

Concretely, for anything that posts outside pdoom1.com:

1. Automation may **prepare** copy, and should. Drafting is genuine work and
   there is no reason a person should start from a blank page.
2. The draft is written to a **committed file** (`content/syndication/<slug>.json`)
   carrying `approved: false`.
3. A human edits the words and sets `approved: true`. This is the gate.
4. Posting happens only on a **manual trigger**, defaults to a dry run, and
   sends *exactly* the text in the file — the posting step never composes copy.
5. `posted_at` is written back, so a re-run cannot double-post.

## Consequences

**Git history becomes the audit trail.** Every outbound message exists as a
committed file with an author and a timestamp. "What did we say, when, and who
approved it" is answerable by `git log`, not by memory.

**The system can never surprise its owner in public.** The strongest property
here is not that mistakes get caught — it is that there is no code path from an
automated event to a public post. Approval is structural, not procedural.

**Drafting stays automated**, so the gate costs a review, not authorship.

**A cost, stated honestly:** posts will sometimes go out late, or not at all,
because a human did not get to them. That is accepted. Nothing outbound here is
time-critical, and a missed post is cheaper than a wrong one.

**This is not a security control.** It is an editorial one. The security control
is separate: the endpoints now require a shared secret (`SYNDICATION_TOKEN`),
fail closed when unconfigured, and are covered by
`scripts/test-syndication-auth.js`. Before that, any unauthenticated POST to a
publicly-discoverable URL would have posted to the project's accounts the moment
a credential was set.

## Scope boundary

"Outbound" means **content addressed to people outside the project on platforms
we do not control**: social posts, newsletters, anything pushed into a feed.

It does **not** mean deploying the website. Deploying is inbound-shaped — the
content is already reviewed in a PR, the destination is ours, and a correction
is one push away. `auto-deploy-on-push.yml` stays automatic.

RSS/Atom feeds also stay automatic. A feed is *pull*, not push: nothing arrives
in anyone's attention because we generated a file, and the content is the blog
post that was already reviewed.

## Rejected alternatives

- **Auto-post with a delay and a cancel window.** Rejected: it makes silence the
  approval, which is exactly backwards. The default must be "not sent".
- **Approve via a GitHub issue comment or a label.** Rejected: the copy would
  live in a comment thread rather than a reviewable file, and editing wording
  would mean re-typing it rather than amending it.
- **Approve in a PR review.** Closer, and workable — but it couples publishing
  cadence to merge cadence, and the words often want changing after the post has
  already merged.

## Open questions

- Should approving copy for one platform imply approval for the others? Today
  it is per-draft, not per-platform. Per-platform would be finer but adds state.
- No "unpublish" path exists. If something goes out wrongly, deletion is manual
  on each platform. Worth building only if it ever happens.
