#!/usr/bin/env python3
"""Derive game_stats.frontier_labs_count from the published frontier-labs roster.

WHAT THIS USED TO DO, AND WHY IT WAS WRONG
------------------------------------------
The previous implementation held a hardcoded list of ~20 lab names inside this
file, substring-searched public/index.html for each of them, and returned
``max(len(matches), 5)`` -- with a bare ``return 7`` if the homepage was missing.

Three separate ways to publish a number nobody can interrogate:

1. The list was invisible. A reader of pdoom1.com could not see what was being
   counted, so the number was unfalsifiable.
2. The floor. ``max(..., 5)`` meant that when the count came out lower, the
   published figure was the floor and not a count. It had in fact settled on
   exactly 5 -- the floor -- in public/data/version.json.
3. The literal fallback. ``return 7`` shipped precisely when the real lookup
   failed, which is the failure mode CLAUDE.md singles out: "a default value
   ships precisely when the real lookup failed."

WHAT IT DOES NOW
----------------
Counts rows in ``public/data/frontier-labs.json`` -- a file that is served to
readers, linked from /frontier-labs/, and whose inclusion boundary is written
out in prose at /frontier-labs/#definition. The count is
``roster.labs where kind == "real" and status == "active"``, which is the same
expression /frontier-labs/ evaluates in the browser, so the page and the
published stat cannot disagree.

There is no floor and no fallback literal. If the roster cannot be read, this
script raises and version.json keeps whatever it already had -- a stale figure
that is visibly stale beats a fresh figure that is invented.

Baseline p(Doom) and "strategic possibilities" are NOT derived and are NOT
literals either. They ship as ``null`` beside a ``pending`` block naming what
each one still needs, because they are owned by the game's calibration emit and
not by this repo, and an invented number under a confident label is worse than a
visible gap. See pdoom1-website#177. Do not restore a literal for either one.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, 'public', 'data')
ROSTER_FILE = os.path.join(DATA_DIR, 'frontier-labs.json')
VERSION_FILE = os.path.join(DATA_DIR, 'version.json')


def load_roster() -> Dict[str, Any]:
    """Read the roster. Raise rather than return a guess."""
    if not os.path.exists(ROSTER_FILE):
        raise RuntimeError(
            f'Frontier-labs roster not found at {ROSTER_FILE}. Refusing to publish a '
            'lab count that is not derived from a roster a reader can inspect.'
        )
    with open(ROSTER_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def count_frontier_labs(roster: Dict[str, Any]) -> int:
    """Count real, active labs on the roster.

    Deliberately the same predicate as the one /frontier-labs/ applies in the
    browser. Hypothetical entries are excluded: a modelling parameter is not an
    organisation, and summing the two is how this page's old headline figure of
    7 was produced out of six real labs.
    """
    labs = (roster.get('roster') or {}).get('labs')
    if not isinstance(labs, list):
        raise RuntimeError(
            'Roster file has no roster.labs list -- shape changed? Refusing to guess a count.'
        )

    real_active = [
        lab for lab in labs
        if lab.get('kind') == 'real' and lab.get('status') == 'active'
    ]

    if not real_active:
        raise RuntimeError(
            'Roster contains no real, active labs. That is almost certainly a data '
            'error rather than the truth, so this is a failure, not a zero.'
        )

    print(f'Roster: {len(labs)} row(s), {len(real_active)} real and active:')
    for lab in real_active:
        print(f"  - {lab.get('name')} (founded {lab.get('founded')})")

    omissions = roster.get('known_omissions') or []
    if omissions:
        print(f'Known omissions not counted ({len(omissions)}): '
              + ', '.join(str(o.get('name')) for o in omissions))

    hypo = roster.get('hypothetical') or []
    if hypo:
        print(f'Hypothetical entries excluded from the count ({len(hypo)}): '
              + ', '.join(str(h.get('name')) for h in hypo))

    return len(real_active)


def read_existing_version() -> Dict[str, Any]:
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def update_game_stats() -> Dict[str, Any]:
    """Write the derived count into version.json, preserving everything else."""
    roster = load_roster()
    frontier_count = count_frontier_labs(roster)

    version_data = read_existing_version()
    if not version_data:
        print('version.json not found; creating a minimal structure')
        version_data = {}

    game_stats: Dict[str, Any] = version_data.get('game_stats') or {}

    # baseline_doom_percent and strategic_possibilities used to ship here as the literals
    # 23 and 10000, commented "Keep stubbed for now". They rendered on three reader-facing
    # pages as "23%" under the label "Baseline Doom" and "10k+" under "Strategic
    # Possibilities" -- presented to a visitor as measurements of the game, with nothing
    # on the page marking them as invented. Nobody ever measured either one.
    #
    # They are now emitted as null, with the reason and the tracking issue alongside, and
    # the pages render "not yet measured" rather than a number. A stat we have not taken
    # is not a small inaccuracy: on a site whose entire pitch is that it does not lie to
    # you, an invented number under a confident label is the whole credibility gone.
    #
    # DO NOT restore a literal here "temporarily". That is exactly how these two survived
    # for months. If a value cannot be derived, it stays null and says so.
    #
    # frontier_labs_count is the one stat here that IS derived -- from the roster below,
    # by a predicate the page evaluates too -- so it is a number rather than a null, and
    # it is deliberately absent from `pending`.
    game_stats['baseline_doom_percent'] = None
    game_stats['strategic_possibilities'] = None
    game_stats['pending'] = {
        'baseline_doom_percent': {
            'status': 'not yet measured',
            'needs': "the game's calibration emit -- baseline doom is a property of "
                     "the simulation, so only pdoom1 can measure it",
            'tracking': 'https://github.com/PipFoweraker/pdoom1-website/issues/177',
        },
        'strategic_possibilities': {
            'status': 'not yet measured',
            'needs': 'a real count derived from the shipped action/upgrade content, '
                     'which lives in the game repo and is not fetchable here yet',
            'tracking': 'https://github.com/PipFoweraker/pdoom1-website/issues/177',
        },
    }

    game_stats['frontier_labs_count'] = frontier_count
    game_stats['frontier_labs_source'] = {
        'file': '/data/frontier-labs.json',
        'predicate': 'roster.labs where kind == "real" and status == "active"',
        'definition_version': roster.get('definition_version'),
        'definition_ref': roster.get('definition_ref'),
        'roster_status': (roster.get('roster') or {}).get('status'),
        'completeness': (roster.get('roster') or {}).get('completeness'),
        'known_omissions': len(roster.get('known_omissions') or []),
    }
    game_stats['last_calculated'] = datetime.now().isoformat()

    version_data['game_stats'] = game_stats
    version_data['last_updated'] = datetime.now().isoformat()

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(version_data, f, indent=2)

    print(f'Updated frontier_labs_count to: {frontier_count}')
    print(f'Saved to: {VERSION_FILE}')

    return version_data


if __name__ == '__main__':
    try:
        update_game_stats()
        print('Game stats calculation complete.')
    except Exception as error:  # noqa: BLE001 - surface the reason, then fail
        print(f'Error calculating game stats: {error}', file=sys.stderr)
        sys.exit(1)
