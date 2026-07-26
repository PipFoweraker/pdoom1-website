// Extracts resolveDownloads() from public/index.html and exercises it against a
// minimal DOM/fetch shim. Verifies the launch-day contract:
//   - a platform WITH an asset gets a direct download href AND a live label
//   - a platform WITHOUT one says "coming soon" instead of a live-looking button
//   - an unreachable API degrades NOTHING and, crucially, never UPGRADES an
//     unshipped platform: macOS/Linux ship disabled in the HTML, so a rate-limited
//     visitor keeps the honest "coming soon" rather than being shown a live button.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');

const m = src.match(/async function resolveDownloads\(\) \{[\s\S]*?\n\t\t\}/);
if (!m) { console.error('FAIL: could not extract resolveDownloads()'); process.exit(1); }

const BASE = 'https://github.com/PipFoweraker/pdoom1/releases/latest';

// Model the REAL initial DOM: Windows ships live (release-page baseline); macOS and
// Linux ship DISABLED ("coming soon", no href) and must only go live on a confirmed
// asset. `available` picks which starting state to build.
function makeEl(id, label, available) {
  const attrs = available
    ? { href: BASE, target: '_blank' }   // Windows: live baseline
    : {};                                 // macOS/Linux: disabled, no href
  return {
    id, dataset: { platformLabel: label },
    textContent: available ? ('Download for ' + label) : (label + ' — coming soon'),
    style: available ? {} : { opacity: '0.55', pointerEvents: 'none', cursor: 'default' },
    _attrs: attrs,
    hasAttribute(k) { return k in this._attrs; },
    removeAttribute(k) { delete this._attrs[k]; },
    setAttribute(k, v) { this._attrs[k] = v; },
    get href() { return this._attrs.href; },
    set href(v) { this._attrs.href = v; },
  };
}

async function run(name, assets, { ok = true } = {}) {
  const els = {
    'download-windows': makeEl('download-windows', 'Windows', true),
    'download-macos': makeEl('download-macos', 'macOS', false),
    'download-linux': makeEl('download-linux', 'Linux', false),
    'macos-gatekeeper-note': { id: 'note', style: { display: 'none' } },
  };
  const document = { getElementById: (id) => els[id] || null };
  const fetch = async () => ({ ok, json: async () => ({ assets }) });
  // The extracted source references bare `document` / `fetch` globals, so inject
  // them as parameters rather than trying to bind `this`.
  const fn = new Function('document', 'fetch', 'return ' + m[0])(document, fetch);
  await fn();
  return els;
}

(async () => {
  let failures = 0;
  const check = (cond, msg) => { console.log((cond ? '  PASS  ' : '  FAIL  ') + msg); if (!cond) failures++; };

  const A = (n) => ({ name: n, browser_download_url: 'https://gh/' + n });

  // Scenario 1: a future release where Windows + macOS ship, Linux does not.
  let els = await run('win+mac', [A('PDoom-v0.14.0-windows.zip'), A('PDoom-v0.14.0-macOS.zip')]);
  console.log('Scenario 1: Windows + macOS assets, no Linux');
  check(els['download-windows'].href === 'https://gh/PDoom-v0.14.0-windows.zip', 'Windows -> direct asset');
  check(els['download-macos'].href === 'https://gh/PDoom-v0.14.0-macOS.zip', 'macOS -> direct asset (upgraded from disabled)');
  check(els['download-macos'].textContent === 'Download for macOS', 'macOS -> label restored to live');
  check(!els['download-linux'].hasAttribute('href'), 'Linux -> no href (not a dead link)');
  check(/coming soon/i.test(els['download-linux'].textContent), 'Linux -> says "coming soon"');
  check(els['macos-gatekeeper-note'].style.display === 'block', 'Gatekeeper note shown (mac resolved)');

  // Scenario 2: Windows only -- TODAY's real shape (v0.13.0).
  els = await run('win only', [A('PDoom-v0.13.0-windows.zip')]);
  console.log('Scenario 2: Windows only (current v0.13.0 shape)');
  check(els['download-windows'].href === 'https://gh/PDoom-v0.13.0-windows.zip', 'Windows -> direct asset');
  check(!els['download-macos'].hasAttribute('href'), 'macOS -> stays "coming soon" (no href)');
  check(/coming soon/i.test(els['download-macos'].textContent), 'macOS -> says "coming soon"');
  check(els['macos-gatekeeper-note'].style.display === 'none', 'Gatekeeper note hidden (no mac build)');

  // Scenario 3: API unreachable -- change nothing. Windows keeps its live baseline;
  // macOS/Linux keep the honest disabled default (NEVER upgraded without an asset).
  els = await run('rate limited', [], { ok: false });
  console.log('Scenario 3: API rate-limited / offline');
  check(els['download-windows'].href === BASE, 'Windows keeps release-page baseline');
  check(!els['download-macos'].hasAttribute('href'), 'macOS stays disabled (NOT falsely upgraded)');
  check(/coming soon/i.test(els['download-macos'].textContent), 'macOS still says "coming soon"');
  check(!els['download-linux'].hasAttribute('href'), 'Linux stays disabled (NOT falsely upgraded)');

  // Scenario 4: assets exist but none match our naming guess -> keep baseline / defaults.
  els = await run('unrecognised', [A('SomethingWeird.bin'), A('checksums.txt')]);
  console.log('Scenario 4: release has assets, none recognised as builds');
  check(els['download-windows'].href === BASE, 'Windows keeps baseline');
  check(!els['download-macos'].hasAttribute('href'), 'macOS stays disabled');

  // Scenario 5: v0.13.1 naming -- bare PDoom.exe / PDoom.x86_64 / PDoom.app.zip.
  // The Windows asset lost its "windows" substring, so /win|\.exe$/ must catch it.
  els = await run('v0.13.1', [A('PDoom.exe'), A('PDoom.x86_64'), A('PDoom.app.zip')]);
  console.log('Scenario 5: v0.13.1 bare-name assets (PDoom.exe / .x86_64 / .app.zip)');
  check(els['download-windows'].href === 'https://gh/PDoom.exe', 'Windows -> PDoom.exe resolved (not missed)');
  check(els['download-macos'].href === 'https://gh/PDoom.app.zip', 'macOS -> PDoom.app.zip resolved');
  check(els['download-linux'].href === 'https://gh/PDoom.x86_64', 'Linux -> PDoom.x86_64 resolved');

  console.log(failures ? `\n${failures} FAILURE(S)` : '\nAll checks passed.');
  process.exit(failures ? 1 : 0);
})();
