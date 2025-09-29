#!/usr/bin/env node
/**
 * Generate Roadmap from GitHub milestones and issues from the main game repo (PipFoweraker/pdoom1).
 * Writes to docs/roadmap.md
 * Requires GitHub CLI (gh) authenticated.
 * 
 * This script maintains the roadmap in sync with GitHub milestones while preserving
 * the existing manual roadmap structure as fallback.
 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO = process.env.SOURCE_REPO || 'PipFoweraker/pdoom1';
const OUT = path.join(__dirname, '..', 'docs', 'roadmap.md');
const FALLBACK_ROADMAP = path.join(__dirname, '..', 'docs', 'roadmap.md.backup');

function runGh(args) {
  try {
    const out = execFileSync('gh', args, { encoding: 'utf8' });
    return out;
  } catch (e) {
    const msg = e.stderr?.toString?.() || e.message;
    console.error('gh failed:', msg);
    return null;
  }
}

function createBackup() {
  // Create backup of current roadmap if it exists
  if (fs.existsSync(OUT)) {
    fs.copyFileSync(OUT, FALLBACK_ROADMAP);
    console.log('Created backup:', FALLBACK_ROADMAP);
  }
}

function restoreFromBackup() {
  if (fs.existsSync(FALLBACK_ROADMAP)) {
    fs.copyFileSync(FALLBACK_ROADMAP, OUT);
    console.log('Restored roadmap from backup due to GitHub API failure');
  }
}

function getMilestones() {
  // Use GitHub API directly since gh milestone command may not be available
  const json = runGh(['api', '-H', 'Accept: application/vnd.github.v3+json', `/repos/${REPO}/milestones?state=all`]);
  if (!json) return null;
  
  try {
    return JSON.parse(json);
  } catch (e) {
    console.error('Failed to parse milestones JSON:', e.message);
    return null;
  }
}

function getIssuesForMilestone(milestoneNumber) {
  // Use GitHub API to get issues for a specific milestone
  const json = runGh(['api', '-H', 'Accept: application/vnd.github.v3+json', `/repos/${REPO}/issues?milestone=${milestoneNumber}&state=all`]);
  if (!json) return [];
  
  try {
    return JSON.parse(json);
  } catch (e) {
    console.error('Failed to parse issues JSON for milestone:', milestoneNumber);
    return [];
  }
}

function generateMilestoneSection(milestone) {
  let section = `\n## ${milestone.title}\n`;
  
  if (milestone.description) {
    section += `\n${milestone.description}\n`;
  }
  
  if (milestone.due_on) {
    const dueDate = new Date(milestone.due_on).toLocaleDateString();
    section += `\n**Target Date:** ${dueDate}\n`;
  }
  
  section += `\n**Status:** ${milestone.state === 'open' ? 'In Progress' : 'Completed'}\n`;
  
  // Get issues for this milestone
  const issues = getIssuesForMilestone(milestone.number);
  if (issues.length > 0) {
    const openIssues = issues.filter(i => i.state === 'open');
    const closedIssues = issues.filter(i => i.state === 'closed');
    
    section += `\n**Progress:** ${closedIssues.length}/${issues.length} issues completed\n`;
    
    if (openIssues.length > 0) {
      section += `\n### Remaining Tasks\n`;
      openIssues.slice(0, 10).forEach(issue => { // Limit to 10 items
        const labels = issue.labels.map(l => l.name).join(', ');
        const labelStr = labels ? ` (${labels})` : '';
        section += `- [#${issue.number}](${issue.html_url}) ${issue.title}${labelStr}\n`;
      });
      
      if (openIssues.length > 10) {
        section += `- ... and ${openIssues.length - 10} more issues\n`;
      }
    }
  }
  
  return section;
}

function generateRoadmapFromGitHub(milestones) {
  const timestamp = new Date().toISOString();
  let roadmap = `# Roadmap\n\n`;
  roadmap += `This roadmap is automatically generated from GitHub milestones in the [${REPO}](https://github.com/${REPO}) repository and updated periodically.\n\n`;
  roadmap += `*Last updated: ${timestamp.split('T')[0]}*\n\n`;
  
  // Sort milestones by due date, then by state (open first)
  const sortedMilestones = milestones.sort((a, b) => {
    if (a.due_on && b.due_on) {
      return new Date(a.due_on) - new Date(b.due_on);
    }
    if (a.due_on && !b.due_on) return -1;
    if (!a.due_on && b.due_on) return 1;
    
    // If no due dates, sort by state (open first)
    if (a.state === 'open' && b.state === 'closed') return -1;
    if (a.state === 'closed' && b.state === 'open') return 1;
    
    return a.title.localeCompare(b.title);
  });
  
  // Generate sections for each milestone
  sortedMilestones.forEach(milestone => {
    roadmap += generateMilestoneSection(milestone);
  });
  
  // Add cross-repository notes
  roadmap += `\n## Notes\n\n`;
  roadmap += `- **Source Repository:** [${REPO}](https://github.com/${REPO}) - Game source code and primary development\n`;
  roadmap += `- **Website Repository:** [PipFoweraker/pdoom1-website](https://github.com/PipFoweraker/pdoom1-website) - This website and documentation\n`;
  roadmap += `- **Live Issues:** See [/docs/pdoom1-open-issues.md](/docs/pdoom1-open-issues.md) for current development tasks\n`;
  roadmap += `- **Releases:** [GitHub Releases](https://github.com/${REPO}/releases) for downloads until Steam launch\n\n`;
  roadmap += `*This roadmap is automatically synchronized with GitHub milestones. Manual updates should be made in the source repository.*\n`;
  
  return roadmap;
}

function generateFallbackRoadmap() {
  // Generate a roadmap that matches the original structure when GitHub is unavailable
  const timestamp = new Date().toISOString();
  let roadmap = `# Roadmap\n\n`;
  roadmap += `This roadmap is a living document. It summarizes major goals and feeds the GitHub Issues backlog for execution.\n\n`;
  
  roadmap += `## 0.0.x (Alpha) – Now\n`;
  roadmap += `- Content cadence: 2–3 dev blog posts per week\n`;
  roadmap += `- Bug intake: Netlify function -> repo dispatch -> Issues\n`;
  roadmap += `- Changelog automation from Airtable\n`;
  roadmap += `- DreamHost static hosting + Netlify API\n`;
  roadmap += `- Social syndication to Discord, Bluesky, X, LinkedIn\n\n`;
  
  roadmap += `## 0.1.0 – Website polish\n`;
  roadmap += `- Accessibility pass (ARIA, contrast, keyboard nav)\n`;
  roadmap += `- Core SEO (meta, sitemap.xml, robots.txt, OpenGraph)\n`;
  roadmap += `- Analytics (privacy-preserving)\n`;
  roadmap += `- Contact form hardening (hCaptcha optional)\n`;
  roadmap += `- Design tokens pulled from \`pdoom1\` main repo\n\n`;
  
  roadmap += `## 0.2.0 – Steam readiness\n`;
  roadmap += `- Download page reoriented to Steam store link\n`;
  roadmap += `- Press kit page (media + factsheet)\n`;
  roadmap += `- Build/version badge + release notes integration\n\n`;
  
  roadmap += `## Later\n`;
  roadmap += `- Community hub improvements (Discord widgets, issue triage)\n`;
  roadmap += `- Newsletter opt-in (double opt-in)\n`;
  roadmap += `- Localization scaffolding\n\n`;
  
  roadmap += `## Notes\n`;
  roadmap += `- Source of truth for game code and design system is the \`${REPO}\` repo. This site links there for downloads until Steam launch.\n`;
  roadmap += ` - Live backlog snapshot: see \`/docs/pdoom1-open-issues.md\` (pulled from the main repo).\n`;
  
  return roadmap;
}

function main() {
  console.log('Generating roadmap from GitHub milestones...');
  
  // Create backup of existing roadmap
  createBackup();
  
  // Try to get milestones from GitHub
  const milestones = getMilestones();
  
  let roadmapContent;
  if (milestones && milestones.length > 0) {
    console.log(`Found ${milestones.length} milestones`);
    roadmapContent = generateRoadmapFromGitHub(milestones);
  } else {
    console.log('No milestones found or GitHub API unavailable, using fallback roadmap');
    roadmapContent = generateFallbackRoadmap();
  }
  
  // Write the roadmap
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, roadmapContent, 'utf8');
  console.log('Wrote roadmap to:', OUT);
}

if (require.main === module) {
  main();
}

module.exports = { main, generateFallbackRoadmap, generateRoadmapFromGitHub };