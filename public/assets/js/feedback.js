/*
 * feedback.js -- the visitor feedback widget and its durable client-side outbox.
 *
 * Contract: docs/decisions/FEEDBACK_INTAKE_CONTRACT.md (§1, §2, §4, §11.2).
 * Destructive suite: scripts/test-feedback-outbox.js (rows F7, F8, F16, F17).
 * The suite was written from the contract alone, before this file existed. If a row
 * there disagrees with this file, the contract is the tiebreaker -- not this file.
 *
 * THE ONE INVARIANT (contract §0)
 * ------------------------------
 *   INV-1  No success state is ever shown to a visitor without a durable write
 *          having completed.
 *
 * Everything below is a consequence of that sentence:
 *
 *   1. The outbox entry is written to storage BEFORE the first fetch (§4.1). A tab
 *      closed mid-request must not take the message with it. bug-submit.php shows
 *      "Thanks!" for a message still sitting in a local variable; that is the bug
 *      this file exists to kill.
 *   2. An entry leaves the outbox ONLY on a 200 whose `rid` matches (INV-1b). Not
 *      on any 2xx, not on a body we could not parse, not on somebody else's rid.
 *   3. `rid` is minted ONCE per message and reused on every retry (§1). That is the
 *      whole mechanism of idempotency: a new rid per attempt turns one message into
 *      two records that read-time dedup has nothing to collapse.
 *   4. The `retrying` state renders NO success affordance (§4.3) -- no tick, no
 *      green, no thanks. It says the message has not been sent.
 *   5. Quota exhaustion REFUSES the new submission (§4.5). It never evicts an older
 *      unsent message to make room, because evicting is choosing which visitor to
 *      lose, and outbox capacity is a loss channel like any other.
 *
 * ESCAPING
 * --------
 * There is exactly ONE escaper on this site and it is public/assets/js/escape.js.
 * This file defines none of its own; it looks the shared one up and FAILS CLOSED --
 * if escape.js did not load, paint() renders nothing rather than rendering visitor
 * text raw. The durable write still happens: a missing render is a UI failure, a
 * raw render is an XSS, and a dropped message is the one thing the directive
 * forbids outright. Sinks used, and why each one:
 *
 *   escapeHTML   every visitor/server string that becomes element TEXT
 *   isSafeUrl    a bare predicate: may this URL be SHOWN at all? `javascript:`
 *                contains no HTML metacharacter, so escaping cannot make it safe
 *                and only a scheme check can decide.
 *
 * No visitor-supplied value is ever placed in an href. The only href this widget
 * emits is a compile-time constant (the GitHub fallback). See "Fallback link" below
 * for why it is not prefilled.
 *
 * WHAT THIS FILE IS NOT
 * ---------------------
 * Wave 1 builds the module; Wave 2 injects it into pages. Nothing here auto-mounts,
 * and no HTML page loads it yet. When a page does, it must load escape.js first with
 * a PLAIN blocking <script src>, exactly as every other data-rendering page does.
 */
(function () {
  'use strict';

  var OUTBOX_KEY = 'pdoom_feedback_outbox';
  var DEFAULT_ENDPOINT = '/ingest.php';

  // §4.4: 0s, 5s, 30s, 5m, then once per page load. Index n is the delay BEFORE
  // attempt n+1, so the first attempt is immediate and the fourth failure schedules
  // nothing -- from there the only retry is an explicit replay(), which is what a
  // page load and an `online` event both call.
  var BACKOFF_MS = [0, 5000, 30000, 300000];

  // Offered on refusal and on a server rejection (§4.6). CONSTANT, never prefilled
  // with the visitor's text: encodeURIComponent leaves ' ( ) * ! unescaped, so a
  // prefilled body would put an apostrophe inside a quoted href, and no amount of
  // escaping fixes a URL that is being built out of hostile text. The visitor's
  // words stay visible in the form so they can be copied.
  var FALLBACK_URL = 'https://github.com/PipFoweraker/pdoom1/issues/new';
  var FALLBACK_LABEL = 'github.com/PipFoweraker/pdoom1/issues/new';

  // ------------------------------------------------------------------------
  // The shared escaper, looked up late and never reimplemented.
  // ------------------------------------------------------------------------
  function getEscapers() {
    var g = (typeof window !== 'undefined') ? window
          : (typeof globalThis !== 'undefined') ? globalThis
          : null;
    if (g && typeof g.escapeHTML === 'function' && typeof g.isSafeUrl === 'function') {
      return g;
    }
    // Node / bundler. escape.js sits beside this file and exports the same names.
    if (typeof require === 'function' && typeof module !== 'undefined' && module.exports) {
      try {
        var m = require('./escape.js');
        if (m && typeof m.escapeHTML === 'function' && typeof m.isSafeUrl === 'function') {
          return m;
        }
      } catch (e) { /* fall through: fail closed */ }
    }
    return null;
  }

  // ------------------------------------------------------------------------
  // Receipt (§1): "F-" + base32 of the first 30 bits of the rid, 6 chars.
  //
  // Derived, never stored-and-trusted: the receipt shown to a visitor is always
  // recomputed from the rid, so a poisoned outbox entry or a server echoing a
  // hostile `receipt` cannot put a chosen string on the screen. It is escaped on
  // render anyway -- two independent reasons it is inert, because one of them will
  // eventually be refactored away by someone who does not read this comment.
  // ------------------------------------------------------------------------
  var B32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

  function receiptFor(rid) {
    var s = (rid === null || rid === undefined) ? '' : String(rid);
    var hex = s.toLowerCase().replace(/[^0-9a-f]/g, '').slice(0, 8);
    var n = hex ? parseInt(hex, 16) : 0;
    if (typeof n !== 'number' || !isFinite(n)) { n = 0; }
    n = Math.floor(n / 4); // 32 bits of hex -> the top 30
    var out = '';
    for (var i = 5; i >= 0; i--) {
      out += B32.charAt(Math.floor(n / Math.pow(32, i)) % 32);
    }
    return 'F-' + out;
  }

  // ------------------------------------------------------------------------
  // Copy. Fixed literals, chosen so the pending states cannot be misread as
  // success (§4.3). Deliberately free of apostrophes and angle brackets: this text
  // is concatenated into an HTML string, and the destructive suite asserts
  // STRUCTURALLY that nothing but whitelisted markup survives.
  // ------------------------------------------------------------------------
  var COPY = {
    queued:    'Saved on this device. Sending…',
    sending:   'Saved on this device. Sending…',
    retrying:  'Not sent yet — saved on this device, will retry.',
    rejected:  'Not sent — the server refused this message. It is still saved on '
             + 'this device and will be tried again.',
    refused:   'Not accepted — this browser has no storage room left, so nothing '
             + 'was written here and nothing was sent.',
    kept:      'Nothing already waiting on this device was removed.',
    mismatch:  'The server answered about a different message, so this one is '
             + 'still waiting.',
    keep:      'Keep this code. It is the only way to ask us to delete this '
             + 'message later.',
    fallback:  'You can open a GitHub issue instead: '
  };

  function createFeedbackClient(deps) {
    deps = deps || {};
    var storage = deps.storage
      || (typeof window !== 'undefined' ? window.localStorage : null);
    var doFetch = deps.fetch
      || (typeof window !== 'undefined' && window.fetch
          ? function (u, i) { return window.fetch(u, i); } : null);
    var mkuuid = deps.uuid || defaultUuid;
    var now = deps.now || Date.now;
    var render = deps.render || function () {};
    var endpoint = deps.endpoint || DEFAULT_ENDPOINT;
    // Scheduling is a browser concern. In a test sandbox there is no page and no
    // visitor, so an un-injected timer would only leave the event loop alive and
    // fire a fetch nobody is watching.
    var schedule = deps.schedule
      || (typeof window !== 'undefined' && window.setTimeout
          ? function (fn, ms) { return window.setTimeout(fn, ms); } : null);

    var inflight = {};   // rid -> true, so a replay cannot double-send a live attempt

    // -- storage -----------------------------------------------------------
    function readOutbox() {
      var raw;
      try { raw = storage ? storage.getItem(OUTBOX_KEY) : null; }
      catch (e) { return []; }
      if (!raw) { return []; }
      var list;
      try { list = JSON.parse(raw); } catch (e) { return []; }
      return Object.prototype.toString.call(list) === '[object Array]' ? list : [];
    }

    /**
     * Write the outbox, or report failure. Returns null on success and the thrown
     * error otherwise -- it never swallows, and it never retries by dropping
     * something. On QuotaExceededError a real localStorage (and the suite's double)
     * leaves the previous value untouched, so a failed write is a no-op and the
     * older unsent messages are byte-identical afterwards (§4.5).
     */
    function writeOutbox(list) {
      try { storage.setItem(OUTBOX_KEY, JSON.stringify(list)); return null; }
      catch (e) { return e; }
    }

    function indexOfRid(list, rid) {
      for (var i = 0; i < list.length; i++) {
        if (list[i] && list[i].rid === rid) { return i; }
      }
      return -1;
    }

    /** Persist a mutated entry. Best effort: a failure here cannot lose the entry,
     *  because the version already in storage still carries the visitor's words. */
    function persist(entry) {
      var list = readOutbox();
      var i = indexOfRid(list, entry.rid);
      if (i === -1) { return; }
      list[i] = entry;
      writeOutbox(list);
    }

    /** The ONLY removal path. INV-1b: called from exactly one place, the branch
     *  that has already checked status 200, ok:true and a matching rid. */
    function dropEntry(rid) {
      var list = readOutbox();
      var kept = [];
      for (var i = 0; i < list.length; i++) {
        if (!list[i] || list[i].rid !== rid) { kept.push(list[i]); }
      }
      writeOutbox(kept);
    }

    // -- render ------------------------------------------------------------
    function payloadOf(entry) {
      var p = entry && entry.payload;
      return (p && typeof p === 'object') ? p : {};
    }

    /**
     * Build the exact string the widget assigns to innerHTML and hand it to
     * render(). Every interpolation is element TEXT and goes through escapeHTML;
     * the one href is a constant. Fails closed when escape.js is absent.
     */
    function paint(entry, state, detail) {
      var E = getEscapers();
      if (!E) { return; }               // fail closed: nothing, rather than raw
      var p = payloadOf(entry);
      var html = '<div class="fb-status fb-' + state + '">';

      if (state === 'acked') {
        html += '<p class="fb-headline">Saved as '
             +  E.escapeHTML(receiptFor(entry.rid)) + '</p>';
        html += '<p class="fb-note">' + COPY.keep + '</p>';
      } else if (state === 'refused') {
        html += '<p class="fb-headline">' + COPY.refused + '</p>';
        html += '<p class="fb-note">' + COPY.kept + '</p>';
        html += fallbackLine();
      } else {
        html += '<p class="fb-headline">' + (COPY[state] || COPY.retrying) + '</p>';
        if (detail) { html += '<p class="fb-detail">' + E.escapeHTML(detail) + '</p>'; }
        if (state === 'rejected') { html += fallbackLine(); }
      }

      // Echo of what is being held. Element text in every case.
      if (p.text) { html += '<p class="fb-echo">' + E.escapeHTML(p.text) + '</p>'; }
      if (p.credit || p.contact) {
        html += '<p class="fb-who">' + E.escapeHTML(p.credit || '')
             +  (p.contact ? ' (' + E.escapeHTML(p.contact) + ')' : '') + '</p>';
      }
      var meta = [];
      if (p.kind) { meta.push(E.escapeHTML(p.kind)); }
      // isSafeUrl, not escapeHTML: a javascript: URL carries no HTML metacharacter,
      // so escaping would render it intact and a reader would be looking at a live
      // scheme. If it is not a URL we would navigate to, it is not one we display.
      if (p.page && E.isSafeUrl(p.page)) { meta.push(E.escapeHTML(p.page)); }
      if (meta.length) { html += '<p class="fb-meta">' + meta.join(' · ') + '</p>'; }

      html += '</div>';
      render(html);
    }

    function fallbackLine() {
      return '<p class="fb-fallback">' + COPY.fallback
           + '<a class="fb-link" href="' + FALLBACK_URL + '">' + FALLBACK_LABEL
           + '</a></p>';
    }

    // -- wire --------------------------------------------------------------
    function buildPayload(entry) {
      var p = payloadOf(entry);
      var out = {
        rid: entry.rid,
        kind: p.kind,
        page: p.page,
        client_ts: p.client_ts,
        attempt: entry.attempt
      };
      // Optional fields are omitted rather than sent as null: §2 says unknown keys
      // are dropped, but a null is a value and would overwrite nothing usefully.
      if (p.value !== undefined) { out.value = p.value; }
      if (p.text !== undefined) { out.text = p.text; }
      if (p.contact !== undefined) { out.contact = p.contact; }
      if (p.credit !== undefined) { out.credit = p.credit; }
      if (p.elapsed_ms !== undefined) { out.elapsed_ms = p.elapsed_ms; }
      out.hp = p.hp === undefined ? '' : p.hp;
      return out;
    }

    /**
     * One attempt at one entry. The entry is ALREADY in storage before this is
     * called -- that ordering is the whole of §4.1 and there is no path here that
     * writes it later.
     */
    function attemptSend(entry) {
      if (!doFetch) {
        entry.state = 'retrying';
        entry.last_error = 'no-transport';
        persist(entry);
        paint(entry, 'retrying');
        return Promise.resolve(result(entry, 'retrying'));
      }
      inflight[entry.rid] = true;
      entry.attempt = (typeof entry.attempt === 'number' && isFinite(entry.attempt)
                       ? entry.attempt : 0) + 1;
      entry.state = 'sending';
      entry.last_attempt_at = now();
      persist(entry);
      paint(entry, 'sending');

      var payload = buildPayload(entry);
      return Promise.resolve()
        .then(function () {
          return doFetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        })
        .then(function (resp) { return handleResponse(entry, resp); })
        .catch(function (err) {
          // fetch REJECTS when there is no network; it does not resolve ok:false.
          return settleRetry(entry, 'network: ' + (err && err.message ? err.message : err));
        })
        .then(function (r) { delete inflight[entry.rid]; return r; });
    }

    function handleResponse(entry, resp) {
      var status = resp && typeof resp.status === 'number' ? resp.status : 0;
      var parse = (resp && typeof resp.json === 'function')
        ? resp.json().catch(function () { return null; })
        : Promise.resolve(null);

      return parse.then(function (body) {
        // INV-1b, in one place and one place only. A 2xx is not enough; a body we
        // could not parse is not enough; somebody else's rid is not enough.
        if (status === 200 && body && body.ok === true && body.rid === entry.rid) {
          dropEntry(entry.rid);
          entry.state = 'acked';
          paint(entry, 'acked');
          return result(entry, 'acked');
        }
        if (status === 200) {
          // Wrote something, told us about something else. Not an acknowledgement.
          entry.last_error = 'rid-mismatch';
          entry.state = 'retrying';
          persist(entry);
          paint(entry, 'retrying', COPY.mismatch);
          return result(entry, 'retrying');
        }
        // §2: `retryable` is explicit so we never infer it from the status code.
        // A body that omits it is treated as retryable -- guessing "permanent"
        // would strand the message.
        var retryable = !(body && body.retryable === false);
        var why = (body && body.error) ? String(body.error) : ('HTTP ' + status);
        if (retryable) { return settleRetry(entry, why); }
        // §11.4 / INV-1e: a 400 or 413 does NOT authorise dropping the message.
        // Our parser being unhappy is our bug, and their words are still here.
        entry.state = 'rejected';
        entry.last_error = why;
        entry.retryable = false;
        persist(entry);
        paint(entry, 'rejected', why);
        return result(entry, 'rejected');
      });
    }

    function settleRetry(entry, why) {
      entry.state = 'retrying';
      entry.last_error = why;
      persist(entry);
      paint(entry, 'retrying');
      scheduleRetry(entry);
      return result(entry, 'retrying');
    }

    function scheduleRetry(entry) {
      if (!schedule) { return; }
      var delay = BACKOFF_MS[entry.attempt];   // attempt 1 failed -> BACKOFF_MS[1]
      if (typeof delay !== 'number') { return; }  // past the tail: once per page load
      schedule(function () {
        var list = readOutbox();
        var i = indexOfRid(list, entry.rid);
        if (i === -1 || inflight[entry.rid]) { return; }  // acked, or already going
        attemptSend(list[i]);
      }, delay);
    }

    function result(entry, state) {
      return {
        state: state,
        rid: entry.rid,
        receipt: receiptFor(entry.rid),
        attempt: entry.attempt
      };
    }

    // -- public ------------------------------------------------------------
    /**
     * Accept a message. The durable write happens FIRST; if it cannot happen, the
     * submission is refused out loud and nothing already queued is touched.
     */
    function submit(input) {
      input = input || {};
      var rid = String(mkuuid());
      var entry = {
        rid: rid,
        receipt: receiptFor(rid),
        state: 'queued',
        attempt: 0,
        created_at: now(),
        payload: {
          rid: rid,
          kind: input.kind,
          page: input.page,
          value: input.value,
          text: input.text,
          contact: input.contact,
          credit: input.credit,
          elapsed_ms: input.elapsed_ms,
          hp: input.hp === undefined ? '' : input.hp,
          client_ts: Math.floor(now() / 1000)
        }
      };

      var list = readOutbox();
      list.push(entry);
      var err = writeOutbox(list);
      if (err) {
        // §4.5. The old entries are still in storage exactly as they were, because
        // the failed setItem never replaced them -- and NOTHING here retries by
        // making room. Evicting is choosing which visitor to lose.
        paint(entry, 'refused');
        return Promise.resolve({
          state: 'refused',
          refused: true,
          rid: rid,
          receipt: entry.receipt,
          message: COPY.refused + ' ' + COPY.kept + ' ' + COPY.fallback + FALLBACK_URL,
          error: err && err.name ? err.name : 'QuotaExceededError'
        });
      }

      paint(entry, 'queued');
      return attemptSend(entry);
    }

    /**
     * Re-attempt everything held locally. Called on DOMContentLoaded and on
     * `online` (§4.4) -- both of which mean "the situation changed", so each entry
     * gets one attempt now rather than waiting out a backoff timer that belongs to
     * a page load that has ended. The backoff sequence governs the timers WITHIN a
     * load; replay() is the "once per page load" tail of the same rule.
     */
    function replay() {
      var list = readOutbox();
      var out = [];
      var chain = Promise.resolve();
      for (var i = 0; i < list.length; i++) {
        chain = chain.then(step(list[i]));
      }
      function step(entry) {
        return function () {
          if (!entry || inflight[entry.rid]) { return null; }
          return attemptSend(entry).then(function (r) { out.push(r); });
        };
      }
      return chain.then(function () { return out; });
    }

    function outbox() { return readOutbox(); }

    return {
      submit: submit,
      replay: replay,
      outbox: outbox,
      OUTBOX_KEY: OUTBOX_KEY
    };
  }

  // crypto.randomUUID is the contract's generator (§1). The fallback is only for
  // browsers without it; both produce a 128-bit v4-shaped string, and the rid is a
  // join key rather than a secret, so a getRandomValues path is sufficient.
  function defaultUuid() {
    var c = (typeof crypto !== 'undefined') ? crypto
          : (typeof window !== 'undefined' ? window.crypto : null);
    if (c && typeof c.randomUUID === 'function') { return c.randomUUID(); }
    var b = new Array(36), hex = '0123456789abcdef';
    for (var i = 0; i < 36; i++) {
      b[i] = hex.charAt(Math.floor(Math.random() * 16));
    }
    b[8] = b[13] = b[18] = b[23] = '-';
    b[14] = '4';
    b[19] = hex.charAt(8 + Math.floor(Math.random() * 4));
    return b.join('');
  }

  // ------------------------------------------------------------------------
  // Browser mount. Wave 2 wires this into pages; nothing auto-mounts here.
  //
  // The form chrome is built with createElement/textContent, so it has no HTML
  // string and therefore no escaping question at all. The ONE innerHTML sink in
  // this file is the status node, and everything reaching it came out of paint().
  // ------------------------------------------------------------------------
  function mountFeedbackWidget(container, options) {
    if (!container || typeof document === 'undefined') { return null; }
    options = options || {};

    var status = document.createElement('div');
    status.className = 'fb-status-region';

    var field = document.createElement('textarea');
    field.className = 'fb-text';
    field.setAttribute('rows', '4');

    var hp = document.createElement('input');       // honeypot: flags, never drops
    hp.className = 'fb-hp';
    hp.setAttribute('type', 'text');
    hp.setAttribute('tabindex', '-1');
    hp.setAttribute('autocomplete', 'off');
    hp.style.position = 'absolute';
    hp.style.left = '-9999px';

    var button = document.createElement('button');
    button.setAttribute('type', 'button');
    button.textContent = options.label || 'Send';

    var form = document.createElement('div');
    form.className = 'fb-form';
    form.appendChild(field);
    form.appendChild(hp);
    form.appendChild(button);

    container.appendChild(form);
    container.appendChild(status);

    var client = createFeedbackClient({
      endpoint: options.endpoint,
      render: function (html) { status.innerHTML = html; }
    });

    var opened = Date.now();
    button.addEventListener('click', function () {
      if (!field.value) { return; }
      client.submit({
        kind: options.kind || 'feedback',
        page: location.pathname + location.search,
        text: field.value,
        hp: hp.value,
        elapsed_ms: Date.now() - opened
      });
    });

    attachReplayHandlers(client);
    return client;
  }

  /** §4.4: replay on DOMContentLoaded and on `online`. */
  function attachReplayHandlers(client) {
    if (typeof window === 'undefined' || !client) { return; }
    if (typeof document !== 'undefined' && document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () { client.replay(); });
    } else {
      client.replay();
    }
    window.addEventListener('online', function () { client.replay(); });
  }

  var API = {
    createFeedbackClient: createFeedbackClient,
    mountFeedbackWidget: mountFeedbackWidget,
    attachReplayHandlers: attachReplayHandlers,
    OUTBOX_KEY: OUTBOX_KEY
  };

  if (typeof window !== 'undefined') {
    window.createFeedbackClient = createFeedbackClient;
    window.mountFeedbackWidget = mountFeedbackWidget;
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; }
})();
