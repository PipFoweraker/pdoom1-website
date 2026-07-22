// Tests that navigation.js is self-contained: it must ship its own CSS, not
// rely on the host page having .nav-links / .logo-container rules.
//
// Exists because it previously injected markup only. Pages with their own nav
// CSS (the homepage) looked fine; pages without (the blog) rendered the nav as
// an unstyled block stack filling the top-left of the fold. The failure was
// invisible to anyone testing on the homepage.
//
// Run: node scripts/test-navigation.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const NAV = path.join(__dirname, '..', 'public', 'assets', 'js', 'navigation.js');
const PUBLIC = path.join(__dirname, '..', 'public');
const src = fs.readFileSync(NAV, 'utf8');

let pass = 0, fail = 0;
const out = console.log.bind(console);
function ok(name, cond, detail) {
  if (cond) { pass++; out('  PASS ' + name); }
  else { fail++; out('  FAIL ' + name + (detail ? ' -> ' + detail : '')); }
}

// --- minimal DOM ----------------------------------------------------------
function makeDom() {
  const created = [];
  function mkEl(tag) {
    return {
      tagName: tag, id: '', textContent: '', innerHTML: '', attrs: {},
      children: [],
      setAttribute(k, v) { this.attrs[k] = v; },
      getAttribute(k) { return this.attrs[k]; },
      hasAttribute(k) { return k in this.attrs; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
      appendChild(c) { this.children.push(c); return c; },
      addEventListener() {},
    };
  }
  const head = mkEl('head');
  const header = mkEl('header');
  const doc = {
    readyState: 'complete',
    head,
    createElement: (t) => { const e = mkEl(t); created.push(e); return e; },
    getElementById: (id) =>
      head.children.find(c => c.id === id) || null,
    querySelector: (sel) => (sel === 'header' ? header : null),
    querySelectorAll: () => [],
    addEventListener() {},
  };
  return { doc, header, head, created };
}

out('self-contained styling');
{
  const { doc, header, head } = makeDom();
  const sandbox = { document: doc, location: { pathname: '/blog/' },
                    console: { warn() {}, log() {}, error() {} } };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox);

  const styleEl = head.children.find(c => c.tagName === 'style');
  ok('injects a <style> element', !!styleEl);
  ok('style element is idempotently identifiable',
     styleEl && styleEl.id === 'pdoom1-nav-styles');
  ok('marks the header so styles can scope to it',
     header.hasAttribute('data-nav-injected'));
  ok('injected nav markup landed', /nav-links/.test(header.innerHTML));

  const css = styleEl ? styleEl.textContent : '';
  for (const sel of ['.nav-links', '.logo-container', '.logo', '.dropdown-menu',
                     '.designer-credit']) {
    ok('ships CSS for ' + sel, css.includes(sel));
  }
  ok('all nav CSS is scoped to the injected header',
     css.split('\n').filter(l => /^\s*\./.test(l)).length === 0,
     'found an unscoped top-level class selector');
  ok('colours degrade on pages with no design tokens',
     (css.match(/var\(--[a-z-]+,\s*#/g) || []).length >= 6,
     'var() fallbacks missing');
  ok('has a mobile breakpoint', css.includes('@media'));
}

out('\nidempotence');
{
  const { doc, head } = makeDom();
  const sandbox = { document: doc, location: { pathname: '/blog/' },
                    console: { warn() {}, log() {}, error() {} } };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox);
  vm.runInContext(src, sandbox);   // second load, e.g. double script tag
  const styles = head.children.filter(c => c.tagName === 'style');
  ok('does not inject styles twice', styles.length === 1,
     'got ' + styles.length);
}

out('\npages adopting the injected nav');
{
  const users = [];
  (function walk(dir) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) { if (e.name !== 'events') walk(p); }
      else if (e.name.endsWith('.html')) {
        const html = fs.readFileSync(p, 'utf8');
        if (html.includes('assets/js/navigation.js')) {
          users.push(path.relative(PUBLIC, p).replace(/\\/g, '/'));
        }
      }
    }
  })(PUBLIC);

  ok('at least one page uses it', users.length > 0, users.length + ' pages');
  out('     ' + users.join(', '));
}

out(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
