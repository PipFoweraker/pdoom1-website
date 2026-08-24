#!/usr/bin/env python
"""Derive data/art-register.json -- one record per image under public/.

WHY THIS EXISTS
---------------
This repo *uplifts* art from pdoom1: a copy is committed here, and from that
moment the copy has no link back to the decision that produced it. #283 is the
worked example. Nine 128px icons -- three slots x three generated variants --
were live on pdoom1.com and referenced by no page, so six pieces of REJECTED
machine-generated art were publicly fetchable and indistinguishable from the
three chosen ones. The fix deleted six files and wrote
`public/assets/icons/events/PROVENANCE.json` by hand.

A hand-written provenance file is a mirror, and a mirror rots. PROVENANCE.json
took its `selected_variant` from pdoom1's `art_prompts/batch_2_actions_and_ui.yaml`
on 2026-08-07. On 2026-08-14 a human reviewed the same corpus and recorded a
verdict per variant in `tools/art_review/review_state.json`. Those two sources
can disagree, and as of this writing they DO -- see the register's own
`findings` and `scripts/check-art-staleness.py`. Nothing in this repo would
ever have asked.

So: derive the register, never type it.

WHAT IS DERIVED vs ASSERTED
---------------------------
Every field carries a `verify` tier copied from `content/campaigns/README.md`
section 2.1 -- `checked`, `delegated`, `online`, `human`, `durable`. Tiers are
declared once, at the top of the register, in `field_verification`; a record
that deviates says so in its own `claims` map. A `human` claim costs a dated
`human_verified` stamp that EXPIRES, exactly as a campaign fact-guard does.

`origin` is `unknown` unless something in THIS repo says otherwise, and unknown
is a first-class value: today it is the commonest one. "Probably a screenshot"
is a guess, and a guess written into a data file becomes a fact to the next
reader.

WHY IT REFUSES
--------------
The upstream corpus lives in pdoom1 (`tools/art_review/`), which no CI runner
here has. Building without it would silently drop every upstream link and
produce a register that is byte-shaped like "no image has any provenance". That
is the difference between "we looked and found nothing" and "we did not look",
and a data file cannot express the difference after the fact. So this script
REFUSES to write unless it can read the corpus, and `--allow-no-upstream` is a
deliberate, recorded downgrade that stamps every upstream block `"unknown"`
rather than `null`.

It also refuses when:
  * an entry in data/art-origins.json names a path that does not exist
    (a stale human assertion is worse than none -- it reads as verified),
  * a human assertion is missing or malforms its `human_verified` clock,
  * a constructed upstream asset id resolves to more than one corpus entry,
  * PROVENANCE.json disagrees with the files actually on disk.

WHERE THE FILE LIVES, AND WHY NOT UNDER public/
-----------------------------------------------
`data/art-register.json`, repo root -- NOT `public/data/`. `public/` is rsynced
to production, so anything placed there is published. The register names another
repo's internal review verdicts on a corpus that is gitignored precisely to keep
it private (`pdoom1/.gitignore:133 art_generated/`), and ART_DRIP gate 3 -- "a
published-asset export with selected/rejected labelled in the file itself" -- is
an unmet decision that belongs to Pip, not to a script. Same reasoning that puts
`data/acknowledgements.json` at the root: this is CI metadata.

Promoting it to `public/data/art-register.json` later is a one-line change to
REGISTER_PATH plus a ruling. Do not make that change without the ruling.

Run:
  python scripts/build-art-register.py                 # needs ../pdoom1
  python scripts/build-art-register.py --game-repo PATH
  python scripts/build-art-register.py --check         # in step? never writes
  python scripts/build-art-register.py --allow-no-upstream
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import datetime as dt
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
PUBLIC = REPO_ROOT / "public"
REGISTER_PATH = REPO_ROOT / "data" / "art-register.json"
ORIGINS_PATH = REPO_ROOT / "data" / "art-origins.json"
EXCLUDES_PATH = REPO_ROOT / "deploy-excludes.txt"

# Derived from PUBLIC at call time, not bound here, so a test can point PUBLIC at
# a fixture tree and have every source follow it. A path frozen at import is a
# test seam that silently reads the real repo.
ICON_PROVENANCE_REL = "assets/icons/events/PROVENANCE.json"

SCHEMA = "pdoom-art-register/v1"

# Extensions a browser renders as a picture. .ico and .svg are included because
# they are art the site serves; excluding them would let a favicon change hands
# with no record.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".ico"}

# What can name an image, for the reference scan. Wider than
# check-deploy-excludes.py's html/css/js on purpose, because the two scripts ask
# DIFFERENT questions. That one asks "does a browser fetch this path", so prose
# in an assets README is correctly ignored. This one asks "is anything using
# this asset", and an unreferenced asset is the #283 shape -- art nobody links
# to, publicly fetchable, indistinguishable from art that was chosen. .md is in
# because public/blog/*.md IS fetched (post.html renders it client-side) and
# eight blog images are referenced from nowhere else; .json is in because
# several pages build an <img> from data rather than markup.
PAGE_SUFFIXES = {".html", ".css", ".js", ".md"}
DATA_SUFFIXES = {".json", ".xml", ".svg"}
REFERENCE_SUFFIXES = PAGE_SUFFIXES | DATA_SUFFIXES

# The split is load-bearing, not tidiness. A sidecar that DESCRIBES an asset is
# not a page that USES it: public/assets/icons/events/PROVENANCE.json names all
# three icons there, and counting that as a reference would have hidden the fact
# that no page in this repo reaches any of them -- which is precisely the #283
# state, six rejected variants publicly fetchable and linked from nowhere. So a
# metadata-only reference is reported as its own weaker class rather than as
# "used".

# Origin vocabulary. The first four are the set named in the brief; `screenshot`
# is added because calling a capture of the game's own rendered UI a
# "photograph" would be false, and folding it into `generated` would imply a
# model produced it. Every value here is a claim someone can check.
ORIGINS = ("generated", "photograph", "human-illustrated", "screenshot", "unknown")

# Verify tiers, copied from content/campaigns/README.md section 2.1. Do NOT
# invent a sixth. `online` has no art use today and is listed so the vocabulary
# does not fork.
VERIFY_TIERS = ("checked", "delegated", "online", "human", "durable")

# How long a mirror of another repo's corpus may go unverified before the
# staleness check calls it stale. Same 90 days as sync-keybinds.py, and for the
# same reason: it is long enough not to nag and short enough that a forgotten
# mirror surfaces inside one quarter.
MIRROR_MAX_AGE_DAYS = 90

UPSTREAM_REL = "tools/art_review"


def short(path):
    """Repo-relative inside the repo, absolute outside it.

    The tests point PUBLIC and REGISTER_PATH at a temp fixture tree, and a bare
    Path.relative_to(REPO_ROOT) raises there -- which would make the test suite
    fail on its own plumbing rather than on the thing under test.
    """
    try:
        return Path(path).relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


class RefuseToWrite(Exception):
    """The register would contain a guess. Callers must NOT catch this."""


# ---------------------------------------------------------------------------
# deploy semantics -- imported, never reimplemented
# ---------------------------------------------------------------------------

# check-deploy-excludes.py is not an importable module name (hyphens), so it is
# loaded by path. ONE implementation of rsync's exclude semantics, not two: a
# second copy is how the two halves of "an exclude is not a delete" drift apart.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_deploy_excludes", REPO_ROOT / "scripts" / "check-deploy-excludes.py")
_dx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dx)

exclude_matches = _dx.matches


def read_exclude_patterns():
    """rsync filter-file patterns, parsed the same way the deploy parses them."""
    text = EXCLUDES_PATH.read_text(encoding="utf-8")
    patterns = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        patterns.append(line)
    if not patterns:
        raise RefuseToWrite(f"{EXCLUDES_PATH} parsed to zero patterns")
    return patterns


def deploy_state(relpath, patterns):
    """(deploys, excluded_by). relpath is relative to public/."""
    for pat in patterns:
        # Patterns rooted at public/ are written that way in the file.
        candidate = "public/" + relpath
        if exclude_matches(relpath, pat) or exclude_matches(candidate, pat):
            return False, pat
    return True, None


# ---------------------------------------------------------------------------
# filesystem
# ---------------------------------------------------------------------------

# SVG is the one image format in IMAGE_SUFFIXES that git treats as TEXT, so its
# line endings are decided by the checkout, not by the file. `core.autocrlf=true`
# on Pip's box yields CRLF in the working tree while the index and every Linux
# runner hold LF (`git ls-files --eol public/favicon.svg` -> `i/lf w/crlf`). A
# straight byte hash therefore disagrees between the author and CI on a file
# nobody touched, and check-art-staleness.py reports S3 "the bytes changed under
# an unchanged filename" -- a FALSE finding, which is the worst kind: it teaches
# the reader that S3 means nothing, and S3 is the guard for a regenerated asset.
# Measured, not theorised: this fired on the first CI run of this branch.
TEXT_IMAGE_SUFFIXES = {".svg"}


def sha256_of(path):
    path = Path(path)
    if path.suffix.lower() in TEXT_IMAGE_SUFFIXES:
        return hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_images():
    out = []
    for path in sorted(PUBLIC.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            out.append(path.relative_to(PUBLIC).as_posix())
    return out


def build_reference_index():
    """basename -> sorted list of repo-relative files that mention it.

    Matched on the basename rather than the full path because pages reference
    the same asset as `/assets/x.png`, `assets/x.png` and `../assets/x.png`.
    That over-matches rather than under-matches, which is the safe direction: a
    false "referenced" hides nothing, a false "orphan" sends someone deleting a
    live asset.
    """
    pages, data = {}, {}
    for path in sorted(PUBLIC.rglob("*")):
        suffix = path.suffix.lower()
        if not path.is_file() or suffix not in REFERENCE_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = short(path)
        bucket = pages if suffix in PAGE_SUFFIXES else data
        for token in set(re.findall(r"[A-Za-z0-9._%+ -]+\.(?:png|jpe?g|webp|gif|svg|avif|ico)",
                                    text, flags=re.IGNORECASE)):
            bucket.setdefault(token.strip().lower(), set()).add(rel)
    return ({k: sorted(v) for k, v in pages.items()},
            {k: sorted(v) for k, v in data.items()})


def git_added_on(relpath):
    """ISO date of the commit that ADDED this file, or None.

    `uplifted_on` is provenance of the COPY, so it is a fact about this repo's
    history and nothing else can supply it.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "--diff-filter=A", "--follow",
             "--format=%ad", "--date=short", "--", "public/" + relpath],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    return lines[-1] if lines else None


# ---------------------------------------------------------------------------
# upstream corpus (pdoom1) -- READ ONLY
# ---------------------------------------------------------------------------

def find_game_repo(explicit, forbid=False):
    """--game-repo, then $PDOOM1_REPO, then a sibling `pdoom1` at any ancestor.

    The ancestor walk exists because this repo is worked in git WORKTREES under
    .claude/worktrees/<id>/, where a plain `../pdoom1` resolves to nothing and a
    seat concludes the corpus is absent when it is three levels up.
    """
    # `forbid` exists for the forced-failure tests and for reproducing what a CI
    # runner sees. Without it a test on a developer box silently finds the real
    # checkout three directories up and asserts the WRONG branch -- the shape of
    # CLAUDE.md's "your agent shell may be lying to you".
    if forbid:
        return None
    candidates = [explicit, os.environ.get("PDOOM1_REPO")]
    for parent in [REPO_ROOT] + list(REPO_ROOT.parents):
        candidates.append(str(parent.parent / "pdoom1"))
    for candidate in candidates:
        if not candidate:
            continue
        p = Path(candidate)
        if (p / UPSTREAM_REL / "review_state.json").exists():
            return p
    return None


def load_corpus(game_repo):
    """(verdicts, quotes_by_asset, commit). Never writes to game_repo."""
    state_path = game_repo / UPSTREAM_REL / "review_state.json"
    quotes_path = game_repo / UPSTREAM_REL / "pullquotes.jsonl"

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise RefuseToWrite(f"{state_path}: review_state.json is not a non-empty object")
    verdicts = {k: v for k, v in raw.items() if k.startswith("gen:")}
    if not verdicts:
        raise RefuseToWrite(
            f"{state_path}: no 'gen:' keys. The corpus shape changed; a build that "
            f"proceeded would record 'no upstream link' for every image, which is "
            f"indistinguishable from having looked.")

    quotes = {}
    if quotes_path.exists():
        for line in quotes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            quotes.setdefault(row.get("asset"), []).append(row)

    commit = None
    try:
        out = subprocess.run(["git", "-C", str(game_repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
        if out.returncode == 0:
            commit = out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    return verdicts, quotes, commit


# ---------------------------------------------------------------------------
# the two in-repo provenance sources
# ---------------------------------------------------------------------------

def load_icon_provenance():
    """public/assets/icons/events/PROVENANCE.json, validated against disk."""
    ICON_PROVENANCE = PUBLIC / ICON_PROVENANCE_REL
    if not ICON_PROVENANCE.exists():
        return {}
    doc = json.loads(ICON_PROVENANCE.read_text(encoding="utf-8"))
    asset_type = doc.get("asset_type")
    if not isinstance(asset_type, str) or not asset_type:
        raise RefuseToWrite(f"{ICON_PROVENANCE}: asset_type missing")
    out = {}
    folder = ICON_PROVENANCE.parent
    for entry in doc.get("icons", []):
        fname = entry.get("file")
        slot = entry.get("slot_id")
        variant = entry.get("selected_variant")
        if not (fname and slot and variant):
            raise RefuseToWrite(
                f"{ICON_PROVENANCE}: an icons[] entry is missing file/slot_id/"
                f"selected_variant; the join to the upstream corpus is built from "
                f"exactly those three and cannot be guessed.")
        if not (folder / fname).exists():
            raise RefuseToWrite(
                f"{ICON_PROVENANCE}: names {fname}, which is not on disk. A "
                f"provenance record for a file that is gone reads as verified "
                f"provenance for whatever replaces it.")
        rel = (folder / fname).relative_to(PUBLIC).as_posix()
        out[rel] = {
            "asset_id": f"gen:{asset_type}:{slot}:{variant}",
            "batch": asset_type,
            "slot_id": slot,
            "selected_variant": variant,
            "machine_generated": bool(entry.get("machine_generated")
                                      or doc.get("machine_generated")),
            "uplifted_from": f"{doc.get('source_repo')}:{doc.get('prompt_file')}",
        }
    return out


def load_origins():
    """data/art-origins.json -- the HUMAN layer, and the only hand-typed input.

    Every entry is an assertion nothing here can derive, so every entry carries
    a clock. Validation is deliberately harsh: the loader refuses the whole file
    rather than skipping a bad entry, for the reason data/acknowledgements.json
    gives -- a skipped entry resurfaces as a fresh finding and sends the next
    person hunting a bug nobody introduced.
    """
    if not ORIGINS_PATH.exists():
        return {}
    doc = json.loads(ORIGINS_PATH.read_text(encoding="utf-8"))
    entries = doc.get("assertions")
    if not isinstance(entries, list):
        raise RefuseToWrite(f"{ORIGINS_PATH}: `assertions` must be a list")
    out = {}
    for i, e in enumerate(entries):
        where = f"{ORIGINS_PATH.name} assertions[{i}]"
        if not isinstance(e, dict):
            raise RefuseToWrite(f"{where}: must be an object")
        path = e.get("path")
        if not isinstance(path, str) or not path.strip():
            raise RefuseToWrite(f"{where}: `path` must be a non-blank string")
        if not (PUBLIC / path).exists():
            raise RefuseToWrite(
                f"{where}: path {path!r} is not on disk. A human assertion about a "
                f"file that no longer exists is a lie waiting for a filename to be "
                f"reused. Delete the entry or fix the path.")
        if path in out:
            raise RefuseToWrite(f"{where}: duplicate assertion for {path!r}")
        origin = e.get("origin")
        if origin not in ORIGINS:
            raise RefuseToWrite(
                f"{where}: origin={origin!r} is not one of {', '.join(ORIGINS)}")
        verify = e.get("verify")
        if verify not in VERIFY_TIERS:
            raise RefuseToWrite(
                f"{where}: verify={verify!r} is not one of {', '.join(VERIFY_TIERS)}")
        if verify == "human":
            hv = e.get("human_verified")
            if not isinstance(hv, dict):
                raise RefuseToWrite(
                    f"{where}: verify=human needs a human_verified object. A "
                    f"verification date with no expiry is the class-5 shape "
                    f"(CLAUDE.md, the acknowledgement clock).")
            for field in ("by", "on", "review_by", "note"):
                v = hv.get(field)
                if not isinstance(v, str) or not v.strip():
                    raise RefuseToWrite(
                        f"{where}: human_verified.{field} must be a non-blank string")
            for field in ("on", "review_by"):
                try:
                    dt.date.fromisoformat(hv[field])
                except ValueError:
                    raise RefuseToWrite(
                        f"{where}: human_verified.{field}={hv[field]!r} is not an "
                        f"ISO date (YYYY-MM-DD)") from None
            if dt.date.fromisoformat(hv["review_by"]) <= dt.date.fromisoformat(hv["on"]):
                raise RefuseToWrite(
                    f"{where}: human_verified.review_by must be after `on`. A "
                    f"zero-length verification makes the clock meaningless.")
            if not isinstance(e.get("why_not_machine"), str) or not e["why_not_machine"].strip():
                raise RefuseToWrite(
                    f"{where}: verify=human needs why_not_machine -- saying WHY no "
                    f"machine here can check it is what stops the tier being an "
                    f"escape hatch.")
        if verify in ("checked", "delegated", "human", "online"):
            if not isinstance(e.get("source"), str) or not e["source"].strip():
                raise RefuseToWrite(f"{where}: verify={verify} needs a `source`")
        if verify == "durable" and (e.get("source") or e.get("check")):
            raise RefuseToWrite(
                f"{where}: verify=durable must carry NO source/check -- it asserts "
                f"nothing about the world, so there is nothing to check it against.")
        out[path] = e
    return out


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

FIELD_VERIFICATION = {
    "path": {
        "verify": "checked",
        "check": "filesystem",
        "source": "public/ walked by scripts/build-art-register.py",
    },
    "bytes": {
        "verify": "checked",
        "check": "filesystem",
        "source": "os.stat of the file in public/",
    },
    "sha256": {
        "verify": "checked",
        "check": "filesystem",
        "source": "sha256 of the file bytes in public/. This is what makes 'the "
                  "asset was regenerated' a detectable event rather than a silent one.",
    },
    "deploys": {
        "verify": "delegated",
        "check": "scripts/check-deploy-excludes.py",
        "source": "deploy-excludes.txt, expanded with that script's own matches() -- "
                  "imported, not reimplemented. NOTE: an exclude is not a delete; "
                  "deploys=false does NOT mean the file is absent from production, "
                  "only that no future deploy uploads it.",
    },
    "excluded_by": {
        "verify": "delegated",
        "check": "scripts/check-deploy-excludes.py",
        "source": "the deploy-excludes.txt pattern that matched, or null",
    },
    "referenced_by_pages": {
        "verify": "checked",
        "check": "reference_scan",
        "source": "basename scan of every .html/.css/.js/.md under public/ -- the "
                  "surfaces a reader reaches. Over-matches on purpose (basename, not "
                  "full path): a false 'referenced' hides nothing, a false 'orphan' "
                  "sends someone deleting a live asset.",
    },
    "referenced_by_data": {
        "verify": "checked",
        "check": "reference_scan",
        "source": "the same scan over .json/.xml/.svg under public/. A sidecar that "
                  "DESCRIBES an asset (PROVENANCE.json) is not a page that USES it, "
                  "so these are counted separately -- folding them together would "
                  "have reported the three event icons as referenced when no page in "
                  "this repo reaches any of them.",
    },
    "origin": {
        "verify": "checked",
        "check": "origin_sources",
        "source": "public/assets/icons/events/PROVENANCE.json (machine_generated), "
                  "then data/art-origins.json (the human layer). Absent both, the "
                  "value is 'unknown' -- which is itself a checked claim about this "
                  "repo: no in-repo source links the file to an origin.",
    },
    "upstream": {
        "verify": "checked",
        "check": "upstream_corpus",
        "source": "pdoom1 tools/art_review/review_state.json + pullquotes.jsonl at "
                  "the commit named in mirror.source_commit. CHECKED AT BUILD TIME "
                  "against a MIRROR: scripts/check-art-staleness.py re-verifies only "
                  "when a pdoom1 checkout is present, and reports UNKNOWN otherwise. "
                  "Freshness is governed by the `mirror` block, not by this tier.",
    },
    "uplifted_on": {
        "verify": "checked",
        "check": "git",
        "source": "git log --diff-filter=A --follow on the file's path in THIS repo. "
                  "Provenance of the copy, which only this repo's history holds.",
    },
    "uplifted_from": {
        "verify": "checked",
        "check": "origin_sources",
        "source": "PROVENANCE.json's source_repo + prompt_file where one exists; "
                  "null where nothing in this repo records where the copy came from.",
    },
}


def build(game_repo, allow_no_upstream, today):
    patterns = read_exclude_patterns()
    page_refs, data_refs = build_reference_index()
    icon_prov = load_icon_provenance()
    origins = load_origins()

    if game_repo is not None:
        verdicts, quotes, commit = load_corpus(game_repo)
        upstream_mode = "read"
    elif allow_no_upstream:
        verdicts, quotes, commit = {}, {}, None
        upstream_mode = "unavailable"
    else:
        raise RefuseToWrite(
            "no pdoom1 checkout found (looked at --game-repo, $PDOOM1_REPO and "
            "../pdoom1). Building without the corpus would write null into every "
            "upstream block, which is byte-identical to 'we looked and this art has "
            "no review record'. Pass --allow-no-upstream to record 'unknown' "
            "explicitly instead, and accept that the register says so out loud.")

    records = []
    unresolved_origin = 0
    unresolved_upstream = 0

    for rel in walk_images():
        full = PUBLIC / rel
        deploys, excluded_by = deploy_state(rel, patterns)
        basename = Path(rel).name.lower()
        self_rel = "public/" + rel
        referenced_by_pages = [r for r in page_refs.get(basename, []) if r != self_rel]
        referenced_by_data = [r for r in data_refs.get(basename, []) if r != self_rel]

        claims = {}
        prov = icon_prov.get(rel)
        assertion = origins.get(rel)

        # --- origin -------------------------------------------------------
        if prov is not None and prov["machine_generated"]:
            origin = "generated"
            origin_source = ("public/assets/icons/events/PROVENANCE.json -> "
                             "machine_generated: true")
        elif assertion is not None:
            origin = assertion["origin"]
            origin_source = assertion["source"] if assertion["verify"] != "durable" else None
            claim = {"verify": assertion["verify"]}
            if origin_source:
                claim["source"] = origin_source
            for k in ("why_not_machine", "why_durable", "human_verified", "check"):
                if assertion.get(k):
                    claim[k] = assertion[k]
            claims["origin"] = claim
        else:
            # No `claims` entry: this record takes the declared default in
            # field_verification (checked / origin_sources), and the checked fact
            # is the ABSENCE -- nothing in this repo links the file to an origin.
            # That is not a claim the art is un-attributable, only that nobody
            # has recorded it here. A per-record copy of that sentence 163 times
            # is noise, and noise in a data file is skipped exactly like noise in
            # a CI log.
            origin = "unknown"
            origin_source = None
            unresolved_origin += 1

        # --- upstream -----------------------------------------------------
        if upstream_mode == "unavailable":
            upstream = "unknown"
            unresolved_upstream += 1
        elif prov is None:
            upstream = None
            unresolved_upstream += 1
        else:
            asset_id = prov["asset_id"]
            matched = [k for k in verdicts if k == asset_id]
            if len(matched) > 1:
                raise RefuseToWrite(
                    f"{rel}: asset id {asset_id} matched {len(matched)} corpus "
                    f"entries. Ambiguity here silently attaches one variant's "
                    f"verdict to another variant's pixels.")
            if not matched:
                raise RefuseToWrite(
                    f"{rel}: PROVENANCE.json implies upstream asset {asset_id}, "
                    f"which is absent from the corpus. Either the naming convention "
                    f"'gen:<asset_type>:<slot_id>:<selected_variant>' no longer "
                    f"holds, or the corpus dropped the asset. Both make every "
                    f"verdict in this register suspect, so nothing is written.")
            row = verdicts[asset_id]
            qs = quotes.get(asset_id, [])
            cleared = None
            for q in qs:
                if q.get("cleared_for"):
                    cleared = q["cleared_for"]
            upstream = {
                "asset_id": asset_id,
                "batch": prov["batch"],
                "slot_id": prov["slot_id"],
                "variant": prov["selected_variant"],
                "verdict": row.get("verdict"),
                "verdict_updated_at": row.get("updated_at"),
                # ids only. The corpus's note/text_verbatim fields are a named
                # reviewer's words; ART_DRIP gate 2 records that consent for
                # publishing them is an OPEN question and attribution is known
                # to be uncertain at variant level. Never copy prose here.
                "artq_ids": sorted(q["id"] for q in qs if q.get("id")),
                "cleared_for": cleared,
                "selected_by_spec": prov["selected_variant"],
            }

        records.append({
            "path": rel,
            "served_url": "/" + rel,
            "bytes": full.stat().st_size,
            "sha256": sha256_of(full),
            "deploys": deploys,
            "excluded_by": excluded_by,
            "referenced_by_pages": referenced_by_pages,
            "referenced_by_data": referenced_by_data,
            "origin": origin,
            "origin_source": origin_source,
            "upstream": upstream,
            "uplifted_from": prov["uplifted_from"] if prov else None,
            "uplifted_on": git_added_on(rel),
            "claims": claims,
        })

    deployed = [r for r in records if r["deploys"]]
    doc = {
        "schema": SCHEMA,
        "_comment": (
            "GENERATED by scripts/build-art-register.py. Do not hand-edit: the next "
            "build overwrites it. The only hand-written input is data/art-origins.json, "
            "which holds human assertions and nothing else. One record per image file "
            "under public/, whether or not it deploys -- recording only the deployed "
            "ones would make a file appear from nowhere the day someone edits "
            "deploy-excludes.txt. Ids and verdicts only: no reviewer's prose is copied "
            "here, ever."),
        "_not_under_public_because": (
            "public/ is rsynced to production. This file names another repo's internal "
            "review verdicts over a corpus that is gitignored to keep it private, and "
            "docs/ART_DRIP_2026-08.md gate 3 -- a published-asset export with "
            "selected/rejected labelled -- is an unmet decision belonging to Pip. Same "
            "reasoning as data/acknowledgements.json."),
        "_claims_rule": (
            "field_verification below declares how EVERY field is known, by default, "
            "for every record. A record carries a `claims` entry only where it "
            "DEVIATES from that default -- which today means exactly one thing: an "
            "origin asserted by a person in data/art-origins.json, at the `human` "
            "tier, with a dated clock. So `claims` is the list of things a machine "
            "did not derive, and it is short on purpose. Absence of a claims entry "
            "means 'derived, per field_verification', never 'unchecked'."),
        "generated_by": "scripts/build-art-register.py",
        "generated_on": today.isoformat(),
        "origin_vocabulary": list(ORIGINS),
        "verify_tiers": list(VERIFY_TIERS),
        "field_verification": FIELD_VERIFICATION,
        "mirror": {
            "is_mirror": True,
            "source_repo": "pdoom1",
            "source_path": UPSTREAM_REL,
            "source_commit": commit,
            "upstream_mode": upstream_mode,
            "verified_on": today.isoformat(),
            "max_age_days": MIRROR_MAX_AGE_DAYS,
            "why_a_mirror": (
                "pdoom1 publishes no art-provenance artifact, so this is a copy taken "
                "at a commit, not a live read. A mirror rots; scripts/check-art-"
                "staleness.py is the thing that notices."),
        },
        "counts": {
            "images_total": len(records),
            "images_deployed": len(deployed),
            "origin_unknown": unresolved_origin,
            "upstream_unresolved": unresolved_upstream,
            "deployed_origin_unknown": sum(1 for r in deployed if r["origin"] == "unknown"),
            "deployed_upstream_resolved": sum(
                1 for r in deployed if isinstance(r["upstream"], dict)),
        },
        "images": records,
    }
    return doc


def write(doc):
    REGISTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTER_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")


def comparable(doc):
    """Everything except the fields that move on every run by construction."""
    clone = json.loads(json.dumps(doc))
    clone.pop("generated_on", None)
    clone.get("mirror", {}).pop("verified_on", None)
    return clone


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-game-repo", action="store_true",
                    help="pretend no pdoom1 checkout exists -- what a CI runner "
                         "actually sees, and what the forced-failure tests need")
    ap.add_argument("--game-repo", help="path to a pdoom1 checkout (read only)")
    ap.add_argument("--allow-no-upstream", action="store_true",
                    help="build with no corpus, stamping every upstream block "
                         "'unknown' rather than null")
    ap.add_argument("--check", action="store_true",
                    help="is the committed register in step? Never writes.")
    ap.add_argument("--register", help="write/read an alternative path (tests)")
    ap.add_argument("--origins", help="alternative human-assertion file (tests)")
    ap.add_argument("--public", help="alternative served-tree root (tests)")
    ap.add_argument("--excludes", help="alternative rsync filter file (tests)")
    ap.add_argument("--as-of", help="build as if today were this ISO date (tests)")
    args = ap.parse_args()

    global REGISTER_PATH, ORIGINS_PATH, PUBLIC, EXCLUDES_PATH
    if args.register:
        REGISTER_PATH = Path(args.register)
    if args.origins:
        ORIGINS_PATH = Path(args.origins)
    if args.public:
        PUBLIC = Path(args.public)
    if args.excludes:
        EXCLUDES_PATH = Path(args.excludes)
    today = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()

    game_repo = find_game_repo(args.game_repo, forbid=args.no_game_repo)
    if args.game_repo and game_repo is None:
        print(f"REFUSED: --game-repo {args.game_repo} has no "
              f"{UPSTREAM_REL}/review_state.json under it.")
        return 2

    try:
        doc = build(game_repo, args.allow_no_upstream, today)
    except RefuseToWrite as exc:
        print("REFUSED TO WRITE -- the register would contain a guess.")
        print(f"  {exc}")
        print("\nNothing was written. A register that guesses is worse than no "
              "register: the guess becomes a fact to whoever reads it next.")
        return 2

    c = doc["counts"]
    if args.check:
        if not REGISTER_PATH.exists():
            print(f"FAIL: {REGISTER_PATH} does not exist. Run without --check.")
            return 1
        current = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        if comparable(current) != comparable(doc):
            print("FAIL: the committed art register is not what this script would "
                  "produce now.")
            print("  Re-run: python scripts/build-art-register.py")
            _diff_summary(current, doc)
            return 1
        print(f"art register in step: {c['images_total']} images, "
              f"{c['images_deployed']} deploy.")
        return 0

    write(doc)
    print(f"wrote {short(REGISTER_PATH)}")
    print(f"  images {c['images_total']} ({c['images_deployed']} deploy)")
    print(f"  origin unknown {c['origin_unknown']} "
          f"({c['deployed_origin_unknown']} of them deployed)")
    print(f"  upstream unresolved {c['upstream_unresolved']} "
          f"({c['deployed_upstream_resolved']} deployed records DID resolve)")
    print(f"  mirror {doc['mirror']['upstream_mode']} @ "
          f"{doc['mirror']['source_commit']}")
    return 0


def _diff_summary(current, fresh):
    cur = {r["path"]: r for r in current.get("images", [])}
    new = {r["path"]: r for r in fresh.get("images", [])}
    for path in sorted(set(new) - set(cur)):
        print(f"  + {path} (in public/, absent from the register)")
    for path in sorted(set(cur) - set(new)):
        print(f"  - {path} (in the register, absent from public/)")
    for path in sorted(set(cur) & set(new)):
        for field in ("sha256", "deploys", "origin", "upstream",
                      "referenced_by_pages", "referenced_by_data"):
            if cur[path].get(field) != new[path].get(field):
                print(f"  ~ {path}: {field} moved")


if __name__ == "__main__":
    sys.exit(main())
