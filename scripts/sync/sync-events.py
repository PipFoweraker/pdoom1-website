#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync events from pdoom-data repository to pdoom1-website

This script:
1. Clones/updates pdoom-data repository
2. Reads event data from data/serveable/api/timeline_events/
3. Generates individual event detail pages
4. Creates events.json for the events index page
5. Downloads game icons from pdoom1 repo (optional)

Usage:
    python scripts/sync/sync-events.py [--pdoom-data-path PATH] [--sync-icons]
"""

import json
import os
import re
import sys
import argparse
import importlib.util
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Force UTF-8 for the console. Was a win32-only io.TextIOWrapper swap, which
# protected this module but is not the idiom check-encoding-safety.py looks for,
# so the sweep reported it as unprotected and it carried a waiver for eleven days
# on a crash risk it did not have. Same effect, plus errors="replace"; see
# CLAUDE.md "Environment / tooling".
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

# Configuration
SCRIPT_DIR = Path(__file__).parent
WEBSITE_ROOT = SCRIPT_DIR.parent.parent
PUBLIC_DIR = WEBSITE_ROOT / "public"
EVENTS_DIR = PUBLIC_DIR / "events"
DATA_DIR = PUBLIC_DIR / "data"
ICONS_DIR = PUBLIC_DIR / "assets" / "icons" / "events"

# Default pdoom-data location (sibling directory)
DEFAULT_PDOOM_DATA = WEBSITE_ROOT.parent / "pdoom-data"
DEFAULT_PDOOM1 = WEBSITE_ROOT.parent / "pdoom1"

# Canonical origin, used to build absolute og:url / og:image values (the
# OpenGraph spec requires absolute URLs -- a relative path is silently ignored
# by every scraper).
SITE_ORIGIN = "https://pdoom1.com"

# The site-wide share card already referenced by index/about/press. Deliberately
# NOT a per-event image: no per-event art exists, and pointing at one that does
# not exist is worse than pointing at the generic card.
OG_IMAGE_URL = f"{SITE_ORIGIN}/assets/og-card.jpg"

# Length budget for the description reused by <meta name="description">,
# og:description and twitter:description.
META_DESCRIPTION_CHARS = 155


def log(message: str, level: str = "INFO"):
    """Simple logger"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def ensure_directories():
    """Create necessary directories if they don't exist"""
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Ensured directories exist: {EVENTS_DIR}, {DATA_DIR}, {ICONS_DIR}")


# THE CORPUS FLOOR.  D6 of pdoom1-website#384.
#
# The absent-file case was already a hard stop. The EMPTY-BUT-VALID case was not:
# an upstream `{}` parses, `len(events)` is 0, and the sync went on to overwrite
# public/data/events.json with `{}` -- so /events/ served an empty index while
# 2,197 generated pages stayed on disk pointing into it. And this file's own test
# claimed to force that state while forcing only the file-absent half, which made
# D6 the most instructive of the seven: the test retired the question.
#
# MIN_EVENTS IS A RULING, NOT A GUESS. The corpus has been ~1,194 for its whole
# life (measured 2026-08-25: 1,194 in source, 1,194 included, 0 excluded). 100 is
# an order of magnitude below that: low enough that deliberate curation, or
# pdoom-data splitting a collection out, never trips it; high enough that a
# truncated fetch, an empty object, or a filter that swallowed everything does.
#
# It is deliberately NOT derived from the current corpus size. A floor computed
# from the thing it is protecting agrees with that thing by construction --
# the same defect as a staleness window derived from its own writer.
MIN_EVENTS = 100


def assert_corpus_floor(events: Dict[str, Any], where: str) -> None:
    """Refuse to proceed on a corpus too small to be real. Never returns falsely.

    Fails CLOSED: the exit happens before anything is written, so the previous
    events.json and the previous pages survive untouched. A stale index is
    recoverable; an empty one that overwrote a good one is not.
    """
    count = len(events)
    if count < MIN_EVENTS:
        log(f"REFUSING TO WRITE: {where} holds {count} events, floor is {MIN_EVENTS}.",
            "ERROR")
        log("Nothing has been written. The previously published events.json and "
            "every generated page are untouched.", "ERROR")
        log("If the corpus really has shrunk this far, MIN_EVENTS is a ruling in "
            "this file and changing it is a decision, not a workaround.", "ERROR")
        sys.exit(1)


def load_events_from_pdoom_data(pdoom_data_path: Path) -> Dict[str, Any]:
    """Load all events from pdoom-data repository"""
    events_file = pdoom_data_path / "data" / "serveable" / "api" / "timeline_events" / "all_events.json"

    if not events_file.exists():
        log(f"Events file not found: {events_file}", "ERROR")
        log(f"Make sure pdoom-data is cloned at: {pdoom_data_path}", "ERROR")
        sys.exit(1)

    with open(events_file, 'r', encoding='utf-8') as f:
        events = json.load(f)

    log(f"Loaded {len(events)} events from pdoom-data")
    assert_corpus_floor(events, "upstream all_events.json")
    return events


def should_include_event(event: Dict[str, Any]) -> bool:
    """Filter events for website display based on event_status metadata"""
    status = event.get('event_status', 'included')

    # Exclude newsletters and explicitly excluded events
    if status in ['newsletter_archive', 'excluded']:
        return False

    # Include all others (included, review_needed)
    return True


def filter_events(events: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out excluded events"""
    filtered = {
        event_id: event
        for event_id, event in events.items()
        if should_include_event(event)
    }

    excluded_count = len(events) - len(filtered)
    if excluded_count > 0:
        log(f"Filtered out {excluded_count} excluded/newsletter events")

    return filtered


# ---------------------------------------------------------------------------
# PII redaction
#
# Many event descriptions are raw text scraped out of paper PDFs, and arXiv/ACM
# author blocks carry the authors' institutional email addresses. Republishing
# those on a public static site hands a spam harvester 75 academics' addresses
# that they never agreed to have listed here. So every string that reaches a
# generated page or events.json is swept before it is written.
#
# Two properties this pattern is built for, both from the real corpus:
#
#   * PDF extraction glues the next author's given name onto the TLD --
#     "madry@mit.eduAleksandar". A greedy [A-Za-z]{2,} TLD eats "Aleksandar"
#     too and silently deletes a name. Requiring the TLD to be one letter
#     followed by LOWERCASE letters stops the match at the capital, so the
#     redaction removes the address and leaves the name.
#   * Line breaks are extracted as a literal "\n" two-character sequence in
#     some records, which is why the corpus contains "nroman.yampolskiy@..."
#     with a leading n. The local part matches whatever precedes the @, so
#     that stray n is left behind as text -- ugly, but it is not an address,
#     and inventing a rule to strip it risks eating real initials.
#
# THE MARKER STRING IS A CROSS-REPO AGREEMENT, not a local style choice.
# pdoom-data redacts the same addresses at source (pdoom-data#50) and writes
# "[email address redacted]" into all_events.json. This repo used to write
# "[email removed]", so the same corpus carried two different markers depending
# on which side caught the address first, and a reader had no way to tell they
# meant the same thing. Pip ruled on 2026-08-03 that both repos use pdoom-data's
# string. If you change it here, change it there too -- and expect the next sync
# to rewrite the visible text on every page that carries one.
REDACTION_MARKER = "[email address redacted]"

# WIDENED 2026-08-15, inheriting pdoom-data 12c0455 (2026-08-09).
#
# MODES (e), (f), (g). The pattern above was correct about ordinary addresses
# and blind to three further modes, all of them consequences of the same fact
# the notes above already turn on: this text is EXTRACTED FROM PDFs, not typed.
# pdoom-data hit exactly these and fixed them at source; this repo never
# inherited that fix, so the three modes were invisible on this side of the sync
# for six days, and the only reason nothing was serving is that the daily sync
# happened to pull an upstream corpus that had already been cleaned.
#
#   (e) BRACE-GROUP NOTATION, the highest-volume mode upstream. Papers print
#       several authors in ONE address: "{aaa,bbb,ccc}@institution.edu" is three
#       data subjects in a single match. The old local part is
#       [A-Za-z0-9._%+\-]+, which contains neither '{' nor ',', so no substring
#       of that string could reach the '@'. The match failed SILENTLY and the
#       address shipped -- and because count_emails() shares this pattern, the
#       sync log confidently reported zero.
#   (f) WHITESPACE INSIDE THE DOMAIN, inserted by the extractor when it breaks a
#       token across a column or line: "institution. edu", "uni -example.de",
#       "cbs .dk".
#   (g) WHITESPACE BEFORE THE '@': "{aaa, bbb} @institution.edu".
#
# PORTED, NOT COPIED, and the difference is load-bearing.
#
# pdoom-data's domain rule ends in [A-Za-z]{2,24}. Transplanting that here is
# WRONG, for the reason the note above already records: a case-insensitive TLD
# eats the capitalised given name the extractor glued on, and silently deletes a
# person's name from the page. The lowercase-TLD rule stays.
#
# It also turns out to be what makes mode (f) SAFE, which was not obvious and is
# the reason this is split into two alternatives instead of one permissive one.
# Once a space is allowed around the dot, "team@pdoom1.com. It usually replies"
# -- an ordinary sentence break in this site's own footer copy -- matches with a
# domain of "pdoom1.com. It", which the anchored allowlist in
# check-published-emails.py then rejects, so the guard fires on our own contact
# address and no page can ever be written again. Requiring the TLD to be
# ENTIRELY lowercase once whitespace is involved stops the match at the capital
# that begins the next sentence, exactly as the original rule stops it at the
# capital that begins the next author's name. Same discipline, second use.
#
# So: the no-whitespace form keeps today's rule EXACTLY, byte for byte, so no
# address that is redacted today can stop being redacted. The broken form is
# strictly additional reach, and pays for it with the stricter TLD.
_LABEL = r"[A-Za-z0-9\-]+"

# Today's domain rule, unchanged. Tried first, so ordinary addresses match
# ordinary addresses and nothing about the existing corpus shifts.
_DOMAIN_TIGHT = _LABEL + r"(?:\.[A-Za-z0-9\-]+)*" + r"\.[A-Za-z][a-z]{1,23}"

# Extractor-broken domains. AT MOST ONE whitespace character at each break: a
# real extraction artefact is one severed token, never a clause, and unbounded
# whitespace lets a match run out of the address and into the surrounding prose.
_DOMAIN_BROKEN = (
    _LABEL + r"(?:\s?[.\-]\s?" + _LABEL + r")*" + r"\s?\.\s?[a-z]{2,24}"
)

# A brace group is bounded by the closing brace immediately before the '@' and
# by 200 characters, so it cannot run away. It admits NEWLINES on purpose: the
# extractor line-wraps long author groups mid-list, and excluding newlines was
# the first bug pdoom-data's own widening shipped.
_LOCAL = r"(?:\{[^{}@]{1,200}\}|[A-Za-z0-9._%+\-]+)"

EMAIL_PATTERN = re.compile(
    r"(?:mailto:)?"                            # swallow a mailto: prefix too
    + _LOCAL +                                 # local part, or a whole group
    r"\s?@\s?"                                 # at most one space either side
    + r"(?:" + _DOMAIN_TIGHT + r"|" + _DOMAIN_BROKEN + r")"
)


def redact_emails_in_text(text: str) -> str:
    """Replace every email address in a string with REDACTION_MARKER.

    Marking rather than deleting: a reader who sees a gap in an author block
    should be able to tell that something was taken out deliberately, not that
    the page is broken. The site's rule is to never mislead a visitor, and a
    silent deletion is a small lie about what the source said.
    """
    return EMAIL_PATTERN.sub(REDACTION_MARKER, text)


def redact_pii(value: Any) -> Any:
    """Recursively redact email addresses in any nested str/list/dict value.

    Deliberately walks the WHOLE event rather than a named list of fields:
    write_events_json() serialises the entire event dict, so a field added
    upstream tomorrow would otherwise ship unscrubbed. Fail closed.
    """
    if isinstance(value, str):
        return redact_emails_in_text(value)
    if isinstance(value, list):
        return [redact_pii(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_pii(v) for k, v in value.items()}
    return value


def count_emails(value: Any) -> int:
    """Count email addresses in a nested structure (for the sync log)."""
    if isinstance(value, str):
        return len(EMAIL_PATTERN.findall(value))
    if isinstance(value, list):
        return sum(count_emails(v) for v in value)
    if isinstance(value, dict):
        return sum(count_emails(v) for v in value.values())
    return 0


# ---------------------------------------------------------------------------
# Obfuscated contact strings -- ADVISORY ONLY, never blocks.
#
# redact_pii() fails CLOSED against a new upstream FIELD (it recurses the whole
# record) but OPEN against a new address FORM: "name [at] domain.edu" is a
# contact string a human reads as an address and EMAIL_PATTERN does not match,
# so today it ships untouched AND UNREPORTED (pdoom1-website#240). Solving
# obfuscated-address detection properly is out of scope -- the ambiguity is
# real and a blocking check would fire on prose.
#
# What is cheap, and what this is, is removing the SILENCE. A count in the log
# and in the sync summary means "something address-shaped got through" is a
# thing someone can notice, instead of a thing nobody can see.
#
# Deliberately narrow: only bracketed markers ([at] (at) {at}) and the all-caps
# "name AT domain DOT edu" form. A general "\s+at\s+" alternative would match
# ordinary prose ("aimed at arxiv.org") and a noisy advisory is one everybody
# learns to ignore, which is worse than no advisory.
OBFUSCATED_CONTACT_PATTERN = re.compile(
    r"[A-Za-z0-9._%+\-]{2,}"
    r"(?:"
    r"\s*(?i:\[at\]|\(at\)|\{at\})\s*"           # name [at] domain.edu
    r"|"
    r"\s+AT\s+"                                   # name AT domain DOT edu
    r")"
    r"[A-Za-z0-9\-]{2,}"
    r"(?:\s*(?:(?i:\[dot\]|\(dot\)|\{dot\})|\s+DOT\s+|\.)\s*[A-Za-z0-9\-]{2,})+"
)


def count_obfuscated_contacts(value: Any) -> int:
    """Count address-shaped strings that EMAIL_PATTERN cannot redact."""
    if isinstance(value, str):
        return len(OBFUSCATED_CONTACT_PATTERN.findall(value))
    if isinstance(value, list):
        return sum(count_obfuscated_contacts(v) for v in value)
    if isinstance(value, dict):
        return sum(count_obfuscated_contacts(v) for v in value.values())
    return 0


# ---------------------------------------------------------------------------
# Truncation-severed addresses -- ADVISORY ONLY, never blocks.
#
# MODE (d). EMAIL_PATTERN requires a TLD, so an address whose domain was CUT OFF
# mid-string is invisible to it by construction: "leimeister@un" has no dot and
# no TLD, and every scanner on both sides of this sync reported the corpus clean
# the whole time it was being served.
#
# It reached this repo TWICE, by two different routes, from one upstream defect:
#
#   1. pdoom-data's importer caps `description` at 1,000 characters
#      (`description[:997] + '...'`) and exactly one cap landed inside a contact
#      line. That shipped to public/data/events.json and to one page under
#      public/events/. Fixed at source in pdoom-data#81 (2026-08-13), which
#      extended that repo's redact_emails.py with a mode-(d) rule of its own.
#
#   2. THEN THE REMEDIATION REPUBLISHED IT. pdoom1#1212 -- the PR that closed
#      the original exposure -- quoted the severed fragment verbatim in its body
#      to explain the defect, and update-game-data.yml harvests OPEN issue and
#      PR bodies into public/data/issues-cache.json, which is served from
#      pdoom1.com. redact_pii() ran on that harvest and could not see it. The
#      fix and the leak were the same sentence.
#
# WHY THIS IS ADVISORY AND NOT A REDACTION, which is the whole design question.
# pdoom-data's SEVERED rule is safe because it is anchored to the END OF THE
# STRING: in a `description` field the cut is necessarily the last thing in the
# value, and that one bound excludes the entirety of prose. Issue and PR bodies
# have no such anchor -- the #1212 fragment sat mid-body on a line ending in a
# quote character -- so transplanting that rule here means scanning free-form
# markdown for `token@token...`, and that fires on ordinary prose and on exactly
# the metric notation this corpus is full of (pass@k appears in it routinely).
# A rewriting check on that basis is the noisy advisory that
# OBFUSCATED_CONTACT_PATTERN's own note argues against, one section up, and a
# noisy advisory is one everybody learns to ignore.
#
# So this removes the SILENCE, which is the cheap half and the half that was
# actually missing: nothing anywhere could report that something address-shaped
# had got through. Same posture and same reasoning as the obfuscated-contact
# advisory above.
#
# The bounds on the local part are pdoom-data's, reused rather than reinvented
# so the two repos agree on what "looks like a person" means, minus its
# line-start refinement -- that keys off extracted-PDF contact lines, which
# markdown does not have, so the stricter uniform bound is used instead.
#
# COUNTS ONLY, NEVER THE MATCHED TEXT. events-sync-summary.json is served from
# pdoom1.com, so printing a match would republish the exact string the redaction
# exists to remove -- #1212's mistake a second time, in the log instead of the
# body.
_TRUNCATION_MARKER = r"(?:\.\.\.|…)"
SEVERED_CONTACT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+\-@])"                      # a whole token, not a tail
    r"(?P<local>[A-Za-z0-9._%+\-]{3,})"             # local part...
    r"@"                                            # ...bound to '@', no space
    r"(?P<domain>[A-Za-z0-9][A-Za-z0-9.\-]{0,23})?" # domain fragment, may be cut
    + _TRUNCATION_MARKER
)


def _severed_local_ok(local: str) -> bool:
    """Does this local part look like a person, or like inline notation?

    Short bare tokens are what metric and LaTeX notation is made of -- pass(4),
    Acc(3), lx(2), math(4), ACDC(4) -- and every one of those appears to the
    LEFT of an '@' in this corpus. A separator, or real length, is what
    distinguishes a name from a token.
    """
    if not re.search(r"[A-Za-z]", local):
        return False
    if len(local) >= 4 and re.search(r"[._%+\-]", local):
        return True
    return len(local) >= 5


def count_severed_contacts(value: Any) -> int:
    """Count truncation-severed address shapes EMAIL_PATTERN cannot see."""
    if isinstance(value, str):
        n = 0
        for m in SEVERED_CONTACT_PATTERN.finditer(value):
            if REDACTION_MARKER in m.group(0):
                continue
            # A complete address is mode (a) and redact_pii() already took it.
            if EMAIL_PATTERN.fullmatch(m.group("local") + "@" + (m.group("domain") or "")):
                continue
            if _severed_local_ok(m.group("local")):
                n += 1
        return n
    if isinstance(value, list):
        return sum(count_severed_contacts(v) for v in value)
    if isinstance(value, dict):
        return sum(count_severed_contacts(v) for v in value.values())
    return 0


# ---------------------------------------------------------------------------
# Pre-write verification
#
# WHY THIS EXISTS AT ALL, given redact_pii() runs first.
#
# scripts/check-published-emails.py is the repo's blocking guard against serving
# a third party's address, and it is wired into content-honesty.yml on `push` to
# public/**/*.html. But the daily sync commits with `[skip ci]`
# (.github/workflows/sync-events.yml), so that workflow NEVER FIRED on the 1,194
# pages this generator writes every day. The guard was live for human pushes and
# blind to the automated path -- i.e. blind to the only path that actually
# produces these pages (pdoom1-website#240).
#
# The fix has to PREVENT, not detect: this refuses to write ANY page if the
# rendered output carries a disallowed address. Nothing reaches disk, so nothing
# reaches the commit, so nothing reaches production. A detector that runs after
# the write can only tell you what you already published.
#
# It scans the RENDERED HTML, not the redacted event dict. Re-scanning the dict
# would be vacuous -- EMAIL_PATTERN.sub() has just removed every match by
# construction, so it could only ever report zero. The rendered page is a
# different artefact: it is the template plus the data, and the failure this
# catches is a REGRESSION IN THE REDACTION PATH (someone narrows redact_pii()
# to a field list, someone interpolates from `all_events` instead of `events`,
# someone adds a template field). scripts/test-sync-events-pii.py forces exactly
# that regression and asserts this refuses.


def load_allowlist():
    """Import is_allowed() from scripts/check-published-emails.py.

    The checker owns the list of addresses this project publishes ON PURPOSE
    (team@pdoom1.com in every page footer, the maintainer's address, form
    placeholders). This generator's own template emits one of them per page, so
    the verification below has to know the same list -- and there must be
    exactly one copy of it, for the same reason there is exactly one
    EMAIL_PATTERN. The checker imports the pattern from here; this imports the
    allowlist from there; neither is forked.

    Imported lazily INSIDE the function on purpose: check-published-emails.py
    exec_module()s this file at call time, so a module-level import here would
    be a cycle.

    Deliberately does NOT degrade if the checker is missing. A verification step
    that silently disarms itself is the failure mode this whole change exists to
    remove.
    """
    path = SCRIPT_DIR.parent / "check-published-emails.py"
    if not path.exists():
        log(f"Cannot verify published emails: {path} is missing", "ERROR")
        log("Refusing to generate pages without the allowlist.", "ERROR")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("check_published_emails", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.is_allowed


# ---------------------------------------------------------------------------
# THE INDEPENDENT SCANNER -- and its independence is the entire point of it.
#
# This is the STRUCTURAL half of pdoom-data 12c0455, and it matters more than
# the widened regex above. Until now this repo had exactly ONE definition of
# "what an email address looks like": redact_pii() removes what EMAIL_PATTERN
# matches, find_published_emails() then verifies the rendered pages with
# EMAIL_PATTERN, and check-published-emails.py imports EMAIL_PATTERN from this
# module ON PURPOSE so there would be exactly one copy.
#
# Half of that reasoning is right and half is exactly backwards, and CLAUDE.md
# already states the rule it violates: A CHECK MUST TAKE AT LEAST ONE INPUT FROM
# OUTSIDE THE SYSTEM IT IS CHECKING. One shared pattern guarantees detection and
# verification CANNOT DISAGREE -- which is worth having only if the pattern is
# right, and is a guarantee that they will be wrong together if it is not.
#
# That is not hypothetical; it is the recorded history of this file. The
# brace-group mode was unmatchable, so redact_pii() left those addresses in,
# find_published_emails() then agreed the pages were clean, check-published-
# emails.py agreed a third time because it imports the same object, and
# count_emails() logged zero for the same reason. FOUR independent-looking green
# results, one blind spot, and the upstream fix is the only reason it did not
# ship again.
#
# So this is built on a DIFFERENT PRINCIPLE, not a different regex of the same
# shape. It does not try to recognise an address. It walks every '@' CHARACTER
# in the text and asks what sits on each side of it, which means a mode nobody
# has thought of yet still gets looked at -- the '@' is the one thing an address
# cannot be spelled without.
#
# Disagreement REFUSES THE WRITE. A false alarm costs a human thirty seconds.
# The alternative already happened: 75 academics' addresses on a public site.
#
# The false-positive families are bounded by the SHAPE OF THE DAMAGE, not by an
# allowlist of things to ignore, because an allowlist is a place for the next
# blind spot to hide. Measured against this repo's own 2,204 published pages,
# the families that put a real '@' in the tree are: BibTeX entry types
# (@article{...}), metric notation (pass@k, Acc@100), hardware strings
# (@ 2.20GHz), CSS at-rules (@media, @keyframes) and bare social handles. Every
# one of those is excluded STRUCTURALLY -- by having no person-shaped local part
# to the left, or no domain to the right -- never by name.
_RESIDUE_BIBTEX = re.compile(
    r"@(?:article|inproceedings|incollection|misc|book|booklet|conference"
    r"|inbook|manual|mastersthesis|phdthesis|proceedings|techreport"
    r"|unpublished)\s*\{",
    re.IGNORECASE,
)
_RESIDUE_CSS_AT_RULE = re.compile(
    r"@(?:media|import|supports|keyframes|font-face|charset|namespace|page"
    r"|layer|container|property)\b",
    re.IGNORECASE,
)
# A domain to the RIGHT of the '@'. Deliberately looser than EMAIL_PATTERN's
# domain rule -- it has to be able to see what EMAIL_PATTERN cannot.
_RESIDUE_DOMAIN = re.compile(
    r"^\s{0,2}[A-Za-z0-9][A-Za-z0-9\-]{0,40}"
    r"(?:\s{0,2}[.\-]\s{0,2}[A-Za-z0-9\-]{1,40}){0,6}"
    r"\s{0,2}\.\s{0,2}[A-Za-z]{2,24}"
)
# A person-shaped local part to the LEFT. Same bound as _severed_local_ok():
# a name carries a separator or real length; pass, Acc, lx, P do not.
_RESIDUE_LOCAL = re.compile(r"(\{[^{}@]{1,200}\}|[A-Za-z0-9._%+\-]{1,64})\s{0,2}$")


def _residue_local_is_person_shaped(local: str) -> bool:
    """Does the text left of an '@' look like a person, or like notation?"""
    local = local.split("mailto:", 1)[-1].strip()
    if not re.search(r"[A-Za-z]", local):
        return False
    if "{" in local:
        # A brace group is a LIST OF PEOPLE. It is never notation, and it was
        # the mode that actually shipped, so it is admitted unconditionally.
        return True
    if len(local) >= 4 and re.search(r"[._%+\-]", local):
        return True
    return len(local) >= 5


def residue_positions(text: str) -> set:
    """The INDEX of every '@' that looks like a real person's address.

    Returns POSITIONS, not text and not a bare count.

    Positions rather than a count, because the comparison against EMAIL_PATTERN
    has to be positional to mean anything. The first version of this subtracted
    one total from the other, and that is silently broken: this scanner
    deliberately ignores short locals like the "team@" in the site footer, while
    EMAIL_PATTERN counts every one of them. On a page carrying two footer
    addresses and one real leak the arithmetic reads 1 - 2 = -1, and the leak is
    reported as no disagreement at all. A guard that is muted by the presence of
    ALLOWED addresses is worse than no guard, and it took a planted brace group
    that the guard failed to flag to notice.

    Never the matched text: every caller either logs to
    events-sync-summary.json or prints to CI, and both are public. Reproducing
    the string is how pdoom1#1212 leaked the address it was fixing.
    """
    found = set()
    for m in re.finditer("@", text):
        i = m.start()
        rest = text[i:]
        if _RESIDUE_BIBTEX.match(rest) or _RESIDUE_CSS_AT_RULE.match(rest):
            continue
        if not _RESIDUE_DOMAIN.match(text[i + 1:i + 120]):
            continue
        left = _RESIDUE_LOCAL.search(text[max(0, i - 240):i])
        if not left:
            continue
        if not _residue_local_is_person_shaped(left.group(1)):
            continue
        found.add(i)
    return found


def explained_positions(text: str) -> set:
    """The index of every '@' that falls inside an EMAIL_PATTERN match.

    This is what "the shared definition can see" means, expressed in the same
    coordinates as residue_positions() so the two can actually be compared.
    """
    covered = set()
    for m in EMAIL_PATTERN.finditer(text):
        for k in range(m.start(), m.end()):
            if text[k] == "@":
                covered.add(k)
    return covered


def residue_scan(text: str) -> int:
    """Count of address-shaped residue. Thin wrapper; positions are the truth."""
    return len(residue_positions(text))


def unexplained_residue(text: str) -> int:
    """How many person-shaped '@' the independent route sees and EMAIL_PATTERN
    does NOT cover. Zero means the two agree about this text."""
    return len(residue_positions(text) - explained_positions(text))


def find_published_emails(rendered: Dict[str, str], is_allowed) -> Dict[str, List[str]]:
    """{artefact_name: [address, ...]} for disallowed addresses in rendered output."""
    findings: Dict[str, List[str]] = {}
    for name, text in rendered.items():
        hits = [m for m in EMAIL_PATTERN.findall(text) if not is_allowed(m)]
        if hits:
            findings[name] = hits
    return findings


def find_residue_disagreements(rendered: Dict[str, str], is_allowed) -> Dict[str, int]:
    """{artefact_name: unexplained_count} where the independent scanner sees
    more address-shaped text than EMAIL_PATTERN can account for.

    The subtraction is what makes this a DISAGREEMENT check rather than a second
    detector. Everything EMAIL_PATTERN found is either already redacted or
    already reported by find_published_emails(); what is interesting is the
    REMAINDER, because a positive remainder means the independent route can see
    something the shared definition cannot -- which is precisely the failure
    that shipped 75 addresses and could not be seen from inside.
    """
    findings: Dict[str, int] = {}
    for name, text in rendered.items():
        unexplained = unexplained_residue(text)
        if unexplained > 0:
            findings[name] = unexplained
    return findings


# ---------------------------------------------------------------------------
# Markdown image syntax
#
# Upstream descriptions are Markdown source, not plain prose. The generator
# emits them into HTML contexts that render Markdown NOWHERE -- the body of
# <p class="description"> and the content="..." of three <meta> tags -- so an
# embedded image arrives at the reader as the literal characters
# "![](https://res.cloudinary.com/lesswrong-2-0/image/upload/...png)".
#
# Two things are wrong with that, and only the first is cosmetic:
#   * it reads as a broken page;
#   * it publishes a third party's CDN URL as VISIBLE TEXT, on a site whose
#     rule is not to hand out other people's identifiers (same family as the
#     75 academics' email addresses redact_pii() exists for).
#
# Live in the shipped corpus on 2026-08-03: 12 pages, and 7 of them also fed
# `/events/` its browse-list snippet through events.json. One
# (alignmentforum_d32b2cc700b53f60) is a run of EIGHT images and no prose at
# all, and its description is truncated upstream mid-URL, which is why the
# unterminated form has to be handled too -- otherwise stripping the complete
# images leaves a bare CDN path behind as the tail of the sentence.
#
# MARKING, NOT DELETING -- the same rule as REDACTION_MARKER. A reader who sees
# a gap should be able to tell that something was taken out on purpose. Silently
# dropping the image leaves "Figure 1: Something happens at future time T",
# which reads as prose about a figure that was never there. "[image]" is true:
# the source had an image here and this page does not reproduce it. It also
# means the result is never the empty string, so a description is never
# silently truncated to nothing.
#
# Deliberately NOT rendering the image: these are third-party CDNs, so an <img>
# would leak every reader's IP and referrer to Cloudinary/imgur/Google, and half
# the URLs are relative paths (`images/multiple-pages.svg`) that resolve to
# nothing on this origin.
MARKDOWN_IMAGE_MARKER = "[image]"

# A URL inside Markdown link parentheses contains no whitespace and no bare
# parenthesis; the optional trailing "title" is quoted. Keeping the body that
# tight matters: a loose [^)]* would run past an unmatched "(" in ordinary prose
# and eat the rest of the sentence, which is exactly the silent truncation this
# is supposed to prevent.
MARKDOWN_IMAGE_PATTERN = re.compile(
    r"!\[[^\]\n]*\]"                 # ![alt]
    r"\([^()\s]*"                    # (url
    r"(?:\s+\"[^\"\n]*\")?"          # optional "title"
    r"\)"                            # )
)

# The same thing with its closing paren cut off by an upstream length budget.
# Anchored to end-of-string so it can only ever consume a genuine tail.
TRUNCATED_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]\n]*\]\([^()\s]*$")

_MARKER_RE = re.escape(MARKDOWN_IMAGE_MARKER)
_MARKER_RUN = re.compile(r"%s(?:[ \t]*%s)+" % (_MARKER_RE, _MARKER_RE))


def strip_markdown_images_in_text(text: str) -> str:
    """Replace Markdown image syntax with MARKDOWN_IMAGE_MARKER.

    Prose either side is preserved verbatim -- only the "![...](...)" run is
    replaced -- and a run of adjacent images collapses to one marker, because
    eight consecutive "[image]"s tell the reader nothing the first one did not.
    """
    out = MARKDOWN_IMAGE_PATTERN.sub(MARKDOWN_IMAGE_MARKER, text)
    out = TRUNCATED_MARKDOWN_IMAGE_PATTERN.sub(MARKDOWN_IMAGE_MARKER, out)
    out = _MARKER_RUN.sub(MARKDOWN_IMAGE_MARKER, out)
    # Upstream writes "![](url)The bridge to AGI control" with no separator, so
    # without this the marker fuses onto the first word of the sentence.
    out = re.sub(r"(%s)(?=[^\s])" % _MARKER_RE, r"\1 ", out)
    out = re.sub(r"(?<=[^\s])(%s)" % _MARKER_RE, r" \1", out)
    return out.strip()


def strip_markdown_images(value: Any) -> Any:
    """Recursively strip Markdown images from any nested str/list/dict value.

    Walks the WHOLE record for the same reason redact_pii() does: events.json
    serialises every field, `description` is merely where the corpus happens to
    carry images today, and a field added upstream tomorrow must be covered on
    the day it appears rather than the day someone notices.
    """
    if isinstance(value, str):
        return strip_markdown_images_in_text(value)
    if isinstance(value, list):
        return [strip_markdown_images(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_markdown_images(v) for k, v in value.items()}
    return value


def count_markdown_images(value: Any) -> int:
    """Count Markdown images in a nested structure (for the sync log)."""
    if isinstance(value, str):
        return (len(MARKDOWN_IMAGE_PATTERN.findall(value))
                + len(TRUNCATED_MARKDOWN_IMAGE_PATTERN.findall(value)))
    if isinstance(value, list):
        return sum(count_markdown_images(v) for v in value)
    if isinstance(value, dict):
        return sum(count_markdown_images(v) for v in value.values())
    return 0


# ---------------------------------------------------------------------------
# HTML escaping
#
# Every string below reaches a generated page through an f-string, so the page
# is built by concatenation and the data decides where the markup ends. Event
# descriptions are raw text extracted from paper PDFs -- arXiv accepts uploads
# from anyone -- so "the data is first-party" is not true of the *contents* of
# these fields, only of the pipeline that carries them.
#
# This was not hypothetical. Before this pass, in the shipped corpus:
#   * arxiv_73643a60bb86bf2f's description contains "<<number to be assigned>>",
#     which the browser parses as a tag start in <p class="description"> AND
#     inside the <meta name="description" content="..."> attribute.
#   * arxiv_aa8c44de8cf70353's description contains a double quote inside the
#     first 155 characters, which TERMINATES the meta content attribute early
#     and turns the rest of the sentence into bogus tag attributes.
# Both were live on pdoom1.com.
#
# escape_event_for_html() mirrors redact_pii(): it walks the WHOLE record rather
# than a named list of fields, so a field added upstream tomorrow is covered on
# the day it appears. Fail closed. Non-strings pass through untouched, so ints
# (year, impact deltas) still render as numbers.
def esc(value: Any) -> str:
    """HTML-escape a single value for text OR attribute context.

    Escaping the double quote is not optional: several slots are attribute values
    (content="...", href="..."), and an unescaped double quote in an attribute is
    an injection, not a typo.

    The apostrophe is deliberately NOT escaped, which is where this differs from
    html.escape(s, quote=True). Every attribute in this template is double-quoted
    (test-sync-events.py asserts that as a rule, so the exemption cannot rot), and
    inside a double-quoted attribute an apostrophe is an ordinary character. Escaping
    it anyway would rewrite ~1,194 published pages for no reader-visible change --
    prose is full of apostrophes -- and burying a real fix in a diff that large is
    how a real fix stops getting reviewed.
    """
    return (str(value).replace("&", "&amp;")
                      .replace("<", "&lt;")
                      .replace(">", "&gt;")
                      .replace('"', "&quot;"))


def escape_event_for_html(value: Any) -> Any:
    """Recursively HTML-escape every string in a nested str/list/dict value.

    Deliberately mirrors redact_pii(): whole-record, not a field list. The page
    template interpolates ~20 distinct expressions off the event dict and gains
    more over time; enumerating them is how the leaderboard shipped six escaped
    fields and thirteen unescaped ones.
    """
    if isinstance(value, str):
        return esc(value)
    if isinstance(value, list):
        return [escape_event_for_html(v) for v in value]
    if isinstance(value, dict):
        return {k: escape_event_for_html(v) for k, v in value.items()}
    return value


def meta_text(value: Any, limit: Optional[int] = None) -> str:
    """Prepare an arbitrary event string for a <meta content="..."> slot.

    Escaping alone is not enough for the meta block, which is why this exists
    alongside esc() rather than instead of it. Two extra problems, both present
    in the shipped corpus:
      * newlines and runs of whitespace -- many arXiv-derived descriptions are
        multi-line, so the raw value emitted an attribute spanning six physical
        lines and rendered as a mangled share-card snippet;
      * length -- og:description and twitter:description want a snippet, not the
        whole abstract.

    It does NOT define a second notion of escaping: the last step calls esc(),
    the single escaper this module owns. Order matters -- collapse and truncate
    FIRST, escape LAST, so the character budget counts what a reader sees and a
    cut can never land inside an entity. That means meta_text() must be handed
    the UNESCAPED value (`raw[...]`), never the pre-escaped `event[...]`, or the
    ampersands get escaped twice.
    """
    collapsed = " ".join(str(value).split())
    if limit is not None and len(collapsed) > limit:
        collapsed = collapsed[:limit].rstrip() + "…"
    return esc(collapsed)


def sanitize_urls_in_text(text: str) -> str:
    """Convert HTTP URLs to HTTPS where safe to do so"""
    import re

    # Known safe HTTP -> HTTPS conversions
    safe_conversions = {
        'http://rohinshah.com': 'https://rohinshah.com',
        'http://redwoodresearch.org': 'https://redwoodresearch.org',
        'http://aitracker.org': 'https://aitracker.org',
        'http://arxiv.org': 'https://arxiv.org',
        'http://lesswrong.com': 'https://lesswrong.com',
        'http://www.lesswrong.com': 'https://www.lesswrong.com',
        'http://forum.effectivealtruism.org': 'https://forum.effectivealtruism.org',
        'http://eepurl.com': 'https://eepurl.com',
        'http://alignment-newsletter.libsyn.com': 'https://alignment-newsletter.libsyn.com',
        'http://www.cs.umd.edu': 'https://www.cs.umd.edu',
        'http://amazon.com': 'https://amazon.com',
        'http://acritch.com': 'https://acritch.com',
        'http://proceedings.mlr.press': 'https://proceedings.mlr.press',
        'http://www.jackspencer.org': 'https://www.jackspencer.org',
    }

    result = text
    for http_url, https_url in safe_conversions.items():
        result = result.replace(http_url, https_url)

    return result


def sanitize_event_urls(event: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize URLs throughout an event object"""
    # Sanitize description
    if 'description' in event:
        event['description'] = sanitize_urls_in_text(event['description'])

    # Sanitize reactions
    for reaction_key in ['safety_researcher_reaction', 'media_reaction']:
        if reaction_key in event:
            event[reaction_key] = sanitize_urls_in_text(event[reaction_key])

    # Sanitize sources
    if 'sources' in event:
        event['sources'] = [sanitize_urls_in_text(s) for s in event['sources']]

    return event


def generate_event_detail_page(event_id: str, event: Dict[str, Any]) -> str:
    """Generate HTML for individual event detail page"""

    # Escape ONCE, at the top, for the whole record -- see escape_event_for_html().
    # `raw` keeps the unescaped values for the two contexts where escaping would be
    # wrong: urllib.parse.quote() percent-encodes for a URL (double-escaping would
    # put "%26amp%3B" in a prefilled GitHub issue title), and the meta-description
    # truncation must slice the source text BEFORE escaping or it can cut an entity
    # in half. Everything else below reads the escaped `event`.
    raw = event
    event = escape_event_for_html(event)
    event_id_esc = esc(event_id)

    # Category icons
    category_icons = {
        'funding_catastrophe': '💸',
        'organizational_crisis': '🏢',
        'technical_research_breakthrough': '🔬',
        'institutional_decay': '⚠️',
        'policy_development': '📜',
        'public_awareness': '📢',
        'capability_advance': '🚀',
        'alignment_breakthrough': '🎯',
        'governance_milestone': '⚖️'
    }

    rarity_emoji = {
        'common': '⚪ Common',
        'rare': '🔵 Rare',
        'legendary': '✨ Legendary'
    }

    icon = category_icons.get(event['category'], '📌')
    rarity = rarity_emoji.get(event['rarity'], event['rarity'])

    # Generate impacts table
    # VARIANT B, ruled by Pip 2026-07-31 after an A/B: show the DIRECTION, never the
    # magnitude.
    #
    # Why the number goes and the row stays. Of 1,194 events the calculated effects reach
    # gameplay in one branch -- 7 events. The other 1,174 are flavour, and flavour is
    # hidden by default. So a precise figure like "-80" was presented on ~2,190 pages for
    # events that move nothing. Direction is the part that is probably right; magnitude is
    # the part that is definitely unverified, and precision reads as authority regardless
    # of the caveat above it. A stamp over a number still shows the number, and the number
    # was the false part.
    #
    # The magnitudes are NOT deleted -- they live in the corpus, and the suggestion links
    # at the foot of every page go straight there. Nothing is hidden; it is just no longer
    # asserted here.
    #
    # Precedent from the game's own repo (events.gd:290): displayed doom numbers were
    # removed there for the same reason -- clobbered at resolve, so "every (+/-N doom)
    # message in event content was a silent lie".
    impacts_html = ""
    for impact in event['impacts']:
        change = impact['change']
        direction = 'up' if change > 0 else ('down' if change < 0 else 'unchanged')
        color_class = 'positive' if change > 0 else 'negative'
        condition_text = f" (if {impact['condition']})" if impact.get('condition') else ""

        impacts_html += f"""
				<tr>
					<td>{impact['variable'].replace('_', ' ').title()}</td>
					<td class="impact-{color_class}">proposed: {direction}</td>
					<td>{condition_text or 'Always'}</td>
				</tr>
		"""

    # ABSENT IS NOT A FINDING.  `pdoom_impact` is None on 2,188 of the 2,197
    # generated event pages, and this used to render that as "No direct impact"
    # -- an affirmative claim about what the game does, manufactured out of a
    # missing field.  CLAUDE.md's manufactured-confidence shape (B), absent
    # coerced to a measurement.  The page contradicted itself three lines later:
    # the suggestion link beside this value has always read "Current p(doom)
    # impact: None".  WEB-E1, ruled by Pip 2026-08-24.
    #
    # "Not recorded" is a statement about the corpus, which is what we can see.
    # "No direct impact" is a statement about the game, which we cannot.
    pdoom_display = (
        event['pdoom_impact'] if event.get('pdoom_impact') is not None else 'Not recorded'
    )

    # Generate sources list
    sources_html = ""
    for i, source in enumerate(event['sources'], 1):
        sources_html += f'<li><a href="{source}" target="_blank" rel="noopener">[{i}] {source}</a></li>\n\t\t\t\t'

    # Generate tags
    tags_html = " ".join([f'<span class="tag">#{tag}</span>' for tag in event['tags']])

    # Generate metadata suggestion URLs
    from urllib.parse import quote

    # These read `raw`, not `event`: quote() is the escaper for a URL context, and
    # running it over already-HTML-escaped text would prefill the GitHub issue with
    # "%26amp%3B" where the source said "&". The percent-encoding quote() produces
    # contains no <, > or " , so the finished URL is safe in an href attribute.
    #
    # ROUTING RULE -- which repo a suggestion is addressed to.
    #
    # A suggest-link is this site letting a stranger author a value in another
    # repo's vocabulary. It must therefore land in the repo that OWNS the field,
    # not the repo that happens to store it. The ruling of 2026-08-02 (see
    # pdoom-data#51, coordination#30) is that the direction of authority for
    # game-mechanical fields runs pdoom1 -> pdoom-data. Until 2026-08-06 all five
    # links here pointed at pdoom-data, which meant the public was being invited
    # to file game-balance changes into the repo that is forbidden to decide them.
    #
    #   descriptive metadata about the real-world event  -> pdoom-data
    #     category, tags
    #   game-mechanical values pdoom1 owns               -> pdoom1
    #     rarity, impacts, p(doom) impact
    #
    # Labels are checked against the TARGET repo's label set -- pdoom1 has no
    # `metadata` or `game-balance` label, so reusing pdoom-data's would silently
    # produce unlabelled issues.
    #
    # If coordination#30 item A1 rules differently on rarity -- keep, split, or
    # null it -- the rarity link is the thing to change here, and the browse
    # index's rarity sort tiebreaker and filter facet change with it.
    DATA_LABELS = "metadata,events"
    GAME_LABELS = "game-mechanics,event-system,community"
    DATA_NEW = "https://github.com/PipFoweraker/pdoom-data/issues/new"
    GAME_NEW = "https://github.com/PipFoweraker/pdoom1/issues/new"

    category_suggestion_url = f"{DATA_NEW}?labels={DATA_LABELS}&title=Metadata%3A%20Change%20category%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0ACurrent%20category%3A%20{quote(raw['category'])}%0A%0ASuggested%20category%3A%20%0A%0AReason%3A%20"

    rarity_suggestion_url = f"{GAME_NEW}?labels={GAME_LABELS}&title=Event%20metadata%3A%20Change%20rarity%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0AThis%20is%20a%20game-mechanical%20field%20owned%20by%20pdoom1.%0A%0ACurrent%20rarity%3A%20{quote(raw['rarity'])}%0A%0ASuggested%20rarity%3A%20%0A%0AReason%3A%20"

    tags_suggestion_url = f"{DATA_NEW}?labels={DATA_LABELS}&title=Metadata%3A%20Change%20tags%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0ACurrent%20tags%3A%20{quote(', '.join(raw['tags']))}%0A%0ASuggested%20tags%3A%20%0A%0AReason%3A%20"

    impacts_suggestion_url = f"{GAME_NEW}?labels={GAME_LABELS}&title=Event%20metadata%3A%20Change%20impacts%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0AThis%20is%20a%20game-balance%20change%20owned%20by%20pdoom1.%0A%0ACurrent%20impacts%3A%20{len(event['impacts'])}%20game%20variable%20changes%0A%0ASuggested%20changes%3A%20%0A-%20Variable%3A%20%0A-%20Change%3A%20%0A%0AReason%3A%20"

    pdoom_suggestion_url = f"{GAME_NEW}?labels={GAME_LABELS}&title=Event%20metadata%3A%20Change%20p(doom)%20impact%20for%20{quote(event_id)}&body=Event%3A%20{quote(raw['title'])}%0A%0AThis%20is%20a%20game-balance%20change%20owned%20by%20pdoom1.%0A%0ACurrent%20p(doom)%20impact%3A%20{quote(str(raw.get('pdoom_impact', 'null')))}%0A%0ASuggested%20p(doom)%20impact%3A%20%0A%0AReason%3A%20"

    # Build reaction provenance badges and source info
    def build_reaction_html(reaction_text: str, reaction_key: str) -> str:
        """Build HTML for a reaction with provenance badge and source link"""
        provenance = event.get('reaction_provenance', {})
        reaction_prov = provenance.get(reaction_key, 'placeholder')

        # Handle simple string format
        if isinstance(reaction_prov, str):
            prov_type = reaction_prov
            prov_data = {}
        else:
            prov_type = reaction_prov.get('type', 'placeholder')
            prov_data = reaction_prov

        # Build badge HTML
        badge_html = ""
        source_html = ""

        if prov_type == "placeholder":
            badge_html = '<span class="provenance-badge provenance-placeholder">⚠️ Placeholder - Needs Real Quote</span>'
        elif prov_type == "human_summary":
            badge_html = '<span class="provenance-badge provenance-summary">ℹ️ Summary (Not Direct Quote)</span>'
            if prov_data.get('sources'):
                sources = prov_data['sources'] if isinstance(prov_data['sources'], list) else [prov_data['sources']]
                source_links = ', '.join([f'<a href="{s}" target="_blank" rel="noopener">source</a>' for s in sources])
                source_html = f'<span class="quote-source">Summarized from: {source_links}</span>'
        elif prov_type == "real_quote":
            badge_html = '<span class="provenance-badge provenance-real">✓ Verified Quote</span>'
            if prov_data.get('source'):
                author = prov_data.get('author', 'Unknown')
                date = prov_data.get('date', '')
                date_text = f" ({date})" if date else ""
                source_html = f'<span class="quote-source">— {author}{date_text} (<a href="{prov_data["source"]}" target="_blank" rel="noopener">source</a>)</span>'
        elif prov_type == "not_applicable":
            badge_html = '<span class="provenance-badge" style="opacity: 0.5;">N/A</span>'

        return badge_html, source_html

    safety_badge, safety_source = build_reaction_html(event['safety_researcher_reaction'], 'safety_researcher_reaction')
    media_badge, media_source = build_reaction_html(event['media_reaction'], 'media_reaction')

    # Values shared by <meta name="description"> and the OpenGraph / Twitter
    # card block. Built from `raw`, NOT from the already-escaped `event`:
    # meta_text() collapses and truncates before escaping (see its docstring),
    # so handing it a pre-escaped string would double-escape the ampersands and
    # let a cut land inside an entity. `event_id_esc` is reused rather than
    # re-derived so the canonical URL and og:url cannot drift apart.
    page_url = f"{SITE_ORIGIN}/events/{event_id_esc}.html"
    og_title = meta_text(raw['title'])
    og_description = meta_text(raw['description'], META_DESCRIPTION_CHARS)

    html_content = f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>{event['title']} | p(Doom)1 Events</title>
	<link rel="canonical" href="{page_url}" />
	<meta name="description" content="{og_description}" />

	<!-- Share cards. Without these an event link pastes as a bare URL. -->
	<meta property="og:type" content="article" />
	<meta property="og:site_name" content="p(Doom)1" />
	<meta property="og:title" content="{og_title}" />
	<meta property="og:description" content="{og_description}" />
	<meta property="og:url" content="{page_url}" />
	<meta property="og:image" content="{OG_IMAGE_URL}" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content="{og_title}" />
	<meta name="twitter:description" content="{og_description}" />
	<!-- twitter:site intentionally omitted until the handle is finalized,
	     matching public/index.html. -->

	<!-- Analytics consent shim. MUST stay above the deferred tracker below:
	     this tag is parser-blocking, so it sets localStorage.plausible_ignore
	     (from Do-Not-Track or an explicit opt-out) before the deferred script
	     runs and fires its pageview. Without it on this page, a deep-linked
	     visitor is counted before the privacy page's promise can be honoured.
	     It never injects a tracker -- see public/assets/js/analytics.js. -->
	<script src="/assets/js/analytics.js"></script>

	<!-- Plausible Analytics -->
	<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.file-downloads.outbound-links.pageview-props.tagged-events.js"></script>

	<link rel="stylesheet" href="/css/site.css">
	<link rel="stylesheet" href="/css/stamp.css">
	<style>
		:root {{
			/* Palette derived from the game's shipped art: amber-dominant CRT chrome
			   with a teal counterpoint over warm near-black. Green is demoted to
			   --phosphor (OK-state / terminal flourish only), matching
			   godot/scripts/ui/terminal_theme.gd: amber = PLAN register, green = WATCH. */
			--bg-primary: #12100F;
			--bg-secondary: #1C1917;
			--bg-tertiary: #262220;
			--text-primary: #E9F2F2;
			--text-secondary: #CFC7BB;
			--text-muted: #A79E92;
			--accent-primary: #F6A800;
			--accent-secondary: #2FD4C2;
			--accent-danger: #E2524A;
			--border-color: #3A342E;
			--success-color: #4FB37A;
			--radius-md: 6px;
			/* extended semantic tokens */
			--border-strong: #574E44;
			--accent-alt: #2FD4C2;
			--phosphor: #5BE87A;
			--warning: #E9752E;
		}}

		body {{
			font-family: 'Courier New', monospace;
			background: var(--bg-primary);
			color: var(--text-primary);
			line-height: 1.6;
			margin: 0;
			padding: 0;
		}}

		header {{
			background: rgba(28, 25, 23, 0.95);
			border-bottom: 2px solid var(--accent-primary);
			padding: 1rem 0;
		}}

		nav {{
			max-width: 1200px;
			margin: 0 auto;
			padding: 0 1rem;
			display: flex;
			justify-content: space-between;
			align-items: center;
		}}

		.breadcrumb {{
			color: var(--text-muted);
			font-size: 0.9rem;
		}}

		.breadcrumb a {{
			color: var(--accent-primary);
			text-decoration: none;
		}}

		main {{
			max-width: 900px;
			margin: 2rem auto;
			padding: 0 1rem;
		}}

		.event-header {{
			background: linear-gradient(135deg, var(--bg-secondary), var(--bg-tertiary));
			border: 1px solid var(--border-color);
			border-radius: var(--radius-md);
			padding: 2rem;
			margin-bottom: 2rem;
		}}

		.event-icon {{
			font-size: 4rem;
			margin-bottom: 1rem;
		}}

		.event-title {{
			font-size: 2.5rem;
			color: var(--accent-primary);
			margin-bottom: 1rem;
		}}

		.event-meta {{
			display: flex;
			gap: 1.5rem;
			flex-wrap: wrap;
			margin-bottom: 1.5rem;
			font-size: 0.95rem;
		}}

		.meta-item {{
			display: flex;
			align-items: center;
			gap: 0.5rem;
		}}

		.category-badge {{
			background: var(--accent-secondary);
			color: var(--bg-primary);
			padding: 0.3rem 0.8rem;
			border-radius: 4px;
			font-weight: bold;
			text-transform: uppercase;
			font-size: 0.85rem;
		}}

		.rarity-badge {{
			background: var(--bg-tertiary);
			color: var(--text-primary);
			padding: 0.3rem 0.8rem;
			border-radius: 4px;
			border: 1px solid var(--border-color);
		}}

		.section {{
			background: var(--bg-secondary);
			border: 1px solid var(--border-color);
			border-radius: var(--radius-md);
			padding: 1.5rem;
			margin-bottom: 1.5rem;
		}}

		.section h2 {{
			color: var(--accent-secondary);
			margin-bottom: 1rem;
			font-size: 1.5rem;
		}}

		.description {{
			font-size: 1.1rem;
			line-height: 1.8;
			color: var(--text-secondary);
		}}

		.impacts-table {{
			width: 100%;
			border-collapse: collapse;
		}}

		.impacts-table th {{
			background: var(--bg-tertiary);
			padding: 0.8rem;
			text-align: left;
			color: var(--accent-primary);
			border-bottom: 2px solid var(--border-color);
		}}

		.impacts-table td {{
			padding: 0.8rem;
			border-bottom: 1px solid var(--border-color);
		}}

		.impact-positive {{
			/* phosphor = the demoted terminal green, kept for live OK-state readouts */
			color: var(--phosphor);
			font-weight: bold;
		}}

		.impact-negative {{
			color: var(--accent-danger);
			font-weight: bold;
		}}

		.quote {{
			background: var(--bg-tertiary);
			border-left: 4px solid var(--accent-primary);
			padding: 1rem 1.5rem;
			margin: 1.5rem 0;
			font-style: italic;
		}}

		.quote-label {{
			font-weight: bold;
			color: var(--accent-primary);
			font-style: normal;
			display: block;
			margin-bottom: 0.5rem;
		}}

		.sources {{
			list-style: none;
			padding: 0;
		}}

		.sources li {{
			margin-bottom: 0.8rem;
		}}

		.sources a {{
			color: var(--accent-primary);
			text-decoration: none;
			word-break: break-all;
		}}

		.sources a:hover {{
			text-decoration: underline;
		}}

		.tags {{
			display: flex;
			gap: 0.5rem;
			flex-wrap: wrap;
		}}

		.tag {{
			background: var(--bg-primary);
			padding: 0.4rem 0.8rem;
			border-radius: 4px;
			font-size: 0.9rem;
			color: var(--text-muted);
		}}

		.metadata-section {{
			background: var(--bg-secondary);
			border: 1px solid var(--border-color);
			border-radius: var(--radius-md);
			padding: 1.5rem;
			margin-bottom: 1.5rem;
		}}

		.metadata-grid {{
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
			gap: 1rem;
			margin-top: 1rem;
		}}

		.metadata-item {{
			background: var(--bg-tertiary);
			padding: 1rem;
			border-radius: 4px;
			border: 1px solid var(--border-color);
		}}

		.metadata-label {{
			font-weight: bold;
			color: var(--accent-primary);
			font-size: 0.85rem;
			display: block;
			margin-bottom: 0.5rem;
		}}

		.metadata-value {{
			color: var(--text-secondary);
			font-size: 0.95rem;
		}}

		.suggest-link {{
			display: inline-block;
			margin-top: 0.5rem;
			color: var(--accent-secondary);
			text-decoration: none;
			font-size: 0.85rem;
			transition: color 0.3s;
		}}

		.suggest-link:hover {{
			color: var(--accent-primary);
			text-decoration: underline;
		}}

		.provenance-badge {{
			display: inline-block;
			padding: 0.25rem 0.6rem;
			border-radius: 4px;
			font-size: 0.75rem;
			font-weight: bold;
			margin-left: 0.5rem;
			vertical-align: middle;
		}}

		/* Tint alpha is 0.12, not 0.20: the badge text sits on the *blended* tint,
		   and at 0.20 the warning variant only reaches 4.36:1 (WCAG AA fail).
		   At 0.12 the three variants measure 4.97 / 7.55 / 5.61. */
		.provenance-placeholder {{
			background: rgba(233, 117, 46, 0.12);
			border: 1px solid var(--warning);
			color: var(--warning);
		}}

		.provenance-summary {{
			background: rgba(47, 212, 194, 0.12);
			border: 1px solid var(--accent-alt);
			color: var(--accent-alt);
		}}

		.provenance-real {{
			background: rgba(79, 179, 122, 0.12);
			border: 1px solid var(--success-color);
			color: var(--success-color);
		}}

		.quote-source {{
			display: block;
			margin-top: 0.5rem;
			font-size: 0.85rem;
			color: var(--text-muted);
		}}

		.quote-source a {{
			color: var(--accent-secondary);
			text-decoration: none;
		}}

		.quote-source a:hover {{
			text-decoration: underline;
		}}

		.suggest-quote-button {{
			display: inline-block;
			margin-top: 0.75rem;
			padding: 0.5rem 1rem;
			background: rgba(47, 212, 194, 0.1);
			border: 1px solid var(--accent-secondary);
			border-radius: 4px;
			color: var(--accent-secondary);
			text-decoration: none;
			font-size: 0.85rem;
			transition: all 0.3s;
		}}

		.suggest-quote-button:hover {{
			background: var(--accent-secondary);
			color: var(--bg-primary);
			transform: translateY(-2px);
		}}

		.contribute-section {{
			background: linear-gradient(135deg, var(--bg-secondary), rgba(47, 212, 194, 0.1));
			border: 1px solid var(--accent-secondary);
			border-radius: var(--radius-md);
			padding: 1.5rem;
			text-align: center;
		}}

		.cta-button {{
			display: inline-block;
			background: var(--accent-secondary);
			color: var(--bg-primary);
			padding: 0.8rem 1.5rem;
			text-decoration: none;
			border-radius: 4px;
			font-weight: bold;
			margin: 0.5rem;
			transition: transform 0.3s;
		}}

		.cta-button:hover {{
			transform: translateY(-2px);
		}}

		footer {{
			background: var(--bg-secondary);
			border-top: 2px solid var(--accent-primary);
			text-align: center;
			padding: 2rem 1rem;
			margin-top: 4rem;
			color: var(--text-muted);
		}}
	</style>
</head>
<body>
	<header>
		<nav>
			<div class="breadcrumb">
				<a href="/">Home</a> / <a href="/events/">Events</a> / {event['title']}
			</div>
		</nav>
	</header>

	<main>
		<div class="event-header">
			<div class="event-icon">{icon}</div>
			<h1 class="event-title">{event['title']}</h1>

			<div class="event-meta">
				<div class="meta-item">
					<span>📅</span>
					<span><strong>{event['year']}</strong></span>
				</div>
				<div class="meta-item">
					<span class="category-badge">{event['category'].replace('_', ' ')}</span>
				</div>
				<div class="meta-item">
					<span class="rarity-badge">{rarity}</span>
				</div>
			</div>

			<div class="tags">
				{tags_html}
			</div>
		</div>

		<div class="section">
			<h2>📖 Description</h2>
			<p class="description">{event['description']}</p>
		</div>

		<div class="section stamp-block">
			<h2>📊 Game Impacts</h2>
			<span class="stamp stamp--restricted stamp--sm">Not verified in game</span>
			<p class="stamp-body">
				Which variables this event was <em>proposed</em> to move, and in which
				direction. The magnitudes are held in the corpus but are not shown here,
				because they have not been verified against the shipped game. They come from
				<a href="https://github.com/PipFoweraker/pdoom-data" target="_blank" rel="noopener">pdoom-data</a>.
				They describe what an event was <em>proposed</em> to do, not what the
				shipped game does with it. <strong>Most events in the corpus are flavour:
				they are shown for colour and do not move any game variable.</strong> Only a
				small minority reach the systems below, and several of the variables listed
				here are not read by the game at all yet.
				Treat this table as a design proposal under review, not as a measurement of
				play. Corrections and arguments are welcome &mdash; the suggestion links at
				the foot of this page go straight to the data repo.
			</p>
			<table class="impacts-table">
				<thead>
					<tr>
						<th>Variable</th>
						<th>Direction</th>
						<th>Condition</th>
					</tr>
				</thead>
				<tbody>
					{impacts_html}
				</tbody>
			</table>
		</div>

		<div class="section">
			<h2>💭 Reactions</h2>

			<div class="quote">
				<span class="quote-label">🔬 Safety Researcher Reaction:</span>
				{safety_badge}
				<br>
				"{event['safety_researcher_reaction']}"
				{safety_source}
			</div>

			<div class="quote">
				<span class="quote-label">📰 Media Reaction:</span>
				{media_badge}
				<br>
				"{event['media_reaction']}"
				{media_source}
			</div>

			<a href="/events/suggest-quote.html?event={quote(event_id)}" class="suggest-quote-button">
				💡 Found a Real Quote? Suggest it here
			</a>
		</div>

		<div class="section">
			<h2>🔗 Sources</h2>
			<ul class="sources">
				{sources_html}
			</ul>
		</div>

		<div class="metadata-section">
			<h2>🏷️ Event Metadata</h2>
			<p style="color: var(--text-muted); margin-bottom: 1rem;">
				Think this event's metadata could be improved? Category and tags describe the real-world event and are maintained in <a href="https://github.com/PipFoweraker/pdoom-data" target="_blank" rel="noopener">pdoom-data</a>. Rarity, game impacts and p(doom) effects are game-mechanical values owned by <a href="https://github.com/PipFoweraker/pdoom1" target="_blank" rel="noopener">pdoom1</a>. Each link below goes to the repository that decides that field.
			</p>

			<div class="metadata-grid">
				<div class="metadata-item">
					<span class="metadata-label">📁 Category</span>
					<span class="metadata-value">{event['category'].replace('_', ' ').title()}</span>
					<a href="{category_suggestion_url}" class="suggest-link" target="_blank">→ Suggest different category</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">⭐ Rarity</span>
					<span class="metadata-value">{rarity}</span>
					<a href="{rarity_suggestion_url}" class="suggest-link" target="_blank">→ Suggest different rarity</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">🏷️ Tags ({len(event['tags'])})</span>
					<span class="metadata-value">{', '.join(event['tags'])}</span>
					<a href="{tags_suggestion_url}" class="suggest-link" target="_blank">→ Suggest tag changes</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">📊 Game Impacts ({len(event['impacts'])})</span>
					<span class="metadata-value">{len(event['impacts'])} variable changes</span>
					<a href="{impacts_suggestion_url}" class="suggest-link" target="_blank">→ Suggest impact changes</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">☢️ p(Doom) Impact</span>
					<span class="metadata-value">{pdoom_display}</span>
					<a href="{pdoom_suggestion_url}" class="suggest-link" target="_blank">→ Suggest p(doom) change</a>
				</div>

				<div class="metadata-item">
					<span class="metadata-label">📝 General Metadata</span>
					<span class="metadata-value">Year, description, reactions</span>
					<a href="/events/suggest-metadata.html?event={quote(event_id)}" class="suggest-link">→ Comprehensive review</a>
				</div>
			</div>
		</div>

		<div class="contribute-section">
			<h2>🤝 Found an Issue?</h2>
			<p>This event data is sourced from the pdoom-data repository. If you notice errors or want to suggest improvements:</p>
			<a href="https://github.com/PipFoweraker/pdoom-data/issues/new?title=Event%20Issue:%20{quote(event_id)}" class="cta-button" target="_blank">GitHub Issue (Preferred)</a>
			<a href="mailto:team@pdoom1.com?subject=Event%20Data%20Issue:%20{quote(event_id)}&amp;body=Event:%20{quote(raw['title'])}%0A%0AWhat's wrong:%20%0A%0ASuggested fix:%20" class="cta-button">📧 Email (No GitHub)</a>
		</div>

		<div style="text-align: center; margin-top: 2rem;">
			<a href="/events/" style="color: var(--accent-primary); text-decoration: none;">← Back to All Events</a>
		</div>
	</main>

	<footer>
		<p>&copy; 2025 p(Doom)1 | <a href="https://github.com/PipFoweraker/pdoom1" style="color: var(--accent-primary);">GitHub</a></p>
		<p style="margin-top: 0.5rem; font-size: 0.9rem;">Event data from <a href="https://github.com/PipFoweraker/pdoom-data" target="_blank" style="color: var(--accent-secondary);">pdoom-data</a></p>
	</footer>
</body>
</html>
"""

    return html_content


def render_events_json(events: Dict[str, Any]) -> str:
    """Serialise events.json.

    Split from the write so the verification below inspects the EXACT bytes that
    will be written. Verifying a second, separately-produced serialisation would
    leave a gap between what was checked and what shipped.
    """
    return json.dumps(events, indent=2)


def write_events_json(text: str):
    """Write events.json for the events index page.

    TEMP-AND-RENAME, so a crash mid-write cannot leave a truncated or empty file
    behind. D6 of pdoom1-website#384: the floor above stops us CHOOSING to write
    an empty index; this stops us leaving one by accident. os.replace is atomic
    within a filesystem on both POSIX and Windows, so a reader either sees the
    whole old file or the whole new one and never a half-written index.

    The temp file is created in the SAME directory as the target, not in the
    system temp dir -- a cross-filesystem replace is not atomic and would
    degrade silently back to the behaviour this replaces.
    """
    output_file = DATA_DIR / "events.json"
    tmp_file = output_file.with_suffix(".json.tmp")

    try:
        with open(tmp_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, output_file)
    except BaseException:
        # Includes KeyboardInterrupt and SystemExit on purpose: an interrupted
        # sync must not leave a .tmp beside the real file for someone to find
        # later and wonder about.
        try:
            if tmp_file.exists():
                tmp_file.unlink()
        except OSError:
            pass
        raise

    log(f"Wrote events index to {output_file}")


def sync_icons(pdoom1_path: Path):
    """Sync game icons from pdoom1 repository"""
    icons_source = pdoom1_path / "art_generated" / "game_icons" / "v1"

    if not icons_source.exists():
        log(f"Icons directory not found: {icons_source}", "WARN")
        log("Skipping icon sync", "WARN")
        return

    # Copy 128px versions of event-related icons
    icon_patterns = [
        "*funding*_128.png",
        "*crisis*_128.png",
        "*research*_128.png",
        "*breakthrough*_128.png",
    ]

    copied = 0
    for pattern in icon_patterns:
        for icon_file in icons_source.glob(pattern):
            dest = ICONS_DIR / icon_file.name
            shutil.copy2(icon_file, dest)
            copied += 1

    log(f"Synced {copied} event icons from pdoom1")


def main():
    parser = argparse.ArgumentParser(description="Sync events from pdoom-data to pdoom1-website")
    parser.add_argument(
        "--pdoom-data-path",
        type=Path,
        default=DEFAULT_PDOOM_DATA,
        help=f"Path to pdoom-data repository (default: {DEFAULT_PDOOM_DATA})"
    )
    parser.add_argument(
        "--pdoom1-path",
        type=Path,
        default=DEFAULT_PDOOM1,
        help=f"Path to pdoom1 repository (default: {DEFAULT_PDOOM1})"
    )
    parser.add_argument(
        "--sync-icons",
        action="store_true",
        help="Also sync game icons from pdoom1 repository"
    )

    args = parser.parse_args()

    log("=" * 60)
    log("Starting events sync from pdoom-data")
    log("=" * 60)

    # Ensure directories exist
    ensure_directories()

    # Load events
    all_events = load_events_from_pdoom_data(args.pdoom_data_path)

    # Filter events (exclude newsletters and explicitly excluded)
    events = filter_events(all_events)

    # The floor again, on THIS side of the filter, and at the CALL SITE rather
    # than inside filter_events(). A healthy upstream whose events all suddenly
    # carry event_status: excluded publishes exactly the same empty index as an
    # empty upstream, and the check on load would have passed it. Putting it
    # here keeps filter_events() a pure filter -- a floor inside it would make
    # the function unusable on any small fixture, including this repo's own
    # tests, which is how a guard ends up being loosened until it cannot fire.
    assert_corpus_floor(events, "the corpus after filtering")

    # Sanitize HTTP URLs to HTTPS
    log("Sanitizing HTTP URLs to HTTPS...")
    url_changes = 0
    for event_id, event in events.items():
        before = json.dumps(event)
        events[event_id] = sanitize_event_urls(event)
        after = json.dumps(events[event_id])
        if before != after:
            url_changes += 1
    if url_changes > 0:
        log(f"Sanitized URLs in {url_changes} events")

    # Redact third-party email addresses harvested out of paper PDFs.
    # Runs AFTER the URL pass so the https rewrite still sees whole strings,
    # and BEFORE page generation and write_events_json() so neither surface
    # can publish one. See redact_pii() for why it walks the whole record.
    log("Redacting third-party email addresses...")
    emails_found = 0
    events_with_emails = 0
    for event_id, event in events.items():
        n = count_emails(event)
        if n:
            emails_found += n
            events_with_emails += 1
            events[event_id] = redact_pii(event)
    if emails_found:
        log(f"Redacted {emails_found} email addresses across {events_with_emails} events")
    else:
        log("No email addresses found in event data")

    # ADVISORY: address-shaped strings EMAIL_PATTERN cannot match. Never blocks;
    # see OBFUSCATED_CONTACT_PATTERN for why the alternative is a noisy gate.
    obfuscated_count = sum(count_obfuscated_contacts(e) for e in events.values())
    obfuscated_events = sorted(
        event_id for event_id, event in events.items()
        if count_obfuscated_contacts(event)
    )
    if obfuscated_count:
        log(
            f"ADVISORY: {obfuscated_count} obfuscated contact string(s) across "
            f"{len(obfuscated_events)} event(s) were NOT redacted -- "
            f"EMAIL_PATTERN does not match forms like 'name [at] domain.edu'. "
            f"Events: {', '.join(obfuscated_events[:20])}"
            + (" ..." if len(obfuscated_events) > 20 else ""),
            "WARN",
        )
    else:
        log("No obfuscated contact strings detected")

    # Replace Markdown image syntax with a marker. Upstream descriptions are
    # Markdown; neither <p class="description"> nor a <meta content="..."> slot
    # renders it, so an image arrives as a literal CDN URL in the reader's face.
    # Runs AFTER redaction (so an address inside an image title is still caught
    # by the address pass) and BEFORE page generation and write_events_json(),
    # so neither surface can publish one. See strip_markdown_images().
    log("Stripping Markdown image syntax from event text...")
    images_found = 0
    events_with_images = 0
    for event_id, event in events.items():
        n = count_markdown_images(event)
        if n:
            images_found += n
            events_with_images += 1
            events[event_id] = strip_markdown_images(event)
    if images_found:
        log(f"Replaced {images_found} Markdown images across {events_with_images} events")
    else:
        log("No Markdown image syntax found in event data")

    # Render EVERYTHING to memory first. Nothing touches disk until the
    # verification below has passed -- see the "Pre-write verification" block.
    log("Generating event detail pages...")
    rendered: Dict[str, str] = {}
    for event_id, event in events.items():
        rendered[f"public/events/{event_id}.html"] = generate_event_detail_page(event_id, event)

    events_json_text = render_events_json(events)
    rendered["public/data/events.json"] = events_json_text

    # THE GATE. Refuse to publish rather than publish-and-alert: an address that
    # reaches public/ has already been committed, deployed and crawled by the
    # time any detector speaks up.
    log("Verifying no third party's email address reached the rendered output...")
    is_allowed = load_allowlist()
    leaks = find_published_emails(rendered, is_allowed)
    if leaks:
        distinct = {a for hits in leaks.values() for a in hits}
        log("=" * 60, "ERROR")
        log(
            f"REFUSING TO WRITE: {len(distinct)} disallowed email address(es) "
            f"survived redaction and reached {len(leaks)} rendered artefact(s).",
            "ERROR",
        )
        for name in sorted(leaks)[:20]:
            log(f"  {name}: {len(leaks[name])} occurrence(s)", "ERROR")
        if len(leaks) > 20:
            log(f"  ... and {len(leaks) - 20} more artefact(s)", "ERROR")
        log("", "ERROR")
        log("NOTHING WAS WRITTEN. public/ is unchanged and there is nothing to "
            "commit. Fix redact_pii() / EMAIL_PATTERN in this file, or the data "
            "in pdoom-data, then re-run.", "ERROR")
        log("The addresses themselves are deliberately not printed -- CI logs "
            "are public.", "ERROR")
        log("=" * 60, "ERROR")
        sys.exit(1)

    # THE SECOND OPINION, and it is allowed to disagree with the first.
    #
    # find_published_emails() above cannot fail in the one way that has actually
    # cost us: it shares EMAIL_PATTERN with the redactor, so if the pattern is
    # blind to a mode, the redaction misses it AND this verification confirms
    # the miss. residue_scan() reaches the same question from the '@' character
    # instead of from a shape, so it is not blind in the same places -- and a
    # count it cannot explain is exactly the signature of a mode nobody has
    # written a rule for yet.
    #
    # This BLOCKS. An unexplained residue means the shared definition has a hole
    # in it, and the entire history of this file says that a hole in the shared
    # definition is how addresses reach production.
    disagreements = find_residue_disagreements(rendered, is_allowed)
    if disagreements:
        total = sum(disagreements.values())
        log("=" * 60, "ERROR")
        log(
            f"REFUSING TO WRITE: the independent scanner found {total} "
            f"address-shaped item(s) across {len(disagreements)} artefact(s) "
            f"that EMAIL_PATTERN cannot account for.",
            "ERROR",
        )
        for name in sorted(disagreements)[:20]:
            log(f"  {name}: {disagreements[name]} unexplained", "ERROR")
        if len(disagreements) > 20:
            log(f"  ... and {len(disagreements) - 20} more artefact(s)", "ERROR")
        log("", "ERROR")
        log("This is a DISAGREEMENT, not a second detection. The two checks are "
            "built on different principles precisely so they can disagree; when "
            "they do, the shared definition is the thing to suspect.", "ERROR")
        log("Widen EMAIL_PATTERN to cover the mode, or characterise the new "
            "false-positive family STRUCTURALLY in residue_scan() -- never by "
            "adding a name to an allowlist.", "ERROR")
        log("NOTHING WAS WRITTEN. Counts only; CI logs are public.", "ERROR")
        log("=" * 60, "ERROR")
        sys.exit(1)

    log(f"Verified {len(rendered)} rendered artefacts: no disallowed addresses, "
        f"and the independent scanner agrees")

    # Verification passed. Only now does anything reach disk.
    for name, html_content in rendered.items():
        if not name.startswith("public/events/"):
            continue
        output_file = EVENTS_DIR / Path(name).name

        # newline='\n' pins LF output. Without it, a Windows run writes CRLF;
        # git's autocrlf clean filter silently REFUSES to normalise any file
        # that already contains a lone CR (one arXiv description does), so that
        # page alone would be committed with CRLF and show up as a whole-file
        # rewrite in every future diff.
        with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(html_content)

    log(f"Generated {len(events)} event detail pages")

    # Write events.json for index page
    write_events_json(events_json_text)

    # Optionally sync icons
    if args.sync_icons:
        log("Syncing game icons...")
        sync_icons(args.pdoom1_path)

    log("=" * 60)
    log(f"✅ Sync complete! {len(events)} events processed")
    log("=" * 60)
    log(f"Events index: {EVENTS_DIR / 'index.html'}")
    log(f"Events data: {DATA_DIR / 'events.json'}")
    log(f"Event pages: {EVENTS_DIR}/*.html")

    # Analyze quote quality
    def get_provenance_type(event: Dict[str, Any], reaction_key: str) -> str:
        """Get the provenance type for a reaction"""
        prov = event.get('reaction_provenance', {}).get(reaction_key, 'placeholder')
        if isinstance(prov, str):
            return prov
        return prov.get('type', 'placeholder')

    quote_stats = {
        'real_quotes': 0,
        'human_summaries': 0,
        'placeholders': 0,
        'not_applicable': 0
    }

    for event in events.values():
        safety_type = get_provenance_type(event, 'safety_researcher_reaction')
        media_type = get_provenance_type(event, 'media_reaction')

        # Count based on "best" provenance type for the event
        if safety_type == 'real_quote' or media_type == 'real_quote':
            quote_stats['real_quotes'] += 1
        elif safety_type == 'human_summary' or media_type == 'human_summary':
            quote_stats['human_summaries'] += 1
        elif safety_type == 'not_applicable' and media_type == 'not_applicable':
            quote_stats['not_applicable'] += 1
        else:
            quote_stats['placeholders'] += 1

    # Create summary report
    summary = {
        "sync_timestamp": datetime.now().isoformat(),
        "total_events_in_source": len(all_events),
        "included_events": len(events),
        "excluded_events": len(all_events) - len(events),
        "categories": len(set(e['category'] for e in events.values())),
        # Counts only, never the strings or the event ids: this file is written
        # under public/ and is served from pdoom1.com, so naming which events
        # carry a contact string would republish a pointer to the thing that was
        # just redacted. The ids go to the job log, which is not a web page.
        "pii": {
            "emails_redacted": emails_found,
            "events_with_emails": events_with_emails,
            "obfuscated_contact_suspects": obfuscated_count,
            "_note": (
                "emails_redacted are addresses EMAIL_PATTERN matched and replaced. "
                "obfuscated_contact_suspects are address-shaped strings it cannot "
                "match (e.g. 'name [at] domain.edu') and therefore did NOT redact -- "
                "advisory, non-blocking, see pdoom1-website#240."
            ),
        },
        "events_by_rarity": {
            rarity: len([e for e in events.values() if e['rarity'] == rarity])
            for rarity in ['common', 'rare', 'legendary']
        },
        "year_range": [
            min(e['year'] for e in events.values()),
            max(e['year'] for e in events.values())
        ],
        "event_status_breakdown": {
            "newsletter_archive": len([e for e in all_events.values() if e.get('event_status') == 'newsletter_archive']),
            "excluded": len([e for e in all_events.values() if e.get('event_status') == 'excluded']),
            "review_needed": len([e for e in events.values() if e.get('event_status') == 'review_needed']),
            "included": len([e for e in events.values() if e.get('event_status', 'included') == 'included'])
        },
        "quote_quality_stats": {
            "events_with_real_quotes": quote_stats['real_quotes'],
            "events_with_summaries": quote_stats['human_summaries'],
            "events_with_placeholders": quote_stats['placeholders'],
            "events_not_applicable": quote_stats['not_applicable'],
            "completion_percentage": round((quote_stats['real_quotes'] / len(events)) * 100, 1) if len(events) > 0 else 0.0,
            "goal_q1_2025": 50,
            "goal_q2_2025": 100,
            "goal_end_2025": 300
        }
    }

    summary_file = DATA_DIR / "events-sync-summary.json"
    with open(summary_file, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(summary, f, indent=2)

    log(f"Summary report: {summary_file}")


if __name__ == "__main__":
    main()
