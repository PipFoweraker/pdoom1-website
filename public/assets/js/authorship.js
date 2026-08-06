/*
 * authorship.js -- who held the pen, resolved honestly.
 *
 * WHAT THIS IS FOR
 * ----------------
 * Most of pdoom1.com is drafted by an assistant. Marking THAT would put a badge on
 * nearly every page, and a mark that appears everywhere is furniture. So the site marks
 * the HUMAN-written pieces instead: scarce by construction, and a claim about the ratio
 * that anyone can check against the volume of everything else.
 *
 * THE ONE RULE THIS FILE EXISTS TO ENFORCE
 * ----------------------------------------
 * ABSENCE IS UNATTRIBUTED. A post with no recorded author is not "probably drafted" and
 * not "probably Pip". Nobody has checked, and the page says exactly that. There is no
 * default identity anywhere in this file -- a fallback ships precisely when the real
 * value is missing, which is when it is most likely to be a lie.
 *
 * It returns PLAIN STRINGS, never markup. Every caller runs them through the site's one
 * escaper (public/assets/js/escape.js) at its own sink. This file deliberately defines no
 * escaping of its own; there is exactly one escaper on this site and it is that file.
 *
 * Identity is open-ended on purpose -- a string key into public/data/authors.json, not a
 * boolean. `pdoom1-website` can become an author by adding a key to that file. A
 * human/not-human flag would have needed a migration to say the same thing.
 *
 * Accountability is NOT here. It never varies -- it is always Pip, including for work
 * done under his direction -- so it is one standing colophon sentence (registry.colophon)
 * rather than a field repeated on every item that would always hold the same value.
 */
(function () {
  'use strict';

  // An id long enough to be a payload is not an id. Truncated before it can be quoted
  // back at a reader in the unresolved message.
  var MAX_ID = 64;

  /**
   * Read `author:` out of a post's YAML front matter.
   *
   * Only the fenced block at the very top is inspected: a line reading "author: someone"
   * in the BODY of a post is prose about a person, not a claim about who wrote it, and
   * treating it as one would let the page's own text change its attribution.
   * Returns '' when there is no front matter or no author key -- which the resolver
   * below renders as unattributed, never as anybody.
   */
  function authorFromFrontMatter(md) {
    if (md === null || md === undefined) { return ''; }
    var text = String(md).replace(/^﻿/, '').replace(/\r\n/g, '\n');
    var lines = text.split('\n');
    if (!/^\s*---\s*$/.test(lines[0] || '')) { return ''; }
    for (var i = 1; i < lines.length; i++) {
      if (/^\s*---\s*$/.test(lines[i])) { break; }
      var m = lines[i].match(/^\s*author\s*:\s*(.*)$/);
      if (m) {
        var v = m[1].trim();
        // Strip one layer of matching quotes; YAML writes author: "pip" and author: pip.
        v = v.replace(/^"([\s\S]*)"$/, '$1').replace(/^'([\s\S]*)'$/, '$1');
        return v.trim();
      }
    }
    return '';
  }

  /**
   * Resolve an author id against the registry, in FIVE states, all of them honest.
   *
   *   unattributed  no id recorded            -> says so; claims neither human nor drafted
   *   human         registry kind === human   -> the marked treatment
   *   attributed    any other registry kind   -> a plain byline (the unmarked default)
   *   unknown-id    id not in the registry    -> quotes the id back, invents no name
   *   no-registry   registry failed to load   -> says the registry is unavailable
   *
   * The last two are separate because the causes are separate, and a message naming the
   * wrong cause is its own small lie: "not in the registry" is false when the registry
   * simply did not load.
   *
   * @param {string} id        the recorded identity, or '' / null when none
   * @param {object|null} reg  parsed public/data/authors.json, or null if unavailable
   * @returns {{state:string, cls:string, text:string, note:string, id:string}}
   *          all plain text -- the CALLER escapes.
   */
  function resolveAuthorship(id, reg) {
    var raw = (id === null || id === undefined) ? '' : String(id).trim();

    if (!raw) {
      return {
        state: 'unattributed',
        cls: 'authorship-unattributed',
        id: '',
        text: 'Authorship not recorded',
        note: 'No author was recorded for this one, so it is claimed as neither hand-written nor drafted.'
      };
    }

    var shown = raw.length > MAX_ID ? raw.slice(0, MAX_ID) + '…' : raw;

    if (!reg || typeof reg !== 'object' || !reg.authors || typeof reg.authors !== 'object') {
      return {
        state: 'no-registry',
        cls: 'authorship-unresolved',
        id: shown,
        text: 'Authorship recorded as “' + shown + '” (author registry unavailable)',
        note: ''
      };
    }

    var entry = Object.prototype.hasOwnProperty.call(reg.authors, raw) ? reg.authors[raw] : null;
    if (!entry || typeof entry !== 'object') {
      return {
        state: 'unknown-id',
        cls: 'authorship-unresolved',
        id: shown,
        text: 'Authorship recorded as “' + shown + '”, which is not in the author registry',
        note: ''
      };
    }

    // A registry entry with no byline still resolves -- to its name, or failing that to
    // the id itself. Never to a manufactured one.
    var byline = typeof entry.byline === 'string' && entry.byline.trim()
      ? entry.byline.trim()
      : (typeof entry.name === 'string' && entry.name.trim() ? entry.name.trim() : shown);
    var note = typeof entry.note === 'string' ? entry.note.trim() : '';

    if (entry.kind === 'human') {
      return { state: 'human', cls: 'authorship-human', id: shown, text: byline, note: note };
    }
    return { state: 'attributed', cls: 'authorship-attributed', id: shown, text: byline, note: note };
  }

  /**
   * The standing accountability sentence, read from the registry rather than typed twice.
   * Returns '' if the registry is unavailable -- the pages carry the same sentence in
   * static HTML, and scripts/test-blog-render.js asserts the two are character-identical,
   * so a drift between them fails CI rather than shipping two versions of a promise.
   */
  function colophonText(reg) {
    if (!reg || typeof reg !== 'object' || typeof reg.colophon !== 'string') { return ''; }
    return reg.colophon.trim();
  }

  var API = {
    authorFromFrontMatter: authorFromFrontMatter,
    resolveAuthorship: resolveAuthorship,
    colophonText: colophonText
  };

  if (typeof window !== 'undefined') {
    window.authorFromFrontMatter = authorFromFrontMatter;
    window.resolveAuthorship = resolveAuthorship;
    window.colophonText = colophonText;
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; }
  if (typeof globalThis !== 'undefined' && typeof window === 'undefined') {
    globalThis.authorFromFrontMatter = authorFromFrontMatter;
    globalThis.resolveAuthorship = resolveAuthorship;
    globalThis.colophonText = colophonText;
  }
})();
