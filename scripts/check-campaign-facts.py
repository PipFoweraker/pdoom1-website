#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Campaign fact-guards: check the CONSTRAINT, never trust the pinned VALUE.

WHY THIS EXISTS
---------------
Every file in content/campaigns/ carries a `_facts_this_copy_must_not_break`
block: the things the person drafting social copy must not contradict. Until
2026-08-14 it was an array of plain prose strings -- no source, no date, nothing
that could ask whether they were still true. Two of them had quietly become
lies:

    "Windows build ships today (v0.13.0). macOS and Linux are NOT yet released"
    "Do NOT promise leaderboards or scores - remote submission is not live yet"

All three platforms ship (version.json, derived from the release's assets) and
the board holds real scores. A third, the "open source" licence claim, was false
too and was corrected by hand in #284 -- by hand, because nothing was watching.

THE DEFECT IS NOT THE TWO WRONG SENTENCES. It is that a block named "facts this
copy must not break" pinned CLAIMS ABOUT A MOVING WORLD as if they were
immutable. Facts about a live project rot. What is actually immutable is the
CONSTRAINT:

    value       "macOS and Linux are NOT yet released"
    constraint  "do not promise a platform that is not downloadable"

    value       "do NOT promise leaderboards, submission is not live"
    constraint  "do not promise a feature that is not live"

A constraint stated that way can be checked against a source on every run
instead of decaying between them. That is what this script does.

THE FIVE TIERS, AND WHY THERE ARE FIVE
--------------------------------------
Each entry declares `verify`, which is a statement about WHAT KIND OF THING it
is. Forcing that declaration is most of the value here -- it is no longer
possible to write a world-claim into this block without saying how anyone would
know it is still true.

  checked    Asserts something about the world that THIS script verifies
             offline against an in-repo source. Blocking.
  delegated  Asserts something another wired guard already owns. This script
             checks that the guard still exists and is still referenced by a
             workflow -- i.e. that the delegation is real. Blocking.
  online     Verifiable, but only over the network (a GitHub issue's state).
             Checked with --online, which only the ADVISORY job runs; the
             blocking job prints NOT CHECKED and counts it. Never silent.
  human      Asserts something about the world that no machine here can check.
             Says so, in the entry, with why_not_machine, a source a human can
             read, and a dated human_verified stamp that EXPIRES. An honest
             "unverifiable, human-reviewed, as of DATE" beats a false green.
  durable    Asserts nothing about the world -- a pure editorial rule, e.g.
             "lead with the fork, not a version number". It cannot rot, so it
             needs no source and no clock. It must NOT carry one: a source on a
             claim-free rule is decoration that makes the other tiers look
             optional.

WHAT EXPIRES IS THE ACCEPTANCE, NEVER THE FINDING
-------------------------------------------------
A `human` entry is green until its `review_by`, then RED on "this human
verification expired, re-verify or fix" -- not on the underlying claim. That red
is always closeable by a person deciding something, which is what stops it
becoming the permanent red CLAUDE.md forbids. The rule and its wording are
scripts/acknowledgements.py's; the warn window is read from that ledger's
`policy.warn_within_days` rather than typed here.

The clock lives INLINE in the campaign file rather than in
data/acknowledgements.json, and that is a deliberate departure. The ledger is
for a finding a check reports and somebody tolerates; a `human` entry is not a
finding, it is a fact's epistemic status, and the person who will act on it is
the one drafting copy -- who reads the campaign file and nothing else. A review
date one file away from its only reader is a date nobody reads.

The ledger IS used, for exactly the thing it is for: one real finding this check
reports today and does not fail on (the alpha-launch copy defers platforms that
have since shipped). See data/acknowledgements.json.

WHAT IT WILL NOT DO
-------------------
It does not rewrite copy and it does not fail a campaign that has already been
POSTED. Once a post is out, its text is a historical record; the remedy for a
stale claim in it is not to edit the file, and a check that demanded that would
be asking someone to falsify the record. Findings against posted copy print as
HISTORY and do not block.

Usage:
    python scripts/check-campaign-facts.py              # the blocking gate
    python scripts/check-campaign-facts.py --online     # + GitHub issue states
    python scripts/check-campaign-facts.py --as-of 2027-01-01   # what expires
    python scripts/check-campaign-facts.py --list       # audit table, exit 0

Exit 0 clean, 1 findings, 2 the acknowledgement ledger could not be trusted.
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acknowledgements import (  # noqa: E402  (must follow the sys.path line)
    AcknowledgementError, load_ledger)

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]

# Every path below is a module constant so the forced-failure tests can redirect
# the whole checker at a temp tree. Same isolation pattern as
# test-platform-claims.py / test-publish-live-board.py.
CAMPAIGNS_DIR = REPO_ROOT / "content" / "campaigns"
VERSION_JSON = REPO_ROOT / "public" / "data" / "version.json"
PUBLISHED_BOARD = REPO_ROOT / "public" / "leaderboard" / "data" / "published-board.json"
BOARD_LIVENESS = REPO_ROOT / "public" / "leaderboard" / "data" / "board-liveness.json"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

FACTS_KEY = "_facts_this_copy_must_not_break"
ACK_CHECK_NAME = "check-campaign-facts"

TIERS = ("checked", "delegated", "online", "human", "durable")

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ISSUE_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#(\d+)$")

# board-liveness.json is rewritten 4x/day by board-liveness.yml. Thirty days
# means that pipeline has been dead for a month, at which point the site's own
# leaderboard surfaces are unsupported too and a red here is the correct answer.
# Deliberately not tighter: a campaign draft must not go red because a bot
# missed a night.
OBSERVATION_MAX_AGE_DAYS = 30

PLATFORM_NAMES = {
    "windows": re.compile(r"\bwindows\b", re.I),
    "macos": re.compile(r"\bmac\s?os\b|\bmacos\b|\bos\s?x\b|\bosx\b|\bmac\b", re.I),
    "linux": re.compile(r"\blinux\b", re.I),
}

# Same vocabulary as check-platform-claims.py's SOFT_QUALIFIER, which is the
# guard for the reader-facing pages. Kept as its own constant rather than
# imported: that script's list also contains the em dash, which is a sentence
# separator here, not a qualifier.
DEFERRAL = re.compile(
    r"coming soon|\bcoming\b|\bsoon\b|this week|within the week|next week|"
    r"in progress|\bplanned\b|not yet|\blater\b|shortly|to follow|any day now",
    re.I)

AVAILABILITY_VERB = re.compile(
    r"\b(download|available|supported|exported to|runs? on|native on|"
    r"get it on|play on|ships? on|grab the)\b", re.I)

# A clause, not a sentence: "Windows today -- macOS and Linux within the week"
# is one sentence making two different claims, and only the second is a
# deferral. Splitting on the dash and the semicolon is what keeps Windows out
# of the finding.
CLAUSE_SPLIT = re.compile(r"[.\n!?;]|—|--")

# Matches a v-prefixed two-part build string, and the bare three-part form. NOT a
# bare two-part number: copy says things like "one turn = one month" and "1.5x",
# and a looser pattern would flag prose for no gain.
VERSION_LITERAL = re.compile(r"\bv\d+\.\d+(?:\.\d+)?\b|\b\d+\.\d+\.\d+\b")


class Finding:
    """One thing that is wrong, or one thing that is true but must be seen.

    `blocking=False` is NOT a severity knob -- it is reserved for two states
    where failing would be dishonest: a claim about copy that has already been
    posted (the remedy would be falsifying a record), and an `online` entry in
    an offline run (it is checked, just not here).
    """

    def __init__(self, key, label, detail, blocking=True, fix=None):
        self.key = key
        self.label = label
        self.detail = detail
        self.blocking = blocking
        self.fix = fix

    def __str__(self):
        return f"{self.key}\n      {self.label}: {self.detail}"


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path} does not exist"
    except OSError as exc:
        return None, f"{path}: cannot read: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"{path}: not valid JSON: {exc}"


def _rel(path):
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def copy_strings(campaign):
    """Every reader-facing string in the copy block, keyed by platform."""
    copy = campaign.get("copy")
    if not isinstance(copy, dict):
        return []
    return [(k, v) for k, v in sorted(copy.items()) if isinstance(v, str)]


def is_posted(campaign):
    posted = campaign.get("posted")
    if not isinstance(posted, dict):
        return False
    return any(bool(v) for v in posted.values())


# ---------------------------------------------------------------------------
# Verifiers. Each takes (campaign, fact, rel) and returns a list of Findings.
# Each is also responsible for PRINTING what it read, because a check that only
# speaks when it is unhappy leaves the copywriter with no way to see today's
# value -- and looking the value up is the thing the old prose block was for.
# ---------------------------------------------------------------------------

def verify_platforms_shipped(campaign, fact, rel, notes):
    key_base = f"{rel}::{fact['id']}"
    data, err = _read_json(VERSION_JSON)
    if err:
        return [Finding(key_base, "SOURCE UNREADABLE", err,
                        fix="This constraint cannot be checked without it. Absence "
                            "is not a clean bill of health.")]
    platforms = (data.get("latest_release") or {}).get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        return [Finding(
            key_base, "SOURCE MISSING THE FIELD",
            f"{_rel(VERSION_JSON)} has no latest_release.platforms. CLAUDE.md: a "
            f"page reading this field must treat absence as 'unrecorded', never as "
            f"'nothing shipped' -- and never as agreement.",
            fix="Re-run scripts/update-version-info.py, or find the second writer.")]

    shipped = sorted(p for p, ok in platforms.items() if ok)
    unshipped = sorted(p for p, ok in platforms.items() if not ok)
    notes.append(f"    platforms  shipped: {', '.join(shipped) or '(none)'} | "
                 f"not shipped: {', '.join(unshipped) or '(none)'}  "
                 f"[{_rel(VERSION_JSON)}]")

    posted = is_posted(campaign)
    over, defer = [], []
    for plat_key, text in copy_strings(campaign):
        for clause in CLAUSE_SPLIT.split(text):
            hits = [p for p, rx in PLATFORM_NAMES.items() if rx.search(clause)]
            if not hits:
                continue
            softened = bool(DEFERRAL.search(clause))
            asserted = len(hits) >= 2 or bool(AVAILABILITY_VERB.search(clause))
            for p in hits:
                if p in unshipped and asserted and not softened:
                    over.append((plat_key, p, clause.strip()[:100]))
                elif p in shipped and softened:
                    defer.append((plat_key, p, clause.strip()[:100]))

    findings = []
    if over:
        findings.append(Finding(
            f"{rel}::copy-promises-an-unshipped-platform",
            "COPY PROMISES A PLATFORM THAT IS NOT DOWNLOADABLE",
            "; ".join(f"copy.{k} claims {p}: \"{c}\"" for k, p, c in over),
            blocking=not posted,
            fix="Say 'coming soon', or drop the platform, or link the download page "
                "and let it resolve."))
    if defer:
        findings.append(Finding(
            f"{rel}::copy-defers-a-shipped-platform",
            "COPY DEFERS A PLATFORM THAT HAS SINCE SHIPPED",
            "; ".join(f"copy.{k} defers {p}: \"{c}\"" for k, p, c in defer),
            blocking=not posted,
            fix="The copy understates what exists, which sends a reader away from a "
                "build they could download today. Post it, update it, or archive the "
                "campaign -- all three are decisions, and any of them closes this."))
    return findings


def verify_board_live(campaign, fact, rel, notes):
    key_base = f"{rel}::{fact['id']}"
    published, err = _read_json(PUBLISHED_BOARD)
    if err:
        return [Finding(key_base, "SOURCE UNREADABLE", err,
                        fix="Without the published key there is no board to check.")]
    seed = published.get("seed")
    epoch = published.get("ladder_epoch")
    if not seed or not epoch:
        return [Finding(
            key_base, "BOARD KEY INCOMPLETE",
            f"{_rel(PUBLISHED_BOARD)} is missing seed and/or ladder_epoch "
            f"(seed={seed!r}, ladder_epoch={epoch!r}).",
            fix="scripts/publish-live-board.py writes this. A half-key cannot "
                "support a claim that any board is live.")]

    liveness, err = _read_json(BOARD_LIVENESS)
    if err:
        return [Finding(key_base, "OBSERVATION UNREADABLE", err,
                        fix="board-liveness.yml writes it. Nothing here can say the "
                            "board is live without an observation of it.")]

    findings = []
    checked_at = liveness.get("checked_at")
    age = None
    try:
        stamp = dt.datetime.fromisoformat(str(checked_at))
        age = (dt.datetime.now(dt.timezone.utc)
               - (stamp if stamp.tzinfo else stamp.replace(
                   tzinfo=dt.timezone.utc))).days
    except (TypeError, ValueError):
        findings.append(Finding(
            key_base, "OBSERVATION UNDATED",
            f"checked_at={checked_at!r} in {_rel(BOARD_LIVENESS)} is not an ISO "
            f"timestamp, so its age cannot be established.",
            fix="An undated observation is not evidence of anything current."))

    board = liveness.get("deployed_board") or {}
    entries = board.get("entries")
    notes.append(f"    board      ({seed}, {epoch})  entries={entries}  "
                 f"verdict={liveness.get('verdict')!r}  observed "
                 f"{checked_at}"
                 + (f" ({age}d ago)" if age is not None else ""))

    if age is not None and age > OBSERVATION_MAX_AGE_DAYS:
        findings.append(Finding(
            key_base, "OBSERVATION TOO OLD TO SUPPORT THE CLAIM",
            f"{_rel(BOARD_LIVENESS)} was last written {age} days ago "
            f"(limit {OBSERVATION_MAX_AGE_DAYS}). board-liveness.yml runs every 6 "
            f"hours, so this means it has not run for a month.",
            fix="Re-run board-liveness.yml. Until it does, nothing here can honestly "
                "say the board is live."))

    if board.get("seed") != seed or board.get("version") != epoch:
        findings.append(Finding(
            key_base, "OBSERVED BOARD IS NOT THE PUBLISHED BOARD",
            f"published ({seed}, {epoch}) vs observed "
            f"({board.get('seed')}, {board.get('version')}). These are two files of "
            f"two different vintages; asserting one key from them is the #293 defect.",
            fix="Run scripts/publish-live-board.py, then board-liveness. If the "
                "ladder forked, the copy needs re-reading, not just the key."))
    elif not isinstance(entries, int) or entries < 1:
        findings.append(Finding(
            key_base, "THE LIVE BOARD HAS NO SCORES ON IT",
            f"({seed}, {epoch}) is observed with entries={entries!r}. The score API "
            f"returns ok:true with an empty board for a key that never existed, so "
            f"an empty board is indistinguishable from a wrong key.",
            fix="Do not point anyone at this board. Confirm the key before writing "
                "copy that names the leaderboard."))
    return findings


def verify_no_version_literal_in_copy(campaign, fact, rel, notes):
    posted = is_posted(campaign)
    hits = []
    for plat_key, text in copy_strings(campaign):
        for m in VERSION_LITERAL.finditer(text):
            hits.append((plat_key, m.group(0)))
    notes.append(f"    versions   {len(hits)} build literal(s) in copy")
    if not hits:
        return []
    return [Finding(
        f"{rel}::version-literal-in-copy",
        "COPY NAMES A BUILD VERSION",
        "; ".join(f"copy.{k}: {v}" for k, v in hits),
        blocking=not posted,
        fix="'The latest build' ages correctly; a version number announces a "
            "superseded build the moment a patch ships.")]


def verify_delegated(campaign, fact, rel, notes):
    key_base = f"{rel}::{fact['id']}"
    target = fact.get("check", "")
    script = REPO_ROOT / target
    if not script.is_file():
        return [Finding(
            key_base, "DELEGATED TO A GUARD THAT DOES NOT EXIST", f"{target} is not "
            f"a file in this repo.",
            fix="Point at the guard that owns this now, or change verify to a tier "
                "that says the truth.")]
    needle = Path(target).name
    callers = sorted(p.name for p in WORKFLOWS_DIR.glob("*.yml")
                     if needle in p.read_text(encoding="utf-8", errors="replace"))
    notes.append(f"    delegated  {target} -> {', '.join(callers) or 'NO WORKFLOW'}")
    if not callers:
        return [Finding(
            key_base, "DELEGATED TO A GUARD NOTHING RUNS",
            f"{target} exists but is referenced by no file in "
            f"{_rel(WORKFLOWS_DIR)}.",
            fix="CLAUDE.md: 'a documented suite is a suite a human runs when they "
                "remember'. Wire it, or stop claiming this constraint is watched.")]
    return []


VERIFIERS = {
    "platforms_shipped": verify_platforms_shipped,
    "board_live": verify_board_live,
    "no_version_literal_in_copy": verify_no_version_literal_in_copy,
}

ONLINE_VERIFIERS = ("issue_state",)


def verify_issue_state(fact, rel, notes):
    """Online only. Never called without --online."""
    import urllib.error
    import urllib.request

    key_base = f"{rel}::{fact['id']}"
    owner, repo, number = ISSUE_RE.match(fact["issue"]).groups()
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "pdoom1-website/check-campaign-facts",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            state = json.loads(resp.read().decode("utf-8")).get("state")
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        # Observation outranks stored state, and a failed observation is not
        # agreement (check-epoch-drift.py's rule). Never blocking: --online only
        # ever runs in the advisory job.
        return [Finding(key_base, "COULD NOT LOOK", f"{url}: {exc}", blocking=False,
                        fix="Unknown, not fine. Re-run, or check by hand.")]
    notes.append(f"    issue      {fact['issue']} is {state} "
                 f"(expected {fact['expect']})")
    if state != fact["expect"]:
        return [Finding(
            key_base, "THE ISSUE THIS CONSTRAINT RESTS ON HAS MOVED",
            f"{fact['issue']} is {state}; the constraint assumes {fact['expect']}.",
            blocking=False,
            fix="Re-read the constraint. If the bug is fixed, the instruction not to "
                "mention the feature is now itself the false claim.")]
    return []


# ---------------------------------------------------------------------------
# Structure. This half is what stops the block rotting back into prose.
# ---------------------------------------------------------------------------

def _iso(value):
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def validate_entry(fact, rel, index, seen_ids):
    """Blocking structural findings only. Every one is fixable in this repo."""
    where = f"{rel}::{FACTS_KEY}[{index}]"
    f = []

    if isinstance(fact, str):
        return [Finding(
            where, "BARE STRING (the old, rotting shape)",
            f"\"{fact[:90]}\"",
            fix="A prose string carries no source, so nothing can ask whether it is "
                "still true -- which is how two of these became lies. Convert it to "
                "an object; see content/campaigns/README.md section 2.1.")]
    if not isinstance(fact, dict):
        return [Finding(where, "NOT AN OBJECT", repr(fact)[:90],
                        fix="See content/campaigns/README.md section 2.1.")]

    fid = fact.get("id")
    if not isinstance(fid, str) or not ID_RE.match(fid or ""):
        f.append(Finding(where, "BAD id", f"{fid!r} is not a lowercase-hyphen slug",
                         fix="The id is the stable name this entry is reported "
                             "under; it must not read differently run to run."))
        fid = f"index-{index}"
    elif fid in seen_ids:
        f.append(Finding(where, "DUPLICATE id", f"{fid!r} appears twice in this file",
                         fix="Two entries reporting under one name means one of them "
                             "is invisible."))
    seen_ids.add(fid)
    where = f"{rel}::{fid}"

    constraint = fact.get("constraint")
    if not isinstance(constraint, str) or not constraint.strip():
        f.append(Finding(where, "MISSING constraint",
                         "every entry needs the rule, in words, for the human "
                         "writing copy",
                         fix="That is this block's primary job. Do not lose it to "
                             "the machinery."))

    tier = fact.get("verify")
    if tier not in TIERS:
        f.append(Finding(
            where, "BAD verify", f"{tier!r} is not one of {', '.join(TIERS)}",
            fix="Declaring the tier is the point: it forces you to say how anyone "
                "would know this is still true."))
        return f

    def need(field, why):
        value = fact.get(field)
        if not isinstance(value, str) or not value.strip():
            f.append(Finding(where, f"MISSING {field}", why))

    if tier in ("checked", "online"):
        need("source", "a checked entry must name what it is checked against")
        known = set(VERIFIERS) if tier == "checked" else set(ONLINE_VERIFIERS)
        if fact.get("check") not in known:
            f.append(Finding(
                where, "UNKNOWN check", f"{fact.get('check')!r} is not one of "
                f"{', '.join(sorted(known))}",
                fix="A verify tier of 'checked' with a verifier that does not exist "
                    "is a claim of coverage with none behind it."))
    if tier == "online" and fact.get("check") == "issue_state":
        if not ISSUE_RE.match(str(fact.get("issue", ""))):
            f.append(Finding(where, "BAD issue",
                             f"{fact.get('issue')!r}, expected owner/repo#number"))
        if fact.get("expect") not in ("open", "closed"):
            f.append(Finding(where, "BAD expect",
                             f"{fact.get('expect')!r}, expected 'open' or 'closed'"))
    if tier == "delegated":
        need("source", "say which guard owns this and where it is wired")
        if not isinstance(fact.get("check"), str) or not fact.get("check"):
            f.append(Finding(where, "MISSING check",
                             "delegated needs the repo-relative path of the guard"))
    if tier == "durable":
        need("why_durable", "say why this rule cannot rot -- the claim is that it "
                            "asserts nothing about the world, and that claim should "
                            "be written down where it can be argued with")
        for forbidden in ("source", "check", "human_verified", "observed"):
            if forbidden in fact:
                f.append(Finding(
                    where, f"durable ENTRY CARRIES {forbidden}",
                    "a rule that asserts nothing about the world has nothing to "
                    "check it against",
                    fix="Either it does make a claim -- then it is not durable -- or "
                        "drop the field. Decoration here makes the real tiers look "
                        "optional."))
    if tier == "human":
        need("why_not_machine", "say why no machine here can check it; 'unverifiable' "
                                "with no reason is indistinguishable from 'nobody "
                                "tried'")
        need("source", "name what a human should read to verify it")
        hv = fact.get("human_verified")
        if not isinstance(hv, dict):
            f.append(Finding(
                where, "MISSING human_verified",
                "a human-verified fact with no record of who, when, and until when "
                "is exactly the shape that rotted",
                fix='Add {"by": ..., "on": "YYYY-MM-DD", "review_by": "YYYY-MM-DD"}.'))
        else:
            if not isinstance(hv.get("by"), str) or not hv.get("by", "").strip():
                f.append(Finding(where, "MISSING human_verified.by",
                                 "an unattributed verification is a rumour"))
            on, review = _iso(hv.get("on")), _iso(hv.get("review_by"))
            if on is None:
                f.append(Finding(where, "BAD human_verified.on",
                                 f"{hv.get('on')!r} is not YYYY-MM-DD"))
            if review is None:
                f.append(Finding(where, "BAD human_verified.review_by",
                                 f"{hv.get('review_by')!r} is not YYYY-MM-DD"))
            if on and review and review <= on:
                f.append(Finding(
                    where, "ZERO-LENGTH VERIFICATION",
                    f"review_by ({review}) must be after on ({on})",
                    fix="A verification that expires the day it is made makes the "
                        "clock meaningless."))
    return f


def check_clock(fact, rel, today, warn_within_days):
    """The human tier's expiry. Returns (findings, expiring_notes)."""
    hv = fact.get("human_verified") or {}
    on, review = _iso(hv.get("on")), _iso(hv.get("review_by"))
    if not (on and review) or review <= on:
        return [], []                      # already reported as a structural fault
    key = f"{rel}::{fact['id']}"
    if today > review:
        return [Finding(
            key, "HUMAN VERIFICATION EXPIRED",
            f"last verified by {hv.get('by')} on {on}; review_by was {review}, "
            f"{(today - review).days} day(s) ago.",
            fix="Re-read the source, then either set a new human_verified.on / "
                "review_by with your name on it, or fix the constraint. What is red "
                "is the VERIFICATION, not the claim -- which is why a person can "
                "always close it.")], []
    left = (review - today).days
    if left <= warn_within_days:
        return [], [f"    {key}  review_by {review} ({left}d left) -- "
                    f"last verified by {hv.get('by')}"]
    return [], []


# ---------------------------------------------------------------------------

def scan(today, online, warn_within_days):
    findings, notes, expiring, unchecked, rows = [], [], [], [], []

    files = sorted(CAMPAIGNS_DIR.glob("*.json"))
    if not files:
        findings.append(Finding(
            _rel(CAMPAIGNS_DIR), "NO CAMPAIGN FILES FOUND",
            "the guard would pass having read nothing",
            fix="If campaigns moved, move this check with them. A guard that scans "
                "an empty set is green and worthless."))
        return findings, notes, expiring, unchecked, rows

    for path in files:
        rel = _rel(path)
        campaign, err = _read_json(path)
        if err:
            findings.append(Finding(rel, "UNREADABLE", err))
            continue
        facts = campaign.get(FACTS_KEY)
        if facts is None:
            findings.append(Finding(
                rel, f"NO {FACTS_KEY} BLOCK",
                "a campaign with no fact-guards is copy with nothing holding it to "
                "the truth",
                fix="See content/campaigns/README.md section 2.1."))
            continue
        if not isinstance(facts, list):
            findings.append(Finding(rel, f"{FACTS_KEY} IS NOT A LIST",
                                    type(facts).__name__))
            continue

        posted = is_posted(campaign)
        notes.append(f"\n  {rel}  ({len(facts)} fact-guards"
                     + (", POSTED -- copy findings print as history)"
                        if posted else ", not yet posted)"))

        seen_ids = set()
        for i, fact in enumerate(facts):
            structural = validate_entry(fact, rel, i, seen_ids)
            findings.extend(structural)
            if structural or not isinstance(fact, dict):
                rows.append((rel, str(fact)[:28] if not isinstance(fact, dict)
                             else str(fact.get("id"))[:28], "STRUCTURE"))
                continue

            tier = fact["verify"]
            rows.append((rel, fact["id"], tier))
            if tier == "checked":
                findings.extend(
                    VERIFIERS[fact["check"]](campaign, fact, rel, notes))
            elif tier == "delegated":
                findings.extend(verify_delegated(campaign, fact, rel, notes))
            elif tier == "online":
                if online:
                    findings.extend(verify_issue_state(fact, rel, notes))
                else:
                    unchecked.append(
                        f"    {rel}::{fact['id']}  {fact['issue']} expected "
                        f"{fact['expect']} -- needs the network. "
                        f"`gh issue view {fact['issue'].split('#')[1]} --repo "
                        f"{fact['issue'].split('#')[0]}`")
            elif tier == "human":
                expired, soon = check_clock(fact, rel, today, warn_within_days)
                findings.extend(expired)
                expiring.extend(soon)

    return findings, notes, expiring, unchecked, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="check mode (the default); exit 1 on any blocking finding")
    ap.add_argument("--online", action="store_true",
                    help="also resolve `online` entries over the network. The "
                         "ADVISORY job runs this; the blocking job does not, so a "
                         "pdoom1 issue closing cannot fail an unrelated PR here.")
    ap.add_argument("--list", action="store_true",
                    help="print every fact-guard and its tier, then exit 0")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="evaluate human_verified expiry at this date instead of "
                         "today -- shows what is about to come due, and lets the "
                         "tests force the expired state rather than wait for it")
    ap.add_argument("--ledger", help="alternative acknowledgement ledger (tests)")
    args = ap.parse_args()

    # Load BEFORE scanning, and never catch this in a way that continues: a
    # ledger that cannot be parsed means the check cannot say what it is
    # tolerating, and a check that cannot say that must not report a verdict.
    try:
        ledger = load_ledger(ACK_CHECK_NAME, args.ledger)
    except AcknowledgementError as exc:
        print(f"REFUSED: the acknowledgement ledger cannot be trusted, so this "
              f"check cannot say what it is tolerating.\n  {exc}", file=sys.stderr)
        return 2

    today = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()
    findings, notes, expiring, unchecked, rows = scan(
        today, args.online, ledger.warn_within_days)

    print("Campaign fact-guards -- the constraint is checked, the value is read")
    print("=" * 74)
    for line in notes:
        print(line)

    if args.list:
        print(f"\n{'file':<46} {'id':<36} tier")
        print("-" * 96)
        for rel, fid, tier in rows:
            print(f"{Path(rel).name:<46} {fid:<36} {tier}")
        print(f"\n{len(rows)} fact-guard(s) across "
              f"{len({r for r, _, _ in rows})} campaign(s)")
        return 0

    report = ledger.assess(fired_keys={f.key for f in findings}, today=today)
    suppressed = report.acknowledged_keys

    waived = [f for f in findings if f.key in suppressed]
    blocking = [f for f in findings if f.blocking and f.key not in suppressed]
    reported = [f for f in findings if not f.blocking and f.key not in suppressed]

    if unchecked:
        print(f"\nNOT CHECKED HERE ({len(unchecked)}) -- `online` tier, needs the "
              f"network. Re-run with --online, which the ADVISORY job does. This is "
              f"not a pass:")
        for line in unchecked:
            print(line)

    if expiring:
        print(f"\nEXPIRING SOON ({len(expiring)}) -- within {ledger.warn_within_days} "
              f"days. Decide now, so a clock never lands as a surprise red on "
              f"someone else's unrelated PR:")
        for line in expiring:
            print(line)

    if waived:
        print(f"\nACKNOWLEDGED FINDINGS ({len(waived)}) -- real, printed, and not "
              f"failed on because somebody decided so on a date:")
        for f in sorted(waived, key=lambda f: f.key):
            print(f"  {f}")

    report.print_to(sys.stdout)

    if reported:
        print(f"\nREPORTED, NOT FAILED ON ({len(reported)}):")
        for f in sorted(reported, key=lambda f: f.key):
            print(f"  {f}")
            if f.fix:
                print(f"      -> {f.fix}")

    if blocking:
        print(f"\nFAIL: {len(blocking)} campaign fact-guard finding(s)\n")
        for f in sorted(blocking, key=lambda f: f.key):
            print(f"  {f}")
            if f.fix:
                print(f"      -> {f.fix}")
        return 1

    if report.blocking:
        print(f"\nFAIL: {len(report.expired)} acknowledgement(s) expired. Every "
              f"finding is either clear or acknowledged -- what is red is the "
              f"ACCEPTANCE, listed above with what to do about it.")
        return 1

    print(f"\nOK: {len(rows)} fact-guard(s) checked, {len(waived)} acknowledged, "
          f"{len(unchecked)} deferred to the online run, "
          f"{len(reported)} reported against posted copy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
