# Workflow attention-cost audit (2026-07-16)

Solo-dev principle: **automation should conserve attention** — silent when fine, ONE
actionable alert when real. More automation is not better; *trustworthy* automation is.
Two antipatterns to hunt: (a) creating issues on success, (b) creating a *new* issue
every failing run (no de-dup).

## Findings

| Workflow | Schedule | Issue-on-success? | Failure de-dup? | Verdict |
|---|---|---|---|---|
| `weekly-league-rollover.yml` | (removed) | **YES (35 spam issues)** | n/a | ✅ Fixed 2026-07-14 (deleted; now logs to /monitoring/, `weekly-league-reset.yml` alerts only on failure) |
| `health-checks.yml` | every 6h | no | **NO → date-in-title, 4 dupes/day** | ✅ Fixed 2026-07-16 (de-dup pattern retrofitted) |
| `auto-update-data.yml` | every 6h | no | **NO** | ✅ Fixed 2026-07-16 (de-dup retrofitted) |
| `sync-leaderboards.yml` | daily | no | **NO** | ✅ Fixed 2026-07-16 (de-dup retrofitted) |
| `extract-analytics.yml` | monthly | no | **NO** | low risk (monthly), retrofit when convenient |
| `data-contract-validation.yml` | daily | no | **YES** | ✅ New; reference implementation |

**Good news:** no workflow still creates success issues (the rollover spam was the only
one, already removed). **Remaining risk:** duplicate *failure* issues from the 6-hourly
jobs that lack de-dup.

## The de-dup pattern (copy this into the remaining `if: failure()` blocks)

Fixed title (no date), search open issues by label, comment if found else create:

```js
const title = '🚨 <fixed title, no date>';
const label = 'automated-alert';
const runUrl = `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`;
const existing = await github.rest.issues.listForRepo({
  owner: context.repo.owner, repo: context.repo.repo, state: 'open', labels: label, per_page: 20 });
const found = existing.data.find(i => i.title === title);
if (found) {
  await github.rest.issues.createComment({ owner: context.repo.owner, repo: context.repo.repo,
    issue_number: found.number, body: `Still failing ${new Date().toUTCString()}. ${runUrl}` });
} else {
  await github.rest.issues.create({ owner: context.repo.owner, repo: context.repo.repo,
    title, body: `Failing. Run: ${runUrl}`, labels: ['automated-alert', 'priority:high'] });
}
```

Reference implementations: `health-checks.yml` and `data-contract-validation.yml`.

## Next
- `extract-analytics.yml` (monthly, low risk) is the only remaining non-deduped alert.
- Now that 3 workflows share the pattern, consider a shared composite action
  (`.github/actions/rolling-alert`) so de-dup is DRY rather than copy-pasted.
