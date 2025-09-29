#!/usr/bin/env python3

"""
Comprehensive health check for pdoom1-website deployment
Validates critical files, data integrity, and system dependencies
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional


class HealthChecker:
    """Comprehensive health check system for website deployment"""
    
    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
        self.failed_tests: List[str] = []
        self.warnings: List[str] = []
        self.start_time = datetime.now()
        
        # Define critical paths
        self.base_dir = os.path.join(os.path.dirname(__file__), '..')
        self.public_dir = os.path.join(self.base_dir, 'public')
        self.data_dir = os.path.join(self.public_dir, 'data')
    
    def log_result(self, test_name: str, passed: bool, message: str = "", is_warning: bool = False) -> None:
        """Log a test result"""
        if is_warning:
            self.warnings.append(f"{test_name}: {message}")
        
        result: Dict[str, Any] = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'is_warning': is_warning
        }
        
        self.results.append(result)
        
        if not passed and not is_warning:
            self.failed_tests.append(f"{test_name}: {message}")
    
    def test_file_exists(self, filepath: str, test_name: str) -> bool:
        """Test if a critical file exists"""
        exists = os.path.exists(filepath)
        self.log_result(test_name, exists, 
                       f"✓ Found: {filepath}" if exists else f"✗ Missing: {filepath}")
        return exists
    
    def test_json_valid(self, filepath: str, test_name: str) -> bool:
        """Test if a JSON file is valid"""
        try:
            if not os.path.exists(filepath):
                self.log_result(test_name, False, f"File not found: {filepath}")
                return False
                
            with open(filepath, 'r', encoding='utf-8') as f:
                json.load(f)
            self.log_result(test_name, True, f"✓ Valid JSON: {filepath}")
            return True
        except json.JSONDecodeError as e:
            self.log_result(test_name, False, f"Invalid JSON: {filepath} - {e}")
            return False
        except Exception as e:
            self.log_result(test_name, False, f"Error reading {filepath}: {e}")
            return False
    
    def test_script_executable(self, script_path: str, test_name: str) -> bool:
        """Test if a script can be executed"""
        try:
            if not os.path.exists(script_path):
                self.log_result(test_name, False, f"Script not found: {script_path}")
                return False
            
            # Test Python script syntax
            result = subprocess.run([sys.executable, '-m', 'py_compile', script_path], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.log_result(test_name, True, f"✓ Script compiles: {script_path}")
                return True
            else:
                self.log_result(test_name, False, f"Compilation error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_result(test_name, False, f"Script compilation timeout: {script_path}")
            return False
        except Exception as e:
            self.log_result(test_name, False, f"Error testing script: {e}")
            return False
    
    def test_version_data_integrity(self) -> bool:
        """Test version data structure and content"""
        version_file = os.path.join(self.data_dir, 'version.json')
        
        try:
            if not os.path.exists(version_file):
                self.log_result("Version Data Structure", False, "version.json not found")
                return False
            
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check required fields
            required_fields = ['latest_release', 'repository_stats', 'game_stats', 'last_updated']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_result("Version Data Structure", False, 
                              f"Missing fields: {', '.join(missing_fields)}")
                return False
            
            # Check release data
            release = data['latest_release']
            release_fields = ['version', 'name', 'published_at', 'html_url']
            missing_release_fields = [field for field in release_fields if field not in release]
            
            if missing_release_fields:
                self.log_result("Release Data Structure", False,
                              f"Missing release fields: {', '.join(missing_release_fields)}")
                return False
            
            # Check game stats
            game_stats = data['game_stats']
            stats_fields = ['baseline_doom_percent', 'frontier_labs_count', 'strategic_possibilities']
            missing_stats_fields = [field for field in stats_fields if field not in game_stats]
            
            if missing_stats_fields:
                self.log_result("Game Stats Structure", False,
                              f"Missing stats fields: {', '.join(missing_stats_fields)}")
                return False
            
            self.log_result("Version Data Structure", True, "✓ All required fields present")
            
            # Validate data freshness (warn if older than 7 days)
            try:
                last_updated = datetime.fromisoformat(data['last_updated'].replace('Z', '+00:00'))
                age_days = (datetime.now() - last_updated.replace(tzinfo=None)).days
                
                if age_days > 7:
                    self.log_result("Data Freshness", True, 
                                  f"Data is {age_days} days old", is_warning=True)
                else:
                    self.log_result("Data Freshness", True, f"✓ Data is {age_days} days old")
            except Exception as e:
                self.log_result("Data Freshness", True, f"Could not parse timestamp: {e}", is_warning=True)
            
            return True
            
        except Exception as e:
            self.log_result("Version Data Structure", False, f"Error validating data: {e}")
            return False
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        print("🏥 Running comprehensive health checks...")
        print("=" * 50)
        
        # Critical file checks
        critical_files = [
            (os.path.join(self.public_dir, 'index.html'), "Main Index File"),
            (os.path.join(self.public_dir, 'config.json'), "Config File"),
            (os.path.join(self.data_dir, 'version.json'), "Version Data"),
            (os.path.join(self.data_dir, 'changes.json'), "Changelog Data"),
        ]
        
        for filepath, name in critical_files:
            self.test_file_exists(filepath, name)
        
        # JSON validation checks
        json_files = [
            (os.path.join(self.public_dir, 'config.json'), "Config JSON"),
            (os.path.join(self.data_dir, 'version.json'), "Version JSON"),
            (os.path.join(self.data_dir, 'changes.json'), "Changes JSON"),
        ]
        
        for filepath, name in json_files:
            if os.path.exists(filepath):
                self.test_json_valid(filepath, name)
        
        # Script validation checks
        script_files = [
            (os.path.join(self.base_dir, 'scripts', 'update-version-info.py'), "Version Update Script"),
            (os.path.join(self.base_dir, 'scripts', 'calculate-game-stats.py'), "Stats Calculation Script"),
        ]
        
        for filepath, name in script_files:
            self.test_script_executable(filepath, name)
        
        # Data integrity checks
        self.test_version_data_integrity()
        
        # Generate summary
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['passed']])
        warning_count = len(self.warnings)
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        summary = {
            'timestamp': end_time.isoformat(),
            'duration_seconds': duration,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'warnings': warning_count,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'overall_status': 'PASS' if len(self.failed_tests) == 0 else 'FAIL',
            'results': self.results,
            'failed_test_details': self.failed_tests,
            'warnings_details': self.warnings
        }
        
        # Save results to file
        results_file = os.path.join(self.data_dir, 'health-check-results.json')
        os.makedirs(self.data_dir, exist_ok=True)
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Print a human-readable summary"""
        print("\n" + "=" * 50)
        print("🏥 HEALTH CHECK SUMMARY")
        print("=" * 50)
        
        status_emoji = "✅" if summary['overall_status'] == 'PASS' else "❌"
        print(f"{status_emoji} Overall Status: {summary['overall_status']}")
        print(f"⏱️  Duration: {summary['duration_seconds']:.2f} seconds")
        print(f"📊 Success Rate: {summary['success_rate']:.1f}%")
        print(f"✅ Passed: {summary['passed_tests']}/{summary['total_tests']}")
        
        if summary['failed_tests'] > 0:
            print(f"❌ Failed: {summary['failed_tests']}")
            print("\n🚨 FAILED TESTS:")
            for failure in summary['failed_test_details']:
                print(f"   • {failure}")
        
        if summary['warnings'] > 0:
            print(f"\n⚠️  Warnings: {summary['warnings']}")
            print("⚠️  WARNING DETAILS:")
            for warning in summary['warnings_details']:
                print(f"   • {warning}")
        
        print(f"\n📄 Full results saved to: public/data/health-check-results.json")
        print("=" * 50)


def main() -> None:
    """Main execution function"""
    checker = HealthChecker()
    summary = checker.run_all_checks()
    checker.print_summary(summary)
    
    # Exit with error code if any tests failed
    if summary['overall_status'] == 'FAIL':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()