#!/usr/bin/env python3
"""
Updates version information from the pdoom1 game repository
Fetches latest release info and updates website data files
"""

import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

# Windows console is cp1252; the check marks below (U+2713) would raise
# UnicodeEncodeError on the FIRST print, aborting before any work. Force UTF-8.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

GITHUB_API_BASE = 'https://api.github.com'
REPO_OWNER = 'PipFoweraker'
REPO_NAME = 'pdoom1'
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'public', 'data')


def fetch_github_data(endpoint: str) -> Optional[Dict[str, Any]]:
    """Fetch data from GitHub API"""
    url = f"{GITHUB_API_BASE}{endpoint}"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'pdoom1-website-updater')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Warning: Could not fetch {endpoint}: {e}")
        return None


def read_existing_version_json() -> Dict[str, Any]:
    """Whatever version.json currently says. Used to preserve, never to invent."""
    version_file = os.path.join(DATA_DIR, 'version.json')
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# Same filename heuristics resolveDownloads() uses in index.html. Keep the two in
# step: if the button can resolve a build for a platform, this must report that
# platform available, and vice versa.
_PLATFORM_PATTERNS = {
    # '\.exe$' catches a bare PDoom.exe (v0.13.1+ dropped "windows" from the name);
    # 'win' still catches PDoom-...-windows.zip (v0.13.0 style).
    'windows': re.compile(r'win|\.exe$', re.I),
    # '\.app(?![a-z])' not '\.app': the bare form also matches ".AppImage", so a
    # Linux-only AppImage release published platforms.macos: true. Second false
    # positive of the same kind as the x86_64 one below, in the field
    # check-platform-claims.py trusts. The lookahead still allows "Game.app" and
    # "Game.app.zip", which are the real macOS bundle shapes.
    'macos':   re.compile(r'mac|osx|darwin|\.app(?![a-z])|\.dmg', re.I),
    'linux':   re.compile(r'linux|x86_64|\.appimage', re.I),
}
_BUILD_SUFFIX = re.compile(r'\.(zip|dmg|appimage|x86_64|exe|tar\.gz)$', re.I)

# 'x86_64' is an ARCHITECTURE, not an operating system. It is in the linux pattern
# because a Godot Linux export is literally named `PDoom.x86_64`, but it also appears
# in Intel Mac and Windows build names -- `PDoom-<version>-macos-x86_64.dmg` matched
# BOTH macos and linux, so one Mac-only release would have published
# `platforms.linux: true`. check-platform-claims.py trusts this field, so that is not
# a cosmetic slip: it is the honesty guard being handed a false positive, which is
# the exact class the field was introduced to prevent.
#
# So an asset is attributed to a platform only if no OTHER platform claims it by
# name. Explicit OS names always win over an architecture hint.
_EXPLICIT_OS = {
    'windows': re.compile(r'win|\.exe$', re.I),
    # '\.app(?![a-z])' not '\.app': the bare form also matches ".AppImage", so a
    # Linux-only AppImage release published platforms.macos: true. Second false
    # positive of the same kind as the x86_64 one below, in the field
    # check-platform-claims.py trusts. The lookahead still allows "Game.app" and
    # "Game.app.zip", which are the real macOS bundle shapes.
    'macos':   re.compile(r'mac|osx|darwin|\.app(?![a-z])|\.dmg', re.I),
    'linux':   re.compile(r'linux|\.appimage', re.I),
}


def _attributable(name: str, os_key: str) -> bool:
    """True if `name` is a build for `os_key` and for no other OS."""
    if not (_PLATFORM_PATTERNS[os_key].search(name) and _BUILD_SUFFIX.search(name)):
        return False
    others = [k for k in _EXPLICIT_OS if k != os_key and _EXPLICIT_OS[k].search(name)]
    if not others:
        return True
    # Another OS is named explicitly. Yield unless THIS platform is named too --
    # a genuinely ambiguous name (e.g. "windows-and-linux.zip") is not something to
    # silently resolve, and counting it for both is the honest reading.
    return bool(_EXPLICIT_OS[os_key].search(name))


def derive_platforms(assets: List[Dict[str, Any]]) -> Dict[str, bool]:
    """Which OS builds are actually attached to the release.

    A platform is 'available' iff a matching downloadable build exists -- the one
    un-fakeable source of truth (the file is either in the release or it is not).
    Pages and the platform-claims guard read this instead of trusting hand-typed
    prose, which is what silently rots into a lie. NOTE: this is only meaningful on
    a FRESH asset list; an empty list from a failed fetch would read as 'nothing
    shipped anywhere', so callers must preserve the prior value on failure rather
    than write all-False. See get_latest_release()."""
    names = [a.get('name', '') for a in (assets or [])]
    return {
        os_key: any(_attributable(n, os_key) for n in names)
        for os_key in _PLATFORM_PATTERNS
    }


def read_platform_tracking() -> Dict[str, Any]:
    """data/platform-tracking.json -> {platform: url}, or {} if unusable.

    Missing or malformed is NOT an error: the link is an enhancement, and the
    absence sentence ("no macOS build in v0.14.3") is already true without it.
    Failing the whole version.json write over a missing nicety would take out
    the platform data that the honesty guard depends on.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'data', 'platform-tracking.json')
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"Note: no usable platform-tracking.json ({exc}); absence clauses carry no link")
        return {}
    out = {}
    for key, entry in (raw.get('platforms') or {}).items():
        url = entry.get('url') if isinstance(entry, dict) else entry
        # Only https, and only to the project's own tracker. This string is
        # written into version.json and becomes an href on the homepage.
        if isinstance(url, str) and url.startswith('https://github.com/PipFoweraker/'):
            out[key] = url
        else:
            print(f"Note: ignoring platform-tracking entry {key!r}: not a project https URL")
    return out


def get_latest_release() -> Dict[str, Any]:
    """Get latest release information"""
    data = fetch_github_data(f"/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest")

    if data and (data.get('tag_name') or data.get('name')):
        return {
            'version': data.get('tag_name') or data.get('name'),
            'name': data.get('name'),
            'published_at': data.get('published_at'),
            'html_url': data.get('html_url'),
            'body': data.get('body', ''),
            # Derived from THIS release's assets. Fresh fetch, so it is safe to
            # write; the failure branch below keeps the last known-good instead.
            'platforms': derive_platforms(data.get('assets', [])),
            # Where a reader finds out why a missing platform is missing. This dict
            # is rebuilt from the API on every successful run, so a value hand-added
            # to version.json would be silently dropped within the hour -- the link
            # has to come from a file this function reads. It asserts nothing about
            # availability: index.html only renders an entry for a platform that
            # derive_platforms() already reported as absent.
            'platform_tracking': read_platform_tracking(),
        }

    # API failed. This function's output is written straight into version.json, which
    # every page treats as the source of truth -- a literal fallback here would
    # overwrite a correct version with an ancient one at exactly the moment nobody is
    # watching. Keep whatever is already on disk; if there is nothing, stop.
    existing = read_existing_version_json().get('latest_release')
    if isinstance(existing, dict) and existing.get('version'):
        print(f"Warning: release lookup failed; preserving existing version {existing['version']}")
        return existing
    raise RuntimeError(
        'Could not fetch the latest release and no usable latest_release exists in '
        'version.json. Refusing to write a guessed version.'
    )


def search_total(query: str) -> Optional[int]:
    """The number of things matching a GitHub search, or None for UNKNOWN.

    None is a real answer here and must never be coerced to 0. A search that
    failed and a search that found nothing are different facts, and only one of
    them is safe to render.
    """
    data = fetch_github_data(f"/search/issues?q={query}&per_page=1")
    if not isinstance(data, dict):
        return None
    total = data.get('total_count')
    return total if isinstance(total, int) else None


def get_repo_stats() -> Dict[str, Any]:
    """Get repository statistics.

    THE FIELD NAME IS NOT THE MEASUREMENT. GitHub's `open_issues_count`
    INCLUDES OPEN PULL REQUESTS -- documented behaviour at their end, not a bug
    at ours. This function used to copy it straight into `open_issues`, and
    public/index.html renders that value beside the words "open issues".
    Measured against the live repo on 2026-08-25: 210 issues + 1 PR = 211,
    which the homepage would have published as "211 open issues".

    So the upstream number keeps the honest name `open_issues_and_prs`, and
    `open_issues` comes from the search API, which can actually answer the
    question the label asks. Rationale and two sibling instances:
    coordination/NOTE_2026-08-25_the-field-name-is-not-the-measurement.md
    """
    data = fetch_github_data(f"/repos/{REPO_OWNER}/{REPO_NAME}")

    if data:
        # NOT carried forward from disk on failure, unlike every other field in
        # this file. A version is stable, so a stale one is merely old; a COUNT
        # moves, so a stale one is a false claim about today wearing a fresh
        # timestamp. None renders as the em dash the markup already shows before
        # any fetch resolves -- verified in both consumers: index.html's
        # _setStatus() maps null to an em dash, and game-stats' measured() gate
        # rejects null before Number() can coerce it to 0.
        issues_only = search_total(
            f"repo:{REPO_OWNER}/{REPO_NAME}+is:open+is:issue")
        if issues_only is None:
            print('Warning: issues-only search failed; publishing open_issues=null '
                  '(UNKNOWN). Pages must render this as an em dash, never as zero.')
        return {
            'stars': data.get('stargazers_count', 0),
            'forks': data.get('forks_count', 0),
            'open_issues': issues_only,
            'open_issues_and_prs': data.get('open_issues_count', 0),
            'last_updated': data.get('updated_at')
        }

    # Same rule as the release lookup: zeroes are a claim ("this project has no stars"),
    # not an absence of one. Preserve the last known-good stats instead of asserting.
    existing = read_existing_version_json().get('repository_stats')
    if isinstance(existing, dict) and existing:
        print('Warning: repo stats lookup failed; preserving existing repository_stats')
        return existing
    raise RuntimeError(
        'Could not fetch repository stats and none exist in version.json. '
        'Refusing to publish zeroes as if they were measured.'
    )


def update_version_data() -> Dict[str, Any]:
    """Update version data file"""
    print('Fetching version information...')
    
    release = get_latest_release()
    stats = get_repo_stats()
    
    version_data: Dict[str, Any] = {
        'latest_release': release,
        'repository_stats': stats,
        'last_updated': datetime.now().isoformat(),
    }

    # game_stats is NOT this script's to write. It used to hardcode
    # baseline_doom_percent: 23, frontier_labs_count: 7, strategic_possibilities: 10000
    # -- three invented numbers published under a confident label, which is the exact
    # thing calculate-game-stats.py was rewritten to stop ("DO NOT restore a literal
    # here 'temporarily'. That is exactly how these two survived for months.").
    # Because both scripts write the same file, re-asserting the literals here undid
    # that fix on every run where this script happened to go last: the honest `null`
    # and its `pending` explanation were silently replaced with a number.
    # Carry forward whatever the calculator last derived; if it has never run, omit
    # the key entirely so a reader sees nothing rather than a fiction.
    existing_stats = read_existing_version_json().get('game_stats')
    if existing_stats:
        version_data['game_stats'] = existing_stats


    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Write version data
    version_file = os.path.join(DATA_DIR, 'version.json')
    with open(version_file, 'w', encoding="utf-8") as f:
        json.dump(version_data, f, indent=2)
    
    print(f"✓ Version data updated: {release['version']}")
    print(f"✓ Written to: {version_file}")
    
    return version_data


def sync_status_json(version_data: Dict[str, Any]) -> None:
    """Keep public/data/status.json's game release block in sync with the canonical
    release so it can't drift from version.json. Only refreshes the game release facts
    and timestamp; it does NOT touch website.version (that is a separate, deliberate bump).
    Guarded so a failed GitHub fetch (which falls back to a stale placeholder) cannot
    clobber status.json: a real release URL contains '/releases/tag/'."""
    release = version_data['latest_release']
    html_url = release.get('html_url', '')
    if '/tag/' not in html_url:
        print('Skipping status.json sync (release lookup used fallback, not a real release)')
        return

    status_file = os.path.join(DATA_DIR, 'status.json')
    if not os.path.exists(status_file):
        return

    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)
    except Exception as e:
        print(f"Warning: could not read status.json, skipping sync: {e}")
        return

    published = release.get('published_at') or ''
    release_date = published.split('T')[0] if published else ''

    game = status.setdefault('game', {})
    latest = game.setdefault('latestRelease', {})
    latest['version'] = release['version']
    if release_date:
        latest['date'] = release_date
    latest.setdefault(
        'downloadUrl',
        f'https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest',
    )
    latest.setdefault('changelog', 'See CHANGELOG.md for details')
    game.setdefault('development', {})['progress'] = f"{release['version']} released"
    game['lastUpdated'] = datetime.now().isoformat()

    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2)

    print(f"✓ Synced status.json game release to {release['version']}")


def update_download_links(version_data: Dict[str, Any]) -> None:
    """Update download links in index.html to use dynamic version"""
    index_file = os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')
    
    if not os.path.exists(index_file):
        print('index.html not found, skipping link updates')
        return
    
    # newline='' so an existing CRLF file round-trips unchanged. Without it, a
    # Windows run rewrites every line ending in index.html and the diff is the whole
    # file -- the same trap sync-events.py pins with newline='\n'.
    with open(index_file, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    version = version_data['latest_release']['version']

    # The version string is a GitHub tag_name -- upstream data, not ours. Two things
    # follow, and the old code got both wrong:
    #
    #  1. In re.sub() the third argument is a REPLACEMENT TEMPLATE, not a literal.
    #     A tag containing \1, \g<0> or a lone backslash was interpreted, and a bad
    #     escape raised re.error, so a mistyped tag could rewrite or crash the
    #     homepage. Passing a function makes the replacement literal by construction.
    #  2. It lands in HTML, so it is escaped. A tag is not allowed to open an element
    #     on the front page.
    safe = html.escape(version, quote=True)

    content = re.sub(r'Download Latest Release', lambda _m: f'Download {safe} (Latest)', content)
    content = re.sub(r'Download v[\d\.]+', lambda _m: f'Download {safe}', content)

    with open(index_file, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    
    print(f"✓ Updated download links to {version}")


if __name__ == '__main__':
    try:
        version_data = update_version_data()
        sync_status_json(version_data)
        update_download_links(version_data)
        print('Version update complete!')
    except Exception as error:
        print(f'Error updating version: {error}')
        exit(1)