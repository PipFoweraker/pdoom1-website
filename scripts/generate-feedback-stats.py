#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The public aggregate feedback counter. COUNTS ONLY, never content.

    python scripts/generate-feedback-stats.py --store <dir> --out public/data/feedback-stats.json

WHY THIS FILE EXISTS
--------------------
docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §8 D-1: comments are private to Pip,
and what the site shows is an aggregate counter. §9 gives the shape. This is a
DERIVED ARTIFACT, never a second store: it reads the private JSONL and writes
integers.

Direct precedent, and the reason the rule is "counts only" and not "counts
mostly": public/data/events-sync-summary.json publishes counts precisely because
naming the items would republish the thing that was redacted. A category name
plus a count of 1 is a pointer to one person's message.

THE TWO HAZARDS, AND WHAT STOPS THEM (§9a, §9b)
-----------------------------------------------
9a -- a public classification is a public claim about a real person's words.
`abusive` displayed on pdoom1.com is a judgment, and an automated classifier that
is wrong publicly mislabels the visitor who tried hardest to talk to us. So a
category is not filtered out of machine output; machine output has NO ROUTE IN.
Categories come from exactly two places:

  * the record's own `kind` and `value` -- structural facts of the submission,
    not judgments about it (a thumb is a thumb);
  * human-confirmed tags in the triage sidecar, which must carry
    source="human" AND a non-blank confirmed_by AND an ISO confirmed_on.

`flags` -- the endpoint's honeypot and too-fast markers, contract §3 -- is never
read by this script. An entry claiming source="human" with nobody named is a
broken triage tool asserting human provenance, and REFUSES the whole run rather
than publishing under a name nobody signed.

Everything not human-confirmed counts as `untriaged`. Never guessed at, never
inferred, never quietly re-labelled.

WHAT COUNTS AS UNTRIAGED -- §9's own example settles this, the prose does not
------------------------------------------------------------------------------
§9 shows 1904 thumbs up, 311 down, 220 comments, and `untriaged: 47`. 47 cannot
be a backlog over 2,435 records, so `untriaged` in the contract's own worked
example counts things there are WORDS to read. §9c agrees: the failure it attacks
is received-and-never-read, and a bare thumb has nothing to read.

So a record is triageable when it carries non-empty `text`. That is derived from
the record rather than allowlisted by kind, which matters twice: §2 makes `text`
optional-but-permitted on a thumb, so a thumb with a comment attached IS a
reading obligation; and a prose kind invented by a newer client is covered the
day it lands. A tombstoned record (§10 erasure) drops out, because the words are
gone and nobody can be obliged to read them.

9b -- small counts re-identify. k = 5. A category below k is WITHHELD and
declared in `suppressed_categories`. Never rounded, never zeroed, never silently
dropped: "a silently-dropped category is the same lie in a smaller font".

NO TOTAL IS EVER PUBLISHED, and that is a k-anonymity decision rather than an
omission. If the file carried a record total alongside the surviving categories,
subtracting one from the other would recover the suppressed count exactly, and
the withholding would be theatre.

`untriaged` is EXEMPT from suppression (§9c). It is a self-imposed accountability
clock aimed at received-and-never-read -- silent loss wearing a different hat --
and capping or hiding it when it gets embarrassing is the failure it exists to
expose. It publishes at 1.

RESIDUAL 9d -- §9b AND §9c CONTRADICT EACH OTHER IN ONE CASE, AND §9c WINS
--------------------------------------------------------------------------
Not in the contract; found while forcing S11 and written down rather than left
for somebody to rediscover. Kind-derived categories PARTITION the records, and
§9c mandates publishing `untriaged` exactly. So in a store where every record
carries text and nothing has been triaged, `untriaged` IS the record total, and
subtracting the published kind counts from it recovers the SUM of the suppressed
ones. With exactly one category suppressed, that sum is that category's count.

What it discloses is bounded and is deliberately the weaker of the two: a
structural fact ("there are two bug reports"), never a judgment, never a page,
never a person -- §9a's actual hazard is untouched. It also closes as soon as any
tag is confirmed, because tag counts do not partition the population, so
untriaged stops equalling the total.

Resolving it the other way would mean capping or hiding `untriaged`, which is the
one thing §9c names as forbidden, and it is forbidden for a stronger reason: the
number exists to embarrass us into reading our mail. So: documented, bounded, and
left standing. If this ever needs closing, close it by TRIAGING, not by
publishing less.

DEDUP IS NOT IMPLEMENTED HERE
-----------------------------
Duplicate writes are normal by design (contract INV-1e: the endpoint never
rejects a rid it has seen). Collapsing them is scripts/read-feedback.py's rule --
"earliest server_ts wins" -- and this script IMPORTS it. This repo's most
expensive recurring defect is a second implementation of a rule that already
existed (five HTML escapers, ten navigation variants, two version.json writers),
and a second collapser would put the public numbers and Pip's private inbox on
two different definitions of "a message". If read-feedback.py is missing or does
not expose load(), this script REFUSES; it does not fall back.

It also verifies the reader's conservation law -- records_parsed minus the
returned count must equal the duplicates it reported -- so a reader that ever
starts LOSING records takes the counter offline instead of publishing a number
that is quietly too small.

EXIT CODES
    0  written
    2  UNKNOWN: no store configured/present, or a sidecar line nobody can read
    3  REFUSED: reader missing or misbehaving, triage claiming unattributed
       human provenance, or an output that failed the counts-only assertion.
       Nothing is written on any refusal; the previous file stands.
"""

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent

EXIT_OK = 0
EXIT_UNKNOWN = 2
EXIT_REFUSED = 3

# Contract §9b. Held as a constant rather than a flag ON PURPOSE: a threshold
# that CI can lower with an argument is a threshold that gets lowered on the day
# it is inconvenient. There is no --k.
K_ANONYMITY = 5

SCHEMA = 1

# A category name becomes a KEY in a file served from pdoom1.com. This is a shape
# constraint, not a value list -- content/campaigns/README.md §2.1's lesson,
# "write the CONSTRAINT, never the value" -- so a new legitimate tag needs no
# edit here, while "Pip is an idiot" can never become a published key.
CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

# Kind-derived categories own these names. A human tag colliding with one would
# silently merge a judgment into a structural count and publish a number that
# means two different things.
RESERVED = {"thumb", "thumb_up", "thumb_down", "thumb_unspecified",
            "comment", "bug", "feature", "question", "feedback"}

ISO_Z = "%Y-%m-%dT%H:%M:%SZ"


class Refused(Exception):
    pass


def _sibling(filename, alias):
    """Import a hyphenated sibling script by path. Absence is LOUD."""
    path = SCRIPTS / filename
    if not path.exists():
        raise Refused(
            "%s does not exist. This script depends on it and will not "
            "improvise a replacement." % path)
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reader(reader_path=None):
    """scripts/read-feedback.py, or an explicit path for tests.

    Required surface: load(store) -> dict with `records`, `record_count`,
    `records_parsed`, `duplicates_collapsed`, `unparseable_lines`,
    `records_without_rid`. If that surface changes, this refuses by name rather
    than degrading to a private collapser.
    """
    path = Path(reader_path) if reader_path else SCRIPTS / "read-feedback.py"
    if not path.exists():
        raise Refused(
            "%s does not exist. It owns read-time deduplication (contract §3, "
            "§11.6: collapse duplicate rid, earliest server_ts wins). Counting "
            "without it would publish every retry as a separate message, and "
            "writing a second collapser here would give the public counter and "
            "Pip's inbox two different definitions of 'a message'." % path)
    spec = importlib.util.spec_from_file_location("read_feedback_dep", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "load", None)
    if not callable(fn):
        raise Refused(
            "%s exists but exposes no callable load(store). Required surface: "
            "load(store) -> {'records': [...], 'record_count': int, "
            "'records_parsed': int, 'duplicates_collapsed': int, "
            "'unparseable_lines': [...], 'records_without_rid': [...]}." % path)
    return module


REQUIRED_READER_KEYS = ("records", "record_count", "records_parsed",
                        "duplicates_collapsed", "unparseable_lines",
                        "records_without_rid")


def verify_reader_doc(doc):
    """The dependency's postcondition, checked -- not its logic, re-run.

    Nothing here decides which duplicate wins; that is the reader's rule and this
    script has no opinion about it. What it checks is the one property the public
    numbers rest on: the collapse LOSES NOTHING. records_parsed - record_count
    must be exactly the duplicate count the reader reported. A reader that starts
    dropping records would otherwise publish a total that is quietly too small,
    which is silent loss with a JSON file in front of it.
    """
    if not isinstance(doc, dict):
        raise Refused("reader returned %s, not a dict" % type(doc).__name__)
    missing = [k for k in REQUIRED_READER_KEYS if k not in doc]
    if missing:
        raise Refused("reader result is missing %s" % ", ".join(missing))
    records = doc["records"]
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise Refused("reader returned a `records` that is not a list of objects")
    if doc["record_count"] != len(records):
        raise Refused("reader says record_count=%s but returned %d record(s)"
                      % (doc["record_count"], len(records)))
    expected = doc["records_parsed"] - doc["record_count"]
    if expected != doc["duplicates_collapsed"]:
        raise Refused(
            "reader conservation law broken: parsed %s, returned %s, but "
            "reported only %s duplicate(s) collapsed. %d record(s) went missing "
            "between reading and returning, so any count derived from this is "
            "too small by an unknown amount."
            % (doc["records_parsed"], doc["record_count"],
               doc["duplicates_collapsed"], expected - doc["duplicates_collapsed"]))
    seen = set()
    for rec in records:
        rid = rec.get("rid")
        if isinstance(rid, str) and rid.strip():
            if rid in seen:
                raise Refused("reader returned rid %s twice; deduplication did "
                              "not happen" % rid)
            seen.add(rid)
    return records


def kind_category(rec):
    """A structural fact about the submission, or None if it is not readable.

    `kind` is allowlisted by the endpoint (contract §2). Anything outside the
    published shape is counted as unreadable rather than published under its own
    name -- an arbitrary string out of the store must never become a key in a
    file served from pdoom1.com.
    """
    kind = rec.get("kind")
    if not isinstance(kind, str) or not CATEGORY_RE.match(kind):
        return None
    if kind != "thumb":
        return kind
    value = rec.get("value")
    if isinstance(value, bool):
        return "thumb_unspecified"
    if value == 1:
        return "thumb_up"
    if value == -1:
        return "thumb_down"
    return "thumb_unspecified"


def is_triageable(rec):
    """True when the record carries words somebody is obliged to read.

    See the header: §9's worked example counts 47 untriaged against 2,435
    records, so `untriaged` is a backlog of PROSE, not of submissions. Derived
    from the presence of `text` rather than from a list of kinds, so a thumb with
    a comment attached counts and a bare thumb does not.
    """
    text = rec.get("text")
    return isinstance(text, str) and bool(text.strip())


def load_confirmations(store, triage_name):
    """{rid: [tags]} from HUMAN-confirmed triage only, plus what was refused.

    Returns (confirmed, unconfirmed_entries, damaged_lines).

    An entry is confirmed only when source == "human" AND confirmed_by names
    somebody AND confirmed_on is an ISO date. Anything else -- a regex tagger's
    output, an entry with no `source` at all, a suggestion awaiting review -- is
    counted in unconfirmed_entries and its tags are DISCARDED, so those records
    stay `untriaged` and the backlog visibly does not shrink. That is the
    designed feedback loop: an auto-tagger can help Pip sort, and cannot help
    itself to the public file.

    "Absence of a marker is never a clean bill of health": a missing `source` is
    treated as not-human, never as human by default.
    """
    path = Path(store) / triage_name
    confirmed = {}
    unconfirmed = 0
    damaged = 0
    if not path.exists():
        return confirmed, unconfirmed, damaged

    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    for lineno, raw in enumerate(text.split("\n"), start=1):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            damaged += 1
            continue
        if not isinstance(entry, dict):
            damaged += 1
            continue

        source = entry.get("source")
        tags = entry.get("tags")
        rid = entry.get("rid")

        if source != "human":
            if tags:
                unconfirmed += 1
            continue

        # From here the entry CLAIMS human provenance. Every defect below is a
        # broken triage tool asserting a person's judgment, so it refuses the run
        # instead of being skipped: a skipped entry undercounts a category that
        # somebody did confirm, and nothing would ever say so.
        where = "%s:%d" % (path.name, lineno)
        if not isinstance(rid, str) or not rid.strip():
            raise Refused("%s: source=human with no rid. A confirmation that "
                          "names no record confirms nothing." % where)
        confirmed_by = entry.get("confirmed_by")
        if not isinstance(confirmed_by, str) or not confirmed_by.strip():
            raise Refused(
                "%s: source=human but confirmed_by is %r. A public category is a "
                "public claim about a real person's words (contract §9a); it "
                "publishes under a human's name or it does not publish."
                % (where, confirmed_by))
        confirmed_on = entry.get("confirmed_on")
        try:
            dt.date.fromisoformat(str(confirmed_on))
        except (TypeError, ValueError):
            raise Refused("%s: confirmed_on=%r is not an ISO date. A judgment "
                          "with no date cannot be reviewed." % (where, confirmed_on))
        if not isinstance(tags, list) or not tags:
            raise Refused("%s: source=human with tags=%r. Nothing to confirm."
                          % (where, tags))
        for tag in tags:
            if not isinstance(tag, str) or not CATEGORY_RE.match(tag):
                raise Refused(
                    "%s: tag %r does not match %s. This string would become a "
                    "key in a file served from pdoom1.com."
                    % (where, tag, CATEGORY_RE.pattern))
            if tag in RESERVED:
                raise Refused(
                    "%s: tag %r collides with a kind-derived category. Merging "
                    "a human judgment into a structural count would publish one "
                    "number meaning two different things. Reserved: %s"
                    % (where, tag, ", ".join(sorted(RESERVED))))
        confirmed.setdefault(rid, set()).update(tags)

    return confirmed, unconfirmed, damaged


def build(records, confirmed, unconfirmed, unreadable, generated):
    """Counts, k-anonymity, and the shape §9 specifies."""
    counts = {}
    untriaged = 0
    for rec in records:
        category = kind_category(rec)
        if category is None:
            unreadable += 1
            continue
        counts[category] = counts.get(category, 0) + 1

        rid = rec.get("rid")
        tags = confirmed.get(rid) if isinstance(rid, str) else None
        if not tags:
            if is_triageable(rec):
                untriaged += 1
            continue
        for tag in sorted(tags):
            counts[tag] = counts.get(tag, 0) + 1

    published = {}
    suppressed = 0
    for name in sorted(counts):
        if counts[name] < K_ANONYMITY:
            suppressed += 1
            continue
        published[name] = counts[name]

    return {
        "generated": generated,
        "window": "all-time",
        "counts": published,
        "untriaged": untriaged,
        "suppressed_categories": suppressed,
        "unconfirmed_tags": unconfirmed,
        "unreadable_records": unreadable,
        "k_threshold": K_ANONYMITY,
        "schema": SCHEMA,
    }, counts


def assert_counts_only(doc):
    """Refuse to write anything that is not an integer or a declared constant.

    The whole promise of this artifact is that no visitor text can reach it. That
    promise is worth exactly as much as the thing that enforces it, so it is
    enforced structurally on the way out, against the finished document, rather
    than trusted to every code path above.
    """
    allowed_ints = {"untriaged", "suppressed_categories", "unconfirmed_tags",
                    "unreadable_records", "k_threshold", "schema"}
    for key, value in doc.items():
        if key in allowed_ints:
            if not isinstance(value, int) or isinstance(value, bool):
                raise Refused("%s must be an int, got %r" % (key, value))
        elif key == "generated":
            if not isinstance(value, str) or not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
                raise Refused("generated=%r is not an ISO-8601 UTC stamp" % value)
        elif key == "window":
            if value != "all-time":
                raise Refused("window=%r is not a declared window" % value)
        elif key == "counts":
            if not isinstance(value, dict):
                raise Refused("counts must be an object")
            for name, count in value.items():
                if not CATEGORY_RE.match(str(name)):
                    raise Refused(
                        "category key %r does not match %s. Refusing to publish: "
                        "an arbitrary string out of the store would be content, "
                        "not a count." % (name, CATEGORY_RE.pattern))
                if not isinstance(count, int) or isinstance(count, bool):
                    raise Refused("count for %r is %r, not an int" % (name, count))
                if count < K_ANONYMITY:
                    raise Refused(
                        "category %r would publish at %d, below k=%d. §9b: "
                        "withheld and declared, never published small."
                        % (name, count, K_ANONYMITY))
        else:
            raise Refused("unexpected key %r in the public document. Counts "
                          "only; every publishable key is declared here." % key)
    return doc


def write_atomic(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", help="feedback store root (or PDOOM_FEEDBACK_STORE)")
    ap.add_argument("--out", default=str(REPO_ROOT / "public" / "data" /
                                         "feedback-stats.json"),
                    help="output path (default: the published one)")
    ap.add_argument("--reader", help="path to read-feedback.py (tests)")
    ap.add_argument("--now", help="ISO-8601 UTC or epoch, for deterministic runs")
    ap.add_argument("--stdout", action="store_true",
                    help="print the document instead of writing it")
    args = ap.parse_args(argv)

    try:
        purge = _sibling("purge-feedback.py", "purge_feedback_dep")
        store = purge.resolve_store(args.store)
        if store is None:
            print("UNKNOWN: no store configured. Pass --store or set "
                  "PDOOM_FEEDBACK_STORE. Publishing a zeroed file would be a "
                  "claim that nobody has written to us.", file=sys.stderr)
            return EXIT_UNKNOWN
        try:
            purge.refuse_bad_store_location(store)
        except purge.Refused as exc:
            raise Refused(str(exc))
        if not store.exists():
            print("UNKNOWN: store %s does not exist." % store, file=sys.stderr)
            return EXIT_UNKNOWN

        generated = purge.iso(purge.now_from(args.now))

        reader = load_reader(args.reader)
        doc = reader.load(str(store))
        records = verify_reader_doc(doc)

        confirmed, unconfirmed, damaged = load_confirmations(
            store, purge.TRIAGE_NAME)
        if damaged:
            print("UNKNOWN: %d unreadable line(s) in %s. A line nobody can parse "
                  "may hold a confirmation, so every category derived from this "
                  "sidecar is uncertain. Nothing written."
                  % (damaged, Path(store) / purge.TRIAGE_NAME), file=sys.stderr)
            return EXIT_UNKNOWN

        unreadable = len(doc["unparseable_lines"])
        public, raw_counts = build(records, confirmed, unconfirmed, unreadable,
                                   generated)
        assert_counts_only(public)

        if args.stdout:
            print(json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            write_atomic(args.out, public)
            print("wrote %s" % args.out)

        withheld = sorted(n for n in raw_counts if n not in public["counts"])
        print("  %d record(s) after dedup, %d duplicate write(s) collapsed"
              % (doc["record_count"], doc["duplicates_collapsed"]))
        print("  %d categor(ies) published, %d withheld below k=%d %s"
              % (len(public["counts"]), len(withheld), K_ANONYMITY,
                 "(names not printed here either)" if withheld else ""))
        print("  untriaged=%d (published at any size, §9c), unconfirmed machine "
              "tags ignored=%d" % (public["untriaged"], unconfirmed))
        return EXIT_OK

    except Refused as exc:
        print("REFUSED: %s\n  Nothing was written; any previously published file "
              "still stands." % exc, file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
