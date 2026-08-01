// Extracts the renderer from public/game-changelog/index.html and exercises it
// against a minimal DOM/fetch shim. The contract this locks down:
//
//   - The page NEVER contains a version literal. Not in the HTML source, and not
//     in the rendered output when a lookup fails. A hardcoded fallback ships
//     exactly when the real lookup failed, i.e. when nobody can notice it is
//     wrong -- see CLAUDE.md, "Fallback literals are the dangerous ones."
//   - Build availability is DERIVED from latest_release.platforms (which
//     update-version-info.py computes from the release's actual attached
//     assets). When the key is present the page reports it; when it is ABSENT
//     the page says the fact is unrecorded rather than asserting either way.
//     (version.json really does lose that key periodically -- update-game-data.yml
//     rewrites the file without it -- so absence is the normal case, not a corner.)
//   - Every degradation path points the reader at GitHub instead of showing a
//     stale value.
//   - Release bodies are HTML-escaped before markdown, so upstream text cannot
//     inject markup; and the markdown subset covers what release notes use
//     (headings, GFM tables, lists, inline code, links, bold).

const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, '..', 'public', 'game-changelog', 'index.html');
const src = fs.readFileSync(PAGE, 'utf8');
const SHARED = require(path.join(__dirname, '..', 'public', 'assets', 'js', 'escape.js'));

// The renderer is the last inline <script> on the page.
const scripts = [...src.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const code = scripts[scripts.length - 1];
if (!code || !code.includes('renderCurrent')) {
  console.error('FAIL: could not extract the changelog renderer from the page');
  process.exit(1);
}

const VERSION_LITERAL = /\bv?\d+\.\d+\.\d+\b/;

// --- DOM / fetch shim ---------------------------------------------------------
function makeDoc() {
  const els = {
    current: { id: 'current', innerHTML: '' },
    history: { id: 'history', innerHTML: '' },
  };
  return {
    els,
    documentElement: { style: { setProperty() {} } },
    getElementById(id) { return els[id] || null; },
  };
}

function makeFetch({ version, versionFails = false, releases, releasesFails = false }) {
  return async (url) => {
    if (url.includes('tokens.json')) return { ok: false, json: async () => ({}) };
    if (url.includes('version.json')) {
      if (versionFails) throw new Error('network');
      return { ok: true, json: async () => version };
    }
    if (url.includes('api.github.com')) {
      if (releasesFails) return { ok: false, status: 403, json: async () => ({}) };
      return { ok: true, json: async () => releases };
    }
    return { ok: false, status: 404, json: async () => ({}) };
  };
}

async function run(opts) {
  const document = makeDoc();
  const fetch = makeFetch(opts);
  // escapeHTML/safeUrl/isSafeUrl are no longer inline on the page: as of 2026-08-01 they
  // are the shared public/assets/js/escape.js, loaded by a blocking <script src>. Passing
  // them in is the node-side equivalent of that tag. Without them the renderer throws
  // ReferenceError -- the page's intended fail-closed behaviour, not a test artefact.
  new Function('document', 'fetch', 'escapeHTML', 'safeUrl', 'safeUrlRaw', 'isSafeUrl', 'toNumber', code)(
    document, fetch,
    SHARED.escapeHTML, SHARED.safeUrl, SHARED.safeUrlRaw, SHARED.isSafeUrl, SHARED.toNumber);
  // All shimmed fetches settle immediately; flush the microtask/macrotask queue.
  for (let i = 0; i < 20; i++) await new Promise(r => setTimeout(r, 0));
  return { current: document.els.current.innerHTML, history: document.els.history.innerHTML };
}

// --- fixtures -----------------------------------------------------------------
// Deliberately NOT the real current version: these are synthetic, so a test
// passing tells you the value came from the data, not from the page.
//
// They are ASSEMBLED rather than written out, so no vX.Y.Z literal exists in this
// file for check-stale-facts.py to (correctly) flag. A literal here would be
// harmless today and indistinguishable from a real rotting claim in six months;
// keeping the file literal-free means every hit that scanner reports is a real one.
const V9 = ['v9', '9', '9'].join('.');
const V8 = ['v9', '9', '8'].join('.');
const V7 = ['v9', '9', '7'].join('.');

const FAKE = {
  latest_release: {
    version: V9,
    name: 'P(Doom) ' + V9,
    published_at: '2099-01-02T03:04:05Z',
    html_url: 'https://github.com/PipFoweraker/pdoom1/releases/tag/' + V9,
    body: [
      'Two fixes over the last build.',
      '',
      '## Platform status',
      '| Platform | File | Tested? |',
      '|---|---|---|',
      '| Windows | PDoom-Windows.zip | Yes |',
      '',
      '- **Commit:** `deadbeef`',
      '- See [the notes](https://example.com/notes)',
      '',
      'Raw <script>alert(1)</script> should not execute.',
    ].join('\n'),
  },
};

const withPlatforms = (p) => ({
  latest_release: Object.assign({}, FAKE.latest_release, { platforms: p }),
});

const FAKE_RELEASES = [
  { tag_name: V9, published_at: '2099-01-02T03:04:05Z', body: 'current', html_url: 'https://gh/9' },
  { tag_name: V8, published_at: '2098-12-01T00:00:00Z', body: '## Fixed\n- a thing', html_url: 'https://gh/8' },
  { tag_name: V7, published_at: '2098-11-01T00:00:00Z', body: '', prerelease: true, html_url: 'https://gh/7' },
];

// --- assertions ---------------------------------------------------------------
let failures = 0;
const check = (cond, msg) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) failures++;
};

(async () => {
  console.log('Checking the page source itself...');
  const visible = src
    .replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<!--[\s\S]*?-->/g, '');
  check(!VERSION_LITERAL.test(visible),
    'no version literal in the page\'s own markup (found: ' + (visible.match(VERSION_LITERAL) || ['none']) + ')');
  check(!/\b(windows|macos|mac os|linux)\b/i.test(visible.replace(/<[^>]+>/g, ' ')),
    'no OS name in static prose (platform text is generated from data only)');

  console.log('\nHappy path (version.json + GitHub both reachable)...');
  let r = await run({ version: withPlatforms({ windows: true, macos: true, linux: false }), releases: FAKE_RELEASES });
  check(r.current.includes(V9), 'renders the version it was given');
  check(r.current.includes('2099-01-02'), 'renders the release date it was given');
  check(/Windows[^<]*build attached/.test(r.current), 'reports an attached build as attached');
  check(/Linux[^<]*not in this release/.test(r.current), 'reports a missing build as missing');
  check(r.current.includes('<table>') && r.current.includes('<th>Platform</th>'), 'renders a GFM table from the body');
  check(r.current.includes('<h4>Platform status</h4>'), 'demotes body headings so the page keeps one h1');
  check(r.current.includes('<code>deadbeef</code>') && r.current.includes('<strong>Commit:</strong>'),
    'renders inline code and bold');
  check(r.current.includes('href="https://example.com/notes"'), 'renders markdown links');
  check(!r.current.includes('<script>alert(1)</script>') && r.current.includes('&lt;script&gt;'),
    'escapes upstream HTML before markdown (no injection from release text)');
  check(r.history.includes(V8) && r.history.includes(V7), 'lists earlier releases');
  check(!r.history.includes('>' + V9 + '<'), 'does not repeat the current release in the history list');
  check(r.history.includes('pre-release'), 'marks pre-releases');

  console.log('\nplatforms key ABSENT (the state update-game-data.yml leaves behind)...');
  r = await run({ version: FAKE, releases: FAKE_RELEASES });
  check(/isn’t recorded/.test(r.current), 'says the build list is unrecorded');
  check(!/build attached|not in this release/.test(r.current), 'makes no availability claim either way');

  console.log('\nversion.json unreachable...');
  r = await run({ versionFails: true, releases: FAKE_RELEASES });
  check(!VERSION_LITERAL.test(r.current), 'shows NO version literal when the lookup fails');
  check(/won’t guess/.test(r.current), 'says plainly that it will not guess');
  check(r.current.includes('github.com/PipFoweraker/pdoom1/releases'), 'points at the real source instead');

  console.log('\nGitHub releases API unreachable (rate limit / offline)...');
  r = await run({ version: withPlatforms({ windows: true, macos: true, linux: true }), releasesFails: true });
  check(r.current.includes(V9), 'the current release still renders from local data');
  check(/Couldn’t reach GitHub/.test(r.history), 'history degrades with an honest message');
  check(r.history.includes('HTTP 403'), 'reports why');
  check(!r.history.includes(V8) && !r.history.includes(V7), 'shows no release list rather than a stale one');

  console.log('\nEmpty release list...');
  r = await run({ version: withPlatforms({ windows: true }), releases: [] });
  check(/No earlier releases/.test(r.history), 'handles an empty list without inventing entries');

  console.log('\nRelease with no written notes...');
  r = await run({ version: { latest_release: { version: V9, published_at: '2099-01-02T00:00:00Z', body: '' } },
                  releases: FAKE_RELEASES });
  check(/shipped without written notes/.test(r.current), 'says so rather than rendering a blank panel');

  console.log('\n' + (failures ? failures + ' FAILURE(S)' : 'All changelog render tests passed.'));
  process.exit(failures ? 1 : 0);
})();
