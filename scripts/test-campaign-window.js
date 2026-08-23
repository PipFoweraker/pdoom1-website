// The Manifund campaign link must appear while the campaign is open and be GONE
// once it has closed -- without anyone remembering to delete it.
//
// Why this test exists. pdoom1-website#194 ("Manifund is LIVE -- site should point
// at it") sat open with no comments for 25 days while the campaign ran. A link
// added by hand and scheduled for removal by hand would fail the same way in the
// other direction: it would outlive the campaign and invite people to fund a thing
// that has stopped taking money. So public/assets/js/navigation.js gates the link
// on a clock, and this file is the proof the clock is wired up.
//
// The whole point is that it is time-dependent behaviour, so this test INJECTS a
// fake Date into the sandbox rather than depending on when it happens to run --
// otherwise the test would itself expire on 2026-09-10, which is the disease.
//
// Run: node scripts/test-campaign-window.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const NAV = path.join(__dirname, '..', 'public', 'assets', 'js', 'navigation.js');
const INDEX = path.join(__dirname, '..', 'public', 'index.html');
const navSrc = fs.readFileSync(NAV, 'utf8');
const indexSrc = fs.readFileSync(INDEX, 'utf8');

let pass = 0, fail = 0;
const out = console.log.bind(console);
function ok(name, cond, detail) {
  if (cond) { pass++; out('  PASS ' + name); }
  else { fail++; out('  FAIL ' + name + (detail ? ' -> ' + detail : '')); }
}

// --- minimal DOM, with the one thing test-navigation.js's stub lacks: a body
//     that can actually hold and lose children, since removal is what we test.
function mkEl(tag) {
  return {
    tagName: tag, id: '', textContent: '', innerHTML: '', attrs: {},
    children: [], parentNode: null,
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    hasAttribute(k) { return k in this.attrs; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); c.parentNode = null; return c; },
    addEventListener() {},
  };
}

// Load navigation.js with the clock pinned to `nowIso`, on a page that already
// carries one data-campaign-window element (standing in for the homepage band).
function render(nowIso, src) {
  const head = mkEl('head'), header = mkEl('header'), body = mkEl('body');
  const band = mkEl('section');
  band.attrs['data-campaign-window'] = '';
  body.appendChild(band);
  const doc = {
    readyState: 'complete', head, body,
    createElement: (t) => mkEl(t),
    getElementById: (id) => head.children.find(c => c.id === id) || null,
    querySelector: (sel) => (sel === 'header' ? header : null),
    querySelectorAll: (sel) => (sel === '[data-campaign-window]'
      ? body.children.filter(c => 'data-campaign-window' in c.attrs) : []),
    addEventListener() {},
  };
  const Real = Date;
  const fixed = new Real(nowIso).getTime();
  class Frozen extends Real {
    constructor(...a) { super(...(a.length ? a : [fixed])); }
    static now() { return fixed; }
  }
  Frozen.UTC = Real.UTC;
  const sandbox = { document: doc, location: { pathname: '/' },
                    console: { warn() {}, log() {}, error() {} }, Date: Frozen };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(src || navSrc, sandbox);
  return {
    nav: header.innerHTML,
    bandStillInDom: body.children.indexOf(band) !== -1,
  };
}

out('while the campaign is open');
for (const when of ['2026-07-29T00:00:00Z', '2026-08-23T00:00:00Z', '2026-09-09T23:59:59Z']) {
  const r = render(when);
  ok(when + ' -- nav carries the campaign link', /nav-fund/.test(r.nav));
  ok(when + ' -- it points at the campaign',
     /https:\/\/manifund\.org\/projects\/fund-development-of-pdoom1/.test(r.nav));
  ok(when + ' -- the page band survives', r.bandStillInDom);
}

out('\nonce the campaign has closed (2026-09-09)');
for (const when of ['2026-09-10T00:00:01Z', '2026-10-01T00:00:00Z', '2027-01-01T00:00:00Z']) {
  const r = render(when);
  ok(when + ' -- no campaign link in the nav', !/nav-fund/.test(r.nav));
  ok(when + ' -- no manifund URL anywhere in the nav',
     !/manifund\.org/.test(r.nav));
  ok(when + ' -- the page band is REMOVED, not merely hidden', !r.bandStillInDom);
}

out('\nthe slot never leaks');
for (const when of ['2026-08-23T00:00:00Z', '2026-10-01T00:00:00Z']) {
  ok(when + ' -- CAMPAIGN_SLOT placeholder is substituted away',
     !/CAMPAIGN_SLOT/.test(render(when).nav));
}

// Forced-failure. Without this, every assertion above could be passing for the
// wrong reason -- e.g. if applyCampaignWindow() were reading a constant nothing
// sets. Move the close date into the past IN THE SOURCE and the open-window cases
// must flip. If they do not, this file is testing nothing.
out('\nthe gate can still close (forced-failure test)');
{
  const mutated = navSrc.replace(/const CAMPAIGN_CLOSES = Date\.UTC\([^)]*\);/,
                                 'const CAMPAIGN_CLOSES = Date.UTC(2000, 0, 1);');
  ok('the mutation applied', mutated !== navSrc,
     'CAMPAIGN_CLOSES declaration not found -- this test has drifted off the source');
  const r = render('2026-08-23T00:00:00Z', mutated);
  ok('with a past close date the nav link is gone', !/nav-fund/.test(r.nav));
  ok('with a past close date the band is removed', !r.bandStillInDom);
}

// The markup half of the contract: the homepage band must actually be static in
// index.html. If someone converts it to script-injected markup, the site shows
// nothing while the campaign is live whenever the script fails to load, which is
// the expensive failure. See the comment above the band in index.html.
out('\nthe homepage band is static markup, not script-injected');
{
  const attrs = (indexSrc.match(/<[a-z]+[^>]*\sdata-campaign-window[\s>]/g) || []);
  ok('index.html carries at least one data-campaign-window element',
     attrs.length >= 1, 'found ' + attrs.length);
  ok('and the band links to the campaign',
     /manifund\.org\/projects\/fund-development-of-pdoom1/.test(indexSrc));
}

out(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
