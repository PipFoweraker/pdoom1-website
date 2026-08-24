#!/usr/bin/env python
"""Every credential the syndication code reads must be documented, with its side.

WHY THIS EXISTS
---------------
docs/SYNDICATION_QUICKSTART.md listed the Bluesky, X, LinkedIn and Discord
credentials and never once mentioned SYNDICATION_TOKEN -- the single value whose
absence makes _auth.js refuse every request with a 503. It also described
workflow inputs ("enter path", a "dry run" checkbox) that syndicate-content.yml
does not have. Anyone following it end to end arrived at a 401 with nothing in
the document to explain it.

That is doc rot of the expensive kind: the reader is Pip, setting credentials by
hand, and the failure it produces looks like a code bug rather than a missing
step.

So the required set is DERIVED here from the code that reads it, never typed:

  netlify/functions/*.js   process.env.X   -> must be set in the NETLIFY site env
  scripts/post-syndication.py  os.environ  -> must be set as a GITHUB secret
  .github/workflows/syndicate-content.yml  secrets.X -> must be a GITHUB secret

A new platform handler, or a new env var in an existing one, fails this check on
the day it lands rather than the day someone tries to follow the document.

Exit 0 clean, 1 with findings. Run: python scripts/check-syndication-docs.py
"""

import re
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
FUNCS = REPO_ROOT / "netlify" / "functions"
POSTER = REPO_ROOT / "scripts" / "post-syndication.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "syndicate-content.yml"
DOC = REPO_ROOT / "docs" / "SYNDICATION_QUICKSTART.md"

# Vars the runtime supplies. Reading one is not a thing a human configures, so
# requiring it to be documented would be noise -- and a noisy guard gets ignored.
RUNTIME_PROVIDED = {"NODE_ENV", "CONTEXT", "DEPLOY_URL", "URL", "NETLIFY"}

JS_ENV = re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)")
PY_ENV = re.compile(r"os\.environ(?:\.get)?\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']")
YML_SECRET = re.compile(r"secrets\.([A-Z][A-Z0-9_]*)")


def collect():
    """Return {name: set(of sides)} where a side is 'netlify' or 'github'."""
    need = {}

    def add(name, side, where):
        if name in RUNTIME_PROVIDED:
            return
        need.setdefault(name, {"sides": set(), "seen_in": set()})
        need[name]["sides"].add(side)
        need[name]["seen_in"].add(where)

    if not FUNCS.is_dir():
        print("ERROR: %s is missing -- refusing to report a clean run over an "
              "absent source tree." % FUNCS, file=sys.stderr)
        sys.exit(2)

    # The syndication surface only: the per-platform handlers plus the shared
    # gate they all call. report-bug.js lives in the same directory and reads
    # hCaptcha and GitHub-dispatch credentials that have nothing to do with
    # posting, and are documented in docs/03-integrations/bug-reporting.md.
    # Sweeping the whole directory produced five findings against a document
    # that was never supposed to cover them -- a guard that cries about the
    # wrong subsystem is one people learn to skip.
    js_files = sorted(list(FUNCS.glob("syndicate-*.js")) + [FUNCS / "_auth.js"])
    js_files = [p for p in js_files
                if p.exists() and not p.name.startswith("test-")]
    if not js_files:
        print("ERROR: no syndication function sources found in %s -- refusing "
              "to report a clean run over an empty scan." % FUNCS,
              file=sys.stderr)
        sys.exit(2)

    for path in js_files:
        for name in JS_ENV.findall(path.read_text(encoding="utf-8")):
            add(name, "netlify", "netlify/functions/" + path.name)

    if POSTER.exists():
        for name in PY_ENV.findall(POSTER.read_text(encoding="utf-8")):
            if name == "DRY_RUN":
                continue          # set by the workflow, never by a human
            add(name, "github", "scripts/post-syndication.py")

    if WORKFLOW.exists():
        for name in YML_SECRET.findall(WORKFLOW.read_text(encoding="utf-8")):
            if name == "GITHUB_TOKEN":
                continue          # supplied by Actions
            add(name, "github", ".github/workflows/syndicate-content.yml")

    return need


def main():
    need = collect()

    if not DOC.exists():
        print("FAIL: %s does not exist, but %d credential(s) need documenting."
              % (DOC, len(need)), file=sys.stderr)
        return 1

    doc_lines = DOC.read_text(encoding="utf-8").splitlines()
    findings = []

    # A DECLARATION is a markdown table row naming the variable in backticks.
    # Anchoring on structure rather than on "the words appear near each other"
    # is deliberate: the first version of this check searched the whole document
    # for `NAME ... Netlify` on one line, and scripts/test-check-syndication-docs.py
    # immediately showed that a prose sentence elsewhere on the page
    # ("Treat `BLUESKY_HANDLE`, ... and Netlify's ...") satisfied it, so a row
    # filed on the WRONG side still passed. A guard that a passing mention can
    # satisfy is measuring the wrong thing.
    def declarations(name):
        needle = "`%s`" % name
        return [ln for ln in doc_lines
                if ln.lstrip().startswith("|") and needle in ln]

    for name in sorted(need):
        info = need[name]
        rows = declarations(name)
        if not rows:
            findings.append(
                "%s is read by %s but has no row declaring it in %s"
                % (name, ", ".join(sorted(info["seen_in"])), DOC.name))
            continue
        # Naming it is not enough -- the failure this guard exists for was a
        # value documented on the wrong side of the fence. SYNDICATION_TOKEN
        # needs BOTH, and setting only one yields a green workflow and a 401.
        for side in sorted(info["sides"]):
            word = "netlify" if side == "netlify" else "github"
            if not any(word in row.lower() for row in rows):
                findings.append(
                    "%s is %s, but no row in %s files it under %s"
                    % (name,
                       "read by a Netlify function" if side == "netlify"
                       else "sent by the workflow",
                       DOC.name,
                       "the Netlify site environment" if side == "netlify"
                       else "GitHub secrets"))

    print("Syndication credentials derived from the code: %d" % len(need))
    for name in sorted(need):
        print("  %-24s %s" % (name, "+".join(sorted(need[name]["sides"]))))
    print("")

    if findings:
        print("FAIL: %d finding(s)" % len(findings), file=sys.stderr)
        for f in findings:
            print("  - %s" % f, file=sys.stderr)
        print("\nFix %s, not this script: the required set is derived from the "
              "code and is correct by construction." % DOC.name, file=sys.stderr)
        return 1

    print("OK: every credential the code reads is documented, on the right side.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
