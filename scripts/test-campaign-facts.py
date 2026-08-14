#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forced-failure tests for scripts/check-campaign-facts.py.

WHY THIS EXISTS
---------------
CLAUDE.md, Testing discipline: "A guard seen only in its passing state has not
been shown to work. Green is equally consistent with 'the condition is safe' and
'the check never fires'."

check-campaign-facts.py is green on the real repo today, and two of its
verifiers are green VACUOUSLY -- platforms_shipped has no unshipped platform to
find, exactly the early-return vacuity test-platform-claims.py exists to record
for its own guard. So the green says nothing on its own. Every case below forces
a state the live repo is not in and asserts the check goes RED, plus the two
states where going red would itself be dishonest (posted copy; an acknowledged
finding) and must stay green.

Nothing here reads or writes real repo data except the last two cases, which
assert that the real campaign files still exist and still parse -- a renamed
directory would otherwise shrink this guard's coverage to nothing while it went
on printing OK.

Isolation follows test-platform-claims.py: import the module, redirect its path
constants at a temp tree, restore afterwards. No network, no secrets, stdlib
only.

Run:  python scripts/test-campaign-facts.py     (exit 0 = pass)
"""

import copy as copymod
import datetime as dt
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_campaign_facts", ROOT / "scripts" / "check-campaign-facts.py")
ccf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ccf)

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


# --- fixtures --------------------------------------------------------------

CLEAN_FACTS = [
    {
        "id": "platforms-downloadable",
        "constraint": "Do not promise a platform that is not downloadable.",
        "verify": "checked",
        "check": "platforms_shipped",
        "source": "public/data/version.json -> latest_release.platforms",
    },
    {
        "id": "leaderboard-live",
        "constraint": "Do not promise a feature that is not live.",
        "verify": "checked",
        "check": "board_live",
        "source": "published-board.json and board-liveness.json",
    },
    {
        "id": "no-version-in-copy",
        "constraint": "Do not name a build version in the copy.",
        "verify": "checked",
        "check": "no_version_literal_in_copy",
        "source": "this campaign's own copy strings",
    },
    {
        "id": "league-page-in-step",
        "constraint": "Do not say the league page shows the current board unless it does.",
        "verify": "delegated",
        "check": "scripts/watcher.py",
        "source": "scripts/watcher.py, wired by .github/workflows/watch.yml",
    },
    {
        "id": "bug-reporter-does-not-transmit",
        "constraint": "Do not point anyone at the F8 reporter while it fails to transmit.",
        "verify": "online",
        "check": "issue_state",
        "issue": "PipFoweraker/pdoom1#800",
        "expect": "open",
        "source": "pdoom1#800",
    },
    {
        "id": "still-an-alpha",
        "constraint": "This is an early alpha.",
        "verify": "human",
        "why_not_machine": "Maturity is a judgement, not a field.",
        "source": "Pip's call.",
        "human_verified": {"by": "a person", "on": "2026-08-14",
                           "review_by": "2026-11-14"},
    },
    {
        "id": "lead-with-the-fork",
        "constraint": "Lead with the fork, not a version number.",
        "verify": "durable",
        "why_durable": "An editorial rule. It asserts nothing about the world.",
    },
]

CLEAN_COPY = {
    "bluesky": "The game is playable. Windows, macOS and Linux.\n\nhttps://pdoom1.com/",
}

LEDGER = {
    "note": "test fixture",
    "schema": "pdoom-acknowledgements/v1",
    "policy": {"warn_within_days": 14, "source": "test fixture"},
    "checks": {"check-campaign-facts": "the campaign fact-guards"},
    "acknowledgements": [],
}


class Sandbox:
    """Point the whole checker at a temp tree.

    Defaults describe a world in which every constraint holds: three shipped
    platforms, a published board observed live today with scores on it, and a
    delegated guard that exists and is wired. Each test changes ONE thing.
    """

    KEYS = ("REPO_ROOT", "CAMPAIGNS_DIR", "VERSION_JSON", "PUBLISHED_BOARD",
            "BOARD_LIVENESS", "WORKFLOWS_DIR")

    def __init__(self, facts=None, copy=None, platforms=None, posted=None,
                 entries=11, observed_days_ago=0, published=("weekly-2026-w32", "L4"),
                 observed_key=None, wire_workflow=True, create_guard=True,
                 campaigns=True, ledger=None, drop_platforms_key=False):
        self.facts = CLEAN_FACTS if facts is None else facts
        self.copy = CLEAN_COPY if copy is None else copy
        self.platforms = {"windows": True, "macos": True, "linux": True} \
            if platforms is None else platforms
        self.posted = posted or {"bluesky": None}
        self.entries = entries
        self.observed_days_ago = observed_days_ago
        self.published = published
        self.observed_key = observed_key or published
        self.wire_workflow = wire_workflow
        self.create_guard = create_guard
        self.campaigns = campaigns
        self.ledger = LEDGER if ledger is None else ledger
        self.drop_platforms_key = drop_platforms_key

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = {k: getattr(ccf, k) for k in self.KEYS}

        camp = self.tmp / "content" / "campaigns"
        camp.mkdir(parents=True)
        if self.campaigns:
            (camp / "2026-01-01-test.json").write_text(json.dumps({
                "campaign": "test", "approved": False,
                "_facts_this_copy_must_not_break": self.facts,
                "copy": self.copy, "posted": self.posted,
            }, indent=2), encoding="utf-8")

        release = {"version": "v9.9.9"}
        if not self.drop_platforms_key:
            release["platforms"] = self.platforms
        vj = self.tmp / "public" / "data" / "version.json"
        vj.parent.mkdir(parents=True)
        vj.write_text(json.dumps({"latest_release": release}), encoding="utf-8")

        board = self.tmp / "public" / "leaderboard" / "data"
        board.mkdir(parents=True)
        (board / "published-board.json").write_text(json.dumps({
            "seed": self.published[0], "ladder_epoch": self.published[1],
        }), encoding="utf-8")
        stamp = (dt.datetime.now(dt.timezone.utc)
                 - dt.timedelta(days=self.observed_days_ago)).isoformat()
        (board / "board-liveness.json").write_text(json.dumps({
            "checked_at": stamp, "verdict": "live",
            "deployed_board": {"seed": self.observed_key[0],
                               "version": self.observed_key[1],
                               "entries": self.entries},
        }), encoding="utf-8")

        wf = self.tmp / ".github" / "workflows"
        wf.mkdir(parents=True)
        if self.create_guard:
            (self.tmp / "scripts").mkdir(exist_ok=True)
            (self.tmp / "scripts" / "watcher.py").write_text("# guard\n",
                                                             encoding="utf-8")
        if self.wire_workflow:
            (wf / "watch.yml").write_text("run: python scripts/watcher.py\n",
                                          encoding="utf-8")
        else:
            (wf / "other.yml").write_text("run: echo nothing\n", encoding="utf-8")

        self.ledger_path = self.tmp / "acknowledgements.json"
        self.ledger_path.write_text(json.dumps(self.ledger), encoding="utf-8")

        ccf.REPO_ROOT = self.tmp
        ccf.CAMPAIGNS_DIR = camp
        ccf.VERSION_JSON = vj
        ccf.PUBLISHED_BOARD = board / "published-board.json"
        ccf.BOARD_LIVENESS = board / "board-liveness.json"
        ccf.WORKFLOWS_DIR = wf
        return self

    def run(self, *extra):
        argv = sys.argv
        sys.argv = ["check-campaign-facts.py", "--ledger", str(self.ledger_path),
                    *extra]
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = ccf.main()
        finally:
            sys.argv = argv
        return code, out.getvalue() + err.getvalue()

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            setattr(ccf, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


def mutate(index, **changes):
    """A copy of CLEAN_FACTS with one entry changed. Keeps each case one edit."""
    facts = copymod.deepcopy(CLEAN_FACTS)
    facts[index].update(changes)
    return facts


def drop(index, field):
    facts = copymod.deepcopy(CLEAN_FACTS)
    facts[index].pop(field, None)
    return facts


# --- the baseline: without this, every red below proves nothing -------------

print("\n0. The clean world is GREEN (so a red anywhere else means something)")
with Sandbox() as s:
    code, out = s.run()
    check(code == 0, f"clean tree exits 0 (got {code})")
    check("OK: 7 fact-guard(s) checked" in out, "reports what it checked, with a count")
    check("NOT CHECKED HERE (1)" in out,
          "the online entry prints as NOT CHECKED, never as a pass")

print("\n1. STRUCTURE -- the old rotting shape cannot come back")
with Sandbox(facts=["Windows ships today. macOS and Linux are NOT yet released."]) as s:
    code, out = s.run()
    check(code == 1, f"a bare prose string is RED (got {code})")
    check("BARE STRING" in out, "and is named as the old shape, with the migration doc")

with Sandbox(facts=mutate(0, check="platforms_shipped_v2")) as s:
    code, out = s.run()
    check(code == 1, f"verify:checked naming a verifier that does not exist is RED "
                     f"(got {code})")
    check("UNKNOWN check" in out, "and says so")

with Sandbox(facts=mutate(0, verify="probably-fine")) as s:
    code, out = s.run()
    check(code == 1, f"an undeclared tier is RED (got {code})")

with Sandbox(facts=drop(5, "human_verified")) as s:
    code, out = s.run()
    check(code == 1, f"a human-tier fact with no dated verification is RED (got {code})")
    check("MISSING human_verified" in out, "and says what to add")

with Sandbox(facts=drop(5, "why_not_machine")) as s:
    code, out = s.run()
    check(code == 1, "'unverifiable' with no reason is RED -- indistinguishable "
                     "from nobody trying")

with Sandbox(facts=mutate(6, source="public/data/version.json")) as s:
    code, out = s.run()
    check(code == 1, "a durable rule carrying a source is RED (it claims nothing "
                     "to check)")

facts = copymod.deepcopy(CLEAN_FACTS)
facts[1]["id"] = "platforms-downloadable"
with Sandbox(facts=facts) as s:
    code, out = s.run()
    check(code == 1 and "DUPLICATE id" in out,
          "two entries reporting under one id is RED -- one of them is invisible")

print("\n2. THE CLOCK -- what expires is the verification, not the claim")
with Sandbox() as s:
    code, out = s.run("--as-of", "2026-11-05")
    check(code == 0 and "EXPIRING SOON (1)" in out,
          "inside the warn window: still green, and warned by name")
    code, out = s.run("--as-of", "2026-11-15")
    check(code == 1, f"one day past review_by is RED (got {code})")
    check("HUMAN VERIFICATION EXPIRED" in out, "and the red is about the VERIFICATION")
    check("re-verify" in out.lower() or "set a new human_verified" in out,
          "and it tells the reader how a person closes it")

print("\n3. platforms_shipped -- both directions, against the derived source")
with Sandbox(platforms={"windows": True, "macos": False, "linux": False},
             copy={"bluesky": "Download for Windows, macOS and Linux today."}) as s:
    code, out = s.run()
    check(code == 1, f"copy promising an unshipped platform is RED (got {code})")
    check("copy-promises-an-unshipped-platform" in out, "keyed for acknowledgement")

with Sandbox(platforms={"windows": True, "macos": False, "linux": False},
             copy={"bluesky": "Windows today; macOS and Linux coming soon."}) as s:
    code, out = s.run()
    check(code == 0, f"...but a softened promise is honest and stays GREEN (got {code})")

with Sandbox(copy={"bluesky": "Windows today; Mac and Linux this week."}) as s:
    code, out = s.run()
    check(code == 1, f"copy deferring a platform that HAS shipped is RED (got {code})")
    check("copy-defers-a-shipped-platform" in out,
          "the direction check-platform-claims.py does not cover")

with Sandbox(copy={"bluesky": "Windows today — Mac and Linux this week."}) as s:
    code, out = s.run()
    check("defers windows" not in out,
          "the clause split keeps 'Windows today' out of the deferral finding")

with Sandbox(drop_platforms_key=True) as s:
    code, out = s.run()
    check(code == 1, f"version.json with no platforms field is RED (got {code})")
    check("never as agreement" in out,
          "absence is unrecorded, never a clean bill of health")

print("\n4. board_live -- an observation, with an age on it")
with Sandbox(entries=0) as s:
    code, out = s.run()
    check(code == 1 and "NO SCORES ON IT" in out,
          "a board observed with zero entries is RED -- empty is indistinguishable "
          "from a wrong key")

with Sandbox(observed_days_ago=45) as s:
    code, out = s.run()
    check(code == 1 and "TOO OLD" in out,
          "an observation older than the window cannot support 'it is live'")

with Sandbox(observed_key=("weekly-2026-w31", "L4")) as s:
    code, out = s.run()
    check(code == 1 and "NOT THE PUBLISHED BOARD" in out,
          "published key vs observed key disagreeing is RED (the #293 composed-key "
          "defect)")

print("\n5. no_version_literal_in_copy")
with Sandbox(copy={"bluesky": "p(Doom)1 v0.14.0 is out."}) as s:
    code, out = s.run()
    check(code == 1 and "NAMES A BUILD VERSION" in out,
          "a build literal in copy is RED")

print("\n6. delegated -- the delegation has to be real")
with Sandbox(create_guard=False) as s:
    code, out = s.run()
    check(code == 1 and "DOES NOT EXIST" in out,
          "delegating to a script that is not there is RED")

with Sandbox(wire_workflow=False) as s:
    code, out = s.run()
    check(code == 1 and "NOTHING RUNS" in out,
          "delegating to a guard no workflow calls is RED -- 'documented' is not "
          "'runs'")

print("\n7. The two states where going red would itself be dishonest")
with Sandbox(copy={"bluesky": "Windows today; Mac and Linux this week."},
             posted={"bluesky": "2026-07-24T09:00:00Z"}) as s:
    code, out = s.run()
    check(code == 0, f"a POSTED campaign does not block (got {code}) -- the remedy "
                     f"would be falsifying a record")
    check("REPORTED, NOT FAILED ON" in out, "...but it is still printed, in full")

ack_ledger = copymod.deepcopy(LEDGER)
ack_ledger["acknowledgements"] = [{
    "check": "check-campaign-facts",
    "key": "content/campaigns/2026-01-01-test.json::copy-defers-a-shipped-platform",
    "what": "copy defers shipped platforms", "why": "unposted draft, Pip's voice",
    "accepted_by": "test", "accepted_on": "2026-08-14", "review_by": "2026-09-15",
    "on_expiry": "post, rewrite or archive", "source": "test fixture",
}]
with Sandbox(copy={"bluesky": "Windows today; Mac and Linux this week."},
             ledger=ack_ledger) as s:
    code, out = s.run("--as-of", "2026-08-14")
    check(code == 0 and "ACKNOWLEDGED FINDINGS (1)" in out,
          "an acknowledged finding is green, printed and COUNTED -- never silent")
    code, out = s.run("--as-of", "2026-09-16")
    check(code == 1 and "EXPIRED" in out,
          "...and the acceptance itself expires, which is a red a person can close")

print("\n8. The check refuses rather than guessing")
bad = copymod.deepcopy(LEDGER)
bad["checks"] = {}
with Sandbox(ledger=bad) as s:
    code, out = s.run()
    check(code == 2 and "REFUSED" in out,
          "a ledger it cannot parse means it cannot say what it is tolerating: "
          "exit 2, not a verdict")

with Sandbox(campaigns=False) as s:
    code, out = s.run()
    check(code == 1 and "NO CAMPAIGN FILES" in out,
          "scanning an empty set is RED -- a guard with nothing to read must not "
          "report OK")

print("\n9. The real repo (so a rename cannot silently shrink coverage)")
real = sorted((ROOT / "content" / "campaigns").glob("*.json"))
check(len(real) >= 2, f"content/campaigns/ still holds campaign JSON ({len(real)} found)")
for path in real:
    data = json.loads(path.read_text(encoding="utf-8"))
    facts = data.get(ccf.FACTS_KEY)
    check(isinstance(facts, list) and facts and all(isinstance(x, dict) for x in facts),
          f"{path.name}: every fact-guard is an object, not prose")
    check(all(x.get("verify") in ccf.TIERS for x in facts),
          f"{path.name}: every fact-guard declares a known tier")

print()
if failures:
    print(f"FAIL: {len(failures)} assertion(s)")
    for m in failures:
        print(f"  - {m}")
    sys.exit(1)
print("PASS: check-campaign-facts.py goes red on every forced state above, and "
      "stays green on the two where red would be a lie.")
sys.exit(0)
