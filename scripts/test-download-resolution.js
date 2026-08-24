// Extracts resolveDownloads() from public/index.html and exercises it against a
// minimal DOM/fetch shim. Verifies the launch-day contract:
//   - a platform WITH an asset gets a direct download href
//   - a platform WITHOUT one degrades to "coming soon" instead of a dead link
//   - an unreachable / unrecognised API degrades NOTHING -- every button keeps the
//     release-page baseline rather than being falsely disabled.
//   - the first-run note (unsigned binaries / extract the zip / SmartScreen / chmod)
//     is STATIC: visible in the shipped HTML and never touched by this function.
//     It used to be `display: none` until resolveDownloads() unhid it, so a GitHub
//     rate-limit left working download buttons and no warning at all. Since the
//     buttons resolve to a direct .zip, the release page carrying this guidance is
//     never visited -- pdoom1.com is the only place a visitor can read it.
//
// NOTE, CORRECTED 2026-08-24. This used to read: "all three buttons ship LIVE in
// the HTML (href = release page, 'Download for <OS>') ... every button starts live
// and only degrades if a future release drops a platform."
//
// A future release did drop a platform -- v0.14.3 shipped with no macOS asset -- and
// that static label was then a false availability claim on exactly the paths this
// function deliberately does NOT take: JS off, and the documented rate-limit no-op.
// check-platform-claims.py flagged it. The buttons now ship with an "<OS> -- checking
// latest release" placeholder that claims nothing, and TWO mechanisms write the real
// label: renderPlatformClaims() from same-origin version.json (covered by
// scripts/test-platform-render.js), then this function refining the available ones to
// direct asset URLs. The href baseline is unchanged -- still the release page, still
// never 404s, still untouched on a rate-limit. makeEl() below mirrors the new shipped
// shape and Scenario 6 asserts that it still does, so this comment cannot rot the way
// the sentence above it did.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');

const m = src.match(/async function resolveDownloads\(\) \{[\s\S]*?\n\t\t\}/);
if (!m) { console.error('FAIL: could not extract resolveDownloads()'); process.exit(1); }

const BASE = 'https://github.com/PipFoweraker/pdoom1/releases/latest';

// Model the REAL initial DOM: every platform points at the release page (never a
// 404) under a placeholder label that claims nothing. resolveDownloads() upgrades
// each to its direct asset URL, or degrades it to "coming soon" only if the release
// actually dropped that platform's build. Scenario 6 pins this string against the
// shipped HTML.
const PLACEHOLDER_LABEL = (label) => label + ' — checking latest release';

function makeEl(id, label) {
  return {
    id, dataset: { platformLabel: label },
    textContent: PLACEHOLDER_LABEL(label),
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
    // Present in the DOM so a regression that re-adds display juggling is caught
    // by the "untouched" assertions below rather than by a null-guard silently
    // skipping. `style` starts empty, exactly as static markup with no inline
    // display would behave.
    'first-run-note': { id: 'first-run-note', style: {} },
    'macos-gatekeeper-note': { id: 'macos-gatekeeper-note', style: {} },
  };
  const document = { getElementById: (id) => els[id] || null };
  const fetch = async () => ({ ok, json: async () => ({ assets }) });
  // The extracted source references bare `document` / `fetch` globals, so inject
  // them as parameters rather than trying to bind `this`.
  const fn = new Function('document', 'fetch', 'return ' + m[0])(document, fetch);
  await fn();
  return els;
}

// resolveDownloads() must not set `display` on either note id -- the current one or
// the retired one, so re-adding the old id does not quietly restore the old bug.
function noteUntouched(els) {
  return ['first-run-note', 'macos-gatekeeper-note']
    .every((id) => els[id].style.display === undefined);
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
  check(noteUntouched(els), 'First-run note untouched (mac resolved)');

  // Scenario 2: a future release that dropped macOS + Linux, Windows only.
  els = await run('win only', [A('PDoom-Windows-v0.13.1.zip')]);
  console.log('Scenario 2: Windows only -> macOS/Linux degrade to "coming soon"');
  check(els['download-windows'].href === 'https://gh/PDoom-Windows-v0.13.1.zip', 'Windows -> direct asset');
  check(!els['download-macos'].hasAttribute('href'), 'macOS -> no href (not a dead link)');
  check(/coming soon/i.test(els['download-macos'].textContent), 'macOS -> says "coming soon"');
  check(!els['download-linux'].hasAttribute('href'), 'Linux -> no href (not a dead link)');
  check(/coming soon/i.test(els['download-linux'].textContent), 'Linux -> says "coming soon"');
  // The note must survive a DROPPED macOS build too: it is a three-OS note now,
  // and hiding it would take the Windows and Linux guidance down with it.
  check(noteUntouched(els), 'First-run note untouched (no mac build)');

  // Scenario 3: API unreachable -- change nothing. Every button keeps its live
  // release-page baseline (we cannot know what shipped, so never degrade).
  els = await run('rate limited', [], { ok: false });
  console.log('Scenario 3: API rate-limited / offline -> all keep release-page baseline');
  check(els['download-windows'].href === BASE, 'Windows keeps release-page baseline');
  check(els['download-macos'].href === BASE, 'macOS keeps release-page baseline');
  check(els['download-linux'].href === BASE, 'Linux keeps release-page baseline');
  // ...and it must not INVENT a label either. On this path renderPlatformClaims()
  // has already written the truth from version.json; resolveDownloads() overwriting
  // it, or a static "Download for macOS" standing here, is the bug being closed.
  check(els['download-macos'].textContent === PLACEHOLDER_LABEL('macOS'),
    'macOS label untouched on rate-limit (whatever version.json wrote survives)');

  // Scenario 4: assets exist but none match our naming guess -> keep baseline.
  els = await run('unrecognised', [A('SomethingWeird.bin'), A('checksums.txt')]);
  console.log('Scenario 4: release has assets, none recognised as builds -> keep baseline');
  check(els['download-windows'].href === BASE, 'Windows keeps baseline');
  check(els['download-macos'].href === BASE, 'macOS keeps baseline');
  check(els['download-linux'].href === BASE, 'Linux keeps baseline');

  // Scenario 5: the SHIPPED markup, not the shim. The note has to be readable with
  // JS off and on a rate-limited API, so it is asserted against index.html directly.
  console.log('Scenario 5: first-run note is static, visible, and covers all three OSes');
  const noteTag = src.match(/<div id="first-run-note"[^>]*>/);
  check(!!noteTag, 'note element exists in index.html');
  if (noteTag) {
    check(!/display\s*:\s*none/i.test(noteTag[0]), 'note does not ship hidden');
  }
  const noteBody = src.match(/<div id="first-run-note"[\s\S]*?\n\t\t\t<\/div>/);
  check(!!noteBody, 'note block is parseable');
  if (noteBody) {
    const body = noteBody[0];
    // One assertion per fact the release notes say a first-run visitor needs. The
    // buttons download a .zip directly, so if a fact is not here it is nowhere.
    for (const [label, rx] of [
      ['says the builds are unsigned', /unsigned/i],
      ['tells you to extract the zip first', /extract the whole zip/i],
      ['names the Windows SmartScreen dialog', /Windows protected your PC/i],
      ['gives the SmartScreen escape', /More info[\s\S]{0,120}Run anyway/i],
      ['tells Sequoia users to double-click FIRST', /double-click the app once[\s\S]{0,200}Privacy/i],
      ['names Open Anyway', /Open&nbsp;Anyway/],
      ['gives the Linux chmod', /chmod \+x/],
    ]) check(rx.test(body), 'note ' + label);
  }
  check(!/getElementById\(['"]macos-gatekeeper-note['"]\)/.test(src),
    'no JS still reaches for the retired macos-gatekeeper-note id');

  // Scenario 6: the shim above is a claim about the shipped HTML. Check it. The
  // header comment of this file asserted the old shape for weeks after it stopped
  // being true; an assertion cannot do that.
  console.log('Scenario 6: the modelled initial DOM matches the shipped markup');
  for (const [id, label] of [['download-windows', 'Windows'],
                             ['download-macos', 'macOS'],
                             ['download-linux', 'Linux']]) {
    const tag = src.match(new RegExp('<a id="' + id + '"[^>]*>\\s*([^<]*?)\\s*\\n'));
    check(!!tag, id + ' anchor found in index.html');
    if (tag) {
      // The shipped HTML entity-encodes the dash; the DOM the browser builds does
      // not, and neither does the shim. Compare on the decoded form.
      const shipped = tag[1].replace(/&mdash;/g, '—');
      check(shipped === PLACEHOLDER_LABEL(label),
        id + ' ships the placeholder this test models (' + shipped + ')');
      check(!/^Download for/.test(shipped),
        id + ' ships no static "Download for <OS>" availability claim');
    }
    check(new RegExp('<a id="' + id + '"[^>]*href="' + BASE.replace(/\//g, '\\/') + '"').test(src),
      id + ' still ships the release-page href baseline');
  }

  console.log(failures ? `\n${failures} FAILURE(S)` : '\nAll checks passed.');
  process.exit(failures ? 1 : 0);
})();
