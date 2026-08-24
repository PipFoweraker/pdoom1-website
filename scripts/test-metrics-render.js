// Extracts the renderer from public/metrics/index.html and runs it against a
// minimal DOM/fetch shim. Modelled on scripts/test-changelog-render.js.
//
// WHY EVERY CASE BELOW IS A *FORCED FAILURE*
// ------------------------------------------
// /metrics/ publishes numbers about the site to the site's own readers, and its
// whole claim is that it will say "I don't know" rather than show something
// comforting. CLAUDE.md: "A guard seen only in its passing state has not been
// shown to work" -- so nothing here checks the happy path and stops. Each
// degradation is forced and observed:
//
//   - the fetch fails                -> an honest error, and NO number appears
//   - the snapshot carries `errors`  -> surfaced, not swallowed
//   - `missing_dates` is non-empty   -> rendered as a gap, never smoothed
//   - a gap sits inside the series   -> a hatched hole, distinguishable from a
//                                       recorded zero, which is also drawn
//   - two snapshots disagree         -> published as disputed, not resolved
//   - a hostile string in `sources`  -> inert text
//   - a string where a number belongs-> the section still renders
//
// The static page is also asserted to carry no traffic figure of its own. A
// literal there would ship precisely when the fetch failed -- CLAUDE.md,
// "Fallback literals are the dangerous ones."

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PAGE = path.join(ROOT, 'public', 'metrics', 'index.html');
const src = fs.readFileSync(PAGE, 'utf8');
const SHARED = require(path.join(ROOT, 'public', 'assets', 'js', 'escape.js'));

// The renderer is the last inline <script> on the page.
const scripts = [...src.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const code = scripts[scripts.length - 1];
if (!code || !code.includes('renderSeries')) {
  console.error('FAIL: could not extract the metrics renderer from the page');
  process.exit(1);
}

let failures = 0;
const check = (cond, msg) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + msg);
  if (!cond) failures++;
};

// --- DOM shim -----------------------------------------------------------------
// Every id the page addresses. A typo'd id in the page would otherwise be
// invisible here AND in the browser, so the shim records which ids were asked
// for and the test asserts they all exist in the markup.
const IDS = [
  'window-line', 'latest-failure', 'latest-errors',
  't-visitors', 't-pageviews', 't-visits', 't-duration', 't-bounce',
  'series-line', 'series-failure', 'chart', 'chart-legend', 'chart-scroller',
  'series-caveats', 'series-table', 'series-table-wrap',
  'breakdown-failure', 't-sources', 'sources-note', 't-pages', 't-countries', 't-goals',
  'archive-line', 'archive-failure', 't-archive', 'archive-wrap',
];

// The site's ONE staleness gate. renderLatest() calls Freshness.assess() on the
// snapshot's own capture stamp, so the tiles cannot render a 30-day window that
// has drifted into the past without saying so.
const FRESHNESS = require(path.join(ROOT, 'public', 'assets', 'js', 'freshness.js'));

function makeDoc() {
  const els = {};
  for (const id of IDS) {
    els[id] = {
      id,
      innerHTML: '',
      textContent: '',
      hidden: true,
      classes: new Set(['unknown']),
      classList: {
        add(c) { els[id].classes.add(c); },
        remove(c) { els[id].classes.delete(c); },
      },
    };
  }
  return {
    els,
    readyState: 'complete',
    getElementById(id) { return els[id] || null; },
    addEventListener() {},
  };
}

// Everything the page put on the screen, in one string. "No number is rendered"
// has to be asked of the WHOLE page, not of one element -- a stale figure that
// leaked into a caption would pass an element-scoped assertion.
function rendered(document) {
  return Object.values(document.els)
    .map((e) => String(e.innerHTML) + ' ' + String(e.textContent))
    .join('\n');
}

function makeFetch({ latest, latestFails, latestStatus, index, indexFails, indexStatus }) {
  return async (url) => {
    if (url.includes('latest.json')) {
      if (latestFails) throw new TypeError('Failed to fetch');
      if (latestStatus) return { ok: false, status: latestStatus, json: async () => ({}) };
      return { ok: true, status: 200, json: async () => latest };
    }
    if (url.includes('index.json')) {
      if (indexFails) throw new TypeError('Failed to fetch');
      if (indexStatus) return { ok: false, status: indexStatus, json: async () => ({}) };
      return { ok: true, status: 200, json: async () => index };
    }
    return { ok: false, status: 404, json: async () => ({}) };
  };
}

async function run(opts) {
  const document = makeDoc();
  // escapeHTML/toNumber are the shared public/assets/js/escape.js, loaded on the
  // page by a blocking <script src>. Passing them in is the node-side equivalent
  // of that tag; without them the renderer throws ReferenceError, which is the
  // page's intended fail-closed behaviour rather than a test artefact.
  // Freshness is public/assets/js/freshness.js -- the site's ONE staleness gate,
  // loaded on the page by a second blocking <script src>. Same reasoning as the
  // escaper above: without it renderLatest() throws ReferenceError, which is the
  // page's intended fail-closed behaviour rather than a test artefact.
  new Function('document', 'fetch', 'escapeHTML', 'safeUrl', 'safeUrlRaw', 'isSafeUrl', 'toNumber', 'Freshness', code)(
    document, makeFetch(opts),
    SHARED.escapeHTML, SHARED.safeUrl, SHARED.safeUrlRaw, SHARED.isSafeUrl, SHARED.toNumber,
    FRESHNESS);
  for (let i = 0; i < 30; i++) await new Promise((r) => setTimeout(r, 0));
  return { document, html: rendered(document) };
}

// --- fixtures -----------------------------------------------------------------
// Synthetic and deliberately unlike the real data, so a passing assertion proves
// the value came from the fixture rather than from the page.
const MAGIC = 7654321;          // no real traffic figure will ever be this
const MAGIC_TEXT = '7,654,321';

// NOTE (2026-08-25): these dates are deliberately far-future so no real snapshot
// can ever match them. renderLatest() now runs Freshness.assess() over
// captured_at_utc, so every fixture below ALSO renders a FUTURE-DATED banner into
// #latest-errors -- correct behaviour for a record dated 2099, and harmless to the
// assertions here, which look for their own MAGIC strings rather than for an empty
// container. The freshness gate's own four states are forced in
// scripts/test-manufactured-confidence.js, section D.
const LATEST = {
  schema: 2,
  snapshot_date: '2099-02-03',
  captured_at_utc: '2099-02-03T01:02:03+00:00',
  sections: {
    aggregate: {
      results: {
        visitors: { value: MAGIC },
        pageviews: { value: 8888 },
        visits: { value: 999 },
        visit_duration: { value: 95 },
        bounce_rate: { value: 42 },
      },
    },
    sources: { results: [{ source: 'DuckDuckGo', visitors: 12 }] },
    pages: { results: [{ page: '/dashboard/', pageviews: 21, visitors: 19 }] },
    countries: { results: [{ country: 'AU', visitors: 28 }] },
    goals: { results: [{ goal: 'Download', events: 4, visitors: 4 }] },
  },
  errors: {},
  coverage: {
    days_returned: 30,
    first_date: '2099-01-05',
    last_date: '2099-02-03',
    missing_dates: [],
    zero_dates: ['2099-01-06'],
    note: 'missing_dates are days the API omitted inside the span it returned; they are recorded, never interpolated',
  },
};

const INDEX = {
  schema: 1,
  snapshot_count: 3,
  latest_snapshot: '2099-02-03',
  unreadable_files: [],
  snapshots: [
    {
      snapshot_date: '2099-02-01', file: '2099-02-01.json', snapshot_schema: null,
      captured_at_utc: null, period: '30d', days_in_timeseries: 30,
      coverage: null, error_sections: [],
    },
    {
      snapshot_date: '2099-02-03', file: '2099-02-03.json', snapshot_schema: 2,
      captured_at_utc: '2099-02-03T01:02:03+00:00', period: '30d', days_in_timeseries: 30,
      coverage: {
        days_returned: 30, first_date: '2099-01-05', last_date: '2099-02-03',
        missing_dates: [], zero_dates: [], note: 'n',
      },
      error_sections: [],
    },
  ],
  series: {
    first_date: '2099-01-01',
    last_date: '2099-01-05',
    days: [
      { date: '2099-01-01', pageviews: 10, visitors: 8, snapshots: 2, conflict: false },
      { date: '2099-01-02', pageviews: 0, visitors: 0, snapshots: 2, conflict: false },
      // 2099-01-03 deliberately absent -> a gap
      { date: '2099-01-04', pageviews: 6, visitors: 5, snapshots: 1, conflict: false },
      { date: '2099-01-05', pageviews: 3, visitors: 3, snapshots: 1, conflict: false },
    ],
    gap_dates: ['2099-01-03'],
    conflict_dates: [],
    reported_missing_dates: [],
  },
};

const clone = (o) => JSON.parse(JSON.stringify(o));

// --- assertions ---------------------------------------------------------------
(async () => {
  // ==========================================================================
  console.log('The page source itself carries no traffic figure...');
  // ==========================================================================
  const visible = src
    .replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<!--[\s\S]*?-->/g, '');
  // Any run of 2+ digits in reader-facing prose. "30 days" and "one/two" are the
  // page describing its own method, so the window size is allowed by name; a
  // count of visitors, pageviews or a percentage is not.
  const NUMERIC_PROSE = /\b\d{2,}\b/g;
  const stray = (visible.replace(/<[^>]+>/g, ' ').match(NUMERIC_PROSE) || [])
    .filter((n) => n !== '30' && n !== '29');
  check(stray.length === 0,
    'no traffic figure is typed into the markup (found: ' + (stray.join(', ') || 'none') + ')');
  check(src.includes('<script src="/assets/js/escape.js"></script>'),
    'loads the ONE shared escaper');
  check(!/<script[^>]*escape\.js[^>]*(?:defer|async)/.test(src),
    'loads it BLOCKING, so the inline renderer cannot run before it');
  check(/<header>\s*(?:<!--[\s\S]*?-->)?\s*<\/header>/.test(src),
    'header is empty -- the nav comes from navigation.js, not hand-copied markup');
  check(src.includes('<script src="/assets/js/navigation.js"></script>'),
    'loads navigation.js at the end of the body');
  for (const id of IDS) {
    if (!src.includes('id="' + id + '"')) {
      check(false, 'the page defines id="' + id + '" that the renderer addresses');
    }
  }
  check(true, 'every id the renderer addresses exists in the markup');

  // ==========================================================================
  console.log('\nHappy path (both files reachable)...');
  // ==========================================================================
  let r = await run({ latest: LATEST, index: INDEX });
  check(r.document.els['t-visitors'].textContent === MAGIC_TEXT,
    'renders the visitor count it was given (' + r.document.els['t-visitors'].textContent + ')');
  check(!r.document.els['t-visitors'].classes.has('unknown'),
    'a real reading drops the "unknown" styling');
  check(r.document.els['t-bounce'].textContent === '42%', 'renders bounce rate as a percentage');
  check(r.document.els['t-duration'].textContent === '1m 35s', 'renders visit duration as a duration');
  check(r.html.includes('2099-01-05') && r.html.includes('2099-02-03'),
    'names the window it is reporting, and the snapshot it came from');
  check(r.html.includes('DuckDuckGo') && r.html.includes('/dashboard/') && r.html.includes('Download'),
    'renders the sources, pages and goals breakdowns');
  check(r.html.includes('<svg'), 'draws a chart');
  check(r.document.els['chart-legend'].hidden === false,
    'shows the legend -- two series are never distinguished by colour alone');
  check(r.document.els['series-table-wrap'].hidden === false,
    'exposes the same numbers as a table');
  check(r.html.includes('never interpolated'),
    'surfaces coverage.note to the reader instead of leaving it in the JSON');
  check(/1 day\(s\) had genuinely zero traffic/.test(r.html),
    'names the recorded zero as a recorded zero');

  // ==========================================================================
  console.log('\nFORCED: the snapshot fetch throws (offline / DNS / CORS)...');
  // ==========================================================================
  r = await run({ latestFails: true, index: INDEX });
  check(/Couldn’t load the latest analytics snapshot/.test(r.html), 'says plainly that it failed');
  check(/Failed to fetch/.test(r.html), 'reports why');
  check(!r.html.includes(MAGIC_TEXT) && !r.html.includes(String(MAGIC)),
    'renders NO figure from the fixture');
  check(r.document.els['t-visitors'].textContent === '' ||
        r.document.els['t-visitors'].textContent === '—',
    'the visitor tile is left showing an em dash, never a remembered number');
  check(r.document.els['t-visitors'].classes.has('unknown'),
    'and it keeps the muted "unknown" styling so it cannot read as a measurement');
  check(r.html.includes('<svg'),
    'the chart still renders -- losing one file does not blank the other section');

  // ==========================================================================
  console.log('\nFORCED: the snapshot fetch 404s (file never deployed)...');
  // ==========================================================================
  r = await run({ latestStatus: 404, index: INDEX });
  check(/HTTP 404/.test(r.html), 'reports the status code');
  check(!r.html.includes(MAGIC_TEXT), 'still shows no number');

  // ==========================================================================
  console.log('\nFORCED: the index fetch fails...');
  // ==========================================================================
  r = await run({ latest: LATEST, indexStatus: 500 });
  check(/Couldn’t load the snapshot index/.test(r.html), 'says the series could not be read');
  check(/HTTP 500/.test(r.html), 'reports why');
  check(!r.html.includes('<svg'), 'draws no chart rather than an empty or invented one');
  check(r.document.els['t-visitors'].textContent === MAGIC_TEXT,
    'the tiles still render -- the two fetches degrade independently');

  // ==========================================================================
  console.log('\nFORCED: the snapshot recorded failed sections...');
  // ==========================================================================
  const withErrors = clone(LATEST);
  withErrors.errors = { countries: 'HTTP 502 from the stats API', goals: 'timeout after 30s' };
  r = await run({ latest: withErrors, index: INDEX });
  check(/failed section/.test(r.html), 'surfaces that the snapshot itself was incomplete');
  check(r.html.includes('countries') && r.html.includes('HTTP 502 from the stats API'),
    'names which section failed and what it said');
  check(r.html.includes('timeout after 30s'), 'names the second one too, not just the first');

  // ==========================================================================
  console.log('\nFORCED: missing_dates is non-empty...');
  // ==========================================================================
  const withMissing = clone(LATEST);
  withMissing.coverage.missing_dates = ['2099-01-11', '2099-01-12'];
  r = await run({ latest: withMissing, index: INDEX });
  check(/2 day\(s\) missing from this window/.test(r.html), 'counts the missing days');
  check(r.html.includes('2099-01-11') && r.html.includes('2099-01-12'), 'names them');
  check(/Recorded, not filled in/.test(r.html), 'says they are not filled in');

  // ==========================================================================
  console.log('\nFORCED: a gap sits inside the daily series...');
  // ==========================================================================
  r = await run({ latest: LATEST, index: INDEX });
  check(/1 day\(s\) have no record at all/.test(r.html), 'counts the gap');
  check(r.html.includes('2099-01-03'), 'names the missing date');
  check(/no data recorded for this day/.test(r.html),
    'the gap carries its own label in the chart');
  check(r.html.includes('url(#hatch-gap)'),
    'the gap is drawn with a texture, not distinguished by colour alone');
  check(/a recorded zero, not a gap/.test(r.html),
    'and the recorded zero on 2099-01-02 is labelled as DIFFERENT from that gap');
  // The structural version of the same claim: the gap day and the zero day must
  // not produce the same markup. If they ever did, the page would be smoothing.
  const gapMark = r.html.indexOf('url(#hatch-gap)');
  const zeroMark = r.html.indexOf('a recorded zero, not a gap');
  check(gapMark !== -1 && zeroMark !== -1 && gapMark !== zeroMark,
    'a gap and a zero render as two different things');
  check(/>no record</.test(r.html) && />recorded</.test(r.html),
    'the table distinguishes "no record" from "recorded" per day');

  // ==========================================================================
  console.log('\nFORCED: two snapshots disagree about a day...');
  // ==========================================================================
  const disputed = clone(INDEX);
  // The values are left POPULATED on purpose even though conflict is true. The
  // generator nulls them, but the page must not be relying on that: a disputed
  // day is unpublishable whatever else the record carries, and this is the only
  // way to see the page make that decision rather than inherit it.
  disputed.series.days[0] = {
    date: '2099-01-01', pageviews: 10, visitors: 8, snapshots: 2, conflict: true,
  };
  disputed.series.conflict_dates = [{
    date: '2099-01-01',
    values: [
      { pageviews: 10, visitors: 8, snapshots: ['2099-02-01'] },
      { pageviews: 11, visitors: 9, snapshots: ['2099-02-03'] },
    ],
  }];
  r = await run({ latest: LATEST, index: disputed });
  check(/1 day\(s\) are disputed between snapshots/.test(r.html), 'says the day is disputed');
  check(/cannot tell you which is right/.test(r.html), 'admits it cannot resolve it');
  check(r.html.includes('url(#hatch-conflict)'), 'draws it as disputed rather than as a value');
  check(/>disputed</.test(r.html), 'the table marks the day disputed');
  // The load-bearing one: find the disputed day's own table row and assert it
  // carries no figure at all. Neither competing value may be presented as the
  // answer, and "10" was sitting right there in the record for it to grab.
  const rows = r.document.els['series-table'].innerHTML.match(/<tr>[\s\S]*?<\/tr>/g) || [];
  const disputedRow = rows.find((row) => row.includes('2099-01-01')) || '';
  check(disputedRow !== '', 'the disputed day still appears in the table (it is not dropped)');
  check(!/>\s*(?:10|8)\s*</.test(disputedRow),
    'neither competing value is published for it (row: ' +
      disputedRow.replace(/<[^>]+>/g, '|').replace(/\|+/g, '|') + ')');
  check((disputedRow.match(/—/g) || []).length === 2,
    'both of its numeric cells render as em dashes');

  // ==========================================================================
  console.log('\nThe one editorial line is DERIVED, so it states whichever way round it is...');
  // ==========================================================================
  // It reads "DuckDuckGo beats Google" today. Typed as prose that becomes false
  // the week Google overtakes and nobody notices, because prose does not fail.
  // Both directions are forced here; neither is in the page source.
  const ddgAhead = clone(LATEST);
  ddgAhead.sections.sources.results = [
    { source: 'Direct / None', visitors: 114 },
    { source: 'DuckDuckGo', visitors: 12 },
    { source: 'Google', visitors: 10 },
  ];
  r = await run({ latest: ddgAhead, index: INDEX });
  check(/DuckDuckGo sends more people here than Google/.test(r.html),
    'says DuckDuckGo is ahead when it is');
  check(/biggest referrer is <strong>DuckDuckGo/.test(r.html),
    'and names it as the top non-direct source (direct traffic is set aside, not counted as a referrer)');

  const googAhead = clone(ddgAhead);
  googAhead.sections.sources.results = [
    { source: 'Direct / None', visitors: 114 },
    { source: 'Google', visitors: 40 },
    { source: 'DuckDuckGo', visitors: 12 },
  ];
  r = await run({ latest: googAhead, index: INDEX });
  check(/Google is ahead of DuckDuckGo/.test(r.html), 'and says the reverse when the reverse is true');
  check(!/DuckDuckGo sends more people/.test(r.html), 'without also asserting the old direction');
  // In the STATIC markup, not in the script -- the comparison code must obviously
  // name both. What must not exist is a sentence in the page asserting an outcome
  // before the data has been read.
  //
  // Scoped rather than a blanket ban on the word "Google": the page legitimately
  // says the analytics is self-hosted Plausible and "not Google", which is a
  // statement about our own stack and cannot rot from traffic moving.
  check(!/duckduckgo/i.test(visible),
    'DuckDuckGo is not named in the page\'s own static prose');
  check(!/(sends more|ahead of|more people here|beats)/i.test(visible),
    'no static sentence asserts which referrer is winning');

  const noSources = clone(LATEST);
  noSources.sections.sources.results = [{ source: 'Direct / None', visitors: 5 }];
  r = await run({ latest: noSources, index: INDEX });
  check(!/biggest referrer/.test(r.html),
    'and says nothing at all when direct traffic is the only source');

  // ==========================================================================
  console.log('\nFORCED: hostile strings in externally-sourced fields...');
  // ==========================================================================
  const hostile = clone(LATEST);
  hostile.sections.sources.results = [
    { source: '<img src=x onerror=alert(1)>', visitors: 3 },
    { source: '" onmouseover="alert(1)', visitors: 2 },
    { source: '</td></tr><tr><td>injected', visitors: 1 },
  ];
  hostile.sections.pages.results = [{ page: '<script>alert(1)</script>', pageviews: 1, visitors: 1 }];
  hostile.errors = { sources: '<svg onload=alert(1)>' };
  r = await run({ latest: hostile, index: INDEX });
  const tables = r.document.els['t-sources'].innerHTML + r.document.els['t-pages'].innerHTML +
                 r.document.els['latest-errors'].innerHTML;
  check(!tables.includes('<img src=x'), 'the img payload does not survive as markup');
  check(!tables.includes('<script>alert(1)</script>'), 'the script payload does not survive as markup');
  check(!tables.includes('<svg onload'), 'the svg payload in errors does not survive as markup');
  check(tables.includes('&lt;img src=x onerror=alert(1)&gt;'), 'it renders as visible inert text');
  check(tables.includes('&quot;') || !tables.includes('" onmouseover="'),
    'the attribute-context payload is quote-escaped');
  // Structural: after removing the markup the renderer is entitled to emit, no
  // angle bracket or quote may survive. Deliberately not a search for handler
  // names -- escaping leaves the letters of "onerror" in place and inert.
  const residue = tables
    .replace(/<\/?(?:table|thead|tbody|tr|th|td|ul|li|div|code|strong|span)(?:\s[^>]*)?>/g, '')
    .replace(/&(?:amp|lt|gt|quot|#39);/g, '');
  check(!/[<>"']/.test(residue),
    'nothing broke out of the cell (residue: ' + residue.replace(/\s+/g, ' ').slice(0, 60) + ')');

  // ==========================================================================
  console.log('\nFORCED: a string where a number belongs...');
  // ==========================================================================
  // `entry.count.toLocaleString()` throws a TypeError on a string, and one throw
  // inside a render loop takes down the WHOLE section, not one row. `|| 0` does
  // not save it: a non-empty string is truthy and String.toLocaleString is the
  // identity function.
  const stringy = clone(LATEST);
  stringy.sections.aggregate.results.visitors = { value: 'not a number' };
  stringy.sections.aggregate.results.pageviews = { value: '8888' };
  stringy.sections.sources.results = [{ source: 'Bing', visitors: 'lots' }];
  const stringyIdx = clone(INDEX);
  stringyIdx.series.days[0].pageviews = 'twelve';
  stringyIdx.snapshot_count = 'three';
  r = await run({ latest: stringy, index: stringyIdx });
  check(r.html.includes('Bing'), 'the sources table still renders (no section-wide throw)');
  check(r.document.els['t-visitors'].textContent === '—',
    'an unparseable count renders as an em dash, not as "not a number" and not as 0');
  check(r.document.els['t-visitors'].classes.has('unknown'),
    'and it is styled as unknown rather than as a measurement');
  check(r.document.els['t-pageviews'].textContent === '8,888',
    'a numeric STRING is still a number and is coerced, not discarded');
  check(r.html.includes('<svg'), 'the chart still draws with a junk value in the series');

  // ==========================================================================
  console.log('\nFORCED: the snapshot predates the coverage block...');
  // ==========================================================================
  const noCoverage = clone(LATEST);
  delete noCoverage.coverage;
  r = await run({ latest: noCoverage, index: INDEX });
  check(/unrecorded/.test(r.html), 'absence of coverage renders as UNRECORDED');
  check(/not the same as none/.test(r.html),
    'and explicitly not as a clean bill of health');
  check(/not recorded/.test(r.html), 'the window line says the range is not recorded');
  // The archive table gets the same treatment for its own null-coverage row.
  check(r.document.els['t-archive'].innerHTML.includes('not recorded'),
    'the archive row for a pre-schema-2 snapshot says "not recorded", not "0"');

  // ==========================================================================
  console.log('\nFORCED: an empty / degenerate index...');
  // ==========================================================================
  r = await run({ latest: LATEST, index: { schema: 1, snapshots: [], series: {} } });
  check(/no daily records yet/.test(r.html), 'an empty series says so rather than drawing an empty chart');
  check(!r.html.includes('<svg'), 'and draws nothing');
  check(r.document.els['t-visitors'].textContent === MAGIC_TEXT, 'the tiles are unaffected');

  // ==========================================================================
  console.log('\nFORCED: a long archive (the state this page reaches by waiting)...');
  // ==========================================================================
  // The archive grows by one day per day and never shrinks, so "it fits today"
  // is not a property -- it is a coincidence with an expiry date. 600 days is
  // roughly where this page is in two years.
  const long = clone(INDEX);
  long.series.days = [];
  long.series.gap_dates = [];
  const start = Date.UTC(2099, 0, 1);
  for (let i = 0; i < 600; i++) {
    const iso = new Date(start + i * 86400000).toISOString().slice(0, 10);
    if (i % 97 === 0) { long.series.gap_dates.push(iso); continue; }
    long.series.days.push({ date: iso, pageviews: i % 40, visitors: i % 31, snapshots: 1, conflict: false });
  }
  r = await run({ latest: LATEST, index: long });
  const svg = (r.document.els['chart'].innerHTML.match(/<svg[^>]*width="(\d+)"/) || [])[1];
  check(svg !== undefined, 'still draws a chart at 600 days');
  check(Number(svg) <= 4000,
    'the chart width stays bounded rather than growing without limit (' + svg + 'px)');
  // A fixed pixel inset (SLOT - 12) goes NEGATIVE once slots thin out, and a
  // negative width is an SVG error that renders nothing at all.
  const widths = [...r.document.els['chart'].innerHTML.matchAll(/\bwidth="(-?[\d.]+)"/g)].map((m) => Number(m[1]));
  check(widths.length > 0 && widths.every((w) => w > 0),
    'no mark has a zero or negative width (min ' + Math.min.apply(null, widths) + ')');
  check(r.html.includes('url(#hatch-gap)'), 'gaps are still drawn at that density');

  // ==========================================================================
  console.log('\nFORCED: an unreadable snapshot file was skipped...');
  // ==========================================================================
  const unreadable = clone(INDEX);
  unreadable.unreadable_files = [{ file: '2099-01-09.json', error: 'Expecting value: line 1 column 1' }];
  r = await run({ latest: LATEST, index: unreadable });
  check(/could not be read/.test(r.html), 'a corrupt snapshot is reported, not silently dropped');
  check(r.html.includes('2099-01-09.json'), 'and named');

  console.log('\n' + (failures ? failures + ' FAILURE(S)' : 'All metrics render tests passed.'));
  process.exit(failures ? 1 : 0);
})();
