#!/usr/bin/env node
/*
 * Guard: the front page's "What we are working on" panel can say UNKNOWN, and says
 * it rather than a reassuring number.
 *
 * WHAT THIS REPLACED, because the failure mode is the point.
 * The front page's entire public account of development was one span:
 *
 *     <span id="open-issues-count">--</span> open issues
 *
 * filled from version.json's `repository_stats.open_issues`. Three defects, all
 * measured on 2026-08-24 rather than inferred:
 *
 *   1. WRONG NUMBER. That field is GitHub's `open_issues_count`, which is documented
 *      to include open PULL REQUESTS. It read 207 against 200 open issues and 7 open
 *      pull requests. Two different things, summed, published as one of them -- the
 *      same category error frontier-labs.json records against its own count.
 *   2. NO AS-OF. A bare integer. A reader could not tell whether it was counted an
 *      hour ago or last quarter, and nothing on the page would have changed if the
 *      producing job had died in March.
 *   3. FAILED INVISIBLY. populateStatusCards()'s catch rewrote EVERY element carrying
 *      .loading-placeholder to an em dash. A total outage and "there is genuinely
 *      nothing to say" rendered identically, and neither said anything to the reader.
 *
 * (The sibling panel on /issues/ was worse and is fixed in the same change: it printed
 * `issues.length` -- the size of a fifteen-item window -- under the words "open
 * issues", and stamped it with `new Date().toLocaleTimeString()`, the READER'S OWN
 * CLOCK at page load. A cache frozen since March rendered as "Last updated: 4:32:10 PM".
 * Tests 13-15 below pin that.)
 *
 * THE RULE THIS ENFORCES (estate ruling, 2026-08-23): a surface reporting a count,
 * status or coverage figure must be able to emit UNKNOWN, and must emit it rather than
 * a reassuring value when its input was unreachable.
 *
 * Every state is driven directly -- renderWorkPanel() takes the parsed file, a host,
 * and an explicit `now` -- so "what happens after a month of silence" is a test that
 * runs in a millisecond instead of an assertion nobody can check.
 *
 * Run: node scripts/test-work-status.js      (exit 0 = pass)
 */

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
let failures = 0;
function check(cond, msg) {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) { failures++; }
}

// core.autocrlf=true on the dev machine, so the working tree is CRLF and every anchor
// below that mentions \n would silently never match. Normalise once, where files are read.
function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8').replace(/\r\n/g, '\n');
}

// Tests 10, 12 and 13 assert that a defect's CODE is gone. Every one of those defects
// is documented in a comment sitting exactly where it used to be -- which is the house
// style and worth keeping -- so a naive scan finds the needle inside its own obituary
// and reports the bug still present. Strip comments first, then scan.
//
// `//` is anchored to the start of a line: an unanchored rule eats `https://...` and
// silently deletes half of every page it is pointed at.
function code(rel) {
  return read(rel)
    .replace(/<!--[\s\S]*?-->/g, '')      // HTML
    .replace(/\/\*[\s\S]*?\*\//g, '')     // JS block
    .replace(/^[ \t]*\/\/.*$/gm, '')      // JS line
    .replace(/^[ \t]*#.*$/gm, '');        // YAML / shell / Python line
}

const PAGE = read('public/index.html');

// ---------------------------------------------------------------------------
// Extract the panel's PURE half from the page and run it. Extracted rather than
// copied, so this test can never drift from what ships -- if someone renames a
// function or moves the block, extraction fails loudly here instead of testing a
// stale copy that still passes.
// ---------------------------------------------------------------------------
const START = 'const WORK_TRACKER_URL =';
const END = 'async function loadWorkPanel()';
const from = PAGE.indexOf(START);
const to = PAGE.indexOf(END);
if (from < 0 || to < 0 || to <= from) {
  console.error('FAIL: could not extract the work-panel block from public/index.html');
  console.error('      looked for "' + START + '" ... "' + END + '"');
  process.exit(1);
}
const BLOCK = PAGE.slice(from, to);

// The shared escaper, exactly as the browser gets it: a blocking <script src> before
// the inline script. Nothing here defines its own.
const SHARED = require(path.join(ROOT, 'public', 'assets', 'js', 'escape.js'));

const sandbox = {
  escapeHTML: SHARED.escapeHTML,
  safeUrl: SHARED.safeUrl,
  safeUrlRaw: SHARED.safeUrlRaw,
  toNumber: SHARED.toNumber,
  Date: Date,
  Math: Math,
  Array: Array,
  String: String,
  console: { warn: function () {}, log: function () {} },
};
vm.createContext(sandbox);
vm.runInContext(BLOCK, sandbox, { filename: 'public/index.html#work-panel' });

const renderWorkPanel = sandbox.renderWorkPanel;
const workInstant = sandbox.workInstant;
const workFreshness = sandbox.workFreshness;
check(typeof renderWorkPanel === 'function', 'renderWorkPanel() extracted from the page');
check(typeof workInstant === 'function', 'workInstant() extracted from the page');
check(typeof workFreshness === 'function', 'workFreshness() extracted from the page');
if (typeof renderWorkPanel !== 'function') { process.exit(1); }

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const NOW = Date.UTC(2026, 7, 24, 12, 0, 0);   // 2026-08-24T12:00:00Z
const HOUR = 3600000;
const DAY = 24 * HOUR;

function host() { return { innerHTML: '' }; }

// A feed whose as_of sits `agoMs` before NOW, with whatever counts are handed in.
function feed(agoMs, counts, extra) {
  const f = {
    issues: [
      {
        title: 'Balance key guard covers 2 files of 213 call sites',
        html_url: 'https://github.com/PipFoweraker/pdoom1/issues/1276',
        updated_at: new Date(NOW - 2 * DAY).toISOString(),
      },
      {
        title: 'print_doc: send -print-settings at all',
        html_url: 'https://github.com/PipFoweraker/pdoom1/pull/1284',
        updated_at: new Date(NOW - 3 * HOUR).toISOString(),
        pull_request: { url: 'https://api.github.com/x' },
      },
    ],
    summary: {
      as_of: new Date(NOW - agoMs).toISOString().replace(/\.\d+Z$/, 'Z'),
      source: {
        repository_url: 'https://github.com/PipFoweraker/pdoom1',
        generated_by: '.github/workflows/update-game-data.yml',
        cadence: 'every 6 hours (cron 0 */6 * * *)',
      },
      counts: counts,
      completeness: 'known_incomplete',
      measurement: 'complete',
      unmeasured: [],
    },
  };
  if (extra) { Object.keys(extra).forEach(function (k) { f.summary[k] = extra[k]; }); }
  return f;
}

const FULL = {
  open_issues: 200,
  open_pull_requests: 7,
  open_issues_without_label: 96,
  open_issues_labelled_bug: 17,
  open_issues_labelled_enhancement: 16,
};

// "Does a figure tile appear at all?" -- the single question every UNKNOWN state
// has to answer with no. Asked structurally (the tile container), not by hunting
// for a digit: a date contains digits too, and a test that cannot tell them apart
// would pass on a panel that printed "0" beside a fresh timestamp.
function hasFigures(html) { return html.indexOf('class="work-figures"') >= 0; }
function tileValues(html) {
  return (html.match(/<span class="work-value">([^<]*)<\/span>/g) || [])
    .map(function (m) { return m.replace(/<[^>]*>/g, ''); });
}

// ===========================================================================
console.log('\n1. an unreachable input renders words, never a number');
// ===========================================================================
{
  const h = host();
  renderWorkPanel(h, null, NOW);
  check(!hasFigures(h.innerHTML), 'fetch failed: no figure tile is rendered at all');
  check(h.innerHTML.indexOf('could not read our own development tracker') >= 0,
    'fetch failed: says so in words a non-technical reader can act on');
  check(h.innerHTML.indexOf('showing none at all') >= 0,
    'fetch failed: states that it is deliberately showing nothing');
  check(h.innerHTML.indexOf('github.com/PipFoweraker/pdoom1/issues') >= 0,
    'fetch failed: hands the reader the source instead');
  check(!/>\s*0\s*</.test(h.innerHTML), 'fetch failed: nothing renders as 0');
}
{
  // The file came back, but the writing job died before the counts existed.
  const h = host();
  renderWorkPanel(h, { issues: [] }, NOW);
  check(!hasFigures(h.innerHTML), 'file present but no summary: no figures');
  check(h.innerHTML.indexOf('did not finish') >= 0,
    'file present but no summary: names what went wrong');
}

// ===========================================================================
console.log('\n2. a measured, current file renders the measured numbers');
// ===========================================================================
{
  const h = host();
  renderWorkPanel(h, feed(2 * HOUR, FULL), NOW);
  const vals = tileValues(h.innerHTML);
  check(vals.join(',') === '200,17,16,7',
    'fresh: the four figures are the four measured counts (got ' + vals.join(',') + ')');
  check(h.innerHTML.indexOf('out of date') < 0, 'fresh: no staleness banner');
  check(h.innerHTML.indexOf('24 August 2026, 10:00 UTC') >= 0,
    'fresh: every figure carries the instant it was counted');
  check(h.innerHTML.indexOf('.github/workflows/update-game-data.yml') >= 0,
    'fresh: names the job that produced the figures');
  check(h.innerHTML.indexOf('96 have not been sorted') >= 0,
    'fresh: publishes the uncategorised denominator alongside the label counts');
  check(h.innerHTML.indexOf('floor, not a total') >= 0,
    'fresh: label counts are declared a floor, not a total');
}

// ===========================================================================
console.log('\n3. stale is shown as stale -- and the old numbers still show');
// ===========================================================================
{
  const h = host();
  renderWorkPanel(h, feed(3 * DAY, FULL), NOW);
  check(hasFigures(h.innerHTML), 'stale: the figures still render (stale-but-honest)');
  check(h.innerHTML.indexOf('These figures are out of date') >= 0,
    'stale: says out of date, in bold, before the numbers');
  check(h.innerHTML.indexOf('3 days ago') >= 0, 'stale: states how old, in plain words');
  check(h.innerHTML.indexOf('was true then') >= 0,
    'stale: states that the figures describe the past, not now');
  const staleAt = h.innerHTML.indexOf('These figures are out of date');
  check(staleAt >= 0 && staleAt < h.innerHTML.indexOf('class="work-figures"'),
    'stale: the banner is ABOVE the figures, so it cannot be scrolled past');
}
{
  // Just inside the threshold -- one missed run must not shout at a visitor.
  const h = host();
  renderWorkPanel(h, feed(20 * HOUR, FULL), NOW);
  check(h.innerHTML.indexOf('out of date') < 0, '20 hours old: not yet flagged stale');
}

// ===========================================================================
console.log('\n4. past the abandonment threshold the numbers stop');
// ===========================================================================
{
  const h = host();
  renderWorkPanel(h, feed(60 * DAY, FULL), NOW);
  check(!hasFigures(h.innerHTML), 'two months old: NO figures render');
  check(h.innerHTML.indexOf('would mislead you') >= 0,
    'two months old: says why it is showing nothing');
  check(h.innerHTML.indexOf('25 June 2026') >= 0,
    'two months old: still names the date it last managed to count');
}

// ===========================================================================
console.log('\n5. an undated or future-dated file is UNKNOWN, not fresh');
// ===========================================================================
[
  ['as_of missing', undefined],
  ['as_of empty', ''],
  ['as_of not a date', 'sometime last week'],
  ['as_of not a string', 12345],
].forEach(function (c) {
  const f = feed(2 * HOUR, FULL);
  f.summary.as_of = c[1];
  const h = host();
  renderWorkPanel(h, f, NOW);
  check(!hasFigures(h.innerHTML), c[0] + ': no figures render');
  check(h.innerHTML.indexOf('cannot tell when its figures were last checked') >= 0,
    c[0] + ': says the date is what is missing');
});
{
  // Clock disagreement. A negative age would otherwise sail through as very fresh.
  const f = feed(-5 * DAY, FULL);
  const h = host();
  renderWorkPanel(h, f, NOW);
  check(!hasFigures(h.innerHTML), 'as_of in the future: no figures render');
}

// ===========================================================================
console.log('\n6. an unmeasured count is the WORD unknown, never 0');
// ===========================================================================
{
  const partial = {
    open_issues: 200,
    open_pull_requests: null,
    open_issues_without_label: null,
    open_issues_labelled_bug: null,
    open_issues_labelled_enhancement: 16,
  };
  const h = host();
  renderWorkPanel(h, feed(2 * HOUR, partial, { measurement: 'partial',
    unmeasured: ['open_pull_requests', 'open_issues_without_label',
                 'open_issues_labelled_bug'] }), NOW);
  const vals = tileValues(h.innerHTML);
  check(vals.join(',') === '200,not counted,16,not counted',
    'partial: unmeasured tiles read "not counted" (got ' + vals.join(',') + ')');
  check(vals.indexOf('0') < 0, 'partial: no unmeasured count renders as 0');
  check(h.innerHTML.indexOf('It is unknown, which is not the same as none') >= 0,
    'partial: each unknown tile spells out that unknown is not none');
  check(h.innerHTML.indexOf('did not come back') >= 0,
    'partial: a banner says part of the count is missing');
  check(h.innerHTML.indexOf('could not establish how many open items are uncategorised') >= 0,
    'partial: with no denominator, the floor caveat degrades instead of disappearing');
}
{
  // A MEASURED zero is a fact and must still render as 0. If this test ever fails
  // the panel has started hiding good news, which is the opposite defect and just
  // as dishonest.
  const zeroed = {
    open_issues: 0, open_pull_requests: 0, open_issues_without_label: 0,
    open_issues_labelled_bug: 0, open_issues_labelled_enhancement: 0,
  };
  const h = host();
  renderWorkPanel(h, feed(2 * HOUR, zeroed), NOW);
  check(tileValues(h.innerHTML).join(',') === '0,0,0,0',
    'a measured zero renders as 0 -- unknown and none stay distinguishable');
}
{
  // Anything non-finite is UNKNOWN. GitHub returning a string, or NaN falling out of
  // arithmetic, must not become a published figure.
  // Labelled by NAME, not by JSON.stringify: that serialises both NaN and Infinity as
  // "null", so two distinct cases would print the same line and a silent drop of one of
  // them would be invisible in the output.
  [['empty string', ''], ['a word', 'lots'], ['NaN', NaN], ['Infinity', Infinity],
   ['an object', {}], ['an array', []], ['undefined', undefined], ['null', null],
   ['a numeric string', '200']].forEach(function (c) {
    const counts = Object.assign({}, FULL, { open_issues: c[1] });
    const h = host();
    renderWorkPanel(h, feed(2 * HOUR, counts), NOW);
    check(tileValues(h.innerHTML)[0] === 'not counted',
      'open_issues as ' + c[0] + ' is UNKNOWN, not a figure');
  });
}

// ===========================================================================
console.log('\n7. a naive timestamp is read as UTC, not as the reader\'s local time');
// ===========================================================================
// The producer wrote `datetime.utcnow().isoformat()` -- no zone -- until 2026-08-24,
// and ECMA-262 reads a bare date-time as LOCAL. On a machine west of UTC that made
// the cache look up to twelve hours NEWER than it was: error in the one direction
// that hides staleness, on the value the staleness gate is computed from.
{
  check(workInstant('2026-08-24T01:45:04') === workInstant('2026-08-24T01:45:04Z'),
    'a zone-less instant is read as UTC');
  check(workInstant('2026-08-24T01:45:04.187160') === workInstant('2026-08-24T01:45:04.187Z'),
    'a zone-less instant with microseconds is read as UTC');
  check(workInstant('2026-08-24T01:45:04+10:00') !== workInstant('2026-08-24T01:45:04Z'),
    'an explicit offset is honoured, not overwritten');
  check(workInstant('not a date') === null && workInstant('') === null &&
        workInstant(null) === null && workInstant(7) === null,
    'anything unreadable is null (UNKNOWN), never a number');
  check(workFreshness(null, NOW).state === 'unknown',
    'workFreshness(null) is unknown, not fresh');
}

// ===========================================================================
console.log('\n8. upstream text cannot reshape the page');
// ===========================================================================
{
  const f = feed(2 * HOUR, FULL);
  f.issues = [{
    title: '<img src=x onerror=alert(1)> "quoted" & <script>alert(2)</script>',
    html_url: 'javascript:alert(3)',
    updated_at: new Date(NOW - HOUR).toISOString(),
  }];
  const h = host();
  renderWorkPanel(h, f, NOW);
  const rows = h.innerHTML.slice(h.innerHTML.indexOf('work-list'));
  check(rows.indexOf('<img') < 0 && rows.indexOf('<script') < 0,
    'a hostile issue title lands as inert text');
  check(h.innerHTML.indexOf('javascript:') < 0,
    'a javascript: html_url is dropped, not linked');
}

// ===========================================================================
console.log('\n9. the recent list is labelled as raw developer shorthand');
// ===========================================================================
{
  const h = host();
  renderWorkPanel(h, feed(2 * HOUR, FULL), NOW);
  check(h.innerHTML.indexOf('word for word, not rewritten') >= 0,
    'the raw-title list says it is unedited, rather than passing as a summary');
  check(h.innerHTML.indexOf('is not the same as most important') >= 0,
    'the raw-title list refuses the ranking a reader would otherwise infer');
  check(h.innerHTML.indexOf('Changes proposed recently') >= 0 &&
        h.innerHTML.indexOf('Recently worked on') >= 0,
    'pull requests are separated from issues rather than shown as one list');
  check(h.innerHTML.indexOf('#1276') < 0 && h.innerHTML.indexOf('#1284') < 0,
    'no issue numbers are shown -- they mean nothing to a visitor');
}

// ===========================================================================
console.log('\n10. the front page no longer publishes the conflated count');
// ===========================================================================
{
  const live = code('public/index.html');
  check(live.indexOf('id="open-issues-count"') < 0,
    'the `open-issues-count` span (issues + pull requests, labelled issues) is gone');
  check(!/_setStatus\('open-issues-count'/.test(live),
    'nothing still writes repository_stats.open_issues to the page');
  check(live.indexOf('repository_stats') < 0,
    'no live code on the front page reads repository_stats at all');
}

// ===========================================================================
console.log('\n11. the committed data file carries the contract the panel reads');
// ===========================================================================
{
  const raw = read('public/data/issues-cache.json');
  let data = null;
  try { data = JSON.parse(raw); } catch (e) { data = null; }
  check(data !== null, 'public/data/issues-cache.json parses');
  const s = (data && data.summary) || null;
  check(s !== null, 'it carries a `summary` block');
  if (s) {
    check(typeof s.as_of === 'string' && /Z$/.test(s.as_of),
      'summary.as_of is a ZONED instant (a naive one is read as local time downstream)');
    check(s.completeness === 'known_incomplete',
      'summary.completeness states the roster is known-incomplete');
    check(s.stat_contract && typeof s.stat_contract.open_issues === 'string' &&
          s.stat_contract.open_issues.indexOf('is:issue') >= 0,
      'summary.stat_contract writes out the query behind open_issues');
    check(s.stat_contract && /not.*zero|does not mean zero/i.test(s.stat_contract.null_means || ''),
      'summary.stat_contract states that null is UNKNOWN and not zero');
    ['open_issues', 'open_pull_requests', 'open_issues_without_label',
     'open_issues_labelled_bug', 'open_issues_labelled_enhancement'].forEach(function (k) {
      const v = s.counts && s.counts[k];
      check(v === null || typeof v === 'number',
        'summary.counts.' + k + ' is a number or null (never a string, never absent)');
    });
    check(s.counts && s.counts.open_issues !== undefined &&
          data.count !== s.counts.open_issues,
      'the fifteen-item window size is NOT published as the open-issue total');
  }
}

// ===========================================================================
console.log('\n12. the producer still writes that contract');
// ===========================================================================
// The renderer degrades safely if the producer stops emitting `summary` -- it shows
// the honest empty state. That is correct behaviour and completely silent, so this
// checks the producer directly rather than waiting for a reader to notice.
{
  const wf = code('.github/workflows/update-game-data.yml');
  check(wf.indexOf('"summary": summary') >= 0,
    'update-game-data.yml writes the summary block into issues-cache.json');
  check(wf.indexOf('is:issue is:open') >= 0,
    'it counts issues with is:issue, which excludes pull requests');
  check(/_unmeasured\.append/.test(wf),
    'a failed query is recorded as unmeasured rather than defaulted');
  check(wf.indexOf('datetime.utcnow()') < 0,
    'it no longer stamps a zone-less timestamp');
}

// ===========================================================================
console.log('\n13. /issues/ states the same three things');
// ===========================================================================
{
  const ISSUES = code('public/issues/index.html');
  check(ISSUES.indexOf('new Date().toLocaleTimeString()') < 0,
    "the 'last updated' stamp is no longer the READER'S OWN CLOCK at page load");
  check(ISSUES.indexOf('issuesLastUpdated') >= 0 || ISSUES.indexOf('summary.as_of') >= 0 ||
        ISSUES.indexOf('cacheData.last_updated') >= 0,
    'it stamps from the cache file instead');
  check(!/<span id="issues-count">0<\/span> open issues/.test(ISSUES),
    'the window size is no longer printed under the words "open issues"');
  check(ISSUES.indexOf('most recently updated') >= 0,
    'the list says what window it is showing');
}

// ---------------------------------------------------------------------------
console.log('');
if (failures) {
  console.error('FAIL: ' + failures + ' honesty check(s) failed.');
  process.exit(1);
}
console.log('OK: the work panel can say UNKNOWN, and says it rather than a number.');
