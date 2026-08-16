#!/usr/bin/env python
"""Refuse reader-facing prose that describes a mechanism which does not run.

THE FAILURE THIS EXISTS FOR
---------------------------
On 2026-08-16 the privacy page was rewritten to be true of a feedback system that
had been built but not wired. The page said "Some pages carry a feedback widget"
while `grep -rln feedback.js public/ --include=*.html` returned nothing, and it
promised 90/180/30-day deletion clocks that only `scripts/purge-feedback.py`
enforces -- a script no workflow scheduled.

FEEDBACK_INTAKE_CONTRACT.md section 7 had recorded that the privacy page must not
LAG the widget. Nobody wrote down that it must not LEAD it either. Both directions
are the same defect: prose and mechanism disagreeing about the present tense.

Leading is the more dangerous direction. "We delete your contact details after 90
days" is FALSE until something deletes them, and a visitor may hand over an
address on the strength of it. And `auto-deploy-on-push.yml` fires ~4x/day gated
on nothing, so "it will be true by the time anyone reads it" is not a defence --
the prose reaches production on its own.

WHAT THIS IS NOT
----------------
This does not read prose for meaning. It pins NAMED claims, listed in
`data/prose-mechanism-claims.json`, to conditions this repo can evaluate. A claim
nothing here can check does not belong in reader-facing prose yet -- that is the
same rule `content/campaigns/README.md` 2.1 arrived at after two fact-guards had
silently become lies.

Exit 0 clean, 1 on a finding, 2 on a malformed registry.

    python scripts/check-prose-mechanism-coupling.py
    python scripts/check-prose-mechanism-coupling.py --registry <path> --root <dir>
"""

import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


REPO = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = REPO / "data" / "prose-mechanism-claims.json"

REQUIRED_KEYS = ("id", "claim_file", "claim_pattern", "requires", "why")
KNOWN_KINDS = ("page_loads_script", "workflow_schedules", "path_exists")

CRON_RE = re.compile(r"^\s*-?\s*cron\s*:", re.MULTILINE)


class RegistryError(Exception):
    """The registry is malformed. Reject the whole file, never skip an entry."""


# ---------------------------------------------------------------- registry ---

def load_registry(path):
    """Load and validate. Rejects the WHOLE file rather than skipping an entry.

    A skipped entry resurfaces later as a fresh finding and sends someone hunting
    a bug nobody introduced -- the reasoning `scripts/acknowledgements.py` already
    landed on for its ledger.
    """
    if not path.is_file():
        raise RegistryError("registry not found: %s" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError("registry is not valid JSON: %s" % exc)

    if not isinstance(data, dict) or "claims" not in data:
        raise RegistryError("registry must be an object with a 'claims' array")
    claims = data["claims"]
    if not isinstance(claims, list) or not claims:
        raise RegistryError("registry 'claims' must be a non-empty array")

    seen = set()
    for i, c in enumerate(claims):
        where = "claims[%d]" % i
        if not isinstance(c, dict):
            raise RegistryError("%s is not an object" % where)
        for k in REQUIRED_KEYS:
            if k not in c or c[k] in (None, "", {}):
                raise RegistryError("%s is missing a non-blank '%s'" % (where, k))
        if c["id"] in seen:
            raise RegistryError("duplicate claim id %r" % c["id"])
        seen.add(c["id"])
        req = c["requires"]
        if not isinstance(req, dict) or "kind" not in req or "value" not in req:
            raise RegistryError("%s 'requires' needs 'kind' and 'value'" % where)
        if req["kind"] not in KNOWN_KINDS:
            # Fail closed. An unknown kind must never silently evaluate to true.
            raise RegistryError(
                "%s has unknown predicate kind %r. Known: %s. Add the predicate "
                "before adding the claim -- an unevaluable claim that passes is "
                "worse than no claim." % (where, req["kind"], ", ".join(KNOWN_KINDS))
            )
        try:
            re.compile(c["claim_pattern"], re.IGNORECASE)
        except re.error as exc:
            raise RegistryError("%s claim_pattern is not a valid regex: %s" % (where, exc))
    return claims


# -------------------------------------------------------------- predicates ---

def _html_files(root):
    return list((root / "public").rglob("*.html"))


def page_loads_script(root, value):
    """Does any page under public/ reference this script path?"""
    hits = []
    for f in _html_files(root):
        try:
            if value in f.read_text(encoding="utf-8", errors="replace"):
                hits.append(f.relative_to(root).as_posix())
                if len(hits) >= 3:
                    break
        except OSError:
            continue
    return (bool(hits), hits)


def workflow_schedules(root, value):
    """Is this script invoked by a workflow that ALSO carries a cron?

    Both halves matter. A script wired only to `workflow_dispatch` runs when a
    human remembers, which is exactly the property a retention promise cannot
    rely on.
    """
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return (False, [])
    hits = []
    for f in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if value in text and CRON_RE.search(text):
            hits.append(f.relative_to(root).as_posix())
    return (bool(hits), hits)


def path_exists(root, value):
    p = root / value
    return (p.exists(), [value] if p.exists() else [])


PREDICATES = {
    "page_loads_script": page_loads_script,
    "workflow_schedules": workflow_schedules,
    "path_exists": path_exists,
}


# ------------------------------------------------------------------- check ---

def check(root, registry_path):
    claims = load_registry(registry_path)

    findings = []
    evaluated = 0
    dormant = 0

    for c in claims:
        claim_file = root / c["claim_file"]
        if not claim_file.is_file():
            # Fail closed: a claim whose page vanished is an unevaluable claim,
            # not a satisfied one. A renamed page would otherwise drop out of
            # coverage silently -- the trap test-platform-claims.py already pins.
            findings.append((c, "claim_file does not exist: %s" % c["claim_file"], []))
            continue

        prose = claim_file.read_text(encoding="utf-8", errors="replace")
        if not re.search(c["claim_pattern"], prose, re.IGNORECASE):
            # The prose does not make this claim, so the mechanism is not owed.
            # Counted and printed -- never silent. Green carries a number.
            dormant += 1
            continue

        evaluated += 1
        kind = c["requires"]["kind"]
        ok, evidence = PREDICATES[kind](root, c["requires"]["value"])
        if not ok:
            findings.append((c, None, []))
        else:
            print("  OK    %-42s <- %s" % (c["id"], ", ".join(evidence[:2])))

    print("")
    if dormant:
        print("%d claim(s) dormant: the prose does not currently make them, so no "
              "mechanism is owed." % dormant)

    if not evaluated and not findings:
        # Never exit 0 having checked nothing. check-platform-claims.py shipped a
        # cheap early-exit that was reached on every real run, and its green said
        # nothing whatsoever about the pages.
        print("")
        print("ERROR: no claim in the registry was live, so this run proved nothing.")
        print("Either the prose stopped making every claim at once (suspicious), or")
        print("the patterns have drifted from the copy. Investigate before trusting")
        print("a green here.")
        return 2

    if findings:
        print("=" * 78)
        print("REFUSING: %d reader-facing claim(s) describe a mechanism that does "
              "not run." % len(findings))
        print("=" * 78)
        for c, err, _ev in findings:
            print("")
            print("  %s" % c["id"])
            print("    page      %s" % c["claim_file"])
            print("    claims    /%s/ is present in the prose" % c["claim_pattern"])
            if err:
                print("    PROBLEM   %s" % err)
            else:
                print("    requires  %s: %s" % (c["requires"]["kind"], c["requires"]["value"]))
                print("    but       that condition is NOT met right now")
            print("    why       %s" % c["why"])
        print("")
        print("Two ways to close this, and only two:")
        print("  1. Make the mechanism real -- mount the script, add the cron.")
        print("  2. Take the sentence out of the prose until it is.")
        print("")
        print("Do NOT close it by loosening the pattern. The visitor reads the")
        print("sentence, not the regex.")
        return 1

    print("OK: %d live claim(s), every one backed by a mechanism that runs." % evaluated)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--root", default=str(REPO))
    args = ap.parse_args(argv)
    try:
        return check(Path(args.root), Path(args.registry))
    except RegistryError as exc:
        print("REGISTRY REJECTED: %s" % exc, file=sys.stderr)
        print("", file=sys.stderr)
        print("The whole registry is rejected rather than skipping the bad entry: a", file=sys.stderr)
        print("skipped claim resurfaces later as a fresh finding and sends someone", file=sys.stderr)
        print("hunting a bug nobody introduced.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
