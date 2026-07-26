// Extracts resolveDownloads() from public/index.html and exercises it against a
// minimal DOM/fetch shim. Verifies the launch-day contract:
//   - a platform WITH an asset gets a direct download href
//   - a platform WITHOUT one degrades to "coming soon" instead of a dead link
//   - an unreachable / unrecognised API degrades NOTHING -- every button keeps the
//     release-page baseline rather than being falsely disabled.
//
// NOTE: all three buttons ship LIVE in the HTML (href = release page, "Download
// for <OS>"). That is copy-pass's launch shape: v0.13.1 ships Windows, macOS AND
// Linux builds, so every button starts live and only degrades if a future release
// drops a platform. This mirrors makeEl() below.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');

const m = src.match(/async function resolveDownloads\(\) \{[\s\S]*?\n\t\t\}/);
if (!m) { console.error('FAIL: could not extract resolveDownloads()'); process.exit(1); }

const BASE = 'https://github.com/PipFoweraker/pdoom1/releases/latest';

// Model the REAL initial DOM: every platform ships LIVE, pointing at the release
// page with a "Download for <OS>" label. resolveDownloads() upgrades each to its
// direct asset URL, or degrades it to "coming soon" only if the release actually
// dropped that platform's build.
function makeEl(id, label) {
  return {
    id, dataset: { platformLabel: label },
    textContent: 'Download for ' + label,
    style: {},
    _attrs: { href: BASE, target: '_blank' },
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

  // Scenario 1: TODAY's real shape (v0.13.1) -- all three builds ship.
  let els = await run('all three', [
    A('PDoom-Windows-v0.13.1.zip'),
    A('PDoom-macOS-v0.13.1.zip'),
    A('PDoom-Linux-v0.13.1.zip'),
  ]);
  console.log('Scenario 1: Windows + macOS + Linux assets (current v0.13.1 shape)');
  check(els['download-windows'].href === 'https://gh/PDoom-Windows-v0.13.1.zip', 'Windows -> direct asset');
  check(els['download-macos'].href === 'https://gh/PDoom-macOS-v0.13.1.zip', 'macOS -> direct asset');
  check(els['download-linux'].href === 'https://gh/PDoom-Linux-v0.13.1.zip', 'Linux -> direct asset');
  check(els['download-macos'].textContent === 'Download for macOS', 'macOS -> live label kept');
  check(els['macos-gatekeeper-note'].style.display === 'block', 'Gatekeeper note shown (mac resolved)');

  // Scenario 2: a future release that dropped macOS + Linux, Windows only.
  els = await run('win only', [A('PDoom-Windows-v0.13.1.zip')]);
  console.log('Scenario 2: Windows only -> macOS/Linux degrade to "coming soon"');
  check(els['download-windows'].href === 'https://gh/PDoom-Windows-v0.13.1.zip', 'Windows -> direct asset');
  check(!els['download-macos'].hasAttribute('href'), 'macOS -> no href (not a dead link)');
  check(/coming soon/i.test(els['download-macos'].textContent), 'macOS -> says "coming soon"');
  check(!els['download-linux'].hasAttribute('href'), 'Linux -> no href (not a dead link)');
  check(/coming soon/i.test(els['download-linux'].textContent), 'Linux -> says "coming soon"');
  check(els['macos-gatekeeper-note'].style.display === 'none', 'Gatekeeper note hidden (no mac build)');

  // Scenario 3: API unreachable -- change nothing. Every button keeps its live
  // release-page baseline (we cannot know what shipped, so never degrade).
  els = await run('rate limited', [], { ok: false });
  console.log('Scenario 3: API rate-limited / offline -> all keep release-page baseline');
  check(els['download-windows'].href === BASE, 'Windows keeps release-page baseline');
  check(els['download-macos'].href === BASE, 'macOS keeps release-page baseline');
  check(els['download-linux'].href === BASE, 'Linux keeps release-page baseline');

  // Scenario 4: assets exist but none match our naming guess -> keep baseline.
  els = await run('unrecognised', [A('SomethingWeird.bin'), A('checksums.txt')]);
  console.log('Scenario 4: release has assets, none recognised as builds -> keep baseline');
  check(els['download-windows'].href === BASE, 'Windows keeps baseline');
  check(els['download-macos'].href === BASE, 'macOS keeps baseline');
  check(els['download-linux'].href === BASE, 'Linux keeps baseline');

  console.log(failures ? `\n${failures} FAILURE(S)` : '\nAll checks passed.');
  process.exit(failures ? 1 : 0);
})();
