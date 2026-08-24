#!/usr/bin/env node
// Assertions for scripts/syndication-helpers.js.
//
// WHY THIS FILE WAS REWRITTEN (2026-08-25)
// ----------------------------------------
// It could not fail. Measured on the version before this one:
//
//     grep -cE "process\.exit|exitCode|assert|throw " scripts/test-syndication.js
//         -> 0
//     node scripts/test-syndication.js >/dev/null 2>&1 ; echo $?
//         -> 0
//
// Every failure path was `catch (error) { console.error('X Failed:', ...) }` and
// then fell through to the next block; Test 2 printed a generated URL with no
// assertion attached to it at all; the file signed off with "All tests
// completed!" whatever had happened. It is exposed as `npm run test:syndication`,
// so the name a human types to check syndication printed a wall of ticks and
// exited 0 no matter what the module did.
//
// CLAUDE.md: "A red test in the suite is worse than no test" -- and a test that
// cannot go red is the same failure wearing the opposite mask, because it reads
// as coverage to everyone who does not open it.
//
// WHY IT WAS KEPT RATHER THAN DELETED
// -----------------------------------
// Deleting it was the other option on the table. Measured against the tree:
// the only `require()` of syndication-helpers.js anywhere under scripts/,
// netlify/ or .github/ is the one at the top of this file. (Block E's first
// draft matched the bare string instead, and flagged
// .github/workflows/syndicate-content.yml:22 -- which is a COMMENT recording
// that an older version of that workflow re-implemented the formatting in bash
// "rather than calling scripts/syndication-helpers.js". A mention is not a
// call; the tripwire matches the wiring mechanism, not the module's name.)
//
// So syndication-helpers.js has NO production consumer. The live pipeline is
// prepare-syndication.py -> post-syndication.py -> netlify/functions/, and the
// real tests (test-syndication-auth.js, test-syndication-facets.js,
// test-post-syndication.py, test-syndication-utm.py, check-syndication-docs.py)
// all cover that path. This file's unique coverage is therefore the ORPHANED
// module, and deleting the test would leave the orphan with none -- while the
// decision to delete the module itself belongs to Pip, not to this PR
// (CLAUDE.md: trace generated content back to its source before deleting it).
//
// So: real assertions, a real exit code, and a tripwire (block E) that fails on
// the day anything wires the module into production, because it carries hazards
// that the live pipeline has already been fixed for.
//
// Run: node scripts/test-syndication.js     (exit 0 = pass)

const fs = require('fs');
const path = require('path');
const helpers = require('./syndication-helpers.js');

const REPO = path.join(__dirname, '..');
let pass = 0;
let fail = 0;

function ok(name, cond, detail) {
  if (cond) {
    pass++;
    console.log('  PASS ' + name);
  } else {
    fail++;
    console.log('  FAIL ' + name + (detail ? ' -> ' + detail : ''));
  }
}

// Predicates are named and reused, so block F can run the SAME function against
// input it must reject. An assertion only inlined at its call site can never be
// shown to discriminate.
function withinLimit(content, max) {
  return typeof content === 'string' && content.length > 0 && content.length <= max;
}

function isPostQueryUrl(url, filename) {
  return typeof url === 'string'
    && url.includes('/blog/post.html?p=')
    && url.includes(encodeURIComponent(filename))
    && !url.includes('/blog/#');
}

// ---------------------------------------------------------------------------
// A. extractBlogMetadata against a real post.
// ---------------------------------------------------------------------------
console.log('\nA. extractBlogMetadata (real post)');

const FIXTURE = '2025-10-09-website-development-sprint-complete-v0-2-0.md';
const fixturePath = path.join(REPO, 'public', 'blog', FIXTURE);

ok('the fixture post still exists', fs.existsSync(fixturePath), fixturePath);

if (fs.existsSync(fixturePath)) {
  const md = helpers.extractBlogMetadata(fixturePath);

  // 'New Update' and today's date are the helper's FALLBACKS. Asserting the
  // values are merely non-empty would pass on a run where extraction returned
  // nothing but the fallbacks -- CLAUDE.md, "fallback literals are the
  // dangerous ones ... a default value ships precisely when the lookup failed."
  ok('title is extracted, not the "New Update" fallback',
    typeof md.title === 'string' && md.title.length > 0 && md.title !== 'New Update',
    JSON.stringify(md.title));
  ok('title is the post\'s own H1',
    md.title === 'Website Development Sprint Complete: v0.2.0 Major Enhancement',
    JSON.stringify(md.title));
  ok('date is ISO yyyy-mm-dd', /^\d{4}-\d{2}-\d{2}$/.test(md.date), md.date);
  ok('date is the post\'s own date, not today\'s fallback',
    md.date === '2025-10-09', md.date);
  ok('tags is a non-empty array of strings',
    Array.isArray(md.tags) && md.tags.length > 0
      && md.tags.every(t => typeof t === 'string' && t.length > 0),
    JSON.stringify(md.tags));
  ok('tags are trimmed', md.tags.every(t => t === t.trim()), JSON.stringify(md.tags));
  ok('summary is non-empty', typeof md.summary === 'string' && md.summary.length > 0);
  ok('summary honours the helper\'s own 280-char cap', md.summary.length <= 280,
    'length=' + md.summary.length);
  ok('raw content is returned', typeof md.content === 'string' && md.content.length > 0);
}

// ---------------------------------------------------------------------------
// B. A missing file must THROW. The old file caught this, printed a red cross
//    and carried on -- so a deleted fixture read as a pass.
// ---------------------------------------------------------------------------
console.log('\nB. extractBlogMetadata (missing file)');

let threw = false;
try {
  helpers.extractBlogMetadata(path.join(REPO, 'public', 'blog', '__no_such_post__.md'));
} catch (e) {
  threw = true;
}
ok('a missing post throws rather than returning fallback metadata', threw);

// ---------------------------------------------------------------------------
// C. generateBlogUrl. The helper's own comment records that the previous form
//    was `/blog/#<slug>` -- an anchor matching no element on the blog index, so
//    every syndicated link dumped the reader on the index with no indication of
//    which post was meant. Nothing asserted the fix; this does.
// ---------------------------------------------------------------------------
console.log('\nC. generateBlogUrl');

const url = helpers.generateBlogUrl(FIXTURE);
ok('url uses the ?p= form post.html actually reads', isPostQueryUrl(url, FIXTURE), url);
ok('url is absolute and https', /^https:\/\//.test(url), url);
ok('url defaults to the production host', url.startsWith('https://pdoom1.com/'), url);
ok('a custom base url is honoured',
  helpers.generateBlogUrl(FIXTURE, 'https://example.test').startsWith('https://example.test/'),
  helpers.generateBlogUrl(FIXTURE, 'https://example.test'));

// A filename with characters that must survive a query string.
const oddName = 'post with spaces & ampersand.md';
const oddUrl = helpers.generateBlogUrl(oddName);
ok('a filename is percent-encoded into the query',
  !/[ ]/.test(oddUrl) && oddUrl.includes(encodeURIComponent(oddName)), oddUrl);

// ---------------------------------------------------------------------------
// D. formatPostContent platform limits. A post that exceeds a platform's cap is
//    rejected by that platform's API, so the cap is the property that matters.
// ---------------------------------------------------------------------------
console.log('\nD. formatPostContent');

const sample = {
  title: 'Test Blog Post: Amazing New Feature',
  summary: 'A test blog post about an amazing new feature with several improvements.',
  tags: ['feature', 'update', 'milestone']
};
const sampleUrl = helpers.generateBlogUrl(FIXTURE);

const LIMITS = { bluesky: 300, twitter: 280, x: 280 };

for (const [platform, max] of Object.entries(LIMITS)) {
  const short = helpers.formatPostContent(sample, sampleUrl, platform);
  ok(platform + ': a short post is within ' + max, withinLimit(short, max),
    'length=' + short.length);
  ok(platform + ': a short post keeps the link', short.includes(sampleUrl));

  // The case that actually bites: a summary longer than the whole budget.
  const long = helpers.formatPostContent(
    { title: 'Test', summary: 'A'.repeat(500), tags: [] }, sampleUrl, platform);
  ok(platform + ': a 500-char summary is still within ' + max, withinLimit(long, max),
    'length=' + long.length);
  ok(platform + ': truncation is marked with an ellipsis', long.endsWith('...'),
    JSON.stringify(long.slice(-8)));
}

const linkedin = helpers.formatPostContent(sample, sampleUrl, 'linkedin');
ok('linkedin carries the title, summary and link',
  linkedin.includes(sample.title) && linkedin.includes(sample.summary)
  && linkedin.includes(sampleUrl));
ok('linkedin renders tags as hashtags with no internal spaces',
  sample.tags.every(t => linkedin.includes('#' + t)));

const discord = helpers.formatPostContent(sample, sampleUrl, 'discord');
ok('discord returns an embed object, not a string',
  discord && typeof discord === 'object' && Array.isArray(discord.embeds));
ok('the discord embed carries title, description and url',
  discord.embeds[0].title === sample.title
  && discord.embeds[0].description === sample.summary
  && discord.embeds[0].url === sampleUrl);

const fallback = helpers.formatPostContent(sample, sampleUrl, 'no-such-platform');
ok('an unknown platform still returns a string containing the link',
  typeof fallback === 'string' && fallback.includes(sampleUrl));

// ---------------------------------------------------------------------------
// E. TRIPWIRE. syndication-helpers.js has no production consumer today, and it
//    carries hazards the live pipeline has already been fixed for. If anything
//    starts requiring it, this fails on that day rather than after the first
//    post goes out -- CLAUDE.md, "when a guard is written for one mirror, check
//    whether a second mirror exists."
// ---------------------------------------------------------------------------
console.log('\nE. Production-consumer tripwire');

const SEARCH_DIRS = [
  path.join(REPO, 'scripts'),
  path.join(REPO, 'netlify'),
  path.join(REPO, '.github', 'workflows'),
];

// Match the WIRING, not the name. Matching the bare string "syndication-helpers"
// flagged a historical comment in syndicate-content.yml, and a tripwire that
// cries on prose is a tripwire people disable. These three are how the module
// can actually come to run: a CommonJS require, an ESM import, or a workflow
// shelling out to node. Prose that happens to contain a literal require() call
// would still trip it -- that direction is the safe one for a tripwire.
const WIRING = [
  /require\s*\(\s*['"][^'"]*syndication-helpers[^'"]*['"]\s*\)/,
  /\bfrom\s+['"][^'"]*syndication-helpers[^'"]*['"]/,
  /\bnode\s+\S*syndication-helpers/,
];

function walk(dir, out) {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules') continue;
      walk(full, out);
    } else if (/\.(js|mjs|cjs|py|yml|yaml)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

const consumers = walk(SEARCH_DIRS[0], [])
  .concat(walk(SEARCH_DIRS[1], []), walk(SEARCH_DIRS[2], []))
  .filter(f => path.basename(f) !== path.basename(__filename))
  .filter(f => !path.basename(f).startsWith('test-'))
  .filter(f => {
    try {
      return WIRING.some(re => re.test(fs.readFileSync(f, 'utf8')));
    } catch (e) {
      return false;
    }
  })
  .map(f => path.relative(REPO, f));

ok('syndication-helpers.js still has no production consumer',
  consumers.length === 0,
  consumers.length
    ? ('now required by: ' + consumers.join(', ')
      + ' -- before this module posts anything, fix: (1) generateBlogUrl emits a '
      + 'UTM-free URL, which content/campaigns/README.md says is unrecoverable '
      + 'attribution loss and test-syndication-utm.py already blocks on the live '
      + 'path; (2) formatPostContent truncates the whole post to the character '
      + 'cap, so a long summary cuts the URL off the end entirely; (3) '
      + 'extractBlogMetadata ignores YAML frontmatter and substitutes TODAY\'S '
      + 'date when a post has no "**Date**:" line.')
    : '');

// ---------------------------------------------------------------------------
// F. NEGATIVE CONTROL. The predicates above must reject what they are meant to
//    reject. Green is otherwise equally consistent with "the module is correct"
//    and "these checks never discriminated".
// ---------------------------------------------------------------------------
console.log('\nF. Negative control (the assertions must be able to say no)');

ok('withinLimit rejects an over-length post', withinLimit('A'.repeat(400), 300) === false);
ok('withinLimit rejects an empty post', withinLimit('', 300) === false);
ok('withinLimit rejects a non-string', withinLimit(null, 300) === false);
ok('withinLimit accepts an exact-length post', withinLimit('A'.repeat(300), 300) === true);

ok('isPostQueryUrl rejects the old /blog/#slug anchor form',
  isPostQueryUrl('https://pdoom1.com/blog/#test-post', FIXTURE) === false);
ok('isPostQueryUrl rejects a url for a different post',
  isPostQueryUrl(helpers.generateBlogUrl('other-post.md'), FIXTURE) === false);
ok('isPostQueryUrl accepts the real generated url',
  isPostQueryUrl(helpers.generateBlogUrl(FIXTURE), FIXTURE) === true);

// A formatter that ignores its cap must be caught by the same call used above.
const brokenFormatter = () => 'B'.repeat(400);
ok('a formatter that ignores the 300-char cap is rejected',
  withinLimit(brokenFormatter(), 300) === false);

// The tripwire in block E, run against text instead of the tree. It has to fire
// on real wiring and stay silent on prose, and block E alone can only ever show
// one of those two.
const wired = s => WIRING.some(re => re.test(s));
ok('the tripwire fires on a CommonJS require',
  wired("const h = require('./syndication-helpers.js');") === true);
ok('the tripwire fires on a require from another directory',
  wired('require("../scripts/syndication-helpers")') === true);
ok('the tripwire fires on an ESM import',
  wired("import { formatPostContent } from './syndication-helpers.js';") === true);
ok('the tripwire fires on a workflow shelling out to node',
  wired('        run: node scripts/syndication-helpers.js --emit') === true);
ok('the tripwire stays silent on the historical comment that fooled its first draft',
  wired('# calling scripts/syndication-helpers.js -- so two divergent formatters existed') === false);
ok('the tripwire stays silent on an unrelated require',
  wired("const helpers = require('./other-helpers.js');") === false);

// ---------------------------------------------------------------------------
console.log('\n' + '='.repeat(60));
console.log(pass + ' passed, ' + fail + ' failed');
if (fail > 0) {
  console.log('scripts/test-syndication.js FAILED');
  process.exitCode = 1;
}
