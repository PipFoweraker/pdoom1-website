#!/usr/bin/env python
"""An acknowledgement is a STATE WITH A CLOCK, not a permanent exemption.

THE PROBLEM THIS SOLVES ("class 5, the knowing allowlist")
----------------------------------------------------------
A check SEES a divergence, PRINTS it, and exits 0 by design. It is not disarmed,
not mis-aimed, not stale. The check is not fooled; the READER is, by its exit
code. pdoom-data's check_invariants.py has printed three known divergences and
exited 0 for about eight months. This repo has the same shape in at least four
places -- check-encoding-safety.py's KNOWN_UNFIXED, check-platform-claims.py's
ALLOWLIST, check-stale-facts.py's SKIP_FILES and LINE_ALLOWLIST.

Each of those entries carries a REASON, which is better than most repos manage.
None of them carries a CLOCK. So the reason can stop being true and nothing
notices. Live example, and the reason this module exists: all three
KNOWN_UNFIXED entries said "held by the <X> branch (2026-07-29 sweep)". As of
2026-08-09 no such branch exists on the remote. The finding is still real; the
justification for tolerating it evaporated eleven days ago, silently, and the
check went on printing WAIVED and exiting 0.

THE RULE
--------
The thing that expires is the ACCEPTANCE, never the finding.

  * Before review_by : the check is GREEN, and every acknowledged item is
                       printed AND counted in the summary line. Green carries a
                       number, never silence.
  * After review_by  : the check is RED -- on "this acceptance expired,
                       re-accept or fix", NOT on the underlying finding.

That distinction is the whole design. A red on the underlying finding is
un-closeable by the person who hits it, so it becomes permanent, and CLAUDE.md's
testing discipline is right that permanent red is worse than no check. A red on
an EXPIRED ACCEPTANCE is always closeable by a human decision -- fix it, or
write down that you still accept it and until when. Either outcome is a fact
somebody chose on a date, which is exactly what was missing.

Two more states, both reported, neither blocking:

  * STALE      an acknowledgement whose key no longer fires. Dead weight, and a
               loaded gun if the key ever returns -- it would be pre-forgiven.
               NOT blocking: deleting a dead exemption is housekeeping, not an
               honesty risk today, and its own review_by will force the question
               on a date anyway. Adding a second blocking mode here would be a
               new knob, and ad-hoc knobs are what this module replaces.
  * EXPIRING   inside policy.warn_within_days of review_by. A cliff with no
               warning gets answered by a panic bulk re-accept, which is the
               same as having no clock at all.

WHAT IS REFUSED (never silently ignored)
----------------------------------------
Loading raises AcknowledgementError -- which the calling check must let fail --
on any of:
  * a missing or unparseable ledger file;
  * an entry missing any REQUIRED_FIELDS key, or with one blank;
  * accepted_on / review_by not a strict ISO date, or review_by <= accepted_on;
  * a `check` name not declared in the ledger's `checks` map. A typo'd check
    name would otherwise exempt nothing while reading as an exemption -- a
    silent no-op is the failure mode this whole module is about.

An entry that cannot be validated is NOT treated as absent, because "absent"
means "not acknowledged" means the check fails on the finding instead -- which
looks like a real finding and sends someone hunting the wrong bug.

NO LITERALS IN SCRIPTS
----------------------
Everything that can move -- the acknowledgements, the warning window, the set of
known check names -- lives in data/acknowledgements.json, each with a `source`.
CLAUDE.md: "pinned values go in a data file with a `source` note, never a script
literal." The ledger deliberately sits at the repo root, NOT under public/: it
is CI metadata, and public/ is rsynced to production.

`today` is injected everywhere rather than read from the clock inside the
logic, so every state below can be forced by a test rather than waited for.

USAGE (see check-encoding-safety.py for the reference wiring)
-------------------------------------------------------------
    from acknowledgements import load_ledger

    ledger = load_ledger("check-encoding-safety")     # raises if malformed
    report = ledger.assess(fired_keys={f.path for f in findings})
    report.print_to(sys.stdout)
    unwaived = [f for f in findings if f.path not in report.acknowledged_keys]
    return 1 if (unwaived or report.blocking) else 0

CLI:
    python scripts/acknowledgements.py --audit          # every entry, every check
    python scripts/acknowledgements.py --audit --check check-encoding-safety
    python scripts/acknowledgements.py --as-of 2027-01-01   # what expires when
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]

# Not deployed: public/ is what rsync ships. This is CI metadata.
LEDGER_PATH = REPO_ROOT / "data" / "acknowledgements.json"

# Every one of these must be present and non-blank on every entry. They are the
# questions that make an acceptance auditable: what, why, who, when, until when,
# what happens then, and on whose authority.
REQUIRED_FIELDS = (
    "check",        # which check this suppresses -- must be in the ledger's `checks`
    "key",          # the stable key the check reports; how the entry is matched
    "what",         # the finding, in the check's own words
    "why",          # why it is tolerated (the part that can stop being true)
    "accepted_by",  # a person, or an honest statement that nobody is recorded
    "accepted_on",  # ISO date
    "review_by",    # ISO date; the acceptance dies here, not the finding
    "on_expiry",    # what the next human should DO -- makes the red actionable
    "source",       # issue, PR, comment or ruling this rests on
)


class AcknowledgementError(Exception):
    """The ledger cannot be trusted. Callers must NOT catch this."""


def _iso_date(value, where, field):
    if not isinstance(value, str):
        raise AcknowledgementError(f"{where}: {field} must be an ISO date string")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise AcknowledgementError(
            f"{where}: {field}={value!r} is not a strict ISO date (YYYY-MM-DD): {exc}"
        ) from None


class Acknowledgement:
    def __init__(self, raw, index):
        where = f"acknowledgements[{index}]"
        if not isinstance(raw, dict):
            raise AcknowledgementError(f"{where}: entry must be an object")

        for field in REQUIRED_FIELDS:
            if field not in raw:
                raise AcknowledgementError(
                    f"{where}: missing required field {field!r}. An acknowledgement "
                    f"without every one of {', '.join(REQUIRED_FIELDS)} is an "
                    f"anonymous permanent exemption, which is the thing this file exists "
                    f"to abolish.")
            value = raw[field]
            if not isinstance(value, str) or not value.strip():
                raise AcknowledgementError(
                    f"{where}: field {field!r} must be a non-blank string, got {value!r}")

        self.raw = raw
        self.check = raw["check"]
        self.key = raw["key"]
        self.what = raw["what"]
        self.why = raw["why"]
        self.accepted_by = raw["accepted_by"]
        self.on_expiry = raw["on_expiry"]
        self.source = raw["source"]
        self.accepted_on = _iso_date(raw["accepted_on"], where, "accepted_on")
        self.review_by = _iso_date(raw["review_by"], where, "review_by")

        if self.review_by <= self.accepted_on:
            raise AcknowledgementError(
                f"{where}: review_by ({self.review_by}) must be after accepted_on "
                f"({self.accepted_on}). A zero-length acceptance is either a typo or "
                f"a way to make the clock meaningless.")

    def days_left(self, today):
        return (self.review_by - today).days

    def is_expired(self, today):
        return today > self.review_by

    def __repr__(self):
        return f"<Acknowledgement {self.check}:{self.key} review_by={self.review_by}>"


def _brief(text, limit=150):
    """One-line summaries only. The full text is one --audit away.

    A wall of prose in a CI log is read as noise and skipped, which would
    reproduce the exact failure this module exists to fix -- a true statement
    nobody reads. The EXPIRED block below is deliberately NOT briefed: that one
    has to be read.
    """
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit - 3] + "..."


class Report:
    """What one check should print and what it should return."""

    def __init__(self, check, today, acknowledged, expired, expiring, stale,
                 warn_within_days):
        self.check = check
        self.today = today
        self.acknowledged = acknowledged   # live (unexpired) AND currently firing
        self.expired = expired             # past review_by; these BLOCK
        self.expiring = expiring           # live, firing, inside the warn window
        self.stale = stale                 # live but the key no longer fires
        self.warn_within_days = warn_within_days

    @property
    def acknowledged_keys(self):
        """Keys a caller may suppress. Expired acceptances are NOT in here.

        An expired acceptance still suppresses the underlying finding -- the red
        must be about the expiry, not about the finding, or the person who hits
        it cannot close it. Callers that want the old behaviour get it: this set
        is `acknowledged + expired` deliberately.
        """
        return {a.key for a in self.acknowledged + self.expired}

    @property
    def blocking(self):
        return bool(self.expired)

    def summary_line(self):
        total = len(self.acknowledged) + len(self.expired) + len(self.stale)
        bits = [f"{total} on file",
                f"{len(self.acknowledged)} live and firing"]
        if self.expired:
            bits.append(f"{len(self.expired)} EXPIRED")
        if self.expiring:
            bits.append(f"{len(self.expiring)} expiring within {self.warn_within_days}d")
        if self.stale:
            bits.append(f"{len(self.stale)} stale (no longer fires)")
        return f"Acknowledgements for {self.check}: " + ", ".join(bits)

    def print_to(self, out):
        # Green must carry a number, never silence. Even the all-clear prints.
        if not (self.acknowledged or self.expired or self.stale):
            print(f"Acknowledgements for {self.check}: none on file.", file=out)
            return

        if self.expired:
            print(f"\nEXPIRED ACCEPTANCE ({len(self.expired)}) -- this is why the "
                  f"check is red. The FINDING is not new; the decision to tolerate "
                  f"it ran out.", file=out)
            print("-" * 72, file=out)
            for a in self.expired:
                overdue = (self.today - a.review_by).days
                print(f"  {a.key}", file=out)
                print(f"      what        {a.what}", file=out)
                print(f"      why         {a.why}", file=out)
                print(f"      accepted    {a.accepted_by} on {a.accepted_on}", file=out)
                print(f"      review_by   {a.review_by}  ({overdue} day(s) overdue)",
                      file=out)
                print(f"      DO THIS     {a.on_expiry}", file=out)
                print(f"      source      {a.source}", file=out)
            print(f"\n  To clear: fix the finding and delete the entry from "
                  f"{LEDGER_PATH.relative_to(REPO_ROOT).as_posix()}, OR set a new "
                  f"review_by with a why that is true today and your name in "
                  f"accepted_by. Both are decisions; neither is a shrug.", file=out)

        if self.acknowledged:
            print(f"\nACKNOWLEDGED ({len(self.acknowledged)}) -- printed, counted, "
                  f"and not failed on. Full reasons: "
                  f"python scripts/acknowledgements.py --audit", file=out)
            for a in self.acknowledged:
                print(f"  [{a.days_left(self.today):>4}d left, review_by "
                      f"{a.review_by}] {a.key}", file=out)
                print(f"      {_brief(a.why)}", file=out)

        if self.expiring:
            print(f"\nEXPIRING SOON ({len(self.expiring)}) -- within "
                  f"{self.warn_within_days} days. Decide now, so the clock never "
                  f"lands as a surprise red on someone else's unrelated PR:", file=out)
            for a in self.expiring:
                print(f"  {a.key}  review_by {a.review_by} "
                      f"({a.days_left(self.today)}d) -- ask "
                      f"{_brief(a.accepted_by, 60)}", file=out)

        if self.stale:
            print(f"\nSTALE ({len(self.stale)}) -- acknowledged, but the check no "
                  f"longer reports this key. Not blocking; it hides nothing today. "
                  f"It is dead weight, and if the key ever returns it would be "
                  f"pre-forgiven by a decision nobody is making any more. Delete it, "
                  f"or say in `why` that you are holding it deliberately:", file=out)
            for a in self.stale:
                print(f"  [review_by {a.review_by}] {a.key}", file=out)
                print(f"      {_brief(a.why)}", file=out)

        print("\n" + self.summary_line(), file=out)


class Ledger:
    def __init__(self, check, entries, warn_within_days, path):
        self.check = check
        self.entries = entries
        self.warn_within_days = warn_within_days
        self.path = path

    def assess(self, fired_keys, today=None):
        """Partition this check's acknowledgements against what actually fired."""
        today = today or dt.date.today()
        fired = set(fired_keys)
        acknowledged, expired, expiring, stale = [], [], [], []
        for a in sorted(self.entries, key=lambda e: (e.review_by, e.key)):
            if a.is_expired(today):
                expired.append(a)
            elif a.key not in fired:
                stale.append(a)
            else:
                acknowledged.append(a)
                if a.days_left(today) <= self.warn_within_days:
                    expiring.append(a)
        return Report(self.check, today, acknowledged, expired, expiring, stale,
                      self.warn_within_days)


def _read(path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise AcknowledgementError(
            f"{path} does not exist. A check that imports this module has "
            f"acknowledgements by definition; a missing ledger is not 'no "
            f"exemptions', it is an unreadable one.") from None
    except OSError as exc:
        raise AcknowledgementError(f"{path}: cannot read: {exc}") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AcknowledgementError(f"{path}: not valid JSON: {exc}") from None


def _parse(doc, path):
    """Validate the whole document once. Returns (all_entries, checks, policy)."""
    if not isinstance(doc, dict):
        raise AcknowledgementError(f"{path}: top level must be an object")

    checks = doc.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise AcknowledgementError(
            f"{path}: `checks` must be a non-empty object mapping every check name "
            f"to a description. Without it a typo in an entry's `check` field "
            f"exempts nothing while reading as an exemption.")

    policy = doc.get("policy")
    if not isinstance(policy, dict):
        raise AcknowledgementError(f"{path}: `policy` must be an object")
    warn = policy.get("warn_within_days")
    if not isinstance(warn, int) or isinstance(warn, bool) or warn < 0:
        raise AcknowledgementError(
            f"{path}: policy.warn_within_days must be a non-negative integer, "
            f"got {warn!r}")
    if not isinstance(policy.get("source"), str) or not policy["source"].strip():
        raise AcknowledgementError(
            f"{path}: policy.source must say where warn_within_days came from. "
            f"CLAUDE.md: pinned values go in a data file WITH a source note.")

    raw_entries = doc.get("acknowledgements")
    if not isinstance(raw_entries, list):
        raise AcknowledgementError(f"{path}: `acknowledgements` must be a list")

    entries = []
    seen = set()
    for i, raw in enumerate(raw_entries):
        ack = Acknowledgement(raw, i)
        if ack.check not in checks:
            raise AcknowledgementError(
                f"acknowledgements[{i}]: check={ack.check!r} is not declared in "
                f"`checks` ({', '.join(sorted(checks))}). A misspelled check name "
                f"silently suppresses nothing.")
        pair = (ack.check, ack.key)
        if pair in seen:
            raise AcknowledgementError(
                f"acknowledgements[{i}]: duplicate entry for {ack.check}:{ack.key}. "
                f"Two acceptances of one finding means two review_by dates, and the "
                f"reader cannot tell which one is in force.")
        seen.add(pair)
        entries.append(ack)
    return entries, checks, policy


def load_ledger(check, path=None):
    """Entries for ONE check. Raises AcknowledgementError -- do not catch it."""
    path = Path(path) if path else LEDGER_PATH
    entries, checks, policy = _parse(_read(path), path)
    if check not in checks:
        raise AcknowledgementError(
            f"{path}: check {check!r} is not declared in `checks`. Declare it (with "
            f"a description) before asking for its acknowledgements, so that a "
            f"renamed check fails loudly instead of quietly losing its exemptions.")
    return Ledger(check, [e for e in entries if e.check == check],
                  policy["warn_within_days"], path)


def load_all(path=None):
    """Every entry, for the audit CLI. Same validation, no filtering."""
    path = Path(path) if path else LEDGER_PATH
    entries, checks, policy = _parse(_read(path), path)
    return entries, checks, policy, path


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", action="store_true",
                    help="list every acknowledgement with its clock state")
    ap.add_argument("--check", help="restrict --audit to one check name")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="evaluate the clock at this date instead of today, to see "
                         "what is about to expire")
    ap.add_argument("--ledger", help="path to an alternative ledger (tests)")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()

    try:
        entries, checks, policy, path = load_all(args.ledger)
    except AcknowledgementError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    print(f"Ledger: {path}")
    print(f"As of:  {today}"
          + ("  (--as-of override)" if args.as_of else ""))
    print(f"Policy: warn within {policy['warn_within_days']} days "
          f"-- {policy['source']}")
    print()

    shown = [e for e in entries if not args.check or e.check == args.check]
    if args.check and args.check not in checks:
        print(f"REFUSED: unknown check {args.check!r}", file=sys.stderr)
        return 2
    if not shown:
        print("No acknowledgements on file.")
        return 0

    expired_total = 0
    for name in sorted({e.check for e in shown}):
        print(f"{name}  -- {checks[name]}")
        for a in sorted((e for e in shown if e.check == name),
                        key=lambda e: e.review_by):
            left = a.days_left(today)
            if left < 0:
                state = f"EXPIRED {-left}d ago"
                expired_total += 1
            elif left <= policy["warn_within_days"]:
                state = f"expiring in {left}d"
            else:
                state = f"{left}d left"
            print(f"  [{state:>18}] {a.key}")
            print(f"      {a.why}")
            print(f"      {a.accepted_by}, {a.accepted_on} -> {a.review_by} "
                  f"| {a.source}")
        print()

    print(f"{len(shown)} acknowledgement(s); {expired_total} expired as of {today}.")
    # --audit is a report, not a gate: the gate belongs to each check, which is
    # the only thing that knows whether the key still fires. Always 0 unless the
    # ledger itself is unreadable.
    return 0


if __name__ == "__main__":
    sys.exit(main())
