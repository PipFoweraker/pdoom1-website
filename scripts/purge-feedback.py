#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Per-field retention for the feedback store, and erasure on request.

    python scripts/purge-feedback.py --store <dir> --docroot <dir> --check
    python scripts/purge-feedback.py --store <dir> --docroot <dir>
    python scripts/purge-feedback.py --store <dir> --docroot <dir> --receipt F-ABC123
    python scripts/purge-feedback.py --store <dir> --docroot <dir> --rid <uuid>

--docroot (or PDOOM_DOCROOT) is REQUIRED and has no default. See "THE DOCROOT
IS AN INPUT" below: guessing it is how a store inside the docroot got waved
through.

WHY THIS FILE EXISTS
--------------------
docs/decisions/FEEDBACK_INTAKE_CONTRACT.md §10: "A retention policy without a
cron job is prose." §10 states per-field clocks; this is the thing that makes
them true, and `--check` is the thing that notices when they stopped being true.

Retention is PER FIELD, not per record, because the fields have different
purposes and therefore different clocks (contract §10):

    text, page, kind, value, timestamps  indefinite  -- the product
    contact                              90 days from the last reply
    credit                               indefinite  -- publication was consented
    ua                                   180 days
    ip_hash                              30 days     (salt rotates daily anyway)

WHAT "ROW DROPPED AT 30d" MEANS HERE -- an ambiguity in §10, resolved
--------------------------------------------------------------------
§10's ip_hash row says "daily salt rotation, row dropped at 30d". Read literally
against the table's own first row -- text and timestamps are INDEFINITE -- it
cannot mean "delete the record", because that would destroy the visitor's words
and the binding directive ("if I ever lose a message silently, that's now the
worst thing my website can do") forbids exactly that. It is read here as: the
ip_hash FIELD is nulled at 30 days. No record is ever deleted by this script.

TOMBSTONE, NEVER DELETE (§10, erasure path)
-------------------------------------------
`--receipt` / `--rid` null text, contact, credit and ua, and leave rid, receipt,
kind, page, value, flags and timestamps standing, so the public aggregate
counter (scripts/generate-feedback-stats.py) cannot silently disagree with
history. An erased submission is still one submission.

THE DOCROOT IS AN INPUT, NOT A GUESS (INV-1c) -- FIXED 2026-08-17
-----------------------------------------------------------------
This script used to enforce INV-1c with a NAME heuristic alone: refuse any store
whose path contained a component called public/public_html/httpdocs. On
DreamHost shared hosting the docroot is /home/<user>/<domain>, so a store at
/home/pdoom1/pdoom1.com/feedback-store -- inside the docroot, publicly
fetchable, and inside `rsync --delete`'s destination -- carried none of those
names and PASSED. public/ingest.php refused the identical path, because it
compares against DOCUMENT_ROOT. Two guards, one invariant, opposite answers.

So the docroot is now an explicit input (--docroot, or PDOOM_DOCROOT, the same
variable ingest.php reads) and the containment test is the one ingest.php does:
realpath both, then "is the store the docroot or under it". The name heuristic
survives as an ADDITIONAL refusal, never as the only one.

If no docroot is supplied this script REFUSES. It does not fall back to the
heuristic, because a fallback ships exactly when the real check is unavailable
(CLAUDE.md: "Fallback literals are the dangerous ones"), and the thing it would
be protecting is somebody's email address.

The guard is deliberately TWO functions, and the split is a known gap, not a
tidy-up. scripts/generate-feedback-stats.py:484 calls
refuse_bad_store_location() by name and has no --docroot to pass, so:

    refuse_bad_store_location()   repo containment + the name heuristic
    refuse_store_inside_docroot() the ingest.php comparison; REFUSES with no
                                  docroot

main() here calls both. generate-feedback-stats.py calls only the first, so it
still carries the weaker guard.

WHY THAT IS TOLERABLE TODAY, STATED SO NOBODY HAS TO REDISCOVER IT: the tally
job in .github/workflows/feedback-maintenance.yml declares `needs: retention`,
and retention runs this script against the SAME store path. A store inside the
docroot therefore fails the retention job and the tally never runs. The gap is
real on any path that runs the generator ALONE.
**Closing it needs a --docroot flag on generate-feedback-stats.py**, which is
outside this file. Do not close it by giving refuse_bad_store_location() a
default docroot: a default here is the exact fallback the paragraph above
forbids.

THE STORE WRITE LOCK -- WHY IT IS A SEPARATE FILE (A1) -- FIXED 2026-08-17
--------------------------------------------------------------------------
os.replace() is atomic with respect to a CRASH. It is not atomic with respect to
a CONCURRENT WRITER, and ingest.php is one.

ingest.php took flock(LOCK_EX) on the month file, which locks an INODE.
os.replace() swaps that inode out. So: this script reads 2026-08.jsonl, a
visitor POSTs 0.4s later, ingest appends and fsyncs and answers 200 with a
receipt, then os.replace() lands and that record is in an orphaned inode nobody
will ever open. The visitor holds a receipt for a message that no longer exists
and nothing anywhere records the loss -- precisely the binding directive's worst
case.

The fix is a lock on a file whose inode NEVER changes: <store>/.write-lock.
ingest.php takes flock(LOCK_EX) on it around its append; this script holds it
across read -> os.replace() for the WHOLE run. The lockfile is created if
absent, never unlinked (unlinking it is how two processes end up locking two
different inodes and both believing they hold the lock), and never counted as a
record by anything -- it is not *.jsonl.

Contention is not an error. A busy lock means a visitor is mid-POST, and the
right answer is to wait: --lock-timeout (default 30s, PDOOM_PURGE_LOCK_TIMEOUT).
On timeout this script writes NOTHING -- REFUSED (3) in a write mode, UNKNOWN
(2) under --check, because a check that never read the store has certified
nothing.

THE REWRITE IS ATOMIC, AND THAT IS THE POINT
--------------------------------------------
This is the one script in the feedback system that WRITES to the store, so it is
the one place where a crash can lose a visitor's message. It never truncates in
place: it renders the whole file to a sibling temp file, fsyncs it, and calls
os.replace(), which is atomic on both POSIX and Windows. A crash at any instant
therefore leaves either the old file or the new one, never a half of either.
`PDOOM_PURGE_CRASH_AFTER=<n>` forces a hard kill after n records have been
written to the temp file -- a test-only seam in the shape contract §11.1 already
accepted for PDOOM_MAIL_SINK, inert when unset, and the only way to OBSERVE the
property rather than assert it. scripts/test-purge-feedback.py uses it.

The guarantee is PER FILE, and saying so is the honest boundary: a crash while
purging a twelve-month store can leave January through June rewritten and July
onward not. No file is ever half-written, no record is ever lost, and the next
run finishes the job -- the operation is idempotent, so re-running is always the
correct response to an interrupted one.

THE ip_hash CLOCK IS NOT ONLY A FIELD (A3) -- FIXED 2026-08-17
--------------------------------------------------------------
§10 nulls ip_hash at 30 days and says the daily salt makes the row "unlinkable
after 24h". Both sentences were false in the same way: this script assessed
record FIELDS only, while ingest.php writes two ip-derived things it never
deleted.

  <store>/.salt/<YYYY-MM-DD>     every day's salt, kept forever
  <store>/.throttle/<hash>.json  a FILENAME derived from ip_hash, kept forever

Keeping every historical salt makes any ip_hash still inside its 30-day window
reversible: the IPv4 space is 2^32, so an attacker with the salt enumerates it
in minutes. "Rotation makes it unlinkable" is only true if the OLD SALT IS
DESTROYED. And a throttle bucket named after an ip_hash outlives the field it
was derived from, so nulling the field deleted the copy nobody was looking at.

So the purge now sweeps both, and --check counts them and goes RED on them:

  .salt/*         kept 2 days   (SALT_KEEP_DAYS; nothing reads a salt older
                                 than today, so 2 is already generous)
  .throttle/*     kept 30 days  (IP_HASH_DAYS -- the same clock as the field,
                                 because it is the same personal datum)

Neither directory is ever read as records: RECORD_GLOB is *.jsonl and a salt has
no extension while a throttle bucket is *.json. scripts/test-purge-feedback.py
asserts that rather than trusting it.

Lines this script cannot parse are PRESERVED BYTE-FOR-BYTE and counted. An
unparseable line is a candidate lost message; a purge is not a licence to tidy.
Records that need no change are re-emitted as their ORIGINAL line text, never
re-serialised, so a run that purges three fields cannot perturb 900 other rows.

EXIT CODES
    0  clean (--check), or the purge applied
    1  --check found a field retained past its clock, a salt or throttle bucket
       retained past its clock, or a demonstrably stale ip_hash salt (§10's
       other half)  <- the gate
    2  UNKNOWN: no store configured/present, unparseable lines, a sidecar
       that makes a clock uncomputable, or a --check that could not take the
       store write lock. Never reported as 0: a check that cannot see the store
       has not certified it.
    3  REFUSED: ambiguous or unmatched receipt, no docroot supplied, a store
       path that resolves somewhere it must never be (contract INV-1c), or a
       write mode that could not take the store write lock.
"""

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import fcntl as _fcntl
except ImportError:                                   # not POSIX
    _fcntl = None
try:
    import msvcrt as _msvcrt
except ImportError:                                   # not Windows
    _msvcrt = None

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]

EXIT_OK = 0
EXIT_RETAINED = 1
EXIT_UNKNOWN = 2
EXIT_REFUSED = 3

DAY = 86400

# Contract §10, verbatim. These are the clocks, in days from their reference.
CONTACT_DAYS = 90
UA_DAYS = 180
IP_HASH_DAYS = 30

# Contract §10 erasure path: "row rewritten with text/contact/credit/ua nulled".
# ip_hash is deliberately NOT in this tuple -- it carries its own 30-day clock,
# it is unlinkable within 24h of the daily salt rotation, and it is what the
# endpoint throttles abuse with. Adding it here would make erasure diverge from
# the contract text on a field the contract already retires by another route.
ERASURE_FIELDS = ("text", "contact", "credit", "ua")

# The same glob read-feedback.store_files() uses. Both mean "record files": the
# endpoint's canary (.probe), salts, throttle buckets and notification log are
# deliberately outside it. scripts/test-purge-feedback.py asserts the two agree,
# because a divergence here would purge a file the reader never counts, or miss
# one it does.
RECORD_GLOB = "*.jsonl"

# The human triage sidecar. Deliberately NOT named *.jsonl: read-feedback.py
# globs *.jsonl for VISITOR RECORDS, so a sidecar with that extension would be
# read as feedback and inflate every published count. Format, one object per
# line:
#   {"rid": "...", "tags": ["abusive"], "confirmed_by": "Pip",
#    "confirmed_on": "2026-08-16", "source": "human", "last_reply_ts": 1755230000}
# This script reads ONLY last_reply_ts from it (the contact clock's reference).
# generate-feedback-stats.py reads the tags, under much stricter rules.
TRIAGE_NAME = "triage.log"

# Path components that mean "this is served to the public". Contract INV-1c: the
# store may never live where rsync --delete can reach it, and the payload carries
# reporter PII, so a store under the docroot is publicly fetchable. Either reason
# alone is sufficient to refuse.
#
# THIS IS THE SECOND LINE OF DEFENCE, NOT THE FIRST. It was the only one until
# 2026-08-17, and it missed the production layout: DreamHost's docroot is
# /home/<user>/<domain>, which carries none of these names. The first line is
# now containment against an EXPLICIT --docroot, the same comparison
# public/ingest.php:693 makes against DOCUMENT_ROOT.
DOCROOT_PARTS = {"public", "public_html", "httpdocs"}

# The one file every writer to this store locks (A1). Its inode must never
# change, which is why it is a dedicated file and not one of the record files:
# os.replace() below swaps a record file's inode out from under any flock held
# on it, so ingest.php's per-file lock and this script's rewrite were locking
# two different objects and could not see each other.
#
# Deliberately NOT *.jsonl: RECORD_GLOB means "visitor records" to every reader
# in this system, and a lockfile counted as a record is a message nobody sent.
LOCK_NAME = ".write-lock"

# Seconds to wait for the write lock. A busy lock means a visitor is mid-POST,
# and waiting is the correct answer -- ingest.php holds it for one append.
DEFAULT_LOCK_TIMEOUT = 30.0

# The endpoint's throttle bucket directory. The FILENAME is derived from
# ip_hash, so the file is personal data with or without the field inside it.
THROTTLE_DIR = ".throttle"

# Salts are kept for two days, measured from the START of the UTC day the salt
# is named for. ingest.php only ever reads gmdate('Y-m-d'), i.e. TODAY's salt,
# so anything older is dead weight that keeps a 30-day-old ip_hash reversible
# over a 2^32 address space. Two rather than one so that a clock skew, a late
# cron or a run straddling UTC midnight can never delete a live salt: losing
# today's salt would not lose a message, but it would re-hash every visitor and
# reset the throttle, and cheap safety here costs one extra day of exposure.
SALT_KEEP_DAYS = 2

# Throttle buckets carry the SAME clock as the ip_hash field they are named
# after, because they are the same personal datum in a different place. A
# different number here would mean the record said one thing and the filesystem
# another.
THROTTLE_KEEP_DAYS = IP_HASH_DAYS

ISO_Z = "%Y-%m-%dT%H:%M:%SZ"


# The endpoint's daily salt directory (read-feedback.py's docstring names it as
# one of the non-record paths in the store). Nothing else in this system checks
# that the rotation actually happens, and the privacy page is about to promise a
# visitor that it does -- "We never store your IP address, only a hash that is
# re-salted daily". A salt that quietly stopped rotating leaves ip_hash linkable
# across months while every other check here stays green.
SALT_DIR = ".salt"

# 48 hours, not 24: a daily rotation observed at an arbitrary moment is
# legitimately up to a day old, so 24 would fire on healthy stores and get
# ignored. Past 48 at least one rotation has been missed.
SALT_STALE_HOURS = 48


class Refused(Exception):
    """The run must stop and say why. Never caught to continue."""


class LockBusy(Exception):
    """Somebody else holds the store write lock and the wait ran out.

    Separate from Refused because the CORRECT exit code differs by mode: a write
    mode that could not take the lock has refused to act (3), while a --check
    that could not take it has certified nothing (2). Collapsing the two would
    report a transient visitor POST as a configuration error, or a
    configuration error as a transient.
    """


def _try_lock(fd):
    """One NON-BLOCKING attempt at an exclusive lock on fd. True on success.

    Both branches are the same primitive the other writer uses:
      POSIX   fcntl.flock == flock(2), which is what PHP's flock() calls on
              Linux, so ingest.php and this script contend on the same object.
              Production is Linux; this is the branch that matters.
      Windows msvcrt.locking == LockFile, which is what PHP's flock() calls on
              Windows. Present so the forced-failure test can observe real
              contention on the dev box rather than a simulation of it.

    Polled rather than blocking so that ONE code path carries the timeout on
    both platforms -- msvcrt has no bounded blocking mode (LK_LOCK retries for a
    fixed ten seconds and then raises), so a blocking call would silently mean
    something different on each OS.
    """
    if _fcntl is not None:
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            return True
        except OSError:
            return False
    if _msvcrt is not None:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    raise Refused(
        "this Python has neither fcntl nor msvcrt, so the store write lock "
        "cannot be taken. Refusing: an unlocked rewrite can silently swallow a "
        "submission ingest.php has already answered 200 for.")


def _unlock(fd):
    if _fcntl is not None:
        try:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        except OSError:
            pass
        return
    if _msvcrt is not None:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


def lock_path_for(store):
    """<store>/.write-lock -- or beside it when --store names a single file.

    record_files() accepts a lone .jsonl path, and `<file>/.write-lock` is not a
    path; the sibling is. It is still the same object every writer in that
    directory takes, which is the only property that matters.
    """
    store = Path(store)
    return (store.parent if store.is_file() else store) / LOCK_NAME


@contextlib.contextmanager
def store_write_lock(store, timeout):
    """Hold <store>/.write-lock exclusively, or raise LockBusy having waited.

    Created if absent, NEVER unlinked. An unlinked lockfile is how two processes
    come to hold locks on two different inodes while both believe they are
    serialised -- the same class of defect this lock exists to fix.
    """
    path = lock_path_for(store)
    try:
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise Refused(
            "cannot open the store write lock %s (%s). Refusing rather than "
            "rewriting the store unlocked: an unlocked rewrite can drop a "
            "record ingest.php has already answered 200 for." % (path, exc))
    try:
        # msvcrt.locking() locks a byte range from the current offset. A region
        # past end-of-file is lockable on Windows, but a one-byte file makes the
        # behaviour identical on both platforms and costs nothing. Two racing
        # processes both writing this byte is harmless: nothing reads it.
        if _fcntl is None and _msvcrt is not None:
            try:
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"L")
            except OSError:
                pass
        deadline = time.monotonic() + max(0.0, float(timeout))
        held = False
        while True:
            if _try_lock(fd):
                held = True
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        if not held:
            raise LockBusy(
                "another process has held %s for more than %.1fs. Nothing was "
                "read and nothing was written. That is almost always ingest.php "
                "appending a submission; re-run, or raise --lock-timeout."
                % (path, float(timeout)))
        try:
            yield path
        finally:
            _unlock(fd)
    finally:
        os.close(fd)


def now_from(value):
    """Epoch seconds. Injected everywhere so a test can FORCE a clock state.

    Accepts an epoch integer or an ISO-8601 UTC stamp. `today` read from the
    system clock inside the logic would make every state below reachable only by
    waiting; scripts/acknowledgements.py takes the same injection for the same
    reason.
    """
    if value is None:
        return int(dt.datetime.now(dt.timezone.utc).timestamp())
    text = str(value).strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    try:
        stamp = dt.datetime.strptime(text, ISO_Z).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        try:
            stamp = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            raise Refused("--now %r is neither an epoch nor an ISO-8601 UTC "
                          "stamp (2026-08-16T00:00:00Z)" % value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return int(stamp.timestamp())


def iso(epoch):
    return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).strftime(ISO_Z)


def resolve_store(explicit):
    """--store, else PDOOM_FEEDBACK_STORE. Returns None when neither is set.

    There is deliberately no derived default. Contract §3 resolves the endpoint's
    store as dirname(docroot)/feedback-store, but this script runs from a git
    checkout on an operator's box, where dirname(docroot) is the repository root
    -- and a store there would put reporter PII inside a git repo. A wrong
    default is worse than no default when the failure mode is committing
    somebody's email address.
    """
    value = explicit or os.environ.get("PDOOM_FEEDBACK_STORE")
    if not value or not str(value).strip():
        return None
    return Path(str(value).strip()).expanduser()


def resolve_docroot(explicit):
    """--docroot, else PDOOM_DOCROOT. Returns None when neither is set.

    PDOOM_DOCROOT is not a name invented here: public/ingest.php:235 reads the
    same variable as its own fallback for DOCUMENT_ROOT. One name, so an
    operator cannot configure the endpoint and the purge to disagree about where
    the web root is -- which is the disagreement this whole guard exists to
    stop.
    """
    value = explicit or os.environ.get("PDOOM_DOCROOT")
    if not value or not str(value).strip():
        return None
    return str(value).strip()


def norm_path(path):
    """The Python half of ingest.php's norm_path(): realpath, non-strict.

    os.path.realpath resolves symlinks as far as the path exists and leaves the
    rest lexically normalised, which is exactly what ingest.php's
    deepest-existing-ancestor loop does. Containment has to work BEFORE the store
    directory exists, or the very first run is the one that skips the check.
    """
    return os.path.realpath(str(path))


def path_inside(child, parent):
    """True when child IS parent or lives under it. ingest.php:212, in Python.

    The trailing separator matters and is the reason this is not a startswith:
    without it a docroot /home/u/pdoom1.com would swallow the sibling store
    /home/u/pdoom1.com-feedback, and refusing a safe path teaches an operator to
    reach for a bypass.
    """
    if not child or not parent:
        return False
    c = norm_path(child).rstrip("/\\")
    p = norm_path(parent).rstrip("/\\")
    if os.name == "nt":
        c, p = c.lower(), p.lower()
    if c == p:
        return True
    return c.startswith(p + os.sep) or c.startswith(p + "/")


def refuse_bad_store_location(store):
    """The two refusals that need NO docroot. INV-1c, first pass.

      1. inside this git checkout -- the store carries reporter PII, a path in
         the repo gets committed, and anything under public/ is rsynced
      2. a docroot-shaped NAME    -- public / public_html / httpdocs

    THIS IS NOT SUFFICIENT ON ITS OWN and was the entire guard until 2026-08-17.
    refuse_store_inside_docroot() below is the half that catches the real
    DreamHost layout; main() calls both.

    KEPT AS A SEPARATE ENTRY POINT ON PURPOSE. scripts/generate-feedback-stats.py
    calls this function by name and has no --docroot to pass, so folding the
    containment test into this signature would break that script's import with a
    TypeError rather than a stated refusal. See the hand-off note in the module
    docstring: that script currently gets only this weaker half.
    """
    resolved = Path(norm_path(store))
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError:
        pass
    else:
        raise Refused(
            "store %s is inside this git checkout (%s). The store carries "
            "reporter PII; a path in the repo gets committed, and anything under "
            "public/ is rsynced to production (contract INV-1c). Point "
            "--store / PDOOM_FEEDBACK_STORE somewhere outside the repository."
            % (resolved, REPO_ROOT))

    hits = [p for p in resolved.parts if p.lower() in DOCROOT_PARTS]
    if hits:
        raise Refused(
            "store %s has the path component %r, which names a web docroot on "
            "every host this project uses. Contract INV-1c: the store may never "
            "live where rsync --delete can reach it, and PII under a docroot is "
            "publicly fetchable." % (resolved, hits[0]))


def refuse_store_inside_docroot(store, docroot):
    """INV-1c, the half that needs a docroot -- and refuses without one.

    This is the comparison public/ingest.php:693 makes against DOCUMENT_ROOT,
    and it is the one that catches /home/<user>/<domain>/feedback-store.
    """
    if docroot is None:
        raise Refused(
            "no docroot was supplied, so INV-1c cannot be enforced. Pass "
            "--docroot <path> or set PDOOM_DOCROOT to the SAME directory "
            "public/ingest.php sees as DOCUMENT_ROOT.\n"
            "  There is deliberately no fallback. The name heuristic that used "
            "to stand alone here (%s) does not match DreamHost's docroot, which "
            "is /home/<user>/<domain> -- so a store at "
            "/home/<user>/<domain>/feedback-store passed this guard while "
            "ingest.php refused the identical path. A guard that runs when the "
            "real check is unavailable is a guard that ships exactly when it is "
            "wrong." % ", ".join(sorted(DOCROOT_PARTS)))

    resolved = Path(norm_path(store))
    if path_inside(resolved, docroot):
        raise Refused(
            "store %s is inside the docroot %s. Contract INV-1c: the store may "
            "never live where rsync --delete can reach it (it runs ~4x/day from "
            "public/), and reporter PII under a docroot is publicly fetchable. "
            "Either reason alone is sufficient. public/ingest.php:693 refuses "
            "this same path with a 507; this is the other half of that guard."
            % (resolved, Path(norm_path(docroot))))


def record_files(store):
    """Record files, oldest name first. Same meaning as read-feedback's glob."""
    store = Path(store)
    if store.is_file():
        return [store]
    return sorted(p for p in store.rglob(RECORD_GLOB) if p.is_file())


def split_lines(text):
    """Split on "\\n" ONLY, keeping the terminator, so a line round-trips.

    Not str.splitlines(): that also splits on \\x0b, \\x1c-\\x1e, \\u2028 and
    \\u2029, and PHP's json_encode with JSON_UNESCAPED_UNICODE emits U+2028 and
    U+2029 raw. splitlines() would tear one record into two, and this script
    would then write both halves back as separate lines -- a corruption invented
    by the tool that exists to protect the data.
    """
    out = []
    start = 0
    while True:
        cut = text.find("\n", start)
        if cut == -1:
            if start < len(text):
                out.append(text[start:])
            return out
        out.append(text[start:cut + 1])
        start = cut + 1


class Entry:
    """One physical line of a store file, and its parse (or the lack of one)."""

    def __init__(self, path, lineno, raw):
        self.path = path
        self.lineno = lineno
        self.raw = raw
        self.blank = not raw.strip()
        self.record = None
        self.unparseable = False
        if self.blank:
            return
        try:
            parsed = json.loads(raw)
        except ValueError:
            self.unparseable = True
            return
        if not isinstance(parsed, dict):
            self.unparseable = True
            return
        self.record = parsed


def read_store(store):
    """[(path, [Entry, ...]), ...]. Raw text is retained for verbatim re-emit."""
    out = []
    for path in record_files(store):
        # surrogateescape, not replace: a store file with an invalid byte must
        # round-trip through this script unchanged. errors="replace" would
        # silently rewrite somebody's message with U+FFFD.
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        entries = [Entry(path, i, raw)
                   for i, raw in enumerate(split_lines(text), start=1)]
        out.append((path, entries))
    return out


def load_reply_times(store):
    """{rid: latest reply epoch} from the triage sidecar, plus a damage count.

    Validation here is deliberately MINIMAL -- rid present, last_reply_ts
    numeric. The strict validation of tags, provenance and attribution belongs to
    generate-feedback-stats.py, which publishes them. If this script refused on a
    malformed tag it would stop purging, and a purge that will not run
    OVER-RETAINS personal data: a triage typo would become a privacy incident.
    What it will not do is guess: an unreadable line could have carried a reply
    timestamp, so it is counted, and the contact clock reports UNKNOWN rather
    than purging on an age it cannot compute.
    """
    path = Path(store) / TRIAGE_NAME
    replies = {}
    damaged = 0
    if not path.exists():
        return replies, damaged
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    for raw in split_lines(text):
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
        rid = entry.get("rid")
        stamp = entry.get("last_reply_ts")
        if not isinstance(rid, str) or not rid.strip():
            continue
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
            continue
        if stamp > replies.get(rid, float("-inf")):
            replies[rid] = int(stamp)
    return replies, damaged


def salt_state(store, now):
    """('absent'|'fresh'|'stale', message). Absence is UNVERIFIED, never fine.

    CLAUDE.md: "Absence of a marker is never a clean bill of health." A missing
    .salt/ can mean the endpoint has not shipped, or that it names its salts
    somewhere else -- either way this script has NOT confirmed the rotation, and
    it says so on every run rather than staying quiet and reading as approval. It
    only sets the exit code when it can see a salt and that salt is stale, which
    is the one state it can actually prove.
    """
    path = Path(store) / SALT_DIR
    if not path.is_dir():
        return ("absent",
                "salt rotation UNVERIFIED: no %s/ in the store. This script has "
                "not confirmed the daily re-salting the privacy page promises; "
                "it has only failed to find where it happens." % SALT_DIR)
    stamps = [p.stat().st_mtime for p in path.iterdir() if p.is_file()]
    if not stamps:
        return ("stale", "salt rotation STALE: %s/ exists but is empty" % SALT_DIR)
    hours = (now - max(stamps)) / 3600.0
    if hours < -1:
        # --now was pushed into the past. Say so rather than printing a negative
        # age, which reads as a bug in the store rather than in the invocation.
        # The tolerance is an hour, not zero: `now` is truncated to whole seconds
        # and a salt written milliseconds earlier lands a hair in the future,
        # which is not a clock override and must not be reported as one.
        return ("fresh", "salt rotation: newest salt is newer than the injected "
                         "--now clock, so its age was not evaluated")
    if hours > SALT_STALE_HOURS:
        return ("stale",
                "salt rotation STALE: newest salt in %s/ is %.0f hours old "
                "(limit %d). ip_hash stays linkable across every day that shares "
                "a salt, so the 30-day clock is not the only thing that matters."
                % (SALT_DIR, hours, SALT_STALE_HOURS))
    return ("fresh", "salt rotation OK: newest salt is %.0f hours old" % hours)


class Expired:
    """One ip-derived FILE past its clock. The other half of the ip_hash row."""

    def __init__(self, path, kind, age_days, limit_days):
        self.path = path
        self.kind = kind
        self.age_days = age_days
        self.limit_days = limit_days

    def __str__(self):
        return ("%s/%s retained %d day(s), clock is %d"
                % (self.path.parent.name, self.path.name,
                   int(self.age_days), self.limit_days))


def salt_age_days(path, now):
    """Age of one salt file, from its NAME first and its mtime only as a fallback.

    ingest.php names a salt for the UTC day it belongs to, so the name is the
    authoritative statement of what the file is for; mtime is not, because a
    backup restore, an rsync or a `touch` rewrites it and would silently
    resurrect a salt that ought to be gone. Age runs from the START of the named
    day, which is the literal reading of "older than N days".

    The mtime fallback is what catches ingest.php's lost-rename leftovers --
    `<day>.<hex>.tmp`, written by daily_salt() when two processes race. Those
    contain salt material and no date this can parse, and nothing else in the
    system would ever remove them.
    """
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", path.name)
    if match:
        try:
            day = dt.datetime(int(match.group(1)), int(match.group(2)),
                              int(match.group(3)), tzinfo=dt.timezone.utc)
            return (now - day.timestamp()) / DAY
        except ValueError:
            pass
    try:
        return (now - path.stat().st_mtime) / DAY
    except OSError:
        return None


def expired_sidecars(store, now):
    """[Expired, ...] -- the salts and throttle buckets past their clock.

    Pure: it decides, never unlinks. --check calls this and reports; the purge
    calls it and then removes exactly what it named.
    """
    out = []
    for dirname, limit, ager in (
            (SALT_DIR, SALT_KEEP_DAYS, salt_age_days),
            (THROTTLE_DIR, THROTTLE_KEEP_DAYS,
             lambda p, n: ((n - p.stat().st_mtime) / DAY))):
        path = Path(store) / dirname
        if not path.is_dir():
            continue
        for entry in sorted(path.iterdir()):
            if not entry.is_file():
                continue
            try:
                age = ager(entry, now)
            except OSError:
                age = None
            if age is None or age <= limit:
                continue
            out.append(Expired(entry, dirname, age, limit))
    return out


def sweep_sidecars(expired):
    """Unlink what expired_sidecars() named. Returns (counts, failures).

    An unlink that fails is REPORTED, never swallowed: the file is still there,
    the privacy promise is still false, and a run that said nothing about it
    would be the silent version of the same defect.
    """
    counts = {}
    failures = []
    for item in expired:
        try:
            item.path.unlink()
        except OSError as exc:
            failures.append("%s: %s" % (item.path, exc))
            continue
        counts[item.kind] = counts.get(item.kind, 0) + 1
    return counts, failures


def is_present(value):
    """True when a field still holds something worth retaining.

    None, absent and "" are all "already gone". "" is what a visitor who typed
    nothing into an optional field leaves behind; treating it as retained would
    rewrite thousands of records to replace "" with null and change nothing about
    what is stored.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


class Overrun:
    def __init__(self, path, lineno, rid, field, age_days, limit_days):
        self.path = path
        self.lineno = lineno
        self.rid = rid
        self.field = field
        self.age_days = age_days
        self.limit_days = limit_days

    def __str__(self):
        return ("%s:%d rid=%s field=%s retained %d day(s), clock is %d"
                % (self.path.name, self.lineno, self.rid or "<none>",
                   self.field, self.age_days, self.limit_days))


def assess(entry, now, replies):
    """(overruns, unknown_reason) for one record. Pure: it decides, never writes.

    An age is only computable from server_ts. A record without one is UNKNOWN,
    never assumed old and never assumed young: purging on a guessed age destroys
    data, and retaining on a guessed age breaks the promise on the privacy page.
    """
    rec = entry.record
    server_ts = rec.get("server_ts")
    if isinstance(server_ts, bool) or not isinstance(server_ts, (int, float)):
        if any(is_present(rec.get(f)) for f in ("contact", "ua", "ip_hash")):
            return [], ("rid=%s has no numeric server_ts, so no clock on it can "
                        "be computed" % rec.get("rid"))
        return [], None

    rid = rec.get("rid") if isinstance(rec.get("rid"), str) else None
    reference_reply = replies.get(rid, server_ts) if rid else server_ts
    contact_ref = max(server_ts, reference_reply)

    out = []
    for field, ref, limit in (("contact", contact_ref, CONTACT_DAYS),
                              ("ua", server_ts, UA_DAYS),
                              ("ip_hash", server_ts, IP_HASH_DAYS)):
        if not is_present(rec.get(field)):
            continue
        age = (now - ref) / DAY
        if age > limit:
            out.append(Overrun(entry.path, entry.lineno, rid, field,
                               int(age), limit))
    return out, None


def serialise(rec):
    """Match the endpoint's json_encode flags (contract §3 append discipline)."""
    return json.dumps(rec, ensure_ascii=False, separators=(",", ":"))


def rewrite_atomic(path, lines):
    """Render the whole file beside the original, fsync, then os.replace().

    Never `open(path, "w")`: truncate-then-write has a window in which the store
    is empty on disk, and a crash inside that window loses every message in the
    file. os.replace() is atomic on POSIX and on Windows.
    """
    crash_after = os.environ.get("PDOOM_PURGE_CRASH_AFTER")
    crash_after = int(crash_after) if crash_after not in (None, "") else None

    tmp = path.with_name(path.name + ".purge-tmp")
    with open(tmp, "w", encoding="utf-8", errors="surrogateescape",
              newline="") as fh:
        for i, line in enumerate(lines):
            if crash_after is not None and i >= crash_after:
                fh.flush()
                os.fsync(fh.fileno())
                # Hard kill: no flush of the remainder, no os.replace, no
                # cleanup. This is what a power cut looks like, and it is the
                # only way to OBSERVE that the original survives it.
                os._exit(70)
            fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    if crash_after is not None:
        # A file with fewer records than the crash point still must not ship a
        # half-purge as a success.
        os._exit(70)
    os.replace(tmp, path)


def apply_to_file(path, entries, mutate, now):
    """mutate(record) -> dict of field->reason, or {}. Returns counts.

    Records the mutation left alone are re-emitted as their ORIGINAL line text.
    Re-serialising an untouched record would rewrite key order and escaping
    across the whole store on every run, turning a three-field purge into a
    file-wide diff nobody can review.
    """
    lines = []
    changed = 0
    per_field = {}
    for entry in entries:
        if entry.record is None:
            lines.append(entry.raw)
            continue
        fields = mutate(entry)
        if not fields:
            lines.append(entry.raw)
            continue
        changed += 1
        for name in fields:
            per_field[name] = per_field.get(name, 0) + 1
        terminator = "\n" if entry.raw.endswith("\n") else ""
        lines.append(serialise(entry.record) + terminator)
    if changed:
        rewrite_atomic(path, lines)
    return changed, per_field


def purge_mutator(now, replies, contact_known):
    def mutate(entry):
        rec = entry.record
        overruns, _unknown = assess(entry, now, replies)
        touched = {}
        for over in overruns:
            if over.field == "contact" and not contact_known:
                # The sidecar is damaged, so "90 days from the last reply" is not
                # a number we have. Skipped and reported, never guessed.
                continue
            rec[over.field] = None
            touched[over.field] = True
        if touched:
            stamp = iso(now)
            purged = rec.get("purged")
            if not isinstance(purged, dict):
                purged = {}
            for name in touched:
                purged[name] = stamp
            rec["purged"] = purged
        return touched
    return mutate


def erase_mutator(now, targets, via):
    def mutate(entry):
        rec = entry.record
        if id(entry) not in targets:
            return {}
        touched = {}
        for field in ERASURE_FIELDS:
            if is_present(rec.get(field)):
                rec[field] = None
                touched[field] = True
        erased = {"on": iso(now), "via": via,
                  "fields": sorted(ERASURE_FIELDS)}
        # The tombstone is written even when every field was already empty: the
        # fact that a person asked is itself the record, and a second run must
        # not read as "no such request".
        rec["erased"] = erased
        touched["erased"] = True
        return touched
    return mutate


def select_for_erasure(files, receipt, rid):
    """Which lines an erasure request names -- or a refusal saying why not.

    A receipt is 30 bits of a UUID and contract §1 says it "may collide; never
    key on it". At ten thousand records the chance that some pair of receipts
    collides is a couple of percent, not a rounding error. If a receipt resolves
    to more than one DISTINCT rid, erasing them all would erase a stranger's
    words on the strength of a display string -- silent loss of exactly the kind
    the binding directive forbids -- so this refuses and asks for --rid.

    Several lines sharing ONE rid is the opposite case: contract INV-1e makes
    duplicate writes normal, they are one submission, and all of them are erased.
    """
    matches = []
    for _path, entries in files:
        for entry in entries:
            if entry.record is None:
                continue
            if receipt is not None and entry.record.get("receipt") == receipt:
                matches.append(entry)
            elif rid is not None and entry.record.get("rid") == rid:
                matches.append(entry)

    if not matches:
        raise Refused(
            "no record matches %s. Nothing was written. An erasure request that "
            "silently succeeds against zero rows tells a person their data is "
            "gone when it is not."
            % ("receipt %s" % receipt if receipt else "rid %s" % rid))

    if receipt is not None:
        rids = sorted({m.record.get("rid") for m in matches})
        if len(rids) > 1:
            detail = "\n".join(
                "    rid=%s  server_ts=%s  page=%s"
                % (m.record.get("rid"), m.record.get("server_ts"),
                   m.record.get("page"))
                for m in matches)
            raise Refused(
                "receipt %s matches %d records across %d distinct rids. The "
                "receipt is 30 bits of a UUID and contract §1 warns it may "
                "collide, so erasing all of them would erase somebody else's "
                "message. Nothing was written. Re-run with --rid <uuid>:\n%s"
                % (receipt, len(matches), len(rids), detail))
    return matches


def report(counts, as_json, out=sys.stdout):
    if as_json:
        print(json.dumps(counts, ensure_ascii=False, sort_keys=True, indent=2),
              file=out)
        return
    for key in sorted(counts):
        value = counts[key]
        if isinstance(value, dict):
            inner = ", ".join("%s=%d" % (k, value[k]) for k in sorted(value)) or "none"
            print("  %-22s %s" % (key, inner), file=out)
        else:
            print("  %-22s %s" % (key, value), file=out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", help="feedback store root (or PDOOM_FEEDBACK_STORE)")
    ap.add_argument("--docroot",
                    help="the web docroot, i.e. what public/ingest.php sees as "
                         "DOCUMENT_ROOT (or PDOOM_DOCROOT). REQUIRED: the store "
                         "must not be inside it (INV-1c), and this script will "
                         "not guess where it is")
    ap.add_argument("--lock-timeout", type=float, default=None,
                    help="seconds to wait for <store>/%s before giving up "
                         "(default %.0f, or PDOOM_PURGE_LOCK_TIMEOUT)"
                         % (LOCK_NAME, DEFAULT_LOCK_TIMEOUT))
    ap.add_argument("--check", action="store_true",
                    help="report fields retained past their clock and exit 1; "
                         "writes nothing")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what a purge would do, write nothing, exit 0")
    ap.add_argument("--receipt", help="erase the submission holding this receipt")
    ap.add_argument("--rid", help="erase by rid; the unambiguous form")
    ap.add_argument("--now", help="epoch or ISO-8601 UTC; forces the clock so "
                                  "every state is testable without waiting")
    ap.add_argument("--json", action="store_true", help="machine-readable counts")
    args = ap.parse_args(argv)

    try:
        if args.receipt and args.rid:
            raise Refused("--receipt and --rid name the same thing two ways; "
                          "pass one.")
        if (args.receipt or args.rid) and args.check:
            raise Refused("--check is a gate over the whole store; it cannot "
                          "also perform an erasure.")
        if (args.receipt or args.rid) and args.dry_run:
            # Erasure is evaluated before the dry-run branch, so accepting this
            # combination would perform a real erasure for somebody who asked for
            # a rehearsal. Refusing beats quietly meaning the opposite.
            raise Refused("--dry-run does not apply to an erasure request. Use "
                          "--check to inspect the store, or run the erasure for "
                          "real; it is idempotent and writes a tombstone, never "
                          "a deletion.")

        now = now_from(args.now)
        store = resolve_store(args.store)
        if store is None:
            print("UNKNOWN: no store configured. Pass --store or set "
                  "PDOOM_FEEDBACK_STORE.\n  Reporting this as success would be a "
                  "vacuous green: a retention check that never saw the store has "
                  "certified nothing.", file=sys.stderr)
            return EXIT_UNKNOWN

        refuse_bad_store_location(store)
        refuse_store_inside_docroot(store, resolve_docroot(args.docroot))

        if not store.exists():
            print("UNKNOWN: store %s does not exist. Nothing certified."
                  % store, file=sys.stderr)
            return EXIT_UNKNOWN

        timeout = args.lock_timeout
        if timeout is None:
            env_timeout = os.environ.get("PDOOM_PURGE_LOCK_TIMEOUT", "")
            try:
                timeout = float(env_timeout) if env_timeout.strip() else None
            except ValueError:
                raise Refused("PDOOM_PURGE_LOCK_TIMEOUT=%r is not a number"
                              % env_timeout)
        if timeout is None:
            timeout = DEFAULT_LOCK_TIMEOUT

        # EVERYTHING that reads or writes the store happens inside this lock,
        # read included. A lock taken only around os.replace() would still lose
        # any record ingest.php appended between the read and the swap -- which
        # is the exact defect (A1), not a smaller version of it.
        try:
            with store_write_lock(store, timeout):
                return run_locked(args, store, now)
        except LockBusy as exc:
            if args.check or args.dry_run:
                print("UNKNOWN: %s\n  A check that never read the store has "
                      "certified nothing, so this is not a green." % exc,
                      file=sys.stderr)
                return EXIT_UNKNOWN
            print("REFUSED: %s" % exc, file=sys.stderr)
            return EXIT_REFUSED

    except Refused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return EXIT_REFUSED


def run_locked(args, store, now):
    """The body of a run, with <store>/.write-lock held. Split out only so the
    lock's scope is visible in one place rather than inferred from indentation.
    """
    try:
        files = read_store(store)

        # Test-only seam, inert when unset -- the same shape and the same
        # justification as PDOOM_PURGE_CRASH_AFTER above. The window this widens
        # is the one between the read and the os.replace(), which is exactly
        # where a concurrent append used to be swallowed. Without it the race is
        # sub-millisecond and a test could only assert about it; with it,
        # scripts/test-purge-feedback.py T17 makes a real appender contend with
        # a real purge and OBSERVES which of them wins.
        stall = os.environ.get("PDOOM_PURGE_STALL_MS", "")
        if stall.strip():
            time.sleep(int(stall) / 1000.0)

        replies, sidecar_damage = load_reply_times(store)
        contact_known = sidecar_damage == 0

        unparseable = [e for _p, entries in files for e in entries if e.unparseable]
        records = [e for _p, entries in files for e in entries
                   if e.record is not None]

        if args.receipt or args.rid:
            targets = select_for_erasure(files, args.receipt, args.rid)
            wanted = {id(t) for t in targets}
            mutate = erase_mutator(now, wanted, "receipt" if args.receipt else "rid")
            total_changed = 0
            for path, entries in files:
                changed, _fields = apply_to_file(path, entries, mutate, now)
                total_changed += changed
            print("ERASED: %d line(s) tombstoned for %s"
                  % (total_changed, args.receipt or args.rid))
            report({"lines_tombstoned": total_changed,
                    "fields_nulled": list(ERASURE_FIELDS),
                    "records_in_store": len(records)}, args.json)
            print("  rid, receipt, kind, page, value, flags and timestamps are "
                  "kept: an erased submission is still one submission, and the "
                  "public counter must not disagree with history.")
            return EXIT_OK

        overruns = []
        unknowns = []
        for _path, entries in files:
            for entry in entries:
                if entry.record is None:
                    continue
                found, unknown = assess(entry, now, replies)
                overruns.extend(found)
                if unknown:
                    unknowns.append(unknown)

        by_field = {}
        for over in overruns:
            by_field[over.field] = by_field.get(over.field, 0) + 1

        # A3: the ip_hash clock is not only a field. These are counted in every
        # mode, so a green --check carries the number rather than silence.
        expired = expired_sidecars(store, now)
        by_sidecar = {}
        for item in expired:
            by_sidecar[item.kind] = by_sidecar.get(item.kind, 0) + 1

        counts = {
            "records": len(records),
            "files": len(files),
            "unparseable_lines": len(unparseable),
            "sidecar_unreadable_lines": sidecar_damage,
            "over_clock": by_field,
            "ip_derived_files_over_clock": by_sidecar,
            "as_of": iso(now),
        }

        # Computed BEFORE any sweep below, so the message describes the state
        # this run found rather than the state it left behind.
        salt_status, salt_message = salt_state(store, now)
        counts["salt_rotation"] = salt_status

        if args.check:
            print("purge-feedback --check on %s" % store)
            report(counts, args.json)
            print("  %s" % salt_message)
            for over in sorted(overruns, key=lambda o: (o.field, o.lineno))[:50]:
                print("  RETAINED %s" % over)
            for item in expired[:50]:
                print("  RETAINED %s" % item)
            for line in unknowns[:20]:
                print("  UNKNOWN  %s" % line)
            if salt_status == "stale":
                print("\nFAIL: %s" % salt_message)
                return EXIT_RETAINED
            if overruns:
                print("\nFAIL: %d field(s) retained past the clock in contract "
                      "§10. Run without --check to purge." % len(overruns))
                return EXIT_RETAINED
            if expired:
                print("\nFAIL: %d ip-derived file(s) retained past their clock. "
                      "A salt kept past its day makes every ip_hash still inside "
                      "the 30-day window reversible over a 2^32 address space, "
                      "and a throttle bucket is NAMED after an ip_hash -- so "
                      "nulling the field deleted the copy nobody was looking at. "
                      "Run without --check to sweep them." % len(expired))
                return EXIT_RETAINED
            if unparseable or unknowns or sidecar_damage:
                print("\nUNKNOWN: %d unparseable line(s), %d record(s) with no "
                      "usable clock, %d unreadable sidecar line(s). No field is "
                      "known to be over-retained, and nothing here is certified "
                      "either -- an unreadable line could be anything."
                      % (len(unparseable), len(unknowns), sidecar_damage))
                return EXIT_UNKNOWN
            print("\nOK: every field in %d record(s) is inside its clock."
                  % len(records))
            return EXIT_OK

        if args.dry_run:
            print("purge-feedback --dry-run on %s (nothing written)" % store)
            report(counts, args.json)
            return EXIT_OK

        mutate = purge_mutator(now, replies, contact_known)
        total_changed = 0
        purged = {}
        for path, entries in files:
            changed, fields = apply_to_file(path, entries, mutate, now)
            total_changed += changed
            for name, n in fields.items():
                purged[name] = purged.get(name, 0) + n

        swept, sweep_failures = sweep_sidecars(expired)

        counts["records_rewritten"] = total_changed
        counts["purged"] = purged
        counts["swept"] = swept
        print("purge-feedback on %s" % store)
        report(counts, args.json)
        print("  %s" % salt_message)
        if sweep_failures:
            print("\nUNKNOWN: %d ip-derived file(s) could not be unlinked. They "
                  "are still on disk, so the ip_hash clock is still not true for "
                  "them:" % len(sweep_failures))
            for line in sweep_failures[:20]:
                print("    %s" % line)
            return EXIT_UNKNOWN
        if not contact_known:
            print("\nUNKNOWN: the triage sidecar has %d unreadable line(s), so "
                  "'90 days from the last reply' is not computable. contact was "
                  "left alone; ua and ip_hash were purged normally. Fix %s and "
                  "re-run." % (sidecar_damage, Path(store) / TRIAGE_NAME))
            return EXIT_UNKNOWN
        if unparseable:
            print("\nUNKNOWN: %d line(s) could not be parsed. They were preserved "
                  "byte-for-byte and NOT purged -- an unparseable line is a "
                  "candidate lost message, not litter." % len(unparseable))
            return EXIT_UNKNOWN
        return EXIT_OK

    except Refused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
