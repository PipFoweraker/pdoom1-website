#!/usr/bin/env node
/*
 * Guard: the "Recent Development Log" box on /dashboard/ derives, and never shows
 * stale content.
 *
 * WHAT WENT WRONG (found 2026-08-02, fixed 2026-08-03)
 * ---------------------------------------------------
 * That box read /data/game-changes.json -- a hand-typed file that no script or
 * workflow has ever written -- and rendered its newest three entries under the word
 * "Recent". It had frozen where the typing stopped, NINE MINOR VERSIONS and ~324
 * days behind the shipping build. The "View Full Changelog" link INSIDE the same box
 * went to /game-changelog/, which derives correctly, so the site contradicted itself
 * one click apart -- on a page that is in the main nav and in the homepage footer.
 *
 * It survived because game-changes.json carried a note saying "NOT RENDERED
 * ANYWHERE" and CLAUDE.md repeated it. Both were false when written: the dashboard
 * had been a consumer for about nine months by then, and the person who wrote the
 * note had migrated /game-changelog/ off the file, verified that ONE page, and
 * generalised. The exact versions and dates are in that file's own `_deprecated`
 * note; they are deliberately NOT repeated here, so that every version literal
 * check-stale-facts.py reports against this file is a real one.
 *
 * WHAT THIS FILE LOCKS DOWN
 * -------------------------
 *  1. DERIVED. The box reads /data/version.json plus the pdoom1 releases API -- the
 *     same two sources /game-changelog/ uses. No version, date or summary literal
 *     exists in the block, and none appears in the rendered output when a lookup
 *     fails. (A hardcoded fallback ships exactly when the real lookup failed, i.e.
 *     when nobody can notice it is wrong. CLAUDE.md: "Fallback literals are the
 *     dangerous ones.")
 *  2. FRESHNESS-GATED. Deriving is not the same as being fresh: the source itself
 *     can stop moving. If the newest release is older than DEVLOG_MAX_AGE_DAYS, or
 *     carries no readable date at all, the box renders NO release. Unknown and
 *     stale take the same exit, because "absence of a marker is never a clean bill
 *     of health".
 *  3. INERT. The releases API is remote and unauthenticated, so every field is
 *     attacker-controlled. Hostile input renders as visible text and does not blank
 *     the box -- structurally checked (after removing the markup the renderer is
 *     entitled to emit, no angle bracket or bare quote may survive), not by
 *     searching the output for the word "onerror", which escaping does not delete.
 *
 * Every case below FORCES the state and observes the result. A guard seen only in
 * its passing state has not been shown to work.
 *
 * Companion to scripts/test-changelog-render.js, which locks the same contract down
 * for /game-changelog/. Neither subsumes the other: they are different pages with
 * different renderers, and it was believing otherwise that produced this bug.
 *
 * Run: node scripts/test-dashboard-devlog.js      (exit 0 = pass)
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PAGE = path.join(ROOT, 'public', 'dashboard', 'index.html');
const SHARED = require(path.join(ROOT, 'public', 'assets', 'js', 'escape.js'));

// core.autocrlf=true on Windows, so anchor every \n-sensitive regex on LF only.
const src = fs.readFileSync(PAGE, 'utf8').replace(/\r\n/g, '\n');

let failures = 0;
function check(cond, msg) {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) { failures++; }
}

// A version literal, in any of the shapes that have rotted here before.
const VERSION_LITERAL = /\bv?\d+\.\d+\.\d+\b/;
const DAY = 86400000;

// ---------------------------------------------------------------------------
// Extract the block. Anchored on the section banners, so moving or renaming the
// section fails loudly here instead of quietly testing nothing.
// ---------------------------------------------------------------------------
const START = '/* ========== Development log: DERIVED, and freshness-gated';
const END = '/* ========== Manifold Markets Integration';
const i0 = src.indexOf(START);
const i1 = src.indexOf(END);
if (i0 < 0 || i1 < 0 || i1 <= i0) {
  console.error('FAIL: could not locate the development-log block in ' + PAGE);
  console.error('      (the section banners moved; re-anchor this test, do not delete it)');
  process.exit(1);
}
const block = src.slice(i0, i1);

// Comments describe the old bug by name; they are not the bug. Strip them before
// asking "does this page still reference the dead file / a version literal?".
const blockCode = block
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^[ \t]*\/\/.*$/gm, '');

// ---------------------------------------------------------------------------
// Load the block with the shims a browser would provide.
// ---------------------------------------------------------------------------
function makeDoc(withDevLog) {
  const el = { id: 'devLog', innerHTML: '' };
  return {
    el: withDevLog ? el : null,
    getElementById(id) { return (withDevLog && id === 'devLog') ? el : null; },
  };
}

// `version`/`releases` are the parsed bodies; `*Fails` throws (offline), `*Status`
// returns a non-ok response (rate limit, 404).
function makeFetch(opts) {
  return async function (url) {
    if (String(url).indexOf('/data/version.json') === 0) {
      if (opts.versionFails) { throw new Error('network'); }
      if (opts.versionStatus) { return { ok: false, status: opts.versionStatus, json: async () => ({}) }; }
      return { ok: true, json: async () => opts.version };
    }
    if (String(url).indexOf('https://api.github.com/') === 0) {
      if (opts.releasesFails) { throw new Error('network'); }
      if (opts.releasesStatus) { return { ok: false, status: opts.releasesStatus, json: async () => ({}) }; }
      return { ok: true, json: async () => opts.releases };
    }
    return { ok: false, status: 404, json: async () => ({}) };
  };
}

const quietConsole = { warn() {}, error() {}, log() {} };

async function run(opts) {
  const doc = makeDoc(opts.noDevLog ? false : true);
  // escapeHTML is injected the way the blocking <script src="/assets/js/escape.js">
  // injects it in a browser. Without it the renderer throws ReferenceError -- the
  // page's intended fail-closed behaviour, not a test artefact.
  const mod = new Function(
    'document', 'fetch', 'escapeHTML', 'console',
    blockCode + '\nreturn {loadEventLog: loadEventLog, devlogAgeDays: devlogAgeDays, ' +
      'devlogDay: devlogDay, devlogSummary: devlogSummary, ' +
      'MAX_AGE: DEVLOG_MAX_AGE_DAYS, MAX_ENTRIES: DEVLOG_ENTRIES};'
  )(doc, makeFetch(opts), SHARED.escapeHTML, opts.console || quietConsole);

  let threw = null;
  try {
    await mod.loadEventLog();
  } catch (e) {
    threw = e;
  }
  return { html: doc.el ? doc.el.innerHTML : '', threw: threw, mod: mod };
}

// Read the policy constants from the page rather than repeating them here: never
// assert a literal against a value that moves.
const CONST = new Function(blockCode + '\nreturn {MAX_AGE: DEVLOG_MAX_AGE_DAYS, ' +
  'MAX_ENTRIES: DEVLOG_ENTRIES};')();
const MAX_AGE = CONST.MAX_AGE;
const MAX_ENTRIES = CONST.MAX_ENTRIES;

// ---------------------------------------------------------------------------
// Fixtures. ASSEMBLED, not written out, so no vX.Y.Z literal exists in this file
// for check-stale-facts.py to (correctly) flag -- and so a passing test proves the
// value came from the data, not from the page.
// ---------------------------------------------------------------------------
const V9 = ['v9', '9', '9'].join('.');
const V8 = ['v9', '9', '8'].join('.');
const V7 = ['v9', '9', '7'].join('.');
const V6 = ['v9', '9', '6'].join('.');
const ISO = (msAgo) => new Date(Date.now() - msAgo).toISOString();

const FRESH_BODY = [
  '## [' + V9.slice(1) + '] - fresh',
  '',
  'Rebuilt the effort economy; scores are not comparable with older boards.',
  '',
  '- **Commit:** `deadbeef`',
].join('\n');

const freshVersionJson = (extra) => ({
  latest_release: Object.assign({
    version: V9,
    published_at: ISO(2 * DAY),
    body: FRESH_BODY,
    html_url: 'https://github.com/PipFoweraker/pdoom1/releases/tag/' + V9,
  }, extra || {}),
});

const freshReleases = [
  { tag_name: V9, published_at: ISO(2 * DAY), body: FRESH_BODY },
  { tag_name: V8, published_at: ISO(20 * DAY), body: 'Fixed the seed banner.' },
  { tag_name: V7, published_at: ISO(40 * DAY), body: '### Changed\n- a thing' },
  { tag_name: V6, published_at: ISO(60 * DAY), body: 'Older still.' },
];

const staleReleases = [
  { tag_name: V9, published_at: ISO(400 * DAY), body: FRESH_BODY },
  { tag_name: V8, published_at: ISO(430 * DAY), body: 'Fixed the seed banner.' },
];

// The markup the box is entitled to emit. Anything left after removing it that
// still carries < > " ' broke out of its context.
const ALLOWED = [
  /<div class="narrative-(?:title|text)"(?: style="margin-top:12px;")?>/g,
  /<span class="highlight">/g,
  /<a href="(?:https?:\/\/|\/)[^"<>]*" target="_blank" rel="noopener(?: noreferrer)?" class="source-link">/g,
  /<\/(?:div|span|a)>/g,
];
function inert(html) {
  let s = String(html);
  for (const re of ALLOWED) { s = s.replace(re, ''); }
  return !/[<>"']/.test(s);
}

// ===========================================================================
(async () => {
  console.log('\n1. the page source itself: nothing hand-maintained survives');
  // ===========================================================================
  check(!/game-changes\.json/.test(blockCode),
    'the block no longer references /data/game-changes.json (the frozen hand-typed file)');
  check(!VERSION_LITERAL.test(blockCode),
    'no version literal anywhere in the block (found: ' +
      (blockCode.match(VERSION_LITERAL) || ['none']) + ')');
  check(blockCode.includes("fetch('/data/version.json'"),
    'reads /data/version.json -- the same current-release source /game-changelog/ uses');
  check(/api\.github\.com\/repos\/PipFoweraker\/pdoom1\/releases/.test(blockCode),
    'reads the pdoom1 releases API for history');
  check(/loadEventLog\(\);/.test(src.slice(i1)),
    'loadEventLog() is still called on page load');
  check(src.includes('<script src="/assets/js/escape.js"></script>'),
    'the page loads the ONE shared escaper (blocking) -- the renderer calls it');
  check(typeof MAX_AGE === 'number' && MAX_AGE > 0 && typeof MAX_ENTRIES === 'number',
    'the freshness window and entry cap are named constants (' + MAX_AGE + ' days, ' +
      MAX_ENTRIES + ' entries)');

  // =========================================================================
  console.log('\n2. happy path: both sources fresh -> real, derived entries');
  // =========================================================================
  let r = await run({ version: freshVersionJson(), releases: freshReleases });
  check(r.threw === null, 'renders without throwing');
  check(r.html.includes('Recent Development Log'), 'headed "Recent Development Log"');
  check(r.html.includes(V9) && r.html.includes(V8) && r.html.includes(V7),
    'renders the versions it was GIVEN (they came from the data, not the page)');
  check(!r.html.includes(V6),
    'caps at ' + MAX_ENTRIES + ' entries -- the fourth release is not rendered');
  check(r.html.includes(new Date(Date.now() - 2 * DAY).toISOString().slice(0, 10)),
    'renders the release date it was given');
  check(r.html.includes('Rebuilt the effort economy'),
    'summarises from the release body, first line of real prose');
  check(!r.html.includes('## [') && !r.html.includes('**Commit:**'),
    'skips the body heading and strips markdown punctuation');
  check(r.html.includes('href="/game-changelog/"'), 'still links to the full changelog');
  check(inert(r.html), 'output is structurally inert');

  // =========================================================================
  console.log('\n3. FORCED FAILURE -- the freshness gate fires on a stale source');
  // =========================================================================
  // This is the defect, reproduced: both lookups succeed and return real, correctly
  // derived data that is simply old. Deriving alone would render it under "Recent".
  r = await run({
    version: freshVersionJson({ published_at: ISO(400 * DAY) }),
    releases: staleReleases,
  });
  check(!VERSION_LITERAL.test(r.html),
    'shows NO version at all -- not the stale one, not a remembered one (found: ' +
      (r.html.match(VERSION_LITERAL) || ['none']) + ')');
  check(!r.html.includes('Recent Development Log'),
    'drops the word "Recent" rather than applying it to a 400-day-old release');
  check(/\d+ days ago/.test(r.html), 'says how old the newest record it can see is');
  check(r.html.includes('github.com/PipFoweraker/pdoom1/releases'),
    'points at the live source instead');
  check(r.html.length > 0, 'the box is not silently blank -- silence reads as "fine"');
  check(inert(r.html), 'the degraded output is structurally inert too');

  // =========================================================================
  console.log('\n4. the gate has a real edge, and it is read from the page constant');
  // =========================================================================
  r = await run({
    version: freshVersionJson({ published_at: ISO((MAX_AGE - 1) * DAY) }),
    releasesFails: true,
  });
  check(r.html.includes(V9), 'just inside the window (' + (MAX_AGE - 1) + 'd): renders');
  r = await run({
    version: freshVersionJson({ published_at: ISO((MAX_AGE + 1) * DAY) }),
    releasesFails: true,
  });
  check(!VERSION_LITERAL.test(r.html),
    'just outside it (' + (MAX_AGE + 1) + 'd): renders no release');

  // A release dated in the future is a broken source, not a scoop.
  r = await run({
    version: freshVersionJson({ published_at: new Date(Date.now() + 30 * DAY).toISOString() }),
    releasesFails: true,
  });
  check(!VERSION_LITERAL.test(r.html) && /in the future/.test(r.html),
    'a future-dated release is refused and named as such');

  // =========================================================================
  console.log('\n5. version.json missing its release fields -> UNKNOWN, not "nothing shipped"');
  // =========================================================================
  r = await run({ version: {}, releasesFails: true });
  check(r.threw === null, 'does not throw on an empty version.json');
  check(!VERSION_LITERAL.test(r.html), 'invents no version');
  check(/could not read the release history/.test(r.html),
    'says the history could not be read -- an unreadable source is unknown, not empty');

  r = await run({ version: { latest_release: {} }, releasesFails: true });
  check(!VERSION_LITERAL.test(r.html) && r.html.length > 0,
    'latest_release present but empty is handled the same way');

  // published_at absent is the case CLAUDE.md warns about: absence of a marker is
  // never a clean bill of health.
  r = await run({
    version: { latest_release: { version: V9, body: FRESH_BODY } },
    releasesFails: true,
  });
  check(!r.html.includes(V9), 'a release with NO date is not rendered as if it were current');
  check(/no readable\s+date/.test(r.html.replace(/\s+/g, ' ')),
    'and the box says the date could not be read');

  // ...but a dateless OLD record must never displace a dated fresh one either.
  r = await run({
    version: { latest_release: { version: V6, body: 'no date on this one' } },
    releases: freshReleases,
  });
  check(r.html.includes(V9) && r.html.includes('Recent Development Log'),
    'a dateless record sorts last and does not disarm the gate for the rest');

  // =========================================================================
  console.log('\n6. transport failures: no stale content, no blank box');
  // =========================================================================
  r = await run({ versionFails: true, releasesFails: true });
  check(r.threw === null, 'both sources offline: does not throw');
  check(!VERSION_LITERAL.test(r.html), 'shows no version');
  check(/could not read the release history/.test(r.html), 'says so plainly');
  check(r.html.includes('github.com/PipFoweraker/pdoom1/releases'), 'and links out');

  r = await run({ versionStatus: 404, releasesStatus: 403 });
  check(!VERSION_LITERAL.test(r.html) && r.html.length > 0,
    'non-ok responses (404 / 403 rate limit) degrade the same way');

  r = await run({ versionFails: true, releases: freshReleases });
  check(r.html.includes(V9) && r.html.includes(V8),
    'version.json alone offline: the API history still renders');
  r = await run({ version: freshVersionJson(), releasesFails: true });
  check(r.html.includes(V9) && !r.html.includes(V8),
    'API alone offline: the current release still renders, with no invented history');

  // =========================================================================
  console.log('\n7. malformed and hostile payloads render inert, and do not blank the box');
  // =========================================================================
  // The releases API answer is not guaranteed to be a list -- rate limiting returns
  // an object -- and Array.isArray is the only thing between that and a TypeError
  // that would kill the whole render.
  r = await run({
    version: freshVersionJson(),
    releases: { message: 'API rate limit exceeded', documentation_url: 'https://x' },
  });
  check(r.threw === null && r.html.includes(V9),
    'a non-array releases payload does not take the render down');

  const HOSTILE_TAG = '"><img src=x onerror=alert(1)>';
  const HOSTILE_BODY = [
    "<script>alert('xss')</script>",
    '[click](javascript:alert(1))',
  ].join('\n');
  r = await run({
    version: freshVersionJson({ version: HOSTILE_TAG, body: HOSTILE_BODY }),
    releases: [{ tag_name: '</span><svg onload=alert(1)>', published_at: ISO(3 * DAY),
                 body: '" onmouseover="alert(1)' }],
  });
  check(r.threw === null, 'hostile fields do not throw');
  check(r.html.length > 0, 'and do not blank the box');
  check(inert(r.html), 'every hostile field renders as inert text');
  check(r.html.includes('&lt;script&gt;') || r.html.includes('&lt;img'),
    'the payload is visible as escaped text, which is the honest outcome');
  check(!/<img|<svg|<script/.test(r.html), 'no live element was created');

  // A string where a number belongs: the date. `|| 0` would not save this -- a
  // non-empty string is truthy -- so the age helper must return null, not NaN.
  // Some of these read as UNKNOWN (unparseable) and some as STALE (0 and false both
  // resolve to the epoch); the point is that both exits are the same -- no release.
  const BAD_DATES = [
    ['a non-date string', 'not-a-date'], ['an empty string', ''], ['zero', 0],
    ['false', false], ['an object', {}], ['an array', []],
    ['Infinity', 1e308 * 10], ['the word "Infinity"', 'Infinity'],
  ];
  for (const [label, bad] of BAD_DATES) {
    const rr = await run({
      version: { latest_release: { version: V9, published_at: bad, body: 'x' } },
      releasesFails: true,
    });
    check(rr.threw === null && !rr.html.includes(V9) && rr.html.length > 0,
      'published_at = ' + label + ' -> no release rendered, box still says something');
  }

  // The unit that decides it, exercised directly.
  const probe = (await run({ versionFails: true, releasesFails: true })).mod;
  check(probe.devlogAgeDays(undefined) === null && probe.devlogAgeDays(null) === null &&
        probe.devlogAgeDays('nonsense') === null && probe.devlogAgeDays({}) === null,
    'devlogAgeDays returns null (unknown) rather than 0 (brand new) for junk');
  check(probe.devlogDay('nonsense') === '' && probe.devlogDay({}) === '',
    'devlogDay returns empty rather than the string "Invalid Date"');
  check(probe.devlogSummary(undefined) === '' && probe.devlogSummary(42) === '' &&
        probe.devlogSummary({ a: 1 }) === '',
    'devlogSummary refuses a non-string body instead of stringifying it');
  const ELLIPSIS = String.fromCharCode(0x2026);
  const long = probe.devlogSummary('x'.repeat(500));
  check(long.length <= 141 && long.slice(-1) === ELLIPSIS,
    'a very long body is truncated, so one release cannot fill the panel');

  // =========================================================================
  console.log('\n8. a missing #devLog element is survivable');
  // =========================================================================
  r = await run({ noDevLog: true, version: freshVersionJson(), releases: freshReleases });
  check(r.threw === null,
    'no #devLog on the page: returns quietly instead of throwing into the console');

  console.log('\n' + (failures
    ? failures + ' FAILURE(S)'
    : 'OK: the dashboard development log derives from version.json + the releases API,\n' +
      '    refuses to present anything older than ' + MAX_AGE + ' days (or undated) as recent,\n' +
      '    and renders hostile upstream fields as inert text.'));
  process.exit(failures ? 1 : 0);
})();
