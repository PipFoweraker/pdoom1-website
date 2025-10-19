#!/usr/bin/env node
/**
 * Generate Markdown listing of open issues from the main game repo (PipFoweraker/pdoom1).
 * Writes to public/docs/pdoom1-open-issues.md
 * Requires GitHub CLI (gh) authenticated OR set SOURCE_REPO to an accessible repo.
 *
 * Improvements:
 *  - checks for `gh` availability
 *  - clearer error messages
 *  - atomic write (temp -> rename)
 *  - defensive JSON parsing
 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO = process.env.SOURCE_REPO || 'PipFoweraker/pdoom1';
const OUT = path.join(__dirname, '..', 'public', 'docs', 'pdoom1-open-issues.md');

// Run a command and return stdout string, throw Error with useful message on failure.
function runGh(args) {
  try {
    // quick check `gh` exists when first invoked; execFileSync will throw if it's missing
    return execFileSync('gh', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (err) {
    const msg = err && err.stderr ? err.stderr.toString().trim() : String(err);
    throw new Error(`Failed to run "gh ${args.join(' ')}": ${msg}`);
  }
}

function toMd(issues) {
  const ts = new Date().toISOString();
  let md = '';
  md += `# Open Issues from ${REPO}\n\n`;
  md += `Generated: ${ts} UTC\n\n`;
  if (!issues || !issues.length) {
    md += '_No open issues found._\n';
    return md;
  }
  md += `| # | Title | Labels | Milestone | Updated | Link |\n`;
  md += `|---:|-------|--------|-----------|---------|------|\n`;
  for (const it of issues) {
    const num = it.number;
    const title = (it.title || '').replace(/\|/g, '\\|');
    const labels = (it.labels || []).map(l => l.name).join(', ').replace(/\|/g, '\\|');
    const ms = it.milestone?.title ? it.milestone.title.replace(/\|/g, '\\|') : '';
    const updated = (it.updatedAt || '').replace('T', ' ').replace('Z', '');
    const link = it.url || '';
    md += `| ${num} | ${title} | ${labels} | ${ms} | ${updated} | [link](${link}) |\n`;
  }
  md += `\n\n---\nSource: \`${REPO}\` via GitHub CLI.\n`;
  return md;
}

function atomicWrite(filePath, content) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(dir, `.tmp-${Date.now()}.md`);
  fs.writeFileSync(tmp, content, 'utf8');
  fs.renameSync(tmp, filePath);
}

function main() {
  // Try to fetch a reasonable number of issues; adjust or page if you have more than 500.
  const args = ['issue', 'list', '-R', REPO, '--state', 'open', '-L', '500', '--json', 'number,title,url,labels,assignees,milestone,updatedAt'];
  let json = '';
  try {
    json = runGh(args);
  } catch (e) {
    console.error('Error fetching issues:', e.message);
    process.exit(1);
  }

  let issues = [];
  try {
    issues = JSON.parse(json);
  } catch (e) {
    console.error('Failed to parse gh JSON:', e.message);
    console.error('Raw output (truncated):', (json || '').slice(0, 2000));
    process.exit(1);
  }

  const md = toMd(issues);
  try {
    atomicWrite(OUT, md);
    console.log('Wrote', OUT);
  } catch (e) {
    console.error('Failed to write output file:', e.message);
    process.exit(1);
  }
}

main();
