#!/usr/bin/env node
/*
 * Guard: no card on this site may render a reassuring value it did not measure.
 *
 * THE DEFECT CLASS ("manufactured confidence", ruled 2026-08-23)
 * -------------------------------------------------------------
 * A value meaning "I could not tell" rendered as a value meaning "fine". The
 * binding rule: anything reporting a count, status or coverage figure must be able
 * to emit UNKNOWN, and must emit it rather than a reassuring value when its input
 * was unreachable, stale or absent.
 *
 * It is not one bug. It is four shapes, and this file is organised by them because
 * a fix for one does nothing for the other three:
 *
 *   A. SILENT SUBSET. A set is assembled from N independent reads, the failures are
 *      dropped with .filter(d => d !== null), and what survived is presented as the
 *      whole. The extreme case -- every read failed -- becomes a positive claim:
 *      /players/ told a visitor a named person "may not have participated in any
 *      weeks yet" having read zero weeks.
 *   B. ABSENT COERCED TO ZERO. `field || 0`, `toNumber(field)` (whose fallback IS
 *      0), and `total ? avg : 0`. Zero is a measurement. A reader cannot tell it
 *      from a failed read, and the failed read is when it is most likely wrong.
 *      /leaderboard/ printed "Average p(Doom) 0.0%" -- the best possible outcome in
 *      this game -- on a board with no entries.
 *   C. ABSENT TIMESTAMP REPLACED BY NOW. /docs/ did
 *      `status.website?.lastUpdated || new Date().toISOString()`, so the one state
 *      in which it knew nothing about its own currency printed the freshest
 *      possible time. Same defect /issues/ carried until 2026-08-24.
 *   D. DERIVED CORRECTLY FROM A SOURCE THAT STOPPED MOVING. No literal, no
 *      fallback, no coercion -- and still wrong, because nothing gates the age of
 *      the file. This is the /dashboard/ defect (a hand-typed changelog rendered
 *      under the word "Recent", ~324 days behind) and the /monitoring/ one (a green
 *      "healthy" card from a file no workflow will ever rewrite again).
 *
 * HOW THIS FILE TESTS
 * -------------------
 * Every case FORCES the state and observes the rendered result. Nothing here is
 * satisfied by reading the code and agreeing with it: functions are lifted out of
 * the pages by name and run against a stub DOM and a stub fetch, with the input in
 * the state that used to produce the lie. A guard seen only in its passing state
 * has not been shown to work.
 *
 * A handful of assertions ARE source-level, and they are labelled. They exist for
 * the shapes where the lie is a single token (`|| 0`) whose reintroduction would be
 * invisible to any output test that happened to use a populated fixture. They are a
 * second line, never the only one.
 *
 * The staleness verdicts come from /assets/js/freshness.js -- the site's ONE
 * staleness gate, written by the /monitoring/ seat in the same session. This file
 * does not test freshness.js itself (scripts/test-freshness.js does); it tests that
 * these pages call it and BRANCH ON `.fresh`, which is the clause that stops a
 * future state added to that file from silently rendering as current.
 *
 * Run: node scripts/test-manufactured-confidence.js      (exit 0 = pass)
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const Freshness = require(path.join(ROOT, 'public', 'assets', 'js', 'freshness.js'));
const ESC = require(path.join(ROOT, 'public', 'assets', 'js', 'escape.js'));

const DAY = 86400000;
const HOUR = 3600000;

let failures = 0;
function check(cond, msg) {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) { failures++; }
}

// core.autocrlf=true on Windows, so normalise before any \n-sensitive matching.
function page(rel) {
  const p = path.join(ROOT, rel);
  if (!fs.existsSync(p)) {
    console.error('FAIL: page missing: ' + rel + ' (renamed? re-anchor this test, do not delete it)');
    process.exit(1);
  }
  return fs.readFileSync(p, 'utf8').replace(/\r\n/g, '\n');
}

// Comments in these pages describe the old bug by name. Strip them before asking
// "does this page still contain the bug?" -- otherwise the explanation trips the test.
function codeOnly(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^[ \t]*\/\/.*$/gm, '');
}

/*
 * Lift a function out of a page by name, by brace matching from its header. Works
 * for `function f(`, `const f = (`, `const f = function`, `async function f(` and
 * `f: function` -- every declaration shape these pages use.
 *
 * Anchored on the NAME. If a function is renamed or deleted, this throws and the
 * test fails loudly rather than quietly testing nothing.
 */
function extractFn(src, name) {
  const patterns = [
    new RegExp('(?:^|\\n)\\s*(?:async\\s+)?function\\s+' + name + '\\s*\\('),
    new RegExp('(?:^|\\n)\\s*(?:const|let|var)\\s+' + name + '\\s*=\\s*(?:async\\s*)?(?:function\\s*\\(|\\()'),
  ];
  let start = -1;
  for (const re of patterns) {
    const m = re.exec(src);
    if (m) { start = m.index + (src[m.index] === '\n' ? 1 : 0); break; }
  }
  if (start < 0) {
    throw new Error('could not find function ' + name + ' (renamed? re-anchor this test)');
  }
  // Brace-match from the first { after the header.
  let i = src.indexOf('{', start);
  if (i < 0) { throw new Error('no body for ' + name); }
  let depth = 0;
  let inStr = null, inTpl = false, inLine = false, inBlock = false, inRe = false;
  for (; i < src.length; i++) {
    const c = src[i], p = src[i - 1];
    if (inLine) { if (c === '\n') { inLine = false; } continue; }
    if (inBlock) { if (c === '/' && p === '*') { inBlock = false; } continue; }
    if (inStr) { if (c === inStr && p !== '\\') { inStr = null; } continue; }
    if (inTpl) { if (c === '`' && p !== '\\') { inTpl = false; } continue; }
    if (inRe) { if (c === '/' && p !== '\\') { inRe = false; } continue; }
    if (c === '/' && src[i + 1] === '/') { inLine = true; continue; }
    if (c === '/' && src[i + 1] === '*') { inBlock = true; continue; }
    if (c === '"' || c === "'") { inStr = c; continue; }
    if (c === '`') { inTpl = true; continue; }
    if (c === '{') { depth++; continue; }
    if (c === '}') {
      depth--;
      if (depth === 0) { return src.slice(start, i + 1); }
    }
  }
  throw new Error('unbalanced braces extracting ' + name);
}

function bundle(src, names) {
  return names.map((n) => extractFn(src, n)).join('\n');
}

// ---------------------------------------------------------------------------
// Stub DOM. Only what these renderers touch. Every node records what was written
// to it, so an assertion can read the RENDERED result rather than the intention.
// ---------------------------------------------------------------------------
function makeNode(id) {
  return {
    id: id,
    textContent: '',
    innerHTML: '',
    title: '',
    hidden: false,
    style: { display: '', cssText: '', width: '' },
    dataset: {},
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      contains(c) { return this._s.has(c); },
    },
    appendChild() {},
    querySelector() { return null; },
    closest() { return null; },
    setAttribute() {},
    removeAttribute() {},
    addEventListener() {},
    parentElement: null,
  };
}

function makeDoc(ids) {
  const nodes = {};
  (ids || []).forEach((id) => { nodes[id] = makeNode(id); });
  const doc = {
    nodes: nodes,
    getElementById(id) { return Object.prototype.hasOwnProperty.call(nodes, id) ? nodes[id] : null; },
    querySelectorAll() { return []; },
    createElement(tag) { const n = makeNode(''); n.tag = tag; return n; },
    addEventListener() {},
  };
  Object.keys(nodes).forEach((id) => { nodes[id].parentElement = makeNode('parent-of-' + id); });
  return doc;
}

const quietConsole = { warn() {}, error() {}, log() {} };

// A timestamp that reads as "right now" to within a minute. Class C is exactly the
// substitution of this for a value that was never read.
function looksLikeNow(text) {
  if (!text) { return false; }
  const s = String(text);
  // Any rendering of a moment within the last ten minutes, in any locale format the
  // page might produce. Cheapest reliable test: does the string contain today's
  // date in either ISO or locale form, AND no age label?
  const now = new Date();
  const iso = now.toISOString().slice(0, 10);
  const loc = now.toLocaleDateString();
  return (s.includes(iso) || s.includes(loc));
}

// ===========================================================================
console.log('\nA. SILENT SUBSET — a set assembled from failed reads is not a finding');
// ===========================================================================
{
  const src = page('public/players/index.html');
  const code = codeOnly(src);

  // Force: EVERY fetch fails. The page has read nothing about anybody.
  const fnSrc = bundle(src, ['loadPlayerProfile', 'aggregatePlayerData']);
  function runPlayers(fetchImpl) {
    let shown = null;
    let profiled = null;
    const doc = makeDoc(['loading', 'error', 'player-content']);
    const mod = new Function(
      'document', 'fetch', 'console', 'playerName', 'showError', 'displayPlayerProfile', 'toNumber',
      fnSrc + '\nreturn { loadPlayerProfile: loadPlayerProfile };'
    )(doc, fetchImpl, quietConsole, 'Ada',
      (m) => { shown = m; },
      (d) => { profiled = d; },
      ESC.toNumber);
    return mod.loadPlayerProfile().then(() => ({ shown: shown, profiled: profiled }));
  }

  const allFail = async () => { throw new Error('offline'); };

  const week = (weekId, players) => ({
    meta: { week_id: weekId, total_participants: players.length },
    entries: players.map((n, i) => ({
      player_name: n, score: 1000 - i * 10, final_doom: 12.5, level_reached: 7,
    })),
  });

  return (async () => {
    // --- 1. total read failure ------------------------------------------------
    const r1 = await runPlayers(allFail);
    check(r1.profiled === null, 'total read failure renders no profile at all');
    check(r1.shown !== null, 'total read failure says something rather than hanging on "Loading"');
    check(!/may not have participated/i.test(String(r1.shown)),
      'total read failure does NOT claim the player may not have participated (this was the lie)');
    check(/could not be read|not know|unknown/i.test(String(r1.shown)),
      'total read failure names itself as a read failure: ' + JSON.stringify(String(r1.shown).slice(0, 80)));

    // --- 2. partial read: player genuinely absent from what loaded ------------
    const partialFetch = async (url) => {
      const u = String(url);
      if (u.indexOf('/weekly/current.json') >= 0) {
        return { ok: true, json: async () => week('2026_W35', ['Grace']) };
      }
      if (u.indexOf('/archive/index.json') >= 0) {
        return { ok: true, json: async () => ({ archives: [{ file: 'a.json' }, { file: 'b.json' }] }) };
      }
      if (u.indexOf('/archive/a.json') >= 0) {
        return { ok: true, json: async () => week('2026_W34', ['Grace']) };
      }
      return { ok: false, status: 404, json: async () => ({}) };   // b.json is unread
    };
    const r2 = await runPlayers(partialFetch);
    check(r2.profiled === null, 'player absent from every readable week renders no profile');
    check(/did not load|incomplete/i.test(String(r2.shown)),
      '"not found" over an incomplete read SAYS the read was incomplete: ' +
      JSON.stringify(String(r2.shown).slice(0, 110)));

    // --- 3. complete read, player genuinely absent ----------------------------
    const completeFetch = async (url) => {
      const u = String(url);
      if (u.indexOf('/weekly/current.json') >= 0) {
        return { ok: true, json: async () => week('2026_W35', ['Grace']) };
      }
      if (u.indexOf('/archive/index.json') >= 0) {
        return { ok: true, json: async () => ({ archives: [] }) };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    };
    const r3 = await runPlayers(completeFetch);
    check(r3.profiled === null, 'complete read, player absent: no profile');
    check(!/did not load|incomplete/i.test(String(r3.shown)),
      'a COMPLETE read does not cry incomplete — the note is silent when there is no hole');

    // --- 4. partial read, player present: the numbers carry the caveat -------
    const presentPartial = async (url) => {
      const u = String(url);
      if (u.indexOf('/weekly/current.json') >= 0) {
        return { ok: true, json: async () => week('2026_W35', ['Ada', 'Grace']) };
      }
      if (u.indexOf('/archive/index.json') >= 0) {
        return { ok: true, json: async () => ({ archives: [{ file: 'a.json' }] }) };
      }
      return { ok: false, status: 500, json: async () => ({}) };   // a.json unread
    };
    const r4 = await runPlayers(presentPartial);
    check(r4.profiled !== null, 'partial read with the player present still renders a profile');
    check(r4.profiled && r4.profiled.weeksUnread === 1,
      'the profile carries the count of weeks that did not load (got ' +
      (r4.profiled && r4.profiled.weeksUnread) + ')');

    // The note itself, rendered.
    const dsp = extractFn(src, 'displayPlayerProfile');
    const doc = makeDoc(['loading', 'player-content', 'incomplete-note', 'player-name',
      'player-avatar', 'total-games', 'best-score', 'avg-score', 'best-rank']);
    try {
      new Function('document', 'data', 'toNumber', dsp + '\ndisplayPlayerProfile(data);')(
        doc, r4.profiled, ESC.toNumber);
    } catch (e) { /* the tail of that function touches nodes this stub does not carry */ }
    const noteText = doc.nodes['incomplete-note'].textContent;
    check(/Incomplete/.test(noteText) && doc.nodes['incomplete-note'].style.display === 'block',
      'the incomplete-read note is VISIBLE above the figures it undermines');
    check(/lower bounds|not this player/i.test(noteText),
      'the note says the ranks and totals are not the player\'s record: ' +
      JSON.stringify(noteText.slice(0, 90)));

    // --- source contract: the drop-and-forget shape is gone -------------------
    check(!/archiveData\s*\)\s*;[\s\S]{0,200}filter\(d\s*=>\s*d\s*!==\s*null\)[\s\S]{0,80}aggregatePlayerData/.test(code),
      '[source] failures are counted before they are filtered away');

    // =======================================================================
    console.log('\nA (cont). /league/archive.html — an archive\'s claim is completeness');
    // =======================================================================
    const asrc = page('public/league/archive.html');
    const acode = codeOnly(asrc);
    const afns = bundle(asrc, ['showNoResults', 'showCompleteness']);
    function runArchive(indexUnread, listed, unread) {
      const d = makeDoc(['loading', 'no-results', 'archive-grid', 'completeness-note']);
      new Function('document', afns +
        '\nshowCompleteness(arguments[1], arguments[2], arguments[3]);' +
        '\nshowNoResults(arguments[1] || arguments[3] > 0);'
      )(d, indexUnread, listed, unread);
      return d.nodes;
    }
    const clean = runArchive(false, 3, 0);
    check(clean['no-results'].style.display === 'block',
      'a COMPLETE read with nothing archived may say "no league weeks archived yet"');
    check(clean['completeness-note'].style.display === 'none',
      '...and says nothing about completeness, because there is no hole');

    const brokenIndex = runArchive(true, 0, 0);
    check(brokenIndex['no-results'].style.display === 'none',
      'an unreadable INDEX must NOT render "no league weeks have been archived yet"');
    check(/does not know how many/i.test(brokenIndex['completeness-note'].textContent),
      '...it says the count of archived weeks is unknown: ' +
      JSON.stringify(brokenIndex['completeness-note'].textContent.slice(0, 80)));

    const partialFiles = runArchive(false, 8, 3);
    check(/3 of 8/.test(partialFiles['completeness-note'].textContent),
      'a partial file read names how many of how many failed');
    check(/not absent from the league/i.test(partialFiles['completeness-note'].textContent),
      '...and distinguishes "missing from this view" from "does not exist"');

    check(!/No fallback needed - empty array is fine/.test(acode),
      '[source] the "empty array is fine" comment is gone with the assumption it recorded');

    // =======================================================================
    console.log('\nA (cont). /league/ trend chart — a gap is not a zero');
    // =======================================================================
    const lsrc = page('public/league/index.html');
    const lcode = codeOnly(lsrc);
    check(!/total_participants\s*\|\|\s*0/.test(lcode),
      '[source] the chart no longer plots an absent participant count as 0');
    check(/measured\(n\)\s*\?\s*toNumber\(n\)\s*:\s*null/.test(lcode),
      '[source] an unmeasured week becomes null (a break in the line), not a point at zero');
    check(/mini-trend-caption/.test(lcode),
      '[source] the chart carries a caption element for stating how many points are missing');

    // =====================================================================
    console.log('\nB. ABSENT COERCED TO ZERO — /league/ counters');
    // =====================================================================
    const lfns = bundle(lsrc, ['measured', 'setValue', 'setCount']);
    function runCount(raw) {
      const d = makeDoc(['x']);
      new Function('document', 'toNumber', 'UNKNOWN_VALUE', lfns + '\nsetCount("x", arguments[3]);')(
        d, ESC.toNumber, '—', raw);
      return d.nodes['x'];
    }
    check(runCount(undefined).textContent === '—', 'absent count renders an em dash, not 0');
    check(runCount(null).textContent === '—', 'null count renders an em dash, not 0');
    check(runCount('').textContent === '—', 'empty-string count renders an em dash, not 0');
    check(runCount('nope').textContent === '—', 'non-numeric count renders an em dash, not 0');
    check(runCount(true).textContent === '—', 'a boolean is not a count');
    check(runCount(0).textContent === '0', 'a MEASURED zero still renders as 0 — the fix must not hide real zeros');
    check(runCount(1234).textContent === '1,234', 'a measured count renders normally');
    check(/not the same as a value of zero/i.test(runCount(undefined).title),
      'the unknown state explains itself on hover rather than being a bare dash');

    check(!/total_participants\s*\|\|\s*0|total_submissions\s*\|\|\s*0|total_games\s*\|\|\s*0|unique_players\s*\|\|\s*0/.test(lcode),
      '[source] none of the four league counters uses `|| 0`');

    // =====================================================================
    console.log('\nB (cont). /leaderboard/ — an average of nothing is not zero');
    // =====================================================================
    const bsrc = page('public/leaderboard/index.html');
    const bcode = codeOnly(bsrc);
    const stats = extractFn(bsrc, 'displayStats');
    function runStats(entries) {
      const d = makeDoc(['total-players', 'total-games', 'avg-score', 'avg-pdoom',
        'current-seed', 'economic-model', 'game-version']);
      new Function('document', 'toNumber', 'data', stats + '\ndisplayStats(data);')(
        d, ESC.toNumber, { entries: entries, meta: {} });
      return d.nodes;
    }
    const empty = runStats([]);
    check(empty['avg-score'].textContent === '—',
      'empty board: Average Score is an em dash, not 0 (was `: 0`)');
    check(empty['avg-pdoom'].textContent === '—',
      'empty board: Average p(Doom) is an em dash, not "0.0%" — the reassuring one');
    check(/nothing to average/i.test(empty['avg-pdoom'].title),
      '...and says why: ' + JSON.stringify(empty['avg-pdoom'].title.slice(0, 60)));
    check(empty['total-games'].textContent === '0',
      'empty board: the COUNT of games is still a real 0 — entries.length genuinely is zero');

    const populated = runStats([
      { player_name: 'Ada', score: 100, final_doom: 10 },
      { player_name: 'Grace', score: 200, final_doom: 20 },
    ]);
    check(populated['avg-score'].textContent === '150', 'populated board still averages correctly');
    check(populated['avg-pdoom'].textContent === '15.0%', 'populated board still shows a p(Doom) average');
    check(populated['avg-score'].title === '', '...with no unknown-state explanation attached');

    check(!/:\s*'0\.0'/.test(bcode), '[source] the `: \'0.0\'` p(Doom) fallback is gone');

    // =====================================================================
    console.log('\nB (cont). /state-of-doom/ — "0 live" is a claim about the site');
    // =====================================================================
    const ssrc = page('public/state-of-doom/index.html');
    const scode = codeOnly(ssrc);
    check(/Array\.isArray\(cfg\.clocks\)/.test(scode),
      '[source] a document with no clocks array is a read failure, not zero clocks');
    check(/clocks\.length\s*\n?\s*\?/.test(scode) || /clocks\.length$/m.test(scode),
      '[source] the "N live" tally is gated on there having been clocks to count');
    check(/if\(!r\.ok\)/.test(scode.replace(/\s+/g, '')) || /if\s*\(\s*!r\.ok\s*\)/.test(scode),
      '[source] a non-200 is an error rather than something handed to the JSON parser');

    // =====================================================================
    console.log('\nC. ABSENT TIMESTAMP REPLACED BY NOW — /docs/');
    // =====================================================================
    const dsrc = page('public/docs/index.html');
    const dcode = codeOnly(dsrc);
    const START = '/* ========== STATUS STAMP';
    const i0 = dsrc.indexOf(START);
    check(i0 >= 0, 'the status-stamp block is where this test expects it');
    const blk = codeOnly(dsrc.slice(i0, dsrc.indexOf('</script>', i0)));

    async function runDocs(statusDoc, opts) {
      const o = opts || {};
      const d = makeDoc(['last-updated']);
      const f = async () => {
        if (o.fails) { throw new Error('offline'); }
        if (o.status) { return { ok: false, status: o.status, json: async () => ({}) }; }
        return { ok: true, json: async () => statusDoc };
      };
      const run = new Function('document', 'fetch', 'Freshness',
        blk + '\nreturn Promise.resolve();')(d, f, Freshness);
      // The block is an async IIFE; give its microtasks a turn to settle.
      await run; await new Promise((r) => setTimeout(r, 0)); await new Promise((r) => setTimeout(r, 0));
      return d.nodes['last-updated'];
    }

    const noField = await runDocs({ website: { version: '1.2.0' } });
    check(noField.textContent === 'unknown',
      'an ABSENT lastUpdated renders "unknown" — this is the exact line that used to print new Date()');
    check(!looksLikeNow(noField.textContent),
      '...and carries no rendering of the current moment anywhere in it');

    const failed = await runDocs(null, { fails: true });
    check(failed.textContent === 'unknown' && !looksLikeNow(failed.textContent),
      'a failed fetch renders "unknown" and no time (it used to leave "Loading..." forever)');

    const http500 = await runDocs(null, { status: 500 });
    check(http500.textContent === 'unknown', 'a non-200 renders "unknown", not the placeholder');

    const stale = await runDocs({ website: { lastUpdated: new Date(Date.now() - 400 * DAY).toISOString() } });
    check(/STALE/.test(stale.textContent),
      'a year-old stamp is LABELLED stale rather than printed bare: ' +
      JSON.stringify(stale.textContent.slice(0, 70)));
    check(/ago/.test(stale.textContent), '...and states how old it is');

    const future = await runDocs({ website: { lastUpdated: new Date(Date.now() + 90 * DAY).toISOString() } });
    check(/FUTURE-DATED/.test(future.textContent),
      'a future-dated stamp is refused as a broken clock, not shown as the freshest thing on the page');

    const fresh = await runDocs({ website: { lastUpdated: new Date(Date.now() - 2 * HOUR).toISOString() } });
    check(!/STALE|UNKNOWN|FUTURE/.test(fresh.textContent) && fresh.textContent !== 'unknown',
      'a genuinely current stamp renders plainly, with no scare label');

    const garbage = await runDocs({ website: { lastUpdated: 'sometime last spring' } });
    check(garbage.textContent === 'unknown',
      'an unparseable stamp is UNKNOWN, never coerced into a date');

    check(!/new Date\(\)\.toISOString\(\)/.test(dcode),
      '[source] `new Date().toISOString()` no longer appears anywhere on the page');

    // =====================================================================
    console.log('\nD. STALE SOURCE — derived correctly, and still out of date');
    // =====================================================================

    // --- /game-stats/ ---------------------------------------------------
    const gsrc = page('public/game-stats/index.html');
    const gcode = codeOnly(gsrc);
    const gfn = bundle(gsrc, ['measured', 'loadStats']);
    async function runGameStats(data, opts) {
      const o = opts || {};
      const ids = ['baseline-doom', 'frontier-labs', 'strategic-possibilities',
        'open-issues', 'repo-stars', 'last-release', 'last-updated'];
      const d = makeDoc(ids);
      const f = async () => {
        if (o.fails) { throw new Error('offline'); }
        if (o.status) { return { ok: false, status: o.status, json: async () => ({}) }; }
        return { ok: true, json: async () => data };
      };
      await new Function('document', 'fetch', 'console', 'Freshness',
        gfn + '\nreturn loadStats();')(d, f, quietConsole, Freshness);
      return d.nodes;
    }

    const freshStats = {
      last_updated: new Date(Date.now() - 2 * HOUR).toISOString(),
      repository_stats: { open_issues: 200, stars: 7 },
      latest_release: { published_at: new Date(Date.now() - 3 * DAY).toISOString() },
      game_stats: {},
    };
    const gf = await runGameStats(freshStats);
    check(gf['open-issues'].textContent === '200', 'fresh: the open-issue count renders');
    check(!/STALE|unknown/i.test(gf['last-updated'].textContent), 'fresh: no staleness label');

    const staleStats = Object.assign({}, freshStats, {
      last_updated: new Date(Date.now() - 40 * DAY).toISOString(),
    });
    const gs = await runGameStats(staleStats);
    check(/STALE/.test(gs['last-updated'].textContent),
      'stale: the whole card set is labelled STALE (this is the /dashboard/ defect, six tiles of it)');
    check(/not what is true now/i.test(gs['last-updated'].textContent),
      '...and says the figures are what a snapshot said: ' +
      JSON.stringify(gs['last-updated'].textContent.slice(-70)));

    const noStamp = await runGameStats(Object.assign({}, freshStats, { last_updated: undefined }));
    check(/unknown/i.test(noStamp['last-updated'].textContent) && !looksLikeNow(noStamp['last-updated'].textContent),
      'no stamp: age is unknown and no time is printed');

    const missingRepo = await runGameStats(Object.assign({}, freshStats, { repository_stats: {} }));
    check(missingRepo['open-issues'].textContent === '—',
      'absent open_issues renders an em dash (it used to render the string "undefined")');
    check(missingRepo['open-issues'].classList.contains('stat-unmeasured'),
      '...and is styled as unmeasured, not in the same weight as a measured tile');

    const noRelease = await runGameStats(Object.assign({}, freshStats, { latest_release: {} }));
    check(noRelease['last-release'].textContent === '—',
      '"Days Since Release" with no release date is an em dash, not a number derived from NaN');

    const gfail = await runGameStats(null, { fails: true });
    check(!looksLikeNow(gfail['last-updated'].textContent),
      'a failed read prints no time at all');
    check(/could not be read/i.test(gfail['last-updated'].textContent),
      '...and names itself a read failure: ' + JSON.stringify(gfail['last-updated'].textContent.slice(0, 70)));

    // --- /frontier-labs/ ------------------------------------------------
    const fsrc = page('public/frontier-labs/index.html');
    const ffn = bundle(fsrc, ['labCard', 'render']);
    function runLabs(doc) {
      const d = makeDoc(['n-roster', 'n-omissions', 'n-hypothetical', 'roster-asof',
        'roster-grid', 'omissions-list', 'hypothetical-grid']);
      new Function('document', 'escapeHTML', 'safeUrl', 'Freshness', 'd',
        ffn + '\nrender(d);')(d, ESC.escapeHTML, ESC.safeUrl, Freshness, doc);
      return d.nodes;
    }
    const roster = (asOf) => ({
      as_of: asOf,
      roster: { labs: [{ name: 'L', kind: 'real', status: 'active', founded: '2015' }] },
      known_omissions: [], hypothetical: [],
    });
    const labsFresh = runLabs(roster(new Date(Date.now() - 5 * DAY).toISOString().slice(0, 10)));
    check(labsFresh['n-roster'].textContent === 1, 'fresh roster: the count renders');
    check(labsFresh['roster-asof'].hidden === true, 'fresh roster: no age warning');

    const labsStale = runLabs(roster('2020-01-01'));
    check(labsStale['roster-asof'].hidden === false,
      'a roster last reviewed years ago says so next to its count');
    check(/last reviewed/i.test(labsStale['roster-asof'].textContent),
      '...naming how long ago: ' + JSON.stringify(labsStale['roster-asof'].textContent.slice(0, 70)));
    check(labsStale['n-roster'].textContent === 1,
      '...while still showing the count, because the list it counts is on the same page');

    const labsNoDate = runLabs({ roster: { labs: [] }, known_omissions: [], hypothetical: [] });
    check(labsNoDate['roster-asof'].hidden === false &&
      /not the same as current/i.test(labsNoDate['roster-asof'].textContent),
      'a roster with no as-of date reads as UNKNOWN age, never as current');

    // --- /metrics/ ------------------------------------------------------
    const msrc = page('public/metrics/index.html');
    const mfn = bundle(msrc, ['present', 'num', 'pct', 'secs', 'el', 'setText', 'renderLatest']);
    function runMetrics(latest) {
      const d = makeDoc(['t-visitors', 't-pageviews', 't-visits', 't-duration', 't-bounce',
        'window-line', 'latest-errors']);
      new Function('document', 'escapeHTML', 'toNumber', 'Freshness', 'latest',
        'var ABSENT = "\\u2014";\n' + mfn + '\nrenderLatest(latest);')(
        d, ESC.escapeHTML, ESC.toNumber, Freshness, latest);
      return d.nodes;
    }
    const snapshot = (capturedAt) => ({
      captured_at_utc: capturedAt,
      snapshot_date: capturedAt ? String(capturedAt).slice(0, 10) : undefined,
      coverage: { first_date: '2026-07-01', last_date: '2026-07-30', note: '', missing_dates: [], zero_dates: [] },
      sections: { aggregate: { results: { visitors: { value: 42 }, pageviews: { value: 99 } } } },
    });
    const mFresh = runMetrics(snapshot(new Date(Date.now() - 6 * HOUR).toISOString()));
    check(mFresh['t-visitors'].textContent === '42', 'fresh snapshot: tiles render');
    check(!/STALE|UNKNOWN/.test(mFresh['latest-errors'].innerHTML), 'fresh snapshot: no staleness banner');

    const mStale = runMetrics(snapshot(new Date(Date.now() - 45 * DAY).toISOString()));
    check(/STALE/.test(mStale['latest-errors'].innerHTML),
      'a 45-day-old snapshot raises a STALE banner above the tiles');
    check(/not a reading of now/i.test(mStale['latest-errors'].innerHTML),
      '...saying the totals are not a reading of now');
    check(mStale['t-visitors'].textContent === '42',
      '...while still showing what the snapshot recorded — nothing is substituted');

    const mNoStamp = runMetrics(snapshot(undefined));
    check(/UNKNOWN/.test(mNoStamp['latest-errors'].innerHTML),
      'a snapshot with no capture stamp is UNKNOWN age, not assumed current');

    const mFuture = runMetrics(snapshot(new Date(Date.now() + 30 * DAY).toISOString()));
    check(/FUTURE-DATED/.test(mFuture['latest-errors'].innerHTML),
      'a future-dated snapshot is refused as a broken clock');

    // =====================================================================
    console.log('\nE. WIRING — every page that gates on age loads the ONE gate, blocking');
    // =====================================================================
    const CALLERS = [
      'public/docs/index.html',
      'public/game-stats/index.html',
      'public/frontier-labs/index.html',
      'public/metrics/index.html',
      'public/leaderboard/index.html',
    ];
    CALLERS.forEach((rel) => {
      const s = page(rel);
      const uses = /Freshness\s*\./.test(codeOnly(s));
      const tag = /<script src="\/assets\/js\/freshness\.js"><\/script>/.test(s);
      const deferred = /<script[^>]*\b(defer|async)\b[^>]*freshness\.js/.test(s);
      check(uses, rel + ' calls Freshness');
      check(tag, rel + ' loads /assets/js/freshness.js');
      check(!deferred, rel + ' loads it BLOCKING (defer/async would let the renderer run first)');
      // The clause that matters: branching on `.state !== stale` would silently
      // start rendering any state added to freshness.js later.
      check(/\.fresh\b/.test(codeOnly(s)) || /state\s*===\s*Freshness\.UNKNOWN/.test(codeOnly(s)),
        rel + ' branches on `.fresh` (or names UNKNOWN explicitly), not on a negated state list');
    });

    // A page must not roll its own STALENESS VERDICT beside the shared gate --
    // a second implementation of "how old is too old" is how five escapers happened.
    //
    // Deliberately NOT applied to public/game-stats/index.html: that page computes
    // `Math.floor((Date.now() - releaseMs) / 86400000)` for its "Days Since Release"
    // tile, which is a PUBLISHED METRIC the page exists to show, not a gate on its
    // own currency. Age-as-a-value and age-as-a-verdict are different things and
    // only the second one belongs behind Freshness. (An earlier draft of this check
    // did include that page, went red, and the red was the test being wrong.)
    ['public/docs/index.html', 'public/frontier-labs/index.html', 'public/metrics/index.html']
      .forEach((rel) => {
        const c = codeOnly(page(rel));
        check(!/Date\.now\(\)\s*-\s*[^;]*\)\s*\/\s*(86400000|3600000)/.test(c),
          rel + ' does not hand-roll an age in ms beside the shared gate');
      });

    // =====================================================================
    console.log('\nF. THE GATE ITSELF STILL REFUSES (sanity, not coverage)');
    // =====================================================================
    // scripts/test-freshness.js owns freshness.js. These four exist so that a
    // change there which quietly made `.fresh` permissive would fail HERE too --
    // every assertion above is downstream of this one property.
    check(Freshness.assess(null, 24).fresh === false, 'assess(null) is not fresh');
    check(Freshness.assess(new Date(Date.now() - 400 * DAY).toISOString(), 24).fresh === false,
      'assess(400 days old, 24h window) is not fresh');
    check(Freshness.assess(new Date(Date.now() + 90 * DAY).toISOString(), 24).fresh === false,
      'assess(future) is not fresh');
    check(Freshness.assess(new Date().toISOString(), undefined).fresh === false,
      'assess with NO declared window is not fresh — a caller cannot pass by forgetting the policy');
    check(Freshness.unavailable('x').fresh === false, 'unavailable() is not fresh');

    // ===========================================================================
    console.log('');
    if (failures) {
      console.error(failures + ' FAILED');
      process.exit(1);
    }
    console.log('All manufactured-confidence checks passed.');
  })().catch((e) => {
    console.error('\nHARNESS ERROR: ' + (e && e.stack ? e.stack : e));
    console.error('(a function was renamed or a block moved — re-anchor this test, do not delete it)');
    process.exit(1);
  });
}
