#!/usr/bin/env python
"""Serve two git refs of the site side by side for visual A/B comparison.

Reviewing a large visual change by reading a diff does not work. This checks out
a second ref into a git worktree and serves both on adjacent ports, so the same
page can be opened in two tabs and flipped between.

    python scripts/ab-preview.py                     # main (B) vs current branch (A)
    python scripts/ab-preview.py --base v0.2.0
    python scripts/ab-preview.py --stop              # tear down the worktree

A is always the CURRENT working tree, so uncommitted edits show up immediately
-- change a colour, hit refresh, compare. B is a clean checkout of the base ref.

Ctrl-C stops the servers. The worktree persists until --stop, so restarting is
instant.
"""

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKTREE = REPO_ROOT.parent / ("%s-ab-base" % REPO_ROOT.name)
PORT_A, PORT_B = 5173, 5174

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=check,
                          capture_output=True, text=True)


def stop():
    if WORKTREE.exists():
        git("worktree", "remove", "--force", str(WORKTREE), check=False)
        print("Removed worktree %s" % WORKTREE)
    else:
        print("No worktree to remove.")
    git("worktree", "prune", check=False)


def serve(directory, port, label):
    handler = functools.partial(QuietHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    httpd.allow_reuse_address = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print("  %-28s http://localhost:%d/" % (label, port))
    return httpd


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # one line per asset across 2,000 pages is not useful


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="main",
                    help="ref to compare AGAINST (default: %(default)s)")
    ap.add_argument("--stop", action="store_true", help="remove the worktree and exit")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = ap.parse_args()

    if args.stop:
        stop()
        return 0

    # Refresh the base worktree so it always reflects the requested ref.
    if WORKTREE.exists():
        git("worktree", "remove", "--force", str(WORKTREE), check=False)
    git("worktree", "prune", check=False)
    r = git("worktree", "add", "--detach", str(WORKTREE), args.base, check=False)
    if r.returncode != 0:
        print("ERROR: could not create worktree for %r:\n%s"
              % (args.base, r.stderr), file=sys.stderr)
        return 2

    current = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    print("\nA/B preview")
    print("=" * 58)
    serve(REPO_ROOT / "public", PORT_A, "A  %s (working tree)" % current)
    serve(WORKTREE / "public", PORT_B, "B  %s" % args.base)
    print("=" * 58)
    print("\nA is your working tree -- edit a file, refresh, compare.")
    print("Worth flipping between: /  /blog/  /dashboard/  /design-notes/")
    print("                        /privacy/  /docs/  /leaderboard/")
    print("                        /events/<any>.html   (the 2,194 rethemed pages)")
    print("\nCtrl-C to stop serving. Worktree persists; --stop to remove it.\n")

    if not args.no_open:
        webbrowser.open("http://localhost:%d/" % PORT_A)
        webbrowser.open("http://localhost:%d/" % PORT_B)

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nStopped. Worktree left at %s (--stop to remove)." % WORKTREE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
