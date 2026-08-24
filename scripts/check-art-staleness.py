#!/usr/bin/env python
"""Art goes stale in ways a leaderboard does not. This is the thing that notices.

THE FOUR WAYS ART ROTS, AND WHY A BOARD-SHAPED CHECK MISSES THEM
----------------------------------------------------------------
A score is wrong or right against a key. A picture is different:

  1. THE VERDICT MOVES UNDER THE PIXELS. The bytes never change; somebody
     reviews the variant again and discards it. Nothing on disk differs, so
     every filesystem check stays green. This is live in this repo right now --
     public/assets/icons/events/PROVENANCE.json records v2 as the selected
     variant of action_funding_grant_proposal, taken from pdoom1's
     art_prompts/batch_2_actions_and_ui.yaml on 2026-08-07; pdoom1's
     tools/art_review/review_state.json records that same variant as `discard`
     on 2026-08-14. Two sources, one week apart, and until this check existed
     nothing in this repo would ever have asked which was newer.
  2. THE BATCH IS SUPERSEDED. A regeneration produces new pixels under an old
     filename. sha256 in the register versus sha256 on disk is what catches it.
  3. THE RULE CHANGES. A whole class becomes wrong at once -- ART_DRIP's A1-A10
     are explicitly "on probation ... reviewed after one full regeneration
     cycle". Nothing here can evaluate an art rule, so this reports the
     REGISTER'S OWN AGE against the corpus it mirrors, and calls a mirror older
     than its max_age_days stale rather than pretending to judge the art.
  4. THE COPY DRIFTS FROM THE SOURCE. The register is a mirror of another repo.
     A mirror rots exactly like public/data/keybinds.json rots, and for the same
     reason: pdoom1 publishes no art-provenance artifact.

UNKNOWN IS A VERDICT, NOT A GAP
-------------------------------
The corpus lives in pdoom1, which no CI runner here has. So the honest states
are three, not two:

    OK      exit 0   everything checkable was checked and nothing diverged
    UNKNOWN exit 0   nothing diverged among the things that COULD be checked,
                     and here is exactly what could not be
    FAIL    exit 1   a divergence, or an acceptance of one that has expired

The word PASS is never printed. Any unknown caps the top line at UNKNOWN --
CLAUDE.md's rule that absence of a marker is never a clean bill of health,
applied to the summary line rather than to a data field. Today the verdict is
UNKNOWN and will stay UNKNOWN while 163 of 173 images have no recorded origin;
that number is in the register, moves only when someone regenerates it, and is
therefore visible in a pull request diff rather than in a check nobody reads.

WHERE THE OBSERVATION COMES FROM
--------------------------------
From inside the system under test: this walks `public/` itself and re-derives
sha256, deployability and references. It does NOT trust the register's roster --
that would be taking the acting party's report that it acted, which is the
inversion CLAUDE.md corrected on 2026-08-22. The register supplies the
EXPECTATION; public/ supplies the observation.

TOLERATED FINDINGS
------------------
Via scripts/acknowledgements.py and data/acknowledgements.json, under the check
name `check-art-staleness`. The acceptance expires; the finding never does. Do
NOT add an allowlist dict to this file -- that is the shape the ledger replaces.

Run:
  python scripts/check-art-staleness.py
  python scripts/check-art-staleness.py --game-repo PATH   # also verifies the mirror
  python scripts/check-art-staleness.py -v
  python scripts/check-art-staleness.py --as-of 2027-01-01 # what expires when
"""

import argparse
import datetime as dt
import hashlib
import importlib.util
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
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from acknowledgements import (  # noqa: E402  (must follow the sys.path line)
    AcknowledgementError,
    load_ledger,
)

ACK_CHECK_NAME = "check-art-staleness"

_spec = importlib.util.spec_from_file_location(
    "build_art_register", REPO_ROOT / "scripts" / "build-art-register.py")
_bar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bar)

# Everything about "what counts as an image", "what deploys" and "how the
# upstream corpus is read" is imported from the generator. Two implementations
# of the same rule is how the two halves of a guard come to disagree, and this
# repo has the receipts (five escapers, two version.json writers).
REGISTER_PATH = _bar.REGISTER_PATH

# A verdict other than these means the site is serving art the reviewer did not
# keep. `remix` and `shelf` are in the corpus vocabulary and neither is a keep:
# remix means "regenerate this", shelf means "not now".
KEEP_VERDICTS = {"keep"}


class Finding:
    """A divergence. Blocking unless an unexpired acceptance names its key."""

    def __init__(self, code, key, headline, detail, remedy):
        self.code = code
        self.key = key
        self.headline = headline
        self.detail = detail
        self.remedy = remedy

    def __str__(self):
        return f"[{self.code}] {self.key}: {self.headline}"


class Unknown:
    """Something this run could not determine. Never a pass, never a failure."""

    def __init__(self, code, headline, detail, how_to_resolve):
        self.code = code
        self.headline = headline
        self.detail = detail
        self.how_to_resolve = how_to_resolve


def _short(path):
    """Repo-relative when it is inside the repo, absolute otherwise (tests)."""
    try:
        return Path(path).relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def load_register():
    if not REGISTER_PATH.exists():
        return None, (f"{_short(REGISTER_PATH)} does not "
                      f"exist. A missing register is not 'this repo serves no art' -- "
                      f"it is an unread one. Build it: "
                      f"python scripts/build-art-register.py")
    try:
        doc = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"{REGISTER_PATH}: not valid JSON: {exc}"
    if doc.get("schema") != _bar.SCHEMA:
        return None, (f"{REGISTER_PATH}: schema is {doc.get('schema')!r}, expected "
                      f"{_bar.SCHEMA!r}. Refusing to interpret an unknown shape.")
    if not isinstance(doc.get("images"), list):
        return None, f"{REGISTER_PATH}: `images` must be a list"
    return doc, None


def observe():
    """Re-derive the tree's own state. The register is not consulted here."""
    patterns = _bar.read_exclude_patterns()
    page_refs, data_refs = _bar.build_reference_index()
    out = {}
    for rel in _bar.walk_images():
        full = _bar.PUBLIC / rel
        deploys, excluded_by = _bar.deploy_state(rel, patterns)
        basename = Path(rel).name.lower()
        self_rel = "public/" + rel
        out[rel] = {
            "sha256": _bar.sha256_of(full),
            "deploys": deploys,
            "excluded_by": excluded_by,
            "referenced_by_pages": [r for r in page_refs.get(basename, [])
                                    if r != self_rel],
            "referenced_by_data": [r for r in data_refs.get(basename, [])
                                   if r != self_rel],
        }
    return out


def check(doc, observed, game_repo, today):
    findings, unknowns, inventory = [], [], []
    records = {r["path"]: r for r in doc["images"]}

    # --- S4 roster drift -----------------------------------------------------
    for rel in sorted(set(observed) - set(records)):
        findings.append(Finding(
            "S4", f"S4:{rel}",
            "an image is served with no register record",
            f"public/{rel} exists on disk and nothing in the register describes it. "
            f"An unregistered image is art with no provenance, which is the state "
            f"this register exists to abolish.",
            "python scripts/build-art-register.py"))
    for rel in sorted(set(records) - set(observed)):
        findings.append(Finding(
            "S4", f"S4:{rel}",
            "the register describes a file that is gone",
            f"The register has a record for public/{rel}, which is not on disk. A "
            f"provenance record for a missing file reads as verified provenance for "
            f"whatever takes the filename next.",
            "python scripts/build-art-register.py"))

    for rel in sorted(set(records) & set(observed)):
        rec, obs = records[rel], observed[rel]

        # --- S3 content drift ------------------------------------------------
        if rec.get("sha256") != obs["sha256"]:
            findings.append(Finding(
                "S3", f"S3:{rel}",
                "the bytes changed under an unchanged filename",
                f"Registered sha256 {str(rec.get('sha256'))[:12]}..., on disk "
                f"{obs['sha256'][:12]}.... This is the regenerated-asset case: same "
                f"path, same page, different picture, and every provenance claim in "
                f"the record now describes the previous image.",
                "Re-run the generator, and re-read the record's origin and upstream "
                "before trusting them: python scripts/build-art-register.py"))

        # --- S5 deployability drift ------------------------------------------
        if bool(rec.get("deploys")) != obs["deploys"] or \
                rec.get("excluded_by") != obs["excluded_by"]:
            findings.append(Finding(
                "S5", f"S5:{rel}",
                "deployability moved since the register was built",
                f"Registered deploys={rec.get('deploys')} "
                f"excluded_by={rec.get('excluded_by')!r}; recomputed against "
                f"deploy-excludes.txt: deploys={obs['deploys']} "
                f"excluded_by={obs['excluded_by']!r}. Remember an exclude is not a "
                f"delete: deploys going false does NOT unpublish anything a previous "
                f"deploy already uploaded.",
                "python scripts/build-art-register.py"))

        upstream = rec.get("upstream")

        # --- S1 superseded verdict -------------------------------------------
        if obs["deploys"] and isinstance(upstream, dict):
            verdict = upstream.get("verdict")
            if verdict not in KEEP_VERDICTS:
                findings.append(Finding(
                    "S1", f"S1:{rel}",
                    f"a deployed image whose upstream verdict is {verdict!r}",
                    f"public/{rel} is uploaded by every deploy. Its upstream asset "
                    f"{upstream.get('asset_id')} carries verdict {verdict!r} "
                    f"(recorded {upstream.get('verdict_updated_at')}), while the "
                    f"spec this repo copied from selected variant "
                    f"{upstream.get('selected_by_spec')!r}. The site is serving art "
                    f"the reviewer did not keep -- #283's defect, arrived at by a "
                    f"different route.",
                    "Decide which source governs: the generation spec "
                    "(art_prompts/*.yaml) or the human review "
                    "(tools/art_review/review_state.json). Then either unpublish the "
                    "file (a DELETE from public/, since an exclude would leave the "
                    "uploaded copy live), or record the decision in "
                    "data/acknowledgements.json with a review_by."))

        # --- S2 mirror drift, only measurable with a checkout -----------------
        if game_repo is not None and isinstance(upstream, dict):
            live = LIVE_VERDICTS.get(upstream.get("asset_id"))
            if live is None:
                findings.append(Finding(
                    "S2", f"S2:{rel}",
                    "the upstream asset has vanished from the corpus",
                    f"{upstream.get('asset_id')} is in the register and absent from "
                    f"{game_repo}/{_bar.UPSTREAM_REL}/review_state.json. The verdict "
                    f"this repo is relying on no longer has a source.",
                    "python scripts/build-art-register.py --game-repo <pdoom1>"))
            elif live.get("verdict") != upstream.get("verdict"):
                findings.append(Finding(
                    "S2", f"S2:{rel}",
                    "the register's mirrored verdict is out of date",
                    f"{upstream.get('asset_id')}: register says "
                    f"{upstream.get('verdict')!r}, the corpus now says "
                    f"{live.get('verdict')!r}. The bytes did not move; the decision "
                    f"did. That is the failure mode a filesystem check cannot see.",
                    "python scripts/build-art-register.py --game-repo <pdoom1>"))

        # --- S7 expired human assertion ---------------------------------------
        claim = (rec.get("claims") or {}).get("origin") or {}
        if claim.get("verify") == "human":
            hv = claim.get("human_verified") or {}
            try:
                review_by = dt.date.fromisoformat(hv.get("review_by", ""))
            except ValueError:
                findings.append(Finding(
                    "S7", f"S7:{rel}",
                    "a human origin assertion has no readable clock",
                    f"claims.origin is verify=human with review_by="
                    f"{hv.get('review_by')!r}. A verification date with no expiry is "
                    f"the class-5 shape.",
                    "Fix the entry in data/art-origins.json and rebuild."))
            else:
                if today > review_by:
                    findings.append(Finding(
                        "S7", f"S7:{rel}",
                        "a human origin assertion EXPIRED",
                        f"origin={rec.get('origin')!r} was asserted by "
                        f"{hv.get('by')} on {hv.get('on')} with review_by "
                        f"{review_by} ({(today - review_by).days} day(s) ago). The "
                        f"claim is not disproved; the decision to keep trusting it "
                        f"without looking again ran out.",
                        "Re-read the sources named in data/art-origins.json, then "
                        "either re-stamp human_verified with a new review_by and your "
                        "name, or drop the entry and let the origin read `unknown`. "
                        "Both are decisions; neither is a shrug."))

        # --- inventory, NOT findings -------------------------------------------
        if obs["deploys"] and not obs["referenced_by_pages"]:
            inventory.append((
                rel, rec.get("origin"),
                "data-only" if obs["referenced_by_data"] else "orphan",
                (upstream or {}).get("verdict") if isinstance(upstream, dict) else None))

        if rec.get("origin") == "unknown":
            unknowns.append(Unknown(
                "U1", f"origin unknown: {rel}",
                "Nothing in this repo records whether this image was generated, "
                "photographed, drawn or captured.",
                "Add an entry to data/art-origins.json (with a clock) if a person "
                "knows, or leave it -- unknown is a true answer."))

        if upstream is None:
            unknowns.append(Unknown(
                "U2", f"no upstream link: {rel}",
                "No file in this repo connects this image to a pdoom1 review asset, "
                "so no verdict can be attached to it either way.",
                "A provenance sidecar naming the upstream asset id would resolve it; "
                "public/assets/icons/events/PROVENANCE.json is the working example."))
        elif upstream == "unknown":
            unknowns.append(Unknown(
                "U4", f"upstream not consulted: {rel}",
                "The register was built with --allow-no-upstream, so the corpus was "
                "never read for this image. This is different from 'no link exists'.",
                "Rebuild with a pdoom1 checkout: "
                "python scripts/build-art-register.py --game-repo <pdoom1>"))

    # --- S6 mirror freshness -------------------------------------------------
    mirror = doc.get("mirror") or {}
    try:
        verified_on = dt.date.fromisoformat(mirror.get("verified_on", ""))
    except ValueError:
        findings.append(Finding(
            "S6", "S6:mirror",
            "the register does not say when it was last verified",
            f"mirror.verified_on={mirror.get('verified_on')!r} is not an ISO date. "
            f"An undated mirror cannot be called stale OR fresh, and defaulting to "
            f"fresh is the reassuring default this check exists to refuse.",
            "python scripts/build-art-register.py"))
    else:
        max_age = mirror.get("max_age_days")
        if not isinstance(max_age, int) or max_age <= 0:
            findings.append(Finding(
                "S6", "S6:mirror",
                "the register declares no maximum mirror age",
                f"mirror.max_age_days={max_age!r}. Without it nothing can go stale, "
                f"which is not the same as nothing being stale.",
                "python scripts/build-art-register.py"))
        else:
            age = (today - verified_on).days
            if age > max_age:
                findings.append(Finding(
                    "S6", "S6:mirror",
                    f"the mirror is {age} days old (limit {max_age})",
                    f"data/art-register.json mirrors pdoom1 "
                    f"{_bar.UPSTREAM_REL} at commit {mirror.get('source_commit')}, "
                    f"verified {verified_on}. pdoom1 publishes no art-provenance "
                    f"artifact, so nothing pushes an update here; the only thing that "
                    f"can notice is this clock.",
                    "python scripts/build-art-register.py --game-repo <pdoom1>"))

    if mirror.get("upstream_mode") == "unavailable":
        unknowns.append(Unknown(
            "U4", "the register was built without the upstream corpus",
            "Every upstream block reads 'unknown' rather than a verdict. That is an "
            "honest record of not having looked, and it is not a clean bill of health.",
            "python scripts/build-art-register.py --game-repo <pdoom1>"))

    if game_repo is None:
        unknowns.append(Unknown(
            "U3", "the mirror could not be re-verified this run",
            f"No pdoom1 checkout was found, so S2 (has a verdict moved since the "
            f"register was built?) did not run at all. The register's verdicts are "
            f"as of {mirror.get('verified_on')}, and this run cannot say whether they "
            f"still hold.",
            "python scripts/check-art-staleness.py --game-repo <pdoom1>, or set "
            "$PDOOM1_REPO. No CI runner here has one -- that is why this is UNKNOWN "
            "and not a failure."))

    # --- S9 the register's own arithmetic -------------------------------------
    declared = doc.get("counts") or {}
    recomputed = {
        "images_total": len(records),
        "images_deployed": sum(1 for r in records.values() if r.get("deploys")),
        "origin_unknown": sum(1 for r in records.values() if r.get("origin") == "unknown"),
        "deployed_origin_unknown": sum(
            1 for r in records.values()
            if r.get("deploys") and r.get("origin") == "unknown"),
        "deployed_upstream_resolved": sum(
            1 for r in records.values()
            if r.get("deploys") and isinstance(r.get("upstream"), dict)),
    }
    for key, value in recomputed.items():
        if declared.get(key) != value:
            findings.append(Finding(
                "S9", f"S9:{key}",
                "the register's summary disagrees with its own records",
                f"counts.{key} says {declared.get(key)!r}; counting the `images` list "
                f"gives {value}. A summary line is what a reader trusts instead of "
                f"reading 173 records, so a wrong one is worse than none.",
                "python scripts/build-art-register.py (and do not hand-edit the "
                "register -- it is generated)."))

    return findings, unknowns, inventory


LIVE_VERDICTS = {}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-game-repo", action="store_true",
                    help="pretend no pdoom1 checkout exists -- what a CI runner "
                         "actually sees, and what the forced-failure tests need")
    ap.add_argument("--game-repo", help="a pdoom1 checkout, read only. Without one, "
                                        "the mirror half reports UNKNOWN.")
    ap.add_argument("--register", help="alternative register path (tests)")
    ap.add_argument("--origins", help="alternative human-assertion file (tests)")
    ap.add_argument("--ledger", help="alternative acknowledgement ledger (tests)")
    ap.add_argument("--public", help="alternative served-tree root (tests)")
    ap.add_argument("--excludes", help="alternative rsync filter file (tests)")
    ap.add_argument("--as-of", help="evaluate clocks at this ISO date instead of today")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="list every UNKNOWN and every inventory row")
    args = ap.parse_args()

    global REGISTER_PATH, LIVE_VERDICTS
    if args.register:
        REGISTER_PATH = Path(args.register)
        _bar.REGISTER_PATH = REGISTER_PATH
    if args.origins:
        _bar.ORIGINS_PATH = Path(args.origins)
    if args.public:
        _bar.PUBLIC = Path(args.public)
    if args.excludes:
        _bar.EXCLUDES_PATH = Path(args.excludes)
    today = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()

    doc, error = load_register()
    if error:
        print("FAIL: the art register cannot be read.")
        print(f"  {error}")
        return 1

    game_repo = _bar.find_game_repo(args.game_repo, forbid=args.no_game_repo)
    if game_repo is not None:
        try:
            LIVE_VERDICTS, _q, _c = _bar.load_corpus(game_repo)
        except (_bar.RefuseToWrite, OSError, json.JSONDecodeError) as exc:
            print(f"FAIL: a pdoom1 checkout was found at {game_repo} but its corpus "
                  f"could not be read.")
            print(f"  {exc}")
            print("  Silently downgrading to UNKNOWN here would hide a broken corpus "
                  "behind the same words as a missing one.")
            return 1

    findings, unknowns, inventory = check(doc, observe(), game_repo, today)

    # --- acknowledgements ----------------------------------------------------
    try:
        ledger = load_ledger(ACK_CHECK_NAME, args.ledger)
    except AcknowledgementError as exc:
        print("REFUSED: the acknowledgement ledger cannot be trusted, so this check "
              "cannot say what is tolerated and what is not.")
        print(f"  {exc}")
        return 1

    report = ledger.assess({f.key for f in findings}, today=today)
    suppressed = report.acknowledged_keys
    blocking = [f for f in findings if f.key not in suppressed]

    # --- output --------------------------------------------------------------
    print(f"art staleness, as of {today}")
    print(f"  register  {_short(REGISTER_PATH)} "
          f"({len(doc['images'])} images, "
          f"{(doc.get('counts') or {}).get('images_deployed')} deploy)")
    print(f"  mirror    pdoom1 {_bar.UPSTREAM_REL} @ "
          f"{(doc.get('mirror') or {}).get('source_commit')}, verified "
          f"{(doc.get('mirror') or {}).get('verified_on')}")
    print(f"  corpus    {'re-read from ' + str(game_repo) if game_repo else 'NOT AVAILABLE this run'}")

    if blocking:
        print(f"\nFINDINGS ({len(blocking)}) -- each one is a divergence, not a style note.")
        print("-" * 72)
        for f in blocking:
            print(f"  [{f.code}] {f.key}")
            print(f"      {f.headline}")
            print(f"      {f.detail}")
            print(f"      DO THIS  {f.remedy}")

    acknowledged_now = [f for f in findings if f.key in suppressed]
    if acknowledged_now:
        print(f"\nACKNOWLEDGED FINDINGS ({len(acknowledged_now)}) -- still true, "
              f"tolerated on a dated decision:")
        for f in acknowledged_now:
            print(f"  {f}")

    report.print_to(sys.stdout)

    by_code = {}
    for u in unknowns:
        by_code.setdefault(u.code, []).append(u)
    if unknowns:
        print(f"\nUNKNOWN ({len(unknowns)}) -- things this run could NOT determine. "
              f"Not findings, and not a pass either.")
        for code in sorted(by_code):
            group = by_code[code]
            print(f"  [{code}] x{len(group)}  {group[0].headline if len(group) == 1 else _class_label(code)}")
            print(f"        {group[0].detail}")
            print(f"        RESOLVE  {group[0].how_to_resolve}")
            if args.verbose and len(group) > 1:
                for u in group:
                    print(f"          - {u.headline}")

    if inventory:
        print(f"\nINVENTORY ({len(inventory)}) -- deployed images that no PAGE "
              f"references. Facts, not findings: #283's harm was rejected art being "
              f"fetchable, and a kept asset nobody links to is dead weight, not a lie.")
        for rel, origin, kind, verdict in inventory if args.verbose else inventory[:10]:
            print(f"  {kind:<9} {rel}  (origin={origin}, upstream verdict={verdict})")
        if not args.verbose and len(inventory) > 10:
            print(f"  ... {len(inventory) - 10} more; -v to list them")

    print()
    if blocking or report.blocking:
        print(f"FAIL: {len(blocking)} finding(s), {len(report.expired)} expired "
              f"acceptance(s).")
        return 1
    if unknowns:
        print(f"UNKNOWN: 0 findings, {len(unknowns)} thing(s) this run could not "
              f"determine ({', '.join(f'{c} x{len(v)}' for c, v in sorted(by_code.items()))}). "
              f"Nothing diverged among what WAS checkable -- which is not the same "
              f"as nothing being wrong.")
        return 0
    print(f"OK: {len(doc['images'])} images, every claim checkable here was checked "
          f"and none diverged.")
    return 0


def _class_label(code):
    return {
        "U1": "images whose origin nothing in this repo records",
        "U2": "images with no link to any upstream review asset",
        "U3": "the mirror could not be re-verified this run",
        "U4": "upstream blocks recorded as 'unknown', never consulted",
    }.get(code, code)


if __name__ == "__main__":
    sys.exit(main())
