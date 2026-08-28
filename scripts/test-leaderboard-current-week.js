// Regression test: the "Current Week" filter must never render a week that has ended.
//
// THE BUG THIS LOCKS DOWN
// /leaderboard/ has two paths that load a board. The first-load path
// (loadLeaderboardWithFiltering) calls applyDataStatus() and applyBoardHonesty();
// until 2026-08-29 those were its ONLY call sites. The second path,
// filterBySeedOrWeek(), replaced originalData and re-rendered without either --
// so switching the dropdown swapped the data out from under a banner that still
// described the previous board.
//
// Worse, populateSeedFilter() had always refused to OFFER a finished week (the end
// timestamp is the authority, not an is_current flag), but "Current Week" is a
// static <option> in the markup. Selecting it walked straight past that guard.
//
// What that meant in production on 2026-08-29: the weekly rollover was parked
// (weekly-league-reset.yml, PARKED-UNTIL 2026-09-02), so current.json still
// described 21-27 Aug -- a week closed two days earlier, stamped ladder_version L4
// in meta and L5 in epoch while the live epoch was L6, holding 0 participants.
// A visitor who had just played the shipped build and submitted a score would read
// that as "the league is empty".
//
// NEGATIVE CONTROL: a guard that never renders anything would pass every
// "did not show the dead week" assertion. Test 2 forces an OPEN week and requires
// the board to actually render, so refusing everything fails too.
//
// Run: node scripts/test-leaderboard-current-week.js     (exit 0 = pass)

const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, '..', 'public', 'leaderboard', 'index.html');
// CRLF -> LF first: core.autocrlf=true on Windows, and the extractors below anchor
// on newlines. test-board-escaping.js died at extraction for exactly this reason.
const src = fs.readFileSync(PAGE, 'utf8').split('\r\n').join('\n');

let failures = 0;
const check = (cond, msg) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) failures++;
};

function extract(re, name) {
  const m = src.match(re);
  if (!m) { console.error(`FAIL: could not extract ${name} from the page`); process.exit(1); }
  return m[0];
}

const srcWeekIsOpen = extract(/    function weekIsOpen\(weekData\) \{[\s\S]*?\n    \}/, 'weekIsOpen()');
const srcNotice = extract(/    function showFilterNotice\(html\) \{[\s\S]*?\n    \}/, 'showFilterNotice()');
const srcFilter = extract(/    async function filterBySeedOrWeek\(\) \{[\s\S]*?\n    \}/, 'filterBySeedOrWeek()');

// ---- harness ---------------------------------------------------------------
const DAY = 86400000;

function makeEnv({ seedFilter, fetchImpl }) {
  const mk = (id) => ({ id, style: {}, innerHTML: '', value: '' });
  const els = {
    'data-status-banner': mk('data-status-banner'),
    'leaderboard-table': mk('leaderboard-table'),
    'cards-view': mk('cards-view'),
    'loading': mk('loading'),
    'filter-by-seed': Object.assign(mk('filter-by-seed'), { value: seedFilter }),
  };
  const calls = { applyDataStatus: 0, applyBoardHonesty: 0, displayLeaderboard: 0, displayStats: 0 };
  const env = {
    document: {
      getElementById: (id) => els[id] || null,
      querySelector: () => ({ style: {} }),
    },
    fetch: fetchImpl,
    console: { error: () => {} },
    // spies
    applyDataStatus: () => { calls.applyDataStatus++; },
    applyBoardHonesty: () => { calls.applyBoardHonesty++; },
    displayStats: () => { calls.displayStats++; },
    displayLeaderboard: () => { calls.displayLeaderboard++; },
    loadLeaderboardWithFiltering: () => {},
    originalData: null,
    filteredData: null,
  };
  return { env, els, calls };
}

// Build one async function that closes over the env, defining the three extracted
// functions in the same scope -- the node-side equivalent of the page's <script>.
function buildRunner(env) {
  const names = Object.keys(env);
  const body = `
    ${srcWeekIsOpen}
    ${srcNotice}
    ${srcFilter}
    return filterBySeedOrWeek();
  `;
  // eslint-disable-next-line no-new-func
  const fn = new Function(...names, `return (async () => {${body}})();`);
  return fn(...names.map((n) => env[n]));
}

function jsonResponse(obj, ok = true, status = 200) {
  return Promise.resolve({ ok, status, json: () => Promise.resolve(obj) });
}

const openWeek = () => ({
  meta: { week_id: '2026_W40', end_date: new Date(Date.now() + 3 * DAY).toISOString() },
  data_status: 'live-empty',
  entries: [],
});
const deadWeek = () => ({
  // The real shape observed on 2026-08-29.
  meta: { week_id: '2026_W35', ladder_version: 'L4',
          end_date: new Date(Date.now() - 2 * DAY).toISOString() },
  epoch: { ladder_version: 'L5' },
  data_status: 'live',
  entries: [],
});

async function main() {
  // ---- 1. a week that ended is NOT rendered --------------------------------
  console.log('1. A week whose end timestamp has passed is not shown as current');
  {
    const { env, els, calls } = makeEnv({
      seedFilter: 'current-week',
      fetchImpl: () => jsonResponse(deadWeek()),
    });
    await buildRunner(env);
    check(calls.displayLeaderboard === 0,
      'the finished week is NOT rendered (this is the bug: it used to render)');
    check(/closed/i.test(els['data-status-banner'].innerHTML),
      'the banner says the week has closed');
    check(els['data-status-banner'].style.display === 'block', 'the notice is visible');
    check(els['leaderboard-table'].style.display === 'none',
      'the table is hidden rather than showing a dead board');
    check(!/L4|L5|L6/.test(els['data-status-banner'].innerHTML),
      'the notice names no ladder epoch literal (it would rot)');
  }

  // ---- 2. NEGATIVE CONTROL: an open week still renders ---------------------
  console.log('2. NEGATIVE CONTROL -- an open week is still rendered');
  {
    const { env, calls } = makeEnv({
      seedFilter: 'current-week',
      fetchImpl: () => jsonResponse(openWeek()),
    });
    await buildRunner(env);
    check(calls.displayLeaderboard === 1, 'an open week IS rendered');
    check(calls.applyDataStatus === 1,
      'applyDataStatus runs on the filter path (it had ONE call site before)');
    check(calls.applyBoardHonesty === 1, 'applyBoardHonesty runs on the filter path');
  }

  // ---- 3. a failed fetch says which failure it was -------------------------
  console.log('3. A failed fetch is named, not swallowed');
  {
    const { env, els, calls } = makeEnv({
      seedFilter: 'current-week',
      fetchImpl: () => jsonResponse({}, false, 404),
    });
    await buildRunner(env);
    check(calls.displayLeaderboard === 0, 'nothing is rendered from a 404');
    check(/site fault/i.test(els['data-status-banner'].innerHTML),
      'the notice distinguishes a site fault from an empty board');
  }

  // ---- 4. absence is not "open" -------------------------------------------
  console.log('4. A week with no usable end timestamp is not treated as open');
  for (const [label, data] of [
    ['no meta at all', {}],
    ['unparseable end_date', { meta: { end_date: 'soon' } }],
    ['null end_date', { meta: { end_date: null } }],
  ]) {
    const { env, calls } = makeEnv({
      seedFilter: 'current-week',
      fetchImpl: () => jsonResponse(data),
    });
    await buildRunner(env);
    check(calls.displayLeaderboard === 0, `${label} -> not rendered (absence is not "open")`);
  }

  // ---- 5. week_info.end_timestamp is honoured too --------------------------
  console.log('5. Either timestamp field is accepted');
  {
    const { env, calls } = makeEnv({
      seedFilter: 'current-week',
      fetchImpl: () => jsonResponse({
        week_info: { end_timestamp: new Date(Date.now() + DAY).toISOString() },
        entries: [],
      }),
    });
    await buildRunner(env);
    check(calls.displayLeaderboard === 1, 'week_info.end_timestamp keeps an open week open');
  }

  // ---- 6. an explicitly chosen archived seed still renders -----------------
  console.log('6. A named archived seed is a finished week the visitor asked for');
  {
    const { env, calls } = makeEnv({
      seedFilter: 'weekly-2026-w31',
      fetchImpl: () => jsonResponse({ entries: [], data_status: 'live' }),
    });
    await buildRunner(env);
    check(calls.displayLeaderboard === 1, 'the archived seed IS rendered');
    check(calls.applyDataStatus === 1,
      'and it gets its own banner rather than inheriting the previous board\'s');
  }

  // ---- 7. source-level: one freshness authority, not two -------------------
  console.log('7. There is ONE freshness authority, shared');
  check((src.match(/function weekIsOpen\(/g) || []).length === 1,
    'weekIsOpen() is defined exactly once');
  check((src.match(/weekIsOpen\(/g) || []).length === 3,
    'and has exactly two callers (dropdown + filter path)');
  check(!/const weekStillOpen = Number\.isFinite/.test(src),
    'populateSeedFilter no longer carries its own inline copy of the check');

  console.log('');
  if (failures) { console.log(`FAIL: ${failures} check(s) failed`); process.exit(1); }
  console.log('OK: the current-week filter fails closed on a week that has ended.');
}

main().catch((e) => { console.error(e); process.exit(1); });
