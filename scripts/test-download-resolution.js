// Extracts resolveDownloads() from public/index.html and exercises it against a
// minimal DOM/fetch shim. Verifies the launch-day contract:
//   - a platform WITH an asset gets a direct download href
//   - a platform WITHOUT one says "coming soon" instead of silently pointing at a
//     release page that has no build for it
//   - an unreachable API degrades NOTHING (we cannot know what shipped)
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');

const m = src.match(/async function resolveDownloads\(\) \{[\s\S]*?\n\t\t\}/);
if (!m) { console.error('FAIL: could not extract resolveDownloads()'); process.exit(1); }

const BASE = 'https://github.com/PipFoweraker/pdoom1/releases/latest';

function makeEl(id, label) {
  return {
    id, dataset: { platformLabel: label }, textContent: 'Download for ' + label,
    style: {}, _attrs: { href: BASE, target: '_blank' },
    hasAttribute(k) { return k in this._attrs; },
    removeAttribute(k) { delete this._attrs[k]; },
    setAttribute(k, v) { this._attrs[k] = v; },
    get href() { return this._attrs.href; },
    set href(v) { this._attrs.href = v; },
  };
}

async function run(name, assets, { ok = true } = {}) {
  const els = {
    'download-windows': makeEl('download-windows', 'Windows'),
    'download-macos': makeEl('download-macos', 'macOS'),
    'download-linux': makeEl('download-linux', 'Linux'),
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

  // Scenario 1: today's intended shape -- Windows + macOS ship, Linux does not.

  let els = await run('win+mac', [A('PDoom-v0.13.0-windows.zip'), A('PDoom-v0.13.0-macOS.zip')]);
  console.log('Scenario 1: Windows + macOS assets, no Linux');
  check(els['download-windows'].href === 'https://gh/PDoom-v0.13.0-windows.zip', 'Windows -> direct asset');
  check(els['download-macos'].href === 'https://gh/PDoom-v0.13.0-macOS.zip', 'macOS -> direct asset');
  check(!els['download-linux'].hasAttribute('href'), 'Linux -> href removed (not a dead link)');
  check(/coming soon/i.test(els['download-linux'].textContent), 'Linux -> says "coming soon"');
  check(els['macos-gatekeeper-note'].style.display === 'block', 'Gatekeeper note shown (mac resolved)');

  // Scenario 2: Windows only -- the CURRENT v0.12.0 shape. Mac must degrade too.
  els = await run('win only', [A('PDoom-v0.12.0-windows.zip')]);
  console.log('Scenario 2: Windows only (current v0.12.0 shape)');
  check(els['download-windows'].href === 'https://gh/PDoom-v0.12.0-windows.zip', 'Windows -> direct asset');
  check(!els['download-macos'].hasAttribute('href'), 'macOS -> degraded');
  check(els['macos-gatekeeper-note'].style.display === 'none', 'Gatekeeper note hidden (no mac build)');

  // Scenario 3: API unreachable -- we know nothing, so change nothing.
  els = await run('rate limited', [], { ok: false });
  console.log('Scenario 3: API rate-limited / offline');
  check(els['download-windows'].href === BASE, 'Windows keeps release-page baseline');
  check(els['download-linux'].href === BASE, 'Linux keeps baseline (NOT falsely "coming soon")');

  // Scenario 4: assets exist but none match our naming guess -> keep baseline.
  els = await run('unrecognised', [A('SomethingWeird.bin'), A('checksums.txt')]);
  console.log('Scenario 4: release has assets, none recognised as builds');
  check(els['download-windows'].href === BASE, 'Windows keeps baseline');
  check(els['download-linux'].href === BASE, 'Linux keeps baseline');

  console.log(failures ? `\n${failures} FAILURE(S)` : '\nAll checks passed.');
  process.exit(failures ? 1 : 0);
})();
