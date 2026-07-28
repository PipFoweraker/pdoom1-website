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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import random


# --- League week geometry -------------------------------------------------
#
# A league week runs Monday 00:00:00 UTC -> Sunday 23:59:59 UTC.
#
# The rollover cron (.github/workflows/weekly-league-reset.yml) fires at
# Sunday 14:00 UTC, which is ~10 hours BEFORE the week it is opening begins.
# The original get_current_week_info() derived everything from `now`, so a
# Sunday-14:00 run re-created the week that was about to *end*: on
# 2026-07-26T14:28Z it wrote week 2026_W30 (2026-07-20 -> 2026-07-26) as the
# brand-new "current" week, ten hours before that week expired. Ten weeks of
# green checkmarks, every one of them a week late. (docs/TECH_DEBT.md A9.)
#
# The fix is to make the run time -> week mapping explicit: at or after the
# rollover moment on a Sunday, the week a run operates on is the one that
# STARTS the following midnight. Pinned by scripts/test-weekly-league-boundary.py.
ROLLOVER_WEEKDAY = 6      # datetime.weekday(): Monday=0 ... Sunday=6
ROLLOVER_HOUR_UTC = 14    # must match the cron in weekly-league-reset.yml

# --- Ladder epoch ---------------------------------------------------------
#
# Everything generated before the 2026-07-31 patch-cycle regularisation is
# deliberately-labelled anomalous pre-history, not silently buried. See
# docs/LEAGUE_EPOCH_ANOMALY.md. A week is pre-epoch iff it STARTS before the
# boundary, so 2026_W31 (starts 2026-07-27, straddles the cut) is anomalous
# and 2026_W32 (starts 2026-08-03) is the first regularised week.
EPOCH_BOUNDARY = datetime(2026, 7, 31, 0, 0, 0, tzinfo=timezone.utc)
EPOCH_PRE_ID = "pre-regularisation"
EPOCH_POST_ID = "regularised"
EPOCH_DOC = "docs/LEAGUE_EPOCH_ANOMALY.md"
EPOCH_PRE_REASON = (
    "Generated before the 2026-07-31 patch-cycle regularisation, while the weekly "
    "rollover was off by one week (it re-opened the week that was ending instead of "
    "the week that was starting) and while no shipped client could submit to these "
    "boards. Retained as a record of what the pipeline produced, NOT as a comparable "
    "competition result."
)
EPOCH_POST_REASON = (
    "Opened on or after the 2026-07-31 patch-cycle regularisation, by a rollover "
    "whose run-time -> week mapping is pinned by "
    "scripts/test-weekly-league-boundary.py."
)

# The seed this script derives is NOT the competitive seed. docs/LEAGUE_SEED_LEDGER.md
# is explicit: "The seed is not a free website-side choice" -- the canonical key is
# whatever the shipped client POSTs (currently seed `weekly-2026-w30`, ladder L2),
# blessed by Pip in the ledger. This script's `weekly_<week_id>_<hash>` values have
# never matched that and no client has ever used one. Every record therefore carries
# its own disclaimer, so nothing downstream can mistake a derived value for a blessed
# one the way `league_2026-07_7d6ced29` was mistaken on 2026-07-24.
SEED_PROVENANCE = {
    "blessed": False,
    "derivation": "sha256('pdoom1_weekly_<week_id>_<season>')[:8], website-side",
    "canonical_source": "the shipped game client, recorded in docs/LEAGUE_SEED_LEDGER.md",
    "note": (
        "Placeholder. Do NOT present this to players as the competitive seed. The board "
        "key scores are actually submitted under is blessed in docs/LEAGUE_SEED_LEDGER.md; "
        "a seed that is not in that ledger routes submissions to a board nobody displays, "
        "with no error shown to the player."
    ),
}


def as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to UTC. Naive input is *assumed* UTC.

    The old code called datetime.now() (naive local time). On a GitHub runner
    that is UTC by accident, on Pip's Windows box it is AEST -- a 10h skew that
    lands exactly on the Sunday-14:00 boundary this module now depends on.
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
    """Monday 00:00:00 UTC of the league week a run at `now` should operate on.

    Before Sunday 14:00 UTC -> the week currently running.
    At or after Sunday 14:00 UTC -> the week that starts the next midnight.
    """
    now = as_utc(now)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = midnight - timedelta(days=now.weekday())
    if now.weekday() == ROLLOVER_WEEKDAY and now.hour >= ROLLOVER_HOUR_UTC:
        week_start += timedelta(days=7)
    return week_start


def epoch_for(week_start: datetime) -> Dict[str, Any]:
    """Machine-readable ladder-epoch stamp for a week beginning at `week_start`."""
    anomalous = as_utc(week_start) < EPOCH_BOUNDARY
    return {
        "id": EPOCH_PRE_ID if anomalous else EPOCH_POST_ID,
        "anomalous": anomalous,
        "boundary_utc": EPOCH_BOUNDARY.isoformat().replace("+00:00", "Z"),
        "reason": EPOCH_PRE_REASON if anomalous else EPOCH_POST_REASON,
        "see": EPOCH_DOC,
    }


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
            "competition_timezone": "UTC",
            "auto_reset_enabled": False,
            "created": datetime.now().isoformat()
        }
    
    def get_game_version(self) -> str:
        """Read the deployed game version from public/data/version.json.

        Raises rather than falling back to a literal. A weekly board is keyed
        (seed, game_version), so stamping a stale version here creates a board that
        the shipped client cannot submit to: players would submit scores and see
        nothing appear, with no error raised anywhere. Failing here is far cheaper
        than publishing a league nobody can enter.
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
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        # ISO week of the WEEK START, not of `now`. Deriving it from `now` is
        # exactly what made the Sunday-14:00 run label the outgoing week.
        # isocalendar()[0] is the ISO year, which is what W53/W01 straddles need.
        year, week, _ = week_start.isocalendar()

        remaining = week_end - now
        remaining_s = max(0, int(remaining.total_seconds()))

        return {
            "week_id": f"{year}_W{week:02d}",
            "year": year,
            "week_number": week,
            "start_date": week_start.strftime("%Y-%m-%d"),
            "end_date": week_end.strftime("%Y-%m-%d"),
            "start_timestamp": week_start.isoformat(),
            "end_timestamp": week_end.isoformat(),
            "days_remaining": remaining_s // 86400,
            "hours_remaining": (remaining_s // 3600) % 24,
            # is_current means "this record is the live league week", which is
            # what validate_data.py's cadence check keys off: it asserts the
            # end_timestamp is not in the past. A rollover run legitimately
            # opens a week ~10h before it starts, so `status` carries the
            # finer-grained truth rather than lying through is_current.
            "is_current": True,
            "status": "upcoming" if now < week_start else "running",
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

        print(f"NEW WEEK: Starting new weekly league for {week_info['week_id']}")
        print(f"SEED: Generated seed: {new_seed}")
        print(f"GAME_VERSION: {game_version}")
        print(f"PERIOD: {week_info['start_date']} to {week_info['end_date']}")
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
                "game_version": game_version,
                "competition_type": "weekly_league",
                "start_date": week_info['start_timestamp'],
                "end_date": week_info['end_timestamp'],
                "total_participants": 0,
                "total_submissions": 0
            },
            "seed": new_seed,
            "seed_provenance": dict(SEED_PROVENANCE),
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
            payload = {
                "archives": archives,
                "total_archives": len(archives),
                "seasons": sorted({a["season"] for a in archives if a.get("season")}),
                "epochs": {
                    "boundary_utc": EPOCH_BOUNDARY.isoformat().replace("+00:00", "Z"),
                    "see": EPOCH_DOC,
                    EPOCH_PRE_ID: {
                        "count": len(anomalous),
                        "anomalous": True,
                        "reason": EPOCH_PRE_REASON,
                    },
                    EPOCH_POST_ID: {
                        "count": len(archives) - len(anomalous),
                        "anomalous": False,
                        "reason": EPOCH_POST_REASON,
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
                        help="Pretend the run happens at this UTC instant "
                             "(e.g. 2026-08-02T14:00:00Z). Naive input is treated as UTC.")

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
            print(f"   PERIOD: {week['start_date']} to {week['end_date']}")
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