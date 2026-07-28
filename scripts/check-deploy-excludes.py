#!/usr/bin/env python
"""Guard the deploy's rsync --exclude list against Chesterton's fence.

WHY THIS EXISTS
---------------
The production deploy is `rsync -avz --delete` from `public/`, so every byte in
`public/` is shipped to DreamHost shared hosting on every push. Source material
that lives in the repo for good reasons (unprocessed cat originals, the image
processing pipeline, full-resolution screenshot masters) has no business being
served, so `.github/workflows/auto-deploy-on-push.yml` carries `--exclude`
patterns for it.

That creates a silent failure mode: an exclude is a *deploy-time* decision, but
a `<img src=...>` is written at *authoring* time, and nothing connects the two.
Add one exclude too many -- or add a page that links an already-excluded file --
and the asset 404s in production while working perfectly in every local preview
and every Netlify PR preview (Netlify serves `public/` whole, without these
excludes). This repo has already had one near-miss of the same shape: 1,000
"orphaned" event pages that turned out to be the only published surface for a
live dataset (docs/TECH_DEBT.md E-0).

So: expand `deploy-excludes.txt` against the real tree, and fail if anything a
browser loads still points at an excluded file.

There is a second failure mode with the same shape. FOUR workflows rsync
`public/` to production. Only `auto-deploy-on-push.yml` ever carried excludes,
so a `workflow_dispatch` of any of the other three would silently re-upload
every byte the first one had just stopped shipping -- and would look like a
successful deploy. This script therefore also asserts that every workflow which
rsyncs `public/` to `$DH_PATH` passes `--exclude-from=deploy-excludes.txt`.

Scope note: only `.html`, `.css` and `.js` under `public/` are scanned, because
those are what a browser actually fetches. Markdown READMEs inside
`public/assets/` legitimately cross-reference the source directories they
document -- that is prose about the pipeline, not a request the browser makes.

Run:  python scripts/check-deploy-excludes.py [-v]
Exit 1 if a deployed page references an excluded file, or if a production
deploy workflow does not use the shared exclude list.
"""
import fnmatch
import os
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = REPO_ROOT / "public"
EXCLUDE_FILE = REPO_ROOT / "deploy-excludes.txt"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

SCAN_SUFFIXES = {".html", ".css", ".js"}

# Extensions worth resolving. Deliberately excludes .md: see the scope note.
ASSET_EXT = r"png|jpe?g|gif|webp|svg|ico|css|js|json|mp4|webm|woff2?|ttf|zip|pdf"
# Path-ish token ending in one of those extensions. Spaces are allowed because
# some assets here genuinely have spaces in the filename ("pdoom1 logo google.png").
TOKEN_RE = re.compile(r"[A-Za-z0-9 _./\\-]*\.(?:" + ASSET_EXT + r")\b", re.IGNORECASE)

# An rsync of public/ at a DreamHost path == a production deploy. The command
# is written across backslash-continued lines in some workflows and on one line
# in others, so follow continuations explicitly -- a regex that only tolerated a
# single extra line silently skipped auto-deploy-on-push.yml, the one workflow
# that matters most.
DEPLOY_RSYNC_RE = re.compile(
    r"rsync(?:[^\n]*\\\n)*[^\n]*?public/\s+\"?\$\{DH_USER\}"
)


def read_excludes():
    if not EXCLUDE_FILE.exists():
        print(f"ERROR: {EXCLUDE_FILE} not found")
        sys.exit(1)
    raw = EXCLUDE_FILE.read_bytes()
    # rsync does not strip a trailing CR from a filter file, so a CRLF checkout
    # turns every pattern into "assets/dump\r" -- matching nothing, and shipping
    # all the source material again while the deploy reports success. This is
    # invisible on Windows, where the whole repo is CRLF locally. .gitattributes
    # pins eol=lf; this catches the case where that pin is lost.
    if b"\r\n" in raw:
        print(f"ERROR: {EXCLUDE_FILE.name} has CRLF line endings.")
        print("rsync --exclude-from would keep the CR and match nothing.")
        print("Check .gitattributes still pins 'deploy-excludes.txt text eol=lf'.")
        sys.exit(1)

    pats = []
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        # rsync filter-file syntax: '#' and ';' start a comment, blanks ignored.
        if not line or line[0] in "#;":
            continue
        pats.append(line)
    if not pats:
        print(f"ERROR: no patterns in {EXCLUDE_FILE}")
        sys.exit(1)
    return pats


def check_workflows():
    """Every workflow that rsyncs public/ to production must use the shared list."""
    problems = []
    checked = []
    for wf in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        text = wf.read_text(encoding="utf-8")
        for match in DEPLOY_RSYNC_RE.finditer(text):
            checked.append(wf.name)
            if "--exclude-from=deploy-excludes.txt" not in match.group(0):
                problems.append((wf.name, " ".join(match.group(0).split())))
    return checked, problems


def matches(relpath, pattern):
    """Approximate rsync's exclude semantics closely enough for this guard.

    rsync: a pattern with no slash matches any path component; a pattern with a
    slash matches against the path (anchored at the transfer root when it starts
    with one); matching a directory excludes everything beneath it.
    """
    p = pattern.rstrip("/")
    if p.startswith("/"):
        p = p[1:]
    if "/" in p:
        return (
            relpath == p
            or relpath.startswith(p + "/")
            or fnmatch.fnmatch(relpath, p)
            or fnmatch.fnmatch(relpath, p + "/*")
        )
    return any(fnmatch.fnmatch(part, p) for part in relpath.split("/"))


def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    patterns = read_excludes()
    failed = False

    checked, problems = check_workflows()
    print(f"production deploy workflows using deploy-excludes.txt: "
          f"{len(checked) - len(problems)}/{len(checked)}")
    for name in sorted(set(checked)):
        print(f"  {name}")
    if problems:
        failed = True
        print("")
        print("FAIL: a workflow rsyncs public/ to production without the shared")
        print("exclude list, so running it would re-upload the source material.")
        for name, line in problems:
            print(f"  {name}: {line}")
    if not checked:
        failed = True
        print("FAIL: found no production rsync at all -- has the deploy moved?")
    print("")

    all_files = []
    for path in PUBLIC.rglob("*"):
        if path.is_file():
            all_files.append(path.relative_to(PUBLIC).as_posix())

    excluded = {}  # relpath -> the pattern that excluded it
    for rel in all_files:
        for pat in patterns:
            if matches(rel, pat):
                excluded[rel] = pat
                break

    by_basename = {}
    for rel in excluded:
        by_basename.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)

    # A bare filename in the markup ("config.json") is ambiguous: the same
    # basename can exist both under an excluded source directory and as a real
    # shipped asset. Only treat a reference as broken when it CANNOT resolve to
    # anything that ships -- otherwise `/config.json` on the homepage reads as a
    # reference to assets/image-processing-systems/dump/*/config.json.
    shipped = set(all_files) - set(excluded)
    shipped_basenames = {r.rsplit("/", 1)[-1] for r in shipped}

    excluded_bytes = sum((PUBLIC / r).stat().st_size for r in excluded)

    print(f"deploy excludes: {len(patterns)} patterns")
    for pat in patterns:
        n = sum(1 for r, p in excluded.items() if p == pat)
        b = sum((PUBLIC / r).stat().st_size for r, p in excluded.items() if p == pat)
        print(f"  {pat:<42} {n:>5} files  {b:>12,} bytes")
    print(f"  {'TOTAL':<42} {len(excluded):>5} files  {excluded_bytes:>12,} bytes")

    scanned = 0
    violations = []
    for rel in all_files:
        if rel in excluded:
            continue
        if os.path.splitext(rel)[1].lower() not in SCAN_SUFFIXES:
            continue
        scanned += 1
        try:
            text = (PUBLIC / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"WARN: could not read {rel}: {exc}")
            continue
        for match in TOKEN_RE.finditer(text):
            token = match.group(0).replace("\\", "/").lstrip("./").strip()
            if not token:
                continue
            hits = []
            if "/" in token:
                if any(s == token or s.endswith("/" + token) for s in shipped):
                    continue
                for ex in excluded:
                    if ex == token or ex.endswith("/" + token):
                        hits.append(ex)
            else:
                if token in shipped_basenames:
                    continue
                hits = by_basename.get(token, [])
            for hit in hits:
                violations.append((rel, token, hit, excluded[hit]))

    print(f"scanned {scanned} deployed html/css/js files")

    if violations:
        failed = True
        print("")
        print("FAIL: deployed pages reference files the deploy excludes.")
        print("Either drop the exclude, or point the page at a shipped asset.")
        seen = set()
        for src, token, hit, pat in violations:
            key = (src, hit)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {src}")
            print(f"    references '{token}' -> public/{hit}  (excluded by {pat})")

    if verbose:
        print("")
        for rel in sorted(excluded):
            print(f"  excluded: {rel}")

    if failed:
        return 1
    print("PASS: exclude list is shared by every production deploy, and no")
    print("      deployed page references an excluded file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
