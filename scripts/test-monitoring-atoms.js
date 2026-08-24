#!/usr/bin/env node
/*
 * Guard: /monitoring/ is made of atoms, every one of them freshness-gated, and none
 * of them able to print a value out of a source that has stopped moving.
 *
 * WHAT WENT WRONG (page created 2025-09-30, rewritten 2026-08-25)
 * --------------------------------------------------------------
 * The page predated every honesty rule this project now runs on. It carried eight
 * status cards and ONE aggregate "Health Score" percentage. Its deployment card read
 * /data/deployment-verification.json -- a file whose only two writers,
 * version-aware-deploy.yml and weekly-deployment.yml, are workflow_dispatch-only --
 * and rendered a green "healthy / 100%" from a snapshot last written 2026-07-17.
 * Nothing was ever going to refresh it. The aggregate it fed stayed green throughout,
 * which is the whole argument against an aggregate: a percentage over unrelated
 * sources can read 100% while several of them are dead, and you cannot tell by
 * looking at it.
 *
 * WHAT THIS FILE LOCKS DOWN
 * -------------------------
 *  1. NO AGGREGATE. No single number combining sources, and no path that divides one
 *     source's passes by its totals and presents the result as site health.
 *  2. EVERY ATOM IS GATED, through the shared gate in /assets/js/freshness.js, and
 *     the page does not reinvent one: no epoch arithmetic of its own.
 *  3. STALE, UNDATED, UNREADABLE AND FUTURE-DATED ALL RENDER NOTHING. Each state is
 *     FORCED here and the output observed. A guard seen only in its passing state has
 *     not been shown to work.
 *  4. NO WRITER IS NAMED, NOT DELETED. The one source nothing schedules keeps its box
 *     and says so, and cannot render a value even when its stamp is fresh.
 *  5. THE DECLARED FETCH LIST CANNOT ROT. This page routes every fetch through one
 *     readSource(url), so test-escaping.js rule 3 finds no URL literal on the page and
 *     passes having checked nothing. This file closes that from the other end: the
 *     ATOMS table and the `fetches` array in scripts/test-escaping.js must agree, in
 *     both directions.
 *  6. INERT. Hostile field values render as visible text and do not blank the page --
 *     checked structurally (after removing the markup the renderer is entitled to
 *     emit, no angle bracket or bare quote may survive), not by grepping the output
 *     for handler names, which escaping does not delete.
 *
 * Companion to scripts/test-freshness.js, which forces the failing states of the
 * shared gate itself. Neither subsumes the other: one is the mechanism, this is the
 * page that has to use it correctly.
 *
 * Run: node scripts/test-monitoring-atoms.js      (exit 0 = pass)
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PAGE = path.join(ROOT, 'public', 'monitoring', 'index.html');
const ESCAPER = require(path.join(ROOT, 'public', 'assets', 'js', 'escape.js'));
const FRESHNESS = require(path.join(ROOT, 'public', 'assets', 'js', 'freshness.js'));

// core.autocrlf=true on Windows, so anchor every \n-sensitive regex on LF only.
const src = fs.readFileSync(PAGE, 'utf8').replace(/\r\n/g, '\n');

let failures = 0;
function check(cond, msg) {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) { failures++; }
}

const HOUR = 3600000;
const DAY = 24 * HOUR;
const isoAgo = (ms) => new Date(Date.now() - ms).toISOString();

// ---------------------------------------------------------------------------
// Extract the block. Anchored on the section banners, so moving or renaming the
// section fails loudly here instead of quietly testing nothing.
// ---------------------------------------------------------------------------
const START = '/* ===== ATOMS: the indicators, one source each, each freshness-gated';
const END = '/* ===== END ATOMS';
const i0 = src.indexOf(START);
const i1 = src.indexOf(END);
if (i0 < 0 || i1 < 0 || i1 <= i0) {
  console.error('FAIL: could not locate the ATOMS block in ' + PAGE);
  console.error('      (the section banners moved; re-anchor this test, do not delete it)');
  process.exit(1);
}
const block = src.slice(i0, i1);

// Comments describe the old bug by name; they are not the bug. Strip them before
// asking structural questions about the code.
const blockCode = block
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^[ \t]*\/\/.*$/gm, '');

// ---------------------------------------------------------------------------
// Browser shims.
// ---------------------------------------------------------------------------
function makeDoc() {
  const atoms = { id: 'atoms', innerHTML: '' };
  const stamp = { id: 'rendered-at', textContent: '' };
  return {
    atoms, stamp,
    getElementById(id) {
      if (id === 'atoms') { return atoms; }
      if (id === 'rendered-at') { return stamp; }
      return null;
    },
  };
}

// `docs` maps a url to the parsed body to hand back. A url mapped to the string
// 'throw' simulates an offline fetch; a number simulates that HTTP status; 'garbage'
// simulates a body that parses into something that is not an object.
function makeFetch(docs) {
  return async function (url) {
    const key = String(url);
    if (!(key in docs)) { return { ok: false, status: 404, json: async () => ({}) }; }
    const v = docs[key];
    if (v === 'throw') { throw new Error('network'); }
    if (typeof v === 'number') { return { ok: false, status: v, json: async () => ({}) }; }
    if (v === 'garbage') { return { ok: true, json: async () => 'a bare string' }; }
    return { ok: true, json: async () => v };
  };
}

const quietConsole = { warn() {}, error() {}, log() {} };

function load() {
  const doc = makeDoc();
  return { doc };
}

function instantiate(doc, docs) {
  return new Function(
    'document', 'fetch', 'escapeHTML', 'toNumber', 'Freshness', 'console',
    blockCode + '\nreturn { ATOMS: ATOMS, renderAtom: renderAtom, ' +
      'loadAtoms: loadAtoms, readSource: readSource };'
  )(doc, makeFetch(docs), ESCAPER.escapeHTML, ESCAPER.toNumber, FRESHNESS, quietConsole);
}

async function run(docs) {
  const doc = makeDoc();
  const mod = instantiate(doc, docs);
  let threw = null;
  try { await mod.loadAtoms(); } catch (e) { threw = e; }
  return { html: doc.atoms.innerHTML, stamp: doc.stamp.textContent, threw, mod };
}

// The ATOMS table, read once with a fetch that answers nothing -- we only want the
// declarations, not a render.
const ATOMS = instantiate(makeDoc(), {}).ATOMS;

// The markup the renderer is entitled to emit.
const ALLOWED = [
  /<div class="atom is-[a-z]+" id="atom-[a-z-]+">/g,
  /<div class="atom-(?:head|derives|source|refusal)">/g,
  /<span class="(?:atom-title|k|v)">/g,
  /<span class="badge badge-[a-z]+">/g,
  /<ul class="atom-rows">/g,
  /<\/?(?:li|b|code|ul|div|span)>/g,
];
function inert(html) {
  let s = String(html);
  for (const re of ALLOWED) { s = s.replace(re, ''); }
  return !/[<>"']/.test(s);
}

// The COMPUTATION the old Health Score performed, not the words describing it: the
// page is allowed -- required, in fact -- to name the thing it removed. Grepping for
// the prose would only teach whoever rewrites this to stop explaining themselves.
const AGGREGATE_SHAPE =
  /healthScore|health_score|\*\s*100\s*\)|Math\.round\([^)]*\/[^)]*\)|\/\s*total_checks/i;

// Extract one atom's box out of the rendered grid. Splitting on the opening div is
// what makes this exact: a lazy [\s\S]*? would happily run past the end of one box
// and find the next box's closing tag, which is how the first version of section 6
// passed while the value list it was looking for was two boxes further down.
function boxFor(html, id) {
  const parts = String(html).split('<div class="atom is-');
  const hit = parts.find((p) => p.indexOf('id="atom-' + id + '"') === 0 ||
    p.indexOf('" id="atom-' + id + '"') > -1);
  return hit === undefined ? null : '<div class="atom is-' + hit;
}

// ===========================================================================
(async () => {
  console.log('\n1. the page source: no aggregate, no second gate, both shared files loaded');
  // ===========================================================================
  check(!AGGREGATE_SHAPE.test(blockCode),
    'no Health-Score-shaped aggregate survives in the block (found: ' +
      (blockCode.match(AGGREGATE_SHAPE) || ['none']) + ')');
  // The words may appear, but only downstream of the heading that frames them as
  // history. An occurrence anywhere above that is a live claim again.
  const visible = src.replace(/<!--[\s\S]*?-->/g, '');
  const historyAt = visible.indexOf('What was removed, and why');
  // Case-SENSITIVE: "Health Score" was the old card's label, and reappearing as a
  // label is the regression. The lower-case phrase in the prose above ("there is
  // deliberately no overall health score") is the page explaining itself, which is
  // the opposite of the defect and must not be forbidden.
  const mentions = [...visible.matchAll(/Health Score/g)].map((x) => x.index);
  check(historyAt > 0, 'the page carries a "What was removed, and why" section');
  check(mentions.every((at) => at > historyAt),
    mentions.every((at) => at > historyAt)
      ? 'the words "Health Score" appear only as history (' + mentions.length + ' mention(s))'
      : 'a "Health Score" mention survives ABOVE the history section');
  check(src.includes('<script src="/assets/js/escape.js"></script>'),
    'loads the ONE escaper, blocking');
  check(src.includes('<script src="/assets/js/freshness.js"></script>'),
    'loads the ONE staleness gate, blocking');
  check(!/<script[^>]*freshness\.js[^>]*(?:defer|async)/.test(src),
    'the gate is NOT deferred -- the inline renderer calls it');

  // Reinventing the gate is how five escapers happened. No epoch arithmetic here.
  check(!/Date\.now\(\)/.test(blockCode),
    'the block does no Date.now() arithmetic of its own');
  check(!/3600000|86400000|36e5|\/\s*1000\s*\/\s*60/.test(blockCode),
    'no hand-rolled millisecond conversion (that is what Freshness.ageHours is for)');
  check(/Freshness\.assess\(/.test(blockCode),
    'every atom is judged by Freshness.assess()');
  check(/Freshness\.unavailable\(/.test(blockCode),
    'and a source that could not be read gets Freshness.unavailable(), not silence');

  // =========================================================================
  console.log('\n2. the ATOMS table is well formed, and declares a window for every source');
  // =========================================================================
  check(Array.isArray(ATOMS) && ATOMS.length >= 5,
    'ATOMS is a table of ' + (ATOMS || []).length + ' indicators');
  for (const atom of ATOMS) {
    check(typeof atom.id === 'string' && typeof atom.title === 'string' &&
          typeof atom.url === 'string' && typeof atom.derives === 'string',
      atom.id + ': declares id/title/url/derives');
    check(typeof atom.maxAgeHours === 'number' && isFinite(atom.maxAgeHours) && atom.maxAgeHours > 0,
      atom.id + ': declares a positive freshness window (' + atom.maxAgeHours + 'h)');
    check(typeof atom.stampedAt === 'function' && typeof atom.rows === 'function',
      atom.id + ': declares how it is dated and how it is read');
  }
  check(new Set(ATOMS.map((a) => a.id)).size === ATOMS.length, 'every atom id is unique');
  check(new Set(ATOMS.map((a) => a.url)).size === ATOMS.length,
    'every atom reads a DIFFERENT source -- two atoms off one file is an aggregate wearing a hat');

  // =========================================================================
  console.log('\n3. the declared fetch list cannot rot (rule 3 is blind on this page)');
  // =========================================================================
  // test-escaping.js finds no URL literal here, because every fetch goes through
  // readSource(url). So its "all 0 fetch target(s) declared" is a vacuous green.
  // Close it from this end instead of pretending it is covered.
  const escSrc = fs.readFileSync(path.join(ROOT, 'scripts', 'test-escaping.js'), 'utf8');
  const entry = escSrc.slice(escSrc.indexOf("page: 'public/monitoring/index.html'"));
  const m = /fetches:\s*(\[[\s\S]*?\])/.exec(entry);
  check(!!m, 'found the monitoring `fetches` declaration in scripts/test-escaping.js');
  if (m) {
    // eslint-disable-next-line no-new-func
    const declared = new Function('return ' + m[1])();
    const used = ATOMS.map((a) => a.url);
    const missing = used.filter((u) => !declared.includes(u));
    const extra = declared.filter((u) => !used.includes(u));
    check(missing.length === 0,
      missing.length === 0
        ? 'every source the page fetches is declared in test-escaping.js'
        : 'UNDECLARED source(s): ' + missing.join(', '));
    check(extra.length === 0,
      extra.length === 0
        ? 'and nothing is declared that the page no longer reads'
        : 'STALE declaration(s) in test-escaping.js: ' + extra.join(', '));
  }

  // =========================================================================
  console.log('\n4. every atom has a fixture here, so a new atom cannot skip coverage');
  // =========================================================================
  // Keyed by url. Stamps are injected fresh at call time by freshDocs() below.
  const FIXTURES = {
    '/data/health-check.json': () => ({
      last_check: isoAgo(2 * HOUR), passed: 11, total_tests: 11,
      results: [{ test: 'Main Index File', passed: true },
                { test: 'Config JSON', passed: false }],
    }),
    '/data/integration-health.json': () => ({
      generated: isoAgo(6 * HOUR), overall_status: 'WARN',
      summary: { fail: 0, warn: 3, ok: 32 },
      checks: [{ name: 'schema:events', status: 'OK', detail: 'valid' },
               { name: 'drift:seed', status: 'WARN', detail: 'one week behind' }],
    }),
    '/data/version.json': () => ({
      last_updated: isoAgo(3 * HOUR),
      latest_release: {
        version: ['v9', '9', '9'].join('.'), published_at: isoAgo(2 * DAY),
        platforms: { windows: true, macos: false, linux: true },
      },
    }),
    '/leaderboard/data/board-liveness.json': () => ({
      checked_at: isoAgo(1 * HOUR), verdict: 'live', unknown_streak: 0, escalate_threshold: 4,
      board_key: { seed: 'weekly-fixture', ladder_epoch: 'L99', epochs_agree: true },
      deployed_board: { entries: 1 },
    }),
    '/data/analytics/latest.json': () => ({
      captured_at_utc: isoAgo(10 * HOUR), period: '30d', source: 'https://analytics.example',
    }),
    '/data/events-sync-summary.json': () => ({
      sync_timestamp: isoAgo(8 * HOUR), included_events: 1194, total_events_in_source: 1194,
      pii: { emails_redacted: 0, obfuscated_contact_suspects: 0 },
    }),
    '/monitoring/data/automation-status.json': () => ({
      last_updated: isoAgo(4 * HOUR),
      jobs: { 'a-job': { last_run: isoAgo(4 * HOUR), success_count: 10, total_runs: 10 } },
    }),
    // SENTINEL VALUES, not realistic ones. Section 8 asserts that not one field of
    // this file reaches the reader, by searching the rendered output for each value.
    // The real file carries `total_checks: 18`, and "18" turns up inside any ISO
    // timestamp the other atoms render -- so a realistic fixture makes that check
    // report a leak on every run. Improbable numbers make the search mean something.
    '/data/deployment-verification.json': () => ({
      timestamp: isoAgo(2 * HOUR), total_checks: 8675309, passed: 8675309,
      failed: 4815162342, deployment_approved: true,
    }),
  };
  const unfixtured = ATOMS.map((a) => a.url).filter((u) => !(u in FIXTURES));
  check(unfixtured.length === 0,
    unfixtured.length === 0
      ? 'every atom has a fixture in this file'
      : 'NO FIXTURE for: ' + unfixtured.join(', ') + ' (add one; do not delete the check)');

  const freshDocs = (override) => {
    const out = {};
    for (const url of Object.keys(FIXTURES)) { out[url] = FIXTURES[url](); }
    return Object.assign(out, override || {});
  };

  // =========================================================================
  console.log('\n5. happy path: fresh sources render their own contents');
  // =========================================================================
  let r = await run(freshDocs());
  check(r.threw === null, 'renders without throwing');
  for (const atom of ATOMS) {
    check(r.html.includes('id="atom-' + atom.id + '"'), 'atom rendered: ' + atom.id);
  }
  check(r.html.includes('CURRENT'), 'at least one atom is labelled CURRENT');
  check(r.html.includes('11 of 11'), 'health-check counts came from the FIXTURE, not the page');
  check(r.html.includes('0 / 3 / 32'), 'contract counts came from the fixture');
  check(r.html.includes('windows, linux') && !/macos/.test(r.html),
    'platforms are derived from the booleans, and a false one is not advertised');
  check(inert(r.html), 'output is structurally inert');
  // The aggregate, tested by observation rather than by grep: no rendered VALUE is a
  // percentage. A page with no percentage in it cannot be showing a health score.
  const values = [...r.html.matchAll(/<span class="v">([^<]*)<\/span>/g)].map((x) => x[1]);
  check(values.length > 0 && values.every((v) => v.indexOf('%') === -1),
    'not one of the ' + values.length + ' rendered values is a percentage');
  check(/your browser/.test(r.stamp),
    'the page says the render clock is the reader\'s own browser');

  // =========================================================================
  console.log('\n6. FORCED FAILURE -- a stale source renders its age, and no value');
  // =========================================================================
  // The defect reproduced: the read succeeds, the JSON is well formed and correct,
  // and the file has not been written in weeks.
  const staleHealth = FIXTURES['/data/health-check.json']();
  staleHealth.last_check = isoAgo(39 * DAY);
  r = await run(freshDocs({ '/data/health-check.json': staleHealth }));
  check(!r.html.includes('11 of 11'),
    'shows NO value out of the stale source -- not the old one, not a remembered one');
  check(/STALE/.test(r.html), 'labels it STALE');
  check(/39 days ago/.test(r.html), 'says how old the source is');
  check(r.html.includes('id="atom-health-checks"'),
    'the box is not silently dropped -- silence reads as "fine"');
  check(r.html.includes('0 / 3 / 32'),
    'one stale source does not take out the atoms beside it');
  check(inert(r.html), 'the degraded output is inert too');

  // The window edge is real, and read from the page's own declaration.
  const gated = ATOMS.find((a) => !a.noWriter);
  const nearFixture = FIXTURES[gated.url]();
  const stampKey = Object.keys(nearFixture).find((k) => {
    try { return gated.stampedAt(nearFixture) === nearFixture[k]; } catch (e) { return false; }
  });
  nearFixture[stampKey] = isoAgo((gated.maxAgeHours - 1) * HOUR);
  r = await run(freshDocs({ [gated.url]: nearFixture }));
  check(r.html.includes('id="atom-' + gated.id + '"') && /CURRENT/.test(r.html),
    'just inside the declared window (' + (gated.maxAgeHours - 1) + 'h): renders');
  nearFixture[stampKey] = isoAgo((gated.maxAgeHours + 1) * HOUR);
  r = await run(freshDocs({ [gated.url]: nearFixture }));
  const edgeBox = boxFor(r.html, gated.id);
  check(edgeBox !== null && /is-stale/.test(edgeBox) && !/atom-rows/.test(edgeBox),
    'just outside it (' + (gated.maxAgeHours + 1) + 'h): that box goes STALE and lists no value');

  // =========================================================================
  console.log('\n7. FORCED FAILURE -- undated, unreadable, absent and future-dated');
  // =========================================================================
  // An undated source: present, parses, carries no stamp at all.
  const undated = FIXTURES['/data/integration-health.json']();
  delete undated.generated;
  r = await run(freshDocs({ '/data/integration-health.json': undated }));
  check(!r.html.includes('0 / 3 / 32'), 'an undated source renders no value');
  check(/UNKNOWN/.test(r.html), 'and is labelled UNKNOWN, not treated as current');

  // A dead fetch, an HTTP error, and a body that is not an object.
  for (const [bad, name] of [['throw', 'an offline fetch'], [503, 'HTTP 503'],
    [404, 'HTTP 404'], ['garbage', 'a body that is not an object']]) {
    r = await run(freshDocs({ '/data/version.json': bad }));
    check(r.html.includes('id="atom-release-data"') && /UNKNOWN/.test(r.html),
      name + ' -> the box stays and reads UNKNOWN');
    check(!/v9\.9\.9/.test(r.html), name + ' -> no version from anywhere else leaks in');
  }

  // A future-dated source is a broken clock, not a scoop.
  const future = FIXTURES['/data/board-liveness.json'] ? null : FIXTURES['/leaderboard/data/board-liveness.json']();
  future.checked_at = new Date(Date.now() + 30 * DAY).toISOString();
  r = await run(freshDocs({ '/leaderboard/data/board-liveness.json': future }));
  check(!/weekly-fixture/.test(r.html), 'a future-dated source renders no value');
  check(/FUTURE-DATED/.test(r.html), 'and is named as future-dated');

  // Every source dead at once: the page degrades, it does not blank.
  const allDead = {};
  for (const atom of ATOMS) { allDead[atom.url] = 'throw'; }
  r = await run(allDead);
  check(r.threw === null, 'with every source dead the render still completes');
  for (const atom of ATOMS) {
    check(r.html.includes('id="atom-' + atom.id + '"'), 'still names its gap: ' + atom.id);
  }
  check(!/CURRENT/.test(r.html), 'and claims nothing is current');
  check(inert(r.html), 'the all-dead output is inert');

  // =========================================================================
  console.log('\n8. FORCED FAILURE -- the source nothing writes cannot render a value');
  // =========================================================================
  const orphans = ATOMS.filter((a) => typeof a.noWriter === 'string' && a.noWriter.length > 0);
  check(orphans.length >= 1,
    'at least one atom is marked as having no scheduled writer (' +
      orphans.map((a) => a.id).join(', ') + ')');
  for (const orphan of orphans) {
    check(/dispatch/i.test(orphan.noWriter),
      orphan.id + ': the prose says WHY nothing refreshes it, not just that nothing does');
    // Fresh stamp, real contents, and it still must not become a health signal.
    r = await run(freshDocs());
    const box = new RegExp('<div class="atom is-nowriter" id="atom-' + orphan.id + '">[\\s\\S]*?<div class="atom-source">')
      .exec(r.html);
    check(!!box, orphan.id + ': renders in the no-writer tone even with a fresh stamp');
    if (box) {
      check(!/atom-rows/.test(box[0]),
        orphan.id + ': renders no value list at all -- a fresh stamp here means a human ran it by hand');
      check(/NO SCHEDULED WRITER/.test(box[0]), orphan.id + ': says so in words');
    }
    // The fixture for this source carries total_checks/passed/deployment_approved.
    // None of them may reach the reader, from this box or from anywhere else.
    const fixture = FIXTURES[orphan.url]();
    const leaked = Object.keys(fixture)
      .filter((k) => k !== 'timestamp')
      .filter((k) => typeof fixture[k] !== 'object')
      .filter((k) => r.html.indexOf(String(fixture[k])) > -1);
    check(leaked.length === 0,
      leaked.length === 0
        ? orphan.id + ': not one field of the file it reads is printed as health'
        : orphan.id + ': LEAKED field value(s) ' + leaked.join(', '));
  }

  // =========================================================================
  console.log('\n9. hostile field values render as text, and take nothing down');
  // =========================================================================
  const hostile = FIXTURES['/leaderboard/data/board-liveness.json']();
  hostile.verdict = '<img src=x onerror=alert(1)>';
  hostile.board_key = {
    seed: '"><svg onload=alert(1)>',
    ladder_epoch: "' onmouseover='alert(1)",
    epochs_agree: 'not a boolean',
  };
  hostile.deployed_board = { entries: 'not a number' };
  hostile.unknown_streak = { nested: 'object' };
  const hostileHealth = FIXTURES['/data/health-check.json']();
  hostileHealth.results = [{ test: '</span></li><tr><td>injected', passed: false }];
  hostileHealth.passed = '<script>alert(1)</script>';
  r = await run(freshDocs({
    '/leaderboard/data/board-liveness.json': hostile,
    '/data/health-check.json': hostileHealth,
  }));
  check(r.threw === null, 'hostile fields do not throw the renderer');
  check(inert(r.html), 'and nothing breaks out of its context');
  check(r.html.includes('id="atom-board-liveness"') && r.html.includes('id="atom-health-checks"'),
    'both hostile boxes still render');
  check(/unrecorded/.test(r.html),
    'a three-valued field given junk reads "unrecorded", not "no"');
  check(!/NaN|undefined|\[object Object\]/.test(r.html),
    'no JavaScript stringification artefact reaches the reader');

  // =========================================================================
  console.log('\n10. reachability: this page is the way in to the developer surfaces');
  // =========================================================================
  // WHY THIS SECTION EXISTS. /metabolism/ is a generated page, rebuilt on every
  // relevant change, and MEASURED 2026-08-25 it had exactly one inbound link on the
  // whole deployed site: this page. /design-questions/ and /dev-notes/ had none at
  // all. A rewrite of this page that dropped the link would have made a live
  // developer surface unreachable without anything going red, so the link list is
  // part of the contract now, not decoration.
  //
  // public/_review/ is excluded from every deploy (deploy-excludes.txt) and is
  // gitignored, so a link from there is not an entry point and must not be counted.
  // That distinction is the whole point: "something links it" is a claim people make
  // without grepping, and this repo has a nine-month case of exactly that.
  const DEPLOYED_HTML = [];
  (function walk(dir) {
    for (const name of fs.readdirSync(dir)) {
      const full = path.join(dir, name);
      if (fs.statSync(full).isDirectory()) {
        // _review never ships; events/ is 2,200 generated pages that link none of this.
        if (name === '_review' || name === 'events') { continue; }
        walk(full);
      } else if (name.endsWith('.html')) {
        DEPLOYED_HTML.push(full);
      }
    }
  })(path.join(ROOT, 'public'));

  function linksTo(target, exclude) {
    return DEPLOYED_HTML.filter((f) => f !== exclude &&
      fs.readFileSync(f, 'utf8').includes('href="' + target + '"'))
      .map((f) => path.relative(ROOT, f).split(path.sep).join('/'));
  }

  const SURFACES = ['/metabolism/', '/design-notes/', '/design-questions/', '/dev-notes/'];
  const listStart = src.indexOf('id="developer-surfaces"');
  check(listStart > 0, 'the page carries a developer-surfaces index');
  const listed = listStart > 0 ? src.slice(listStart, src.indexOf('</ul>', listStart)) : '';
  for (const surface of SURFACES) {
    check(fs.existsSync(path.join(ROOT, 'public', surface.slice(1), 'index.html')),
      surface + ' still exists on disk (a dead link is worse than no link)');
    check(listed.indexOf('href="' + surface + '"') > -1,
      surface + ' is listed in that index');
  }

  // And this page must itself be reachable, or the index above is unreachable too --
  // the same trap, one level up.
  const inbound = linksTo('/monitoring/', PAGE);
  check(inbound.length > 0,
    inbound.length > 0
      ? '/monitoring/ is linked from ' + inbound.length + ' deployed page(s): ' + inbound.join(', ')
      : '/monitoring/ IS ORPHANED -- no deployed page links it, so nothing below it is reachable');

  // ===========================================================================
  console.log('\n' + (failures ? failures + ' FAILURE(S)' : 'All checks passed.'));
  process.exit(failures ? 1 : 0);
})();
