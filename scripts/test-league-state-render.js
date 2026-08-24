// Regression test for the leaderboard's league-state block. pdoom1-website#351.
//
// THE BUG THIS LOCKS DOWN
// The board key is compiled into the build, so a published build posts scores to a
// key that may never have been opened by anyone. Until 2026-08-24 this page had no
// representation of "which league is OPEN" distinct from "what is downloadable", so
// a published-but-unopened board and an open board rendered identically -- and a
// visitor whose score landed on a key this page does not publish saw an ordinary
// leaderboard with no error anywhere.
//
// WHAT IS ASSERTED, in order of how much damage the failure does:
//   1. The page NEVER says a league is open unless the data names who opened it and
//      when. Fabricating an opening is pdoom1-website#297 one gate later.
//   2. An unblessed seed NEVER reaches a visitor.
//   3. Unknown renders as unknown -- missing file, missing block, expired stamp.
//   4. A key that differs in BOTH halves is described as unreachable, not as late.
//   5. Every value from the data file is escaped.
//
// The function is extracted from the page source and run against a stub, the same
// technique as test-board-honesty.js, so the thing under test is the shipped code
// and not a copy of it.
//
// Run: node scripts/test-league-state-render.js     (exit 0 = pass)

const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, '..', 'public', 'leaderboard', 'index.html');
const DATA = path.join(__dirname, '..', 'public', 'data', 'ladder-epochs.json');
// CRLF -> LF first: the extractor anchors on '\n    }' and core.autocrlf=true on
// Windows would otherwise kill this at extraction rather than at an assertion.
const src = fs.readFileSync(PAGE, 'utf8').split('\r\n').join('\n');

let failures = 0;
const check = (cond, msg) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) failures++;
};

const m = src.match(
  /    function buildLeagueStateHTML\(epochs, publishedKey, nowMs\) \{[\s\S]*?\n    \}/);
if (!m) {
  console.error('FAIL: could not extract buildLeagueStateHTML() from the page');
  process.exit(1);
}
const SHARED = require(path.join(__dirname, '..', 'public', 'assets', 'js', 'escape.js'));
// eslint-disable-next-line no-new-func
const build = new Function('escapeHTML',
  m[0] + '\n; return buildLeagueStateHTML;')(SHARED.escapeHTML);

const REAL = JSON.parse(fs.readFileSync(DATA, 'utf8'));
const clone = () => JSON.parse(JSON.stringify(REAL));
// Every case pins its own clock relative to the file's own stamp, so a passing run
// today cannot become a failing run next week for a reason unrelated to the code.
const stampMs = Date.parse(REAL.player_facing.verified_utc);
const FRESH = stampMs + 3600000;                 // one hour after verification
const EXPIRED = stampMs + 400 * 86400000;        // long past any sane window
const PUB = { seed: 'weekly-2026-w32', ladder_epoch: 'L4' };

// ---------------------------------------------------------------------------
console.log('\n1. the committed file, rendered fresh');
// ---------------------------------------------------------------------------
const now = build(clone(), PUB, FRESH);
check(/No league is currently open/i.test(now),
  'says plainly that no league is open');
check(/opening is a separate/i.test(now),
  'and says why: publishing a key is not opening a league');
check(/v0\.14\.2/.test(now), 'names the downloadable build');
check(/weekly-2026-w33/.test(now),
  'names the blessed seed the downloadable build posts to');
check(/no released build carries it/i.test(now),
  'says the coming season is not carried by any released build');
check(!/\b(19|20)\d\d-\d\d-\d\d\b/.test(
        now.split('Coming')[1] ? now.split('Coming')[1].split('This page is showing')[0] : ''),
  'gives NO date for the coming season -- the epoch is not forecastable');

// ---------------------------------------------------------------------------
console.log('\n2. an opening the data does not record is never rendered');
// ---------------------------------------------------------------------------
const halfOpen = clone();
halfOpen.player_facing.league_open.state = 'open';
halfOpen.player_facing.league_open.seed = 'weekly-2026-w33';
halfOpen.player_facing.league_open.ladder_version = 'L5';
// opened_by and opened_utc stay null: the exact shape a seat produces when it
// reasons "scores are landing, so the board must be open".
const halfOpenHTML = build(halfOpen, PUB, FRESH);
check(!/<strong>Open<\/strong>/.test(halfOpenHTML),
  'state "open" with no opener and no timestamp does NOT render as open');
check(/Unknown/i.test(halfOpenHTML),
  '...it renders as unknown instead of as either answer');

const reallyOpen = clone();
Object.assign(reallyOpen.player_facing.league_open, {
  state: 'open', seed: 'weekly-2026-w33', ladder_version: 'L5',
  opened_by: 'Pip', opened_utc: '2026-08-21T07:00:00Z',
});
const openHTML = build(reallyOpen, PUB, FRESH);
check(/<strong>Open<\/strong>/.test(openHTML) && /Pip/.test(openHTML),
  'a full opening record DOES render as open, naming who opened it');
check(/2026-08-21T07:00:00Z/.test(openHTML), '...and when');

// ---------------------------------------------------------------------------
console.log('\n3. an unblessed seed never reaches a visitor');
// ---------------------------------------------------------------------------
const unblessed = clone();
unblessed.player_facing.downloadable_now.seed_blessed = false;
const unblessedHTML = build(unblessed, PUB, FRESH);
check(!/weekly-2026-w33/.test(
        unblessedHTML.split('League open now')[0]),
  'seed_blessed:false suppresses the seed in the downloadable line');
check(/L5/.test(unblessedHTML),
  '...while the season, which is not a blessing, is still named');
check(!/weekly-2026-w34/.test(now),
  'the game repo seed const recorded in epochs[] is never rendered');

// ---------------------------------------------------------------------------
console.log('\n4. unknown is a first-class answer');
// ---------------------------------------------------------------------------
check(/Unknown/i.test(build(null, PUB, FRESH)),
  'a file that did not load renders as unknown, not as an empty league');
check(/Unknown/i.test(build({}, PUB, FRESH)),
  'a file with no player_facing block renders as unknown');
const expiredHTML = build(clone(), PUB, EXPIRED);
check(/outside the window/i.test(expiredHTML),
  'an expired verification says so');
check(!/No league is currently open/i.test(expiredHTML),
  '...and stops asserting the answers it can no longer date');
const noExpiry = clone();
delete noExpiry.player_facing.stale_after_days;
check(!/No league is currently open/i.test(build(noExpiry, PUB, FRESH)),
  'a verification date with NO expiry is treated as stale, not as permanent');

// ---------------------------------------------------------------------------
console.log('\n5. a key differing in both halves is unreachable, not late');
// ---------------------------------------------------------------------------
check(/in either half/i.test(now) && /never/i.test(now),
  'both halves differing: the run can NEVER appear here, stated as such');
check(/saved/i.test(now),
  '...and the visitor is told their run is saved, so the page owns the fault');
const sameSeed = clone();
const oneHalf = build(sameSeed, { seed: 'weekly-2026-w33', ladder_epoch: 'L4' }, FRESH);
check(!/in either half/i.test(oneHalf) && /catches up/i.test(oneHalf),
  'one half differing: the weaker, true claim -- it will appear once this page catches up');
const matching = build(clone(), { seed: 'weekly-2026-w33', ladder_epoch: 'L5' }, FRESH);
check(!/not the board the current build submits to/i.test(matching),
  'a matching key raises no alarm -- being loudly wrong spends the alarm');

// ---------------------------------------------------------------------------
console.log('\n6. every value from the data file is escaped');
// ---------------------------------------------------------------------------
const hostile = clone();
const PAYLOAD = '<img src=x onerror=alert(1)>';
hostile.player_facing.downloadable_now.build = PAYLOAD;
hostile.player_facing.downloadable_now.board_key.seed = PAYLOAD;
hostile.player_facing.downloadable_now.board_key.ladder_version = PAYLOAD;
hostile.player_facing.coming.ladder_version = PAYLOAD;
hostile.player_facing.league_open.since_note = PAYLOAD;
hostile.player_facing.verified_utc = REAL.player_facing.verified_utc;
const hostileHTML = build(hostile, { seed: PAYLOAD, ladder_epoch: PAYLOAD }, FRESH);
check(!hostileHTML.includes('<img src=x'),
  'no markup from the data file survives into the rendered HTML');
check(hostileHTML.includes('&lt;img'), '...it is entity-escaped rather than dropped');

console.log('\n' + '-'.repeat(72));
if (failures) {
  console.log('FAILED: ' + failures + ' check(s)');
  process.exit(1);
}
console.log('PASSED: the page cannot claim an opening nobody performed, cannot show an');
console.log('unblessed seed, and says unknown when it does not know.');
