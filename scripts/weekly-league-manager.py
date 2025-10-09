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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import random


class WeeklyLeagueManager:
    """Manages weekly league competitions for p(Doom)1."""
    
    def __init__(self):
        self.website_dir = Path(__file__).parent.parent
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
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"WARNING: Failed to save config: {e}")
    
    def get_current_week_info(self) -> Dict[str, Any]:
        """Get detailed information about the current week."""
        now = datetime.now()
        
        # Find the start of the current week (Monday)
        days_since_monday = now.weekday()
        week_start = now - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Week end is Sunday
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        # ISO week number
        year, week, _ = now.isocalendar()
        
        # Calculate days remaining
        days_remaining = (week_end - now).days
        hours_remaining = int((week_end - now).total_seconds() // 3600) % 24
        
        return {
            "week_id": f"{year}_W{week:02d}",
            "year": year,
            "week_number": week,
            "start_date": week_start.strftime("%Y-%m-%d"),
            "end_date": week_end.strftime("%Y-%m-%d"),
            "start_timestamp": week_start.isoformat(),
            "end_timestamp": week_end.isoformat(),
            "days_remaining": days_remaining,
            "hours_remaining": hours_remaining,
            "is_current": True,
            "season": self.config["current_season"]
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
    
    def get_league_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the weekly league system."""
        week_info = self.get_current_week_info()
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
    
    def start_new_week(self) -> bool:
        """Start a new weekly league competition."""
        week_info = self.get_current_week_info()
        new_seed = self.generate_weekly_seed(week_info)
        
        print(f"NEW WEEK: Starting new weekly league for {week_info['week_id']}")
        print(f"SEED: Generated seed: {new_seed}")
        print(f"PERIOD: {week_info['start_date']} to {week_info['end_date']}")
        
        # Archive current week if it exists
        if self.current_league_file.exists():
            print("ARCHIVE: Archiving previous week...")
            self.archive_current_week()
        
        # Create new league data structure
        new_league_data = {
            "meta": {
                "week_id": week_info['week_id'],
                "season": self.config["current_season"],
                "generated": datetime.now().isoformat() + "Z",
                "game_version": "v0.4.1",
                "competition_type": "weekly_league",
                "start_date": week_info['start_timestamp'],
                "end_date": week_info['end_timestamp'],
                "total_participants": 0,
                "total_submissions": 0
            },
            "seed": new_seed,
            "economic_model": "Bootstrap_v0.4.1",
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
            self.config["last_week_start"] = datetime.now().isoformat()
            self.config["current_week_id"] = week_info['week_id']
            self.config["current_seed"] = new_seed
            self.save_config()
            
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to create new league: {e}")
            return False
    
    def archive_current_week(self) -> bool:
        """Archive the current week's league data."""
        if not self.current_league_file.exists():
            print("INFO: No current league to archive")
            return True
        
        try:
            # Load current league data
            with open(self.current_league_file, 'r', encoding='utf-8') as f:
                league_data = json.load(f)
            
            # Add archival metadata
            league_data["archived_at"] = datetime.now().isoformat() + "Z"
            league_data["archive_status"] = "completed"
            
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
            
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to archive current week: {e}")
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
                "generated_at": datetime.now().isoformat() + "Z"
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
    
    args = parser.parse_args()
    
    manager = WeeklyLeagueManager()
    
    try:
        if args.status:
            status = manager.get_league_status()
            week = status['current_week']
            
            print("WEEKLY LEAGUE STATUS:")
            print(f"   SEASON: {status['season']}")
            print(f"   CURRENT_WEEK: {week['week_id']}")
            print(f"   PERIOD: {week['start_date']} to {week['end_date']}")
            print(f"   TIME_REMAINING: {week['days_remaining']} days, {week['hours_remaining']} hours")
            print(f"   CURRENT_SEED: {status['current_seed']}")
            print(f"   LEAGUE_ACTIVE: {status['league_active']}")
            print(f"   PARTICIPANTS: {status['total_participants']}")
            print(f"   ARCHIVED_WEEKS: {status['archived_weeks']}")
            
        elif args.new_week:
            success = manager.start_new_week()
            sys.exit(0 if success else 1)
        
        elif args.archive_week:
            success = manager.archive_current_week()
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
            
            # Show current status
            status = manager.get_league_status()
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