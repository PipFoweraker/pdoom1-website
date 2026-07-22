// Tests the shared-secret gate on the syndication endpoints.
//
// These functions are deployed and publicly reachable, and they post to real
// social accounts. Before the gate, any unauthenticated POST would have been
// honoured the moment a credential was configured. This asserts the gate is
// present on every one of them and behaves correctly, including failing CLOSED
// when unconfigured.
//
// Run: node scripts/test-syndication-auth.js

const fs = require('fs');
const path = require('path');

const FUNCS = path.join(__dirname, '..', 'netlify', 'functions');
let pass = 0, fail = 0;

// Report through the REAL console, captured before any silencing below.
// Routing this through `console` meant results vanished while the module's own
// logging was muted -- the run printed 14 lines and claimed 19 passes.
const out = console.log.bind(console);

function ok(name, cond, detail) {
  if (cond) { pass++; out('  PASS ' + name); }
  else { fail++; out('  FAIL ' + name + (detail ? ' -> ' + detail : '')); }
}

function freshAuth(env) {
  delete require.cache[require.resolve(path.join(FUNCS, '_auth.js'))];
  const saved = process.env.SYNDICATION_TOKEN;
  if (env === undefined) delete process.env.SYNDICATION_TOKEN;
  else process.env.SYNDICATION_TOKEN = env;
  const mod = require(path.join(FUNCS, '_auth.js'));
  return { mod, restore: () => { if (saved === undefined) delete process.env.SYNDICATION_TOKEN; else process.env.SYNDICATION_TOKEN = saved; } };
}

const quiet = { error: () => {}, warn: () => {}, log: () => {} };
const realConsole = console;

out('gate behaviour');
{
  // Unconfigured must REFUSE, not allow.
  const { mod, restore } = freshAuth(undefined);
  global.console = quiet;
  const r = mod.requireAuth({ headers: { 'x-syndication-token': 'anything' } });
  global.console = realConsole;
  ok('fails CLOSED when SYNDICATION_TOKEN unset', r && r.statusCode === 503,
     r ? 'got ' + r.statusCode : 'got null (WOULD HAVE ALLOWED)');
  restore();
}
{
  const { mod, restore } = freshAuth('correct-horse-battery-staple');
  global.console = quiet;

  const noHeader = mod.requireAuth({ headers: {} });
  ok('rejects a request with no token', noHeader && noHeader.statusCode === 401);

  const wrong = mod.requireAuth({ headers: { 'x-syndication-token': 'wrong' } });
  ok('rejects a wrong token', wrong && wrong.statusCode === 401);

  const prefix = mod.requireAuth({ headers: { 'x-syndication-token': 'correct-horse' } });
  ok('rejects a correct PREFIX of the token', prefix && prefix.statusCode === 401);

  const right = mod.requireAuth({
    headers: { 'x-syndication-token': 'correct-horse-battery-staple' } });
  ok('accepts the correct token', right === null,
     right ? 'got ' + right.statusCode : '');

  const upper = mod.requireAuth({
    headers: { 'X-Syndication-Token': 'correct-horse-battery-staple' } });
  ok('accepts a differently-cased header name', upper === null);

  global.console = realConsole;
  restore();
}

console.log('\nevery syndication function is gated');
const files = fs.readdirSync(FUNCS).filter(f => /^syndicate-.*\.js$/.test(f));
ok('found syndication functions', files.length >= 4, 'found ' + files.length);

for (const f of files) {
  const src = fs.readFileSync(path.join(FUNCS, f), 'utf8');
  const requires = src.includes("require('./_auth')");
  const calls = /const\s+denied\s*=\s*requireAuth\(event\)/.test(src) &&
                /if\s*\(denied\)\s*return\s+denied/.test(src);

  // The gate must run BEFORE the credential lookup, or a misconfigured caller
  // could still reach the account.
  const authAt = src.indexOf('requireAuth(event)');
  const credAt = src.search(/process\.env\.(BLUESKY|TWITTER|LINKEDIN|DISCORD)/);
  const ordered = authAt !== -1 && (credAt === -1 || authAt < credAt);

  ok(`${f}: requires _auth`, requires);
  ok(`${f}: calls and returns the gate`, calls);
  ok(`${f}: gate runs before credentials are read`, ordered);
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
