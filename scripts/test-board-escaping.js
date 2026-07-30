// Regression test: nothing from the score API reaches innerHTML unescaped, and the
// two new identity/dev-build surfaces stay honest.
//
// THE BUG THIS LOCKS DOWN (found 2026-07-30, league week)
// https://api.pdoom1.com/score_api.php is an UNAUTHENTICATED flat-file API. Anyone can
// POST an entry carrying any string. The leaderboard interpolated `player_name` and
// `game_mode` raw into three innerHTML templates -- the table row, the card, and the
// profile modal -- so one crafted POST ran script for every visitor to /leaderboard/.
// It had never fired only because the shipped client generates lab names from a fixed
// table, which constrains the client and not an attacker with curl. The board was about
// to be publicly promoted for the Friday league, which is what made it urgent.
//
// `score` and `level_reached` were interpolated without the `|| 0` coercion that the
// money/staff fields happen to get, so they were sinks too. The loop below covers the
// class rather than the two instances.
//
// WHY THE IDENTITY/DEV TESTS LIVE HERE
// Both features render fields the game does not emit yet (pdoom1 issue lodged
// 2026-07-30). The risk is not that they break -- it is that someone "simplifies" them
// into asserting something untrue: that an entry with no dev marker is known to be
// clean, or that a missing lab name means the player has none. The absent-means-unknown
// behaviour is pinned so a future edit has to argue with a failing test.
//
// Run: node scripts/test-board-escaping.js     (exit 0 = pass)

const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, '..', 'public', 'leaderboard', 'index.html');

// Normalise CRLF -> LF before anything looks at this.
//
// `core.autocrlf=true` on Windows, so a fresh checkout writes CRLF into the working tree.
// Several extractors below anchor on `;\n` or `\n    }`; under CRLF the byte after `;` is
// `\r`, so those patterns can never match and the test dies at extraction with
// "could not extract isDevBuild()" -- exit 1, before a single assertion runs.
//
// That is worse than a failing test: it fails on the ONLY platform CLAUDE.md tells you to
// run it on, while passing in a Linux CI that does not run it either. The guard on the
// one escaper protecting an unauthenticated API would have been permanently inert while
// looking like it existed. Found 2026-07-31 by an audit, not by the test.
const src = fs.readFileSync(PAGE, 'utf8').replace(/\r\n/g, '\n');

let failures = 0;
const check = (cond, msg) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) failures++;
};

// ---- extract the helpers under test -----------------------------------------
function extract(re, name) {
  const m = src.match(re);
  if (!m) { console.error('FAIL: could not extract ' + name + ' from the page'); process.exit(1); }
  return m[0];
}
const srcEscape   = extract(/    function escapeHTML\(s\) \{[\s\S]*?\n    \}/, 'escapeHTML()');
const srcIdentity = extract(/    const identityHTML = \(entry\) => \{[\s\S]*?\n    \};/, 'identityHTML()');
const srcMarker   = extract(/    const DEV_MARKER = .*/, 'DEV_MARKER');
const srcIsDev    = extract(/    const isDevBuild = \(entry\) =>[\s\S]*?;\n/, 'isDevBuild()');
const srcBadge    = extract(/    const devBadgeHTML = \(entry\) =>[\s\S]*?;\n/, 'devBadgeHTML()');

const sandbox = {};
new Function('S', 'with (S) { ' + srcEscape + '\n' + srcIdentity + '\n' + srcMarker + '\n'
  + srcIsDev + '\n' + srcBadge + '\n'
  + 'S.escapeHTML = escapeHTML; S.identityHTML = identityHTML;'
  + 'S.isDevBuild = isDevBuild; S.devBadgeHTML = devBadgeHTML; }')(sandbox);
const { escapeHTML, identityHTML, isDevBuild, devBadgeHTML } = sandbox;

// A payload of the shapes an attacker would actually try.
const HOSTILE = [
  '<img src=x onerror=alert(1)>',
  '<script>alert(1)</script>',
  '"><svg onload=alert(1)>',
  "' onmouseover='alert(1)",
  '</td></tr><tr><td>injected',
  '&lt;already escaped&gt;',
];

// Escaping does not delete the characters that spell "onerror=" -- it makes them inert
// TEXT. So the predicate is STRUCTURAL, not a keyword blocklist: after removing the
// markup this page is entitled to emit, no angle bracket or bare quote may survive.
// A keyword blocklist would happily pass a payload that spelled its handler differently.
const ALLOWED = /<\/?span(?: class="identity-lab")?>/g;
const inert = (html) => !/[<>"']/.test(String(html).replace(ALLOWED, ''));

console.log('\n1. escapeHTML neutralises every hostile shape');
for (const h of HOSTILE) {
  check(inert(escapeHTML(h)), 'escaped: ' + h.slice(0, 34));
}
check(escapeHTML('&').includes('&amp;'), 'ampersand is escaped (no double-unescape path)');
check(escapeHTML(null) === '' && escapeHTML(undefined) === '',
  'null/undefined render empty, not the string "null"');

console.log('\n2. no innerHTML template interpolates an API field raw');
// A template literal assigned to .textContent is safe by construction -- the DOM escapes
// it -- so those lines are exempt rather than rewritten into escapeHTML() calls, which
// would render a visible "&amp;" to the reader. Everything else must be escaped.
// Order matters: excise the multi-line textContent assignment FIRST, while its anchor
// line is still present. Filtering by line beforehand removes the `textContent` line and
// leaves its continuation lines orphaned, which is what this test did on its first run.
const htmlOnly = src
  .replace(/modalName\.textContent =[\s\S]{0,240}?;\n/, '')
  .split('\n')
  .filter((l) => !/textContent/.test(l))
  .join('\n');
// ENFORCE THE CLASS, NOT A LIST. The first version of this test named six fields --
// player_name, game_mode, score, level_reached, lab_name, player_handle -- and passed
// while THIRTEEN other entry fields were still interpolated raw, including entry_uuid and
// every `${(entry.final_money || 0).toLocaleString()}`. Those looked safe because they
// are numeric BY NAME, but `|| 0` does not coerce a string and String.toLocaleString() is
// the identity function, so a POST setting final_money to markup reached innerHTML intact.
// The score API is unauthenticated, so field names promise nothing about field types.
//
// So: scan for EVERY `${...entry.X...}` in an innerHTML template and require each one to
// go through escapeHTML. A new field added later is covered on the day it is added,
// without anyone remembering to extend a list.
const interpolations = htmlOnly.match(/\$\{[^}]*entry\.[^}]*\}/g) || [];
const unescaped = interpolations.filter((x) => !x.includes('escapeHTML'));
check(interpolations.length > 0, `found ${interpolations.length} entry interpolations to check`);
check(unescaped.length === 0,
  unescaped.length === 0
    ? 'every entry.* interpolation in an innerHTML template goes through escapeHTML'
    : `${unescaped.length} UNESCAPED: ${unescaped.slice(0, 4).join('  ')}`);
check(/modalName\.textContent =/.test(src),
  'the modal name still goes through textContent, not innerHTML');
check(!/const esc =/.test(src),
  'exactly ONE escaper on the page -- no second helper to drift from escapeHTML');

console.log('\n3. identityHTML escapes BOTH slots');
for (const h of HOSTILE.slice(0, 5)) {
  check(inert(identityHTML({ player_name: h, lab_name: h })),
    'identity inert with hostile name+lab: ' + h.slice(0, 28));
}
check(identityHTML({ player_name: 'Pip', lab_name: 'Applied AI Safety' }).includes('identity-lab'),
  'both fields present -> lab rendered in its own span');
check(!identityHTML({ player_name: 'Applied AI Safety' }).includes('identity-lab'),
  'lab absent -> renders exactly the one field, inventing nothing');
check(!identityHTML({ player_name: 'Same', lab_name: 'Same' }).includes('identity-lab'),
  'identical values are not printed twice');
check(identityHTML({ player_name: 'Applied AI Safety', player_handle: 'Pip' }).startsWith('Pip'),
  'player_handle shape: the human name leads, the lab follows');

console.log('\n4. dev-build marker fires only on evidence');
check(isDevBuild({ game_mode: 'v0.13.2-dev' }), 'game_mode "v0.13.2-dev" is a dev build');
check(isDevBuild({ game_mode: 'v0.13.2+dev' }), 'game_mode "v0.13.2+dev" is a dev build');
check(isDevBuild({ game_mode: 'v0.13.2-development-preview' }), '"-development" counts too');
check(isDevBuild({ dev_mode: true }), 'explicit dev_mode:true is a dev build');
check(isDevBuild({ game_mode: 'v0.13.2', dev_mode: 'true' }), 'stringified "true" honoured');
check(!isDevBuild({ game_mode: 'v0.13.2' }), 'plain release build is NOT flagged');
check(!isDevBuild({ game_mode: 'v0.13.2-rc1' }), 'a release candidate is NOT a dev build');
check(!isDevBuild({}), 'an entry with no version info at all is NOT flagged');

console.log('\n5. absence is never rendered as a clean bill of health');
check(devBadgeHTML({ game_mode: 'v0.13.2' }) === '',
  'unmarked entry renders NOTHING -- not a "release build" badge');
check(devBadgeHTML({}) === '', 'empty entry renders nothing');
check(/dev-badge/.test(devBadgeHTML({ dev_mode: true })), 'marked entry renders the badge');
check(!/\bclean\b|\bverified\b|\blegit/i.test(devBadgeHTML({ dev_mode: true })),
  'the badge makes no claim about entries that lack it');
check(/not comparable/i.test(devBadgeHTML({ dev_mode: true })),
  'the badge explains WHY it matters (non-comparability), not just that it is dev');

console.log('\n6. the supporting CSS exists');
check(/\.dev-badge\s*\{/.test(src), '.dev-badge rule present');
check(/\.identity-lab\s*\{/.test(src), '.identity-lab rule present');

console.log('\n7. the search filter survives a malformed entry');
const searchBlock = src.match(/const hay = \(e\) =>[\s\S]{0,260}/);
check(!!searchBlock, 'search builds its haystack from a coerced field list');
check(!!searchBlock && /filter\(Boolean\)/.test(searchBlock[0]),
  'missing fields are filtered out rather than .toLowerCase()-d');
check(!/entry\.player_name\.toLowerCase\(\)/.test(src),
  'no unguarded .toLowerCase() on an API-supplied field');

console.log(failures === 0
  ? '\nOK: board rendering escapes every API-supplied field; identity and dev marker stay honest.'
  : '\n' + failures + ' FAILURE(S)');
process.exit(failures === 0 ? 0 : 1);
