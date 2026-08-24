/*
 * freshness.js -- THE staleness gate for pdoom1.com. There is exactly one, and this
 * is it. Sibling of escape.js: same load rules, same fail-closed posture, same "do
 * not write a second one".
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * Every published value on this site comes out of a file some workflow writes. A
 * workflow can stop running -- parked, broken, or dispatch-only from birth -- and
 * the file it wrote stays on disk, gets rsynced to production forever, and keeps
 * rendering the last thing it said. Nothing about a frozen file looks frozen.
 *
 * Two measured instances, both live for months:
 *   /dashboard/  read a hand-typed changelog file and rendered its newest entries
 *                under the word "Recent". It had frozen nine minor versions and
 *                ~324 days behind the shipping build (fixed 2026-08-03).
 *   /monitoring/ rendered a green "healthy / 100%" deployment card out of
 *                /data/deployment-verification.json, last written 2026-07-17. Both
 *                writers of that file are workflow_dispatch-only, so nothing will
 *                ever refresh it. The card was live and lying (fixed 2026-08-25).
 *
 * /dashboard/ grew a freshness gate for its own box. This file is that gate, lifted
 * out so the next page does not reinvent it -- the way five separately-written
 * escapers happened before escape.js.
 *
 * THE CONTRACT -- read this before calling anything below
 * -------------------------------------------------------
 *  1. assess(when, maxAgeHours) returns a VERDICT ABOUT AN AGE. It never returns,
 *     holds, or remembers the value being judged. There is deliberately no API here
 *     that hands you back "the last known good value": a remembered value ships
 *     exactly when the real source failed, i.e. when nobody can notice it is wrong.
 *  2. `verdict.fresh` is the ONLY key a caller may branch on to decide whether to
 *     render a value. It is true for exactly one state and false for every other
 *     one, including states added to this file later. A caller written against
 *     `state !== 'stale'` would silently start rendering a new failure mode; a
 *     caller written against `.fresh` cannot.
 *  3. UNKNOWN IS NOT FINE. An unreadable timestamp, an absent timestamp, a missing
 *     freshness window and a failed fetch all return `fresh: false`. Absence of a
 *     marker is never a clean bill of health -- everything predating a marker is
 *     unmarked too.
 *  4. A FUTURE DATE IS A BROKEN SOURCE, NOT A SCOOP. A record dated ahead of now by
 *     more than the tolerance is refused and named, because the only thing it can
 *     tell you is that a clock is wrong.
 *  5. The window (`maxAgeHours`) is POLICY, chosen by the caller, not an observation
 *     of what a workflow does. Callers should name it as a constant and say what it
 *     is a multiple of. Deriving a window from the cron that writes the file would
 *     make the gate agree with the thing it is supposed to be checking.
 *  6. Every string this file returns is PLAIN TEXT for a human, and it is built from
 *     values that came out of a fetched document. It introduces no markup of its
 *     own, and it does NOT escape: the CALLER escapes with escape.js, picking by
 *     sink. That is the same division of labour every other renderer here uses.
 *
 * LOADING IT
 * ----------
 * Plain blocking <script src="/assets/js/freshness.js"></script> in the head, before
 * the inline renderer that calls it -- not defer, not async. If it fails to load,
 * `Freshness` is undefined, the renderer throws, and the page shows nothing rather
 * than showing an ungated value. Fail closed, exactly like escape.js.
 *
 * Forced-failure test: scripts/test-freshness.js. Every clause above is asserted
 * there by making it fail on purpose, because a guard seen only in its passing state
 * has not been shown to work.
 */
(function () {
  'use strict';

  // The four states. FRESH is the only one that permits a value to be rendered.
  var FRESH = 'fresh';
  var STALE = 'stale';
  var FUTURE = 'future';
  var UNKNOWN = 'unknown';

  var HOUR = 3600000;

  /**
   * Age of a record in hours, or null when the age cannot be established at all.
   *
   * null means UNKNOWN and every caller must treat it as such. It must never
   * collapse into 0 ("just written") or into any number that lets a record render:
   * 0 is the single most dangerous wrong answer here, because it reads as perfect.
   *
   * Accepted: an ISO string, a millisecond epoch number, a real Date instance.
   * Refused: null, undefined, booleans, arrays, and every other object -- a value
   * parsed out of JSON is never a Date, so an object arriving here is a field of the
   * wrong shape, and guessing at it is how a wrong answer gets published.
   */
  function ageHours(when) {
    if (when === null || when === undefined) { return null; }
    if (typeof when === 'boolean') { return null; }
    var t;
    if (when instanceof Date) {
      t = when.getTime();
    } else if (typeof when === 'number') {
      t = when;
    } else if (typeof when === 'string') {
      // A bare-digit string is an epoch that lost its type somewhere. Refuse it
      // rather than pick between seconds and milliseconds -- the two answers are 3
      // orders of magnitude apart and both look plausible on screen.
      if (/^\s*-?\d+(\.\d+)?\s*$/.test(when)) { return null; }
      t = new Date(when).getTime();
    } else {
      return null;
    }
    if (typeof t !== 'number' || !isFinite(t)) { return null; }
    return (Date.now() - t) / HOUR;
  }

  /**
   * A signed age in hours as a phrase a human can judge: "3 hours ago",
   * "39 days ago", "2 hours from now". Returns 'age unknown' for null, which is the
   * phrase that must appear wherever a value would otherwise have gone.
   */
  function ageText(hours) {
    if (hours === null || hours === undefined || !isFinite(hours)) { return 'age unknown'; }
    var dir = hours < 0 ? 'from now' : 'ago';
    var abs = Math.abs(hours);
    var n, unit;
    if (abs < 1) { n = Math.max(0, Math.floor(abs * 60)); unit = 'minute'; }
    else if (abs < 48) { n = Math.floor(abs); unit = 'hour'; }
    else if (abs < 24 * 60) { n = Math.floor(abs / 24); unit = 'day'; }
    else { n = Math.floor(abs / 24 / 30); unit = 'month'; }
    return n + ' ' + unit + (n === 1 ? '' : 's') + ' ' + dir;
  }

  /** A declared window as a phrase, for explaining a refusal. */
  function windowText(maxAgeHours) {
    if (typeof maxAgeHours !== 'number' || !isFinite(maxAgeHours) || maxAgeHours <= 0) {
      return 'undeclared';
    }
    if (maxAgeHours < 48) { return maxAgeHours + ' hours'; }
    return Math.round(maxAgeHours / 24) + ' days';
  }

  // Every verdict is built here, so `fresh` can only ever be true for one state.
  // A caller cannot construct a passing verdict by hand without importing this.
  function verdict(state, hours, reason) {
    return {
      state: state,
      fresh: state === FRESH,
      ageHours: hours,
      ageText: ageText(hours),
      label: state === FRESH ? 'CURRENT'
        : state === STALE ? 'STALE'
          : state === FUTURE ? 'FUTURE-DATED'
            : 'UNKNOWN',
      reason: reason || ''
    };
  }

  /**
   * Judge one source's timestamp against a declared window.
   *
   * @param {*} when          the source's own "written at" stamp, whatever shape it
   *                          arrived in. Anything unreadable yields UNKNOWN.
   * @param {number} maxAgeHours  POLICY: how old this page is willing to call current.
   * @param {object} [opts]   { futureToleranceHours } -- how far ahead of now a record
   *                          may be dated before it is refused. Default 1 hour, which
   *                          absorbs ordinary clock skew between a runner and a reader
   *                          without absorbing a wrong date.
   * @returns {{state:string, fresh:boolean, ageHours:(number|null), ageText:string,
   *            label:string, reason:string}}
   */
  function assess(when, maxAgeHours, opts) {
    var o = opts || {};
    var tol = typeof o.futureToleranceHours === 'number' && isFinite(o.futureToleranceHours)
      ? Math.abs(o.futureToleranceHours) : 1;

    var hours = ageHours(when);
    if (hours === null) {
      return verdict(UNKNOWN, null,
        'This source carries no timestamp this page can read, so its age cannot be ' +
        'established. Unknown is not the same as fine: a file that stopped being ' +
        'written looks exactly like this.');
    }
    // A caller that forgets to declare a window gets UNKNOWN, never a pass. The
    // alternative -- defaulting to some window -- would invent the policy silently.
    if (typeof maxAgeHours !== 'number' || !isFinite(maxAgeHours) || maxAgeHours <= 0) {
      return verdict(UNKNOWN, hours,
        'No freshness window is declared for this source, so this page cannot say ' +
        'whether ' + ageText(hours) + ' is current or long dead.');
    }
    if (hours < -tol) {
      return verdict(FUTURE, hours,
        'This source is dated ' + ageText(hours) + '. A record from the future means ' +
        'the clock that wrote it is wrong, so nothing in it can be trusted as current.');
    }
    if (hours > maxAgeHours) {
      return verdict(STALE, hours,
        'This source was last written ' + ageText(hours) + '; this page treats ' +
        'anything older than ' + windowText(maxAgeHours) + ' as a past state. What it ' +
        'holds may well be true, but nothing here can tell you that it still is.');
    }
    return verdict(FRESH, hours, '');
  }

  /**
   * The verdict for a source that could not be read at all -- a failed fetch, a
   * non-200, unparseable JSON, a document missing the field entirely.
   *
   * Exists so that "we could not look" and "we looked and it was old" are different
   * sentences on the page while being the same thing to the branch: `fresh` is false
   * for both. `why` is the caller's plain-text explanation.
   */
  function unavailable(why) {
    return verdict(UNKNOWN, null,
      why || 'This source could not be read, so this page has nothing to report about ' +
      'it. That is an absence of information, not an absence of problems.');
  }

  var API = {
    FRESH: FRESH, STALE: STALE, FUTURE: FUTURE, UNKNOWN: UNKNOWN,
    ageHours: ageHours, ageText: ageText, windowText: windowText,
    assess: assess, unavailable: unavailable
  };

  if (typeof window !== 'undefined') { window.Freshness = API; }
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; }
  if (typeof globalThis !== 'undefined' && typeof window === 'undefined') {
    globalThis.Freshness = API;
  }
})();
