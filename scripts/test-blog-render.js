// Tests the ACTUAL markdown renderer extracted from public/blog/post.html
// against the ACTUAL published posts.
//
// Exists because 10 of 14 live posts were rendering their YAML front matter as
// the first paragraph a reader saw -- the opening "---" parsed as a horizontal
// rule and the metadata block fell through as prose. Nothing caught it because
// nothing had ever run the renderer outside a browser.
//
// Run: node scripts/test-blog-render.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const BLOG = path.join(ROOT, 'public', 'blog');
const POST_HTML = path.join(BLOG, 'post.html');
const LIST_HTML = path.join(BLOG, 'index.html');
const AUTHORSHIP_JS = path.join(ROOT, 'public', 'assets', 'js', 'authorship.js');
const AUTHORS_JSON = path.join(ROOT, 'public', 'data', 'authors.json');

let pass = 0, fail = 0;
function ok(name, cond, detail) {
  if (cond) { pass++; console.log('  PASS ' + name); }
  else { fail++; console.log('  FAIL ' + name + (detail ? '\n        ' + detail : '')); }
}

// --- extract the renderer from the page, so the test can never drift from it --
const html = fs.readFileSync(POST_HTML, 'utf8');
const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)]
  .map(m => m[1]);
const source = blocks.find(b => b.includes('function renderMarkdown'));
if (!source) {
  console.error('Could not find renderMarkdown in post.html');
  process.exit(1);
}

const sandbox = { document: { getElementById: () => null }, window: {}, console };
sandbox.window = sandbox;
vm.createContext(sandbox);
// The page's escaper is no longer inline: as of 2026-08-01 it is the shared
// public/assets/js/escape.js, pulled in by a blocking <script src> in the head. Load it
// FIRST, exactly as the browser does -- without it the renderer below throws
// ReferenceError, which is the intended fail-closed behaviour and not a test artefact.
vm.runInContext(
  fs.readFileSync(path.join(ROOT, 'public', 'assets', 'js', 'escape.js'), 'utf8'), sandbox);
// Only evaluate the function declarations; skip page bootstrapping that needs a DOM.
// The authorship module, loaded the same way the page loads it: AFTER the escaper,
// because it hands plain strings to callers that escape them and the page's own
// block builder calls escapeHTML directly.
vm.runInContext(fs.readFileSync(AUTHORSHIP_JS, 'utf8'), sandbox);
vm.runInContext(source.replace(/^\s*(document|window)\.[\s\S]*$/m, ''), sandbox);
const render = sandbox.renderMarkdown;
const strip = sandbox.stripFrontMatter;
const authorOf = sandbox.authorFromFrontMatter;
const resolve = sandbox.resolveAuthorship;
const blockHTML = sandbox.authorshipBlockHTML;
const assemble = sandbox.assemblePost;

console.log('front matter stripping');
ok('strips a normal block',
   strip('---\ntitle: "x"\n---\n\n# Heading\n').trim().startsWith('# Heading'));
ok('leaves a post with no front matter alone',
   strip('# Heading\n\ntext').startsWith('# Heading'));
ok('does not eat an unterminated fence',
   strip('---\ntitle: "x"\n\n# Heading').includes('# Heading'));
ok('does not strip a leading horizontal rule mid-document',
   render('# Title\n\n---\n\ntext').includes('<h1>'));

console.log('\nevery published post renders without leaking metadata');
const index = JSON.parse(fs.readFileSync(path.join(BLOG, 'index.json'), 'utf8'));
const posts = index.posts || index;

let checked = 0, missing = [];
for (const p of posts) {
  const f = path.join(BLOG, p.filename);
  if (!fs.existsSync(f)) { missing.push(p.filename); continue; }
  checked++;
  const out = render(fs.readFileSync(f, 'utf8'));
  const leaked = /<p>[^<]*\b(title:|date:|tags:|summary:|commit:)/.test(out);
  if (leaked) {
    ok('no front-matter leak: ' + p.filename, false,
       (out.match(/<p>[^<]{0,110}/) || [''])[0]);
  }
}
ok(`all ${checked} existing posts render without a metadata paragraph`, true);

console.log('\nindex.json matches what is on disk');
ok('every indexed post has a file', missing.length === 0,
   missing.length ? 'missing: ' + missing.join(', ') : '');

const onDisk = fs.readdirSync(BLOG).filter(f => f.endsWith('.md'));
const indexed = new Set(posts.map(p => p.filename));
const orphans = onDisk.filter(f => !indexed.has(f));
if (orphans.length) {
  console.log(`  NOTE ${orphans.length} .md file(s) on disk are not in index.json ` +
              `(unreachable, not an error): ${orphans.slice(0, 3).join(', ')}` +
              (orphans.length > 3 ? ', ...' : ''));
}

// ---------------------------------------------------------------------------
// WHAT THE RENDERER SUPPORTS, ASSERTED CONSTRUCT BY CONSTRUCT
// ---------------------------------------------------------------------------
// Added 2026-08-03. Until then this file tested front-matter stripping and one
// NEGATIVE fact (tables unsupported) -- nothing asserted that `##` produces an <h2>.
// CLAUDE.md meanwhile described the parser as handling "links, images, inline code,
// bold, italic -- no tables, no fenced code blocks, no headings", which had been wrong
// since cf38e315. A documented capability with no test is a claim; this is the list.
//
// So: if you are here to find out what you may write in a post, read THIS, not prose.
console.log('\nblock constructs render to the right tag');
const tag = (md, re, label) => ok(label, re.test(render(md)), render(md).slice(0, 150));
tag('# One', /<h1>One<\/h1>/, '# -> <h1>');
tag('## Two', /<h2>Two<\/h2>/, '## -> <h2>');
tag('### Three', /<h3>Three<\/h3>/, '### -> <h3>');
tag('#### Four', /<h4>Four<\/h4>/, '#### -> <h4>');
tag('##### Five', /<h5>Five<\/h5>/, '##### -> <h5>');
tag('###### Six', /<h6>Six<\/h6>/, '###### -> <h6>');
ok('a # with no space is NOT a heading (a hashtag in prose survives)',
   /<p>#NotAHeading<\/p>/.test(render('#NotAHeading')), render('#NotAHeading'));
tag('```\nx = 1\n```', /<pre><code>x = 1<\/code><\/pre>/, 'fenced code -> <pre><code>');
tag('```python\nx = 1\n```', /<pre><code>x = 1<\/code><\/pre>/, 'fenced code with a language tag');
tag('- a\n- b', /<ul>\n<li>a<\/li>\n<li>b<\/li>\n<\/ul>/, '- -> <ul><li>');
tag('1. a\n2. b', /<ol>\n<li>a<\/li>\n<li>b<\/li>\n<\/ol>/, '1. -> <ol><li>');
tag('> quoted', /<blockquote>quoted<\/blockquote>/, '> -> <blockquote>');
tag('---', /<hr>/, '--- -> <hr>');
tag('plain line', /<p>plain line<\/p>/, 'bare line -> <p>');

console.log('\ninline constructs render to the right tag');
ok('[x](url) -> <a>', /<a href="https:\/\/pdoom1\.com" rel="noopener">site<\/a>/.test(render('[site](https://pdoom1.com)')), render('[site](https://pdoom1.com)'));
ok('![x](url) -> <img>', /<img src="\/a\.png" alt="cap"/.test(render('![cap](/a.png)')), render('![cap](/a.png)'));
ok('`x` -> <code>', /<code>x<\/code>/.test(render('`x`')));
ok('**b** -> <strong>', /<strong>b<\/strong>/.test(render('**b**')));
ok('*i* -> <em>', /<em>i<\/em>/.test(render('*i*')));
ok('_i_ -> <em>', /<em>i<\/em>/.test(render('_i_')));
ok('inline formatting works INSIDE a heading',
   /<h2><strong>b<\/strong> and <a href="\/x" rel="noopener">l<\/a><\/h2>/.test(render('## **b** and [l](/x)')),
   render('## **b** and [l](/x)'));

console.log('\ntables (added 2026-08-03; previously shipped literal pipes at the reader)');
const tableOut = render('| a | b |\n|---|---|\n| 1 | 2 |\n');
ok('header cells -> <th>',
   /<table><thead><tr><th>a<\/th><th>b<\/th><\/tr><\/thead>/.test(tableOut), tableOut);
ok('body cells -> <td>',
   /<tbody><tr><td>1<\/td><td>2<\/td><\/tr><\/tbody>/.test(tableOut), tableOut);
ok('the table is wrapped so IT scrolls, not the page body',
   /<div class="table-wrap">/.test(tableOut));
ok('alignment colons are accepted and ignored',
   /<th>a<\/th>/.test(render('| a | b |\n|:--|--:|\n| 1 | 2 |')));
ok('inline formatting works inside a cell',
   /<td><strong>x<\/strong><\/td>/.test(render('| a |\n|---|\n| **x** |')));
ok('a row shorter than the header does not throw or invent cells',
   /<tr><td>1<\/td><\/tr>/.test(render('| a | b |\n|---|---|\n| 1 |')));

// THE OVER-EAGERNESS GUARD, and the reason the delimiter row is mandatory.
// Existing posts contain pipes in prose and in shell pipelines. If the detector fired
// on any line containing `|`, this change would silently restructure PUBLISHED pages --
// a content regression dressed as a feature. These assert it does not.
ok('prose containing a pipe with NO delimiter row stays a paragraph',
   /<p>a \| b<\/p>/.test(render('a | b')), render('a | b'));
ok('a shell pipeline in prose is not eaten as a table',
   /<p>run cat x \| grep y<\/p>/.test(render('run cat x | grep y')), render('run cat x | grep y'));
ok('a pipe line followed by a bare --- is an hr, not a table',
   /<hr>/.test(render('a | b\n---\n')), render('a | b\n---\n'));
ok('a delimiter-shaped line with no pipes above it is not a table',
   !/<table>/.test(render('text\n\n|---|---|\n')), render('text\n\n|---|---|\n'));

// A table cell is a NEW block context, so it needs its own escaping evidence.
// scripts/test-escaping.js runs the hostile corpus through this renderer, but that
// corpus predates tables and contains no table input -- a green there would say
// nothing about the cell path. Forced here instead of assumed.
console.log('\na table cell is escaped like any other inline context');
const hostileCell = render('| <img src=x onerror=alert(1)> | b |\n|---|---|\n| <script>alert(1)</script> | 2 |');
ok('markup in a header cell renders as visible text',
   /<th>&lt;img src=x onerror=alert\(1\)&gt;<\/th>/.test(hostileCell), hostileCell.slice(0, 170));
ok('markup in a body cell renders as visible text',
   /<td>&lt;script&gt;alert\(1\)&lt;\/script&gt;<\/td>/.test(hostileCell), hostileCell.slice(0, 170));
ok('no event-handler attribute survives anywhere in a rendered table',
   !/\son\w+\s*=\s*["']/i.test(hostileCell), hostileCell.slice(0, 170));

// FORCED FAILURE. CLAUDE.md: "a guard seen only in its passing state has not been shown
// to work." The three assertions above are all of the form "the output does NOT contain
// live markup", and a predicate that is simply wrong passes those trivially. So run the
// same predicate against a deliberately-unescaped cell and require it to REJECT.
const fakeUnescapedCell = '<div class="table-wrap"><table><thead><tr>'
  + '<th><img src=x onerror="alert(1)"></th></tr></thead><tbody></tbody></table></div>';
ok('FORCED FAILURE: the same predicate REJECTS an unescaped cell (so the PASSes mean something)',
   /\son\w+\s*=\s*["']/i.test(fakeUnescapedCell));

console.log('\nthe CSS exists for every tag the renderer emits');
for (const sel of ['h4', 'table', 'th', 'td', 'pre', 'blockquote', 'hr', 'ul', 'code', 'img']) {
  ok('article ' + sel + ' is styled',
     new RegExp('article\\s+[^{;]*\\b' + sel + '\\b[^{;]*\\{').test(html));
}
ok('.table-wrap scrolls horizontally (a wide table must not scroll the page body)',
   /\.table-wrap\s*\{[^}]*overflow-x:\s*auto/.test(html));

console.log('\nevery .md on disk still renders without throwing');
let renderedOk = 0;
for (const p of onDisk) {
  try { render(fs.readFileSync(path.join(BLOG, p), 'utf8')); renderedOk++; }
  catch (e) { ok('renders: ' + p, false, e.message); }
}
ok(`${renderedOk}/${onDisk.length} .md files render without throwing`, renderedOk === onDisk.length);

// ===========================================================================
// AUTHORSHIP (added 2026-08-06, #267)
// ===========================================================================
// The site marks the HUMAN-written pieces, not the drafted ones, because most of it is
// drafted and a mark that appears everywhere is furniture. The whole design therefore
// rests on one property that is easy to get wrong and impossible to see in a passing
// render: ABSENCE MUST STAY ABSENT. Sixteen published posts record no author and nobody
// knows who wrote them; stamping them either way would be fabrication.
//
// So the assertions below are mostly of the form "this output claims NOTHING", and a
// predicate that is simply broken passes those trivially. Each such group therefore ends
// with a FORCED FAILURE: the same predicate, run against a deliberately-wrong output,
// required to reject it.
console.log('\nauthorship: the module, and the registry it reads');

ok('public/assets/js/authorship.js exists', fs.existsSync(AUTHORSHIP_JS));
const authorshipSrc = fs.readFileSync(AUTHORSHIP_JS, 'utf8');
// There is exactly ONE escaper on this site and it is public/assets/js/escape.js.
// A new shared module is exactly where a second one would appear.
ok('authorship.js defines no escaper of its own',
   !/(?:function|const|let|var)\s+(?:esc|escape[A-Za-z]*|sanitize[A-Za-z]*|htmlEscape[A-Za-z]*)\s*[=(]/
     .test(authorshipSrc));
ok('authorship.js contains no default identity (no fallback author id)',
   !/\|\|\s*['"](?:pip|assistant|human)['"]/i.test(authorshipSrc));

for (const [label, file] of [['post.html', POST_HTML], ['index.html', LIST_HTML]]) {
  const src = fs.readFileSync(file, 'utf8');
  ok(label + ' loads authorship.js',
     src.includes('<script src="/assets/js/authorship.js"></script>'));
  ok(label + ' loads it BLOCKING (not defer/async)',
     !/<script[^>]*authorship\.js[^>]*(?:defer|async)/.test(src));
}

ok('public/data/authors.json exists', fs.existsSync(AUTHORS_JSON));
const reg = JSON.parse(fs.readFileSync(AUTHORS_JSON, 'utf8'));
ok('the registry has an authors map',
   reg && typeof reg.authors === 'object' && Object.keys(reg.authors).length > 0);
ok('the registry carries a colophon sentence',
   typeof reg.colophon === 'string' && reg.colophon.trim().length > 20);

// The id rule is READ OUT of the builder rather than retyped, so the two cannot drift.
// (CLAUDE.md: never assert a literal against a value that moves.)
const builderSrc = fs.readFileSync(path.join(ROOT, 'scripts', 'build-blog-index.py'), 'utf8');
const idRuleSrc = (builderSrc.match(/AUTHOR_ID_RE\s*=\s*re\.compile\(r"([^"]+)"\)/) || [])[1];
ok('the builder still declares AUTHOR_ID_RE (the id rule is readable from one place)',
   !!idRuleSrc, 'AUTHOR_ID_RE not found in scripts/build-blog-index.py');
if (idRuleSrc) {
  const idRule = new RegExp(idRuleSrc);
  for (const id of Object.keys(reg.authors)) {
    ok('registry id "' + id + '" satisfies the builder\'s own id rule', idRule.test(id));
  }
}
for (const [id, a] of Object.entries(reg.authors)) {
  ok('registry entry "' + id + '" has a name and a kind',
     a && typeof a.name === 'string' && a.name.trim() && typeof a.kind === 'string' && a.kind.trim());
}
// If nothing is kind:"human" the marked treatment is unreachable and the whole feature
// is decoration. Asserted as a rule, not as a count, so adding identities cannot break it.
ok('at least one identity is kind:"human" (or the human treatment is dead code)',
   Object.values(reg.authors).some((a) => a.kind === 'human'));

// Everything the registry could put on a page. Used below to prove that the states which
// must claim NOTHING claim nothing.
const IDENTITY_STRINGS = Object.values(reg.authors)
  .flatMap((a) => [a.name, a.byline]).filter((s) => typeof s === 'string' && s.trim());
const claimsAnIdentity = (a) =>
  a.cls === 'authorship-human' ||
  IDENTITY_STRINGS.some((n) => (a.text + ' ' + a.note).includes(n));

console.log('\nauthorship: the identity is read from the post itself');
ok('author: pip in front matter is read', authorOf('---\nauthor: pip\n---\n# x') === 'pip');
ok('quoted form is read', authorOf('---\nauthor: "pip"\n---\n# x') === 'pip');
ok('single-quoted form is read', authorOf("---\nauthor: 'pip'\n---\n# x") === 'pip');
ok('front matter with no author yields no author',
   authorOf('---\ntitle: "x"\ndate: "2026-01-01"\n---\n# x') === '');
ok('a post with no front matter yields no author', authorOf('# x\n\ntext') === '');
ok('an "author:" line in the BODY is prose, not an attribution claim',
   authorOf('---\ntitle: "x"\n---\n# x\n\nauthor: someone-else') === '',
   authorOf('---\ntitle: "x"\n---\n# x\n\nauthor: someone-else'));
ok('null/empty input yields no author', authorOf(null) === '' && authorOf('') === '');

console.log('\nauthorship: five states, none of which defaults to a person');
const unattributed = resolve('', reg);
ok('no author -> state "unattributed"', unattributed.state === 'unattributed', unattributed.state);
ok('no author -> the reader is TOLD it is unrecorded, not shown silence',
   /not recorded/i.test(unattributed.text), unattributed.text);
ok('no author -> NOT the human treatment', unattributed.cls !== 'authorship-human');
ok('no author -> claims no identity at all: not human, not drafted, not anybody',
   !claimsAnIdentity(unattributed), unattributed.text + ' / ' + unattributed.note);
ok('no author -> says BOTH negatives explicitly (the AI-drafted reading is closed too)',
   /hand-written/i.test(unattributed.note) && /drafted/i.test(unattributed.note),
   unattributed.note);

const human = resolve('pip', reg);
ok('a human id -> state "human"', human.state === 'human', human.state);
ok('a human id -> the marked class', human.cls === 'authorship-human', human.cls);
ok('a human id -> the registry byline verbatim, not a manufactured one',
   human.text === reg.authors.pip.byline, human.text);

const drafted = resolve('assistant', reg);
ok('a non-human id -> state "attributed"', drafted.state === 'attributed', drafted.state);
ok('a non-human id does NOT get the human treatment',
   drafted.cls !== 'authorship-human', drafted.cls);

const unknown = resolve('nobody-in-the-registry', reg);
ok('an unknown id -> state "unknown-id"', unknown.state === 'unknown-id', unknown.state);
ok('an unknown id is quoted back rather than resolved to a name',
   unknown.text.includes('nobody-in-the-registry'), unknown.text);
ok('an unknown id invents no identity', !claimsAnIdentity(unknown), unknown.text);
ok('an unknown id names the real cause (not in the registry)',
   /not in the author registry/i.test(unknown.text), unknown.text);

for (const badReg of [null, undefined, {}, { authors: 'x' }, 'nope', 42]) {
  const r = resolve('pip', badReg);
  ok('registry ' + JSON.stringify(badReg) + ' -> state "no-registry"',
     r.state === 'no-registry', r.state);
  ok('...and invents no identity from it', !claimsAnIdentity(r), r.text);
}
ok('a missing registry names ITS cause, not the wrong one',
   /registry unavailable/i.test(resolve('pip', null).text), resolve('pip', null).text);

// A 500-character "id" is a payload, not an id. It must not be quoted back whole.
const longId = 'a'.repeat(500);
ok('an absurdly long id is truncated before it is quoted back',
   resolve(longId, reg).text.length < 200, String(resolve(longId, reg).text.length));

// FORCED FAILURE. Every assertion above of the form "claims no identity" is satisfied by
// a predicate that is simply broken. Run the same predicate against the two mistakes this
// whole design exists to prevent, and require it to REJECT both.
ok('FORCED FAILURE: claimsAnIdentity() REJECTS a resolver that defaults an unknown post to the human',
   claimsAnIdentity({ cls: 'authorship-human', text: reg.authors.pip.byline, note: '' }));
ok('FORCED FAILURE: ...and REJECTS one that defaults it to the assistant',
   claimsAnIdentity({ cls: 'authorship-attributed', text: reg.authors.assistant.byline, note: '' }));

console.log('\nauthorship: hostile strings are inert text, from either side');
const liveMarkup = (h) => /<(?:img|script|svg|iframe)\b/i.test(h) || /\son\w+\s*=\s*["']/i.test(h);
const HOSTILE_ID = '"><img src=x onerror=alert(1)>';
const hostileIdOut = blockHTML(resolve(HOSTILE_ID, reg));
ok('a hostile author id renders as visible text, not markup',
   !liveMarkup(hostileIdOut), hostileIdOut.slice(0, 160));
ok('...and the payload is still SHOWN, escaped, rather than silently dropped',
   hostileIdOut.includes('&lt;img'), hostileIdOut.slice(0, 160));

// The other side of the same sink: the registry is a data file, and a data file is edited.
const hostileReg = { authors: { x: {
  name: 'n', kind: 'human',
  byline: '<script>alert(1)</script>',
  note: '" onmouseover="alert(1)' } } };
const hostileRegOut = blockHTML(resolve('x', hostileReg));
ok('a hostile registry byline renders as visible text', !liveMarkup(hostileRegOut), hostileRegOut);
ok('a hostile registry note cannot break out of the class attribute',
   !/class="[^"]*"[^>]*\son\w+=/i.test(hostileRegOut), hostileRegOut);
ok('FORCED FAILURE: liveMarkup() REJECTS an unescaped block (so the PASSes mean something)',
   liveMarkup('<p class="authorship"><img src=x onerror="alert(1)"></p>'));

console.log('\nauthorship: the byline is ADDITIVE -- it cannot alter the post body');
const bodyFixture = '<h1>T</h1>\n<p>one</p>\n<p>two</p>';
const blockFixture = '<p class="authorship authorship-unattributed">A</p>';
const withH1 = assemble(bodyFixture, blockFixture);
// The exact property, not a substring smell: delete the byline again and you must be
// holding the original body, byte for byte.
ok('removing the byline yields the original body, byte for byte',
   withH1.replace(blockFixture, '') === bodyFixture, withH1);
ok('the byline lands immediately after the title', /<\/h1>\s*<p class="authorship/.test(withH1), withH1);
const noH1 = assemble('<p>one</p>', blockFixture);
ok('with no <h1> the byline goes first and the body is untouched',
   noH1 === blockFixture + '<p>one</p>', noH1);

console.log('\nauthorship: the sixteen existing posts are unchanged and unattributed');
let unattributedPosts = 0, bodyPreserved = 0, oneBylineEach = 0;
for (const p of posts) {
  const f = path.join(BLOG, p.filename);
  if (!fs.existsSync(f)) { continue; }
  const md = fs.readFileSync(f, 'utf8');
  const id = authorOf(md);
  const a = resolve(id, reg);
  if (!id && a.state === 'unattributed' && !claimsAnIdentity(a)) { unattributedPosts++; }
  const body = render(md);
  const block = blockHTML(a);
  const final = assemble(body, block);
  // Delete the byline and you must be holding exactly what the renderer produced
  // before this change existed. That is the "do not break the existing posts" contract.
  if (final.replace(block, '') === body) { bodyPreserved++; }
  if ((final.match(/class="authorship /g) || []).length === 1) { oneBylineEach++; }
}
ok(`all ${checked} existing posts resolve to unattributed and claim nobody`,
   unattributedPosts === checked, `${unattributedPosts}/${checked}`);
ok(`all ${checked} existing post bodies survive the byline insertion verbatim`,
   bodyPreserved === checked, `${bodyPreserved}/${checked}`);
ok(`each of the ${checked} posts gets exactly one byline`,
   oneBylineEach === checked, `${oneBylineEach}/${checked}`);

// The RULE, not the count: today no post carries an author, but the first one lands
// within days. Asserting "zero authors" would go red on exactly the commit it should
// go green on. Assert instead that whatever is recorded actually resolves.
console.log('\nauthorship: index.json records nothing it cannot resolve');
const withAuthor = posts.filter((p) => Object.prototype.hasOwnProperty.call(p, 'author'));
ok('no post carries an EMPTY author key (absence is absence, not "")',
   withAuthor.every((p) => typeof p.author === 'string' && p.author.trim() !== ''),
   JSON.stringify(withAuthor.filter((p) => !String(p.author || '').trim()).map((p) => p.filename)));
ok(`every recorded author (${withAuthor.length} of ${posts.length} posts) is in the registry`,
   withAuthor.every((p) => Object.prototype.hasOwnProperty.call(reg.authors, p.author)),
   JSON.stringify(withAuthor.filter((p) => !reg.authors[p.author]).map((p) => p.author)));

console.log('\nthe colophon is ONE sentence, from one source');
// Accountability never varies here -- it is always Pip, including for work done under his
// direction -- so it is a standing sentence rather than a field repeated on every post.
// It is served as static HTML (so a failed fetch cannot remove an accountability
// statement) and mirrored in the registry (so an agent reading the site can find it).
// Two copies of a promise is one copy too many unless something enforces they are equal.
const colophon = reg.colophon.trim();
for (const [label, file] of [['post.html', POST_HTML], ['index.html', LIST_HTML]]) {
  const src = fs.readFileSync(file, 'utf8');
  const hits = src.split(colophon).length - 1;
  ok(label + ' carries the registry colophon, character-identical', hits >= 1,
     'not found; page says: ' + ((src.match(/<footer class="colophon">([\s\S]{0,220})/) || [])[1] || '(no colophon footer)').trim());
  ok(label + ' carries it exactly once', hits === 1, 'found ' + hits + ' times');
}
ok('the colophon names who is accountable and for what',
   /mistakes/i.test(colophon) && /approval/i.test(colophon), colophon);
ok('FORCED FAILURE: the same check REJECTS a page that does not carry it',
   ('<footer class="colophon">something else entirely</footer>').split(colophon).length - 1 === 0);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
