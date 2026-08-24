// Sibling of test-download-resolution.js, for the OTHER half of the download
// surface: the PROSE.
//
// WHY IT EXISTS. On 2026-08-24 v0.14.3 published with no macOS asset. The download
// buttons self-healed -- resolveDownloads() degraded macOS to "coming soon" with
// nobody touching a file, and test-download-resolution.js had covered exactly that
// case since before it happened. Three lines of static prose did not self-heal,
// because no mechanism fed them: "Windows, macOS & Linux", "64-bit Windows, macOS,
// or Linux", and three hand-typed platform chips. renderPlatformClaims() now writes
// all of them from version.json -> latest_release.platforms. This file is the
// coverage that makes that claim checkable.
//
// It extracts renderPlatformClaims() and its helpers out of public/index.html and
// runs them against a DOM/fetch shim, exactly as its sibling does for
// resolveDownloads(). Nothing is mocked at the boundary that matters: the shim
// feeds a version.json document and the assertions read the resulting text.
//
// BOTH ANSWERS ARE PROVEN, which is the point. Scenario A feeds all three platforms
// and asserts three render. Scenario B feeds macOS: false and asserts the same code
// path renders an honest absence and NEVER an availability claim for macOS. A test
// that only ever sees the passing state has not been shown to work.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');

// ---------------------------------------------------------------------------
// Extract the renderer. Same technique as test-download-resolution.js: pull the
// real shipped source out of the page rather than re-implementing it here, so the
// test cannot pass against code that is not the code that ships.
// ---------------------------------------------------------------------------
const m = src.match(
  /const PLATFORM_ORDER = [\s\S]*?\n\t\tasync function renderPlatformClaims\(\) \{[\s\S]*?\n\t\t\}/);
if (!m) { console.error('FAIL: could not extract renderPlatformClaims() and helpers'); process.exit(1); }
const RENDERER_SRC = m[0];

// ---------------------------------------------------------------------------
// Minimal DOM. Only what the renderer touches; anything it starts using that is
// not here will throw rather than silently no-op.
// ---------------------------------------------------------------------------
function textNode(s) { return { nodeType: 3, _text: s, get textContent() { return this._text; } }; }

function makeEl(tag, opts) {
  opts = opts || {};
  return {
    tag,
    dataset: Object.assign({}, opts.dataset),
    style: {},
    _attrs: Object.assign({}, opts.attrs),
    // Modelled as a child text node, NOT a separate _text field. Setting
    // .textContent and then appendChild()-ing is exactly what appendAbsenceClause()
    // does to a chip, and a shim that dropped the first half would have reported a
    // passing chip with no text in it.
    _children: (opts.text === undefined || opts.text === '') ? [] : [textNode(opts.text)],
    title: '',
    get textContent() { return this._children.map(c => c.textContent).join(''); },
    set textContent(v) { this._children = (v === '' ? [] : [textNode(v)]); },
    appendChild(n) { this._children.push(n); return n; },
    hasAttribute(k) { return k in this._attrs; },
    getAttribute(k) { return this._attrs[k]; },
    setAttribute(k, v) { this._attrs[k] = v; },
    removeAttribute(k) { delete this._attrs[k]; },
    // href/target/rel reflect to attributes, as they do on a real HTMLAnchorElement.
    // Without this, `a.rel = 'noopener'` would set an inert plain property and the
    // rel=noopener assertion would fail against correct code.
    get href() { return this._attrs.href; },
    set href(v) { this._attrs.href = v; },
    get target() { return this._attrs.target; },
    set target(v) { this._attrs.target = v; },
    get rel() { return this._attrs.rel; },
    set rel(v) { this._attrs.rel = v; },
    // Links created by the renderer end up here; the tests read them back.
    links() {
      const out = [];
      const walk = (n) => {
        if (n.tag === 'a') out.push(n);
        (n._children || []).forEach(walk);
      };
      this._children.forEach(walk);
      return out;
    },
    childCount() { return this._children.length; },
  };
}

const RELEASE_PAGE = 'https://github.com/PipFoweraker/pdoom1/releases/latest';

// The REAL shipped initial state of every rendered slot, so a scenario that leaves
// a slot alone can be asserted to have left the honest placeholder standing.
function freshSlots() {
  const mk = (slot, text, extra) => makeEl('span', Object.assign(
    { dataset: { platformClaim: 'rendered', platformSlot: slot }, text }, extra || {}));
  const button = (key, label) => makeEl('a', {
    dataset: { platformClaim: 'rendered', platformSlot: 'button',
               platformKey: key, platformLabel: label },
    attrs: { href: RELEASE_PAGE, target: '_blank', rel: 'noopener' },
    text: label + ' — checking latest release',
  });
  return [
    mk('platform-list', 'Platform availability loads from the current release'),
    mk('requirements', '64-bit desktop OS — the platform list loads from the current release'),
    makeEl('div', { dataset: { platformClaim: 'rendered', platformSlot: 'chips' },
                    text: 'Loading from the current release...' }),
    mk('install-note', 'Which builds this release carries loads from the current release.'),
    button('windows', 'Windows'),
    button('macos', 'macOS'),
    button('linux', 'Linux'),
  ];
}

// `payload` is what /data/version.json returns. `ok:false` models an unreachable
// file; `throws:true` models a network error mid-fetch.
async function render(payload, opts) {
  opts = opts || {};
  const slots = freshSlots();
  const document = {
    querySelectorAll(sel) {
      if (sel !== '[data-platform-claim="rendered"]') {
        throw new Error('unexpected selector: ' + sel);
      }
      return slots;
    },
    createElement: (t) => makeEl(t),
    createTextNode: textNode,
  };
  const fetch = async (url) => {
    if (url !== '/data/version.json') throw new Error('unexpected fetch: ' + url);
    if (opts.throws) throw new Error('network down');
    if (opts.ok === false) return { ok: false, json: async () => ({}) };
    return { ok: true, json: async () => payload };
  };
  const fn = new Function('document', 'fetch', RENDERER_SRC + '\nreturn renderPlatformClaims;')(document, fetch);
  await fn();
  const by = {};
  for (const s of slots) {
    const k = s.dataset.platformSlot === 'button'
      ? 'button:' + s.dataset.platformKey : s.dataset.platformSlot;
    by[k] = s;
  }
  return by;
}

// Deliberately NOT a real version literal. Two reasons: asserting on a token
// that could never be hardcoded anywhere proves the rendered version came off
// the feed, and a real version here would go stale at the next bump -- which is
// exactly what check-stale-facts.py flags test fixtures for elsewhere in this
// directory.
const V = 'TEST-RELEASE';
const feed = (platforms, tracking) => {
  const rel = { version: V, platforms };
  if (tracking) rel.platform_tracking = tracking;
  return { latest_release: rel };
};
const TRACKING_URL = 'https://github.com/PipFoweraker/pdoom1/issues/9999';

let failures = 0;
const check = (cond, msg) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) failures++;
};

// Everything BEFORE the absence clause. appendAbsenceClause() introduces the clause
// with an em dash + "no" or a sentence break + "No", and a platform named after that
// point is being declared missing, not offered. Without this split, the honest
// "64-bit Windows and Linux — no macOS build in TEST-RELEASE" reads as a macOS claim to
// any pattern that scans the whole string.
function availabilityHalf(text) {
  return text.split(/\s—\s*no\s|\.\s+No\s/i)[0];
}

// A claim of availability for a platform, in the shape a reader would take as one.
// Used to assert ABSENCE of such a claim, so it is deliberately generous within the
// availability half: any hit counts against us.
function claimsAvailable(text, name) {
  const n = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const head = availabilityHalf(text);
  return new RegExp('(download for|available on|get it on|play on|runs on)\\s+' + n, 'i').test(head)
    || new RegExp('64-bit[^.]*\\b' + n + '\\b', 'i').test(head)
    || new RegExp('carries builds for[^.]*\\b' + n + '\\b', 'i').test(head);
}

(async () => {
  // -------------------------------------------------------------------------
  console.log('\nScenario A: all three platforms shipped -> all three render');
  let s = await render(feed({ windows: true, macos: true, linux: true }));
  check(s['platform-list'].textContent === 'Windows, macOS and Linux',
    'platform list renders all three, in order');
  check(s['requirements'].textContent === '64-bit Windows, macOS and Linux',
    'system requirements render all three');
  check(s['chips'].childCount() === 3, 'three platform chips rendered');
  check(s['chips'].textContent === 'WindowsmacOSLinux',
    'each chip is a bare platform name, no absence text');
  check(s['install-note'].textContent === 'This release carries builds for Windows, macOS and Linux.',
    'install note names all three');
  check(s['button:macos'].textContent === 'Download for macOS',
    'macOS button becomes a live download label');
  check(s['button:macos'].hasAttribute('href'), 'macOS button keeps its href');
  check(!/coming soon|no .* build/i.test(s['platform-list'].textContent + s['requirements'].textContent),
    'no absence clause anywhere when nothing is absent');
  check(s['platform-list'].links().length === 0, 'no tracking link when nothing is missing');

  // -------------------------------------------------------------------------
  console.log('\nScenario B: macOS absent, feed carries a tracking URL -> honest absence + link');
  s = await render(feed({ windows: true, macos: false, linux: true },
                        { macos: { url: TRACKING_URL } }));
  check(s['platform-list'].textContent === 'Windows and Linux — no macOS build in TEST-RELEASE (tracking the build)',
    'platform list names what shipped, then says plainly what did not');
  check(s['requirements'].textContent.indexOf('64-bit Windows and Linux') === 0,
    'system requirements list only shipped platforms');
  check(/no macOS build in TEST-RELEASE/.test(s['requirements'].textContent),
    'system requirements still SAY macOS is absent rather than quietly dropping it');
  check(s['platform-list'].links().length === 1, 'exactly one tracking link');
  check(s['platform-list'].links()[0].href === TRACKING_URL, 'the link is the feed-supplied URL');
  check(s['platform-list'].links()[0].getAttribute('rel') === 'noopener',
    'the tracking link is rel=noopener');
  check(s['chips'].childCount() === 3, 'three chips still render -- absence is shown, not hidden');
  check(/macOS — no build in TEST-RELEASE/.test(s['chips'].textContent),
    'the macOS chip says there is no build');
  check(s['chips'].links().length === 1 && s['chips'].links()[0].href === TRACKING_URL,
    'the macOS chip links to the tracking issue');
  check(s['button:macos'].textContent === 'macOS — coming soon',
    'macOS button degrades to "coming soon" from version.json alone');
  check(!s['button:macos'].hasAttribute('href'),
    'macOS button has no href -- not a dead link to a release page with no Mac asset');
  check(s['button:macos'].getAttribute('aria-disabled') === 'true',
    'macOS button is marked disabled for assistive tech');
  check(s['button:windows'].textContent === 'Download for Windows' &&
        s['button:windows'].hasAttribute('href'),
    'Windows button is unaffected and stays live');

  // THE LOAD-BEARING NEGATIVE: no rendered slot may assert a macOS build exists.
  for (const key of ['platform-list', 'requirements', 'install-note', 'chips',
                     'button:macos', 'button:windows']) {
    check(!claimsAvailable(s[key].textContent, 'macOS'),
      `${key} makes no availability claim for macOS`);
  }
  check(!/older release|previous release|earlier version|\bv\d+\.\d+\.\d+\b/i.test(
          Object.values(s).map(e => e.textContent).join(' ')),
    'nothing points a Mac user at an older release (ruled out 2026-08-24)');

  // -------------------------------------------------------------------------
  console.log('\nScenario C: macOS absent, feed carries NO platform_tracking -> honest text, no link');
  s = await render(feed({ windows: true, macos: false, linux: true }));
  check(s['platform-list'].textContent === 'Windows and Linux — no macOS build in TEST-RELEASE',
    'same honest sentence, with the link simply absent');
  check(s['platform-list'].links().length === 0, 'no link is invented when the feed has none');
  check(s['chips'].links().length === 0, 'no chip link is invented either');
  check(s['button:macos'].textContent === 'macOS — coming soon',
    'the button degrades identically without the field');
  check(!claimsAvailable(s['platform-list'].textContent, 'macOS'),
    'still no availability claim for macOS');

  // A bare string URL is accepted too, so the pdoom1 side can land either shape.
  s = await render(feed({ windows: true, macos: false, linux: true }, { macos: TRACKING_URL }));
  check(s['platform-list'].links().length === 1 &&
        s['platform-list'].links()[0].href === TRACKING_URL,
    'a bare string tracking URL is accepted as well as { url: ... }');

  // A malformed entry must not produce a broken link.
  s = await render(feed({ windows: true, macos: false, linux: true }, { macos: { issue: 42 } }));
  check(s['platform-list'].links().length === 0,
    'a tracking entry with no url yields no link rather than an undefined href');

  // -------------------------------------------------------------------------
  console.log('\nScenario D: two platforms absent -> honest, and no misattributed link');
  s = await render(feed({ windows: true, macos: false, linux: false },
                        { macos: { url: TRACKING_URL } }));
  check(s['platform-list'].textContent === 'Windows — no macOS and Linux builds in TEST-RELEASE',
    'both absences named in one clause');
  check(s['platform-list'].links().length === 0,
    'no single link when several platforms are missing -- it would mean the wrong one');
  check(s['chips'].links().length === 1,
    'the per-chip links still attribute correctly (only macOS has a URL)');

  console.log('\nScenario D2: nothing shipped at all -> says so, claims nothing');
  s = await render(feed({ windows: false, macos: false, linux: false }));
  check(s['platform-list'].textContent === 'No Windows, macOS and Linux builds in TEST-RELEASE',
    'an empty release renders as an absence, not as an empty string');
  check(s['install-note'].textContent.indexOf('This release carries no platform builds.') === 0,
    'install note says plainly that nothing shipped');

  // -------------------------------------------------------------------------
  // UNKNOWN, not a reassuring default (ruled 2026-08-23). Every failure path must
  // leave the shipped placeholder standing -- it names no OS, so it claims nothing.
  console.log('\nScenario E: version.json unreachable / malformed -> UNKNOWN placeholders stand');
  const PLACEHOLDER = 'Platform availability loads from the current release';
  const REQ_PLACEHOLDER = '64-bit desktop OS — the platform list loads from the current release';
  for (const [label, args] of [
    ['fetch returns !ok', [null, { ok: false }]],
    ['fetch throws', [null, { throws: true }]],
    ['no latest_release', [{}, {}]],
    ['latest_release with no platforms key', [{ latest_release: { version: V } }, {}]],
    ['platforms is not an object', [{ latest_release: { version: V, platforms: 'yes' } }, {}]],
    ['platforms has no recognised keys', [{ latest_release: { version: V, platforms: { beos: true } } }, {}]],
    ['platform values are not booleans', [{ latest_release: { version: V, platforms: { windows: 1, macos: 0 } } }, {}]],
  ]) {
    const r = await render(args[0], args[1]);
    check(r['platform-list'].textContent === PLACEHOLDER &&
          r['requirements'].textContent === REQ_PLACEHOLDER,
      `${label} -> placeholders untouched (UNKNOWN, not a default)`);
    check(r['button:macos'].hasAttribute('href') &&
          /checking latest release/.test(r['button:macos'].textContent),
      `${label} -> buttons left for resolveDownloads(), not falsely disabled`);
  }

  // -------------------------------------------------------------------------
  // The shim above claims to model the SHIPPED markup. Assert that, or the whole
  // file is testing a page that does not exist. This is the check that would have
  // caught test-download-resolution.js's shim drifting off the real button labels.
  console.log('\nScenario F: the shipped markup matches what this test models');
  const declared = [...src.matchAll(/data-platform-slot="([^"]+)"/g)].map(x => x[1]);
  const expected = ['platform-list', 'requirements', 'chips', 'install-note',
                    'button', 'button', 'button'];
  check(JSON.stringify(declared.sort()) === JSON.stringify(expected.sort()),
    'index.html declares exactly the slots this test renders (' + declared.join(', ') + ')');
  for (const slot of new Set(declared)) {
    check(RENDERER_SRC.indexOf("'" + slot + "'") !== -1,
      `renderPlatformClaims() handles the "${slot}" slot declared in the markup`);
  }
  // Every rendered element must carry both attributes -- one without a slot would
  // be silently skipped by the renderer and silently trusted by a reader.
  const renderedTags = [...src.matchAll(/<[a-zA-Z][^>]*data-platform-claim="rendered"[^>]*>/g)];
  check(renderedTags.length === 7,
    `all 7 rendered elements found in index.html (got ${renderedTags.length})`);
  check(renderedTags.every(t => /data-platform-slot="/.test(t[0])),
    'every data-platform-claim="rendered" element also declares a slot');

  // The shipped placeholders must themselves be honest with JS off: the prose ones
  // name no operating system at all, and the buttons say they are still checking.
  console.log('\nScenario G: shipped placeholders claim nothing');
  for (const [slot, rx] of [
    ['platform-list', /Platform availability loads from the current release/],
    ['requirements', /64-bit desktop OS/],
    ['install-note', /Which builds this release carries loads from the current release\./],
  ]) {
    const tag = src.match(new RegExp('data-platform-slot="' + slot + '">([^<]*)<'));
    check(!!tag && rx.test(tag[1]), `${slot} ships the expected placeholder`);
    check(!!tag && !/\b(windows|mac\s?os|osx|linux)\b/i.test(tag[1]),
      `${slot} placeholder names no operating system`);
  }
  const btnLabels = [...src.matchAll(
    /data-platform-slot="button"[^>]*>\s*([^<]*?)\s*\n/g)].map(x => x[1]);
  check(btnLabels.length === 3, 'three button placeholders found');
  check(btnLabels.every(l => /checking latest release/.test(l)),
    'every button placeholder says it is still checking, not "Download for <OS>"');
  check(btnLabels.every(l => !/^Download for/.test(l)),
    'no button ships a static "Download for <OS>" availability claim');

  console.log(failures ? `\n${failures} FAILURE(S)` : '\nAll checks passed.');
  process.exit(failures ? 1 : 0);
})();
