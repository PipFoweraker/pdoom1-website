#!/usr/bin/env node
/**
 * Sitemap generator for pdoom1.com.
 *
 * Enumerates the real pages under public/ instead of carrying a hardcoded route
 * list. Before 2026-07-28 this shipped 15 URLs out of ~2,244 pages, so the
 * ~2,196 event pages -- the entire long-tail indexable content -- were invisible
 * to search engines (TECH_DEBT B3).
 *
 * Rules enforced here, each with a reason:
 *
 *  1. Anything robots.txt disallows is excluded. Listing a disallowed URL in a
 *     sitemap is a contradiction that Search Console reports as an error, and
 *     the old sitemap did exactly that for /changelog/. robots.txt is PARSED,
 *     not duplicated here, so the two files cannot drift apart.
 *  2. Anything carrying <meta name="robots" content="noindex"> is excluded, for
 *     the same reason.
 *  3. HTML fragments that are not pages (public/includes/*, the steam badge
 *     template) are excluded via NON_PAGE_FILES.
 *  4. <lastmod> comes from git commit dates -- real data. When git cannot
 *     supply one (shallow clone, no git, untracked file) the element is OMITTED
 *     rather than filled with today's date. A fabricated lastmod is worse than
 *     none: it claims 2,200 pages changed today, on every deploy.
 *     Blog posts take lastmod from public/blog/index.json, which is real data
 *     that survives a shallow checkout.
 *  5. The only routes dropped relative to the old hardcoded list are the five
 *     /docs/*.md entries. DreamHost serves markdown as a download rather than a
 *     page (TECH_DEBT B8), so they were never indexable content.
 *
 * NOTE for CI: actions/checkout defaults to fetch-depth 1. Under a shallow
 * checkout every git date would be the deploy commit's date, so this script
 * detects shallowness and drops lastmod entirely instead of lying. Setting
 * `fetch-depth: 0` on the checkout step of the deploy workflows would restore
 * real lastmod values in production.
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const BASE_URL = 'https://pdoom1.com';
const REPO_ROOT = path.join(__dirname, '..');
const PUBLIC_DIR = path.join(REPO_ROOT, 'public');
const SITEMAP_PATH = path.join(PUBLIC_DIR, 'sitemap.xml');
const ROBOTS_PATH = path.join(PUBLIC_DIR, 'robots.txt');
const BLOG_INDEX_PATH = path.join(PUBLIC_DIR, 'blog', 'index.json');

// Sitemap protocol hard limits. Over either, a sitemap index is required.
const MAX_URLS = 50000;
const MAX_BYTES = 50 * 1024 * 1024;

// HTML files under public/ that are not pages: fragments injected into other
// documents, each of which renders as a styleless orphan if visited directly.
const NON_PAGE_FILES = new Set([
  'includes/navigation.html',
  'includes/analytics.html',
  'assets/steam-badge-template.html',
  // The client-side blog renderer. Visited without ?p= it shows "post not
  // found". The real post URLs are added from blog/index.json below.
  'blog/post.html',
]);

// Curated hints preserved from the previous hardcoded list. Google ignores both
// fields; they are kept so prior editorial intent is not silently dropped.
// Pages not listed here get neither field rather than an invented one.
const CURATED = {
  '/': { priority: '1.0', changefreq: 'weekly' },
  '/about/': { priority: '0.9', changefreq: 'monthly' },
  '/blog/': { priority: '0.8', changefreq: 'weekly' },
  '/press/': { priority: '0.8', changefreq: 'monthly' },
  '/leaderboard/': { priority: '0.8', changefreq: 'daily' },
  '/privacy/': { priority: '0.7', changefreq: 'monthly' },
  '/resources/': { priority: '0.7', changefreq: 'monthly' },
  '/game-stats/': { priority: '0.7', changefreq: 'weekly' },
  '/docs/': { priority: '0.7', changefreq: 'weekly' },
};

// ---------------------------------------------------------------------------
// robots.txt
// ---------------------------------------------------------------------------

/**
 * Parse the `User-agent: *` group out of robots.txt.
 * Returns { allow: [paths], disallow: [paths] }.
 */
function parseRobots(text) {
  const allow = [];
  const disallow = [];
  let inStar = false;
  let sawDirective = false;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/#.*$/, '').trim();
    if (!line) continue;
    const idx = line.indexOf(':');
    if (idx === -1) continue;
    const field = line.slice(0, idx).trim().toLowerCase();
    const value = line.slice(idx + 1).trim();

    if (field === 'user-agent') {
      // A user-agent line following directives starts a new group.
      if (sawDirective) {
        inStar = false;
        sawDirective = false;
      }
      if (value === '*') inStar = true;
      continue;
    }
    if (field !== 'allow' && field !== 'disallow') continue;
    sawDirective = true;
    if (!inStar || !value) continue;
    (field === 'allow' ? allow : disallow).push(value);
  }
  return { allow, disallow };
}

/**
 * Google's longest-match rule: the most specific matching directive wins, and
 * Allow wins ties. Prefix matching only -- wildcards are not supported, so warn
 * loudly rather than silently mis-classifying a URL.
 */
function makeRobotsFilter(rules) {
  const wildcarded = [...rules.allow, ...rules.disallow].filter((p) => /[*$]/.test(p));
  if (wildcarded.length) {
    console.warn(
      'WARNING: robots.txt contains wildcard patterns this parser does not ' +
      'understand: ' + wildcarded.join(', ') + '. Sitemap exclusion may be wrong.'
    );
  }
  return function isDisallowed(urlPath) {
    let bestAllow = -1;
    let bestDisallow = -1;
    for (const p of rules.allow) {
      if (urlPath.startsWith(p) && p.length > bestAllow) bestAllow = p.length;
    }
    for (const p of rules.disallow) {
      if (urlPath.startsWith(p) && p.length > bestDisallow) bestDisallow = p.length;
    }
    return bestDisallow > bestAllow;
  };
}

// ---------------------------------------------------------------------------
// lastmod from git
// ---------------------------------------------------------------------------

const GIT_MARK = '@@';

/**
 * One `git log` pass over public/, newest commit first. The first date seen for
 * a path is that file's last modification. Returns Map<repoRelPath, YYYY-MM-DD>
 * or null when git cannot give a trustworthy answer.
 */
function gitLastModMap() {
  const git = (args) =>
    execFileSync('git', args, {
      cwd: REPO_ROOT,
      encoding: 'utf8',
      maxBuffer: 512 * 1024 * 1024,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

  try {
    if (git(['rev-parse', '--is-shallow-repository']).trim() === 'true') {
      console.warn(
        'WARNING: shallow git clone -- every file would report the same commit ' +
        'date, so <lastmod> is omitted entirely. Set fetch-depth: 0 on the ' +
        'checkout step to restore real dates.'
      );
      return null;
    }
  } catch (err) {
    console.warn('WARNING: git unavailable (' + String(err.message).trim() + '); <lastmod> omitted.');
    return null;
  }

  let out;
  try {
    out = git([
      '-c', 'core.quotepath=false',
      'log', '--pretty=format:' + GIT_MARK + '%cI', '--name-only', '--', 'public',
    ]);
  } catch (err) {
    console.warn('WARNING: git log failed (' + String(err.message).trim() + '); <lastmod> omitted.');
    return null;
  }

  const map = new Map();
  let current = null;
  for (const line of out.split('\n')) {
    if (line.startsWith(GIT_MARK)) {
      current = line.slice(GIT_MARK.length).trim().split('T')[0];
      continue;
    }
    const file = line.trim();
    if (!file || !current) continue;
    if (!map.has(file)) map.set(file, current);
  }
  return map;
}

/**
 * Last-known-good fallback: read <lastmod> values out of the sitemap.xml that
 * is already committed. Used only when git cannot supply dates (the shallow-CI
 * case). CLAUDE.md's rule is to preserve the last known-good value rather than
 * substitute a literal, and a stale-but-true date beats today's date on 2,200
 * pages. Returns Map<absoluteUrl, YYYY-MM-DD>.
 */
function existingLastModMap() {
  const map = new Map();
  if (!fs.existsSync(SITEMAP_PATH)) return map;
  const xml = fs.readFileSync(SITEMAP_PATH, 'utf8');
  const re = /<url>\s*<loc>([^<]+)<\/loc>\s*<lastmod>([^<]+)<\/lastmod>/g;
  let m;
  while ((m = re.exec(xml)) !== null) {
    map.set(m[1], m[2].trim());
  }
  return map;
}

// ---------------------------------------------------------------------------
// Page discovery
// ---------------------------------------------------------------------------

function walkHtml(dir, out) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkHtml(full, out);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.html')) {
      out.push(full);
    }
  }
  return out;
}

const NOINDEX_RE = /<meta[^>]+name=["']robots["'][^>]*content=["'][^"']*noindex/i;

function hasNoindex(absPath) {
  // The meta tag lives in <head>; reading the first 16 KB is enough and keeps
  // this cheap across ~2,200 files.
  const fd = fs.openSync(absPath, 'r');
  try {
    const buf = Buffer.alloc(16384);
    const read = fs.readSync(fd, buf, 0, buf.length, 0);
    return NOINDEX_RE.test(buf.slice(0, read).toString('utf8'));
  } finally {
    fs.closeSync(fd);
  }
}

/** public/about/index.html -> /about/ ; public/stats/x.html -> /stats/x.html */
function toUrlPath(relPosix) {
  if (relPosix === 'index.html') return '/';
  if (relPosix.endsWith('/index.html')) return '/' + relPosix.slice(0, -'index.html'.length);
  return '/' + relPosix;
}

function xmlEscape(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function collectUrls() {
  const robots = parseRobots(fs.readFileSync(ROBOTS_PATH, 'utf8'));
  const isDisallowed = makeRobotsFilter(robots);
  const lastmods = gitLastModMap();
  // Consulted only when git could not answer, and only for URLs git did not
  // cover; never used to overwrite a real git date.
  const previous = lastmods ? null : existingLastModMap();
  if (previous) {
    console.warn('Preserving ' + previous.size + ' <lastmod> values from the committed sitemap.xml.');
  }

  const stats = { total: 0, fragments: 0, disallowed: 0, noindex: 0 };
  const urls = [];
  const seen = new Set();

  const add = (urlPath, lastmod) => {
    if (seen.has(urlPath)) return;
    seen.add(urlPath);
    const entry = { path: urlPath };
    if (!lastmod && previous) {
      lastmod = previous.get(xmlEscape(BASE_URL + urlPath)) || null;
    }
    if (lastmod) entry.lastmod = lastmod;
    const curated = CURATED[urlPath];
    if (curated) Object.assign(entry, curated);
    urls.push(entry);
  };

  for (const abs of walkHtml(PUBLIC_DIR, []).sort()) {
    stats.total += 1;
    const rel = path.relative(PUBLIC_DIR, abs).split(path.sep).join('/');
    if (NON_PAGE_FILES.has(rel)) {
      stats.fragments += 1;
      continue;
    }
    const urlPath = toUrlPath(rel);
    if (isDisallowed(urlPath)) {
      stats.disallowed += 1;
      continue;
    }
    if (hasNoindex(abs)) {
      stats.noindex += 1;
      continue;
    }
    add(urlPath, lastmods ? lastmods.get('public/' + rel) : null);
  }

  // Blog posts are markdown rendered client-side by /blog/post.html?p=<file>,
  // which sets document.title per post. Publication dates in index.json are
  // real data, so these carry lastmod even under a shallow checkout.
  if (!isDisallowed('/blog/post.html') && fs.existsSync(BLOG_INDEX_PATH)) {
    const index = JSON.parse(fs.readFileSync(BLOG_INDEX_PATH, 'utf8'));
    for (const post of index.posts || []) {
      if (!post.filename) continue;
      if (!fs.existsSync(path.join(PUBLIC_DIR, 'blog', post.filename))) {
        // index.json has historically listed files that do not exist. Skip and
        // report rather than publish a dead link (same policy as the feeds).
        console.warn('WARNING: blog/index.json lists a missing file: ' + post.filename);
        continue;
      }
      const lastmod = /^\d{4}-\d{2}-\d{2}$/.test(post.date || '') ? post.date : null;
      add('/blog/post.html?p=' + encodeURIComponent(post.filename), lastmod);
    }
  }

  // Homepage first: conventional, and it makes the file readable. Node's sort
  // is stable, so everything else keeps discovery order.
  urls.sort((a, b) => (a.path === '/' ? -1 : b.path === '/' ? 1 : 0));

  return { urls, stats, hasLastmod: lastmods !== null };
}

function renderSitemap(urls) {
  let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
  xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';
  for (const u of urls) {
    xml += '  <url>\n';
    xml += '    <loc>' + xmlEscape(BASE_URL + u.path) + '</loc>\n';
    if (u.lastmod) xml += '    <lastmod>' + u.lastmod + '</lastmod>\n';
    if (u.changefreq) xml += '    <changefreq>' + u.changefreq + '</changefreq>\n';
    if (u.priority) xml += '    <priority>' + u.priority + '</priority>\n';
    xml += '  </url>\n';
  }
  xml += '</urlset>\n';
  return xml;
}

function generateSitemap() {
  return renderSitemap(collectUrls().urls);
}

function main() {
  const { urls, stats, hasLastmod } = collectUrls();
  const sitemap = renderSitemap(urls);
  const bytes = Buffer.byteLength(sitemap, 'utf8');

  if (urls.length > MAX_URLS || bytes > MAX_BYTES) {
    console.error(
      'ERROR: sitemap exceeds a protocol limit (' + urls.length + ' URLs, ' +
      bytes + ' bytes; limits are ' + MAX_URLS + ' URLs / ' + MAX_BYTES +
      ' bytes). It must be split into a sitemap index before shipping.'
    );
    process.exit(1);
  }

  fs.writeFileSync(SITEMAP_PATH, sitemap, 'utf8');

  const withLastmod = urls.filter((u) => u.lastmod).length;
  console.log('Sitemap written to ' + SITEMAP_PATH);
  console.log('  URLs:                          ' + urls.length);
  console.log('  with <lastmod>:                ' + withLastmod +
    (hasLastmod ? '' : ' (git could not supply dates; preserved from the previous sitemap)'));
  console.log('  size:                          ' + (bytes / 1024).toFixed(1) + ' KB');
  console.log('  HTML files seen:               ' + stats.total);
  console.log('  skipped, not a page:           ' + stats.fragments);
  console.log('  skipped, robots.txt disallows: ' + stats.disallowed);
  console.log('  skipped, meta noindex:         ' + stats.noindex);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error('ERROR generating sitemap:', error);
    process.exit(1);
  }
}

module.exports = {
  generateSitemap,
  collectUrls,
  parseRobots,
  makeRobotsFilter,
  toUrlPath,
};
