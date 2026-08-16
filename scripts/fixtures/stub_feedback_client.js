// DELIBERATELY NAIVE stub of the feedback widget's client-side outbox.
//
// THIS IS NOT AN IMPLEMENTATION AND MUST NEVER BECOME ONE.
//
// docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §6 requires the destructive suite to
// be observed RED before agent A2 writes public/assets/js/feedback.js (Gate 2). A
// test that has never failed has not been shown to be a test -- so the suite needs
// something to run against that is real enough to accept a submission and wrong
// enough to fail. That is this file.
//
// Every naive behaviour below has shipped somewhere, and §4.3 says the worst of
// them shipped HERE: "This is the exact failure bug-submit.php shipped and
// TECH_DEBT C5 half-fixed."
//
//   * the outbox entry is written AFTER the fetch, not before   -> §4.1   (F7)
//   * a failed send still renders "Thanks!"                     -> §4.3   (F7)
//   * a fresh rid is minted on every attempt, so a retry is a
//     new message and the server cannot dedup                   -> §1     (F8)
//   * the entry is removed on any 2xx, without checking the rid -> INV-1b (F8)
//   * a quota error evicts the OLDEST entry to make room        -> §4.5   (F16)
//   * every field is interpolated raw into innerHTML            -> escaping rule (F17)
//
// DO NOT "FIX" THIS FILE. Fixing it makes the suite green against a stub, which is
// the vacuous-green shape CLAUDE.md's testing discipline forbids.
//
// THE FACTORY SHAPE IS A TEST SEAM, and agent A2's real module must export the
// same one (see the report on branch feedback/intake-contract). The contract
// specifies the state machine but no API, so this shape was chosen by the test
// author and is the thing to argue with if it is wrong:
//
//   createFeedbackClient({ storage, fetch, uuid, now, render, endpoint })
//     -> { submit(input) -> Promise<result>, replay() -> Promise<result[]>, outbox() }
//
//   storage   localStorage-like: getItem/setItem/removeItem. setItem MAY throw
//             QuotaExceededError -- that is F16's injection.
//   fetch     window.fetch-like. MAY reject (offline) -- that is F7's injection.
//   render    called with the HTML string the widget would assign to innerHTML.
//             This is the sink F17 attacks; a real widget passes its own node's
//             innerHTML through here so the test can see what the DOM would get.
//   result    { state, rid, receipt, refused?, message? }
//             state is one of queued | sending | acked | retrying | refused.

(function () {
  'use strict';

  var OUTBOX_KEY = 'pdoom_feedback_outbox';

  function createFeedbackClient(deps) {
    var storage = deps.storage;
    var doFetch = deps.fetch;
    var uuid = deps.uuid;
    var now = deps.now || Date.now;
    var render = deps.render || function () {};
    var endpoint = deps.endpoint || '/ingest.php';

    function readOutbox() {
      try { return JSON.parse(storage.getItem(OUTBOX_KEY) || '[]'); }
      catch (e) { return []; }
    }

    function writeOutbox(list) {
      storage.setItem(OUTBOX_KEY, JSON.stringify(list));
    }

    function receiptFor(rid) {
      return 'F-' + String(rid).replace(/-/g, '').slice(0, 6).toUpperCase();
    }

    // NAIVE: raw interpolation into an innerHTML string, in five places at once.
    function paint(entry, state) {
      var p = entry.payload || {};
      if (state === 'acked') {
        render('<div class="fb-ok">Thanks! Saved as ' + entry.receipt + '</div>');
        return;
      }
      render(
        '<div class="fb-ok">' +
        '<p>Thanks! We got your ' + (p.kind || 'note') + ' about ' +
        '<a href="' + (p.page || '/') + '">this page</a></p>' +
        '<p class="fb-echo">' + (p.text || '') + '</p>' +
        '<p class="fb-credit">' + (p.credit || '') + ' &lt;' + (p.contact || '') + '&gt;</p>' +
        '</div>'
      );
    }

    function push(entry) {
      var list = readOutbox();
      list.push(entry);
      try {
        writeOutbox(list);
      } catch (e) {
        // NAIVE, and this is the loss channel §4.5 names: the visitor's OLDEST
        // unsent message is thrown away so the newest one fits.
        while (list.length > 1) {
          list.shift();
          try { writeOutbox(list); return; } catch (e2) { /* keep evicting */ }
        }
        try { writeOutbox(list); } catch (e3) { /* give up silently */ }
      }
    }

    function drop(rid) {
      writeOutbox(readOutbox().filter(function (e) { return e.rid !== rid; }));
    }

    function send(payload) {
      return doFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }

    function submit(input) {
      // NAIVE: a brand-new rid per attempt. The join key across outbox, store and
      // notification is therefore never the same twice.
      var rid = uuid();
      var payload = Object.assign({}, input, {
        rid: rid,
        client_ts: Math.floor(now() / 1000),
        attempt: 1
      });
      var entry = { rid: rid, receipt: receiptFor(rid), payload: payload, state: 'sending', attempt: 1 };

      // NAIVE: nothing is in the outbox yet. If the tab closes here, or the fetch
      // never returns, the message existed only in a variable.
      return Promise.resolve()
        .then(function () { return send(payload); })
        .then(function (resp) {
          if (resp && resp.ok) {
            // NAIVE: removed on any 2xx. The rid in the response is never checked.
            drop(rid);
            paint(entry, 'acked');
            return { state: 'acked', rid: rid, receipt: entry.receipt };
          }
          entry.state = 'queued';
          push(entry);
          paint(entry, 'queued');
          return { state: 'queued', rid: rid, receipt: entry.receipt };
        })
        .catch(function () {
          entry.state = 'queued';
          push(entry);
          // NAIVE: a cheerful success affordance for a message that never left.
          paint(entry, 'queued');
          return { state: 'queued', rid: rid, receipt: entry.receipt };
        });
    }

    function replay() {
      var list = readOutbox();
      return list.reduce(function (chain, entry) {
        return chain.then(function (acc) {
          // NAIVE: a new rid again, so the retry is indistinguishable from a new
          // submission and read-time dedup has nothing to collapse on.
          var rid = uuid();
          var payload = Object.assign({}, entry.payload, {
            rid: rid,
            attempt: (entry.attempt || 1) + 1
          });
          return send(payload).then(function (resp) {
            if (resp && resp.ok) {
              drop(entry.rid);
              paint(entry, 'acked');
              acc.push({ state: 'acked', rid: rid, receipt: entry.receipt });
            } else {
              paint(entry, 'queued');
              acc.push({ state: 'queued', rid: rid, receipt: entry.receipt });
            }
            return acc;
          }).catch(function () {
            paint(entry, 'queued');
            acc.push({ state: 'queued', rid: rid, receipt: entry.receipt });
            return acc;
          });
        });
      }, Promise.resolve([]));
    }

    function outbox() { return readOutbox(); }

    return { submit: submit, replay: replay, outbox: outbox, OUTBOX_KEY: OUTBOX_KEY };
  }

  var API = { createFeedbackClient: createFeedbackClient, OUTBOX_KEY: OUTBOX_KEY };
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; }
  if (typeof window !== 'undefined') { window.createFeedbackClient = createFeedbackClient; }
})();
