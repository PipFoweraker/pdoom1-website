#!/usr/bin/env node
/**
 * Guard: /docs/roadmap/ renders /docs/roadmap.md, and holds no copy of its own.
 *
 * WHY THIS EXISTS
 * ---------------
 * DreamHost serves a .md file as a DOWNLOAD, so /docs/roadmap.md is not a page a
 * visitor can read (TECH_DEBT B8). The rendering surface exists to fix that. The
 * trap it must not fall into is becoming a SECOND copy of the roadmap prose,
 * which would then drift from the markdown, which is itself a projection of the
 * game repo's ROADMAP.md. So the page fetches the markdown at runtime and renders
 * it with a deliberately small parser -- and this test pins that parser against
 * the actual file, because a silently-mangled table is exactly the kind of thing
 * nobody notices until a funder reads it.
 *
 * It also asserts the two honesty properties the roadmap depends on:
 *   1. the HTML page contains no hardcoded game version (it derives one, or shows
 *      nothing), and
 *   2. every forward-looking Theme row is marked provisional or unnamed.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PAGE = path.join(ROOT, 'public', 'docs', 'roadmap', 'index.html');
const DOC = path.join(ROOT, 'public', 'docs', 'roadmap.md');

let failures = 0;
function check(name, ok, detail) {
	if (ok) {
		console.log('  PASS  ' + name);
	} else {
		failures++;
		console.log('  FAIL  ' + name + (detail ? ' -- ' + detail : ''));
	}
}

const html = fs.readFileSync(PAGE, 'utf8');
const md = fs.readFileSync(DOC, 'utf8');

// --- Pull the renderer out of the page and run it here, with no DOM. ---------
const scripts = html.match(/<script>([\s\S]*?)<\/script>/g) || [];
const rendererTag = scripts.find((s) => s.includes('function render'));
if (!rendererTag) {
	console.log('  FAIL  page still contains an inline renderer script');
	process.exit(1);
}
const code = rendererTag.replace(/^<script>/, '').replace(/<\/script>$/, '');

const fakeModule = { exports: {} };
// `document` is genuinely undefined here, so the page's own guard short-circuits
// the fetch calls and only the pure function is exercised.
new Function('module', 'exports', code)(fakeModule, fakeModule.exports);

check('renderer is exported for testing', typeof fakeModule.exports.render === 'function');
if (typeof fakeModule.exports.render !== 'function') { process.exit(1); }

const out = fakeModule.exports.render(md);

// --- The page must not carry its own copy of the roadmap. -------------------
const bodyOnly = html.replace(/<script>[\s\S]*?<\/script>/g, '').replace(/<style>[\s\S]*?<\/style>/g, '');
check('page holds no copy of the roadmap prose',
	!/monthly rhythm|First Contact|Rivals & News|Per-tick/i.test(bodyOnly),
	'found roadmap wording inline in the page');

// --- No hardcoded game version anywhere in the page. ------------------------
// A literal here would ship precisely when the version.json lookup failed.
const versionLiteral = bodyOnly.match(/\bv?0\.\d+\.\d+\b/);
check('page hardcodes no game version', !versionLiteral,
	versionLiteral ? 'found ' + versionLiteral[0] : '');

// --- Structure survived the parser. -----------------------------------------
check('renders an h1', /<h1>Roadmap<\/h1>/.test(out));
check('renders the month-by-month table', /<table>/.test(out));

const rowCount = (out.match(/<tbody>([\s\S]*?)<\/tbody>/) || ['', ''])[1].split('<tr>').length - 1;
const mdRows = md.split('\n').filter((l) => /^\|/.test(l)).length - 2; // minus header + separator
check('every markdown table row rendered', rowCount === mdRows && rowCount > 0,
	'rendered ' + rowCount + ' of ' + mdRows);

check('no raw pipe characters leaked into prose', !/<p>[^<]*\|/.test(out));
check('ordered list (the release ladder) rendered', /<ol>/.test(out));
check('links rendered', /<a href="https:\/\/github\.com\/PipFoweraker\/pdoom1\/blob/.test(out));
check('external links open safely', !/target="_blank"(?![^>]*rel="noopener")/.test(out));
check('bold survived', /<strong>/.test(out));
// A relative markdown link silently fails to linkify (the href guard rejects it),
// which is how "[Website roadmap](website-roadmap.md)" once shipped as raw text.
check('every markdown link linkified', !/\]\(/.test(out),
	(out.match(/\[[^\]]*\]\([^)]*\)/) || [''])[0]);
check('ASCII double-dash rendered as a dash', !/\s--\s/.test(out));

// --- Escaping: the parser escapes before it inserts markup. -----------------
const nasty = fakeModule.exports.render('<img src=x onerror=alert(1)>\n\n[ok](javascript:alert(1))');
check('html in the source is escaped', !/<img/.test(nasty), nasty);
check('javascript: links are not linkified', !/href="javascript:/.test(nasty), nasty);

// --- The honesty property this whole page exists to protect. ----------------
// Every future Theme row must be marked provisional or explicitly unnamed.
const themeRows = md.split('\n').filter((l) => /^\|\s*\d+ \w+ 20\d\d/.test(l));
check('there are future Theme rows to check', themeRows.length > 0);
const unmarked = themeRows.filter((r) => !/provisional|not yet named/i.test(r));
check('every future Theme is marked provisional or unnamed', unmarked.length === 0,
	unmarked.join(' // '));

// A forward row must not read as committed.
check('no future row claims to be committed',
	!themeRows.some((r) => /\bcommitted\b/i.test(r)));

console.log('');
if (failures) {
	console.log(failures + ' check(s) failed.');
	process.exit(1);
}
console.log('All roadmap render checks passed.');
