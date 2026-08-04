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
vm.runInContext(source.replace(/^\s*(document|window)\.[\s\S]*$/m, ''), sandbox);
const render = sandbox.renderMarkdown;
const strip = sandbox.stripFrontMatter;

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

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
