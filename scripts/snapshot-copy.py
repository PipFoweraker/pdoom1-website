#!/usr/bin/env python
"""Snapshot the site's user-facing prose so copy changes stay reviewable.

WHY THIS EXISTS
---------------
Git already stores every past version of every page, but a page is 3-16 KB of
inline CSS and markup wrapped around a few hundred words of prose. A `git diff`
on public/index.html is unreadable when what you actually want to know is
"did the tone change, and did we quietly drop a promise we made to players?"

This extracts prose ONLY -- no markup, no CSS, no scripts -- one block per line,
in document order. Diffing two snapshots therefore shows sentence-level wording
changes and nothing else.

The baseline in docs/copy-baseline/ is a FROZEN record of the hand-written copy
as it stood before the 2026-07 truth-and-accuracy pass. It is not auto-updated;
regenerating it requires --force, deliberately, so it keeps working as a
reference point rather than drifting along with the site.

USAGE
-----
    python scripts/snapshot-copy.py --check
        Diff the working tree's prose against the frozen baseline. Exit 1 if
        anything changed. This is the everyday command.

    python scripts/snapshot-copy.py --ref <git-ref> --out <dir>
        Extract prose as it existed at ANY commit, tag or branch. This is how
        you reach further back than the baseline -- e.g.
            --ref $(git log --format=%H --reverse -- public/index.html | head -1)
        gets the very first version of the homepage.

    python scripts/snapshot-copy.py --out <dir>
        Snapshot the current working tree to an arbitrary directory.

    python scripts/snapshot-copy.py --out docs/copy-baseline --force
        Re-freeze the baseline. Think before doing this.

Generated pages (public/events/*.html, 2,197 of them) are excluded by default:
their text comes from the pdoom-data repo, not from anyone's hand. --include-generated
overrides that.
"""

import argparse
import difflib
import re
import subprocess
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = REPO_ROOT / "public"
DEFAULT_BASELINE = REPO_ROOT / "docs" / "copy-baseline"

# Content of these elements is never shown to a reader as prose.
SKIP_CONTENT = {"script", "style", "noscript", "svg", "template"}

# Block-level elements whose text is emitted as its own line. Anything else
# (span, em, strong, code, a...) is inline and flows into the current block.
BLOCK = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "caption",
    "blockquote", "figcaption", "dt", "dd", "label", "legend", "summary",
    "button", "option", "title", "pre",
}

# Attributes that carry reader-visible copy even though they aren't text nodes.
COPY_ATTRS = [
    ("meta", "name", "description", "content"),
    ("meta", "property", "og:title", "content"),
    ("meta", "property", "og:description", "content"),
    ("input", None, None, "placeholder"),
    ("textarea", None, None, "placeholder"),
    ("img", None, None, "alt"),
]


class ProseExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []          # (kind, text)
        self._buf = []
        self._skip_depth = 0
        self._tagstack = []

    # -- helpers ----------------------------------------------------------
    def _flush(self, kind="text"):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if text:
            self.blocks.append((kind, text))

    # -- parser callbacks -------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in SKIP_CONTENT:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        d = dict(attrs)
        for etag, key, val, out in COPY_ATTRS:
            if tag != etag:
                continue
            if key is not None and d.get(key) != val:
                continue
            content = (d.get(out) or "").strip()
            if content:
                self._flush()
                label = "%s@%s" % (tag, (val or out))
                self.blocks.append((label, re.sub(r"\s+", " ", content)))
        if tag in BLOCK:
            self._flush()
        if tag == "br":
            self._buf.append(" ")
        self._tagstack.append(tag)

    def handle_endtag(self, tag):
        if tag in SKIP_CONTENT:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in BLOCK:
            self._flush(tag)
        if self._tagstack and tag in self._tagstack:
            while self._tagstack and self._tagstack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._skip_depth:
            return
        self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def extract_prose(html_text):
    """Return the reader-visible prose of an HTML document, one block per line."""
    p = ProseExtractor()
    try:
        p.feed(html_text)
        p.close()
    except Exception as exc:                      # malformed markup shouldn't abort a sweep
        return "!! PARSE ERROR: %s\n" % exc
    lines = []
    seen_consecutive = None
    for kind, text in p.blocks:
        text = unescape(text).strip()
        if not text:
            continue
        line = "[%s] %s" % (kind, text)
        # Nav/footer repeat verbatim; collapse immediate duplicates only.
        if line == seen_consecutive:
            continue
        seen_consecutive = line
        lines.append(line)
    return "\n".join(lines) + "\n"


def page_paths(include_generated=False):
    paths = sorted(
        p for p in PUBLIC.rglob("*.html")
        if include_generated or "events" not in p.relative_to(PUBLIC).parts[:1]
    )
    return [p.relative_to(REPO_ROOT).as_posix() for p in paths]


def read_at_ref(relpath, ref):
    """File content at a git ref, or None if it did not exist there."""
    try:
        out = subprocess.run(
            ["git", "show", "%s:%s" % (ref, relpath)],
            cwd=REPO_ROOT, capture_output=True, check=True)
        return out.stdout.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError:
        return None


def snapshot(out_dir, ref=None, include_generated=False, force=False):
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.rglob("*.txt")) and not force:
        print("ERROR: %s already contains a snapshot. Pass --force to overwrite."
              % out_dir, file=sys.stderr)
        print("       The baseline is meant to stay frozen -- see the module docstring.",
              file=sys.stderr)
        return 2

    if ref:
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref, "public/"],
            cwd=REPO_ROOT, capture_output=True, check=True)
        rels = sorted(
            line for line in listing.stdout.decode("utf-8").splitlines()
            if line.endswith(".html")
            and (include_generated or not line.startswith("public/events/"))
        )
    else:
        rels = page_paths(include_generated)

    written = 0
    for rel in rels:
        src = read_at_ref(rel, ref) if ref else \
            (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        if src is None:
            continue
        prose = extract_prose(src)
        dest = out_dir / (rel[len("public/"):] + ".txt")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(prose, encoding="utf-8", newline="\n")
        written += 1

    (out_dir / "README.md").write_text(
        "# Copy snapshot\n\n"
        "Reader-visible prose extracted from `public/**/*.html`, one block per\n"
        "line, generated by `scripts/snapshot-copy.py`. Markup, CSS and scripts\n"
        "are stripped so that a diff shows wording changes and nothing else.\n\n"
        "Source: %s\n\n"
        "Pages: %d (generated event pages %s)\n\n"
        "Compare the current site against this with:\n\n"
        "    python scripts/snapshot-copy.py --check\n\n"
        "Reach further back than this snapshot with `--ref <commit>`.\n"
        % (("git ref `%s`" % ref) if ref else "working tree",
           written, "included" if include_generated else "excluded"),
        encoding="utf-8", newline="\n")

    print("Wrote %d page snapshots to %s" % (written, out_dir))
    return 0


def check(baseline_dir, include_generated=False):
    baseline_dir = Path(baseline_dir)
    if not baseline_dir.exists():
        print("ERROR: no baseline at %s" % baseline_dir, file=sys.stderr)
        return 2

    changed = added = removed = 0
    for rel in page_paths(include_generated):
        name = rel[len("public/"):] + ".txt"
        base_file = baseline_dir / name
        current = extract_prose(
            (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace"))
        if not base_file.exists():
            print("\n=== ADDED PAGE: %s ===" % rel)
            added += 1
            continue
        before = base_file.read_text(encoding="utf-8")
        if before == current:
            continue
        changed += 1
        print("\n=== %s ===" % rel)
        for line in difflib.unified_diff(
                before.splitlines(), current.splitlines(),
                fromfile="baseline", tofile="current", lineterm="", n=1):
            if line.startswith(("---", "+++", "@@")):
                continue
            print("  " + line)

    for base_file in sorted(baseline_dir.rglob("*.txt")):
        rel = "public/" + base_file.relative_to(baseline_dir).as_posix()[:-4]
        if not (REPO_ROOT / rel).exists():
            print("\n=== REMOVED PAGE: %s ===" % rel)
            removed += 1

    total = changed + added + removed
    print("\n%d page(s) with copy changes, %d added, %d removed."
          % (changed, added, removed))
    if total == 0:
        print("Copy is identical to the baseline.")
    return 1 if total else 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="directory to write the snapshot into")
    ap.add_argument("--ref", help="git ref to extract from (default: working tree)")
    ap.add_argument("--check", action="store_true",
                    help="diff the working tree against the frozen baseline")
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE),
                    help="baseline directory (default: %(default)s)")
    ap.add_argument("--include-generated", action="store_true",
                    help="also snapshot the ~2,197 generated event pages")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing snapshot directory")
    args = ap.parse_args()

    if args.check:
        return check(args.baseline, args.include_generated)
    if not args.out:
        ap.error("one of --check or --out is required")
    return snapshot(args.out, args.ref, args.include_generated, args.force)


if __name__ == "__main__":
    sys.exit(main())
