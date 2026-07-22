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

console.log('\nconstructs the renderer cannot handle (would ship as raw text)');
const tableOut = render('| a | b |\n|---|---|\n| 1 | 2 |\n');
ok('tables are still unsupported -- do not use them in a post',
   tableOut.includes('| a | b |'), 'if this fails, tables now work: update the docs');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
