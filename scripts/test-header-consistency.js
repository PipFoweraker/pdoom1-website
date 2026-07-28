#!/usr/bin/env node

/**
 * Header/nav consistency check for the hand-written pages.
 * Usage: node scripts/test-header-consistency.js
 *
 * WHAT IT ASSERTS
 * ---------------
 * There is exactly ONE canonical nav on this site, and it lives in
 * `public/assets/js/navigation.js` (the `navigationHTML` template). A page may
 * satisfy the contract in one of two ways:
 *
 *   (A) DELEGATE -- ship an empty `<header></header>` (HTML comments allowed)
 *       and load `/assets/js/navigation.js` at the end of the body. The nav a
 *       reader actually sees is then the canonical markup, which this script
 *       validates ONCE, strictly, against the structural rules below. This is
 *       the regime new pages should adopt.
 *
 *   (B) SHIP STATIC MARKUP -- put a full nav inside the `<header>` that passes
 *       the same structural rules on its own. Kept as a legal regime because
 *       `public/index.html` deliberately carries a homepage-specific nav
 *       (in-page `#home` anchor, an `Events` link the shared nav lacks). Any
 *       page in this regime is drift waiting to happen -- prefer (A).
 *
 * A delegating page MAY keep a small no-JS fallback in its `<header>`, as long
 * as that fallback's `<nav>` has no `.nav-links` class. That is not a loophole,
 * it is navigation.js's own contract: the script replaces the header's nav
 * unless it finds `.nav-links`, on the assumption that a page with `.nav-links`
 * already has a real nav. `public/design-notes/index.html` uses this on purpose
 * (with a comment saying so) to render links on first paint and with JS off.
 *
 * What IS an error is loading navigation.js while the header's nav DOES carry
 * `.nav-links`: the script then leaves that markup alone, so the page is a
 * hand-copy that looks like it inherits the shared nav and silently will not.
 *
 * TWO REAL BUGS WERE FIXED HERE (2026-07-28), both of which made the old
 * numbers meaningless -- read before "fixing" a failure by relaxing a rule:
 *
 *   1. `EMOJI_REGEX` was `/[\u{1F600}-\u{1F64F}|\u{1F300}-\u{1F5FF}|...]/gu`.
 *      Inside a character class `|` is a LITERAL PIPE, not alternation, so the
 *      class matched every `|` in every file. Most of the reported "emojis"
 *      were pipe characters in CSS, JS and prose. 15 of 25 pages were already
 *      emoji-clean and were being failed for punctuation.
 *
 *   2. The header test did `content.includes('<header>')` -- an exact string.
 *      `public/bug-report/index.html` and `public/docs/index.html` use
 *      `<header role="banner">`, which is BETTER markup, and were failed for
 *      it. Worse, that check `return`ed early, so those two pages' real nav
 *      errors were never reported at all.
 *
 * The emoji rule is UNCHANGED in strictness and still gates the exit code. The
 * pages that still fail it fail on genuine content emoji in reader-facing
 * prose, which is frozen by `docs/copy-baseline/` and is not a nav problem.
 *
 * This is a regex-based check, not a DOM parse, to avoid external dependencies.
 */

const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.join(__dirname, '..');
const PUBLIC_DIR = path.join(REPO_ROOT, 'public');
const NAV_SOURCE = path.join(PUBLIC_DIR, 'assets', 'js', 'navigation.js');
const NAV_SCRIPT_SRC = '/assets/js/navigation.js';

// Structural rules. These describe the ONE nav; they are applied to
// navigation.js's markup and to any page that ships its own.
const EXPECTED_STRUCTURE = {
  requiredDropdowns: ['Community ▾', 'Info ▾'],
  requiredLinks: ['Game', 'Leaderboard'],
};

// Emoji detection. `|` removed -- inside a character class it is a literal
// pipe, which is what made this flag ordinary punctuation as emoji.
const EMOJI_REGEX = /[\u{1F300}-\u{1F5FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu;

// Presentation-selector / joiner sequences the range scan above cannot see on
// their own (VS16 after a base char outside those ranges, ZWJ in a compound).
// Written as escapes on purpose: these characters are invisible in an editor,
// so a literal here would be an unreviewable diff.
const ADDITIONAL_EMOJIS = ['\u{FE0F}', '\u{200D}'];

function findHtmlFiles(dir) {
  const files = [];
  const items = fs.readdirSync(dir, { withFileTypes: true });

  for (const item of items) {
    const fullPath = path.join(dir, item.name);
    if (item.isDirectory() && !item.name.startsWith('.') && item.name !== 'node_modules') {
      files.push(...findHtmlFiles(fullPath));
    } else if (item.isFile() && item.name === 'index.html') {
      files.push(fullPath);
    }
  }

  return files;
}

/**
 * Pull the canonical nav markup out of navigation.js. Deliberately NOT copied
 * into this file: a duplicated expectation is how the ten variants happened.
 */
function loadCanonicalNav(sourcePath = NAV_SOURCE) {
  const src = fs.readFileSync(sourcePath, 'utf8');
  const match = src.match(/const\s+navigationHTML\s*=\s*`([\s\S]*?)`;/);
  if (!match) {
    throw new Error(`Could not find the navigationHTML template in ${sourcePath}`);
  }
  return match[1];
}

/**
 * Structural rules applied to a nav's markup, wherever that markup came from.
 */
function testNavMarkup(nav) {
  const errors = [];

  if (!/role="navigation"/.test(nav) || !/aria-label="Main navigation"/.test(nav)) {
    errors.push('Missing nav with proper ARIA attributes');
  }

  if (!/class="designer-credit"/.test(nav)) {
    errors.push('Missing designer credit (.designer-credit)');
  } else if (!nav.includes("Pip Foweraker's")) {
    errors.push('Designer credit does not contain "Pip Foweraker\'s"');
  }

  if (!/class="logo-container"/.test(nav)) {
    errors.push('Missing logo container (.logo-container)');
  }

  const dropdownMatches = nav.match(/class="dropdown"/g);
  if (!dropdownMatches || dropdownMatches.length < 2) {
    errors.push('Missing dropdown navigation elements (expected at least 2)');
  }

  for (const requiredDropdown of EXPECTED_STRUCTURE.requiredDropdowns) {
    if (!nav.includes(requiredDropdown)) {
      errors.push(`Missing required dropdown: "${requiredDropdown}"`);
    }
  }

  for (const requiredLink of EXPECTED_STRUCTURE.requiredLinks) {
    const linkRegex = new RegExp(`role="menuitem"[^>]*>${requiredLink}<`, 'i');
    if (!linkRegex.test(nav)) {
      errors.push(`Missing required navigation link: "${requiredLink}"`);
    }
  }

  return errors;
}

/**
 * Work out which regime a page is in and hand back the markup a reader will
 * actually see, so the structural rules are applied to the RENDERED nav rather
 * than to whatever happens to sit in the file.
 */
function resolvePageNav(content, canonicalNav) {
  const headerMatch = content.match(/<header(?:\s[^>]*)?>([\s\S]*?)<\/header>/);
  if (!headerMatch) {
    return { errors: ['Missing <header> element'], nav: null, regime: 'none' };
  }

  const inner = headerMatch[1];
  const strippedInner = inner.replace(/<!--[\s\S]*?-->/g, '').trim();
  const loadsNavScript = content.includes(NAV_SCRIPT_SRC);

  if (loadsNavScript) {
    // navigation.js's own contract: it replaces the header's nav UNLESS that
    // nav contains .nav-links, in which case it assumes the page has a real
    // nav already and leaves it alone. So markup in the header is only safe
    // while it has no .nav-links -- design-notes uses exactly that to keep a
    // small link row rendering on first paint and with JS off.
    const keptByScript = /class="[^"]*\bnav-links\b/.test(inner);
    if (keptByScript) {
      return {
        errors: [
          'Loads navigation.js but its <header> nav has .nav-links, so ' +
          'navigation.js leaves that markup in place. The page is really a ' +
          'hand-copy pretending to inherit the shared nav - drop .nav-links ' +
          'to make it a no-JS fallback, or empty the header.',
        ],
        nav: inner,
        regime: 'static(masquerading)',
      };
    }
    return {
      errors: [],
      nav: canonicalNav,
      regime: strippedInner.length > 0 ? 'delegate(+fallback)' : 'delegate',
    };
  }

  if (/<nav[\s>]/.test(inner)) {
    return { errors: [], nav: inner, regime: 'static' };
  }

  return {
    errors: [`Header has no nav and does not load ${NAV_SCRIPT_SRC}`],
    nav: null,
    regime: 'none',
  };
}

function testHeaderStructure(filePath, content, canonicalNav) {
  const resolved = resolvePageNav(content, canonicalNav || loadCanonicalNav());
  const errors = [...resolved.errors];
  if (resolved.nav !== null) {
    errors.push(...testNavMarkup(resolved.nav));
  }
  return errors;
}

function testEmojiRemoval(filePath, content) {
  const errors = [];

  const emojiMatches = content.match(EMOJI_REGEX);
  if (emojiMatches) {
    const unique = [...new Set(emojiMatches)];
    errors.push(`Found Unicode emojis (${emojiMatches.length} occurrences): ${unique.join(', ')}`);
  }

  for (const emoji of ADDITIONAL_EMOJIS) {
    if (content.includes(emoji)) {
      errors.push(`Found emoji presentation/joiner sequence: U+${emoji.codePointAt(0).toString(16).toUpperCase()}`);
    }
  }

  return errors;
}

function runTests() {
  console.log('Testing header consistency and emoji removal...\n');

  let canonicalNav;
  try {
    canonicalNav = loadCanonicalNav();
  } catch (e) {
    console.error(`FATAL: ${e.message}`);
    process.exit(1);
  }

  // The single source is checked first. If it regresses, every delegating page
  // regresses with it -- which is the whole point of having a single source.
  const sourceErrors = testNavMarkup(canonicalNav);
  console.log('='.repeat(64));
  console.log('CANONICAL NAV SOURCE: public/assets/js/navigation.js');
  console.log('='.repeat(64));
  if (sourceErrors.length === 0) {
    console.log('PASS navigationHTML satisfies the structural rules\n');
  } else {
    console.log('FAIL navigationHTML violates the structural rules');
    for (const error of sourceErrors) console.log(`  - ${error}`);
    console.log('');
  }

  const htmlFiles = findHtmlFiles(PUBLIC_DIR);
  console.log(`Found ${htmlFiles.length} HTML files to test:\n`);

  const results = [];
  const regimeCounts = {};

  for (const filePath of htmlFiles) {
    const relativePath = path.relative(PUBLIC_DIR, filePath);
    const content = fs.readFileSync(filePath, 'utf8');

    const resolved = resolvePageNav(content, canonicalNav);
    regimeCounts[resolved.regime] = (regimeCounts[resolved.regime] || 0) + 1;

    const headerErrors = [...resolved.errors];
    if (resolved.nav !== null) headerErrors.push(...testNavMarkup(resolved.nav));
    const emojiErrors = testEmojiRemoval(filePath, content);

    results.push({
      file: relativePath,
      regime: resolved.regime,
      headerErrors,
      emojiErrors,
      headerOk: headerErrors.length === 0,
      emojiOk: emojiErrors.length === 0,
      passed: headerErrors.length === 0 && emojiErrors.length === 0,
    });
  }

  console.log('='.repeat(64));
  console.log('TEST RESULTS');
  console.log('='.repeat(64));

  for (const result of results) {
    const status = result.passed ? 'PASS' : 'FAIL';
    console.log(`${status} [${result.regime}] ${result.file}`);

    if (!result.passed) {
      for (const error of [...result.headerErrors, ...result.emojiErrors]) {
        console.log(`  - ${error}`);
      }
      console.log('');
    }
  }

  const headerPass = results.filter(r => r.headerOk).length;
  const emojiPass = results.filter(r => r.emojiOk).length;
  const bothPass = results.filter(r => r.passed).length;
  const totalErrors =
    sourceErrors.length +
    results.reduce((n, r) => n + r.headerErrors.length + r.emojiErrors.length, 0);

  console.log('='.repeat(64));
  console.log(`Nav regimes: ${Object.entries(regimeCounts).map(([k, v]) => `${k}=${v}`).join('  ')}`);
  console.log(`Header/nav contract: ${headerPass}/${results.length} files passed`);
  console.log(`Emoji-free:          ${emojiPass}/${results.length} files passed`);
  console.log(`SUMMARY: ${bothPass}/${results.length} files passed`);
  console.log(`Total errors: ${totalErrors}`);

  if (totalErrors === 0) {
    console.log('All tests passed! Header structure is consistent and emojis have been removed.');
  } else {
    console.log('Some tests failed. Please address the errors above.');
    process.exit(1);
  }
}

if (require.main === module) {
  runTests();
}

module.exports = {
  testHeaderStructure,
  testNavMarkup,
  testEmojiRemoval,
  findHtmlFiles,
  loadCanonicalNav,
  resolvePageNav,
};
