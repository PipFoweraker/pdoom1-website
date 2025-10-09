#!/usr/bin/env python3
"""
Weekly Deployment Preparation Script

This script automates the preparation steps for the weekly Friday deployment.
It checks all systems, syncs data, and validates deployment readiness.

Usage:
    python scripts/prepare-weekly-deployment.py              # Full preparation
    python scripts/prepare-weekly-deployment.py --check-only # Just check, no changes
    python scripts/prepare-weekly-deployment.py --quick      # Skip long-running checks
"""

import json
import sys
import subprocess
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

class WeeklyDeploymentPrep:
    """Prepares for weekly Friday deployment."""
    
    def __init__(self, check_only: bool = False, quick: bool = False):
        self.check_only = check_only
        self.quick = quick
        self.project_root = Path(__file__).parent.parent
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        self.errors = []
        
    def log_check(self, name: str, passed: bool, message: str = "", is_critical: bool = True):
        """Log a check result."""
        status = "✅" if passed else ("❌" if is_critical else "⚠️ ")
        print(f"{status} {name}")
        if message:
            print(f"   {message}")
        
        if passed:
            self.checks_passed += 1
        else:
            if is_critical:
                self.checks_failed += 1
                self.errors.append(f"{name}: {message}")
            else:
                self.warnings.append(f"{name}: {message}")
    
    def run_command(self, cmd: List[str], check: bool = True) -> Tuple[bool, str]:
        """Run a command and return success status and output."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=60 if not self.quick else 30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def check_git_status(self) -> bool:
        """Check git status and ensure we're on main branch."""
        print("\n📋 Git Status Check")
        print("-" * 50)
        
        # Check current branch
        success, output = self.run_command(["git", "branch", "--show-current"])
        if not success:
            self.log_check("Git available", False, "Git command failed")
            return False
        
        branch = output.strip()
        is_main = branch == "main"
        self.log_check(
            "On main branch",
            is_main,
            f"Current branch: {branch}",
            is_critical=False
        )
        
        # Check for uncommitted changes
        success, output = self.run_command(["git", "status", "--porcelain"])
        has_changes = len(output.strip()) > 0
        self.log_check(
            "No uncommitted changes",
            not has_changes,
            f"{len(output.strip().splitlines())} files with changes" if has_changes else "Working tree clean",
            is_critical=False
        )
        
        # Check if up to date with origin
        self.run_command(["git", "fetch", "origin"])
        success, output = self.run_command(["git", "rev-list", "--count", "HEAD..origin/main"])
        if success:
            behind = int(output.strip()) if output.strip() else 0
            self.log_check(
                "Up to date with origin",
                behind == 0,
                f"{behind} commits behind" if behind > 0 else "Up to date",
                is_critical=False
            )
        
        return True
    
    def check_version_info(self) -> bool:
        """Check version information."""
        print("\n📦 Version Check")
        print("-" * 50)
        
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            self.log_check("package.json exists", False, "File not found")
            return False
        
        try:
            with open(package_json) as f:
                data = json.load(f)
                version = data.get("version", "unknown")
                self.log_check("Version found", True, f"v{version}")
                print(f"   Current version: v{version}")
                return True
        except Exception as e:
            self.log_check("Version check", False, str(e))
            return False
    
    def check_weekly_league_status(self) -> bool:
        """Check weekly league system."""
        print("\n🏆 Weekly League Status")
        print("-" * 50)
        
        script = self.project_root / "scripts" / "weekly-league-manager.py"
        if not script.exists():
            self.log_check("League manager exists", False, "Script not found")
            return False
        
        success, output = self.run_command([
            "python",
            str(script),
            "--status"
        ])
        
        if success:
            self.log_check("League system operational", True)
            print("   Current league status:")
            for line in output.split('\n')[:8]:  # Show first 8 lines
                if line.strip():
                    print(f"   {line}")
            return True
        else:
            self.log_check("League system operational", False, "Status check failed")
            return False
    
    def check_game_integration(self) -> bool:
        """Check game integration status."""
        print("\n🎮 Game Integration Check")
        print("-" * 50)
        
        script = self.project_root / "scripts" / "game-integration.py"
        if not script.exists():
            self.log_check("Game integration exists", False, "Script not found", is_critical=False)
            return False
        
        success, output = self.run_command([
            "python",
            str(script),
            "--status"
        ])
        
        if success:
            self.log_check("Game integration operational", True)
            # Show key lines from status
            for line in output.split('\n'):
                if 'Connected' in line or 'Last sync' in line or 'Status' in line:
                    print(f"   {line.strip()}")
            return True
        else:
            self.log_check(
                "Game integration operational",
                False,
                "Status check failed (may be normal if not configured)",
                is_critical=False
            )
            return False
    
    def run_health_checks(self) -> bool:
        """Run health checks."""
        print("\n🏥 Health Checks")
        print("-" * 50)
        
        script = self.project_root / "scripts" / "health-check.py"
        if not script.exists():
            self.log_check("Health check script exists", False, "Script not found", is_critical=False)
            return False
        
        success, output = self.run_command([
            "python",
            str(script)
        ])
        
        self.log_check(
            "Health checks passed",
            success,
            "Some checks failed" if not success else "All checks passed",
            is_critical=False
        )
        
        return success
    
    def run_deployment_verification(self) -> bool:
        """Run deployment verification."""
        print("\n✅ Deployment Verification")
        print("-" * 50)
        
        script = self.project_root / "scripts" / "verify-deployment.py"
        if not script.exists():
            self.log_check("Verification script exists", False, "Script not found")
            return False
        
        success, output = self.run_command([
            "python",
            str(script)
        ])
        
        self.log_check(
            "Deployment verification",
            success,
            "Some checks failed" if not success else "All checks passed"
        )
        
        return success
    
    def sync_game_data(self) -> bool:
        """Sync game data from repository."""
        if self.check_only:
            print("\n🎮 Game Data Sync")
            print("-" * 50)
            print("   ⏩ Skipped (check-only mode)")
            return True
        
        print("\n🎮 Game Data Sync")
        print("-" * 50)
        
        script = self.project_root / "scripts" / "game-integration.py"
        if not script.exists():
            self.log_check("Game integration script", False, "Not found", is_critical=False)
            return False
        
        # Sync all leaderboards
        print("   Syncing all leaderboards...")
        success1, output1 = self.run_command([
            "python",
            str(script),
            "--sync-leaderboards"
        ])
        self.log_check("Leaderboard sync", success1, is_critical=False)
        
        # Sync weekly league data
        print("   Syncing weekly league data...")
        success2, output2 = self.run_command([
            "python",
            str(script),
            "--weekly-sync"
        ])
        self.log_check("Weekly league sync", success2, is_critical=False)
        
        return success1 or success2
    
    def update_version_and_stats(self) -> bool:
        """Update version info and stats."""
        if self.check_only:
            print("\n📊 Version & Stats Update")
            print("-" * 50)
            print("   ⏩ Skipped (check-only mode)")
            return True
        
        print("\n📊 Version & Stats Update")
        print("-" * 50)
        
        # Update version info
        success1, _ = self.run_command(["npm", "run", "update:version"])
        self.log_check("Version info updated", success1, is_critical=False)
        
        # Update stats
        success2, _ = self.run_command(["npm", "run", "update:stats"])
        self.log_check("Stats updated", success2, is_critical=False)
        
        return success1 and success2
    
    def generate_deployment_report(self) -> Dict:
        """Generate deployment readiness report."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "warnings": self.warnings,
            "errors": self.errors,
            "deployment_ready": self.checks_failed == 0,
            "check_only_mode": self.check_only,
            "quick_mode": self.quick
        }
        
        report_file = self.project_root / "deployment-prep-report.json"
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report saved to: {report_file}")
        except Exception as e:
            print(f"\n⚠️  Could not save report: {e}")
        
        return report
    
    def print_summary(self):
        """Print deployment preparation summary."""
        print("\n" + "=" * 50)
        print("📋 DEPLOYMENT PREPARATION SUMMARY")
        print("=" * 50)
        print(f"✅ Checks passed: {self.checks_passed}")
        print(f"❌ Checks failed: {self.checks_failed}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        
        if self.errors:
            print("\n❌ Critical Errors:")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print("\n⚠️  Warnings (non-critical):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        print("\n" + "=" * 50)
        if self.checks_failed == 0:
            print("✅ READY FOR DEPLOYMENT!")
            print("=" * 50)
            print("\nNext steps:")
            print("1. Go to GitHub → Actions")
            print("2. Run 'Weekly Scheduled Deployment' workflow")
            print("3. Monitor deployment progress")
            print("4. Start Twitch stream at 16:30 AEST")
            return True
        else:
            print("❌ NOT READY FOR DEPLOYMENT")
            print("=" * 50)
            print("\nPlease fix the errors above before deploying.")
            return False
    
    def prepare(self) -> bool:
        """Run full preparation process."""
        print("🚀 Weekly Deployment Preparation")
        print("=" * 50)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'CHECK ONLY' if self.check_only else 'FULL PREPARATION'}")
        if self.quick:
            print("Quick mode: Enabled")
        print("=" * 50)
        
        # Run all checks
        self.check_git_status()
        self.check_version_info()
        self.check_weekly_league_status()
        self.check_game_integration()
        
        if not self.quick:
            self.run_health_checks()
            self.run_deployment_verification()
        
        # Run data sync operations
        if not self.check_only:
            self.sync_game_data()
            self.update_version_and_stats()
        
        # Generate report
        self.generate_deployment_report()
        
        # Print summary
        return self.print_summary()


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Prepare for weekly deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/prepare-weekly-deployment.py              # Full preparation
  python scripts/prepare-weekly-deployment.py --check-only # Just check
  python scripts/prepare-weekly-deployment.py --quick      # Quick check
        """
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check status, don't sync or update data"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip long-running checks"
    )
    
    args = parser.parse_args()
    
    prep = WeeklyDeploymentPrep(
        check_only=args.check_only,
        quick=args.quick
    )
    
    success = prep.prepare()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
