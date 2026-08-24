#!/usr/bin/env python
"""Force every failure scripts/check-art-staleness.py claims to catch, and watch it.

WHY THIS FILE EXISTS
--------------------
CLAUDE.md's testing discipline, verbatim in spirit: "A guard seen only in its
passing state has not been shown to work. Green is equally consistent with 'the
condition is safe' and 'the check never fires'."

check-art-staleness.py is EXPOSED to that critique more than most, because on
the real tree its verdict is UNKNOWN with zero findings. An UNKNOWN with no
findings looks identical to a check that examines nothing. So every assertion
below builds a fixture tree in a temp directory, breaks exactly one thing, and
requires the specific finding code -- not merely a non-zero exit, which a
crashing script also produces.

It also asserts the two directions people forget:
  * that the check can reach OK at all (a permanently-UNKNOWN check is a
    permanently-red check wearing a nicer word), and
  * that an EXPIRED acceptance goes red on the EXPIRY and not on the finding,
    which is the whole design of scripts/acknowledgements.py.

Nothing here mutates a committed file. The real register, the real ledger and
the real public/ tree are read at most once, to prove the fixtures have not
drifted away from the shapes the production code actually meets.

Run:  python scripts/test-art-staleness.py [-v]
"""

import json
import shutil
import subprocess
import sys
import tempfile
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
BUILDER = REPO_ROOT / "scripts" / "build-art-register.py"
CHECKER = REPO_ROOT / "scripts" / "check-art-staleness.py"

FAILURES = []
PASSES = []
VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv


def check(label, condition, detail=""):
    if condition:
        PASSES.append(label)
        if VERBOSE:
            print(f"  ok    {label}")
    else:
        FAILURES.append(f"{label}: {detail}")
        print(f"  FAIL  {label}\n        {detail}")


def run(script, *args):
    proc = subprocess.run([sys.executable, str(script), *[str(a) for a in args]],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(REPO_ROOT))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

EXCLUDES = "# fixture rsync filter\nassets/hidden\n"

PROVENANCE = {
    "source_repo": "pdoom1",
    "prompt_file": "art_prompts/fixture.yaml",
    "asset_type": "fixture_icons",
    "machine_generated": True,
    "icons": [
        {"file": "kept_v1_128.png", "slot_id": "kept", "selected_variant": "v1",
         "machine_generated": True},
        {"file": "dropped_v2_128.png", "slot_id": "dropped", "selected_variant": "v2",
         "machine_generated": True},
    ],
}

CORPUS = {
    "gen:fixture_icons:kept:v1": {"verdict": "keep", "updated_at": "2026-08-14T00:00:00Z",
                                  "note": "", "tags": []},
    "gen:fixture_icons:dropped:v2": {"verdict": "discard",
                                     "updated_at": "2026-08-14T00:00:00Z",
                                     "note": "", "tags": []},
}

LEDGER_SKELETON = {
    "schema": "pdoom-acknowledgements/v1",
    "policy": {"warn_within_days": 14, "source": "fixture"},
    "checks": {"check-art-staleness": "fixture"},
    "acknowledgements": [],
}


def make_tree(root, *, with_photo_assertion=None, corpus=True):
    """A miniature pdoom1-website + pdoom1 pair. Returns a paths dict."""
    public = root / "public"
    icons = public / "assets" / "icons" / "events"
    icons.mkdir(parents=True)
    (public / "assets" / "hidden").mkdir(parents=True)
    (public / "assets" / "photos").mkdir(parents=True)

    (icons / "kept_v1_128.png").write_bytes(b"\x89PNG-kept")
    (icons / "dropped_v2_128.png").write_bytes(b"\x89PNG-dropped")
    (public / "assets" / "hidden" / "secret.png").write_bytes(b"\x89PNG-secret")
    (public / "assets" / "photos" / "cat.jpg").write_bytes(b"\xff\xd8cat")
    (icons / "PROVENANCE.json").write_text(json.dumps(PROVENANCE, indent=2),
                                           encoding="utf-8")
    # One page that references the cat, so the fixture exercises both the
    # referenced and the unreferenced branch.
    (public / "index.html").write_text(
        '<img src="/assets/photos/cat.jpg" alt="">', encoding="utf-8")

    excludes = root / "deploy-excludes.txt"
    excludes.write_text(EXCLUDES, encoding="utf-8")

    origins = root / "art-origins.json"
    assertions = []
    if with_photo_assertion:
        assertions.append(with_photo_assertion)
    origins.write_text(json.dumps({"schema": "pdoom-art-origins/v1",
                                   "assertions": assertions}, indent=2),
                       encoding="utf-8")

    game = root / "pdoom1"
    if corpus:
        (game / "tools" / "art_review").mkdir(parents=True)
        (game / "tools" / "art_review" / "review_state.json").write_text(
            json.dumps(CORPUS, indent=2), encoding="utf-8")
        (game / "tools" / "art_review" / "pullquotes.jsonl").write_text(
            json.dumps({"asset": "gen:fixture_icons:dropped:v2", "id": "artq-999",
                        "cleared_for": None}) + "\n", encoding="utf-8")

    ledger = root / "acknowledgements.json"
    ledger.write_text(json.dumps(LEDGER_SKELETON, indent=2), encoding="utf-8")

    return {"root": root, "public": public, "excludes": excludes,
            "origins": origins, "game": game, "ledger": ledger,
            "register": root / "art-register.json"}


def build(paths, *args):
    return run(BUILDER, "--public", paths["public"], "--excludes", paths["excludes"],
               "--origins", paths["origins"], "--register", paths["register"],
               "--game-repo", paths["game"], *args)


def verify(paths, *args):
    return run(CHECKER, "--public", paths["public"], "--excludes", paths["excludes"],
               "--origins", paths["origins"], "--register", paths["register"],
               "--ledger", paths["ledger"], *args)


def load(paths):
    return json.loads(paths["register"].read_text(encoding="utf-8"))


def save(paths, doc):
    paths["register"].write_text(json.dumps(doc, indent=2), encoding="utf-8")


def set_ledger(paths, entries):
    doc = dict(LEDGER_SKELETON)
    doc["acknowledgements"] = entries
    paths["ledger"].write_text(json.dumps(doc, indent=2), encoding="utf-8")


PHOTO_ASSERTION = {
    "path": "assets/photos/cat.jpg",
    "origin": "photograph",
    "verify": "human",
    "why_not_machine": "fixture: a camera and a real animal are not in any repo",
    "source": "fixture",
    "human_verified": {"by": "fixture", "on": "2026-01-01",
                       "review_by": "2027-01-01", "note": "fixture"},
}


# ---------------------------------------------------------------------------
# the tests
# ---------------------------------------------------------------------------

def test_builder(tmp):
    print("\nBUILDER -- it refuses rather than guessing")
    paths = make_tree(tmp / "b1", with_photo_assertion=PHOTO_ASSERTION)

    code, out = build(paths)
    check("builds a register from a clean fixture", code == 0, out[-400:])
    doc = load(paths)
    by_path = {r["path"]: r for r in doc["images"]}

    check("every image under the served tree gets a record",
          set(by_path) == {"assets/icons/events/kept_v1_128.png",
                           "assets/icons/events/dropped_v2_128.png",
                           "assets/hidden/secret.png",
                           "assets/photos/cat.jpg"},
          f"got {sorted(by_path)}")
    check("an excluded image is recorded as NOT deploying, not omitted",
          by_path["assets/hidden/secret.png"]["deploys"] is False
          and by_path["assets/hidden/secret.png"]["excluded_by"] == "assets/hidden",
          json.dumps(by_path["assets/hidden/secret.png"])[:200])
    check("PROVENANCE.json machine_generated becomes origin=generated",
          by_path["assets/icons/events/kept_v1_128.png"]["origin"] == "generated")
    check("the upstream verdict is mirrored per variant",
          by_path["assets/icons/events/dropped_v2_128.png"]["upstream"]["verdict"]
          == "discard")
    check("artq ids are carried and reviewer prose is NOT",
          by_path["assets/icons/events/dropped_v2_128.png"]["upstream"]["artq_ids"]
          == ["artq-999"]
          and "note" not in by_path["assets/icons/events/dropped_v2_128.png"]["upstream"],
          "a reviewer's words must never reach this file")
    check("a human assertion lands as a claims entry at the human tier",
          by_path["assets/photos/cat.jpg"]["claims"]["origin"]["verify"] == "human")
    check("an image with no in-repo source reads origin=unknown with NO claims entry",
          by_path["assets/hidden/secret.png"]["origin"] == "unknown"
          and by_path["assets/hidden/secret.png"]["claims"] == {})
    check("a sidecar reference is not counted as a page reference",
          by_path["assets/icons/events/kept_v1_128.png"]["referenced_by_pages"] == []
          and by_path["assets/icons/events/kept_v1_128.png"]["referenced_by_data"] != [],
          "PROVENANCE.json describes the icon; no page uses it")
    check("a page reference IS counted",
          by_path["assets/photos/cat.jpg"]["referenced_by_pages"] != [])

    code, out = build(paths, "--check")
    check("--check is green on a register it just wrote", code == 0, out[-300:])

    # FORCED: no corpus at all
    paths2 = make_tree(tmp / "b2", corpus=False)
    code, out = run(BUILDER, "--public", paths2["public"], "--excludes",
                    paths2["excludes"], "--origins", paths2["origins"],
                    "--register", paths2["register"], "--no-game-repo")
    check("REFUSES to write with no upstream corpus",
          code == 2 and "REFUSED TO WRITE" in out and not paths2["register"].exists(),
          f"exit {code}; register exists: {paths2['register'].exists()}")

    code, out = run(BUILDER, "--public", paths2["public"], "--excludes",
                    paths2["excludes"], "--origins", paths2["origins"],
                    "--register", paths2["register"], "--no-game-repo",
                    "--allow-no-upstream")
    check("--allow-no-upstream writes 'unknown', never null",
          code == 0 and all(r["upstream"] == "unknown"
                            for r in load(paths2)["images"]),
          out[-300:])

    # FORCED: a human assertion pointing at a path that is gone
    paths3 = make_tree(tmp / "b3", with_photo_assertion=dict(
        PHOTO_ASSERTION, path="assets/photos/deleted.jpg"))
    code, out = build(paths3)
    check("REFUSES a human assertion whose file does not exist",
          code == 2 and "not on disk" in out and not paths3["register"].exists(),
          out[-300:])

    # FORCED: a human assertion with no clock
    clockless = dict(PHOTO_ASSERTION)
    clockless.pop("human_verified")
    paths4 = make_tree(tmp / "b4", with_photo_assertion=clockless)
    code, out = build(paths4)
    check("REFUSES a human assertion with no human_verified clock",
          code == 2 and "human_verified" in out, out[-300:])

    # FORCED: a zero-length clock
    zero = dict(PHOTO_ASSERTION,
                human_verified=dict(PHOTO_ASSERTION["human_verified"],
                                    review_by="2026-01-01"))
    paths5 = make_tree(tmp / "b5", with_photo_assertion=zero)
    code, out = build(paths5)
    check("REFUSES a zero-length human verification",
          code == 2 and "review_by" in out, out[-300:])

    # FORCED: PROVENANCE.json naming a file that is gone
    paths6 = make_tree(tmp / "b6")
    (paths6["public"] / "assets/icons/events/kept_v1_128.png").unlink()
    code, out = build(paths6)
    check("REFUSES when PROVENANCE.json names a file that is not there",
          code == 2 and "not on disk" in out, out[-300:])

    # FORCED: the constructed asset id is absent from the corpus
    paths7 = make_tree(tmp / "b7")
    corpus = paths7["game"] / "tools" / "art_review" / "review_state.json"
    corpus.write_text(json.dumps(
        {"gen:fixture_icons:kept:v1": CORPUS["gen:fixture_icons:kept:v1"]}, indent=2),
        encoding="utf-8")
    code, out = build(paths7)
    check("REFUSES when a PROVENANCE slot has no matching corpus asset",
          code == 2 and "absent from the corpus" in out, out[-400:])

    # FORCED: the corpus has changed shape entirely
    paths8 = make_tree(tmp / "b8")
    (paths8["game"] / "tools" / "art_review" / "review_state.json").write_text(
        json.dumps({"px:something:else": {}}), encoding="utf-8")
    code, out = build(paths8)
    check("REFUSES when the corpus holds no gen: keys at all",
          code == 2 and "corpus shape changed" in out, out[-400:])

    # FORCED: a file added to public/ after the build
    paths9 = make_tree(tmp / "b9")
    build(paths9)
    (paths9["public"] / "assets" / "photos" / "new.png").write_bytes(b"\x89PNGnew")
    code, out = build(paths9, "--check")
    check("--check FAILS when public/ gained an image the register lacks",
          code == 1 and "assets/photos/new.png" in out, out[-400:])


def test_checker(tmp):
    print("\nCHECKER -- every finding code, forced")

    # S1: a deployed image whose upstream verdict is not keep.
    paths = make_tree(tmp / "c1", with_photo_assertion=PHOTO_ASSERTION)
    build(paths)
    code, out = verify(paths, "--game-repo", paths["game"])
    key = "S1:assets/icons/events/dropped_v2_128.png"
    check("S1 fires on a deployed image with verdict 'discard'",
          code == 1 and "[S1]" in out and key in out, out[-600:])
    check("S1 does NOT fire on the sibling with verdict 'keep'",
          "S1:assets/icons/events/kept_v1_128.png" not in out, out[-600:])

    # ...and an unexpired acceptance suppresses the finding, not the print.
    entry = {
        "check": "check-art-staleness", "key": key,
        "what": "fixture", "why": "fixture",
        "accepted_by": "fixture", "accepted_on": "2026-01-01",
        "review_by": "2999-01-01", "on_expiry": "fixture", "source": "fixture",
    }
    set_ledger(paths, [entry])
    code, out = verify(paths, "--game-repo", paths["game"])
    check("a live acceptance turns S1 green and STILL prints it",
          code == 0 and "ACKNOWLEDGED" in out and key in out, out[-600:])
    check("green carries a number, never silence",
          "1 on file" in out and "1 live and firing" in out, out[-600:])

    # ...and an expired one is red on the EXPIRY, not on the finding.
    set_ledger(paths, [dict(entry, review_by="2026-01-02")])
    code, out = verify(paths, "--game-repo", paths["game"], "--as-of", "2026-08-25")
    check("an EXPIRED acceptance fails", code == 1, out[-600:])
    check("...and the red is about the expiry, not the picture",
          "EXPIRED ACCEPTANCE" in out and "the decision to tolerate" in out,
          out[-800:])
    set_ledger(paths, [])

    # S3: the bytes change under an unchanged filename.
    paths = make_tree(tmp / "c3")
    build(paths)
    (paths["public"] / "assets/photos/cat.jpg").write_bytes(b"\xff\xd8DIFFERENT")
    code, out = verify(paths, "--no-game-repo")
    check("S3 fires when an asset is regenerated in place",
          code == 1 and "[S3]" in out and "assets/photos/cat.jpg" in out, out[-600:])

    # S4: roster drift, both directions.
    paths = make_tree(tmp / "c4a")
    build(paths)
    (paths["public"] / "assets" / "photos" / "extra.png").write_bytes(b"\x89PNGx")
    code, out = verify(paths, "--no-game-repo")
    check("S4 fires on an image served with no register record",
          code == 1 and "[S4]" in out and "extra.png" in out, out[-600:])

    paths = make_tree(tmp / "c4b")
    build(paths)
    (paths["public"] / "assets/photos/cat.jpg").unlink()
    code, out = verify(paths, "--no-game-repo")
    check("S4 fires on a register record whose file is gone",
          code == 1 and "[S4]" in out and "cat.jpg" in out, out[-600:])

    # S5: deployability drift.
    paths = make_tree(tmp / "c5")
    build(paths)
    paths["excludes"].write_text("# fixture\nassets/photos\n", encoding="utf-8")
    code, out = verify(paths, "--no-game-repo")
    check("S5 fires when deploy-excludes.txt moves under the register",
          code == 1 and "[S5]" in out and "assets/photos/cat.jpg" in out, out[-600:])
    check("...and the S5 text says an exclude is not a delete",
          "exclude is not a delete" in out, out[-600:])

    # S6: the mirror goes stale, and an undated mirror is not 'fresh'.
    paths = make_tree(tmp / "c6")
    build(paths)
    doc = load(paths)
    doc["mirror"]["verified_on"] = "2020-01-01"
    save(paths, doc)
    code, out = verify(paths, "--no-game-repo")
    check("S6 fires on a mirror older than its declared max age",
          code == 1 and "[S6]" in out, out[-600:])

    doc["mirror"]["verified_on"] = ""
    save(paths, doc)
    code, out = verify(paths, "--no-game-repo")
    check("an UNDATED mirror is a failure, never a pass",
          code == 1 and "[S6]" in out and "cannot be called stale OR fresh" in out,
          out[-600:])

    # S7: a human assertion expires.
    expiring = dict(PHOTO_ASSERTION,
                    human_verified=dict(PHOTO_ASSERTION["human_verified"],
                                        on="2026-01-01", review_by="2026-02-01"))
    paths = make_tree(tmp / "c7", with_photo_assertion=expiring)
    build(paths)
    code, out = verify(paths, "--no-game-repo", "--as-of", "2026-08-25")
    check("S7 fires when a human origin assertion is past review_by",
          code == 1 and "[S7]" in out and "EXPIRED" in out, out[-700:])
    check("...on the expiry, explicitly not on the claim",
          "not disproved" in out, out[-700:])
    code, out = verify(paths, "--no-game-repo", "--as-of", "2026-01-15")
    check("S7 is silent while the assertion is still in force",
          "[S7]" not in out, out[-700:])

    # S8/S2: the mirrored verdict moves while the bytes do not.
    paths = make_tree(tmp / "c2")
    build(paths)
    doc = load(paths)
    for r in doc["images"]:
        if isinstance(r.get("upstream"), dict) \
                and r["upstream"]["asset_id"] == "gen:fixture_icons:dropped:v2":
            r["upstream"]["verdict"] = "keep"
    save(paths, doc)
    code, out = verify(paths, "--game-repo", paths["game"])
    check("S2 fires when the corpus verdict has moved since the register was built",
          code == 1 and "[S2]" in out, out[-700:])
    check("...and S2 is UNKNOWN, not silence, when no checkout exists",
          "[U3]" in verify(paths, "--no-game-repo")[1], "U3 must be reported")

    # S2b: the upstream asset disappears from the corpus entirely.
    paths = make_tree(tmp / "c2b")
    build(paths)
    (paths["game"] / "tools" / "art_review" / "review_state.json").write_text(
        json.dumps({"gen:fixture_icons:kept:v1": CORPUS["gen:fixture_icons:kept:v1"],
                    "gen:something:else:v1": {"verdict": "keep"}}), encoding="utf-8")
    code, out = verify(paths, "--game-repo", paths["game"])
    check("S2 fires when a mirrored asset vanishes upstream",
          code == 1 and "vanished from the corpus" in out, out[-700:])

    # S9: the register's own arithmetic.
    paths = make_tree(tmp / "c9")
    build(paths)
    doc = load(paths)
    doc["counts"]["images_deployed"] = 99
    save(paths, doc)
    code, out = verify(paths, "--no-game-repo")
    check("S9 fires when the summary disagrees with the records it summarises",
          code == 1 and "[S9]" in out, out[-600:])

    # A broken corpus is a FAILURE, never a quiet downgrade to UNKNOWN.
    paths = make_tree(tmp / "cbroken")
    build(paths)
    (paths["game"] / "tools" / "art_review" / "review_state.json").write_text(
        "{not json", encoding="utf-8")
    code, out = verify(paths, "--game-repo", paths["game"])
    check("a corpus that exists but cannot be read FAILS, never reads as UNKNOWN",
          code == 1 and "could not be read" in out, out[-600:])

    # A missing register is a failure, not "no art".
    paths = make_tree(tmp / "cmissing")
    code, out = verify(paths, "--no-game-repo")
    check("a missing register FAILS rather than reporting an empty site",
          code == 1 and "not 'this repo serves no art'" in out, out[-400:])


def test_verdict_vocabulary(tmp):
    print("\nVERDICTS -- OK, UNKNOWN and FAIL are three states, not two")

    # UNKNOWN: something is unresolved, nothing diverged.
    paths = make_tree(tmp / "v1", with_photo_assertion=PHOTO_ASSERTION)
    build(paths)
    set_ledger(paths, [{
        "check": "check-art-staleness",
        "key": "S1:assets/icons/events/dropped_v2_128.png",
        "what": "fixture", "why": "fixture", "accepted_by": "fixture",
        "accepted_on": "2026-01-01", "review_by": "2999-01-01",
        "on_expiry": "fixture", "source": "fixture"}])
    code, out = verify(paths, "--no-game-repo")
    check("an unresolved origin caps the verdict at UNKNOWN",
          code == 0 and out.rstrip().splitlines()[-1].startswith("UNKNOWN"),
          out[-400:])
    check("the word PASS is never printed", "PASS" not in out, out[-400:])
    check("UNKNOWN says out loud that it is not a clean bill of health",
          "not the same as nothing being wrong" in out, out[-400:])

    # OK: reachable. If it were not, UNKNOWN would be a permanent red in a
    # friendlier font, and nobody would ever read it.
    paths = make_tree(tmp / "v2")
    for junk in ("assets/hidden/secret.png", "assets/photos/cat.jpg"):
        (paths["public"] / junk).unlink()
    (paths["public"] / "index.html").write_text(
        '<img src="/assets/icons/events/kept_v1_128.png" alt="">'
        '<img src="/assets/icons/events/dropped_v2_128.png" alt="">',
        encoding="utf-8")
    build(paths)
    set_ledger(paths, [{
        "check": "check-art-staleness",
        "key": "S1:assets/icons/events/dropped_v2_128.png",
        "what": "fixture", "why": "fixture", "accepted_by": "fixture",
        "accepted_on": "2026-01-01", "review_by": "2999-01-01",
        "on_expiry": "fixture", "source": "fixture"}])
    code, out = verify(paths, "--game-repo", paths["game"])
    check("OK is REACHABLE when every origin and every upstream link resolves",
          code == 0 and out.rstrip().splitlines()[-1].startswith("OK"),
          out[-500:])


def test_against_the_real_tree():
    print("\nTHE REAL TREE -- the fixtures have not drifted from production shapes")
    register = REPO_ROOT / "data" / "art-register.json"
    check("the committed register exists", register.exists(),
          "run python scripts/build-art-register.py")
    if not register.exists():
        return
    doc = json.loads(register.read_text(encoding="utf-8"))
    check("the committed register is NOT under public/ (it would be published)",
          "public" not in register.relative_to(REPO_ROOT).parts,
          "public/ is rsynced to production; this file names another repo's "
          "internal review verdicts")
    check("the committed register declares the schema the checker expects",
          doc.get("schema") == "pdoom-art-register/v1", doc.get("schema"))
    # The upstream block is where a reviewer's words would leak in, because the
    # corpus row it is built from carries `note` and the pullquote row carries
    # `text_verbatim`. Assert the SHAPE, so a future field added upstream fails
    # here rather than being copied through. (`note` under claims.human_verified
    # is this repo's own note about its own verification, not a reviewer's.)
    allowed = {"asset_id", "batch", "slot_id", "variant", "verdict",
               "verdict_updated_at", "artq_ids", "cleared_for", "selected_by_spec"}
    leaked = sorted({k for r in doc.get("images", [])
                     if isinstance(r.get("upstream"), dict)
                     for k in r["upstream"] if k not in allowed})
    check("no reviewer prose reached the register",
          not leaked and "text_verbatim" not in json.dumps(doc),
          f"unexpected upstream keys {leaked}. Ids and verdicts only -- ART_DRIP "
          f"gate 2 records that consent to publish a second named reviewer's words "
          f"is an OPEN question, and attribution is known-uncertain at variant level.")
    check("the ledger declares this check, so a rename fails loudly",
          "check-art-staleness" in json.loads(
              (REPO_ROOT / "data" / "acknowledgements.json").read_text(encoding="utf-8")
          ).get("checks", {}),
          "add it to data/acknowledgements.json -> checks")

    code, out = run(CHECKER, "--no-game-repo")
    last = out.rstrip().splitlines()[-1] if out.strip() else ""
    check("the real run exits 0 or 1 and never crashes", code in (0, 1), out[-400:])
    check("the real run's last line is one of OK / UNKNOWN / FAIL",
          last.startswith(("OK", "UNKNOWN", "FAIL")), last)


def main():
    with tempfile.TemporaryDirectory(prefix="art-staleness-") as td:
        tmp = Path(td)
        test_builder(tmp)
        test_checker(tmp)
        test_verdict_vocabulary(tmp)
    test_against_the_real_tree()

    print(f"\n{len(PASSES)} assertion(s) passed, {len(FAILURES)} failed.")
    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("Every failure mode check-art-staleness.py claims to catch was forced "
          "and observed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
