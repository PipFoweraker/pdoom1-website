#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Destructive tests for scripts/sync/sync-events.py.

# WHY THIS EXISTS
# ---------------
# sync-events.py is the single largest publisher in this repo. One run writes
# ~1,194 `public/events/*.html` pages, `public/data/events.json` and
# `public/data/events-sync-summary.json`, and `sync-events.yml` runs it on a
# daily cron that COMMITS the result. Until this file it had zero tests.
#
# Two things it owns, both of which have already gone wrong on production:
#
# 1. redact_pii() -- the ONLY live guard against republishing third parties' email
#    addresses. Event descriptions are raw text extracted from paper PDFs, and
#    arXiv/ACM author blocks carry institutional addresses; 75 distinct academics'
#    addresses were served across 44 pages until 2026-07-29. The downstream
#    re-check, scripts/check-published-emails.py, is an ORPHAN -- no workflow runs
#    it (verified 2026-08-01). So if redact_pii() regresses, nothing else notices,
#    and the daily cron commits the leak straight back.
#
# 2. HTML escaping. The page is one 500-line f-string, so the data decides where
#    the markup ends, and arXiv accepts uploads from anyone. Before 2026-08-01 the
#    generator escaped NOTHING, and the shipped corpus already broke it twice:
#      * arxiv_73643a60bb86bf2f's description contains "<<number to be assigned>>",
#        parsed as a tag start in <p class="description"> and inside the
#        <meta name="description" content="..."> attribute.
#      * arxiv_aa8c44de8cf70353's description carries a double quote inside its
#        first 155 characters, which TERMINATED the meta content attribute early
#        and turned the rest of the sentence into bogus tag attributes.
#    Both were live on pdoom1.com. escape_event_for_html() is the fix; this file
#    is the evidence that it works.
#
# HOW IT ASSERTS THE RULE RATHER THAN A LIST
# ------------------------------------------
# Naming the fields to check is how the leaderboard came to escape six fields and
# leave thirteen raw (see scripts/test-board-escaping.js). So section 3 does not
# name any field. It renders the SAME event twice -- once with benign text in
# every string slot, once with a hostile payload in every string slot -- and
# requires the two documents to have an IDENTICAL tag-and-attribute skeleton. Any
# interpolation added later that forgets to escape changes the skeleton and fails
# here on the day it is added, with no list to remember to extend.
#
# Likewise section 2 puts an address in a field that does not exist in today's
# schema, because redact_pii()'s stated contract is to walk the WHOLE record.
#
# HOW IT ISOLATES
# ---------------
# Section 6 redirects the module's EVENTS_DIR / DATA_DIR / ICONS_DIR into a temp
# dir and builds a fake pdoom-data tree there, so no test touches public/ or the
# network. Nothing here clones a repo or issues an HTTP request.
#
# Run:  python scripts/test-sync-events.py     (exit 0 = pass)
"""

import importlib.util
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from html.parser import HTMLParser
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

# Import before any redirect_stdout: on win32 the module replaces sys.stdout with
# io.TextIOWrapper(sys.stdout.buffer, ...) at import time, and a StringIO has no
# .buffer, so importing under a redirect dies with AttributeError.
_spec = importlib.util.spec_from_file_location(
    "sync_events", ROOT / "scripts" / "sync" / "sync-events.py")
se = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(se)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


# --------------------------------------------------------------------------- helpers
def make_event(text, **over):
    """An event whose every string-typed slot carries `text`.

    Numeric slots stay numeric because the template does arithmetic on them
    (impact['change'] > 0) and formats event['year'] directly.
    """
    e = {
        "title": text,
        "description": text,
        "year": 2024,
        "category": text,
        "rarity": text,
        "tags": [text, text + "-two"],
        "sources": ["https://example.com/" + text, text],
        "safety_researcher_reaction": text,
        "media_reaction": text,
        "pdoom_impact": 3,
        "impacts": [{"variable": text, "change": 2, "condition": text}],
        "reaction_provenance": {
            "safety_researcher_reaction": {
                "type": "real_quote", "source": "https://example.com/" + text,
                "author": text, "date": text,
            },
            "media_reaction": {
                "type": "human_summary", "sources": ["https://example.com/" + text],
            },
        },
        # Not in today's schema on purpose. redact_pii()/escape_event_for_html()
        # both claim to walk the WHOLE record; this is the field "added upstream
        # tomorrow" that proves it, and it is serialised into events.json.
        "future_field_added_upstream": {"nested": [{"deep": text}]},
    }
    e.update(over)
    return e


class Skeleton(HTMLParser):
    """Collect (tag, sorted attribute names) for every start tag, in order.

    This is the structural fingerprint of the document. Escaped payload text
    cannot change it; injected markup always does -- whether it opens a tag or
    merely terminates an attribute early and spills new attribute names into the
    tag it was sitting in.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.seq = []

    def handle_starttag(self, tag, attrs):
        self.seq.append((tag, tuple(sorted(a for a, _ in attrs))))

    handle_startendtag = handle_starttag


def skeleton(html_text):
    p = Skeleton()
    p.feed(html_text)
    return p.seq


def all_text(value):
    """Every string anywhere in a nested structure."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from all_text(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from all_text(v)


# =========================================================================== 1
print("\n1. The email pattern matches addresses and only addresses")

# Both of these come from the real corpus and are why the pattern is shaped the
# way it is. They are behaviours, not incidental: a greedy TLD deletes a person's
# name, which is a worse outcome than the leak it was fixing.
glued = se.redact_emails_in_text("contact madry@mit.eduAleksandar Madry for details")
check("madry@mit.edu" not in glued, "PDF-glued address is removed")
check("Aleksandar Madry" in glued,
      "the next author's NAME survives a glued address -- redaction must not eat data")

check(se.redact_emails_in_text("write to mailto:a.b@cs.example.ac.uk now")
      == f"write to {se.REDACTION_MARKER} now",
      "a mailto: prefix is swallowed with the address, not left dangling")

check(se.REDACTION_MARKER in se.redact_emails_in_text("x@y.com"),
      "redaction MARKS the gap rather than silently deleting -- a silent deletion "
      "is a small lie about what the source said")

# The other direction. A pattern that eats non-addresses is a different way of
# lying about the source, and there is no downstream check that would catch it.
for benign in ("@openai mentioned it", "see fig@ 3", "n@", "a@b", "price 5@10"):
    check(se.redact_emails_in_text(benign) == benign,
          f"leaves non-address text alone: {benign!r}")

check(se.count_emails({"a": ["x@y.com", {"b": "p@q.org"}], "c": 7}) == 2,
      "count_emails walks nested structures (the sync log's number is real)")


# =========================================================================== 2
print("\n2. redact_pii walks the WHOLE record, not a field list")

ADDR = "victim@institute.example.org"
ev = make_event(f"text with {ADDR} inside")
red = se.redact_pii(ev)

leaked = [s for s in all_text(red) if "@" in s and "example.org" in s]
check(not leaked, f"no address survives anywhere in the record (leaked: {leaked[:2]})")
check(any(se.REDACTION_MARKER in s for s in all_text(red)), "the marker is present")

# The point of the whole-record contract: a field nobody has written a case for.
check(ADDR not in json.dumps(red["future_field_added_upstream"]),
      "THE BIG ONE: an unknown field added upstream tomorrow is redacted today, "
      "because redact_pii walks the record instead of enumerating fields")

check(se.redact_pii(ev) is not None and ADDR in json.dumps(ev),
      "redact_pii returns a new structure and does not mutate its input")

check(se.redact_pii(2024) == 2024 and se.redact_pii(None) is None,
      "non-string leaves pass through unchanged (year stays an int)")


# =========================================================================== 3
print("\n3. Nothing an event can say changes the shape of the page")

BENIGN = "ordinary"
HOSTILE_PAYLOADS = [
    '<script>alert(1)</script>',
    '"><img src=x onerror=alert(1)>',
    "' onmouseover='alert(1)",
    '</p></div><div class="injected">',
    '<<number to be assigned>>',              # the real arxiv_73643a60bb86bf2f string
    'Kott, "Cybertrust: From Explainable',    # the real arxiv_aa8c44de8cf70353 shape
    'Arts & Sciences',                        # bare ampersand, the real corpus case
    '&lt;already escaped&gt;',                # must not be double-unescaped
]

base = skeleton(se.generate_event_detail_page("evt_benign", make_event(BENIGN)))
check(len(base) > 20, f"baseline page parsed into {len(base)} tags")

for payload in HOSTILE_PAYLOADS:
    got = skeleton(se.generate_event_detail_page("evt_hostile", make_event(payload)))
    check(got == base,
          "page skeleton is identical with payload in every field: " + payload[:38])

# The event id reaches an href and the canonical link. It is a dict key upstream,
# so nothing validates its shape here.
for payload in HOSTILE_PAYLOADS[:4]:
    got = skeleton(se.generate_event_detail_page(payload, make_event(BENIGN)))
    check(got == base, "page skeleton survives a hostile EVENT ID: " + payload[:34])

# Structural equality is necessary but says nothing about whether the payload text
# is present at all, so pin the two ends explicitly.
hostile_html = se.generate_event_detail_page("evt", make_event('<script>alert(1)</script>'))
check("<script>alert(1)</script>" not in hostile_html, "no raw <script> reaches the page")
check("&lt;script&gt;alert(1)&lt;/script&gt;" in hostile_html,
      "the payload is still SHOWN to the reader, as inert text -- escaping is not censorship")

# The two live production defects, named.
meta_break = se.generate_event_detail_page(
    "evt", make_event('Kott, "Cybertrust: From Explainable' + " x" * 200))
check(skeleton(meta_break) == base,
      "REGRESSION arxiv_aa8c44de8cf70353: a double quote inside the first 155 "
      "characters no longer terminates the meta description attribute")
angle = se.generate_event_detail_page(
    "evt", make_event("Unite Paper 2021 <<number to be assigned>> A Framework"))
check("<<number to be assigned>>" not in angle,
      "REGRESSION arxiv_73643a60bb86bf2f: '<<...>>' is escaped, not emitted raw")

# Escaping must not silently truncate. The description is the reader-facing prose.
long_desc = "Sentence one. " * 40
page = se.generate_event_detail_page("evt", make_event(BENIGN, description=long_desc))
check(long_desc.strip() in page, "the full description still reaches the page body")

# esc() escapes & < > and the DOUBLE quote, but deliberately not the apostrophe --
# see its docstring. That exemption is only sound while every attribute in the
# template is double-quoted, so pin the precondition rather than trusting it.
# Without this, someone writing style='...' in the template silently reopens the
# hole, and only for a payload containing an apostrophe.
tmpl_src = (ROOT / "scripts" / "sync" / "sync-events.py").read_text(
    encoding="utf-8").replace("\r\n", "\n")
tmpl = tmpl_src.split("html_content = f", 1)[1]
single_quoted_attrs = re.findall(r"<[a-zA-Z][^>]*?=\'[^\']*\'", tmpl)
check(not single_quoted_attrs,
      f"every attribute in the page template is double-quoted, so esc() may leave "
      f"apostrophes alone (found {single_quoted_attrs[:2]})")
check(se.esc("it's") == "it's", "an apostrophe survives unescaped, keeping the diff honest")
check(se.esc('a "b" <c> & d') == 'a &quot;b&quot; &lt;c&gt; &amp; d',
      "the four characters that CAN end markup are all escaped")
check(se.esc("&amp;") == "&amp;amp;",
      "an ampersand is escaped even when it already looks like an entity -- otherwise "
      "text that legitimately reads '&amp;' would render as '&'")


# =========================================================================== 4
print("\n4. Redaction happens BEFORE the page is built, on every published surface")

# Ordering is the whole safety property: redacting after generation would leave
# the address in the HTML. Assert against the generator's output directly.
ev = make_event(f"author {ADDR} et al")
page = se.generate_event_detail_page("evt", se.redact_pii(ev))
check(ADDR not in page, "no address in the generated page")
check("victim@institute" not in page, "not even a partial address survives")

# ...and that an UNredacted event would have leaked, i.e. the check above is
# actually testing redaction rather than some incidental escaping.
check(ADDR in se.generate_event_detail_page("evt", ev),
      "control: without redact_pii the address DOES reach the page, so the "
      "assertion above is measuring redaction and not a coincidence")


# =========================================================================== 5
print("\n5. Filtering: an excluded event must never become a page")

allev = {
    "keep": make_event("a"),
    "news": make_event("b", event_status="newsletter_archive"),
    "gone": make_event("c", event_status="excluded"),
    "review": make_event("d", event_status="review_needed"),
}
kept = se.filter_events(allev)
check(set(kept) == {"keep", "review"},
      f"newsletter_archive and excluded are dropped, review_needed is kept (got {sorted(kept)})")
check(se.should_include_event({}) is True,
      "an event with NO event_status defaults to included -- absence is not exclusion")


# =========================================================================== 6
print("\n6. End to end in a temp dir: nothing published carries an address or a CRLF")


class Sandbox:
    """Point every write at a temp dir and hand main() a fake pdoom-data tree."""

    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = {k: getattr(se, k) for k in ("EVENTS_DIR", "DATA_DIR", "ICONS_DIR")}
        se.EVENTS_DIR = self.tmp / "events"
        se.DATA_DIR = self.tmp / "data"
        se.ICONS_DIR = self.tmp / "icons"
        src = self.tmp / "pdoom-data" / "data" / "serveable" / "api" / "timeline_events"
        src.mkdir(parents=True)
        (src / "all_events.json").write_text(
            json.dumps(self.events), encoding="utf-8")
        self.data_path = self.tmp / "pdoom-data"
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            setattr(se, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


# THE FLOOR IS REAL IN PRODUCTION AND SCOPED HERE, not weakened there.
#
# sync-events.py refuses a corpus below MIN_EVENTS (D6, pdoom1-website#384) and
# has NO override -- no flag, no environment variable -- because an override is a
# disarm switch that eventually gets used in anger. The fixtures below are four
# events on purpose: they exist to test escaping and redaction, not corpus size.
#
# So the test patches the module constant it imported, for the sections that are
# not about the floor, and restores it. Section 7 asserts the floor against
# REAL_MIN_EVENTS, so a change to the ruling is caught there rather than being
# silently satisfied by whatever this helper happens to set.
REAL_MIN_EVENTS = se.MIN_EVENTS


@contextlib.contextmanager
def floor_of(n):
    """Run a block with the corpus floor at n. Restores unconditionally."""
    before = se.MIN_EVENTS
    se.MIN_EVENTS = n
    try:
        yield
    finally:
        se.MIN_EVENTS = before


def run_main(sandbox):
    sys.argv = ["sync-events.py", "--pdoom-data-path", str(sandbox.data_path)]
    buf = io.StringIO()
    with floor_of(1), redirect_stdout(buf):
        se.main()
    return buf.getvalue()


CORPUS = {
    "evt_pii": make_event(f"Aleksandar Madry, madry@mit.eduNext Author, {ADDR}"),
    "evt_html": make_event('Report "<<draft>>" & Sons <script>alert(1)</script>'),
    "evt_plain": make_event("nothing special here"),
    "evt_dropped": make_event("newsletter body", event_status="newsletter_archive"),
}

with Sandbox(CORPUS) as sb:
    out = run_main(sb)
    written = sorted(p for p in sb.tmp.rglob("*") if p.is_file()
                     and p.parent != sb.tmp / "pdoom-data")
    pages = sorted(p.name for p in (sb.tmp / "events").glob("*.html"))

    check(pages == ["evt_html.html", "evt_pii.html", "evt_plain.html"],
          f"one page per included event, none for the excluded one (got {pages})")

    published = [p for p in written if "pdoom-data" not in p.parts]
    check(len(published) >= 5, f"wrote {len(published)} files (pages + json)")

    # THE RULE: scan every published byte, rather than the fields we thought of.
    offenders = []
    for p in published:
        body = p.read_bytes().decode("utf-8")
        if ADDR in body or "madry@mit.edu" in body:
            offenders.append(p.name + " :: address")
        if "<script>alert(1)</script>" in body and p.suffix == ".html":
            offenders.append(p.name + " :: raw script tag")
        if b"\r\n" in p.read_bytes():
            offenders.append(p.name + " :: CRLF")
    check(not offenders, f"no published file leaks an address, raw markup or CRLF "
                         f"(offenders: {offenders[:3]})")

    ejson = json.loads((sb.tmp / "data" / "events.json").read_text(encoding="utf-8"))
    check("evt_dropped" not in ejson, "events.json omits the excluded event")
    check(se.REDACTION_MARKER in json.dumps(ejson),
          "events.json carries the redaction marker, so the gap is visible in the data too")
    check("&lt;" not in json.dumps(ejson),
          "events.json holds the ORIGINAL text, not HTML entities -- escaping is a "
          "property of the page, and entity-encoding the JSON would corrupt every "
          "consumer that renders it with textContent")

    summary = json.loads(
        (sb.tmp / "data" / "events-sync-summary.json").read_text(encoding="utf-8"))
    check(summary["total_events_in_source"] == 4 and summary["included_events"] == 3,
          "the summary counts what actually happened, not what was asked for")
    check("Redacted" in out, "the run says out loud that it redacted something")


# =========================================================================== 7
print("\n7. Missing source data is a hard stop, not a quiet empty publish")

# Publishing zero events would delete nothing (rsync copies public/), but it WOULD
# overwrite events.json with {} and every page would still be served pointing at an
# empty index. Refusing is the correct behaviour; this forces it.
with Sandbox({}) as sb:
    (sb.data_path / "data" / "serveable" / "api" / "timeline_events"
     / "all_events.json").unlink()
    buf = io.StringIO()
    code = None
    try:
        with redirect_stdout(buf):
            se.load_events_from_pdoom_data(sb.data_path)
    except SystemExit as exc:
        code = exc.code
    check(code == 1, f"exits 1 when all_events.json is absent (got {code})")
    check("not found" in buf.getvalue().lower(), "names the missing file")
    check(not (sb.tmp / "data" / "events.json").exists(),
          "wrote no events.json on the refusal path")

# THE HALF THIS TEST DID NOT COVER, and the reason D6 was the most instructive of
# the seven vacuous guards (pdoom1-website#384). The section above is titled
# "Missing source data is a hard stop, not a quiet empty publish" and forced only
# the MISSING half. An empty-but-valid upstream parses, len() is 0, and the sync
# went on to overwrite events.json with {} -- the quiet empty publish the title
# rules out. A test that covers half of what its name says is worse than no test,
# because it retires the question.

EXISTING = "the events.json that is already published"

for label, corpus in [("an empty object", {}),
                      ("a single event", {"only_one": {"id": "only_one"}})]:
    with Sandbox({}) as sb:
        src = (sb.data_path / "data" / "serveable" / "api" / "timeline_events"
               / "all_events.json")
        src.write_text(json.dumps(corpus), encoding="utf-8")

        # A good events.json already on disk. The property that matters is not
        # just "refuses" -- it is "refuses WITHOUT touching what is published".
        published = sb.tmp / "data" / "events.json"
        published.parent.mkdir(parents=True, exist_ok=True)
        published.write_text(EXISTING, encoding="utf-8")

        buf = io.StringIO()
        code = None
        try:
            with redirect_stdout(buf):
                se.load_events_from_pdoom_data(sb.data_path)
        except SystemExit as exc:
            code = exc.code
        out = buf.getvalue()

        check(code == 1, f"{label} upstream exits 1, not 0 (got {code})")
        check("REFUSING" in out, f"...and says it is refusing, for {label}")
        check(str(REAL_MIN_EVENTS) in out, f"...and names the floor, for {label}")
        check(published.read_text(encoding="utf-8") == EXISTING,
              f"...and the already-published events.json is byte-identical, for {label}")

# NEGATIVE CONTROL. Without this, every assertion above is consistent with a
# floor that refuses everything -- which would look identical from outside and
# would be a far worse bug than the one being fixed.
with Sandbox({}) as sb:
    big = {f"e{i}": {"id": f"e{i}"} for i in range(REAL_MIN_EVENTS)}
    (sb.data_path / "data" / "serveable" / "api" / "timeline_events"
     / "all_events.json").write_text(json.dumps(big), encoding="utf-8")
    buf = io.StringIO()
    code = None
    try:
        with redirect_stdout(buf):
            loaded = se.load_events_from_pdoom_data(sb.data_path)
    except SystemExit as exc:
        code = exc.code
    check(code is None, "NEGATIVE CONTROL: a corpus exactly at the floor is ACCEPTED")
    check(len(loaded) == REAL_MIN_EVENTS, "...and every event survives the check")

# The floor applies on the far side of the filter too. A healthy upstream whose
# events all become excluded publishes the same empty index, and the load-time
# check would have passed it.
excluded = {f"e{i}": {"id": f"e{i}", "event_status": "excluded"}
            for i in range(REAL_MIN_EVENTS * 2)}
buf = io.StringIO()
code = None
try:
    with redirect_stdout(buf):
        # filter_events() stays a PURE filter -- a floor inside it would make it
        # unusable on any small fixture. The refusal lives at the call site, so
        # that is what is exercised here.
        se.assert_corpus_floor(se.filter_events(excluded), "the corpus after filtering")
except SystemExit as exc:
    code = exc.code
check(code == 1, "a corpus filtered down to nothing exits 1, not 0")
check("after filtering" in buf.getvalue(),
      "...and says the floor was crossed AFTER filtering, not upstream")
check("assert_corpus_floor(events" in open(
          ROOT / "scripts" / "sync" / "sync-events.py", encoding="utf-8").read(),
      "...and the sync actually calls it after filtering, not just in this test")

# The floor must not be derived from the corpus it protects -- a floor computed
# from the current size agrees with it by construction and can never fire.
check(isinstance(REAL_MIN_EVENTS, int) and REAL_MIN_EVENTS > 0,
      "MIN_EVENTS is a declared integer ruling")
check(REAL_MIN_EVENTS < 1194,
      "...set below the live corpus, so ordinary curation does not trip it")


# =========================================================================== 8
print("\n8. Markdown image syntax never reaches a reader as literal text")

# Neither <p class="description"> nor a <meta content="..."> slot renders Markdown,
# so an image in an upstream description was published as the characters
# "![](https://res.cloudinary.com/...png)" -- broken-looking, and a third party's
# CDN URL handed out as visible text. 12 pages were live like that on 2026-08-03.

MK = se.MARKDOWN_IMAGE_MARKER

# The two real shapes from the corpus.
one = se.strip_markdown_images_in_text("![](https://i.imgur.com/Rgc4aOs.png)")
check(one == MK, f"an image-only description becomes exactly the marker (got {one!r})")
check(one != "", "and is never the empty string -- a description is never silently "
                 "truncated to nothing")

prose = se.strip_markdown_images_in_text(
    "![](https://cdn.example.net/a.jpg)The bridge to AGI control. Mind the gaps!!")
check("cdn.example.net" not in prose, "the CDN URL is gone")
check("The bridge to AGI control. Mind the gaps!!" in prose,
      f"the prose either side survives verbatim (got {prose!r})")
check(prose.startswith(MK + " T"),
      f"a marker fused to the next word gets separated (got {prose!r})")

run = se.strip_markdown_images_in_text(
    "![](https://cdn.example.net/1.png)![](https://cdn.example.net/2.png)"
    "![](https://cdn.example.net/3.png)")
check(run == MK, f"a run of adjacent images collapses to ONE marker (got {run!r})")

# alignmentforum_d32b2cc700b53f60's description is truncated upstream mid-URL. If
# only the complete form were handled, the tail would stay behind as a bare CDN
# path in the middle of the sentence -- the leak, minus the syntax that made it
# obvious.
cut = se.strip_markdown_images_in_text(
    "Figure 1. ![](https://res.cloudinary.com/lesswrong-2-0/image/upload/v167/sHpi")
check("cloudinary" not in cut, f"an unterminated trailing image is stripped too (got {cut!r})")
check(cut.startswith("Figure 1."), "and the prose before it is kept")

# THE GUARD AGAINST THE FIX: a loose [^)]* body would run from a "![" past an
# unmatched "(" and swallow the rest of the paragraph. That is silent truncation,
# which is worse than the defect.
safe = "See ![diagram](x.png) and note (this parenthetical) plus a lone ( bracket."
got = se.strip_markdown_images_in_text(safe)
check("(this parenthetical)" in got and "lone ( bracket." in got,
      f"prose parentheses are not eaten (got {got!r})")

untouched = "Cost! [1] is a citation, and f(x) = 3 -- no images here."
check(se.strip_markdown_images_in_text(untouched) == untouched,
      "text with '!' and '[' but no image syntax is returned byte-identical")

# Whole-record, not a field list -- same contract as redact_pii().
walked = se.strip_markdown_images(
    {"future_field_added_upstream": {"nested": ["![](https://cdn.example.net/x.png)"]},
     "year": 2024})
check(walked["future_field_added_upstream"]["nested"][0] == MK,
      "strips inside a field that does not exist in today's schema")
check(walked["year"] == 2024, "and leaves non-strings alone")

check(se.count_markdown_images(
    {"a": "![](x.png)![](y.png)", "b": "![alt](z.png"}) == 3,
      "count_markdown_images counts complete and truncated forms")

# Forced end to end: publish an event whose description is nothing but images and
# assert no published BYTE carries the syntax or the host.
IMG_CORPUS = {
    "evt_img": make_event(
        "![](https://cdn.example.net/one.png)![](https://cdn.example.net/two.png)"
        "Figure 1: something happens at future time T"),
}
with Sandbox(IMG_CORPUS) as sb:
    out = run_main(sb)
    published = [p for p in sb.tmp.rglob("*") if p.is_file()
                 and "pdoom-data" not in p.parts]
    offenders = []
    for p in published:
        body = p.read_bytes().decode("utf-8")
        if "![" in body:
            offenders.append(p.name + " :: markdown image syntax")
        if "cdn.example.net" in body:
            offenders.append(p.name + " :: third-party CDN URL")
    check(not offenders,
          f"no published page or json carries image syntax or the CDN host "
          f"(offenders: {offenders[:3]})")

    page = (sb.tmp / "events" / "evt_img.html").read_text(encoding="utf-8")
    check("Figure 1: something happens at future time T" in page,
          "the surrounding prose is still on the page")
    check(MK in page, "and the marker says an image was taken out on purpose")
    ejson = json.loads((sb.tmp / "data" / "events.json").read_text(encoding="utf-8"))
    check("![" not in json.dumps(ejson),
          "events.json is clean too -- /events/ renders description.substring(0,150) "
          "from it, so the browse list was a third surface for the same defect")
    check("Replaced" in out, "the run says out loud that it replaced something")


print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK: sync-events redacts every address in the whole record, strips Markdown "
      "image syntax from every string it publishes, and no event text can change "
      "the shape of a published page.")
