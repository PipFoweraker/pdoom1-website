#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mail authentication guard for pdoom1.com -- M1..M5 of the feedback intake contract.

WHY THIS EXISTS
---------------
The binding directive (Pip, 2026-08-15) is: "If I ever lose a message silently,
that's now the worst thing my website can do." Mail is how an intake message
reaches a human. Two ways it is lost silently:

  1. Nothing authenticates our mail, so a receiving MTA is free to bin it. No
     bounce reaches the visitor, no error reaches us. Measured 2026-08-15
     against ns1.dreamhost.com (authoritative): pdoom1.com publishes NO SPF, NO
     DKIM (google._domainkey is NXDOMAIN) and NO DMARC.

  2. Somebody FIXES (1) by publishing a strict DMARC policy, and the fix is what
     kills the path. public/bug-submit.php calls mail() with no 5th parameter,
     so the envelope sender is a DreamHost system address, so SPF alignment
     fails, so a p=quarantine or p=reject policy tells every receiver to discard
     the intake mail -- while the DNS looks, to anyone auditing it, correct.

M5 exists for (2), and it is the reason this script exists rather than a
checklist. It refuses to let the DMARC policy rise above p=none while any PHP
mailer in the repo would fail alignment.

WHAT EACH CHECK ASSERTS
-----------------------
Preconditions (NOT in the contract; they exist so a green run cannot be vacuous):

  P1  The observation of DNS in data/mail-auth.json is complete and not older
      than max_observation_age_days. A stale mirror is a claim about a world
      that has moved on.
  P2  The mailer scan actually found the mailers the spec says exist. Without
      this, deleting or renaming bug-submit.php would make M5 pass by having
      nothing to check -- the exact shape of check-platform-claims.py's
      early return, which returned 0 before opening a single page.

Contract section 5:

  M1  An SPF record exists at the apex, and there is exactly ONE. Two v=spf1
      records is a permerror, which fails harder than none at all.
  M2  That SPF record covers every sender in the spec -- either by carrying the
      sender's `include:` mechanism, or by an ip4: prefix that genuinely
      contains the sender's address (computed with `ipaddress`, not string
      matching).
  M3  A DMARC record exists at _dmarc.<domain>, is unique, and carries a p= tag
      with a value DMARC defines.
  M4  The DKIM selector resolves and looks like a key.
  M5  The DMARC policy -- both the one this repo INTENDS to publish and the one
      actually published -- is no stronger than the alignment ceiling.

THE THREE STATES, KEPT APART
----------------------------
Every check reports one of: PASS, WRONG (a record is there and says the wrong
thing), ABSENT (measured, and nothing is there), UNMEASURED (nobody has looked),
UNEVALUABLE (a prior check makes this one unanswerable). CLAUDE.md: "Absence of
a marker is never a clean bill of health. Everything predating a marker is
unmarked too, so a missing flag must render as *unknown*, never as *fine*."
Only PASS is green. UNMEASURED and UNEVALUABLE are findings like any other.

THE ALIGNMENT CEILING (M5), derived rather than asserted
--------------------------------------------------------
Mail leaving the DreamHost box cannot be DKIM-signed by Google -- Google never
sees it -- so its ONLY route to a DMARC pass is SPF alignment, which needs two
things at once:

  a) the envelope sender (`-f address@pdoom1.com`, mail()'s 5th parameter) is on
     the same domain as the From: header; and
  b) SPF for that domain authorises the DreamHost IP, i.e. M2 passes for every
     sender with runs_php: true.

Fail either and the ceiling is p=none. Both must hold before the ceiling rises,
which is why M5 is coupled to M2 and not merely to the PHP source.

Unresolvable is treated as unaligned. If the 5th parameter is a variable, a
function call, or anything this parser cannot evaluate to a literal, the mailer
counts as FAILING alignment. Fail closed: the cost of a false "aligned" is the
silent loss the directive forbids; the cost of a false "unaligned" is a policy
that stays at p=none one PR longer.

OFFLINE BY DEFAULT, ON PURPOSE
------------------------------
The blocking run reads the recorded observation and touches no network. A gate
that resolves DNS on every PR goes red when a runner's resolver hiccups, and
CLAUDE.md: "a red test in the suite is worse than no test -- it teaches everyone
to skip the suite." `--live` re-resolves and reports drift; it is advisory.

ACKNOWLEDGEMENTS
----------------
M1-M4 are red today because the records genuinely do not exist, and only Pip can
publish them from the DreamHost panel and Google Admin. That is not a defect a
seat can close, so it would become the permanent red CLAUDE.md forbids. It is
carried in data/acknowledgements.json instead: printed and counted on every run,
green until review_by, red on "this acceptance expired" after it. See
docs/decisions/ACKNOWLEDGEMENT_CLOCK.md. Do NOT add an allowlist to this file.

Note that the acknowledgement keys encode the STATE, not just the check --
`pdoom1.com/M1/absent`, not `pdoom1.com/M1`. An acceptance of "SPF is absent"
must not silently forgive "SPF is present and wrong": when the state changes the
acknowledgement goes STALE, which is visible, instead of pre-forgiving a
different finding.

USAGE
-----
    python scripts/check-mail-auth.py                  # check, offline, exit 1 on finding
    python scripts/check-mail-auth.py --check          # identical; CI idiom
    python scripts/check-mail-auth.py --json           # machine-readable results
    python scripts/check-mail-auth.py --live           # re-resolve and report drift
    python scripts/check-mail-auth.py --live --update  # ...and rewrite the observation
    python scripts/check-mail-auth.py --as-of 2026-09-01   # force the clock forward
    python scripts/check-mail-auth.py --spec F --ledger G --repo-root D   # fixtures

EXIT CODES
    0  every check PASS, or every finding acknowledged and unexpired
    1  an unacknowledged finding, or an acknowledgement expired
    2  REFUSED -- the spec or the ledger cannot be trusted, so this check cannot
       say what it is asserting or what it is tolerating
    3  --live only: DNS resolution failed. Never silently downgraded to green.
"""

import argparse
import datetime as dt
import ipaddress
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acknowledgements import (  # noqa: E402  (must follow the sys.path line)
    AcknowledgementError, load_ledger)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "data" / "mail-auth.json"
ACK_CHECK_NAME = "check-mail-auth"

# Directories never scanned for PHP. `.claude/worktrees` holds full checkouts of
# this repo made by concurrent agents; scanning them reports the same mailer
# three or four times over and makes P2's counts meaningless.
SKIP_DIRS = {".git", ".claude", "node_modules", "vendor", ".venv", "venv"}

STATE_PASS = "PASS"
STATE_WRONG = "WRONG"          # a record is there and says the wrong thing
STATE_ABSENT = "ABSENT"        # measured; nothing is there
STATE_UNMEASURED = "UNMEASURED"    # nobody has looked
STATE_UNEVALUABLE = "UNEVALUABLE"  # a prior check makes this unanswerable

POLICY_RANK = {"none": 0, "quarantine": 1, "reject": 2}


class SpecError(Exception):
    """The spec cannot be trusted. Callers must NOT catch this."""


# --------------------------------------------------------------------------
# Spec loading. Validated hard: a spec that is half-written must refuse, not
# silently check less. "Absent" would read as "nothing to guard".
# --------------------------------------------------------------------------

def load_spec(path=None):
    path = Path(path) if path else SPEC_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SpecError(
            f"{path} does not exist. Without it this check has no idea which "
            f"senders must be covered or what was last measured, and a check "
            f"that knows nothing must say so rather than pass.") from None
    except OSError as exc:
        raise SpecError(f"{path}: cannot read: {exc}") from None
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SpecError(f"{path}: not valid JSON: {exc}") from None

    if not isinstance(spec, dict):
        raise SpecError(f"{path}: top level must be an object")

    domain = spec.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        raise SpecError(f"{path}: `domain` must be a non-blank string")

    age = spec.get("max_observation_age_days")
    if not isinstance(age, int) or isinstance(age, bool) or age <= 0:
        raise SpecError(
            f"{path}: max_observation_age_days must be a positive integer, got "
            f"{age!r}. Without it the observation below never goes stale, and a "
            f"mirror that cannot rot is a mirror nobody re-measures.")

    senders = spec.get("senders")
    if not isinstance(senders, list) or not senders:
        raise SpecError(
            f"{path}: `senders` must be a non-empty list. M2 asks whether SPF "
            f"covers every sender; an empty list makes that question vacuous.")
    for i, s in enumerate(senders):
        if not isinstance(s, dict):
            raise SpecError(f"{path}: senders[{i}] must be an object")
        for field in ("id", "what", "spf_mechanism", "source"):
            if not isinstance(s.get(field), str) or not s[field].strip():
                raise SpecError(
                    f"{path}: senders[{i}].{field} must be a non-blank string")
        if "ip" not in s:
            raise SpecError(
                f"{path}: senders[{i}] must carry `ip` -- an address string, or "
                f"null to say explicitly that this sender has no single address "
                f"we can test an ip4: prefix against. Omitting the key makes "
                f"'no address' and 'nobody wrote one down' the same thing.")
        if s["ip"] is not None:
            try:
                ipaddress.ip_address(s["ip"])
            except ValueError as exc:
                raise SpecError(f"{path}: senders[{i}].ip: {exc}") from None
        if not isinstance(s.get("runs_php"), bool):
            raise SpecError(
                f"{path}: senders[{i}].runs_php must be a boolean. It decides "
                f"which senders M5's alignment ceiling depends on.")

    intended = spec.get("intended")
    if not isinstance(intended, dict):
        raise SpecError(f"{path}: `intended` must be an object")
    for field in ("spf", "dmarc", "dkim_selector", "source"):
        if not isinstance(intended.get(field), str) or not intended[field].strip():
            raise SpecError(
                f"{path}: intended.{field} must be a non-blank string")

    expected = spec.get("php_mailers_expected")
    if not isinstance(expected, list):
        raise SpecError(
            f"{path}: `php_mailers_expected` must be a list (possibly empty). "
            f"It is the anti-vacuous-green control for M5.")
    for i, p in enumerate(expected):
        if not isinstance(p, str) or not p.strip():
            raise SpecError(
                f"{path}: php_mailers_expected[{i}] must be a non-blank path")

    _validate_observation(spec.get("observation"), path)
    return spec


def _validate_observation(obs, path):
    if not isinstance(obs, dict):
        raise SpecError(f"{path}: `observation` must be an object")
    for field in ("observed_on", "resolver", "observed_by", "source"):
        if not isinstance(obs.get(field), str) or not obs[field].strip():
            raise SpecError(f"{path}: observation.{field} must be a non-blank string")
    try:
        dt.date.fromisoformat(obs["observed_on"])
    except ValueError as exc:
        raise SpecError(
            f"{path}: observation.observed_on={obs['observed_on']!r} is not a "
            f"strict ISO date: {exc}") from None

    records = obs.get("records")
    if not isinstance(records, dict):
        raise SpecError(f"{path}: observation.records must be an object")
    for key in ("spf", "dmarc"):
        if key not in records:
            raise SpecError(
                f"{path}: observation.records.{key} is missing. Write [] to mean "
                f"QUERIED AND EMPTY, or null to mean NOT QUERIED. Those are "
                f"different facts and this checker will not guess which you meant.")
        val = records[key]
        if val is not None and not (isinstance(val, list)
                                    and all(isinstance(x, str) for x in val)):
            raise SpecError(
                f"{path}: observation.records.{key} must be null or a list of "
                f"strings, got {val!r}")
    dkim = records.get("dkim")
    if dkim is not None and not isinstance(dkim, dict):
        raise SpecError(
            f"{path}: observation.records.dkim must be null (not queried) or an "
            f"object mapping selector -> list of TXT strings")
    if isinstance(dkim, dict):
        for sel, val in dkim.items():
            if val is not None and not (isinstance(val, list)
                                        and all(isinstance(x, str) for x in val)):
                raise SpecError(
                    f"{path}: observation.records.dkim[{sel!r}] must be null or a "
                    f"list of strings")


# --------------------------------------------------------------------------
# PHP scanning. There is no PHP parser in the stdlib, so this is a small state
# machine that knows where strings and comments are. It is deliberately
# conservative: anything it cannot resolve counts as UNALIGNED.
# --------------------------------------------------------------------------

def code_mask(src):
    """mask[i] is True where src[i] is PHP *code* -- not inside a string or comment.

    Without this, `mail(` inside a docblock or a string literal reads as a call,
    and a comma inside a quoted subject line splits an argument in half.
    """
    n = len(src)
    mask = [True] * n
    i = 0
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                mask[k] = False
            i = j
        elif c == "#" and not (i + 1 < n and src[i + 1] == "["):
            j = src.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                mask[k] = False
            i = j
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                mask[k] = False
            i = j
        elif c in "'\"":
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, n)):
                mask[k] = False
            i = j
        else:
            i += 1
    return mask


_MAIL_RE = re.compile(r"mail\s*\(")
_IDENT_TAIL = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _split_args(src, mask, open_idx):
    """Split a call's arguments, respecting nesting and string/comment spans."""
    depth = 0
    args = []
    start = open_idx + 1
    i = open_idx
    n = len(src)
    while i < n:
        if mask[i]:
            c = src[i]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
                if depth == 0:
                    args.append(src[start:i])
                    return args
            elif c == "," and depth == 1:
                args.append(src[start:i])
                start = i + 1
        i += 1
    return None   # unbalanced: refuse to guess


def php_constants(src, mask):
    """`const NAME = 'value';` and `define('NAME','value')`, code-level only."""
    consts = {}
    for m in re.finditer(r"\bconst\s+([A-Za-z_]\w*)\s*=\s*(['\"])(.*?)\2\s*;", src,
                         re.DOTALL):
        if mask[m.start()]:
            consts[m.group(1)] = m.group(3)
    for m in re.finditer(
            r"\bdefine\s*\(\s*(['\"])([A-Za-z_]\w*)\1\s*,\s*(['\"])(.*?)\3\s*\)",
            src, re.DOTALL):
        if mask[m.start()]:
            consts[m.group(2)] = m.group(4)
    return consts


def eval_php_string(expr, consts):
    """Evaluate a PHP expression to a literal string, or None if it cannot be.

    Handles quoted literals, known constants, and `.` concatenation of those.
    Anything else -- a variable, a function call, an unknown constant -- returns
    None, which the caller reads as UNALIGNED. Fail closed.
    """
    if expr is None:
        return None
    m = code_mask(expr)
    out = []
    i = 0
    n = len(expr)
    while i < n:
        c = expr[i]
        if c in "'\"" and not m[i]:
            q = c
            j = i + 1
            buf = []
            while j < n:
                if expr[j] == "\\" and j + 1 < n:
                    nxt = expr[j + 1]
                    buf.append({"n": "\n", "r": "\r", "t": "\t"}.get(nxt, nxt))
                    j += 2
                    continue
                if expr[j] == q:
                    j += 1
                    break
                buf.append(expr[j])
                j += 1
            out.append("".join(buf))
            i = j
        elif m[i] and (c.isalpha() or c == "_"):
            j = i
            while j < n and expr[j] in _IDENT_TAIL:
                j += 1
            name = expr[i:j]
            if name not in consts:
                return None
            out.append(consts[name])
            i = j
        elif m[i] and (c.isspace() or c == "."):
            i += 1
        elif not m[i]:
            i += 1   # inside a comment
        else:
            return None
    return "".join(out)


class MailCall:
    def __init__(self, path, line, argc, fifth_raw, fifth_value):
        self.path = path
        self.line = line
        self.argc = argc
        self.fifth_raw = fifth_raw
        self.fifth_value = fifth_value

    def envelope_sender(self):
        """The `-f` address the 5th parameter sets, or None."""
        if not self.fifth_value:
            return None
        m = re.search(r"-f\s*([^\s'\"]+)", self.fifth_value)
        return m.group(1) if m else None

    def alignment(self, domain):
        """(aligned: bool, reason: str)."""
        if self.argc < 5:
            return False, (f"mail() has {self.argc} argument(s); no 5th parameter, "
                           f"so the envelope sender is whatever the host chooses "
                           f"(a DreamHost system address) and SPF alignment fails")
        if self.fifth_value is None:
            return False, (f"5th parameter {self.fifth_raw.strip()!r} does not "
                           f"resolve to a literal string, so alignment cannot be "
                           f"proven. Counted as unaligned -- fail closed")
        addr = self.envelope_sender()
        if addr is None:
            return False, (f"5th parameter is {self.fifth_value!r}, which sets no "
                           f"-f envelope sender")
        if "@" not in addr:
            return False, f"envelope sender {addr!r} has no domain part"
        sender_domain = addr.rsplit("@", 1)[1].strip("<>").lower()
        if sender_domain != domain.lower():
            return False, (f"envelope sender {addr!r} is on {sender_domain}, not "
                           f"{domain} -- SPF alignment is a DOMAIN match")
        return True, f"envelope sender {addr!r} aligns with {domain}"


def find_mail_calls(src, rel):
    calls = []
    mask = code_mask(src)
    consts = php_constants(src, mask)
    for m in _MAIL_RE.finditer(src):
        start = m.start()
        if not mask[start]:
            continue
        # Reject wp_mail(, $obj->mail(, Klass::mail(, and any identifier ending
        # in "mail". `@mail(` is the real thing (error-suppressed).
        prev = src[start - 1] if start else ""
        if prev in _IDENT_TAIL or prev in ">:\\$":
            continue
        open_idx = src.index("(", m.end() - 1)
        args = _split_args(src, mask, open_idx)
        if args is None:
            calls.append(MailCall(rel, src.count("\n", 0, start) + 1, -1,
                                  "<unbalanced parentheses>", None))
            continue
        fifth_raw = args[4] if len(args) >= 5 else ""
        fifth_val = eval_php_string(fifth_raw, consts) if len(args) >= 5 else None
        calls.append(MailCall(rel, src.count("\n", 0, start) + 1, len(args),
                              fifth_raw, fifth_val))
    return calls


def php_files(root):
    root = Path(root)
    for path in sorted(root.rglob("*.php")):
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        yield path, rel


def scan_mailers(root):
    calls = []
    files = 0
    for path, rel in php_files(root):
        files += 1
        calls.extend(find_mail_calls(path.read_text(encoding="utf-8",
                                                    errors="replace"), rel))
    return files, calls


# --------------------------------------------------------------------------
# Record parsing
# --------------------------------------------------------------------------

def spf_records(txts):
    return [t for t in txts if t.strip().lower().startswith("v=spf1")]


def dmarc_records(txts):
    return [t for t in txts if t.strip().lower().startswith("v=dmarc1")]


def dmarc_tags(record):
    tags = {}
    for part in record.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            tags[k.strip().lower()] = v.strip()
    return tags


def spf_covers(record, sender):
    """(covered: bool, how: str) for one sender against one SPF record.

    Two ways to be covered, and the second is derived rather than matched:
      - the sender's declared include: mechanism is present verbatim;
      - an ip4: prefix in the record actually contains the sender's address.
    """
    tokens = record.split()
    mech = sender["spf_mechanism"].strip().lower()
    for t in tokens:
        if t.strip().lower().lstrip("+").lstrip("~-?") == mech.lstrip("+"):
            return True, f"carries {sender['spf_mechanism']}"
    if sender.get("ip"):
        addr = ipaddress.ip_address(sender["ip"])
        for t in tokens:
            bare = t.lstrip("+~-?")
            for prefix, fam in (("ip4:", 4), ("ip6:", 6)):
                if bare.lower().startswith(prefix) and addr.version == fam:
                    try:
                        net = ipaddress.ip_network(bare[len(prefix):], strict=False)
                    except ValueError:
                        continue
                    if addr in net:
                        return True, f"{bare} contains {sender['ip']}"
    return False, (f"neither {sender['spf_mechanism']} nor any ip4:/ip6: prefix "
                   f"covering {sender.get('ip') or 'its addresses'}")


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

class Result:
    def __init__(self, cid, title, state, detail, key_state=None):
        self.cid = cid
        self.title = title
        self.state = state
        self.detail = detail
        self.key_state = key_state

    @property
    def ok(self):
        return self.state == STATE_PASS

    def key(self, domain):
        return f"{domain}/{self.cid}/{self.key_state or self.state.lower()}"

    def as_dict(self, domain):
        return {"check": self.cid, "title": self.title, "state": self.state,
                "detail": self.detail,
                "key": None if self.ok else self.key(domain)}


def evaluate(spec, root, today, observation=None):
    """The whole verdict. Pure: no network, no clock, no file writes."""
    domain = spec["domain"]
    obs = observation if observation is not None else spec["observation"]
    records = obs["records"]
    results = []

    # ---- P1: is the observation usable at all? ---------------------------
    observed_on = dt.date.fromisoformat(obs["observed_on"])
    age = (today - observed_on).days
    cap = spec["max_observation_age_days"]
    if age > cap:
        results.append(Result(
            "P1", "DNS observation is fresh", STATE_WRONG,
            f"observed {observed_on} ({age} days ago), cap is {cap}. Every M1-M4 "
            f"verdict below is a claim about a world that may have moved. Re-run "
            f"`python scripts/check-mail-auth.py --live --update`.",
            key_state="observation-stale"))
    elif age < 0:
        results.append(Result(
            "P1", "DNS observation is fresh", STATE_WRONG,
            f"observed_on is {observed_on}, which is {-age} day(s) in the future. "
            f"A future measurement is a typo or a wrong clock; either way it is "
            f"not evidence.",
            key_state="observation-future-dated"))
    else:
        results.append(Result(
            "P1", "DNS observation is fresh", STATE_PASS,
            f"observed {observed_on} via {obs['resolver']} ({age}d old, cap {cap}d)"))

    # ---- P2: did the scan find the mailers the spec says exist? ----------
    files, calls = scan_mailers(root)
    by_path = {}
    for c in calls:
        by_path.setdefault(c.path, []).append(c)
    missing_file, no_call = [], []
    for rel in spec["php_mailers_expected"]:
        if not (Path(root) / rel).exists():
            missing_file.append(rel)
        elif rel not in by_path:
            no_call.append(rel)
    if missing_file or no_call:
        bits = []
        if missing_file:
            bits.append("declared but not on disk: " + ", ".join(missing_file))
        if no_call:
            bits.append("on disk but the scanner found no mail() call in: "
                        + ", ".join(no_call))
        results.append(Result(
            "P2", "The mailer scan found what the spec says exists", STATE_WRONG,
            "; ".join(bits) + ". M5 constrains PHP mailers, so a scan that finds "
            "none passes trivially -- this is the control that stops that green "
            "being vacuous. Fix the scanner or update php_mailers_expected with a "
            "reason; do not delete the entry to go green.",
            key_state="mailer-scan-broken"))
    else:
        results.append(Result(
            "P2", "The mailer scan found what the spec says exists", STATE_PASS,
            f"{files} PHP file(s) scanned, {len(calls)} mail() call(s) found, "
            f"all {len(spec['php_mailers_expected'])} declared mailer(s) present"))

    # ---- M1: SPF exists and is exactly one record ------------------------
    spf_txt = records.get("spf")
    spf_record = None
    if spf_txt is None:
        results.append(Result("M1", "SPF exists and is one record", STATE_UNMEASURED,
                              f"observation.records.spf is null -- nobody has "
                              f"queried TXT {domain}. Unknown, not fine.",
                              key_state="unmeasured"))
    else:
        found = spf_records(spf_txt)
        if not found:
            results.append(Result("M1", "SPF exists and is one record", STATE_ABSENT,
                                  f"queried TXT {domain}: no v=spf1 record. Every "
                                  f"receiver evaluates SPF as `none`, so nothing "
                                  f"we send is authorised by us.",
                                  key_state="absent"))
        elif len(found) > 1:
            results.append(Result("M1", "SPF exists and is one record", STATE_WRONG,
                                  f"{len(found)} v=spf1 records at {domain}. RFC "
                                  f"7208 makes that a permerror -- worse than "
                                  f"none, because it fails deterministically: "
                                  f"{found!r}",
                                  key_state="multiple-records"))
        else:
            spf_record = found[0].strip()
            if not re.search(r"[\s+~?-]all\b", spf_record):
                results.append(Result("M1", "SPF exists and is one record",
                                      STATE_WRONG,
                                      f"record has no `all` mechanism, so it never "
                                      f"reaches a verdict for an unlisted sender: "
                                      f"{spf_record!r}",
                                      key_state="no-all-mechanism"))
                spf_record = None
            else:
                results.append(Result("M1", "SPF exists and is one record",
                                      STATE_PASS, spf_record))

    # ---- M2: SPF covers every sender -------------------------------------
    spf_covers_php = False
    if spf_record is None:
        results.append(Result(
            "M2", "SPF covers every sending IP", STATE_UNEVALUABLE,
            "there is no single usable SPF record to read (see M1). Not a pass: "
            "the senders are uncovered either way.",
            key_state="unevaluable-no-spf"))
    else:
        uncovered = []
        how = []
        for s in spec["senders"]:
            ok, why = spf_covers(spf_record, s)
            (how if ok else uncovered).append(f"{s['id']}: {why}")
        if uncovered:
            results.append(Result(
                "M2", "SPF covers every sending IP", STATE_WRONG,
                "uncovered sender(s) -- " + "; ".join(uncovered),
                key_state="uncovered-sender"))
        else:
            results.append(Result("M2", "SPF covers every sending IP", STATE_PASS,
                                  "; ".join(how)))
        spf_covers_php = all(
            spf_covers(spf_record, s)[0] for s in spec["senders"] if s["runs_php"])

    # ---- M3: DMARC exists -------------------------------------------------
    dmarc_txt = records.get("dmarc")
    published_policy = None
    published_sp = None
    if dmarc_txt is None:
        results.append(Result("M3", "DMARC exists", STATE_UNMEASURED,
                              f"observation.records.dmarc is null -- nobody has "
                              f"queried TXT _dmarc.{domain}.",
                              key_state="unmeasured"))
    else:
        found = dmarc_records(dmarc_txt)
        if not found:
            results.append(Result("M3", "DMARC exists", STATE_ABSENT,
                                  f"queried TXT _dmarc.{domain}: no v=DMARC1 "
                                  f"record. No policy, and no rua, so we get no "
                                  f"reports telling us who is failing.",
                                  key_state="absent"))
        elif len(found) > 1:
            results.append(Result("M3", "DMARC exists", STATE_WRONG,
                                  f"{len(found)} v=DMARC1 records at _dmarc.{domain}; "
                                  f"DMARC requires exactly one and ignores the lot "
                                  f"otherwise: {found!r}",
                                  key_state="multiple-records"))
        else:
            tags = dmarc_tags(found[0])
            p = tags.get("p", "").lower()
            if not p:
                results.append(Result("M3", "DMARC exists", STATE_WRONG,
                                      f"record carries no p= tag: {found[0]!r}",
                                      key_state="no-policy-tag"))
            elif p not in POLICY_RANK:
                results.append(Result("M3", "DMARC exists", STATE_WRONG,
                                      f"p={p!r} is not one of "
                                      f"{sorted(POLICY_RANK)}: {found[0]!r}",
                                      key_state="bad-policy-value"))
            else:
                published_policy = p
                sp = tags.get("sp", "").lower()
                published_sp = sp if sp in POLICY_RANK else None
                results.append(Result("M3", "DMARC exists", STATE_PASS,
                                      f"p={p}"
                                      + (f", sp={sp}" if sp else "")
                                      + (f", rua={tags['rua']}" if "rua" in tags
                                         else " -- WARNING: no rua=, so failures "
                                              "are invisible to us")))

    # ---- M4: DKIM selector resolves ---------------------------------------
    selector = spec["intended"]["dkim_selector"]
    dkim = records.get("dkim")
    if dkim is None:
        results.append(Result("M4", "DKIM selector resolves", STATE_UNMEASURED,
                              f"observation.records.dkim is null -- nobody has "
                              f"queried TXT {selector}.{domain}.",
                              key_state="unmeasured"))
    elif selector not in dkim:
        results.append(Result("M4", "DKIM selector resolves", STATE_UNMEASURED,
                              f"the observation records no answer for the selector "
                              f"the spec intends ({selector}); it lists "
                              f"{sorted(dkim) or 'nothing'}.",
                              key_state="unmeasured"))
    else:
        txts = dkim[selector]
        if txts is None:
            results.append(Result("M4", "DKIM selector resolves", STATE_UNMEASURED,
                                  f"{selector}.{domain} recorded as not queried",
                                  key_state="unmeasured"))
        elif not txts:
            results.append(Result("M4", "DKIM selector resolves", STATE_ABSENT,
                                  f"queried TXT {selector}.{domain}: nothing "
                                  f"(NXDOMAIN). Nothing we send is signed, so DKIM "
                                  f"alignment is unavailable to every sender.",
                                  key_state="absent"))
        else:
            joined = " ".join(txts)
            if "v=DKIM1" not in joined and "p=" not in joined:
                results.append(Result("M4", "DKIM selector resolves", STATE_WRONG,
                                      f"TXT at {selector}.{domain} does not look "
                                      f"like a DKIM key: {txts!r}",
                                      key_state="not-a-dkim-key"))
            else:
                results.append(Result("M4", "DKIM selector resolves", STATE_PASS,
                                      f"{selector}.{domain} publishes a key"))

    # ---- M5: THE INTERLOCK ------------------------------------------------
    unaligned = []
    aligned = []
    for c in calls:
        ok, why = c.alignment(domain)
        (aligned if ok else unaligned).append((c, why))

    if unaligned or not spf_covers_php:
        ceiling = "none"
    else:
        ceiling = "reject"

    reasons = []
    if unaligned:
        reasons.append(f"{len(unaligned)} PHP mailer(s) fail envelope-sender alignment")
    if not spf_covers_php:
        reasons.append("SPF does not (or cannot be shown to) authorise the IP that "
                       "runs PHP, so an aligned -f would still not produce an SPF pass")

    intended_tags = dmarc_tags(spec["intended"]["dmarc"])
    intended_policy = intended_tags.get("p", "").lower()
    intended_sp = intended_tags.get("sp", "").lower()

    over = []
    for label, value in (("intended (data/mail-auth.json)", intended_policy),
                         ("intended sp=", intended_sp),
                         ("published (observed in DNS)", published_policy),
                         ("published sp=", published_sp)):
        if value and value in POLICY_RANK and POLICY_RANK[value] > POLICY_RANK[ceiling]:
            over.append(f"{label} p={value}")

    if intended_policy and intended_policy not in POLICY_RANK:
        results.append(Result(
            "M5", "DMARC policy is at or below the alignment ceiling", STATE_WRONG,
            f"intended.dmarc has p={intended_policy!r}, which is not a DMARC "
            f"policy value. Refusing to reason about a policy nobody can publish.",
            key_state="intended-policy-unparseable"))
    elif over:
        results.append(Result(
            "M5", "DMARC policy is at or below the alignment ceiling", STATE_WRONG,
            f"ceiling is p={ceiling} because " + "; and ".join(reasons)
            + ". Above it: " + ", ".join(over)
            + ". Publishing that policy tells every receiver to discard mail this "
              "site sends -- silently, with no bounce to the visitor and no error "
              "to us. Fix the mailer(s) and the SPF record FIRST, then raise the "
              "policy.",
            key_state="policy-above-ceiling"))
    else:
        detail = (f"ceiling p={ceiling}; intended p={intended_policy or 'unset'}; "
                  f"published: "
                  + (f"p={published_policy}" if published_policy
                     else "no DMARC policy is published"))
        if reasons:
            detail += " -- ceiling held down by: " + "; ".join(reasons)
        results.append(Result(
            "M5", "DMARC policy is at or below the alignment ceiling",
            STATE_PASS, detail))

    return results, files, calls, aligned, unaligned, ceiling


# --------------------------------------------------------------------------
# Live resolution (advisory; --live only)
# --------------------------------------------------------------------------

class ResolveError(Exception):
    pass


def resolve_txt(name, nameserver=None):
    """TXT strings for `name`. Uses dnspython if installed, else nslookup.

    Raises ResolveError rather than returning [] on a failure: an empty answer
    and a broken resolver are different facts, and conflating them is how a
    guard reports a clean bill of health it never earned.
    """
    try:
        import dns.resolver  # noqa: F401
    except ImportError:
        pass
    else:
        import dns.resolver as _r
        try:
            resolver = _r.Resolver(configure=True)
            if nameserver:
                import socket
                resolver.nameservers = [socket.gethostbyname(nameserver)]
            answer = resolver.resolve(name, "TXT")
            return ["".join(s.decode("utf-8", "replace") for s in rr.strings)
                    for rr in answer]
        except _r.NXDOMAIN:
            return []
        except _r.NoAnswer:
            return []
        except Exception as exc:  # noqa: BLE001 -- any resolver failure is a refusal
            raise ResolveError(f"{name}: {exc}") from None

    exe = shutil.which("nslookup")
    if not exe:
        raise ResolveError(
            "no resolver available: dnspython is not installed and nslookup is "
            "not on PATH. `pip install dnspython` or run this where nslookup is.")
    cmd = [exe, "-type=TXT", name] + ([nameserver] if nameserver else [])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ResolveError(f"{name}: {exc}") from None
    out = proc.stdout or ""
    low = out.lower()
    if "can't find" in low or "nxdomain" in low or "non-existent domain" in low:
        return []
    if proc.returncode != 0 and not re.search(r'text\s*=', low):
        raise ResolveError(f"{name}: nslookup exit {proc.returncode}: "
                           f"{(proc.stderr or out).strip()[:300]}")
    txts = []
    for m in re.finditer(r'text\s*=\s*((?:"[^"]*"\s*)+)', out, re.IGNORECASE):
        txts.append("".join(re.findall(r'"([^"]*)"', m.group(1))))
    return txts


def live_observation(spec, today):
    domain = spec["domain"]
    ns = spec["observation"].get("resolver") or None
    selector = spec["intended"]["dkim_selector"]
    return {
        "observed_on": today.isoformat(),
        "resolver": ns or "system resolver",
        "method": "Live TXT queries by scripts/check-mail-auth.py --live.",
        "observed_by": "scripts/check-mail-auth.py --live",
        "records": {
            "spf": resolve_txt(domain, ns),
            "dmarc": resolve_txt(f"_dmarc.{domain}", ns),
            "dkim": {selector: resolve_txt(f"{selector}.{domain}", ns)},
        },
        "source": (f"Resolved live against {ns or 'the system resolver'} by "
                   f"scripts/check-mail-auth.py --live."),
    }


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def print_results(results, spec, aligned, unaligned, ceiling, files, calls, out):
    domain = spec["domain"]
    print(f"Mail auth guard -- {domain}", file=out)
    print(f"  spec   {spec.get('_spec_path', 'data/mail-auth.json')}", file=out)
    print(f"  scan   {files} PHP file(s), {len(calls)} mail() call(s), "
          f"{len(aligned)} aligned / {len(unaligned)} unaligned", file=out)
    print(file=out)
    width = max(len(r.state) for r in results)
    for r in results:
        print(f"  {r.cid:<3} {r.state:<{width}}  {r.title}", file=out)
        print(f"        {r.detail}", file=out)
    print(file=out)

    # Green must carry a number, never silence: the ceiling is printed on every
    # run, pass or fail, with the file:line that holds it down.
    print(f"M5 CEILING -- p={ceiling}", file=out)
    if unaligned:
        print(f"  held down by {len(unaligned)} unaligned PHP mailer(s):", file=out)
        for c, why in unaligned:
            print(f"    {c.path}:{c.line}  {why}", file=out)
        print("  Fix: pass a 5th parameter, e.g. mail($to, $subj, $body, $hdrs, "
              f"'-f ' . FROM) with FROM on {domain}, AND publish an SPF record "
              "covering the sending IP. Both, or the ceiling stays here.", file=out)
    for c, why in aligned:
        print(f"  aligned: {c.path}:{c.line}  {why}", file=out)
    if not calls:
        print("  no mail() calls found at all -- see P2", file=out)
    print(file=out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="check mode (the default); exit 1 on any unacknowledged finding")
    ap.add_argument("--json", action="store_true",
                    help="emit the verdict as JSON on stdout (still sets the exit code)")
    ap.add_argument("--live", action="store_true",
                    help="re-resolve DNS and judge against what is there NOW instead "
                         "of the recorded observation. Needs network; exit 3 if the "
                         "resolver fails, never a silent green.")
    ap.add_argument("--update", action="store_true",
                    help="with --live, write the fresh observation back into the spec")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="evaluate the observation clock and acknowledgement expiry "
                         "at this date, so a test can force the states rather than "
                         "wait for them")
    ap.add_argument("--spec", help="path to an alternative mail-auth spec (tests)")
    ap.add_argument("--ledger", help="path to an alternative acknowledgement ledger (tests)")
    ap.add_argument("--repo-root", help="tree to scan for PHP mailers (tests)")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()
    spec_path = Path(args.spec) if args.spec else SPEC_PATH
    root = Path(args.repo_root) if args.repo_root else REPO_ROOT

    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        print(f"REFUSED: the mail-auth spec cannot be trusted, so this check "
              f"cannot say what it is asserting.\n  {exc}", file=sys.stderr)
        return 2
    spec["_spec_path"] = str(spec_path)

    # Loaded BEFORE evaluating, for the reason check-encoding-safety.py loads it
    # first: a malformed ledger must stop the run outright, or every acknowledged
    # finding reappears as a fresh one and sends someone hunting a bug nobody
    # introduced.
    try:
        ledger = load_ledger(ACK_CHECK_NAME, args.ledger)
    except AcknowledgementError as exc:
        print(f"REFUSED: the acknowledgement ledger cannot be trusted, so this "
              f"check cannot say what it is tolerating.\n  {exc}", file=sys.stderr)
        return 2

    observation = None
    if args.live:
        try:
            observation = live_observation(spec, today)
        except ResolveError as exc:
            print(f"REFUSED (--live): DNS resolution failed, so this run has "
                  f"measured nothing. A resolver failure is not an empty answer.\n"
                  f"  {exc}", file=sys.stderr)
            return 3
        recorded = spec["observation"]["records"]
        if observation["records"] != recorded:
            print("DRIFT: live DNS disagrees with the recorded observation in "
                  f"{spec_path}.", file=sys.stderr)
            print(f"  recorded ({spec['observation']['observed_on']}): "
                  f"{json.dumps(recorded, sort_keys=True)}", file=sys.stderr)
            print(f"  live     ({today}): "
                  f"{json.dumps(observation['records'], sort_keys=True)}",
                  file=sys.stderr)
            print("  Re-run with --update to record it.", file=sys.stderr)
        if args.update:
            doc = json.loads(spec_path.read_text(encoding="utf-8"))
            observation["mx"] = doc.get("observation", {}).get("mx")
            doc["observation"] = observation
            spec_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
            print(f"Wrote a fresh observation into {spec_path}.", file=sys.stderr)

    results, files, calls, aligned, unaligned, ceiling = evaluate(
        spec, root, today, observation)

    findings = [r for r in results if not r.ok]
    domain = spec["domain"]
    report = ledger.assess(fired_keys={r.key(domain) for r in findings}, today=today)
    suppressed = report.acknowledged_keys
    waived = [r for r in findings if r.key(domain) in suppressed]
    unwaived = [r for r in findings if r.key(domain) not in suppressed]

    if args.json:
        print(json.dumps({
            "domain": domain,
            "as_of": today.isoformat(),
            "ceiling": ceiling,
            "php_files_scanned": files,
            "mail_calls": [{"path": c.path, "line": c.line, "argc": c.argc,
                            "aligned": c.alignment(domain)[0],
                            "reason": c.alignment(domain)[1]} for c in calls],
            "results": [r.as_dict(domain) for r in results],
            "acknowledged": sorted(suppressed),
            "expired_acknowledgements": [a.key for a in report.expired],
            "unwaived": [r.key(domain) for r in unwaived],
        }, indent=2))
        return 1 if (unwaived or report.blocking) else 0

    print_results(results, spec, aligned, unaligned, ceiling, files, calls,
                  sys.stdout)

    if waived:
        print(f"ACKNOWLEDGED FINDINGS ({len(waived)}) -- real, printed, counted, "
              f"and not failed on because somebody accepted them on a date:")
        for r in waived:
            print(f"  {r.key(domain)}")
            print(f"      {r.detail}")
        print()

    report.print_to(sys.stdout)
    print()

    if unwaived:
        print(f"FAIL: {len(unwaived)} unacknowledged mail-auth finding(s):")
        for r in unwaived:
            print(f"  [{r.state}] {r.cid} {r.title}")
            print(f"      key    {r.key(domain)}")
            print(f"      detail {r.detail}")
        print("\nEach one is either fixed, or written into "
              "data/acknowledgements.json with a name, a reason and a review_by. "
              "Both are decisions; neither is a shrug.")
        return 1

    if report.blocking:
        print(f"FAIL: {len(report.expired)} acknowledgement(s) expired. Every "
              f"mail-auth finding is either clear or acknowledged -- what is red "
              f"is the ACCEPTANCE, listed above with what to do about it.")
        return 1

    print(f"OK: {len(results)} check(s), {len(results) - len(findings)} passing, "
          f"{len(waived)} acknowledged. DMARC ceiling p={ceiling}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
