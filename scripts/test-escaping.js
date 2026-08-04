#!/usr/bin/env node
/*
 * Guard: no page splices fetched data into innerHTML without the site's one escaper.
 *
 * SCOPE. scripts/test-board-escaping.js locks down /leaderboard/ specifically -- its
 * identity/dev-badge honesty rules, its search filter, its CSS. This file is the
 * SITE-WIDE half: the escaper itself, and the same class of bug on the other fourteen
 * pages that render fetched data. Both run; neither subsumes the other.
 *
 * WHAT WENT WRONG (2026-07-30 -> 2026-08-01)
 * The score API is unauthenticated and validates nothing, so every field it returns is
 * attacker-controlled. /leaderboard/ was fixed in PRs #202 and #208. Nothing else was.
 * The sweep that followed found the same sink class on /dashboard/ (third-party Manifold
 * market titles, on a top-level nav page), /issues/ (GitHub issue text -- anyone with a
 * GitHub account), /league/, /league/archive.html, /players/, /monitoring/, and three
 * markdown renderers -- plus FIVE separately-written escapers, three of which did not
 * cover quotes while feeding attribute contexts.
 *
 * THE THREE RULES BELOW, AND WHY EACH IS SHAPED THIS WAY
 *
 * Rule 1 -- ONE ESCAPER. Any page defining its own is a failure. Five copies with three
 *   coverages is how "escaped" stopped meaning anything here.
 *
 * Rule 2 -- EVERY INTERPOLATION OF EXTERNAL DATA IS ESCAPED. Enforced by ROOT, not by
 *   field name. test-board-escaping.js's first version named six fields and passed while
 *   thirteen were unprotected, because a list only ever covers what someone remembered.
 *   Here each page declares the identifiers that hold parsed fetch results (`entry`,
 *   `market`, `issue`, ...) and every `${...}` mentioning one must go through the
 *   escaper or a numeric coercion. A NEW FIELD on an existing root is covered the day it
 *   is added, with no test edit.
 *
 * Rule 3 -- THE ROOT LIST CANNOT ROT SILENTLY. A new field is covered by rule 2; a new
 *   DATA SOURCE would not be. So every fetch() URL on a guarded page must appear in that
 *   page's declared list. Add a fetch, and this test fails until its roots are declared.
 *   That is the loop the field-list version of this test was missing.
 *
 * Plus behavioural tests of escape.js and of each markdown renderer, against hostile
 * input, with a STRUCTURAL predicate: after removing the markup the renderer is entitled
 * to emit, no angle bracket, no bare quote inside a tag, no dangerous scheme may survive.
 * Not a keyword blocklist -- escaping does not delete the letters that spell "onerror",
 * it makes them inert, so searching the output for "onerror" proves nothing either way.
 *
 * Run: node scripts/test-escaping.js      (exit 0 = pass)
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

// core.autocrlf=true here, so the working tree is CRLF and every regex below that
// anchors on \n would silently never match. test-board-escaping.js was inert on Windows
// -- the only platform CLAUDE.md tells you to run it on -- for exactly this reason, and
// an audit found that, not the test. Normalise once, at the only place files are read.
function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8').replace(/\r\n/g, '\n');
}

// ---------------------------------------------------------------------------
// The pages that render fetched data, and the identifiers their fetch results
// land in. `roots` is deliberately coarse: it names the VARIABLE, not the fields,
// so new fields are covered automatically (see rule 2 above).
// `fetches` is every URL the page fetches; rule 3 checks the page has no others.
// ---------------------------------------------------------------------------
// `safeHelpers` are functions DEFINED ON THE PAGE that return already-escaped HTML.
// Allowing them is not a hole: each one's own body is scanned by the same rule, so its
// interpolations must be escaped too. Every name listed must actually exist on the page,
// so a rename or a deletion fails here rather than quietly widening the allowance -- and
// a helper someone adds LATER is not listed, so it fails closed until declared.
const GUARDED = [
  {
    page: 'public/leaderboard/index.html',
    roots: ['entry', 'data', 'e'],
    safeHelpers: ['identityHTML', 'devBadgeHTML'],
    fetches: ['/leaderboard/data/weekly/current.json', '/data/ladder-epochs.json',
              '/design/tokens.json', '/leaderboard/data/preserved/',
              'data/leaderboard.json', '/leaderboard/data/seed_'],
  },
  {
    page: 'public/dashboard/index.html',
    // market.* is THIRD-PARTY: any Manifold user who owns one of those markets can
    // edit its title, and this is a top-level nav page.
    // rel.*/ent.* are the development-log entries. As of 2026-08-03 that box no
    // longer reads the hand-typed /data/game-changes.json (which had frozen nine
    // minor versions behind the shipping build); it derives from version.json plus
    // the pdoom1 releases API, which is remote and unauthenticated like every other
    // source on this list.
    roots: ['market', 'rel', 'ent'],
    safeHelpers: ['devlogWhenHtml', 'devlogSummaryHtml'],
    fetches: ['https://api.manifold.markets/v0/slug/', '/data/version.json',
              'https://api.github.com/repos/PipFoweraker/pdoom1/releases'],
  },
  {
    page: 'public/issues/index.html',
    // issue.* is GitHub API data: anyone with a GitHub account can open an issue.
    roots: ['issue', 'label'],
    safeHelpers: [],
    fetches: ['/data/issues-cache.json'],
  },
  {
    page: 'public/league/index.html',
    roots: ['entry', 'data', 'w'],
    safeHelpers: [],
    fetches: ['/design/tokens.json', '/leaderboard/data/weekly/current.json',
              '/api/league/current', '/leaderboard/data/weekly/archive/'],
  },
  {
    page: 'public/league/archive.html',
    roots: ['archive', 'meta', 'stats', 'weekInfo', 'winner', 'b', 'e', 'index'],
    safeHelpers: [],
    fetches: ['/design/tokens.json', '/leaderboard/data/weekly/archive/',
              '/leaderboard/data/preserved/'],
  },
  {
    page: 'public/players/index.html',
    roots: ['week', 'entry', 'playerEntry', 'e'],
    safeHelpers: [],
    fetches: ['/design/tokens.json', '/leaderboard/data/weekly/current.json',
              '/leaderboard/data/weekly/archive/'],
  },
  {
    page: 'public/monitoring/index.html',
    roots: ['check', 'job', 'jobName', 'league', 'weekInfo', 'c', 'h', 'summary'],
    safeHelpers: ['badge'],
    fetches: ['/data/health-check.json', '/data/version.json',
              '/data/deployment-verification.json', '/monitoring/data/automation-status.json',
              '/leaderboard/data/weekly/current.json', '/data/integration-health.json'],
  },
  {
    page: 'public/blog/index.html',
    roots: ['post', 'tag'],
    safeHelpers: [],
    fetches: ['/blog/index.json'],
  },
  {
    page: 'public/game-changelog/index.html',
    roots: ['rel', 'r'],
    safeHelpers: ['platformsHtml', 'releaseBodyHtml', 'md', 'inline', 'isoDay'],
    fetches: ['/design/tokens.json', '/data/version.json',
              'https://api.github.com/repos/PipFoweraker/pdoom1/releases'],
  },
  {
    page: 'public/website-changelog/index.html',
    roots: ['x', 'i'],
    safeHelpers: [],
    fetches: ['/data/website-changes.json'],
  },
  {
    page: 'public/state-of-doom/index.html',
    roots: ['o', 'c', 'cfg'],
    safeHelpers: [],
    fetches: ['/design/tokens.json', '/data/clocks.json'],
  },
  {
    page: 'public/index.html',
    roots: ['status'],
    safeHelpers: [],
    fetches: ['config.json', 'data/status.json', 'design/tokens.json', '/data/version.json',
              'https://api.github.com/repos/PipFoweraker/pdoom1/releases/latest'],
  },
];

// Markdown renderers get behavioural tests instead of a root scan: their input is one
// big untrusted string, not a field, so "is this ${} escaped" is the wrong question.
const RENDERERS = [
  'public/blog/post.html',
  'public/docs/roadmap/index.html',
  'public/dev-notes/index.html',
  'public/game-changelog/index.html',
];

const ALL_PAGES = GUARDED.map((g) => g.page)
  .concat(RENDERERS.filter((r) => !GUARDED.some((g) => g.page === r)));

// ===========================================================================
console.log('\n1. the escaper: one implementation, correct in both contexts');
// ===========================================================================
const ESCAPE_SRC = path.join(ROOT, 'public', 'assets', 'js', 'escape.js');
check(fs.existsSync(ESCAPE_SRC), 'public/assets/js/escape.js exists');
const E = require(ESCAPE_SRC);

// Payloads of the shapes an attacker actually sends, split by which context each one
// is aimed at. The attribute payloads are the ones the three quote-blind escapers let
// straight through.
const HOSTILE_TEXT = [
  '<img src=x onerror=alert(1)>',
  '<script>alert(1)</script>',
  '</td></tr><tr><td>injected',
  '&lt;already escaped&gt;',
  '<svg/onload=alert(1)>',
];
const HOSTILE_ATTR = [
  '" onmouseover="alert(1)',
  "' onmouseover='alert(1)",
  '"><svg onload=alert(1)>',
  'x" autofocus onfocus="alert(1)',
];
const HOSTILE_URL = [
  'javascript:alert(1)',
  'JaVaScRiPt:alert(1)',
  '  javascript:alert(1)',
  'data:text/html,<script>alert(1)</script>',
  'vbscript:msgbox(1)',
  '//evil.example/x',
];

// STRUCTURAL predicate. `allowed` is the markup the producer is entitled to emit; after
// removing it, a surviving < > or a quote means something broke out. Deliberately not a
// blocklist of handler names: escaping leaves the LETTERS of "onerror" in place and makes
// them inert, so a name search answers a different question than the one that matters.
function inert(html, allowed) {
  let s = String(html);
  for (const re of (allowed || [])) { s = s.replace(re, ''); }
  return !/[<>"']/.test(s);
}

for (const h of HOSTILE_TEXT.concat(HOSTILE_ATTR)) {
  check(inert(E.escapeHTML(h)), 'escapeHTML inert: ' + h.slice(0, 36));
}
check(E.escapeHTML('&').includes('&amp;'), 'ampersand escaped (no double-unescape path)');
check(E.escapeHTML('"') === '&quot;', 'double quote escaped -- the attribute context');
check(E.escapeHTML("'") === '&#39;', 'single quote escaped -- the attribute context');
check(E.escapeHTML(null) === '' && E.escapeHTML(undefined) === '',
  'null/undefined render empty, not the strings "null"/"undefined"');
check(E.escapeHTML(0) === '0', 'zero renders as "0", not as empty');

// Forced failure: the property is only demonstrated if the check is seen failing. This
// is the quote-blind escaper the three pages used to carry; it must NOT pass.
const quoteBlind = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
check(!inert(quoteBlind('" onmouseover="alert(1)')),
  'the check FIRES: a & < > -only escaper is rejected on an attribute payload');
check(inert(quoteBlind('<img src=x onerror=alert(1)>')),
  '...and passes on an element payload -- which is why nobody noticed for months');

for (const u of HOSTILE_URL) {
  check(E.safeUrl(u) === '', 'safeUrl drops: ' + u.slice(0, 36));
  check(E.isSafeUrl(u) === false, 'isSafeUrl false for: ' + u.slice(0, 36));
}
check(E.safeUrl('java\tscript:alert(1)') === '' && E.safeUrl('java\nscript:alert(1)') === '',
  'a control character inside the scheme does not smuggle javascript: past the check');
check(E.safeUrl('https://pdoom1.com/a?b=1&c=2') === 'https://pdoom1.com/a?b=1&amp;c=2',
  'safeUrl keeps a real https URL and escapes it for an attribute');
check(E.safeUrlRaw('https://pdoom1.com/a?b=1&c=2') === 'https://pdoom1.com/a?b=1&c=2',
  'safeUrlRaw keeps & intact -- for window.open(), where &amp; would corrupt the query');
check(E.safeUrl('/blog/post.html?p=a.md') === '/blog/post.html?p=a.md',
  'a same-origin relative URL still works');
check(E.safeUrl('javascript:alert(1)', '#') === '#', 'a rejected URL yields the fallback');
check(E.safeUrl('https://a"onmouseover=alert(1)').indexOf('"') === -1,
  'a quote in an otherwise-valid URL cannot end the href attribute');

check(E.toNumber('12.5') === 12.5 && E.toNumber('x') === 0 && E.toNumber(undefined) === 0,
  'toNumber coerces or falls back -- never returns a string');
check(E.toNumber(NaN) === 0 && E.toNumber(Infinity) === 0,
  'NaN/Infinity are not numbers a reader can use; both fall back');
check(typeof E.toNumber('9').toFixed === 'function',
  'toNumber output always has .toFixed -- the DoS this closes');

// ===========================================================================
console.log('\n2. exactly ONE escaper exists on the site');
// ===========================================================================
// Definitions, not calls: `function esc(`, `const escapeHtml =`, and friends.
const DEFINES_ESCAPER =
  /(?:function|const|let|var)\s+(esc|escape[A-Za-z]*|sanitize[A-Za-z]*|htmlEscape[A-Za-z]*)\s*[=(]/g;
for (const rel of ALL_PAGES) {
  const src = read(rel);
  const found = [...src.matchAll(DEFINES_ESCAPER)].map((m) => m[1]);
  check(found.length === 0,
    found.length === 0
      ? rel + ' defines no escaper of its own'
      : rel + ' DEFINES ITS OWN ESCAPER: ' + found.join(', '));
  check(src.includes('<script src="/assets/js/escape.js"></script>'),
    rel + ' loads the shared escaper');
  // async/defer would run the inline renderer first and break the page on every load.
  check(!/<script[^>]*escape\.js[^>]*(?:defer|async)/.test(src),
    rel + ' loads it BLOCKING (not defer/async)');
}

// Hand-rolled partial escaping is the other way a second escaper sneaks in: it looks
// like formatting rather than like a function definition.
const HAND_ROLLED = /\.replace\(\s*\/(?:\[?[&<>"']\]?)\/g\s*,\s*['"]&(?:amp|lt|gt|quot|#39);['"]\s*\)/;
for (const rel of ALL_PAGES) {
  const src = read(rel);
  const hit = HAND_ROLLED.test(src.replace(/^\s*(\/\/|\*).*$/gm, ''));
  check(!hit, rel + ' has no inline hand-rolled entity replace');
}

// ===========================================================================
console.log('\n3. every interpolation of external data goes through the escaper');
// ===========================================================================
// Approved sanitisers. Anything else is an unescaped sink.
const SAFE_CALL = /\b(escapeHTML|safeUrl|safeUrlRaw|isSafeUrl|toNumber|encodeURIComponent)\s*\(/;

// String literals inside an expression are the page's own text, not data. They are
// removed before asking "does this mention a root?", or a root named `s` matches the
// letter s inside `'s'` and the whole scan turns to noise.
function stripLiterals(expr) {
  return String(expr)
    .replace(/'(?:[^'\\]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""')
    .replace(/`(?:[^`\\$]|\\.)*`/g, '``');
}

// `cond ? 'literal' : 'literal'` emits a literal whichever way the condition falls, so
// the condition may mention a root freely -- no value from it can reach the output.
// This is about what CAN BE EMITTED, not about what is tested.
const LITERAL_TERNARY =
  /^\(?\s*[^?]*\?\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\s*:\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\s*\)?$/;

function classify(expr, helperRe) {
  const body = expr.replace(/^\$\{/, '').replace(/\}$/, '').trim();
  if (SAFE_CALL.test(body)) { return 'escaped'; }
  if (helperRe && helperRe.test(body)) { return 'helper'; }
  if (LITERAL_TERNARY.test(body)) { return 'literal-ternary'; }
  return 'UNESCAPED';
}

// Sinks that are safe BY CONSTRUCTION and so are excised before the scan, rather than
// rewritten into escapeHTML() calls that would print a visible "&amp;" to the reader:
//  - .textContent / .title / .value / .alt  -- the DOM escapes these itself
//  - fetch(`...`) URLs                      -- not an HTML sink (path traversal is a
//                                              different bug with a different fix)
//  - console.* and new Error(...)           -- not rendered
//  - document.querySelector(`...`)          -- a selector, not markup
// Order matters: excise multi-line statements FIRST, while their anchor line is still
// present. Filtering by line beforehand orphans the continuation lines -- which is the
// bug test-board-escaping.js hit on its first run.
function htmlSinksOnly(src) {
  return src
    .replace(/\.(?:textContent|title|value|alt|placeholder|href|src|className|cssText)\s*=[\s\S]{0,400}?;\n/g, '\n')
    .replace(/\bfetch\(\s*`[^`]*`/g, 'fetch(``')
    .replace(/\bconsole\.\w+\([\s\S]{0,300}?\);\n/g, '\n')
    .replace(/\bnew Error\([^)]*\)/g, 'new Error()')
    .replace(/\bdocument\.querySelector(?:All)?\(\s*`[^`]*`\s*\)/g, 'q()')
    .split('\n')
    .filter((l) => !/\.(?:textContent|title|value|alt|placeholder)\s*=/.test(l))
    .join('\n');
}

for (const g of GUARDED) {
  const raw = read(g.page);
  const src = htmlSinksOnly(raw);
  const rootAlt = g.roots.map((r) => r.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const rootRe = new RegExp('\\b(?:' + rootAlt + ')\\b');
  const helperRe = g.safeHelpers.length
    ? new RegExp('\\b(?:' + g.safeHelpers.join('|') + ')\\s*\\(')
    : null;

  // Every declared safe helper must really be defined on the page. Without this, the
  // allowance outlives the function and quietly widens.
  for (const h of g.safeHelpers) {
    const defined = new RegExp('(?:function\\s+' + h + '\\s*\\(|(?:const|let|var)\\s+' + h + '\\s*=)').test(raw);
    check(defined, g.page + ': declared safe helper ' + h + '() is defined on the page');
  }

  // Template-literal interpolations `${ ... }` that mention a declared root, either as
  // `root.field` or as the bare identifier.
  const templateHits = (src.match(/\$\{[^{}]*\}/g) || [])
    .filter((x) => rootRe.test(stripLiterals(x)));

  // String-concatenation interpolations: `'...' + root.field + '...'`. The older pages
  // (state-of-doom, game-changelog, index.html) build markup this way, and a scan that
  // only understood template literals would report them clean.
  const concatHits = [...src.matchAll(/['"]\s*\+\s*([^+;]*)\+\s*['"]/g)]
    .map((m) => m[1].trim())
    .filter((x) => rootRe.test(stripLiterals(x)));

  const hits = templateHits.concat(concatHits);
  const unescaped = hits.filter((x) => classify(x, helperRe) === 'UNESCAPED');

  check(hits.length > 0,
    g.page + ': found ' + hits.length + ' interpolations of ' + g.roots.length + ' declared root(s)');
  check(unescaped.length === 0,
    unescaped.length === 0
      ? g.page + ': every one goes through the escaper'
      : g.page + ': ' + unescaped.length + ' UNESCAPED -> ' +
        unescaped.slice(0, 4).map((s) => s.replace(/\s+/g, ' ').slice(0, 70)).join(' | '));
}

// ===========================================================================
console.log('\n4. the root list cannot rot: every fetch is declared');
// ===========================================================================
// Rule 2 covers a new FIELD for free. It cannot cover a new DATA SOURCE, because a new
// source arrives with a new variable name. This closes that gap: adding a fetch() fails
// the test until whoever added it declares where its result lands.
for (const g of GUARDED) {
  const src = read(g.page);
  const urls = [...src.matchAll(/\bfetch\(\s*[`'"]([^`'"$]*)/g)]
    .map((m) => m[1])
    .filter(Boolean)
    // fetch(window.location.origin) and friends carry no literal to match.
    .filter((u) => u !== '');
  const undeclared = urls.filter((u) => !g.fetches.some((known) => u.indexOf(known) === 0 || known.indexOf(u) === 0));
  check(undeclared.length === 0,
    undeclared.length === 0
      ? g.page + ': all ' + urls.length + ' fetch target(s) declared'
      : g.page + ': UNDECLARED fetch -> ' + [...new Set(undeclared)].join(', ') +
        ' (add it and its result variable to GUARDED in this file)');
}

// ===========================================================================
console.log('\n5. the markdown renderers neutralise hostile source');
// ===========================================================================
// These take one untrusted STRING rather than fields, so they are tested by running
// them. Each renderer is extracted from its own page, so the test can never drift from
// what ships -- and each is given the shared escaper, exactly as the browser does via
// the <script src> tag.
const HOSTILE_MD = [
  '<img src=x onerror=alert(1)>',
  '<script>alert(1)</script>',
  '# <svg onload=alert(1)>',
  '[click](javascript:alert(1))',
  '[click](java\tscript:alert(1))',
  '![alt](javascript:alert(1))',
  '[click](https://a"onmouseover=alert(1))',
  '![" onerror="alert(1)](https://x/y.png)',
  '**<iframe src=//evil>**',
  '> <object data=x>',
  '- [x](vbscript:msgbox(1))',
  '`<b>code</b>`',
];

// The markup each renderer is entitled to emit. Anything left after removing these and
// still carrying < > or a quote is a break-out.
const MD_ALLOWED = [
  /<\/?(?:h[1-6]|p|ul|ol|li|strong|em|code|pre|blockquote|hr|br|div|table|thead|tbody|tr|th|td|details|summary|span)(?:\s+class="[\w -]*")?\s*\/?>/g,
  /<a href="(?:https?:\/\/|\/|#|mailto:)[^"<>]*"(?:\s+target="_blank")?(?:\s+rel="[\w ]+")?>/g,
  /<img src="(?:https?:\/\/|\/)[^"<>]*" alt="[^"<>]*"(?:\s+loading="lazy")?(?:\s+decoding="async")?>/g,
  /<\/a>/g,
];

function runInSandbox(code) {
  const sandbox = {
    console,
    // Enough DOM for the page's bootstrap to no-op instead of throwing.
    document: { getElementById: () => null, querySelector: () => null, createElement: () => ({ style: {} }) },
    fetch: () => ({ then: () => ({ then: () => ({ catch: () => {} }), catch: () => {} }) }),
    location: { search: '' },
    module: { exports: {} },
  };
  sandbox.window = sandbox;
  sandbox.exports = sandbox.module.exports;
  vm.createContext(sandbox);
  // The shared escaper FIRST -- the same order the <script> tags impose in a browser.
  // Without it these renderers throw ReferenceError, which is the fail-closed behaviour
  // the pages rely on and also proves the dependency is real.
  vm.runInContext(fs.readFileSync(ESCAPE_SRC, 'utf8'), sandbox);
  try {
    vm.runInContext(code, sandbox);
  } catch (err) {
    // Page bootstraps touch a DOM that is not really here; the declarations still landed.
    if (!/is not a function|Cannot read|not defined|Illegal return/.test(String(err))) { throw err; }
  }
  return sandbox;
}

function pick(box, fn) {
  if (!box) { return null; }
  const v = box[fn] || (box.module && box.module.exports && box.module.exports[fn]);
  return typeof v === 'function' ? v : null;
}

function loadRenderer(rel, needle, fn) {
  const html = read(rel);
  const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
  const code = blocks.find((b) => b.includes(needle));
  if (!code) { return null; }

  // First try as-is. roadmap/index.html is an IIFE but publishes render() through
  // module.exports, so it works unmodified.
  let box = runInSandbox(code);
  if (pick(box, fn)) { return box; }

  // game-changelog wraps everything in an IIFE and exports nothing, so hoisting does not
  // reach the sandbox. Unwrap ONE level -- and only as a fallback, because unwrapping a
  // body that contains a top-level `return` guard (roadmap does) is a SyntaxError.
  const iife = code.match(/^\s*\(function\s*\(\s*\)\s*\{([\s\S]*)\}\s*\)\s*\(\s*\)\s*;?\s*$/);
  if (iife) {
    box = runInSandbox(iife[1]);
    if (pick(box, fn)) { return box; }
  }
  return box;
}

const RENDER_ENTRY = [
  { page: 'public/blog/post.html', needle: 'function renderMarkdown', fn: 'renderMarkdown' },
  { page: 'public/docs/roadmap/index.html', needle: 'function render', fn: 'render', via: 'module' },
  { page: 'public/game-changelog/index.html', needle: 'function md(', fn: 'md' },
];

for (const r of RENDER_ENTRY) {
  const box = loadRenderer(r.page, r.needle, r.fn);
  if (!box) { check(false, r.page + ': could not extract ' + r.fn + '()'); continue; }
  const fn = pick(box, r.fn);
  if (!fn) { check(false, r.page + ': ' + r.fn + '() not callable'); continue; }
  let bad = [];
  for (const src of HOSTILE_MD) {
    let out;
    try { out = fn(src); } catch (e) { bad.push(src + ' -> THREW ' + e.message); continue; }
    if (!inert(out, MD_ALLOWED)) { bad.push(src + ' -> ' + String(out).slice(0, 90)); }
    // A dangerous scheme only matters INSIDE an href/src. `javascript:alert(1)` sitting
    // in the body as escaped TEXT is the correct, safe outcome of a rejected link -- so
    // searching the whole output for the word answers a different question. Extract the
    // attribute values and test only those.
    for (const m of String(out).matchAll(/(?:href|src)\s*=\s*"([^"]*)"/g)) {
      if (!E.isSafeUrl(m[1])) { bad.push(src + ' -> live href/src: ' + m[1].slice(0, 50)); }
    }
  }
  check(bad.length === 0,
    bad.length === 0
      ? r.page + ': all ' + HOSTILE_MD.length + ' hostile inputs render inert'
      : r.page + ': ' + bad.length + ' LEAK(S) -> ' + bad.slice(0, 2).join(' | '));
}

// dev-notes has no named renderer function -- its transform is a chained .replace() in
// an async loader -- so it is checked structurally: escapeHTML must be applied to the
// whole document BEFORE any tag is introduced, and the link rule must check its scheme.
{
  const src = read('public/dev-notes/index.html');
  check(/let html = escapeHTML\(md\)/.test(src),
    'public/dev-notes/index.html escapes the markdown BEFORE adding tags');
  const linkRule = src.match(/\.replace\(\/\\\[\(\.\*\?\)\\\]\\\(\(\.\*\?\)\\\)\/g[\s\S]{0,600}?\n {10}\}\)/);
  check(!!linkRule && /isSafeUrl\(/.test(linkRule[0]),
    'public/dev-notes/index.html scheme-checks the link href');
}

// ===========================================================================
console.log('\n6. hostile API values do not take the render down (availability)');
// ===========================================================================
// Not injection: a plain TypeError. `entry.score.toLocaleString()` and
// `(entry.final_doom || 0).toFixed(1)` both throw on a string, and one throw inside a
// render loop kills the WHOLE list -- a denial of service by one hostile POST. `|| 0`
// does not fix it, because a non-empty string is truthy.
for (const g of GUARDED) {
  // Comments describe the bug; they are not the bug. Strip them, or the explanatory
  // note above each fix trips the check that the fix was made.
  const src = read(g.page)
    .replace(/^\s*\/\/.*$/gm, '')
    .replace(/\/\*[\s\S]*?\*\//g, '');
  const rootAlt = g.roots.map((r) => r.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  // `root.field.toFixed(`  and  `(root.field || 0).toFixed(`  -- both unguarded.
  // The negative lookbehind is what keeps `toNumber(root.field).toFixed(` -- the FIXED
  // form -- from matching its own repair.
  const direct = new RegExp(
    '(?<!toNumber\\()\\b(?:' + rootAlt + ')\\.\\w+(?:\\?\\.\\w+)*\\s*\\.(?:toFixed|toLocaleString|toPrecision)\\s*\\(', 'g');
  const orZero = new RegExp(
    '\\(\\s*(?:' + rootAlt + ')\\.[\\w.?]+\\s*\\|\\|\\s*[\\d.]+\\s*\\)\\s*\\.(?:toFixed|toLocaleString|toPrecision)\\s*\\(', 'g');
  const hits = (src.match(direct) || []).concat(src.match(orZero) || []);
  check(hits.length === 0,
    hits.length === 0
      ? g.page + ': no numeric method called on a raw API field'
      : g.page + ': ' + hits.length + ' unguarded -> ' + [...new Set(hits)].slice(0, 3).join(', ') +
        '  (wrap in toNumber())');
}

console.log(failures === 0
  ? '\nOK: one escaper, every external interpolation escaped, every fetch declared,\n' +
    '    every markdown renderer inert, no numeric method on a raw API field.'
  : '\n' + failures + ' FAILURE(S)');
process.exit(failures === 0 ? 0 : 1);
