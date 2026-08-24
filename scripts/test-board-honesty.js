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
// CRLF -> LF first: core.autocrlf=true on Windows, and the extractors below anchor on
// newlines. test-board-escaping.js died at extraction for exactly this reason.
const src = fs.readFileSync(PAGE, 'utf8').split('\r\n').join('\n');

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
// Both banner branches that describe a key mismatch now call boardMechanismHTML(), the
// ONE source for that sentence (#353 review, 2026-08-24: the two boxes on this page had
// drifted into contradicting each other about the same key -- one promised the run would
// appear "until this page catches up", the other that it could "never" appear).
// Extracted rather than stubbed, so the sandbox exercises the shipped sentence.
const srcMech = extract(/    function boardMechanismHTML\(publishedEpoch, clientEpoch\) \{[\s\S]*?\n    \}/, 'boardMechanismHTML');
const srcHonesty = extract(/    async function applyBoardHonesty\(data\) \{[\s\S]*?\n    \}/, 'applyBoardHonesty');

// escapeHTML() is no longer inline on this page. As of 2026-08-01 it is the shared
// public/assets/js/escape.js, loaded by a blocking <script src> in the head -- the site
// carried FIVE separately-written escapers with three different coverages, and three of
// them could not protect the attribute contexts they fed. It is passed in below as a
// function parameter, which is the node-side equivalent of that <script> tag.
const SHARED = require(path.join(__dirname, '..', 'public', 'assets', 'js', 'escape.js'));

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
    'document', 'fetch', 'escapeHTML', 'safeUrl', 'isSafeUrl', 'toNumber',
    srcMech + '\n' + srcApply + '\n' + srcHonesty +
    '\nreturn { applyDataStatus, applyBoardHonesty, escapeHTML };'
  );
  const api = build(dom.document, makeFetch(fetchMap),
    SHARED.escapeHTML, SHARED.safeUrl, SHARED.isSafeUrl, SHARED.toNumber);
  api.applyDataStatus(data);
  await api.applyBoardHonesty(data);
  return { dom, api, text: dom.banner._visible, shown: dom.banner.style.display };
}

// The archive: acknowledged history, permanent by Pip's ruling. Reported, never failed on.
const ARCHIVE = {
  acknowledged: true,
  entries_total: 27,
  player_names: ['AI Safety Lab', 'CogDerp', 'Cognitive Development',
    'Division of Intelligent Agents', 'Hamthropic', 'Laboratory of Autonomous Systems'],
  boards: [
    { seed: 'weekly-2026-w0', version: 'v0.11.0', entries: 20 },
    { seed: 'weekly-2026-w0', version: 'v0.12.0', entries: 3 },
    { seed: 'weekly-2026-w30', version: 'L2', entries: 4 },
  ],
};
const NO_NEW = { boards: [], entries_total: 0 };
const AT = '2026-07-29T09:30:00+00:00';

// Today's real state: boards visible, current epoch unknowable.
const LIVENESS_EPOCH_UNKNOWN = {
  checked_at: AT, verdict: 'epoch-unknown',
  board_key: { seed: 'weekly_2026_W30_18a08709', ladder_epoch: null, epoch_known: false },
  archived_orphans: ARCHIVE, new_orphans: NO_NEW,
};
// After the artifact exists and the board agrees. THE regression case.
const LIVENESS_LIVE = {
  checked_at: AT, verdict: 'live',
  board_key: { seed: 's', ladder_epoch: 'L3', epoch_known: true },
  deployed_board: { entries: 12 },
  archived_orphans: ARCHIVE, new_orphans: NO_NEW,
};
const BOARD_L3 = { data_status: 'live', entries: [{}], meta: { game_version: 'L3' } };
const BOARD_V11 = { data_status: 'pre-launch', entries: [], meta: { game_version: 'v0.11.0' } };

(async () => {
  // 1. THE REGRESSION THAT MATTERS. The board key is the ladder epoch, not the build.
  //    Board L3, live epoch L3, build v0.13.2 -- correct data. Any "version mismatch"
  //    here would fire permanently from the next ladder bump onward and burn the alarm.
  console.log('1. Board L3 + epoch L3 + build v0.13.2 -> NO mismatch claim');
  const r1 = await run(BOARD_L3, {
    '/data/version.json': { latest_release: { version: 'v0.13.2' } },
    'board-liveness.json': LIVENESS_LIVE,
  });
  check(!/mismatch/i.test(r1.text),
    'does NOT claim a mismatch when board and epoch agree but the build differs');
  check(!/not the current season/i.test(r1.text), 'does not claim the wrong season');
  check(!r1.text.includes('v0.13.2'),
    'does not put the build version into a board-key claim at all');

  // 2. Today's honest state: the epoch cannot be derived.
  console.log('2. Epoch unknown -> "cannot confirm", never "mismatch"');
  const r2 = await run(BOARD_V11, {
    '/data/version.json': { latest_release: { version: 'v0.13.1' } },
    'board-liveness.json': LIVENESS_EPOCH_UNKNOWN,
  });
  check(r2.shown === 'block', 'banner is displayed');
  check(/Cannot confirm this is the current board/i.test(r2.text), 'says it cannot confirm');
  // The page may use the word "mismatch" ONLY to disclaim one. What must never survive is
  // a positive claim, so strip the disclaimer and require nothing to be left.
  check(/not claiming a mismatch/i.test(r2.text), 'explicitly disclaims a mismatch finding');
  check(!/mismatch/i.test(r2.text.replace(/It is not claiming a mismatch[^.]*\./i, '')),
    'makes no positive mismatch claim it cannot demonstrate');
  check(/does not know|genuinely does not know/i.test(r2.text), 'admits not knowing');
  check(/does not by itself mean nobody has played/i.test(r2.text),
    'still refuses the "nobody played" inference');

  // 3. Epoch known AND different -> now a mismatch claim IS earned.
  console.log('3. Board L2 vs live epoch L3 -> names both, plainly');
  const r3 = await run({ ...BOARD_V11, meta: { game_version: 'L2' } }, {
    '/data/version.json': { latest_release: { version: 'v0.13.2' } },
    'board-liveness.json': {
      ...LIVENESS_LIVE, verdict: 'genuinely-empty',
      board_key: { seed: 's', ladder_epoch: 'L3', epoch_known: true },
    },
  });
  check(/not the current season/i.test(r3.text), 'states the board is not the live season');
  check(r3.text.includes('L2') && r3.text.includes('L3'), 'names BOTH board keys');
  check(!r3.text.includes('v0.13.2'), 'still keeps the build out of the board-key claim');

  // 3b. THE BRANCH THAT ACTUALLY RENDERS ON THE LIVE SITE, and which had no assertion
  //     at all until 2026-08-24. `epochs_agree: false` is today's real state (published
  //     L4, live L5). Its tail promised the run would appear "until this page catches
  //     up" -- a promise conditional on catching up before the next fork, which has
  //     failed twice this month -- while a second box on the same page said the run
  //     could "never" appear. Both are gone; one mechanism sentence serves both.
  console.log('3b. Superseded publication -> the mechanism, and no promise');
  const r3b = await run({ ...BOARD_L3, meta: { game_version: 'L4' } }, {
    'board-liveness.json': {
      ...LIVENESS_LIVE, verdict: 'superseded-publication',
      board_key: {
        seed: 'weekly-2026-w32', ladder_epoch: 'L4', epoch_known: true,
        published_ladder_epoch: 'L4', current_ladder_epoch: 'L5', epochs_agree: false,
      },
    },
  });
  check(/previous season/i.test(r3b.text), 'still says the board is a previous season');
  check(r3b.text.includes('L4') && r3b.text.includes('L5'), 'still names both keys');
  check(!/catches up/i.test(r3b.text),
    'the unearned "until this page catches up" promise is gone');
  check(!/never/i.test(r3b.text) && !/not ever/i.test(r3b.text),
    'and it does not swing to the opposite false claim either');
  check(/if and when this page publishes/i.test(r3b.text),
    'states the mechanism, conditional on a publish rather than on a timeline');
  check(/stays on/i.test(r3b.text),
    'and says what happens if a new season opens first');

  // 4. The permanent archive is reported to the visitor, with counts and people.
  console.log('4. Archived anomaly is surfaced with counts');
  check(r2.text.includes('27'), 'reports the archived entry count');
  check(/Laboratory of Autonomous Systems/.test(r2.text), 'names the players');
  check(/re-stamped/i.test(r2.text), 'rules out re-stamping onto a newer board');

  // 5. A NEW orphan is a different, louder thing than the archive.
  console.log('5. New unacknowledged orphan -> people are playing RIGHT NOW');
  const r5 = await run(BOARD_L3, {
    '/data/version.json': { latest_release: { version: 'v0.13.2' } },
    'board-liveness.json': {
      checked_at: AT, verdict: 'orphaned-scores',
      board_key: { seed: 's', ladder_epoch: 'L3', epoch_known: true },
      archived_orphans: ARCHIVE,
      new_orphans: { entries_total: 5, boards: [{ seed: 's', version: 'L4', entries: 5 }] },
    },
  });
  check(/playing right now/i.test(r5.text), 'flags a live incident, not history');
  check(r5.text.includes('5') && r5.text.includes('L4'), 'names the new orphan count and board');
  check(r5.text.includes('27'), 'still reports the archive alongside it');

  // 6. Genuinely empty must read differently from every other state.
  console.log('6. Genuinely empty board');
  const r6 = await run(BOARD_V11, {
    '/data/version.json': { latest_release: { version: 'v0.13.1' } },
    'board-liveness.json': {
      checked_at: AT, verdict: 'genuinely-empty',
      board_key: { seed: 's', ladder_epoch: 'L3', epoch_known: true },
      archived_orphans: { ...ARCHIVE, entries_total: 0, boards: [], player_names: [] },
      new_orphans: NO_NEW,
    },
  });
  check(/really is empty/i.test(r6.text), 'says the board really is empty, with a timestamp');
  check(r6.text !== r2.text && r6.text !== r5.text, 'renders differently from unknown/orphaned');

  // 7. API unreachable -> unknown, never zero.
  console.log('7. Score API unreachable at last check');
  const r7 = await run(BOARD_V11, {
    '/data/version.json': { latest_release: { version: 'v0.13.1' } },
    'board-liveness.json': {
      checked_at: AT, verdict: 'unreachable',
      board_key: { seed: 's', ladder_epoch: 'L3', epoch_known: true },
      archived_orphans: ARCHIVE, new_orphans: NO_NEW,
    },
  });
  check(/unknown, not zero/i.test(r7.text), 'unreachable reads as UNKNOWN, not zero');

  // 8. No live check on record -> must not imply the board is truly empty.
  console.log('8. board-liveness.json missing');
  const r8 = await run(BOARD_V11, {
    '/data/version.json': { latest_release: { version: 'v0.13.1' } },
    'board-liveness.json': null,
  });
  check(/No live check on record/i.test(r8.text), 'admits nothing has been verified');
  check(/not evidence/i.test(r8.text), 'says an empty board is not evidence of no scores');
  check(!/mismatch/i.test(r8.text), 'claims no mismatch with nothing to compare against');

  // 9. Withheld local files are named with counts. These are BUILD stamps on stored
  //    files -- a separate concern from the board key, and labelled as such.
  console.log('9. Withheld local result files are reported with counts');
  const r9 = await run({
    ...BOARD_V11,
    exclusions: {
      deployed_version: 'v0.13.1', version_mismatched_files: 5,
      version_mismatched_entries: 21, version_mismatched_versions: ['1.0.0'],
    },
  }, { '/data/version.json': null, 'board-liveness.json': LIVENESS_EPOCH_UNKNOWN });
  check(r9.text.includes('5') && r9.text.includes('21') && r9.text.includes('1.0.0'),
    'names file count, entry count and the excluded build');
  check(/re-stamping would fabricate history/i.test(r9.text), 'rules out re-stamping');

  // 10. Data-file strings are escaped, not injected as markup.
  console.log('10. Strings from data files are escaped');
  const r10 = await run(
    { data_status: 'pre-launch', entries: [], meta: { game_version: '<img src=x onerror=alert(1)>' } },
    { '/data/version.json': null, 'board-liveness.json': {
      ...LIVENESS_LIVE, verdict: 'genuinely-empty',
      board_key: { seed: 's', ladder_epoch: 'L3', epoch_known: true } } });
  check(!r10.text.includes('<img src=x'), 'markup from a data file is escaped');
  check(r10.text.includes('&lt;img'), 'escaped form is present');

  // 11. Idempotence: the seed/week filter re-runs the loader.
  console.log('11. Re-running does not stack duplicate notices');
  const dom = makeDOM();
  const api = new Function('document', 'fetch', 'escapeHTML', 'safeUrl', 'isSafeUrl', 'toNumber',
    srcMech + '\n' + srcApply + '\n' + srcHonesty +
    '\nreturn { applyDataStatus, applyBoardHonesty };')(
    dom.document, makeFetch({ 'board-liveness.json': LIVENESS_EPOCH_UNKNOWN }),
    SHARED.escapeHTML, SHARED.safeUrl, SHARED.isSafeUrl, SHARED.toNumber);
  api.applyDataStatus(BOARD_V11);
  await api.applyBoardHonesty(BOARD_V11);
  const once = (dom.banner._visible.match(/Cannot confirm/g) || []).length;
  await api.applyBoardHonesty(BOARD_V11);
  const twice = (dom.banner._visible.match(/Cannot confirm/g) || []).length;
  check(once === 1 && twice === 1, `notice rendered once, still once after reload (${once}/${twice})`);

  // ---- source-level contracts (the dead-code bug) ----------------------------
  console.log('12. The live loader actually calls the honesty code');
  const loader = src.match(/async function loadLeaderboardWithFiltering\(\) \{[\s\S]*?\n    \}/);
  check(!!loader, 'loadLeaderboardWithFiltering() found');
  check(/applyDataStatus\(/.test(loader[0]),
    'live loader calls applyDataStatus (it did NOT before -- banner never rendered)');
  check(/applyBoardHonesty\(/.test(loader[0]), 'live loader calls applyBoardHonesty');

  console.log('13. No second, dead loader reintroduced');
  const loaders = (src.match(/async function loadLeaderboard\b/g) || []).length;
  check(loaders === 0, 'the dead loadLeaderboard() decoy is gone');
  check(/leaderboard-table'\)\.style\.display =\s*\n?\s*\(filteredData\.entries/.test(loader[0]),
    'empty table is not revealed as if it were a real ranking');

  console.log('14. Nothing about the board key is hardcoded');
  const banners = srcApply + srcHonesty;
  check(!/v0\.\d+\.\d+/.test(banners), 'no build-version literal in the banner code');
  check(!/\bL\d+\b/.test(banners.replace(/\/\/[^\n]*/g, '')),
    'no ladder-epoch literal in the banner code (it must be read at run time)');
  // The build version must not reach the board-key comparison by ANY route. Reading
  // version.json here is how the invalidated comparison got written the first time.
  check(!/version\.json/.test(srcHonesty),
    'applyBoardHonesty does not read version.json -- the build is not part of the board key');
  check(!/latest_release/.test(srcHonesty), 'does not reach for latest_release');

  console.log('');
  if (failures) { console.log(`FAIL: ${failures} check(s) failed`); process.exit(1); }
  console.log('PASS: board-key mismatch is visible, counted, and cannot silently read as "nobody is playing"');
})();
