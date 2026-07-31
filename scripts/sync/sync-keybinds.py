#!/usr/bin/env python
"""Derive public/data/keybinds.json from the GAME's keybind_manager.gd.

WHY THIS EXISTS
---------------
The bug-report page has to tell a player which key opens the in-game bug
reporter. Typing that key into the HTML is exactly what rots: three files in
the pdoom1 repo (CONTRIBUTING.md, CHANGELOG.md) still say "backslash" and one
website issue says "F8", all of which are now WRONG -- the bind moved to N.
A player who presses a wrong key, sees nothing happen, and concludes the game
is broken is worse off than a player who was told nothing.

So the key is never typed into the page. The page renders it from
public/data/keybinds.json, and this script produces that file by PARSING the
authoritative source:

    <game repo>/godot/autoload/keybind_manager.gd

THE HONEST LIMIT
----------------
pdoom1 publishes no keybind artifact. This script reads a LOCAL CHECKOUT of the
game, so the committed JSON is a *mirror taken at a point in time*, not a live
derivation, and it goes stale the moment the game rebinds something without
anyone re-running this. That is why:

  * the emitted JSON carries `mirror: true` plus the source path, source commit
    and verification date, rather than pretending to be authoritative; and
  * `--check` FAILS on drift when the checkout is present, and fails on age
    when it is not (see check_freshness), so staleness surfaces instead of
    silently shipping.

The real fix is for the game to emit a keybind artifact per release, which the
website would then consume the way it consumes version.json. That ask is filed
upstream; see ASK_ISSUE below.

USAGE
-----
    python scripts/sync/sync-keybinds.py            # regenerate the JSON
    python scripts/sync/sync-keybinds.py --check    # verify; non-zero on drift

--check is the CI/pre-PR mode and performs three independent checks:
    1. drift    -- committed JSON still matches keybind_manager.gd (needs checkout)
    2. freshness-- the mirror was verified recently enough to be trusted
    3. no-hardcoding -- no page renders a key as a literal instead of from data

Check 3 runs everywhere, including CI without a game checkout, and is the one
that structurally enforces Pip's "use variables, don't hardcode" rule.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Windows console is cp1252; a non-ASCII print dies on the FIRST print, before
# any work happens. See CLAUDE.md "Environment / tooling".
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "public" / "data" / "keybinds.json"

# Relative to the game repo root.
SOURCE_REL = "godot/autoload/keybind_manager.gd"

# Upstream ask that would turn this mirror into a real derivation.
ASK_ISSUE = "PipFoweraker/pdoom1#1011"

# How long a mirror may go unverified before --check calls it stale. The game
# rebinds keys often enough (backslash -> N, F9 -> F6) that a quarter is
# generous; past this we would rather fail than keep publishing an old answer.
MAX_MIRROR_AGE_DAYS = 90

# Pages that render keybinds. Each must use <kbd data-keybind="action"></kbd>
# placeholders rather than a typed key -- see check_no_hardcoded_keys.
KEYBIND_PAGES = ["public/bug-report/index.html"]

# The single parse rule. A checker MUST import this rather than re-writing it:
# two copies of a regex drift apart and then the guard silently stops guarding.
# (Pattern borrowed from check-published-emails.py, which imports the
# generator's regex instead of copying it.)
#
# Matches one entry of the `keybinds` dictionary literal, e.g.
#   "bug_reporter": {"key": KEY_N, "category": Category.UI, "description": "Open Bug Reporter"},
# Optional modifier flags (e.g. "shift": true) may appear before "category".
BIND_RE = re.compile(
    r'^\s*"(?P<action>\w+)"\s*:\s*\{'
    r'\s*"key"\s*:\s*(?P<key>KEY_\w+)\s*,'
    r'(?P<mods>(?:\s*"(?:shift|ctrl|alt)"\s*:\s*(?:true|false)\s*,)*)'
    r'\s*"category"\s*:\s*Category\.(?P<category>\w+)\s*,'
    r'\s*"description"\s*:\s*"(?P<description>[^"]*)"',
    re.MULTILINE,
)

MOD_RE = re.compile(r'"(?P<name>shift|ctrl|alt)"\s*:\s*(?P<value>true|false)')

# Godot's OS.get_keycode_string() for the constants this project actually binds.
# Kept explicit rather than derived: a wrong display name is a wrong instruction
# to a player, so an unknown constant must fail loudly (see key_display).
KEYCODE_DISPLAY = {
    "KEY_BACKSLASH": "\\",
    "KEY_BRACKETLEFT": "[",
    "KEY_BRACKETRIGHT": "]",
    "KEY_SPACE": "Space",
    "KEY_ESCAPE": "Escape",
    "KEY_ENTER": "Enter",
    "KEY_TAB": "Tab",
    "KEY_NONE": "Unbound",
}

# Actions whose handler refuses to act unless BuildInfo.is_dev_build() is true.
# Verified by reading each handler's _ready(), not inferred from the DEBUG
# category -- debug_overlay is in category DEBUG and is NOT gated.
DEV_BUILD_GATED = {
    "dev_mode": "godot/scripts/debug/dev_mode_overlay.gd",
    "flight_recorder": "godot/scripts/debug/flight_recorder.gd",
    "ui_evolution_shot": "godot/scripts/debug/ui_evolution_recorder.gd",
}


def key_display(keycode: str) -> str:
    """Human-readable key name, mirroring Godot's OS.get_keycode_string()."""
    if keycode in KEYCODE_DISPLAY:
        return KEYCODE_DISPLAY[keycode]
    bare = keycode[len("KEY_"):]
    # Letters and digits render as themselves; F-keys as F1..F35.
    if re.fullmatch(r"[A-Z0-9]", bare) or re.fullmatch(r"F\d{1,2}", bare):
        return bare
    raise SystemExit(
        f"ERROR: no display name known for Godot keycode {keycode}.\n"
        f"  Add it to KEYCODE_DISPLAY in {Path(__file__).name}. Refusing to guess:\n"
        f"  a guessed key name is an instruction that sends a player to a key that\n"
        f"  does nothing."
    )


def find_game_repo(explicit=None):
    """Locate the pdoom1 checkout, or return None if it is not available."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("PDOOM1_REPO")
    if env:
        candidates.append(Path(env))
    # Normal layout: pdoom1 and pdoom1-website are siblings.
    candidates.append(REPO_ROOT.parent / "pdoom1")
    # This repo is often worked in a git worktree under .claude/worktrees/<id>,
    # which pushes REPO_ROOT three levels deeper than the real sibling layout.
    candidates.append(REPO_ROOT.parents[2] / "pdoom1" if len(REPO_ROOT.parents) > 2 else REPO_ROOT)
    candidates.append(Path.cwd().parent / "pdoom1")
    for c in candidates:
        try:
            if (c / SOURCE_REL).is_file():
                return c.resolve()
        except (OSError, IndexError):
            continue
    return None


def git_commit(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=20,
            # text=True decodes with the LOCALE codec; on a cp1252 console a child
            # writing UTF-8 raises UnicodeDecodeError. Be explicit.
            encoding="utf-8", errors="replace",
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def parse_keybinds(gd_text: str):
    """Parse keybind_manager.gd into a list of bind dicts."""
    # Only the `keybinds` dictionary literal, so a commented-out or unrelated
    # dict elsewhere in the file cannot leak in.
    start = gd_text.find("var keybinds: Dictionary = {")
    if start == -1:
        raise SystemExit("ERROR: could not find `var keybinds: Dictionary = {` in the source.")
    body = gd_text[start:]
    end = body.find("\n}")
    if end == -1:
        raise SystemExit("ERROR: could not find the end of the keybinds dictionary.")
    body = body[:end]

    binds = []
    for m in BIND_RE.finditer(body):
        action = m.group("action")
        mods = {mm.group("name"): mm.group("value") == "true"
                for mm in MOD_RE.finditer(m.group("mods") or "")}
        modifiers = sorted(k for k, v in mods.items() if v)
        entry = {
            "action": action,
            "godot_keycode": m.group("key"),
            "key": key_display(m.group("key")),
            "modifiers": modifiers,
            "category": m.group("category").lower(),
            "description": m.group("description"),
        }
        if action in DEV_BUILD_GATED:
            entry["availability"] = {
                "kind": "dev_build_only",
                "gate": "BuildInfo.DEV_BUILD",
                "gate_source": "godot/scripts/core/build_info.gd",
                "handler": DEV_BUILD_GATED[action],
                "note": (
                    "The handler returns early unless BuildInfo.is_dev_build(). "
                    "DEV_BUILD is a plain constant that a release cut is meant to flip "
                    "off, so this key may do nothing in the build a player downloaded."
                ),
            }
        else:
            entry["availability"] = {"kind": "all_builds"}
        binds.append(entry)
    if not binds:
        raise SystemExit("ERROR: parsed zero keybinds -- the source format probably changed.")
    return binds


def read_gate_value(repo: Path):
    """Read the literal value of BuildInfo.DEV_BUILD, or None if unreadable."""
    p = repo / "godot/scripts/core/build_info.gd"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^const\s+DEV_BUILD\s*:=\s*(true|false)", text, re.MULTILINE)
    return m.group(1) == "true" if m else None


def build_document(repo: Path):
    source = repo / SOURCE_REL
    binds = parse_keybinds(source.read_text(encoding="utf-8"))
    gate = read_gate_value(repo)
    return {
        "_README": (
            "DEFAULT keybinds for p(Doom)1, MIRRORED from the game's "
            "godot/autoload/keybind_manager.gd. Not authoritative and not live: the game "
            "publishes no keybind artifact yet, so this file is a point-in-time copy taken "
            "by scripts/sync/sync-keybinds.py from a local checkout. These are DEFAULTS -- "
            "every bind is rebindable by the player, so the in-game Keybindings screen is "
            "the only thing that can state a given player's actual key. Pages must render "
            "from this file rather than typing a key into HTML; "
            "`python scripts/sync/sync-keybinds.py --check` enforces both that rule and "
            "this file's freshness. Upstream ask to make this a real derivation: " + ASK_ISSUE
        ),
        "version": 1,
        "mirror": True,
        "source": {
            "repo": "PipFoweraker/pdoom1",
            "path": SOURCE_REL,
            "commit": git_commit(repo),
            "verified_on": date.today().isoformat(),
            "generator": "scripts/sync/sync-keybinds.py",
            "ask_issue": ASK_ISSUE,
        },
        "rebindable": {
            "value": True,
            "where": "Keybindings, on the game's main (welcome) screen",
            "note": (
                "Rebinding lives on the main menu's Keybindings screen, NOT in the in-game "
                "Settings menu -- settings_menu.tscn has no keybind row. Saved binds live in "
                "user://keybinds.cfg and are reset to defaults when the game's "
                "KEYBINDS_CONFIG_VERSION is bumped."
            ),
        },
        "dev_build_gate": {
            "constant": "BuildInfo.DEV_BUILD",
            "value_at_verification": gate,
            "note": (
                "A plain GDScript constant, not OS.is_debug_build(). Nothing in the export "
                "tooling flips it, so its shipped value is whatever was committed at the "
                "release cut. Treat dev-gated keys as 'may or may not be present'."
            ),
        },
        "keybinds": binds,
    }


def load_committed():
    if not OUT_PATH.exists():
        return None
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"ERROR: {OUT_PATH} is unreadable: {e}")


def write_document(doc):
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


# ---- checks -----------------------------------------------------------------

def check_drift(repo, committed, problems, notes):
    """Committed binds still match the game source. Needs a checkout."""
    if repo is None:
        notes.append(
            "SKIP drift: no pdoom1 checkout found (set PDOOM1_REPO to enable). "
            "Cannot compare against the game source from here."
        )
        return
    fresh = build_document(repo)
    if fresh["keybinds"] != committed.get("keybinds"):
        fresh_map = {b["action"]: b for b in fresh["keybinds"]}
        old_map = {b["action"]: b for b in committed.get("keybinds", [])}
        for action in sorted(set(fresh_map) | set(old_map)):
            f, o = fresh_map.get(action), old_map.get(action)
            if f == o:
                continue
            if o is None:
                problems.append(f"drift: '{action}' is new in the game and missing here")
            elif f is None:
                problems.append(f"drift: '{action}' no longer exists in the game")
            else:
                problems.append(
                    f"drift: '{action}' is {o.get('key')!r} here but "
                    f"{f.get('key')!r} in the game source"
                )
        problems.append(
            "  -> re-run: python scripts/sync/sync-keybinds.py  (then review the page copy)"
        )
    else:
        notes.append(f"OK drift: keybinds match {repo / SOURCE_REL}")


def check_freshness(committed, problems, notes):
    """The mirror was verified recently enough to be worth trusting."""
    stamp = (committed.get("source") or {}).get("verified_on")
    if not stamp:
        problems.append("freshness: source.verified_on is missing -- mirror age unknowable")
        return
    try:
        verified = datetime.strptime(stamp, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        problems.append(f"freshness: source.verified_on {stamp!r} is not an ISO date")
        return
    age = (datetime.now(timezone.utc) - verified).days
    if age > MAX_MIRROR_AGE_DAYS:
        problems.append(
            f"freshness: mirror last verified {stamp} ({age} days ago, limit "
            f"{MAX_MIRROR_AGE_DAYS}). Re-run the sync against a current pdoom1 checkout, "
            f"or land {ASK_ISSUE} so this derives instead of mirroring."
        )
    else:
        notes.append(f"OK freshness: verified {stamp} ({age} days ago)")


def check_no_hardcoded_keys(committed, problems, notes):
    """No page may type a key literal; every <kbd> must read from the data.

    This is the check that runs everywhere, including CI with no game checkout,
    and it is the one that structurally prevents the rot that produced the three
    stale pdoom1 docs.
    """
    actions = {b["action"] for b in committed.get("keybinds", [])}
    # A <kbd> may carry data-keybind="<known action>" and must be empty or hold
    # only the ellipsis placeholder that JS overwrites.
    kbd_re = re.compile(r"<kbd\b(?P<attrs>[^>]*)>(?P<inner>.*?)</kbd>", re.DOTALL | re.IGNORECASE)
    attr_re = re.compile(r'data-keybind\s*=\s*"(?P<action>[^"]+)"')
    # Only RENDERED markup counts. Style and script blocks legitimately mention
    # <kbd> in comments (this file's own convention is documented there), and
    # scanning them made the first version of this check report its own
    # documentation as a violation.
    inert_re = re.compile(r"<(style|script)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
    checked = 0
    for rel in KEYBIND_PAGES:
        path = REPO_ROOT / rel
        if not path.exists():
            problems.append(f"no-hardcoding: {rel} is listed but missing")
            continue
        html = inert_re.sub("", path.read_text(encoding="utf-8"))
        for m in kbd_re.finditer(html):
            checked += 1
            attrs, inner = m.group("attrs"), m.group("inner").strip()
            am = attr_re.search(attrs)
            if not am:
                problems.append(
                    f"no-hardcoding: {rel} has <kbd>{inner}</kbd> with no data-keybind. "
                    f"A typed key rots -- use <kbd data-keybind=\"<action>\">...</kbd>."
                )
                continue
            if am.group("action") not in actions:
                problems.append(
                    f"no-hardcoding: {rel} references unknown action "
                    f"'{am.group('action')}' (not in keybinds.json)"
                )
            if inner not in ("", "…"):
                problems.append(
                    f"no-hardcoding: {rel} <kbd data-keybind=\"{am.group('action')}\"> "
                    f"contains the literal {inner!r}. Leave it as the placeholder so the "
                    f"value can only come from keybinds.json."
                )
    notes.append(f"OK no-hardcoding: {checked} <kbd> element(s) across {len(KEYBIND_PAGES)} page(s)")


def run_check(repo):
    committed = load_committed()
    if committed is None:
        print(f"FAIL: {OUT_PATH.relative_to(REPO_ROOT)} does not exist. "
              f"Run: python scripts/sync/sync-keybinds.py")
        return 1
    problems, notes = [], []
    check_drift(repo, committed, problems, notes)
    check_freshness(committed, problems, notes)
    check_no_hardcoded_keys(committed, problems, notes)
    for n in notes:
        print(n)
    if problems:
        print("\nFAIL: keybind mirror problems:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nPASS: keybind data is consistent, fresh, and rendered from data.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="verify instead of writing; non-zero exit on any problem")
    ap.add_argument("--game-repo", default=None,
                    help="path to the pdoom1 checkout (else $PDOOM1_REPO, else ../pdoom1)")
    args = ap.parse_args()

    repo = find_game_repo(args.game_repo)

    if args.check:
        return run_check(repo)

    if repo is None:
        print("ERROR: no pdoom1 checkout found. Pass --game-repo or set PDOOM1_REPO.\n"
              "  This script derives the keybinds by parsing the game's source; it will\n"
              "  not invent values.")
        return 1
    doc = build_document(repo)
    prev = load_committed()
    write_document(doc)
    rel = OUT_PATH.relative_to(REPO_ROOT)
    print(f"Wrote {rel} -- {len(doc['keybinds'])} binds from {repo / SOURCE_REL}")
    print(f"  source commit {doc['source']['commit']}, verified {doc['source']['verified_on']}")
    if prev and prev.get("keybinds") != doc["keybinds"]:
        print("  NOTE: binds CHANGED since the last mirror -- re-read the bug-report page copy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
