#!/usr/bin/env python3
"""
Game Repository Integration for p(Doom)1 Website

This script integrates with the actual p(Doom)1 game repository to:
1. Detect game installations
2. Export real leaderboard data from the game
3. Sync with website data format
4. Monitor for game updates

Usage:
    python scripts/game-integration.py --scan          # Scan for game installations
    python scripts/game-integration.py --export        # Export real game data
    python scripts/game-integration.py --setup         # Set up integration
"""

import json
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import glob


class GameRepositoryIntegration:
    """Integration with the p(Doom)1 game repository for real data export."""
    
    def __init__(self):
        self.website_dir = Path(__file__).parent.parent
        self.leaderboard_output = self.website_dir / "public" / "leaderboard" / "data" / "leaderboard.json"
        self.integration_config = self.website_dir / "scripts" / "game-integration-config.json"
        
        # Common game repository locations to search
        self.search_paths = [
            Path.home() / "Documents" / "A Local Code" / "pdoom1",
            Path.home() / "Documents" / "GitHub" / "pdoom1", 
            Path.home() / "pdoom1",
            Path.cwd().parent / "pdoom1"
        ]
        
        self.game_repo_path = None
        self.config = self.load_config()
        
        # Set game_repo_path from config if available
        if self.config.get("game_repo_path"):
            self.game_repo_path = Path(self.config["game_repo_path"])
    
    def load_config(self) -> Dict[str, Any]:
        """Load integration configuration."""
        if self.integration_config.exists():
            try:
                with open(self.integration_config, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        return {
            "game_repo_path": None,
            "last_export": None,
            "integration_status": "not_configured"
        }
    
    def save_config(self):
        """Save integration configuration."""
        try:
            with open(self.integration_config, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")
    
    def scan_for_game_repo(self) -> List[Path]:
        """Scan for p(Doom)1 game repository installations."""
        found_repos = []
        
        print("SCANNING: Scanning for p(Doom)1 game repository...")
        
        for search_path in self.search_paths:
            if search_path.exists():
                print(f"  Checking: {search_path}")
                
                if self.validate_game_repo(search_path):
                    found_repos.append(search_path)
                    print(f"  FOUND: Valid game repo: {search_path}")
                else:
                    print(f"  SKIP: Not a valid game repo: {search_path}")
            else:
                print(f"  SKIP: Path doesn't exist: {search_path}")
        
        return found_repos
    
    def validate_game_repo(self, path: Path) -> bool:
        """Validate that a path contains a valid p(Doom)1 game repository."""
        try:
            # Check for key game files/directories
            required_indicators = [
                "main.py",  # Main game entry point
                "src",      # Source directory
                "ui.py"     # Game UI
            ]
            
            # Check for leaderboard-specific files
            leaderboard_indicators = [
                "src/scores",
                "src/scores/enhanced_leaderboard.py",
                "src/scores/local_store.py"
            ]
            
            # Must have all required indicators
            for indicator in required_indicators:
                if not (path / indicator).exists():
                    return False
            
            # Must have at least some leaderboard indicators
            leaderboard_found = any((path / indicator).exists() for indicator in leaderboard_indicators)
            
            return leaderboard_found
            
        except Exception:
            return False
    
    def set_game_repo_path(self, repo_path: Path) -> bool:
        """Set the game repository path and validate it."""
        if self.validate_game_repo(repo_path):
            self.game_repo_path = repo_path
            self.config["game_repo_path"] = str(repo_path)
            self.config["integration_status"] = "configured"
            self.save_config()
            print(f"SUCCESS: Game repository set: {repo_path}")
            return True
        else:
            print(f"ERROR: Invalid game repository: {repo_path}")
            return False
    
    def get_game_leaderboard_data(self) -> Optional[Dict[str, Any]]:
        """Extract leaderboard data from the game repository."""
        if not self.game_repo_path:
            print("ERROR: No game repository configured")
            return None
        
        # Look for leaderboard files in the game repository
        leaderboard_dirs = [
            self.game_repo_path / "leaderboards",
            self.game_repo_path / "data" / "leaderboards",
            self.game_repo_path / "saves" / "leaderboards"
        ]
        
        leaderboard_data = None
        
        for leaderboard_dir in leaderboard_dirs:
            if leaderboard_dir.exists():
                print(f"FOUND: Leaderboard directory: {leaderboard_dir}")
                
                # Look for JSON files
                json_files = list(leaderboard_dir.glob("*.json"))
                
                if json_files:
                    # Use the most recent file or a file with "seed" in the name
                    target_file = None
                    
                    # Prefer files with "seed" in the name
                    seed_files = [f for f in json_files if "seed" in f.name.lower()]
                    if seed_files:
                        target_file = max(seed_files, key=lambda f: f.stat().st_mtime)
                    else:
                        target_file = max(json_files, key=lambda f: f.stat().st_mtime)
                    
                    try:
                        with open(target_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        print(f"SUCCESS: Loaded leaderboard data from: {target_file.name}")
                        leaderboard_data = self.convert_game_to_website_format(data, target_file)
                        break
                        
                    except Exception as e:
                        print(f"ERROR: Failed to load {target_file}: {e}")
        
        if not leaderboard_data:
            print("WARNING: No leaderboard data found in game repository")
            # Fall back to generating sample data based on game presence
            leaderboard_data = self.generate_game_aware_sample_data()
        
        return leaderboard_data
    
    def convert_game_to_website_format(self, game_data: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
        """Convert game leaderboard format to website format."""
        
        # Handle different possible game data formats
        entries = []
        
        if "entries" in game_data:
            # Already in the expected format
            entries = game_data["entries"]
        elif isinstance(game_data, list):
            # Direct list of entries
            entries = game_data
        else:
            # Try to extract entries from other structures
            for key, value in game_data.items():
                if isinstance(value, list) and value:
                    # Check if this looks like leaderboard entries
                    if all(isinstance(item, dict) and "score" in item for item in value[:3]):
                        entries = value
                        break
        
        # Convert entries to website format
        website_entries = []
        for i, entry in enumerate(entries[:50]):  # Limit to top 50
            try:
                website_entry = {
                    "score": entry.get("score", 0),
                    "player_name": entry.get("player_name", entry.get("lab_name", f"Player {i+1}")),
                    "date": entry.get("date", datetime.now().isoformat() + "Z"),
                    "level_reached": entry.get("level_reached", entry.get("score", 0)),
                    "game_mode": entry.get("game_mode", "Bootstrap_v0.4.1"),
                    "duration_seconds": entry.get("duration_seconds", 0.0),
                    "entry_uuid": entry.get("entry_uuid", f"game-{i+1:03d}"),
                    "final_doom": entry.get("final_doom", 25.0),
                    "final_money": entry.get("final_money", 100000),
                    "final_staff": entry.get("final_staff", 5),
                    "final_reputation": entry.get("final_reputation", 50.0),
                    "final_compute": entry.get("final_compute", 10000),
                    "research_papers_published": entry.get("research_papers_published", 0),
                    "technical_debt_accumulated": entry.get("technical_debt_accumulated", 0)
                }
                website_entries.append(website_entry)
            except Exception as e:
                print(f"Warning: Could not convert entry {i}: {e}")
        
        # Sort by score (highest first)
        website_entries.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "meta": {
                "generated": datetime.now().isoformat() + "Z",
                "game_version": game_data.get("version", "v0.4.1"),
                "total_seeds": 1,
                "total_players": len(set(entry["player_name"] for entry in website_entries)),
                "export_source": "game-repository",
                "source_file": source_file.name,
                "note": "Exported from actual game leaderboard data"
            },
            "seed": game_data.get("seed", source_file.stem.replace("seed_", "")),
            "economic_model": game_data.get("economic_model", "Bootstrap_v0.4.1"),
            "entries": website_entries
        }
    
    def generate_game_aware_sample_data(self) -> Dict[str, Any]:
        """Generate sample data that's aware of the game repository presence."""
        print("FALLBACK: Generating game-aware sample data...")
        
        # Fallback minimal data
        return {
            "meta": {
                "generated": datetime.now().isoformat() + "Z",
                "game_version": "v0.4.1",
                "total_seeds": 0,
                "total_players": 0,
                "export_source": "fallback",
                "note": "No game data available - game repository detected but no leaderboard data found"
            },
            "seed": "no-data",
            "economic_model": "Bootstrap_v0.4.1",
            "entries": []
        }
    
    def export_game_data(self) -> bool:
        """Export leaderboard data from game to website."""
        if not self.game_repo_path:
            print("ERROR: No game repository configured. Run --setup first.")
            return False
        
        print(f"EXPORT: Exporting leaderboard data from: {self.game_repo_path}")
        
        leaderboard_data = self.get_game_leaderboard_data()
        if not leaderboard_data:
            print("ERROR: Failed to get leaderboard data")
            return False
        
        # Ensure output directory exists
        self.leaderboard_output.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to website leaderboard file
        try:
            with open(self.leaderboard_output, 'w', encoding='utf-8') as f:
                json.dump(leaderboard_data, f, indent=2, ensure_ascii=False)
            
            print(f"SUCCESS: Exported leaderboard data to: {self.leaderboard_output}")
            print(f"STATS: Entries: {len(leaderboard_data['entries'])}")
            
            if leaderboard_data['entries']:
                top_entry = leaderboard_data['entries'][0]
                print(f"TOP: Top Score: {top_entry['score']} turns")
                print(f"LEADER: Leader: {top_entry['player_name']}")
            
            # Update config
            self.config["last_export"] = datetime.now().isoformat()
            self.config["integration_status"] = "active"
            self.save_config()
            
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to write leaderboard data: {e}")
            return False
    
    def setup_integration(self) -> bool:
        """Set up integration with game repository."""
        print("SETUP: Setting up game repository integration...")
        
        # Scan for repositories
        found_repos = self.scan_for_game_repo()
        
        if not found_repos:
            print("\nERROR: No p(Doom)1 game repositories found.")
            print("\nSETUP: To set up integration:")
            print("   1. Clone the game repository: git clone <pdoom1-repo-url>")
            print("   2. Place it in one of these locations:")
            for path in self.search_paths[:3]:
                print(f"      - {path}")
            print("   3. Run this setup again")
            return False
        
        if len(found_repos) == 1:
            # Auto-select the only repository found
            selected_repo = found_repos[0]
            print(f"\nAUTO: Auto-selected repository: {selected_repo}")
        else:
            # Let user choose
            print(f"\nFOUND: Found {len(found_repos)} repositories:")
            for i, repo in enumerate(found_repos, 1):
                print(f"   {i}. {repo}")
            
            try:
                choice = input(f"\nSelect repository (1-{len(found_repos)}): ")
                index = int(choice) - 1
                if 0 <= index < len(found_repos):
                    selected_repo = found_repos[index]
                else:
                    print("ERROR: Invalid selection")
                    return False
            except (ValueError, KeyboardInterrupt):
                print("ERROR: Setup cancelled")
                return False
        
        # Set up the selected repository
        if self.set_game_repo_path(selected_repo):
            print("\nSUCCESS: Integration setup complete!")
            print("\nNEXT: Next steps:")
            print("   • Run: python scripts/game-integration.py --export")
            print("   • Test: python scripts/test-integration.py --quick")
            print("   • View: http://localhost:5173/leaderboard/")
            return True
        
        return False
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status."""
        status = {
            "configured": self.config.get("game_repo_path") is not None,
            "game_repo_path": self.config.get("game_repo_path"),
            "last_export": self.config.get("last_export"),
            "integration_status": self.config.get("integration_status", "not_configured"),
            "leaderboard_file_exists": self.leaderboard_output.exists(),
            "config_file": str(self.integration_config)
        }
        
        if status["configured"]:
            repo_path = Path(status["game_repo_path"])
            status["repo_exists"] = repo_path.exists()
            status["repo_valid"] = self.validate_game_repo(repo_path) if repo_path.exists() else False
        
        return status


def main():
    """CLI interface for game repository integration."""
    parser = argparse.ArgumentParser(description="p(Doom)1 Game Repository Integration")
    parser.add_argument("--scan", action="store_true", help="Scan for game repository installations")
    parser.add_argument("--export", action="store_true", help="Export game leaderboard data to website")
    parser.add_argument("--setup", action="store_true", help="Set up integration with game repository")
    parser.add_argument("--status", action="store_true", help="Show integration status")
    parser.add_argument("--repo-path", type=str, help="Manually specify game repository path")
    
    args = parser.parse_args()
    
    integration = GameRepositoryIntegration()
    
    try:
        if args.status:
            status = integration.get_integration_status()
            print("STATUS: Game Repository Integration Status:")
            print(f"   CONFIGURED: {status['configured']}")
            print(f"   REPOSITORY: {status.get('game_repo_path', 'Not set')}")
            print(f"   VALID: {status.get('repo_valid', False)}")
            print(f"   LAST_EXPORT: {status.get('last_export', 'Never')}")
            print(f"   STATUS: {status['integration_status']}")
            return
        
        if args.repo_path:
            repo_path = Path(args.repo_path)
            if integration.set_game_repo_path(repo_path):
                print("SUCCESS: Repository path set successfully")
            else:
                print("ERROR: Failed to set repository path")
                sys.exit(1)
        
        if args.scan:
            found_repos = integration.scan_for_game_repo()
            print(f"\nSCAN: Scan complete. Found {len(found_repos)} repositories.")
        
        elif args.setup:
            success = integration.setup_integration()
            sys.exit(0 if success else 1)
        
        elif args.export:
            success = integration.export_game_data()
            sys.exit(0 if success else 1)
        
        else:
            print("USAGE: p(Doom)1 Game Repository Integration")
            print("\nAvailable commands:")
            print("   --setup     Set up integration with game repository")
            print("   --scan      Scan for game repository installations")
            print("   --export    Export game leaderboard data to website")
            print("   --status    Show current integration status")
            print("\nSTART: Start with: python scripts/game-integration.py --setup")
    
    except KeyboardInterrupt:
        print("\nSTOP: Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()