// Destructive suite for the feedback widget's client outbox -- rows F7, F8, F16 and
// F17 of docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §6.
//
//   node scripts/test-feedback-outbox.js          (exit 0 = every row green)
//
// WHICH WORKFLOW SHOULD RUN THIS (agent A4 owns the wiring; this file must not)
// ----------------------------------------------------------------------------
//   .github/workflows/escaping.yml for the F17 half and
//   .github/workflows/content-honesty.yml for F7/F8/F16 -- or one blocking step in
//   content-honesty.yml running the whole file, which is simpler and equivalent.
//   Wire it in the SAME PR that lands public/assets/js/feedback.js, never before:
//   until then this suite is RED by design (Gate 2), and "a red test in the suite
//   is worse than no test" because it teaches everyone to skip the suite.
//
//   Whichever job takes it, it must ALSO be listed in escaping.yml's GUARDED set
//   when the widget lands -- escaping.yml enforces the CLASS ("every page that
//   renders fetched data") and a new page that renders visitor text is exactly
//   what that class is for.
//
// WHY F17 IS HERE AND NOT IN THE PYTHON SUITE
// -------------------------------------------
// F17 says "escaped at every sink; no attribute break". The server has no HTML
// sink: it answers JSON, and its record is JSONL read by a human. The ONE place a
// hostile payload becomes markup is the widget, which renders the visitor's own
// words back at them (their text, their contact, their credit, the page they were
// on) and, on replay, renders whatever is sitting in localStorage. So the sink is
// here. The Python suite covers the server half of the same class -- F11 asserts
// the error body is JSON rather than an HTML fatal, F15 asserts the store holds
// exactly the bytes that were submitted.
//
// The outbox is a SECOND-ORDER sink and that is the interesting part: localStorage
// is writable by anything on the origin and by the user, so replay() renders data
// that did not come from our server at all. Case (c) below poisons the outbox
// directly rather than going through a submission.
//
// WHAT THIS FILE IS
// -----------------
// Written by agent A3 from the contract ALONE, before any client existed. Nobody
// who wrote a line of the widget wrote a line of this file. If a row here disagrees
// with feedback.js, the contract is the tiebreaker.

const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// Subject resolution -- printed, never inferred silently.
// ---------------------------------------------------------------------------
const REAL = path.join(__dirname, '..', 'public', 'assets', 'js', 'feedback.js');
const STUB = path.join(__dirname, 'fixtures', 'stub_feedback_client.js');

function resolveSubject() {
  const explicit = process.env.PDOOM_FEEDBACK_CLIENT;
  if (explicit) return { file: path.resolve(explicit), label: 'explicit: ' + explicit };
  if (fs.existsSync(REAL)) return { file: REAL, label: 'REAL: public/assets/js/feedback.js' };
  return { file: STUB, label: 'STUB (scripts/fixtures/stub_feedback_client.js) -- '
           + 'public/assets/js/feedback.js does not exist yet' };
}

const SUBJECT = resolveSubject();
const MODULE = require(SUBJECT.file);
const SOURCE = fs.readFileSync(SUBJECT.file, 'utf8').replace(/\r\n/g, '\n');

if (!MODULE || typeof MODULE.createFeedbackClient !== 'function') {
  console.error(
    'FATAL: ' + SUBJECT.file + ' does not export createFeedbackClient.\n' +
    'The widget must expose the factory the contract\'s state machine is testable\n' +
    'through:\n\n' +
    '  createFeedbackClient({ storage, fetch, uuid, now, render, endpoint })\n' +
    '    -> { submit(input), replay(), outbox() }\n\n' +
    'Export it the way public/assets/js/escape.js does (module.exports when\n' +
    'module exists, window.* in a browser). Without an injectable storage and\n' +
    'fetch there is no way to make the network fail or the quota run out, and\n' +
    'rows F7/F8/F16 become untestable -- which is not the same as passing.'
  );
  process.exit(1);
}

const OUTBOX_KEY = MODULE.OUTBOX_KEY || 'pdoom_feedback_outbox';

// ---------------------------------------------------------------------------
// Row plumbing
// ---------------------------------------------------------------------------
const ROWS = [];

function row(id, title, fault, invariants, fn) {
  ROWS.push({ id, title, fault, invariants, fn, checks: [], notes: [] });
}

function mkctx(r) {
  return {
    // The invariant is not optional: an assertion nobody can trace back to a
    // contract line is an assertion nobody can act on.
    check(ok, inv, msg) { r.checks.push({ ok: !!ok, inv, msg: '[' + inv + '] ' + msg }); return !!ok; },
    note(t) { r.notes.push(t); }
  };
}

function verdict(r) {
  if (!r.checks.length) return 'UNINJECTABLE';
  return r.checks.every((c) => c.ok) ? 'PASS' : 'FAIL';
}

// ---------------------------------------------------------------------------
// Test doubles. Everything is in memory: no network, no browser, no secret.
// ---------------------------------------------------------------------------

function makeStorage(capBytes) {
  const map = new Map();
  return {
    _map: map,
    getItem(k) { return map.has(k) ? map.get(k) : null; },
    setItem(k, v) {
      const value = String(v);
      let total = value.length + k.length;
      for (const [kk, vv] of map) if (kk !== k) total += kk.length + vv.length;
      if (capBytes && total > capBytes) {
        // The real thing a browser throws. Name matters: code that switches on
        // e.name must see the same string it will see in production.
        const e = new Error('QuotaExceededError: localStorage is full');
        e.name = 'QuotaExceededError';
        e.code = 22;
        throw e;
      }
      map.set(k, value);
    },
    removeItem(k) { map.delete(k); },
    snapshot() { return JSON.stringify([...map.entries()]); }
  };
}

function response(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body))
  };
}

function offline() {
  // What window.fetch actually does with no network: it REJECTS. It does not
  // resolve with ok:false, so a client that only inspects resp.ok never runs.
  return Promise.reject(new TypeError('Failed to fetch'));
}

function makeFetch(storage, plan) {
  const calls = [];
  function fn(url, init) {
    let body = null;
    try { body = JSON.parse(init && init.body); } catch (e) { body = init && init.body; }
    calls.push({
      url,
      body,
      // Snapshot the outbox AT THE MOMENT of the call. §4.1 says the entry is
      // written BEFORE the first fetch; that is only observable from in here.
      outboxAtCall: storage.getItem(OUTBOX_KEY)
    });
    const step = plan[Math.min(calls.length - 1, plan.length - 1)];
    return typeof step === 'function' ? step(body, calls.length) : Promise.resolve(step);
  }
  return { fn, calls };
}

let seq = 0;
function uuid() {
  seq += 1;
  return '0000000' + seq + '-dead-4bee-8fff-' + String(seq).padStart(12, '0');
}

function makeRender() {
  const painted = [];
  return { fn: (html) => painted.push(String(html)), painted };
}

// A success affordance is a checkmark, a "thanks", a green tick, or a receipt
// presented as confirmation. §4.3: `retrying` MUST NOT render any of it.
//
// NOT in this pattern, deliberately: a bare /\bsent\b/. §4's own honest copy for
// the retrying state is "Not sent yet -- saved on this device, will retry.", so a
// pattern matching "sent" would fail a CORRECT implementation for saying exactly
// what the contract tells it to say. A guard that a compliant implementation
// cannot pass is not a guard, it is a rewrite request.
const SUCCESS_AFFORDANCE = /thank|✓|✔|success|saved as f-|we got (?:your|it)|\breceived\b/i;
const HONEST_PENDING = /not sent|saved on this device|will retry|sending|queued/i;

// ---------------------------------------------------------------------------
// F7 -- POST never leaves the client
// ---------------------------------------------------------------------------
row('F7', 'POST never leaves the client',
    'fetch rejects with TypeError("Failed to fetch"), as a real offline browser does',
    'INV-1b, §4.1, §4.3',
    async (t) => {
      const storage = makeStorage();
      const net = makeFetch(storage, [offline]);
      const render = makeRender();
      const client = MODULE.createFeedbackClient({
        storage, fetch: net.fn, uuid, now: () => 1755230000000, render: render.fn,
        endpoint: '/ingest.php'
      });

      const result = await client.submit({
        kind: 'bug', page: '/blog/post.html?p=x', text: 'the linux build 404s'
      });

      t.check(net.calls.length === 1, '§4.1',
        'the client must actually attempt the send; ' + net.calls.length + ' fetch call(s)');
      const rid = net.calls.length ? net.calls[0].body.rid : null;
      t.check(!!rid, '§1', 'the request must carry a client-generated rid; got ' + JSON.stringify(rid));

      const atCall = net.calls.length ? net.calls[0].outboxAtCall : null;
      t.check(!!atCall && atCall.indexOf(rid) !== -1, '§4.1',
        'the outbox entry must be in localStorage BEFORE the first fetch (§4.1), or a '
        + 'tab closed mid-request loses the message entirely. Outbox at call time was '
        + JSON.stringify(atCall));

      const stored = JSON.parse(storage.getItem(OUTBOX_KEY) || '[]');
      t.check(stored.length === 1, 'INV-1b',
        'exactly one entry must remain queued after a failed send; found ' + stored.length);
      t.check(stored.length === 1 && stored[0].rid === rid, 'INV-1b',
        'the queued entry must carry the SAME rid that was sent, or the retry cannot be '
        + 'joined to the server-side record');
      t.check(['queued', 'retrying', 'sending'].indexOf(result.state) !== -1, '§4',
        'submit() must report a pending state, not success; got ' + JSON.stringify(result.state));

      const painted = render.painted.join('\n');
      t.check(!SUCCESS_AFFORDANCE.test(painted), '§4.3',
        'a message that never left MUST NOT render a success affordance -- this is the '
        + 'exact failure bug-submit.php shipped. Rendered: ' + JSON.stringify(painted.slice(0, 160)));
      t.check(HONEST_PENDING.test(painted), '§4.3',
        'the visitor must be TOLD the message has not been sent and is held on this '
        + 'device. Rendered: ' + JSON.stringify(painted.slice(0, 160)));

      // §4.4: replay runs on the next load. Same client instance, fresh call.
      await client.replay();
      t.check(net.calls.length >= 2, '§4.4',
        'replay() must re-attempt the queued entry on the next load; total fetch calls '
        + net.calls.length);
      if (net.calls.length >= 2) {
        t.check(net.calls[1].body.rid === rid, '§1',
          'the replay must reuse the ORIGINAL rid -- that is what makes a retry '
          + 'idempotent; got ' + net.calls[1].body.rid + ' vs ' + rid);
      }
      const afterReplay = JSON.parse(storage.getItem(OUTBOX_KEY) || '[]');
      t.check(afterReplay.length === 1, 'INV-1b',
        'a replay that also failed must LEAVE the entry in the outbox; found '
        + afterReplay.length);
    });

// ---------------------------------------------------------------------------
// F8 -- response lost after the server wrote
// ---------------------------------------------------------------------------
row('F8', 'response lost after the server wrote',
    'attempt 1 rejects at the transport (the server did write); attempt 2 gets a 200',
    'INV-1b, §1',
    async (t) => {
      const storage = makeStorage();
      const render = makeRender();
      const net = makeFetch(storage, [
        offline,                                   // server wrote; the 200 never arrived
        (body) => Promise.resolve(response(200, {
          ok: true, rid: body.rid, receipt: 'F-ABC123', stored_at: 1755230001
        }))
      ]);
      const client = MODULE.createFeedbackClient({
        storage, fetch: net.fn, uuid, now: () => 1755230000000, render: render.fn
      });

      await client.submit({ kind: 'comment', page: '/', text: 'good post' });
      await client.replay();

      t.check(net.calls.length >= 2, '§4.4',
        'the lost response must produce a retry; ' + net.calls.length + ' fetch call(s)');
      const rids = [...new Set(net.calls.map((c) => c.body && c.body.rid))];
      t.check(rids.length === 1, '§1',
        'a retry MUST reuse the rid generated before the first attempt. ' + rids.length
        + ' distinct rids were sent (' + JSON.stringify(rids) + '), so the server stored '
        + 'the same message under two keys and read-time dedup has nothing to collapse '
        + '-- that is the double-count');
      if (net.calls.length >= 2) {
        const a1 = net.calls[0].body.attempt, a2 = net.calls[1].body.attempt;
        t.check(typeof a2 === 'number' && a2 > a1, '§2',
          'the advisory attempt counter must increment across retries; got ' + a1 + ' then ' + a2);
      }
      const after = JSON.parse(storage.getItem(OUTBOX_KEY) || '[]');
      t.check(after.length === 0, 'INV-1b',
        'a 200 carrying the MATCHING rid is the only thing that empties the outbox; '
        + after.length + ' entr(ies) remain');

      // Negative control for INV-1b. Without this, "removed on 200" and "removed on
      // 200 with a matching rid" are indistinguishable, and the whole point of the
      // rid is the match.
      const storage2 = makeStorage();
      const render2 = makeRender();
      const net2 = makeFetch(storage2, [
        offline,
        () => Promise.resolve(response(200, {
          ok: true, rid: 'a-completely-different-rid', receipt: 'F-ZZZZZZ', stored_at: 2
        }))
      ]);
      const client2 = MODULE.createFeedbackClient({
        storage: storage2, fetch: net2.fn, uuid, now: () => 1755230000000, render: render2.fn
      });
      await client2.submit({ kind: 'comment', page: '/', text: 'second case' });
      await client2.replay();
      const left = JSON.parse(storage2.getItem(OUTBOX_KEY) || '[]');
      t.check(left.length === 1, 'INV-1b',
        'a 200 whose rid does NOT match must leave the entry in the outbox -- otherwise '
        + 'any 200 from any request drops a message; ' + left.length + ' entr(ies) remain');
      t.check(!SUCCESS_AFFORDANCE.test(render2.painted.join('\n')), 'INV-1b',
        'a mismatched rid is not an acknowledgement and must not be shown as one');
    });

// ---------------------------------------------------------------------------
// F16 -- localStorage quota exhausted
// ---------------------------------------------------------------------------
row('F16', 'localStorage quota exhausted',
    'storage.setItem throws QuotaExceededError once the outbox is near its cap',
    '§4.5, INV-1',
    async (t) => {
      // Seed three unsent messages, then cap the storage just above their size so
      // the fourth cannot fit. The seeded entries are what the visitor already
      // wrote and has not got back -- the thing §4.5 forbids evicting.
      const seeded = [1, 2, 3].map((i) => ({
        rid: 'seeded-rid-' + i,
        receipt: 'F-SEED0' + i,
        payload: { rid: 'seeded-rid-' + i, kind: 'bug', page: '/p' + i, text: 'older unsent message ' + i },
        state: 'queued',
        attempt: 1
      }));
      const seededJson = JSON.stringify(seeded);
      const cap = seededJson.length + OUTBOX_KEY.length + 40;
      const storage = makeStorage(cap);
      storage.setItem(OUTBOX_KEY, seededJson);
      const before = storage.snapshot();

      const render = makeRender();
      const net = makeFetch(storage, [offline]);
      const client = MODULE.createFeedbackClient({
        storage, fetch: net.fn, uuid, now: () => 1755230000000, render: render.fn
      });

      let result = null, threw = null;
      try {
        result = await client.submit({
          kind: 'bug', page: '/blog/post.html?p=x',
          text: 'a long new message that cannot possibly fit in the remaining quota '.repeat(4)
        });
      } catch (e) {
        threw = e;
      }

      const refused = (result && (result.refused === true || result.state === 'refused'))
        || (threw && /quota|full|refus/i.test(String(threw.message || threw)));
      t.check(refused, '§4.5',
        'on quota exhaustion the NEW submission must be refused explicitly; got result='
        + JSON.stringify(result) + ' threw=' + (threw && threw.message));

      const message = String((result && (result.message || result.error)) || (threw && threw.message) || '')
        + '\n' + render.painted.join('\n');
      t.check(/github|e-?mail|issue/i.test(message), '§4.6',
        'the refusal must offer the GitHub/mail fallback, AFTER telling the truth about '
        + 'what happened; message was ' + JSON.stringify(message.slice(0, 200)));
      t.check(!SUCCESS_AFFORDANCE.test(render.painted.join('\n')), '§4.3',
        'a refused submission must render no success affordance; rendered '
        + JSON.stringify(render.painted.join('\n').slice(0, 160)));

      const after = JSON.parse(storage.getItem(OUTBOX_KEY) || '[]');
      const survivors = after.map((e) => e.rid).filter((rid) => /^seeded-rid-/.test(rid));
      t.check(survivors.length === 3, '§4.5',
        'NOTHING may be evicted to make room: expected all 3 older unsent messages to '
        + 'survive, ' + survivors.length + ' did. Outbox capacity is a loss channel, and '
        + 'evicting is choosing which visitor to lose');
      t.check(storage.snapshot() === before, '§4.5',
        'the outbox must be byte-identical after a refused submission -- a rewrite that '
        + 'happens to keep the same rids still rewrites entries nobody asked it to touch');
    });

// ---------------------------------------------------------------------------
// F17 -- hostile payload in every field
// ---------------------------------------------------------------------------

// Escaping does not delete the characters that spell an event handler; it makes
// them inert TEXT. So the predicate is STRUCTURAL, exactly as in
// scripts/test-board-escaping.js: strip the markup the widget is entitled to emit
// and require that no angle bracket or bare quote survives. A keyword blocklist
// would happily pass a payload that spelled its handler differently.
//
// The allowlist is deliberately strict -- a tag name, optionally one class, one
// href that is either https: or origin-relative and contains no quote. An
// injected attribute cannot match it. If a real widget needs another attribute,
// extend this CONSCIOUSLY and say why; loosening it to `[^>]*` would delete the
// test.
const ALLOWED = new RegExp(
  '<\\/?[a-z][a-z0-9]*' +
  '(?:\\s+class="[a-z0-9 _-]*")?' +
  '(?:\\s+href="(?:https:\\/\\/|\\/)[a-z0-9._~\\/?=&%#:+-]*")?' +
  '\\s*\\/?>', 'gi');

const inert = (html) => !/[<>"']/.test(String(html).replace(ALLOWED, ''));

const HOSTILE = [
  '<img src=x onerror=alert(1)>',
  '<script>alert(1)</script>',
  '"><svg onload=alert(1)>',
  "' onmouseover='alert(1)",
  '</p></div><div class="fb-ok">Thanks! Saved as F-000000',
  'javascript:alert(1)'
];

row('F17', 'hostile payload in every field',
    'every free-text field, the page, the server-echoed receipt, and a poisoned '
    + 'outbox are each loaded with markup',
    'escaping rule (CLAUDE.md)',
    async (t) => {
      t.check(!/(?:function|const|let|var)\s+(?:esc|escape[A-Za-z]*|sanitiz[eE][A-Za-z]*)\s*[=(]/.test(SOURCE),
        'escaping',
        'the widget must define NO escaper of its own -- there is exactly ONE, and it '
        + 'is public/assets/js/escape.js. Before 2026-08-01 this site had FIVE, three of '
        + 'which did not escape quotes while feeding attribute contexts');

      for (const h of HOSTILE) {
        // (a) the pending render -- the visitor's own words echoed back
        const storageA = makeStorage();
        const renderA = makeRender();
        const netA = makeFetch(storageA, [offline]);
        const clientA = MODULE.createFeedbackClient({
          storage: storageA, fetch: netA.fn, uuid, now: () => 1755230000000, render: renderA.fn
        });
        await clientA.submit({
          kind: h, page: h, text: h, contact: h, credit: h, value: h
        });
        t.check(inert(renderA.painted.join('\n')), 'escaping',
          'pending render inert with hostile fields: ' + h.slice(0, 30) + ' -- got '
          + JSON.stringify(renderA.painted.join('').slice(0, 180)));

        // (b) the acknowledged render, with the SERVER echoing hostile values.
        // The score API taught this repo that a field name promises nothing about
        // a field's contents, and the receipt is composed from client input.
        const storageB = makeStorage();
        const renderB = makeRender();
        const netB = makeFetch(storageB, [
          (body) => Promise.resolve(response(200, { ok: true, rid: body.rid, receipt: h, stored_at: h }))
        ]);
        const clientB = MODULE.createFeedbackClient({
          storage: storageB, fetch: netB.fn, uuid, now: () => 1755230000000, render: renderB.fn
        });
        await clientB.submit({ kind: 'bug', page: h, text: h, contact: h, credit: h });
        t.check(inert(renderB.painted.join('\n')), 'escaping',
          'acked render inert with a hostile server-echoed receipt: ' + h.slice(0, 30)
          + ' -- got ' + JSON.stringify(renderB.painted.join('').slice(0, 180)));

        // (c) the second-order sink: a poisoned outbox. localStorage is writable by
        // anything on the origin, so replay() renders data our server never saw.
        const storageC = makeStorage();
        storageC.setItem(OUTBOX_KEY, JSON.stringify([{
          rid: h, receipt: h, state: 'queued', attempt: 1,
          payload: { rid: h, kind: h, page: h, text: h, contact: h, credit: h }
        }]));
        const renderC = makeRender();
        const netC = makeFetch(storageC, [offline]);
        const clientC = MODULE.createFeedbackClient({
          storage: storageC, fetch: netC.fn, uuid, now: () => 1755230000000, render: renderC.fn
        });
        await clientC.replay();
        t.check(inert(renderC.painted.join('\n')), 'escaping',
          'replay render inert with a poisoned outbox: ' + h.slice(0, 30) + ' -- got '
          + JSON.stringify(renderC.painted.join('').slice(0, 180)));
      }

      // A URL cannot be made safe by escaping: javascript:alert(1) contains no HTML
      // metacharacter at all. escape.js exports isSafeUrl/safeUrl for exactly this.
      const storageD = makeStorage();
      const renderD = makeRender();
      const netD = makeFetch(storageD, [offline]);
      const clientD = MODULE.createFeedbackClient({
        storage: storageD, fetch: netD.fn, uuid, now: () => 1755230000000, render: renderD.fn
      });
      await clientD.submit({ kind: 'bug', page: 'javascript:alert(1)', text: 'hi' });
      t.check(!/javascript:/i.test(renderD.painted.join('\n')), 'escaping',
        'a javascript: URL in `page` must never reach an href -- escaping alone cannot '
        + 'make a URL safe, it needs safeUrl()/isSafeUrl() from escape.js');
    });

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------
(async function main() {
  console.log('='.repeat(78));
  console.log('FEEDBACK OUTBOX -- DESTRUCTIVE SUITE (contract §6, rows F7, F8, F16, F17)');
  console.log('subject under test: ' + SUBJECT.label);
  console.log('node: ' + process.version);
  console.log('='.repeat(78));

  for (const r of ROWS) {
    console.log('\n--- ' + r.id + '  ' + r.title);
    console.log('    inject: ' + r.fault);
    const t = mkctx(r);
    try {
      await r.fn(t);
    } catch (e) {
      // A row that explodes is a FAIL, never a skip.
      t.check(false, r.invariants, 'the row itself threw ' + e.name + ': ' + e.message);
    }
    for (const n of r.notes) console.log('    note: ' + n);
    for (const c of r.checks) console.log('    ' + (c.ok ? 'PASS ' : 'FAIL ') + c.msg);
    console.log('    => ' + verdict(r));
  }

  console.log('\n' + '='.repeat(78));
  for (const r of ROWS) console.log(r.id.padEnd(5) + verdict(r).padEnd(13) + r.title);
  const bad = ROWS.filter((r) => verdict(r) !== 'PASS');
  console.log('='.repeat(78));
  if (bad.length) {
    console.log(bad.length + ' of ' + ROWS.length + ' rows are not green: '
      + bad.map((r) => r.id).join(', '));
    console.log('If the subject above is the STUB, this is Gate 2 evidence and the exit '
      + 'code is supposed to be 1.');
    process.exit(1);
  }
  console.log('all ' + ROWS.length + ' rows green against ' + SUBJECT.label);
})();
