# Jira export

This repo **produces a payload**; it does not write to Jira. The coordination seat
holds the only verified Atlassian connection (`pipfoweraker.atlassian.net`,
project key `PDOOM`, checked writable 2026-08-10). Neither half works alone — this
seat knows what its issues mean, that seat is the one that can create them.

## Regenerate before any import

```
gh issue list --repo PipFoweraker/pdoom1-website --state open --limit 1000 \
  --json number,title,url,labels,createdAt,updatedAt > /tmp/issues.json
python scripts/build-jira-export.py /tmp/issues.json docs/jira/export_$(date +%F).jsonl
```

A committed payload is a **dated snapshot and it rots** — issues open and close
daily. Treat any file here as evidence of what was true on its date, not as the
current state. Regenerate rather than reusing one.

## The exporter refuses rather than guessing

Every open issue must appear in the `C` table in `scripts/build-jira-export.py`
with an epic, a tier, and a one-sentence `why`. There is no default branch,
because a default would silently mislabel the issues the classifier understands
least — which are exactly the ones a human most needs flagged.

Run it against an issue set containing anything unclassified and it exits with:

```
REFUSING: no classification for [...]. Classify them or the export lies by omission.
```

That refusal is the point, and it is cited as worked precedent A2 in
`docs/decisions/ADR-0002-designing-guards-that-can-fail.md`. **It also means
staleness is self-announcing:** this export sat unused for eleven days, and the
only cost was that eight new issues had to be classified before it would run
again. It could not have quietly shipped an incomplete payload.

## The vocabulary

Nine epics, and no others without a deliberate decision to add one:

`content-honesty` · `site-design-and-copy` · `rulings-inbox` ·
`architecture-and-adrs` · `board-and-league` · `release-pipeline` ·
`grant-readiness` · `community-and-comms` · `infra-and-security`

Three tiers, calibrated from the original classification pass:

| tier | means |
|---|---|
| 1 | wrong **right now**, with a visitor or data consequence |
| 2 | real work, not currently breaking |
| 3 | context, a reminder, or thinking recorded rather than instructed |

## History

The original pass (`103ad8b6`, 2026-08-10) classified 51 open issues in response
to Pip's ask — *"I want to start shoving the work from all the PDoom repos up into
JIRA … by like 4pm"* — and was announced ready in `coordination#58`. Sibling
exports were produced the same afternoon by `pdoom1` (209 issues,
`coordination#55`) and `pdoom-data` (39 issues, `coordination#53`). **None of the
three was ever written to Jira**; all three notices still carry zero comments.
Nothing was declined — the handoff simply stopped, and this repo cannot tell you
why, because the next step happens somewhere git cannot see.
