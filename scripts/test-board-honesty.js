// Regression test for the leaderboard's board-key honesty.
//
// THE BUG THIS LOCKS DOWN
// A board is keyed by (seed, game_version) -- pdoom1 PR #679. If a player's client
// submits under a key this page does not publish, their run is recorded and is
// invisible here, with no error to anyone. "0 entries" then means either "nobody
// played" or "the scores went somewhere nobody reads", and until 2026-07-29 the page
// could not tell a visitor which.
//
// Worse, applyDataStatus() -- the honesty banner -- was only ever called from
// loadLeaderboard(), a function nothing invoked. The live loader
// (loadLeaderboardWithFiltering) never called it, so the banner had NEVER rendered
// in production, and the empty table was revealed unconditionally. Tests 8-10 below
// exist purely so that cannot regress.
//
// Run: node scripts/test-board-honesty.js     (exit 0 = pass)

const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, '..', 'public', 'leaderboard', 'index.html');
const src = fs.readFileSync(PAGE, 'utf8');

let failures = 0;
const check = (cond, msg) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) failures++;
};

// ---- extract the three functions under test ---------------------------------
function extract(re, name) {
  const m = src.match(re);
  if (!m) { console.error(`FAIL: could not extract ${name}() from the page`); process.exit(1); }
  return m[0];
}
const srcApply = extract(/    function applyDataStatus\(data\) \{[\s\S]*?\n    \}/, 'applyDataStatus');
const srcHonesty = extract(/    async function applyBoardHonesty\(data\) \{[\s\S]*?\n    \}/, 'applyBoardHonesty');
const srcEscape = extract(/    function escapeHTML\(s\) \{[\s\S]*?\n    \}/, 'escapeHTML');

// ---- minimal DOM shim --------------------------------------------------------
function makeDOM() {
  const mk = (id) => ({
    id, style: {}, innerHTML: '', _children: [],
    appendChild(c) { this._children.push(c); c._parent = this; return c; },
    insertAdjacentHTML(_pos, html) { this.innerHTML += html; },
    // text seen by a visitor = own innerHTML plus any child hosts
    get _visible() { return this.innerHTML + this._children.map(c => c.innerHTML).join(''); },
  });
  const banner = mk('data-status-banner');
  const controls = { style: {} };
  const els = { 'data-status-banner': banner };
  const document = {
    getElementById: (id) => els[id] || null,
    querySelector: (sel) => (sel === '.controls-section' ? controls : null),
    createElement: (tag) => {
      const e = mk(null);
      e.tagName = tag;
      Object.defineProperty(e, 'id', {
        get() { return this._id; },
        set(v) { this._id = v; els[v] = this; },
      });
      return e;
    },
  };
  return { document, banner, controls, els };
}

// fetchMap: url -> object | null (null models a 404 / unreachable file)
function makeFetch(fetchMap) {
  return async (url) => {
    const key = Object.keys(fetchMap).find(k => url.includes(k));
    if (key === undefined || fetchMap[key] === null) return { ok: false, status: 404 };
    return { ok: true, status: 200, json: async () => fetchMap[key] };
  };
}

async function run(data, fetchMap, { status } = {}) {
  const dom = makeDOM();
  const build = new Function(
    'document', 'fetch',
    srcEscape + '\n' + srcApply + '\n' + srcHonesty +
    '\nreturn { applyDataStatus, applyBoardHonesty, escapeHTML };'
  );
  const api = build(dom.document, makeFetch(fetchMap));
  api.applyDataStatus(data);
  await api.applyBoardHonesty(data);
  return { dom, api, text: dom.banner._visible, shown: dom.banner.style.display };
}

const LIVENESS_ORPHANED = {
  checked_at: '2026-07-28T20:45:33+00:00',
  verdict: 'orphaned-scores',
  orphaned_entries_total: 23,
  orphaned_boards: [
    { seed: 'weekly-2026-w0', version: 'v0.11.0', entries: 20, players: 3 },
    { seed: 'weekly-2026-w0', version: 'v0.12.0', entries: 3, players: 2 },
  ],
};
const V13 = { latest_release: { version: 'v0.13.1' } };
const BOARD_V11 = { data_status: 'pre-launch', entries: [], meta: { game_version: 'v0.11.0' } };

(async () => {
  // 1. The live situation: board stamped v0.11.0, deployed v0.13.1, scores orphaned.
  console.log('1. Board v0.11.0 vs deployed v0.13.1, 23 orphaned entries');
  let r = await run(BOARD_V11, {
    '/data/version.json': V13,
    'board-liveness.json': LIVENESS_ORPHANED,
  });
  check(r.shown === 'block', 'banner is displayed');
  check(r.text.includes('v0.11.0') && r.text.includes('v0.13.1'), 'names BOTH versions');
  check(/Version mismatch/i.test(r.text), 'calls it a version mismatch plainly');
  check(r.text.includes('23'), 'reports the orphaned entry COUNT, not just "empty"');
  check(/People are playing/i.test(r.text), 'tells the visitor people are playing');
  // The page may mention "nobody has played" only to REFUSE that inference. What must
  // never appear is a bare assertion of it.
  check(/does not by itself mean nobody has played/i.test(r.text),
    'explicitly refuses the "nobody played" inference');
  check(!/\b(no one|nobody) (has )?played\b(?!.{0,40}(not|does not))/i.test(
    r.text.replace(/does not by itself mean nobody has played/gi, '')),
    'makes no bare claim that nobody played');

  // 2. Genuinely empty must read differently from orphaned. If these two produced the
  //    same page, the whole exercise would be pointless.
  console.log('2. Genuinely empty board');
  const r2 = await run(BOARD_V11, {
    '/data/version.json': { latest_release: { version: 'v0.11.0' } },
    'board-liveness.json': {
      checked_at: '2026-07-28T20:45:33+00:00', verdict: 'genuinely-empty',
      orphaned_entries_total: 0, orphaned_boards: [],
    },
  });
  check(/really is empty|no scores had been submitted/i.test(r2.text),
    'says the board really is empty, with a timestamp');
  check(r2.text !== r.text, 'empty and orphaned render DIFFERENTLY');

  // 3. API unreachable -> unknown, never zero.
  console.log('3. Score API unreachable at last check');
  const r3 = await run(BOARD_V11, {
    '/data/version.json': V13,
    'board-liveness.json': {
      checked_at: '2026-07-28T20:45:33+00:00', verdict: 'unreachable',
      orphaned_entries_total: 0, orphaned_boards: [],
    },
  });
  check(/unknown, not zero/i.test(r3.text), 'unreachable reads as UNKNOWN, not zero');

  // 4. No live check on record -> must not imply the board is truly empty.
  console.log('4. board-liveness.json missing');
  const r4 = await run(BOARD_V11, { '/data/version.json': V13, 'board-liveness.json': null });
  check(/No live check on record/i.test(r4.text), 'admits nothing has been verified');
  check(/not evidence/i.test(r4.text), 'says an empty board is not evidence of no scores');

  // 5. version.json unreadable -> must not silently assume the versions agree.
  console.log('5. version.json unreadable');
  const r5 = await run(BOARD_V11, { '/data/version.json': null, 'board-liveness.json': LIVENESS_ORPHANED });
  check(/Cannot verify the version/i.test(r5.text), 'says it cannot verify the version');
  // "matches" may appear only inside "cannot confirm ... matches". A positive claim of
  // agreement, having read nothing, is the failure mode.
  check(/cannot confirm/i.test(r5.text), 'frames it as unconfirmed, not agreed');
  check(!/\b(board|version)\s+matches\b(?!.{0,60}$)/i.test(
    r5.text.replace(/cannot confirm[\s\S]*?playing\./i, '')),
    'never asserts the versions agree');

  // 6. Withheld local files are named with counts.
  console.log('6. Version-mismatched local seed files are reported with counts');
  const r6 = await run({
    ...BOARD_V11,
    exclusions: {
      deployed_version: 'v0.13.1', version_mismatched_files: 5,
      version_mismatched_entries: 21, version_mismatched_versions: ['1.0.0'],
    },
  }, { '/data/version.json': V13, 'board-liveness.json': LIVENESS_ORPHANED });
  check(r6.text.includes('5') && r6.text.includes('21') && r6.text.includes('1.0.0'),
    'names file count, entry count and the excluded version');
  check(/re-stamping would fabricate history/i.test(r6.text), 'rules out re-stamping');

  // 7. Data-file strings are escaped, not injected as markup.
  console.log('7. Version strings from data files are escaped');
  const r7 = await run(
    { data_status: 'pre-launch', entries: [], meta: { game_version: '<img src=x onerror=alert(1)>' } },
    { '/data/version.json': V13, 'board-liveness.json': LIVENESS_ORPHANED });
  check(!r7.text.includes('<img src=x'), 'markup from a data file is escaped');
  check(r7.text.includes('&lt;img'), 'escaped form is present');

  // 8. Idempotence: the seed/week filter re-runs the loader.
  console.log('8. Re-running does not stack duplicate notices');
  const dom = makeDOM();
  const api = new Function('document', 'fetch',
    srcEscape + '\n' + srcApply + '\n' + srcHonesty +
    '\nreturn { applyDataStatus, applyBoardHonesty };')(
    dom.document, makeFetch({ '/data/version.json': V13, 'board-liveness.json': LIVENESS_ORPHANED }));
  api.applyDataStatus(BOARD_V11);
  await api.applyBoardHonesty(BOARD_V11);
  const once = (dom.banner._visible.match(/Version mismatch/g) || []).length;
  await api.applyBoardHonesty(BOARD_V11);
  const twice = (dom.banner._visible.match(/Version mismatch/g) || []).length;
  check(once === 1 && twice === 1, `notice rendered once, still once after reload (${once}/${twice})`);

  // ---- source-level contracts (the dead-code bug) ----------------------------
  console.log('9. The live loader actually calls the honesty code');
  const loader = src.match(/async function loadLeaderboardWithFiltering\(\) \{[\s\S]*?\n    \}/);
  check(!!loader, 'loadLeaderboardWithFiltering() found');
  check(/applyDataStatus\(/.test(loader[0]),
    'live loader calls applyDataStatus (it did NOT before -- banner never rendered)');
  check(/applyBoardHonesty\(/.test(loader[0]), 'live loader calls applyBoardHonesty');

  console.log('10. No second, dead loader reintroduced');
  const loaders = (src.match(/async function loadLeaderboard\b/g) || []).length;
  check(loaders === 0, 'the dead loadLeaderboard() decoy is gone');
  check(/leaderboard-table'\)\.style\.display =\s*\n?\s*\(filteredData\.entries/.test(loader[0]),
    'empty table is not revealed as if it were a real ranking');

  console.log('11. No version literal is hardcoded in the banner copy');
  const banners = srcApply + srcHonesty;
  check(!/v0\.\d+\.\d+/.test(banners),
    'banner text contains no hardcoded version (it must read both at run time)');

  console.log('');
  if (failures) { console.log(`FAIL: ${failures} check(s) failed`); process.exit(1); }
  console.log('PASS: board-key mismatch is visible, counted, and cannot silently read as "nobody is playing"');
})();
