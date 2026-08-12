#!/usr/bin/env python
"""Guard: does this PR actually qualify for the self-merge class it claims?

    python scripts/check-self-merge-eligibility.py --self-test
    python scripts/check-self-merge-eligibility.py --base origin/main

WHY THIS EXISTS
---------------

Ruling ``RULED_2026-08-10_pr-self-merge-and-four-more.md`` R1 lets a seat merge
two PR classes without Pip:

  * **Guard** -- adds or repairs a check, gate, alarm or CI condition. YES, on green.
  * **Docs** -- corrects documentation to match measured reality. YES, on green.
  * Anything touching a **public claim**, an **entity boundary**, a **rule**, or
    anything **irreversible** -- NO, still Pip.

The labels ``class:guard`` and ``class:docs`` were created in three repos on
2026-08-10 and, until this file existed, they **promised eligibility and checked
nothing**. That is the same defect that retired ``ship:hotpatch-48h`` on the same
day: a label asserting a property no mechanism enforces is a claim, not a
control. This is the mechanism. R1's first condition is the one it mechanises:

    Estate rule Section 5g still applies to the guard class. "A guard PR merged
    without a RED run observed and its run ID recorded is not an installed
    guard, it is an untested one."

WHAT IT ENFORCES
----------------

  1. ``needs:pip`` present alongside a class label -> FAIL. The label means
     blocked on Pip and nobody else; a class label cannot lift a hold.
  2. Both class labels -> FAIL. A PR is one class or neither.
  3. Neither class label -> PASS, neutral. **This check never blocks a normal
     PR.** It has an opinion only about PRs claiming an exemption. That includes
     ``needs:pip`` on its own: a hold nobody is trying to skip is not this
     gate's business, and a check that reddens every held PR is one everyone
     learns to ignore. ``BLOCKED_FAILS_ALONE`` flips that if it is overruled.
  4. ``class:docs`` -> PASS only if EVERY changed path is documentation.
  5. ``class:guard`` -> PASS only if the PR body carries a RED-run declaration.

THE ``RED-RUN`` TOKEN
---------------------

::

    RED-RUN: <run-url-or-run-id> -- <one line: what was broken to make it fail>

Adopted from ``pdoom1``'s ``tools/check_ladder_bump.py`` ``Ladder-Impact:`` line,
which solved the same problem: a required human declaration, preserved by git,
parsed by a regex, with a mandatory substantive reason so the magic words alone
are not enough. It verifies that a run reference and a reason were **stated**,
not that the run exists or was red. Same trust boundary: it converts a silent
omission into an attributable statement. The reviewer clicks the link.

WHAT COUNTS AS DOCUMENTATION HERE (and why this repo is not pdoom1)
-------------------------------------------------------------------

On a website repo the obvious rule is wrong. ``public/blog/*.md`` are published
posts and every file under ``public/`` is served to visitors, so editing one is
changing a **public claim** -- which R1 explicitly keeps with Pip, and which
this repo's prime directive ("never lie to a visitor") makes the highest-stakes
edit available. So:

  documentation = a path under ``docs/`` or ``content/``, or a file ending
  ``.md`` / ``.rst`` / ``.txt``, EXCLUDING everything under ``public/`` (served
  to visitors), ``docs/copy-baseline/`` (the frozen prose snapshot that
  ``scripts/snapshot-copy.py --check`` diffs against -- editing the baseline is
  how you make a copy-drift check agree with drifted copy), and the machine-read
  files in ``NOT_DOCUMENTATION`` (``deploy-excludes.txt`` decides what does not
  ship; ``requirements.txt`` / ``runtime.txt`` are pins).

Inputs arrive by environment variable, never inlined into a shell command, since
both are author-controlled:

  * ``PR_LABELS`` -- JSON array or comma/newline separated label names
  * ``PR_BODY``   -- the pull request body text

Exit 1 on any finding, 0 otherwise. Stdlib only, no network, no GitHub API.
"""

import argparse
import json
import os
import re
import subprocess
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

GUARD_LABEL = "class:guard"
DOCS_LABEL = "class:docs"
BLOCKED_LABEL = "needs:pip"

# Does needs:pip fail a PR that claims no self-merge class? No, by the argument
# in rule 3 above. One constant, so overruling it is one edit.
BLOCKED_FAILS_ALONE = False

# ---------------------------------------------------------------------------
# What counts as documentation
# ---------------------------------------------------------------------------

DOC_SUFFIXES = (".md", ".rst", ".txt")
DOC_PREFIXES = ("docs/", "content/")

# Prose that is NOT internal documentation, for reasons specific to this repo.
NOT_DOCUMENTATION_PREFIXES = (
    "public/",  # served to visitors: a public claim, which R1 keeps with Pip
    "docs/copy-baseline/",  # the frozen snapshot the copy-drift check compares to
)

# Machine-read files that merely happen to end in a doc suffix.
NOT_DOCUMENTATION = (
    "deploy-excludes.txt",  # decides what never ships; four workflows read it
    "requirements.txt",  # dependency pin
    "runtime.txt",  # Python runtime pin
)

# ---------------------------------------------------------------------------
# The RED-RUN declaration
# ---------------------------------------------------------------------------

RED_RUN_FORMAT = "RED-RUN: <run-url-or-run-id> -- <what was broken to make it fail>"

# A reference is either a URL or a bare numeric run id. GitHub run ids are long
# integers; requiring >= 6 digits rejects "RED-RUN: 1 -- trust me" without
# pretending to validate the id.
RED_RUN_RE = re.compile(
    r"^[^\S\n]*RED-RUN:[^\S\n]*(?P<ref>https?://\S+|[0-9]{6,})"
    r"[^\S\n]*(?:--|:)?[^\S\n]*(?P<reason>.*?)[^\S\n]*$",
    re.IGNORECASE | re.MULTILINE,
)

# A verdict with a token reason records that someone typed the magic words, not
# what they did. Same threshold and same argument as Ladder-Impact.
RED_RUN_MIN_REASON_CHARS = 8


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


def parse_labels(raw):
    """Label names from a JSON array, or a comma/newline separated list.

    Actions can hand us either shape depending on how the workflow interpolates
    the labels; accept both rather than silently seeing zero labels, which would
    pass everything.
    """
    text = (raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            loaded = []
        names = []
        for item in loaded:
            if isinstance(item, dict):
                item = item.get("name", "")
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
        return names
    return [part.strip() for part in re.split(r"[,\n]", text) if part.strip()]


def is_documentation(path):
    """True when the path alone proves the change is internal prose."""
    p = (path or "").replace("\\", "/").strip()
    if not p:
        return False
    if p in NOT_DOCUMENTATION:
        return False
    if p.startswith(NOT_DOCUMENTATION_PREFIXES):
        return False
    if p.startswith(DOC_PREFIXES):
        return True
    return p.endswith(DOC_SUFFIXES)


def find_red_run(text):
    """The RED-RUN declaration in `text`, or None if it carries no usable one."""
    for m in RED_RUN_RE.finditer(text or ""):
        if len(m.group("reason").strip()) >= RED_RUN_MIN_REASON_CHARS:
            return m.group(0).strip()
    return None


# ---------------------------------------------------------------------------
# git plumbing (only used when the caller does not supply the paths)
# ---------------------------------------------------------------------------


def _git(args, check=True):
    return subprocess.run(
        ["git"] + args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        # Explicit, per scripts/check-encoding-safety.py R3: text mode without
        # this decodes git's output with the locale codec, which on Pip's
        # machine is cp1252. A path with a non-ASCII byte would then crash the
        # gate rather than judge the PR.
        encoding="utf-8",
        errors="replace",
        check=check,
    ).stdout


def changed_paths(base, head="HEAD"):
    try:
        _git(["merge-base", base, head])
        spec = ["%s...%s" % (base, head)]
    except subprocess.CalledProcessError:
        # Shallow checkouts often lack the merge base. Two-endpoint diff
        # overcounts but is never silent.
        spec = [base, head]
    out = _git(["diff", "--name-only"] + spec)
    if head == "HEAD":
        out += _git(["diff", "--name-only", "HEAD"])
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------


def _bullets(paths, limit=20):
    shown = "".join("    - %s\n" % p for p in paths[:limit])
    if len(paths) > limit:
        shown += "    ... and %d more\n" % (len(paths) - limit)
    return shown


def run(labels, paths, body):
    """Return a list of findings (empty == this PR may claim what it claims)."""
    names = {label.strip().lower() for label in labels}
    guard = GUARD_LABEL in names
    docs = DOCS_LABEL in names
    findings = []

    # Rule 1 -- needs:pip beats every class label.
    if BLOCKED_LABEL in names and (guard or docs or BLOCKED_FAILS_ALONE):
        claimed = [lb for lb in (GUARD_LABEL, DOCS_LABEL) if lb in names]
        findings.append(
            "%s is present, so this PR is blocked on Pip and nobody else.\n"
            "  A self-merge class does not override it (R1 names two classes a seat\n"
            "  MAY merge, not a way to clear a hold).\n"
            "  Claimed class label(s): %s\n"
            "  Fix: remove %s once Pip has answered, or drop the class label."
            % (BLOCKED_LABEL, ", ".join(claimed) or "none", BLOCKED_LABEL)
        )

    # Rule 2 -- one class or neither.
    if guard and docs:
        findings.append(
            "both %s and %s are present. A PR is one class or neither. The two\n"
            "  classes carry different evidence requirements (a guard owes a RED run;\n"
            "  docs owes a docs-only diff), so a PR claiming both has not said which\n"
            "  standard it is asking to be held to.\n"
            "  Fix: remove one label, or split the PR." % (GUARD_LABEL, DOCS_LABEL)
        )

    # Rule 3 -- neither class label: this check has no opinion.
    if not guard and not docs:
        if not findings:
            print(
                "[self-merge-eligibility] NEUTRAL: no self-merge class label (%s / %s)\n"
                "  on this PR -- nothing claimed, nothing to check. Normal review applies\n"
                "  and this check does not block." % (GUARD_LABEL, DOCS_LABEL)
            )
            if BLOCKED_LABEL in names:
                print(
                    "  (%s is present. That is a hold for a human to lift, not a claim\n"
                    "   for this gate to refuse -- it only fails when a class label tries\n"
                    "   to skip it.)" % BLOCKED_LABEL
                )
        return findings

    # Rule 4 -- docs class: every changed path must be documentation.
    if docs and not guard:
        offenders = [p for p in paths if not is_documentation(p)]
        if not paths:
            findings.append(
                "%s is claimed but the diff contains no changed paths.\n"
                "  An empty docs PR corrects no documentation. If the paths could not be\n"
                "  computed (shallow clone, missing base ref), fix the checkout rather\n"
                "  than passing this check on no evidence." % DOCS_LABEL
            )
        elif offenders:
            findings.append(
                "%s is claimed, but this PR changes files that are not internal\n"
                "  documentation. The docs class is 'corrects documentation to match\n"
                "  measured reality' (R1) -- it is not a shortcut for a mixed PR, and on\n"
                "  this repo anything under public/ is served to visitors, which makes it\n"
                "  a PUBLIC CLAIM and still Pip's.\n"
                "  Documentation here means: a path under docs/ or content/, or a file\n"
                "  ending %s -- excluding public/, docs/copy-baseline/ (the frozen prose\n"
                "  snapshot the copy-drift check diffs against), and machine-read files\n"
                "  such as deploy-excludes.txt, requirements.txt and runtime.txt.\n"
                "  Not documentation:\n%s"
                "  Fix: split the non-doc changes into their own PR, or drop %s."
                % (DOCS_LABEL, ", ".join(DOC_SUFFIXES), _bullets(sorted(offenders)), DOCS_LABEL)
            )
        else:
            print(
                "[self-merge-eligibility] %s: all %d changed path(s) are documentation."
                % (DOCS_LABEL, len(paths))
            )

    # Rule 5 -- guard class: Section 5g wants a RED run on the record.
    if guard and not docs:
        declared = find_red_run(body)
        if declared is None:
            findings.append(
                "%s is claimed, but the PR body carries no RED-RUN declaration.\n"
                "  Estate rule Section 5g: a guard merged without a RED run observed and\n"
                "  its run ID recorded is not an installed guard, it is an untested one.\n"
                "  Make the new check fail on purpose, then record the run that failed.\n"
                "  Add one line to the PR body, exactly this shape:\n"
                "      %s\n"
                "  Examples:\n"
                "      RED-RUN: https://github.com/OWNER/REPO/actions/runs/1234567890"
                " -- ran with the assertion inverted\n"
                "      RED-RUN: 1234567890 -- guard label with no declaration in the body\n"
                "  The reason is mandatory and must be at least %d characters: a bare run\n"
                "  id records that a job went red, not that THIS guard made it go red."
                % (GUARD_LABEL, RED_RUN_FORMAT, RED_RUN_MIN_REASON_CHARS)
            )
        else:
            print("[self-merge-eligibility] %s declared: %s" % (GUARD_LABEL, declared))

    if not findings:
        claimed = GUARD_LABEL if guard else DOCS_LABEL
        print(
            "[self-merge-eligibility] OK: %s is supported by the evidence in this PR.\n"
            "  Eligible for self-merge on green (R1). Say what you merged where Pip will\n"
            "  see it." % claimed
        )
    return findings


# ---------------------------------------------------------------------------
# Self-test: prove the rules without GitHub, on every CI run
# ---------------------------------------------------------------------------

_RED_URL = "https://github.com/PipFoweraker/pdoom1-website/actions/runs/1234567890"

# (name, labels, paths, body, expected exit, why)
SELF_TEST_CASES = (
    (
        "no class label at all",
        [],
        ["public/index.html"],
        "",
        0,
        "MUST PASS: a normal PR is never blocked by this check",
    ),
    (
        "unrelated labels only",
        ["bug", "ship:now"],
        ["public/index.html"],
        "",
        0,
        "MUST PASS: only the two class labels mean anything here",
    ),
    (
        "needs:pip alone, no class label",
        ["needs:pip"],
        ["public/index.html"],
        "",
        0,
        "MUST PASS: a hold nobody is trying to skip is not this gate's business",
    ),
    (
        "docs class, internal prose only",
        ["class:docs"],
        ["docs/TECH_DEBT.md", "CLAUDE.md", "content/INSIGHTS.md"],
        "",
        0,
        "MUST PASS: every path is internal documentation",
    ),
    (
        "docs class touching a served page",
        ["class:docs"],
        ["docs/TECH_DEBT.md", "public/about/index.html"],
        "",
        1,
        "MUST FAIL: a served page is a public claim, and R1 keeps those with Pip",
    ),
    (
        "docs class touching a published blog post",
        ["class:docs"],
        ["public/blog/2025-09-10-version-0-2-12-release.md"],
        "",
        1,
        "MUST FAIL: .md suffix, but it is published prose, not internal docs",
    ),
    (
        "docs class editing the frozen copy baseline",
        ["class:docs"],
        ["docs/copy-baseline/about/index.html.txt"],
        "",
        1,
        "MUST FAIL: that is how a copy-drift check is made to agree with drifted copy",
    ),
    (
        "docs class touching deploy-excludes.txt",
        ["class:docs"],
        ["deploy-excludes.txt"],
        "",
        1,
        "MUST FAIL: .txt suffix, but it decides what never ships",
    ),
    (
        "guard class with a recorded RED run",
        ["class:guard"],
        [".github/workflows/self-merge-eligibility.yml"],
        "Adds the gate.\n\nRED-RUN: %s -- label present, no declaration in body\n" % _RED_URL,
        0,
        "MUST PASS: Section 5g satisfied, run id on the record",
    ),
    (
        "guard class with no declaration",
        ["class:guard"],
        [".github/workflows/self-merge-eligibility.yml"],
        "Adds the gate. Trust me, it works.\n",
        1,
        "MUST FAIL: an unproven guard is an untested one (Section 5g)",
    ),
    (
        "guard class, run id but no reason",
        ["class:guard"],
        [".github/workflows/self-merge-eligibility.yml"],
        "RED-RUN: 1234567890\n",
        1,
        "MUST FAIL: a bare id says a job went red, not that this guard did it",
    ),
    (
        "needs:pip beats the guard class",
        ["class:guard", "needs:pip"],
        [".github/workflows/self-merge-eligibility.yml"],
        "RED-RUN: %s -- deliberately inverted assertion\n" % _RED_URL,
        1,
        "MUST FAIL: blocked on Pip, and a class label cannot clear a hold",
    ),
    (
        "needs:pip beats the docs class",
        ["class:docs", "needs:pip"],
        ["docs/TECH_DEBT.md"],
        "",
        1,
        "MUST FAIL: same rule, other class",
    ),
    (
        "both class labels",
        ["class:guard", "class:docs"],
        ["docs/TECH_DEBT.md"],
        "RED-RUN: %s -- deliberately inverted assertion\n" % _RED_URL,
        1,
        "MUST FAIL: a PR is one class or neither",
    ),
)


def self_test():
    ran = failed = 0
    for name, labels, paths, body, expected, why in SELF_TEST_CASES:
        print("\n[self-test] CASE  %s\n            %s" % (name, why))
        findings = run(labels, paths, body)
        for f in findings:
            print("[self-merge-eligibility] FAIL: %s" % f)
        actual = 1 if findings else 0
        ran += 1
        if actual != expected:
            failed += 1
        print(
            "[self-test] %s: expected exit %d, got %d"
            % ("OK" if actual == expected else "MISMATCH", expected, actual)
        )

    print("\n[self-test] %d case(s) ran, %d mismatch(es)." % (ran, failed))
    if failed:
        print("[self-test] FAIL: the gate does not reproduce its own rules.")
        return 1
    print(
        "[self-test] PASS: neutral on unlabelled PRs, red on every unsupported claim, "
        "green on the two supported ones."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description="Self-merge class eligibility gate (R1).")
    parser.add_argument("--base", default="origin/main", help="base ref (default: origin/main)")
    parser.add_argument("--head", default="HEAD", help="head ref (default: HEAD)")
    parser.add_argument(
        "--paths-file", help="file with one changed path per line (default: git diff)"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="replay the rule table hermetically and verify red/green (no GitHub needed)",
    )
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    labels = parse_labels(os.environ.get("PR_LABELS", ""))
    body = os.environ.get("PR_BODY", "")
    if args.paths_file:
        text = Path(args.paths_file).read_text(encoding="utf-8")
        paths = [ln.strip() for ln in text.splitlines() if ln.strip()]
    else:
        paths = changed_paths(args.base, args.head)

    print("[self-merge-eligibility] labels: %s" % (", ".join(labels) if labels else "(none)"))
    print("[self-merge-eligibility] changed paths: %d" % len(paths))

    findings = run(labels, paths, body)
    for f in findings:
        print("[self-merge-eligibility] FAIL: %s" % f)
    if not findings:
        return 0
    print(
        "[self-merge-eligibility] Ruling: RULED_2026-08-10_pr-self-merge-and-four-more.md R1. "
        "A label that checks nothing is a claim, not a control."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
