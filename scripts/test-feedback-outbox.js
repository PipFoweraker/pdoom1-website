// Destructive suite for the feedback widget's client outbox -- rows F7, F8, F16 and
// F17 of docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §6, plus C1 and C2.
//
//   node scripts/test-feedback-outbox.js          (exit 0 = every row green)
//   PDOOM_FEEDBACK_CLIENT=<path> node scripts/test-feedback-outbox.js
//                                                 (point it at another build)
//
// C1 AND C2 ARE NOT CONTRACT ROWS. They are two defects found by review on
// 2026-08-17 and fixed the same day; each is kept as a row because the fix asserts
// a safety property, and a claimed safety property needs a test that FORCES the
// failing condition rather than watching the fixed path pass.
//
//   C1  escape.js does not load       -> the visitor must still be told something
//                                        TRUE, in constants, rather than shown a
//                                        blank region after a durable write
//   C2  the endpoint is unreachable   -> §4.6's prefilled GitHub fallback must be
//                                        rendered on `retrying`, the exact state
//                                        §4.6 was written for
//
// Both were observed RED against the pre-fix client (git show
// feedback/intake-contract:public/assets/js/feedback.js) with F7/F8/F16/F17 still
// green -- which is what says they are aimed at these two defects and nothing else.
// PDOOM_FEEDBACK_CLIENT is how to reproduce that.
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
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

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

// ===========================================================================
// C1 -- escape.js fails to load
// ===========================================================================
// Not a contract row: a defect found by review on 2026-08-17 and fixed in the
// same PR as C2. Recorded here as a row because the fix asserts a SAFETY property
// ("the visitor is always told something true"), and this repo's rule is that a
// claimed safety property needs a test that FORCES the failing condition and
// observes the outcome.
//
// The defect: paint() read `if (!E) { return; }`. Failing closed on the ESCAPING
// question is right and stays. Failing closed on the whole message is not -- the
// durable write had already happened, so the visitor saw an empty region, which is
// indistinguishable from a button that did nothing. That invites a resubmit and
// invites the conclusion that the message was dropped. Under the binding directive
// a message that WAS saved but LOOKS lost is the same harm as a lost one.
//
// HOW THE FAULT IS INJECTED, and why it needs a child process
// -----------------------------------------------------------
// getEscapers() looks at window/globalThis first and only then at
// require('./escape.js'). escape.js:152-159 assigns its five names onto globalThis
// whenever there is no window -- which is every Node run -- so the moment this file
// requires the real widget, `globalThis.escapeHTML` is set for the life of the
// process and no in-process trick can un-set it honestly. So: copy the REAL widget
// bytes into a temp dir beside a STUB escape.js that exports nothing, and drive it
// from a fresh `node` with a clean global. The subject is the real file, unedited;
// only its neighbour is broken. Nothing committed is touched.

const C1_HOSTILE_TEXT = '<img src=x onerror=alert(1)> "quoted" \' apostrophe';
const C1_PAGE = '/blog/post.html?p=<script>';
const C1_CONTACT = 'a"b@example.com';
const C1_CREDIT = "</p><div class='fb-ok'>Thanks";

// The driver runs INSIDE the temp dir. It reports what reached render(), plus
// whether an escaper was reachable at all -- because a run in which escape.js was
// somehow still present would be green for the wrong reason, and "the fault did not
// inject" must never read as "the property holds".
const C1_DRIVER = `
'use strict';
const FB = require('./feedback.js');
let stubEscaper = null;
try { stubEscaper = require('./escape.js'); } catch (e) { stubEscaper = 'threw'; }
const escaperPresent =
  (typeof globalThis.escapeHTML === 'function') ||
  (typeof window !== 'undefined' && window && typeof window.escapeHTML === 'function') ||
  !!(stubEscaper && typeof stubEscaper.escapeHTML === 'function');

function mkStore() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => { m.set(k, String(v)); },
    removeItem: (k) => { m.delete(k); }
  };
}
const INPUT = ${JSON.stringify({
  kind: 'bug', page: C1_PAGE, text: C1_HOSTILE_TEXT,
  contact: C1_CONTACT, credit: C1_CREDIT
})};

function client(painted, fetchImpl) {
  return FB.createFeedbackClient({
    storage: mkStore(),
    fetch: fetchImpl,
    uuid: () => 'ffffffff-dead-4bee-8fff-000000000001',
    now: () => 1755230000000,
    render: (h) => { painted.push(String(h)); }
  });
}

(async function () {
  const offlinePainted = [];
  const offlineResult = await client(offlinePainted,
    () => Promise.reject(new TypeError('Failed to fetch'))).submit(INPUT);

  const ackedPainted = [];
  await client(ackedPainted, (u, i) => {
    const body = JSON.parse(i.body);
    return Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({ ok: true, rid: body.rid, receipt: 'F-ZZZZZZ' })
    });
  }).submit(INPUT);

  process.stdout.write(JSON.stringify({
    escaperPresent: escaperPresent,
    offlinePainted: offlinePainted,
    offlineState: offlineResult && offlineResult.state,
    ackedPainted: ackedPainted
  }));
})().catch((e) => {
  process.stdout.write(JSON.stringify({ driverError: e.name + ': ' + e.message }));
});
`;

function runWithoutEscaper() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pdoom-fb-noescape-'));
  try {
    fs.copyFileSync(SUBJECT.file, path.join(dir, 'feedback.js'));
    // The stub: present, requireable, and useless. This is what a CDN 404, a CSP
    // block or a typo'd <script src> looks like from inside the widget.
    fs.writeFileSync(path.join(dir, 'escape.js'),
      '// deliberately empty: escape.js did not load\nmodule.exports = {};\n', 'utf8');
    fs.writeFileSync(path.join(dir, 'drive.js'), C1_DRIVER, 'utf8');
    const p = spawnSync(process.execPath, [path.join(dir, 'drive.js')],
      { encoding: 'utf8', timeout: 30000 });
    if (p.status !== 0) {
      return { spawnFailed: 'exit ' + p.status + ' :: ' + String(p.stderr).slice(0, 400) };
    }
    try { return JSON.parse(p.stdout); }
    catch (e) { return { spawnFailed: 'unparseable stdout: ' + String(p.stdout).slice(0, 400) }; }
  } finally {
    try { fs.rmSync(dir, { recursive: true, force: true }); } catch (e) { /* temp dir */ }
  }
}

row('C1', 'escape.js fails to load',
    'the widget is run beside a STUB escape.js that exports nothing, in a fresh '
    + 'node process so no earlier require can have leaked the real escaper onto globalThis',
    'INV-1, §4.3, §4.6, binding directive (never lose a message)',
    async (t) => {
      const out = runWithoutEscaper();
      if (out.spawnFailed || out.driverError) {
        t.check(false, 'INV-1',
          'the fault could not be injected, which is NOT the same as the property '
          + 'holding: ' + (out.spawnFailed || out.driverError));
        return;
      }

      // Without this the whole row is vacuous -- green would mean "escaping worked",
      // not "the degraded path worked".
      t.check(out.escaperPresent === false, 'INV-1',
        'the fault must actually be injected: no escaper may be reachable in the '
        + 'child process, got escaperPresent=' + out.escaperPresent);

      const painted = (out.offlinePainted || []).join('\n');
      t.note('painted with no escaper: ' + JSON.stringify(painted.slice(0, 240)));

      // THE DEFECT. Before the fix this array was empty and this check is the one
      // that fails.
      t.check((out.offlinePainted || []).length > 0, 'INV-1',
        'with escape.js missing the widget rendered NOTHING at all -- the write was '
        + 'durable and the visitor saw a blank region, which reads as "the button did '
        + 'nothing" and invites a resubmit. Painted ' + (out.offlinePainted || []).length
        + ' time(s)');
      t.check(painted.trim().length > 0, 'INV-1',
        'the render must carry actual words, not an empty shell');
      t.check(HONEST_PENDING.test(painted), '§4.3',
        'the visitor must still be told their message is held on this device and not '
        + 'yet sent; rendered ' + JSON.stringify(painted.slice(0, 240)));
      t.check(!SUCCESS_AFFORDANCE.test(painted), '§4.3',
        'the degraded render must not claim success either; rendered '
        + JSON.stringify(painted.slice(0, 240)));
      t.check(/github|e-?mail|issue/i.test(painted), '§4.6',
        'the fallback must survive the degraded path -- an unreachable endpoint plus '
        + 'a missing escaper is exactly when a visitor needs somewhere else to go');

      // The point of the fix: CONSTANTS ONLY. Not "escaped correctly" -- there is no
      // escaper here, so any interpolation at all is raw, and raw is the XSS the
      // early return was avoiding.
      const both = painted + '\n' + (out.ackedPainted || []).join('\n');
      const leaks = [
        ['text', C1_HOSTILE_TEXT], ['page', C1_PAGE],
        ['contact', C1_CONTACT], ['credit', C1_CREDIT]
      ].filter(([, v]) => both.indexOf(v) !== -1).map(([k]) => k);
      t.check(leaks.length === 0, 'escaping',
        'NO visitor value may be interpolated on the no-escaper path (it would be '
        + 'raw). Leaked: ' + JSON.stringify(leaks));
      t.check(inert(both), 'escaping',
        'the degraded render must still be structurally inert; got '
        + JSON.stringify(both.slice(0, 240)));

      // A receipt cannot be shown without an escaper, and pretending otherwise is
      // the class of lie this repo forbids: the receipt is the visitor's only handle
      // for a later erasure request (§10).
      const acked = (out.ackedPainted || []).join('\n');
      t.check(acked.trim().length > 0, 'INV-1',
        'an ACKNOWLEDGED message must also render something -- a 200 that paints '
        + 'nothing is the same blank region');
      t.check(!/F-[A-Z2-7]{6}/.test(acked), 'escaping',
        'no receipt code may be composed into the degraded string; got '
        + JSON.stringify(acked.slice(0, 240)));
      t.check(/receipt/i.test(acked), '§10',
        'and the visitor must be TOLD the receipt cannot be shown, rather than left '
        + 'to notice its absence; got ' + JSON.stringify(acked.slice(0, 240)));
    });

// ===========================================================================
// C2 -- §4.6's fallback on the state it was written for
// ===========================================================================
// Also a 2026-08-17 review defect, not a contract row. §4.6 says: "If the endpoint
// is unreachable entirely, the fallback is a prefilled GitHub issue -- offered
// AFTER telling the truth about what happened, never instead of it." The widget
// emitted the fallback only for `refused` and `rejected`. `retrying` -- which is
// precisely where an unreachable endpoint lands, via settleRetry() -- rendered no
// fallback at all, so the one state §4.6 names was the one state without it.
//
// Two halves, because "a fallback is present" and "the fallback is prefilled" are
// different claims:
//   (a) with no element factory, the constant-url line must appear in the string;
//   (b) with one, an anchor NODE must appear carrying the visitor's own words, and
//       that url must never appear in the html string -- a url built out of hostile
//       text has no business in an attribute.

/** A minimal element, faithful on the two things that matter: assignment is to a
 *  PROPERTY (no HTML parsing anywhere) and children are appended, not serialised. */
function makeElementFactory() {
  const created = [];
  function fn(tag) {
    const el = {
      tagName: String(tag).toLowerCase(),
      children: [],
      appendChild(n) { this.children.push(n); return n; }
    };
    created.push(el);
    return el;
  }
  return { fn, created };
}

function allText(node) {
  if (!node) return '';
  let s = typeof node.textContent === 'string' ? node.textContent : '';
  for (const c of (node.children || [])) s += allText(c);
  return s;
}

function anchorsIn(nodeLists) {
  const out = [];
  const walk = (n) => {
    if (!n) return;
    if (n.tagName === 'a') out.push(n);
    for (const c of (n.children || [])) walk(c);
  };
  for (const list of nodeLists) for (const n of (list || [])) walk(n);
  return out;
}

function makeRender2() {
  const painted = [];
  const nodes = [];
  return {
    fn: (html, ns) => { painted.push(String(html)); nodes.push(ns || []); },
    painted, nodes
  };
}

const GH_BASE = 'https://github.com/PipFoweraker/pdoom1/issues/new';

row('C2', 'the endpoint is unreachable entirely -- §4.6 fallback in `retrying`',
    'fetch rejects, so settleRetry() runs and the entry sits in `retrying`; the '
    + 'render is inspected for the fallback that §4.6 asks for on exactly that state',
    '§4.6, §4.3',
    async (t) => {
      const TEXT = "the linux build 404s & it's \"broken\" <script>alert(1)</script>";

      // -- (a) no element factory: the string channel must still carry the offer ---
      const storageA = makeStorage();
      const renderA = makeRender2();
      const netA = makeFetch(storageA, [offline]);
      const clientA = MODULE.createFeedbackClient({
        storage: storageA, fetch: netA.fn, uuid, now: () => 1755230000000,
        render: renderA.fn
      });
      const rA = await clientA.submit({ kind: 'bug', page: '/download/', text: TEXT });

      t.check(rA.state === 'retrying', '§4',
        'the row must actually reach `retrying`, or it is testing nothing; got '
        + JSON.stringify(rA.state));
      const lastA = renderA.painted[renderA.painted.length - 1] || '';
      t.note('retrying render: ' + JSON.stringify(lastA.slice(0, 200)));

      // THE DEFECT. Before the fix this is the check that fails.
      t.check(/github|e-?mail|issue/i.test(lastA), '§4.6',
        'an unreachable endpoint is the exact case §4.6 was written for, and the '
        + '`retrying` render offered NO fallback. Rendered: '
        + JSON.stringify(lastA.slice(0, 240)));
      t.check(lastA.indexOf(GH_BASE) !== -1, '§4.6',
        'the offer must be a usable link, not a mention; rendered '
        + JSON.stringify(lastA.slice(0, 240)));

      // Rule 3 is absolute and the fix must not have bent it while adding an
      // affordance to this state.
      t.check(!SUCCESS_AFFORDANCE.test(renderA.painted.join('\n')), '§4.3',
        'a `retrying` render carrying a fallback still MUST NOT carry a success '
        + 'affordance; rendered ' + JSON.stringify(lastA.slice(0, 240)));
      t.check(HONEST_PENDING.test(lastA), '§4.6',
        'the fallback is offered AFTER the truth, never instead of it -- the same '
        + 'render must still say the message is unsent and held here');
      t.check(inert(renderA.painted.join('\n')), 'escaping',
        'adding a link to this state must not add an escaping hole');

      // Negative control. Without it, "fallback in retrying" is indistinguishable
      // from "fallback pasted into every state", which would put an escape hatch on
      // a render that is going fine and read as an apology for a success.
      const queuedA = renderA.painted[0] || '';
      t.check(queuedA.indexOf(GH_BASE) === -1, '§4.6',
        'the queued/sending render must NOT offer the fallback -- nothing has gone '
        + 'wrong yet; rendered ' + JSON.stringify(queuedA.slice(0, 200)));

      // -- (b) with an element factory: a PREFILLED anchor, built as a node --------
      const storageB = makeStorage();
      const renderB = makeRender2();
      const el = makeElementFactory();
      const netB = makeFetch(storageB, [offline]);
      const clientB = MODULE.createFeedbackClient({
        storage: storageB, fetch: netB.fn, uuid, now: () => 1755230000000,
        render: renderB.fn, createElement: el.fn
      });
      await clientB.submit({
        kind: 'bug', page: '/download/', text: TEXT,
        contact: 'someone@example.com', credit: 'Pat'
      });

      const anchors = anchorsIn(renderB.nodes);
      t.check(anchors.length >= 1, '§4.6',
        'with an element factory available the fallback must be built as DOM nodes; '
        + 'found ' + anchors.length + ' anchor(s) across '
        + renderB.nodes.length + ' render call(s)');
      if (!anchors.length) { return; }
      const a = anchors[anchors.length - 1];
      t.note('anchor href: ' + JSON.stringify(String(a.href).slice(0, 220)));

      t.check(String(a.href).indexOf(GH_BASE + '?') === 0, '§4.6',
        'the link must be the PREFILLED issue form, not a bare new-issue url -- §4.6 '
        + 'says prefilled and the widget shipped a constant for a year; got '
        + JSON.stringify(String(a.href).slice(0, 160)));
      t.check(/[?&]template=bug_report\.yml(&|$)/.test(String(a.href)), '§4.6',
        'pdoom1 disables blank issues, so a prefill that does not name the form is '
        + 'dropped on the redirect to /issues/new/choose and the link silently lies '
        + 'about being pre-filled; got ' + JSON.stringify(String(a.href).slice(0, 160)));
      t.check(String(a.href).indexOf(encodeURIComponent('the linux build 404s')
        .replace(/%20/g, '+')) !== -1, '§4.6',
        'the visitor\'s own words must actually be in the prefill; got '
        + JSON.stringify(String(a.href).slice(0, 220)));
      t.check(allText(a).trim().length > 0, '§4.6',
        'the link must have visible text -- an anchor with no text is not an offer');

      // A url built out of hostile text is exactly why this is a node and not a
      // string. x-www-form-urlencoded cannot emit any of these; assert it rather
      // than trust it, because the whole safety argument rests on that alphabet.
      t.check(!/["'<>\s]/.test(String(a.href)), 'escaping',
        'the prefilled url must contain no quote, angle bracket or space -- those are '
        + 'what break out of an attribute; got ' + JSON.stringify(String(a.href)));

      // ...and it must never have been a string in the first place. This is the
      // check that stops a later refactor from "simplifying" the node channel away.
      const htmlB = renderB.painted.join('\n');
      t.check(htmlB.indexOf(String(a.href)) === -1, 'escaping',
        'the prefilled url must NEVER appear in the html string -- it is built from '
        + 'the visitor\'s words and belongs on a property, not in an attribute');
      t.check(inert(htmlB), 'escaping',
        'the html channel stays inert with the node channel in play');
      t.check(!SUCCESS_AFFORDANCE.test(htmlB + '\n' + allText(a)), '§4.3',
        'neither channel may carry a success affordance in `retrying`');

      // A GitHub issue is public. Neither field was given to us for publication --
      // the same call public/issues/index.html:825-826 already made.
      t.check(String(a.href).indexOf('someone') === -1
           && String(a.href).indexOf('%40example.com') === -1, '§7',
        'the reporter\'s contact must not be pushed into a PUBLIC issue prefill; got '
        + JSON.stringify(String(a.href).slice(0, 220)));

      // -- (c) the hostile corpus through the prefill ------------------------------
      for (const h of HOSTILE) {
        const storageC = makeStorage();
        const renderC = makeRender2();
        const elC = makeElementFactory();
        const netC = makeFetch(storageC, [offline]);
        const clientC = MODULE.createFeedbackClient({
          storage: storageC, fetch: netC.fn, uuid, now: () => 1755230000000,
          render: renderC.fn, createElement: elC.fn
        });
        await clientC.submit({ kind: h, page: h, text: h, contact: h, credit: h });
        const hostileAnchors = anchorsIn(renderC.nodes);
        const hrefs = hostileAnchors.map((n) => String(n.href)).join(' ');
        t.check(!/["'<>\s]/.test(hrefs), 'escaping',
          'prefill url stays free of attribute-breaking characters for payload '
          + h.slice(0, 30) + ' -- got ' + JSON.stringify(hrefs.slice(0, 200)));
        t.check(hrefs.indexOf(GH_BASE) === 0 || hrefs === '', 'escaping',
          'the prefill must stay on the GitHub origin for payload ' + h.slice(0, 30)
          + ' -- got ' + JSON.stringify(hrefs.slice(0, 120)));
        t.check(inert(renderC.painted.join('\n')), 'escaping',
          'html channel inert with a hostile prefill in play: ' + h.slice(0, 30));
      }
    });

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------
(async function main() {
  console.log('='.repeat(78));
  console.log('FEEDBACK OUTBOX -- DESTRUCTIVE SUITE (contract §6 rows F7, F8, F16, F17'
            + ' + review defects C1, C2)');
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
