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
// The mechanism sentence is shared with the honesty banner one box above, so it is
// extracted too rather than stubbed -- a stub here would let the two boxes drift apart
// again, which is exactly the defect this shares a fix with (#353 review 2026-08-24).
const mech = src.match(
  /    function boardMechanismHTML\(publishedEpoch, clientEpoch\) \{[\s\S]*?\n    \}/);
if (!mech) {
  console.error('FAIL: could not extract boardMechanismHTML() from the page');
  process.exit(1);
}
const SHARED = require(path.join(__dirname, '..', 'public', 'assets', 'js', 'escape.js'));
// eslint-disable-next-line no-new-func
const build = new Function('escapeHTML',
  mech[0] + '\n' + m[0] + '\n; return buildLeagueStateHTML;')(SHARED.escapeHTML);

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

// A COMPLETE fabrication -- real opener, plausible timestamp, real seed and epoch --
// is the shape that would survive review, and it is the one every guard missed until
// the 2026-08-24 review of #353. The page's second lock is the ledger quote: the
// checker verifies the quote against the ledger, and the page refuses to announce an
// opening that carries no quote at all, so data reaching production without CI having
// run on it still cannot make this page say "Open".
const fabricated = clone();
Object.assign(fabricated.player_facing.league_open, {
  state: 'open', seed: 'weekly-2026-w33', ladder_version: 'L5',
  opened_by: 'Pip', opened_utc: '2026-08-21T07:00:00Z',
});
const fabricatedHTML = build(fabricated, PUB, FRESH);
check(!/<strong>Open<\/strong>/.test(fabricatedHTML),
  'a COMPLETE opening with no ledger quote still does NOT render as open');
check(!/Pip/.test(fabricatedHTML),
  '...and the fabricated opener never reaches the page');

const reallyOpen = clone();
Object.assign(reallyOpen.player_facing.league_open, {
  state: 'open', seed: 'weekly-2026-w33', ladder_version: 'L5',
  opened_by: 'Pip', opened_utc: '2026-08-21T07:00:00Z',
  opening_ledger_quote: 'Pip opened the board for ladder epoch L5 at the ceremony.',
});
const openHTML = build(reallyOpen, PUB, FRESH);
check(/<strong>Open<\/strong>/.test(openHTML) && /Pip/.test(openHTML),
  'an opening WITH its ledger quote renders as open, naming who opened it');
check(/2026-08-21T07:00:00Z/.test(openHTML), '...and when');
check(/From the league seed ledger/.test(openHTML) && /at the ceremony/.test(openHTML),
  '...and shows the ledger sentence, so the claim carries its evidence');

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
console.log('\n5. a key mismatch is described by MECHANISM, with no promise');
// ---------------------------------------------------------------------------
// CORRECTED 2026-08-24, before shipping. This section asserted that a key differing
// in both halves means the run "can NEVER appear here". That is false:
// publish-live-board.py takes its epoch from board-probe-targets.json (L5) and its
// derived seed list already contains weekly-2026-w33, so the shipped client's exact
// key is publishable by the existing 6-hourly job -- it refuses today only because
// several L5 boards are empty and indistinguishable, which one real score resolves.
// The number of differing halves changes nothing about the mechanism.
check(!/never/i.test(now) && !/not ever/i.test(now),
  'the page does NOT claim a run can never appear -- that claim was false');
check(!/catches up/i.test(now),
  'and it does not make the opposite unearned promise either');
check(/if and when this page publishes/i.test(now),
  'it states the condition: a publish of the season the run is recorded against');
check(/recorded against/i.test(now),
  '...names the season the run IS on, which is what "saved" actually means here');
check(/stays on/i.test(now),
  '...and says what happens if a new season opens first');

const oneHalf = build(clone(), { seed: 'weekly-2026-w33', ladder_epoch: 'L4' }, FRESH);
check(/if and when this page publishes/i.test(oneHalf),
  'one half differing gets the SAME sentence -- the mechanism does not depend on how');
const matching = build(clone(), { seed: 'weekly-2026-w33', ladder_epoch: 'L5' }, FRESH);
check(!/not the board the current build submits to/i.test(matching),
  'a matching key raises no alarm -- being loudly wrong spends the alarm');

// ---------------------------------------------------------------------------
console.log('\n5b. going stale must not DELETE the mismatch warning');
// ---------------------------------------------------------------------------
// Rows 1-3 degraded to unknown on expiry, but row 4 used to keep its bare
// "The board keyed X, Y." and silently drop the paragraph explaining that it is not
// your board. That is a true-looking fact with the safety notice deleted, which is
// worse than either the warning or a plain unknown. Unattended, it began the moment
// the stamp aged out.
const staleRow4 = build(clone(), PUB, EXPIRED);
check(/Unknown/i.test(staleRow4), 'an expired stamp renders unknown');
check(!/That is not the board the current build submits to/i.test(staleRow4),
  'the mismatch claim is not asserted from data too old to date');
check(/cannot be established right now/i.test(staleRow4),
  '...and the row says so, rather than presenting the bare key as if it were fine');
check(/weekly-2026-w32/.test(staleRow4),
  '...while still naming what this page is serving, which is not in doubt');

// ---------------------------------------------------------------------------
console.log('\n6. every value from the data file is escaped');
// ---------------------------------------------------------------------------
// EVERY rendered field, including the ones only an OPEN league reaches. The earlier
// version of this case never set state=open, so opened_by and opened_utc were never
// rendered and never escape-tested -- a mutation dropping escapeHTML() on either
// stayed green here AND in test-escaping.js (whose root rule matches only expressions
// literally naming a declared root, and this function aliases everything). This is
// now the only guard on those two fields, so it names them explicitly.
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

const hostileOpen = clone();
Object.assign(hostileOpen.player_facing.league_open, {
  state: 'open', seed: PAYLOAD, ladder_version: PAYLOAD,
  opened_by: PAYLOAD, opened_utc: PAYLOAD, opening_ledger_quote: PAYLOAD,
});
const hostileOpenHTML = build(hostileOpen, PUB, FRESH);
check(/<strong>Open<\/strong>/.test(hostileOpenHTML),
  'the open branch really is exercised (otherwise the next check proves nothing)');
check(!hostileOpenHTML.includes('<img src=x'),
  'opened_by, opened_utc, the open seed/epoch and the ledger quote are all escaped');
check((hostileOpenHTML.match(/&lt;img/g) || []).length >= 5,
  '...each of the five fields separately, not just the first one reached');

console.log('\n' + '-'.repeat(72));
if (failures) {
  console.log('FAILED: ' + failures + ' check(s)');
  process.exit(1);
}
console.log('PASSED: the page cannot claim an opening nobody performed, cannot show an');
console.log('unblessed seed, and says unknown when it does not know.');
