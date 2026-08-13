#!/usr/bin/env python3
"""
Weekly League Management System for p(Doom)1 Website

This script manages the weekly league competition system:
1. Generate weekly competitive seeds
2. Manage league resets and archival
3. Track weekly standings and statistics
4. Handle season management

Usage:
    python scripts/weekly-league-manager.py --status          # Show current league status
    python scripts/weekly-league-manager.py --new-week        # Start new weekly league
    python scripts/weekly-league-manager.py --archive-week    # Archive current week
    python scripts/weekly-league-manager.py --generate-seed   # Generate new competitive seed
"""

import json
import argparse
import sys
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import random

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass


# --- League week geometry -------------------------------------------------
#
# A league week runs Friday 00:00:00 -> Thursday 23:59:59 **in Hobart**.
#
# Two rulings produced that shape:
#
#   1. pdoom1/docs/RELEASE_NOMENCLATURE.md is canonical on the cadence:
#      "Seed -- weekly (every Fri) -- a fresh board on UNCHANGED rules (new
#      `seed`, same `ladder_version`)". The website ran a Monday->Sunday week
#      with a Sunday rollover, i.e. two days out of phase with the game's own
#      spec, for its whole life.
#   2. Pip, 2026-07-28: "Everything is going to be based off Hobart time,
#      AEST. The rest of the world can deal with it."
#
# Hobart is NOT a fixed offset. Tasmania observes daylight saving: UTC+10
# (AEST) in winter, UTC+11 (AEDT) from early October to early April. So the
# week boundary is defined in the *zone*, never in an offset -- see league_tz().
#
# The cron (.github/workflows/weekly-league-reset.yml) fires Thursday 14:00 UTC,
# which is:
#     winter  Thu 2026-07-30 14:00Z -> Fri 2026-07-31 00:00 +10:00  (week start)
#     summer  Thu 2026-11-26 14:00Z -> Fri 2026-11-27 01:00 +11:00  (1h in)
# Always a Friday in Hobart, in both halves of the year, and never EARLIER than
# the week start -- so the run always lands inside the week it opens. That is
# the whole point: the cron is only a trigger, correctness lives in
# league_week_start(), so a DST shift cannot move the answer. GitHub cron can
# run late (which is harmless here, it lands further into the same week) but
# never early.
#
# This replaces the shipped bug (docs/TECH_DEBT.md A9): the old
# get_current_week_info() derived everything from `now`, so the Sunday-14:00 run
# re-created the week that was about to *end* -- on 2026-07-26T14:28Z it wrote
# 2026_W30 (2026-07-20 -> 2026-07-26) as the brand-new "current" week, ten hours
# before that week expired. Ten weeks of green checkmarks, every one a week late.
# Pinned by scripts/test-weekly-league-boundary.py.
LEAGUE_TZ_NAME = "Australia/Hobart"
ANCHOR_WEEKDAY = 4          # datetime.weekday(): Mon=0 ... Fri=4, in LEAGUE_TZ_NAME
ROLLOVER_HOUR_UTC = 14      # cron hour; must match weekly-league-reset.yml
ROLLOVER_CRON_DOW = 4       # cron day-of-week numbering: 0=Sun ... 4=Thu

_TZ_CACHE = []


def league_tz():
    """The IANA zone the league week is anchored to. Raises, never guesses.

    zoneinfo ships no tz database on Windows -- ZoneInfo("Australia/Hobart")
    raises ZoneInfoNotFoundError until `pip install tzdata` (it is pinned in
    requirements.txt). That failure mode is asymmetric and nasty: CI passes on
    ubuntu-latest while the same code dies on Pip's box.

    A fallback to a fixed +10:00 is deliberately NOT offered. Hobart is +10 in
    winter and +11 under daylight saving, so a hardcoded offset would silently
    move every rollover by an hour for ~half the year -- which is the exact bug
    class this module exists to eliminate. A loud crash is the cheap outcome.
    """
    if _TZ_CACHE:
        return _TZ_CACHE[0]
    try:
        from zoneinfo import ZoneInfo
    except ImportError as e:  # pragma: no cover - Python < 3.9
        raise RuntimeError(
            f"The league week is anchored to {LEAGUE_TZ_NAME} and this interpreter "
            f"has no zoneinfo module ({e}). Python 3.9+ is required."
        )
    try:
        tz = ZoneInfo(LEAGUE_TZ_NAME)
    except Exception as e:
        raise RuntimeError(
            f"Cannot resolve the league timezone {LEAGUE_TZ_NAME!r}: {e}\n"
            "  Fix: pip install tzdata   (it is in requirements.txt)\n"
            "  Why this is fatal rather than falling back to UTC+10: Hobart is "
            "UTC+10 (AEST) in winter and UTC+11 (AEDT) from October to April, so a "
            "hardcoded offset would put the weekly rollover an hour off the "
            "anchor for half of every year, silently."
        )
    _TZ_CACHE.append(tz)
    return tz


# --- Ladder epoch ---------------------------------------------------------
#
# Everything opened before the L2 -> L3 ladder fork is deliberately-labelled
# anomalous pre-history, not silently buried. See docs/LEAGUE_EPOCH_ANOMALY.md.
#
# The boundary is NOT a literal in this file. It lives in
# public/data/ladder-epochs.json with its source cited, because it has already
# moved twice in two days and because Pip's standing rule (2026-07-29) is
# "Let's keep using variables and not hardcoding things where we can!".
#
# The reason it is a fork and not a date: L3 removed the action-point pool
# entirely in favour of an attention economy, plus office lease/lock-in, four-way
# founder hours, six previously-inert upgrades and a quirk rebalance. Scores set
# under the old rules cannot be ranked against scores set under the new ones --
# which is exactly why `ladder_version` is part of the board key. The board key
# is `(seed, L<n>)`, literally "L3"; the build version never touches it.
# (Authoritative: pdoom1 on pdoom1-website#151, 2026-07-28T23:13Z. That comment
# supersedes RELEASE_NOMENCLATURE.md's calendar row for this cut -- the ladder
# forked mid-month rather than on the first Friday.)
#
# A week is pre-epoch iff it STARTS before the boundary.
EPOCH_PRE_ID = "pre-regularisation"
EPOCH_POST_ID = "regularised"
EPOCH_DOC = "docs/LEAGUE_EPOCH_ANOMALY.md"
LADDER_CONTRACT_REL = "public/data/ladder-epochs.json"

_CONTRACT_CACHE = []


def ladder_contract() -> Dict[str, Any]:
    """The ladder/epoch contract from public/data/ladder-epochs.json.

    Raises rather than falling back to a literal. CLAUDE.md: "Fallback literals
    are the dangerous ones. A default value ships precisely when the real lookup
    failed." A wrong epoch boundary mislabels which scores are comparable, which
    is the one thing the ladder split exists to prevent.
    """
    if _CONTRACT_CACHE:
        return _CONTRACT_CACHE[0]
    path = Path(__file__).parent.parent / LADDER_CONTRACT_REL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(
            f"Cannot read the ladder/epoch contract {path}: {e}. Refusing to guess a "
            "boundary -- see docs/LEAGUE_EPOCH_ANOMALY.md."
        )
    cut = data.get("regularised_from")
    if not isinstance(cut, dict):
        raise RuntimeError(f"{path} has no `regularised_from` object")
    for key in ("ladder_version", "boundary_local", "boundary_tz",
                "reason_pre", "reason_post"):
        if not cut.get(key):
            raise RuntimeError(f"{path} -> regularised_from.{key} is missing or empty")
    if cut["boundary_tz"] != LEAGUE_TZ_NAME:
        raise RuntimeError(
            f"{path} anchors the boundary to {cut['boundary_tz']!r} but the league week "
            f"is anchored to {LEAGUE_TZ_NAME!r}. Two clocks, one boundary -- refusing."
        )
    _CONTRACT_CACHE.append(data)
    return data


def epoch_boundary() -> datetime:
    """The ladder-fork instant, resolved in the league zone.

    The offset written in the contract file is CHECKED against the real tz
    database rather than trusted: a hand-edited "+11:00" on a July date would
    otherwise move the boundary an hour without anyone noticing.
    """
    cut = ladder_contract()["regularised_from"]
    raw = cut["boundary_local"]
    try:
        stated = datetime.fromisoformat(raw)
    except ValueError as e:
        raise RuntimeError(f"regularised_from.boundary_local is not ISO-8601: {raw!r} ({e})")
    if stated.tzinfo is None:
        raise RuntimeError(
            f"regularised_from.boundary_local must carry its offset, got {raw!r}"
        )
    resolved = stated.replace(tzinfo=None).replace(tzinfo=league_tz())
    if resolved.utcoffset() != stated.utcoffset():
        raise RuntimeError(
            f"regularised_from.boundary_local says {raw!r}, but {LEAGUE_TZ_NAME} is at "
            f"{resolved.utcoffset()} at that local time. Fix the file, not the zone."
        )
    return resolved


def board_opens() -> Optional[datetime]:
    """When the board for the current epoch actually starts accepting scores.

    Deliberately separate from epoch_boundary(): the week is labelled from its
    own anchor, but a player could not submit until the board opened ~17 hours
    later. Returning it lets pages say so instead of implying midnight.
    """
    cut = ladder_contract()["regularised_from"]
    raw = cut.get("board_opens_local")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def ladder_version_for(week_start: datetime) -> str:
    """The ladder epoch a week beginning at `week_start` actually ran under.

    NOT the frontier. `regularised_from.ladder_version` is the epoch a NEW week
    opens on and it moves at every fork; a week that has already run keeps the
    epoch it was played under, because that half of the board key is the whole
    reason scores either side of a fork are not comparable.

    Reading the frontier for every week is a live history-rewrite, not a
    hypothetical one: stamp-league-epoch.py restamps all 45 weekly records from
    this contract on every rollover, so bumping the frontier L3 -> L4 without
    this function would have relabelled the closed L3 weeks as L4 -- the same
    class as the composed key #293 published, and forbidden by TECH_DEBT section
    E ("restamping the v0.4.1 records is forbidden").

    Resolved from epochs[].boundary_local: the latest epoch whose boundary is at
    or before the week's start. An epoch with no boundary_local (L1, L2 -- both
    pre-regularisation, where no week is stamped with a ladder version anyway)
    is skipped. Falls back to boundary_ladder_version, never to the frontier.
    """
    contract = ladder_contract()
    ws = as_utc(week_start)
    best: Optional[tuple] = None
    for e in (contract.get("epochs") or []):
        raw, lv = e.get("boundary_local"), e.get("ladder_version")
        if not raw or not lv:
            continue
        try:
            stated = datetime.fromisoformat(raw)
        except ValueError:
            raise RuntimeError(
                f"{LADDER_CONTRACT_REL} -> epochs[] entry {lv} has a "
                f"boundary_local that is not ISO-8601: {raw!r}")
        if stated.tzinfo is None:
            raise RuntimeError(
                f"{LADDER_CONTRACT_REL} -> epochs[] entry {lv} boundary_local "
                f"must carry its offset, got {raw!r}")
        b = as_utc(stated)
        if b <= ws and (best is None or b > best[0]):
            best = (b, lv)
    if best is not None:
        return best[1]
    cut = contract["regularised_from"]
    return cut.get("boundary_ladder_version") or cut["ladder_version"]

# The seed this script derives is NOT the competitive seed. docs/LEAGUE_SEED_LEDGER.md
# is explicit: "The seed is not a free website-side choice" -- the canonical key is
# whatever the shipped client POSTs, blessed by Pip in the ledger. This script's
# `weekly_<week_id>_<hash>` values have never matched that and no client has ever used
# one. Every record therefore carries its own disclaimer, so nothing downstream can
# mistake a derived value for a blessed one the way `league_2026-07_7d6ced29` was
# mistaken on 2026-07-24.
#
# When a blessed seed EXISTS it goes in public/data/ladder-epochs.json ->
# regularised_from.seed and seed_for_week() uses it instead of deriving. It is null
# there on purpose right now: the L3 seed is drawn at a ceremony ~1645 AEST Fri
# 2026-07-31 and pdoom1 asked explicitly that nothing hardcode it beforehand.
SEED_PROVENANCE_UNBLESSED = {
    "blessed": False,
    "derivation": "sha256('pdoom1_weekly_<week_id>_<season>')[:8], website-side",
    "canonical_source": "the shipped game client, recorded in docs/LEAGUE_SEED_LEDGER.md",
    "note": (
        "Placeholder. Do NOT present this to players as the competitive seed. The board "
        "key scores are actually submitted under is blessed in docs/LEAGUE_SEED_LEDGER.md; "
        "a seed that is not in that ledger routes submissions to a board nobody displays, "
        "with no error shown to the player. The live score API has NO key validation -- a "
        "wrong seed or version returns ok:true with an empty board (verified 2026-07-29), "
        "so a bad key is indistinguishable from nobody having played."
    ),
}


def seed_for_week(derived: str) -> Dict[str, Any]:
    """`{seed, seed_provenance}` -- the blessed value if one exists, else the
    derived placeholder, always labelled with which it is."""
    contract = ladder_contract()
    cut = contract["regularised_from"]
    source = (contract.get("sources") or [{}])[0].get("where")
    blessed = cut.get("seed")
    if blessed:
        return {
            "seed": blessed,
            "seed_provenance": {
                "blessed": True,
                "ladder_version": cut["ladder_version"],
                "board_key": f"({blessed}, {cut['ladder_version']})",
                "canonical_source": (
                    "the shipped game client; blessed in docs/LEAGUE_SEED_LEDGER.md and "
                    f"copied into {LADDER_CONTRACT_REL}"
                ),
                "source": source,
            },
        }
    return {
        "seed": derived,
        "seed_provenance": dict(
            SEED_PROVENANCE_UNBLESSED,
            seed_status=cut.get("seed_status", "unblessed"),
            ladder_version=cut["ladder_version"],
            board_key_shape=(contract.get("board_key") or {}).get("shape"),
        ),
    }


def as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to UTC. Naive input is *assumed* UTC.

    The old code called datetime.now() (naive local time). On a GitHub runner
    that is UTC by accident, on Pip's Windows box it is AEST -- a 10h skew, which
    is exactly the distance between the rollover instant and the Hobart midnight
    it is meant to sit on.
    """
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso_z(dt: datetime) -> str:
    """UTC ISO-8601 with a trailing Z.

    The old code wrote `datetime.now().isoformat() + "Z"` -- naive LOCAL time
    with a UTC suffix bolted on, i.e. every archived timestamp on a non-UTC
    machine is off by the local offset while claiming to be UTC.
    """
    return as_utc(dt).isoformat().replace("+00:00", "Z")


def league_week_start(now: datetime) -> datetime:
    """Friday 00:00:00 Australia/Hobart opening the league week containing `now`.

    Note what is NOT here: no look-ahead, no "if it is rollover o'clock, jump to
    next week". The cron fires at or just after the Hobart Friday midnight, so
    the week a run operates on is simply the week that contains the run. Removing
    the look-ahead removes the thing that went wrong in A9.

    Arithmetic is done on the local *date*, not by subtracting a timedelta from an
    aware datetime: absolute arithmetic across a DST change lands on 23:00 or
    01:00 of the wrong day. Hobart's transitions are at 02:00/03:00 on a Sunday,
    so a Friday 00:00 is never a skipped or repeated local time -- but doing the
    arithmetic on dates means that stays true even if the rule ever moves.
    """
    local = as_utc(now).astimezone(league_tz())
    days_since_anchor = (local.weekday() - ANCHOR_WEEKDAY) % 7
    start_day = local.date() - timedelta(days=days_since_anchor)
    return datetime.combine(start_day, time(0, 0, 0), tzinfo=league_tz())


def league_week_end(week_start: datetime) -> datetime:
    """Last instant of the league week: Thursday 23:59:59 Australia/Hobart.

    Derived from the NEXT anchor rather than from a fixed 6d23h59m59s span,
    because the absolute length of a Hobart week is 7 days +/- 1 hour across the
    two DST transitions. The wall-clock span is always exactly one week minus a
    second; the elapsed-seconds span is not, and asserting that it is would be a
    lie twice a year.
    """
    tz = week_start.tzinfo or league_tz()
    next_start = datetime.combine(week_start.date() + timedelta(days=7),
                                  time(0, 0, 0), tzinfo=tz)
    return next_start - timedelta(seconds=1)


def week_id_for(week_start: datetime) -> str:
    """`YYYY_Www` label for a league week, from the ISO week of its Thursday.

    ISO 8601 numbers a week by the year and week containing its Thursday; a
    Friday-to-Thursday league week contains exactly one Thursday (its last day),
    so applying the same rule keeps the label unique and strictly increasing week
    over week, and keeps the W53 -> W01 straddle correct (Fri 2026-12-25 ->
    2026_W53, Fri 2027-01-01 -> 2027_W01).

    Transition note: the old Monday-anchored geometry used the same label space
    shifted by two days, so the Friday week of 2026-07-24 would also be called
    2026_W31 -- the id already taken by the last Monday-anchored week. That week
    is never materialised (the switch happens at the 2026-07-30 rollover, which
    opens the Friday week of 2026-07-31 = 2026_W32), but the overlap is real and
    is why archives before and after the switch must not be compared by id.
    """
    iso_year, iso_week, _ = (week_start.date() + timedelta(days=6)).isocalendar()
    return f"{iso_year}_W{iso_week:02d}"


def epoch_for(week_start: datetime) -> Dict[str, Any]:
    """Machine-readable ladder-epoch stamp for a week beginning at `week_start`."""
    contract = ladder_contract()
    cut = contract["regularised_from"]
    boundary = epoch_boundary()
    anomalous = as_utc(week_start) < as_utc(boundary)
    stamp = {
        "id": EPOCH_PRE_ID if anomalous else EPOCH_POST_ID,
        "anomalous": anomalous,
        # The ladder version IS the board key's second element. Recorded on both
        # sides of the fork so a reader never has to infer it from a date.
        #
        # Resolved PER WEEK, not from the frontier: a closed L3 week must keep
        # saying L3 after the ladder forks to L4. See ladder_version_for().
        "ladder_version": None if anomalous else ladder_version_for(week_start),
        "boundary_ladder_version": cut.get("boundary_ladder_version")
                                   or cut["ladder_version"],
        "boundary_local": boundary.isoformat(),
        "boundary_tz": LEAGUE_TZ_NAME,
        "boundary_utc": as_utc(boundary).isoformat().replace("+00:00", "Z"),
        "reason": cut["reason_pre"] if anomalous else cut["reason_post"],
        "see": EPOCH_DOC,
        "source": (contract.get("sources") or [{}])[0].get("where"),
    }
    if not anomalous:
        # A regularised week is labelled from its own Friday anchor, but the
        # board did not open until later that day. Say so in the record rather
        # than letting the week's start imply the board was live.
        opens = board_opens()
        if opens is not None:
            stamp["board_opens_local"] = opens.isoformat()
            stamp["board_opens_utc"] = as_utc(opens).isoformat().replace("+00:00", "Z")
            stamp["board_opens_confirmed"] = bool(cut.get("board_opens_confirmed"))
    return stamp


class WeeklyLeagueManager:
    """Manages weekly league competitions for p(Doom)1."""
    
    def __init__(self):
        self.website_dir = Path(__file__).parent.parent
        self.version_file = self.website_dir / "public" / "data" / "version.json"
        self.league_data_dir = self.website_dir / "public" / "leaderboard" / "data" / "weekly"
        self.current_league_file = self.league_data_dir / "current.json"
        self.archive_dir = self.league_data_dir / "archive"
        self.config_file = self.website_dir / "scripts" / "weekly-league-config.json"
        
        # Ensure directories exist
        self.league_data_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load weekly league configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"WARNING: Failed to load config: {e}")
        
        # Default configuration
        return {
            "current_season": "2025_Q4",
            "league_start_date": "2025-10-07",  # First Monday of league
            "seed_generation_method": "deterministic",
            "archive_policy": "keep_all",
            "max_entries_per_week": 1000,
            "competition_timezone": LEAGUE_TZ_NAME,
            "league_reset_day": "Friday",
            "league_reset_time": "00:00",
            "auto_reset_enabled": False,
            "created": datetime.now().isoformat()
        }
    
    def get_game_version(self) -> str:
        """Read the deployed game version from public/data/version.json.

        This is a RECORD STAMP -- which build produced the file -- and is NOT part
        of the board key. Boards are keyed `(seed, ladder_version)`, literally
        `L3`; pdoom1 on #151 (2026-07-28): "the build version no longer touches
        the board key at all -- that was the whole point of the build-vs-ladder
        split. A cosmetic patch bump will never again fork a board." Under the old
        `(seed, game_version)` keying a patch bump DID fork the board, which is how
        23 of the 27 preserved submissions were stranded.

        Still raises rather than falling back to a literal: a stale stamp here
        misdescribes which build produced a record, and CLAUDE.md is explicit that
        a fallback literal ships precisely when the real lookup failed.
        """
        try:
            with open(self.version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(
                f"Cannot read {self.version_file} for the game version: {e}"
            )
        version = (data.get("latest_release") or {}).get("version")
        if not version:
            raise RuntimeError(
                f"{self.version_file} has no latest_release.version -- refusing to "
                "guess a game version for a new weekly league"
            )
        return version

    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"WARNING: Failed to save config: {e}")
    
    def get_current_week_info(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Detailed information about the league week a run at `now` operates on.

        `now` defaults to the real UTC time; passing it explicitly is how the
        boundary test and `--as-of` pin the run-time -> week mapping.
        """
        now = as_utc(now if now is not None else datetime.now(timezone.utc))

        week_start = league_week_start(now)
        week_end = league_week_end(week_start)

        # Label from the WEEK START's own Thursday, never from `now`. Deriving
        # the label from `now` is the second half of the A9 bug: it is what made
        # the rollover run label the outgoing week.
        week_id = week_id_for(week_start)
        iso_year, iso_week, _ = (week_start.date() + timedelta(days=6)).isocalendar()

        remaining = week_end - now
        remaining_s = max(0, int(remaining.total_seconds()))

        return {
            "week_id": week_id,
            "year": iso_year,
            "week_number": iso_week,
            # Dates and timestamps are Hobart-local and carry their offset, so
            # start_date and start_timestamp can never disagree the way they
            # would if the date were local and the timestamp were UTC.
            "timezone": LEAGUE_TZ_NAME,
            "start_date": week_start.strftime("%Y-%m-%d"),
            "end_date": week_end.strftime("%Y-%m-%d"),
            "start_timestamp": week_start.isoformat(),
            "end_timestamp": week_end.isoformat(),
            "start_timestamp_utc": as_utc(week_start).isoformat().replace("+00:00", "Z"),
            "end_timestamp_utc": as_utc(week_end).isoformat().replace("+00:00", "Z"),
            "days_remaining": remaining_s // 86400,
            "hours_remaining": (remaining_s // 3600) % 24,
            # is_current means "this record is the live league week", which is
            # what validate_data.py's cadence check keys off: it asserts the
            # end_timestamp is not in the past. Under the Friday anchor the
            # rollover fires inside the week it opens, so `status` is "running"
            # on every scheduled run; the "upcoming" branch survives only for
            # hand-run --as-of instants ahead of a boundary.
            "is_current": True,
            "status": "upcoming" if now < as_utc(week_start) else "running",
            "season": self.config["current_season"],
            "epoch": epoch_for(week_start),
        }
    
    def generate_weekly_seed(self, week_info: Optional[Dict[str, Any]] = None) -> str:
        """Generate a deterministic competitive seed for the week."""
        if not week_info:
            week_info = self.get_current_week_info()
        
        if self.config["seed_generation_method"] == "deterministic":
            # Create deterministic seed based on week
            seed_base = f"pdoom1_weekly_{week_info['week_id']}_{self.config['current_season']}"
            
            # Use hash to create consistent but unpredictable seed
            hash_object = hashlib.sha256(seed_base.encode())
            hex_hash = hash_object.hexdigest()
            
            # Use first 8 characters for readability
            return f"weekly_{week_info['week_id']}_{hex_hash[:8]}"
        
        else:  # random method
            random.seed(week_info['week_id'])
            random_suffix = ''.join(random.choices('0123456789abcdef', k=8))
            return f"weekly_{week_info['week_id']}_{random_suffix}"
    
    def get_league_status(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Get comprehensive status of the weekly league system."""
        week_info = self.get_current_week_info(now)
        current_seed = self.generate_weekly_seed(week_info)
        
        # Check for current league data
        current_league_exists = self.current_league_file.exists()
        current_league_data = None
        
        if current_league_exists:
            try:
                with open(self.current_league_file, 'r', encoding='utf-8') as f:
                    current_league_data = json.load(f)
            except Exception as e:
                print(f"WARNING: Failed to load current league data: {e}")
        
        # Count archived weeks
        archived_weeks = len(list(self.archive_dir.glob("*.json"))) if self.archive_dir.exists() else 0
        
        # Calculate league statistics
        total_participants = 0
        if current_league_data and current_league_data.get('entries'):
            total_participants = len(set(entry['player_name'] for entry in current_league_data['entries']))
        
        return {
            "current_week": week_info,
            "current_seed": current_seed,
            "league_active": current_league_exists,
            "current_league_data": current_league_data,
            "total_participants": total_participants,
            "archived_weeks": archived_weeks,
            "season": self.config["current_season"],
            "config": self.config,
            "data_directories": {
                "league_data": str(self.league_data_dir),
                "current_file": str(self.current_league_file),
                "archive_dir": str(self.archive_dir)
            }
        }
    
    def start_new_week(self, now: Optional[datetime] = None) -> bool:
        """Start a new weekly league competition."""
        now = as_utc(now if now is not None else datetime.now(timezone.utc))
        week_info = self.get_current_week_info(now)
        new_seed = self.generate_weekly_seed(week_info)
        game_version = self.get_game_version()

        seed_block = seed_for_week(new_seed)
        # Take the ladder version from the week's OWN epoch stamp rather than
        # re-reading the contract, so meta.ladder_version, board_key and
        # epoch.ladder_version are one value and cannot silently disagree inside
        # a single record. Falls back to the frontier only for an anomalous week,
        # which stamps no ladder version of its own.
        ladder = (week_info['epoch'].get('ladder_version')
                  or ladder_contract()["regularised_from"]["ladder_version"])

        print(f"NEW WEEK: Starting new weekly league for {week_info['week_id']}")
        print(f"SEED: {seed_block['seed']} "
              f"(blessed={seed_block['seed_provenance']['blessed']})")
        print(f"BOARD_KEY: ({seed_block['seed']}, {ladder})")
        print(f"GAME_VERSION: {game_version}  [record stamp only -- NOT part of the board key]")
        print(f"PERIOD: {week_info['start_date']} to {week_info['end_date']} "
              f"({week_info['timezone']})")
        print(f"EPOCH: {week_info['epoch']['id']} "
              f"(anomalous={week_info['epoch']['anomalous']})")

        # Archive current week if it exists
        if self.current_league_file.exists():
            print("ARCHIVE: Archiving previous week...")
            self.archive_current_week(now)

        # Create new league data structure
        new_league_data = {
            "meta": {
                "week_id": week_info['week_id'],
                "season": self.config["current_season"],
                "generated": iso_z(now),
                # A RECORD STAMP, not part of the board key. The board is keyed
                # (seed, ladder_version) -- an `L<n>` string, never a build
                # version and never `L<n>.<m>`; see the `board_key.is_not` list in
                # public/data/ladder-epochs.json. pdoom1 on #151, 2026-07-28: "the
                # build version no longer touches the board key at all". Keeping
                # game_version here says which build produced the record;
                # nothing may key off it.
                "game_version": game_version,
                "ladder_version": ladder,
                "competition_type": "weekly_league",
                "start_date": week_info['start_timestamp'],
                "end_date": week_info['end_timestamp'],
                "total_participants": 0,
                "total_submissions": 0
            },
            "seed": seed_block["seed"],
            "seed_provenance": seed_block["seed_provenance"],
            # The board key, spelled out, so no consumer has to reassemble it and
            # get the shape wrong. See public/data/ladder-epochs.json.
            "board_key": {
                "seed": seed_block["seed"],
                "ladder_version": ladder,
                "shape": "(seed, L<n>)",
                "blessed": seed_block["seed_provenance"]["blessed"],
            },
            # "Bootstrap_v0.4.1" was a legacy-pygame concept; the current Godot client
            # exports no economic model, so claiming one would be inventing a fact.
            "economic_model": "unknown",
            # Top-level epoch stamp so any consumer reading only the envelope
            # still sees whether this week is comparable. See LEAGUE_EPOCH_ANOMALY.md.
            "epoch": week_info['epoch'],
            "week_info": week_info,
            "entries": [],
            "statistics": {
                "highest_score": 0,
                "average_score": 0.0,
                "total_games": 0,
                "unique_players": 0
            }
        }

        # Save new league data
        try:
            with open(self.current_league_file, 'w', encoding='utf-8') as f:
                json.dump(new_league_data, f, indent=2, ensure_ascii=False)

            print(f"SUCCESS: New weekly league created: {self.current_league_file}")

            # Update config
            self.config["last_week_start"] = iso_z(now)
            self.config["current_week_id"] = week_info['week_id']
            self.config["current_seed"] = new_seed
            self.save_config()

            self.rebuild_archive_index()

            return True

        except Exception as e:
            print(f"ERROR: Failed to create new league: {e}")
            return False
    
    def archive_current_week(self, now: Optional[datetime] = None) -> bool:
        """Archive the current week's league data."""
        if not self.current_league_file.exists():
            print("INFO: No current league to archive")
            return True

        now = as_utc(now if now is not None else datetime.now(timezone.utc))
        try:
            # Load current league data
            with open(self.current_league_file, 'r', encoding='utf-8') as f:
                league_data = json.load(f)

            # Add archival metadata
            league_data["archived_at"] = iso_z(now)
            league_data["archive_status"] = "completed"
            # An archived week is not the current week. Every archive file
            # written before this fix still carries is_current: true -- see
            # docs/LEAGUE_EPOCH_ANOMALY.md; those are left as found, because the
            # anomaly record is the artefact, not a bug to retouch.
            if isinstance(league_data.get("week_info"), dict):
                league_data["week_info"]["is_current"] = False
                league_data["week_info"]["status"] = "ended"

            # Determine archive filename
            week_id = league_data.get("week_info", {}).get("week_id", "unknown_week")
            archive_filename = f"{week_id}_league.json"
            archive_path = self.archive_dir / archive_filename

            # Save to archive
            with open(archive_path, 'w', encoding='utf-8') as f:
                json.dump(league_data, f, indent=2, ensure_ascii=False)

            print(f"SUCCESS: Archived week to: {archive_path}")

            # Remove current league file
            self.current_league_file.unlink()
            print("SUCCESS: Current league file removed")

            self.rebuild_archive_index(now)

            return True

        except Exception as e:
            print(f"ERROR: Failed to archive current week: {e}")
            return False

    def scan_preserved_boards(self) -> list:
        """Summarise `public/leaderboard/data/preserved/**/*.json` for the archive page.

        These are boards captured live from the score API that the website never
        published -- 27 real submissions from 6 players, stranded by a board-key
        mismatch (two independent ones: the client submitted seed `weekly-2026-w0`
        while the site derived `weekly_2026_W30_...`, AND the versions differed).
        Pip's ruling 2026-07-29: they belong in the anomaly archive, and they must
        NEVER be merged forward across epochs -- merging scores earned under
        different rules is the exact lie the ladder split exists to prevent. So
        this only ever SUMMARISES; it never copies an entry into a league record.

        Derived from the directory: returns [] when the preserved data is not
        present, so the page shows nothing rather than claiming something. (The
        capture lives on branch `data/preserve-orphaned-boards`; the moment it
        merges, any rollover or `--rebuild-archive-index` lights this up.)
        """
        root = self.league_data_dir.parent / "preserved"
        out = []
        if not root.exists():
            return out
        for path in sorted(root.glob("*/*.json")):
            if path.name.lower() in ("index.json", "readme.json"):
                continue
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"WARNING: skipping unreadable preserved board {path.name}: {e}")
                continue
            entries = d.get("entries") or []
            if not isinstance(entries, list):
                continue
            dates = sorted(str(e.get("date")) for e in entries if e.get("date"))
            players = sorted({str(e.get("player_name")) for e in entries
                              if e.get("player_name")})
            version = d.get("version")
            out.append({
                "file": f"{path.parent.name}/{path.name}",
                "captured": path.parent.name,
                "seed": d.get("seed"),
                "version": version,
                # `L<n>` is a ladder epoch; anything else is a build version, i.e.
                # a board forked by the OLD (seed, game_version) keying.
                "key_kind": "ladder" if isinstance(version, str) and version.startswith("L")
                            else "build-version (pre-split keying)",
                "board_key": f"({d.get('seed')}, {version})",
                "entry_count": len(entries),
                "players": players,
                "first_entry": dates[0] if dates else None,
                "last_entry": dates[-1] if dates else None,
            })
        return out

    def rebuild_archive_index(self, now: Optional[datetime] = None) -> bool:
        """Regenerate archive/index.json from the archive files that exist.

        Nothing used to write this file after the initial hand-authored version:
        it listed 3 archives while 41 files sat beside it, and its `last_updated`
        was frozen at 2025-10-31. The archive page reads ONLY the index, so 38
        weeks of pre-history were invisible. Rebuilding from the directory makes
        the index a derived fact instead of a stale assertion.
        """
        now = as_utc(now if now is not None else datetime.now(timezone.utc))
        index_path = self.archive_dir / "index.json"
        archives = []
        try:
            for path in sorted(self.archive_dir.glob("*_league.json")):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                except Exception as e:
                    print(f"WARNING: skipping unreadable archive {path.name}: {e}")
                    continue
                meta = d.get("meta") or {}
                wi = d.get("week_info") or {}
                start = wi.get("start_timestamp") or wi.get("start_date")
                epoch = d.get("epoch") or wi.get("epoch")
                if not epoch and start:
                    try:
                        epoch = epoch_for(datetime.fromisoformat(str(start).replace("Z", "+00:00")))
                    except ValueError:
                        epoch = None
                archives.append({
                    "week_id": meta.get("week_id") or wi.get("week_id") or path.stem,
                    "season": meta.get("season"),
                    "year": wi.get("year"),
                    "week_number": wi.get("week_number"),
                    "start_date": wi.get("start_date"),
                    "end_date": wi.get("end_date"),
                    "file": path.name,
                    "archived_at": d.get("archived_at"),
                    "game_version": meta.get("game_version"),
                    "entry_count": len(d.get("entries") or []),
                    "epoch": epoch,
                })

            anomalous = [a for a in archives if (a.get("epoch") or {}).get("anomalous")]
            contract = ladder_contract()
            cut = contract["regularised_from"]
            payload = {
                "archives": archives,
                "total_archives": len(archives),
                "seasons": sorted({a["season"] for a in archives if a.get("season")}),
                # Boards captured from the live API that the website never
                # published. Derived from the directory, so this key is absent
                # when there is nothing to show and the page claims nothing.
                "preserved_boards": self.scan_preserved_boards(),
                "epochs": {
                    "ladder_version": cut["ladder_version"],
                    "board_key": contract.get("board_key"),
                    "board_opens_local": cut.get("board_opens_local"),
                    "board_opens_confirmed": bool(cut.get("board_opens_confirmed")),
                    "boundary_local": epoch_boundary().isoformat(),
                    "boundary_tz": LEAGUE_TZ_NAME,
                    "boundary_utc": as_utc(epoch_boundary()).isoformat().replace("+00:00", "Z"),
                    "boundary_why": cut.get("boundary_why"),
                    "see": EPOCH_DOC,
                    EPOCH_PRE_ID: {
                        "count": len(anomalous),
                        "anomalous": True,
                        "reason": cut["reason_pre"],
                    },
                    EPOCH_POST_ID: {
                        "count": len(archives) - len(anomalous),
                        "anomalous": False,
                        "reason": cut["reason_post"],
                    },
                },
                "last_updated": iso_z(now),
            }
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            print(f"SUCCESS: Rebuilt archive index ({len(archives)} weeks, "
                  f"{len(anomalous)} anomalous): {index_path}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to rebuild archive index: {e}")
            return False
    
    def get_league_standings(self) -> Optional[Dict[str, Any]]:
        """Get current league standings with rankings."""
        if not self.current_league_file.exists():
            return None
        
        try:
            with open(self.current_league_file, 'r', encoding='utf-8') as f:
                league_data = json.load(f)
            
            entries = league_data.get('entries', [])
            
            # Sort by score (highest first, lowest turn count wins)
            sorted_entries = sorted(entries, key=lambda x: x.get('score', 0), reverse=True)
            
            # Add rankings
            for i, entry in enumerate(sorted_entries, 1):
                entry['rank'] = i
            
            # Calculate statistics
            scores = [entry.get('score', 0) for entry in entries]
            unique_players = len(set(entry.get('player_name', '') for entry in entries))
            
            standings = {
                "week_info": league_data.get('week_info', {}),
                "seed": league_data.get('seed', ''),
                "total_entries": len(entries),
                "unique_players": unique_players,
                "top_10": sorted_entries[:10],
                "statistics": {
                    "highest_score": max(scores) if scores else 0,
                    "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
                    "median_score": sorted(scores)[len(scores)//2] if scores else 0,
                    "total_submissions": len(entries)
                },
                "generated_at": iso_z(datetime.now(timezone.utc))
            }
            
            return standings
            
        except Exception as e:
            print(f"ERROR: Failed to get league standings: {e}")
            return None


def main():
    """CLI interface for weekly league management."""
    parser = argparse.ArgumentParser(description="p(Doom)1 Weekly League Manager")
    parser.add_argument("--status", action="store_true", help="Show current league status")
    parser.add_argument("--new-week", action="store_true", help="Start new weekly league")
    parser.add_argument("--archive-week", action="store_true", help="Archive current week")
    parser.add_argument("--generate-seed", action="store_true", help="Generate new competitive seed")
    parser.add_argument("--standings", action="store_true", help="Show current league standings")
    parser.add_argument("--week-id", type=str, help="Specify week ID (for seed generation)")
    parser.add_argument("--rebuild-archive-index", action="store_true",
                        help="Regenerate archive/index.json from the archive files on disk")
    parser.add_argument("--as-of", type=str, metavar="ISO8601",
                        help="Pretend the run happens at this instant "
                             "(e.g. 2026-08-06T14:00:00Z, the rollover that opens the "
                             "first regularised week). Naive input is treated as UTC.")

    args = parser.parse_args()

    now = None
    if args.as_of:
        try:
            now = as_utc(datetime.fromisoformat(args.as_of.replace("Z", "+00:00")))
        except ValueError:
            print(f"ERROR: --as-of is not an ISO-8601 timestamp: {args.as_of}")
            sys.exit(1)

    manager = WeeklyLeagueManager()

    try:
        if args.status:
            status = manager.get_league_status(now)
            week = status['current_week']

            print("WEEKLY LEAGUE STATUS:")
            print(f"   SEASON: {status['season']}")
            print(f"   CURRENT_WEEK: {week['week_id']}")
            print(f"   PERIOD: {week['start_date']} to {week['end_date']} "
                  f"({week['timezone']})")
            print(f"   WEEK_STATUS: {week['status']}")
            print(f"   EPOCH: {week['epoch']['id']} (anomalous={week['epoch']['anomalous']})")
            print(f"   TIME_REMAINING: {week['days_remaining']} days, {week['hours_remaining']} hours")
            print(f"   CURRENT_SEED: {status['current_seed']}")
            print(f"   LEAGUE_ACTIVE: {status['league_active']}")
            print(f"   PARTICIPANTS: {status['total_participants']}")
            print(f"   ARCHIVED_WEEKS: {status['archived_weeks']}")

        elif args.new_week:
            success = manager.start_new_week(now)
            sys.exit(0 if success else 1)

        elif args.archive_week:
            success = manager.archive_current_week(now)
            sys.exit(0 if success else 1)

        elif args.rebuild_archive_index:
            success = manager.rebuild_archive_index(now)
            sys.exit(0 if success else 1)

        elif args.generate_seed:
            week_info = None
            if args.week_id:
                # Parse week ID and create week info
                try:
                    year, week_part = args.week_id.split('_')
                    week_num = int(week_part[1:])  # Remove 'W' prefix
                    week_info = {"week_id": args.week_id, "year": int(year), "week_number": week_num}
                except ValueError:
                    print(f"ERROR: Invalid week ID format: {args.week_id}")
                    sys.exit(1)
            
            if week_info is None:
                week_info = manager.get_current_week_info(now)
            seed = manager.generate_weekly_seed(week_info)
            print(f"SEED: Generated weekly seed: {seed}")
        
        elif args.standings:
            standings = manager.get_league_standings()
            if standings:
                print(f"LEAGUE STANDINGS - Week {standings['week_info']['week_id']}:")
                print(f"   Seed: {standings['seed']}")
                print(f"   Participants: {standings['unique_players']}")
                print(f"   Total Submissions: {standings['total_entries']}")
                print(f"   High Score: {standings['statistics']['highest_score']} turns")
                print(f"   Average Score: {standings['statistics']['average_score']} turns")
                
                print("\n   TOP 10:")
                for entry in standings['top_10']:
                    print(f"   #{entry['rank']:2d}. {entry.get('player_name', 'Unknown'):20s} - {entry.get('score', 0):3d} turns")
            else:
                print("INFO: No active league or standings available")
        
        else:
            print("USAGE: p(Doom)1 Weekly League Manager")
            print("\nAvailable commands:")
            print("   --status          Show current league status")
            print("   --new-week        Start new weekly league")
            print("   --archive-week    Archive current week")
            print("   --generate-seed   Generate new competitive seed")
            print("   --standings       Show current league standings")
            print("   --rebuild-archive-index  Regenerate archive/index.json from disk")
            print("   --as-of ISO8601   Pin the run instant (testing / backfill)")

            # Show current status
            status = manager.get_league_status(now)
            week = status['current_week']
            print(f"\nCURRENT STATUS:")
            print(f"   Week: {week['week_id']} ({week['days_remaining']} days remaining)")
            print(f"   Seed: {status['current_seed']}")
    
    except KeyboardInterrupt:
        print("\nSTOP: Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()