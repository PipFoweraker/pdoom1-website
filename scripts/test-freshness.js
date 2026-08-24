#!/usr/bin/env node
/*
 * Guard: the shared staleness gate, public/assets/js/freshness.js, actually refuses.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * freshness.js claims six things in its header comment. A docstring is documentation,
 * not evidence -- and a guard seen only in its passing state has not been shown to
 * work, because green is equally consistent with "the condition is safe" and "the
 * check never fires". So every case below FORCES the failing state and observes the
 * refusal. The happy path is the smallest section in the file, on purpose.
 *
 * The defect this gate exists to stop, measured twice in this repo:
 *   /dashboard/  rendered a hand-typed changelog that had frozen ~324 days back
 *                under the word "Recent" (fixed 2026-08-03).
 *   /monitoring/ rendered "healthy / 100%" out of a file whose only two writers are
 *                workflow_dispatch-only, so nothing had refreshed it since
 *                2026-07-17 (fixed 2026-08-25).
 * Both are the same shape: a correct read of a source that stopped moving.
 *
 * THE CLAUSE THIS FILE CARES ABOUT MOST is #2 of the contract: `verdict.fresh` is
 * true for exactly one state and false for every other, INCLUDING states added
 * later. That is tested structurally (every state the module can name is enumerated
 * and its verdict checked), not by listing today's three failure modes -- a list
 * only ever covers what someone remembered, which is how test-board-escaping.js's
 * first version passed while thirteen fields were unprotected.
 *
 * Run: node scripts/test-freshness.js      (exit 0 = pass)
 */

'use strict';

const path = require('path');
const fs = require('fs');

const ROOT = path.join(__dirname, '..');
const SRC = path.join(ROOT, 'public', 'assets', 'js', 'freshness.js');
const F = require(SRC);

let failures = 0;
function check(cond, msg) {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) { failures++; }
}

const HOUR = 3600000;
const DAY = 24 * HOUR;
const isoAgo = (ms) => new Date(Date.now() - ms).toISOString();

// ===========================================================================
console.log('\n1. the module exists, ships its own states, and exports nothing else');
// ===========================================================================
check(fs.existsSync(SRC), 'public/assets/js/freshness.js exists');
check(typeof F.assess === 'function' && typeof F.unavailable === 'function',
  'exports assess() and unavailable()');
check(typeof F.ageHours === 'function' && typeof F.ageText === 'function',
  'exports the two primitives assess() is built on');

// There is deliberately NO API that hands back a remembered value. If one ever
// appears, this fails and whoever added it has to argue for it in a review.
const REMEMBERING = ['lastKnown', 'lastGood', 'fallback', 'cached', 'remember', 'orLast'];
const smuggled = Object.keys(F).filter((k) =>
  REMEMBERING.some((bad) => k.toLowerCase().includes(bad.toLowerCase())));
check(smuggled.length === 0,
  smuggled.length === 0
    ? 'no export offers a remembered/last-known value (contract clause 1)'
    : 'SMUGGLED last-known-value API: ' + smuggled.join(', '));

// ===========================================================================
console.log('\n2. happy path -- a genuinely fresh source, and only that, is fresh');
// ===========================================================================
let v = F.assess(isoAgo(2 * HOUR), 24);
check(v.state === F.FRESH && v.fresh === true, 'a 2h-old source inside a 24h window is FRESH');
check(v.label === 'CURRENT', 'labelled CURRENT');
check(v.reason === '', 'a fresh verdict carries no excuse text');
check(Math.abs(v.ageHours - 2) < 0.05, 'reports the age it measured (' + v.ageHours.toFixed(2) + 'h)');

// Accepted input shapes. All three must agree, or a caller picks a shape and gets a
// different answer for the same instant.
const twoHoursAgo = Date.now() - 2 * HOUR;
check(F.assess(new Date(twoHoursAgo), 24).fresh === true, 'a real Date instance is accepted');
check(F.assess(twoHoursAgo, 24).fresh === true, 'a millisecond epoch NUMBER is accepted');
check(F.assess(new Date(twoHoursAgo).toISOString(), 24).fresh === true, 'an ISO string is accepted');

// ===========================================================================
console.log('\n3. FORCED FAILURE -- a source that stopped moving is refused');
// ===========================================================================
// This is the /monitoring/ defect reproduced exactly: the read succeeds, the JSON is
// well-formed, every field is correct, and the file has not been written in weeks.
v = F.assess(isoAgo(39 * DAY), 24);
check(v.fresh === false, 'a 39-day-old source in a 24h window is NOT fresh');
check(v.state === F.STALE, 'named STALE (not merely "not fresh")');
check(v.label === 'STALE', 'labelled STALE for the reader');
check(/39 days ago/.test(v.reason), 'the reason says HOW old it is: ' + JSON.stringify(v.reason.slice(0, 60) + '...'));
check(/24 hours/.test(v.reason), 'and states the window it was judged against');
check(!/health|ok|fine|good/i.test(v.label), 'the label cannot be mistaken for a pass');

// The edge is a real edge, and it is on the right side of the window.
check(F.assess(isoAgo(23.5 * HOUR), 24).fresh === true, 'just inside a 24h window: fresh');
check(F.assess(isoAgo(24.5 * HOUR), 24).fresh === false, 'just outside it: not fresh');

// ===========================================================================
console.log('\n4. FORCED FAILURE -- an unreadable age is UNKNOWN, never 0, never fine');
// ===========================================================================
// 0 is the single most dangerous wrong answer: it renders as "just written".
const UNREADABLE = [
  [null, 'null'],
  [undefined, 'undefined'],
  ['', 'empty string'],
  ['not a date', 'prose'],
  ['2026-13-45T99:99:99Z', 'an out-of-range ISO-shaped string'],
  [{}, 'an empty object'],
  [{ iso: '2026-08-25' }, 'an object carrying the date one level down'],
  [[], 'an array'],
  [true, 'the boolean true (new Date(true) is 1970, which parses)'],
  [false, 'the boolean false'],
  [NaN, 'NaN'],
  [Infinity, 'Infinity'],
  ['1756000000', 'a bare-digit string -- seconds or milliseconds is a 1000x guess'],
];
for (const [bad, name] of UNREADABLE) {
  const r = F.assess(bad, 24);
  check(r.fresh === false && r.state === F.UNKNOWN && r.ageHours === null,
    'UNKNOWN (not 0, not fresh) for ' + name);
}
check(F.ageHours(null) === null && F.ageHours({}) === null,
  'ageHours() returns null rather than a number it had to invent');
check(F.assess(null, 24).ageText === 'age unknown',
  'the rendered age is the words "age unknown", so the gap is visible on the page');

// The one number that legitimately parses and must NOT be treated as unknown.
check(F.assess(0, 24).state === F.STALE,
  'epoch 0 is a real date (1970) and reports STALE -- refusing it as UNKNOWN would ' +
  'hide a clock bug behind the same verdict as a missing field');

// ===========================================================================
console.log('\n5. FORCED FAILURE -- a future date is a broken clock, not a scoop');
// ===========================================================================
v = F.assess(new Date(Date.now() + 30 * DAY).toISOString(), 24);
check(v.fresh === false, 'a source dated 30 days ahead is NOT fresh');
check(v.state === F.FUTURE, 'named FUTURE, distinct from STALE and from UNKNOWN');
check(/from now/.test(v.ageText), 'the age reads as "from now": ' + JSON.stringify(v.ageText));
check(/clock/.test(v.reason), 'the reason names the actual cause (a wrong clock)');

// ...but ordinary skew between a CI runner and a reader's browser is absorbed.
check(F.assess(new Date(Date.now() + 5 * 60000).toISOString(), 24).fresh === true,
  '5 minutes of clock skew is absorbed, not reported as a broken clock');
check(F.assess(new Date(Date.now() + 5 * 60000).toISOString(), 24,
  { futureToleranceHours: 0 }).fresh === false,
  'a caller that wants zero tolerance can have it');

// ===========================================================================
console.log('\n6. FORCED FAILURE -- a caller who forgets the window gets UNKNOWN');
// ===========================================================================
// The tempting alternative is a default window. That would invent the policy
// silently and make every un-migrated caller look green.
for (const [w, name] of [[undefined, 'omitted'], [null, 'null'], [0, 'zero'],
  [-5, 'negative'], ['24', 'a string'], [NaN, 'NaN'], [Infinity, 'Infinity']]) {
  const r = F.assess(isoAgo(1 * HOUR), w);
  check(r.fresh === false && r.state === F.UNKNOWN,
    'window ' + name + ' -> UNKNOWN, even though the source is one hour old');
}
check(/No freshness window/.test(F.assess(isoAgo(HOUR)).reason),
  'and the reason says the window is missing, not that the data is old');

// ===========================================================================
console.log('\n7. FORCED FAILURE -- "we could not look" is not "nothing is wrong"');
// ===========================================================================
v = F.unavailable('The fetch returned 404.');
check(v.fresh === false && v.state === F.UNKNOWN, 'unavailable() is never fresh');
check(v.ageHours === null && v.ageText === 'age unknown', 'it claims no age');
check(v.reason.includes('404'), 'it carries the caller\'s explanation verbatim');
check(F.unavailable().reason.length > 0,
  'and with no explanation given it still says something, rather than rendering blank');

// ===========================================================================
console.log('\n8. THE STRUCTURAL CLAUSE -- `fresh` is true for exactly one state');
// ===========================================================================
// Contract clause 2. Enumerated from the module's own exported state constants, so a
// FIFTH state added tomorrow is covered by this test on the day it lands, with no
// edit here. A caller written against `state !== 'stale'` would silently start
// rendering that new failure mode; this is what stops that being possible.
const STATE_KEYS = Object.keys(F).filter((k) => k === k.toUpperCase() && typeof F[k] === 'string');
check(STATE_KEYS.length >= 4,
  'the module names its states as exported constants (' + STATE_KEYS.join(', ') + ')');

// Build one verdict per state by feeding the input that produces it, then assert the
// invariant over whatever came back.
const SAMPLES = [
  F.assess(isoAgo(HOUR), 24),                                        // fresh
  F.assess(isoAgo(39 * DAY), 24),                                    // stale
  F.assess(new Date(Date.now() + 30 * DAY).toISOString(), 24),       // future
  F.assess(null, 24),                                                // unknown (no stamp)
  F.assess(isoAgo(HOUR), undefined),                                 // unknown (no window)
  F.unavailable('unreadable'),                                       // unknown (no read)
];
const seen = new Set(SAMPLES.map((s) => s.state));
check(seen.size === 4 && STATE_KEYS.every((k) => seen.has(F[k])),
  'every state the module exports is reachable and was produced here (' +
    [...seen].join(', ') + ')');
for (const s of SAMPLES) {
  check(s.fresh === (s.state === F.FRESH),
    '`fresh` agrees with state for ' + s.state + ' -> ' + s.fresh);
}
check(SAMPLES.filter((s) => s.fresh).length === 1,
  'exactly one of the six sample verdicts is fresh');

// A verdict must never be truthy-by-accident: a caller doing `if (v)` would render
// everything. So the shape has to force the branch onto `.fresh`.
check(SAMPLES.every((s) => typeof s.fresh === 'boolean'),
  '`fresh` is a real boolean on every verdict, not a truthy string');
check(SAMPLES.every((s) => typeof s.label === 'string' && s.label.length > 0),
  'every verdict carries a non-empty label -- silence reads as "fine"');
check(SAMPLES.filter((s) => !s.fresh).every((s) => s.reason.length > 0),
  'every non-fresh verdict carries a reason -- a bare state name is a code, not an answer');
// The reasons the MODULE writes (as opposed to the one a caller hands to
// unavailable()) have to be sentences a reader can act on, not three words.
check(SAMPLES.filter((s) => !s.fresh && s !== SAMPLES[5]).every((s) => s.reason.length > 40),
  'every reason the module writes itself is a full sentence');

// ===========================================================================
console.log('\n9. the module introduces no markup, so the caller can escape it');
// ===========================================================================
// Contract clause 6. If any returned string carried markup of its own, escaping it
// at the call site would visibly mangle the page and someone would stop escaping.
const strings = SAMPLES.flatMap((s) => [s.ageText, s.label, s.reason, s.state]);
check(strings.every((s) => !/[<>&"']/.test(s)),
  'no returned string contains a character that means anything in HTML');

// And it must not become an injection vector by echoing hostile input back. The only
// caller-supplied string is unavailable()'s reason, which is the page's own text --
// but a page that ever passes fetched text through it must still escape the result.
const hostile = F.unavailable('<img src=x onerror=alert(1)>');
check(hostile.reason.includes('<img'),
  'unavailable() passes its argument through UNCHANGED (it does not half-escape) -- ' +
  'so the call site escaping it once is correct and escaping it twice is visible');

// ===========================================================================
console.log('\n10. ageText() is readable at every scale a reader will meet');
// ===========================================================================
check(F.ageText(0.25) === '15 minutes ago', 'minutes: ' + F.ageText(0.25));
check(F.ageText(1) === '1 hour ago', 'singular hour has no "s": ' + F.ageText(1));
check(F.ageText(5) === '5 hours ago', 'hours: ' + F.ageText(5));
check(F.ageText(24 * 39) === '39 days ago', 'days: ' + F.ageText(24 * 39));
check(/months? ago/.test(F.ageText(24 * 400)), 'months: ' + F.ageText(24 * 400));
check(F.ageText(null) === 'age unknown', 'null: ' + F.ageText(null));
check(F.ageText(-2) === '2 hours from now', 'negative reads forward: ' + F.ageText(-2));

// ===========================================================================
console.log('\n' + (failures ? failures + ' FAILURE(S)' : 'All checks passed.'));
process.exit(failures ? 1 : 0);
