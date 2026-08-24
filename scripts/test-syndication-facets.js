// Forced-failure test for Bluesky link facets.
//
// WHY THIS FILE EXISTS
// --------------------
// An AT Protocol facet marks a span of a post as a link, and the span is
// measured in UTF-8 BYTES. syndicate-bluesky.js used a JavaScript string index
// instead. Those two numbers are equal for as long as the text before the URL
// is pure ASCII -- which every auto-generated draft in content/syndication/
// happens to be. So the defect was live, and a test written against the real
// drafts would have passed.
//
// That is CLAUDE.md's "a guard seen only in its passing state has not been shown
// to work", so the central assertion here is NOT "the numbers look right". It is
// a round trip: take the byte range the facet claims, cut it out of the UTF-8
// encoding of the post, decode it, and require that what comes back is exactly
// the URL. That invariant cannot be satisfied by accident, and it is the same
// thing Bluesky's renderer does.
//
// The last block re-runs the OLD algorithm on the same inputs and asserts it
// FAILS the round trip. Without it this file could be green because the bug is
// gone or because the test never discriminated, and those two look identical
// from the outside.
//
// Run: node scripts/test-syndication-facets.js

const path = require('path');
const { linkFacets } = require(
  path.join(__dirname, '..', 'netlify', 'functions', 'syndicate-bluesky.js'));

let pass = 0, fail = 0;
const out = console.log.bind(console);

function ok(name, cond, detail) {
  if (cond) { pass++; out('  PASS ' + name); }
  else { fail++; out('  FAIL ' + name + (detail ? ' -> ' + detail : '')); }
}

// The invariant, stated once and reused: the bytes the facet points at ARE the
// link. Everything else in this file is a way of getting an interesting text
// into this function.
function spanDecodesTo(text, facet) {
  const buf = Buffer.from(text, 'utf8');
  return buf.slice(facet.index.byteStart, facet.index.byteEnd).toString('utf8');
}

function roundTrips(text, facet) {
  return spanDecodesTo(text, facet) === facet.features[0].uri;
}

const URL = 'https://pdoom1.com/';

out('the ASCII case -- the one that hid the bug');
{
  const text = 'p(Doom)1 is playable. ' + URL;
  const f = linkFacets(text);
  ok('one facet', f.length === 1, 'got ' + f.length);
  ok('span decodes to the URL', f.length === 1 && roundTrips(text, f[0]),
     f.length === 1 ? spanDecodesTo(text, f[0]) : '');
  // Recorded deliberately: here the buggy and correct answers AGREE. This line
  // is why an ASCII-only corpus could never have caught the defect.
  ok('byte index happens to equal the string index (documents the blind spot)',
     f[0].index.byteStart === text.indexOf(URL));
}

out('non-ASCII before the link -- where it actually broke');
[
  ['em dash', 'Early alpha — rough, free. ' + URL],
  ['curly quotes', '“mostly via spreadsheet” ' + URL],
  ['emoji (4 bytes)', '\u{1F680} ship it ' + URL],
  ['accented latin', 'café conversations about doom ' + URL],
  ['several, mixed', '— “x” \u{1F680} é ' + URL],
].forEach(([label, text]) => {
  const f = linkFacets(text);
  ok(label + ': one facet', f.length === 1, 'got ' + f.length);
  if (f.length !== 1) return;
  ok(label + ': span decodes to the URL', roundTrips(text, f[0]),
     JSON.stringify(spanDecodesTo(text, f[0])));
  ok(label + ': byte index is NOT the string index (the drift is real)',
     f[0].index.byteStart !== text.indexOf(URL),
     'both were ' + f[0].index.byteStart);
});

out('the same URL twice -- indexOf() found only the first');
{
  const text = 'read ' + URL + ' then — again — ' + URL;
  const f = linkFacets(text);
  ok('two facets', f.length === 2, 'got ' + f.length);
  ok('their spans differ', f.length === 2 &&
     f[0].index.byteStart !== f[1].index.byteStart);
  ok('both spans decode to the URL',
     f.length === 2 && f.every(x => roundTrips(text, x)));
}

out('trailing punctuation is not part of the link');
{
  const text = 'see ' + URL + '.';
  const f = linkFacets(text);
  ok('full stop is excluded from the uri', f[0].features[0].uri === URL,
     f[0].features[0].uri);
  ok('and from the span too', roundTrips(text, f[0]),
     spanDecodesTo(text, f[0]));
}
{
  const wiki = 'https://en.wikipedia.org/wiki/Doom_(1993)';
  const text = 'the original ' + wiki + ', obviously';
  const f = linkFacets(text);
  ok('a BALANCED bracket stays in the uri', f[0].features[0].uri === wiki,
     f[0].features[0].uri);
  ok('the comma after it does not', roundTrips(text, f[0]),
     spanDecodesTo(text, f[0]));
}
{
  const text = '(see ' + URL + ')';
  const f = linkFacets(text);
  ok('an UNBALANCED closer is trimmed', f[0].features[0].uri === URL,
     f[0].features[0].uri);
}

out('nothing to link');
{
  ok('no URL yields no facets', linkFacets('no links here at all').length === 0);
  ok('empty text yields no facets', linkFacets('').length === 0);
}

out('the old algorithm must FAIL this suite (proves the test discriminates)');
{
  // Verbatim shape of what syndicate-bluesky.js did before 2026-08-24.
  function legacyFacets(text) {
    const facets = [];
    const urlMatch = text.match(/(https?:\/\/[^\s]+)/g);
    if (urlMatch) {
      urlMatch.forEach(foundUrl => {
        const start = text.indexOf(foundUrl);
        facets.push({
          index: { byteStart: start, byteEnd: start + foundUrl.length },
          features: [{ $type: 'app.bsky.richtext.facet#link', uri: foundUrl }]
        });
      });
    }
    return facets;
  }

  const emDash = 'Early alpha — rough, free. ' + URL;
  const legacy = legacyFacets(emDash);
  ok('legacy: span does NOT decode to the URL on em-dash copy',
     !roundTrips(emDash, legacy[0]),
     'legacy round-tripped, so this test cannot tell the versions apart');

  const twice = 'read ' + URL + ' then again ' + URL;
  const legacyTwice = legacyFacets(twice);
  ok('legacy: duplicate URLs collapse to the same span',
     legacyTwice.length === 2 &&
     legacyTwice[0].index.byteStart === legacyTwice[1].index.byteStart,
     'legacy handled repeats, so that half of the fix is untested');
}

out('');
out(pass + ' passed, ' + fail + ' failed');
process.exit(fail === 0 ? 0 : 1);
