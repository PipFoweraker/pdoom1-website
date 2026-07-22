// Behavioural test for public/assets/js/analytics.js in a fake browser.
const fs = require('fs');
const vm = require('vm');
const SRC = fs.readFileSync('public/assets/js/analytics.js', 'utf8');

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  PASS ' + name); }
  else { fail++; console.log('  FAIL ' + name + (extra ? ' -> ' + extra : '')); }
}

function makeEnv(opts) {
  const store = Object.assign({}, opts.store || {});
  const sandbox = {
    localStorage: {
      getItem: k => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: k => { delete store[k]; }
    },
    navigator: { doNotTrack: opts.dnt ? '1' : null },
    console: { log() {}, warn() {}, error() {} },
    document: { createElement: () => { throw new Error('SCRIPT INJECTED'); },
                head: { appendChild: () => { throw new Error('SCRIPT INJECTED'); } } },
    _store: store
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(SRC, sandbox);
  return sandbox;
}

console.log('1. No opt-out, no DNT: tracker flag must be absent');
let e = makeEnv({});
ok('plausible_ignore not set', e._store.plausible_ignore === undefined, JSON.stringify(e._store));
ok('hasOptedOut() false', e.pdoom1Analytics.hasOptedOut() === false);

console.log('2. DNT on: tracker flag must be set (claim "we honor DNT" becomes true)');
e = makeEnv({ dnt: true });
ok('plausible_ignore === "true"', e._store.plausible_ignore === 'true');
ok('hasOptedOut() true', e.pdoom1Analytics.hasOptedOut() === true);

console.log('3. Explicit optOut() sets the key the real tracker reads');
e = makeEnv({});
e.pdoom1Analytics.optOut();
ok('plausible_ignore === "true"', e._store.plausible_ignore === 'true');
ok('explicit key recorded', e._store.pdoom1_analytics_optout === 'true');

console.log('4. optIn() clears both');
e.pdoom1Analytics.optIn();
ok('plausible_ignore cleared', e._store.plausible_ignore === undefined);
ok('explicit key cleared', e._store.pdoom1_analytics_optout === undefined);

console.log('5. DNT turned OFF later must un-stick a DNT-derived flag');
e = makeEnv({ store: { plausible_ignore: 'true' }, dnt: false });
ok('flag released', e._store.plausible_ignore === undefined);

console.log('6. ...but an EXPLICIT opt-out must survive DNT being off');
e = makeEnv({ store: { plausible_ignore: 'true', pdoom1_analytics_optout: 'true' }, dnt: false });
ok('flag retained', e._store.plausible_ignore === 'true');

console.log('7. No script injection ever (the regression this file existed to cause)');
// Strip comments -- the file deliberately DOCUMENTS the old plausible.io bug,
// so a raw substring match would flag the explanation as the offence.
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
ok('no cloud plausible.io reference in code', !/plausible\.io/.test(CODE),
   (CODE.match(/.*plausible\.io.*/) || [''])[0].trim());
ok('no createElement in code', !/createElement/.test(CODE));
ok('no appendChild in code', !/appendChild/.test(CODE));
ok('bug still documented in comments', /plausible\.io/.test(SRC));

console.log('8. trackEvent routes to window.plausible and respects opt-out');
e = makeEnv({});
let got = null;
e.plausible = (n, o) => { got = [n, o]; };
e.pdoom1Analytics.trackEvent('Download', { platform: 'Windows' });
ok('event forwarded', got && got[0] === 'Download' && got[1].props.platform === 'Windows');
e.pdoom1Analytics.optOut();
got = null;
e.pdoom1Analytics.trackEvent('Download', {});
ok('suppressed after opt-out', got === null);

console.log('9. Storage disabled (private mode) must not throw');
const sb = { navigator: {}, console: { log() {} },
  localStorage: { getItem() { throw new Error('denied'); },
                  setItem() { throw new Error('denied'); },
                  removeItem() { throw new Error('denied'); } } };
sb.window = sb;
vm.createContext(sb);
let threw = false;
try { vm.runInContext(SRC, sb); sb.pdoom1Analytics.hasOptedOut(); sb.pdoom1Analytics.optOut(); }
catch (err) { threw = true; console.log('     threw: ' + err.message); }
ok('survives storage denial', !threw);

console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail === 0 ? 0 : 1);
