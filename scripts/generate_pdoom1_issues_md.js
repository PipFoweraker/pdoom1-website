#!/usr/bin/env node
/**
 * Generate Markdown listing of open issues from the main game repo (PipFoweraker/pdoom1).
 * Writes to public/docs/pdoom1-open-issues.md
 * Requires GitHub CLI (gh) authenticated.
 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO = process.env.SOURCE_REPO || 'PipFoweraker/pdoom1';
const OUT = path.join(__dirname, '..', 'public', 'docs', 'pdoom1-open-issues.md');

function runGh(args) {
  try {
    const out = execFileSync('gh', args, { encoding: 'utf8' });
    return out;
  } catch (e) {
    const msg = e.stderr?.toString?.() || e.message;
    console.error('gh failed:', msg);
    process.exit(1);
  }
}

function toMd(issues) {
  const ts = new Date().toISOString();
  let md = '';
  md += `# Open Issues from ${REPO}\n\n`;
  md += `Generated: ${ts} UTC\n\n`;
  if (!issues.length) {
    md += '_No open issues found._\n';
    return md;
  }
  md += `| # | Title | Labels | Milestone | Updated | Link |\n`;
  md += `|---:|-------|--------|-----------|---------|------|\n`;
  for (const it of issues) {
    const num = it.number;
    const title = it.title.replace(/\|/g, '\\|');
    const labels = (it.labels || []).map(l => l.name).join(', ').replace(/\|/g, '\\|');
    const ms = it.milestone?.title ? it.milestone.title.replace(/\|/g, '\\|') : '';
    const updated = (it.updatedAt || '').replace('T', ' ').replace('Z', '');
    const link = it.url;
    md += `| ${num} | ${title} | ${labels} | ${ms} | ${updated} | [link](${link}) |\n`;
  }
  // Use backticks in Markdown without breaking this template string
  md += `\n\n---\nSource: \`${REPO}\` via GitHub CLI.\n`;
  return md;
}

function main() {
  const json = runGh(['issue', 'list', '-R', REPO, '--state', 'open', '-L', '200', '--json', 'number,title,url,labels,assignees,milestone,updatedAt']);
  let issues = [];
  try {
    issues = JSON.parse(json);
  } catch (e) {
    console.error('Failed to parse gh JSON:', e.message);
    process.exit(1);
  }
  const md = toMd(issues);
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, md, 'utf8');
  console.log('Wrote', OUT);
}

main();
