/*
 * escape.js -- THE escaper for pdoom1.com. There is exactly one, and this is it.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * On 2026-07-30 a live stored-XSS hole was found in /leaderboard/: the score API at
 * api.pdoom1.com is UNAUTHENTICATED and validates nothing, so every field it returns is
 * attacker-controlled, and several were being spliced raw into innerHTML. That page was
 * fixed (PRs #202, #208). The 2026-08-01 sweep found the same class on fourteen other
 * pages -- and found FIVE separately-written escapers with three different coverages:
 *
 *   public/blog/post.html          escapeHtml   & < >            (no quotes)
 *   public/docs/roadmap/index.html esc          & < >            (no quotes)
 *   public/game-changelog/...      esc          & < >            (no quotes)
 *   public/issues/index.html       escapeHtml   via textContent  (no quotes)
 *   public/league/archive.html     escapeHtml   & < > " '        (complete)
 *
 * Missing `"` is not a nitpick: four of those five feed an ATTRIBUTE context
 * (href="...", style="background:#...", alt="..."), where a bare double quote ends the
 * attribute and the next token is read as a NEW attribute -- onmouseover= among them.
 * So three of the five escapers could not protect their own primary sink.
 *
 * THE RULE: one implementation, correct in BOTH contexts. Do not write a second one.
 * scripts/test-escaping.js fails if a page defines its own.
 *
 * CONTEXTS THIS IS CORRECT FOR
 *   - element text        <span>${escapeHTML(x)}</span>
 *   - QUOTED attribute    <a title="${escapeHTML(x)}">     (single or double quotes)
 *   - URL attribute       <a href="${safeUrl(x)}">         escapeHTML alone is NOT enough:
 *                                                          javascript: needs no metachars
 * CONTEXTS IT IS *NOT* CORRECT FOR -- do not use it there, restructure instead:
 *   - unquoted attribute  <a title=${...}>       a space alone breaks out
 *   - inside <script>     var x = "${...}";      </script> and \ break out
 *   - inside <style>, or a style="" value that is not a plain literal
 *   - event handlers      onclick="${...}"       that is script, not markup
 *
 * FAILURE MODE, ON PURPOSE: if this file fails to load, escapeHTML is undefined and the
 * calling template throws a ReferenceError, so the render aborts and the page shows
 * nothing rather than showing unescaped data. Fail closed. Every page that calls it must
 * load it with a PLAIN blocking <script src> before its own inline script -- not defer,
 * not async, or the inline script runs first and the page breaks on every load.
 */
(function () {
  'use strict';

  var ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

  /**
   * Render any value as inert HTML text.
   * null/undefined render as '' -- never as the strings "null"/"undefined", which look
   * like data to a reader and are how a missing field gets mistaken for a present one.
   */
  function escapeHTML(s) {
    if (s === null || s === undefined) { return ''; }
    return String(s).replace(/[&<>"']/g, function (c) { return ENTITIES[c]; });
  }

  // A scheme is [a-z][a-z0-9+.-]* before the first ':'. Only these three may survive.
  // Everything else -- javascript:, data:, vbscript:, blob:, filesystem: -- is dropped.
  var SCHEME = /^([a-z][a-z0-9+.\-]*):/i;
  var ALLOWED_SCHEMES = { http: true, https: true, mailto: true };

  /**
   * Does this URL resolve to something safe to navigate to?
   *
   * The one primitive; safeUrl and safeUrlRaw are both built on it. Two things escapeHTML
   * cannot do on its own, which is why a URL needs its own check at all:
   *  1. `javascript:alert(1)` contains no HTML metacharacter, so escaping leaves it
   *     intact and clicking the link runs it in this origin.
   *  2. Browsers strip control characters from INSIDE a scheme before resolving it, so
   *     "java<TAB>script:alert(1)" is javascript: to the parser. The scheme is therefore
   *     tested against a control-character-stripped probe, not the raw string.
   *
   * Safe to call on an ALREADY-ESCAPED string: HTML entity decoding can only ever
   * produce & < > " ', none of which can manufacture a `scheme:` prefix that was not
   * already there. (`javascript&#58;x` escapes to `javascript&amp;#58;x`, which the
   * parser decodes back to `javascript&#58;x` -- a relative URL, not a scheme.)
   */
  function isSafeUrl(u) {
    if (u === null || u === undefined) { return false; }
    var raw = String(u);
    // Strip anything a browser ignores inside a scheme (control chars, NBSP, BOM).
    // Built by code point rather than a regex class so this source file can never
    // itself contain a raw control character -- one did, and git called the whole
    // file binary.
    var probe = '';
    for (var i = 0; i < raw.length; i++) {
      var cc = raw.charCodeAt(i);
      if (cc > 0x20 && cc !== 0x7f && cc !== 0xa0 && cc !== 0x200b && cc !== 0xfeff) {
        probe += raw.charAt(i);
      }
    }
    if (probe === '') { return false; }
    // Protocol-relative ("//host/x") silently leaves the origin; nothing here wants it.
    if (probe.slice(0, 2) === '//') { return false; }
    var m = SCHEME.exec(probe);
    return !(m && !ALLOWED_SCHEMES[m[1].toLowerCase()]);
  }

  /**
   * Three names, one check. Pick by SINK, and the choice stays visible at the call site:
   *
   *   safeUrl(u, fb)     quoted href/src inside an HTML string   scheme-checked + escaped
   *   safeUrlRaw(u, fb)  a JS sink: window.open(), el.href        scheme-checked only
   *   isSafeUrl(u)       a URL that is already escaped in situ    the bare predicate
   *
   * Using safeUrl in a JS sink corrupts the URL: escapeHTML turns the `&` between query
   * parameters into `&amp;`, which is correct in markup (the parser decodes it) and wrong
   * everywhere else. Using safeUrlRaw in markup leaves a `"` free to end the attribute.
   *
   * Both return `fallback` ('' by default) rather than a dangerous URL, so a rejected
   * link renders as a dead anchor instead of a live payload.
   */
  function safeUrlRaw(u, fallback) {
    return isSafeUrl(u) ? String(u).trim() : (arguments.length > 1 ? fallback : '');
  }

  function safeUrl(u, fallback) {
    return isSafeUrl(u) ? escapeHTML(String(u).trim()) : (arguments.length > 1 ? fallback : '');
  }

  /**
   * Coerce an API value to a real number.
   *
   * Not an escaping concern -- an availability one. `entry.score.toLocaleString()` and
   * `(entry.final_doom || 0).toFixed(1)` both throw a TypeError when the API returns a
   * string, and one throw inside a render loop takes down the WHOLE list, not one row.
   * The score API validates nothing, so a single hostile POST of {"score":"x"} was a
   * denial of service on /league/ and /league/archive.html with no injection at all.
   * `|| 0` does not fix it: a non-empty string is truthy, and String.toLocaleString is
   * the identity function, so the raw string sails straight through into innerHTML.
   */
  function toNumber(v, fallback) {
    var fb = arguments.length > 1 ? fallback : 0;
    var n = typeof v === 'number' ? v : parseFloat(v);
    return (typeof n === 'number' && isFinite(n)) ? n : fb;
  }

  var API = {
    escapeHTML: escapeHTML, safeUrl: safeUrl, safeUrlRaw: safeUrlRaw,
    isSafeUrl: isSafeUrl, toNumber: toNumber
  };

  if (typeof window !== 'undefined') {
    window.escapeHTML = escapeHTML;
    window.safeUrl = safeUrl;
    window.safeUrlRaw = safeUrlRaw;
    window.isSafeUrl = isSafeUrl;
    window.toNumber = toNumber;
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; }
  if (typeof globalThis !== 'undefined' && typeof window === 'undefined') {
    // Node/test sandboxes with no window still get the bare names.
    globalThis.escapeHTML = escapeHTML;
    globalThis.safeUrl = safeUrl;
    globalThis.safeUrlRaw = safeUrlRaw;
    globalThis.isSafeUrl = isSafeUrl;
    globalThis.toNumber = toNumber;
  }
})();
